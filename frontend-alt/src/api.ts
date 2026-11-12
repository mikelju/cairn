// Typed API client and HTML fragment parsers for the existing FastAPI Cairn backend.
// Works 100% against existing endpoints via Vite proxy without modifying src/cairn/.

export type { ViewId } from './i18n';
export type Actor = 'A. Author' | 'R. Reviewer';

export interface HealthResponse {
  status: string;
}

export interface ToolInfo {
  name: string;
  version: string;
}

export interface Observation<T = Record<string, unknown>> {
  obs_id: string;
  kind: string;
  population: string;
  n_examined: number | null;
  values: T;
  sql: string;
  source_rows: Array<Record<string, unknown>>;
  content_sha256: string;
  tool: ToolInfo;
  snapshot_sha256: string;
}

export interface StudyDesignGroup {
  setcd: string;
  label: string;
  sex: 'F' | 'M';
  dose: number;
  dose_unit: string;
  toxicokinetic: boolean;
  animals: number;
}

export interface StudyDesignValues {
  study_id: string;
  species: string;
  strain: string;
  route: string;
  groups: StudyDesignGroup[];
}

export interface IncidenceGroup {
  dose: number;
  examined: number | null;
  affected: number | null;
  status: 'examined' | 'not examined';
}

export interface IncidenceFinding {
  sex: 'F' | 'M';
  tissue: string;
  finding: string;
  groups: IncidenceGroup[];
}

export interface IncidenceValues {
  screen: boolean;
  screen_rule: string | null;
  n_findings: number;
  findings: IncidenceFinding[];
}

export interface BodyWeightGroup {
  dose: number;
  n: number;
  mean_day29_g: number;
  percent_lower_than_control: number | null;
  mean_change_from_baseline_g: number;
}

export interface BodyWeightValues {
  sex: 'F' | 'M';
  day: number;
  wording: string;
  groups: BodyWeightGroup[];
  animals_with_negative_change: Array<{
    usubjid: string;
    dose: number;
    change_g: number;
  }>;
}

export interface TkSummaryValues {
  sex: 'F' | 'M';
  dose: number;
  day: number;
  test: string;
  with_quarantined: { n: number; mean: number | null };
  without_quarantined: { n: number; mean: number | null };
  ratio_without_over_with: number | null;
  contains_quarantined: boolean;
  quarantined_rows: Array<{
    usubjid: string;
    value: number;
    source_row: number | null;
  }>;
}

export interface GuidanceSentence {
  sentence_id: string;
  text: string;
}

export interface GuidanceHit {
  passage_id: string;
  fused_rank: number;
  fused_score: number;
  lexical_rank: number | null;
  lexical_score: number;
  semantic_rank: number | null;
  semantic_score: number;
  rerank_rank: number;
  rerank_score: number;
  doc: string;
  section: string;
  page_start: number;
  page_end: number;
  text: string;
  sentences: GuidanceSentence[];
}

export interface SearchGuidanceResult {
  query: string;
  abstained: boolean;
  best_score: number;
  threshold: number;
  message: string | null;
  hits: GuidanceHit[];
}

export interface QuarantineRow {
  rule: string;
  domain: string;
  source_row: number;
  usubjid: string;
  test: string;
  value: number;
  unit: string;
  visit_day: number | null;
}

export interface ValidateStudyReport {
  rows: Record<string, number>;
  xpt_zeros_normalised: Record<string, number>;
  structure_failures: Record<string, number>;
  auc: Record<string, { negative: number; quantified: number }>;
  concentrations: { quantified: number; negative: number };
  age: {
    ts_age_text: string;
    animals_checked: number;
    animals_mismatching: number;
    dm_age_values: number[];
  };
  terminology: { value: string; well_formed: boolean };
  deaths: Array<{
    usubjid: string;
    day: number;
    disposition: string;
    setcd: string;
    group: string;
  }>;
  integrity: {
    duplicate_usubjid: number;
    dm_setcd_missing_in_tx: number;
    orphan_usubjid: Record<string, number>;
    animals_by_set: Record<string, number>;
    planned_sets: number;
  };
  quarantine: {
    total: number;
    by_rule: Record<string, number>;
    rows: QuarantineRow[];
  };
  snapshot_sha256: string;
  naive_mean_auctau: {
    group: { sex: string; dose: number; day: number };
    with_quarantined: { n: number; mean: number; animals: string[] };
    without_quarantined: { n: number; mean: number; animals: string[] };
  };
  report_sha256: string;
}

