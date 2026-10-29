# Phase 05 - Audit and judge: specification

Status: approved (frozen 2026-10-28)
Approved by the user: 2026-10-28 (decisions O1-O7 option A, see `plan.md` U1; audit chain reduced to a minimal one by U2)
Master plan: `../0_plan_maestro.md`
Definitions of phases 02a to 04 (Observation, ValueRef, QuoteRef, DecisionRef, rules 1-8, renderer, gateway, recordings, the `nonclinical-summary` workflow, the thread API, E1-E4 and E6, steps 4 and 5) apply unchanged unless this spec extends them.

## Objective
Leave a draft that is audited and second-read: every event of a workflow session goes into a minimal SHA-256 hash chain that a pure function can verify and that tests prove fails when an entry is edited, and a Sonnet judge, calibrated against labelled cases (E5, kappa), reads the final text and warns about wording that overstates the data.
It adds the judge panel to step 5, builds step 6 with a one-line chain status, and completes the milestone "full walkthrough of steps 1 to 6".
It is needed now because the draft and the people's decisions exist since phase 04, and phase 06 only adds the live question, step 7 and delivery.
Priority set by the user (phase 04, still standing): the minimum that meets each criterion, no extra abstractions, configuration or speculative tests, reuse what phases 01-04 built.
The user judged the full audit chain unnecessary for a demo (plan U2), so it is kept minimal: the demo says what it is and what production would use.

## Scope
In:
- Audit chain per session (a session is a workflow thread), minimal: an append-only list of entries `seq`, `ts`, `actor`, `action`, `payload`, `prev_hash`, `hash`; `hash` is the canonical SHA-256 (`canonical.py`) of the other fields; the first `prev_hash` is 64 zeros.
  Events chained (decision O3): thread started (snapshot hash, draft recording model and date), decisions recorded, NOAEL confirmed, verify_final verdict, judge run (counts only), approval refused (403 or 409) and approved.
  Entries are written inside the per-thread lock of `web/threads.py`, next to the state change they describe, in a new table of the same SQLite file as the threads.
- Verify (decision O4 as amended by U2): a pure `verify_chain` function and one read-only endpoint `GET /api/threads/{id}/audit/verify` returning the entry count and ok, or the first broken entry.
  Tampering (edit, delete, swap, insert on a copy) is shown by tests only; the app has no way to alter or to simulate altering a chain.
- SEC-002 closed (decision O7): the Observations of a session claim a snapshot only if the DuckDB build in use was made from it.
- Judge: one call per final-text sentence through the existing gateway to Sonnet 4.6 (the drafter is Opus 4.6), strict tool `judge_verdict` (verdict, category, short reason), `stop_reason` read by the gateway, reason text rejected if it holds a digit.
  The judge sees the sentence and the Observation facts it cites; it warns and never blocks: `verify_final` and approval do not read it.
  It runs as a graph node after `verify_final` and before `await_approval`.
- E5 (decision O2): a file of labelled cases (faithful or overstated, with the kind of overstatement), the kappa of the judge against the labels computed by code, and a threshold on it.
- Judge recordings (decisions O1 and O5): E5 cases, the example-decisions draft sentences and one example overstated sentence, recorded once from Bedrock and replayed everywhere; the judge never runs live in the demo.
- Step 5 gains the judge panel to the 02c mockup; step 6 is built (decision O6): rules table to the 02c mockup, one status line for the chain (for example "Audit chain: 9 entries, verified") and the note "In production -> external append-only log".
- Tests for the chain (including the tampering cases) and E5 in the `evals` check; word cap, offline check and screenshots extended to steps 5 and 6.

