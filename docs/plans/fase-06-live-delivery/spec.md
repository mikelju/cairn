# Phase 06 - Live question and delivery: specification

Status: spec in review
Approved by the user: -
Master plan: `../0_plan_maestro.md`
Definitions of phases 01 to 05 (Observation, ValueRef, QuoteRef, DecisionRef, rules 1-8, renderer, gateway with replay, record and live modes, recordings, the question loop, the `nonclinical-summary` workflow, the thread API, the audit chain, the judge, E1-E6 and steps 1 to 6) apply unchanged unless this spec extends them.

## Objective
Close Cairn as v0.1.0: a visitor with the access code asks their own question live in Explore, bounded by a daily cap, and without the code gets the recorded questions; step 1 has its remaining switches; step 7 closes the walkthrough; a second workflow, `data-quality-memo`, arrives in a configuration-only commit; a clean clone and two timed people prove the demo; the docs and the v0.1.0 tag ship it.
It is needed now because it is the last phase: the milestone is a tagged v0.1.0 meeting every acceptance criterion of the PRD.
Priority set by the user (phase 04, still standing), literal: "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."
It is a demo: edge cases beyond the criteria are not chased.

## Scope
In:
- Live Explore (decision O1): the Explore text box takes a free question plus the access code; with a valid code and the daily cap not reached, the question runs through the existing question loop with the gateway in live mode (45 s timeout, `max_retries=0`, no streaming, as `gateway.py` already builds the client) and the same verifier; the answer shows the REAL badge with model, latency and cost; a refusal, truncation or timeout is shown as is.
  Without a code, with a wrong code or with the cap reached, the box offers the recorded questions and makes no Bedrock call.
  This reverses decision D8 of phase 02b for this one gated route only; every other web route stays replay-only.
- Daily cap (decision O2): spend of the current UTC day counted from the real tokens of each live call with the existing `pricing.call_cost`; one live question at a time; the code and the cap value come from environment variables of the service, never from the repo.
- SEC-003 closed before live is exposed: a lock on the lazy index and reranker load, and a length limit on the live question; SEC-001 handled as decision O1 says; `docs/security.md` rows updated.
- Step 1: the remaining switches of decision O3, each revalidating in memory like the existing "Inject a negative concentration" and showing the rule that fires and the new quarantine.
- Step 7 (decision O4) built to the walkthrough's closing purpose, within 1440x900 and the word cap.
- Workflow configuration (decision O5): a YAML file per workflow, loaded into the existing `Workflow` Pydantic model of `src/cairn/workflow.py`, extended only with the fields both workflows need; `nonclinical-summary` moves to YAML with identical behaviour.
- `data-quality-memo`: a workflow for the data owner that runs only gather, draft and verify_final (no decisions, no judge), reusing tested tools and the 8 rules; it arrives in one commit with 0 `.py` files (YAML, prompt, eval cases and its W2 draft recording); no button in the web, step 7 links to that commit and its green `evals` check.
- W2 recording: one draft of the memo recorded once from Bedrock in eu-west-1 by the user on the laptop, replayed everywhere.
- Clean-clone test and timed test (decision O6): a fresh clone reproduces the checks and the offline demo of steps 1 to 7; two people without context walk the tour against a stopwatch.
- Docs and release (decision O6): one-screen README (make demo, make live, make record, make deploy, and the video link), ADR-002 (LangGraph for workflows, simple loop for questions, framework-free tools via MCP), `docs/production.md`, a generated CHANGELOG and the v0.1.0 tag.
- Offline check, word cap test and screenshots extended to step 7.

