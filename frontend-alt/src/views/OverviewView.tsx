import React, { useEffect, useState } from 'react';
import {
  AuditVerifyResponse,
  ParsedAskResult,
  ParsedProvenanceItem,
  ThreadView,
  ViewId,
  runRecordedQuestion,
} from '../api';
import { ProvenanceInline } from '../components/ProvenanceModal';
import { Locale } from '../i18n';

interface OverviewViewProps {
  locale: Locale;
  thread: ThreadView | null;
  audit: AuditVerifyResponse | null;
  onNavigate: (view: ViewId) => void;
  onSelectProvenance: (item: ParsedProvenanceItem) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  locale,
  thread,
  audit,
  onNavigate,
  onSelectProvenance,
}) => {
  const [sampleAsk, setSampleAsk] = useState<ParsedAskResult | null>(null);
  const [activeStage, setActiveStage] = useState<number>(2);

  useEffect(() => {
    runRecordedQuestion('Q3')
      .then((res) => setSampleAsk(res))
      .catch(() => {});
  }, []);

  const fConfirmed = thread?.confirmed.includes('F') ?? false;
  const mConfirmed = thread?.confirmed.includes('M') ?? false;
  const fNoael = thread?.noael?.F?.dose;
  const mNoael = thread?.noael?.M?.dose;

  const stages = [
    {
      num: 1,
      title: locale === 'en' ? '1. Study Data (SEND)' : '1. Datos del Estudio (SEND)',
      sub: locale === 'en' ? 'DuckDB + Pandera Quarantine' : 'DuckDB + Cuarentena Pandera',
      view: 'study' as ViewId,
      detail:
        locale === 'en'
          ? 'Ingests 8 CDISC SEND domains (DM, TX, TS, DS, MI, BW, PP, PC) from PhUSE PDS2014. Normalizes XPT float zeros and quarantines 12 physically impossible negative AUC rows before any tool can read them.'
          : 'Ingiere 8 dominios CDISC SEND (DM, TX, TS, DS, MI, BW, PP, PC) de PhUSE PDS2014. Normaliza ceros flotantes XPT y pone en cuarentena 12 filas de AUC negativas físicamente imposibles antes de que las herramientas las lean.',
    },
    {
      num: 2,
      title: locale === 'en' ? '2. AI Agent (Claude)' : '2. Agente IA (Claude)',
      sub: locale === 'en' ? 'Tool Selection & Prose Skeleton' : 'Selección de Herramientas y Estructura',
      view: 'guidelines' as ViewId,
      detail:
        locale === 'en'
          ? 'Claude calls read-only typed tools (study_design, incidence, body_weight_change, tk_summary, search_guidance) and emits structured Sentence objects containing ValueRef, QuoteRef and DecisionRef—never raw numbers.'
          : 'Claude invoca herramientas tipadas de solo lectura y emite objetos Sentence estructurados con ValueRef, QuoteRef y DecisionRef, sin escribir jamás un solo dígito.',
    },
    {
      num: 3,
      title: locale === 'en' ? '3. Deterministic Verifier' : '3. Verificador Determinista',
      sub: locale === 'en' ? '8 Code Rules + Calibrated Judge' : '8 Reglas de Código + Juez Calibrado',
      view: 'data' as ViewId,
      detail:
        locale === 'en'
          ? 'Code resolves every reference against the ObservationLedger and applies 8 deterministic rules (0 AI digits, mandatory denominators, quarantine disclosure, no unconfirmed NOAEL, verbatim quotes) plus a calibrated Sonnet 4.6 Judge.'
          : 'El código resuelve cada referencia contra el ObservationLedger y aplica 8 reglas deterministas (0 dígitos por IA, denominadores obligatorios, aviso de cuarentena, citas literales) más un Juez Sonnet 4.6 calibrado.',
    },
    {
      num: 4,
      title: locale === 'en' ? '4. Human-in-the-Loop' : '4. Decisión Humana (NOAEL)',
      sub: locale === 'en' ? 'Role-Gated Adversity & NOAEL' : 'Adversidad y NOAEL por Rol',
      view: 'assessment' as ViewId,
      detail:
        locale === 'en'
          ? 'LangGraph pauses at await_decisions. Only R. Reviewer can classify treatment-related and adverse onset doses across slots D1–D11 and confirm the deterministically derived NOAEL per sex.'
          : 'LangGraph se pausa en await_decisions. Solo R. Reviewer puede clasificar las dosis relacionadas con el tratamiento y adversas en D1–D11 y confirmar el NOAEL calculado por código.',
    },
    {
      num: 5,
      title: locale === 'en' ? '5. CTD 2.6.6.3 & Audit' : '5. Informe CTD 2.6.6.3 y Auditoría',
      sub: locale === 'en' ? 'Electronic Sign-Off & SHA-256 Chain' : 'Firma Electrónica y Cadena SHA-256',
      view: 'report' as ViewId,
      detail:
        locale === 'en'
          ? 'Produces the regulatory CTD 2.6.6.3 Written Summary with clickable provenance chips, enforces separation of duties (Author cannot self-approve), and chains every event in a tamper-evident SHA-256 log.'
          : 'Genera el Resumen Escrito CTD 2.6.6.3 con chips de trazabilidad interactivos, exige separación de funciones (el Autor no puede autoaprobarse) y encadena cada evento con SHA-256.',
    },
  ];

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'EXECUTIVE STUDY OVERVIEW · TRACEABLE AGENTIC WORKSPACE'
              : 'RESUMEN EJECUTIVO DEL ESTUDIO · ESPACIO AGÉNTICO TRAZABLE'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Study PDS2014 — 28-Day Oral Toxicity & TK in Rats'
              : 'Estudio PDS2014 — Toxicidad Oral de 28 Días y TK en Ratas'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'The model selects tools and drafts prose structure; deterministic code places every number and verbatim quotation; qualified toxicologists make the adversity and NOAEL decisions.'
              : 'El modelo elige herramientas y redacta la estructura; el código determinista coloca cada número y cita literal; los científicos toman las decisiones de adversidad y NOAEL.'}
          </p>
        </div>
        <div className="head-actions">
          <span className="status-pill">
            ● {locale === 'en' ? 'SEND Snapshot Verified' : 'Snapshot SEND Verificado'}
          </span>
          <button className="btn" onClick={() => onNavigate('assessment')}>
            {locale === 'en' ? 'Go to Scientific Assessment →' : 'Ir a Evaluación Científica →'}
          </button>
          <button className="btn secondary" onClick={() => onNavigate('report')}>
            {locale === 'en' ? 'Open CTD 2.6.6.3 Draft' : 'Abrir Borrador CTD 2.6.6.3'}
          </button>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <div className="grid four">
        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'ANIMALS EXAMINED (DM)' : 'ANIMALES EXAMINADOS (DM)'}
          </div>
          <div className="kpi-value cyan">124</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'Sprague-Dawley Rats · 20 treatment/TK sets'
              : 'Ratas Sprague-Dawley · 20 grupos estudio/TK'}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'ORAL GAVAGE DOSE LEVELS' : 'NIVELES DE DOSIS (SONDA ORAL)'}
          </div>
          <div className="kpi-value">0, 20, 200, 400</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'mg/kg/day · 28-day dosing + recovery'
              : 'mg/kg/día · 28 días de dosis + recuperación'}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'SCREENED FINDINGS (MI)' : 'HALLAZGOS CRIBADOS (MI)'}
          </div>
          <div className="kpi-value amber">9</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'Key target: Adrenal Gland Vacuolization (F & M)'
              : 'Diana clave: Vacuolización Suprarrenal (H y M)'}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'QUARANTINED ROWS (PP)' : 'FILAS EN CUARENTENA (PP)'}
          </div>
          <div className="kpi-value green">12 Held</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'Negative AUC values isolated · 5.66× mean impact'
              : 'Valores AUC negativos aislados · impacto 5.66×'}
          </div>
        </div>
      </div>

      {/* Main Two-Column Section */}
      <div className="grid main-side">
        {/* Left: Visual Dose-Response & NOAEL Summary */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? 'Dose-Response Profile & Deterministic NOAEL Summary'
                  : 'Perfil Dosis-Respuesta y Resumen Determinista de NOAEL'}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Adrenal cortical vacuolization incidence (%) and Day-29 body weight reduction vs. control across dose groups'
                  : 'Incidencia (%) de vacuolización cortical suprarrenal y reducción de peso en Día 29 frente a control por grupo de dosis'}
              </p>
            </div>
            <span className="chip">Tool: incidence + body_weight_change</span>
          </div>

          {/* SVG Dose-Response Chart */}
          <div
            style={{
              background: 'linear-gradient(180deg, rgba(12, 42, 58, 0.7), rgba(6, 20, 30, 0.85))',
              border: '1px solid #1e4f63',
              borderRadius: 12,
              padding: '14px 16px',
              marginBottom: 14,
            }}
          >
            <svg viewBox="0 0 680 215" style={{ width: '100%', height: 210, display: 'block' }}>
              {/* Grid lines */}
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

              {/* X-axis Dose Positions: 0->100, 20->270, 200->450, 400->610 */}
              {[
                { label: '0 mg/kg (Control)', x: 100 },
                { label: '20 mg/kg (Low)', x: 270 },
                { label: '200 mg/kg (Mid)', x: 450 },
                { label: '400 mg/kg (High)', x: 610 },
              ].map((d) => (
                <g key={d.label}>
                  <line x1={d.x} y1={35} x2={d.x} y2={175} stroke="#143545" />
                  <text x={d.x} y={196} textAnchor="middle" fill="#b8d4df" fontSize="11" fontFamily="var(--mono)">
                    {d.label}
                  </text>
                </g>
              ))}

              {/* Female Adrenal Vacuolization: 0/10 (0%), 2/5 (40%), 4/5 (80%), 9/10 (90%) */}
              <polyline
                fill="none"
                stroke="#29d7d4"
                strokeWidth="3"
                points="100,175 270,119 450,63 610,49"
              />
              {[
                { x: 100, y: 175, txt: '0/10 (0%)' },
                { x: 270, y: 119, txt: '2/5 (40%)' },
                { x: 450, y: 63, txt: '4/5 (80%)' },
                { x: 610, y: 49, txt: '9/10 (90%)' },
              ].map((pt, i) => (
                <g key={`f-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="5" fill="#29d7d4" stroke="#06131d" strokeWidth="2" />
                  <text x={pt.x} y={pt.y - 10} textAnchor="middle" fill="#70f0e8" fontSize="10" fontFamily="var(--mono)">
                    {pt.txt}
                  </text>
                </g>
              ))}

              {/* Male Adrenal Vacuolization: 0/10 (0%), 0/0 (not exam -> 0%), 0/0, 7/10 (70%) */}
              <polyline
                fill="none"
                stroke="#8b65f5"
                strokeWidth="2.5"
                strokeDasharray="6 3"
                points="100,175 270,175 450,175 610,77"
              />
              {[
                { x: 100, y: 175, txt: '0/10' },
                { x: 270, y: 175, txt: 'n/e' },
                { x: 450, y: 175, txt: 'n/e' },
                { x: 610, y: 77, txt: '7/10 (70%)' },
              ].map((pt, i) => (
                <g key={`m-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="4.5" fill="#8b65f5" stroke="#06131d" strokeWidth="2" />
                  {i === 3 && (
                    <text x={pt.x - 6} y={pt.y + 16} textAnchor="end" fill="#d3c4ff" fontSize="10" fontFamily="var(--mono)">
                      M: {pt.txt}
                    </text>
                  )}
                </g>
              ))}

              {/* Female Body Weight % lower than control: 0%, 4.29%, 14.22%, 14.27% */}
              <polyline
                fill="none"
                stroke="#f5b84c"
                strokeWidth="2.2"
                points="100,175 270,169 450,155 610,155"
              />
              {[
                { x: 270, y: 169, txt: '-4.3% BW' },
                { x: 450, y: 155, txt: '-14.2% BW' },
                { x: 610, y: 155, txt: '-14.3% BW' },
              ].map((pt, i) => (
                <g key={`bw-${i}`}>
                  <circle cx={pt.x} cy={pt.y} r="4" fill="#f5b84c" />
                  <text x={pt.x} y={pt.y - 8} textAnchor="middle" fill="#ffd88a" fontSize="9.5" fontFamily="var(--mono)">
                    {pt.txt}
                  </text>
                </g>
              ))}

              {/* Legend */}
              <g transform="translate(75, 16)">
                <circle cx={0} cy={0} r={4} fill="#29d7d4" />
                <text x={8} y={4} fill="#cfe7ef" fontSize="10.5">
                  Female Adrenal Vacuolization
                </text>
                <circle cx={195} cy={0} r={4} fill="#8b65f5" />
                <text x={203} y={4} fill="#cfe7ef" fontSize="10.5">
                  Male Adrenal Vacuolization
                </text>
                <circle cx={380} cy={0} r={4} fill="#f5b84c" />
                <text x={388} y={4} fill="#cfe7ef" fontSize="10.5">
                  Female Day-29 BW (% Lower vs Control)
                </text>
              </g>
            </svg>
          </div>

          {/* Live NOAEL Status Cards */}
          <div className="grid two">
            <div
              style={{
                padding: 14,
                borderRadius: 11,
                border: fConfirmed ? '1px solid #287a67' : '1px solid #7a5c29',
                background: fConfirmed ? 'rgba(22, 102, 82, 0.16)' : 'rgba(130, 92, 24, 0.14)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="eyebrow" style={{ margin: 0 }}>
                  {locale === 'en' ? 'FEMALE (F) NOAEL' : 'NOAEL HEMBRAS (F)'}
                </span>
                <span className={`status-pill ${fConfirmed ? '' : 'warn'}`}>
                  {fConfirmed
                    ? locale === 'en'
                      ? 'Confirmed by Reviewer'
                      : 'Confirmado por Revisor'
                    : locale === 'en'
                      ? 'Awaiting Confirmation'
                      : 'Pendiente de Confirmar'}
                </span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6, color: '#fff' }}>
                {fNoael !== undefined && fNoael !== null
                  ? `${fNoael} mg/kg/day`
                  : locale === 'en'
                    ? 'Pending human decision'
                    : 'Pendiente de decisión'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                {thread?.noael?.F?.flags?.length
                  ? `⚠ ${thread.noael.F.flags[0]}`
                  : locale === 'en'
                    ? 'Adverse from 200 mg/kg/day (Adrenal vacuolization & BW)'
                    : 'Adverso desde 200 mg/kg/día (Vacuolización suprarrenal y peso)'}
              </div>
            </div>

            <div
              style={{
                padding: 14,
                borderRadius: 11,
                border: mConfirmed ? '1px solid #287a67' : '1px solid #7a5c29',
                background: mConfirmed ? 'rgba(22, 102, 82, 0.16)' : 'rgba(130, 92, 24, 0.14)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="eyebrow" style={{ margin: 0 }}>
                  {locale === 'en' ? 'MALE (M) NOAEL' : 'NOAEL MACHOS (M)'}
                </span>
                <span className={`status-pill ${mConfirmed ? '' : 'warn'}`}>
                  {mConfirmed
                    ? locale === 'en'
                      ? 'Confirmed by Reviewer'
                      : 'Confirmado por Revisor'
                    : locale === 'en'
                      ? 'Awaiting Confirmation'
                      : 'Pendiente de Confirmar'}
                </span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 700, marginTop: 6, color: '#fff' }}>
                {mNoael !== undefined && mNoael !== null
                  ? `${mNoael} mg/kg/day`
                  : locale === 'en'
                    ? 'Pending human decision'
                    : 'Pendiente de decisión'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4 }}>
                {thread?.noael?.M?.flags?.length
                  ? `⚠ ${thread.noael.M.flags[0]}`
                  : locale === 'en'
                    ? 'Adverse at 400 mg/kg/day · Flags incomplete mid-dose exam'
                    : 'Adverso a 400 mg/kg/día · Advierte examen incompleto a 200'}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Active Workflow Thread & Traceable Sentence Demo */}
        <div className="stack">
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>
                  {locale === 'en'
                    ? 'Active Workflow Thread Status'
                    : 'Estado del Hilo de Trabajo Activo'}
                </h2>
                <p>
                  {locale === 'en'
                    ? 'Live LangGraph checkpoint & SHA-256 audit state'
                    : 'Checkpoint LangGraph en vivo y auditoría SHA-256'}
                </p>
              </div>
              <span className="status-pill info">{thread?.waiting || 'loading'}</span>
            </div>

            <div className="stack" style={{ gap: 10 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: '#081b28',
                  border: '1px solid #1a4659',
                }}
              >
                <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {locale === 'en' ? 'Recorded Decisions (D1–D11)' : 'Decisiones Grabadas (D1–D11)'}
                </span>
                <strong className="mono" style={{ color: '#fff' }}>
                  {thread ? `${thread.decisions.length} / ${thread.slots.length}` : '—'}
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: '#081b28',
                  border: '1px solid #1a4659',
                }}
              >
                <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {locale === 'en' ? '8 Deterministic Verifier Rules' : '8 Reglas del Verificador'}
                </span>
                <strong
                  className="mono"
                  style={{ color: thread?.final?.ok ? 'var(--green)' : 'var(--amber)' }}
                >
                  {thread?.final?.ok
                    ? '8 / 8 PASSED'
                    : `${8 - (thread?.final?.failures?.length || 0)} / 8 (Awaiting NOAEL)`}
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: '#081b28',
                  border: '1px solid #1a4659',
                }}
              >
                <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {locale === 'en' ? 'SHA-256 Audit Chain' : 'Cadena de Auditoría SHA-256'}
                </span>
                <strong className="mono" style={{ color: 'var(--cyan2)' }}>
                  {audit ? `${audit.count} entries · ${audit.ok ? 'INTACT' : 'BROKEN'}` : '—'}
                </strong>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  padding: '9px 12px',
                  borderRadius: 9,
                  background: '#081b28',
                  border: '1px solid #1a4659',
                }}
              >
                <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>
                  {locale === 'en' ? 'Electronic Sign-Off' : 'Firma Electrónica Final'}
                </span>
                <strong
                  className="mono"
                  style={{ color: thread?.approved_by ? 'var(--green)' : 'var(--muted)' }}
                >
                  {thread?.approved_by || (locale === 'en' ? 'Not yet approved' : 'Sin aprobar aún')}
                </strong>
              </div>
            </div>
          </div>

          {/* Interactive Traceability Preview Card */}
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>
                  {locale === 'en'
                    ? 'Zero-Hallucination Number Placement'
                    : 'Colocación de Cifras sin Alucinaciones'}
                </h2>
                <p>
                  {locale === 'en'
                    ? 'Click any green chip below to inspect its DuckDB Observation & SEND rows'
                    : 'Haz clic en cualquier chip verde para inspeccionar su Observation en DuckDB'}
                </p>
              </div>
              <span className="status-pill">0 AI Digits</span>
            </div>

            {sampleAsk && sampleAsk.verifiedParts.length > 0 ? (
              <>
                <div
                  style={{
                    padding: 13,
                    borderRadius: 10,
                    background: '#071824',
                    border: '1px solid #1f5368',
                    lineHeight: 1.75,
                    fontSize: 13.5,
                  }}
                >
                  <ProvenanceInline
                    parts={sampleAsk.verifiedParts}
                    onSelect={onSelectProvenance}
                  />
                </div>
                {sampleAsk.aiWritten && (
                  <div style={{ marginTop: 10 }}>
                    <div
                      style={{
                        fontSize: 11,
                        fontFamily: 'var(--mono)',
                        color: 'var(--muted)',
                        marginBottom: 4,
                      }}
                    >
                      {locale === 'en'
                        ? 'RAW AI TEMPLATE (WHAT CLAUDE WROTE — 0 DIGITS):'
                        : 'PLANTILLA CRUDA DE LA IA (0 DÍGITOS ESCRITOS POR EL MODELO):'}
                    </div>
                    <div
                      className="mono"
                      style={{
                        fontSize: 11.5,
                        color: '#9ec0ce',
                        padding: 10,
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
              <div className="callout">
                {locale === 'en' ? 'Loading live example from /ask/run...' : 'Cargando ejemplo en vivo desde /ask/run...'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Interactive 5-Stage Pipeline */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? 'End-to-End Traceable Agentic Architecture'
                : 'Arquitectura Agéntica Trazable de Extremo a Extremo'}
            </h2>
            <p>
              {locale === 'en'
                ? 'Select any stage to inspect how Cairn separates statistical/regulatory facts from LLM prose generation'
                : 'Selecciona cualquier etapa para inspeccionar cómo Cairn separa los hechos estadísticos de la generación LLM'}
            </p>
          </div>
          <span className="chip">LangGraph + FastMCP + DuckDB + Pandera</span>
        </div>

        <div className="pipeline-grid">
          {stages.map((st) => (
            <button
              key={st.num}
              type="button"
              className={`pipeline-step ${activeStage === st.num ? 'active' : ''}`}
              onClick={() => setActiveStage(st.num)}
            >
              <div className="pipeline-num">{st.num}</div>
              <div style={{ fontWeight: 700, fontSize: 13.5, marginBottom: 3 }}>{st.title}</div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>{st.sub}</div>
            </button>
          ))}
        </div>

        {stages.map((st) =>
          st.num === activeStage ? (
            <div
              key={st.num}
              style={{
                marginTop: 14,
                padding: '14px 16px',
                borderRadius: 11,
                background: 'rgba(8, 28, 42, 0.9)',
                border: '1px solid #26657c',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 16,
                flexWrap: 'wrap',
              }}
            >
              <div style={{ maxWidth: 880 }}>
                <div className="eyebrow" style={{ marginBottom: 4 }}>
                  {st.title} — {st.sub}
                </div>
                <p style={{ margin: 0, fontSize: 13.5, color: '#d8ecf3' }}>{st.detail}</p>
              </div>
              <button className="btn sm" onClick={() => onNavigate(st.view)}>
                {locale === 'en' ? 'Open Stage Workspace →' : 'Abrir Vista de la Etapa →'}
              </button>
            </div>
          ) : null,
        )}
      </div>
    </div>
  );
};