Out:
- Live judge anywhere, judge in Explore, multi-dimension rubric, reject and redo with diff (deferred past v0.1.0 by the master plan).
- Live question and access code, remaining step 1 switches, step 7, `data-quality-memo` and its workflow loader, clean-clone and timed tests, documentation and v0.1.0 (phase 06).
- An external or append-only log, signatures, real identity, GxP or Part 11 claims; a CLI for the chain; a listing endpoint or any display of individual entries or hashes in the app (decision O4, U2).
- Changes to the master plan, to phases 01-04 criteria, to the rules, the NOAEL rule or the draft prompt.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | `uv sync` and `npm run check` pass from a clean clone with no network: ruff, strict mypy, pytest with coverage of at least 85% on `src/cairn`, hooks; E1, E2, E4 and E6 still pass (E6 updated only for the judge replay calls) | Fresh clone; CI green on the PR |
| C2 | A session builds its chain: each entry stores the hash of the previous one, the first stores 64 zeros, `hash` equals the canonical SHA-256 of the entry's other fields; two runs with the same inputs and timestamps give the same hashes; verify on an untouched chain reports ok with the entry count | pytest `test_audit_chain_*` |
| C3 | Every event of decision O3 is chained, in order, on the API path of the example walkthrough (start, decisions, confirm, verify_final, judge, approve); a 403 and a 409 each add a refusal entry naming actor and reason; a failed request that changes nothing (422, 404) adds none | pytest `test_audit_events_*` on a temporary SQLite file |
| C4 | Tampering is detected, shown by tests only: on a copy, changing any field of any entry, deleting an entry, swapping two entries, or inserting one makes verify report not ok and name the first broken `seq`; truncating the tail is detected only against a head hash given to verify, and the test states that limit; the stored chain is identical before and after | pytest `test_audit_tamper_*` (parametrized over the cases) |
| C5 | `GET /api/threads/{id}/audit/verify` returns the entry count and ok, or the first broken entry; an unknown thread returns 404; it is the only audit endpoint and nothing in the API changes the stored chain | pytest `test_api_audit_*` |
| C6 | SEC-002 is closed: with a DuckDB build whose snapshot differs from the manifest, gathering fails with a clear error instead of producing Observations that claim the pinned snapshot; with the real build it passes; `docs/security.md` row updated | pytest `test_snapshot_*`; row read in the diff |
| C7 | The judge returns one structured verdict per sentence (supported or overstated, category, reason); a reason with a digit is dropped and the verdict stays; a refusal or truncation gives "not judged" rather than a verdict; the judge model is not the drafter's; warnings never change `final.ok` and approval by the reviewer still succeeds with warnings present | pytest `test_judge_*`, `test_judge_warns_never_blocks` |
| C8 | E5: the file holds at least 24 labelled cases with both labels and at least 3 kinds of overstatement; kappa of the recorded judge against the labels is computed by code (checked on hand-computed examples) and is at least the threshold of decision O2; the result, `n` and kappa are written to a file the panel reads; changing the judge prompt or schema makes the recording stale and fails the test | pytest `tests/evals/test_e5.py` in the `evals` check; `test_kappa_*` |
| C9 | Judge recordings are in git, each from Bedrock in eu-west-1 with model, region, date, latency, tokens and cost; they replay offline; a sentence without a recording shows "not judged" and never an invented verdict; total spend of this phase stays under the ceiling of decision O1 | pytest `test_recordings_metadata_*`, `test_judge_replay_*`; `make record-judge` cost output |
| C10 | Step 5 at 1440x900 with network off, to the 02c mockup: the judge panel lists each warning with sentence, category and reason, says it warns and never blocks, shows "judge, model, n, kappa", carries the RECORDED badge and an example overstated sentence labelled EXAMPLE; approval still works with warnings; no scroll and within the word cap | Browser walkthrough with screenshots in `evidence/`; `test_word_cap` extended |
| C11 | Step 6 at 1440x900 with network off, REAL badge: the 8 rules with result and note for this session (02c mockup table), one chain status line from the verify endpoint (for example "Audit chain: 9 entries, verified") and the note "In production -> external append-only log"; no scroll and within the word cap; without a thread it redirects like step 5 | Browser walkthrough with screenshots; `test_word_cap` extended; pytest `test_step6_*` |
| C12 | `make demo` serves the full walkthrough of steps 1 to 6 from a clean clone with network off; deploying the merged PR is done by the user and is outside this phase | `make demo-offline-check` extended |
| C13 | No company name, logo or colour from the PRD, no third-party person's name and no AWS account ID in the repo or the app; no GxP claim; step 6 says the chain detects edits and is not a validated or external log | Local grep of PRD terms and 12-digit literals over tracked files, diff and commit messages before every push; screenshot text |