Out:
- Everything the master plan defers past v0.1.0: live judge in Explore, reject and redo with diff, similar-question finder and Autoplay, multi-dimension judge rubric, .md or DOCX export, Pydantic-AI client and DCAT record.
- The highlighted PDF page generated on the fly for live answers (first item of the PRD cut order): a live quotation links to its page of the official PDF; recorded quotations keep their precomputed highlights.
- The judge on live questions (the PRD says the judge does not run on free questions); a web button for `data-quality-memo`.
- Chain display, tampering in the app or a JSONL download of the chain (removed by phase 05 U2).
- Real identity, per-user limits, Guardrails or WAF (they stay SIMULATED with their "In production" line); GxP or Part 11 claims.
- Deploying to Lightsail, merging, tagging and recording the video: done by the user (see "Who does what").
- Changes to rules, the NOAEL rule, the draft or judge prompts of `nonclinical-summary`, and the frozen criteria of phases 01-05.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with coverage of at least 85% on `src/cairn`, hooks; E1-E6 still pass unchanged; CI `evals` green on the PR | `npm run check`; `gh pr checks` |
| C2 | Without a code, with a wrong code, or with an over-long question, `POST` to the Explore box makes 0 Bedrock calls and offers the recorded questions; with the valid code a new question runs the question loop in live mode through the same verifier and shows the REAL badge with model, latency and cost; a refusal, truncation or timeout from the client is shown as is, never as an answer | pytest `test_explore_live_*` with a fake live client counting calls |
| C3 | The daily cap holds: once the spend of the current UTC day reaches the cap, the box offers the recorded questions with 0 calls; the next UTC day it accepts again; a second live question while one runs is refused; the live client is built with timeout 45 s and `max_retries=0`; the code is compared in constant time and never logged or rendered | pytest `test_live_cap_*`, `test_gateway_*` |
| C4 | On real Bedrock (eu-west-1), run by the user on the laptop with the app served locally and the code set: one new question answers in 45 s or less with the REAL badge, or shows the refusal or cut as is; the screenshot and the spend are kept | Screenshot in `evidence/`; spend line in the plan |
| C5 | SEC-003 closed: concurrent first live requests load the index and reranker once; a question over the length limit is refused before any model or retrieval call; `docs/security.md` SEC-001 and SEC-003 rows updated as decision O1 says | pytest `test_live_index_*`; rows read in the diff |
| C6 | Step 1 at 1440x900 with network off: each switch of decision O3 revalidates in memory, shows the rule that fires and the new quarantine, leaves the source files untouched, and the page stays within the word cap and without scroll | pytest `test_step1_*`, `test_word_cap`; screenshots in `evidence/` |
| C7 | Step 7 at 1440x900 with network off, with the content of decision O4: every number comes from an Observation, a decision record or recording metadata; every badge tells the truth; the links named in O4 resolve; within the word cap and without scroll | pytest `test_step7_*`, `test_word_cap`; screenshot in `evidence/` |
| C8 | `nonclinical-summary` is defined in a YAML file that loads into the `Workflow` model; the graph built from it behaves as before (E6 unchanged and green); a YAML with an unknown step, tool or missing field is rejected with a clear error | pytest `test_workflow_config_*`; `tests/evals/test_e6.py` |
| C9 | The `data-quality-memo` commit changes 0 `.py` files (YAML, prompt, eval cases, W2 recording); its workflow runs gather, draft and verify_final with no pause and no judge, from the W2 recording offline; its eval cases pass in the `evals` check; the W2 recording is from Bedrock in eu-west-1 with model, region, date, latency, tokens and cost | `git show --name-only <commit>` lists no `.py`; pytest over the memo cases; `test_recordings_metadata_*` |
| C10 | Clean clone: in an empty directory, `git clone`, `uv sync`, `make weights` and `npm run check` pass, and `make demo-offline-check` serves steps 1 to 7 with network none | Run by the user on the laptop, output pasted in the plan; fallback as in phase 05: the image workflow builds the committed Dockerfile and the offline check runs on its artifact |
| C11 | Two people without context, reading everything visible, finish the tour in 5:00 or less each and explain unaided what problem it solves, what is REAL, RECORDED and SIMULATED, and why it matters | Run by the user; the two times and a one-line note each recorded in the plan |
| C12 | Docs: README fits one screen and names make demo, make live, make record and make deploy and links the video; ADR-002 and `docs/production.md` exist; CHANGELOG is produced by the command of decision O6, not by hand | Files read in the diff; the CHANGELOG command output |
| C13 | v0.1.0: the tag points to the merge commit of this phase on `main`; the release carries the CHANGELOG and the evaluation summary; the image deployed to the URL is built from that commit | `git tag --points-at`; `gh release view v0.1.0`; footer commit on the URL (user) |
| C14 | No company name, logo or colour from the PRD, no third-party person's name, no AWS account ID and no access code in the repo, the app or the commit messages; no GxP claim | Local PRD-term grep and 12-digit grep over tracked files, the diff and commit messages before every push |

