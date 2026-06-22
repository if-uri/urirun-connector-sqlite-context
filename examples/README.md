# sqlite-context connector — examples

Local SQLite context: logs, artifacts, datasets, checks.

## Install
```bash
urirun install urirun-connector-sqlite-context
```
`urirun install` resolves catalog ids via connect.ifuri.com; `--catalog <url>` points at a
local/on-prem registry; a full package name / git URL / path falls back to `pip install`.

## Run
```bash
# Local SQLite context: logs, artifacts, datasets, checks (read)
urirun run 'log://host/logs/query/recent' --payload '{"limit": 5}' --execute --allow 'log://*'

# preview without running (dry-run): drop --execute
urirun run 'log://host/logs/query/recent' --payload '{"limit": 5}' --allow 'log://*'
```

## Inspect the runtime (no path — like error:// / log://)
```bash
urirun list | grep 'log://'                                   # this connector's routes
urirun run 'registry://local/routes/query/list' --payload '{"scheme":"log"}' --allow 'registry://*'
urirun run 'registry://local/bindings/query/show' --payload '{"uri":"log://host/logs/query/recent"}' --allow 'registry://*'   # full typed contract
urirun errors                                                      # recent runtime errors (error://)
```

## Generate a client / API surface from the binding
```bash
urirun discover | urirun gen openapi - --out openapi.json   # OpenAPI 3 (one path per route)
urirun discover | urirun gen proto   - --out service.proto  # protobuf + gRPC (typed rpc per route)
urirun discover | urirun gen client  - --out client.py      # typed Python client
```
