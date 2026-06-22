# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""SQLite context connector.

Thin wrapper over urirun's host SQLite backend (``urirun.host.host_db``): the
connector owns the URI route declarations and the JSON envelope, while the actual
storage logic lives once in the urirun backend. This keeps urirun the single
source of truth and avoids duplicating the sqlite implementation.

Each route is declared once with ``@<scheme>.command``: the function signature
becomes the input schema and the body returns the ``argv`` template urirun runs.
The template invokes this package's ``_exec`` module out-of-process, so the route
works through the file-based registry CLI (``urirun compile`` / ``urirun run``) —
no console-script install needed — as well as the in-process Python helpers that
``_exec`` (and the tests) call directly via ``run_action``.

The manifest stays prose-only; ``routes``/``uriSchemes`` are derived from the
declared routes.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import urirun
from urirun.host import host_db

CONNECTOR_ID = "sqlite-context"
DATA = urirun.connector(CONNECTOR_ID, scheme="data")
ARTIFACT = urirun.connector(CONNECTOR_ID, scheme="artifact")
CHECK = urirun.connector(CONNECTOR_ID, scheme="check")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")

# argv prefix the compiled registry uses to execute a route out-of-process.
_EXEC = ["python3", "-m", "urirun_connector_sqlite_context._exec"]


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", **fields}


# --- operations: delegate to the urirun.host.host_db backend ---

def list_datasets(db: str = "") -> dict[str, Any]:
    return _ok(datasets=host_db.list_datasets(db or None))


def create_dataset(db: str = "", name: str = "", description: str = "", schema: str = "") -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    return _ok(dataset=host_db.create_dataset(db or None, name, description, _json_value(schema, {"type": "object"})))


def upsert_record(db: str = "", dataset: str = "", key: str = "", data: str = "", source_uri: str = "", confidence: float = 0.0) -> dict[str, Any]:
    if not dataset:
        raise ValueError("dataset is required")
    if not key:
        raise ValueError("key is required")
    record = host_db.upsert_record(
        db or None, dataset, key, _json_value(data, {}),
        source_uri=source_uri or None, confidence=confidence or None,
    )
    return _ok(record=record)


