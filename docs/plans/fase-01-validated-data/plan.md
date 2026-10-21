# Phase 01 - Validated data and skeleton: plan and results

Status: in progress
Spec: `spec.md` (approved, frozen)
Base: branch `fase-01-validated-data` from `inicio-cairn` (no remote yet)

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.

- [x] 1. Python skeleton: `pyproject.toml` with uv, Apache-2.0 licence, `src/cairn` package, ruff, strict mypy, pytest-cov at 85%, pre-commit and `npm run check` chaining them with the hook suite (C1) - evidence: `npm run check` green (ruff, mypy strict, pytest 1 passed at 100% coverage, hook suite all OK); commit in increment 1 log.
- [ ] 2. Data fetch and manifest: script that fetches the 8 PDS2014 XPT files, pins their SHA-256 in a versioned manifest and computes the snapshot hash; canonical JSON helper (C2) - evidence:
- [ ] 3. Ingestion and validation: `read_sas`, zero normalisation, pandera schemas, cross rules, quarantine table, read-only DuckDB and JSON report; E1 phase 01 assertions (C2, C3, C4, C5) - evidence:
- [ ] 4. Jobs: `validate_study` as an in-process asyncio task behind `POST /jobs` and `GET /jobs/{id}` with the `Job` contract (C6) - evidence:
- [ ] 5. Tool registry: `run_job` and `study_design` in one registry served by FastMCP at `/mcp`, FastAPI at `/api` and `/docs`, and the Typer CLI; same-hash test over the three surfaces (C7) - evidence:
- [ ] 6. Web: Jinja2, local HTMX and plain CSS; landing page, step bar, header, footer, badges, `/healthz` and step 1 with the "Inject a negative concentration" switch (C8, C9) - evidence:
- [ ] 7. Word-cap test over the step templates, including a failing case (C10) - evidence:
- [ ] 8. Docker multi-stage linux/amd64 image that builds DuckDB at build time; `make demo` with the network off (C11) - evidence:
- [ ] 9. CI: GitHub Actions workflow with the required `evals` check, no network, no keys, no deploy (C13) - evidence:
- [ ] 10. `make deploy` to Lightsail eu-west-1 with HTTPS and `/healthz` (C12); needs open decisions 2 and 3 - evidence:
- [ ] 11. Brand grep and adversarial review before the PR (C14) - evidence:

## Deviations
| ID | Summary | Affects criteria | Status |
|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Results
Per criterion: command or walkthrough run, observed result and reference to the evidence.
Pending items, limitations and what could not be checked, stated plainly.

## Candidate learnings
Only reusable lessons with a verbatim quote from the session; consolidated when the phase closes.
