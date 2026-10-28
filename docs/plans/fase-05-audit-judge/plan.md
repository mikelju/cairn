# Phase 05 - Audit and judge: plan and results

Status: in progress
Spec: `spec.md` (approved by the user on 2026-10-28, see U1 and U2)
Base: branch `claude/jolly-knuth-g8jdjq` from `main` at 3a92dd4 (phase 04 merged, PR https://github.com/mikelju/cairn/pull/12)

## Records
- User priority, literal (phase 04, still standing): "the project is getting complex. Avoid over-engineering at every step. Do the minimum that meets each criterion; no extra abstractions, configuration, layers or speculative tests; fewer and larger increments when that is simpler; reuse what phases 01-03 already built."
- User request for this phase, literal: "arranca la spec y el plan de la 05. ya sabes, pasame un lavish bien visual para explicarme todo lo que se va a hacer y las decisiones pendientes."
- User instruction of 2026-10-28, literal: "las tareas de ejecución las deben realizar agentes sonnet 5.5".
- User instruction of 2026-10-28, literal: "una vez que el plan esté cerrado, pasa a ejecutar con sonnet 5.5 como hemos dicho antes. finaliza la fase 05 y dame la PR".

## Increments
Each increment leaves the product working and covers specific criteria.
This file is the durable state: a new session resumes from here and from Git.
Every increment closes with `npm run check` green (C1) and a commit on the phase branch.
Only increment 3 calls Bedrock (decision O1): the agent runs `make record-judge` with the `default` AWS profile within the ceiling, and no agent reads or prints credentials or account IDs.
Reuse, not rebuild: `canonical.py` (hash), `web/threads.py` (events and per-thread lock), `workflow.py` (graph), `gateway.py`, `recording.py` and `live.py` (JUDGE_TOOL from the smoke test, `record_draft` as the model for the record command, ceilings), `verify.py` (`RULE_REASONS`), `web/` (shell, components, word cap test), `tests/evals/`.

- [x] 1. Audit chain and SEC-002: an `audit` module with the entry, `append` and the pure `verify_chain`; table in the threads SQLite file; events written in `web/threads.py` inside the thread lock (start, decisions, confirm, verify_final, refusals 403 and 409, approve; the judge entry arrives in increment 2); the single read-only endpoint `GET /api/threads/{id}/audit/verify`; tampering of a copy proven by tests only; the build records its snapshot and gather fails on a mismatch; `docs/security.md` SEC-002 row updated (C2, C3, C4, C5, C6) - verification: `uv run pytest -k "audit or snapshot"`, `tests/evals/test_e6.py` - evidence: `uv run pytest -k "audit or snapshot"` 18 passed (chain links and determinism, 10 tamper cases plus truncated tail with the stated head-hash limit, events of the walkthrough with 403 and 409 refusals and none for 422 or 404, the single GET verify endpoint, snapshot mismatch fails gather); `tests/evals/test_e6.py` 21 passed; `npm run check` exit 0, 572 passed, coverage 97.24% (threshold 85%); SEC-002 row of `docs/security.md` marked fixed. Refusals are chained for 403 and for the verify_final 409 on confirm and approve; the wrong-step 409 changes nothing and adds none
- [x] 2. Judge core and E5, offline: `judge` module (prompt, strict tool reusing `JUDGE_TOOL`, per-sentence call through the gateway, digit-free reason, "not judged" on refusal or truncation, kappa function); the graph node after `verify_final` that never changes `final.ok`; the judge audit entry; the E5 case file (24 cases, 4 kinds) and `tests/evals/test_e5.py` against a hand-written fixture recording under `tests/fixtures/recordings/`; E6 updated for the replay calls (C7, C8 offline part, C1) - verification: `uv run pytest -k "judge or kappa"`, `tests/evals/test_e5.py`, `tests/evals/test_e6.py` - evidence: `uv run pytest -k "judge or kappa"` 23 passed (verdict per sentence, digit reason dropped, refusal/truncation/malformed give not judged, no recording gives not judged, stale on prompt or schema change, judge never changes `final.ok` and approval succeeds with a warning, judge audit entry with counts only, kappa on hand-computed examples, record-judge with a fake client within the ceiling and the 4-decimal spend); `tests/evals/test_e5.py` 4 passed (24 cases built by code, 12 faithful and 12 overstated in 4 kinds, case file equals the builder, kappa 0.83 of the hand-written fixture recordings against the 0.70 threshold); `tests/evals/test_e6.py` 21 passed (judge replay calls counted); `npm run check` exit 0, 595 passed, coverage 96.98%. Judge recordings are one file per sentence (`j-<hash>.json`, keyed by sentence and cited data); `make record-judge` is ready and was not run: 41 sentences (24 E5, draft under the example decisions, the EXAMPLE sentence), ceiling 0.74 USD of 2.00, expected spend about 0.3 USD; result file `data/judge/e5_result.json`
- [ ] 3. Judge recording and calibration (the only Bedrock increment): `make record-judge` records the E5 cases, the example-decisions draft sentences and the example overstated sentence with Sonnet 4.6 in eu-west-1; prints the estimated ceiling first and the real spend after; saves only within the ceiling; writes the kappa result file; at most 2 prompt revisions, then stop and return `necesita decisión` if kappa is under the threshold (C8, C9) - verification: `uv run pytest -k "recordings_metadata or judge_replay"`, `tests/evals/test_e5.py` offline on the real files; `make record-judge` cost output
- [ ] 4. Steps 5 and 6 in the app and demo: judge panel in step 5 with the EXAMPLE row, "not judged" and the 8 checks moved per decision O6; step 6 built (rules table to the 02c mockup, one chain status line from the verify endpoint, the "In production -> external append-only log" note, REAL badge); redirect without a thread; word cap test extended; screenshots at 1440x900 in `evidence/`; offline check extended to steps 5 and 6 (C10, C11, C12, C13) - verification: `uv run pytest -k "step5 or step6 or word_cap"`, browser walkthrough with network off, `make demo-offline-check`
- [ ] 5. Adversarial review: independent review with sdd-review over the phase range, four lenses (correctness, security and data, evidence and tests, scope and maintenance), at most two rounds; confirmed findings fixed with regressions; open items after round 2 go to the user (all criteria) - verification: review table below
- [ ] 6. Delivery: PRD-term grep (needs the git-ignored PRD on the user's machine; stated if not run), push the phase branch and open the PR to `main`, not merged, with the `evals` check green (C1, C13) - verification: `gh pr checks` green, PR URL in Results

## Briefs
Kept by the supervisor. Statuses: in progress, blocked, needs decision, done, failed, cancelled.

| ID | Agent | Brief | Status | Result or blocker |
|---|---|---|---|---|
| E170 | ejecutor (Sonnet) | Draft spec and plan of phase 05 (document mode) | done | f89a342; seven open decisions, all answered A in U1 |
| E171 | ejecutor (Sonnet) | Freeze the spec with the minimal audit chain of U2 | done | 34de8e1; C2, C4, C5, C11 narrowed, numbering kept |
| E172 | ejecutor (Sonnet) | Increment 1: audit chain, verify endpoint, SEC-002 | done | e54e93a; `npm run check` exit 0, 572 passed, 97.24%; refusals chained on confirm as well as approve (supervisor accepts: C3 names refusals without limiting them to approval) |
| E173 | ejecutor (Sonnet) | Increment 2: judge core and E5 offline | in progress | |

## User decisions
Questions the supervisor raises to the user. Statuses: open, answered, deferred; closed with the literal answer.

| ID | Question | Options and recommendation | Status | User answer |
|---|---|---|---|---|
| U1 | Spec open decisions O1-O7 and approval of the spec | See `spec.md`, Open decisions; recommended A for all seven | answered | "O1 (Modelo y gasto del juez): A: Sonnet 4.6, tope 2 USD, perfil default; O2 (Calibración del juez): A: 24 casos generados por código (12 fieles, 12 exagerados, 4 tipos), los revisas antes de grabar, kappa 0,70; O3 (Qué cubre la cadena y dónde vive): A: todos los eventos del flujo, tabla nueva en el mismo SQLite de los hilos; O4 (Cómo se enseña la manipulación): A: el botón edita una copia en memoria; solo API y botones; O5 (Juez en vivo o reproducido): A: solo reproducido; frases sin grabación salen como no juzgadas; O6 (Dónde van las 8 comprobaciones de reglas): A: pasan al paso 6; el paso 5 deja una línea 'Reglas: 8 de 8, ver paso 6'; O7 (SEC-002, huella de los datos): A: cerrarlo en esta fase; spec (Aprobación de la spec): Apruebo la spec de la fase 05 con las respuestas anteriores" |
| U2 | Comments on the decision page (2026-10-28) | Judge card and audit chain card | answered | Judge: "esto me parece bien. es como una revisión neutra del texto en si". Audit chain: "realmente merece la pena tener esto en la demo? lo podemos indicar e incluso podemos hacer una versión minima de esto, pero no creo que sea necesaria esta implementacion completa en una demo". Supervisor reading, applied before freezing the spec: a minimal chain (append and pure verify over the events of O3 in the same SQLite, tampering of a copy shown by tests, one read-only verify endpoint, step 6 shows one status line and an "In production" note); no tamper endpoint or button and no hash trace in the UI, so O4 is reduced to tests; the user can redirect |

## Deviations
| ID | Summary | Affects criteria | Status |
|---|---|---|---|

## Adversarial review
| Round | Backend | Range | Lenses | Findings | Status |
|---|---|---|---|---|---|

## Results
Per criterion: command or walkthrough run, observed result and reference to the evidence.
Pending items, limits and what could not be checked, stated plainly.

## Candidate learnings
Only reusable lessons with a literal quote from the session; consolidated when the phase closes.
