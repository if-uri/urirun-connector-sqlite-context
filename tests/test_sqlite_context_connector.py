from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from urirun import v2
from urirun_connector_sqlite_context import (
    connector_manifest,
    create_dataset,
    log_write,
    search_records,
    upsert_record,
    urirun_bindings,
)
from urirun_connector_sqlite_context.cli import main


SCHEMA = {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}}}


def _registry():
    return v2.compile_registry(urirun_bindings())


def test_manifest_and_bindings_shape() -> None:
    manifest = connector_manifest()
    bindings = urirun_bindings()
    routes = v2.list_routes(_registry())

    assert manifest["id"] == "sqlite-context"
    assert "data://host/record/command/upsert" in manifest["routes"]
    assert bindings["version"] == "urirun.bindings.v2"
    assert "log://host/logs/query/recent" in bindings["bindings"]
    assert any(route["uri"] == "artifact://host/artifact/command/register" for route in routes)


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


def test_cli_and_urirun_run_connector_uri(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "host.db")
        assert main(["dataset-create", "--db", db, "--name", "domains", "--schema", json.dumps(SCHEMA)]) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True

        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "urirun-sqlite-context"
        wrapper.write_text(
            f"#!/usr/bin/env sh\nexec {sys.executable} -m urirun_connector_sqlite_context.cli \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{previous_path}"
        try:
            result = v2.run(
                "data://host/record/command/upsert",
                _registry(),
                {
                    "db": db,
                    "dataset": "domains",
                    "key": "ifuri.com",
                    "data": json.dumps({"domain": "ifuri.com"}),
                },
                mode="execute",
                policy={"execute": {"allow": ["data://host/*"]}},
            )
            assert result["ok"] is True, result
            stdout = json.loads(result["result"]["stdout"])
            assert stdout["record"]["key"] == "ifuri.com"
        finally:
            os.environ["PATH"] = previous_path