## Constraints and risks
- Bedrock spend needs the user's go-ahead (decision O2).
  Cost per live question, from the recordings of the question loop (Opus 4.6, eu-west-1, 2026-10-23, summed `cost_usd` per file): `recordings/q1.json` 0.128 (4 calls), `q2` 0.066, `q3` 0.091, `q4` 0.095, `q5` 0.094, `q6` 0.017 (declined), `q7` 0.017 (declined), `q8` 0.064, `g1` 0.065, `g2` 0.066, `g3` 0.066; total 0.767 USD over 11 questions, mean 0.070 USD, maximum 0.128 USD.
  Code ceiling per question: 6 calls (`MAX_CALLS`) at 20k input and 4,096 output tokens on Opus 4.6 is 1.21 USD (`live.call_ceiling` times 6).
  A daily cap of 2 USD allows about 28 typical questions; with one question at a time the day can overshoot by one question at most, so the hard daily maximum is 3.21 USD (estimate).
  W2: `recordings/draft.json` cost 0.054 USD for one draft call, so the memo draft is estimated at about 0.05 to 0.10 USD.
  Phase ceiling for development spend on the laptop (W2 recording plus about 10 live checks, about 0.75 USD typical): 2 USD, as in phases 04 and 05; the hosted live cap is separate and is counted per day while the code is set.
- Bedrock calls only run on the user's laptop: the cloud container's AWS credentials are rejected (phase 05 U4). Agents build and test everything against fake clients and fixture recordings.
- The 5.5 models stay unavailable (02b deviation D2): live and W2 use Opus 4.6, and the badges say so.
- A daily cap kept in process memory resets if the container restarts; the hard maximum per day assumes no restart. Lightsail restarts are rare; the risk is stated, not engineered away.
- A shared code is weak access control: anyone with the link and the code can spend up to the cap. This is SIMULATED and its "In production" line names identity and per-user limits.
- Step 7 must fit 93 words; the production table stays folded under a disclosure.
- Moving `nonclinical-summary` to YAML touches the graph builder; E6 is the guard that behaviour did not change.
- The timed test needs two people without context and the clean-clone run needs the laptop; if either is late, the PR can merge and the tag waits.

## Assumptions
- "Access code" is one shared code sent with the link, set as a service environment variable together with the IAM key limited to InvokeModel on the used profiles; the user sets them with `make deploy`.
- "Counts the calls of the day" (PRD) is met by counting spend, which bounds cost better than a count of calls; the panel can still show the questions answered today.
- A live answer uses the same question loop, tools, retrieval and verifier as the recordings; a quotation from a live answer links to the official PDF page.
- The remaining step 1 switches are "Duplicate an animal ID" and "Use a dose not in TX" (PRD), each a pure transform of in-memory frames like `_inject`.
- Step 7 is the "Review" entry already in the app navigation (`STEPS`); approval stays in step 5.
- The YAML loader uses PyYAML, already in `uv.lock` as a transitive dependency, declared as a direct dependency; no other new dependency.
- The memo reuses the validation report and the existing study tools; which Observations it gathers is fixed in the YAML.
- Merging, tagging, deploying, the clean-clone run, the timed test and the video are done by the user; agents never write to `main`.

