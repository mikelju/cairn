# Phase 04 - People decide: specification

Status: approved (frozen)
Approved by the user: 2026-10-27 (A in O1-O4, Bedrock ceiling 2 USD with the `default` profile)
Master plan: `../0_plan_maestro.md`
Definitions of phases 02a, 02b and 03 (Observation, ValueRef, QuoteRef, rules 1-8, renderer, gateway, recordings, E1-E4, step 3 fixed queries) apply unchanged unless this spec extends them.

## Objective
Leave a `nonclinical-summary` workflow where the model drafts and people decide: a LangGraph graph that pauses for decisions and for approval, decision slots the model cannot fill, a model-free NOAEL rule, an API that refuses self-approval (403) and approval of a failing text (409), E6, and steps 4 and 5 of the walkthrough without the judge.
It is needed now because the phase 05 judge, audit chain and step 6 run on this workflow's draft and decisions.
Priority set by the user: the minimum that meets each criterion, reusing what phases 01-03 built; it is a demo, not every edge case.

## Scope
In:
- `DecisionRef(slot)` as a new content part and a `Decision` record (`dec_id`, finding, sex, `treatment_related_from`, `adverse_from`, actor, ts); slots enumerated by code before drafting: D1..Dn per finding and sex from the `incidence` and `body_weight_change` Observations, plus NOAEL-F and NOAEL-M; the renderer places a decision's text or a visible empty slot.
- Rules 1 and 2 accept and resolve `DecisionRef` (an unfilled slot fails rule 2); rule 6 accepts a NOAEL only when placed through a confirmed NOAEL `DecisionRef`.
- NOAEL rule as a pure function, per sex: the highest dose below the lowest adverse dose; the highest dose tested if nothing is adverse; "not established" if the lowest adverse dose is the lowest dose. It flags an adverse finding whose tissue was not examined in every animal at the proposed dose and asks to confirm it; its sentence quotes the step 3 NOAEL definition passage through `QuoteRef`.
- Graph in LangGraph with AsyncSqliteSaver: gather -> draft -> await_decisions -> verify_final -> await_approval -> approve; only a person resumes the two pauses. Gather calls the existing tools and reads the two fixed workflow queries (NS1, NS2) from the retrieval cache. The judge node is added by phase 05.
- Draft: one model call path through the existing gateway, with a prompt that forbids writing adversity, treatment relatedness or NOAEL; 4 sections (design, findings, tk, noael); one Bedrock recording replayed everywhere (decision O1).
- API: record decisions (recompute NOAEL, re-render and re-verify with 0 model calls), confirm as reviewer, approve; 403 when the approver is the draft's author; 409 when verify_final is not green or the thread is not at the pause the endpoint resumes.
- Two demo users (A. Author, R. Reviewer), SIMULATED, shown in the header (decision O3).
- E6 (about 10 parametrized cases) in the `evals` check, and the example NOAEL added to E1.
- Steps 4 and 5 of the walkthrough, built to the approved phase 02c mockups (decision O2).

