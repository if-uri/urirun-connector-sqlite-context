# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Route contracts for the sqlite-context connector (LLM-editable declaration).

The contract *type* and conformance *gate* live in the kernel
(``urirun_connectors_toolkit.contract_gate``); only these declarations live here. This connector is
multi-scheme (data/artifact/check/log share one connector id), so contract keys are FULL URIs and
``attach_contracts(None, CONTRACTS)`` joins them by URI.

Every handler returns ``{"ok": True, "connector": "sqlite-context", "type": "host-db", <field>}``.
The golden examples below were captured by running the real handlers against a temp DB (so they are
faithful, not idealized); ``conform()`` checks their STRUCTURE, not the exact ids/timestamps.

Wiring (one line in core.py, after the handlers)::

    from urirun_connectors_toolkit.contract_gate import attach_contracts
    from urirun_connector_sqlite_context.contracts import CONTRACTS
    attach_contracts(None, CONTRACTS)
"""
from __future__ import annotations

from urirun_connectors_toolkit.contract_gate import Contract

# Shared envelope head every route returns.
_HEAD = {"ok": "const:true", "connector": "const:sqlite-context", "type": "const:host-db"}


def _q(field_schema: dict, **kw) -> Contract:
    """A query contract whose out is the shared head plus one field."""
    return Contract(version="v1", effect="query", out={**_HEAD, **field_schema}, **kw)


def _c(field_schema: dict, **kw) -> Contract:
    """A command contract whose out is the shared head plus one field."""
    return Contract(version="v1", effect="command", out={**_HEAD, **field_schema}, **kw)


CONTRACTS: dict[str, Contract] = {

    "data://host/datasets/query/list": _q(
        {"datasets": "list"}, inp={"db": "?str"},
        examples=({"payload": {},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "datasets": [{"id": "ds_x", "name": "people", "description": "d",
                                            "created_at": "2026-06-27T10:36:30Z", "schema": {"type": "object"}}]}},)),

    "data://host/dataset/command/create": _c(
        {"dataset": "obj"}, inp={"name": "str", "db": "?str", "description": "?str", "dataset_schema": "?str"},
        examples=({"payload": {"name": "people", "description": "d"},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "dataset": {"id": "ds_x", "name": "people", "description": "d",
                                          "created_at": "2026-06-27T10:36:30Z", "schema": {"type": "object"}}}},)),

    "data://host/record/command/upsert": _c(
        {"record": "obj"},
        inp={"dataset": "str", "key": "str", "db": "?str", "data": "?str", "source_uri": "?str", "confidence": "?num"},
        examples=({"payload": {"dataset": "people", "key": "k1", "data": "{\"n\":1}"},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "record": {"id": "rec_x", "dataset_id": "ds_x", "key": "k1", "source_uri": None,
                                         "confidence": None, "created_at": "2026-06-27T10:36:30Z",
                                         "updated_at": "2026-06-27T10:36:30Z", "data": {"n": 1}}}},)),

    "data://host/records/query/search": _q(
        {"records": "list"}, inp={"db": "?str", "query": "?str", "dataset": "?str", "limit": "?int"},
        examples=({"payload": {"dataset": "people", "limit": 5},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "records": [{"id": "rec_x", "dataset_id": "ds_x", "key": "k1", "source_uri": None,
                                           "confidence": None, "created_at": "2026-06-27T10:36:30Z",
                                           "updated_at": "2026-06-27T10:36:30Z", "dataset_name": "people",
                                           "data": {"n": 1}}]}},)),

    "data://host/sql/query/read-only": _q(
        {"rows": "list"}, inp={"db": "?str", "query": "?str", "params": "?str", "limit": "?int"},
        examples=({"payload": {"query": "select 1 as one", "limit": 5},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "rows": [{"one": 1}]}},)),

    "artifact://host/artifact/command/register": _c(
        {"artifact": "obj"}, inp={"kind": "str", "uri": "str", "db": "?str", "path": "?str", "meta": "?str"},
        examples=({"payload": {"kind": "screenshot", "uri": "kvm://x", "path": "/x.png"},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "artifact": {"id": "art_x", "kind": "screenshot", "uri": "kvm://x", "path": "/x.png",
                                           "created_at": "2026-06-27T10:36:30Z", "meta": {}}}},)),

    "artifact://host/artifacts/query/list": _q(
        {"artifacts": "list"}, inp={"db": "?str", "kind": "?str", "limit": "?int"},
        examples=({"payload": {"limit": 5},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "artifacts": [{"id": "art_x", "kind": "screenshot", "uri": "kvm://x", "path": "/x.png",
                                             "created_at": "2026-06-27T10:36:30Z", "meta": {}}]}},)),

    "check://host/check/command/add": _c(
        {"check": "obj"}, inp={"subject": "str", "check_uri": "str", "status": "str", "db": "?str", "result": "?str"},
        examples=({"payload": {"subject": "ifuri.com", "check_uri": "httpcheck://x", "status": "ok"},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "check": {"id": "chk_x", "subject": "ifuri.com", "check_uri": "httpcheck://x",
                                        "status": "ok", "created_at": "2026-06-27T10:36:30Z", "result": {}}}},)),

    "check://host/checks/query/recent": _q(
        {"checks": "list"}, inp={"db": "?str", "subject": "?str", "limit": "?int"},
        examples=({"payload": {"limit": 5},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "checks": [{"id": "chk_x", "subject": "ifuri.com", "check_uri": "httpcheck://x",
                                          "status": "ok", "created_at": "2026-06-27T10:36:30Z", "result": {}}]}},)),

    "log://host/logs/query/recent": _q(
        {"logs": "list"}, inp={"db": "?str", "stream": "?str", "limit": "?int"},
        examples=({"payload": {"limit": 5},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "logs": [{"id": "log_x", "stream": "daily", "event": "test.event",
                                        "created_at": "2026-06-27T10:36:44Z", "detail": {"msg": "hi"}}]}},)),

    "log://host/daily/command/write": _c(
        {"log": "obj"}, inp={"event": "str", "db": "?str", "stream": "?str", "detail": "?str"},
        examples=({"payload": {"stream": "daily", "event": "test.event", "detail": "{\"msg\":\"hi\"}"},
                   "result": {"ok": True, "connector": "sqlite-context", "type": "host-db",
                              "log": {"id": "log_x", "stream": "daily", "event": "test.event",
                                      "created_at": "2026-06-27T10:36:44Z", "detail": {"msg": "hi"}}}},)),
}
