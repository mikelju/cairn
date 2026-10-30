# 003 - Explanation inside the demo and a new visual style

Status: proposed

## Contract
Goal and reason: a first-time visitor finds the demo unclear and plain.
Two changes: (1) each page explains what its step does, why, and how to read its traces, quotations and rules; (2) a new visual style in the spirit of a dark, editorial photography-school site the user pointed to (inspiration only).
The explanation content comes from a private explainer kept outside git; it is rewritten here in our own words, in English, with no company or person names.
Out of scope: behaviour changes, new routes beyond what U3 decides, new features, new runtime dependencies, any asset, logo, text or code from the reference site, phone layouts beyond "does not break".
Constraints / decisions that need the user: the frozen rule "7-step walkthrough at 1440x900 without scrolling, with a per-step word cap checked by a test" (`docs/plans/0_plan_maestro.md:44`, cap 93 in `tests/test_word_cap.py:11`); step 3 already renders 93 words, step 2 Q2 open and step 5 refused 92, so any explanation inside `<main>` breaks the cap (U1).
The phase 02c decision "calm scientific report, light neutral background" changes if the dark direction is taken (U2).
Current authorisation and limits: E1 drafts this record, the before screenshots and a scratchpad mockup only; implementation waits for the user decisions.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | The landing, steps 1 to 7 and Explore each render a "How to read this page" explanation with three parts: what it does, why, how to read it; the texts are the ones in "Explanation content" below (or as edited by the user) | pytest rendering each page through the app and asserting the panel and its three headings exist and are non-empty; failing sample with one page missing it |
| C2 | The new tokens are applied: the `:root` block in `cairn.css` holds the values in "Visual direction" (background `#0e1316`, surface `#151c20`, ink `#e6ecee`, accent `#6cbcf5`, display tracking `-0.025em`, eyebrow tracking `0.14em`, card radius `10px`, pill radius `999px`); tokens stay in one block and no literal appears elsewhere | `test_design_tokens_*` updated to the new values (single block, adopted values, no inline style); computed style of `body` and `.card` read in the headless browser |
| C3 | Every page in every state of `test_word_cap_rendered`, plus Explore after each of Q1 and G1, has `document.documentElement.scrollHeight` 900 and `scrollWidth` 1440 at 1440x900, with the explanation closed and open | Headless Edge walkthrough over the DevTools protocol; measured values recorded in this file |
| C4 | Word caps hold as decided in U1: the `<main>` count stays at or under 93 for every state (counting rule unchanged); the explanation is counted by its own rule (recommended: at most 80 words per page and 25 per sentence) | `uv run pytest tests/test_word_cap.py -s` output with the printed counts |
| C5 | Contrast and badges keep phase 02c guarantees on the new palette: every token pair in use meets WCAG AA, every control has a visible `:focus-visible` outline, badges differ in at least two cues besides colour | `test_contrast_*` and badge tests green on the new tokens; keyboard pass through landing, step 3 and the explanation panel |
| C6 | After screenshots at 1440x900 of the landing, steps 1 to 7 (each after running the step as a visitor) and Explore exist as `docs/changes/003-evidence/after-<page>.png` next to the `before-<page>.png` files | The PNG files, captured with the same script and path as the before set |
| C7 | No new runtime dependency and no new font file: `pyproject.toml`, `uv.lock`, `package.json` and `src/cairn/web/static/fonts/` unchanged (unless U4 says otherwise); no template or stylesheet references an external URL | `git diff --stat origin/main -- pyproject.toml uv.lock package.json src/cairn/web/static/fonts`; existing external-URL test |
| C8 | Nothing is copied from the reference site: no file, image, logo, font, text or CSS from it in the diff; no hex value of its palette reused verbatim | Review of the diff; grep of the diff for the reference domain and for its observed hex values (`31a8ff`, `8adbd3`, `a3b1b7`, `1569af`, `eef3f4`) returns nothing |
| C9 | No regression: `npm run check` green and `make demo-offline-check` passes | Command output |

