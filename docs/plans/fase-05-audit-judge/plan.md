# Phase 05 - Audit and judge: plan and results

Status: pending
Spec: `spec.md` (draft, not yet approved)
Base: branch `fase-05-audit-judge` from the phase 04 delivery (PR https://github.com/mikelju/cairn/pull/12, not yet merged to `main`)

## Records
- User priority, literal (phase 04, still standing): "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."
- User request for this phase, literal: "arranca la spec y el plan de la 05. ya sabes, pasame un lavish bien visual para explicarme todo lo que se va a hacer y las decisiones pendientes."
- User instruction of 2026-10-28, literal: "las tareas de ejecución las deben realizar agentes sonnet 5.5".

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on the phase branch.
Only increment 3 calls Bedrock (decision O1): the agent runs `make record-judge` with the `default` AWS profile within the ceiling, and no agent reads or prints credentials or account IDs.
Reuse, not rebuild: `canonical.py` (hash), `web/threads.py` (events and per-thread lock), `workflow.py` (graph), `gateway.py`, `recording.py` and `live.py` (JUDGE_TOOL from the smoke test, `record_draft` as the model for the record command, ceilings), `verify.py` (`RULE_REASONS`), `web/` (shell, components, word cap test), `tests/evals/`.

- [ ] 1. Audit chain and SEC-002: an `audit` module with the entry, `append`, the pure `verify_chain` and the tampering of a copy; table in the threads SQLite file; events written in `web/threads.py` inside the thread lock (start, decisions, confirm, verify_final, refusals 403 and 409, approve; the judge entry arrives in increment 2); the three audit endpoints; the build records its snapshot and gather fails on a mismatch; `docs/security.md` SEC-002 row updated (C2, C3, C4, C5, C6) - verification: `uv run pytest -k "audit or snapshot"`, `tests/evals/test_e6.py`
- [ ] 2. Judge core and E5, offline: `judge` module (prompt, strict tool reusing `JUDGE_TOOL`, per-sentence call through the gateway, digit-free reason, "not judged" on refusal or truncation, kappa function); the graph node after `verify_final` that never changes `final.ok`; the judge audit entry; the E5 case file (24 cases, 4 kinds) and `tests/evals/test_e5.py` against a hand-written fixture recording under `tests/fixtures/recordings/`; E6 updated for the replay calls (C7, C8 offline part, C1) - verification: `uv run pytest -k "judge or kappa"`, `tests/evals/test_e5.py`, `tests/evals/test_e6.py`
- [ ] 3. Judge recording and calibration (the only Bedrock increment): `make record-judge` records the E5 cases, the example-decisions draft sentences and the example overstated sentence with Sonnet 4.6 in eu-west-1; prints the estimated ceiling first and the real spend after; saves only within the ceiling; writes the kappa result file; at most 2 prompt revisions, then stop and return `necesita decisión` if kappa is under the threshold (C8, C9) - verification: `uv run pytest -k "recordings_metadata or judge_replay"`, `tests/evals/test_e5.py` offline on the real files; `make record-judge` cost output
- [ ] 4. Steps 5 and 6 in the app and demo: judge panel in step 5 with the EXAMPLE row, "not judged" and the 8 checks moved per decision O6; step 6 built to the 02c mockup (rules table, chain trace, Verify chain, tamper button, REAL badge); redirect without a thread; word cap test extended; screenshots at 1440x900 in `evidence/`; offline check extended to steps 5 and 6 (C10, C11, C12, C13) - verification: `uv run pytest -k "step5 or step6 or word_cap"`, browser walkthrough with network off, `make demo-offline-check`
- [ ] 5. Adversarial review: independent review with sdd-review over the phase range, four lenses (correctness, security and data, evidence and tests, scope and maintenance), at most two rounds; confirmed findings fixed with regressions; open items after round 2 go to the user (all criteria) - verification: review table below
- [ ] 6. Delivery: PRD-term grep (needs the git-ignored PRD on the user's machine; stated if not run), push the phase branch and open the PR to `main`, not merged, with the `evals` check green (C1, C13) - verification: `gh pr checks` green, PR URL in Results

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|

## User decisions
Questions the supervisor raises to the user. Statuses: open, answered, deferred; closed with the literal answer.

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
Pending items, limits and what could not be checked, stated plainly.

## Candidate learnings
Only reusable lessons with a literal quote from the session; consolidated when the phase closes.