## Who does what
| Step | Who | Where |
|---|---|---|
| Code, tests, fixtures, docs, screenshots, offline check, PR | Sonnet executors | Worktree or cloud session |
| W2 recording (`make record-memo AWS_PROFILE=default`) | User | Laptop |
| Live check on real Bedrock (C4) | User | Laptop, app served locally with the code set |
| Clean-clone run (C10) | User (fallback: image workflow plus offline check by an executor) | Laptop |
| Timed test with two people (C11) | User | Any browser on the URL or `make demo` |
| Merge, `make deploy` with the code and the IAM key, tag v0.1.0, release, video | User | Laptop and GitHub |

## Open decisions
Each lists the recommended option first.

| ID | Decision | Options, consequences and recommendation |
|---|---|---|
| O1 | How live Explore is gated and hosted | A (recommended): shared code from `CAIRN_ACCESS_CODE`, compared in constant time; live only on the Explore box route, which may import the live gateway (D8 reversed for that route only); one live question at a time; SEC-003 closed; SEC-001 kept open and documented as an accepted demo risk (the other public endpoints run no model, so they cost CPU, not Bedrock). Least code; meets the PRD. B: as A, plus the code also gates `POST /jobs` and `/api/tools/*`, closing SEC-001; more code, and the MCP and REST demo of step 7 would need the code too. C: no hosted live; live stays `make live` on the laptop (PRD cut item 4); cheapest and no spend risk, but it fails the PRD criterion of a live question on the URL. |
| O2 | Bedrock spend: daily live cap and phase ceiling | A (recommended): cap 2 USD of spend per UTC day (about 28 typical questions, hard maximum 3.21 USD per day); phase ceiling 2 USD for the W2 recording and live checks on the laptop, `default` AWS profile; no agent reads or prints credentials or account IDs. B: cap 1 USD per day (about 14 questions, hard maximum 2.21 USD); safer, but a busy demo day may hit it. C: cap of 20 questions per day counted as calls (PRD wording); simple to explain, but the worst case is 24 USD per day. |
| O3 | Which step 1 switches remain | A (recommended): add "Duplicate an animal ID" and "Use a dose not in TX" next to the existing one, one switch at a time; meets the PRD, about two small transforms and their tests. B: keep only "Inject a negative concentration" (PRD cut item 2); no work, and the step 1 criterion of the PRD is met only in its cut form. |
| O4 | What step 7 shows | A (recommended): "Same product, production-shaped" under the existing "Review" nav entry: a session strip (numbers placed by code and 0 by the model, verbatim quotations, human decisions, recorded cost and latency, chain status), the same tool called over MCP and REST with the same hash, links to the `data-quality-memo` commit with its `evals` check, the blocked bad PR, `/docs` and `/mcp`, and the production table folded; replaces the 02c sign-off mockup, since approval already lives in step 5. B: the 02c mockup (decisions table and a SIMULATED sign-off); repeats step 5 and loses the PRD's closing message. C: A without the MCP and REST call; less code, but the "same product over MCP and REST" claim is only a link. |
| O5 | Workflow configuration format | A (recommended): one YAML file per workflow (for example `workflows/nonclinical-summary.yaml`, `workflows/data-quality-memo.yaml`) loaded with PyYAML into the existing `Workflow` model, extended only with the fields both workflows need (steps, pauses, tools to gather, prompt file, sections, recording name); one prior code commit makes the graph read them, so the memo commit has 0 `.py`. B: the same in JSON with the standard library; no dependency, but the PRD says YAML. C: workflows as Python objects as today; no loader, but the memo commit would carry a `.py` and fail the PRD criterion. |
| O6 | Clean-clone and timed tests, docs and the tag | A (recommended): clean clone run by the user on the laptop as in C10, with the image workflow plus offline check as fallback; timed test by the user with two people, times recorded in the plan; README one screen, ADR-002, `docs/production.md`; CHANGELOG generated by a `make changelog` target from the merged PR titles via `gh` (no new dependency, no hand edit); the user tags v0.1.0 on the merge commit and creates the release after merging, since agents never write to `main`. B: as A, but no CHANGELOG file: the GitHub release notes generated by `gh release create --generate-notes` are the changelog; less work, but the PRD deliverable names a CHANGELOG. C: the delivery tags the PR head before merge; the tag would not point to the merged commit on `main`. |
