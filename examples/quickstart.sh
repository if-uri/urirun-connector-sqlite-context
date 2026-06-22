#!/usr/bin/env bash
# sqlite-context: install once, then run — auto-discovered, no registry path.
set -euo pipefail
urirun install urirun-connector-sqlite-context            # local dev: pip install -e .
urirun run 'log://host/logs/query/recent' --payload '{"limit": 5}' --execute --allow 'log://*'
