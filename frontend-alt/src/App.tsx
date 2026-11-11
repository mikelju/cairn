import React, { useEffect, useState } from 'react';
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
  const [showNewModal, setShowNewModal] = useState<boolean>(false);
  const [selectedProv, setSelectedProv] = useState<ParsedProvenanceItem | null>(null);
  const [resetting, setResetting] = useState<boolean>(false);

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
      setAudit(res);
    } catch {
      // ignore
    }
  };

  const initThread = async (forceNew = false) => {
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
      setAudit(aud);
      const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
      setSessionEvents([
        {
          seqHint: '#1',
          ts: nowIso,
          actor: loaded.author || 'A. Author',
          action: 'thread_started',
          detail: `Initialized LangGraph replay workflow on PDS2014 snapshot (waiting=${loaded.waiting})`,
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

  const handleThreadUpdated = async (updated: ThreadView, actionLabel: string) => {
    setThread(updated);
    const aud = await verifyThreadAudit(updated.thread_id);
    setAudit(aud);
    const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    setSessionEvents((prev) => [
      ...prev,
      {
        seqHint: `#${aud.count}`,
        ts: nowIso,
        actor,
        action: actionLabel.split(' ')[0],
        detail: actionLabel,
        status: 'ok',
      },
    ]);
  };

  const handleAuditRefusal = async (actionLabel: string, status: number, detail: string) => {
    if (!thread) return;
    const aud = await verifyThreadAudit(thread.thread_id);
    setAudit(aud);
    const nowIso = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
    setSessionEvents((prev) => [
      ...prev,
      {
        seqHint: `#${aud.count}`,
        ts: nowIso,
        actor,
        action: `refused (${actionLabel})`,
        detail: `HTTP ${status}: ${detail}`,
        status: 'refused',
      },
    ]);
  };

  const bothConfirmed =
    Boolean(thread?.confirmed.includes('F')) && Boolean(thread?.confirmed.includes('M'));

  return (
    <div className="app">
      {/* Persistent Left Sidebar */}
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
          <div>
            <div className="brand-name">CAIRN</div>
            <div className="brand-sub">{t.brandSub}</div>
          </div>
        </div>

        {/* Production Preview + New Analysis Button */}
        <button
          type="button"
          className="new-analysis-btn"
          onClick={() => setShowNewModal(true)}
          title="Click to learn how study ingestion works in production vs. this pinned demo"
        >
          <span>{t.newAnalysis}</span>
          <span className="prod-badge">{t.prodPreview}</span>
        </button>

        <div className="nav-label">{t.navSectionMain}</div>
        <nav className="nav" aria-label="Main Navigation">
          <button
            type="button"
            className={`nav-item ${activeView === 'overview' ? 'active' : ''}`}
            onClick={() => navigate('overview')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">◈</span>
              <span>{t.navOverview}</span>
            </span>
            <span className="nav-pill">PDS2014</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeView === 'study' ? 'active' : ''}`}
            onClick={() => navigate('study')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">⬡</span>
              <span>{t.navStudy}</span>
            </span>
            <span className="nav-pill ok">12 Held</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeView === 'data' ? 'active' : ''}`}
            onClick={() => navigate('data')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">📊</span>
              <span>{t.navData}</span>
            </span>
            <span className="nav-pill">4 Tools</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeView === 'guidelines' ? 'active' : ''}`}
            onClick={() => navigate('guidelines')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">📘</span>
              <span>{t.navGuidelines}</span>
            </span>
            <span className="nav-pill">13 Q&amp;A</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeView === 'assessment' ? 'active' : ''}`}
            onClick={() => navigate('assessment')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">⚖</span>
              <span>{t.navAssessment}</span>
            </span>
            <span className={`nav-pill ${bothConfirmed ? 'ok' : 'warn'}`}>
              {bothConfirmed ? 'NOAEL ✓' : 'Decide'}
            </span>
          </button>
        </nav>

        <div className="nav-label" style={{ marginTop: 8 }}>
          {t.navSectionGov}
        </div>
        <nav className="nav" aria-label="Governance Navigation">
          <button
            type="button"
            className={`nav-item ${activeView === 'report' ? 'active' : ''}`}
            onClick={() => navigate('report')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">📄</span>
              <span>{t.navReport}</span>
            </span>
            <span className={`nav-pill ${thread?.approved_by ? 'ok' : 'warn'}`}>
              {thread?.approved_by ? 'Signed' : 'Draft'}
            </span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeView === 'audit' ? 'active' : ''}`}
            onClick={() => navigate('audit')}
          >
            <span className="nav-item-left">
              <span className="nav-icon">⛓</span>
              <span>{t.navAudit}</span>
            </span>
            <span className="nav-pill ok">
              {audit ? `${audit.count} SHA` : 'SHA-256'}
            </span>
          </button>
        </nav>

        <div className="sidebar-bottom">
          <div className="env-row">
            <span>FastAPI Backend</span>
            <span className={`health-dot ${healthy ? '' : 'offline'}`}>
              {healthy ? t.backendHealthy : t.backendOffline}
            </span>
          </div>
          <div className="env-row">
            <span>Bedrock Region</span>
            <span className="mono" style={{ color: '#cfe4ec', fontSize: 11 }}>
              eu-west-1 (Replay)
            </span>
          </div>
          <div className="env-row">
            <span>Snapshot Hash</span>
            <span className="mono" style={{ color: 'var(--cyan2)', fontSize: 11 }}>
              9b981329b14d
            </span>
          </div>
          <div
            style={{
              marginTop: 4,
              paddingTop: 8,
              borderTop: '1px solid #133242',
              fontSize: 10.5,
              color: '#6b8c9b',
            }}
          >
            {t.notGxp}
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <div className="workspace">
        {/* Persistent Top Context Bar */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="chip study">{t.studyPill}</span>
            {thread && (
              <span className="chip" title={`Full thread_id: ${thread.thread_id}`}>
                thread: <strong style={{ color: '#fff' }}>{thread.thread_id.slice(0, 8)}…</strong>
                <span style={{ color: 'var(--cyan2)' }}>({thread.waiting})</span>
              </span>
            )}
            <button
              type="button"
              className="btn secondary sm"
              onClick={() => initThread(true)}
              disabled={resetting}
              style={{ padding: '4px 10px', fontSize: 11.5 }}
            >
              ↻ {t.resetThread}
            </button>
          </div>

          <div className="topbar-right">
            {/* Role Switcher (A. Author vs R. Reviewer) */}
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              title={actor === 'A. Author' ? t.roleAuthorHint : t.roleReviewerHint}
            >
              <span style={{ fontSize: 11.5, color: 'var(--muted)' }}>{t.activeRole}:</span>
              <div className="seg-group">
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
            </div>

            {/* Bilingual Language Toggle (EN | ES) */}
            <div className="seg-group" aria-label="Language selector">
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

        {/* Active View Content */}
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
              onChangeActor={setActor}
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

      {/* Production Preview Modal for "+ New Analysis" */}
      {showNewModal && (
        <div className="modal-backdrop" onClick={() => setShowNewModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <div>
                <span className="prod-badge">{t.prodPreview}</span>
                <h2 style={{ marginTop: 6 }}>{t.modalNewTitle}</h2>
              </div>
              <button className="btn secondary sm" onClick={() => setShowNewModal(false)}>
                {t.close} ✕
              </button>
            </div>
            <p style={{ fontSize: 13.5, color: '#d7eaf1', lineHeight: 1.65 }}>
              {t.modalNewDesc}
            </p>
            <div className="callout warn" style={{ margin: '14px 0' }}>
              {t.modalNewDemoNote}
            </div>
            <div className="dropzone-preview" style={{ opacity: 0.75 }}>
              <div>
                <strong style={{ color: '#fff' }}>
                  CDISC SEND Study Package (.xpt) + Protocol PDF
                </strong>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                  DM.xpt, TX.xpt, TS.xpt, DS.xpt, MI.xpt, BW.xpt, PP.xpt, PC.xpt
                </div>
              </div>
              <button className="btn secondary sm" disabled>
                Upload Disabled in Demo
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Provenance Inspector Modal */}
      <ProvenanceModal
        item={selectedProv}
        locale={locale}
        onClose={() => setSelectedProv(null)}
        onGoToDecide={() => navigate('assessment')}
      />
    </div>
  );
};
