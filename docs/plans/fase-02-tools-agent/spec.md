# Phase 02a - Tools and rules that write no numbers: specification

Status: approved (frozen)
Approved by the user: 2026-10-21
Master plan: `../0_plan_maestro.md`
Split from the approved phase 02 spec (decision D1); the other half is `../fase-02b-live-agent/spec.md`.

## Objective
Leave the deterministic core of the agent working and checkable offline, with no network and no cost: tested study tools that return Observations, a typed content model, a renderer that places every number, a verifier that blocks anything that breaks rules 1-7, full E1 and E2, and a bad PR whose required `evals` check goes red.
It is needed now because every later phase (the live agent of 02b, RAG, human decisions, audit, judge) builds on the Observation contract, the typed content model, the renderer and the verifier.
The model gateway, the question loop, the recordings and step 2 of the walkthrough are phase 02b.

## Scope
In:
- `Observation` contract (Pydantic v2): `obs_id`, `kind`, `population`, `n_examined`, `values`, `sql`, `source_rows`, `content_sha256`, `tool{name, version}`, `snapshot_sha256`; hashes use the existing canonical JSON.
- Four study tools in the existing registry, each returning an `Observation` over fixed SQL on the read-only DuckDB, saying "not examined" when it applies: `study_design` (upgraded from the plain contract of phase 01), `incidence`, `body_weight_change`, `tk_summary`. `run_job` stays as is.
- `incidence` with the screening rule, printed on screen: a finding enters, by sex, if in any dose group with 5 or more examined animals at least 3 more are affected than in control.
  It is a screen, not a statistical test nor a treatment-relatedness decision.
  Without the screen it returns the full table.
  Populations, findings and counts follow the Data definitions below.
- Descriptive statistics only, examined animals as denominator, TK satellites and recovery animals handled by explicit population arguments, never silently mixed.
- Typed content parts `Text`, `ValueRef(obs_id, field)` and `Sentence`; short stable IDs assigned by code (`O1`, `O2`... by call order, so replay repeats the order). `QuoteRef` and `DecisionRef` are defined in phases 03 and 04.
- Deterministic renderer: places numbers and study terms from `ValueRef`, formatting by type; model text goes in as written.
- Verifier rules 1-7 (defined below), always applied, in this order, with fixed expression lists living with the code, not in configuration.
- Evaluations: full E1 (exact figures, no LLM) and E2 (grounding and adversarial fixtures, blocked by the verifier), as parametrized pytest, run by the required `evals` check, with the assertion and fixture sets fixed by decisions D3 and D4.
- The bad PR: a pull request that relaxes rule 3 (lets digits through in model text), left open on GitHub as a draft from its own branch with the label "do not merge" (decision D5), whose `evals` check fails deterministically without network.

Out:
- Phase 02b: the Bedrock smoke test and ADR-001, `LLMGateway` (replay, record and live), recordings and `make record`, `cairn ask` and `make live`, the bounded question loop, step 2 of the walkthrough, the deployed step 2 and the new dependencies `anthropic[bedrock]` and `boto3`.
- `search_guidance`, the guideline index, `QuoteRef`, rule 8 and the E2 fixture "citation to a passage not retrieved" (phase 03, decision D4).
- Explore with recorded questions Q1, Q3, Q4, Q5, Q7, Q8 and G1-G3, and E3 on the question loop (phase 03).
- `DecisionRef`, the `nonclinical-summary` workflow, LangGraph, decision form, NOAEL rule, the example NOAEL inside E1, 403 and 409 (phase 04, decision D3).
- Audit chain, LLM judge and E5 (phase 05).
- Access code, daily cap, the container IAM key, the remaining step 1 switches and their E1 assertions, step 7 and `data-quality-memo` (phase 06, decision D3).
- Free SQL written by the model, a second model provider, organ weights, clinical pathology and inferential statistics (master plan out of scope).

## Definitions taken from the PRD
- Rules 1-7 (verifier, on the final rendered text; rule 8, quote provenance, belongs to phase 03):
  1. Every sentence carries at least one reference: a tool result, a guideline passage or a recorded decision. In this phase only tool results exist, so a sentence with no `ValueRef` fails.
  2. Every reference resolves: its `obs_id` and field exist and the value can be formatted.
  3. No digit appears in model-written text, without exceptions; section and guideline numbers are placed by code.
  4. Every incidence statement says how many animals were examined.
  5. A data-quality note is mandatory wherever data with quarantined rows are cited.
  6. No safety claim and no NOAEL that a person has not recorded (fixed expression list, for example "safe", "no risk", "NOAEL is").
  7. No study term written by hand (it goes as a `ValueRef`) and no expression from the wording list: weight is "lower than control", never "lost".
