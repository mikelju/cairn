import React, { useEffect, useState } from 'react';
import {
  Actor,
  ApiError,
  DecisionInput,
  ThreadView,
  ViewId,
  confirmThreadNoael,
  noaelDisplay,
  recordThreadDecisions,
} from '../api';
import { Icon, Spinner } from '../components/Icon';
import { NoaelPill, noaelLabel } from '../components/Noael';
import { EXAMPLE_DECISIONS_MAP, Locale, UI_TEXT } from '../i18n';

interface AssessmentViewProps {
  locale: Locale;
  actor: Actor;
  thread: ThreadView | null;
  onThreadUpdated: (updated: ThreadView, actionLabel: string, effectiveActor?: Actor) => void | Promise<void>;
  onAuditRefusal: (
    actionLabel: string,
    status: number,
    detail: string,
    effectiveActor?: Actor,
  ) => void | Promise<void>;
  onResetThread: () => Promise<void>;
  onNavigate: (view: ViewId) => void;
}

type SlotDraft = { related: number | null; adverse: number | null; example: boolean };

const KEY_FINDING = 'GLAND, ADRENAL Vacuolization';

const BARS: Record<'F' | 'M', Array<{ dose: number; text: string; pct: number; exam: boolean }>> = {
  F: [
    { dose: 0, text: '0/10', pct: 0, exam: true },
    { dose: 20, text: '2/5', pct: 40, exam: true },
    { dose: 200, text: '4/5', pct: 80, exam: true },
    { dose: 400, text: '9/10', pct: 90, exam: true },
  ],
  M: [
    { dose: 0, text: '0/10', pct: 0, exam: true },
    { dose: 20, text: 'n/e', pct: 0, exam: false },
    { dose: 200, text: 'n/e', pct: 0, exam: false },
    { dose: 400, text: '7/10', pct: 70, exam: true },
  ],
};

