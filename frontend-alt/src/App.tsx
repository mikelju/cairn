import React, { useEffect, useRef, useState } from 'react';
import {
  Actor,
  AuditVerifyResponse,
  ParsedProvenanceItem,
  ThreadView,
  checkHealth,
  getThread,
  startThread,
  verifyThreadAudit,
} from './api';
import { Icon, Spinner } from './components/Icon';
import { ProvenanceModal } from './components/ProvenanceModal';
import { Locale, UI_TEXT, ViewId } from './i18n';
import { AssessmentView } from './views/AssessmentView';
import { AuditView, SessionAuditEvent } from './views/AuditView';
import { DataExplorerView } from './views/DataExplorerView';
import { GuidelinesAskView } from './views/GuidelinesAskView';
import { OverviewView } from './views/OverviewView';
import { ReportView } from './views/ReportView';
import { StudyView } from './views/StudyView';

const STORAGE_KEY = 'cairn_alt_thread_id';

const VALID_VIEWS: ViewId[] = [
  'overview',
  'study',
  'data',
  'guidelines',
  'assessment',
  'report',
  'audit',
];

function getInitialView(): ViewId {
  const hash = window.location.hash.replace('#', '').trim() as ViewId;
  return VALID_VIEWS.includes(hash) ? hash : 'overview';
}

