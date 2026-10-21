# Phase 01 - Validated data and skeleton: plan and results

Status: in progress
Spec: `spec.md` (approved, frozen)
Base: branch `fase-01-validated-data` from `inicio-cairn` (no remote yet)

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.

- [x] 1. Python skeleton: `pyproject.toml` with uv, Apache-2.0 licence, `src/cairn` package, ruff, strict mypy, pytest-cov at 85%, pre-commit and `npm run check` chaining them with the hook suite (C1) - evidence: `npm run check` green (ruff, mypy strict, pytest 1 passed at 100% coverage, hook suite all OK); commit e6d15cb.
- [x] 2. Data fetch and manifest: script that fetches the 8 PDS2014 XPT files, pins their SHA-256 in a versioned manifest and computes the snapshot hash; canonical JSON helper (C2) - evidence: `uv run python -m cairn.fetch` pinned 8 files, refetch verified 0 new, snapshot hash `9b981329b14d5bab53d71737d5f2cac514055045307adc10156ba6d7d33b534c`; the 8 XPT files (1.5 MB) are vendored in `data/pds2014` with the MIT notice; `npm run check` green, 11 passed, 100% coverage; commit in the next increment's evidence.
- [x] 3. Ingestion and validation: `read_sas`, zero normalisation, pandera schemas, cross rules, quarantine table, read-only DuckDB and JSON report; E1 phase 01 assertions (C2, C3, C4, C5) - evidence: 
pm run check green, 19 passed, 98.8% coverage; observed 12 negative AUC (AUCIFO 10 of 16, AUCTAU 2 of 36), 0 of 226 concentrations negative, DM.AGE mismatch 124 of 124, terminology malformed, death PDS2014-0119 day 3, naive mean 2820.67 (n=3) vs 15956 (n=2); commit 7a169fc.
- [x] 4. Jobs: `validate_study` as an in-process asyncio task behind `POST /jobs` and `GET /jobs/{id}` with the `Job` contract (C6) - evidence:
- [x] 5. Tool registry: `run_job` and `study_design` in one registry served by FastMCP at `/mcp`, FastAPI at `/api` and `/docs`, and the Typer CLI; same-hash test over the three surfaces (C7) - evidence: `npm run check` green (ruff, strict mypy, 29 tests, coverage 99.25%, hook suite); C7 test_same_hash_over_mcp_rest_and_cli passes with the official mcp Client against uvicorn on a free port; commit 2aacfc5
- [x] 6. Web: Jinja2, local HTMX and plain CSS; landing page, step bar, header, footer, badges, `/healthz` and step 1 with the "Inject a negative concentration" switch (C8, C9) - evidence: `npm run check` green (34 tests, coverage 98.93%); tests cover routes, badges, disclaimer, step 1 with 12 quarantined and means 2,821 (n=3) and 15,956 (n=2) computed by code, the switch (13th row, rule pc_concentration_positive, DuckDB file bytes unchanged) and the no-literal grep on templates; HTMX 2.0.4 from unpkg, SHA-256 e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447, notice in `static/vendor/htmx.NOTICE.txt`; commit bdef72b. Browser walkthrough at 1440x900 pending (C9).
- [x] 7. Word-cap test over the step templates, including a failing case (C10) - evidence: `npm run check` green (38 tests, coverage 98.93%); step 1 has 66 visible words against a cap of 93 per step (about 650 for 7) and one sentence of at most 25 words; `test_cap_fails_on_an_over_cap_sample` proves the failure; commit 772f3a2.
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