def search_records(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(records=host_db.search_records(db or None, query, dataset=dataset or None, limit=int(limit)))


def sql_read_only(db: str = "", query: str = "", params: str = "", limit: int = 100) -> dict[str, Any]:
    return _ok(rows=host_db.read_only_sql(db or None, query, _json_value(params, []), int(limit)))


def register_artifact(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> dict[str, Any]:
    if not kind:
        raise ValueError("kind is required")
    if not uri:
        raise ValueError("uri is required")
    return _ok(artifact=host_db.register_artifact(db or None, kind, uri, path or None, _json_value(meta, {})))


def list_artifacts(db: str = "", kind: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(artifacts=host_db.list_artifacts(db or None, kind=kind or None, limit=int(limit)))


def add_check(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> dict[str, Any]:
    if not subject:
        raise ValueError("subject is required")
    if not check_uri:
        raise ValueError("check_uri is required")
    if not status:
        raise ValueError("status is required")
    return _ok(check=host_db.add_check(db or None, subject, check_uri, status, _json_value(result, {})))


def recent_checks(db: str = "", subject: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(checks=host_db.recent_checks(db or None, subject=subject or None, limit=int(limit)))


def log_write(db: str = "", stream: str = "default", event: str = "", detail: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    return _ok(log=host_db.add_log(db or None, stream, event, _json_value(detail, {})))


def recent_logs(db: str = "", stream: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(logs=host_db.recent_logs(db or None, stream=stream or None, limit=int(limit)))


# --- shared dispatch (CLI execute path + out-of-process _exec) -------------

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


# --- route declarations: schema + argv template all derived ---------------

@DATA.command("datasets/query/list", meta={"label": "List datasets", "cliAlias": "datasets-list"})
def datasets_list_command(db: str = "") -> list[str]:
    return [*_EXEC, "datasets-list", "--db", "{db}"]


@DATA.command("dataset/command/create", meta={"label": "Create dataset", "cliAlias": "dataset-create"})
def dataset_create_command(db: str = "", name: str = "", description: str = "", dataset_schema: str = "") -> list[str]:
    return [*_EXEC, "dataset-create", "--db", "{db}", "--name", "{name}", "--description", "{description}", "--schema", "{dataset_schema}"]


@DATA.command("record/command/upsert", meta={"label": "Upsert record", "cliAlias": "record-upsert"})
def record_upsert_command(db: str = "", dataset: str = "", key: str = "", data: str = "", source_uri: str = "", confidence: float = 0.0) -> list[str]:
    return [*_EXEC, "record-upsert", "--db", "{db}", "--dataset", "{dataset}", "--key", "{key}", "--data", "{data}", "--source-uri", "{source_uri}", "--confidence", "{confidence}"]


@DATA.command("records/query/search", meta={"label": "Search records", "cliAlias": "records-search"})
def records_search_command(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> list[str]:
    return [*_EXEC, "records-search", "--db", "{db}", "--query", "{query}", "--dataset", "{dataset}", "--limit", "{limit}"]


@DATA.command("sql/query/read-only", meta={"label": "Read-only SQL", "cliAlias": "sql-read-only"})
def sql_read_only_command(db: str = "", query: str = "", params: str = "", limit: int = 100) -> list[str]:
    return [*_EXEC, "sql-read-only", "--db", "{db}", "--query", "{query}", "--params", "{params}", "--limit", "{limit}"]


@ARTIFACT.command("artifact/command/register", meta={"label": "Register artifact", "cliAlias": "artifact-register"})
def artifact_register_command(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> list[str]:
    return [*_EXEC, "artifact-register", "--db", "{db}", "--kind", "{kind}", "--uri", "{uri}", "--path", "{path}", "--meta", "{meta}"]


@ARTIFACT.command("artifacts/query/list", meta={"label": "List artifacts", "cliAlias": "artifacts-list"})
def artifacts_list_command(db: str = "", kind: str = "", limit: int = 20) -> list[str]:
    return [*_EXEC, "artifacts-list", "--db", "{db}", "--kind", "{kind}", "--limit", "{limit}"]


@CHECK.command("check/command/add", meta={"label": "Add check", "cliAlias": "check-add"})
def check_add_command(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> list[str]:
    return [*_EXEC, "check-add", "--db", "{db}", "--subject", "{subject}", "--check-uri", "{check_uri}", "--status", "{status}", "--result", "{result}"]


@CHECK.command("checks/query/recent", meta={"label": "Recent checks", "cliAlias": "checks-recent"})
def checks_recent_command(db: str = "", subject: str = "", limit: int = 20) -> list[str]:
    return [*_EXEC, "checks-recent", "--db", "{db}", "--subject", "{subject}", "--limit", "{limit}"]


@LOG.command("logs/query/recent", meta={"label": "Recent logs", "cliAlias": "logs-recent"})
def logs_recent_command(db: str = "", stream: str = "", limit: int = 20) -> list[str]:
    return [*_EXEC, "logs-recent", "--db", "{db}", "--stream", "{stream}", "--limit", "{limit}"]


@LOG.command("daily/command/write", meta={"label": "Write daily log", "cliAlias": "log-write"})
def log_write_command(db: str = "", stream: str = "daily", event: str = "", detail: str = "") -> list[str]:
    return [*_EXEC, "log-write", "--db", "{db}", "--stream", "{stream}", "--event", "{event}", "--detail", "{detail}"]


# --- authoring surface: bindings / manifest / CLI --------------------------

def urirun_bindings() -> dict[str, Any]:
    return urirun.connector_bindings(connector=CONNECTOR_ID)


def connector_manifest() -> dict[str, Any]:
    """Manifest prose (connector.manifest.json) merged with the derived route set."""
    text = resources.files(__package__).joinpath("connector.manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    bindings = urirun_bindings()["bindings"]
    manifest["routes"] = sorted(bindings)
    manifest["uriSchemes"] = sorted({uri.split("://", 1)[0] for uri in bindings})
    return manifest


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point: ``bindings``/``manifest`` plus the route
    subcommands (delegated to the out-of-process executor)."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "bindings":
        print(json.dumps(urirun_bindings(), indent=2))
        return 0
    if args and args[0] == "manifest":
        print(json.dumps(connector_manifest(), indent=2))
        return 0
    from ._exec import main as _exec_main

    return _exec_main(args)


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
