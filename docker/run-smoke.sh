#!/usr/bin/env bash
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

set -euo pipefail

mkdir -p .docker-smoke
DB=".docker-smoke/host.db"

echo "==> direct connector CLI"
urirun-sqlite-context dataset-create \
  --db "$DB" \
  --name domains \
  --schema '{"type":"object","required":["domain"],"properties":{"domain":{"type":"string"}}}' > .docker-smoke/dataset.json
urirun-sqlite-context record-upsert \
  --db "$DB" \
  --dataset domains \
  --key ifuri.com \
  --data '{"domain":"ifuri.com"}' > .docker-smoke/record.json

echo "==> build bindings and registry"
python3 - <<'PY' > .docker-smoke/bindings.json
import json
from urirun_connector_sqlite_context import urirun_bindings
print(json.dumps(urirun_bindings(), indent=2))
PY

urirun validate .docker-smoke/bindings.json
urirun compile .docker-smoke/bindings.json --out .docker-smoke/registry.json

echo "==> execute connector URI through urirun"
urirun run 'data://host/records/query/search' .docker-smoke/registry.json \
  --payload "{\"db\":\"$DB\",\"dataset\":\"domains\",\"query\":\"ifuri\"}" \
  --execute \
  --allow 'data://host/*' > .docker-smoke/urirun-result.json

echo "==> project registry to MCP tools and A2A card"
python3 -m urirun.v2_mcp tools .docker-smoke/registry.json > .docker-smoke/mcp-tools.json
python3 -m urirun.v2_mcp card .docker-smoke/registry.json \
  --name sqlite-context-docker \
  --url http://tester/ > .docker-smoke/a2a-card.json

python3 - <<'PY'
import json
from pathlib import Path

base = Path(".docker-smoke")
dataset = json.loads((base / "dataset.json").read_text())
record = json.loads((base / "record.json").read_text())
run = json.loads((base / "urirun-result.json").read_text())
run_payload = json.loads(run["result"]["stdout"])
tools = json.loads((base / "mcp-tools.json").read_text())
card = json.loads((base / "a2a-card.json").read_text())

assert dataset["ok"] is True, dataset
assert record["record"]["key"] == "ifuri.com", record
assert run["ok"] is True, run
assert run_payload["records"][0]["key"] == "ifuri.com", run_payload
assert any(tool["name"] == "data_host_records_query" for tool in tools["tools"]), tools
assert any("data://host/records/query/search" in skill.get("examples", []) for skill in card["skills"]), card
print(json.dumps({
    "ok": True,
    "mcpTools": len(tools["tools"]),
    "a2aSkills": len(card["skills"]),
}, indent=2))
PY
