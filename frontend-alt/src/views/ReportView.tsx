import React, { useEffect, useState } from 'react';
import {
  Actor,
  ApiError,
  DecisionInput,
  ParsedDraftSheet,
  ParsedProvenanceItem,
  ThreadView,
  ViewId,
  VERIFIER_RULE_TOTAL,
  approveThreadDraft,
  confirmThreadNoael,
  fetchDraftSheet,
  recordThreadDecisions,
  verifierFailedRules,
  verifierRulesPassed,
} from '../api';
import { Icon, Spinner } from '../components/Icon';
import { ProvenanceInline } from '../components/ProvenanceModal';
import { EXAMPLE_DECISIONS_MAP, Locale, UI_TEXT, VERIFIER_RULES } from '../i18n';

interface ReportViewProps {
  locale: Locale;
  actor: Actor;
  onChangeActor: (actor: Actor) => void;
  thread: ThreadView | null;
  onThreadUpdated: (updated: ThreadView, actionLabel: string, effectiveActor?: Actor) => void | Promise<void>;
  onAuditRefusal: (
    actionLabel: string,
    status: number,
    detail: string,
    effectiveActor?: Actor,
  ) => void | Promise<void>;
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
  const t = UI_TEXT[locale];
  const [sheet, setSheet] = useState<ParsedDraftSheet | null>(null);
  const [loadingSheet, setLoadingSheet] = useState(false);
  const [busyAction, setBusyAction] = useState(false);
  const [tab, setTab] = useState<'rules' | 'judge'>('rules');
  const [banner, setBanner] = useState<{ kind: 'success' | 'warn' | 'danger'; text: string } | null>(null);

  // The sheet carries backend text, so it is refetched when the language changes.
  useEffect(() => {
    if (!thread) return;
    setLoadingSheet(true);
    fetchDraftSheet(thread.thread_id, actor, locale)
      .then((res) => setSheet(res))
      .catch(() => {})
      .finally(() => setLoadingSheet(false));
  }, [thread, actor, locale]);

