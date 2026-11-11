import React, { useEffect, useState } from 'react';
import {
  ParsedHighlightPage,
  ParsedProvenanceItem,
  fetchHighlightDetails,
} from '../api';
import { Locale } from '../i18n';

interface ProvenanceModalProps {
  item: ParsedProvenanceItem | null;
  locale: Locale;
  onClose: () => void;
  onGoToDecide?: () => void;
}

export const ProvenanceModal: React.FC<ProvenanceModalProps> = ({
  item,
  locale,
  onClose,
  onGoToDecide,
}) => {
  const [highlightData, setHighlightData] = useState<ParsedHighlightPage | null>(null);
  const [loadingHl, setLoadingHl] = useState(false);
  const [hlError, setHlError] = useState('');
  const [showSourceRows, setShowSourceRows] = useState(false);

  useEffect(() => {
    setHighlightData(null);
    setHlError('');
    setShowSourceRows(false);
    if (item && item.kind === 'quote' && item.highlightHref) {
      setLoadingHl(true);
      fetchHighlightDetails(item.highlightHref)
        .then((res) => setHighlightData(res))
        .catch((err) => setHlError(err instanceof Error ? err.message : String(err)))
        .finally(() => setLoadingHl(false));
    }
  }, [item]);

  if (!item) return null;

  const badgeLabel =
    item.kind === 'data'
      ? locale === 'en'
        ? 'STUDY DATA PROVENANCE (PLACED BY CODE)'
        : 'PROCEDENCIA DE DATOS DEL ESTUDIO (COLOCADO POR CÓDIGO)'
      : item.kind === 'quote'
        ? locale === 'en'
          ? 'VERBATIM GUIDELINE CITATION'
          : 'CITA REGULATORIA LITERAL'
        : locale === 'en'
          ? 'RECORDED HUMAN SCIENTIFIC DECISION'
          : 'DECISIÓN CIENTÍFICA HUMANA REGISTRADA';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head" style={{ marginBottom: 12 }}>
          <div>
            <div className="eyebrow">{badgeLabel}</div>
            <h2 style={{ fontSize: 18, margin: 0 }}>
              {item.text}
              {item.citation ? (
                <span style={{ color: 'var(--cyan2)', marginLeft: 8, fontSize: 14 }}>
                  ({item.citation})
                </span>
              ) : null}
            </h2>
          </div>
          <button className="btn secondary sm" onClick={onClose}>
            {locale === 'en' ? 'Close' : 'Cerrar'} ✕
          </button>
        </div>

        {item.facts && item.facts.length > 0 && (
          <div
            className="grid three"
            style={{
              gap: 10,
              marginBottom: 14,
              background: 'rgba(6, 20, 30, 0.7)',
              padding: 12,
              borderRadius: 10,
              border: '1px solid #1d4c60',
            }}
          >
            {item.facts.map((f, idx) => (
              <div key={idx}>
                <div style={{ fontSize: 10.5, color: 'var(--muted)', textTransform: 'uppercase' }}>
                  {f.label}
                </div>
                <div className="mono" style={{ fontSize: 12.5, color: '#fff', marginTop: 2 }}>
                  {f.value}
                </div>
              </div>
            ))}
          </div>
        )}

        {item.table && item.table.rows.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                fontSize: 11.5,
                color: 'var(--cyan2)',
                fontFamily: 'var(--mono)',
                marginBottom: 6,
              }}
            >
              {locale === 'en'
                ? 'Deterministic Tool Result Table (Highlighted Cell = Placed Value)'
                : 'Tabla de Resultado Determinista (Celda Resaltada = Valor Colocado)'}
            </div>
            <div className="table-wrap" style={{ maxHeight: 240 }}>
              <table>
                <thead>
                  <tr>
                    {item.table.headers.map((h, i) => (
                      <th key={i}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {item.table.rows.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => {
                        const isHit =
                          item.table?.hitCell &&
                          item.table.hitCell[0] === rIdx &&
                          item.table.hitCell[1] === cIdx;
                        return (
                          <td key={cIdx} className={isHit ? 'hit' : ''}>
                            {cell}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {item.sourceRowsTable && item.sourceRowsTable.rows.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <button
              className="btn secondary sm"
              onClick={() => setShowSourceRows((s) => !s)}
              style={{ marginBottom: 8 }}
            >
              {showSourceRows ? '▼' : '▶'} {item.sourceRowsTable.countLabel} (SEND Domain Rows)
            </button>
            {showSourceRows && (
              <div className="table-wrap" style={{ maxHeight: 220 }}>
                <table>
                  <thead>
                    <tr>
                      {item.sourceRowsTable.headers.map((h, i) => (
                        <th key={i}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {item.sourceRowsTable.rows.map((row, rIdx) => (
                      <tr key={rIdx}>
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="mono">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {item.kind === 'quote' && (
          <div style={{ marginTop: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
                marginBottom: 10,
              }}
            >
              <span className="status-pill info">
                {locale === 'en'
                  ? 'Rule 8 Verified · Verbatim PDF Page Highlight'
                  : 'Regla 8 Verificada · Página PDF Oficial Resaltada'}
              </span>
              {item.officialHref && (
                <a
                  href={item.officialHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn secondary sm"
                >
                  {locale === 'en' ? 'Open Official PDF ↗' : 'Abrir PDF Oficial ↗'}
                </a>
              )}
            </div>
            {loadingHl && (
              <div className="callout">
                {locale === 'en'
                  ? 'Loading highlighted guideline page from /highlight/...'
                  : 'Cargando página resaltada de la guía desde /highlight/...'}
              </div>
            )}
            {hlError && <div className="callout warn">{hlError}</div>}
            {highlightData &&
              highlightData.pages.map((p, idx) => (
                <div
                  key={idx}
                  style={{
                    border: '1px solid #285d72',
                    borderRadius: 10,
                    padding: 10,
                    background: '#061520',
                    marginTop: 8,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: 12,
                      color: 'var(--muted)',
                      marginBottom: 8,
                    }}
                  >
                    <span>
                      {locale === 'en' ? 'Highlighted Source Page:' : 'Página Fuente Resaltada:'}{' '}
                      <strong style={{ color: '#fff' }}>p. {p.page}</strong>
                    </span>
                    <a href={p.imageUrl} target="_blank" rel="noopener noreferrer">
                      {locale === 'en' ? 'View Full PNG ↗' : 'Ver PNG Completo ↗'}
                    </a>
                  </div>
                  <img
                    src={p.imageUrl}
                    alt={`Highlighted page ${p.page}`}
                    style={{
                      width: '100%',
                      maxHeight: 420,
                      objectFit: 'contain',
                      borderRadius: 6,
                      background: '#fff',
                    }}
                  />
                </div>
              ))}
          </div>
        )}

        {item.kind === 'decision' && onGoToDecide && (
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn sm"
              onClick={() => {
                onClose();
                onGoToDecide();
              }}
            >
              {locale === 'en'
                ? 'Inspect / Modify in Scientific Assessment →'
                : 'Inspeccionar / Modificar en Evaluación Científica →'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

interface ProvenanceInlineProps {
  parts: ParsedProvenanceItem[];
  onSelect: (item: ParsedProvenanceItem) => void;
}

export const ProvenanceInline: React.FC<ProvenanceInlineProps> = ({ parts, onSelect }) => {
  return (
    <>
      {parts.map((part, idx) => {
        if (part.kind === 'text') {
          return <React.Fragment key={idx}>{part.text}</React.Fragment>;
        }
        if (part.kind === 'hole') {
          return (
            <span key={idx} className="prov-hole" title="Pending human decision">
              ⚠ {part.text}
            </span>
          );
        }
        return (
          <button
            key={idx}
            type="button"
            className={`prov-inline-btn ${part.kind}`}
            onClick={() => onSelect(part)}
            title={
              part.kind === 'data'
                ? 'Click to inspect DuckDB Observation & SEND rows'
                : part.kind === 'quote'
                  ? 'Click to view highlighted regulatory PDF page'
                  : 'Click to inspect recorded human decision'
            }
          >
            <span>{part.text}</span>
            {part.citation && (
              <span style={{ opacity: 0.85, fontSize: '0.9em' }}>({part.citation})</span>
            )}
          </button>
        );
      })}
    </>
  );
};
