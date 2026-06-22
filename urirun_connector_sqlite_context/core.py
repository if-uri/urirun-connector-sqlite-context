# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""SQLite context connector.

Thin wrapper over urirun's host SQLite backend (``urirun.host.host_db``): the
connector owns the URI route declarations and the JSON envelope, while the actual
storage logic lives once in the urirun backend. This keeps urirun the single
source of truth and avoids duplicating the sqlite implementation.

Each route is declared once with a typed ``@<scheme>.handler(..., isolated=True)``:
the function signature becomes the input schema and the body is the
implementation -- no argv template, no ``_exec.py``, no ``run_action`` dispatcher.
``isolated=True`` runs each route out-of-process through the shared
``python -m urirun.exec`` runner, so the binding stays **registry-portable**: it
executes from a compiled/served registry (``urirun run`` / ``urirun node serve``)
with only the package importable -- no console-script install and no per-connector
shim.

The manifest stays prose-only; ``routes``/``uriSchemes`` are derived from the
declared routes.
"""

from __future__ import annotations

import json
from typing import Any

import urirun
from urirun.host import host_db

CONNECTOR_ID = "sqlite-context"
DATA = urirun.connector(CONNECTOR_ID, scheme="data")
ARTIFACT = urirun.connector(CONNECTOR_ID, scheme="artifact")
CHECK = urirun.connector(CONNECTOR_ID, scheme="check")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _ok(**fields: Any) -> dict[str, Any]:
    return {"ok": True, "connector": CONNECTOR_ID, "type": "host-db", **fields}


# --- route handlers: schema + implementation all derived ------------------
# Each handler delegates to the urirun.host.host_db backend so the storage
# logic lives once in the runtime. ``isolated=True`` keeps every route
# registry-portable (runs out-of-process via ``python -m urirun.exec``).

@DATA.handler("datasets/query/list", isolated=True, meta={"label": "List datasets", "cliAlias": "datasets-list"})
def list_datasets(db: str = "") -> dict[str, Any]:
    return _ok(datasets=host_db.list_datasets(db or None))


@DATA.handler("dataset/command/create", isolated=True, meta={"label": "Create dataset", "cliAlias": "dataset-create"})
def create_dataset(db: str = "", name: str = "", description: str = "", dataset_schema: str = "") -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    return _ok(dataset=host_db.create_dataset(db or None, name, description, _json_value(dataset_schema, {"type": "object"})))


@DATA.handler("record/command/upsert", isolated=True, meta={"label": "Upsert record", "cliAlias": "record-upsert"})
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


@DATA.handler("records/query/search", isolated=True, meta={"label": "Search records", "cliAlias": "records-search"})
def search_records(db: str = "", query: str = "", dataset: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(records=host_db.search_records(db or None, query, dataset=dataset or None, limit=int(limit)))


@DATA.handler("sql/query/read-only", isolated=True, meta={"label": "Read-only SQL", "cliAlias": "sql-read-only"})
def sql_read_only(db: str = "", query: str = "", params: str = "", limit: int = 100) -> dict[str, Any]:
    return _ok(rows=host_db.read_only_sql(db or None, query, _json_value(params, []), int(limit)))


@ARTIFACT.handler("artifact/command/register", isolated=True, meta={"label": "Register artifact", "cliAlias": "artifact-register"})
def register_artifact(db: str = "", kind: str = "", uri: str = "", path: str = "", meta: str = "") -> dict[str, Any]:
    if not kind:
        raise ValueError("kind is required")
    if not uri:
        raise ValueError("uri is required")
    return _ok(artifact=host_db.register_artifact(db or None, kind, uri, path or None, _json_value(meta, {})))


@ARTIFACT.handler("artifacts/query/list", isolated=True, meta={"label": "List artifacts", "cliAlias": "artifacts-list"})
def list_artifacts(db: str = "", kind: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(artifacts=host_db.list_artifacts(db or None, kind=kind or None, limit=int(limit)))


@CHECK.handler("check/command/add", isolated=True, meta={"label": "Add check", "cliAlias": "check-add"})
def add_check(db: str = "", subject: str = "", check_uri: str = "", status: str = "", result: str = "") -> dict[str, Any]:
    if not subject:
        raise ValueError("subject is required")
    if not check_uri:
        raise ValueError("check_uri is required")
    if not status:
        raise ValueError("status is required")
    return _ok(check=host_db.add_check(db or None, subject, check_uri, status, _json_value(result, {})))


@CHECK.handler("checks/query/recent", isolated=True, meta={"label": "Recent checks", "cliAlias": "checks-recent"})
def recent_checks(db: str = "", subject: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(checks=host_db.recent_checks(db or None, subject=subject or None, limit=int(limit)))


@LOG.handler("logs/query/recent", isolated=True, meta={"label": "Recent logs", "cliAlias": "logs-recent"})
def recent_logs(db: str = "", stream: str = "", limit: int = 20) -> dict[str, Any]:
    return _ok(logs=host_db.recent_logs(db or None, stream=stream or None, limit=int(limit)))


@LOG.handler("daily/command/write", isolated=True, meta={"label": "Write daily log", "cliAlias": "log-write"})
def log_write(db: str = "", stream: str = "daily", event: str = "", detail: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    return _ok(log=host_db.add_log(db or None, stream, event, _json_value(detail, {})))


# --- authoring surface: bindings / manifest / CLI --------------------------
# Every connector object shares CONNECTOR_ID, so these aggregate all routes
# (data/artifact/check/log) regardless of which object we call them on.

def urirun_bindings() -> dict[str, Any]:
    """Serializable v2 bindings for this connector (entry point: urirun.bindings)."""
    return DATA.bindings()


def connector_manifest() -> dict[str, Any]:
    """Full manifest: prose (connector.manifest.json) + routes/uriSchemes/
    adapterKinds/examples derived from the handlers."""
    return DATA.manifest(urirun.load_manifest(__package__))


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point: subcommands + dispatch derived from the handlers."""
    return DATA.cli(argv, manifest_prose=urirun.load_manifest(__package__))


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
