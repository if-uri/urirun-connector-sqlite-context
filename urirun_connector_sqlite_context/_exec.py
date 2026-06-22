# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Out-of-process executor for sqlite-context routes.

The compiled v2 registry runs each route as an ``argv`` template that invokes
``python3 -m urirun_connector_sqlite_context._exec <subcommand> ...``. urirun only
spawns this template under ``--execute``, so this module always runs the route
logic (via ``core.run_action``) and prints the connector's JSON result to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import core


def _add_db(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="urirun_connector_sqlite_context._exec")
    sub = parser.add_subparsers(dest="command", required=True)

    datasets = sub.add_parser("datasets-list", help="List datasets")
    _add_db(datasets)

    dataset = sub.add_parser("dataset-create", help="Create or update a dataset")
    _add_db(dataset)
    dataset.add_argument("--name", required=True)
    dataset.add_argument("--description", default="")
    dataset.add_argument("--schema", default="")

    record = sub.add_parser("record-upsert", help="Create or update a record")
    _add_db(record)
    record.add_argument("--dataset", required=True)
    record.add_argument("--key", required=True)
    record.add_argument("--data", default="")
    record.add_argument("--source-uri", default="")
    record.add_argument("--confidence", type=float, default=0.0)

    search = sub.add_parser("records-search", help="Search records")
    _add_db(search)
    search.add_argument("--query", default="")
    search.add_argument("--dataset", default="")
    search.add_argument("--limit", type=int, default=20)

    sql = sub.add_parser("sql-read-only", help="Run read-only SQL")
    _add_db(sql)
    sql.add_argument("--query", required=True)
    sql.add_argument("--params", default="")
    sql.add_argument("--limit", type=int, default=100)

    artifact = sub.add_parser("artifact-register", help="Register an artifact")
    _add_db(artifact)
    artifact.add_argument("--kind", required=True)
    artifact.add_argument("--uri", required=True)
    artifact.add_argument("--path", default="")
    artifact.add_argument("--meta", default="")

    artifacts = sub.add_parser("artifacts-list", help="List artifacts")
    _add_db(artifacts)
    artifacts.add_argument("--kind", default="")
    artifacts.add_argument("--limit", type=int, default=20)

    check = sub.add_parser("check-add", help="Add a check result")
    _add_db(check)
    check.add_argument("--subject", required=True)
    check.add_argument("--check-uri", required=True)
    check.add_argument("--status", required=True)
    check.add_argument("--result", default="")

    checks = sub.add_parser("checks-recent", help="Read recent checks")
    _add_db(checks)
    checks.add_argument("--subject", default="")
    checks.add_argument("--limit", type=int, default=20)

    log_write = sub.add_parser("log-write", help="Write a log record")
    _add_db(log_write)
    log_write.add_argument("--stream", default="daily")
    log_write.add_argument("--event", required=True)
    log_write.add_argument("--detail", default="")

    logs = sub.add_parser("logs-recent", help="Read recent logs")
    _add_db(logs)
    logs.add_argument("--stream", default="")
    logs.add_argument("--limit", type=int, default=20)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    kwargs = {k: v for k, v in vars(args).items() if k != "command"}
    try:
        result = core.run_action(args.command, **kwargs)
    except Exception as exc:  # noqa: BLE001 - connector executor reports JSON errors.
        print(json.dumps({"ok": False, "connector": core.CONNECTOR_ID, "action": args.command, "error": str(exc)}))
        return 2
    print(json.dumps(result))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
