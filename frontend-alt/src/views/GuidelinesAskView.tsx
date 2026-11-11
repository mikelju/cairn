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
import { ProvenanceInline } from '../components/ProvenanceModal';
import {
  CACHED_SEARCH_PRESETS,
  Locale,
  PINNED_GUIDELINES,
  PRESET_QUESTIONS,
} from '../i18n';

interface GuidelinesAskViewProps {
  locale: Locale;
  onSelectProvenance: (item: ParsedProvenanceItem) => void;
}

export const GuidelinesAskView: React.FC<GuidelinesAskViewProps> = ({
  locale,
  onSelectProvenance,
}) => {
  // Ask CAIRN state
  const [askCategory, setAskCategory] = useState<'all' | 'study' | 'guideline' | 'guardrail' | 'live'>('all');
  const [selectedQ, setSelectedQ] = useState<string>('Q2');
  const [askRes, setAskRes] = useState<ParsedAskResult | null>(null);
  const [loadingAsk, setLoadingAsk] = useState(false);

  // Live Explore state
  const [liveQuestion, setLiveQuestion] = useState(
    'Which histopathology findings increase with dose in females?',
  );
  const [liveCode, setLiveCode] = useState('');
  const [liveRes, setLiveRes] = useState<ParsedAskResult | null>(null);
  const [loadingLive, setLoadingLive] = useState(false);

  // Search Guidance tool state
  const [searchQuery, setSearchQuery] = useState<string>(CACHED_SEARCH_PRESETS[0].query);
  const [guidanceRes, setGuidanceRes] = useState<SearchGuidanceResult | null>(null);
  const [guidanceErr, setGuidanceErr] = useState<string>('');
  const [loadingGuidance, setLoadingGuidance] = useState(false);

  useEffect(() => {
    handleSelectQuestion('Q2');
    handleRunSearch(CACHED_SEARCH_PRESETS[0].query);
  }, []);

  const handleSelectQuestion = async (qId: string) => {
    setSelectedQ(qId);
    setLoadingAsk(true);
    try {
      const res = await runRecordedQuestion(qId);
      setAskRes(res);
    } finally {
      setLoadingAsk(false);
    }
  };

  const handleRunLive = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoadingLive(true);
    try {
      const res = await runLiveExploreQuestion(liveQuestion, liveCode);
      setLiveRes(res);
    } finally {
      setLoadingLive(false);
    }
  };

  const handleRunSearch = async (q: string) => {
    setSearchQuery(q);
    setLoadingGuidance(true);
    setGuidanceErr('');
    try {
      const res = await fetchSearchGuidance(q);
      setGuidanceRes(res);
    } catch (err) {
      if (err instanceof ApiError) {
        setGuidanceErr(`HTTP ${err.status}: ${err.detail}`);
      } else {
        setGuidanceErr(String(err));
      }
      setGuidanceRes(null);
    } finally {
      setLoadingGuidance(false);
    }
  };

  const filteredQuestions = PRESET_QUESTIONS.filter(
    (q) => askCategory === 'all' || askCategory === 'live' || q.category === askCategory,
  );
  const currentQObj = PRESET_QUESTIONS.find((q) => q.id === selectedQ);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 2 & 3 · PINNED REGULATORY GUIDANCE & VERIFIED AGENT Q&A'
              : 'ETAPA 2 Y 3 · GUÍAS REGULATORIAS FIJADAS Y Q&A AGÉNTICO VERIFICADO'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Regulatory Library, Hybrid Retrieval & Ask CAIRN'
              : 'Biblioteca Regulatoria, Búsqueda Híbrida y Preguntar a CAIRN'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'Every answer is verified by 8 deterministic rules before display: numbers are placed from DuckDB Observations and quotations are linked to highlighted official FDA/ICH PDF pages.'
              : 'Cada respuesta pasa por 8 reglas deterministas antes de mostrarse: las cifras provienen de DuckDB y las citas enlazan con páginas resaltadas de los PDFs oficiales FDA/ICH.'}
          </p>
        </div>
        <div className="head-actions">
          <button
            className="btn secondary sm"
            disabled
            title="Disabled in public demo (guidelines are SHA-256 pinned in data/guidelines/manifest.json)"
          >
            + {locale === 'en' ? 'Upload Guideline PDF' : 'Subir Guía PDF'}{' '}
            <span className="prod-badge" style={{ marginLeft: 6 }}>
              PROD PREVIEW
            </span>
          </button>
        </div>
      </div>

      {/* 4 Pinned Guidelines Grid */}
      <div className="grid four">
        {PINNED_GUIDELINES.map((g) => (
          <div key={g.id} className="panel" style={{ padding: 15 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="status-pill info">{g.code}</span>
              <a
                href={g.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 11.5, fontFamily: 'var(--mono)' }}
              >
                PDF ↗
              </a>
            </div>
            <h3 style={{ fontSize: 13.5, margin: '10px 0 6px', color: '#fff' }}>{g.title}</h3>
            <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 10px' }}>
              {g.scope[locale]}
            </p>
            <div
              className="mono"
              style={{
                fontSize: 10.5,
                color: 'var(--cyan2)',
                borderTop: '1px solid #194355',
                paddingTop: 8,
              }}
            >
              SHA-256: {g.sha256.slice(0, 16)}… ({Math.round(g.bytes / 1024)} KB)
            </div>
          </div>
        ))}
      </div>

      {/* Ask CAIRN Interactive Evaluation Surface */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? 'Ask CAIRN — Verified Answer vs. Raw AI Output (POST /ask/run)'
                : 'Preguntar a CAIRN — Respuesta Verificada vs. Plantilla IA (POST /ask/run)'}
            </h2>
            <p>
              {locale === 'en'
                ? 'Select any study question, regulatory query, or adversarial trick question to inspect the agentic verification loop'
                : 'Selecciona cualquier pregunta del estudio, consulta regulatoria o pregunta trampa para inspeccionar el bucle de verificación'}
            </p>
          </div>
          <div className="seg-group">
            {(
              [
                { id: 'all', label: locale === 'en' ? 'All Presets (13)' : 'Todas (13)' },
                { id: 'study', label: locale === 'en' ? 'Study Data (Q1-Q5)' : 'Datos Estudio' },
                {
                  id: 'guideline',
                  label: locale === 'en' ? 'Guidelines (G1-G3, NS)' : 'Guías (G1-G3, NS)',
                },
                {
                  id: 'guardrail',
                  label: locale === 'en' ? 'Guardrails / Tricks (Q4, Q6-Q8)' : 'Guardarraíles',
                },
                {
                  id: 'live',
                  label: locale === 'en' ? '⚡ Live Bedrock (/explore/live)' : '⚡ Bedrock en Vivo',
                },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`seg-btn ${askCategory === tab.id ? 'active' : ''}`}
                onClick={() => setAskCategory(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {askCategory === 'live' ? (
          <div
            style={{
              padding: 16,
              borderRadius: 12,
              background: '#071926',
              border: '1px solid #23586e',
            }}
          >
            <div className="eyebrow">
              {locale === 'en'
                ? 'OPTIONAL LIVE BEDROCK QUERY (POST /explore/live)'
                : 'CONSULTA OPCIONAL EN VIVO A BEDROCK (POST /explore/live)'}
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--muted)', marginBottom: 12 }}>
              {locale === 'en'
                ? 'Protected by CAIRN_ACCESS_CODE and a daily USD spend cap. Without an access code configured on the server, the endpoint returns its controlled refusal message.'
                : 'Protegido por CAIRN_ACCESS_CODE y un límite de gasto diario en USD. Sin código configurado en el servidor, el endpoint devuelve su mensaje de rechazo controlado.'}
            </p>
            <form
              onSubmit={handleRunLive}
              style={{ display: 'grid', gridTemplateColumns: '1fr 200px auto', gap: 10 }}
            >
              <input
                type="text"
                className="input"
                value={liveQuestion}
                onChange={(e) => setLiveQuestion(e.target.value)}
                maxLength={500}
                placeholder="Ask a question (max 500 chars)…"
              />
              <input
                type="password"
                className="input"
                value={liveCode}
                onChange={(e) => setLiveCode(e.target.value)}
                placeholder="Access code (CAIRN_ACCESS_CODE)"
              />
              <button type="submit" className="btn violet" disabled={loadingLive}>
                {loadingLive ? 'Running…' : 'Ask Live Bedrock'}
              </button>
            </form>
            {liveRes && (
              <div style={{ marginTop: 14 }}>
                {liveRes.refused ? (
                  <div className="callout warn">
                    <strong>POST /explore/live response:</strong> {liveRes.refused}
                  </div>
                ) : (
                  <div className="callout success">
                    <ProvenanceInline
                      parts={liveRes.verifiedParts}
                      onSelect={onSelectProvenance}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Question Selector Pills */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(265px, 1fr))',
                gap: 8,
                marginBottom: 16,
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
                      padding: '10px 12px',
                      borderRadius: 10,
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
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 4,
                      }}
                    >
                      <strong className="mono" style={{ color: 'var(--cyan2)', fontSize: 12 }}>
                        {q.id}
                      </strong>
                      <span
                        className={`status-pill ${
                          isTrick ? 'block' : q.category === 'guideline' ? 'info' : ''
                        }`}
                        style={{ padding: '1px 7px', fontSize: 10 }}
                      >
                        {q.badge}
                      </span>
                    </div>
                    <div style={{ fontSize: 12.5, lineHeight: 1.38 }}>{q.text[locale]}</div>
                  </button>
                );
              })}
            </div>

            {/* Active Question Result */}
            {currentQObj && (
              <div
                style={{
                  padding: 16,
                  borderRadius: 12,
                  background: '#071824',
                  border: '1px solid #215368',
                  opacity: loadingAsk ? 0.6 : 1,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 12,
                    flexWrap: 'wrap',
                    gap: 8,
                  }}
                >
                  <div>
                    <span className="eyebrow" style={{ marginRight: 10 }}>
                      QUESTION {currentQObj.id}
                    </span>
                    <strong style={{ fontSize: 15, color: '#fff' }}>
                      {currentQObj.text[locale]}
                    </strong>
                    <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
                      {currentQObj.note[locale]}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span className="chip" style={{ borderColor: '#28766e', color: '#8ef5d8' }}>
                      ■ DATA (Placed by Code)
                    </span>
                    <span className="chip" style={{ borderColor: '#6f58b8', color: '#ded2ff' }}>
                      ■ CITATION (Click for PDF Highlight)
                    </span>
                  </div>
                </div>

                {askRes?.calloutText && (
                  <div
                    className={`callout ${
                      askRes.calloutKind === 'blocked' ? 'danger' : 'warn'
                    }`}
                    style={{ marginBottom: 12 }}
                  >
                    <strong>
                      {askRes.calloutKind === 'blocked'
                        ? locale === 'en'
                          ? 'Guardrail / Verifier Blocked Unverified Output: '
                          : 'Guardarraíl / Verificador Bloqueó Salida No Verificada: '
                        : ''}
                    </strong>
                    {askRes.calloutText}
                    {askRes.calloutList && askRes.calloutList.length > 0 && (
                      <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
                        {askRes.calloutList.map((li, i) => (
                          <li key={i}>{li}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {askRes && askRes.verifiedParts.length > 0 && (
                  <div className={askRes.aiWritten ? 'grid two' : 'stack'}>
                    <div
                      style={{
                        padding: 15,
                        borderRadius: 10,
                        background: 'rgba(13, 41, 58, 0.85)',
                        border: '1px solid #266b80',
                      }}
                    >
                      <div className="eyebrow" style={{ color: 'var(--green)' }}>
                        {locale === 'en'
                          ? '✓ VERIFIED ANSWER (NUMBERS & QUOTES PLACED BY CODE — CLICK ANY CHIP)'
                          : '✓ RESPUESTA VERIFICADA (CIFRAS Y CITAS COLOCADAS POR CÓDIGO — CLIC EN CHIPS)'}
                      </div>
                      <div style={{ fontSize: 14, lineHeight: 1.78, color: '#eef8fb' }}>
                        <ProvenanceInline
                          parts={askRes.verifiedParts}
                          onSelect={onSelectProvenance}
                        />
                      </div>
                    </div>

                    {askRes.aiWritten && (
                      <div
                        style={{
                          padding: 15,
                          borderRadius: 10,
                          background: 'rgba(8, 22, 33, 0.9)',
                          border: '1px dashed #2b5d73',
                        }}
                      >
                        <div className="eyebrow" style={{ color: 'var(--cyan2)' }}>
                          {locale === 'en'
                            ? 'RAW AI SKELETON (WHAT THE MODEL WROTE — 0 DIGITS)'
                            : 'ESQUELETO CRUDO DE LA IA (LO QUE ESCRIBIÓ EL MODELO — 0 DÍGITOS)'}
                        </div>
                        <div
                          className="mono"
                          style={{
                            fontSize: 12.5,
                            lineHeight: 1.7,
                            color: '#a3c3d1',
                          }}
                        >
                          {askRes.aiWritten}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Screening Table or Evidence Trace if returned */}
                {askRes?.screeningTable && (
                  <div style={{ marginTop: 14 }}>
                    <div className="eyebrow">
                      {locale === 'en'
                        ? 'ATTACHED HISTOPATHOLOGY SCREENING TABLE'
                        : 'TABLA ADJUNTA DE CRIBADO HISTOPATOLÓGICO'}
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            {askRes.screeningTable.headers.map((h, i) => (
                              <th key={i}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {askRes.screeningTable.rows.map((r, rIdx) => (
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
                  </div>
                )}

                {askRes && askRes.evidenceTraces.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 10,
                      borderTop: '1px solid #194456',
                      fontSize: 12,
                      color: 'var(--muted)',
                      fontFamily: 'var(--mono)',
                    }}
                  >
                    <strong>Tool Execution Trace:</strong> {askRes.evidenceTraces.join('  |  ')}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Hybrid Retrieval Inspector (POST /api/tools/search_guidance) */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? 'Hybrid Guideline Retrieval & Reranker Inspector (search_guidance)'
                : 'Inspector de Búsqueda Híbrida y Reranker (search_guidance)'}
            </h2>
            <p>
              {locale === 'en'
                ? 'BM25 lexical + BGE-small-en-v1.5 semantic embeddings -> Reciprocal Rank Fusion (k=60) -> BGE-reranker-v2-m3 cross-encoder'
                : 'BM25 léxico + embeddings BGE-small-en-v1.5 -> Reciprocal Rank Fusion (k=60) -> Cross-encoder BGE-reranker-v2-m3'}
            </p>
          </div>
          <span className="chip">POST /api/tools/search_guidance</span>
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
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

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleRunSearch(searchQuery);
          }}
          style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 10, marginBottom: 14 }}
        >
          <input
            type="text"
            className="input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Select a cached query above or test an uncached query string…"
          />
          <button type="submit" className="btn secondary" disabled={loadingGuidance}>
            {loadingGuidance
              ? 'Searching…'
              : locale === 'en'
                ? 'Execute search_guidance'
                : 'Ejecutar search_guidance'}
          </button>
        </form>

        {guidanceErr && (
          <div className="callout warn">
            <strong>
              {locale === 'en'
                ? 'Deterministic Replay Cache Enforcement: '
                : 'Control de Caché Determinista en Modo Replay: '}
            </strong>
            {guidanceErr} —{' '}
            {locale === 'en'
              ? 'In replay mode, search_guidance serves precomputed cross-encoder rankings without loading ONNX weights into memory. Click any preset above to inspect its cached top-5 passages.'
              : 'En modo replay, search_guidance sirve rankings precalculados sin cargar pesos ONNX. Haz clic en cualquier botón superior para ver los 5 pasajes principales.'}
          </div>
        )}

        {guidanceRes && (
          <div className="stack">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className={`status-pill ${guidanceRes.abstained ? 'block' : ''}`}>
                {guidanceRes.abstained ? 'ABSTAINED (Below Threshold)' : 'IN-LIBRARY MATCH'}
              </span>
              <span className="chip">
                Best Rerank Score:{' '}
                <strong style={{ color: 'var(--green)' }}>
                  {guidanceRes.best_score.toFixed(4)}
                </strong>
              </span>
              <span className="chip">
                Abstention Threshold:{' '}
                <strong style={{ color: 'var(--amber)' }}>
                  {guidanceRes.threshold.toFixed(4)}
                </strong>
              </span>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rerank #</th>
                    <th>Passage ID</th>
                    <th>Document & Section</th>
                    <th className="num">Pages</th>
                    <th className="num">BM25 Rank</th>
                    <th className="num">Dense Rank</th>
                    <th className="num">RRF Rank</th>
                    <th className="num">Cross-Encoder Score</th>
                    <th>Verbatim Passage & Sentence IDs</th>
                  </tr>
                </thead>
                <tbody>
                  {guidanceRes.hits.map((h) => (
                    <tr key={h.passage_id}>
                      <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                        #{h.rerank_rank}
                      </td>
                      <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>
                        {h.passage_id}
                      </td>
                      <td>
                        <strong>{h.doc.toUpperCase()}</strong> · Sec. {h.section}
                      </td>
                      <td className="num">
                        p. {h.page_start}
                        {h.page_end !== h.page_start ? `–${h.page_end}` : ''}
                      </td>
                      <td className="num">{h.lexical_rank ?? '—'}</td>
                      <td className="num">{h.semantic_rank ?? '—'}</td>
                      <td className="num">#{h.fused_rank}</td>
                      <td
                        className="num"
                        style={{
                          color:
                            h.rerank_score >= guidanceRes.threshold
                              ? 'var(--green)'
                              : 'var(--amber)',
                          fontWeight: 700,
                        }}
                      >
                        {h.rerank_score.toFixed(4)}
                      </td>
                      <td style={{ maxWidth: 460 }}>
                        <div style={{ fontSize: 12, color: '#d7eaf1' }}>
                          {h.sentences.map((s) => (
                            <span key={s.sentence_id} style={{ marginRight: 6 }}>
                              <span
                                className="mono"
                                style={{
                                  fontSize: 10.5,
                                  color: 'var(--cyan2)',
                                  marginRight: 3,
                                }}
                              >
                                [{s.sentence_id}]
                              </span>
                              {s.text}
                            </span>
                          ))}
                        </div>
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
