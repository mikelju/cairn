# Phase 03 - RAG over public guidelines: plan and results

Status: in progress
Spec: `spec.md` (draft)
Base: branch `claude/fase-03-rag-guidance-1a7bcb` from `main` at 4236c59

## Dependency handling
On 2026-10-22 the user decided to start phase 03 now, in parallel with phase 02c (visual design, in progress on another branch).
Relayed words: "phase 03 officially depends on 02c. Start 03 now with everything that does not depend on the visual design: guideline acquisition and pinning, index, reranker, `search_guidance`, QuoteRef, rule 8, E3, E4, recordings for Explore questions. Leave the step 3 UI and the highlighted page for last; build them only after 02c is merged into main and its step 3 mockup is approved, rebasing this branch on main first. Avoid touching shared web templates and CSS (src/cairn/web/) until then, to prevent conflicts with 02c."
- Now part: every criterion marked "now" in the spec (C1-C13, C17); no edit under `src/cairn/web/`.
- Gated part: the step 3 UI, the highlighted page shown in the app and Explore (C14-C16); starts only after 02c is merged into `main` and its step 3 mockup is approved.
- Before the gated part: rebase this branch on `main`, then build to the 02c step 3 mockup.
- The master plan row for phase 03 records the partial start.

## Increments
Written by the plan brief once the spec is approved.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.
Phase 03 brief IDs start at E101 and review rounds at R101, so they never collide with phase 02c.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E101 | ejecutor (Opus) | Draft the phase 03 spec and records | in progress | |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|

## Deviations
| ID | Summary | Affects criteria | Status |
|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Results
Per criterion: command or walkthrough run, observed result and reference to the evidence.
Pending items, limitations and what could not be checked, stated plainly.

## Candidate learnings
Only reusable lessons with a verbatim quote from the session; consolidated when the phase closes.