export const App: React.FC = () => {
  const [locale, setLocale] = useState<Locale>('en');
  const [activeView, setActiveView] = useState<ViewId>(getInitialView);
  const [actor, setActor] = useState<Actor>('R. Reviewer');
  const [healthy, setHealthy] = useState<boolean>(true);
  const [thread, setThread] = useState<ThreadView | null>(null);
  const [audit, setAudit] = useState<AuditVerifyResponse | null>(null);
  const [sessionEvents, setSessionEvents] = useState<SessionAuditEvent[]>([]);
  const [selectedProv, setSelectedProv] = useState<ParsedProvenanceItem | null>(null);
  const [resetting, setResetting] = useState<boolean>(false);
  const initPromiseRef = useRef<Promise<void> | null>(null);
  const auditCountRef = useRef<number>(0);

  const t = UI_TEXT[locale];

  const navigate = (v: ViewId) => {
    setActiveView(v);
    window.location.hash = v;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  useEffect(() => {
    const onHashChange = () => {
      const h = window.location.hash.replace('#', '').trim() as ViewId;
      if (VALID_VIEWS.includes(h)) {
        setActiveView(h);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const refreshAudit = async (tid?: string) => {
    const id = tid || thread?.thread_id;
    if (!id) return;
    try {
      const res = await verifyThreadAudit(id);
      auditCountRef.current = res.count;
      setAudit(res);
    } catch {
      // ignore
    }
  };

  const initThread = (forceNew = false): Promise<void> => {
    // StrictMode mounts effects twice: reuse the in-flight init so only one thread is created.
    if (initPromiseRef.current) return initPromiseRef.current;
    const p = doInitThread(forceNew).finally(() => {
      initPromiseRef.current = null;
    });
    initPromiseRef.current = p;
    return p;
  };

  const doInitThread = async (forceNew: boolean) => {
    setResetting(true);
    try {
      const saved = !forceNew ? localStorage.getItem(STORAGE_KEY) : null;
      let loaded: ThreadView | null = null;
      if (saved) {
        try {
          loaded = await getThread(saved);
        } catch {
          loaded = null;
        }
      }
      if (!loaded) {
        loaded = await startThread();
        localStorage.setItem(STORAGE_KEY, loaded.thread_id);
      }
      setThread(loaded);
      const aud = await verifyThreadAudit(loaded.thread_id);
      auditCountRef.current = aud.count;
      setAudit(aud);
      const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
      setSessionEvents([
        {
          seqHint: '#1',
          ts: nowIso,
          actor: loaded.author || 'A. Author',
          action: 'thread_started',
          detail: `thread started (${loaded.waiting})`,
          status: 'ok',
        },
      ]);
    } finally {
      setResetting(false);
    }
  };

  useEffect(() => {
    document.cookie = `cairn_lang=${locale}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    checkHealth()
      .then((res) => setHealthy(res.status === 'ok'))
      .catch(() => setHealthy(false));
    initThread(false);
  }, []);

  // Chain entries written by one action can be several (confirm both sexes writes
  // noael_confirmed, verify_final and judge_run): show the range, not only the last.
  const seqRange = (prevCount: number, newCount: number): string =>
    newCount > prevCount + 1 ? `#${prevCount + 1}-#${newCount}` : `#${newCount}`;

  const handleThreadUpdated = async (
    updated: ThreadView,
    actionLabel: string,
    effectiveActor?: Actor,
  ) => {
    setThread(updated);
    const prevCount = auditCountRef.current;
    const aud = await verifyThreadAudit(updated.thread_id);
    auditCountRef.current = aud.count;
    setAudit(aud);
    const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    setSessionEvents((prev) => [
      ...prev,
      {
        seqHint: seqRange(prevCount, aud.count),
        ts: nowIso,
        actor: effectiveActor || actor,
        action: actionLabel.split(' ')[0],
        detail: actionLabel,
        status: 'ok',
      },
    ]);
  };

  const handleAuditRefusal = async (
    actionLabel: string,
    status: number,
    detail: string,
    effectiveActor?: Actor,
  ) => {
    if (!thread) return;
    const aud = await verifyThreadAudit(thread.thread_id);
    auditCountRef.current = aud.count;
    setAudit(aud);
    const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    setSessionEvents((prev) => [
      ...prev,
      {
        seqHint: `#${aud.count}`,
        ts: nowIso,
        actor: effectiveActor || actor,
        action: `refused (${actionLabel})`,
        detail: `HTTP ${status}: ${detail}`,
        status: 'refused',
      },
    ]);
  };

  const bothConfirmed =
    Boolean(thread?.confirmed.includes('F')) && Boolean(thread?.confirmed.includes('M'));

  const NAV: Array<{ id: ViewId; label: string; pill?: { text: string; cls: string } }> = [
    { id: 'overview', label: t.navOverview },
    { id: 'study', label: t.navStudy },
    { id: 'data', label: t.navData },
    { id: 'guidelines', label: t.navGuidelines },
    {
      id: 'assessment',
      label: t.navAssessment,
      pill: bothConfirmed ? { text: '✓', cls: 'ok' } : { text: t.decide, cls: 'warn' },
    },
    {
      id: 'report',
      label: t.navReport,
      pill: thread?.approved_by ? { text: t.signed, cls: 'ok' } : { text: t.draft, cls: 'warn' },
    },
    { id: 'audit', label: t.navAudit, pill: audit ? { text: String(audit.count), cls: audit.ok ? 'ok' : 'warn' } : undefined },
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 28 28" width="22" height="22" fill="none">
              <ellipse cx="14" cy="22" rx="9" ry="2.8" stroke="currentColor" strokeWidth="1.8" />
              <ellipse cx="14" cy="15.5" rx="6.5" ry="2.4" stroke="currentColor" strokeWidth="1.8" />
              <ellipse cx="14" cy="9.5" rx="4.2" ry="2" stroke="currentColor" strokeWidth="1.8" />
              <circle cx="14" cy="4.5" r="2" fill="currentColor" />
            </svg>
          </div>
          <div className="brand-name">CAIRN</div>
        </div>

        <button type="button" className="new-analysis-btn" disabled title={t.prodTip}>
          <span className="row" style={{ gap: 6 }}>
            <Icon name="plus" size={14} />
            {t.newAnalysis}
          </span>
          <span className="prod-badge">{t.production}</span>
        </button>

        <nav className="nav" aria-label="Main">
          {NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              className={`nav-item ${activeView === n.id ? 'active' : ''}`}
              onClick={() => navigate(n.id)}
            >
              <span className="nav-item-left">
                <span className="nav-icon">
                  <Icon name={n.id} size={16} />
                </span>
                <span>{n.label}</span>
              </span>
              {n.pill && <span className={`nav-pill ${n.pill.cls}`}>{n.pill.text}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="env-row">
            <span className={`health-dot ${healthy ? '' : 'offline'}`}>
              {healthy ? t.online : t.offline}
            </span>
            <span className="mono" style={{ color: 'var(--cyan2)', fontSize: 11 }}>
              9b981329b14d
            </span>
          </div>
          <div style={{ fontSize: 10.5, color: '#6b8c9b' }}>{t.demo}</div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <span className="chip study">PDS2014 · SEND</span>
            {thread && (
              <span className="chip" title={thread.thread_id}>
                {thread.thread_id.slice(0, 8)}
                <span style={{ color: 'var(--cyan2)' }}>{thread.waiting}</span>
              </span>
            )}
            <button
              type="button"
              className="icon-btn"
              onClick={() => initThread(true)}
              disabled={resetting}
              title={t.newThread}
              aria-label={t.newThread}
            >
              {resetting ? <Spinner /> : <Icon name="reset" size={14} />}
            </button>
          </div>

          <div className="topbar-right">
            <div className="seg-group" title={t.role} aria-label={t.role}>
              <button
                type="button"
                className={`seg-btn ${actor === 'A. Author' ? 'active author-mode' : ''}`}
                onClick={() => setActor('A. Author')}
              >
                A. Author
              </button>
              <button
                type="button"
                className={`seg-btn ${actor === 'R. Reviewer' ? 'active' : ''}`}
                onClick={() => setActor('R. Reviewer')}
              >
                R. Reviewer
              </button>
            </div>
            <div className="seg-group" aria-label="Language">
              <button
                type="button"
                className={`seg-btn ${locale === 'en' ? 'active' : ''}`}
                onClick={() => setLocale('en')}
              >
                EN
              </button>
              <button
                type="button"
                className={`seg-btn ${locale === 'es' ? 'active' : ''}`}
                onClick={() => setLocale('es')}
              >
                ES
              </button>
            </div>
          </div>
        </header>

        <main className="content">
          {activeView === 'overview' && (
            <OverviewView
              locale={locale}
              thread={thread}
              audit={audit}
              onNavigate={navigate}
              onSelectProvenance={setSelectedProv}
            />
          )}
          {activeView === 'study' && <StudyView locale={locale} />}
          {activeView === 'data' && <DataExplorerView locale={locale} />}
          {activeView === 'guidelines' && (
            <GuidelinesAskView locale={locale} onSelectProvenance={setSelectedProv} />
          )}
          {activeView === 'assessment' && (
            <AssessmentView
              locale={locale}
              actor={actor}
              thread={thread}
              onThreadUpdated={handleThreadUpdated}
              onAuditRefusal={handleAuditRefusal}
              onResetThread={() => initThread(true)}
              onNavigate={navigate}
            />
          )}
          {activeView === 'report' && (
            <ReportView
              locale={locale}
              actor={actor}
              onChangeActor={setActor}
              thread={thread}
              onThreadUpdated={handleThreadUpdated}
              onAuditRefusal={handleAuditRefusal}
              onNavigate={navigate}
              onSelectProvenance={setSelectedProv}
            />
          )}
          {activeView === 'audit' && (
            <AuditView
              locale={locale}
              thread={thread}
              audit={audit}
              sessionEvents={sessionEvents}
              onRefreshAudit={() => refreshAudit()}
            />
          )}
        </main>
      </div>

      <ProvenanceModal
        item={selectedProv}
        locale={locale}
        onClose={() => setSelectedProv(null)}
        onGoToDecide={() => navigate('assessment')}
      />
    </div>
  );
};
