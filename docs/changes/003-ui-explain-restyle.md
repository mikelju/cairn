# 003 - Demo redesign: a landing that sells, visual hierarchy and a side help panel

Status: proposed

## Contract
Goal and reason: the user did not approve proposal 1 (explanation drawer plus restyle) and widened the scope.
Kept from proposal 1: the dark style and the side help panel.
Critique of the current demo: what matters is not visible; pages are a wall of English text; questions cannot be told apart (Q1, G1 codes); it is unclear why some answers show a table and others do not; disclosures are barely visible and their purpose is unclear.
New goal: a site a client can be shown; in 5 to 10 seconds a visitor sees what Cairn does and feels invited to continue (feel of a dark editorial site the user pointed to, inspiration only).
Scope: (1) a landing understood in 10 seconds: one message, a four-stage journey diagram (study, data, questions, traceable draft) and one obvious call to action; (2) visual hierarchy on every page: key numbers highlighted, icons, diagrams and visual states, with detail (traces, rows, JSON) behind disclosures drawn as clear pill buttons that name their content; (3) Explore question cards that show the question text instead of Q/G codes; (4) one visible line on every answer saying why it is a table or prose; (5) much less visible text; (6) side help panel on every page; (7) UI language as U6 decides.
Out of scope: behaviour changes, new routes, new features, new runtime dependencies, re-recording (unless U6 B), any asset, logo, text or code from the reference site, phone layouts beyond "does not break".
Constraints / decisions that need the user: the frozen rules "7-step walkthrough at 1440x900 without scrolling, with a per-step word cap checked by a test" (`docs/plans/0_plan_maestro.md:44`, cap 93 at `tests/test_word_cap.py:11`) and "everything versioned is in English ... and UI" (`docs/plans/0_plan_maestro.md:47`) clash with the request; adjustments are proposed in U6, U7 and U8 and nothing is lowered without an answer.
The phase 02c decision "calm scientific report, light neutral background" is replaced by the dark style (U2 answered).
Nothing versioned names the client or people.
Current authorisation and limits: E4 rewrites this record; E3 produces mockups v2; implementation waits for U4 to U8.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | The landing, steps 1 to 7 and Explore each render the side help panel (`<aside class="explain">` outside `<main>`) with three non-empty parts: what, why, how to read | pytest rendering every page through the app and asserting the panel and its three parts; failing sample with one page missing it |
| C2 | Dark tokens in one `:root` block of `cairn.css` (paper `#0e1316`, surface `#151c20`, ink `#e6ecee`, accent `#6cbcf5`, display tracking `-0.025em`, eyebrow tracking `0.14em`, card radius `10px`, pill radius `999px`); no colour literal elsewhere | `test_design_tokens_*` updated; computed style of `body` and `.card` in the headless browser |
| C3 | Viewport as U8 decides (recommended: landing and every state of `test_word_cap_rendered` have `scrollHeight` 900 and `scrollWidth` 1440 at 1440x900 with disclosures closed and the help panel closed and open; Explore may scroll vertically, never horizontally) | Headless Edge walkthrough over the DevTools protocol; measured values recorded in this file |
| C4 | The landing has exactly one `h1`, a journey of four ordered stages (study, data, questions, traceable draft) and exactly one primary call to action | pytest on `/`: one `h1`, one `ol.journey` with four `li`, one `.btn-primary` |
| C5 | Contrast and badges keep phase 02c guarantees on the dark palette: every token pair in use meets WCAG AA, every control has a visible `:focus-visible` outline, badges differ in at least two cues besides colour | `test_contrast_*` and badge tests green; keyboard pass through landing, step 3, a disclosure and the help panel |
| C6 | After screenshots at 1440x900 of the landing, steps 1 to 7 (each after running the step as a visitor) and Explore exist as `docs/changes/003-evidence/after-<page>.png` next to `before-<page>.png` | The PNG files, captured with the same script as the before set |
| C7 | No new runtime dependency and no new font file unless U4 says otherwise: `pyproject.toml`, `uv.lock`, `package.json` and `src/cairn/web/static/fonts/` unchanged; no external URL in templates or stylesheets | `git diff --stat origin/main -- pyproject.toml uv.lock package.json src/cairn/web/static/fonts`; existing external-URL test |
| C8 | Nothing copied from the reference site: no file, image, logo, font, text or CSS; none of its hex values (`31a8ff`, `8adbd3`, `a3b1b7`, `1569af`, `eef3f4`) | Diff review; grep of the diff for the reference domain and those values returns nothing |
| C9 | No regression: `npm run check` green and `make demo-offline-check` passes | Command output |
| C10 | Explore question cards show the question text as their visible label; no `Q<n>` or `G<n>` code is a visible label (an id attribute or a small secondary tag is allowed) | pytest on `/explore`: each card's label equals the text in `src/cairn/questions.py` and no card label matches `^[QG]\d+$` |
| C11 | Every disclosure is a `<details>` whose `<summary>` is styled as a pill button and names its content and size, for example "Ver ranking de pasajes · 3 filas" or "Show passage ranking · 3 rows"; no bare "Details", "More" or "Show" | pytest over every rendered state: each `summary` has class `pill` and matches the pattern `<verb> <content> · <n> <unit>` or a listed fixed label; screenshot of step 3 |
| C12 | Every answer (step 2 and Explore) shows one format line saying why it is a table or prose, for example "Tabla: varias dosis y sexos" or "Texto: una sola cifra" | pytest over step 2 Q2, Q6 and Explore after each recorded question: one `.format-line` present and non-empty |
| C13 | Visible word count with disclosures and the help panel closed stays within the cap as U7 decides (recommended 93) on the landing, every step state and Explore after each recorded question | `uv run pytest tests/test_word_cap.py -s` output with printed counts, Explore states added |

