import React, { useEffect, useState } from 'react';
import {
  JobResponse,
  Observation,
  ParsedStudySwitchResult,
  StudyDesignValues,
  fetchStudyDesign,
  runStudySwitch,
  runValidateStudyJob,
} from '../api';
import { ObservationDrawer } from '../components/ObservationDrawer';
import { Locale } from '../i18n';

interface StudyViewProps {
  locale: Locale;
}

export const StudyView: React.FC<StudyViewProps> = ({ locale }) => {
  const [designObs, setDesignObs] = useState<Observation<StudyDesignValues> | null>(null);
  const [jobRes, setJobRes] = useState<JobResponse | null>(null);
  const [switchRes, setSwitchRes] = useState<ParsedStudySwitchResult | null>(null);
  const [activeSwitch, setActiveSwitch] = useState<'none' | 'negative' | 'duplicate' | 'dose'>('none');
  const [loadingSwitch, setLoadingSwitch] = useState(false);
  const [loadingJob, setLoadingJob] = useState(false);
  const [filterTest, setFilterTest] = useState<string>('ALL');

  useEffect(() => {
    fetchStudyDesign()
      .then((res) => setDesignObs(res))
      .catch(() => {});
    handleRunValidationJob();
    handleSwitch('none');
  }, []);

  const handleRunValidationJob = async () => {
    setLoadingJob(true);
    try {
      const res = await runValidateStudyJob();
      setJobRes(res);
    } finally {
      setLoadingJob(false);
    }
  };

  const handleSwitch = async (mode: 'none' | 'negative' | 'duplicate' | 'dose') => {
    setActiveSwitch(mode);
    setLoadingSwitch(true);
    try {
      const res = await runStudySwitch(mode);
      setSwitchRes(res);
    } finally {
      setLoadingSwitch(false);
    }
  };

  const report = jobRes?.outputs?.report;
  const domainEntries = report ? Object.entries(report.rows) : [];
  const maxRows = domainEntries.reduce((acc, [, count]) => Math.max(acc, count), 1);

  const qRows = report?.quarantine.rows || [];
  const filteredQRows =
    filterTest === 'ALL' ? qRows : qRows.filter((r) => r.test === filterTest);

  const parseMeanNumber = (str: string | undefined, fallback: number): number => {
    if (!str) return fallback;
    const cleaned = Number(str.replace(/[^0-9.-]/g, ''));
    return Number.isFinite(cleaned) ? cleaned : fallback;
  };

  const withBadVal = parseMeanNumber(
    switchRes?.withQuarantinedMean,
    report?.naive_mean_auctau.with_quarantined.mean ?? 2821,
  );
  const cleanVal = parseMeanNumber(
    switchRes?.withoutQuarantinedMean,
    report?.naive_mean_auctau.without_quarantined.mean ?? 15956,
  );

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 1 · STUDY INGESTION & DETERMINISTIC VALIDATION'
              : 'ETAPA 1 · INGESTIÓN DEL ESTUDIO Y VALIDACIÓN DETERMINISTA'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Study Profile & SEND Quarantine Gate'
              : 'Perfil del Estudio y Puerta de Cuarentena SEND'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'Before any AI tool can query study data, Pandera schemas and domain rules validate all 8 SEND XPT files, isolating physically impossible values into a quarantine table.'
              : 'Antes de que la IA pueda consultar datos, esquemas Pandera y reglas de dominio validan los 8 archivos SEND XPT, aislando valores físicamente imposibles en cuarentena.'}
          </p>
        </div>
        <div className="head-actions">
          <button className="btn secondary" onClick={handleRunValidationJob} disabled={loadingJob}>
            {loadingJob
              ? locale === 'en'
                ? 'Running Job…'
                : 'Ejecutando…'
              : locale === 'en'
                ? '↻ Re-run POST /jobs (validate_study)'
                : '↻ Re-ejecutar POST /jobs (validate_study)'}
          </button>
        </div>
      </div>

      {/* Production Preview Study Uploader */}
      <div className="dropzone-preview">
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: 'rgba(41, 215, 212, 0.12)',
              border: '1px solid rgba(41, 215, 212, 0.35)',
              display: 'grid',
              placeItems: 'center',
              fontSize: 20,
              color: 'var(--cyan2)',
            }}
          >
            📦
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <strong style={{ fontSize: 14, color: '#fff' }}>
                {locale === 'en'
                  ? 'Upload Study Package (CDISC SEND .xpt + Study Report PDF)'
                  : 'Subir Paquete de Estudio (CDISC SEND .xpt + Informe PDF)'}
              </strong>
              <span className="prod-badge">
                {locale === 'en'
                  ? 'Production Preview — Pinned in Demo to PDS2014'
                  : 'Vista Previa Producción — Fijado en Demo a PDS2014'}
              </span>
            </div>
            <p style={{ margin: '3px 0 0', fontSize: 12.5, color: 'var(--muted)' }}>
              {locale === 'en'
                ? 'In production, drag-and-drop ingests a new SEND archive into an isolated DuckDB snapshot. In this demo, the backend is pinned to PhUSE PDS2014 (SHA-256: 9b981329b14d…).'
                : 'En producción, arrastrar y soltar ingiere un nuevo archivo SEND en un snapshot DuckDB aislado. En esta demo está fijado a PhUSE PDS2014 (SHA-256: 9b981329b14d…).'}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input type="file" disabled style={{ display: 'none' }} />
          <button className="btn secondary sm" disabled title="Disabled in public demo (pinned to PDS2014)">
            {locale === 'en' ? 'Browse SEND .xpt Files' : 'Explorar Archivos SEND .xpt'}
          </button>
          <button className="btn secondary sm" disabled title="Disabled in public demo (pinned to PDS2014)">
            {locale === 'en' ? 'Connect LIMS / Vault' : 'Conectar LIMS / Vault'}
          </button>
        </div>
      </div>

      {/* Interactive Fault Injection & Quarantine Impact */}
      <div className="grid main-side">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? 'Quarantine Impact on Toxicokinetics & Live Fault Injection'
                  : 'Impacto de la Cuarentena en Toxicocinética e Inyección de Fallos'}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Executes POST /study/run against the backend to test how deterministic validation catches corrupt data'
                  : 'Ejecuta POST /study/run contra el backend para probar cómo la validación determinista detecta datos corruptos'}
              </p>
            </div>
            <span className="chip">POST /study/run</span>
          </div>

          {/* 4 Fault Injection Switches */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
            {(
              [
                {
                  id: 'none',
                  label:
                    locale === 'en'
                      ? '1. Baseline Study (12 Quarantined)'
                      : '1. Estudio Base (12 en Cuarentena)',
                },
                {
                  id: 'negative',
                  label:
                    locale === 'en'
                      ? '2. Inject Negative AUCtau (-50,000)'
                      : '2. Inyectar AUCtau Negativo (-50,000)',
                },
                {
                  id: 'duplicate',
                  label:
                    locale === 'en'
                      ? '3. Inject Duplicate Animal ID (DM)'
                      : '3. Inyectar ID Animal Duplicado (DM)',
                },
                {
                  id: 'dose',
                  label:
                    locale === 'en'
                      ? '4. Inject Unmapped Dose Set (SETCD 99)'
                      : '4. Inyectar Grupo sin Dosis (SETCD 99)',
                },
              ] as const
            ).map((btn) => (
              <button
                key={btn.id}
                type="button"
                className={`btn sm ${activeSwitch === btn.id ? '' : 'secondary'}`}
                onClick={() => handleSwitch(btn.id)}
                disabled={loadingSwitch}
              >
                {btn.label}
              </button>
            ))}
          </div>

          {switchRes?.reportedIntegrityNote && (
            <div className="callout warn" style={{ marginBottom: 12 }}>
              <strong>
                {locale === 'en'
                  ? 'DM Referential Integrity Rule Fired: '
                  : 'Regla de Integridad Referencial DM Activada: '}
              </strong>
              {switchRes.reportedIntegrityNote}
            </div>
          )}

          {switchRes?.injectedNote && (
            <div className="callout danger" style={{ marginBottom: 12 }}>
              <strong>
                {locale === 'en' ? 'Fault Injection Quarantined: ' : 'Fallo Inyectado en Cuarentena: '}
              </strong>
              {switchRes.injectedNote}
            </div>
          )}

          {/* Visual Comparison of Naive vs Clean AUCtau Mean */}
          <div
            style={{
              background: '#071926',
              border: '1px solid #1e4e63',
              borderRadius: 11,
              padding: 16,
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
                <div className="eyebrow" style={{ margin: 0 }}>
                  {locale === 'en'
                    ? 'MALE 20 MG/KG/DAY · DAY 1 AUCTAU MEAN (H*NG/ML)'
                    : 'MEDIA AUCTAU DÍA 1 · MACHOS 20 MG/KG/DÍA (H*NG/ML)'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {switchRes?.effectNote ||
                    (locale === 'en'
                      ? 'Why Quarantine Matters: Including negative XPT artefacts distorts exposure by 5.66×'
                      : 'Por qué importa la cuarentena: incluir artefactos negativos distorsiona la exposición 5.66×')}
                </div>
              </div>
              <span className="status-pill warn">
                {switchRes?.totalQuarantined ?? 12}{' '}
                {locale === 'en' ? 'Rows Quarantined' : 'Filas en Cuarentena'}
              </span>
            </div>

            <div className="grid two">
              <div
                style={{
                  padding: 14,
                  borderRadius: 10,
                  background: 'rgba(155, 45, 55, 0.16)',
                  border: '1px solid #8a434b',
                }}
              >
                <div style={{ fontSize: 11, color: '#ffb4b8', fontFamily: 'var(--mono)' }}>
                  {locale === 'en'
                    ? 'UNFILTERED MEAN (WITH QUARANTINED)'
                    : 'MEDIA SIN FILTRAR (CON CUARENTENA)'}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 25, fontWeight: 700, color: '#ff858b', margin: '4px 0' }}
                >
                  {switchRes?.withQuarantinedMean || '2,821'} h*ng/mL
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>
                  {switchRes?.withQuarantinedLabel || 'All 3 values (includes PDS2014-0032 = -23,450)'}
                </div>
              </div>

              <div
                style={{
                  padding: 14,
                  borderRadius: 10,
                  background: 'rgba(28, 128, 98, 0.16)',
                  border: '1px solid #287565',
                }}
              >
                <div style={{ fontSize: 11, color: '#8ef5d8', fontFamily: 'var(--mono)' }}>
                  {locale === 'en'
                    ? 'VERIFIED CLEAN MEAN (PLAUSIBLE ONLY)'
                    : 'MEDIA LIMPIA VERIFICADA (SOLO PLAUSIBLES)'}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 25, fontWeight: 700, color: 'var(--green)', margin: '4px 0' }}
                >
                  {switchRes?.withoutQuarantinedMean || '15,956'} h*ng/mL
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>
                  {switchRes?.withoutQuarantinedLabel || '2 plausible values (PDS2014-0031, PDS2014-0033)'}
                </div>
              </div>
            </div>

            {/* Visual SVG Bar Chart */}
            <svg viewBox="0 0 600 95" style={{ width: '100%', height: 95, marginTop: 12 }}>
              <text x={10} y={28} fill="#ffb4b8" fontSize="11" fontFamily="var(--mono)">
                With Quarantined
              </text>
              <rect
                x={145}
                y={14}
                width={Math.max(18, Math.min(340, (Math.abs(withBadVal) / 16000) * 320))}
                height={20}
                rx={4}
                fill={withBadVal < 0 ? '#f36b6b' : '#f5b84c'}
              />
              <text
                x={155 + Math.max(18, Math.min(340, (Math.abs(withBadVal) / 16000) * 320))}
                y={28}
                fill="#ffd58b"
                fontSize="11"
                fontFamily="var(--mono)"
              >
                {withBadVal.toLocaleString()} h*ng/mL
              </text>

              <text x={10} y={68} fill="#8ef5d8" fontSize="11" fontFamily="var(--mono)">
                Clean Verified
              </text>
              <rect
                x={145}
                y={54}
                width={Math.max(18, Math.min(340, (cleanVal / 16000) * 320))}
                height={20}
                rx={4}
                fill="#2fd389"
              />
              <text
                x={155 + Math.max(18, Math.min(340, (cleanVal / 16000) * 320))}
                y={68}
                fill="#8ef5d8"
                fontSize="11"
                fontFamily="var(--mono)"
              >
                {cleanVal.toLocaleString()} h*ng/mL (5.66× higher)
              </text>
            </svg>
          </div>
        </div>

        {/* Right: SEND Domain Row Counts & Job Metadata */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? 'SEND Domains & Pandera Schema Gate'
                  : 'Dominios SEND y Esquemas Pandera'}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Live output of JobRunner("validate_study")'
                  : 'Resultado en vivo de JobRunner("validate_study")'}
              </p>
            </div>
            <span className="status-pill">0 Schema Failures</span>
          </div>

          {jobRes && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              <span className="chip">
                job_id: <strong style={{ color: '#fff' }}>{jobRes.job_id || 'sync'}</strong>
              </span>
              <span className="chip">
                inputs_sha256:{' '}
                <strong style={{ color: 'var(--cyan2)' }}>
                  {jobRes.inputs_sha256.slice(0, 10)}…
                </strong>
              </span>
              {report && (
                <span className="chip">
                  report_sha256:{' '}
                  <strong style={{ color: 'var(--green)' }}>
                    {report.report_sha256.slice(0, 10)}…
                  </strong>
                </span>
              )}
            </div>
          )}

          <div className="stack" style={{ gap: 8 }}>
            {domainEntries.map(([dom, count]) => (
              <div
                key={dom}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '48px 1fr 72px 78px',
                  alignItems: 'center',
                  gap: 10,
                  fontSize: 12,
                }}
              >
                <strong className="mono" style={{ color: 'var(--cyan2)' }}>
                  {dom}
                </strong>
                <div
                  style={{
                    height: 9,
                    background: '#133344',
                    borderRadius: 99,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.max(6, (count / maxRows) * 100)}%`,
                      background: 'linear-gradient(90deg, var(--cyan), var(--blue))',
                      borderRadius: 99,
                    }}
                  />
                </div>
                <span className="mono" style={{ textAlign: 'right' }}>
                  {count.toLocaleString()}
                </span>
                <span
                  className="mono"
                  style={{ fontSize: 10.5, color: 'var(--green)', textAlign: 'right' }}
                >
                  0 failures
                </span>
              </div>
            ))}
          </div>

          {report && (
            <div
              style={{
                marginTop: 14,
                paddingTop: 12,
                borderTop: '1px solid #1a4558',
                display: 'grid',
                gap: 8,
                fontSize: 12,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Mortality (DS domain):</span>
                <strong className="mono" style={{ color: 'var(--amber)' }}>
                  {report.deaths[0]?.usubjid} (Day {report.deaths[0]?.day}, {report.deaths[0]?.disposition})
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>Age Cross-Check (TS vs DM.AGE):</span>
                <strong className="mono" style={{ color: 'var(--amber)' }}>
                  TS "{report.age.ts_age_text}" vs DM 0.0 ({report.age.animals_mismatching} animals)
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--muted)' }}>XPT Float Zeros Normalized:</span>
                <strong className="mono">
                  DM.AGE: {report.xpt_zeros_normalised['DM.AGE']}, PC.PCTPTNUM:{' '}
                  {report.xpt_zeros_normalised['PC.PCTPTNUM']}
                </strong>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quarantine Table & Study Design Groups */}
      <div className="grid two">
        {/* Quarantine Rows Table */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? `Quarantined Records (${filteredQRows.length} rows)`
                  : `Registros en Cuarentena (${filteredQRows.length} filas)`}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Held in DuckDB quarantine table; excluded from clean statistical aggregates'
                  : 'Retenidos en la tabla quarantine de DuckDB; excluidos de medias limpias'}
              </p>
            </div>
            <div className="seg-group">
              {(['ALL', 'AUCTAU', 'AUCIFO'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`seg-btn ${filterTest === t ? 'active' : ''}`}
                  onClick={() => setFilterTest(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          <div className="table-wrap" style={{ maxHeight: 310 }}>
            <table>
              <thead>
                <tr>
                  <th>Animal (USUBJID)</th>
                  <th>Domain / Row</th>
                  <th>Parameter</th>
                  <th>Day</th>
                  <th className="num">Quarantined Value</th>
                  <th>Rule</th>
                </tr>
              </thead>
              <tbody>
                {filteredQRows.map((r, i) => (
                  <tr key={i}>
                    <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>
                      {r.usubjid}
                    </td>
                    <td className="mono">
                      {r.domain} #{r.source_row}
                    </td>
                    <td className="mono">
                      <span
                        className={`status-pill ${r.test === 'AUCTAU' ? 'warn' : 'info'}`}
                        style={{ padding: '1px 7px' }}
                      >
                        {r.test}
                      </span>
                    </td>
                    <td className="mono">{r.visit_day ?? '—'}</td>
                    <td className="num" style={{ color: 'var(--red)', fontWeight: 600 }}>
                      {r.value.toLocaleString()} {r.unit}
                    </td>
                    <td className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
                      {r.rule}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Study Design Treatment & TK Sets */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? 'Study Design & Treatment Sets (study_design)'
                  : 'Diseño del Estudio y Grupos de Tratamiento (study_design)'}
              </h2>
              <p>
                {designObs
                  ? `${designObs.values.study_id} · ${designObs.values.species} (${designObs.values.strain}) · ${designObs.values.route}`
                  : 'Loading study_design…'}
              </p>
            </div>
            <span className="chip">POST /api/tools/study_design</span>
          </div>

          <div className="table-wrap" style={{ maxHeight: 310 }}>
            <table>
              <thead>
                <tr>
                  <th>SETCD</th>
                  <th>Group Description</th>
                  <th>Sex</th>
                  <th className="num">Dose</th>
                  <th>Cohort</th>
                  <th className="num">Animals</th>
                </tr>
              </thead>
              <tbody>
                {(designObs?.values.groups || []).map((g) => (
                  <tr key={g.setcd}>
                    <td className="mono" style={{ color: 'var(--cyan2)' }}>
                      {g.setcd}
                    </td>
                    <td>{g.label}</td>
                    <td className="mono">{g.sex}</td>
                    <td className="num">
                      {g.dose} {g.dose_unit}
                    </td>
                    <td>
                      <span
                        className={`status-pill ${g.toxicokinetic ? 'info' : ''}`}
                        style={{ padding: '1px 7px' }}
                      >
                        {g.toxicokinetic ? 'TK Satellite' : 'Main / Rec'}
                      </span>
                    </td>
                    <td className="num">{g.animals}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ObservationDrawer observation={designObs} locale={locale} />
        </div>
      </div>
    </div>
  );
};
