# Cairn demo style (estilo.md)

This file is the single source of the visual style of the Cairn demo canvas.
It describes the design as published (Main, Step1, Step2, Step3, Step4), version 14 of the canvas.
Edit the token values here, then apply them as described in "How to apply".
Every CSS variable name below is identical to the name in the `:root` rule of each file.

## 1
Color tokens

Mode: medium-dark, cool slate grey.
Not near-black, not cream.
Contrast ratios are computed against the token they sit on.

### Surfaces and text

- --paper: #2b323d.
  Page background and the body of every screen.
  Also the text color on inverted controls (active step, primary button, plus/minus marker).
- --rail: #232930.
  Left side panel background and the Step2 live-question bar.
- --surface: #353d4a.
  Cards, language tag, question buttons.
- --ink: #eef1f6.
  Normal text, including the text written by the AI. Also fills inverted controls. 11.4:1 on --paper, 9.7:1 on --surface.
- --muted: #b0bacb.
  Secondary text: lede, meta, labels, footer, inactive step links. 6.6:1 on --paper, 5.6:1 on --surface.
- --line: #4b5565.
  Hairlines, table row lines, card borders, hard offset shadow of cards.
- --ctl: #8190a5.
  Borders of controls (language switch, question buttons, fields, role switch) and the underline of details summaries. 4.0:1 on --paper.

### Accent

- --accent: #8db8f2.
  Single sober accent: step counter, badge, links, small buttons, active language, active role segment, offset shadow of the primary button, radio color. 6.3:1 on --paper, 5.4:1 on --surface.
- --accent-tint: #2b405e.
  Background of the info box in Step4.
  Text on it is --ink, --muted and --accent (5.1:1 or more).
- --on-accent: #101620.
  Text on --accent fills. 8.9:1.

### Semantic colors

- --real: #80e3ac.
  Text of a study datum, always on --real-bg. 6.5:1.
- --real-bg: #1b4a38.
  Background of a study datum.
- --decided: #c9bcff.
  Text of a decision already taken (violet). 7.5:1 on --paper, 6.3:1 on --surface.
- --pending: #ffd84a.
  Background of a decision not yet taken (yellow).
  Also highlights the injected row in Step1.
- --on-pending: #14171c.
  Text on --pending, always. 13.0:1.
- --block: #ff9a94.
  Error, impossible value, trap marker, validation warnings. 6.3:1 on --paper, 5.4:1 on --surface.

### Document sheet (the draft in Step4, light paper on purpose)

- --sheet-wrap: #1f252d.
  Dark area around the sheet.
- --sheet-bg: #f8f9fb.
  Sheet paper.
- --sheet-ink: #1a1d23.
  Sheet body text. 16.0:1.
- --sheet-ink-strong: #0f1217.
  Sheet title and headings.
- --sheet-ink-2: #3a404c.
  Subtitle, quote text, table header rule.
- --sheet-muted: #566070.
  Sheet header, footer and metadata labels. 6.0:1.
- --sheet-line: #d5d9e0.
  Table row lines and metadata box border.
- --sheet-line-soft: #e2e5ea.
  Lines inside the metadata box.
- --sheet-rule: #9aa2b0.
  Header, footer, heading and quote rules.
- --sheet-tint: #eff1f5.
  Metadata box background.
- --sheet-shadow: rgba(0,0,0,.45).
  Shadow under the sheet.
- --sheet-real: #0b6b47.
  Study datum text and underline inside the sheet. 5.5:1 on --sheet-real-bg.
- --sheet-real-bg: #d9f0e2.
  Study datum background inside the sheet.
- --sheet-decided: #3f3597.
  Decision taken, text inside the sheet. 7.5:1 on --sheet-decided-bg.
- --sheet-decided-bg: #e4e0fa.
  Decision taken, background inside the sheet.

### Root-level setting

- color-scheme: dark
  Native controls (password field, scrollbars, radios) render dark.

## 2
Typography tokens

