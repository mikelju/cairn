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
- [x] 1. Failing test on the real path, root cause, fix, re-record if needed.
- [x] 2. Re-run C3 and update this record.

## Decisions
Root cause: the prompt (question-3) told the model to answer with one sentence citing the screen's examined count and never to name tissues, findings or sexes, so the model obeyed and wrote a count sentence; "shown above" was the model's own words, and the table sits in the right column beside the answer.
The tool output already carries `findings.N.tissue`, `.finding` and `.sex`, so no tool change was needed.
Fix: prompt question-4 asks for one sentence naming one finding (tissue and finding by ref) and its sexes by ref, with no counts and no table position, and tells the model to decline Q6-type requests in plain text.
The first re-recordings of question-4 drifted: a two-finding sentence broke the 93-word cap, and one prompt variant made Q6 answer instead of decline; both were fixed in the prompt, not by changing criteria.
Q6 is re-recorded too because the prompt version is part of the recording key; its outcome is still declined.
Test fixtures only got the new `prompt_version`.
Existing tests that pinned the old count sentence were updated (real-recording text, toggle marker; the count-consistency test now runs on the fixture only, since the real prose no longer states a count).
Recording cost: three runs of Q2 and Q6 with Bedrock Opus 4.6, 0.0749 + 0.1094 + 0.0589 = 0.243 USD, 0.059 USD for the kept recordings; within the 5 USD limit.


### Update after the user decision U1 (prompt question-5)
The prose now says how many findings passed the screen and names the clearest one.
The count is a new code-computed value, `n_findings` in the incidence values (`src/cairn/incidence.py`), placed by reference; the model writes no digit.
"Clearest" is defined in the prompt: a finding present in both sexes; among those, the one with the most affected animals in the highest dose group of its entries.
The model picks the entry; code does not check that criterion, only that every name and number is a ref.
The 93-word cap is untouched and holds only with the short wording "N screened findings; the clearest is T F in S and S" (92 words open): the longer "N findings passed the screen; the clearest is ..." gave 96 and "N screened findings passed; ..." gave 94.
S1 (supervisor decision, kept): the prompt line telling the model to decline, in plain text, requests to state the compound is safe or to skip citations, so Q6 keeps declining.
Recording cost of this update: 0.0656 + 0.0669 + 0.0674 + one earlier run = about 0.20 USD; total of the change about 0.45 USD of the 5 USD limit.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E55 | ejecutor (Sonnet) | Reproduce, find the root cause and fix the Q2 prose with a failing-first test | done | Prompt question-4 and re-recording; see Decisions and Evidence |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | The Q2 sentence must say how many findings pass the screen (count placed by code) and name the clearest, keeping the 93-word cap | Recommended and chosen: count by reference plus the clearest finding in both sexes | answered | Cap stays at 93; count by reference and name the clearest finding (via supervisor) |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
- C1 (updated by U1): `test_q2_prose_counts_the_screened_findings_by_reference` failed before (`GLAND, ADRENAL Vacuolization passed the screen in F and M.` did not match `9 screened findings`), passes after; rendered: "9 screened findings; the clearest is GLAND, ADRENAL Vacuolization in F and M"; the count equals the 9 table rows and `n_findings`.
- C1 (first version): `tests/test_web.py::test_q2_prose_names_the_screened_findings_by_sex_and_places_no_table_position`.
  Before: failed, `the prose names no finding that passes the screen: 'The screening table examined a total of 80 animals and is shown above.'`.
  After: passed; rendered prose "GLAND, ADRENAL Vacuolization passed the screen in F and M."; no table position stated.
- C2: the toggle shows "[tissue] [finding] passed the screen in [sex] and [sex]." with no digit (`test_step2_toggle_shows_markers_and_no_digits`); every value is a ref.
- C3 after U1: `npm run check` exit 0 (324 passed); words Q2 80, Q2 open 92, Q6 39; `make demo-offline-check PLATFORM=linux/arm64` exit 0.
- C3 (first version): `npm run check` exit 0 (323 passed); word cap rendered: step 2 Q2 77, Q2 open 86 (cap 93), Q6 39; `make demo-offline-check PLATFORM=linux/arm64` exit 0 (`POST /step/2/run 200 RECORDED`); the default amd64 build failed once on DNS during `uv sync` and was not retried on amd64.

## Delivery
