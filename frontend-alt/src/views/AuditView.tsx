import React, { useState } from 'react';
import { AuditVerifyResponse, ThreadView } from '../api';
import { Locale } from '../i18n';

export interface SessionAuditEvent {
  seqHint: string;
  ts: string;
  actor: string;
  action: string;
  detail: string;
  status: 'ok' | 'refused';
}

interface AuditViewProps {
  locale: Locale;
  thread: ThreadView | null;
  audit: AuditVerifyResponse | null;
  sessionEvents: SessionAuditEvent[];
  onRefreshAudit: () => Promise<void>;
}

export const AuditView: React.FC<AuditViewProps> = ({
  locale,
  thread,
  audit,
  sessionEvents,
  onRefreshAudit,
}) => {
  const [verifying, setVerifying] = useState(false);

  const handleVerifyNow = async () => {
    setVerifying(true);
    try {
      await onRefreshAudit();
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <div className="eyebrow">
            {locale === 'en'
              ? 'STAGE 5 · CRYPTOGRAPHIC SHA-256 AUDIT TRAIL & TAMPER VERIFICATION'
              : 'ETAPA 5 · CADENA DE AUDITORÍA CRIPTOGRÁFICA SHA-256 Y VERIFICACIÓN'}
          </div>
          <h1>
            {locale === 'en'
              ? 'Tamper-Evident SHA-256 Hash Chain'
              : 'Cadena de Bloques SHA-256 a Prueba de Manipulaciones'}
          </h1>
          <p className="lede">
            {locale === 'en'
              ? 'Every workflow event—including rejected 403/409 attempts by an unauthorized role—is appended to SQLite with a canonical SHA-256 hash chained to the previous entry.'
              : 'Cada evento del flujo —incluidos los intentos rechazados con 403/409 por rol no autorizado— se añade a SQLite con un hash SHA-256 canónico encadenado al anterior.'}
          </p>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={handleVerifyNow} disabled={verifying}>
            {verifying
              ? locale === 'en'
                ? 'Verifying Chain…'
                : 'Verificando Cadena…'
              : locale === 'en'
                ? '✓ Verify SHA-256 Chain Integrity Now'
                : '✓ Verificar Integridad SHA-256 Ahora'}
          </button>
        </div>
      </div>

      {/* 3 KPI Cards for Audit Verification */}
      <div className="grid three">
        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en'
              ? 'CRYPTOGRAPHIC INTEGRITY (audit/verify)'
              : 'INTEGRIDAD CRIPTOGRÁFICA (audit/verify)'}
          </div>
          <div className={`kpi-value ${audit?.ok ? 'green' : 'amber'}`}>
            {audit ? (audit.ok ? 'INTACT (OK = TRUE)' : 'BROKEN') : '—'}
          </div>
          <div className="kpi-sub">
            GET /api/threads/{thread?.thread_id.slice(0, 8)}…/audit/verify
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'CHAINED SQLITE ENTRIES (COUNT)' : 'ENTRADAS ENCADENADAS EN SQLITE'}
          </div>
          <div className="kpi-value cyan">{audit?.count ?? 0}</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'Includes thread_started, decisions, refusals, confirm, verify & approve'
              : 'Incluye inicio, decisiones, rechazos, confirmación, verificador y firma'}
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            {locale === 'en' ? 'FIRST BROKEN SEQUENCE (first_broken)' : 'PRIMER ESLABÓN ROTO'}
          </div>
          <div className="kpi-value">{audit?.first_broken ?? 'null (0 tampered)'}</div>
          <div className="kpi-sub">
            {locale === 'en'
              ? 'Recomputes canonical_sha256 from genesis ("0"*64) through entry #N'
              : 'Recalcula canonical_sha256 desde el génesis ("0"*64) hasta la entrada #N'}
          </div>
        </div>
      </div>

      {/* Visual SHA-256 Hash-Chain Architecture Diagram */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? 'How Cairn Computes & Verifies Each Chained Audit Link'
                : 'Cómo Calcula y Verifica Cairn Cada Eslabón de la Cadena'}
            </h2>
            <p>
              {locale === 'en'
                ? 'Modifying or deleting any row in the SQLite audit_log table invalidates every subsequent entry_hash'
                : 'Modificar o borrar cualquier fila en la tabla SQLite audit_log invalida todos los hashes posteriores'}
              </p>
          </div>
          <span className="chip">cairn/audit.py · canonical_sha256</span>
        </div>

        <div
          style={{
            background: '#071824',
            border: '1px solid #1e4f63',
            borderRadius: 12,
            padding: 16,
          }}
        >
          <svg viewBox="0 0 880 140" style={{ width: '100%', height: 135, display: 'block' }}>
            {/* Block 1: Genesis */}
            <rect
              x={10}
              y={16}
              width={250}
              height={108}
              rx={10}
              fill="#0c2638"
              stroke="#29d7d4"
              strokeWidth="1.5"
            />
            <text x={24} y={38} fill="#70f0e8" fontSize="11" fontWeight="700" fontFamily="var(--mono)">
              SEQ #1 · thread_started
            </text>
            <text x={24} y={58} fill="#9db7c3" fontSize="10.5" fontFamily="var(--mono)">
              actor: &quot;A. Author&quot;
            </text>
            <text x={24} y={76} fill="#9db7c3" fontSize="10.5" fontFamily="var(--mono)">
              prev_hash: 0000000000000000…
            </text>
            <text x={24} y={102} fill="#2fd389" fontSize="10.5" fontWeight="600" fontFamily="var(--mono)">
              entry_hash: H₁ = SHA256(B₁)
            </text>

            {/* Arrow 1 -> 2 */}
            <path d="M 264 70 L 308 70" stroke="#29d7d4" strokeWidth="2" />
            <polygon points="308,65 318,70 308,75" fill="#29d7d4" />

            {/* Block 2: Reviewer / Refusal */}
            <rect
              x={320}
              y={16}
              width={255}
              height={108}
              rx={10}
              fill="#0c2638"
              stroke="#4d8df5"
              strokeWidth="1.5"
            />
            <text x={334} y={38} fill="#a3d0ff" fontSize="11" fontWeight="700" fontFamily="var(--mono)">
              SEQ #2..k · decisions / refused
            </text>
            <text x={334} y={58} fill="#9db7c3" fontSize="10.5" fontFamily="var(--mono)">
              actor: &quot;R. Reviewer&quot; | &quot;A. Author&quot;
            </text>
            <text x={334} y={76} fill="#70f0e8" fontSize="10.5" fontFamily="var(--mono)">
              prev_hash: H₁ (linked to #1)
            </text>
            <text x={334} y={102} fill="#2fd389" fontSize="10.5" fontWeight="600" fontFamily="var(--mono)">
              entry_hash: Hₖ = SHA256(Bₖ)
            </text>

            {/* Arrow 2 -> 3 */}
            <path d="M 579 70 L 618 70" stroke="#8b65f5" strokeWidth="2" />
            <polygon points="618,65 628,70 618,75" fill="#8b65f5" />

            {/* Block 3: Confirm / Verify / Approve */}
            <rect
              x={630}
              y={16}
              width={240}
              height={108}
              rx={10}
              fill="#0c2638"
              stroke="#8b65f5"
              strokeWidth="1.5"
            />
            <text x={644} y={38} fill="#ded2ff" fontSize="11" fontWeight="700" fontFamily="var(--mono)">
              SEQ #N · verify_final &amp; approved
            </text>
            <text x={644} y={58} fill="#9db7c3" fontSize="10.5" fontFamily="var(--mono)">
              actor: &quot;system&quot; | &quot;R. Reviewer&quot;
            </text>
            <text x={644} y={76} fill="#a3d0ff" fontSize="10.5" fontFamily="var(--mono)">
              prev_hash: Hₙ₋₁ (linked to #N-1)
            </text>
            <text x={644} y={102} fill="#2fd389" fontSize="10.5" fontWeight="600" fontFamily="var(--mono)">
              Verify: count = {audit?.count ?? 1}, ok = {String(audit?.ok ?? true)}
            </text>
          </svg>
        </div>
      </div>

      {/* Active Thread Event Timeline & Contract Note */}
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>
              {locale === 'en'
                ? `Active Thread Event Log (Thread ${thread?.thread_id.slice(0, 12)}…)`
                : `Registro de Eventos del Hilo Activo (${thread?.thread_id.slice(0, 12)}…)`}
            </h2>
            <p>
              {locale === 'en'
                ? 'Tracks every action and 403/409 refusal executed in this session alongside the live SQLite chain counter'
                : 'Registra cada acción y rechazo 403/409 ejecutado en esta sesión junto con el contador SQLite en vivo'}
            </p>
          </div>
          <span className="status-pill info">
            SQLite Chain Count: {audit?.count ?? 0}
          </span>
        </div>

        <div className="callout" style={{ marginBottom: 14 }}>
          <strong>
            {locale === 'en'
              ? 'Backend API Contract Note: '
              : 'Nota de Contrato de la API del Backend: '}
          </strong>
          {locale === 'en'
            ? 'By design, GET /api/threads/{thread_id}/audit/verify exposes cryptographic verification (ok, count, first_broken) without dumping raw SQLite rows over HTTP. The table below mirrors the exact events triggered during your session.'
            : 'Por diseño, GET /api/threads/{thread_id}/audit/verify expone la verificación criptográfica (ok, count, first_broken) sin volcar las filas crudas de SQLite por HTTP. La tabla inferior refleja los eventos ejecutados en tu sesión.'}
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event #</th>
                <th>Timestamp (UTC)</th>
                <th>Actor</th>
                <th>Chained Action</th>
                <th>Status</th>
                <th>Details / Payload Summary</th>
              </tr>
            </thead>
            <tbody>
              {sessionEvents.map((ev, idx) => (
                <tr key={idx}>
                  <td className="mono" style={{ color: 'var(--cyan2)', fontWeight: 700 }}>
                    {ev.seqHint}
                  </td>
                  <td className="mono">{ev.ts}</td>
                  <td className="mono" style={{ color: '#fff', fontWeight: 600 }}>
                    {ev.actor}
                  </td>
                  <td className="mono">{ev.action}</td>
                  <td>
                    <span
                      className={`status-pill ${ev.status === 'refused' ? 'block' : ''}`}
                      style={{ padding: '1px 7px' }}
                    >
                      {ev.status === 'refused' ? 'REFUSED (CHAINED)' : 'RECORDED'}
                    </span>
                  </td>
                  <td>{ev.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
