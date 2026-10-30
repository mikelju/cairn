# 003 - Demo redesign: a landing that sells, visual hierarchy, in-page reading cues and an ES/EN toggle

Status: in progress

## Contract
Goal and reason: the user did not approve proposal 1 (explanation drawer plus restyle) and widened the scope.
Kept from proposal 1: the dark style; the side help panel is dropped (U9).
Critique of the current demo: what matters is not visible; pages are a wall of English text; questions cannot be told apart (Q1, G1 codes); it is unclear why some answers show a table and others do not; disclosures are barely visible and their purpose is unclear; the 11 Explore cards have no reading order.
New goal: a site a client can be shown; in 5 to 10 seconds a visitor sees what Cairn does and feels invited to continue (feel of a dark editorial site the user pointed to, inspiration only).
Scope: (1) a landing understood in 10 seconds: one message, a four-stage journey diagram (study, data, questions, traceable draft) and one obvious call to action; (2) visual hierarchy on every page: key numbers highlighted, icons, diagrams and visual states, with detail (traces, rows, JSON) behind disclosures drawn as clear pill buttons that name their content; (3) Explore as a guided sequence of three stages with the question text instead of Q/G codes; (4) one visible line on every answer saying why it is a table or prose; (5) much less visible text; (6) in-page reading cues on every page, no help panel or help button (U9); (7) an ES/EN language selector across the whole interface (U6).
Out of scope: behaviour changes, new routes, new features, new runtime dependencies, re-recording, translating study data, guideline passages or recorded model answers, any asset, logo, text or code from the reference site, phone layouts beyond "does not break".
Constraints: the frozen walkthrough rule (`docs/plans/0_plan_maestro.md:44`, cap 93 at `tests/test_word_cap.py:11`) holds for the landing and steps 1 to 7 in both locales; Explore scrolls vertically by design (U8).
The master plan rule "everything versioned is in English" (`docs/plans/0_plan_maestro.md:48`) still holds for code, docs, specs, tests and commits; the UI string catalogue is the one versioned place that holds both languages, by U6.
The phase 02c decision "calm scientific report, light neutral background" is replaced by the dark style (U2 answered).
Nothing versioned names the client or people.
Current authorisation and limits: E5 produces mockups v3; E6 records the user decisions; implementation follows the plan below, one executor per increment.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | Every page (landing, steps 1 to 7, Explore) teaches its own reading order in place: a visible ordered path (`ol` of numbered stages) or at least two section labels (`.eyebrow`) inside `<main>`; no help panel and no help button exist anywhere | pytest rendering every page in both locales and asserting the path or labels; a test grepping templates, CSS and rendered HTML for `aside.explain`, `class="explain"` and the old "How to read this page" label finds nothing |
| C2 | Dark tokens in one `:root` block of `cairn.css` (paper `#0e1316`, surface `#151c20`, ink `#e6ecee`, accent `#6cbcf5`, display tracking `-0.025em`, eyebrow tracking `0.14em`, card radius `10px`, pill radius `999px`); no colour literal elsewhere | `test_design_tokens_*` updated; computed style of `body` and `.card` in the headless browser |
| C3 | At 1440x900 with disclosures closed, the landing and every state of `test_word_cap_rendered`, in both locales, have `scrollHeight` 900 and `scrollWidth` 1440; Explore has `scrollWidth` 1440 at every scroll position and any `scrollHeight` | Headless Edge walkthrough over the DevTools protocol; measured values recorded in this file |
| C4 | The landing has exactly one `h1`, a journey of four ordered stages (study, data, questions, traceable draft) and exactly one primary call to action | pytest on `/`: one `h1`, one `ol.journey` with four `li`, one `.btn-primary` |
| C5 | Contrast and badges keep phase 02c guarantees on the dark palette: every token pair in use meets WCAG AA, every control has a visible `:focus-visible` outline, badges differ in at least two cues besides colour | `test_contrast_*` and badge tests green; keyboard pass through the landing, the language toggle, step 3, a disclosure and the Explore stages |
| C6 | After screenshots at 1440x900 exist as `docs/changes/003-evidence/after-<page>.png` next to `before-<page>.png` for steps 1 to 7 (each after running the step as a visitor), and in both locales (`after-<page>-es.png`, `after-<page>-en.png`) for the landing and Explore | The PNG files, captured with the same script as the before set |
| C7 | No new runtime dependency and no new font file: `pyproject.toml`, `uv.lock`, `package.json` and `src/cairn/web/static/fonts/` unchanged; no external URL in templates or stylesheets | `git diff --stat origin/main -- pyproject.toml uv.lock package.json src/cairn/web/static/fonts`; existing external-URL test |
| C8 | Nothing copied from the reference site: no file, image, logo, font, text or CSS; none of its hex values (`31a8ff`, `8adbd3`, `a3b1b7`, `1569af`, `eef3f4`) | Diff review; grep of the diff for the reference domain and those values returns nothing |
| C9 | No regression: `npm run check` green and `make demo-offline-check` passes | Command output |
| C10 | Explore question cards show the question text in the active locale as their visible label; no `Q<n>` or `G<n>` code is a visible label (an id attribute or a small secondary tag is allowed) | pytest on `/explore` in both locales: each card's label equals the catalogue text (EN equals `src/cairn/questions.py`) and no card label matches `^[QG]\d+$` |
| C11 | Every disclosure is a `<details>` whose `<summary>` is styled as a pill button and names its content and size in the active locale, for example "Ver ranking de pasajes · 3 filas" or "Show passage ranking · 3 rows"; no bare "Details", "More", "Show" or their Spanish equivalents | pytest over every rendered state in both locales: each `summary` has class `pill` and matches `<verb> <content> · <n> <unit>` or a listed fixed label; screenshot of step 3 |
| C12 | Every answer (step 2 and Explore) shows one format line saying why it is a table or prose, for example "Tabla: varias dosis y sexos" or "Table: several doses and sexes" | pytest over step 2 Q2, Q6 and Explore after each recorded question, both locales: one `.format-line` present and non-empty |
| C13 | Visible words inside `<main>` with disclosures closed stay at or under 93 on the landing and every step state, counted separately in ES and EN under the existing rule (`tests/test_word_cap.py:17-75`); Explore has no word cap (C15 governs it) | `uv run pytest tests/test_word_cap.py -s` output with printed counts per locale |
| C14 | An ES/EN toggle is visible on every page; with EN every UI string is English and with ES every UI string is Spanish; study data, guideline passages and recorded model prose are identical in both modes; the chosen locale persists across navigation (query parameter or cookie, no new dependency); both catalogues have the same keys | pytest rendering every page and state in both locales and asserting no string from the other locale's catalogue appears (shared tokens such as REAL, NOAEL or units excluded by a listed set), the data and recorded prose blocks are equal across locales, a follow-up request keeps the locale, and the key sets match |
| C15 | Explore renders three ordered stages, one per question group (the study; limits and trick questions; the guidelines), each with a visible stage number; an answer renders inside its stage under the card that asked it; stages reveal on scroll with vanilla JS and are fully visible with JS off and under `prefers-reduced-motion` | pytest on `/explore` and after one question per group: three `section.stage` in order numbered 1 to 3, the answer inside the asking card's stage; headless check with JS disabled and with reduced motion emulated shows every stage visible; mockups v3 as the visual reference |

