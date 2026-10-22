# 001 - Step 2 animal count matches its evidence

Status: in progress

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
- [ ] 1. Reproduce on the real path and find the root cause (renderer, tool output or recording) with a failing test.
- [ ] 2. Fix at the root, keep the failing test green, re-run C3.
- [ ] 3. Deliver: push, PR to `main`, CI.

## Decisions
Records of the phase 02c closure (integrated after PR 8) travel in this branch, since records do not go to `main` directly.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E53 | ejecutor (Sonnet) | Reproduce, find the root cause and fix the step 2 animal count with a failing-first test | in progress | |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Delivery
Result, commands and observed results, resolved or pending findings, limitations and references to evidence.