- E1 (full): about 35 exact-equality assertions, no LLM: the phase 01 validation facts; the 9 rows of the `incidence` screen with their examined counts; female body weight with its n; the naive mean 2,821 versus 15,956 and the 5.7 times ratio. The PRD also lists the example NOAEL and the three broken-data switches inside E1; by decision D3 the NOAEL moves to phase 04 and the switches to phase 06.
- E2: about 15 adversarial fixtures, each blocked by the verifier with the rule that fires: free number, sentence with no citation, incidence with no denominator, "safe", NOAEL written by the model, study term written by hand, "lost", a number coming from an instruction hidden in the data, and a citation to a passage not retrieved (this last one needs phase 03; by decision D4 it moves there with rule 8, so E2 here has about 14 fixtures).
- Bad PR blocked: an open PR whose only change relaxes rule 3; the required `evals` check goes red because E2 fixtures stop being blocked, deterministically and without network.

## Data definitions
These readings reproduce the PRD figures on the pinned snapshot (see Data check); the tools implement exactly these.
- TK satellites: animals whose trial set has `TX.TKDESC = TK`.
- Recovery animals: animals whose `DM.ARM` contains "with recovery" (terminal sacrifice on day 58).
- Main study: every animal that is neither a TK satellite nor a recovery animal (10 per sex and dose group).
- Finding: one tissue (`MI.MISPEC`) with one exact standardised result (`MI.MISTRESC`) other than NORMAL; results are not merged, so "Inflammation" and "Inflammation chronic" are different findings.
- Examined: distinct animals with an MI record for that tissue whose `MISTAT` is not NOT DONE; affected: distinct examined animals with the finding; a group with no examined animal is "not examined", never zero.
- Screen: computed on the main study only, by sex; a finding passes if some dose group above zero has at least 5 examined animals and at least 3 more affected animals than control.
- Body weight: `BWTESTCD = BW`; baseline is the record with `BWBLFL = Y` (day 1); the day-29 value is `BWDY = 29`.
- Percent lower than control: 100 x (control mean - group mean) / control mean of the day-29 body weight, a difference of group means of absolute weight, not of change from baseline.
- Change from baseline: day-29 weight minus baseline weight, per animal.
- Naive TK mean: arithmetic mean of `PP.PPSTRESN` for `PPTESTCD = AUCTAU` and `VISITDY = 1` in the TK satellite set of males at 20 mg/kg/day, with and without the quarantined row; the ratio is without over with, to one decimal.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.
Criterion IDs are kept from the approved phase 02 spec so that nothing is renumbered; C11-C18 and C20 live in phase 02b, and C1 and C21 are shared and must hold at the close of each phase.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite (shared with 02b) | Run the commands on a fresh clone |
| C2 | Every study tool returns a valid `Observation` with population, `n_examined`, fixed SQL, source rows and a `content_sha256` that is identical on two runs; if a tissue was not examined it says "not examined" instead of zero; the tools open the app's real DuckDB file read-only, so a write through their connection fails and the file bytes are unchanged | pytest `test_observation_*` and `test_tools_duckdb_read_only` |
| C3 | `incidence` with the screen returns exactly the 9 rows named in the PRD (adrenal vacuolation F and M, mammary fat atrophy F, renal necrosis M, hepatic vacuolation F and M, hepatocellular hypertrophy F, pancreatic inflammation M, splenic congestion F), each with the affected and examined counts of the Data check table, examined animals as denominator and without TK satellites or recovery animals; "not examined" appears exactly for renal necrosis M at 20, pancreatic inflammation M at 20 and 200, and splenic congestion F at 20 and 200 mg/kg/day, while renal necrosis M at 200 shows 0 of 1 examined | pytest `test_incidence_screen_*`, exact equality |
| C4 | `incidence` without the screen returns the full table, and the screen rule text printed on screen is the one the code applies (a single source) | pytest `test_incidence_full_*` and `test_screen_rule_text_matches` |
| C5 | `body_weight_change` for females returns mean day-29 body weight 9.3, 17.6 and 20.7 percent lower than control at 20, 200 and 400 mg/kg/day (as defined in Data definitions), with n = 15/10/10/15, TK satellites excluded and recovery animals included; it also returns a positive mean change from baseline in every group and exactly one animal with a negative change, PDS2014-0165 at 400 mg/kg/day with -5.3 g; no code-placed wording says "lost" | pytest `test_body_weight_change_*`, exact equality at one decimal |
| C6 | `tk_summary` reproduces the naive AUCtau mean for males at 20 mg/kg/day on day 1: 2,821 with the quarantined value of PDS2014-0032 (n=3) and 15,956 without it (n=2), 5.7 times lower, over the TK satellite set; a request to include TK satellites in body-weight means is rejected by the tool schema | pytest `test_tk_summary_*` and `test_tool_rejects_tk_in_body_weight` |
| C7 | The four study tools return the same result hash over MCP (official `mcp` client), REST and the CLI | pytest `test_registry_same_hash_*` |
| C8 | The renderer places every number and study term from a `ValueRef`; a sentence list with no digits renders to text where each number matches its Observation field | pytest `test_renderer_*` |
| C9 | Rules 1-7 each have a passing and a failing fixture, and the verifier reports the rule number and a plain-language reason for each failure | pytest `test_rule_N_*` for N = 1..7 |
| C10 | E1 passes at 100% with the assertion set fixed by decision D3 and E2 blocks 100% of its fixtures, with no network and no keys | pytest `tests/evals/test_e1.py` and `test_e2.py`, run inside the `evals` check |
| C19 | The bad PR is open on GitHub; its `evals` check is red because E2 fixtures fail; `main` stays green and the branch rule keeps `evals` required | PR checks page, `gh pr checks` on both, and the branch protection of `main` read with `gh api` |
| C21 | No company name, logo or colour from the PRD and no person's name appear in the repo or the app, and no claim of GxP validation is added (shared with 02b) | Local brand grep of the PRD company, person and place terms over tracked files, the diff and commit messages before every push |

