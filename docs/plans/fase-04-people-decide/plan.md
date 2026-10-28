# Phase 04 - People decide: plan and results

Status: ready locally
Spec: `spec.md` (approved, frozen)
Base: branch `claude/fase-04-people-decide-0d45bc` from `main` at 047f764 (phase 03 merged, PR #11)

## Records
- The master plan now shows phase 03 integrated and phase 04 in progress (committed with this plan).
- From 2026-10-28 the phase continues in a cloud session on branch `claude/jolly-knuth-g8jdjq`, based on the tip f2419be of `claude/fase-04-people-decide-0d45bc`; later commits on that branch are brought in by merge, never by rebase, and delivery (increment 6) pushes and opens the PR from `claude/jolly-knuth-g8jdjq`.
- User instruction of 2026-10-28, literal: "las tareas de ejecución las deben realizar agentes sonnet 5.5".
- User priority for this phase, literal: "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on `claude/fase-04-people-decide-0d45bc`.
Only increment 2 calls Bedrock (decision O1): the agent runs `make record` with the `default` AWS profile, and no agent reads or prints credentials or account IDs.
Reuse, not rebuild: `content.py` (parts), `render.py`, `verify.py` (rules 1-8), `tools.py` (`REGISTRY`), `retrieval.py` (cache for NS1 and NS2), `gateway.py` and `recording.py` (replay and record), `web/` (shell, components, HTMX, word cap test), `tests/evals/` (E1, E2).

- [x] 1. Decisions core, no graph and no UI: `DecisionRef` in `content.py`; a `Decision` record and slot enumeration from the `incidence` and `body_weight_change` Observations; renderer placing decisions or an empty slot; rules 1, 2 and 6 extended with passing and failing fixtures; NOAEL rule as a pure function with the not-examined flag and the step 3 definition `QuoteRef`; the example decision set and its E1 assertion (C2, C3) - verification: `uv run pytest -k "decisionref or rule_6 or noael_rule"`, `tests/evals/test_e1.py`, `test_e2.py`
  - Evidence: `uv run pytest -k "decisionref or rule_6 or noael_rule"` 15 passed; `tests/evals/test_e1.py` and `test_e2.py` 53 passed; `npm run check` green. `DecisionRef` is hidden from the JSON schema (`SkipJsonSchema`) so the question loop's tool schema hash and the phase 03 recordings are unchanged; the draft schema of increment 2 must add it back. New module `src/cairn/decisions.py` (slots, `Decision`, `noael_rule`, example set); the NOAEL definition quoted is `FDA-IV-01.s2`, returned by NS1.
- [x] 2. Workflow and draft: add `langgraph` and `langgraph-checkpoint-sqlite`; the graph gather -> draft -> await_decisions -> verify_final -> await_approval -> approve with AsyncSqliteSaver and two interrupts; the workflow as a small Pydantic model (decision O4); the draft prompt and call through the gateway, first against a hand-written fixture under `tests/fixtures/recordings/`, then one real recording under `recordings/` within the O1 ceiling (C4, C5) - verification: `uv run pytest -k "workflow or recordings"`; `make record` cost output
  - Evidence (offline part, E160): `uv run pytest -k "workflow or recordings"` 22 passed against `tests/fixtures/recordings/draft.json`; `npm run check` green. New `src/cairn/workflow.py` (Workflow model, draft schema with DecisionRef, graph with two interrupts, pure `verify_final`), `src/cairn/prompts/draft.md`, `cairn record-draft` and `make record-draft`. Still pending: the real recording under `recordings/draft.json` (`make record-draft AWS_PROFILE=default`); this increment stays unticked until then.
  - Evidence (real recording, E161): `make record-draft AWS_PROFILE=default` with `opus-4-6` (Bedrock eu-west-1), 1 attempt, 1 call, 0.054 USD spent (ceiling 2 USD); `recordings/draft.json` saved only after the example decision set verified green; no prompt change; `uv run pytest -k "workflow or recordings"` 24 passed offline including the real file; `npm run check` green.
- [x] 3. API and E6: endpoints to record decisions (recompute, re-render, re-verify with 0 model calls), confirm and approve; actor per request and author check (decision O3); 403, 409 and idempotent resume; `tests/evals/test_e6.py` in the `evals` check (C6, C7) - verification: `uv run pytest -k "api_ or resume" tests/evals/test_e6.py`
  - Evidence: 13 cases in `tests/evals/test_e6.py` (pauses, 403 on confirm and approve, 409 not at pause or red verify_final, idempotent resume, example set and 4 other forms incl. female NOAEL "not established") green offline; every case asserts the only model call is the draft at start; `npm run check` green.
- [x] 4. Steps 4 and 5 in the app, demo and deployment: templates built to the 02c mockups under decision O2, HTMX recompute on each dropdown change, fill-example and role buttons, 403 banner, word cap test extended, screenshots at 1440x900 in `evidence/`, offline check extended (C8, C9, C10) - verification: `test_word_cap`, browser walkthrough with network off, `make demo-offline-check` - evidence (2026-10-28, after round 2 fixes, HEAD 7da54c2): `npm run check` exit 0, 556 passed, coverage 97.17%; `make demo-offline-check` green, but the image build needed a proxy CA for `uv sync` (a local Dockerfile copy with the CA, not committed; plain `make` fails at that step in this container); four PNGs at 1440x900 in `evidence/` taken offline (replay), scrollHeight 900 on each page (no vertical overflow)
- [x] 5. Adversarial review: independent review with sdd-review over `git diff 047f764`, at most two rounds; confirmed findings fixed with regressions; open items after round 2 go to the user (all criteria) - verification: review table below
  - Evidence: two rounds in the Adversarial review table; round 1 fixed in E165, round 2 fixed in E167 with regressions; no open finding; the accepted limits of round 2 go to the user with the delivery.
- [x] 6. Delivery: PRD-term grep, push `claude/fase-04-people-decide-0d45bc` and open the PR to `main`, not merged, with the required `evals` check green (C1, C11) - verification: `gh pr checks` green, PR URL in Results
  - Evidence (2026-10-28, E168): PR https://github.com/mikelju/cairn/pull/12 from `claude/jolly-knuth-g8jdjq` (head 3116c44), not merged; `evals` on the pull_request run green, https://github.com/mikelju/cairn/actions/runs/40669269888/job/122751619793; the push-event run https://github.com/mikelju/cairn/actions/runs/40669117684 stayed in progress with no update since start (GitHub side, not a failure). `claude/fase-04-people-decide-0d45bc` had no commits beyond f2419be, so nothing to merge in. C11 12-digit grep over tracked files (excluding `data/` and lock files), added lines of `git diff main...HEAD` and commit messages: no AWS account ID, only hex hashes; no GxP claim added. PRD-term grep NOT run: `docs/PRD_Cairn.pdf` is not in the cloud container; the user must run it locally before merging.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E157 | ejecutor (Opus) | Draft spec and plan of phase 04 (document mode) | done | fc9a814; supervisor cut the deploy out of C10 (the user deploys) |
| E158 | ejecutor (Sonnet) | Increment 1: DecisionRef, slots, rules 1, 2 and 6, NOAEL rule, E1 example set | done | 778f72a; 48 tests of decisions and E1 rerun by the supervisor, green |
| E159 | ejecutor (Sonnet) | Increment 2: LangGraph workflow, draft prompt, one Bedrock recording under 2 USD | done | partial; remainder done in E160 and E161; ff6d4c0: dependencies only (sqlite-vec skipped on Windows ARM64 by a uv override); context budget ran out; 0 USD spent |
| E160 | ejecutor (Sonnet) | Increment 2 without Bedrock: workflow module, draft schema and prompt, hand-written fixture, tests, `record-draft` target | done | 68f00bf; 22 workflow and recording tests rerun offline by the supervisor, green |
| E161 | ejecutor (Sonnet) | Increment 2 closing: one real draft recording with `make record-draft`, ceiling 2 USD | done | 183e731; opus-4-6, 1 attempt, 0.054 USD of 2; 24 tests rerun offline by the supervisor, green |
| E162 | ejecutor (Sonnet) | Increment 3: API for decisions, confirm and approve, 403, 409, idempotent resume, E6 | done | 3dd8517; E6 rerun offline by the supervisor, green; threads in `:memory:` unless `CAIRN_THREADS_DB` is set |
| E163 | ejecutor (Sonnet) | Increment 4: steps 4 and 5 to the 02c mockups, HTMX, word cap, offline check | done | partial; remainder done in E167; 06a827d; steps 4 and 5 work end to end offline, 24 targeted tests green; screenshots, full `npm run check` and `make demo-offline-check` pending (browser pane refused localhost; slow machine) |
| E164 | ejecutor (Sonnet) | Increment 4 closing: screenshots at 1440x900, full `npm run check`, `make demo-offline-check` | cancelled | ran in a local session; its screenshots were never committed and no full check was recorded; superseded by E166 and E167 in a cloud session |
| E165 | ejecutor (Sonnet) | Round 1 review fixes F1-F6 with regressions | done | 281dca3 and f2419be; verified by R3 |
| E166 | ejecutor (Opus) | Increment 4 closing on branch `claude/jolly-knuth-g8jdjq` | cancelled | stopped by the supervisor because the user asked for Sonnet executors; its untracked screenshots were reused by E167 |
| E167 | ejecutor (Sonnet) | Round 2 fixes A1-A4 and increment 4 closing | done | 7bd32d0, 7da54c2, 1485f70; targeted tests 80 passed, rerun by the supervisor; `npm run check` exit 0, 556 passed, 97.17% |
| E168 | ejecutor (Sonnet) | Delivery: merge check with the local branch, C11 grep, push, PR to `main`, checks | done | d3fd27b; nothing new on `claude/fase-04-people-decide-0d45bc`; PR https://github.com/mikelju/cairn/pull/12; `evals` on the PR head green; PRD-term grep pending for the user |

## User decisions
Questions the supervisor raises to the user. Statuses: open, answered, deferred; closed with the literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | Spec open decisions O1-O4 and approval of the spec | See `spec.md`, Open decisions; recommended A for all four | answered | "Apruebo la spec de la fase 04 con A en O1, O2, O3 y O4, incluido un gasto máximo de 2 USD en Bedrock con el perfil default para la grabación del borrador." |

## Deviations
| ID | Summary | Affects criteria | Status |
|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|
| 1 (R1, R2) | local revisores, previous session | `git diff 047f764` up to 06a827d | correctness, security and data (the round's reports were not recorded; reconstructed from commits 281dca3 and 46a8d93) | F1 concurrent confirm/approve/decisions on one thread (TOCTOU); F2 any `author` accepted, so the reviewer could confirm their own draft; F3 doses unvalidated (1e9, negatives, NaN -> 500); F4 step pages 500 on bad input, raw JSON on 409, invented actor; F5 prompt edits did not make the recording stale; F6 `record-draft` did not print or check real spend; SEC-001 widened with the thread endpoints. Fixed in E165 | closed |
| 2 (R3, R4) | local revisores | R3: `git diff 46a8d93 f2419be`; R4: `git diff 047f764 f2419be` | R3 correctness with authorization; R4 evidence and tests | F1-F6 confirmed fixed on the real path (R3 reverted the per-thread lock in a scratch copy and the race test failed 3 of 3). Confirmed and fixed in E167: A1 adverse onset without treatment-related onset, or the control dose, accepted; A2 `record-draft` cost printed with 2 decimals; A3 draft replay test green without DecisionRefs; A4 no test of the HTMX recompute happy path; stale evidence for C1 and C6-C10 (refreshed in E167). Accepted limits, not fixed: the per-thread lock map grows for unknown thread ids (as thread storage already does); `record-draft` saves before the ceiling check and compares the per-call ceiling, not the phase budget (only 0.054 USD spent, no recording planned) | closed |

## Results
Per criterion: command or walkthrough run, observed result and reference to the evidence.
Pending items, limits and what could not be checked, stated plainly.

- C1: `npm run check` exit 0, 556 passed, coverage 97.17% after the last code change (E167); `evals` green on the PR head (E168).
- C2-C7: increments 1-3 and E6, refreshed after the round 1 and round 2 fixes; targeted E6, web and workflow tests 80 passed, rerun by the supervisor.
- C8-C10: increment 4 evidence (four screenshots at 1440x900 with no overflow, HTMX recompute test, `make demo-offline-check` exit 0).
- C11: 12-digit and GxP grep clean (E168).
- Pending for the user: the PRD-term grep, which needs the git-ignored PRD on the user's machine.
- Limits: `make demo-offline-check` passed in the cloud container only with an uncommitted proxy-CA build context; the per-thread lock map grows for unknown thread ids; `record-draft` saves before its per-call ceiling check.

## Candidate learnings
Only reusable lessons with a literal quote from the session; consolidated when the phase closes.
