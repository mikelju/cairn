# Master plan - Cairn

Status: approved
Approved by the user: 2026-10-20

## Vision
Cairn is a working, product-shaped demo of a small agentic platform for drug safety scientists.
It takes a public toxicology study (SEND, PhUSE PDS2014) to a draft nonclinical summary in the style of CTD 2.6.6.3.
The model picks tools and drafts text, but never writes a number or a quotation: code places every number from an Observation and every verbatim quotation from a retrieved passage.
Scientific decisions (treatment relatedness, adversity, NOAEL) are made by a person and recorded in a hash-chained audit trail.
It works if a person with no context finishes the 7-step web walkthrough in 5 minutes or less and can tell what is REAL, RECORDED and SIMULATED, and if everything reproduces from a clean clone.

## Out of scope
- Oncology workflow with public APIs (Open Targets, FAERS, DailyMed, ClinicalTrials.gov) and the ICH S9 profile with first-in-human dose.
- Free SQL written by the model, a second model provider, RO-Crate, Postgres, docker compose, Streamlit and OpenTelemetry.
- A third QA role, recovery animals as a population of their own, organ weights, clinical pathology (OM, LB and EX are not loaded) and inferential statistics.
- Clinical advice, safety claims and GxP or Part 11 validation.
- Deferred past v0.1.0, outside the walkthrough: live judge in Explore, reject and redo with diff, similar-question finder and Autoplay, multi-dimension judge rubric, .md or DOCX export, Pydantic-AI client and DCAT record.

## Phases
| Phase | One-sentence goal | Depends on | Status |
|---|---|---|---|
| 01 | Validated data and skeleton: Python repo with quality tooling and CI, SEND ingestion with quarantine, `validate_study`, MCP/REST/CLI registry, landing page and step 1, offline `make demo` and Lightsail deployment | - | integrated |
| 02a | Tools and rules that write no numbers, offline and at no cost: Observation, the four study tools, renderer, rules 1-7, full E1, E2 and the bad PR blocked | 01 | integrated |
| 02b | An agent that writes no numbers, live and recorded: Bedrock smoke test and ADR-001, LLMGateway (replay, record, live), the question loop, Q2 and Q6 recordings and step 2 | 02a | integrated |
| 02c | App visual design that invites use: a visual system (type, colour, spacing, components, badges, tables, trace) applied to the landing page and steps 1 and 2, plus approved mockups of steps 3 to 7 that later phases build to, all within 1440x900 and the word caps | 02b | integrated |
| 03 | RAG over public guidelines: 4 guidelines with pinned SHA-256, hybrid index with reranker, `search_guidance`, QuoteRef, rule 8, highlighted page, E3, E4, Explore with recorded questions and step 3 | 02c | in progress (partial start 2026-10-22: all but the step 3 UI and the highlighted page, which wait for 02c in main) |
| 04 | People decide: `nonclinical-summary` workflow in LangGraph with two pauses, DecisionRef, decision form and model-free NOAEL rule, 403 and 409, E6 and steps 4 and 5 without judge | 03 | pending |
| 05 | Audit and judge: per-session SHA-256 chain with verify and tampering, calibrated Sonnet judge (E5, kappa), judge panel in step 5 and step 6 | 04 | pending |
| 06 | Live question and delivery: live Explore behind an access code and cap, remaining step 1 switches, step 7, configuration-only `data-quality-memo` workflow, clean-clone and timed tests, documentation and v0.1.0 | 05 | pending |

Statuses: pending, spec in review, spec approved, in progress, blocked, ready locally, integrated.
Only the user adds, removes or reorders phases; the agent proposes.

