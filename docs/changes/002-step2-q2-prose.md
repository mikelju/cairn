# 002 - Step 2 Q2 prose answers the question

Status: in progress

## Contract
Goal and reason: the Q2 prose says "The screening table examined a total of 80 animals and is shown above."
It does not answer the question (which findings increase with dose versus control, by sex) and the table is beside the answer, not above it.
The prose should name the findings that pass the screen and their sex; the code keeps placing every number and every quotation.
Found during the phase 02c walkthrough; logged there as a follow-up outside the phase.
Out of scope: other steps, visual design, other questions (Q6 is only re-recorded because the prompt version is part of its key), the screening rule itself.
Constraints / decisions that need the user: the word cap of 93 words with the toggle open is frozen; if the new prose does not fit, stop and ask.
Current authorisation and limits: standalone change in its own worktree; re-recording with Bedrock is authorised within the existing 5 USD ceiling; no push and no PR in this brief.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | On the real user path (step 2 run in RECORDED mode), the Q2 prose names the findings that pass the screen and their sex, and states no false table position | Test that renders step 2 through the app, failing before the fix and passing after; rendered text |
| C2 | Every number in the prose is placed by code by reference; the model writes no digit and no number word | Test or code reference; toggle shows markers and no digit |
| C3 | No regression: `npm run check` green, step 2 states within the word cap (93 with the toggle open) and `make demo-offline-check` passes | Command output |

## Plan
- [ ] 1. Failing test on the real path, root cause, fix, re-record if needed.
- [ ] 2. Re-run C3 and update this record.

## Decisions

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E55 | ejecutor (Sonnet) | Reproduce, find the root cause and fix the Q2 prose with a failing-first test | in progress | |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence

## Delivery
