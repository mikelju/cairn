# 001 - Step 2 animal count matches its evidence

Status: integrated

## Contract
Goal and reason: the step 2 answer says "examined a total of 80 animals" while its evidence line says "n=80, 37 animals"; the visible sentence and the evidence must state the same count, placed by code from the data.
Found during the phase 02c walkthrough; logged there as a follow-up outside the phase.
Out of scope: other steps, visual design, new questions, re-recording live runs unless the root cause requires it.
Constraints / decisions that need the user: none expected; if the fix needs new recordings or changes a frozen criterion of an earlier phase, ask first.
Current authorisation and limits: the user asked for this as a standalone change in its own worktree; delivery is a PR to `main` on `origin`, not merged.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | On the real user path (step 2 run in RECORDED mode), the answer sentence states the number of animals examined consistently with the evidence line: no sentence says 80 animals examined when the evidence counts 37 | Test that renders step 2 through the app, failing before the fix and passing after; rendered text |
| C2 | The count in the sentence comes from the same data as the evidence line (code places it), not from model text or a hand-written literal | Test or code reference showing the single source |
| C3 | No regression: `npm run check` green, step 2 states stay within the word cap (93 with the toggle open) and `make demo-offline-check` passes | Command output |

## Plan
- [x] 1. Reproduce on the real path and find the root cause (renderer, tool output or recording) with a failing test.
- [x] 2. Fix at the root, keep the failing test green, re-run C3.
- [x] 3. Deliver: push, PR to `main`, CI.

## Decisions
Root cause: the two figures were different quantities with the same label.
The sentence places `n_examined` of the incidence Observation by reference (80: distinct main-study animals with at least one examined tissue, `EXAMINED_ANIMALS_SQL`), which is correct for "examined".
The evidence line printed `n=80` from that same field, then "37 animals" as the distinct animals in `source_rows`, which for incidence are only the animals affected by the screened findings (`AFFECTED_ANIMALS_SQL`), so "37 animals" read as a contradictory total.
The recording (RECORDED mode) is correct and untouched: the sentence references a field, and no re-recording is needed.
Fix: `_evidence` in `src/cairn/web/__init__.py` labels the source count of incidence observations "affected" instead of "animals" (same word count, other tools keep "animals").
The sentence keeps 80, placed by code from `n_examined`, the same field as the evidence `n`.
Records of the phase 02c closure (integrated after PR 8) travel in this branch, since records do not go to `main` directly.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E53 | ejecutor (Sonnet) | Reproduce, find the root cause and fix the step 2 animal count with a failing-first test | done | Mislabelled affected-animal count in the evidence line fixed with a failing-first test; see Decisions and Evidence |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
- C1: `tests/test_web.py::test_q2_sentence_and_evidence_state_the_same_examined_count` (fixture and real recording) and the updated `test_q2_evidence_counts_distinct_animals_not_source_rows`.
  Before the fix: `uv run pytest tests/test_web.py -k "same_examined_count or distinct_animals" --no-cov` gave 3 failed (`assert 'animals' == 'affected'`, `'37 affected, from ' not in` the page).
  After: 3 passed.
- C2: sentence count and evidence `n` both come from `Observation.n_examined` (the sentence through the `ValueRef`, the evidence through `_evidence`); the test compares them on the rendered page.
- C3: `npm run check` exit 0 (ruff, mypy, 323 passed including `tests/test_word_cap.py` with cap 93, hooks tests); `make demo-offline-check` exit 0 (`POST /step/2/run 200 RECORDED`).

## Delivery
Result, commands and observed results, resolved or pending findings, limitations and references to evidence.

Result: the step 2 evidence line now reads "n=80, 37 affected" so it no longer contradicts the sentence's 80 examined animals; the fix is the label in `_evidence` (`src/cairn/web/__init__.py`).
Checks after the last change: `npm run check` exit 0; `make demo-offline-check` OK (see Evidence).
Adversarial review: not run for this one-word label change; no findings open.
Limitations: none known; recordings untouched.
Branch `cambio-001-step2-animal-count` also carries the phase 02c closure records (69633c6).
PR: https://github.com/mikelju/cairn/pull/9 - CI green (evals pass on both runs).