## Data check
Computed on 2026-10-21 from the vendored XPT files in `data/pds2014` with pandas `read_sas`, following the Data definitions.
Counts are affected over examined at 0, 20, 200 and 400 mg/kg/day; NE means not examined.

| Criterion | Expected (PRD) | Observed | Choices that reproduce it | Result |
|---|---|---|---|---|
| C3 adrenal vacuolization F | in the screen; 0/10, 2/10, 7/10, 10/10 | 0/10, 2/10, 7/10, 10/10 | main study only; examined denominator | matches |
| C3 adrenal vacuolization M | in the screen; 1/10, 1/10, 1/10, 9/10 | 1/10, 1/10, 1/10, 9/10 | same | matches |
| C3 mammary fat atrophy F | in the screen; 0/10, 0/10, 5/10, 5/10 | 0/10, 0/10, 5/10, 5/10 | result "Atrophy fat" | matches |
| C3 renal necrosis M | in the screen; low and middle dose not examined except 1 male at 200 | 0/10, NE, 0/1, 3/10 | a group with fewer than 5 examined cannot pass | matches |
| C3 hepatic vacuolization F and M | in the screen | F 0/10, 0/10, 0/10, 3/10; M 0/10, 0/10, 0/10, 3/10 | liver result "Vacuolization"; "Vacuolization hepatocellular" occurs only in recovery and one low-dose animal | matches |
| C3 hepatocellular hypertrophy F | in the screen | 0/10, 0/10, 0/10, 3/10 | result "Hypertrophy hepatocellular" | matches |
| C3 pancreatic inflammation M | in the screen | 0/10, NE, NE, 3/10 | result "Inflammation", exact | matches |
| C3 splenic congestion F | in the screen | 5/10, NE, NE, 8/10 | difference to control of 3 | matches |
| C3 row count | exactly 9 | exactly 9 | results not merged; merging "Inflammation" with "Inflammation chronic" adds pancreatic inflammation F (3/10 at 400) as a 10th row | matches |
| C5 percent lower than control, F day 29 | 9.3, 17.6, 20.7 | 9.30, 17.58, 20.72 (means 269.48, 244.41, 222.11, 213.65 g) | day-29 weight, difference of group means; change from baseline would give 32.2, 59.0, 68.3, and leaving out recovery 8.9, 17.2, 20.1 | matches |
| C5 n | 15/10/10/15 | 15/10/10/15 | TK excluded, recovery included | matches |
| C5 gain and PDS2014-0165 | groups gained on average; PDS2014-0165 -5.3 g | mean change 76.01, 51.57, 31.14, 24.08 g; only PDS2014-0165 negative, 196.1 to 190.8 g | baseline `BWBLFL = Y` on day 1 | matches |
| C6 naive AUCtau M 20 day 1 | 2,821 (n=3) vs 15,956 (n=2), 5.7 | 2,820.67 (n=3: 11,126, -23,450, 20,786) vs 15,956.00 (n=2); ratio 5.66 | TK satellite set; quarantined row of PDS2014-0032 kept or removed; ratio rounded to one decimal | matches |

