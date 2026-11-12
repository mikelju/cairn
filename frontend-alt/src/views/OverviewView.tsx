import React, { useEffect, useState } from 'react';
import {
  AuditVerifyResponse,
  ParsedAskResult,
  ParsedProvenanceItem,
  ThreadView,
  VERIFIER_RULE_TOTAL,
  noaelDisplay,
  runRecordedQuestion,
  verifierRulesPassed,
} from '../api';
import { Icon, Spinner } from '../components/Icon';
import { NoaelPill, noaelLabel } from '../components/Noael';
import { ProvenanceInline } from '../components/ProvenanceModal';
import { Locale, UI_TEXT, ViewId } from '../i18n';

interface OverviewViewProps {
  locale: Locale;
  thread: ThreadView | null;
  audit: AuditVerifyResponse | null;
  onNavigate: (view: ViewId) => void;
  onSelectProvenance: (item: ParsedProvenanceItem) => void;
}

const PIPE_VIEWS: ViewId[] = ['study', 'guidelines', 'data', 'assessment', 'report'];

export const OverviewView: React.FC<OverviewViewProps> = ({
  locale,
  thread,
  audit,
  onNavigate,
  onSelectProvenance,
}) => {
  const t = UI_TEXT[locale];
  const [sampleAsk, setSampleAsk] = useState<ParsedAskResult | null>(null);

  useEffect(() => {
    setSampleAsk(null);
    runRecordedQuestion('Q3', locale)
      .then((res) => setSampleAsk(res))
      .catch(() => {});
  }, [locale]);

  const passed = thread ? verifierRulesPassed(thread.final) : 0;
  const decided = thread?.decisions.length ?? 0;
  const total = thread?.slots.length ?? 11;

  const noaelTiles = (['F', 'M'] as const).map((sex) => {
    const d = noaelDisplay(thread, sex);
    return { sex, d, flag: d.state === 'pending' ? undefined : thread?.noael?.[sex]?.flags?.[0] };
  });

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>PDS2014</h1>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {t.studySub}
          </div>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={() => onNavigate('assessment')}>
            {t.navAssessment} <Icon name="chevron" size={14} />
          </button>
        </div>
      </div>

      <div className="grid four">
        <div className="kpi-card">
          <div className="kpi-label">{t.animals}</div>
          <div className="kpi-value cyan">124</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">{t.doseLevels}</div>
          <div className="kpi-value">0 · 20 · 200 · 400</div>
          <div className="kpi-sub">mg/kg/day</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">{t.screened}</div>
          <div className="kpi-value amber">9</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">{t.quarantined}</div>
          <div className="kpi-value green">12</div>
          <div className="kpi-sub">PP · AUC &lt; 0</div>
        </div>
      </div>

      <div className="grid main-side">
        <div className="panel">
          <div className="panel-head">
            <h2>{t.doseResponse}</h2>
            <span className="chip">mg/kg/day</span>
          </div>

          <div className="chart-box" style={{ marginBottom: 12 }}>
            <svg viewBox="0 0 680 215" style={{ width: '100%', height: 200, display: 'block' }}>
              {[0, 25, 50, 75, 100].map((pct) => {
                const y = 175 - (pct / 100) * 140;
                return (
                  <g key={pct}>
                    <line
                      x1={60}
                      y1={y}
                      x2={640}
                      y2={y}
                      stroke="#184052"
                      strokeDasharray={pct === 0 ? undefined : '4 4'}
                    />
                    <text x={48} y={y + 4} textAnchor="end" fill="#88aab8" fontSize="10.5" fontFamily="var(--mono)">
                      {pct}%
                    </text>
                  </g>
                );
              })}

              {[
                { label: '0', x: 100 },
                { label: '20', x: 270 },
                { label: '200', x: 450 },
                { label: '400', x: 610 },
              ].map((d) => (
                <g key={d.label}>
                  <line x1={d.x} y1={35} x2={d.x} y2={175} stroke="#143545" />
                  <text x={d.x} y={196} textAnchor="middle" fill="#b8d4df" fontSize="11" fontFamily="var(--mono)">
                    {d.label}
                  </text>
                </g>
              ))}

              <polyline fill="none" stroke="#29d7d4" strokeWidth="3" points="100,175 270,119 450,63 610,49" />
              {[
                { x: 100, y: 175, txt: '0/10' },
                { x: 270, y: 119, txt: '2/5' },
                { x: 450, y: 63, txt: '4/5' },
                { x: 610, y: 49, txt: '9/10' },
              ].map((pt, i) => (
                <g key={`f-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="5" fill="#29d7d4" stroke="#06131d" strokeWidth="2" />
                  <text x={pt.x} y={pt.y - 10} textAnchor="middle" fill="#70f0e8" fontSize="10" fontFamily="var(--mono)">
                    {pt.txt}
                  </text>
                </g>
              ))}

              <polyline
                fill="none"
                stroke="#8b65f5"
                strokeWidth="2.5"
                strokeDasharray="6 3"
                points="100,175 270,175 450,175 610,77"
              />
              {[
                { x: 100, y: 175 },
                { x: 270, y: 175 },
                { x: 450, y: 175 },
                { x: 610, y: 77 },
              ].map((pt, i) => (
                <g key={`m-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="4.5" fill="#8b65f5" stroke="#06131d" strokeWidth="2" />
                  {i === 3 && (
                    <text x={pt.x - 8} y={pt.y + 16} textAnchor="end" fill="#d3c4ff" fontSize="10" fontFamily="var(--mono)">
                      7/10
                    </text>
                  )}
                </g>
              ))}

              <polyline
                fill="none"
                stroke="#f5b84c"
                strokeWidth="2.2"
                points="100,175 270,169 450,155 610,155"
              />
              {[
                { x: 270, y: 169, txt: '-4.3%' },
                { x: 450, y: 155, txt: '-14.2%' },
                { x: 610, y: 155, txt: '-14.3%' },
              ].map((pt, i) => (
                <g key={`bw-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="4" fill="#f5b84c" />
                  <text x={pt.x} y={pt.y - 8} textAnchor="middle" fill="#ffd88a" fontSize="9.5" fontFamily="var(--mono)">
                    {pt.txt}
                  </text>
                </g>
              ))}

              <g transform="translate(75, 16)">
                <circle cx={0} cy={0} r={4} fill="#29d7d4" />
                <text x={8} y={4} fill="#cfe7ef" fontSize="10.5">
                  F adrenal vacuolization
                </text>
                <circle cx={175} cy={0} r={4} fill="#8b65f5" />
                <text x={183} y={4} fill="#cfe7ef" fontSize="10.5">
                  M adrenal vacuolization
                </text>
                <circle cx={355} cy={0} r={4} fill="#f5b84c" />
                <text x={363} y={4} fill="#cfe7ef" fontSize="10.5">
                  F body weight vs control
                </text>
              </g>
            </svg>
          </div>

          <div className="grid two">
            {noaelTiles.map(({ sex, d, flag }) => (
              <div key={sex} className={`tile ${d.confirmed ? 'ok' : 'warn'}`}>
                <div className="row between">
                  <span className="tile-label">
                    {t.noael} {sex}
                  </span>
                  <NoaelPill d={d} t={t} />
                </div>
                <div className="tile-value sm">{noaelLabel(d, t)}</div>
                {flag && (
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }} title={flag}>
                    <Icon name="alert" size={12} /> {flag}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <h2>Thread</h2>
              <span className="status-pill info">{thread?.waiting ?? '…'}</span>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="kv">
                <span>{t.decisions}</span>
                <span className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
                  <span className="bar" style={{ width: 70 }}>
                    <i style={{ width: `${(decided / total) * 100}%` }} />
                  </span>
                  <strong>
                    {decided}/{total}
                  </strong>
                </span>
              </div>
              <div className="kv">
                <span>{t.verifier}</span>
                <span className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
                  <span className="bar" style={{ width: 70 }}>
                    <i style={{ width: `${(passed / VERIFIER_RULE_TOTAL) * 100}%` }} />
                  </span>
                  <strong style={{ color: thread?.final?.ok ? 'var(--green)' : 'var(--amber)' }}>
                    {passed}/{VERIFIER_RULE_TOTAL}
                  </strong>
                </span>
              </div>
              <div className="kv">
                <span>{t.auditChain}</span>
                <strong style={{ color: audit && !audit.ok ? 'var(--red)' : 'var(--cyan2)' }}>
                  {audit ? `${audit.count} · ${audit.ok ? t.intact : t.broken}` : '—'}
                </strong>
              </div>
              <div className="kv">
                <span>{t.signOff}</span>
                <strong style={{ color: thread?.approved_by ? 'var(--green)' : 'var(--muted)' }}>
                  {thread?.approved_by || '—'}
                </strong>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>{t.traceable}</h2>
              <span className="status-pill">{t.aiDigits}</span>
            </div>
            {sampleAsk && sampleAsk.verifiedParts.length > 0 ? (
              <>
                <div style={{ lineHeight: 1.75, fontSize: 13.5 }}>
                  <ProvenanceInline parts={sampleAsk.verifiedParts} onSelect={onSelectProvenance} />
                </div>
                {sampleAsk.aiWritten && (
                  <div style={{ marginTop: 10 }}>
                    <div className="tile-label" style={{ marginBottom: 4 }}>
                      {t.modelDraft}
                    </div>
                    <div
                      className="mono"
                      style={{
                        fontSize: 11.5,
                        color: '#9ec0ce',
                        padding: 8,
                        borderRadius: 8,
                        background: 'rgba(5, 16, 24, 0.8)',
                        border: '1px dashed #235368',
                      }}
                    >
                      {sampleAsk.aiWritten}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="center-pad">
                <Spinner />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="pipe">
        {t.pipeline.map((name, i) => (
          <React.Fragment key={name}>
            {i > 0 && <span className="pipe-line" />}
            <button type="button" className="pipe-step" onClick={() => onNavigate(PIPE_VIEWS[i])}>
              <b>{i + 1}</b>
              {name}
            </button>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