export interface JobResponse {
  job_id?: string;
  kind: string;
  inputs_sha256: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  outputs?: { report: ValidateStudyReport } | null;
  error?: string | null;
}

export interface ThreadSlot {
  slot: string;
  finding: string;
  sex: 'F' | 'M';
  doses: number[];
}

export interface ThreadDecision {
  dec_id: string;
  finding: string;
  sex: 'F' | 'M';
  treatment_related_from: number | null;
  adverse_from: number | null;
  actor: string;
  ts: string;
}

export interface JudgeEntry {
  sentence: string;
  verdict: 'supported' | 'overstated' | 'not judged';
  category: string;
  reason: string;
}

export interface ThreadView {
  thread_id: string;
  author: string;
  waiting: 'await_decisions' | 'await_approval' | 'done' | string;
  slots: ThreadSlot[];
  decisions: ThreadDecision[];
  confirmed: Array<'F' | 'M'>;
  noael: Record<'F' | 'M', { dose: number | null; flags: string[] }>;
  final: {
    ok: boolean;
    text: string | null;
    failures: string[];
  };
  judge: JudgeEntry[];
  approved_by: string | null;
}

export interface DecisionInput {
  dec_id: string;
  treatment_related_from: number | null;
  adverse_from: number | null;
  example?: boolean;
}

export interface AuditVerifyResponse {
  ok: boolean;
  count: number;
  first_broken: number | null;
}

export interface ParsedProvenanceItem {
  kind: 'text' | 'data' | 'quote' | 'decision' | 'hole';
  text: string;
  citation?: string;
  facts?: Array<{ label: string; value: string }>;
  table?: {
    headers: string[];
    rows: string[][];
    hitCell?: [number, number] | null;
  };
  sourceRowsTable?: {
    headers: string[];
    rows: string[][];
    countLabel: string;
  };
  highlightHref?: string;
  officialHref?: string;
}

export interface ParsedAskResult {
  stale?: string;
  refused?: string;
  calloutKind?: string;
  calloutText?: string;
  calloutList?: string[];
  verifiedParts: ParsedProvenanceItem[];
  aiWritten: string;
  evidenceRows: string[][];
  screeningTable?: {
    headers: string[];
    rows: string[][];
  };
  evidenceTraces: string[];
}

export interface ParsedStudySwitchResult {
  switchMode: 'none' | 'negative' | 'duplicate' | 'dose';
  totalQuarantined: number;
  effectNote: string;
  withQuarantinedMean: string;
  withQuarantinedLabel: string;
  withoutQuarantinedMean: string;
  withoutQuarantinedLabel: string;
  quarantineRows: Array<{ animal: string; measure: string; value: string }>;
  reportedIntegrityNote: string;
  injectedNote: string;
}

export interface ParsedHighlightPage {
  sentence: string;
  pages: Array<{
    page: string;
    officialUrl: string;
    imageUrl: string;
  }>;
}

export interface ParsedDraftSheet {
  undecided: boolean;
  error: string;
  countsLine: string;
  metaRows: Array<{
    label1: string;
    parts1: ParsedProvenanceItem[];
    label2: string;
    parts2: ParsedProvenanceItem[];
  }>;
  studyIntro: ParsedProvenanceItem[];
  decisionIntro?: string;
  parameterRows: Array<{ label: string; parts: ParsedProvenanceItem[] }>;
  decisionRows: Array<{ slot: string; parts: ParsedProvenanceItem[] }>;
  tkIntro: ParsedProvenanceItem[];
  tkMeanHeader: string;
  tkMeanRows: Array<{ label: string; parts: ParsedProvenanceItem[] }>;
  tkNotes: ParsedProvenanceItem[][];
  noaelSections: Array<{
    heading: string;
    text: ParsedProvenanceItem[];
    quote: ParsedProvenanceItem[];
  }>;
  references: string[];
  footerNote: string;
  rulesTable: Array<{ rule: string; status: string; note: string }>;
  judgeTable: Array<{ sentence: string; verdict: string; reason: string; isExample: boolean }>;
  doorsTable: Array<{ door: string; hash: string }>;
  doorsMatch: boolean;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || data.error || JSON.stringify(data);
    } catch {
      const txt = await res.text();
      if (txt) detail = txt;
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/healthz');
}

