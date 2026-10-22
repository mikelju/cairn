# Phase 02c - App visual design that invites use: specification

Status: approved (frozen)
Approved by the user: 2026-10-22
Master plan: `../0_plan_maestro.md`

## Objective
Give Cairn a designed look that a visitor trusts and wants to use in the few minutes the demo is seen.
The phase leaves one shared visual system (type, colour, spacing, components, badges, tables, trace) applied to the landing page and steps 1 and 2, and approved static mockups of steps 3 to 7 that phases 03 to 06 build to.
Every page fits 1440x900 without scrolling and within its word cap as the visitor actually sees it, including the result of a question.
It is needed now because step 2 works but looks undesigned (02b decision U3), and because the step 2 page after the Q2 question shows about 238 visible words while the word-cap test only counts the template (46 of 93, 02b review R1).
Designing before phases 03 to 06 means each later step is built once, on the shared components, instead of being restyled at the end.

## Scope
In:
- Design tokens (font families, type scale, colours, spacing, radii, borders, shadows) declared in one place in the web stylesheet.
- Shared components used by every step: page shell (header with the step navigation and role, footer with the "not GxP-validated" notice and build line), step header (number, title, badge, one-sentence lede), REAL, RECORDED, SIMULATED and FIXTURE badges with their metadata line, buttons and form controls, data table (with "not examined" cells and highlighted new rows), tool trace, evidence panel, callouts for blocked results, rules fired and stale recordings, the "What the model wrote" toggle and the "In production →" line.
- The landing page, step 1 and step 2 rebuilt on those tokens and components, in every state a visitor reaches: step 1 before and after running validation, with and without the injected value; step 2 before asking, after Q2, after Q2 with the toggle open and after Q6.
- The word-cap test changed to measure the rendered pages in those states, not the templates.
- Static mockups of steps 3 (Explore), 4 (Analyse), 5 (Draft), 6 (Check) and 7 (Review) at 1440x900, built from the same tokens and components with clearly labelled placeholder content, approved by the user.
- Screenshots at 1440x900 of every built state and every mockup, stored in `evidence/` of this phase.

Out:
- Domain logic, the study tools, the renderer, the verifier and its rules, the question loop, the gateway, prompts, tool schemas and recordings; the Q2 and Q6 recordings replay unchanged and nothing is re-recorded.
- Building steps 3 to 7 as working routes (phases 03 to 06); the mockups are static and carry no data path.
- New paid dependencies, new Python or npm runtime dependencies, and any resource loaded from outside the app at run time (web fonts, CDNs, analytics, icons from remote hosts).
- Changes to the step order, the step names or the walkthrough content beyond the wording needed to fit the caps.
- Deployment changes; the user redeploys `main` after merge as in phase 02b.
- Any company name, logo or colour from the PRD.

## Acceptance criteria
Frozen on approval. Changing them requires a deviation approved by the user.

| ID | Observable criterion | How it is checked |
|---|---|---|
| C1 | From a clean clone, `uv sync` and `npm run check` pass: ruff, strict mypy, pytest with line coverage of at least 85% on `src/cairn`, and the hook suite | Run the commands on a fresh clone |
| C2 | All design tokens live in one block of custom properties in the web stylesheet; no colour literal, font family or raw font size appears in any other CSS rule or in any template, and templates carry no inline `style` attributes | pytest `test_design_tokens_*` scanning the CSS and templates, with a failing sample |
| C3 | The landing page, step 1 and step 2 render through shared Jinja macros for the step header, badge, data table, trace, evidence panel, callout and "In production →" line; no step template writes its own `<table>`, badge or trace markup | pytest `test_shared_components_*` scanning the templates, plus review of the diff |
| C4 | The landing page and steps 1 and 2, in every state listed in Scope, open in a browser at 1440x900 with `document.documentElement.scrollHeight` of at most 900 and use the new visual system | Walkthrough at 1440x900 with one screenshot per state in `evidence/` and the measured scroll height recorded in the plan |
| C5 | The word cap is measured on the rendered HTML of each page state listed in Scope, as returned by the app (including the step 2 results for Q2 and Q6 and the step 1 result): at most 93 visible words per step page, counted on the main area of the rendered page with the header, step navigation and footer dropped, every word in it counted including table headers, captions, badges and metadata, and each data table body counted as one block (decision U4), and the lede is one sentence of at most 25 words; the test fails on an over-cap rendered sample | pytest `test_word_cap_rendered_*` through the FastAPI test client, with a failing case |
| C6 | REAL, RECORDED, SIMULATED and FIXTURE badges differ in at least two cues besides colour (for example fill, border style or a leading glyph) and always show their word; RECORDED keeps its date, region, model, latency and cost line and SIMULATED its "In production →" line | pytest on the badge macro output and CSS, plus side-by-side screenshot of the four badges in `evidence/` |
| C7 | Basic accessibility: every text and background token pair in use reaches WCAG AA contrast (4.5:1 for body text, 3:1 for large text and for control and focus outlines); every interactive element shows a visible `:focus-visible` outline; no state, badge or table highlight depends on colour alone | pytest `test_contrast_*` computing ratios from the tokens, a CSS check for `:focus-visible`, and a keyboard-only pass through landing, step 1 and step 2 recorded in the plan |
| C8 | The behaviour proven in phase 02b still holds on the new pages: step 1 quarantines the injected value; step 2 shows the trace, the screening table with the printed rule and "not examined" cells, the toggle with markers and zero digits, the evidence panel, the rules fired, the RECORDED badge with its metadata and the "In production →" line; Q6 shows the rules that fired | Existing `tests/test_web.py` assertions kept or strengthened, none removed; `test_q2_replay` and `test_q6_blocked` pass on the unchanged recordings |
| C9 | Static mockups of steps 3, 4, 5, 6 and 7 exist as static HTML pages in this phase's folder that link the app's real stylesheet, are screenshotted at 1440x900 and are presented for approval on a Lavish page (decision U3), use only the shared tokens and components, each fits 1440x900 without scrolling and within the word cap, and each marks its placeholder content as a mockup | Screenshots at 1440x900 in `evidence/`; the same word count rule as C5 applied to each mockup |
| C10 | The user approves the five mockups, and the approval is recorded literally in this spec's decisions before the phase closes | User answer recorded in the spec and the plan |
| C11 | With the network disabled, `make demo` serves the landing page and steps 1 and 2 with every request going to the local host; no template or stylesheet references an `http://` or `https://` resource, and any font file is served from `src/cairn/web/static/` | `demo-offline-check` plus a pytest scanning templates and CSS for external URLs; network log of the walkthrough |
| C12 | The diff of the phase touches no file under `src/cairn/` outside `src/cairn/web/`, and nothing under `recordings/` | `git diff --stat main...HEAD` reviewed at delivery |
| C13 | No company name, logo or colour from the PRD and no person's name appear in the repo or the app, including the mockups and their placeholder content, and no claim of GxP validation is added | Local brand grep of the PRD company, person and place terms over tracked files, the diff and commit messages before every push |

