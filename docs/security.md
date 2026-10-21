# Deferred security findings

| ID | Severity | Where | What happens | Status | Origin |
| --- | --- | --- | --- | --- | --- |
| SEC-001 | Medium | `POST /jobs` and `/api/tools/{name}` (all registry tools since phase 02a) | Public unauthenticated endpoints with unbounded in-memory job dicts, and study tools that each open DuckDB and run several queries per request, can be abused for memory and CPU on the public demo. | Deferred to phase 06 (access code). | Phase 01, widened in phase 02a |
| SEC-002 | Low | `src/cairn/observation.py` `snapshot_sha256` | The snapshot hash comes from the manifest, not from the DuckDB file queried; a stale or altered `data/build/cairn.duckdb` yields Observations that claim the pinned snapshot. | Open; to close before the audit trail of phase 05 relies on it. | Phase 02a |