## Plan
Each increment fits one Sonnet executor with limited context.
- [x] 1. Tokens and shell with locale: dark `:root` values, floating pill header bar with the ES/EN toggle, mono footer, badges as pills keeping glyphs and border styles; a string catalogue (one EN and one ES table of our own UI text), locale from query parameter and cookie, every shell string read from it; update `test_design_tokens_*`; catalogue key-parity test (C2, C5, C7, C8, C14).
- [x] 2. Components: a disclosure macro (`<details>` with a pill `<summary>` taking content label and count) and in-page reading cues (ordered path or section labels) for every page, from the catalogue; remove the help button and any help panel; tests for C1 and C11 in both locales (C1, C5, C11).
- [ ] 3. Landing: one-line message, `h1`, four-stage journey diagram with icons, one primary CTA to step 1, badge legend inline as a reading cue; within the cap in both locales (C3, C4, C13, C14).
- [ ] 4. Explore guided sequence: three numbered stages (study, limits and trick questions, guidelines), cards with the question text, answer inside its stage under its card, format line on every answer (step 2 too), vanilla JS scroll reveal that degrades to fully visible; tests in both locales (C3, C10, C12, C14, C15).
- [ ] 5. Steps 1 to 7 hierarchy pass in both locales: one highlighted key number or state per step, traces, rows and JSON behind the disclosure component, prose trimmed, every string from the catalogue; word-cap test parametrised by locale (C3, C11, C13, C14).
- [ ] 6. Walkthrough at 1440x900 in both locales, after screenshots (both locales for landing and Explore), scroll heights recorded, `npm run check` and `make demo-offline-check`, update this record (C3, C6, C9).

