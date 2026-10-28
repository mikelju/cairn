# Phase 05 - Audit and judge: specification

Status: draft
Approved by the user: pending
Master plan: `../0_plan_maestro.md`
Definitions of phases 02a to 04 (Observation, ValueRef, QuoteRef, DecisionRef, rules 1-8, renderer, gateway, recordings, the `nonclinical-summary` workflow, the thread API, E1-E4 and E6, steps 4 and 5) apply unchanged unless this spec extends them.

## Objective
Leave a draft that is audited and second-read: every event of a workflow session goes into a SHA-256 hash chain that anyone can verify and that visibly fails when an entry is edited, and a Sonnet judge, calibrated against labelled cases (E5, kappa), reads the final text and warns about wording that overstates the data.
It adds the judge panel to step 5, builds step 6, and completes the milestone "full walkthrough of steps 1 to 6".
It is needed now because the draft and the people's decisions exist since phase 04, and phase 06 only adds the live question, step 7 and delivery.
Priority set by the user (phase 04, still standing): the minimum that meets each criterion, no extra abstractions, configuration or speculative tests, reuse what phases 01-04 built.

## Scope
In:
- Audit chain per session (a session is a workflow thread): an append-only list of entries `seq`, `ts`, `actor`, `action`, `payload`, `prev_hash`, `hash`; `hash` is the canonical SHA-256 (`canonical.py`) of the other fields; the first `prev_hash` is 64 zeros; the head hash is shown.
  Events chained (decision O3): thread started (snapshot hash, draft recording model and date), decisions recorded, NOAEL confirmed, verify_final verdict, judge run (counts only), approval refused (403 or 409) and approved.
  Entries are written inside the per-thread lock of `web/threads.py`, next to the state change they describe.
- Verify and tampering (decision O4): a pure `verify_chain` function; an API to read the chain and to verify it; a tampering demonstration that edits one entry of an in-memory copy and shows verify failing at the first broken entry; the stored chain is never modified.
- SEC-002 closed (decision O7): the Observations of a session claim a snapshot only if the DuckDB build in use was made from it.
- Judge: one call per final-text sentence through the existing gateway to Sonnet 4.6 (the drafter is Opus 4.6), strict tool `judge_verdict` (verdict, category, short reason), `stop_reason` read by the gateway, reason text rejected if it holds a digit.
  The judge sees the sentence and the Observation facts it cites; it warns and never blocks: `verify_final` and approval do not read it.
  It runs as a graph node after `verify_final` and before `await_approval`.
- E5 (decision O2): a file of labelled cases (faithful or overstated, with the kind of overstatement), the kappa of the judge against the labels computed by code, and a threshold on it.
- Judge recordings (decisions O1 and O5): E5 cases, the example-decisions draft sentences and one example overstated sentence, recorded once from Bedrock and replayed everywhere; the judge never runs live in the demo.
- Step 5 gains the judge panel to the 02c mockup; step 6 is built to the 02c mockup (decision O6): rules table, audit chain trace, Verify chain and the tampering demonstration.
- Tests for the chain (including E-style tampering cases) and E5 in the `evals` check; word cap, offline check and screenshots extended to steps 5 and 6.

