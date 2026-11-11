# 006 - Production-grade alternative frontend

Status: ready locally

## Contract
Goal and reason: the user wants a modern, visual, production-shaped alternative frontend that improves upon the static reference HTML files in `data/cairn-frontend-reference/` and reflects the visual direction of the reference mockups (deep navy/petrol clinical SaaS workspace, cyan/teal and violet accents, visual charts, clean cards, explicit production-preview disabled controls and full end-to-end interactivity).
It must operate exclusively against the existing FastAPI backend and its existing endpoints, so that both the current server-rendered frontend and the new alternative frontend work independently against the same backend process without modifying a single line of `src/cairn/` or `tests/`.
Out of scope: modifying `src/cairn/`, `tests/`, `recordings/`, `data/pds2014/`, `data/guidance/`, root `package.json` or `pyproject.toml`.
Constraints / decisions that need the user: resolved in U1 and U2 (standalone Vite + React + TypeScript app in `frontend-alt/` with reverse proxy to `http://127.0.0.1:8000`, bilingual EN/ES with EN default).
Current authorisation and limits: work on branch `cambio-006-frontend-alternativo` from `origin/main`; keep `src/cairn/` untouched and `npm run check` green.

| ID | Observable criterion | Evidence when verifying |
|---|---|---|
| C1 | Zero backend modifications: `git diff origin/main -- src/ tests/ package.json pyproject.toml` is empty and root `npm run check` passes | `git diff` and `npm run check` output |
| C2 | Standalone Vite + React + TypeScript application in `frontend-alt/` with a clean `npm run build` and a dev/preview proxy forwarding `/api`, `/jobs`, `/study`, `/ask`, `/decide`, `/draft`, `/explore`, `/highlight`, `/highlights`, `/static` and `/healthz` to `http://127.0.0.1:8000` | `npm run build` in `frontend-alt/` exits 0; live browser/HTTP verification against `uv run cairn serve` |
| C3 | Visual design and bilingual UI (EN default, instant EN/ES toggle in header): dark clinical-grade palette (`#06131d` / `#0b2231` surfaces, `#29d7d4` cyan-teal and `#8b65f5` violet accents, light `.doc-sheet` for CTD 2.6.6.3), `IBM Plex Sans` + `IBM Plex Mono`, persistent left navigation, top context bar (active study `PDS2014`, backend health indicator, active thread ID, `A. Author` / `R. Reviewer` role switcher, `EN` / `ES` selector) | Browser screenshots and DOM verification in EN and ES |
| C4 | Explicit production-preview controls (disabled in demo with clear badges/tooltips explaining why): `+ New Analysis` button, SEND/XPT/PDF study drag-and-drop uploader on the Study view, Guideline PDF uploader on the Guidelines view, and `Download PDF` / `Export DOCX` buttons on the Report view | Rendered controls with `disabled` attribute and production-preview explanation |
| C5 | Executive Overview & Study Validation views: Overview shows study summary card, key findings, visual dose-response / NOAEL chart, interactive 5-step architecture pipeline (`Study -> AI Agent -> Deterministic Tools & Rules -> Human Review -> Validated CTD Report`) and live traceable sentence preview; Study & Validation executes live `POST /jobs` (`validate_study`) and `POST /study/run` fault-injection switches (`none`, `negative`, `duplicate`, `dose`), displaying domain counts, quarantine table and visual comparison of naive vs clean `AUCtau` means (`h*ng/mL`) | Live interaction against backend endpoints |
| C6 | Interactive Data Explorer view: calls live `POST /api/tools/study_design`, `incidence` (screened vs full toggle), `body_weight_change` (`F`/`M` and `main`/`main_and_recovery` toggles) and `tk_summary` (`sex`, `dose`, `day` controls), rendering visual dose-response / incidence / body-weight / TK charts alongside structured tables and expandable `Observation` provenance (`obs_id`, `content_sha256`, `snapshot_sha256`, SQL and `source_rows`) | Live tool calls and rendered charts/tables |
| C7 | Guidelines & Ask CAIRN view: displays the 4 pinned guidelines with live `POST /api/tools/search_guidance` search and passage ranking inspector; executes preset recorded questions (`Q1`-`Q8`, `G1`-`G3`, `NS1`, `NS2`) via `POST /ask/run` and optional live queries via `POST /explore/live`, rendering side-by-side Verified Answer vs Raw AI Template (0 digits) and interactive provenance chips (clicking a quote opens a modal/drawer with the highlighted PDF page PNG from `/highlights/{name}` and `/highlight/{sentence_id}`) | Live question execution and highlighted guideline page preview |
| C8 | Scientific Assessment (Human-in-the-Loop) & CTD 2.6.6.3 Report views: manages active workflow thread via `/api/threads`, visualizes incidence per dose and sex, enforces role rules (`A. Author` receives real `403` refusal from backend; `R. Reviewer` records decisions across `Adrenal gland vacuolization` and all `D1`-`D11` slots, loads example decisions and confirms NOAEL), displays deterministic NOAEL and unexamined-tissue flags, renders the CTD 2.6.6.3 draft sheet with interactive provenance chips (`DATA`, `CITATION`, `DECISION`), shows the 8 verifier rules and Sonnet 4.6 Judge sentence verdicts (`supported` / `overstated`), and handles role-gated final approval | End-to-end thread lifecycle (`POST /api/threads` -> `/decisions` -> `/confirm` -> `/approve` + `403` author check) |
| C9 | Audit Trail view: queries live `GET /api/threads/{thread_id}/audit/verify` (`ok`, `count`, `first_broken`), renders an interactive SHA-256 hash-chain diagram (`prev_hash -> canonical payload -> entry_hash`), and tracks the active session's recorded actions and refusals in real time while clearly noting that raw DB row listing is unexposed by the API | Live verification response and rendered chain status |