Fonts are loaded from Google Fonts: DM Mono 400 and 500, DM Sans 400, 500 and 700, Fraunces 400, 600 and 700 (optical size 9 to 144).

- Body: DM Sans, then system-ui, sans-serif. 15px, line-height 1.55, weight 400.
- Display and headings: Fraunces, then Georgia, serif
  Weight 600, brand weight 700.
- Labels and code-like text: DM Mono, then monospace.
- Sheet body and headings: Georgia, then Times New Roman, serif. 14.5px, line-height 1.6.
- Sheet header, footer, metadata labels: system-ui, sans-serif.

Sizes in use:

- Brand (Cairn, in the side panel): Fraunces 700, 34px, letter-spacing -.02em, line-height 1.
- h1: Fraunces 600, 48px, letter-spacing -.025em, line-height 1.05
  At phone width 34px
  The cover headline is 64px, line-height 1.02.
- h2: Fraunces 600, 20px, line-height 1.2
  Card titles use 22px.
- Lede: 19px, --muted, max width 700px.
- Meta text: 13px, --muted.
- Step counter: DM Mono 500, 12px, uppercase, letter-spacing .12em, --accent.
- Step number in the panel: Fraunces 600, 20px.
- Step link in the panel: 15px.
- Tile number: Fraunces 600, 60px, letter-spacing -.03em, tabular numbers
  Large variants use 96px and 56px.
- Table: 13px, tabular numbers
  Table header: DM Mono 500, 11px, uppercase, letter-spacing .06em.
- Footer and role label: DM Mono, 11px, letter-spacing .03em and .04em.
- Language switch: DM Mono 500, 12px, letter-spacing .08em.
- Badge: DM Mono 500, 11px, letter-spacing .08em.
- Language tag: DM Mono 500, 12px, uppercase, letter-spacing .06em.
- Buttons: primary and secondary 16px weight 700; small 14px weight 700; segment 13px weight 700.
- Question buttons: weight 500; small variant 13px.
- Details summary: 14px weight 700.
- Sheet title 30px; sheet h2 18px; sheet h3 15px; sheet header and footer 11px uppercase letter-spacing .06em; metadata labels 12px.
- Example quote on the cover: Fraunces, 21px, line-height 1.6.

## 3
Shape, shadow and spacing tokens

Radii:

- 4px: cards, buttons, language switch, role switch, fields, question buttons, plus/minus marker, step links, sheet wrap.
- 2px: badge, language tag, trap marker, highlight, datum chips (top corners only), sheet decision and datum.

Borders:

- Cards and hairlines: 1px --line.
- Control borders: 1.5px --ctl (question buttons, fields, role switch); language switch 1px --ctl.
- Primary and secondary buttons and small buttons: 2px.
- Table header rule: 2px --ink
  Tile top rule: 2px --ink.
- Datum chips: 2px underline in the current text color.
- Trap marker: 1px dashed --block.
- Answer card on the AI side in Step2: dashed border, no shadow, transparent.

Shadows (hard offset, no blur):

- Card: 3px 3px 0 --line.
- Primary button and selected question button: 4px 4px 0 --accent.
- Sheet: 0 6px 24px --sheet-shadow.

Layout:

- Side panel width: 240px, padding 32px 24px, gap 24px, right border 1px --line
  Under 900px wide it becomes a full-width top bar with padding 16px and a bottom border.
- Main column: max width 1100px, padding 56px 64px 24px
  Under 900px padding 32px 16px.
- Step content max width 900px.
- Footer: padding 16px 64px 24px, top border 1px --line, side margin 64px
  Under 900px padding 16px, side margin 16px.
- Card padding: 20px 24px.
- Buttons: primary and secondary padding 12px 28px; small padding 6px 18px; question button padding 14px 18px (small 8px 12px); segment padding 5px 16px; field padding 6px 10px; step link padding 8px 12px.
- Gaps: step list 2px; button row 12px (top margin 32px); tile grid 24px; question grid 12px and 8px.
- Sheet: max width 794px, min width 560px, padding 64px 72px 40px; wrap padding 40px 16px.

