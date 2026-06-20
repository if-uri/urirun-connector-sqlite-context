from __future__ import annotations

import json
from importlib import resources
from typing import Any

import urirun


CONNECTOR_ID = "sqlite-context"
DATA = urirun.connector(CONNECTOR_ID, scheme="data")
ARTIFACT = urirun.connector(CONNECTOR_ID, scheme="artifact")
CHECK = urirun.connector(CONNECTOR_ID, scheme="check")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")


def _json_resource(name: str) -> dict[str, Any]:
    text = resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def connector_manifest() -> dict[str, Any]:
    return _json_resource("connector.manifest.json")


def _host_db():
    from urirun import host_db

    return host_db


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def list_datasets(db: str = "") -> dict[str, Any]:
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "datasets": _host_db().list_datasets(db or None)}


def create_dataset(db: str = "", name: str = "", description: str = "", schema: str = "") -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    dataset = _host_db().create_dataset(db or None, name, description, _json_value(schema, {"type": "object"}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "dataset": dataset}


def upsert_record(db: str = "", dataset: str = "", key: str = "", data: str = "", source_uri: str = "", confidence: float = 0.0) -> dict[str, Any]:
    if not dataset:
        raise ValueError("dataset is required")
    if not key:
        raise ValueError("key is required")
    record = _host_db().upsert_record(
        db or None,
        dataset,
        key,
        _json_value(data, {}),
        source_uri=source_uri or None,
        confidence=confidence or None,
    )
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "record": record}


def search_records(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> dict[str, Any]:
    records = _host_db().search_records(db or None, query, dataset=dataset or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "records": records}


def sql_read_only(db: str = "", query: str = "", params: str = "", limit: int = 100) -> dict[str, Any]:
    rows = _host_db().read_only_sql(db or None, query, _json_value(params, []), int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "rows": rows}


def register_artifact(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> dict[str, Any]:
    if not kind:
        raise ValueError("kind is required")
    if not uri:
        raise ValueError("uri is required")
    artifact = _host_db().register_artifact(db or None, kind, uri, path or None, _json_value(meta, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "artifact": artifact}


def list_artifacts(db: str = "", kind: str = "", limit: int = 20) -> dict[str, Any]:
    artifacts = _host_db().list_artifacts(db or None, kind=kind or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "artifacts": artifacts}


def add_check(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> dict[str, Any]:
    if not subject:
        raise ValueError("subject is required")
    if not check_uri:
        raise ValueError("check_uri is required")
    if not status:
        raise ValueError("status is required")
    check = _host_db().add_check(db or None, subject, check_uri, status, _json_value(result, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "check": check}


def recent_checks(db: str = "", subject: str = "", limit: int = 20) -> dict[str, Any]:
    checks = _host_db().recent_checks(db or None, subject=subject or None, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "checks": checks}


def log_write(db: str = "", stream: str = "default", event: str = "", detail: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    log = _host_db().add_log(db or None, stream, event, _json_value(detail, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", "log": log}


def recent_logs(db: str = "", stream: str = "", limit: int = 20) -> dict[str, Any]:
    logs = _host_db().recent_logs(db or None, stream=stream or None, limit=int(limit))
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
