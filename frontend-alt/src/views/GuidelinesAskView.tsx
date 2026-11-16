import React, { useEffect, useState } from 'react';
import {
  ApiError,
  ParsedAskResult,
  ParsedProvenanceItem,
  SearchGuidanceResult,
  fetchSearchGuidance,
  runLiveExploreQuestion,
  runRecordedQuestion,
} from '../api';
import { Icon, Spinner } from '../components/Icon';
import { ProvenanceInline } from '../components/ProvenanceModal';
import {
  CACHED_SEARCH_PRESETS,
  Locale,
  PINNED_GUIDELINES,
  PRESET_QUESTIONS,
  UI_TEXT,
  UiText,
} from '../i18n';

interface GuidelinesAskViewProps {
  locale: Locale;
  onSelectProvenance: (item: ParsedProvenanceItem) => void;
}

type AskTab = 'all' | 'study' | 'guideline' | 'guardrail' | 'live';

const AskBody: React.FC<{
  res: ParsedAskResult;
  t: UiText;
  onSelect: (item: ParsedProvenanceItem) => void;
}> = ({ res, t, onSelect }) => {
  if (res.refused || res.stale) {
    return <div className="callout warn">{res.refused || res.stale}</div>;
  }
  return (
    <div className="stack">
      {res.calloutText && (
        <div className={`callout ${res.calloutKind === 'blocked' ? 'danger' : 'warn'}`}>
          {res.calloutKind === 'blocked' && (
            <strong>
              <Icon name="lock" size={13} /> {t.blocked}:{' '}
            </strong>
          )}
          {res.calloutText}
          {res.calloutList && res.calloutList.length > 0 && (
            <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
              {res.calloutList.map((li, i) => (
                <li key={i}>{li}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {res.verifiedParts.length > 0 && (
        <div className={res.aiWritten ? 'grid two' : 'stack'}>
          <div className="tile ok">
            <div className="tile-label" style={{ color: 'var(--green)', marginBottom: 6 }}>
              <Icon name="check" size={12} /> {t.verified}
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.75, color: '#eef8fb' }}>
              <ProvenanceInline parts={res.verifiedParts} onSelect={onSelect} />
            </div>
          </div>
          {res.aiWritten && (
            <div className="tile" style={{ borderStyle: 'dashed' }}>
              <div className="tile-label" style={{ marginBottom: 6 }}>
                {t.modelDraft}
              </div>
              <div className="mono" style={{ fontSize: 12, lineHeight: 1.7, color: '#a3c3d1' }}>
                {res.aiWritten}
              </div>
            </div>
          )}
        </div>
      )}

      {res.screeningTable && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {res.screeningTable.headers.map((h, i) => (
                  <th key={i}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {res.screeningTable.rows.map((r, rIdx) => (
                <tr key={rIdx}>
                  {r.map((c, cIdx) => (
                    <td key={cIdx} className={cIdx >= 2 ? 'mono' : ''}>
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {res.evidenceTraces.length > 0 && (
        <div className="row" style={{ gap: 6 }}>
          <span className="tile-label">{t.trace}</span>
          {res.evidenceTraces.map((tr, i) => (
            <span key={i} className="chip" style={{ whiteSpace: 'normal' }}>
              {tr}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

export const GuidelinesAskView: React.FC<GuidelinesAskViewProps> = ({ locale, onSelectProvenance }) => {
  const t = UI_TEXT[locale];

  const [askTab, setAskTab] = useState<AskTab>('all');
  const [selectedQ, setSelectedQ] = useState<string>('Q2');
  const [askRes, setAskRes] = useState<ParsedAskResult | null>(null);
  const [loadingAsk, setLoadingAsk] = useState(false);

  const [liveQuestion, setLiveQuestion] = useState('Which histopathology findings increase with dose in females?');
  const [liveCode, setLiveCode] = useState('');
  const [liveRes, setLiveRes] = useState<ParsedAskResult | null>(null);
  const [loadingLive, setLoadingLive] = useState(false);

  const [searchQuery, setSearchQuery] = useState<string>(CACHED_SEARCH_PRESETS[0].query);
  const [guidanceRes, setGuidanceRes] = useState<SearchGuidanceResult | null>(null);
  const [guidanceErr, setGuidanceErr] = useState<string>('');
  const [loadingGuidance, setLoadingGuidance] = useState(false);

  useEffect(() => {
    handleRunSearch(CACHED_SEARCH_PRESETS[0].query);
  }, []);

  // Backend text follows the active language: refetch the recorded answer on toggle.
  useEffect(() => {
    handleSelectQuestion(selectedQ);
  }, [locale]);

  const handleSelectQuestion = async (qId: string) => {
    setSelectedQ(qId);
    setLoadingAsk(true);
    try {
      setAskRes(await runRecordedQuestion(qId, locale));
    } catch (err) {
      setAskRes({
        refused: err instanceof ApiError ? `HTTP ${err.status}: ${err.detail}` : String(err),
        verifiedParts: [],
        aiWritten: '',
        evidenceRows: [],
        evidenceTraces: [],
      });
    } finally {
      setLoadingAsk(false);
    }
  };

  const handleRunLive = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoadingLive(true);
    try {
      setLiveRes(await runLiveExploreQuestion(liveQuestion, liveCode, locale));
    } catch (err) {
      setLiveRes({
        refused: err instanceof ApiError ? `HTTP ${err.status}: ${err.detail}` : String(err),
        verifiedParts: [],
        aiWritten: '',
        evidenceRows: [],
        evidenceTraces: [],
      });
    } finally {
      setLoadingLive(false);
    }
  };

  const handleRunSearch = async (q: string) => {
    setSearchQuery(q);
    setLoadingGuidance(true);
    setGuidanceErr('');
    try {
      setGuidanceRes(await fetchSearchGuidance(q));
    } catch (err) {
      setGuidanceErr(err instanceof ApiError ? `HTTP ${err.status}: ${err.detail}` : String(err));
      setGuidanceRes(null);
    } finally {
      setLoadingGuidance(false);
    }
  };

  const filteredQuestions = PRESET_QUESTIONS.filter((q) => askTab === 'all' || askTab === 'live' || q.category === askTab);
  const currentQObj = PRESET_QUESTIONS.find((q) => q.id === selectedQ);

  const tabs: Array<{ id: AskTab; label: string }> = [
    { id: 'all', label: t.catAll },
    { id: 'study', label: t.catStudy },
    { id: 'guideline', label: t.catGuideline },
    { id: 'guardrail', label: t.catGuardrail },
    { id: 'live', label: t.catLive },
  ];

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{t.guidelines}</h1>
        <div className="head-actions">
          <button className="btn secondary sm" disabled title={t.prodTip}>
            <Icon name="upload" size={13} /> {t.upGuideline}
            <span className="prod-badge">{t.production}</span>
          </button>
        </div>
      </div>

      <div className="grid four">
        {PINNED_GUIDELINES.map((g) => (
          <div key={g.id} className="tile">
            <div className="row between">
              <span className="status-pill info">{g.code}</span>
              <a href={g.url} target="_blank" rel="noopener noreferrer" title="PDF">
                <Icon name="ext" size={13} />
              </a>
            </div>
            <div style={{ fontSize: 12.5, margin: '8px 0 6px', color: '#fff' }}>{g.title}</div>
            <div className="mono muted" style={{ fontSize: 10.5 }} title={g.sha256}>
              {g.sha256.slice(0, 12)} · {Math.round(g.bytes / 1024)} KB
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        <div className="panel-head">
          <div className="seg-group">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`seg-btn ${askTab === tab.id ? 'active' : ''}`}
                onClick={() => setAskTab(tab.id)}
              >
                {tab.id === 'live' && '⚡ '}
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {askTab === 'live' ? (
          <div className="stack">
            <form onSubmit={handleRunLive} style={{ display: 'grid', gridTemplateColumns: '1fr 180px auto', gap: 8 }}>
              <input
                type="text"
                className="input"
                value={liveQuestion}
                onChange={(e) => setLiveQuestion(e.target.value)}
                maxLength={500}
                placeholder={t.liveQ}
              />
              <input
                type="password"
                className="input"
                value={liveCode}
                onChange={(e) => setLiveCode(e.target.value)}
                placeholder={t.accessCode}
              />
              <button type="submit" className="btn violet" disabled={loadingLive}>
                {loadingLive ? <Spinner /> : <Icon name="bolt" size={13} />} {t.ask}
              </button>
            </form>
            {liveRes && <AskBody res={liveRes} t={t} onSelect={onSelectProvenance} />}
          </div>
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                gap: 6,
                marginBottom: 12,
              }}
            >
              {filteredQuestions.map((q) => {
                const isSelected = q.id === selectedQ;
                const isTrick = q.category === 'guardrail';
                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => handleSelectQuestion(q.id)}
                    style={{
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: 9,
                      border: isSelected
                        ? '1px solid var(--cyan)'
                        : isTrick
                          ? '1px solid #6b3c46'
                          : '1px solid #1e4b5e',
                      background: isSelected
                        ? 'linear-gradient(135deg, rgba(41, 215, 212, 0.18), rgba(16, 48, 66, 0.9))'
                        : 'rgba(9, 28, 41, 0.75)',
                      color: '#e6f5fa',
                    }}
                  >
                    <div className="row between" style={{ marginBottom: 3 }}>
                      <strong className="mono" style={{ color: 'var(--cyan2)', fontSize: 11.5 }}>
                        {q.id}
                      </strong>
                      <span
                        className={`status-pill ${isTrick ? 'block' : q.category === 'guideline' ? 'info' : ''}`}
                        style={{ padding: '0 7px', fontSize: 10 }}
                      >
                        {q.badge}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, lineHeight: 1.35 }}>{q.text[locale]}</div>
                  </button>
                );
              })}
            </div>

            {currentQObj && (
              <div className={`stack ${loadingAsk ? 'busy' : ''}`}>
                <div className="row between">
                  <strong style={{ fontSize: 14, color: '#fff' }}>
                    <span className="mono muted" style={{ marginRight: 8 }}>
                      {currentQObj.id}
                    </span>
                    {currentQObj.text[locale]}
                  </strong>
                  {loadingAsk && <Spinner />}
                </div>
                {askRes && <AskBody res={askRes} t={t} onSelect={onSelectProvenance} />}
              </div>
            )}
          </>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t.retrieval}</h2>
          <div className="row" style={{ gap: 4 }}>
            {CACHED_SEARCH_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`btn sm ${searchQuery === p.query ? '' : 'secondary'}`}
                onClick={() => handleRunSearch(p.query)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleRunSearch(searchQuery);
          }}
          style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginBottom: 12 }}
        >
          <input
            type="text"
            className="input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="btn secondary" disabled={loadingGuidance}>
            {loadingGuidance ? <Spinner /> : <Icon name="chevron" size={13} />} {t.search}
          </button>
        </form>

        {guidanceErr && <div className="callout warn">{guidanceErr}</div>}

        {guidanceRes && (
          <div className="stack">
            <div className="row">
              <span className={`status-pill ${guidanceRes.abstained ? 'block' : ''}`}>
                {guidanceRes.abstained ? t.abstained : t.match}
              </span>
              <span className="chip">
                {t.bestScore} <strong style={{ color: 'var(--green)' }}>{guidanceRes.best_score.toFixed(4)}</strong>
              </span>
              <span className="chip">
                {t.threshold} <strong style={{ color: 'var(--amber)' }}>{guidanceRes.threshold.toFixed(4)}</strong>
              </span>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t.passage}</th>
                    <th>{t.doc}</th>
                    <th className="num">{t.pages}</th>
                    <th className="num">BM25</th>
                    <th className="num">Dense</th>
                    <th className="num">RRF</th>
                    <th className="num">{t.score}</th>
                    <th>{t.text}</th>
                  </tr>
                </thead>
                <tbody>
                  {guidanceRes.hits.map((h) => (
                    <tr key={h.passage_id}>
                      <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                        {h.rerank_rank}
                      </td>
                      <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>
                        {h.passage_id}
                      </td>
                      <td>
                        <strong>{h.doc.toUpperCase()}</strong> · {h.section}
                      </td>
                      <td className="num">
                        {h.page_start}
                        {h.page_end !== h.page_start ? `–${h.page_end}` : ''}
                      </td>
                      <td className="num">{h.lexical_rank ?? '—'}</td>
                      <td className="num">{h.semantic_rank ?? '—'}</td>
                      <td className="num">{h.fused_rank}</td>
                      <td
                        className="num"
                        style={{
                          color: h.rerank_score >= guidanceRes.threshold ? 'var(--green)' : 'var(--amber)',
                          fontWeight: 700,
                        }}
                      >
                        {h.rerank_score.toFixed(4)}
                      </td>
                      <td style={{ maxWidth: 460, fontSize: 12, color: '#d7eaf1' }}>
                        {h.sentences.map((s) => (
                          <span key={s.sentence_id} style={{ marginRight: 6 }}>
                            <span className="mono" style={{ fontSize: 10.5, color: 'var(--cyan2)', marginRight: 3 }}>
                              [{s.sentence_id}]
                            </span>
                            {s.text}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
