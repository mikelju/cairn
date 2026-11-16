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
import { Icon, Spinner } from '../components/Icon';
import { ObservationDrawer } from '../components/ObservationDrawer';
import { Locale, UI_TEXT } from '../i18n';

interface DataExplorerViewProps {
  locale: Locale;
}

const Seg: React.FC<{
  value: string;
  options: Array<{ id: string; label: string }>;
  onChange: (id: string) => void;
}> = ({ value, options, onChange }) => (
  <div className="seg-group">
    {options.map((o) => (
      <button
        key={o.id}
        type="button"
        className={`seg-btn ${value === o.id ? 'active' : ''}`}
        onClick={() => onChange(o.id)}
      >
        {o.label}
      </button>
    ))}
  </div>
);

export const DataExplorerView: React.FC<DataExplorerViewProps> = ({ locale }) => {
  const t = UI_TEXT[locale];

  const [screenOnly, setScreenOnly] = useState(true);
  const [incSexFilter, setIncSexFilter] = useState<'ALL' | 'F' | 'M'>('ALL');
  const [incSearch, setIncSearch] = useState('');
  const [incObs, setIncObs] = useState<Observation<IncidenceValues> | null>(null);
  const [loadingInc, setLoadingInc] = useState(false);

  const [bwSex, setBwSex] = useState<'F' | 'M'>('F');
  const [bwPop, setBwPop] = useState<'main_and_recovery' | 'main'>('main_and_recovery');
  const [bwObs, setBwObs] = useState<Observation<BodyWeightValues> | null>(null);
  const [loadingBw, setLoadingBw] = useState(false);

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
  const negAnimals = bwObs?.values.animals_with_negative_change ?? [];

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{t.data}</h1>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>{t.histo} · MI</h2>
          <div className="row">
            <Seg
              value={screenOnly ? 'screen' : 'all'}
              options={[
                { id: 'screen', label: t.screenedTab },
                { id: 'all', label: t.allTissues },
              ]}
              onChange={(id) => setScreenOnly(id === 'screen')}
            />
            <Seg
              value={incSexFilter}
              options={[
                { id: 'ALL', label: t.all },
                { id: 'F', label: 'F' },
                { id: 'M', label: 'M' },
              ]}
              onChange={(id) => setIncSexFilter(id as 'ALL' | 'F' | 'M')}
            />
            <input
              type="text"
              className="input"
              placeholder={t.filter}
              value={incSearch}
              onChange={(e) => setIncSearch(e.target.value)}
              style={{ width: 150, padding: '4px 10px', fontSize: 12 }}
            />
            {loadingInc && <Spinner />}
          </div>
        </div>

        <div className={`table-wrap ${loadingInc ? 'busy' : ''}`} style={{ maxHeight: 380 }}>
          <table>
            <thead>
              <tr>
                <th>{t.sex}</th>
                <th>{t.tissue}</th>
                <th>{t.finding}</th>
                <th>0</th>
                <th>20</th>
                <th>200</th>
                <th>400</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f, idx) => {
                const isKey = `${f.tissue} ${f.finding}` === 'GLAND, ADRENAL Vacuolization';
                return (
                  <tr
                    key={`${f.sex}-${f.tissue}-${f.finding}-${idx}`}
                    style={isKey ? { background: 'rgba(41, 215, 212, 0.08)' } : undefined}
                  >
                    <td>
                      <span className={`status-pill ${f.sex === 'F' ? 'info' : ''}`}>{f.sex}</span>
                    </td>
                    <td className="mono" style={{ fontWeight: 600, color: '#fff' }}>
                      {f.tissue}
                    </td>
                    <td>
                      {f.finding}
                      {isKey && (
                        <span className="prod-badge" style={{ marginLeft: 6 }}>
                          {t.key}
                        </span>
                      )}
                    </td>
                    {f.groups.map((g) => {
                      if (g.status === 'not examined' || !g.examined) {
                        return (
                          <td key={g.dose} className="mono" style={{ color: 'var(--dim)' }}>
                            {t.notExamined}
                          </td>
                        );
                      }
                      const ratio = (g.affected || 0) / g.examined;
                      return (
                        <td key={g.dose}>
                          <div className="row" style={{ gap: 8, flexWrap: 'nowrap' }}>
                            <span
                              className="mono"
                              style={{
                                minWidth: 40,
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
                            <span className="bar" style={{ flex: 1 }}>
                              <i className={ratio >= 0.6 ? 'hot' : ''} style={{ width: `${Math.round(ratio * 100)}%` }} />
                            </span>
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

      <div className="grid two">
        <div className="panel">
          <div className="panel-head">
            <h2>{t.bodyWeight} · BW D29</h2>
            <div className="row">
              <Seg
                value={bwSex}
                options={[
                  { id: 'F', label: 'F' },
                  { id: 'M', label: 'M' },
                ]}
                onChange={(id) => setBwSex(id as 'F' | 'M')}
              />
              <Seg
                value={bwPop}
                options={[
                  { id: 'main_and_recovery', label: t.mainRec },
                  { id: 'main', label: t.mainOnly },
                ]}
                onChange={(id) => setBwPop(id as 'main_and_recovery' | 'main')}
              />
            </div>
          </div>

          <div className={`chart-box ${loadingBw ? 'busy' : ''}`} style={{ marginBottom: 10 }}>
            <svg viewBox="0 0 520 155" style={{ width: '100%', height: 150, display: 'block' }}>
              <defs>
                <linearGradient id="bwWarnGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f5b84c" />
                  <stop offset="100%" stopColor="#d96b43" />
                </linearGradient>
              </defs>
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
                      fill={g.dose === 0 ? '#3a7ca5' : isReduced ? 'url(#bwWarnGrad)' : '#29d7d4'}
                    />
                    <text x={x + 32} y={y - 16} textAnchor="middle" fill="#fff" fontSize="11" fontWeight="700" fontFamily="var(--mono)">
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
                      {g.percent_lower_than_control === null ? t.control : `-${g.percent_lower_than_control}%`}
                    </text>
                    <text x={x + 32} y={138} textAnchor="middle" fill="#b8d4df" fontSize="11" fontFamily="var(--mono)">
                      {g.dose} (n={g.n})
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t.dose}</th>
                  <th className="num">n</th>
                  <th className="num">{t.meanDay29}</th>
                  <th className="num">{t.vsControl}</th>
                  <th className="num">{t.vsBaseline}</th>
                </tr>
              </thead>
              <tbody>
                {bwGroups.map((g) => (
                  <tr key={g.dose}>
                    <td className="mono">{g.dose}</td>
                    <td className="num">{g.n}</td>
                    <td className="num">{g.mean_day29_g.toFixed(2)}</td>
                    <td
                      className="num"
                      style={{
                        color: (g.percent_lower_than_control || 0) >= 10 ? 'var(--amber)' : 'var(--cyan2)',
                        fontWeight: 600,
                      }}
                    >
                      {g.percent_lower_than_control === null ? '—' : `${g.percent_lower_than_control.toFixed(2)}%`}
                    </td>
                    <td className="num">+{g.mean_change_from_baseline_g.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {bwObs && (
            <div className="row" style={{ marginTop: 8 }}>
              <span className={`status-pill ${negAnimals.length === 0 ? '' : 'warn'}`}>
                {t.weightLoss}: {negAnimals.length} {t.animalsShort}
              </span>
              {negAnimals.map((a) => (
                <span key={a.usubjid} className="chip">
                  {a.usubjid} · {a.dose} · {a.change_g} g
                </span>
              ))}
            </div>
          )}

          <ObservationDrawer observation={bwObs} locale={locale} />
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>{t.tk} · AUCtau</h2>
            <div className="row">
              <Seg
                value={tkSex}
                options={[
                  { id: 'M', label: 'M' },
                  { id: 'F', label: 'F' },
                ]}
                onChange={(id) => setTkSex(id as 'F' | 'M')}
              />
              <Seg
                value={String(tkDose)}
                options={[20, 200, 400].map((d) => ({ id: String(d), label: String(d) }))}
                onChange={(id) => setTkDose(Number(id))}
              />
              <Seg
                value={String(tkDay)}
                options={[1, 29].map((d) => ({ id: String(d), label: `D${d}` }))}
                onChange={(id) => setTkDay(Number(id))}
              />
            </div>
          </div>

          {!tkObs ? (
            <div className="center-pad">
              <Spinner />
            </div>
          ) : (
            <div className={`stack ${loadingTk ? 'busy' : ''}`}>
              <div className="grid two">
                <div className={`tile ${tkObs.values.contains_quarantined ? 'bad' : ''}`}>
                  <div className="tile-label">{t.withQ}</div>
                  <div className="tile-value">
                    {tkObs.values.with_quarantined.mean !== null
                      ? tkObs.values.with_quarantined.mean.toLocaleString()
                      : '—'}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    n = {tkObs.values.with_quarantined.n} · h*ng/mL
                  </div>
                </div>
                <div className="tile ok">
                  <div className="tile-label">{t.cleanMean}</div>
                  <div className="tile-value" style={{ color: 'var(--green)' }}>
                    {tkObs.values.without_quarantined.mean !== null
                      ? tkObs.values.without_quarantined.mean.toLocaleString()
                      : '—'}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    n = {tkObs.values.without_quarantined.n} · {t.ratio} {tkObs.values.ratio_without_over_with ?? '1.0'}×
                  </div>
                </div>
              </div>

              {tkObs.values.contains_quarantined ? (
                <div className="row">
                  <span className="status-pill warn">
                    <Icon name="alert" size={12} /> {t.quarantined}
                  </span>
                  {tkObs.values.quarantined_rows.map((q) => (
                    <span key={q.usubjid} className="chip">
                      {q.usubjid} · PP #{q.source_row} · {q.value.toLocaleString()}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="row">
                  <span className="status-pill">
                    <Icon name="check" size={12} /> {t.plausible}
                  </span>
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
