# 004 - What the demo shows

Status: in progress

## Contract
Objective and motive: rethink what the demo shows a visitor, not what it does inside.
The user, after testing change 003, still "does not understand half the process": the 7-step menu does not lead to Explore, step 07 is unreachable (clicking returns to 3 or 4), the path is not linear, there is too much hard text and unexplained elements such as traces, and claims like "no data" or "the value is X" mean nothing to a visitor who does not know the study.
The user suggests showing where each value comes from in the study to fill the sentences, instead of asking the visitor to believe or check.
Out of scope: implementation until the user approves the proposal; agent, tools and data internals.
Restrictions / decisions that need the user: the proposal (screens to remove, merge or reorder; text budget; navigation model).
Current authorization and limits: stranger tests and a visual proposal only; no code changes; PR 15 stays open and unmerged.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | To be frozen after the user approves the proposal | |

## Plan
- [ ] Stranger tests: a domain expert persona and a recruiter persona, without project context
- [ ] 360 proposal with screen flow and mockups
- [ ] User decision on the proposal

## Decisions

## Briefs
| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E1 | explorador (opus) | Stranger test, domain expert persona | done | Gets the promise, not the path: three competing numberings, both navigation bugs reproduced; inconsistent values across screens (13 vs 12 quarantined, animal 0031 vs 0032), AUC without units, NOAEL 400 shown before any human decision, judge warning vs "8/8 rules passed" unexplained |
| E3 | ejecutor (opus) | 360 proposal: purpose per screen, linear path, less text, value provenance; visual document with flow and mockups in `.lavish/004/` | done | `.lavish/004/propuesta.html`: landing plus 4 screens (study, ask, you decide, draft) and a folded "Inside" panel; click-to-source provenance; fix-regardless list; 5 owner decisions |
| E2 | explorador (opus) | Stranger test, recruiter persona | done | Gets the headline but not the problem or audience; jargon from step 1; both navigation bugs reproduced: menu 03 goes to /step/3, menu links drop `thread` so /step/5-7 redirect to /step/4 with a new thread and lost progress; step 6 has no link to 7 |

## User decisions
| ID | Question | Options and recommendation | Status | User's answer |
|---|---|---|---|---|
| D1 | Structure | A: landing + 4 screens + folded "Inside" (recommended); B: keep 7 steps, fix navigation, trim text | open | |
| D2 | Provenance | A: highlighted numbers open their table cell or guideline page (recommended); B: model template next to final sentence | open | |
| D3 | Decision screen | A: one key finding visible, NOAEL for females and males, nothing preset (recommended); B: full 11-finding table, no default | open | |
| D4 | Language | A: ES/EN UI, plain findings, draft always English and labelled (recommended); B: translate everything, re-record answers | open | |
| D5 | Technical detail | A: folded "Inside" panel on each screen (recommended); B: separate technical page | open | |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Delivery
The stop-gate `npm run check` times out mid-suite; a full standalone run on 2026-11-03 finished with exit code 0 ("Todos los casos correctos"). The only change so far is this record.