Out:
- Live judge anywhere, judge in Explore, multi-dimension rubric, reject and redo with diff (deferred past v0.1.0 by the master plan).
- Live question and access code, remaining step 1 switches, step 7, `data-quality-memo` and its workflow loader, clean-clone and timed tests, documentation and v0.1.0 (phase 06).
- An external or append-only log, signatures, real identity, GxP or Part 11 claims; a CLI for the chain (decision O4).
- Changes to the master plan, to phases 01-04 criteria, to the rules, the NOAEL rule or the draft prompt.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | `uv sync` and `npm run check` pass from a clean clone with no network: ruff, strict mypy, pytest with coverage of at least 85% on `src/cairn`, hooks; E1, E2, E4 and E6 still pass (E6 updated only for the judge replay calls) | Fresh clone; CI green on the PR |
| C2 | A session builds its chain: each entry stores the hash of the previous one, the first stores 64 zeros, `hash` equals the canonical SHA-256 of the entry's other fields, and the head is the last hash; two runs with the same inputs and timestamps give the same hashes; verify on an untouched chain reports ok with the entry count and the head | pytest `test_audit_chain_*` |
| C3 | Every event of decision O3 is chained, in order, on the API path of the example walkthrough (start, decisions, confirm, verify_final, judge, approve); a 403 and a 409 each add a refusal entry naming actor and reason; a failed request that changes nothing (422, 404) adds none | pytest `test_audit_events_*` on a temporary SQLite file |
| C4 | Tampering is detected: changing any field of any entry, deleting an entry, swapping two entries, or inserting one makes verify report not ok and name the first broken `seq`; truncating the tail is detected only against a head hash given to verify, and the test states that limit; the stored chain is identical before and after the demonstration | pytest `test_audit_tamper_*` (parametrized over the cases) |
| C5 | The chain API returns the entries and the verify result (`GET /api/threads/{id}/audit`, `GET /api/threads/{id}/audit/verify`, `POST /api/threads/{id}/audit/tamper` returning the verify of the edited copy); an unknown thread returns 404; no endpoint changes the stored chain | pytest `test_api_audit_*` |
| C6 | SEC-002 is closed: with a DuckDB build whose snapshot differs from the manifest, gathering fails with a clear error instead of producing Observations that claim the pinned snapshot; with the real build it passes; `docs/security.md` row updated | pytest `test_snapshot_*`; row read in the diff |
| C7 | The judge returns one structured verdict per sentence (supported or overstated, category, reason); a reason with a digit is dropped and the verdict stays; a refusal or truncation gives "not judged" rather than a verdict; the judge model is not the drafter's; warnings never change `final.ok` and approval by the reviewer still succeeds with warnings present | pytest `test_judge_*`, `test_judge_warns_never_blocks` |
| C8 | E5: the file holds at least 24 labelled cases with both labels and at least 3 kinds of overstatement; kappa of the recorded judge against the labels is computed by code (checked on hand-computed examples) and is at least the threshold of decision O2; the result, `n` and kappa are written to a file the panel reads; changing the judge prompt or schema makes the recording stale and fails the test | pytest `tests/evals/test_e5.py` in the `evals` check; `test_kappa_*` |
| C9 | Judge recordings are in git, each from Bedrock in eu-west-1 with model, region, date, latency, tokens and cost; they replay offline; a sentence without a recording shows "not judged" and never an invented verdict; total spend of this phase stays under the ceiling of decision O1 | pytest `test_recordings_metadata_*`, `test_judge_replay_*`; `make record-judge` cost output |
| C10 | Step 5 at 1440x900 with network off, to the 02c mockup: the judge panel lists each warning with sentence, category and reason, says it warns and never blocks, shows "judge, model, n, kappa", carries the RECORDED badge and an example overstated sentence labelled EXAMPLE; approval still works with warnings; no scroll and within the word cap | Browser walkthrough with screenshots in `evidence/`; `test_word_cap` extended |
| C11 | Step 6 at 1440x900 with network off, to the 02c mockup, REAL badge: the 8 rules with result and note for this session, the chain as a trace of short hashes with the head, Verify chain showing ok and the count, and the tampering button showing "chain broken at entry N" on a copy; no scroll and within the word cap; without a thread it redirects like step 5 | Browser walkthrough with screenshots; `test_word_cap` extended; pytest `test_step6_*` |
| C12 | `make demo` serves the full walkthrough of steps 1 to 6 from a clean clone with network off; deploying the merged PR is done by the user and is outside this phase | `make demo-offline-check` extended |
| C13 | No company name, logo or colour from the PRD, no third-party person's name and no AWS account ID in the repo or the app; no GxP claim; the audit page says the chain detects edits and is not a validated or external log | Local grep of PRD terms and 12-digit literals over tracked files, diff and commit messages before every push; screenshot text |

## Constraints and risks
- Bedrock spend needs the user's go-ahead (decision O1). Estimate on Sonnet 4.6 (3 USD input and 15 USD output per million tokens): about 1.5k input and 0.2k output tokens per judged sentence, about 0.0075 USD; 24 E5 cases plus about 20 draft sentences plus the example is about 0.35 USD per full pass (estimate). Prompt revisions during calibration re-record E5, so a few passes fit well under 2 USD.
- The 5.5 models stay unavailable (02b deviation D2): the judge is Sonnet 4.6, as ADR-001 already chose, and the badge says so.
- Calibration weakness: with labels written by us, kappa measures agreement with our definition of overstatement, not with independent experts, and 24 cases give a wide uncertainty. The panel states `n` and the label source; the spec does not claim more.
- The draft text is mostly code-placed, so on the real draft the judge is expected to find few or no warnings; that is a correct result, and the example sentence and E5 are what show the warning behaviour.
- A chain detects edits, deletions, swaps and insertions by someone who does not recompute every later hash; it does not stop an actor who rewrites the whole chain or cuts its tail, and the store is the same ephemeral SQLite file as the threads. The step 6 line "In production → an external append-only log" says so.
- Threads and their chains live in `:memory:` unless `CAIRN_THREADS_DB` is set, so a restart empties the chain (as it already empties the thread).
- The judge changes the graph after `verify_final`, so threads checkpointed before this phase are not resumable; the demo has none that matter.
- A judge call per sentence adds replay lookups after confirm; with decisions other than the example set most sentences have no recording and show "not judged" (decision O5). This is stated on screen, not hidden.
- Step 5 and step 6 word caps (93) are tight; the chain trace may sit behind a disclosure as in 02c S1.

