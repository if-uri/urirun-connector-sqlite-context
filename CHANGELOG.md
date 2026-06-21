# Changelog

## [Unreleased]

### Changed
- Reuse the urirun host SQLite backend (`urirun.host.host_db`) instead of a
  bundled copy of the storage logic. The connector now owns only the URI route
  declarations and the JSON envelope (509 -> 186 lines); urirun is the single
  source of truth. Routes, manifest and CLI behaviour are unchanged.

### Added
- Add follow-up tasks for IFURI-016 matrix coverage and richer SQLite context
  route documentation.
- Expose `urirun_bindings()` through the `urirun.bindings` entry-point group
  and document `urirun discover` / `urirun list --entry-points`.

### Changed
- Link README related projects to the `if-uri/urirun` runtime repository.
- Update README URI payload examples to use `dataset_schema`.
- Record that the connector is published and listed in the connector hub.

## [0.1.1] - 2026-06-20

### Changed
- Make the connector runtime self-contained for datasets, records, artifacts,
  checks, logs and read-only SQL.
- Stop importing `urirun.host_db`; the connector now owns the SQLite store it
  exposes through URI bindings.

## [0.1.0] - 2026-06-20

### Added
- Add initial SQLite context connector with decorated data, artifact, check and
  log URI bindings.