  if (!thread) {
    return (
      <div className="center-pad">
        <Spinner />
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
      const confirmedThread = await confirmThreadNoael(thread.thread_id, 'R. Reviewer', ['F', 'M']);
      onChangeActor('R. Reviewer');
      await onThreadUpdated(
        confirmedThread,
        'quick_confirm D1-D11 + F/M NOAEL by R. Reviewer',
        'R. Reviewer',
      );
      setBanner({
        kind: confirmedThread.final.ok ? 'success' : 'warn',
        text: `${t.bothConfirmed} · ${verifierRulesPassed(confirmedThread.final)}/${VERIFIER_RULE_TOTAL}`,
      });
    } catch (err) {
      setBanner({ kind: 'danger', text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusyAction(false);
    }
  };

  const handleApprove = async (asActor: Actor) => {
    setBusyAction(true);
    setBanner(null);
    try {
      const updated = await approveThreadDraft(thread.thread_id, asActor);
      await onThreadUpdated(updated, `approve_draft by ${asActor}`, asActor);
      setBanner({ kind: 'success', text: `${t.approved} · ${updated.approved_by}` });
    } catch (err) {
      if (err instanceof ApiError) {
        await onAuditRefusal(`approve_draft (${asActor})`, err.status, err.detail, asActor);
        setBanner({ kind: 'danger', text: `HTTP ${err.status} · ${asActor}: ${err.detail}` });
      } else {
        setBanner({ kind: 'danger', text: String(err) });
      }
    } finally {
      setBusyAction(false);
    }
  };

  const isUndecided = thread.waiting === 'await_decisions';
  const failedRules = verifierFailedRules(thread.final);
  const passed = verifierRulesPassed(thread.final);
  const exampleRows = (sheet?.judgeTable ?? []).filter((r) => r.isExample);

  return (
    <div className="stack">
      <div className="page-head">
        <div className="row">
          <h1>{t.ctd}</h1>
          <span className={`status-pill ${thread.approved_by ? '' : 'warn'}`}>
            {thread.approved_by ? `${t.signed} · ${thread.approved_by}` : thread.waiting}
          </span>
        </div>
        <div className="head-actions">
          <button className="btn secondary sm" disabled title={t.prodTip}>
            <Icon name="download" size={13} /> {t.pdf}
          </button>
          <button className="btn secondary sm" disabled title={t.prodTip}>
            <Icon name="download" size={13} /> {t.docx}
          </button>
          <span className="prod-badge">{t.production}</span>
        </div>
      </div>

      {isUndecided && (
        <div className="callout warn row between">
          <span className="row" style={{ gap: 8 }}>
            <Icon name="alert" size={15} /> {t.decisionsPending}
          </span>
          <span className="row">
            <button type="button" className="btn sm secondary" onClick={() => onNavigate('assessment')}>
              {t.navAssessment}
            </button>
            <button type="button" className="btn sm" disabled={busyAction} onClick={handleQuickConfirmAll}>
              {busyAction ? <Spinner /> : <Icon name="bolt" size={13} />} {t.autoConfirm}
            </button>
          </span>
        </div>
      )}

      {banner && <div className={`callout ${banner.kind}`}>{banner.text}</div>}

      <div className="grid main-side">
        <div className="stack">
          <div className="panel row between" style={{ padding: '8px 14px' }}>
            <span className="row">
              <span className="status-pill">{t.aiDigits}</span>
              {sheet?.countsLine && (
                <span className="mono muted" style={{ fontSize: 12 }}>
                  {sheet.countsLine}
                </span>
              )}
            </span>
            <span className="row mono" style={{ gap: 10, fontSize: 11 }}>
              <span style={{ color: '#8ef5d8' }}>● {t.data_}</span>
              <span style={{ color: '#ded2ff' }}>● {t.quote}</span>
              <span style={{ color: '#ffe3a3' }}>● {t.decision}</span>
            </span>
          </div>

          {sheet ? (
            <article className={`doc-sheet ${loadingSheet ? 'busy' : ''}`}>
              <div
                className="row between"
                style={{
                  fontSize: 11.5,
                  fontFamily: 'var(--mono)',
                  color: '#4c6875',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}
              >
                <span>ICH M4S(R2) · CTD 2.6.6.3</span>
                <span>
                  {thread.approved_by ? `${t.approved} · ${thread.approved_by}` : isUndecided ? t.draft : t.awaiting}
                </span>
              </div>

              <h1>Nonclinical Summary — Study PDS2014</h1>

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
              {sheet.studyIntro.length > 0 && (
                <p>
                  <ProvenanceInline parts={sheet.studyIntro} onSelect={onSelectProvenance} />
                </p>
              )}
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '32%' }}>Parameter</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {sheet.parameterRows.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{r.label}</td>
                      <td>
                        <ProvenanceInline parts={r.parts} onSelect={onSelectProvenance} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h2>2. Recorded Decisions</h2>
              <p>{sheet.decisionIntro || 'The following decisions on adversity of the findings were recorded.'}</p>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 80 }}>Ref.</th>
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
              {sheet.tkIntro.length > 0 && (
                <p>
                  <ProvenanceInline parts={sheet.tkIntro} onSelect={onSelectProvenance} />
                </p>
              )}
              {sheet.tkMeanRows.length > 0 && (
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: '45%' }}>Quarantined value</th>
                      <th>{sheet.tkMeanHeader}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.tkMeanRows.map((r, i) => (
                      <tr key={i}>
                        <td style={{ fontWeight: 600 }}>{r.label}</td>
                        <td>
                          <ProvenanceInline parts={r.parts} onSelect={onSelectProvenance} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {sheet.tkNotes.length > 0 && (
                <ul style={{ paddingLeft: 22 }}>
                  {sheet.tkNotes.map((note, i) => (
                    <li key={i} style={{ margin: '6px 0' }}>
                      <ProvenanceInline parts={note} onSelect={onSelectProvenance} />
                    </li>
                  ))}
                </ul>
              )}

              <h2>4. No-observed-adverse-effect level (NOAEL)</h2>
              {sheet.noaelSections.map((sec, i) => (
                <div key={i} style={{ marginBottom: 14 }}>
                  <h3>{sec.heading}</h3>
                  {sec.text.length > 0 && (
                    <p>
                      <ProvenanceInline parts={sec.text} onSelect={onSelectProvenance} />
                    </p>
                  )}
                  {sec.quote.length > 0 && (
                    <blockquote>
                      <ProvenanceInline parts={sec.quote} onSelect={onSelectProvenance} />
                    </blockquote>
                  )}
                </div>
              ))}

              <h2>References</h2>
              <ol style={{ paddingLeft: 22 }}>
                {sheet.references.map((ref, i) => (
                  <li key={i} style={{ margin: '4px 0' }}>{ref}</li>
                ))}
              </ol>

              <div
                style={{
                  marginTop: 18,
                  paddingTop: 10,
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
            <div className="panel center-pad">
              <Spinner />
            </div>
          )}
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>{t.signOff}</h2>
              <span className={`status-pill ${thread.approved_by ? '' : 'warn'}`}>
                {thread.approved_by ? thread.approved_by : thread.waiting}
              </span>
            </div>
            {thread.approved_by ? (
              <div className="callout success row" style={{ gap: 8 }}>
                <Icon name="check" size={15} /> {t.approved} · {thread.approved_by}
              </div>
            ) : (
              <div className="row">
                <button
                  type="button"
                  className="btn amber sm"
                  disabled={busyAction || isUndecided}
                  onClick={() => handleApprove('A. Author')}
                >
                  <Icon name="lock" size={13} /> {t.selfApprove}
                </button>
                <button
                  type="button"
                  className="btn sm"
                  disabled={busyAction || isUndecided}
                  onClick={() => handleApprove('R. Reviewer')}
                >
                  <Icon name="check" size={13} /> {t.approve}
                </button>
              </div>
            )}
          </div>

          <div className="panel">
            <div className="tabs">
              <button type="button" className={`tab ${tab === 'rules' ? 'active' : ''}`} onClick={() => setTab('rules')}>
                {t.rules}{' '}
                <span className={`status-pill ${thread.final.ok ? '' : 'block'}`} style={{ padding: '0 7px' }}>
                  {passed}/{VERIFIER_RULE_TOTAL}
                </span>
              </button>
              <button type="button" className={`tab ${tab === 'judge' ? 'active' : ''}`} onClick={() => setTab('judge')}>
                {t.judge}
              </button>
            </div>

            {tab === 'rules' ? (
              <div className="stack" style={{ gap: 5 }}>
                {VERIFIER_RULES.map((r) => {
                  const fired = failedRules.has(r.id);
                  return (
                    <div
                      key={r.id}
                      className="kv"
                      style={fired ? { background: 'rgba(155, 42, 52, 0.22)', borderColor: '#8c454e' } : undefined}
                    >
                      <span style={{ color: '#fff' }}>
                        <span className="mono muted" style={{ marginRight: 8 }}>
                          R{r.id}
                        </span>
                        {r.title[locale]}
                      </span>
                      <span className={`status-pill ${fired ? 'block' : ''}`} style={{ padding: '0 7px', fontSize: 10 }}>
                        {fired ? t.fired : t.pass}
                      </span>
                    </div>
                  );
                })}
                {sheet?.doorsTable && sheet.doorsTable.length >= 2 && (
                  <div className="row" style={{ marginTop: 4 }}>
                    <span className={`status-pill ${sheet.doorsMatch ? '' : 'block'}`}>
                      <Icon name={sheet.doorsMatch ? 'check' : 'alert'} size={12} /> {t.parity}
                    </span>
                    {sheet.doorsTable.map((d) => (
                      <span key={d.door} className="chip" title={d.hash}>
                        {d.door} <strong style={{ color: 'var(--green)' }}>{d.hash.slice(0, 8)}</strong>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="stack" style={{ gap: 6 }}>
                {exampleRows.map((r, i) => (
                  <div key={`ex-${i}`} className="tile warn" style={{ fontSize: 12 }}>
                    <div className="row between" style={{ marginBottom: 4 }}>
                      <span className="prod-badge">{t.example}</span>
                      <span className="status-pill warn" style={{ padding: '0 7px', fontSize: 10 }}>
                        {(r.verdict || 'overstated').toUpperCase()}
                      </span>
                    </div>
                    <div style={{ color: '#e4f2f7', marginBottom: 3 }}>{r.sentence}</div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      {r.reason}
                    </div>
                  </div>
                ))}
                {thread.judge.length === 0 && exampleRows.length === 0 && <div className="empty">{t.notRun}</div>}
                {thread.judge.map((j, idx) => (
                  <div
                    key={idx}
                    className={`tile ${j.verdict === 'overstated' ? 'warn' : ''}`}
                    style={{ fontSize: 12 }}
                  >
                    <div className="row between" style={{ marginBottom: 4 }}>
                      <span className="mono muted" style={{ fontSize: 10.5 }}>
                        #{idx + 1}
                      </span>
                      <span
                        className={`status-pill ${
                          j.verdict === 'overstated' ? 'warn' : j.verdict === 'not judged' ? 'info' : ''
                        }`}
                        style={{ padding: '0 7px', fontSize: 10 }}
                      >
                        {j.verdict.toUpperCase()}
                        {j.category && j.category !== 'none' ? ` · ${j.category}` : ''}
                      </span>
                    </div>
                    <div style={{ color: '#e4f2f7', marginBottom: 3 }}>{j.sentence}</div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      {j.reason}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
