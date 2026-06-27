# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Conformance gate for the sqlite-context connector's route contracts.

Unlike a hardware connector (kvm), sqlite-context is pure I/O — so the gate runs the REAL handlers
against a temp DB and asserts the live output conforms to the declared contract (the strongest check:
code↔contract at runtime, no fixtures to drift). No env gating, no hardware.
"""
from __future__ import annotations

import urirun_connector_sqlite_context.core as core
from urirun_connector_sqlite_context.contracts import CONTRACTS
from urirun_connectors_toolkit.contract_gate import conform, envelope_violation
from urirun_connectors_toolkit.contract_lint import lint_handler_signatures


def test_contracts_conform():
    """Static oracle: effect↔verb, golden examples satisfy in/out, error taxonomy."""
    conform(CONTRACTS)


def test_signatures_bound_to_contract():
    """Every contract.inp field must exist in the live handler signature with a compatible type."""
    problems = lint_handler_signatures(CONTRACTS, core.urirun_bindings())
    assert not problems, "contract<->signature drift:\n" + "\n".join(problems)


def test_every_route_has_a_contract():
    """Coverage + dangling guard: every live route is contracted, and no contract points at a
    route that does not exist. sqlite-context is small enough to require FULL coverage."""
    live = set(core.urirun_bindings()["bindings"])
    contracted = set(CONTRACTS)
    assert not (contracted - live), f"contracts point at missing routes: {sorted(contracted - live)}"
    assert not (live - contracted), f"routes without a contract: {sorted(live - contracted)}"


def test_live_output_conforms_to_contract(tmp_path):
    """Run each real handler against a temp DB (dependency order) and assert the actual envelope
    conforms to its contract — code↔contract verified by execution, not by a hand-written fixture."""
    db = str(tmp_path / "ctx.db")
    steps = [
        ("data://host/dataset/command/create", lambda: core.create_dataset(db=db, name="people", description="d")),
        ("data://host/datasets/query/list", lambda: core.list_datasets(db=db)),
        ("data://host/record/command/upsert", lambda: core.upsert_record(db=db, dataset="people", key="k1", data='{"n":1}')),
        ("data://host/records/query/search", lambda: core.search_records(db=db, dataset="people", limit=5)),
        ("data://host/sql/query/read-only", lambda: core.sql_read_only(db=db, query="select 1 as one", limit=5)),
        ("artifact://host/artifact/command/register", lambda: core.register_artifact(db=db, kind="screenshot", uri="kvm://x", path="/x.png")),
        ("artifact://host/artifacts/query/list", lambda: core.list_artifacts(db=db, limit=5)),
        ("check://host/check/command/add", lambda: core.add_check(db=db, subject="ifuri.com", check_uri="httpcheck://x", status="ok")),
        ("check://host/checks/query/recent", lambda: core.recent_checks(db=db, limit=5)),
        ("log://host/daily/command/write", lambda: core.log_write(db=db, stream="daily", event="e", detail='{"m":1}')),
        ("log://host/logs/query/recent", lambda: core.recent_logs(db=db, limit=5)),
    ]
    for uri, run in steps:
        env = run()
        bad = envelope_violation(CONTRACTS[uri], env)
        assert bad is None, f"{uri}: live output violates contract: {bad}\nenvelope={env}"