## Plan
- [x] 1. Scaffold `frontend-alt/` (Vite + React + TypeScript), configure proxy to `http://127.0.0.1:8000` and build the typed API client (`api.ts`) covering all JSON routes (`/healthz`, `/jobs`, `/api/tools/*`, `/api/threads/*`) and HTML fragment parsers (`/study/run`, `/ask/run`, `/explore/live`, `/draft`, `/highlight/*`). — Evidence: `frontend-alt/package.json`, `frontend-alt/vite.config.ts`, `frontend-alt/src/api.ts` compiled cleanly with `tsc -b && vite build`.
- [x] 2. Implement the design system (`cairn-alt.css`), bilingual EN/ES catalogue (`i18n.ts`), persistent sidebar, top context bar (study pill, health status, thread manager, role switcher, language toggle, production-preview `+ New analysis` modal) and reusable visual components (SVG charts, provenance drawer/modal, production-preview disabled dropzones). — Evidence: `frontend-alt/src/cairn-alt.css`, `frontend-alt/src/i18n.ts`, `frontend-alt/src/components/ProvenanceModal.tsx`, `frontend-alt/src/components/ObservationDrawer.tsx`, `frontend-alt/src/App.tsx`.
- [x] 3. Implement the 7 views (`Overview`, `Study & Validation`, `Data Explorer`, `Guidelines & Ask AI`, `Scientific Assessment`, `CTD 2.6.6.3 Report`, `Audit Trail`) connected live to the backend, plus documentation in `frontend-alt/README.md`. — Evidence: `frontend-alt/src/views/*.tsx` and `frontend-alt/README.md`.
- [x] 4. Verify end-to-end against `uv run cairn serve` (all 7 views, live tool calls, thread decisions, NOAEL confirmation, report approval, 403 author refusal, audit verification), run `npm run build` in `frontend-alt/` and `npm run check` at repo root. — Evidence: end-to-end verification against `http://127.0.0.1:4173` proxying to `http://127.0.0.1:8000` (`VERIFICATION_SUCCESS: thread=98df9192 noael_F=20.0 noael_M=200.0 final_ok=True approved_by=R. Reviewer audit_ok=True audit_count=9`), `npm run build` in `frontend-alt/` (exit 0) and root `npm run check` (exit 0).

## Decisions
- The alternative frontend lives in `frontend-alt/` with its own `package.json` so root `package.json` (`npm ls --depth=0`) and `src/cairn/` remain completely untouched.
- Vite configures `server.proxy` and `preview.proxy` for `/api`, `/jobs`, `/study`, `/ask`, `/decide`, `/draft`, `/explore`, `/highlight`, `/highlights`, `/static` and `/healthz` -> `http://127.0.0.1:8000`, avoiding any CORS change in FastAPI.

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E1 | explorador | Inspect `data/cairn-frontend-reference/` and its 7 HTML files and 4 PNG mockups | done | Static templates with unrendered `{{ ... }}` placeholders, empty tables and unused JS stub |
| E2 | explorador | Catalogue all FastAPI JSON and HTML endpoints on `origin/main` and check constraints | done | Full endpoint contract documented; proxy approach keeps `src/cairn/` untouched |
| E3 | ejecutor | Build and verify `frontend-alt/` (Vite + React + TS) connected to all existing Cairn endpoints | done | Built `frontend-alt/` with 7 live views, bilingual EN/ES UI, SVG charts, provenance modals and full E2E proxy verification |

## User decisions
Questions the supervisor raises with the user. Statuses: open, answered, deferred; each closes with the user's literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | How to structure and serve the alternative frontend alongside the current one without altering backend endpoints? | Standalone modern app in its own folder (Vite + React + TypeScript) with proxy to `127.0.0.1:8000` (Recommended) vs Vanilla HTML/JS vs FastAPI sub-mount | answered | "(Recommended) App moderna independiente en carpeta propia (Vite + React + TypeScript) con proxy a 127.0.0.1:8000 (0 cambios en src/cairn/)" |
| U2 | Language of the alternative frontend UI? | Bilingual EN/ES with EN default and header toggle (Recommended) vs EN only vs ES only | answered | "(Recommended) Bilingüe (EN por defecto como en las imágenes de referencia, con selector EN/ES en la cabecera)" |

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Evidence

