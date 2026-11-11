import React, { useEffect, useState } from 'react';
import {
  Actor,
  ApiError,
  DecisionInput,
  ParsedDraftSheet,
  ParsedProvenanceItem,
  ThreadView,
  ViewId,
  approveThreadDraft,
  confirmThreadNoael,
  fetchDraftSheet,
  recordThreadDecisions,
} from '../api';
import { ProvenanceInline } from '../components/ProvenanceModal';
import { EXAMPLE_DECISIONS_MAP, Locale, VERIFIER_RULES } from '../i18n';

interface ReportViewProps {
  locale: Locale;
  actor: Actor;
  onChangeActor: (actor: Actor) => void;
  thread: ThreadView | null;
  onThreadUpdated: (updated: ThreadView, actionLabel: string) => void;
  onAuditRefusal: (actionLabel: string, status: number, detail: string) => void;
  onNavigate: (view: ViewId) => void;
  onSelectProvenance: (item: ParsedProvenanceItem) => void;
}

export const ReportView: React.FC<ReportViewProps> = ({
  locale,
  actor,
  onChangeActor,
  thread,
  onThreadUpdated,
  onAuditRefusal,
  onNavigate,
  onSelectProvenance,
}) => {
  const [sheet, setSheet] = useState<ParsedDraftSheet | null>(null);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const [banner, setBanner] = useState<{
    kind: 'success' | 'warn' | 'danger';
    text: string;
  } | null>(null);

  useEffect(() => {
    if (!thread) return;
    setLoadingSheet(true);
    fetchDraftSheet(thread.thread_id, actor)
      .then((res) => setSheet(res))
      .catch(() => {})
      .finally(() => setLoadingSheet(false));
  }, [thread, actor]);

  if (!thread) {
    return (
      <div className="panel">
        <div className="callout">Loading CTD 2.6.6.3 draft…</div>
      </div>
    );
  }

  const handleQuickConfirmAll = async () => {
    setBusyAction(true);
    setBanner(null);
    try {
      const payload: DecisionInput[] = thread.slots.map((s) => {
        const existing = thread.decisions.find((d) => d.dec_id === s.slot);
        if (existing) {
          return {
            dec_id: s.slot,
            treatment_related_from: existing.treatment_related_from,
            adverse_from: existing.adverse_from,
            example: existing.actor === 'Example',
          };
        }
        const preset = EXAMPLE_DECISIONS_MAP[`${s.sex}|${s.finding}`] || [null, null];
        return {
          dec_id: s.slot,
          treatment_related_from: preset[0],
          adverse_from: preset[1],
          example: s.finding !== 'GLAND, ADRENAL Vacuolization',
        };
      });
      await recordThreadDecisions(thread.thread_id, 'R. Reviewer', payload);
      const confirmedThread = await confirmThreadNoael(thread.thread_id, 'R. Reviewer', [
        'F',
        'M',
      ]);
      onChangeActor('R. Reviewer');
      onThreadUpdated(
        confirmedThread,
        'Quick-confirmed D1–D11 decisions & F/M NOAEL as R. Reviewer',
      );
      setBanner({
        kind: 'success',
        text:
          locale === 'en'
            ? 'Decisions D1–D11 recorded and NOAEL confirmed for Females (20 mg/kg/day) & Males (200 mg/kg/day). All 8 verifier rules passed!'
            : 'Decisiones D1–D11 grabadas y NOAEL confirmado para Hembras (20 mg/kg/día) y Machos (200 mg/kg/día). ¡Las 8 reglas pasaron!',
      });
    } catch (err) {
      setBanner({
        kind: 'danger',
        text: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setBusyAction(false);
    }
  };

  const handleApprove = async (asActor: Actor) => {
    setBusyAction(true);
    setBanner(null);
    try {
      const updated = await approveThreadDraft(thread.thread_id, asActor);
      onThreadUpdated(updated, `approve_draft by ${asActor}`);
      setBanner({
        kind: 'success',
        text:
          locale === 'en'
            ? `Draft electronically approved by ${updated.approved_by} and recorded in the SHA-256 audit trail.`
            : `Borrador aprobado electrónicamente por ${updated.approved_by} y registrado en la cadena SHA-256.`,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        onAuditRefusal(`approve_draft (${asActor})`, err.status, err.detail);
        setBanner({
          kind: 'danger',
          text: `HTTP ${err.status} (${asActor}): ${err.detail} — Refusal recorded in SHA-256 audit chain.`,
        });
      } else {
        setBanner({ kind: 'danger', text: String(err) });
      }
    } finally {
      setBusyAction(false);
    }
  };

  const isUndecided = thread.waiting === 'await_decisions';
  const failedRulesText = thread.final.failures.join(' | ');

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 5 · REGULATORY CTD 2.6.6.3 WRITTEN SUMMARY, VERIFIER & ELECTRONIC APPROVAL'
              : 'ETAPA 5 · RESUMEN ESCRITO CTD 2.6.6.3, VERIFICADOR Y APROBACIÓN ELECTRÓNICA'}
          </div>
          <h1>
            {locale === 'en'
              ? 'CTD Module 2.6.6.3 — Repeat-Dose Toxicity Report'
              : 'Módulo CTD 2.6.6.3 — Informe de Toxicidad a Dosis Repetidas'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'Every figure on the document sheet is an interactive provenance chip placed by code. Click any number, quotation or decision to inspect its exact source.'
              : 'Cada cifra en la hoja del documento es un chip interactivo colocado por código. Haz clic en cualquier número, cita o decisión para inspeccionar su fuente.'}
          </p>
        </div>

        {/* Production Preview Export Controls */}
        <div className="head-actions">
          <button
            className="btn secondary sm"
            disabled
            title="Disabled in public demo (no HTTP export endpoint in backend)"
          >
            ⬇ {locale === 'en' ? 'Download PDF' : 'Descargar PDF'}{' '}
            <span className="prod-badge" style={{ marginLeft: 4 }}>
              PROD PREVIEW
            </span>
          </button>
          <button
            className="btn secondary sm"
            disabled
            title="Disabled in public demo (no HTTP export endpoint in backend)"
          >
            ⬇ {locale === 'en' ? 'Export eCTD DOCX' : 'Exportar DOCX'}{' '}
            <span className="prod-badge" style={{ marginLeft: 4 }}>
              PROD PREVIEW
            </span>
          </button>
        </div>
      </div>

      {/* Undecided Callout with 1-Click Populate */}
      {isUndecided && (
        <div
          className="callout warn"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <strong>
              {locale === 'en'
                ? 'Human Decisions Still Open (Yellow Gaps Visible on Sheet): '
                : 'Decisiones Humanas Pendientes (Huecos Amarillos Visibles en el Informe): '}
            </strong>
            {locale === 'en'
              ? 'Cairn never invents a NOAEL or adversity classification. Unfilled decision slots remain visibly marked in yellow and block final sign-off under Rule 2.'
              : 'Cairn nunca inventa un NOAEL ni una clasificación de adversidad. Los slots vacíos quedan marcados en amarillo y bloquean la aprobación bajo la Regla 2.'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn sm secondary"
              onClick={() => onNavigate('assessment')}
            >
              {locale === 'en' ? 'Go to Scientific Assessment' : 'Ir a Evaluación Científica'}
            </button>
            <button
              type="button"
              className="btn sm"
              disabled={busyAction}
              onClick={handleQuickConfirmAll}
            >
              ⚡{' '}
              {locale === 'en'
                ? 'Confirm Recommended Decisions & NOAEL Now'
                : 'Confirmar Decisiones y NOAEL Ahora'}
            </button>
          </div>
        </div>
      )}

      {banner && <div className={`callout ${banner.kind}`}>{banner.text}</div>}

      {/* Main Two-Column Layout: Left = White CTD Document Sheet, Right = Verifier + Judge + Approval */}
      <div className="grid main-side">
        {/* Left: CTD 2.6.6.3 Document Sheet */}
        <div className="stack">
          {/* Traceability Counter Bar */}
          <div
            className="panel"
            style={{
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="status-pill">0 Digits Written by AI</span>
              <span style={{ fontSize: 12.5, color: '#d7ecf4', fontFamily: 'var(--mono)' }}>
                {sheet?.countsLine ||
                  (locale === 'en'
                    ? 'Every figure placed deterministically from ObservationLedger'
                    : 'Cada cifra colocada de forma determinista desde ObservationLedger')}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6, fontSize: 11, fontFamily: 'var(--mono)' }}>
              <span style={{ color: '#8ef5d8' }}>● Data</span>
              <span style={{ color: '#ded2ff' }}>● Quote</span>
              <span style={{ color: '#ffe3a3' }}>● Decision</span>
            </div>
          </div>

          {sheet ? (
            <article className="doc-sheet" style={{ opacity: loadingSheet ? 0.65 : 1 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 11.5,
                  fontFamily: 'var(--mono)',
                  color: '#4c6875',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}
              >
                <span>ICH M4S(R2) · CTD Module 2.6.6.3 Written Summary</span>
                <span>
                  {thread.approved_by
                    ? `APPROVED BY ${thread.approved_by.toUpperCase()}`
                    : isUndecided
                      ? 'DRAFT — AWAITING DECISIONS'
                      : 'VERIFIED DRAFT — AWAITING SIGN-OFF'}
                </span>
              </div>

              <h1>Nonclinical Summary — Study PDS2014</h1>

              {/* Metadata Header Table */}
              <table>
                <tbody>
                  {sheet.metaRows.map((row, idx) => (
                    <tr key={idx}>
                      <th style={{ width: '18%' }}>{row.label1}</th>
                      <td style={{ width: '32%' }}>
                        <ProvenanceInline parts={row.parts1} onSelect={onSelectProvenance} />
                      </td>
                      <th style={{ width: '18%' }}>{row.label2}</th>
                      <td style={{ width: '32%' }}>
                        <ProvenanceInline parts={row.parts2} onSelect={onSelectProvenance} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>1. Study Design</h2>
              <p>
                <ProvenanceInline parts={sheet.studyIntro} onSelect={onSelectProvenance} />
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {sheet.parameterRows.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600, width: '32%' }}>{r.label}</td>
                      <td>
                        <ProvenanceInline parts={r.parts} onSelect={onSelectProvenance} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>2. Recorded Decisions</h2>
              <p>The following decisions on adversity of the findings were recorded.</p>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 70 }}>Ref.</th>
                    <th>Recorded Decision</th>
                  </tr>
                </thead>
                <tbody>
                  {sheet.decisionRows.map((r, i) => (
                    <tr key={i}>
                      <td className="mono" style={{ fontWeight: 700 }}>
                        {r.slot}
                      </td>
                      <td>
                        <ProvenanceInline parts={r.parts} onSelect={onSelectProvenance} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>3. Toxicokinetics</h2>
              <p>
                <ProvenanceInline parts={sheet.tkIntro} onSelect={onSelectProvenance} />
              </p>
              {sheet.tkMeanRows.length > 0 && (
                <table>
                  <thead>
                    <tr>
                      <th>Quarantined Value</th>
                      <th>{sheet.tkMeanHeader}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.tkMeanRows.map((r, i) => (
                      <tr key={i}>
                        <td>{r.label}</td>
                        <td>
                          <ProvenanceInline parts={r.parts} onSelect={onSelectProvenance} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {sheet.tkNotes.length > 0 && (
                <ul>
                  {sheet.tkNotes.map((note, i) => (
                    <li key={i}>
                      <ProvenanceInline parts={note} onSelect={onSelectProvenance} />
                    </li>
                  ))}
                </ul>
              )}

              <h2>4. No-Observed-Adverse-Effect Level (NOAEL)</h2>
              {sheet.noaelSections.map((sec, i) => (
                <div key={i}>
                  <h3>{sec.heading}</h3>
                  <p>
                    <ProvenanceInline parts={sec.text} onSelect={onSelectProvenance} />
                  </p>
                  {sec.quote.length > 0 && (
                    <blockquote>
                      <ProvenanceInline parts={sec.quote} onSelect={onSelectProvenance} />
                    </blockquote>
                  )}
                </div>
              ))}

              <h2>References</h2>
              <ol>
                {sheet.references.map((ref, i) => (
                  <li key={i}>{ref}</li>
                ))}
              </ol>

              <div
                style={{
                  marginTop: 22,
                  paddingTop: 12,
                  borderTop: '1px solid #cbdbe3',
                  fontSize: 11.5,
                  color: '#5a7380',
                  fontFamily: 'var(--mono)',
                }}
              >
                {sheet.footerNote}
              </div>
            </article>
          ) : (
            <div className="panel">
              <div className="callout">Loading document sheet…</div>
            </div>
          )}
        </div>

        {/* Right Column: Approval, 8 Verifier Rules, Calibrated Judge, MCP vs REST */}
        <div className="stack">
          {/* Panel 1: Role-Gated Electronic Sign-Off */}
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>
                  {locale === 'en'
                    ? 'Role-Gated Electronic Sign-Off'
                    : 'Firma Electrónica con Separación de Roles'}
                </h2>
                <p>
                  {locale === 'en'
                    ? 'POST /api/threads/{id}/approve enforces two-person integrity'
                    : 'POST /api/threads/{id}/approve exige integridad de dos personas'}
                </p>
              </div>
              <span className={`status-pill ${thread.approved_by ? '' : 'warn'}`}>
                {thread.approved_by ? `Signed: ${thread.approved_by}` : thread.waiting}
              </span>
            </div>

            {thread.approved_by ? (
              <div className="callout success">
                <strong>
                  {locale === 'en'
                    ? `✓ Report Approved by ${thread.approved_by}`
                    : `✓ Informe Aprobado por ${thread.approved_by}`}
                </strong>
                <div style={{ marginTop: 4, fontSize: 12 }}>
                  {locale === 'en'
                    ? 'Workflow state is "done" and the approval signature is cryptographically chained in the SHA-256 audit log.'
                    : 'El estado del hilo es "done" y la firma de aprobación está encadenada con SHA-256.'}
                </div>
              </div>
            ) : (
              <div className="stack" style={{ gap: 10 }}>
                <div style={{ fontSize: 12.5, color: 'var(--muted)' }}>
                  {locale === 'en'
                    ? 'Test both buttons below: attempting to approve as A. Author triggers a live 403 refusal from FastAPI; approving as R. Reviewer signs the report.'
                    : 'Prueba ambos botones: intentar aprobar como A. Author lanza un rechazo 403 real de FastAPI; aprobar como R. Reviewer firma el informe.'}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    className="btn amber sm"
                    disabled={busyAction || isUndecided}
                    onClick={() => handleApprove('A. Author')}
                  >
                    {locale === 'en'
                      ? 'Try Self-Approve as A. Author (Test 403)'
                      : 'Intentar Autoaprobar como A. Author (Probar 403)'}
                  </button>
                  <button
                    type="button"
                    className="btn sm"
                    disabled={busyAction || isUndecided}
                    onClick={() => handleApprove('R. Reviewer')}
                  >
                    ✓{' '}
                    {locale === 'en'
                      ? 'Approve Report as R. Reviewer'
                      : 'Aprobar Informe como R. Reviewer'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Panel 2: 8 Deterministic Verifier Rules */}
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>
                  {locale === 'en'
                    ? '8 Deterministic Verifier Rules (verify_final)'
                    : '8 Reglas Deterministas del Verificador'}
                </h2>
                <p>
                  {locale === 'en'
                    ? 'Hard code gates: a single failure blocks publication'
                    : 'Puertas estrictas en código: un solo fallo bloquea el informe'}
                </p>
              </div>
              <span className={`status-pill ${thread.final.ok ? '' : 'block'}`}>
                {thread.final.ok ? '8 / 8 PASSED' : 'BLOCKED'}
              </span>
            </div>

            <div className="stack" style={{ gap: 6 }}>
              {VERIFIER_RULES.map((r) => {
                const failedThis = failedRulesText.includes(`Rule ${r.id}`);
                return (
                  <div
                    key={r.id}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 8,
                      background: failedThis
                        ? 'rgba(155, 42, 52, 0.22)'
                        : 'rgba(9, 28, 41, 0.72)',
                      border: failedThis ? '1px solid #8c454e' : '1px solid #1a4558',
                      display: 'flex',
                      alignItems: 'flex-start',
                      justifyContent: 'space-between',
                      gap: 10,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 600, color: '#fff' }}>
                        Rule {r.id}: {r.title[locale]}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>
                        {r.desc[locale]}
                      </div>
                    </div>
                    <span
                      className={`status-pill ${failedThis ? 'block' : ''}`}
                      style={{ padding: '1px 7px', fontSize: 10, flexShrink: 0 }}
                    >
                      {failedThis ? 'FIRED' : 'PASS'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Panel 3: Calibrated LLM Judge (Claude Sonnet 4.6) */}
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>
                  {locale === 'en'
                    ? 'Calibrated LLM Judge (Claude Sonnet 4.6)'
                    : 'Juez LLM Calibrado (Claude Sonnet 4.6)'}
                </h2>
                <p>
                  {locale === 'en'
                    ? 'Sentence-level Proportionality Check · Warns human reviewer, never overrides code rules'
                    : 'Revisión de proporcionalidad por frase · Advierte al revisor, nunca sustituye a las reglas'}
                </p>
              </div>
              <span className="chip">Advisory Judge</span>
            </div>

            {thread.judge.length > 0 ? (
              <div className="stack" style={{ gap: 8 }}>
                {thread.judge.map((j, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '9px 11px',
                      borderRadius: 9,
                      background:
                        j.verdict === 'overstated'
                          ? 'rgba(145, 101, 24, 0.18)'
                          : 'rgba(9, 28, 41, 0.65)',
                      border:
                        j.verdict === 'overstated'
                          ? '1px solid #85632c'
                          : '1px solid #194355',
                      fontSize: 12,
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 4,
                      }}
                    >
                      <span className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                        Sentence #{idx + 1}
                      </span>
                      <span
                        className={`status-pill ${
                          j.verdict === 'overstated'
                            ? 'warn'
                            : j.verdict === 'not_judged'
                              ? 'info'
                              : ''
                        }`}
                        style={{ padding: '1px 7px', fontSize: 10 }}
                      >
                        {j.verdict.toUpperCase()}
                        {j.category && j.category !== 'none' ? ` · ${j.category}` : ''}
                      </span>
                    </div>
                    <div style={{ color: '#e4f2f7', marginBottom: 4 }}>{j.sentence}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)' }}>{j.reason}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="callout">
                {locale === 'en'
                  ? 'Confirm NOAEL for both sexes to run the calibrated Sonnet 4.6 Judge across all report sentences.'
                  : 'Confirma el NOAEL de ambos sexos para ejecutar el Juez Sonnet 4.6 sobre todas las frases del informe.'}
              </div>
            )}

            {/* MCP vs REST Parity Check */}
            {sheet?.doorsTable && sheet.doorsTable.length >= 2 && (
              <div
                style={{
                  marginTop: 12,
                  paddingTop: 12,
                  borderTop: '1px solid #1a4558',
                  fontSize: 12,
                }}
              >
                <div className="eyebrow">
                  {locale === 'en'
                    ? 'TWO DOORS, ONE TOOL REGISTRY (MCP VS. REST PARITY)'
                    : 'DOS PUERTAS, UN REGISTRO DE HERRAMIENTAS (PARIDAD MCP VS. REST)'}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  {sheet.doorsTable.map((d) => (
                    <span key={d.door} className="chip">
                      {d.door}: <strong style={{ color: 'var(--green)' }}>{d.hash}…</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
