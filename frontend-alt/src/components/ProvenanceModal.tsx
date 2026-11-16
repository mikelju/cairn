import React, { useEffect, useState } from 'react';
import { ParsedHighlightPage, ParsedProvenanceItem, fetchHighlightDetails } from '../api';
import { Locale, UI_TEXT } from '../i18n';
import { Icon, Spinner } from './Icon';

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
  const t = UI_TEXT[locale];
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

  const badgeLabel = item.kind === 'data' ? t.data_ : item.kind === 'quote' ? t.quote : t.decision;
  const pillCls = item.kind === 'quote' ? 'info' : item.kind === 'decision' ? 'warn' : '';

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head" style={{ marginBottom: 10 }}>
          <div className="row" style={{ gap: 10, flexWrap: 'nowrap' }}>
            <span className={`status-pill ${pillCls}`}>{badgeLabel}</span>
            <h2 style={{ fontSize: 17 }}>
              {item.text}
              {item.citation ? (
                <span style={{ color: 'var(--cyan2)', marginLeft: 8, fontSize: 13 }}>({item.citation})</span>
              ) : null}
            </h2>
          </div>
          <button className="icon-btn" onClick={onClose} title={t.close} aria-label={t.close}>
            <Icon name="x" size={14} />
          </button>
        </div>

        {item.facts && item.facts.length > 0 && (
          <div
            className="grid three"
            style={{
              gap: 8,
              marginBottom: 12,
              background: 'rgba(6, 20, 30, 0.7)',
              padding: 10,
              borderRadius: 10,
              border: '1px solid #1d4c60',
            }}
          >
            {item.facts.map((f, idx) => (
              <div key={idx}>
                <div className="tile-label">{f.label}</div>
                <div className="mono" style={{ fontSize: 12.5, color: '#fff', marginTop: 2 }}>
                  {f.value}
                </div>
              </div>
            ))}
          </div>
        )}

        {item.table && item.table.rows.length > 0 && (
          <div className="table-wrap" style={{ maxHeight: 240, marginBottom: 12 }}>
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
        )}

        {item.sourceRowsTable && item.sourceRowsTable.rows.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <button
              className="btn secondary sm"
              onClick={() => setShowSourceRows((s) => !s)}
              style={{ marginBottom: 8 }}
            >
              <Icon name="chevron" size={12} /> {t.sourceRows} · {item.sourceRowsTable.countLabel}
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
          <div>
            {item.officialHref && (
              <a
                href={item.officialHref}
                target="_blank"
                rel="noopener noreferrer"
                className="btn secondary sm"
                style={{ marginBottom: 8 }}
              >
                {t.openPdf} <Icon name="ext" size={12} />
              </a>
            )}
            {loadingHl && (
              <div className="center-pad">
                <Spinner />
              </div>
            )}
            {hlError && <div className="callout warn">{hlError}</div>}
            {highlightData?.pages.map((p, idx) => (
              <div
                key={idx}
                style={{
                  border: '1px solid #285d72',
                  borderRadius: 10,
                  padding: 8,
                  background: '#061520',
                  marginTop: 8,
                }}
              >
                <div className="row between muted" style={{ fontSize: 12, marginBottom: 6 }}>
                  <strong style={{ color: '#fff' }}>
                    {t.page} {p.page}
                  </strong>
                  <a href={p.imageUrl} target="_blank" rel="noopener noreferrer" title="PNG">
                    <Icon name="ext" size={12} />
                  </a>
                </div>
                <img
                  src={p.imageUrl}
                  alt={`${t.page} ${p.page}`}
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
          <div className="row" style={{ marginTop: 10, justifyContent: 'flex-end' }}>
            <button
              className="btn sm"
              onClick={() => {
                onClose();
                onGoToDecide();
              }}
            >
              {t.inspect} <Icon name="chevron" size={12} />
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
            <span key={idx} className="prov-hole">
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
          >
            <span>{part.text}</span>
            {part.citation && <span style={{ opacity: 0.85, fontSize: '0.9em' }}>({part.citation})</span>}
          </button>
        );
      })}
    </>
  );
};
