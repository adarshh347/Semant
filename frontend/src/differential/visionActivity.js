// CIRCULATION-SPINE-001 · P2.2 — Vision Activity Rail: pure, honest presentation logic.
//
// This module holds ALL of the rail's derivation/copy so it is unit-testable in the existing
// (node, no-DOM) vitest harness; the JSX stays thin. It is READ-ONLY observation of the four
// currently instrumented operations — it never claims causality between separate runs and
// never renders raw technical error text (R2).

// The ONLY operations Semant currently records. The rail scopes itself to exactly these and
// must not imply that all vision endpoints are observable.
export const OPERATIONS = ['dissect', 'refine', 'semantic_read', 'find_similar'];

export const OPERATION_LABEL = {
  dissect: 'Dissect',
  refine: 'Refine',
  semantic_read: 'Semantic read',
  find_similar: 'Find similar',
};

// Restrained epistemic copy (P2.2 §4). No causal wording anywhere.
export const EPISTEMIC = {
  dissect: 'Visual evidence produced.',
  refine: 'Geometry revision.',
  semantic_read: 'Interpretation only — geometry unchanged.',
  find_similar: 'Research neighbours — no relation created.',
};

// What each operation honestly touches (drives a terse chip, not a claim of effect on others).
export const AFFECTS = {
  dissect: 'geometry',
  refine: 'geometry',
  semantic_read: 'interpretation',
  find_similar: 'research',
};

export function latestUrl(apiUrl, postId, operation) {
  return `${apiUrl}/api/v1/posts/${postId}/vision-runs/latest?operation=${operation}`;
}

// Fetch the four latest-operation runs in parallel. A per-operation read miss becomes
// `null` ("no record"), never a rail-level error; an abort propagates so the caller can drop
// a superseded fetch. Pure/injectable (`fetchImpl`) so it is unit-testable without a DOM.
export async function fetchAllRuns(apiUrl, postId, { signal, fetchImpl } = {}) {
  const doFetch = fetchImpl || (typeof fetch !== 'undefined' ? fetch : null);
  const pairs = await Promise.all(
    OPERATIONS.map(async (op) => {
      try {
        const res = await doFetch(latestUrl(apiUrl, postId, op), { signal });
        if (!res || !res.ok) return [op, null];
        const data = await res.json();
        return [op, data && 'run' in data ? data.run : null];
      } catch (e) {
        if (e && e.name === 'AbortError') throw e;
        return [op, null];
      }
    }),
  );
  return Object.fromEntries(pairs);
}

// ── status → quiet presentation ───────────────────────────────────────────────
// Statuses: pending/running/succeeded/partial/skipped/unavailable/timed_out/cancelled/failed,
// plus a `stale` flag the projection sets on an interrupted running run.
export function statusPresentation(run) {
  if (!run) return { key: 'empty', label: 'No recorded activity', tone: 'muted' };
  const s = String(run.status || '').toLowerCase();
  if ((s === 'running' || s === 'pending') && run.stale) {
    return { key: 'stale', label: 'Interrupted', tone: 'warn' };
  }
  switch (s) {
    case 'running': return { key: 'running', label: 'Observing…', tone: 'active' };
    case 'pending': return { key: 'running', label: 'Queued', tone: 'active' };
    case 'succeeded': return { key: 'succeeded', label: 'Complete', tone: 'ok' };
    case 'partial': return { key: 'partial', label: 'Partial', tone: 'warn' };
    case 'failed': return { key: 'failed', label: 'Didn’t complete', tone: 'err' };
    case 'cancelled': return { key: 'cancelled', label: 'Stopped', tone: 'muted' };
    case 'unavailable': return { key: 'unavailable', label: 'Unavailable', tone: 'muted' };
    case 'skipped': return { key: 'skipped', label: 'Skipped', tone: 'muted' };
    case 'timed_out': return { key: 'timed_out', label: 'Timed out', tone: 'warn' };
    default: return { key: s || 'unknown', label: s || 'Unknown', tone: 'muted' };
  }
}

