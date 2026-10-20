# Cairn

Traceable agentic demo for drug safety science: from a public SEND study to a draft nonclinical summary.
The model picks tools and drafts; code places every number and every quotation, and people make the scientific decisions.
Work follows SDD Lite: master plan, phases with frozen criteria, autonomous execution and adversarial review.

## Always
- Act as the single point of contact; to develop, load `.agents/skills/sdd-lite/SKILL.md`.
- State assumptions and doubts before coding; ask when they change the outcome.
- Do the minimum that meets the criterion: no unrequested features, abstractions or configuration.
- Surgical changes: touch only what the request requires and respect the existing style.
- Work against observable criteria; reproduce failures on the real user path before fixing them.
- Every result carries current evidence; fix clear related defects and log unrelated ones.
- Read only the context you need; broad exploration goes to subagents that return summaries.
- Plain hyphens; in long Markdown, one sentence per line; Python output without special symbols.
- One source per decision; reusable learnings go to the most specific file.
- Everything versioned is written in English; talk to the user in Spanish.
- This file has a 5,000-token cap and is not edited mid-session; a new rule needs evidence and, if it does not fit, another one goes.

## Ask first
- Decisions pending from the user, new costs or dependencies and changes to frozen criteria.
- Publishing beyond the delivery: authorization covers that destination and that content; respect confidentiality and inherited permissions.
  The delivery includes pushing the working branch and a PR to `main` on the project's `origin` remote.

## Never
- Lower criteria or hide failing or unrun tests.
- Merge, approve your own work or write to the default branch; the `.claude/` hooks block it.
- Hand-edit generated files or CHANGELOG.md, or add the agent as a commit co-author.

## Map
- Skills in `.agents/skills/`: flow, routing and delegation in `sdd-lite`; review in `sdd-review`; delivery and No Mistakes in `sdd-delivery`.
- Master plan and phases: `docs/plans/`; standalone changes: `docs/changes/`; templates: `docs/templates/`.
- Guarantees: `.claude/settings.json` and `.claude/hooks/`; checks: `npm run check`.
- Product in `README.md`; method in `docs/como-trabajar.md`. Environment: Windows, Python 3.12 with uv, Node.js 22, Git and GitHub CLI.
- Private PRD in `docs/PRD_Cairn.pdf`, ignored by git: the repo is public, so nothing versioned names companies or people from the PRD.
