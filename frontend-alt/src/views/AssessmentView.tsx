import React, { useEffect, useState } from 'react';
import {
  Actor,
  ApiError,
  DecisionInput,
  ThreadView,
  ViewId,
  confirmThreadNoael,
  recordThreadDecisions,
} from '../api';
import { EXAMPLE_DECISIONS_MAP, Locale } from '../i18n';

interface AssessmentViewProps {
  locale: Locale;
  actor: Actor;
  onChangeActor: (actor: Actor) => void;
  thread: ThreadView | null;
  onThreadUpdated: (updated: ThreadView, actionLabel: string) => void;
  onAuditRefusal: (actionLabel: string, status: number, detail: string) => void;
  onResetThread: () => Promise<void>;
  onNavigate: (view: ViewId) => void;
}

export const AssessmentView: React.FC<AssessmentViewProps> = ({
  locale,
  actor,
  onChangeActor,
  thread,
  onThreadUpdated,
  onAuditRefusal,
  onResetThread,
  onNavigate,
}) => {
  const [draftMap, setDraftMap] = useState<
    Record<string, { related: number | null; adverse: number | null; example: boolean }>
  >({});
  const [showAllSlots, setShowAllSlots] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{
    kind: 'success' | 'warn' | 'danger';
    text: string;
  } | null>(null);

  useEffect(() => {
    if (!thread) return;
    const bySlot: Record<
      string,
      { related: number | null; adverse: number | null; example: boolean }
    > = {};
    thread.slots.forEach((s) => {
      const existing = thread.decisions.find((d) => d.dec_id === s.slot);
      if (existing) {
        bySlot[s.slot] = {
          related: existing.treatment_related_from,
          adverse: existing.adverse_from,
          example: existing.actor === 'Example',
        };
      } else {
        const key = `${s.sex}|${s.finding}`;
        const preset = EXAMPLE_DECISIONS_MAP[key] || [null, null];
        const isKey = s.finding === 'GLAND, ADRENAL Vacuolization';
        bySlot[s.slot] = {
          related: preset[0],
          adverse: preset[1],
          example: !isKey,
        };
      }
    });
    setDraftMap(bySlot);
  }, [thread]);

  if (!thread) {
    return (
      <div className="panel">
        <div className="callout">Loading workflow thread…</div>
      </div>
    );
  }

  const updateSlotDraft = (
    slotId: string,
    field: 'related' | 'adverse',
    valStr: string,
  ) => {
    const num = valStr === 'none' ? null : Number(valStr);
    setDraftMap((prev) => {
      const cur = prev[slotId] || { related: null, adverse: null, example: false };
      const next = { ...cur, [field]: num, example: false };
      // Keep related <= adverse automatically for UX convenience
      if (field === 'adverse' && num !== null && (next.related === null || next.related > num)) {
        next.related = num;
      }
      if (field === 'related' && num === null) {
        next.adverse = null;
      } else if (
        field === 'related' &&
        num !== null &&
        next.adverse !== null &&
        num > next.adverse
      ) {
        next.adverse = num;
      }
      return { ...prev, [slotId]: next };
    });
  };

  const buildDecisionPayload = (): DecisionInput[] => {
    return thread.slots.map((s) => {
      const d = draftMap[s.slot] || { related: null, adverse: null, example: false };
      return {
        dec_id: s.slot,
        treatment_related_from: d.related,
        adverse_from: d.adverse,
        example: d.example,
      };
    });
  };

  const handleSaveDecisions = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      const payload = buildDecisionPayload();
      const updated = await recordThreadDecisions(thread.thread_id, actor, payload);
      onThreadUpdated(updated, `record_decisions (${payload.length} slots) by ${actor}`);
      setFeedback({
        kind: 'success',
        text:
          locale === 'en'
            ? `Recorded ${payload.length} slot decisions (D1–D11) in checkpoint and recomputed deterministic NOAEL.`
            : `Se registraron las ${payload.length} decisiones (D1–D11) en el checkpoint y se recalculó el NOAEL determinista.`,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        onAuditRefusal('record_decisions', err.status, err.detail);
        setFeedback({
          kind: 'danger',
          text: `HTTP ${err.status} (${actor}): ${err.detail} — Recorded in SHA-256 audit chain.`,
        });
      } else {
        setFeedback({ kind: 'danger', text: String(err) });
      }
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmNoael = async (sexes: Array<'F' | 'M'>) => {
    setBusy(true);
    setFeedback(null);
    try {
      // If no decisions have been saved yet and actor is Reviewer, save them first
      let currentThread = thread;
      if (actor === 'R. Reviewer' && currentThread.decisions.length === 0) {
        const payload = buildDecisionPayload();
        currentThread = await recordThreadDecisions(currentThread.thread_id, actor, payload);
        onThreadUpdated(currentThread, `record_decisions (${payload.length} slots) by ${actor}`);
      }
      const updated = await confirmThreadNoael(currentThread.thread_id, actor, sexes);
      onThreadUpdated(
        updated,
        `confirm_noael (${sexes.join(', ')}) by ${actor} -> waiting=${updated.waiting}`,
      );
      setFeedback({
        kind: 'success',
        text:
          locale === 'en'
            ? `NOAEL confirmed for ${sexes.join(' & ')} by ${actor}. Workflow transitioned to ${updated.waiting} and ran 8 verifier rules + Sonnet 4.6 Judge.`
            : `NOAEL confirmado para ${sexes.join(' y ')} por ${actor}. El flujo avanzó a ${updated.waiting} y ejecutó las 8 reglas y el Juez Sonnet 4.6.`,
      });
    } catch (err) {
      if (err instanceof ApiError) {
        onAuditRefusal('confirm_noael', err.status, err.detail);
        setFeedback({
          kind: 'danger',
          text: `HTTP ${err.status} (${actor}): ${err.detail} — Refusal chained in SHA-256 audit log.`,
        });
      } else {
        setFeedback({ kind: 'danger', text: String(err) });
      }
    } finally {
      setBusy(false);
    }
  };

  const keyFemaleSlot = thread.slots.find(
    (s) => s.finding === 'GLAND, ADRENAL Vacuolization' && s.sex === 'F',
  );
  const keyMaleSlot = thread.slots.find(
    (s) => s.finding === 'GLAND, ADRENAL Vacuolization' && s.sex === 'M',
  );

  const isLocked = thread.waiting !== 'await_decisions';

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 4 · HUMAN-IN-THE-LOOP SCIENTIFIC ASSESSMENT & NOAEL DERIVATION'
              : 'ETAPA 4 · EVALUACIÓN CIENTÍFICA HUMANA Y DERIVACIÓN DETERMINISTA DEL NOAEL'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Adversity Classification & Deterministic NOAEL'
              : 'Clasificación de Adversidad y NOAEL Determinista'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'A qualified reviewer classifies treatment-related and adverse onset doses; Python code deterministically derives the NOAEL per sex and flags any unexamined tissues at that dose.'
              : 'Un revisor cualificado clasifica las dosis de inicio relacionadas con el tratamiento y adversas; el código deriva de forma determinista el NOAEL por sexo y advierte de tejidos no examinados.'}
          </p>
        </div>
        <div className="head-actions">
          <span className="status-pill info">Thread Step: {thread.waiting}</span>
          {isLocked && (
            <button className="btn secondary sm" onClick={onResetThread}>
              ↻ {locale === 'en' ? 'Start Fresh Thread to Edit' : 'Iniciar Nuevo Hilo para Editar'}
            </button>
          )}
          <button className="btn" onClick={() => onNavigate('report')}>
            {locale === 'en' ? 'Open CTD 2.6.6.3 Report →' : 'Abrir Informe CTD 2.6.6.3 →'}
          </button>
        </div>
      </div>

      {/* Role Gate Banner */}
      <div
        className={`callout ${actor === 'A. Author' ? 'warn' : 'success'}`}
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
            {locale === 'en' ? 'Active Session Role: ' : 'Rol Activo en Sesión: '}
            <span className="mono">{actor}</span>
          </strong>{' '}
          —{' '}
          {actor === 'A. Author'
            ? locale === 'en'
              ? 'In Cairn, the author of the draft cannot record adversity decisions or confirm a NOAEL. Try clicking "Save Decisions" or "Confirm NOAEL" below to trigger the live HTTP 403 refusal, or switch to R. Reviewer.'
              : 'El autor del borrador no puede registrar decisiones de adversidad ni confirmar el NOAEL. Prueba a pulsar Guardar o Confirmar para ver el bloqueo HTTP 403 en vivo, o cambia a R. Reviewer.'
            : locale === 'en'
              ? 'R. Reviewer is active. You have full authority to record D1–D11 onset doses and confirm the NOAEL for Females and Males.'
              : 'R. Reviewer activo. Tienes permisos completos para grabar las decisiones D1–D11 y confirmar el NOAEL.'}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            className={`btn sm ${actor === 'A. Author' ? 'amber' : 'secondary'}`}
            onClick={() => onChangeActor('A. Author')}
          >
            Switch to A. Author (Test 403)
          </button>
          <button
            type="button"
            className={`btn sm ${actor === 'R. Reviewer' ? '' : 'secondary'}`}
            onClick={() => onChangeActor('R. Reviewer')}
          >
            Switch to R. Reviewer ✓
          </button>
        </div>
      </div>

      {feedback && <div className={`callout ${feedback.kind}`}>{feedback.text}</div>}

      {/* Key Finding Evaluation Cards (Female & Male Adrenal Vacuolization) */}
      <div className="grid two">
        {[
          {
            sex: 'F' as const,
            title:
              locale === 'en'
                ? 'Females (F) — Key Finding: GLAND, ADRENAL Vacuolization'
                : 'Hembras (F) — Hallazgo Clave: GLAND, ADRENAL Vacuolization',
            slot: keyFemaleSlot,
            bars: [
              { dose: 0, text: '0/10 (0%)', pct: 0, exam: true },
              { dose: 20, text: '2/5 (40%)', pct: 40, exam: true },
              { dose: 200, text: '4/5 (80%)', pct: 80, exam: true },
              { dose: 400, text: '9/10 (90%)', pct: 90, exam: true },
            ],
            contextNote:
              locale === 'en'
                ? 'Accompanied by -14.2% lower Day-29 body weight vs control from 200 mg/kg/day (Slot D10).'
                : 'Acompañado de peso corporal -14.2% menor que el control desde 200 mg/kg/día (Slot D10).',
          },
          {
            sex: 'M' as const,
            title:
              locale === 'en'
                ? 'Males (M) — Key Finding: GLAND, ADRENAL Vacuolization'
                : 'Machos (M) — Hallazgo Clave: GLAND, ADRENAL Vacuolization',
            slot: keyMaleSlot,
            bars: [
              { dose: 0, text: '0/10 (0%)', pct: 0, exam: true },
              { dose: 20, text: 'not examined', pct: 0, exam: false },
              { dose: 200, text: 'not examined', pct: 0, exam: false },
              { dose: 400, text: '7/10 (70%)', pct: 70, exam: true },
            ],
            contextNote:
              locale === 'en'
                ? 'Note: Adrenals were not examined at 20 or 200 mg/kg/day in males; code automatically flags incomplete examination at NOAEL = 200 mg/kg/day.'
                : 'Nota: No se examinaron suprarrenales a 20 ni 200 mg/kg/día en machos; el código señala automáticamente examen incompleto en el NOAEL.',
          },
        ].map((card) => {
          const slotId = card.slot?.slot || (card.sex === 'F' ? 'D1' : 'D6');
          const curDraft = draftMap[slotId] || { related: null, adverse: null, example: false };
          const noaelObj = thread.noael[card.sex];
          const isConfirmed = thread.confirmed.includes(card.sex);

          return (
            <div key={card.sex} className="panel">
              <div className="panel-head">
                <div>
                  <span className="eyebrow">SLOT {slotId}</span>
                  <h2>{card.title}</h2>
                </div>
                <span className={`status-pill ${isConfirmed ? '' : 'warn'}`}>
                  {isConfirmed ? 'NOAEL Confirmed' : 'Open for Decision'}
                </span>
              </div>

              {/* Incidence Bars */}
              <div
                style={{
                  background: '#071926',
                  border: '1px solid #1d4c60',
                  borderRadius: 10,
                  padding: 12,
                  marginBottom: 12,
                  display: 'grid',
                  gap: 8,
                }}
              >
                {card.bars.map((b) => (
                  <div
                    key={b.dose}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '95px 1fr 95px',
                      alignItems: 'center',
                      gap: 10,
                      fontSize: 12,
                    }}
                  >
                    <span className="mono">{b.dose} mg/kg/day</span>
                    <div
                      style={{
                        height: 10,
                        background: '#123142',
                        borderRadius: 99,
                        overflow: 'hidden',
                      }}
                    >
                      {b.exam && (
                        <div
                          style={{
                            height: '100%',
                            width: `${b.pct}%`,
                            background:
                              b.pct >= 70
                                ? 'linear-gradient(90deg, #f5b84c, #f36b6b)'
                                : 'linear-gradient(90deg, #29d7d4, #4d8df5)',
                          }}
                        />
                      )}
                    </div>
                    <span
                      className="mono"
                      style={{
                        textAlign: 'right',
                        color: !b.exam ? 'var(--dim)' : b.pct >= 70 ? 'var(--amber)' : '#fff',
                      }}
                    >
                      {b.text}
                    </span>
                  </div>
                ))}
              </div>

              <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>
                {card.contextNote}
              </p>

              {/* Selectors for Treatment-Related & Adverse Onset */}
              <div className="grid two" style={{ marginBottom: 14 }}>
                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 11.5,
                      color: 'var(--cyan2)',
                      fontFamily: 'var(--mono)',
                      marginBottom: 5,
                    }}
                  >
                    {locale === 'en'
                      ? 'TREATMENT-RELATED FROM (MG/KG/DAY)'
                      : 'RELACIONADO CON TRATAMIENTO DESDE'}
                  </label>
                  <select
                    className="select"
                    style={{ width: '100%' }}
                    disabled={isLocked}
                    value={curDraft.related === null ? 'none' : String(curDraft.related)}
                    onChange={(e) => updateSlotDraft(slotId, 'related', e.target.value)}
                  >
                    <option value="none">None (Not treatment-related)</option>
                    <option value="20">20 mg/kg/day (Low dose)</option>
                    <option value="200">200 mg/kg/day (Mid dose)</option>
                    <option value="400">400 mg/kg/day (High dose)</option>
                  </select>
                </div>

                <div>
                  <label
                    style={{
                      display: 'block',
                      fontSize: 11.5,
                      color: 'var(--amber)',
                      fontFamily: 'var(--mono)',
                      marginBottom: 5,
                    }}
                  >
                    {locale === 'en' ? 'ADVERSE FROM (MG/KG/DAY)' : 'ADVERSO DESDE (MG/KG/DÍA)'}
                  </label>
                  <select
                    className="select"
                    style={{ width: '100%' }}
                    disabled={isLocked}
                    value={curDraft.adverse === null ? 'none' : String(curDraft.adverse)}
                    onChange={(e) => updateSlotDraft(slotId, 'adverse', e.target.value)}
                  >
                    <option value="none">None (Non-adverse at all doses)</option>
                    <option value="20">20 mg/kg/day (Low dose)</option>
                    <option value="200">200 mg/kg/day (Mid dose)</option>
                    <option value="400">400 mg/kg/day (High dose)</option>
                  </select>
                </div>
              </div>

              {/* Deterministic NOAEL Output Box */}
              <div
                style={{
                  padding: 14,
                  borderRadius: 11,
                  background: 'linear-gradient(115deg, rgba(20, 96, 84, 0.24), rgba(11, 38, 52, 0.6))',
                  border: '1px solid #267868',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  <div>
                    <div className="eyebrow" style={{ margin: 0 }}>
                      {locale === 'en'
                        ? `DETERMINISTIC NOAEL (${card.sex}) COMPUTED BY CODE`
                        : `NOAEL DETERMINISTA (${card.sex}) CALCULADO POR CÓDIGO`}
                    </div>
                    <div
                      className="mono"
                      style={{ fontSize: 24, fontWeight: 700, color: 'var(--green)', marginTop: 2 }}
                    >
                      {noaelObj?.dose !== null && noaelObj?.dose !== undefined
                        ? `${noaelObj.dose} mg/kg/day`
                        : 'Not established (< 20 mg/kg/day)'}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn sm"
                    disabled={busy || isLocked}
                    onClick={() => handleConfirmNoael([card.sex])}
                  >
                    {isConfirmed
                      ? locale === 'en'
                        ? `Confirmed (${card.sex}) ✓`
                        : `Confirmado (${card.sex}) ✓`
                      : locale === 'en'
                        ? `Confirm ${card.sex} NOAEL`
                        : `Confirmar NOAEL ${card.sex}`}
                  </button>
                </div>
                {noaelObj?.flags && noaelObj.flags.length > 0 && (
                  <div
                    style={{
                      marginTop: 8,
                      paddingTop: 8,
                      borderTop: '1px solid rgba(41, 215, 212, 0.2)',
                      fontSize: 11.5,
                      color: '#ffd58b',
                    }}
                  >
                    <strong>Incomplete Examination Flags Placed in Report:</strong>
                    <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                      {noaelObj.flags.map((fl, i) => (
                        <li key={i}>{fl}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Action Bar + Full 11-Slot Ledger Inspector */}
      <div className="panel">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 14,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <h2 style={{ margin: '0 0 4px', fontSize: 16 }}>
              {locale === 'en'
                ? 'All 11 Enumerated Study Decision Slots (D1–D11)'
                : 'Los 11 Slots de Decisión Enumerados del Estudio (D1–D11)'}
            </h2>
            <p style={{ margin: 0, fontSize: 12.5, color: 'var(--muted)' }}>
              {locale === 'en'
                ? 'Slots D1–D9 cover the 9 screened histopathology findings; D10–D11 cover Day-29 body weight for Females and Males.'
                : 'Los slots D1–D9 cubren los 9 hallazgos histopatológicos cribados; D10–D11 cubren el peso corporal en Día 29.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn secondary sm"
              onClick={() => setShowAllSlots((s) => !s)}
            >
              {showAllSlots ? '▼' : '▶'}{' '}
              {locale === 'en'
                ? 'Inspect / Edit All 11 Slots (D1–D11)'
                : 'Inspeccionar / Editar los 11 Slots (D1–D11)'}
            </button>

            <button
              type="button"
              className="btn secondary sm"
              disabled={busy || isLocked}
              onClick={handleSaveDecisions}
            >
              {locale === 'en'
                ? `Save Decisions (D1–D11) as ${actor}`
                : `Guardar Decisiones (D1–D11) como ${actor}`}
            </button>

            <button
              type="button"
              className="btn sm"
              disabled={busy || isLocked}
              onClick={() => handleConfirmNoael(['F', 'M'])}
            >
              {locale === 'en'
                ? `Confirm Both Sexes (F & M) & Run Verifier as ${actor} →`
                : `Confirmar Ambos Sexos (F y M) y Ejecutar Verificador como ${actor} →`}
            </button>
          </div>
        </div>

        {showAllSlots && (
          <div className="table-wrap" style={{ marginTop: 14 }}>
            <table>
              <thead>
                <tr>
                  <th>Slot ID</th>
                  <th>Sex</th>
                  <th>Screened Finding / Endpoint</th>
                  <th>Treatment-Related From</th>
                  <th>Adverse From</th>
                  <th>Recorded Actor</th>
                </tr>
              </thead>
              <tbody>
                {thread.slots.map((s) => {
                  const d = draftMap[s.slot] || { related: null, adverse: null, example: false };
                  const savedDec = thread.decisions.find((x) => x.dec_id === s.slot);
                  return (
                    <tr key={s.slot}>
                      <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                        {s.slot}
                      </td>
                      <td className="mono">{s.sex}</td>
                      <td style={{ fontWeight: 600, color: '#fff' }}>{s.finding}</td>
                      <td>
                        <select
                          className="select"
                          style={{ padding: '4px 8px', fontSize: 12 }}
                          disabled={isLocked}
                          value={d.related === null ? 'none' : String(d.related)}
                          onChange={(e) => updateSlotDraft(s.slot, 'related', e.target.value)}
                        >
                          <option value="none">no dose (none)</option>
                          {s.doses
                            .filter((x) => x > 0)
                            .map((doseVal) => (
                              <option key={doseVal} value={String(doseVal)}>
                                {doseVal} mg/kg/day
                              </option>
                            ))}
                        </select>
                      </td>
                      <td>
                        <select
                          className="select"
                          style={{ padding: '4px 8px', fontSize: 12 }}
                          disabled={isLocked}
                          value={d.adverse === null ? 'none' : String(d.adverse)}
                          onChange={(e) => updateSlotDraft(s.slot, 'adverse', e.target.value)}
                        >
                          <option value="none">no dose (none)</option>
                          {s.doses
                            .filter((x) => x > 0)
                            .map((doseVal) => (
                              <option key={doseVal} value={String(doseVal)}>
                                {doseVal} mg/kg/day
                              </option>
                            ))}
                        </select>
                      </td>
                      <td className="mono" style={{ fontSize: 11.5 }}>
                        {savedDec ? (
                          <span
                            className={`status-pill ${
                              savedDec.actor === 'R. Reviewer' ? '' : 'info'
                            }`}
                            style={{ padding: '1px 7px' }}
                          >
                            {savedDec.actor}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--muted)' }}>Unsaved preset</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
