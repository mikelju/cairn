import React, { useEffect, useState } from 'react';
import {
  BodyWeightValues,
  IncidenceValues,
  Observation,
  TkSummaryValues,
  fetchBodyWeight,
  fetchIncidence,
  fetchTkSummary,
} from '../api';
import { ObservationDrawer } from '../components/ObservationDrawer';
import { Locale } from '../i18n';

interface DataExplorerViewProps {
  locale: Locale;
}

export const DataExplorerView: React.FC<DataExplorerViewProps> = ({ locale }) => {
  // Incidence state
  const [screenOnly, setScreenOnly] = useState(true);
  const [incSexFilter, setIncSexFilter] = useState<'ALL' | 'F' | 'M'>('ALL');
  const [incSearch, setIncSearch] = useState('');
  const [incObs, setIncObs] = useState<Observation<IncidenceValues> | null>(null);
  const [loadingInc, setLoadingInc] = useState(false);

  // Body Weight state
  const [bwSex, setBwSex] = useState<'F' | 'M'>('F');
  const [bwPop, setBwPop] = useState<'main_and_recovery' | 'main'>('main_and_recovery');
  const [bwObs, setBwObs] = useState<Observation<BodyWeightValues> | null>(null);
  const [loadingBw, setLoadingBw] = useState(false);

  // TK Summary state
  const [tkSex, setTkSex] = useState<'F' | 'M'>('M');
  const [tkDose, setTkDose] = useState<number>(20);
  const [tkDay, setTkDay] = useState<number>(1);
  const [tkObs, setTkObs] = useState<Observation<TkSummaryValues> | null>(null);
  const [loadingTk, setLoadingTk] = useState(false);

  useEffect(() => {
    setLoadingInc(true);
    fetchIncidence(screenOnly)
      .then((res) => setIncObs(res))
      .catch(() => {})
      .finally(() => setLoadingInc(false));
  }, [screenOnly]);

  useEffect(() => {
    setLoadingBw(true);
    fetchBodyWeight(bwSex, bwPop)
      .then((res) => setBwObs(res))
      .catch(() => {})
      .finally(() => setLoadingBw(false));
  }, [bwSex, bwPop]);

  useEffect(() => {
    setLoadingTk(true);
    fetchTkSummary(tkSex, tkDose, tkDay)
      .then((res) => setTkObs(res))
      .catch(() => {})
      .finally(() => setLoadingTk(false));
  }, [tkSex, tkDose, tkDay]);

  const findings = (incObs?.values.findings || []).filter((f) => {
    if (incSexFilter !== 'ALL' && f.sex !== incSexFilter) return false;
    if (incSearch.trim()) {
      const q = incSearch.toLowerCase();
      return f.tissue.toLowerCase().includes(q) || f.finding.toLowerCase().includes(q);
    }
    return true;
  });

  const bwGroups = bwObs?.values.groups || [];
  const maxBw = bwGroups.reduce((m, g) => Math.max(m, g.mean_day29_g), 250);

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 2 & 3 · STRUCTURED STUDY DATA EXPLORER (READ-ONLY TOOLS)'
              : 'ETAPA 2 Y 3 · EXPLORADOR DE DATOS ESTRUCTURADOS (HERRAMIENTAS DE SOLO LECTURA)'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Interactive SEND Domain Tools & Provenance Inspector'
              : 'Herramientas Interactivas de Dominios SEND e Inspector de Procedencia'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'Every chart and table below calls the exact read-only FastAPI/MCP tools used by the AI agent, returning typed Observations with SHA-256 content hashes and fixed DuckDB SQL.'
              : 'Cada gráfico y tabla invoca en vivo las mismas herramientas FastAPI/MCP de solo lectura que usa el agente IA, devolviendo Observations tipadas con hash SHA-256 y SQL fijo.'}
          </p>
        </div>
      </div>

      {/* Panel 1: Histopathology Incidence */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? '1. Microscopic Histopathology Incidence (MI Domain)'
                : '1. Incidencia Histopatológica Microscópica (Dominio MI)'}
            </h2>
            <p>
              {incObs?.values.screen_rule ||
                (locale === 'en'
                  ? 'Full incidence across all examined tissues in main-study animals (TK satellites & recovery excluded)'
                  : 'Incidencia completa en todos los tejidos examinados de animales principales')}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <div className="seg-group">
              <button
                type="button"
                className={`seg-btn ${screenOnly ? 'active' : ''}`}
                onClick={() => setScreenOnly(true)}
              >
                {locale === 'en' ? 'Screened Findings (9)' : 'Cribados (9)'}
              </button>
              <button
                type="button"
                className={`seg-btn ${!screenOnly ? 'active' : ''}`}
                onClick={() => setScreenOnly(false)}
              >
                {locale === 'en' ? 'All Tissues (Full MI)' : 'Todos los Tejidos'}
              </button>
            </div>

            <div className="seg-group">
              {(['ALL', 'F', 'M'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`seg-btn ${incSexFilter === s ? 'active' : ''}`}
                  onClick={() => setIncSexFilter(s)}
                >
                  {s === 'ALL' ? (locale === 'en' ? 'All Sexes' : 'Ambos') : s}
                </button>
              ))}
            </div>

            <input
              type="text"
              className="input"
              placeholder={
                locale === 'en' ? 'Filter tissue or finding…' : 'Filtrar órgano o hallazgo…'
              }
              value={incSearch}
              onChange={(e) => setIncSearch(e.target.value)}
              style={{ width: 190, padding: '5px 10px', fontSize: 12 }}
            />
          </div>
        </div>

        <div className="table-wrap" style={{ maxHeight: 380, opacity: loadingInc ? 0.6 : 1 }}>
          <table>
            <thead>
              <tr>
                <th>Sex</th>
                <th>Tissue / Organ (MISPEC)</th>
                <th>Microscopic Finding (MISTRESC)</th>
                <th>0 mg/kg (Control)</th>
                <th>20 mg/kg (Low)</th>
                <th>200 mg/kg (Mid)</th>
                <th>400 mg/kg (High)</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, idx) => {
                const isKey = `${f.tissue} ${f.finding}` === 'GLAND, ADRENAL Vacuolization';
                return (
                  <tr
                    key={`${f.sex}-${f.tissue}-${f.finding}-${idx}`}
                    style={
                      isKey
                        ? { background: 'rgba(41, 215, 212, 0.08)' }
                        : undefined
                    }
                  >
                    <td className="mono">
                      <span
                        className={`status-pill ${f.sex === 'F' ? 'info' : ''}`}
                        style={{ padding: '1px 7px' }}
                      >
                        {f.sex}
                      </span>
                    </td>
                    <td className="mono" style={{ fontWeight: 600, color: '#fff' }}>
                      {f.tissue}
                    </td>
                    <td>
                      {f.finding}{' '}
                      {isKey && (
                        <span className="prod-badge" style={{ marginLeft: 6 }}>
                          KEY FINDING
                        </span>
                      )}
                    </td>
                    {f.groups.map((g) => {
                      if (g.status === 'not examined' || !g.examined) {
                        return (
                          <td
                            key={g.dose}
                            className="mono"
                            style={{ color: 'var(--dim)', fontStyle: 'italic' }}
                          >
                            not examined
                          </td>
                        );
                      }
                      const ratio = (g.affected || 0) / g.examined;
                      const pct = Math.round(ratio * 100);
                      return (
                        <td key={g.dose}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span
                              className="mono"
                              style={{
                                minWidth: 42,
                                fontWeight: (g.affected || 0) > 0 ? 700 : 400,
                                color:
                                  ratio >= 0.5
                                    ? 'var(--amber)'
                                    : (g.affected || 0) > 0
                                      ? 'var(--cyan2)'
                                      : 'var(--muted)',
                              }}
                            >
                              {g.affected}/{g.examined}
                            </span>
                            <div
                              style={{
                                flex: 1,
                                height: 8,
                                background: '#133344',
                                borderRadius: 99,
                                overflow: 'hidden',
                                minWidth: 50,
                              }}
                            >
                              <div
                                style={{
                                  height: '100%',
                                  width: `${pct}%`,
                                  background:
                                    ratio >= 0.6
                                      ? 'linear-gradient(90deg, #f5b84c, #f36b6b)'
                                      : 'linear-gradient(90deg, #29d7d4, #4d8df5)',
                                }}
                              />
                            </div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <ObservationDrawer observation={incObs} locale={locale} />
      </div>

      {/* Bottom Two Columns: Body Weight & Toxicokinetics */}
      <div className="grid two">
        {/* Panel 2: Body Weight Change */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? '2. Day-29 Body Weight vs. Control (BW Domain)'
                  : '2. Peso Corporal en Día 29 frente a Control (Dominio BW)'}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Enforces Rule 7 controlled wording: "lower than control" (never "weight loss")'
                  : 'Aplica la Regla 7 de vocabulario controlado: "lower than control"'}
              </p>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <div className="seg-group">
                {(['F', 'M'] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`seg-btn ${bwSex === s ? 'active' : ''}`}
                    onClick={() => setBwSex(s)}
                  >
                    {s === 'F'
                      ? locale === 'en'
                        ? 'Females (F)'
                        : 'Hembras (F)'
                      : locale === 'en'
                        ? 'Males (M)'
                        : 'Machos (M)'}
                  </button>
                ))}
              </div>
              <div className="seg-group">
                <button
                  type="button"
                  className={`seg-btn ${bwPop === 'main_and_recovery' ? 'active' : ''}`}
                  onClick={() => setBwPop('main_and_recovery')}
                >
                  Main + Rec
                </button>
                <button
                  type="button"
                  className={`seg-btn ${bwPop === 'main' ? 'active' : ''}`}
                  onClick={() => setBwPop('main')}
                >
                  Main Only
                </button>
              </div>
            </div>
          </div>

          {/* Visual SVG Bar Chart for Day 29 Body Weight */}
          <div
            style={{
              background: '#071926',
              border: '1px solid #1e4e63',
              borderRadius: 11,
              padding: 12,
              marginBottom: 12,
              opacity: loadingBw ? 0.6 : 1,
            }}
          >
            <svg viewBox="0 0 520 155" style={{ width: '100%', height: 150, display: 'block' }}>
              {bwGroups.map((g, idx) => {
                const x = 45 + idx * 120;
                const barH = Math.round((g.mean_day29_g / maxBw) * 95);
                const y = 120 - barH;
                const isReduced = (g.percent_lower_than_control || 0) >= 10;
                return (
                  <g key={g.dose}>
                    <rect
                      x={x}
                      y={y}
                      width={64}
                      height={barH}
                      rx={6}
                      fill={
                        g.dose === 0
                          ? '#3a7ca5'
                          : isReduced
                            ? 'url(#bwWarnGrad)'
                            : '#29d7d4'
                      }
                    />
                    <text
                      x={x + 32}
                      y={y - 16}
                      textAnchor="middle"
                      fill="#fff"
                      fontSize="11"
                      fontWeight="700"
                      fontFamily="var(--mono)"
                    >
                      {g.mean_day29_g.toFixed(1)} g
                    </text>
                    <text
                      x={x + 32}
                      y={y - 4}
                      textAnchor="middle"
                      fill={isReduced ? '#ffd37a' : '#8ef5d8'}
                      fontSize="10"
                      fontFamily="var(--mono)"
                    >
                      {g.percent_lower_than_control === null
                        ? 'Control'
                        : `-${g.percent_lower_than_control}%`}
                    </text>
                    <text
                      x={x + 32}
                      y={138}
                      textAnchor="middle"
                      fill="#b8d4df"
                      fontSize="11"
                      fontFamily="var(--mono)"
                    >
                      {g.dose} mg/kg (n={g.n})
                    </text>
                  </g>
                );
              })}
              <defs>
                <linearGradient id="bwWarnGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f5b84c" />
                  <stop offset="100%" stopColor="#d96b43" />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Dose</th>
                  <th className="num">n</th>
                  <th className="num">Mean Day-29 (g)</th>
                  <th className="num">% Lower Than Control</th>
                  <th className="num">Mean Change vs Baseline</th>
                </tr>
              </thead>
              <tbody>
                {bwGroups.map((g) => (
                  <tr key={g.dose}>
                    <td className="mono">{g.dose} mg/kg/day</td>
                    <td className="num">{g.n}</td>
                    <td className="num">{g.mean_day29_g.toFixed(2)} g</td>
                    <td
                      className="num"
                      style={{
                        color:
                          (g.percent_lower_than_control || 0) >= 10
                            ? 'var(--amber)'
                            : 'var(--cyan2)',
                        fontWeight: 600,
                      }}
                    >
                      {g.percent_lower_than_control === null
                        ? '— (Control)'
                        : `${g.percent_lower_than_control.toFixed(2)}%`}
                    </td>
                    <td className="num">+{g.mean_change_from_baseline_g.toFixed(2)} g</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {bwObs && (
            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)' }}>
              <strong>Animals with negative change from baseline (weight loss):</strong>{' '}
              {bwObs.values.animals_with_negative_change.length === 0 ? (
                <span style={{ color: 'var(--green)' }}>
                  0 animals (all animals gained weight vs Day 1; hence "lower than control" is mandatory)
                </span>
              ) : (
                bwObs.values.animals_with_negative_change
                  .map((a) => `${a.usubjid} (${a.dose} mg/kg: ${a.change_g}g)`)
                  .join(', ')
              )}
            </div>
          )}

          <ObservationDrawer observation={bwObs} locale={locale} />
        </div>

        {/* Panel 3: Toxicokinetics (tk_summary) */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>
                {locale === 'en'
                  ? '3. Toxicokinetics AUCtau Explorer (PP Domain)'
                  : '3. Explorador de Toxicocinética AUCtau (Dominio PP)'}
              </h2>
              <p>
                {locale === 'en'
                  ? 'Compares naive mean with vs. without quarantined negative AUCtau rows'
                  : 'Compara la media con y sin filas negativas de AUCtau en cuarentena'}
              </p>
            </div>
            <span className="chip">POST /api/tools/tk_summary</span>
          </div>

          {/* Controls for Sex, Dose, Day */}
          <div
            style={{
              display: 'flex',
              gap: 10,
              flexWrap: 'wrap',
              marginBottom: 14,
              alignItems: 'center',
            }}
          >
            <div className="seg-group">
              {(['M', 'F'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`seg-btn ${tkSex === s ? 'active' : ''}`}
                  onClick={() => setTkSex(s)}
                >
                  Sex: {s}
                </button>
              ))}
            </div>

            <div className="seg-group">
              {[20, 200, 400].map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`seg-btn ${tkDose === d ? 'active' : ''}`}
                  onClick={() => setTkDose(d)}
                >
                  {d} mg/kg
                </button>
              ))}
            </div>

            <div className="seg-group">
              {[1, 29].map((dy) => (
                <button
                  key={dy}
                  type="button"
                  className={`seg-btn ${tkDay === dy ? 'active' : ''}`}
                  onClick={() => setTkDay(dy)}
                >
                  Day {dy}
                </button>
              ))}
            </div>
          </div>

          {tkObs && (
            <div className="stack" style={{ opacity: loadingTk ? 0.6 : 1 }}>
              <div className="grid two">
                <div
                  style={{
                    padding: 14,
                    borderRadius: 11,
                    background: tkObs.values.contains_quarantined
                      ? 'rgba(155, 45, 55, 0.16)'
                      : 'rgba(14, 45, 64, 0.6)',
                    border: tkObs.values.contains_quarantined
                      ? '1px solid #8a434b'
                      : '1px solid #215266',
                  }}
                >
                  <div className="eyebrow" style={{ margin: 0 }}>
                    {locale === 'en' ? 'WITH QUARANTINED ROWS' : 'CON FILAS EN CUARENTENA'}
                  </div>
                  <div className="mono" style={{ fontSize: 23, fontWeight: 700, margin: '6px 0' }}>
                    {tkObs.values.with_quarantined.mean !== null
                      ? `${tkObs.values.with_quarantined.mean.toLocaleString()} h*ng/mL`
                      : 'n/a'}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    n = {tkObs.values.with_quarantined.n} TK satellite animals
                  </div>
                </div>

                <div
                  style={{
                    padding: 14,
                    borderRadius: 11,
                    background: 'rgba(28, 128, 98, 0.16)',
                    border: '1px solid #287565',
                  }}
                >
                  <div className="eyebrow" style={{ margin: 0 }}>
                    {locale === 'en' ? 'CLEAN VERIFIED MEAN' : 'MEDIA LIMPIA VERIFICADA'}
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 23,
                      fontWeight: 700,
                      color: 'var(--green)',
                      margin: '6px 0',
                    }}
                  >
                    {tkObs.values.without_quarantined.mean !== null
                      ? `${tkObs.values.without_quarantined.mean.toLocaleString()} h*ng/mL`
                      : 'n/a'}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                    n = {tkObs.values.without_quarantined.n} plausible animals · Ratio:{' '}
                    <strong>{tkObs.values.ratio_without_over_with ?? '1.0'}×</strong>
                  </div>
                </div>
              </div>

              {tkObs.values.contains_quarantined ? (
                <div className="callout warn">
                  <strong>
                    {locale === 'en'
                      ? 'Rule 5 Triggered (contains_quarantined = true): '
                      : 'Regla 5 Activada (contains_quarantined = true): '}
                  </strong>
                  {tkObs.values.quarantined_rows.map((q) => (
                    <span key={q.usubjid} className="mono">
                      Animal {q.usubjid} (PP row #{q.source_row}) = {q.value.toLocaleString()} h*ng/mL
                    </span>
                  ))}
                </div>
              ) : (
                <div className="callout success">
                  {locale === 'en'
                    ? 'All AUCtau measurements in this sex/dose/day cohort are physically plausible (0 quarantined rows).'
                    : 'Todas las mediciones de AUCtau en esta cohorte son físicamente plausibles (0 en cuarentena).'}
                </div>
              )}
            </div>
          )}

          <ObservationDrawer observation={tkObs} locale={locale} />
        </div>
      </div>
    </div>
  );
};
