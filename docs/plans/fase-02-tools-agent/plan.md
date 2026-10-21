# Phase 02a - Tools and rules that write no numbers: plan and results

Status: in progress
Spec: `spec.md` (approved, frozen)
Base: branch `fase-02-tools-agent` from `main` at 70eebd1

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on `fase-02-tools-agent`; nothing in this phase calls a model, needs AWS access or adds a dependency.

- [x] 1. Observation contract and read-only DuckDB access: new `src/cairn/observation.py` with the `Observation` model and `content_sha256` from `cairn.canonical`; one helper that opens `cairn.ingest.DEFAULT_DB` with `read_only=True` (a pytest fixture builds the file with `cairn.ingest.ingest()` when it is missing, so a fresh clone and CI work); `study_design` in `src/cairn/tools.py` moves from the XPT path to fixed SQL on that file and returns an `Observation` (C2, C1) - verification: `uv run pytest tests/test_observation.py -k "observation or duckdb_read_only"` with `test_observation_*` (valid fields, same hash on two runs) and `test_tools_duckdb_read_only` (a write through the tool connection fails and the real file bytes are unchanged), then `npm run check` - evidence: `uv run pytest tests/test_observation.py -k "observation or duckdb_read_only"` 3 passed; `npm run check` green
- [x] 2. `incidence` tool with the screen: fixed SQL over `mi`, `dm` and `tx` following the Data definitions (main study, exact findings, examined denominator, "not examined" for empty groups), the screen rule text as one constant used both by the code and by the output (C3, C4, C2) - verification: `uv run pytest tests/test_incidence.py` with `test_incidence_screen_*` (exactly the 9 rows and the counts of the Data check table, the five "not examined" cells and renal necrosis M at 200 as 0 of 1), `test_incidence_full_*` and `test_screen_rule_text_matches`, plus `test_observation_*` extended to `incidence` - evidence: `uv run pytest tests/test_incidence.py` 8 passed (9 screen rows, 5 not-examined cells, 0 of 1, 82 full findings); `npm run check` green
- [x] 3. `body_weight_change` tool: fixed SQL over `bw`, `dm` and `tx`, population argument that excludes TK satellites and includes recovery animals, percent lower than control of the day-29 means, change from baseline per animal, wording "lower than control" only; the schema rejects TK satellites (C5, C6, C2) - verification: `uv run pytest tests/test_body_weight.py` with `test_body_weight_change_*` (9.3, 17.6 and 20.7 at one decimal, n = 15/10/10/15, positive mean change in every group, only PDS2014-0165 negative with -5.3 g, no "lost") and `test_tool_rejects_tk_in_body_weight` - evidence: `uv run pytest tests/test_body_weight.py` 11 passed (9.3/17.6/20.7, n 15/10/10/15, PDS2014-0165 -5.3, TK rejected by schema); `npm run check` green
- [x] 4. `tk_summary` tool: fixed SQL over `pp` and the `quarantine` table for AUCtau on day 1 in the TK satellite set, naive mean with and without the quarantined row and the ratio to one decimal; the quarantine flag feeds rule 5 later (C6, C2) - verification: `uv run pytest tests/test_tk_summary.py` with `test_tk_summary_*` (2,821 with n=3, 15,956 with n=2, ratio 5.7, matching `cairn.validate.mean_auctau`) - evidence: `uv run pytest tests/test_tk_summary.py` 5 passed (2,821 n=3, 15,956 n=2, ratio 5.7, matches mean_auctau); `npm run check` green
- [x] 5. Registry over three surfaces: the four study tools in `REGISTRY`, REST routes under `/api/tools/` in `src/cairn/app.py`, Typer commands in `src/cairn/cli.py`, MCP through the existing FastMCP mount; `tests/test_tools.py` updated from the two-tool registry test (C7) - verification: `uv run pytest tests/test_tools.py -k registry_same_hash` with `test_registry_same_hash_*` over the official `mcp` client, REST and the CLI for each study tool - evidence: `uv run pytest tests/test_tools.py -k registry_same_hash` 5 passed (run_job, study_design, incidence, body_weight_change, tk_summary: same hash over MCP, REST, CLI and direct); `npm run check` green, 70 tests, coverage 98.95%; E7 fix: `call_tool` validates arguments against each tool's annotations, REST answers 422 and the CLI exits 2 with a plain message, `uv run pytest tests/test_tools.py` 18 passed (9 new tests failed before the fix, TK and bad `sex` rejected on MCP, REST and CLI)
- [x] 6. Typed content and renderer: new `src/cairn/content.py` with `Text`, `ValueRef(obs_id, field)` and `Sentence` and code-assigned IDs `O1`, `O2`... by call order; new `src/cairn/render.py` that places numbers and study terms from `ValueRef`, formatting by type, and passes model text as written (C8) - verification: `uv run pytest tests/test_renderer.py` with `test_renderer_*` (a digit-free sentence list over real Observations renders text whose every number matches its Observation field; IDs repeat across two runs) - evidence: `uv run pytest tests/test_renderer.py` 6 passed (2,821 / 15,956 / 5.7 / 20.7 placed from fields, IDs O1-O3 repeat across two runs, unresolved refs raise); `npm run check` green, 76 tests, coverage 99.06%
- [x] 7. Verifier rules 1-7: new `src/cairn/verify.py` applying the rules in order on the rendered text, with the fixed expression lists (safety claims, NOAEL, wording such as "lost") in the module, and a failure that carries the rule number and a plain-language reason; rule 5 reads the quarantine state from phase 01 and its note text is fixed in code (C9) - verification: `uv run pytest tests/test_rules.py` with `test_rule_N_*` for N = 1..7, one passing and one failing fixture each - evidence: `uv run pytest tests/test_rules.py` 16 passed (one passing and one failing `test_rule_N_*` for N = 1..7, plus a clean draft and the in-order check); rule 5 fixed note built by `data_quality_note`; `npm run check` green
- [x] 8. Evaluations: `tests/evals/test_e1.py` with about 35 exact-equality assertions as fixed by decision D3 (phase 01 validation facts, the 9 screening rows with examined counts, female body weight with n, 2,821 versus 15,956 and 5.7) and `tests/evals/test_e2.py` with about 14 adversarial fixtures as fixed by decision D4, each blocked with the rule that fires, including a number coming from an instruction hidden in the data; both run in the existing `evals` job of `.github/workflows/ci.yml` because pytest collects `tests/` (C10) - verification: `uv run pytest tests/evals` at 100%, with no network and no keys, then `npm run check` - evidence: `uv run pytest tests/evals` 50 passed offline (E1 34 tests over the frozen literals: 14 validation facts, death, 9 screen rows plus row count, female weight, TK; E2 14 fixtures, rules fired: 1 x2, 2 x1, 3 x3, 4 x1, 5 x2, 6 x3, 7 x2, plus the has-14 and fixed-draft checks); `npm run check` green, 151 tests, coverage 99%
- [ ] 9. Clean clone, brand grep and adversarial review before the PR: fresh clone with `uv sync` and `npm run check`; brand grep of the PRD company, person and place terms over tracked files, the `main...HEAD` diff and the commit messages; no GxP validation claim added; independent review with sdd-review, findings in the table below (C1, C21) - verification: fresh clone output green, grep with 0 hits, review table filled - evidence:
- [ ] 10. Delivery and the bad PR: push `fase-02-tools-agent` and open the phase PR to `main`, not merged, with the required `evals` check green; then branch `bad-pr-relax-rule-3` from the phase tip with a single commit that relaxes rule 3, opened as a draft PR labelled "do not merge" whose `evals` check is red because E2 fixtures stop being blocked; while the phase PR is open the bad PR targets `fase-02-tools-agent` so its diff is that one change, and it is retargeted to `main` once the user merges the phase PR (C19, C21) - verification: `gh pr checks` on both PRs (phase green, bad PR red on `evals` with failing E2 fixtures), `gh pr view` showing draft and the label, branch protection of `main` read with `gh api` still requiring `evals` - evidence:

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E4 | ejecutor (Opus) | Split and freeze the spec, update the master plan, write this plan | done | 391f70a, f4a812e |
| E5 | ejecutor (Sonnet) | Increments 1-4: Observation, read-only DuckDB and the four study tools | done | 06c42b6, 4995fbb, 1e8f5c7, f0df120; 66 tests, coverage 98.93% |
| E6 | ejecutor (Sonnet) | Increments 5-6: registry over MCP, REST and CLI; typed content and renderer | done | 2a65f4d, 5209cb5; 76 tests, coverage 99.06%; REST and CLI skip argument validation, fixed in E7 |
| E7 | ejecutor (Sonnet) | Argument validation on REST and CLI; increments 7-8: verifier rules 1-7, E1 and E2 | done | validation fix, verifier, evals; 151 tests, coverage 99% |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|

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