## Assumptions
- A session is a thread; "per-session chain" means one chain per thread id, not one for the whole server.
- The judge reads the final rendered text, so it runs once, after the reviewer confirms; recording decisions still makes 0 model calls.
- The judge reason is shown only if it contains no digit (global criterion: no free numbers); verdicts and categories are fixed words.
- Categories of overstatement come from the existing wording rules and master plan: causal wording ("caused"), loss or certainty wording ("lost", "proved"), safety claim, and magnitude wording not supported by the counts.
- The hash is computed with the existing canonical JSON hash; no new dependency.
- The two demo users stay SIMULATED; the audit actor is the demo user or the name of the judge model, never a real identity.

## Open decisions
Questions the user must resolve before approving. Empty on approval.

| ID | Question | Options and consequences | Recommendation |
|---|---|---|---|
| O1 | Bedrock spend and model for the judge recordings | A: Sonnet 4.6 (the ADR-001 judge, distinct from the Opus 4.6 drafter), ceiling 2 USD for the phase, `default` AWS profile as in 03 O5 and 04 O1; room for about 3 calibration passes; no agent reads or prints credentials or account IDs. B: same model, ceiling 1 USD; at most 1 or 2 passes, a prompt miss may need a new decision. C: no Bedrock, hand-written fixture verdicts labelled SIMULATED, 0 USD; E5 and kappa would measure a script, not a model, and step 5 loses its RECORDED badge | A |
| O2 | E5 calibration set: size, who labels, kappa threshold | A: 24 cases built by code from the study's own findings (12 faithful, 12 overstated in 4 kinds), labels fixed by construction, you read the list before it is recorded; threshold 0.70 (at most 3 wrong in 24); it measures agreement with our definition. B: you label about 20 sentences by hand; independent labels, but it costs your time and the phase waits on it. C: 40 cases from code; a tighter kappa estimate and about double the spend, still our labels. Threshold alternatives: 0.60 is looser, 0.80 allows 2 wrong in 24 and may force prompt rounds. If kappa stays under the threshold after 2 prompt revisions, work stops and returns to you (lower the bar, change cases, or ship the real kappa shown honestly) | A, threshold 0.70 |
| O3 | What the audit chain covers and where it lives | A: every workflow event listed in Scope, in a new table of the same SQLite file as the threads (ephemeral, `:memory:` by default); one place to write, tested with the threads. B: decisions and approval only; fewer entries, but the judge result and refusals would be outside the trail. C: a JSONL file per session; easy to edit by hand for a demo, but a second storage to configure and clean | A |
| O4 | How verify and tampering are shown | A: API plus step 6 buttons; tampering edits an in-memory copy of one entry and verify fails on the copy; the stored chain is never changed, so a demo cannot corrupt a session and the append-only property stays true. B: the button edits the real stored entry; more vivid, but the session stays broken and the app then contradicts its own claim. C: A plus a `cairn audit verify` CLI; useful only with `CAIRN_THREADS_DB`, extra code to test | A |
| O5 | Does the judge run live or only replayed | A: replayed only; each sentence is looked up in the recordings by the hash of sentence and cited facts; no recording means "not judged"; offline, free and deterministic like every other step. B: live judge for any decisions in step 5; shows real verdicts for any form, but needs network, keys, the access code and the daily cap of phase 06, and breaks `make demo` offline | A |
| O6 | Where the 8 rule checks live now that step 6 has a rules table | A: move them to step 6 as in the mockup; step 5 shows the final text, the judge panel, approval and one line "Rules: 8 of 8 passed, see step 6"; this changes the delivered step 5 (phase 04 C9 showed the 8 checks there). B: keep the checks in step 5 and show them again in step 6; duplicated words against the 93 cap | A |
| O7 | SEC-002: Observations claim the pinned snapshot while the DuckDB file queried may differ | A: close it here: the build records the snapshot it was made from and gather fails if it differs from the manifest; the audit trail then does not rest on an unchecked claim; a few lines plus a test. B: leave it open and write the limit in the step 6 text; the chain would certify hashes of data it did not check | A |
