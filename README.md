# urirun-connector-sqlite-context

`sqlite-context` is an external urirun connector for local host memory:
datasets, records, artifacts, checks and logs.

Each route is declared once as a typed `@<scheme>.handler(..., isolated=True)`:
the function signature is the input schema and the body is the implementation —
no argv template, no `_exec.py` shim, no `run_action` dispatcher. `isolated=True`
keeps every route **registry-portable**: the runtime runs it out-of-process via
the shared `python -m urirun.exec` runner, hydrating the handler from the
serialized `python: {module, export}` descriptor. A route therefore executes from
a compiled file registry, `urirun run`, or a served node alike — with only the
package importable, no console-script install required.

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

After installation, `urirun` can discover this connector automatically through
the `urirun.bindings` entry-point group:

```bash
urirun discover --out connectors.bindings.json --registry-out connectors.registry.json
urirun list --entry-points
```

The connector owns the URI route declarations and the JSON envelope; the storage
logic lives once in urirun's host SQLite backend (`urirun.host.host_db`), so the
runtime stays the single source of truth.

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

## License

Released under the terms in [LICENSE](LICENSE).