export const AssessmentView: React.FC<AssessmentViewProps> = ({
  locale,
  actor,
  thread,
  onThreadUpdated,
  onAuditRefusal,
  onResetThread,
  onNavigate,
}) => {
  const t = UI_TEXT[locale];
  const [draftMap, setDraftMap] = useState<Record<string, SlotDraft>>({});
  const [showAllSlots, setShowAllSlots] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'warn' | 'danger'; text: string } | null>(null);

  useEffect(() => {
    if (!thread) return;
    const bySlot: Record<string, SlotDraft> = {};
    thread.slots.forEach((s) => {
      const existing = thread.decisions.find((d) => d.dec_id === s.slot);
      if (existing) {
        bySlot[s.slot] = {
          related: existing.treatment_related_from,
          adverse: existing.adverse_from,
          example: existing.actor === 'Example',
        };
      } else {
        const preset = EXAMPLE_DECISIONS_MAP[`${s.sex}|${s.finding}`] || [null, null];
        bySlot[s.slot] = { related: preset[0], adverse: preset[1], example: s.finding !== KEY_FINDING };
      }
    });
    setDraftMap(bySlot);
  }, [thread]);

  if (!thread) {
    return (
      <div className="center-pad">
        <Spinner />
      </div>
    );
  }

  const updateSlotDraft = (slotId: string, field: 'related' | 'adverse', valStr: string) => {
    const num = valStr === 'none' ? null : Number(valStr);
    setDraftMap((prev) => {
      const cur = prev[slotId] || { related: null, adverse: null, example: false };
      const next = { ...cur, [field]: num, example: false };
      // Keep related <= adverse automatically
      if (field === 'adverse' && num !== null && (next.related === null || next.related > num)) {
        next.related = num;
      }
      if (field === 'related' && num === null) {
        next.adverse = null;
      } else if (field === 'related' && num !== null && next.adverse !== null && num > next.adverse) {
        next.adverse = num;
      }
      return { ...prev, [slotId]: next };
    });
  };

  const buildDecisionPayload = (): DecisionInput[] =>
    thread.slots.map((s) => {
      const d = draftMap[s.slot] || { related: null, adverse: null, example: false };
      return {
        dec_id: s.slot,
        treatment_related_from: d.related,
        adverse_from: d.adverse,
        example: d.example,
      };
    });

  // True when the form differs from what the checkpoint holds (or nothing is saved yet).
  const draftDiffersFromSaved = (): boolean =>
    thread.slots.some((s) => {
      const saved = thread.decisions.find((d) => d.dec_id === s.slot);
      const d = draftMap[s.slot] || { related: null, adverse: null, example: false };
      if (!saved) return true;
      return saved.treatment_related_from !== d.related || saved.adverse_from !== d.adverse;
    });

  const refuse = async (label: string, err: unknown) => {
    if (err instanceof ApiError) {
      await onAuditRefusal(label, err.status, err.detail, actor);
      setFeedback({ kind: 'danger', text: `HTTP ${err.status} · ${actor}: ${err.detail}` });
    } else {
      setFeedback({ kind: 'danger', text: String(err) });
    }
  };

  const handleSaveDecisions = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      const payload = buildDecisionPayload();
      const updated = await recordThreadDecisions(thread.thread_id, actor, payload);
      await onThreadUpdated(updated, `record_decisions (${payload.length} slots) by ${actor}`, actor);
      setFeedback({ kind: 'success', text: t.savedMsg });
    } catch (err) {
      await refuse('record_decisions', err);
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmNoael = async (sexes: Array<'F' | 'M'>) => {
    setBusy(true);
    setFeedback(null);
    try {
      let currentThread = thread;
      // Save first when nothing is saved or the dropdowns were edited after the last save.
      if (actor === 'R. Reviewer' && (currentThread.decisions.length === 0 || draftDiffersFromSaved())) {
        const payload = buildDecisionPayload();
        currentThread = await recordThreadDecisions(currentThread.thread_id, actor, payload);
        await onThreadUpdated(currentThread, `record_decisions (${payload.length} slots) by ${actor}`, actor);
      }
      const updated = await confirmThreadNoael(currentThread.thread_id, actor, sexes);
      await onThreadUpdated(
        updated,
        `confirm_noael (${sexes.join(', ')}) by ${actor} -> waiting=${updated.waiting}`,
        actor,
      );
      setFeedback({
        kind: 'success',
        text:
          updated.waiting === 'await_approval'
            ? t.bothConfirmed
            : `${sexes.join(' & ')} ${t.oneConfirmed}`,
      });
    } catch (err) {
      await refuse('confirm_noael', err);
    } finally {
      setBusy(false);
    }
  };

  const isLocked = thread.waiting !== 'await_decisions';

  const optionList = (
    <>
      <option value="none">{t.noneOpt}</option>
      <option value="20">20 mg/kg</option>
      <option value="200">200 mg/kg</option>
      <option value="400">400 mg/kg</option>
    </>
  );

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{t.assessment}</h1>
        <div className="head-actions">
          <span className="status-pill info">{thread.waiting}</span>
          {actor === 'A. Author' && (
            <span className="status-pill warn" title="A. Author">
              <Icon name="lock" size={12} /> {t.authorOnly}
            </span>
          )}
          {isLocked && (
            <button className="btn secondary sm" onClick={onResetThread}>
              <Icon name="reset" size={13} /> {t.newThread}
            </button>
          )}
          <button className="btn" onClick={() => onNavigate('report')}>
            {t.report} <Icon name="chevron" size={14} />
          </button>
        </div>
      </div>

      {feedback && <div className={`callout ${feedback.kind}`}>{feedback.text}</div>}

      <div className="grid two">
        {(['F', 'M'] as const).map((sex) => {
          const slot = thread.slots.find((s) => s.finding === KEY_FINDING && s.sex === sex);
          const slotId = slot?.slot || (sex === 'F' ? 'D1' : 'D6');
          const cur = draftMap[slotId] || { related: null, adverse: null, example: false };
          const nd = noaelDisplay(thread, sex);
          const flags = nd.state === 'pending' ? [] : thread.noael[sex]?.flags || [];

          return (
            <div key={sex} className="panel">
              <div className="panel-head">
                <h2>
                  {sex} · {KEY_FINDING}
                </h2>
                <span className="chip">{slotId}</span>
              </div>

              <div className="stack" style={{ gap: 6, marginBottom: 12 }}>
                {BARS[sex].map((b) => (
                  <div
                    key={b.dose}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '42px 1fr 44px',
                      alignItems: 'center',
                      gap: 10,
                      fontSize: 12,
                    }}
                  >
                    <span className="mono muted">{b.dose}</span>
                    <span className="bar" style={{ height: 10 }}>
                      {b.exam && <i className={b.pct >= 70 ? 'hot' : ''} style={{ width: `${b.pct}%` }} />}
                    </span>
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

              <div className="grid two" style={{ marginBottom: 12 }}>
                <label>
                  <span className="tile-label" style={{ color: 'var(--cyan2)' }}>
                    {t.related}
                  </span>
                  <select
                    className="select"
                    style={{ width: '100%', marginTop: 4 }}
                    disabled={isLocked}
                    value={cur.related === null ? 'none' : String(cur.related)}
                    onChange={(e) => updateSlotDraft(slotId, 'related', e.target.value)}
                  >
                    {optionList}
                  </select>
                </label>
                <label>
                  <span className="tile-label" style={{ color: 'var(--amber)' }}>
                    {t.adverse}
                  </span>
                  <select
                    className="select"
                    style={{ width: '100%', marginTop: 4 }}
                    disabled={isLocked}
                    value={cur.adverse === null ? 'none' : String(cur.adverse)}
                    onChange={(e) => updateSlotDraft(slotId, 'adverse', e.target.value)}
                  >
                    {optionList}
                  </select>
                </label>
              </div>

              <div className={`tile ${nd.confirmed ? 'ok' : nd.state === 'pending' ? '' : 'warn'}`}>
                <div className="row between">
                  <div>
                    <div className="tile-label">
                      {t.noael} {sex}
                    </div>
                    <div className="tile-value" style={{ color: nd.state === 'dose' ? 'var(--green)' : '#fff' }}>
                      {noaelLabel(nd, t)}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 8 }}>
                    <NoaelPill d={nd} t={t} />
                    <button
                      type="button"
                      className="btn sm"
                      disabled={busy || isLocked}
                      onClick={() => handleConfirmNoael([sex])}
                    >
                      {nd.confirmed ? <Icon name="check" size={13} /> : null}
                      {nd.confirmed ? t.confirmed : `${t.confirm} ${sex}`}
                    </button>
                  </div>
                </div>
                {flags.length > 0 && (
                  <div className="row" style={{ marginTop: 8, gap: 6 }}>
                    {flags.map((fl, i) => (
                      <span key={i} className="status-pill warn" style={{ whiteSpace: 'normal' }}>
                        <Icon name="alert" size={12} /> {fl}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="panel">
        <div className="row between">
          <button type="button" className="btn secondary sm" onClick={() => setShowAllSlots((s) => !s)}>
            <span style={{ display: 'inline-flex', transform: showAllSlots ? 'rotate(90deg)' : undefined }}>
              <Icon name="chevron" size={12} />
            </span>
            {t.slots}
          </button>
          <div className="row">
            {busy && <Spinner />}
            <button
              type="button"
              className="btn secondary sm"
              disabled={busy || isLocked}
              onClick={handleSaveDecisions}
            >
              {t.save}
            </button>
            <button
              type="button"
              className="btn sm"
              disabled={busy || isLocked}
              onClick={() => handleConfirmNoael(['F', 'M'])}
            >
              {t.confirmBoth} <Icon name="chevron" size={12} />
            </button>
          </div>
        </div>

        {showAllSlots && (
          <div className="table-wrap" style={{ marginTop: 12 }}>
            <table>
              <thead>
                <tr>
                  <th>{t.slot}</th>
                  <th>{t.sex}</th>
                  <th>{t.finding}</th>
                  <th>{t.related}</th>
                  <th>{t.adverse}</th>
                  <th>{t.by}</th>
                </tr>
              </thead>
              <tbody>
                {thread.slots.map((s) => {
                  const d = draftMap[s.slot] || { related: null, adverse: null, example: false };
                  const savedDec = thread.decisions.find((x) => x.dec_id === s.slot);
                  const doses = s.doses.filter((x) => x > 0);
                  return (
                    <tr key={s.slot}>
                      <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                        {s.slot}
                      </td>
                      <td className="mono">{s.sex}</td>
                      <td style={{ fontWeight: 600, color: '#fff' }}>{s.finding}</td>
                      {(['related', 'adverse'] as const).map((field) => (
                        <td key={field}>
                          <select
                            className="select"
                            style={{ padding: '3px 8px', fontSize: 12 }}
                            disabled={isLocked}
                            value={d[field] === null ? 'none' : String(d[field])}
                            onChange={(e) => updateSlotDraft(s.slot, field, e.target.value)}
                          >
                            <option value="none">{t.noneOpt}</option>
                            {doses.map((doseVal) => (
                              <option key={doseVal} value={String(doseVal)}>
                                {doseVal} mg/kg
                              </option>
                            ))}
                          </select>
                        </td>
                      ))}
                      <td>
                        {savedDec ? (
                          <span className={`status-pill ${savedDec.actor === 'R. Reviewer' ? '' : 'info'}`}>
                            {savedDec.actor}
                          </span>
                        ) : (
                          <span className="muted">{t.unsaved}</span>
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
