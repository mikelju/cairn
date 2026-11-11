import React, { useState } from 'react';
import { Observation } from '../api';
import { Locale } from '../i18n';

interface ObservationDrawerProps {
  observation: Observation<any> | null;
  locale: Locale;
}

export const ObservationDrawer: React.FC<ObservationDrawerProps> = ({ observation, locale }) => {
  const [open, setOpen] = useState(false);

  if (!observation) return null;

  const sampleRows = observation.source_rows.slice(0, 12);
  const columns = sampleRows.length > 0 ? Object.keys(sampleRows[0]) : [];

  return (
    <div
      style={{
        marginTop: 14,
        borderTop: '1px solid #1b485b',
        paddingTop: 12,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="chip">
            obs_id: <strong style={{ color: '#fff' }}>{observation.obs_id}</strong>
          </span>
          <span className="chip">
            sha256: <strong style={{ color: 'var(--cyan2)' }}>{observation.content_sha256.slice(0, 12)}…</strong>
          </span>
          <span className="chip">
            n_examined: <strong style={{ color: '#fff' }}>{observation.n_examined ?? 'n/a'}</strong>
          </span>
          <span className="chip">
            source_rows: <strong style={{ color: '#fff' }}>{observation.source_rows.length}</strong>
          </span>
        </div>
        <button className="btn secondary sm" onClick={() => setOpen((o) => !o)}>
          {open ? '▼' : '▶'}{' '}
          {locale === 'en'
            ? 'Inspect Typed Observation & Fixed SQL'
            : 'Inspeccionar Observation Tipada y SQL Fijo'}
        </button>
      </div>

      {open && (
        <div
          className="grid two"
          style={{
            marginTop: 12,
            padding: 14,
            borderRadius: 10,
            background: '#061520',
            border: '1px solid #1f5064',
          }}
        >
          <div>
            <div className="eyebrow">
              {locale === 'en'
                ? 'READ-ONLY DUCKDB SQL STATEMENT (NO FREE-FORM SQL)'
                : 'CONSULTA SQL FIJA EN DUCKDB (SOLO LECTURA)'}
            </div>
            <pre
              className="mono"
              style={{
                margin: 0,
                padding: 10,
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
            <div style={{ marginTop: 8, fontSize: 11.5, color: 'var(--muted)' }}>
              <div>
                <strong>Population:</strong> {observation.population}
              </div>
              <div>
                <strong>Snapshot SHA-256:</strong>{' '}
                <span className="mono">{observation.snapshot_sha256}</span>
              </div>
              <div>
                <strong>Content SHA-256:</strong>{' '}
                <span className="mono">{observation.content_sha256}</span>
              </div>
            </div>
          </div>

          <div>
            <div className="eyebrow">
              {locale === 'en'
                ? `SEND SOURCE ROWS (${observation.source_rows.length} TOTAL, SHOWING FIRST ${sampleRows.length})`
                : `FILAS FUENTE SEND (${observation.source_rows.length} TOTAL, MOSTRANDO ${sampleRows.length})`}
            </div>
            {columns.length > 0 ? (
              <div className="table-wrap" style={{ maxHeight: 220 }}>
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
              <div className="callout">No source rows attached.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
