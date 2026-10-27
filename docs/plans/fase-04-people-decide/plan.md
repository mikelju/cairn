# Phase 04 - People decide: plan and results

Status: draft
Spec: `spec.md` (draft)
Base: branch `claude/fase-04-people-decide-0d45bc` from `main` at 047f764 (phase 03 merged, PR #11)

## Records
- The master plan now shows phase 03 integrated and phase 04 in progress (committed with this plan).
- User priority for this phase, literal: "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on `claude/fase-04-people-decide-0d45bc`.
Only increment 2 calls Bedrock (decision O1): the agent runs `make record` with the `default` AWS profile, and no agent reads or prints credentials or account IDs.
Reuse, not rebuild: `content.py` (parts), `render.py`, `verify.py` (rules 1-8), `tools.py` (`REGISTRY`), `retrieval.py` (cache for NS1 and NS2), `gateway.py` and `recording.py` (replay and record), `web/` (shell, components, HTMX, word cap test), `tests/evals/` (E1, E2).

- [ ] 1. Decisions core, no graph and no UI: `DecisionRef` in `content.py`; a `Decision` record and slot enumeration from the `incidence` and `body_weight_change` Observations; renderer placing decisions or an empty slot; rules 1, 2 and 6 extended with passing and failing fixtures; NOAEL rule as a pure function with the not-examined flag and the step 3 definition `QuoteRef`; the example decision set and its E1 assertion (C2, C3) - verification: `uv run pytest -k "decisionref or rule_6 or noael_rule"`, `tests/evals/test_e1.py`, `test_e2.py`
- [ ] 2. Workflow and draft: add `langgraph` and `langgraph-checkpoint-sqlite`; the graph gather -> draft -> await_decisions -> verify_final -> await_approval -> approve with AsyncSqliteSaver and two interrupts; the workflow as a small Pydantic model (decision O4); the draft prompt and call through the gateway, first against a hand-written fixture under `tests/fixtures/recordings/`, then one real recording under `recordings/` within the O1 ceiling (C4, C5) - verification: `uv run pytest -k "workflow or recordings"`; `make record` cost output
- [ ] 3. API and E6: endpoints to record decisions (recompute, re-render, re-verify with 0 model calls), confirm and approve; actor per request and author check (decision O3); 403, 409 and idempotent resume; `tests/evals/test_e6.py` in the `evals` check (C6, C7) - verification: `uv run pytest -k "api_ or resume" tests/evals/test_e6.py`
- [ ] 4. Steps 4 and 5 in the app, demo and deployment: templates built to the 02c mockups under decision O2, HTMX recompute on each dropdown change, fill-example and role buttons, 403 banner, word cap test extended, screenshots at 1440x900 in `evidence/`, offline check extended (C8, C9, C10) - verification: `test_word_cap`, browser walkthrough with network off, `make demo-offline-check`
- [ ] 5. Adversarial review: independent review with sdd-review over `git diff 047f764`, at most two rounds; confirmed findings fixed with regressions; open items after round 2 go to the user (all criteria) - verification: review table below
- [ ] 6. Delivery: PRD-term grep, push `claude/fase-04-people-decide-0d45bc` and open the PR to `main`, not merged, with the required `evals` check green (C1, C11) - verification: `gh pr checks` green, PR URL in Results

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E157 | ejecutor (Opus) | Draft spec and plan of phase 04 (document mode) | done | fc9a814; supervisor cut the deploy out of C10 (the user deploys) |

## User decisions
Questions the supervisor raises to the user. Statuses: open, answered, deferred; closed with the literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | Spec open decisions O1-O4 and approval of the spec | See `spec.md`, Open decisions; recommended A for all four | open | |

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