## Plan
- [ ] 1. Tokens and shell: new `:root` values, header as a floating pill bar, footer in mono, badges as pills keeping their glyphs and border styles; update `test_design_tokens_define_the_adopted_values` (C2, C5, C7, C8).
- [ ] 2. Explanation component: one macro rendering an `<aside class="explain">` outside `<main>` with a closed `<details>` and the three parts; texts for landing, steps 1 to 7 and Explore; word-cap test extended as U1 decides (C1, C4).
- [ ] 3. Landing: hero with the three lanes (model, code, people) and the badge legend within 93 words (the mockup is at 105 and must be trimmed) (C1, C4).
- [ ] 4. Walkthrough at 1440x900 with the explanation closed and open, after screenshots, scroll heights recorded; Explore Q1 overflow handled as U5 decides (C3, C6).
- [ ] 5. `npm run check`, `make demo-offline-check`, update this record (C9).

## Decisions
Placement: the explanation is a closed-by-default drawer in an `<aside>` beside `<main>`, opened with plain `<details>` (no JavaScript), drawn over the page with fixed position so it never adds height; this keeps the 1440x900 rule and leaves the `<main>` count unchanged.
The mockup's eyebrow line ("Step 03 of 07 · Guidance") adds 6 words inside `<main>` and takes step 3 to 98: it goes into the header bar or is dropped.
Fonts: the reference uses a grotesque display sans, a neutral text sans and a mono for labels; the existing self-hosted IBM Plex Sans (400, 600, 700) and IBM Plex Mono cover the same roles, so no new font is needed.
Found while taking the before set: Explore after Q1 measures `scrollHeight` 985 at 1440x900 (the evidence list runs below the fold), a pre-existing defect outside the frozen 7-step states (U5).

### Visual direction
- Type: IBM Plex Sans 700 for display, tracking -0.025em, h1 30px on steps and 52px on the landing; IBM Plex Sans 400 for body at 15px, line height 1.5; IBM Plex Mono 11px uppercase with 0.14em tracking for eyebrows, table headers, badges, step numbers and footer.
- Palette (dark): paper `#0e1316`, surface `#151c20`, surface-2 `#1b242a`, line `#27323a`, control border `#4a5862`, ink `#e6ecee`, muted `#9aa7ad`, accent `#6cbcf5` with on-accent `#071019`, teal `#7fd0c6` (REAL, eyebrow dots), recorded `#8fc3f2`, simulated `#e9b25d`, block `#ff8f86`.
- Spacing: 4, 8, 12, 16, 24, 32, 48, 64 px; content width 1248px, gutters 48px.
- Shapes: cards 10px radius with a 1px line and no shadow; buttons, badges, step links and the header bar as pills; the explanation panel is the only element with a shadow.
- Layout feel: a floating pill navigation bar centred at the top, generous negative space, a centred landing hero with a small mono eyebrow, a large tight headline and three numbered lane cards ("01 · The model", "02 · The code", "03 · The people").
- Mockup (scratchpad, not versioned): `mockup-landing.png` and `mockup-step3.png` in `003-evidence/`.