Out:
- Judge, rubric, E5, judge panel, audit hash chain, verify and tampering, step 6 (phase 05).
- Live Explore, step 7, `data-quality-memo`, workflow YAML loader (phases 06 and later, decision O4).
- Reject and redo, signatures beyond recording intent, real identity; the Q6 refusal explanation (pending, user decides later).

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | `uv sync` and `npm run check` pass from a clean clone with no network: ruff, strict mypy, pytest with coverage of at least 85% on `src/cairn`, hooks | Fresh clone; CI green on the PR |
| C2 | `DecisionRef` renders a confirmed decision or a visible empty slot; slot IDs (D1..Dn, NOAEL-F, NOAEL-M) are enumerated by code and stable across runs; rules 1 and 2 accept and resolve it, an unfilled slot fails rule 2, a NOAEL in model text fails rule 6 and a confirmed NOAEL `DecisionRef` passes it; rules 1-8 fixtures and E2 still pass | pytest `test_decisionref_*`, `test_rule_6_*`, `tests/evals/test_e2.py` |
| C3 | The NOAEL rule is a pure function covered by a parametrized test of its three branches; the example decision set gives females 20 and males 200 mg/kg/day (asserted in E1); it flags male kidney (1 of 10 examined) and pancreas (none examined) at 200 and requires confirmation; its sentence quotes the NOAEL definition passage of step 3 | pytest `test_noael_rule_*`, `tests/evals/test_e1.py` |
| C4 | The graph runs gather -> draft -> await_decisions -> verify_final -> await_approval -> approve with AsyncSqliteSaver, stops at both pauses, and only the decision and approval endpoints resume it | pytest `test_workflow_*` on a temporary SQLite file |
| C5 | A draft recording from Bedrock in eu-west-1 is in git with model, region, date, latency, tokens and cost; it replays offline to 4 sections with DecisionRef slots, no digit in model text, and rules 1-8 green once the example set is confirmed; recording spend stays under the ceiling of decision O1 | pytest `test_recordings_metadata_*`, `test_workflow_draft_replay`; `make record` cost output |
| C6 | Any change of decisions recomputes the NOAEL and re-renders and re-verifies the text with 0 model calls; approving as the author returns 403; approving with verify_final not green, or resuming a thread not at that pause, returns 409; resuming twice adds no model call, tool call or event | pytest `test_api_decisions_*`, `test_api_403`, `test_api_409_*`, `test_resume_idempotent` |
| C7 | E6 passes at 100% offline: pauses in place, 403, 409, idempotent resume, the example set and at least 3 other form combinations with 0 model calls (one leaves female NOAEL "not established"), and the NOAEL rule test | pytest `tests/evals/test_e6.py` in the `evals` check |
| C8 | Step 4 at 1440x900 with network off, to the 02c mockup: draft with dashed empty slots, TK quality note "inherited from step 1", one row per finding and sex with two dropdowns, a fill-example button labelled as an example, NOAEL per sex with the PRD example label and the rule citing step 3, "Model calls for these decisions: 0", confirm as R. Reviewer; HTMX recomputes on each change; no scroll and within the word cap | Browser walkthrough with screenshots in `evidence/`; `test_word_cap` extended to step 4 |
| C9 | Step 5 at 1440x900 with network off: final text with 8 checks green and the RECORDED badge of the draft; "Approve as A. Author" shows the red banner "403 · Authors cannot approve their own draft. Enforced by the API, not the UI"; "Approve as R. Reviewer" approves; no scroll and within the word cap | Browser walkthrough with screenshots; `test_word_cap` extended to step 5 |
| C10 | `make demo` serves steps 4 and 5 from a clean clone with network off; deploying the merged PR is done by the user and is outside this phase | `make demo-offline-check` extended |
| C11 | No company name, logo or colour from the PRD, no third-party person's name and no AWS account ID in the repo or the app; no GxP claim | Local grep of PRD terms and 12-digit literals over tracked files, diff and commit messages before every push |

## Constraints and risks
- New dependencies `langgraph` and `langgraph-checkpoint-sqlite` (MIT), already chosen in the master plan's strategic decisions; checkpoints live in a local SQLite file, ephemeral in the container.
- Recording costs money and needs the user's AWS go-ahead; measured Q and G calls cost about 0.017 USD each on Opus 4.6. A draft with all Observations and two passages is estimated at 15k input and 3k output tokens, about 0.15 USD per attempt (estimate). Any change to the draft prompt or slot list makes the recording stale.
- The 5.5 models remain unavailable (02b deviation D2): the recording uses Opus 4.6 with Sonnet 4.6 as fallback, and the badge says which.
- The 93-word cap is tight for step 4 (draft, form and NOAEL on one screen); the draft may sit behind a disclosure as in 02c S1.
- The 02c mockups name step 4 "Analyse" and step 5 "Draft", while the PRD puts the draft in step 4 and approval in step 5 (decision O2).

## Open decisions
Resolved by the user on 2026-10-27: A in all four (literal answer in `plan.md`, U1).

| ID | Question | Options | Recommendation |
|---|---|---|---|
| O1 | Bedrock spend for the draft recording | A: record one draft with Opus 4.6 (Sonnet 4.6 fallback), ceiling 2 USD, `default` AWS profile as in 03 O5. B: hand-written fixture draft badged SIMULATED, 0 USD, but step 5 loses its RECORDED badge | A |
| O2 | Mapping PRD steps 4 and 5 onto the approved mockups | A: keep the nav labels; "Analyse" holds the draft with empty slots and the decision form, "Draft" holds the final text, checks and approval; mockups adjusted only where content differs. B: rename steps 4 and 5 to the PRD titles | A |
| O3 | How the acting demo user is chosen | A: each role-labelled button posts its actor; the API compares it with the draft's author; the header shows the acting user with a SIMULATED badge. B: a login or session cookie per user | A |
| O4 | Workflow definition format | A: a small Pydantic model in Python now; the YAML loader arrives with `data-quality-memo` in phase 06. B: the PRD YAML file and loader now | A |