// ── stage_id → concise human phrase (within-run observation only) ─────────────
export const STAGE_HUMAN = {
  'dissect.receive': 'Received request',
  'dissect.fetch_image': 'Fetched image',
  'dissect.route_domain': 'Routed by domain',
  'dissect.segment.fashion': 'Garment segmentation',
  'dissect.segment.architecture': 'Architecture segmentation',
  'dissect.segment.general': 'General segmentation',
  'dissect.segment.coarse': 'Coarse segmentation',
  'dissect.merge_anchors': 'Merged anchors',
  'dissect.fallback.detect': 'Fallback detection',
  'dissect.decompose_fine': 'Fine decomposition',
  'dissect.merge_curator_state': 'Preserved curator parts',
  'dissect.canonicalize_geometry': 'Canonicalized geometry',
  'dissect.persist_regions': 'Saved parts',
  'dissect.complete': 'Complete',
  'refine.receive': 'Received request',
  'refine.propose': 'Proposed exact mask',
  'refine.merge_curator_state': 'Preserved curator fields',
  'refine.persist_regions': 'Saved part',
  'refine.complete': 'Complete',
  'semantic_read.receive': 'Received request',
  'semantic_read.fetch_image': 'Fetched image',
  'semantic_read.run': 'Interpreted parts',
  'semantic_read.merge_curator_state': 'Kept curator decisions',
  'semantic_read.persist_semantics': 'Saved interpretation',
  'semantic_read.complete': 'Complete',
  'find_similar.receive': 'Received request',
  'find_similar.route_space': 'Chose vector space',
  'find_similar.scope': 'Scoped corpus',
  'find_similar.fetch_image': 'Fetched image',
  'find_similar.retrieve': 'Retrieved neighbours',
  'find_similar.complete': 'Complete',
};