## Plan
Each increment fits one Sonnet executor with limited context.
- [ ] 1. Tokens and shell: dark `:root` values, floating pill header bar, mono footer, badges as pills keeping glyphs and border styles; update `test_design_tokens_*` (C2, C5, C7, C8).
- [ ] 2. Components: a disclosure macro (`<details>` with a pill `<summary>` taking content label and count) and the side help panel macro outside `<main>`, closed by default, fixed position so it adds no height; help texts for every page; tests for C1 and C11 (C1, C5, C11).
- [ ] 3. Landing: one-line message, `h1`, four-stage journey diagram with icons, one primary CTA to step 1, badge legend moved to the help panel; within the cap (C3, C4, C13).
- [ ] 4. Explore: question cards with the question text, grouped "About the study" and "About the guidelines"; format line on every answer (step 2 too); Explore overflow handled as U5 and U8 decide; Explore states added to the word-cap test (C3, C10, C12, C13).
- [ ] 5. Steps 1 to 7 hierarchy pass: one highlighted key number or state per step, traces, rows and JSON moved behind the disclosure component, prose trimmed (C3, C11, C13).
- [ ] 6. Spanish UI, only if U6 A: navigation, labels, help texts, question cards and format lines in Spanish; recorded English model prose shown as is with the tag "EN · grabado"; tests that match UI strings updated (C10, C11, C12, C13).
- [ ] 7. Walkthrough at 1440x900, after screenshots, scroll heights recorded, `npm run check` and `make demo-offline-check`, update this record (C3, C6, C9).

## Decisions
Help panel placement: an `<aside>` beside `<main>`, closed by default, opened with plain `<details>` (no JavaScript) and drawn over the page with fixed position, so it never adds height and is outside the `<main>` count.
How the word cap counts today (`tests/test_word_cap.py:17-75`): only text inside `<main>`; header, footer and anything outside `<main>` are free; a closed `<details>` counts only its `<summary>`; a `<tbody>` counts as one word; `<script>`, `<style>` and `<template>` are dropped; the lede must be one sentence of at most 25 words.
So "visible text with disclosures closed" is already the rule inside `<main>`; U7 only states it and extends it to Explore, which is not in the parametrised states today.
Proposal 1 measured step 3 at 93 and step 2 Q2 open and step 5 refused at 92 under this rule; the redesign moves detail behind disclosures, so counts should fall.
Fonts: the existing self-hosted IBM Plex Sans (400, 600, 700) and IBM Plex Mono cover display, text and label roles (U4).
Found while taking the before set: Explore after Q1 measures `scrollHeight` 985 at 1440x900 (U5, U8).

### Visual direction
- Type: IBM Plex Sans 700 for display, tracking -0.025em, h1 30px on steps and 52px on the landing; IBM Plex Sans 400 for body at 15px, line height 1.5; IBM Plex Mono 11px uppercase with 0.14em tracking for eyebrows, table headers, badges, step numbers and footer.
- Palette (dark): paper `#0e1316`, surface `#151c20`, surface-2 `#1b242a`, line `#27323a`, control border `#4a5862`, ink `#e6ecee`, muted `#9aa7ad`, accent `#6cbcf5` with on-accent `#071019`, teal `#7fd0c6` (REAL), recorded `#8fc3f2`, simulated `#e9b25d`, block `#ff8f86`.
- Spacing 4, 8, 12, 16, 24, 32, 48, 64 px; content width 1248px, gutters 48px; cards 10px radius, 1px line, no shadow; buttons, badges, disclosures and the header bar as pills; the help panel is the only element with a shadow.
- Hierarchy: each page leads with one highlighted number or state (for example "12 filas en cuarentena", "NOAEL 30 mg/kg/día") in display size, then at most two short lines, then pill disclosures for detail.
- Mockups v2 (E3): `docs/changes/003-evidence/mockup2-landing.png`, `mockup2-step3.png`, `mockup2-explore.png`.
- Proposal 1 record, not approved: `docs/changes/003-evidence/mockup-landing.png` and `mockup-step3.png`.