## Decisions
Reading cues instead of a help panel (U9): each page marks its own path with numbered stages or section labels inside `<main>`; on the landing and steps 1 to 7 they count toward the cap.
How the word cap counts today (`tests/test_word_cap.py:17-75`): only text inside `<main>`; header, footer and anything outside `<main>` are free; a closed `<details>` counts only its `<summary>`; a `<tbody>` counts as one word; `<script>`, `<style>` and `<template>` are dropped; the lede must be one sentence of at most 25 words.
The cap stays 93 and is counted once per locale (supervisor decision, keeping the master plan freeze); Explore leaves the cap and is governed by sequence (U7).
Fonts: the existing self-hosted IBM Plex Sans (400, 600, 700) and IBM Plex Mono cover display, text and label roles (U4 A).
Language (U6): one catalogue of our own UI strings per locale; templates read every string through it; study data, guideline passages, recorded model prose and Observation JSON pass through untouched and stay English; nothing is re-recorded.
Default locale: ES, with EN one click away for the client's team members who do not read Spanish (supervisor decision; reversible in increment 1).
Explore groups (supervisor decision, from `src/cairn/questions.py`): stage 1 the study (Q1, Q2, Q3, Q5), stage 2 limits and trick questions (Q4, Q6, Q7, Q8), stage 3 the guidelines (G1, G2, G3).
Scroll reveal: a small inline script adds a class through `IntersectionObserver`; without the script or under `prefers-reduced-motion` every stage is visible from the start, so the server-rendered page is complete.
Found while taking the before set: Explore after Q1 measures `scrollHeight` 985 at 1440x900; no longer a defect, since Explore scrolls by design (U5, U8).

### Visual direction
- Type: IBM Plex Sans 700 for display, tracking -0.025em, h1 30px on steps and 52px on the landing; IBM Plex Sans 400 for body at 15px, line height 1.5; IBM Plex Mono 11px uppercase with 0.14em tracking for eyebrows, stage numbers, table headers, badges, step numbers and footer.
- Palette (dark): paper `#0e1316`, surface `#151c20`, surface-2 `#1b242a`, line `#27323a`, control border `#5f6f79`, ink `#e6ecee`, muted `#9aa7ad`, accent `#6cbcf5` with on-accent `#071019`, teal `#7fd0c6` (REAL), recorded `#8fc3f2`, simulated `#e9b25d`, block `#ff8f86`.
- Spacing 4, 8, 12, 16, 24, 32, 48, 64 px; content width 1248px, gutters 48px; cards 10px radius, 1px line, no shadow; buttons, badges, disclosures, the language toggle and the header bar as pills.
- Hierarchy: each page leads with one highlighted number or state (for example "12 filas en cuarentena", "NOAEL 30 mg/kg/día") in display size, then at most two short lines, then pill disclosures for detail.
- Mockups v3 (E5), the reference for implementation: `docs/changes/003-evidence/mockup3-landing.png`, `mockup3-step3.png`, `mockup3-explore-1.png`, `mockup3-explore-2.png`, `mockup3-explore-3.png`, `mockup3-explore-full.png`.
- Earlier mockups, superseded: v2 (E3) `mockup2-landing.png`, `mockup2-step3.png`, `mockup2-explore.png`; proposal 1 `mockup-landing.png`, `mockup-step3.png`.

