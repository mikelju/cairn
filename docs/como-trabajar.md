# How to work with SDD Lite

Guide to the working method, for the person who leads the project.
The README describes the product; this file describes how to work with the agents, and it is the same in every project.

## Division of roles

You decide what gets built and against which criteria.
You talk to a single agent, the supervisor: it does not write code, it briefs other agents, judges their evidence and brings you results and decisions.
- `ejecutor`: implements, fixes, drafts specs and plans and delivers the branch or the PR.
- `explorador`: investigates and reproduces failures without touching anything.
- `revisor`: looks for how the work fails, without fixing it.
You never talk to them or hand out work to them.
You approve at three points: the master plan, each phase's spec and the PR.
In between, the supervisor and its agents work on their own and only interrupt you for decisions that are yours.

## Starting a session

Cairn is already set up: open the repository root in VS Code and start a new Claude Code session.
On start, the supervisor receives the bearing: branch, open work, unclosed briefs and decisions it owes you.
Deliveries arrive as PRs to `main` on the `origin` remote.

## The four commands

| Command | When | What you get |
|---|---|---|
| `/iniciar <idea>` | Once, at the start | Master plan with the phases, to approve |
| `/planear <what>` | Before each phase or a standalone change | Phase spec or change document, to approve |
| `/ejecutar <what>` | With the spec approved | Implementation, adversarial review and PR |
| `/verificar <what>` | When you want a second opinion | Findings only: it neither fixes nor publishes |

The skills in `.agents/skills/` are not called by hand: each command loads the ones it needs.
The commands are shortcuts; asking in natural language works the same.

## The cycle of a phase

1. `/planear fase 01`: the supervisor briefs `docs/plans/fase-01-name/spec.md` with acceptance criteria and open questions.
   You answer the questions and say "spec approved"; from then on the criteria are frozen.
2. `/ejecutar fase 01`: the supervisor creates the branch and briefs the increments; the agents implement, pass the checks,
   go through adversarial review, fix what is confirmed and open the PR to `main` with evidence per criterion.
   It only interrupts you for a deviation, a new cost or a decision of yours.
3. You review the PR on GitHub.
   If something must change, say so in the chat ("in the PR, criterion C3 does not convince me because...") and it updates the PR.
4. You merge; no agent can merge or approve.
   Then, locally: `git switch main` and `git pull`.
5. When the phase closes it proposes at most five learnings for its rules; you accept or discard them.
6. Next phase: `/planear fase 02`.

## Common situations

- Small bug or tweak: `/planear fix X` and then `/ejecutar cambio NNN`; if it is trivial, "fix X" is enough.
- Resuming another day: "continue phase 02" in a new session; the state lives in `plan.md` and in Git, not in the conversation.
  On start the supervisor receives the bearing: open work, unclosed briefs and decisions it owes you.
- Seeing what is going on: ask "how is it going?"; briefs and decisions are in the tables of their plan or change.
- Changing an approved criterion: the supervisor opens a deviation in the phase folder and proposes it to you; it does not change it alone.
- Reviewing something without touching it: `/verificar fase 02` or `/verificar rama X`.
- Security audit, for example before publishing or deploying: `/verificar seguridad completo`.
  It gives findings by severity and touches nothing; the possible scopes are in `.agents/skills/sdd-delivery/SKILL.md`.

## Adopting SDD Lite in an existing repository of your own

To continue with the full method in a project of yours that started without it, for example with the old SDD-WAT.
Unlike contribution mode, the method stays in the repo, versioned.

1. With a clean tree, open the repo root and type `/sdd-adoptar`.
   It creates the `adoptar-sdd-lite` branch, copies what does not clash and merges `.claude/settings.json` and `.gitignore`.
   It creates `.sdd-lite.json`, with the check command, the format command and the default branch.
2. The agent surveys the repo and merges your `CLAUDE.md` into `AGENTS.md`, keeping what is specific to the project.
   It also replaces the old flow: it retires the process commands and keeps the domain skills, `workflows/` and `tools/`.
   And it writes a master plan that starts with phase 00, "inherited state".
3. It proposes the check and format commands, and everything arrives as a PR with a table of what is retired and where each thing goes.
4. After merging, in a new session: `/planear fase 01` and the normal cycle.

## Contributing to an existing repository (contribution mode)

To work with this method in a repo that was not created with SDD Lite, such as a fork or a project already under way, in any language.
Nothing is copied into the repo: the skills and hooks run from the template, and on exit the repo is left as it was.

1. Open the repo root (not a subfolder) in VS Code and type `/sdd-entrar`.
   It activates the hooks and creates three local things Git does not see: `.sdd/`, `CLAUDE.local.md` and `.claude/settings.local.json`.
   Their configuration and the snapshot of the previous state go inside `.git/`, where no branch of the repo can touch them.
   If it does not know the repo's default branch, it asks you.
   Subagents survey the repo and leave a map in `.sdd/mapa.md`, and it proposes the command to check the work.
2. `/sdd-planear <your contribution>`: contract in `.sdd/cambio.md` for you to approve.
3. `/sdd-ejecutar`: branch from the project's base, implementation with its conventions, adversarial review and push to your fork.
   It shows you the PR text and only opens it, as a draft, when you confirm; Claude Code asks you too.
4. `/sdd-verificar` asks for a review without touching anything; `/sdd-verificar seguridad`, for a security audit.
5. `/sdd-salir` when you finish: it archives your documents in `~/.sdd-lite/archivo/<repo>/<date>/`,
   restores the repo byte for byte and checks that no trace is left, in the commits either.

The repo's rules (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`) take precedence over the method's.
Do not move the template or switch its branch with a contribution open: the hooks run from it.
If that already happened, exit from a terminal: `node "<new path>/scripts/salir.mjs"` at the repo root.
The `/sdd-*` and `/nuevo-proyecto` commands are installed with `node "<path to SDD-lite>/scripts/instalar-comandos.mjs"`.
Run it again if you move the template.

## Lavish in any repository

For the agent to ask you for decisions or comments in the browser in a repo without SDD Lite, without adopting it or entering contribution mode.
Type `/sdd-lavish` followed by what you want to decide or review.
The pages and their state are saved in `~/.sdd-lite/lavish/`, one folder per repo, outside it: the repo is left as it was.
Lavish is for decisions and comments; reports go in the chat.

## Where everything is

| What | Where |
|---|---|
| Master plan | `docs/plans/0_plan_maestro.md` |
| Spec, plan and results of a phase | `docs/plans/fase-NN-name/` |
| Standalone changes | `docs/changes/NNN-name.md` |
| Rules the agent always loads | `AGENTS.md` |
| Procedures of the supervisor and the agents | `.agents/skills/` |
| Agent definitions | `.claude/agents/` |
| Open or deferred security findings | `docs/security.md` (created with the first one) |
| Automatic blocks (push to `main`, secrets, merging) | `.claude/settings.json` and `.claude/hooks/` |

## Tips

- One phase per session: the context stays clean, it is cheaper and the agents work better.
- Observable criteria in the spec ("the report flags invoices with an overrun above 5 %"), not wishes ("it should work well").
- If an agent gets stuck, the supervisor corrects or relaunches it; if that fails, it explains the decision it needs from you.
- To change something yourself with Claude without the supervisor, start the session with the variable `SDD_SUPERVISOR_LIBRE=1`.
- Nobody writes directly to `main`; everything goes through a PR.
