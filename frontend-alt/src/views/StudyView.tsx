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
import { Icon, Spinner } from '../components/Icon';
import { ObservationDrawer } from '../components/ObservationDrawer';
import { Locale, UI_TEXT } from '../i18n';

interface StudyViewProps {
  locale: Locale;
}

type SwitchMode = 'none' | 'negative' | 'duplicate' | 'dose';

export const StudyView: React.FC<StudyViewProps> = ({ locale }) => {
  const t = UI_TEXT[locale];
  const [designObs, setDesignObs] = useState<Observation<StudyDesignValues> | null>(null);
  const [jobRes, setJobRes] = useState<JobResponse | null>(null);
  const [switchRes, setSwitchRes] = useState<ParsedStudySwitchResult | null>(null);
  const [activeSwitch, setActiveSwitch] = useState<SwitchMode>('none');
  const [loadingSwitch, setLoadingSwitch] = useState(false);
  const [loadingJob, setLoadingJob] = useState(false);
  const [filterTest, setFilterTest] = useState<string>('ALL');

  useEffect(() => {
    fetchStudyDesign()
      .then((res) => setDesignObs(res))
      .catch(() => {});
    handleRunValidationJob();
  }, []);

  // Backend text (notes, labels) follows the active language: refetch on toggle.
  useEffect(() => {
    handleSwitch(activeSwitch);
  }, [locale]);

  const handleRunValidationJob = async () => {
    setLoadingJob(true);
    try {
      setJobRes(await runValidateStudyJob());
    } catch {
      // keep previous result
    } finally {
      setLoadingJob(false);
    }
  };

  const handleSwitch = async (mode: SwitchMode) => {
    setActiveSwitch(mode);
    setLoadingSwitch(true);
    try {
      setSwitchRes(await runStudySwitch(mode, locale));
    } catch {
      // keep previous result
    } finally {
      setLoadingSwitch(false);
    }
  };

  const report = jobRes?.outputs?.report;
  const domainEntries = report ? Object.entries(report.rows) : [];
  const maxRows = domainEntries.reduce((acc, [, count]) => Math.max(acc, count), 1);

  const qRows = report?.quarantine.rows || [];
  const filteredQRows = filterTest === 'ALL' ? qRows : qRows.filter((r) => r.test === filterTest);

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
  const barW = (v: number) => Math.max(18, Math.min(340, (Math.abs(v) / 16000) * 320));

  const modes: Array<{ id: SwitchMode; label: string }> = [
    { id: 'none', label: t.baseline },
    { id: 'negative', label: t.negAuc },
    { id: 'duplicate', label: t.dupId },
    { id: 'dose', label: t.badDose },
  ];

  return (
    <div className="stack">
      <div className="page-head">
        <h1>{t.study}</h1>
        <div className="head-actions">
          <button className="btn secondary sm" disabled title={t.prodTip}>
            <Icon name="upload" size={13} /> {t.upload}
            <span className="prod-badge">{t.production}</span>
          </button>
          <button
            className="btn secondary sm"
            onClick={handleRunValidationJob}
            disabled={loadingJob}
            title={t.rerun}
          >
            {loadingJob ? <Spinner /> : <Icon name="reset" size={13} />} {t.rerun}
          </button>
        </div>
      </div>

      <div className="grid main-side">
        <div className="panel">
          <div className="panel-head">
            <div className="seg-group">
              {modes.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={`seg-btn ${activeSwitch === m.id ? 'active' : ''}`}
                  onClick={() => handleSwitch(m.id)}
                  disabled={loadingSwitch}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <span className="status-pill warn">
              {switchRes?.totalQuarantined ?? 12} {t.quarantined.toLowerCase()}
            </span>
          </div>

          {switchRes?.reportedIntegrityNote && (
            <div className="callout warn" style={{ marginBottom: 10 }}>
              {switchRes.reportedIntegrityNote}
            </div>
          )}
          {switchRes?.injectedNote && (
            <div className="callout danger" style={{ marginBottom: 10 }}>
              {switchRes.injectedNote}
            </div>
          )}

          <div className={loadingSwitch ? 'busy' : ''}>
            <div className="tile-label" style={{ marginBottom: 6 }}>
              AUCtau D1 · M 20 mg/kg/day · h*ng/mL
            </div>
            <div className="grid two">
              <div className="tile bad">
                <div className="tile-label">{t.withQ}</div>
                <div className="tile-value" style={{ color: '#ff858b' }}>
                  {switchRes?.withQuarantinedMean || '2,821'}
                </div>
                {switchRes?.withQuarantinedLabel && (
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    {switchRes.withQuarantinedLabel}
                  </div>
                )}
              </div>
              <div className="tile ok">
                <div className="tile-label">{t.clean}</div>
                <div className="tile-value" style={{ color: 'var(--green)' }}>
                  {switchRes?.withoutQuarantinedMean || '15,956'}
                </div>
                {switchRes?.withoutQuarantinedLabel && (
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    {switchRes.withoutQuarantinedLabel}
                  </div>
                )}
              </div>
            </div>

            <div className="chart-box" style={{ marginTop: 10 }}>
              <svg viewBox="0 0 600 80" style={{ width: '100%', height: 80, display: 'block' }}>
                <text x={10} y={26} fill="#ffb4b8" fontSize="11" fontFamily="var(--mono)">
                  {t.withQ}
                </text>
                <rect
                  x={145}
                  y={12}
                  width={barW(withBadVal)}
                  height={20}
                  rx={4}
                  fill={withBadVal < 0 ? '#f36b6b' : '#f5b84c'}
                />
                <text x={155 + barW(withBadVal)} y={26} fill="#ffd58b" fontSize="11" fontFamily="var(--mono)">
                  {withBadVal.toLocaleString()}
                </text>
                <text x={10} y={62} fill="#8ef5d8" fontSize="11" fontFamily="var(--mono)">
                  {t.clean}
                </text>
                <rect x={145} y={48} width={barW(cleanVal)} height={20} rx={4} fill="#2fd389" />
                <text x={155 + barW(cleanVal)} y={62} fill="#8ef5d8" fontSize="11" fontFamily="var(--mono)">
                  {cleanVal.toLocaleString()}
                  {withBadVal > 0 && cleanVal > 0
                    ? ` (${(cleanVal / withBadVal).toFixed(2)}× ${t.higher})`
                    : ''}
                </text>
              </svg>
            </div>
            {switchRes?.effectNote && (
              <div className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
                {switchRes.effectNote}
              </div>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2>{t.domains}</h2>
            <span className="status-pill">0 {t.failures}</span>
          </div>

          {jobRes && (
            <div className="row" style={{ marginBottom: 10 }}>
              <span className="chip" title={jobRes.inputs_sha256}>
                in <strong style={{ color: 'var(--cyan2)' }}>{jobRes.inputs_sha256.slice(0, 10)}</strong>
              </span>
              {report && (
                <span className="chip" title={report.report_sha256}>
                  out <strong style={{ color: 'var(--green)' }}>{report.report_sha256.slice(0, 10)}</strong>
                </span>
              )}
            </div>
          )}

          {!report ? (
            <div className="center-pad">
              <Spinner />
            </div>
          ) : (
            <>
              <div className="stack" style={{ gap: 7 }}>
                {domainEntries.map(([dom, count]) => (
                  <div
                    key={dom}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '40px 1fr 56px',
                      alignItems: 'center',
                      gap: 10,
                      fontSize: 12,
                    }}
                  >
                    <strong className="mono" style={{ color: 'var(--cyan2)' }}>
                      {dom}
                    </strong>
                    <span className="bar">
                      <i style={{ width: `${Math.max(4, (count / maxRows) * 100)}%` }} />
                    </span>
                    <span className="mono" style={{ textAlign: 'right' }}>
                      {count.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>

              <div className="stack" style={{ gap: 6, marginTop: 12 }}>
                <div className="kv">
                  <span>{t.deaths}</span>
                  <strong style={{ color: 'var(--amber)' }}>
                    {report.deaths[0]
                      ? `${report.deaths[0].usubjid} · D${report.deaths[0].day}`
                      : '—'}
                  </strong>
                </div>
                <div className="kv">
                  <span>{t.age}</span>
                  <strong style={{ color: 'var(--amber)' }}>
                    “{report.age.ts_age_text}” · {report.age.animals_mismatching}
                  </strong>
                </div>
                <div className="kv">
                  <span>{t.xptZeros}</span>
                  <strong>
                    {report.xpt_zeros_normalised['DM.AGE']} · {report.xpt_zeros_normalised['PC.PCTPTNUM']}
                  </strong>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid two">
        <div className="panel">
          <div className="panel-head">
            <h2>
              {t.quarantineRows} ({filteredQRows.length})
            </h2>
            <div className="seg-group">
              {(['ALL', 'AUCTAU', 'AUCIFO'] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`seg-btn ${filterTest === k ? 'active' : ''}`}
                  onClick={() => setFilterTest(k)}
                >
                  {k}
                </button>
              ))}
            </div>
          </div>

          <div className="table-wrap" style={{ maxHeight: 300 }}>
            <table>
              <thead>
                <tr>
                  <th>{t.animal}</th>
                  <th>{t.row}</th>
                  <th>{t.param}</th>
                  <th>{t.day}</th>
                  <th className="num">{t.value}</th>
                  <th>{t.rule}</th>
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
                    <td>
                      <span className={`status-pill ${r.test === 'AUCTAU' ? 'warn' : 'info'}`}>{r.test}</span>
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

        <div className="panel">
          <div className="panel-head">
            <h2>{t.design}</h2>
            {designObs && (
              <span className="chip">
                {designObs.values.species} · {designObs.values.route}
              </span>
            )}
          </div>

          {!designObs ? (
            <div className="center-pad">
              <Spinner />
            </div>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 300 }}>
              <table>
                <thead>
                  <tr>
                    <th>SETCD</th>
                    <th>{t.group}</th>
                    <th>{t.sex}</th>
                    <th className="num">{t.dose}</th>
                    <th>{t.cohort}</th>
                    <th className="num">n</th>
                  </tr>
                </thead>
                <tbody>
                  {designObs.values.groups.map((g) => (
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
                        <span className={`status-pill ${g.toxicokinetic ? 'info' : ''}`}>
                          {g.toxicokinetic ? t.tkSat : t.main}
                        </span>
                      </td>
                      <td className="num">{g.animals}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <ObservationDrawer observation={designObs} locale={locale} />
        </div>
      </div>
    </div>
  );
};
