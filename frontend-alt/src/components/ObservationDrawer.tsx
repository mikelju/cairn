import React, { useState } from 'react';
import { Observation } from '../api';
import { UI_TEXT, Locale } from '../i18n';
import { Icon } from './Icon';

interface ObservationDrawerProps {
  observation: Observation<any> | null;
  locale: Locale;
}

export const ObservationDrawer: React.FC<ObservationDrawerProps> = ({ observation, locale }) => {
  const t = UI_TEXT[locale];
  const [open, setOpen] = useState(false);

  if (!observation) return null;

  const sampleRows = observation.source_rows.slice(0, 12);
  const columns = sampleRows.length > 0 ? Object.keys(sampleRows[0]) : [];

  return (
    <div style={{ marginTop: 12, borderTop: '1px solid #1b485b', paddingTop: 10 }}>
      <div className="row between">
        <div className="row" style={{ gap: 6 }}>
          <span className="chip" title={observation.content_sha256}>
            {observation.obs_id}
          </span>
          <span className="chip" title={observation.content_sha256}>
            sha256 <strong style={{ color: 'var(--cyan2)' }}>{observation.content_sha256.slice(0, 10)}</strong>
          </span>
          <span className="chip">
            n <strong style={{ color: '#fff' }}>{observation.n_examined ?? '—'}</strong>
          </span>
          <span className="chip">
            {t.sourceRows} <strong style={{ color: '#fff' }}>{observation.source_rows.length}</strong>
          </span>
        </div>
        <button className="btn secondary sm" onClick={() => setOpen((o) => !o)}>
          <Icon name="chevron" size={12} /> {t.provenance}
        </button>
      </div>

      {open && (
        <div
          className="grid two"
          style={{
            marginTop: 10,
            padding: 12,
            borderRadius: 10,
            background: '#061520',
            border: '1px solid #1f5064',
          }}
        >
          <div>
            <div className="tile-label">SQL</div>
            <pre
              className="mono"
              style={{
                margin: '4px 0 0',
                padding: 8,
                borderRadius: 8,
                background: '#040e16',
                border: '1px solid #173c4d',
                fontSize: 11.5,
                color: '#9ce6f0',
                overflowX: 'auto',
                whiteSpace: 'pre-wrap',
              }}
            >
              {observation.sql}
            </pre>
            <div className="muted" style={{ marginTop: 6, fontSize: 11.5 }}>
              <div>
                {t.population}: {observation.population}
              </div>
              <div className="mono" title={observation.snapshot_sha256}>
                snapshot {observation.snapshot_sha256.slice(0, 16)}
              </div>
            </div>
          </div>

          <div>
            <div className="tile-label">
              {t.sourceRows} ({sampleRows.length}/{observation.source_rows.length})
            </div>
            {columns.length > 0 ? (
              <div className="table-wrap" style={{ maxHeight: 220, marginTop: 4 }}>
                <table>
                  <thead>
                    <tr>
                      {columns.map((c) => (
                        <th key={c}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sampleRows.map((row, idx) => (
                      <tr key={idx}>
                        {columns.map((c) => (
                          <td key={c} className="mono">
                            {String(row[c] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty">{t.noRows}</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
