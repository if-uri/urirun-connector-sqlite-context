# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from urirun import v2
from urirun_connector_sqlite_context import (
    connector_manifest,
    create_dataset,
    log_write,
    run_action,
    search_records,
    upsert_record,
    urirun_bindings,
)
from urirun_connector_sqlite_context import _exec
from urirun_connector_sqlite_context.core import main

SCHEMA = {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}}

_EXEC_PREFIX = ["python3", "-m", "urirun_connector_sqlite_context._exec"]


def _registry():
    return v2.compile_registry(urirun_bindings())


def test_hybrid_argv_template_binding() -> None:
    bindings = urirun_bindings()["bindings"]
    binding = bindings["data://host/datasets/query/list"]
    assert binding["adapter"] == "argv-template"
    assert binding["argv"][:4] == [*_EXEC_PREFIX, "datasets-list"]

    # every route is an out-of-process argv-template pointing at _exec.
    for uri, b in bindings.items():
        assert b["adapter"] == "argv-template", uri
        assert b["argv"][:3] == _EXEC_PREFIX, uri


def test_compile_registry_routes_present() -> None:
    routes = v2.list_routes(_registry())
    uris = {route["uri"] for route in routes}
    assert "data://host/record/command/upsert" in uris
    assert "artifact://host/artifact/command/register" in uris
    assert "log://host/logs/query/recent" in uris


def test_manifest_derived_routes_and_schemes() -> None:
    manifest = connector_manifest()
    assert manifest["id"] == "sqlite-context"
    assert "data://host/record/command/upsert" in manifest["routes"]
    assert manifest["uriSchemes"] == sorted(["data", "artifact", "check", "log"])


def test_direct_dataset_record_and_log() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        dataset = create_dataset(db=db, name="domains", schema=json.dumps(SCHEMA))
        assert dataset["ok"] is True

        record = upsert_record(db=db, dataset="domains", key="ifuri.com", data=json.dumps({"domain": "ifuri.com"}))
        assert record["record"]["key"] == "ifuri.com"

        found = search_records(db=db, query="ifuri", dataset="domains")
        assert found["records"][0]["key"] == "ifuri.com"

        written = log_write(db=db, stream="daily", event="test.finished", detail=json.dumps({"ok": True}))
        assert written["log"]["event"] == "test.finished"


def test_run_action_dispatch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        result = run_action("datasets-list", db=db)
        assert result["ok"] is True
        assert isinstance(result["datasets"], list)


def test_exec_main_prints_json(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        rc = _exec.main(["log-write", "--db", db, "--stream", "daily", "--event", "test.exec"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["ok"] is True
        assert out["log"]["event"] == "test.exec"

        rc = _exec.main(["logs-recent", "--db", db, "--stream", "daily"])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert out["ok"] is True
        assert any(log["event"] == "test.exec" for log in out["logs"])


def test_main_bindings_and_manifest(capsys) -> None:
    assert main(["bindings"]) == 0
    bindings = json.loads(capsys.readouterr().out)
    assert bindings["version"] == "urirun.bindings.v2"
    assert "log://host/logs/query/recent" in bindings["bindings"]

    assert main(["manifest"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["id"] == "sqlite-context"
    assert "data://host/record/command/upsert" in manifest["routes"]