## Global criteria
- No free numbers: every number on screen comes from an Observation or a decision record; model text contains no digits.
- Every quotation is verbatim, with guideline, section and page, and comes from a passage retrieved in that run.
- The model does not decide treatment relatedness, adversity or NOAEL; whoever drafts does not approve their own work.
- Descriptive statistics only, examined animals as denominator and wording faithful to the data ("lower than control", never "lost").
- Python 3.12 with uv, ruff, strict mypy and pytest with coverage; `npm run check` chains them with the hook suite.
- `make demo` and CI run with no network or keys, in replay mode; a stale recording fails its test.
- Models only through Amazon Bedrock in the EU (eu-west-1, EU inference profiles); `stop_reason` is checked before reading.
- Every badge tells the truth: REAL, RECORDED (date, region, model, latency and cost) or SIMULATED with its "In production →" line.
- 7-step walkthrough at 1440x900 without scrolling, with a per-step word cap checked by a test.
- No company name, logo or colour and no third-party person's name in the app or the repo; "not GxP-validated" notice.
- Bounded AWS spend: IAM key limited to InvokeModel, access code, daily cap, 45 s and `max_retries=0` when live.
- Dependencies with licences compatible with Apache-2.0 (pypdfium2, not PyMuPDF).
- Everything versioned is in English: code, docs, specs, plans, commits and UI.

## Strategic decisions
| Date | Decision | Reason | Rejected alternative |
|---|---|---|---|
| 2026-10-20 | SEND data in read-only DuckDB with fixed SQL; only the guidelines are embedded | Every number must be exact and reproducible | Embeddings over the study data |
| 2026-10-20 | Typed content (Text, ValueRef, QuoteRef, DecisionRef) and a deterministic renderer | The verifier checks everything without an LLM | Let the model write numbers and review them afterwards |
| 2026-10-20 | LangGraph with AsyncSqliteSaver for workflows; a simple 6-call loop for questions | Native human pauses where the text must be defended; autonomy where mistakes are cheap | A single framework for everything |
| 2026-10-20 | Hybrid RAG with BM25 and bge-small fused by RRF, local bge-reranker-v2-m3 reranker; threshold on the reranker score | Deterministic, offline and with reliable abstention | Managed index or ms-marco reranker |
| 2026-10-20 | Real Bedrock recordings in git (replay) for the walkthrough, CI and `make demo`; live only in Explore behind a code | The walkthrough does not depend on network, credentials or refusals | Live walkthrough |
| 2026-10-20 | LLM judge distinct from the drafter that only warns | Rules see form, not overstatement | Blocking judge |
| 2026-10-20 | Lightsail deployment with `make deploy` from the laptop; CI does not deploy | The shortest real deployment with HTTPS | Terraform, ECS or AgentCore |
| 2026-10-20 | Private PRD kept out of git (`docs/PRD_Cairn.pdf` ignored) | The repo is public and the PRD is not shared | Versioning it |
| 2026-10-20 | Six phases instead of the PRD's five days; day 4 is split into phases 04 and 05 | Day 4 is the longest (11 h) and each phase must leave something working | One phase per day |
| 2026-10-20 | English for every versioned artifact; conversation with the user stays in Spanish | The repo is public and the demo audience reads English | Spanish documentation |
| 2026-10-21 | Phase 02 split into 02a (tools, rules and the bad PR, no network and no cost) and 02b (model connection, recordings and step 2), approved by the user | A smaller PR, and the work with no network and no cost goes first; 02b isolates what depends on AWS access and model behaviour | A single phase 02 |
| 2026-10-22 | New phase 02c for the visual design of the whole app, between 02b and 03, decided by the user | The demo gets little viewing time, so it has to look good and make people want to use it; the step 2 walkthrough showed a working but undesigned page | Polishing step 2 inside 02b; leaving design to the end |

## Milestones
- After phase 01: HTTPS URL with landing page and step 1, and an equivalent offline `make demo`.
- After phase 03: questions with traceable numbers and verbatim quotations, walkable up to step 3.
- After phase 05: full walkthrough of steps 1 to 6.
- After phase 06: tagged v0.1.0 meeting every acceptance criterion of the PRD.