### Help panel content
Three short parts per page, in our own words, to be trimmed and translated in increments 2 and 6.
- Landing. What: Cairn takes a public rat study in SEND format to a draft repeat-dose toxicity summary. Why: today numbers are copied by hand for days, and each copy is a risk. How to read: REAL is computed now; RECORDED is a real model answer saved with date and cost; SIMULATED stands in for a production system.
- Step 1 Validate. What: every value is checked against fixed rules first. Why: impossible values, such as the 12 negative exposures, must never reach the model. How to read: each quarantined row shows its rule; the switches inject a fault to watch the gate stop it; values are flagged, never corrected.
- Step 2 Ask. What: the model chooses tools and writes sentences with gaps; code fills each gap with a tested number. Why: the model never types a digit. How to read: the trace lists tool calls in order; "Rules fired: none" means every check passed; Q6 shows the model declining.
- Step 3 Guidance. What: two searches over four public guidelines keep the best passages with guideline, section and page. Why: a quotation must be copied, not remembered. How to read: Lex ranks by shared words, Sem by meaning, Fused combines both; each quotation is checked letter by letter.
- Explore. What: recorded questions about the study (including trick questions) and about the guidelines. Why: to try the demo yourself. How to read: same answer, trace and rules as step 2; a refused question is a feature.
- Step 4 Analyse. What: a person marks from which dose each finding is treatment-related and adverse; a fixed rule proposes the NOAEL. Why: judgement stays with people; no model here. How to read: the NOAEL is a reference for the first human dose, not a safe dose.
- Step 5 Draft. What: the model drafts; code places every value and quotation; a judge model warns on overstatement. Why: a draft defensible sentence by sentence. How to read: the judge warns and never blocks; the author cannot approve their own draft.
- Step 6 Check. What: fixed rules on the final text and a chained audit log. Why: who did what and when, and any later edit shows. How to read: each event carries the previous fingerprint; not a validated external log.
- Step 7 Review. What: the session summary and one tool through two doors, MCP and REST. Why: the result must not depend on the interface. How to read: equal hashes mean the same Observation.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E1 | ejecutor | Draft proposal 1: explanation content, visual direction, before screenshots, scratchpad mockup, open decisions | done | Record, 9 before and 2 mockup screenshots; proposal not approved, scope widened |
| E2 | ejecutor | Rework the record for the wider scope | failed | Ran out of context; nothing written |
| E3 | ejecutor | Mockups v2: landing, step 3 and Explore under the new scope | in progress | |
| E4 | ejecutor | Rewrite this record: contract, criteria, decisions U1 to U8, plan in Sonnet-sized increments | done | This record |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | How does the explanation fit the 93-word cap? | Side help panel outside `<main>` (proposal 1 option A) | answered | Dark style and side help panel stay (via Jefe) |
| U2 | Dark theme replacing the phase 02c light report style? | Dark, AA contrast kept by test | answered | Dark style and side help panel stay (via Jefe) |
| U3 | Add a one-page glossary at `/guide`? | Superseded by the wider scope: no glossary page; the help panel carries the explanations | deferred | Superseded |
| U4 | Fonts: reuse IBM Plex or add a closer display font? | A (recommended): reuse IBM Plex Sans and Mono, no new file. B: one OFL display font under `static/fonts/` with its licence (about 50 to 100 KB, new asset) | open | |
| U5 | Explore after Q1 overflows to 985 px at 1440x900. Fix it here? | A (recommended): yes, as a related layout defect, by folding the evidence behind a disclosure; C3 covers it. B: log it for a later change | open | |
| U6 | UI language. The master plan freezes "everything versioned in English, including UI"; the client is Spanish-speaking | A (recommended): Spanish UI (navigation, labels, help texts, question cards, format lines); code, docs and tests in English; recorded English model prose shown as is, tagged "EN · grabado"; amends the master plan line for the UI only. B: re-record every answer in Spanish with Bedrock (about 0.06 USD per question per change 002, plus re-checking the number-word rules for Spanish). C: keep the UI in English | open | |
| U7 | Word cap. Today it counts only visible text inside `<main>`, a closed disclosure by its summary and a table body as one word (`tests/test_word_cap.py:17-75`) | A (recommended): keep that rule and the cap of 93 for Spanish, stating it as "visible words with disclosures and the help panel closed" and adding Explore states. B: raise the cap for Spanish by about 15 percent (Spanish runs longer), a change to a frozen criterion | open | |
| U8 | Viewport. The frozen rule is the 7-step walkthrough at 1440x900 without scrolling | A (recommended): keep no scroll on the landing and the 7 steps; allow vertical scroll below the fold only on Explore, never horizontal. B: no scroll anywhere, Explore included (forces folding every answer) | open | |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
- Before set at commit ceb0f17: `uv run cairn serve --port 8765` (after `uv run python -m cairn.ingest`), headless Edge over the DevTools protocol at 1440x900; landing, steps 1 to 7 measured `scrollHeight` 900 and `scrollWidth` 1440; Explore after Q1 measured 985.
- Word counts before (`tests/test_word_cap.py`, cap 93): landing 41, step1 before 45, after 71, injected 80, duplicate 89, dose 89, step2 before 20, Q2 80, Q2 open 92, Q6 39, step3 93, step4 empty 75, filled 79, step5 77, refused 92, step6 46, step7 60.

## Delivery
Not started.