### Reading cue content
Source notes per page, in our own words, to be cut into path labels and short lines and written in ES and EN in increments 2 to 5.
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
| E3 | ejecutor | Mockups v2: landing, step 3 and Explore under the new scope | done | `mockup2-*.png`; superseded by v3 after U6, U7 and U9 |
| E4 | ejecutor | Rewrite this record: contract, criteria, decisions U1 to U8, plan in Sonnet-sized increments | done | Record rewritten |
| E5 | ejecutor | Mockups v3: landing, step 3 and the Explore guided sequence with the ES/EN toggle and in-page cues | in progress | |
| E6 | ejecutor | Record the user answers to U4 to U8 and the help removal; rework criteria and plan | done | This record |
| E7 | ejecutor | Increment 1: dark tokens, pill shell with ES/EN toggle, string catalogue and parity test | done | See plan item 1 and Evidence |
| E8 | ejecutor | Increment 2: disclosure pill macro, reading-cue macros, C1 and C11 tests | done | See plan item 2 and Evidence |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | How does the explanation fit the 93-word cap? | Side help panel outside `<main>` (proposal 1 option A) | answered | Dark style and side help panel stay (via Jefe). The side help panel part is superseded by U9; the dark style from U2 stays |
| U2 | Dark theme replacing the phase 02c light report style? | Dark, AA contrast kept by test | answered | Dark style and side help panel stay (via Jefe) |
| U3 | Add a one-page glossary at `/guide`? | Superseded by the wider scope: no glossary page | deferred | Superseded |
| U4 | Fonts: reuse IBM Plex or add a closer display font? | A (recommended): reuse IBM Plex Sans and Mono, no new file. B: one OFL display font under `static/fonts/` with its licence (about 50 to 100 KB, new asset) | answered | "A, approved (reuse IBM Plex)" (via Jefe) |
| U5 | Explore after Q1 overflows to 985 px at 1440x900. Fix it here? | A: fold the evidence behind a disclosure. B: log it for a later change | answered | Superseded: Explore becomes a scroll page (U7), so its height is no longer a defect (supervisor decision, recorded as such) |
| U6 | UI language. The master plan freezes "everything versioned in English, including UI"; the client is Spanish-speaking | A: Spanish UI, recorded prose tagged "EN · grabado". B: re-record every answer in Spanish. C: keep the UI in English | answered | "Neither A nor B. An ES/EN language selector across the whole interface: all our own text (UI, labels, explanations) in Spanish or all in English, per the selector. Study data, guidelines and recorded model answers stay in English in both modes and nothing is re-recorded. The repo documentation stays in English. Reason: to share it with members of the client's team who do not speak Spanish." (via Jefe) |
| U7 | Word cap. Today it counts only visible text inside `<main>`, a closed disclosure by its summary and a table body as one word (`tests/test_word_cap.py:17-75`) | A: keep the rule and the cap of 93, adding Explore states. B: raise the cap for Spanish by about 15 percent | answered | "Replace the Explore word cap with a guided path. The 11 cards are piled up without a clear reading order and the right column goes its own way. Wanted: a natural sequence while navigating (scroll that reveals by stages, or animations): first one group, then the second, then the third, not all at once. Text should stay short, but the criterion is the sequence, not a word count." (via Jefe) |
| U8 | Viewport. The frozen rule is the 7-step walkthrough at 1440x900 without scrolling | A: no scroll on the landing and the 7 steps; vertical scroll only on Explore, never horizontal. B: no scroll anywhere | answered | Resolved by U7: no scroll on the landing and steps 1 to 7; Explore scrolls vertically by design, never horizontally (supervisor decision, recorded as such) |
| U9 | Keep the "? How to read this page" help button? | Raised by the user | answered | "Remove the '? How to read this page' button. The page itself must mark the path and teach how to read it without going to a help panel. Apply it to every page, not only Explore." (via Jefe) |
| U10 | Approve change 003 for implementation? | Raised by the supervisor after mockups v3 | answered | "Apruebo el cambio 003 con los criterios C1-C15 de la spec actual: estilo oscuro, IBM Plex, selector ES/EN con datos y respuestas grabadas en inglés, recorrido guiado por etapas en Explore, sin panel de ayuda y tope de 93 palabras en portada y pasos. Implementa hasta la PR" |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
- Before set at commit ceb0f17: `uv run cairn serve --port 8765` (after `uv run python -m cairn.ingest`), headless Edge over the DevTools protocol at 1440x900; landing, steps 1 to 7 measured `scrollHeight` 900 and `scrollWidth` 1440; Explore after Q1 measured 985.
- Word counts before (`tests/test_word_cap.py`, cap 93): landing 41, step1 before 45, after 71, injected 80, duplicate 89, dose 89, step2 before 20, Q2 80, Q2 open 92, Q6 39, step3 93, step4 empty 75, filled 79, step5 77, refused 92, step6 46, step7 60.

- Increment 1 (E7): dark `:root` in `src/cairn/web/static/cairn.css` (C2); pill shell in `_components.html` and `base.html`; catalogue `src/cairn/web/i18n.py` (EN and ES dicts, `?lang=` query parameter remembered by the `cairn_lang` cookie through an ASGI middleware, default ES); `tests/test_i18n.py` checks key parity, the default, the toggle, persistence and toggle links; `tests/test_design.py` pins the new tokens. Deviation: `--color-control-border` is `#5f6f79`, not `#4a5862`, because the specified value gave 2.55:1 on paper and C5 needs 3:1 (now 3.59:1 on paper, 3.31:1 on surface). Existing tests that read English shell strings now request `?lang=en`. Body strings are not translated yet (increments 2 to 5).
- Increment 2 (E8): macros `disclosure(key, n, unit, tag)`, `reading_path(labels, label)` and `cue(number)` in `src/cairn/web/templates/_components.html`, pill CSS in `cairn.css` (focus outline from the shared `summary:focus-visible` rule); labels `disc_*` and units `unit_*` ("singular|plural") in `src/cairn/web/i18n.py`; every `<details>` in the templates goes through the macro and the HTMX fragments now receive the catalogue. `tests/test_disclosures.py` (both locales): every rendered summary has class `pill` and matches `<verb> <content> · <n> <unit>` with a non-generic content; no `aside`, `class="explain"` or help label in templates, CSS or rendered pages; the path and cue macros render. The path and cue are components only: pages adopt them in increments 3 to 5. Word cap kept without touching the counter: evidence line of step 2 and Explore moved behind a pill (`disc_evidence`), step 3 and step 5 wording trimmed ("Verbatim: n/m", "Recorded questions", "The judge never blocks."). Counts in ES (default): step2 Q2 81, Q2 open 93, step3 92.

## Delivery
Not started.
