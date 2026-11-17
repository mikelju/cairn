# 007 - Serve the alternative frontend from the app image

Status: integrated

## Contract
Goal and reason: the user wants to see the new frontend from change 006 on the hosted Lightsail demo; today the image only ships the server-rendered UI, so `frontend-alt/` runs only locally.
Build `frontend-alt/` inside the Docker image and serve it from the same FastAPI process under `/alt/`, next to the existing UI at `/`.
Out of scope: changing the server-rendered UI, the backend endpoints or their behaviour; porting visuals; deploying (the user deploys).
Constraints / decisions that need the user: U1 answered (option 1, serve frontend-alt in the image); mount path `/alt/` decided by the supervisor (keeps `/` unchanged).
Current authorisation and limits: code on branch `cambio-007-serve-frontend-alt` from `origin/main`, worktree `.claude/worktrees/cambio-007-serve-frontend-alt`; push and PR to `main` allowed, no merge, no deploy.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | The Docker image builds `frontend-alt/` in a Node stage and the runtime serves it at `/alt/`; `/` still serves the server-rendered UI | pytest on `/alt/` and `/`; local run of the app with the built bundle |
| C2 | In a browser on the running app, `/alt/` loads with no failed requests and its API calls reach the same process (no Vite proxy) | browser walkthrough of `/alt/` against `uvicorn`, no 4xx/5xx in the network panel |
| C3 | The app still starts and tests pass when the bundle is absent (local dev without a build) | test without the dist folder; `npm run check` green |
| C4 | The `image.yml` workflow builds the image from the branch | `gh workflow run image.yml --ref cambio-007-serve-frontend-alt` succeeds |

## Plan
- [x] 1. Node build stage in `Dockerfile`, Vite `base: '/alt/'`, FastAPI mount at `/alt/` when the bundle exists, tests (C1, C2, C3) - d877f42; test_web.py 121 passed; /alt/#study in browser, no 4xx/5xx
- [x] 2. Image built by the workflow from the branch, push and PR (C4) - run 44074759904 success on 2226728; PR 20

## Decisions
- Mount at `/alt/` rather than replacing `/`: the existing UI, its tests and its links stay untouched.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.
`Result or blocker`: at most 160 characters (commit, command and short result).

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E1 | ejecutor (sonnet) | Increment 1 | done | d877f42; check:puerta 369 passed; test_web.py 121 passed; browser /alt/ ok; full check run by supervisor |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | How to show the new frontend on Lightsail | 1 serve frontend-alt in the image; 2 port its visuals into the current UI (recommended) | answered | "1" |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|
| - | - | - | - | Skipped: small change, user merged PR 20 before review | n/a |

## Delivery
- PR https://github.com/mikelju/cairn/pull/20 merged by the user (481ffab).
- Full `npm run check` on the branch: 928 passed, coverage 97.03%, 1 h 14 min.
- Image from `main`: `image.yml` run 44083241350 success; deployed by the user to Lightsail on 2026-11-17.
- Live check: `/alt/` 200 serving `/alt/assets/*`, `/` 200, `/healthz` ok.