## 4
Semantic distinctions

Use these rules everywhere
Each meaning has one look and no other meaning may share it.

- Study datum (a value that comes from the study, placed by code): text --real on --real-bg, bold, with a 2px underline in the same color
  Inside the Step4 sheet: --sheet-real on --sheet-real-bg, underlined
  Datum chips are buttons; the plain legend key is a span.
- Decision pending (a gap that a person must still decide): background --pending with text --on-pending, bold
  Black text on yellow
  Used in the Step4 sheet and its legend, and for the injected row in Step1.
- Decision taken (by the reviewer): text --decided, bold, no background in the screens
  Inside the Step4 sheet: --sheet-decided on --sheet-decided-bg, bold
  Never green, never yellow.
- AI text (what the model writes): normal text color --ink, no background, no underline, in the placeholder view and in answers
  Only study data and decisions are colored.
- Error or impossible value: --block, bold for warnings, dashed border for the trap marker
  Not used for decisions.
- Secondary information: --muted.
- Inactive or locked control: opacity .5, transparent background, --muted text, --ctl border.

## 5
Components and the tokens they use

- Page and shell: background --paper, text --ink.
- Side panel (rail): background --rail, right border --line
  Role label: --muted text, top border --line.
- Brand: --ink.
- Step list: links --muted; hover background --paper; current link background --ink with text --paper.
- Language switch: border --ctl; links --muted; current background --accent with text --on-accent.
- Footer: --muted text, top border --line.
- Step counter: --accent.
- Lede and meta: --muted.
- Card: background --surface, border --line, shadow --line.
- Tables: lines --line, header rule --ink; the highlighted row uses --pending with --on-pending.
- Tiles: top rule --ink, labels --muted.
- Details summary (pill) and plus-minus button: text --ink, underline --ctl, marker background --ink with text --paper.
- Primary button: background --ink, text --paper, border --ink, shadow --accent.
- Secondary button: transparent, text --ink, border --ink.
- Small button: background --accent, text --on-accent, border --accent
  Secondary small: transparent with --accent text
  Locked: see section 4.
- Datum chip and key (.chip.data, .key.data): --real on --real-bg.
- Badge: border and text --accent.
- Language tag: border and text --ink, background --surface.
- Question button: background --surface, text --ink, border --ctl; hover border --ink; selected background --ink, text --paper, shadow --accent.
- Trap marker: dashed border and text --block, background --surface.
- AI text (.aiw): --ink.
- Text field: border --ctl, background --paper, text --ink.
- Live-question bar (Step2): background --rail.
- Role switch (Step3): border --ctl, background --paper; segment text --muted; selected segment --accent with --on-accent.
- Radio button: accent color --accent.
- Warning text (.warn and the Step2 empty-question note): --block, bold.
- Decision line in Step3 cards: --decided, bold.
- NOAEL values in Step4 table: --decided, bold.
- Info box in Step4: background --accent-tint, link --accent, text --muted.
- Highlight (.hl): --pending with --on-pending.
- Sheet and wrap: see section 1, document sheet tokens
  Datum (.dv), decision (.dec).

## 6
How to apply

The CSS variables are defined once per file in the `:root` rule inside the `<style>` of `<helmet>`.
The same `:root` rule is in Main.dc.html, Step1.dc.html, Step2.dc.html, Step3.dc.html and Step4.dc.html.
To change the style, edit the values in this file, then copy the same value into the `:root` rule of every one of the five files.
Keep the variable names exactly as in section 1: they are the token names with two leading hyphens.
No color is written anywhere else in the CSS or in the markup, so changing a variable changes the whole demo.
Do not add a new hex value outside `:root`; add a token here and in `:root` first, then use `var(--name)`.
Typography values (section 2), shape and spacing values (section 3) are written directly in the CSS rules of each file; to change one, change that value in the same rule in all five files.
After editing, publish one file at a time: Main, Step1, Step2, Step3, Step4.
The canvas.json file holds no colors and does not change.
Check that text keeps at least 4.5:1 contrast against its background before publishing.
