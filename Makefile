.PHONY: test smoke docker-test clean

test:
	python3 -m pytest -q

smoke:
	tmp=$$(mktemp -d); \
	mkdir -p "$$tmp/bin"; \
	printf '%s\n' '#!/usr/bin/env sh' 'exec python3 -m urirun_connector_sqlite_context.cli "$$@"' > "$$tmp/bin/urirun-sqlite-context"; \
	chmod +x "$$tmp/bin/urirun-sqlite-context"; \
	export PATH="$$tmp/bin:$$PATH"; \
	db="$$tmp/host.db"; \
	python3 -m urirun_connector_sqlite_context.cli dataset-create --db "$$db" --name domains --schema '{"type":"object","required":["domain"],"properties":{"domain":{"type":"string"}}}' > "$$tmp/dataset.json"; \
	python3 -m urirun_connector_sqlite_context.cli bindings > "$$tmp/bindings.json"; \
	urirun validate "$$tmp/bindings.json"; \
	urirun compile "$$tmp/bindings.json" --out "$$tmp/registry.json"; \
	urirun run 'data://host/record/command/upsert' "$$tmp/registry.json" \
	  --payload "{\"db\":\"$$db\",\"dataset\":\"domains\",\"key\":\"ifuri.com\",\"data\":\"{\\\"domain\\\":\\\"ifuri.com\\\"}\"}" \
	  --execute --allow 'data://host/*' > "$$tmp/run.json"; \
	python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["ok"], data; out=json.loads(data["result"]["stdout"]); assert out["record"]["key"] == "ifuri.com", out' "$$tmp/run.json"; \
	python3 -m urirun.v2_mcp tools "$$tmp/registry.json" > "$$tmp/tools.json"; \
	python3 -m urirun.v2_mcp card "$$tmp/registry.json" --name sqlite-context --url http://localhost/ > "$$tmp/card.json"

docker-test:
	docker compose up --build --abort-on-container-exit --exit-code-from tester
	docker compose down -v --remove-orphans

clean:
	rm -rf .pytest_cache .docker-smoke build dist *.egg-info