## Constraints and risks
- Depends on phase 02b: step 2 and its recordings are the main content to design; the recordings must keep replaying without a new paid call.
- The 93-word cap is tight once a result is on screen: the Q2 page shows about 238 words today, mostly the screening rule sentence, the table and the evidence line. Meeting C5 means shortening wording, moving secondary text behind a disclosure and the counting rule of decision U4; the number of table rows cannot change, since they come from the data.
- Fitting 1440x900 with the 9-row screening table, the trace, the evidence panel and the badge line leaves little vertical room; a two-column layout may be needed.
- Text that comes from the renderer (the screening rule sentence, the model's sentence, failure messages) cannot be reworded in the web layer without touching domain code, which is out of scope; if it alone breaks the cap, C5 needs a deviation.
- Self-hosting a font adds files under `src/cairn/web/static/` and a licence notice; only fonts under the SIL Open Font License or another licence compatible with Apache-2.0 qualify.
- The mockups of steps 3 to 7 anticipate later phases; if a later spec changes what a step shows, that phase updates its mockup instead of reopening this one.
- Approval of the mockups (C10) needs the user's time; the phase cannot close without it.

## Assumptions
- The landing page is held to the same 93-word cap and 25-word lede as the steps.
- The step names stay as they are: Validate, Ask, Explore, Analyse, Draft, Check, Review.
- Header, step navigation and footer are page chrome and are not counted toward a step's word cap, as in the template count of phases 01 and 02b; the "not GxP-validated" notice stays visible on every page.
- HTMX stays vendored as today; no JavaScript framework or CSS build step is added.
- Phone and tablet layouts are not required; the pages must not break at narrower widths, but only 1440x900 is a criterion.
- Mockup placeholder content uses the public study and public guideline names only, never PRD terms.

## User decisions
The user approved this spec on 2026-10-22 through the phase 02c Lavish review page, answering six questions; the answers are kept literally, with their resolved meaning in English.

| ID | Question | User answer (literal) | Resolved meaning |
|---|---|---|---|
| U1 | O1 Visual direction | "O1-A: informe científico sereno" | Option A, calm scientific report: light neutral background, one deep accent colour, strong type hierarchy, tabular figures in tables, generous white space |
| U2 | O2 Typography | "O2-A: fuentes de licencia abierta autoalojadas" | Option A: self-hosted open-licence fonts, one sans for text and one mono for trace and IDs, served from `src/cairn/web/static/`, about 150 to 250 KB |
| U3 | O3 Format of the step 3 to 7 mockups | "O3-A: páginas HTML estáticas con la hoja real, presentadas en Lavish" | Option A: static HTML pages in this phase's folder that link the app's real stylesheet and reuse the macros' markup, screenshotted at 1440x900 and presented for approval on a Lavish page; later phases copy the markup |
| U4 | O4 How visible words are counted on a rendered page | "O4-A: área principal renderizada; cada cuerpo de tabla cuenta como un bloque" | Option A: render each state through the app, drop header, navigation and footer, count every word in the main area including table headers, captions, badges and metadata, and count each data table body as one block |
| U5 | O5 Dark mode | "O5-A: solo tema claro" | Option A: light theme only |
| U6 | Approval of the phase 02c spec and the direction | "Sí, apruebo la spec y la dirección" | Spec approved and frozen with the direction of U1 to U5 |

Decision taken by the supervisor, not by the user (supervisor decision, recommended option):

| ID | Decision | Reason | Effect on criteria |
|---|---|---|---|
| S1 | On step 2, the screening rule sentence that comes from the renderer and the text of the question are folded behind a disclosure control (`<details>`); they stay printed in the HTML, but closed disclosure content is not visible text under U4 | The step 2 mockup after Q2 counts 96 words under U4 against the cap of 93 | None: no criterion changes, so it is not a deviation |

## Open decisions
Questions the user must resolve before approving. Empty on approval.

None.
