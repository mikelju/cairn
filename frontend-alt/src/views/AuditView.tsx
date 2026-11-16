import React, { useState } from 'react';
import { AuditVerifyResponse, ThreadView } from '../api';
import { Icon, Spinner } from '../components/Icon';
import { Locale, UI_TEXT } from '../i18n';

export interface SessionAuditEvent {
  seqHint: string;
  ts: string;
  actor: string;
  action: string;
  detail: string;
  status: 'ok' | 'refused';
}

interface AuditViewProps {
  locale: Locale;
  thread: ThreadView | null;
  audit: AuditVerifyResponse | null;
  sessionEvents: SessionAuditEvent[];
  onRefreshAudit: () => Promise<void>;
}

const BLOCKS = [
  { x: 10, w: 250, stroke: '#29d7d4', title: '#1 thread_started', prev: 'prev 0000…', hash: 'H₁' },
  { x: 320, w: 255, stroke: '#4d8df5', title: '#2…k decisions · refused', prev: 'prev H₁', hash: 'Hₖ' },
  { x: 630, w: 240, stroke: '#8b65f5', title: '#N verify · approve', prev: 'prev Hₙ₋₁', hash: 'Hₙ' },
];

export const AuditView: React.FC<AuditViewProps> = ({
  locale,
  thread,
  audit,
  sessionEvents,
  onRefreshAudit,
}) => {
  const t = UI_TEXT[locale];
  const [verifying, setVerifying] = useState(false);

  const handleVerifyNow = async () => {
    setVerifying(true);
    try {
      await onRefreshAudit();
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <div className="row">
          <h1>{t.audit}</h1>
          {thread && <span className="chip">{thread.thread_id.slice(0, 8)}</span>}
        </div>
        <div className="head-actions">
          <button className="btn" onClick={handleVerifyNow} disabled={verifying}>
            {verifying ? <Spinner /> : <Icon name="check" size={14} />} {t.verify}
          </button>
        </div>
      </div>

      <div className="grid three">
        <div className={`kpi-card ${audit && !audit.ok ? 'bad' : ''}`}>
          <div className="kpi-label">{t.integrity}</div>
          <div className={`kpi-value ${audit?.ok ? 'green' : 'amber'}`}>
            {audit ? (audit.ok ? t.intact : t.broken) : '—'}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">{t.entries}</div>
          <div className="kpi-value cyan">{audit?.count ?? 0}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">{t.firstBroken}</div>
          <div className="kpi-value">{audit?.first_broken ?? '—'}</div>
        </div>
      </div>

      <div className="panel">
        <div className="chart-box">
          <svg viewBox="0 0 880 110" style={{ width: '100%', height: 105, display: 'block' }}>
            {BLOCKS.map((b, i) => (
              <g key={b.title}>
                <rect x={b.x} y={10} width={b.w} height={88} rx={10} fill="#0c2638" stroke={b.stroke} strokeWidth="1.5" />
                <text x={b.x + 14} y={34} fill="#fff" fontSize="11.5" fontWeight="700" fontFamily="var(--mono)">
                  {b.title}
                </text>
                <text x={b.x + 14} y={56} fill="#9db7c3" fontSize="10.5" fontFamily="var(--mono)">
                  {b.prev}
                </text>
                <text x={b.x + 14} y={80} fill="#2fd389" fontSize="10.5" fontWeight="600" fontFamily="var(--mono)">
                  {b.hash} = SHA256(…)
                </text>
                {i < BLOCKS.length - 1 && (
                  <>
                    <path d={`M ${b.x + b.w + 4} 54 L ${BLOCKS[i + 1].x - 12} 54`} stroke={b.stroke} strokeWidth="2" />
                    <polygon
                      points={`${BLOCKS[i + 1].x - 12},49 ${BLOCKS[i + 1].x - 2},54 ${BLOCKS[i + 1].x - 12},59`}
                      fill={b.stroke}
                    />
                  </>
                )}
              </g>
            ))}
          </svg>
        </div>
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>{t.time}</th>
                <th>{t.actor}</th>
                <th>{t.action}</th>
                <th>{t.status}</th>
                <th>{t.detail}</th>
              </tr>
            </thead>
            <tbody>
              {sessionEvents.map((ev, idx) => (
                <tr key={idx}>
                  <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                    {ev.seqHint}
                  </td>
                  <td className="mono">{ev.ts}</td>
                  <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>
                    {ev.actor}
                  </td>
                  <td className="mono">{ev.action}</td>
                  <td>
                    <span className={`status-pill ${ev.status === 'refused' ? 'block' : ''}`}>
                      {ev.status === 'refused' ? t.refused : t.recorded}
                    </span>
                  </td>
                  <td>{ev.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
