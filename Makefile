.PHONY: help manifest bindings smoke test docker-test clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-12s %s\n",$$1,$$2}'

manifest: ## Print the connector manifest
	urirun-sqlite-context manifest

bindings: ## Print urirun bindings
	urirun-sqlite-context bindings

smoke: ## bindings -> urirun connectors smoke (validate/compile/run/MCP/A2A)
	tmp=$$(mktemp -d); \
	urirun-sqlite-context bindings | urirun connectors smoke - \
	  --run 'log://host/daily/command/write' \
	  --payload "{\"db\":\"$$tmp/host.db\",\"stream\":\"daily\",\"event\":\"smoke.write\"}" \
	  --allow 'log://host/*' --name sqlite-context

test: ## Run the test suite
	python3 -m pytest -q

docker-test: ## Run connector in Docker and verify registry, MCP and A2A
	docker compose up --build --abort-on-container-exit --exit-code-from tester
	docker compose down -v --remove-orphans

clean:
	rm -rf .pytest_cache .docker-smoke build dist *.egg-info
