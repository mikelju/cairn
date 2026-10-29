# Phase 06 - Live question and delivery: plan and results

Status: in progress
Spec: `spec.md` (spec in review, see U1)
Base: branch `claude/fase-06-live-delivery-b608ff` from `main` at d7a68e3 (phase 05 merged, PR https://github.com/mikelju/cairn/pull/13)

## Records
- The master plan now shows phase 05 integrated and phase 06 in spec review (committed with this plan).
- PRD-term grep for phases 04 and 05 run locally on HEAD d7a68e3: 0 hits on 17 terms plus one false positive inside a Spanish word; the only 12-digit number is a GitHub Actions job id.
- User priority, literal (phase 04, still standing): "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."
- Execution by Sonnet executors; Bedrock recordings and live calls run only on the user's laptop (phase 05 U4).
- Bedrock spend so far: phase 04 0.054 USD, phase 05 0.271 USD.

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on the phase branch.
Only increment 4 calls Bedrock, and it is run by the user on the laptop; every other increment uses fake clients and fixture recordings.
Reuse, not rebuild: `gateway.py` (live client, 45 s, `max_retries=0`), `live.py` (`ask_live`, ceilings, the record commands), `pricing.call_cost`, `loop.py`, `web/__init__.py` (Explore, `_inject`, `_step2_context`), `workflow.py` (`Workflow`, `build_graph`), `recording.py`, `offline_check.py`, `tests/test_word_cap.py`, `tests/evals/`.

- [ ] 1. Live Explore behind the code and the cap: the Explore box takes a free question and the code; valid code and cap not reached run `ask_live` through the same verifier with the REAL badge; otherwise the recorded questions with 0 calls; spend per UTC day from `call_cost`, one question at a time, length limit; SEC-003 lock on the lazy index and reranker load; `docs/security.md` SEC-001 and SEC-003 rows per O1 (C2, C3, C5) - verification: `uv run pytest -k "explore_live or live_cap or live_index or gateway"` - evidence:
- [ ] 2. Step 1 switches and step 7: the switches of O3 as in-memory transforms beside `_inject`; step 7 with the content of O4 (session strip, MCP and REST call with the same hash, links, folded production table); word cap and offline check extended to step 7; screenshots at 1440x900 in `evidence/` (C6, C7) - verification: `uv run pytest -k "step1 or step7 or word_cap"`, browser walkthrough with network off - evidence:
- [ ] 3. Workflow YAML and `data-quality-memo`: one code commit that loads workflows from YAML into the `Workflow` model (O5), moves `nonclinical-summary` to YAML with E6 unchanged, adds a generic eval test over workflow case files and `make record-memo`; then one commit with 0 `.py` adding the memo YAML, prompt, eval cases and a hand-written fixture recording (C8, C9 offline part) - verification: `uv run pytest -k "workflow_config or memo"`, `tests/evals/test_e6.py`, `git show --name-only` of the memo commit - evidence:
- [ ] 4. Laptop run by the user (the only Bedrock increment): `make record-memo AWS_PROFILE=default` records W2 within the ceiling of O2 and replaces the fixture in a commit with 0 `.py`; the app served locally with the code set answers one new live question (screenshot and spend); clean clone in an empty directory with `uv sync`, `make weights`, `npm run check` and `make demo-offline-check`; then an executor verifies the recording offline and retakes the evidence (C4, C9, C10) - verification: `uv run pytest -k "recordings_metadata or memo"`; the user's pasted outputs - evidence:
- [ ] 5. Docs and adversarial review: one-screen README, ADR-002, `docs/production.md`, `make changelog` per O6 (C12); then independent review with sdd-review over the phase range, four lenses (correctness, security and data, evidence and tests, scope and maintenance), at most two rounds, confirmed findings fixed with regressions (all criteria) - verification: review table below; `make changelog` output - evidence:
- [ ] 6. Delivery and release: PRD-term and 12-digit grep (C14), push the phase branch and open the PR to `main`, not merged, with `evals` green (C1); after the user merges: the user tags v0.1.0 on the merge commit, creates the release with the CHANGELOG and evaluation summary, deploys with `make deploy` and the code, runs the timed test with two people and records the video (C11, C13) - verification: `gh pr checks`, `git tag --points-at`, `gh release view v0.1.0`, times recorded below - evidence:

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E180 | explorador | Summary of PRs 12 and 13 and PRD-term grep of phases 04 and 05 | done | Summary returned; PRD-term grep 0 hits |
| E181 | ejecutor | Draft spec and plan of phase 06 (document mode); mark phase 05 integrated | done | Spec and plan drafted, b267d69 |
| E182 | ejecutor (Sonnet) | Lavish page for phase 06 decisions | done | `.lavish/fase-06.html` (git-ignored) with 3 diagrams and the 6 open decisions as a poll |

## User decisions
Questions the supervisor raises to the user. Statuses: open, answered, deferred; closed with the literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | Spec open decisions O1-O6 and approval of the spec | See `spec.md`, Open decisions; recommended A for all six | open | |

## Deviations
| ID | Summary | Affects criteria | Status |
|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Results
Per criterion: command or walkthrough run, observed result and reference to the evidence.
Pending items, limits and what could not be checked, stated plainly.

## Candidate learnings
Only reusable lessons with a literal quote from the session; consolidated when the phase closes.
