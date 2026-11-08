# 005 - Final README

Status: ready locally

## Contract
Goal and reason: the project is finished and the README is its public face (the repository is public).
The user asked for a README that matches the final project and reads at a glance: flow diagrams that show how it works, no promises of things that were not done.
The user then said there is no video, so that reference goes.
Out of scope: application code, `CHANGELOG.md` (generated), any generated file, the private PRD.
Constraints / decisions that need the user: none open.
Current authorisation and limits: standalone change in its own worktree; commit, push of the branch and a PR to `main` on `origin`; no merge.
The access code, company or person names from the private PRD and the AWS account ID never appear.

Frozen criterion that this change overrides, by explicit user instruction: phase 06 C12 (and decision O6) say the README "fits one screen" and links the video.
The user asked for a visual README with workflow diagrams and no video, so the README is longer than one screen and has no video link.
ADR-002, named in the same criterion, was never written; the old README pointed to `docs/adr/` for "workflows" decisions that are not there, and the new one does not claim it.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | The README has no reference to a video and no placeholder (`VIDEO_URL`) | `git grep -i "video\|VIDEO_URL" -- README.md` has no matches |
| C2 | Every claim in the README is supported by the repository | Table of claims below |
| C3 | The README has Mermaid diagrams for the end-to-end flow, who does what, the four steps and the AWS deployment, with valid syntax | Parsed with Mermaid 11.4.0 (see Evidence) |
| C4 | The README links the deployed demo, says how to run it locally and how to run the checks, and links `docs/como-trabajar.md` | Read the file; links resolve to existing paths |
| C5 | No access code, PRD company or person names, or AWS account ID in the repository | `git grep` has no matches |
| C6 | `npm run check` is green | Command output |

## Plan
- [x] Review the old README against the repository and rewrite it
- [x] Validate the diagrams
- [x] Checks, commit, push and PR

## Decisions
Mermaid is used (GitHub renders it in the README); no image files and no new dependency or tool in the repository.
The validation used a throwaway install of Mermaid outside the repository.
The README has four diagrams: end-to-end flow, who does what, the four demo steps and deployment.
The first two carry the explanation; the other two are short strips.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E2 | ejecutor | Review the README against the project, rewrite it with diagrams, no video; record the change and open the PR | in progress | See Evidence and Delivery |

## User decisions
| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | Is there a video to link? | Link it or remove the reference | answered | "no hay video. quita esa referencia" (via supervisor) |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence
Removed or corrected against the old README:
- Removed "Video walkthrough: VIDEO_URL (pending ...)": there is no video.
- Removed the command list as the main body; kept only the commands that exist in the `Makefile`, now as a table.
- Dropped the pointer to `docs/adr/` for "workflows" decisions: only ADR-001 (Bedrock) exists; there is no ADR-002.
- Condensed the long `make deploy` paragraph (environment kept on redeploy, `CAIRN_ACCESS_CODE` and `CAIRN_LIVE_CAP_USD` overrides, dry run); it is covered by `docs/production.md` and the `Makefile`.
- Kept: `make demo`, `make demo-offline-check`, `make live`, `make deploy`, the other record targets and `docs/production.md`, since the `Makefile` still has them.

Claims in the new README and where the repository supports them:

| Claim | Source |
|---|---|
| Public SEND study PhUSE PDS2014, fictitious compound | `data/pds2014/LICENSE.md`, `data/manifest.json`, `docs/plans/0_plan_maestro.md` |
| Four public guidelines | `data/guidelines/manifest.json` |
| Bad rows go to quarantine, never corrected | `src/cairn/validate.py` module docstring |
| Tools with numbers and source rows; guideline passages with page | `src/cairn/tools.py` `REGISTRY`, `search_guidance` |
| Model picks tools and writes prose without digits; 8 rules | `src/cairn/loop.py`, `src/cairn/verify.py` `RULE_REASONS` |
| Judge warns, never blocks | `src/cairn/judge.py` docstring |
| Reviewer decides and signs; the author cannot sign their own draft | `tests/evals/test_e6.py::test_api_403_author_cannot_approve_own_draft`, `workflows/nonclinical-summary.yaml` pauses |
| People decide relatedness and adversity; code derives the NOAEL | `src/cairn/decisions.py` module docstring and `Decision` |
| Hash-chained audit trail | `src/cairn/audit.py` |
| Four screens: study, ask, decide, draft | `docs/changes/004-what-the-demo-shows.md` C2, `src/cairn/web/templates/` |
| Replays Bedrock recordings; offline | `recordings/`, `Makefile` `demo`, `demo-offline-check` |
| One live question, access code, 2 USD per UTC day cap | `src/cairn/web/explore_live.py`, `docs/production.md` |
| Spanish and English interface, draft in English | `docs/changes/004-what-the-demo-shows.md` C12 |
| Lightsail container in `eu-west-1`, Bedrock in `eu-west-1` | `Makefile` `deploy`, `docs/adr/ADR-001-bedrock.md` |
| REST `POST /api/tools/{name}`, OpenAPI `/docs`, MCP `/mcp` | `src/cairn/app.py`; `/docs` answers 200 on the deployed demo |
| `data-quality-memo` runs from configuration | `workflows/data-quality-memo.yaml` |
| CI runs checks on every push; nothing deploys from CI | `.github/workflows/ci.yml`, `image.yml` (manual build only) |
| Apache-2.0 | `LICENSE` |
| Deployed demo link | `GET /study` and `/healthz` answered 200 on 2026-11-08 |

`npm run check` exit 0: 926 passed, coverage 97 %, hook suite "Todos los casos correctos".

Diagram validation: the four blocks were parsed with `mermaid.parse` (Mermaid 11.4.0 under jsdom, installed outside the repository); all four returned `flowchart-v2`.
Parsing proves the syntax; the layout was not rendered in a browser here, so the rendering on GitHub is the last check.

## Delivery
Branch `cambio-005-readme-final`, PR to `main`; see the PR for the CI result.