| Criterion | Command or interaction | Observed result |
|---|---|---|
| C1 | `git diff origin/main -- src/ tests/ package.json pyproject.toml` and root `npm run check` | Empty diff on `src/`, `tests/`, `package.json`, `pyproject.toml`; `npm run check` exits 0 (`ruff`, `mypy`, `pytest` 129 passed, `npm ls`) |
| C2 | `cd frontend-alt && npm run build` + live proxy test (`http://127.0.0.1:4173` -> `http://127.0.0.1:8000`) | `tsc -b && vite build` exits 0 (`dist/assets/index-*.css` 13.50 kB, `dist/assets/index-*.js` 364.74 kB); all 11 proxied prefixes return HTTP 200/201/403 as expected |
| C3 | Inspect `frontend-alt/src/cairn-alt.css`, `frontend-alt/src/i18n.ts`, `frontend-alt/src/App.tsx` and `/static/fonts/IBMPlex*.woff2` over proxy | Deep clinical dark theme (`#06131d`/`#0b2231`), cyan (`#29d7d4`) & violet (`#8b65f5`) accents, light `.doc-sheet` (`#f8fafb`), `IBM Plex Sans` + `IBM Plex Mono` served via `/static/fonts/*` (HTTP 200), persistent left sidebar and top context bar with `EN` default and instant `EN`/`ES` switcher |
| C4 | Inspect disabled production-preview controls in `App.tsx`, `StudyView.tsx`, `GuidelinesAskView.tsx`, `ReportView.tsx` | `+ New Analysis (PROD PREVIEW)` modal, disabled SEND `.xpt`/PDF uploader dropzone on Study view, disabled `+ Upload Guideline PDF (PROD PREVIEW)` button on Guidelines view, and disabled `Download PDF` / `Export eCTD DOCX` buttons on Report view |
| C5 | Live `OverviewView` and `StudyView` against `POST /jobs` (`validate_study`) and `POST /study/run?lang=en` (`switch=none\|negative\|duplicate\|dose`) | Overview renders 4 KPIs, SVG dose-response curve, live NOAEL cards, 5-stage interactive pipeline and `Q3` traceable sentence; Study view renders `job_id`, `inputs_sha256`, 8 SEND domain counts (`0` schema failures), 12 quarantined rows, and `AUCtau` mean comparison (`2,821` vs `15,956 h*ng/mL`) across all 4 fault switches |
| C6 | Live `DataExplorerView` against `POST /api/tools/study_design`, `incidence` (`screen=true` & `false`), `body_weight_change` (`F`/`M`, `main`/`main_and_recovery`), `tk_summary` (`M`, `20`, `1`) | Screened (9 findings) and full incidence tables with dose bars, Day-29 body weight SVG chart enforcing `"lower than control"`, TK `AUCtau` comparison (`contains_quarantined=true`), and expandable `ObservationDrawer` showing `obs_id`, `content_sha256`, `snapshot_sha256`, fixed DuckDB SQL and `source_rows` |
| C7 | Live `GuidelinesAskView` against `POST /api/tools/search_guidance`, `POST /ask/run` (`Q1`–`Q8`, `G1`–`G3`, `NS1`, `NS2`), `GET /highlight/FDA-IV-01.s2`, `GET /highlights/FDA-IV-01.s2@p8.png`, `POST /explore/live` | Displays 4 pinned guidelines with SHA-256 hashes, live hybrid retrieval ranking table (`rerank_score` vs `threshold`), side-by-side Verified Answer vs Raw AI Skeleton (0 digits), and modal displaying `/highlights/FDA-IV-01.s2@p8.png` (HTTP 200 PNG) |
| C8 | Live `AssessmentView` and `ReportView` against `/api/threads` lifecycle + `/draft` | `POST /api/threads` (201) -> `A. Author` `/decisions` (403) -> `R. Reviewer` `/decisions` D1–D11 (200, `noael.F=20.0`, `noael.M=200.0` with 2 incomplete-exam flags) -> `A. Author` `/confirm` (403) -> `R. Reviewer` `/confirm` (200, `waiting="await_approval"`, `final.ok=true`) -> `/draft` `.doc-sheet` with interactive chips, 8 rules, Sonnet 4.6 Judge & MCP/REST parity -> `A. Author` `/approve` (403) -> `R. Reviewer` `/approve` (200, `approved_by="R. Reviewer"`) |
| C9 | Live `AuditView` against `GET /api/threads/{thread_id}/audit/verify` | Returns `{"ok": true, "count": 9, "first_broken": null}` after the full lifecycle including 3 chained `403` refusals; renders visual SHA-256 block chain diagram and real-time session event log |

## Delivery
- Branch: `cambio-006-frontend-alternativo`
- Scope: `frontend-alt/**` and `docs/changes/006-alternative-frontend.md` (zero changes to `src/`, `tests/`, root `package.json` or `pyproject.toml`).
