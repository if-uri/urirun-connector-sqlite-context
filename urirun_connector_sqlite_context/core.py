# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

import urirun


CONNECTOR_ID = "sqlite-context"
DATA = urirun.connector(CONNECTOR_ID, scheme="data")
ARTIFACT = urirun.connector(CONNECTOR_ID, scheme="artifact")
CHECK = urirun.connector(CONNECTOR_ID, scheme="check")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")
DEFAULT_DB = "~/.urirun/host.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  schema_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_uri TEXT,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(dataset_id, key)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  uri TEXT NOT NULL UNIQUE,
  path TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checks (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  check_uri TEXT NOT NULL,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  stream TEXT NOT NULL,
  event TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
"""


def _json_resource(name: str) -> dict[str, Any]:
    text = resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def connector_manifest() -> dict[str, Any]:
    return _json_resource("connector.manifest.json")


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _db_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_HOST_DB", DEFAULT_DB)).expanduser()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _connect(path: str | None = None) -> sqlite3.Connection:
    resolved = _db_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _connection(path: str | None = None):
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("schema_json", "data_json", "meta_json", "result_json", "detail_json"):
        if key in data and data[key] is not None:
            try:
                data[key.removesuffix("_json")] = json.loads(data.pop(key))
            except json.JSONDecodeError:
                pass
    return data


def _rows_dict(rows) -> list[dict]:
    return [_row_dict(row) for row in rows]


def _init_db(path: str | None = None) -> dict[str, Any]:
    with _connection(path) as conn:
        conn.executescript(SCHEMA)
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS records_fts "
                "USING fts5(record_id UNINDEXED, dataset_id UNINDEXED, key, data_text, source_uri)"
            )
            fts = True
        except sqlite3.OperationalError:
            fts = False
    return {"ok": True, "path": str(_db_path(path)), "fts": fts}


def _schema_json(schema: dict | None) -> str:
    schema = schema or {"type": "object"}
    Draft202012Validator.check_schema(schema)
    return json.dumps(schema, sort_keys=True)


def _get_dataset(path: str | None, name_or_id: str) -> dict:
    _init_db(path)
    with _connection(path) as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ? OR name = ?", (name_or_id, name_or_id)).fetchone()
    if not row:
        raise ValueError(f"dataset not found: {name_or_id}")
    return _row_dict(row)


def _validate_record(dataset: dict, data: dict) -> None:
    Draft202012Validator(dataset.get("schema") or {"type": "object"}).validate(data)


def _sync_record_fts(conn: sqlite3.Connection, record: dict, dataset_id: str) -> None:
    try:
        conn.execute("DELETE FROM records_fts WHERE record_id = ?", (record["id"],))
        conn.execute(
            "INSERT INTO records_fts(record_id, dataset_id, key, data_text, source_uri) VALUES(?, ?, ?, ?, ?)",
            (
                record["id"],
                dataset_id,
                record["key"],
                json.dumps(record["data"], sort_keys=True, ensure_ascii=False),
                record.get("source_uri") or "",
            ),
        )
    except sqlite3.OperationalError:
        return


def _list_datasets(path: str | None = None) -> list[dict]:
    _init_db(path)
    with _connection(path) as conn:
        return _rows_dict(conn.execute("SELECT * FROM datasets ORDER BY name").fetchall())


def _create_dataset(path: str | None, name: str, description: str = "", schema: dict | None = None) -> dict:
    _init_db(path)
    dataset_id = _new_id("ds")
    created_at = _now_iso()
    with _connection(path) as conn:
        conn.execute(
            """
            INSERT INTO datasets(id, name, description, schema_json, created_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET description=excluded.description, schema_json=excluded.schema_json
            """,
            (dataset_id, name, description, _schema_json(schema), created_at),
        )
    return _get_dataset(path, name)


def _upsert_record(path: str | None, dataset: str, key: str, data: dict, *, source_uri: str | None = None, confidence: float | None = None) -> dict:
    _init_db(path)
    dataset_row = _get_dataset(path, dataset)
    _validate_record(dataset_row, data)
    timestamp = _now_iso()
    record_id = _new_id("rec")
    data_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
    with _connection(path) as conn:
        conn.execute(
            """
            INSERT INTO records(id, dataset_id, key, data_json, source_uri, confidence, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id, key) DO UPDATE SET
              data_json=excluded.data_json,
              source_uri=excluded.source_uri,
              confidence=excluded.confidence,
              updated_at=excluded.updated_at
            """,
            (record_id, dataset_row["id"], key, data_json, source_uri, confidence, timestamp, timestamp),
        )
        row = conn.execute("SELECT * FROM records WHERE dataset_id = ? AND key = ?", (dataset_row["id"], key)).fetchone()
        record = _row_dict(row)
        _sync_record_fts(conn, record, dataset_row["id"])
        return record


def _search_records(path: str | None, query: str = "", dataset: str | None = None, limit: int = 20) -> list[dict]:
    _init_db(path)
    params: list[Any] = []
    where = []
    if dataset:
        dataset_row = _get_dataset(path, dataset)
        where.append("r.dataset_id = ?")
        params.append(dataset_row["id"])
    with _connection(path) as conn:
        if query:
            try:
                fts_params = list(params)
                fts_where = list(where)
                fts_where.append("records_fts MATCH ?")
                fts_params.append(query)
                sql = "SELECT r.*, d.name AS dataset_name FROM records r JOIN datasets d ON d.id = r.dataset_id JOIN records_fts ON records_fts.record_id = r.id"
                if fts_where:
                    sql += " WHERE " + " AND ".join(fts_where)
                sql += " ORDER BY r.updated_at DESC LIMIT ?"
                fts_params.append(limit)
                return _rows_dict(conn.execute(sql, fts_params).fetchall())
            except sqlite3.OperationalError:
                where.append("(r.key LIKE ? OR r.data_json LIKE ? OR COALESCE(r.source_uri, '') LIKE ?)")
                needle = f"%{query}%"
                params.extend([needle, needle, needle])
        sql = "SELECT r.*, d.name AS dataset_name FROM records r JOIN datasets d ON d.id = r.dataset_id"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY r.updated_at DESC LIMIT ?"
        params.append(limit)
        return _rows_dict(conn.execute(sql, params).fetchall())


def _read_only_sql(path: str | None, query: str, params: list[Any] | None = None, limit: int = 100) -> list[dict]:
    _init_db(path)
    stripped = query.strip().rstrip(";")
    lowered = stripped.lower()
    if not (lowered.startswith("select ") or lowered.startswith("with ")):
        raise ValueError("only SELECT/WITH read-only SQL is allowed")
    if ";" in stripped:
        raise ValueError("multiple SQL statements are not allowed")
    with _connection(path) as conn:
        return _rows_dict(conn.execute(stripped + f" LIMIT {int(limit)}", params or []).fetchall())


def _register_artifact(path: str | None, kind: str, uri: str, artifact_path: str | None = None, meta: dict | None = None) -> dict:
    _init_db(path)
    artifact_id = _new_id("art")
    with _connection(path) as conn:
        conn.execute(
            """
            INSERT INTO artifacts(id, kind, uri, path, meta_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(uri) DO UPDATE SET kind=excluded.kind, path=excluded.path, meta_json=excluded.meta_json
            """,
            (artifact_id, kind, uri, artifact_path, json.dumps(meta or {}, sort_keys=True), _now_iso()),
        )
        return _row_dict(conn.execute("SELECT * FROM artifacts WHERE uri = ?", (uri,)).fetchone())


def _list_artifacts(path: str | None = None, kind: str | None = None, limit: int = 20) -> list[dict]:
    _init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM artifacts"
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connection(path) as conn:
        return _rows_dict(conn.execute(sql, params).fetchall())


def _add_check(path: str | None, subject: str, check_uri: str, status: str, result: dict | None = None) -> dict:
    _init_db(path)
    check_id = _new_id("chk")
    with _connection(path) as conn:
        conn.execute(
            "INSERT INTO checks(id, subject, check_uri, status, result_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
            (check_id, subject, check_uri, status, json.dumps(result or {}, sort_keys=True), _now_iso()),
        )
        return _row_dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone())


def _recent_checks(path: str | None = None, subject: str | None = None, limit: int = 20) -> list[dict]:
    _init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM checks"
    if subject:
        sql += " WHERE subject = ?"
        params.append(subject)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connection(path) as conn:
        return _rows_dict(conn.execute(sql, params).fetchall())


def _add_log(path: str | None, stream: str, event: str, detail: dict | None = None) -> dict:
    _init_db(path)
    log_id = _new_id("log")
    with _connection(path) as conn:
        conn.execute(
            "INSERT INTO logs(id, stream, event, detail_json, created_at) VALUES(?, ?, ?, ?, ?)",
            (log_id, stream, event, json.dumps(detail or {}, sort_keys=True), _now_iso()),
        )
        return _row_dict(conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone())


def _recent_logs(path: str | None = None, stream: str | None = None, limit: int = 20) -> list[dict]:
    _init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM logs"
    if stream:
        sql += " WHERE stream = ?"
        params.append(stream)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connection(path) as conn:
        return _rows_dict(conn.execute(sql, params).fetchall())


def list_datasets(db: str = "") -> dict[str, Any]:
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "datasets": _list_datasets(db or None)}


def create_dataset(db: str = "", name: str = "", description: str = "", schema: str = "") -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    dataset = _create_dataset(db or None, name, description, _json_value(schema, {"type": "object"}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "dataset": dataset}


def upsert_record(db: str = "", dataset: str = "", key: str = "", data: str = "", source_uri: str = "", confidence: float = 0.0) -> dict[str, Any]:
    if not dataset:
        raise ValueError("dataset is required")
    if not key:
        raise ValueError("key is required")
    record = _upsert_record(
        db or None,
        dataset,
        key,
        _json_value(data, {}),
        source_uri=source_uri or None,
        confidence=confidence or None,
    )
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "record": record}


def search_records(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> dict[str, Any]:
    records = _search_records(db or None, query, dataset=dataset or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "records": records}


def sql_read_only(db: str = "", query: str = "", params: str = "", limit: int = 100) -> dict[str, Any]:
    rows = _read_only_sql(db or None, query, _json_value(params, []), int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "rows": rows}


def register_artifact(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> dict[str, Any]:
    if not kind:
        raise ValueError("kind is required")
    if not uri:
        raise ValueError("uri is required")
    artifact = _register_artifact(db or None, kind, uri, path or None, _json_value(meta, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "artifact": artifact}


def list_artifacts(db: str = "", kind: str = "", limit: int = 20) -> dict[str, Any]:
    artifacts = _list_artifacts(db or None, kind=kind or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "artifacts": artifacts}


def add_check(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> dict[str, Any]:
    if not subject:
        raise ValueError("subject is required")
    if not check_uri:
        raise ValueError("check_uri is required")
    if not status:
        raise ValueError("status is required")
    check = _add_check(db or None, subject, check_uri, status, _json_value(result, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "check": check}


def recent_checks(db: str = "", subject: str = "", limit: int = 20) -> dict[str, Any]:
    checks = _recent_checks(db or None, subject=subject or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "checks": checks}


def log_write(db: str = "", stream: str = "default", event: str = "", detail: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    log = _add_log(db or None, stream, event, _json_value(detail, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "log": log}


def recent_logs(db: str = "", stream: str = "", limit: int = 20) -> dict[str, Any]:
    logs = _recent_logs(db or None, stream=stream or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "logs": logs}


def run_action(action: str, **kwargs: Any) -> dict[str, Any]:
    table = {
        "datasets-list": list_datasets,
        "dataset-create": create_dataset,
        "record-upsert": upsert_record,
        "records-search": search_records,
        "sql-read-only": sql_read_only,
        "artifact-register": register_artifact,
        "artifacts-list": list_artifacts,
        "check-add": add_check,
        "checks-recent": recent_checks,
        "log-write": log_write,
        "logs-recent": recent_logs,
    }
    if action not in table:
        raise ValueError(f"unsupported action: {action}")
    return table[action](**kwargs)


@DATA.command("datasets/query/list", meta={"label": "List datasets"})
def datasets_list_command(db: str = "") -> list[str]:
    return ["urirun-sqlite-context", "datasets-list", "--db", "{db}"]


@DATA.command("dataset/command/create", meta={"label": "Create dataset"})
def dataset_create_command(db: str = "", name: str = "", description: str = "", dataset_schema: str = "") -> list[str]:
    return ["urirun-sqlite-context", "dataset-create", "--db", "{db}", "--name", "{name}", "--description", "{description}", "--schema", "{dataset_schema}"]


@DATA.command("record/command/upsert", meta={"label": "Upsert record"})
def record_upsert_command(db: str = "", dataset: str = "", key: str = "", data: str = "", source_uri: str = "", confidence: float = 0.0) -> list[str]:
    return ["urirun-sqlite-context", "record-upsert", "--db", "{db}", "--dataset", "{dataset}", "--key", "{key}", "--data", "{data}", "--source-uri", "{source_uri}", "--confidence", "{confidence}"]


@DATA.command("records/query/search", meta={"label": "Search records"})
def records_search_command(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> list[str]:
    return ["urirun-sqlite-context", "records-search", "--db", "{db}", "--query", "{query}", "--dataset", "{dataset}", "--limit", "{limit}"]


@DATA.command("sql/query/read-only", meta={"label": "Read-only SQL"})
def sql_read_only_command(db: str = "", query: str = "", params: str = "", limit: int = 100) -> list[str]:
    return ["urirun-sqlite-context", "sql-read-only", "--db", "{db}", "--query", "{query}", "--params", "{params}", "--limit", "{limit}"]


@ARTIFACT.command("artifact/command/register", meta={"label": "Register artifact"})
def artifact_register_command(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> list[str]:
    return ["urirun-sqlite-context", "artifact-register", "--db", "{db}", "--kind", "{kind}", "--uri", "{uri}", "--path", "{path}", "--meta", "{meta}"]


@ARTIFACT.command("artifacts/query/list", meta={"label": "List artifacts"})
def artifacts_list_command(db: str = "", kind: str = "", limit: int = 20) -> list[str]:
    return ["urirun-sqlite-context", "artifacts-list", "--db", "{db}", "--kind", "{kind}", "--limit", "{limit}"]


@CHECK.command("check/command/add", meta={"label": "Add check"})
def check_add_command(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> list[str]:
    return ["urirun-sqlite-context", "check-add", "--db", "{db}", "--subject", "{subject}", "--check-uri", "{check_uri}", "--status", "{status}", "--result", "{result}"]


@CHECK.command("checks/query/recent", meta={"label": "Recent checks"})
def checks_recent_command(db: str = "", subject: str = "", limit: int = 20) -> list[str]:
    return ["urirun-sqlite-context", "checks-recent", "--db", "{db}", "--subject", "{subject}", "--limit", "{limit}"]


@LOG.command("logs/query/recent", meta={"label": "Recent logs"})
def logs_recent_command(db: str = "", stream: str = "", limit: int = 20) -> list[str]:
    return ["urirun-sqlite-context", "logs-recent", "--db", "{db}", "--stream", "{stream}", "--limit", "{limit}"]


@LOG.command("daily/command/write", meta={"label": "Write daily log"})
def log_write_command(db: str = "", stream: str = "daily", event: str = "", detail: str = "") -> list[str]:
    return ["urirun-sqlite-context", "log-write", "--db", "{db}", "--stream", "{stream}", "--event", "{event}", "--detail", "{detail}"]


def urirun_bindings() -> dict[str, Any]:
    return urirun.connector_bindings(connector=CONNECTOR_ID)