export function humanStage(stageId) {
  if (STAGE_HUMAN[stageId]) return STAGE_HUMAN[stageId];
  const tail = String(stageId || '').split('.').slice(1).join(' ') || String(stageId || '');
  return tail.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

// ── friendly, curator-facing message (NEVER the raw stored error — R2) ────────
export function friendlyMessage(run) {
  if (!run) return null;
  const s = String(run.status || '').toLowerCase();
  const reason = String(run.terminal_reason || '');
  const op = OPERATION_LABEL[run.operation] || 'This operation';
  if ((s === 'running' || s === 'pending') && run.stale) {
    return 'This record looks interrupted — it never reported a result.';
  }
  if (s === 'cancelled') return 'Stopped before finishing.';
  if (s === 'failed') return `${op} didn’t finish.`;
  if (s === 'unavailable') return 'This capability was unavailable.';
  if (s === 'partial') {
    if (reason === 'fine_decomposition_degraded') return 'Evidence produced; fine decomposition was skipped.';
    if (reason === 'persist_no_match') return 'Finished, but the save matched no current record.';
    if (run.operation === 'find_similar') return 'Neighbour search was unavailable; no results returned.';
    return 'Finished with one stage degraded.';
  }
  return null;
}

// Scrub obvious URLs / filesystem paths / tokens / DB URIs before any diagnostic display.
export function scrubTechnical(text) {
  if (!text) return '';
  return String(text)
    .replace(/mongodb(?:\+srv)?:\/\/[^\s'")]+/gi, '[db-uri]')
    .replace(/https?:\/\/[^\s'")]+/gi, '[url]')
    .replace(/(?:[A-Za-z]:\\|\/(?:home|usr|var|etc|tmp|root|opt)\/)[^\s'":)]+/g, '[path]')
    .replace(/\b(?:sk|gho|ghp|ghs|xox[baprs]|AKIA|Bearer)[-_A-Za-z0-9]{6,}\b/gi, '[redacted]')
    .replace(/\b[A-Fa-f0-9]{32,}\b/g, '[redacted]')
    .trim()
    .slice(0, 280);
}

// Test/guard aid: the rail's produced copy must never imply cross-run causality.
export const CAUSAL_FORBIDDEN = [
  'caused by', 'because', 'led to', 'resulted in', 'followed from',
  'as a result', 'triggered by', 'due to', 'consequently',
];
export function hasCausalWording(text) {
  const t = String(text || '').toLowerCase();
  return CAUSAL_FORBIDDEN.some((w) => t.includes(w));
}

// Region references this run recorded (co-reference only — never a causal link).
export function regionRefs(run) {
  const rp = (run && run.requested_profile) || {};
  if (Array.isArray(rp.region_ids)) return rp.region_ids.filter(Boolean);
  if (rp.region_id) return [rp.region_id];
  return [];
}
export function regionRefLabel(run, regionsById) {
  const ids = regionRefs(run);
  if (!ids.length) return null;
  if (ids.length === 1) {
    const name = regionsById && regionsById[ids[0]];
    return name ? `Referenced ${name}` : 'Referenced 1 part';
  }
  return `Referenced ${ids.length} parts`;
}

function relTime(iso, now) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const secs = Math.max(0, Math.round((now - t) / 1000));
  if (secs < 45) return 'just now';
  if (secs < 90) return 'a minute ago';
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  const days = Math.round(hrs / 24);
  return `${days} d ago`;
}

function totalLatency(stages) {
  const vals = stages.map((s) => s.latencyMs).filter((v) => typeof v === 'number');
  if (!vals.length) return null;
  return Math.round(vals.reduce((a, b) => a + b, 0));
}

// ── the one derivation the component renders ──────────────────────────────────
export function deriveEntry(operation, run, { regionsById, now = Date.now() } = {}) {
  const present = statusPresentation(run);
  const stages = (run && run.events ? run.events : []).map((e) => ({
    id: e.stage_id,
    human: humanStage(e.stage_id),
    status: String(e.status || '').toLowerCase(),
    latencyMs: typeof e.latency_ms === 'number' ? e.latency_ms : null,
    adapter: e.adapter || null,
    fallbacks: Array.isArray(e.fallbacks) ? e.fallbacks : [],
    deps: (Array.isArray(e.dependencies) ? e.dependencies : []).map(humanStage),
    hasError: !!e.error,
  }));
  const fallbacks = Array.from(new Set(stages.flatMap((s) => s.fallbacks)));
  return {
    operation,
    label: OPERATION_LABEL[operation] || operation,
    epistemic: EPISTEMIC[operation] || '',
    affects: AFFECTS[operation] || null,
    isEmpty: !run,
    present,
    isActive: present.key === 'running',
    isStale: present.key === 'stale',
    status: run ? String(run.status || '').toLowerCase() : null,
    terminalReason: run ? run.terminal_reason || null : null,
    adapter: (run && run.actual_source) || null,
    latencyMs: totalLatency(stages),
    ageText: run ? relTime(run.completed_at || run.updated_at || run.created_at, now) : null,
    stages,
    fallbacks,
    friendly: friendlyMessage(run),
    regionRef: regionRefLabel(run, regionsById),
    // raw stored error is exposed ONLY here, scrubbed, and the component keeps it behind a
    // deliberate diagnostics disclosure — never the default view.
    diagnostics: run && run.error ? scrubTechnical(run.error) : null,
    telemetryDegraded: !!(run && run.telemetry_degraded),
    neighbours: run && run.result_summary ? run.result_summary.neighbours : undefined,
    space: (run && run.result_summary && run.result_summary.space) || (run && run.actual_source) || null,
  };
}

// A Differential action's terminal hook-status → the rail should refresh that family.
export function isTerminalActionStatus(s) {
  return ['ok', 'confirmed', 'ready', 'empty', 'unavailable', 'error', 'timeout'].includes(s);
}
