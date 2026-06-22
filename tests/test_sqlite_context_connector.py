# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import urirun
from urirun import v2
from urirun_connector_sqlite_context import (
    connector_manifest,
    create_dataset,
    list_datasets,
    log_write,
    search_records,
    upsert_record,
    urirun_bindings,
)
from urirun_connector_sqlite_context.core import main

SCHEMA = {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}}

ROUTE_DATASETS_LIST = "data://host/datasets/query/list"
ROUTE_DATASET_CREATE = "data://host/dataset/command/create"
ROUTE_RECORD_UPSERT = "data://host/record/command/upsert"
ROUTE_RECORDS_SEARCH = "data://host/records/query/search"
ROUTE_SQL_READ_ONLY = "data://host/sql/query/read-only"
ROUTE_ARTIFACT_REGISTER = "artifact://host/artifact/command/register"
ROUTE_ARTIFACTS_LIST = "artifact://host/artifacts/query/list"
ROUTE_CHECK_ADD = "check://host/check/command/add"
ROUTE_CHECKS_RECENT = "check://host/checks/query/recent"
ROUTE_LOGS_RECENT = "log://host/logs/query/recent"
ROUTE_LOG_WRITE = "log://host/daily/command/write"

ALL_ROUTES = {
    ROUTE_DATASETS_LIST,
    ROUTE_DATASET_CREATE,
    ROUTE_RECORD_UPSERT,
    ROUTE_RECORDS_SEARCH,
    ROUTE_SQL_READ_ONLY,
    ROUTE_ARTIFACT_REGISTER,
    ROUTE_ARTIFACTS_LIST,
    ROUTE_CHECK_ADD,
    ROUTE_CHECKS_RECENT,
    ROUTE_LOGS_RECENT,
    ROUTE_LOG_WRITE,
}


def _registry():
    return v2.compile_registry(urirun_bindings())


# --- real impl functions called directly ---

def test_direct_dataset_record_and_log() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        dataset = create_dataset(db=db, name="domains", dataset_schema=json.dumps(SCHEMA))
        assert dataset["ok"] is True

        record = upsert_record(db=db, dataset="domains", key="ifuri.com", data=json.dumps({"domain": "ifuri.com"}))
        assert record["record"]["key"] == "ifuri.com"

        found = search_records(db=db, query="ifuri", dataset="domains")
        assert found["records"][0]["key"] == "ifuri.com"

        written = log_write(db=db, stream="daily", event="test.finished", detail=json.dumps({"ok": True}))
        assert written["log"]["event"] == "test.finished"


def test_direct_datasets_list_offline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        result = list_datasets(db=db)
        assert result["ok"] is True
        assert isinstance(result["datasets"], list)


# --- v2 authoring contract: isolated handlers (registry-portable) ---

def test_bindings_are_isolated_handlers() -> None:
    b = urirun_bindings()["bindings"]
    assert set(b) == ALL_ROUTES
    module = "urirun_connector_sqlite_context.core"
    for route, export in (
        (ROUTE_DATASETS_LIST, "list_datasets"),
        (ROUTE_DATASET_CREATE, "create_dataset"),
        (ROUTE_RECORD_UPSERT, "upsert_record"),
        (ROUTE_ARTIFACT_REGISTER, "register_artifact"),
        (ROUTE_CHECK_ADD, "add_check"),
        (ROUTE_LOG_WRITE, "log_write"),
    ):
        # registry-portable in-process handler: runs out-of-process via urirun.exec
        assert b[route]["adapter"] == "local-function-subprocess", route
        assert b[route]["python"]["module"] == module, route
        assert b[route]["python"]["export"] == export, route
        assert "argv" not in b[route], route
    # derived input schema preserved (old contract params)
    assert "dataset_schema" in b[ROUTE_DATASET_CREATE]["inputSchema"]["properties"]
    assert b[ROUTE_LOG_WRITE]["inputSchema"]["properties"]["stream"]["default"] == "daily"
    json.dumps(urirun_bindings())  # serializable: no live ref leaks


def test_compile_registry_routes_present() -> None:
    uris = {route["uri"] for route in v2.list_routes(_registry())}
    assert ALL_ROUTES <= uris


def test_manifest_derived_routes_and_schemes() -> None:
    manifest = connector_manifest()
    assert manifest["id"] == "sqlite-context"
    assert set(manifest["routes"]) == ALL_ROUTES
    assert manifest["uriSchemes"] == sorted(["data", "artifact", "check", "log"])
    assert manifest["summary"]  # prose preserved
    assert manifest["install"]["mode"] == "urirun-extra"
    json.dumps(manifest)


def test_runtime_executes_from_compiled_registry() -> None:
    # the whole point: a serialized->compiled registry still runs the route
    # out-of-process via urirun.exec, against a tmp db (offline).
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        registry = v2.compile_registry(json.loads(json.dumps(urirun_bindings())))
        policy = urirun.policy(allow=["log://*"])

        env = v2.run(ROUTE_LOG_WRITE, registry,
                     payload={"db": db, "stream": "daily", "event": "test.compiled"},
                     mode="execute", policy=policy)
        assert env["ok"] is True
        data = urirun.result_data(env)
        assert data["ok"] is True
        assert data["log"]["event"] == "test.compiled"

        env = v2.run(ROUTE_LOGS_RECENT, registry,
                     payload={"db": db, "stream": "daily"},
                     mode="execute", policy=urirun.policy(allow=["log://*"]))
        assert env["ok"] is True
        recent = urirun.result_data(env)
        assert any(log["event"] == "test.compiled" for log in recent["logs"])


# --- CLI ---

def test_main_bindings_and_manifest(capsys) -> None:
    assert main(["bindings"]) == 0
    bindings = json.loads(capsys.readouterr().out)
    assert bindings["version"] == "urirun.bindings.v2"
    assert ALL_ROUTES <= set(bindings["bindings"])

    assert main(["manifest"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["id"] == "sqlite-context"
    assert ROUTE_RECORD_UPSERT in manifest["routes"]
