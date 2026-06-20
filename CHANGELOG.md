# Changelog

## [Unreleased]

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