## Constraints and risks
- No network and no cost (decision D1): nothing in this phase calls a model, needs AWS credentials or adds the 02b dependencies; any other new dependency needs the user's approval.
- The expected figures of C3, C5 and C6 were reproduced on the pinned snapshot (Data check); they hold only under the Data definitions, and any other reading (for example merging MI results or using change from baseline for the percentages) breaks them.
- Phase 01 open review items that touch this phase: the C8 DuckDB protection test does not exercise the app's real file, and the tools must open the DuckDB file read-only, so a real read-only test is added here. SEC-001 (unauthenticated `POST /jobs` and tool endpoints) stays deferred to phase 06; this phase adds tool endpoints but no model behind them.
- The bad PR needs a branch kept open deliberately; it must never be merged.
- Size: tools, renderer, rules, E1, E2 and the bad PR are the larger half of the original phase 02; the split (decision D1) keeps the work that needs credentials and model behaviour out of it.

## Assumptions
- The pinned PDS2014 snapshot from phase 01 and its read-only DuckDB file are the only data source.
- Rule 5 uses the quarantine state already produced by phase 01; the data-quality note text is fixed in code.
- Rules 1-7 apply later to workflow drafts and to the 02b question loop without change.

## Decisions
The user approved the phase 02 spec on 2026-10-21 through a Lavish page, answering four questions; the answers are kept literally, with an English translation.

| ID | Question | User answer (literal) | Translation |
|---|---|---|---|
| U1 | Size of phase 02 | "Partir en dos: 02a herramientas, reglas y PR de prueba, sin red ni coste; 02b conexión al modelo, grabaciones y paso 2 de la web" | "Split in two: 02a tools, rules and the test PR, with no network and no cost; 02b model connection, recordings and step 2 of the web" |
| U2 | Dependencies and spend on Amazon Bedrock | "Aprobar las librerías y un tope de 10 USD, con un usuario de AWS limitado a invocar el modelo" | "Approve the libraries and a 10 USD ceiling, with an AWS user limited to invoking the model" |
| U3 | Model that records the demo answers | "Opus 5.5, y Opus 4.8 solo si Opus 5.5 se niega; la etiqueta dice cuál respondió" | "Opus 5.5, and Opus 4.8 only if Opus 5.5 refuses; the label says which one answered" |
| U4 | Approval of the phase 02 specification | "Aprobada, también lo que decides tú" | "Approved, including what you decide" |

"Lo que decides tú" ("what you decide") covers the supervisor's decisions shown on the same page as decided unless objected, which the user did not object to.
Each former open decision is closed below; the ones that belong to phase 02b are recorded there and listed here only for traceability.

| ID | Former open decision | Resolution | Source |
|---|---|---|---|
| D1 | Is one phase too large? | Option A: split into 02a (this spec, no network and no cost) and 02b (`../fase-02b-live-agent/spec.md`) | U1 |
| D2 | Which model records Q2 and Q6 | Phase 02b | U3 |
| D3 | Which E1 assertions belong to this phase | Option A: E1 covers the validation facts, the 9 screening rows, female weight, 2,821 versus 15,956 and the 5.7 ratio; the example NOAEL moves to phase 04 and the remaining switches to phase 06 | supervisor, accepted by U4 |
| D4 | Rule 8 and the E2 fixture "citation to a passage not retrieved" | Option A: rule 8 and its E2 fixture move to phase 03; E2 here has about 14 fixtures | supervisor, accepted by U4 |
| D5 | How the bad PR is kept from being merged | Option A: a draft PR from its own branch with the label "do not merge", with the required `evals` check failing | supervisor, accepted by U4 |
| D6 | New dependencies and spend | Phase 02b; this phase adds neither | U2 |
| D7 | Where the recordings live | Phase 02b | supervisor, accepted by U4 |
| D8 | Whether the question loop is exposed outside step 2 | Phase 02b | supervisor, accepted by U4 |

## Open decisions
Questions the user must resolve before approving. Empty on approval.

None.

## PRD content judged out of scope for this phase
- Model connection, recordings, the question loop and step 2 (phase 02b).
- RAG, guideline library, Q1, Q3, Q4, Q5, Q7, Q8, G1-G3, Explore and E3 (phase 03).
- Rule 8 (phase 03), `DecisionRef` and rules about recorded decisions beyond rule 6 (phase 04).
- Workflow YAML, LangGraph, decision form, NOAEL rule and E6 (phase 04).
- Audit chain, judge and E5 (phase 05).
- Access code, daily cap, container IAM key, step 7, `data-quality-memo`, production documentation and the timed tests (phase 06).