### Explanation content
Each page shows three parts; texts are short and in our own words.
- Landing. What: Cairn takes a public rat study in SEND format to a draft of the repeat-dose toxicity summary of a regulatory dossier. Why: today a toxicologist copies numbers by hand for days, and each copied number is a risk. How to read: REAL is computed now from the data; RECORDED is a real model answer saved with its date and cost; SIMULATED stands in for a production system.
- Step 1 Validate. What: loads the study and checks every value against fixed rules before anything else. Why: impossible values, such as the 12 negative exposures in the public study, must never reach the model. How to read: each quarantined row shows the rule it broke; the group mean is shown with and without the bad value; the switches inject a fault so you can watch the gate stop it. Values are flagged, never corrected.
- Step 2 Ask. What: you pick a question; the model chooses tools and writes sentences with gaps, and code fills each gap with a tested number. Why: the model never types a digit, so no number can be invented. How to read: "What the model wrote" shows the gaps; Trace lists the tool calls in order; each evidence line gives tool, population, n and source animals; "Rules fired: none" means every check passed; Q6 shows the model declining.
- Step 3 Guidance. What: two fixed searches over four public guidelines keep the best passages, each with guideline, section and page. Why: a quotation must be copied from the official text, not remembered. How to read: Lex ranks by shared words, Sem by meaning, Fused combines both, and rank 1 is best; every quotation is checked letter by letter on its page; "highlighted page" opens the page with the sentence marked.
- Explore. What: recorded questions as buttons, Q about the study (including trick questions) and G about the guidelines. Why: so you can try the demo on your own. How to read: the same answer, trace, rules and evidence as step 2; G answers quote guideline pages; a refused question is a feature, not an error.
- Step 4 Analyse. What: one row per finding and sex; a person marks from which dose it is treatment-related and from which it is adverse; a fixed rule proposes the NOAEL and the person confirms it. Why: scientific judgement stays with people, and the model is not called here. How to read: the NOAEL is the highest dose without relevant adverse effects versus control; it is a reference for the first human dose, not a safe dose.
- Step 5 Draft. What: the model drafts the summary; code places every value and quotation and leaves the human decisions as gaps; a second model, the judge, warns when a sentence overstates its source. Why: a draft you can defend sentence by sentence. How to read: each judge row gives the sentence, the kind of warning and the reason; the judge warns and never blocks; the author cannot approve their own draft.
- Step 6 Check. What: fixed rules run on the final text, and every action is written to a chained audit log. Why: who did what and when, and any later edit shows. How to read: a passed rule is green; each event carries the fingerprint of the previous one, so an altered copy points to the exact event; the log detects edits and is not a validated external log.
- Step 7 Review. What: the session summary, and the same tool called through two doors, MCP and REST. Why: the result must not depend on the interface. How to read: equal hashes mean the same Observation; the production table maps each demo piece to its production counterpart.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E1 | ejecutor | Draft this record: explanation content from the private explainer, visual direction from the reference site, before screenshots, scratchpad mockup, open decisions | needs decision | Record, 9 before and 2 mockup screenshots; U1 to U5 open |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | How does the explanation fit the frozen 93-word cap per step? Step 3 is already at 93, so even a one-word summary inside `<main>` breaks it | A (recommended): explanation in an `<aside>` outside `<main>`, closed by default; the `<main>` rule and cap stay unchanged and the test adds a separate cap for the explanation (80 words per page, 25 per sentence), so nothing is lowered. B: closed `<details>` inside `<main>` counted by its summary, trimming 2 to 4 words on step 3, step 2 Q2 open and step 5 refused. C: one separate `/guide` page linked from the header, nothing per page (less in context). D: raise the cap (changes a frozen criterion) | open | |
| U2 | Dark theme like the reference, replacing the phase 02c "calm scientific report, light background" decision? | A (recommended): dark as in the mockup, AA contrast kept by test. B: same type, spacing and shapes on a light background (closer to 02c, further from the reference) | open | |
| U3 | Also add a one-page guide (glossary of terms such as NOAEL, SEND, TK, adverse) linked from the header? | A (recommended): no, the per-page panels are enough and the brief asks for minimal. B: yes, a static `/guide` page with the short glossary, one new route | open | |
| U4 | Fonts: reuse IBM Plex or add a closer display font (for example an OFL grotesque, about 50 to 100 KB)? | A (recommended): reuse IBM Plex Sans and Mono, no new file. B: add one OFL display font file under `static/fonts/` with its licence notice (a new asset, not a runtime package) | open | |
| U5 | Explore after Q1 overflows to 985 px at 1440x900 today. Fix it in this change? | A (recommended): yes, as a clear related layout defect, by moving the evidence list into the right column or folding it; C3 covers it. B: log it and leave it for a later change | open | |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
- Before set at commit ceb0f17: `uv run cairn serve --port 8765` (after `uv run python -m cairn.ingest` to rebuild the ignored DuckDB file), headless Edge over the DevTools protocol at 1440x900; landing, step 1 (validation run), step 2 (Q2 asked), step 3, step 4 (example decisions filled), step 5 (NOAEL confirmed, approved as R. Reviewer), steps 6 and 7 (same thread) all measured `scrollHeight` 900 and `scrollWidth` 1440; Explore after Q1 measured 985.
- Current word counts (`tests/test_word_cap.py`, cap 93): landing 41, step1 before 45, after 71, injected 80, duplicate 89, dose 89, step2 before 20, Q2 80, Q2 open 92, Q6 39, step3 93, step4 empty 75, filled 79, step5 77, refused 92, step6 46, step7 60.
- Mockup: landing and step 3 (explanation open) measured `scrollHeight` 900; `<main>` counts 105 (landing) and 98 (step 3, because of the eyebrow), both to be trimmed in implementation as stated in Plan and Decisions.

## Delivery
Not started.
