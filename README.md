# urirun-connector-sqlite-context

`sqlite-context` is an external urirun connector for local host memory:
datasets, records, artifacts, checks and logs.

It generates normal urirun bindings through decorators and executes them through
`urirun-sqlite-context`.

## Install

```bash
pip install "git+https://github.com/if-uri/urirun-connector-sqlite-context.git@v0.1.1"
```

## Use

```bash
urirun-sqlite-context bindings > bindings.json
urirun validate bindings.json
urirun compile bindings.json --out registry.json

urirun run 'data://host/dataset/command/create' registry.json \
  --payload '{"name":"domains","dataset_schema":"{\"type\":\"object\"}"}' \
  --execute \
  --allow 'data://host/*'
```

The connector owns its SQLite runtime and does not import `urirun.host_db` from
the core runtime.

## Test

```bash
make test
make smoke
make docker-test
```

## Related projects

- Runtime: [if-uri/urirun](https://github.com/if-uri/urirun)
- Docs: [docs.ifuri.com/connectors.html](https://docs.ifuri.com/connectors.html) · [authoring a connector](https://docs.ifuri.com/connector-authoring.html)
- Hub page: [connect.ifuri.com/connectors/sqlite-context](https://connect.ifuri.com/connectors/sqlite-context)
- Connector hub: [connect.ifuri.com](https://connect.ifuri.com)
- Examples: [if-uri/examples](https://github.com/if-uri/examples)
- Work summary: [work-summary-2026-06-20](https://github.com/if-uri/docs/blob/main/work-summary-2026-06-20.md)

Repository notes: [TODO.md](TODO.md) · [CHANGELOG.md](CHANGELOG.md)
