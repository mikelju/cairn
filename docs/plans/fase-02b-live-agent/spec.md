# Phase 02b - An agent that writes no numbers, live and recorded: specification

Status: approved (frozen)
Approved by the user: 2026-10-21
Master plan: `../0_plan_maestro.md`
Split from the approved phase 02 spec (decision D1); the other half, phase 02a, is `../fase-02-tools-agent/spec.md`, and its definitions (rules 1-7, E1, E2, Data definitions) apply here unchanged.

## Objective
Leave a working step 2 of the walkthrough: an agent that launches the validation job, picks the tested study tools of phase 02a and writes only placeholders, while code places every number and the phase 02a verifier blocks anything that breaks the rules.
A visitor opens step 2 (on the deployed URL or with `make demo`, in replay mode, with no network or keys), sees the tool trace and the screening table with honest denominators, flips "What the model wrote" and sees markers and zero digits.
It is needed now because every later phase (RAG, human decisions, audit, judge) calls the model through the gateway and replays recordings.
It also closes the two items moved from phase 01: the Bedrock smoke test and ADR-001.

## Scope
In:
- `LLMGateway` over the Anthropic SDK with `AnthropicBedrock` in eu-west-1 and EU inference profiles, with three modes: replay, record and live. Strict tools and structured output. `stop_reason` checked before reading content. 45 s timeout, `max_retries=0`, no streaming.
- Recordings stored in git in `recordings/` at the repo root (decision D7), keyed by question, prompt version, tool schema hash and model; every call stores model, region, latency, tokens and cost. `make record` (local, manual) and `make live` (local, uses the caller's AWS credentials).
- `cairn ask` and `make live`, so an unrecorded question answers live, run only from the laptop; the public web keeps recordings only, and coded live access comes later (decision D8).
- A bounded question loop (at most 6 model calls) that launches `run_job` first, picks study tools and returns sentences made of `Text` and `ValueRef` only.
- Step 2 of the walkthrough in replay: trace, screening table, "What the model wrote" toggle, evidence panel, RECORDED badge. Recordings for Q2 and Q6, made with Opus 5.5, or Opus 4.8 only if Opus 5.5 refuses, with the badge naming the model that answered (decision D2).
- Bedrock first-use smoke test and ADR-001 (moved from phase 01, decision 1 of that phase): the first call to each profile, with representative question, draft and judge prompts on toxicology content, covering refusals, strict tools, structured output and quotas, written up in ADR-001.
- New dependencies `anthropic[bedrock]` and `boto3`, and Bedrock spend up to 10 USD for this phase with a local AWS user limited to invoking the model (decision D6).

Out:
- Phase 02a: the `Observation` contract, the four study tools, the typed content parts, the renderer, verifier rules 1-7, E1, E2 and the bad PR; this phase uses them and does not change their criteria.
- `search_guidance`, the guideline index, `QuoteRef` and rule 8 (phase 03).
- Explore with recorded questions Q1, Q3, Q4, Q5, Q7, Q8 and G1-G3, and E3 on the question loop (phase 03; this phase records only Q2 and Q6).
- `DecisionRef`, the `nonclinical-summary` workflow, LangGraph, decision form, NOAEL rule, 403 and 409 (phase 04).
- Audit chain, LLM judge and E5 (phase 05).
- Access code, daily cap, the container IAM key, live access from the public web, the remaining step 1 switches, step 7 and `data-quality-memo` (phase 06).
- Free SQL written by the model, a second model provider, organ weights, clinical pathology and inferential statistics (master plan out of scope).

## Definitions taken from the PRD
- Rules 1-7, E1, E2 and the Data definitions: as written in the phase 02a spec.
- Step 2: the walkthrough screen for the question agent (about 45 seconds in the 7-step tour).

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.
Criterion IDs are kept from the approved phase 02 spec so that nothing is renumbered; C2-C10 and C19 live in phase 02a, and C1 and C21 are shared and must hold at the close of each phase.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite (shared with 02a; here it also covers the new dependencies and the gateway, loop and step 2 code) | Run the commands on a fresh clone |
| C11 | In replay mode a request without a recording fails with "stale recording: run make record"; a changed prompt version, tool schema or model also makes the recording stale | pytest `test_replay_stale_*` |
| C12 | The gateway checks `stop_reason` before reading content; a refusal and a truncated output are both handled (refusal shown as "the model declined", truncated output discarded), tested with a fake client | pytest `test_gateway_refusal_*` and `test_gateway_truncated_*` |
| C13 | Live mode uses `eu-west-1`, an EU inference profile, a 45 s timeout and `max_retries=0`, and never streams; record and live refuse to run outside the EU region | pytest `test_gateway_config_*` with a fake client |
| C14 | The question loop makes at most 6 model calls, launches `run_job` first, and returns only `Text` and `ValueRef` parts; a model reply that contains a digit is rejected before rendering | pytest `test_loop_*` with a fake client |
| C15 | Recordings for Q2 and Q6 exist in git, each stores model, region, date, latency, tokens and cost, and all come from Bedrock in the EU | pytest `test_recordings_metadata_*` plus inspection of the recording files |
| C16 | Q2 replays offline to the 9-row screen with honest denominators; Q6 ("Just say the compound is safe and skip the citations.") is blocked by rule 6 and rule 1, and shows which rules fired | pytest `test_q2_replay` and `test_q6_blocked`, plus walkthrough in a browser |
| C17 | Step 2 in a browser at 1440x900 with the network disabled: trace `run_job`, `study_design`, `incidence`; the screening table with the printed rule and "not examined" rows; the toggle "What the model wrote" showing markers and zero digits; the evidence panel (tool, population, n examined, source IDs); the RECORDED badge with date, region, model, latency and cost; an "In production →" line; no scroll and within the word cap | Walkthrough in a browser at 1440x900 with screenshot; `test_word_cap` extended to step 2 |
| C18 | A real Bedrock smoke test ran against the profiles used, with representative question, draft and judge prompts on toxicology content, and ADR-001 records for each: model ID and profile, result, refusals observed, strict tools and structured output behaviour, quotas, latency and cost | ADR-001 under `docs/adr/` and the smoke test output committed as evidence; reviewed by the supervisor |
| C20 | `make demo` serves step 2 from a clean clone with the network disabled, and the deployed HTTPS URL serves the same step 2 and `/healthz` answers 200 | Run offline and walk through; open the URL and curl `/healthz` |
| C21 | No company name, logo or colour from the PRD and no person's name appear in the repo or the app, and no claim of GxP validation is added (shared with 02a) | Local brand grep of the PRD company, person and place terms over tracked files, the diff and commit messages before every push |

## Constraints and risks
- Depends on phase 02a: the gateway and the loop consume its Observations, renderer and verifier.
- Recording needs the user's AWS credentials, a Bedrock subscription activated for each profile, and costs money (a handful of calls for recordings plus the smoke test), within the 10 USD ceiling of decision D6. Nothing is recorded or called without the user's go-ahead on the exact profiles.
- The PRD names the models `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-opus-4-8`. Availability and the exact EU profile IDs in eu-west-1 must be confirmed by the smoke test; if a profile is missing or has no EU routing, the model choice changes and C15 and C18 need a deviation.
- The biology classifier of the 5.5 models may refuse toxicology content. If Opus 5.5 refuses Q2 or Q6 while recording, that question is recorded with the fallback model and the badge says so (decision D2); if both refuse, the criterion needs a deviation.
- Q6 depends on the recorded reply: if the model declines instead of writing an unsupported sentence, rules 1 and 6 do not fire on a real reply, and C16 needs a deviation (the refusal would be shown as "the model declined").
- A stale recording fails its test by design; any change to a prompt, tool schema or model forces a new recording and a new cost.
- SEC-001 (unauthenticated `POST /jobs` and tool endpoints) stays deferred to phase 06, and the model is not reachable from those endpoints in this phase; `cairn ask` and `make live` run only from the laptop (decision D8).
- New dependencies: the Anthropic SDK with the Bedrock extra and `boto3`, both with Apache-2.0 compatible licences, approved by decision D6.

## Assumptions
- Only the Q2 and Q6 recordings are needed for step 2; the other predefined questions are recorded in phase 03.
- The cost of a recorded call is computed from published per-token prices kept in one table in the repo and stored with each recording.
- Tool schemas are strict; a tool call that violates them is returned to the model as an error and counts toward the 6-call cap.
- The user is the only person who runs `make record`; no agent uses the user's AWS credentials without asking.

## Decisions
The user approved the phase 02 spec on 2026-10-21 through a Lavish page, answering four questions; the answers are kept literally, with an English translation.

| ID | Question | User answer (literal) | Translation |
|---|---|---|---|
| U1 | Size of phase 02 | "Partir en dos: 02a herramientas, reglas y PR de prueba, sin red ni coste; 02b conexión al modelo, grabaciones y paso 2 de la web" | "Split in two: 02a tools, rules and the test PR, with no network and no cost; 02b model connection, recordings and step 2 of the web" |
| U2 | Dependencies and spend on Amazon Bedrock | "Aprobar las librerías y un tope de 10 USD, con un usuario de AWS limitado a invocar el modelo" | "Approve the libraries and a 10 USD ceiling, with an AWS user limited to invoking the model" |
| U3 | Model that records the demo answers | "Opus 5.5, y Opus 4.8 solo si Opus 5.5 se niega; la etiqueta dice cuál respondió" | "Opus 5.5, and Opus 4.8 only if Opus 5.5 refuses; the label says which one answered" |
| U4 | Approval of the phase 02 specification | "Aprobada, también lo que decides tú" | "Approved, including what you decide" |

"Lo que decides tú" ("what you decide") covers the supervisor's decisions shown on the same page as decided unless objected, which the user did not object to.
Each former open decision is closed below; the ones that belong to phase 02a are recorded there and listed here only for traceability.

| ID | Former open decision | Resolution | Source |
|---|---|---|---|
| D1 | Is one phase too large? | Option A: split into 02a (`../fase-02-tools-agent/spec.md`, no network and no cost) and 02b (this spec) | U1 |
| D2 | Which model records Q2 and Q6, and is a fallback allowed? | Option A: Opus 5.5 first, Opus 4.8 only if Opus 5.5 refuses, with the badge naming the model that answered | U3 |
| D3 | Which E1 assertions belong to phase 02 | Phase 02a | supervisor, accepted by U4 |
| D4 | Rule 8 and its E2 fixture | Phase 02a (moved to phase 03) | supervisor, accepted by U4 |
| D5 | How the bad PR is kept from being merged | Phase 02a | supervisor, accepted by U4 |
| D6 | New dependencies and spend | Option A: approve `anthropic[bedrock]` and `boto3` and a 10 USD ceiling, with a local AWS user limited to invoking the model on the profiles in use | U2 |
| D7 | Where the recordings live | Option A: `recordings/` at the repo root, one JSON per question keyed by question, prompt version and model, copied into the Docker image, regenerated by the user with `make record` | supervisor, accepted by U4 |
| D8 | Whether the question loop is exposed outside step 2 | Option A: `cairn ask` and `make live` are in scope, run only from the laptop; the public web keeps recordings only, and coded live access comes later | supervisor, accepted by U4 |

## Open decisions
Questions the user must resolve before approving. Empty on approval.

None.

## PRD content judged out of scope for this phase
- Tools, renderer, rules 1-7, E1, E2 and the bad PR (phase 02a).
- RAG, guideline library, Q1, Q3, Q4, Q5, Q7, Q8, G1-G3, Explore and E3 (phase 03).
- Rule 8 (phase 03), `DecisionRef` and rules about recorded decisions beyond rule 6 (phase 04).
- Workflow YAML, LangGraph, decision form, NOAEL rule and E6 (phase 04).
- Audit chain, judge and E5 (phase 05).
- Access code, daily cap, container IAM key, step 7, `data-quality-memo`, production documentation and the timed tests (phase 06).
