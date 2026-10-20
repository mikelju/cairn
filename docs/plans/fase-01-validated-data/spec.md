# Phase 01 - Validated data and skeleton: specification

Status: draft
Approved by the user: pending
Master plan: `../0_plan_maestro.md`

## Objective
Leave a public, deployed skeleton that proves the first promise of Cairn: bad data stops at the door before any AI sees it.
A visitor opens the HTTPS URL or runs `make demo` offline, sees the landing page, runs the validation job in step 1 and sees the 12 negative AUC values quarantined, never silently fixed.
Every later phase builds on this repo, this data layer, this tool registry and this deployment path.

## Scope
In:
- Python 3.12 package `cairn` managed with uv, Apache-2.0 licence, ruff, strict mypy, pytest with coverage and pre-commit.
- `npm run check` chains ruff, mypy and pytest with the hook suite.
- GitHub Actions workflow with a required check named `evals` that runs tests and the phase 01 part of E1, with no network, no keys and no deploy.
- SEND ingestion of the 8 domains DM, TX, TS, DS, MI, BW, PP and PC of PhUSE PDS2014 from XPT, with a SHA-256 manifest of the input files and a snapshot hash.
- pandera schemas on the columns read, XPT zero normalisation (absolute value below 1e-70 becomes 0) and cross rules: AUC > 0, quantified PC concentrations > 0, DM.AGE against TS, terminology version, unique IDs and populations from TX.
- Read-only DuckDB file with one table per domain and one quarantine table; rows that fail are flagged, never corrected.
- `validate_study` job behind `POST /jobs` and `GET /jobs/{id}`, run as an in-process asyncio task, with a JSON report and the contract `Job{job_id, kind, inputs_sha256, status, outputs}`; hashes use one canonical JSON.
- One registry of typed tools, `run_job` and `study_design`, served by FastMCP at `/mcp`, FastAPI at `/api` and `/docs`, and a Typer CLI `cairn`.
- Web app with FastAPI, Jinja2, a pinned local copy of HTMX and plain CSS: landing page, step bar, header with the simulated role, footer with version, commit and snapshot hash, `/healthz`, and step 1 with the "Inject a negative concentration" switch.
- Badges REAL, RECORDED and SIMULATED with the shared step anatomy; step 1's job runner is shown as SIMULATED with its "In production →" line.
- Word-cap test over the templates.
- Multi-stage linux/amd64 Docker image that builds the DuckDB file during the build.
- `make demo` (offline, from a clean clone) and `make deploy` (Lightsail container service in eu-west-1 with HTTPS, from the laptop).

Out:
- Any model call, LLMGateway, recordings, `make record` and `make live` (phase 02).
- The full Observation contract and the other study tools (phase 02); `study_design` returns a plain typed contract for now.
- The other two step 1 switches, the live question, the access code and the IAM key for the container (phase 06).
- Steps 2 to 7, which appear in the step bar but are not reachable yet.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite | Run the commands on a fresh clone |
| C2 | Ingestion loads exactly the 8 domains, writes the SHA-256 manifest and the snapshot hash, and the same input gives the same snapshot hash twice | pytest |
| C3 | Validation reports exactly: 12 negative AUC (AUCIFO 10 of 16, AUCTAU 2 of 36) in quarantine, 0 of 226 quantified concentrations negative, DM.AGE 0 for all 124 animals versus TS, malformed terminology version, 1 death (PDS2014-0119, day 3, control TK satellite) and XPT zeros normalised | E1 phase 01 assertions in pytest, exact equality, no LLM |
| C4 | Quarantined rows are absent from the domain tables, present in the quarantine table with the rule that fired, and their values are unchanged | pytest |
| C5 | The naive mean AUCtau for males at 20 mg/kg/day on day 1 is 2,821 with the bad value (n=3) and 15,956 without it (n=2); both numbers are computed by code, not written in templates | pytest plus a grep that the templates contain no such literal |
| C6 | `POST /jobs` with `validate_study` returns a job that reaches `done` and `GET /jobs/{id}` returns the JSON report with `inputs_sha256` | pytest with the FastAPI test client |
| C7 | `run_job` and `study_design` give the same result hash over MCP (official `mcp` client), REST and the CLI | pytest |
| C8 | The "Inject a negative concentration" switch revalidates in memory and shows the rule that fires and the new quarantine row, without touching the DuckDB file | pytest plus walkthrough in a browser |
| C9 | The landing page and step 1 fit 1440x900 without scrolling, show the three badges truthfully, the disclaimer "Public sample data · fictional compound · not GxP-validated", and step 1's SIMULATED "In production →" line | Walkthrough in a browser at 1440x900 with screenshot |
| C10 | A test counts the visible words per step template and fails above the cap (one sentence of at most 25 words per step, about 650 words for the 7 steps) | pytest, including a failing case |
| C11 | `make demo` serves the same landing page and step 1 from a clean clone with the network disabled | Run with network off and walk through it |
| C12 | The HTTPS Lightsail URL serves the same landing page and step 1, and `/healthz` answers 200 | Open the URL and curl `/healthz` |
| C13 | GitHub Actions is green on the phase PR with the `evals` check, and the workflow has no deploy step | PR checks page |
| C14 | No company name, logo or colour from the PRD and no person's name appear in the repo or the app | Local brand grep before every push |

## Constraints and risks
- Data source: the PRD names the PhUSE SEND sample datasets (MIT licence) but no URL or checksums; the XPT files are pinned by SHA-256 in the repo the first time they are fetched.
- If the published PDS2014 files differ from the PRD's expected facts, C3 and C5 cannot pass as written and a deviation is needed.
- Lightsail medium (1 vCPU, 4 GB) has a monthly cost on the user's AWS account.
- `make deploy` needs the user's local AWS credentials; CI never holds them.
- If the AWS skeleton fails persistently, the PRD's fallback is to drop AWS hosting; that would change C12 and needs a deviation.
- New dependencies, all Apache-2.0 compatible: duckdb, pandas, pandera, pyreadstat or pandas `read_sas`, fastapi, uvicorn, jinja2, fastmcp, mcp, typer, pydantic, plus dev tools.

## Open decisions
Questions the user must resolve before approval.
1. Bedrock: the PRD puts the first-use form, the first call to each profile and the smoke test with ADR-001 on day 1. Proposal: you submit the form now because it has lead time, and the smoke test with ADR-001 moves to phase 02, where the first model call lives. Agree?
2. Public repo: you create the public GitHub repo, add it as `origin` and set the branch rule that requires `evals`, or you authorize me to do it with `gh`. Which one?
3. Lightsail: do you authorize creating the medium container service in eu-west-1, with its monthly cost, using your local AWS credentials?
4. Coverage threshold: 85% on `src/cairn` (the PRD gives none). Agree?
