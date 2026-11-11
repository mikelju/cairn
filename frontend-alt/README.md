# CAIRN — Production-Grade Alternative Frontend (`frontend-alt/`)

A modern, clinical-grade workspace frontend for **Cairn** built with **Vite + React + TypeScript**.
It operates **100% against the existing FastAPI backend (`127.0.0.1:8000`)** without modifying a single line of `src/cairn/` or `tests/`, allowing both the server-rendered Jinja/HTMX interface and this rich interactive application to run concurrently against the same backend process.

## Quick Start

1. **Start the existing FastAPI backend** from the repository root:
   ```bash
   uv run cairn serve
   ```
   The backend listens on `http://127.0.0.1:8000`.

2. **Start the alternative frontend** from `frontend-alt/`:
   ```bash
   cd frontend-alt
   npm install
   npm run dev
   ```
   Open `http://127.0.0.1:5173`. Vite proxies all backend routes (`/api`, `/jobs`, `/study`, `/ask`, `/decide`, `/draft`, `/explore`, `/highlight`, `/highlights`, `/static`, `/healthz`) directly to `http://127.0.0.1:8000`.

3. **Production build & preview**:
   ```bash
   cd frontend-alt
   npm run build
   npm run preview
   ```

## Workspace Views & Live Backend Integration

| View | Purpose | Live FastAPI Endpoints Used |
|---|---|---|
| **1. Executive Overview** (`#overview`) | Study KPIs, multi-series SVG dose-response & NOAEL chart, live workflow status, interactive 5-stage architecture stepper, and live zero-AI-digit sentence preview | `GET /healthz`, `POST /api/threads`, `GET /api/threads/{id}`, `GET /api/threads/{id}/audit/verify`, `POST /ask/run` (`Q3`) |
| **2. Study & Validation** (`#study`) | Production-preview SEND uploader (`disabled`), live study design cohorts, Pandera domain validation report, 4 fault-injection switches (`none`, `negative`, `duplicate`, `dose`), and quarantine `AUCtau` impact chart | `POST /jobs`, `GET /jobs/{id}`, `POST /api/tools/study_design`, `POST /study/run` |
| **3. Data Explorer** (`#data`) | Interactive histopathology incidence (`screen=true/false`), Day-29 body weight (`F`/`M`, `main`/`main_and_recovery`), and toxicokinetics `AUCtau` (`sex`, `dose`, `day`) with SVG charts and expandable `Observation` SQL/provenance drawers | `POST /api/tools/incidence`, `POST /api/tools/body_weight_change`, `POST /api/tools/tk_summary` |
| **4. Guidelines & Ask AI** (`#guidelines`) | 4 SHA-256 pinned FDA/ICH guidelines, live `search_guidance` reranker inspector, 13 recorded study/guideline/guardrail questions (`Q1`–`Q8`, `G1`–`G3`, `NS1`, `NS2`) with side-by-side Verified vs. Raw AI template, clickable PDF page highlights, and optional `/explore/live` | `POST /api/tools/search_guidance`, `POST /ask/run`, `GET /highlight/{sentence_id}`, `GET /highlights/{name}`, `POST /explore/live` |
| **5. Scientific Assessment** (`#assessment`) | Role-gated Human-in-the-Loop adversity evaluation (`A. Author` 403 refusal test vs. `R. Reviewer` privileges), `GLAND, ADRENAL Vacuolization` cards + full `D1`–`D11` slot editor, deterministic NOAEL derivation, incomplete-examination flags, and NOAEL confirmation | `GET /api/threads/{id}`, `POST /api/threads/{id}/decisions`, `POST /api/threads/{id}/confirm` |
| **6. CTD 2.6.6.3 Report** (`#report`) | Regulatory `.doc-sheet` with clickable `DATA`, `CITATION`, and `DECISION` chips, production-preview PDF/DOCX export controls (`disabled`), 8 deterministic verifier rules, calibrated Sonnet 4.6 Judge verdicts, MCP vs. REST parity check, and role-gated electronic sign-off | `GET /draft?thread={id}&actor={actor}`, `POST /api/threads/{id}/approve` |
| **7. Audit Trail** (`#audit`) | Live cryptographic SHA-256 chain verification (`ok`, `count`, `first_broken`), visual hash-linking diagram, and real-time session event ledger | `GET /api/threads/{id}/audit/verify` |

## Bilingual Support (`EN` / `ES`)

The top context bar includes an instant `EN` | `ES` language selector (`EN` by default, matching the clinical SaaS design references).
