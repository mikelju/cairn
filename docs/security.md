# Deferred security findings

| ID | Severity | Where | What happens | Status | Origin |
| --- | --- | --- | --- | --- | --- |
| SEC-001 | Medium | `POST /jobs` and `/api/tools/run_job` | Public unauthenticated endpoints with unbounded in-memory job dicts can be abused for memory and CPU on the public demo. | Deferred to phase 06 (access code). | Phase 01 |