export async function runValidateStudyJob(): Promise<JobResponse> {
  // Submit via POST /jobs and poll GET /jobs/{id} until done
  const created = await requestJson<JobResponse>('/jobs', {
    method: 'POST',
    body: JSON.stringify({ kind: 'validate_study', params: {} }),
  });
  if (created.status === 'done' && created.outputs) {
    return created;
  }
  if (!created.job_id) {
    return requestJson<JobResponse>('/api/tools/run_job', {
      method: 'POST',
      body: JSON.stringify({ kind: 'validate_study', params: {} }),
    });
  }
  for (let i = 0; i < 30; i++) {
    const polled = await requestJson<JobResponse>(`/jobs/${created.job_id}`);
    if (polled.status === 'done' || polled.status === 'failed') {
      return polled;
    }
    await new Promise((r) => setTimeout(r, 120));
  }
  return requestJson<JobResponse>(`/jobs/${created.job_id}`);
}

export async function fetchStudyDesign(): Promise<Observation<StudyDesignValues>> {
  return requestJson<Observation<StudyDesignValues>>('/api/tools/study_design', {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function fetchIncidence(screen: boolean): Promise<Observation<IncidenceValues>> {
  return requestJson<Observation<IncidenceValues>>('/api/tools/incidence', {
    method: 'POST',
    body: JSON.stringify({ screen }),
  });
}

export async function fetchBodyWeight(
  sex: 'F' | 'M',
  population: 'main_and_recovery' | 'main',
): Promise<Observation<BodyWeightValues>> {
  return requestJson<Observation<BodyWeightValues>>('/api/tools/body_weight_change', {
    method: 'POST',
    body: JSON.stringify({ sex, population }),
  });
}

export async function fetchTkSummary(
  sex: 'F' | 'M',
  dose: number,
  day: number,
): Promise<Observation<TkSummaryValues>> {
  return requestJson<Observation<TkSummaryValues>>('/api/tools/tk_summary', {
    method: 'POST',
    body: JSON.stringify({ sex, dose, day }),
  });
}

export async function fetchSearchGuidance(query: string): Promise<SearchGuidanceResult> {
  return requestJson<SearchGuidanceResult>('/api/tools/search_guidance', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

export async function startThread(): Promise<ThreadView> {
  return requestJson<ThreadView>('/api/threads', {
    method: 'POST',
  });
}

export async function getThread(threadId: string): Promise<ThreadView> {
  return requestJson<ThreadView>(`/api/threads/${threadId}`);
}

export async function recordThreadDecisions(
  threadId: string,
  actor: Actor,
  decisions: DecisionInput[],
): Promise<ThreadView> {
  return requestJson<ThreadView>(`/api/threads/${threadId}/decisions`, {
    method: 'POST',
    body: JSON.stringify({ actor, decisions }),
  });
}

export async function confirmThreadNoael(
  threadId: string,
  actor: Actor,
  confirmed: Array<'F' | 'M'>,
): Promise<ThreadView> {
  return requestJson<ThreadView>(`/api/threads/${threadId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ actor, confirmed }),
  });
}

export async function approveThreadDraft(
  threadId: string,
  actor: Actor,
): Promise<ThreadView> {
  return requestJson<ThreadView>(`/api/threads/${threadId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ actor }),
  });
}

export async function verifyThreadAudit(threadId: string): Promise<AuditVerifyResponse> {
  return requestJson<AuditVerifyResponse>(`/api/threads/${threadId}/audit/verify`);
}

// --- Verifier rule count ---

export const VERIFIER_RULE_TOTAL = 8;

// Failures read "Rule N: ..." or "Rule N (sentence k): ..." (src/cairn/verify.py Failure.__str__).
// Several failures can share a rule, so rules failed = distinct rule numbers.
export function verifierFailedRules(final: ThreadView['final']): Set<number> {
  const rules = new Set<number>();
  if (final.ok) return rules;
  for (const f of final.failures) {
    const m = f.match(/^Rule (\d+)/);
    if (m) rules.add(Number(m[1]));
  }
  return rules;
}

export function verifierRulesPassed(final: ThreadView['final']): number {
  if (final.ok) return VERIFIER_RULE_TOTAL;
  const failed = verifierFailedRules(final).size || (final.failures.length > 0 ? 1 : 0);
  return Math.max(0, VERIFIER_RULE_TOTAL - failed);
}

// --- NOAEL display per sex ---

// The backend fills noael with a default dose before any decision is recorded,
// so the dose is only meaningful once there are decisions or the sex is confirmed.
export interface NoaelDisplay {
  state: 'pending' | 'not_established' | 'dose';
  dose: number | null;
  confirmed: boolean;
}

export function noaelDisplay(thread: ThreadView | null, sex: 'F' | 'M'): NoaelDisplay {
  const hasDecisions = (thread?.decisions.length ?? 0) > 0;
  const confirmed = thread?.confirmed.includes(sex) ?? false;
  if (!thread || (!hasDecisions && !confirmed)) {
    return { state: 'pending', dose: null, confirmed: false };
  }
  const dose = thread.noael?.[sex]?.dose ?? null;
  return dose === null
    ? { state: 'not_established', dose: null, confirmed }
    : { state: 'dose', dose, confirmed };
}

// --- HTML Fragment Parsers ---

function parseTableElement(table: Element): {
  headers: string[];
  rows: string[][];
  hitCell: [number, number] | null;
} {
  const headers = Array.from(table.querySelectorAll('thead th')).map(
    (th) => th.textContent?.trim() || '',
  );
  let hitCell: [number, number] | null = null;
  const rows = Array.from(table.querySelectorAll('tbody tr')).map((tr, rIdx) =>
    Array.from(tr.querySelectorAll('td')).map((td, cIdx) => {
      if (td.classList.contains('hit')) {
        hitCell = [rIdx, cIdx];
      }
      return td.textContent?.trim() || '';
    }),
  );
  return { headers, rows, hitCell };
}

function parseDetailsProv(details: Element): ParsedProvenanceItem {
  const classList = Array.from(details.classList);
  const kind: 'data' | 'quote' | 'decision' = classList.includes('prov-quote')
    ? 'quote'
    : classList.includes('prov-decision')
      ? 'decision'
      : 'data';

  const summary = details.querySelector('summary.prov-chip');
  const citeSpan = summary?.querySelector('.prov-cite');
  const citation = citeSpan ? citeSpan.textContent?.trim().replace(/^\(|\)$/g, '') : undefined;

  let text = summary?.textContent?.trim() || '';
  if (citeSpan && citeSpan.textContent) {
    text = text.replace(citeSpan.textContent, '').trim();
  }

  const body = details.querySelector('.prov-body');
  const facts: Array<{ label: string; value: string }> = [];
  if (body) {
    const dts = body.querySelectorAll('dl.prov-facts dt');
    const dds = body.querySelectorAll('dl.prov-facts dd');
    dts.forEach((dt, idx) => {
      facts.push({
        label: dt.textContent?.trim() || '',
        value: dds[idx]?.textContent?.trim() || '',
      });
    });
  }

  let table: ParsedProvenanceItem['table'] | undefined;
  let sourceRowsTable: ParsedProvenanceItem['sourceRowsTable'] | undefined;

  if (body) {
    const directTable = Array.from(body.children).find((el) => el.tagName === 'TABLE');
    if (directTable) {
      table = parseTableElement(directTable);
    }
    const nestedDetails = body.querySelector('details.pill');
    if (nestedDetails) {
      const nestedSummary = nestedDetails.querySelector('summary')?.textContent?.trim() || '';
      const nestedTable = nestedDetails.querySelector('table');
      if (nestedTable) {
        const parsedNested = parseTableElement(nestedTable);
        sourceRowsTable = {
          headers: parsedNested.headers,
          rows: parsedNested.rows,
          countLabel: nestedSummary,
        };
      }
    }
  }

  let highlightHref: string | undefined;
  let officialHref: string | undefined;
  if (body && kind === 'quote') {
    const links = Array.from(body.querySelectorAll('p.meta a'));
    for (const a of links) {
      const href = a.getAttribute('href') || '';
      if (href.startsWith('/highlight/')) {
        highlightHref = href;
      } else if (href.startsWith('http')) {
        officialHref = href;
      }
    }
  }

  return {
    kind,
    text,
    citation,
    facts,
    table,
    sourceRowsTable,
    highlightHref,
    officialHref,
  };
}

function directTbodyRows(table: Element): Element[] {
  const rows: Element[] = [];
  for (const child of Array.from(table.children)) {
    if (child.tagName === 'TBODY') {
      for (const row of Array.from(child.children)) {
        if (row.tagName === 'TR') rows.push(row);
      }
    } else if (child.tagName === 'TR' && !child.querySelector('th')) {
      rows.push(child);
    }
  }
  return rows;
}

function directTableRows(table: Element): Element[] {
  const rows: Element[] = [];
  for (const child of Array.from(table.children)) {
    if (child.tagName === 'TBODY' || child.tagName === 'THEAD') {
      for (const row of Array.from(child.children)) {
        if (row.tagName === 'TR') rows.push(row);
      }
    } else if (child.tagName === 'TR') {
      rows.push(child);
    }
  }
  return rows;
}

function directRowCells(row: Element): { ths: Element[]; tds: Element[] } {
  const ths: Element[] = [];
  const tds: Element[] = [];
  for (const child of Array.from(row.children)) {
    if (child.tagName === 'TH') {
      ths.push(child);
    } else if (child.tagName === 'TD') {
      tds.push(child);
    }
  }
  return { ths, tds };
}

function parseContainerParts(container: Element | null): ParsedProvenanceItem[] {
  if (!container) return [];
  const items: ParsedProvenanceItem[] = [];
  container.childNodes.forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const txt = node.textContent || '';
      if (txt) {
        items.push({ kind: 'text', text: txt });
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as Element;
      if (el.tagName === 'DETAILS' && el.classList.contains('prov')) {
        items.push(parseDetailsProv(el));
      } else if (el.classList.contains('hl')) {
        items.push({ kind: 'hole', text: el.textContent || '' });
      } else if (el.classList.contains('prov-body')) {
        // Explicitly ignore .prov-body if encountered
        return;
      } else {
        const hasProvOrHl = el.querySelector('details.prov, .hl');
        if (hasProvOrHl) {
          items.push(...parseContainerParts(el));
        } else {
          const body = el.querySelector('.prov-body');
          if (body) {
            const clone = el.cloneNode(true) as Element;
            clone.querySelectorAll('.prov-body').forEach((b) => b.remove());
            const txt = clone.textContent || '';
            if (txt) items.push({ kind: 'text', text: txt });
          } else {
            const txt = el.textContent || '';
            if (txt) items.push({ kind: 'text', text: txt });
          }
        }
      }
    }
  });
  return items;
}

export async function runStudySwitch(
  switchMode: 'none' | 'negative' | 'duplicate' | 'dose',
  locale: 'en' | 'es' = 'en',
): Promise<ParsedStudySwitchResult> {
  const form = new URLSearchParams();
  form.set('switch', switchMode);
  const res = await fetch(`/study/run?lang=${locale}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!res.ok) {
    throw new ApiError(res.status, `Study switch failed (${res.status})`);
  }
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const gone = doc.querySelector('.gone');
  const totalQuarantined = Number(
    gone?.querySelector('.tile.big .num')?.textContent?.trim() || '12',
  );
  const effectNote = gone?.querySelector('p.meta.effect')?.textContent?.trim() || '';
  const meanTiles = Array.from(gone?.querySelectorAll('.tiles.two .tile') || []);
  const withQuarantinedMean =
    meanTiles[0]?.querySelector('.prov-chip')?.textContent?.trim() ||
    meanTiles[0]?.querySelector('.num')?.textContent?.trim() ||
    '';
  const withQuarantinedLabel = meanTiles[0]?.querySelector('.lbl')?.textContent?.trim() || '';
  const withoutQuarantinedMean =
    meanTiles[1]?.querySelector('.prov-chip')?.textContent?.trim() ||
    meanTiles[1]?.querySelector('.num')?.textContent?.trim() ||
    '';
  const withoutQuarantinedLabel = meanTiles[1]?.querySelector('.lbl')?.textContent?.trim() || '';

  const qTable = gone?.querySelector('details.pill table');
  const quarantineRows = Array.from(qTable?.querySelectorAll('tbody tr') || []).map((tr) => {
    const tds = Array.from(tr.querySelectorAll('td'));
    return {
      animal: tds[0]?.textContent?.trim() || '',
      measure: tds[1]?.textContent?.trim() || '',
      value: tds[2]?.textContent?.trim() || '',
    };
  });

  const reportedIntegrityNote =
    Array.from(gone?.querySelectorAll('p.meta') || [])
      .find((p) => !p.classList.contains('effect') && !p.classList.contains('note'))
      ?.textContent?.trim() || '';
  const injectedNote = gone?.querySelector('p.meta.note')?.textContent?.trim() || '';

  return {
    switchMode,
    totalQuarantined,
    effectNote,
    withQuarantinedMean,
    withQuarantinedLabel,
    withoutQuarantinedMean,
    withoutQuarantinedLabel,
    quarantineRows,
    reportedIntegrityNote,
    injectedNote,
  };
}

export async function runRecordedQuestion(
  questionId: string,
  locale: 'en' | 'es' = 'en',
): Promise<ParsedAskResult> {
  const form = new URLSearchParams();
  form.set('question', questionId);
  const res = await fetch(`/ask/run?lang=${locale}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!res.ok) {
    throw new ApiError(res.status, `Ask run failed (${res.status})`);
  }
  const html = await res.text();
  return parseAskFragment(html);
}

export async function runLiveExploreQuestion(
  question: string,
  code: string,
  locale: 'en' | 'es' = 'en',
): Promise<ParsedAskResult> {
  const form = new URLSearchParams();
  form.set('question', question);
  form.set('code', code);
  const res = await fetch(`/explore/live?lang=${locale}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  if (!res.ok) {
    throw new ApiError(res.status, `Live explore failed (${res.status})`);
  }
  const html = await res.text();
  return parseAskFragment(html);
}

export function parseAskFragment(html: string): ParsedAskResult {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const staleCallout = doc.querySelector('.callout.stale');
  if (staleCallout) {
    return {
      stale: staleCallout.textContent?.trim() || 'Stale recording',
      verifiedParts: [],
      aiWritten: '',
      evidenceRows: [],
      evidenceTraces: [],
    };
  }

  // Check if explore_refused.html was returned
  const panel = doc.querySelector('article.answer-panel');
  if (!panel) {
    const callout = doc.querySelector('.callout');
    return {
      refused: callout?.textContent?.trim() || doc.body.textContent?.trim() || 'Request refused',
      verifiedParts: [],
      aiWritten: '',
      evidenceRows: [],
      evidenceTraces: [],
    };
  }

  const callout = panel.querySelector('.callout');
  const calloutKind = callout
    ? Array.from(callout.classList).find((c) => c !== 'callout') || 'note'
    : undefined;
  const calloutText = callout?.querySelector('p')?.textContent?.trim() || undefined;
  const calloutList = callout
    ? Array.from(callout.querySelectorAll('li')).map((li) => li.textContent?.trim() || '')
    : undefined;

  const answerCards = Array.from(panel.querySelectorAll('.card.answer'));
  const firstUnit = answerCards[0]?.querySelector('.answer-unit') || null;
  const verifiedParts = parseContainerParts(firstUnit);
  const aiWritten = answerCards[1]?.querySelector('.answer-unit')?.textContent?.trim() || '';

  // Only the evidence pill that is a direct child of the panel: data tags nest their own
  // "Show source rows" pill, which must not be taken for the evidence block.
  const disc =
    Array.from(panel.children).find(
      (el) => el.tagName === 'DETAILS' && el.classList.contains('pill'),
    ) || null;
  const tables = Array.from(disc?.querySelectorAll('table') || []);
  let evidenceRows: string[][] = [];
  let screeningTable: ParsedAskResult['screeningTable'] | undefined;

  if (tables.length === 1) {
    const parsed = parseTableElement(tables[0]);
    if (parsed.headers.length > 2) {
      screeningTable = { headers: parsed.headers, rows: parsed.rows };
    } else {
      evidenceRows = parsed.rows;
    }
  } else if (tables.length >= 2) {
    evidenceRows = parseTableElement(tables[0]).rows;
    const parsedScreen = parseTableElement(tables[1]);
    screeningTable = { headers: parsedScreen.headers, rows: parsedScreen.rows };
  }

  const evidenceTraces = Array.from(disc?.querySelectorAll('.evidence p') || []).map(
    (p) => p.textContent?.trim() || '',
  );

  return {
    calloutKind,
    calloutText,
    calloutList,
    verifiedParts,
    aiWritten,
    evidenceRows,
    screeningTable,
    evidenceTraces,
  };
}

export async function fetchHighlightDetails(sentenceId: string): Promise<ParsedHighlightPage> {
  const cleanPath = sentenceId.startsWith('/highlight/')
    ? sentenceId
    : `/highlight/${sentenceId}`;
  const res = await fetch(cleanPath);
  if (!res.ok) {
    throw new ApiError(res.status, `Highlight not found (${res.status})`);
  }
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const sentence = doc.querySelector('blockquote.quote')?.textContent?.trim() || '';
  const figures = Array.from(doc.querySelectorAll('.page-images figure'));
  const pages = figures.map((fig) => {
    const metaLinks = Array.from(fig.querySelectorAll('p.meta a'));
    const officialUrl =
      metaLinks.find((a) => (a.getAttribute('href') || '').startsWith('http'))?.getAttribute('href') ||
      '';
    const metaText = fig.querySelector('p.meta')?.textContent || '';
    const pageMatch = metaText.match(/(\d+)/);
    const img = fig.querySelector('img.page-image');
    const imageUrl = img?.getAttribute('src') || '';
    return {
      page: pageMatch ? pageMatch[1] : '1',
      officialUrl,
      imageUrl,
    };
  });
  return { sentence, pages };
}

export async function fetchDraftSheet(
  threadId: string,
  actor: Actor,
  locale: 'en' | 'es' = 'en',
): Promise<ParsedDraftSheet> {
  const params = new URLSearchParams({ thread: threadId, actor, lang: locale });
  const res = await fetch(`/draft?${params.toString()}`);
  if (!res.ok && res.status !== 403) {
    throw new ApiError(res.status, `Draft fetch failed (${res.status})`);
  }
  const html = await res.text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const stepSec = doc.querySelector('section.step.draft');
  const undecided = Boolean(stepSec?.querySelector('.callout.note a[href="/decide"]'));
  const error = stepSec?.querySelector('.callout.blocked')?.textContent?.trim() || '';
  const countsLine = stepSec?.querySelector('p.prov-counts')?.textContent?.trim() || '';

  const sheet = doc.querySelector('article.sheet');
  const metaTable = sheet?.querySelector('table.sh-meta');
  const metaRows = metaTable
    ? directTableRows(metaTable)
        .map((tr) => {
          const { ths, tds } = directRowCells(tr);
          if (ths.length === 0 && tds.length === 0) return null;
          return {
            label1: ths[0]?.textContent?.trim() || '',
            parts1: parseContainerParts(tds[0] || null),
            label2: ths[1]?.textContent?.trim() || '',
            parts2: parseContainerParts(tds[1] || null),
          };
        })
        .filter((r): r is NonNullable<typeof r> => r !== null && (Boolean(r.label1) || Boolean(r.label2)))
    : [];

  const h2s = Array.from(sheet?.querySelectorAll('h2') || []);
  const sec1H2 = h2s.find((h) => h.textContent?.includes('1.'));
  const sec1P = sec1H2?.nextElementSibling?.classList.contains('sh-p')
    ? (sec1H2.nextElementSibling as Element)
    : null;
  const studyIntro = parseContainerParts(sec1P);

  const sec2H2 = h2s.find((h) => h.textContent?.includes('2.'));
  const sec2P = sec2H2?.nextElementSibling?.tagName === 'P'
    ? sec2H2.nextElementSibling.textContent?.trim() || ''
    : 'The following decisions on adversity of the findings were recorded.';
  const decisionIntro = sec2P;

  const sec3H2 = h2s.find((h) => h.textContent?.includes('3.'));
  const sec3P = sec3H2?.nextElementSibling?.classList.contains('sh-p')
    ? (sec3H2.nextElementSibling as Element)
    : null;
  const tkIntro = parseContainerParts(sec3P);

  // Top-level sh-tabs inside sheet (only direct report tables)
  const shTabs = Array.from(sheet?.querySelectorAll('table.sh-tab') || []).filter(
    (t) => t.parentElement === sheet || t.closest('article.sheet') === sheet,
  );

  const parameterRows = shTabs[0]
    ? directTbodyRows(shTabs[0])
        .map((tr) => {
          const { tds } = directRowCells(tr);
          return {
            label: tds[0]?.textContent?.trim() || '',
            parts: parseContainerParts(tds[1] || null),
          };
        })
        .filter((r) => r.label.length > 0)
    : [];

  const decisionRows = shTabs[1]
    ? directTbodyRows(shTabs[1])
        .map((tr) => {
          const { tds } = directRowCells(tr);
          return {
            slot: tds[0]?.textContent?.trim() || '',
            parts: parseContainerParts(tds[1] || null),
          };
        })
        .filter((r) => r.slot.length > 0)
    : [];

  let tkMeanHeader = 'Mean AUCtau';
  let tkMeanRows: Array<{ label: string; parts: ParsedProvenanceItem[] }> = [];
  if (shTabs[2]) {
    const headRow = directTableRows(shTabs[2]).find((tr) => tr.querySelector('th'));
    if (headRow) {
      const { ths } = directRowCells(headRow);
      if (ths[1]?.textContent?.trim()) {
        tkMeanHeader = ths[1].textContent.trim();
      }
    }
    tkMeanRows = directTbodyRows(shTabs[2])
      .map((tr) => {
        const { tds } = directRowCells(tr);
        return {
          label: tds[0]?.textContent?.trim() || '',
          parts: parseContainerParts(tds[1] || null),
        };
      })
      .filter((r) => r.label.length > 0);
  }

  // TK notes: direct ul inside sheet
  const tkNotesList = Array.from(sheet?.querySelectorAll('ul') || []).filter(
    (u) => u.parentElement === sheet,
  );
  const tkNotes = tkNotesList.flatMap((ul) =>
    Array.from(ul.children)
      .filter((li) => li.tagName === 'LI')
      .map((li) => parseContainerParts(li)),
  );

  // Parse NOAEL 4.1 & 4.2 sections
  const noaelSections: ParsedDraftSheet['noaelSections'] = [];
  const h3s = Array.from(sheet?.querySelectorAll('h3') || []);
  h3s.forEach((h3) => {
    const heading = h3.textContent?.trim() || '';
    const nextP = h3.nextElementSibling;
    const text = nextP && nextP.classList.contains('sh-p') ? parseContainerParts(nextP) : [];
    const maybeQuote = nextP?.nextElementSibling;
    const quote =
      maybeQuote && maybeQuote.tagName === 'BLOCKQUOTE' ? parseContainerParts(maybeQuote) : [];
    noaelSections.push({ heading, text, quote });
  });

  const references = Array.from(sheet?.querySelectorAll('ol li') || []).map(
    (li) => li.textContent?.trim() || '',
  );
  const footerNote = sheet?.querySelector('.sh-foot')?.textContent?.trim() || '';

  // Parse Inside fold tables (Judge, 8 Rules, Session, MCP vs REST, In production).
  // While undecided the fold holds only the In production table: parse nothing else then.
  const insideTables = Array.from(doc.querySelectorAll('details.inside .inside-body table'));
  const fullInside = !undecided && insideTables.length >= 4;
  const judgeTable = Array.from(
    (fullInside && insideTables[0]?.querySelectorAll('tbody tr')) || [],
  ).map((tr) => {
    const tds = Array.from(tr.querySelectorAll('td'));
    const isExample = Boolean(tds[0]?.querySelector('.badge.example'));
    let sentence = tds[0]?.textContent?.trim() || '';
    if (isExample) {
      sentence = sentence.replace(/^EXAMPLE\s*/, '');
    }
    return {
      sentence,
      verdict: tds[1]?.textContent?.trim() || '',
      reason: tds[2]?.textContent?.trim() || '',
      isExample,
    };
  });

  const rulesTable = Array.from(
    (fullInside && insideTables[1]?.querySelectorAll('tbody tr')) || [],
  ).map((tr) => {
    const tds = Array.from(tr.querySelectorAll('td'));
    return {
      rule: tds[0]?.textContent?.trim() || '',
      status: tds[1]?.textContent?.trim() || '',
      note: tds[2]?.textContent?.trim() || '',
    };
  });

  const doorsTable = Array.from(
    (fullInside && insideTables[3]?.querySelectorAll('tbody tr')) || [],
  ).map((tr) => {
    const tds = Array.from(tr.querySelectorAll('td'));
    return {
      door: tds[0]?.textContent?.trim() || '',
      hash: tds[1]?.textContent?.trim() || '',
    };
  });

  const doorsMatch =
    doorsTable.length >= 2 ? doorsTable[0].hash === doorsTable[1].hash : true;

  return {
    undecided,
    error,
    countsLine,
    metaRows,
    studyIntro,
    decisionIntro,
    parameterRows,
    decisionRows,
    tkIntro,
    tkMeanHeader,
    tkMeanRows,
    tkNotes,
    noaelSections,
    references,
    footerNote,
    rulesTable,
    judgeTable,
    doorsTable,
    doorsMatch,
  };
}