## Constraints and risks
- Bedrock spend needs the user's go-ahead (decision O1). Estimate on Sonnet 4.6 (3 USD input and 15 USD output per million tokens): about 1.5k input and 0.2k output tokens per judged sentence, about 0.0075 USD; 24 E5 cases plus about 20 draft sentences plus the example is about 0.35 USD per full pass (estimate). Prompt revisions during calibration re-record E5, so a few passes fit well under 2 USD.
- The 5.5 models stay unavailable (02b deviation D2): the judge is Sonnet 4.6, as ADR-001 already chose, and the badge says so.
- Calibration weakness: with labels written by us, kappa measures agreement with our definition of overstatement, not with independent experts, and 24 cases give a wide uncertainty. The panel states `n` and the label source; the spec does not claim more.
- The draft text is mostly code-placed, so on the real draft the judge is expected to find few or no warnings; that is a correct result, and the example sentence and E5 are what show the warning behaviour.
- A chain detects edits, deletions, swaps and insertions by someone who does not recompute every later hash; it does not stop an actor who rewrites the whole chain or cuts its tail, and the store is the same ephemeral SQLite file as the threads. The step 6 note "In production -> external append-only log" says so.
- Threads and their chains live in `:memory:` unless `CAIRN_THREADS_DB` is set, so a restart empties the chain (as it already empties the thread).
- The judge changes the graph after `verify_final`, so threads checkpointed before this phase are not resumable; the demo has none that matter.
- A judge call per sentence adds replay lookups after confirm; with decisions other than the example set most sentences have no recording and show "not judged" (decision O5). This is stated on screen, not hidden.
- Step 5 and step 6 word caps (93) are tight; step 6 carries a rules table, one status line and one note.

## Assumptions
- A session is a thread; "per-session chain" means one chain per thread id, not one for the whole server.
- The judge reads the final rendered text, so it runs once, after the reviewer confirms; recording decisions still makes 0 model calls.
- The judge reason is shown only if it contains no digit (global criterion: no free numbers); verdicts and categories are fixed words.
- Categories of overstatement come from the existing wording rules and master plan: causal wording ("caused"), loss or certainty wording ("lost", "proved"), safety claim, and magnitude wording not supported by the counts.
- The hash is computed with the existing canonical JSON hash; no new dependency.
- The two demo users stay SIMULATED; the audit actor is the demo user or the name of the judge model, never a real identity.

## Open decisions
All decided by the user on 2026-10-28 (plan U1 and U2); none open.

| ID | Decision | Chosen option |
|---|---|---|
| O1 | Bedrock spend and model for the judge recordings | A: Sonnet 4.6, ceiling 2 USD for the phase, `default` AWS profile; no agent reads or prints credentials or account IDs |
| O2 | E5 calibration set | A: 24 cases built by code from the study's findings (12 faithful, 12 overstated in 4 kinds), the user reads the list before recording; kappa threshold 0.70; if kappa stays under it after 2 prompt revisions, work stops and returns to the user |
| O3 | What the audit chain covers and where it lives | A: every workflow event listed in Scope, in a new table of the same SQLite file as the threads |
| O4 | How verify and tampering are shown | A as amended by U2: tampering (edit, delete, swap, insert on a copy) is shown by tests only; the API has one read-only verify endpoint and step 6 one status line |
| O5 | Does the judge run live or only replayed | A: replayed only; a sentence without a recording is "not judged" |
| O6 | Where the 8 rule checks live | A: step 6 rules table; step 5 keeps one line "Rules: 8 of 8 passed, see step 6" |
| O7 | SEC-002 | A: closed in this phase; the build records its snapshot and gather fails if it differs from the manifest |
