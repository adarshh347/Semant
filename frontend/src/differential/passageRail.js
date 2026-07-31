// CIRCUIT-001 P5-B — derivation for the Passage Rail.
//
// The rail is a WITNESS, not a narrator (Invariant 9): it shows only what was recorded.
// All of the honesty lives here, in pure functions, so the JSX cannot quietly invent a
// state the record does not support. The rules this module enforces, each mapped to the
// anti-spec (P0.5 §4.3 + CIRCULATION-SPINE Invariants 8/9/12/13):
//
//   • Absent telemetry stays `null` → the view renders "—", never an estimate (Inv 8).
//   • Progress is an event SEQUENCE, never a fraction — nothing records percent (Inv 9).
//   • A stalled RUNNING doc is NOT "live": we stop polling and say "no events for Ns",
//     we never animate waiting (Inv 13).
//   • Backend run events and this session's local events are TWO sources with TWO voices;
//     they share a list but never a claim of causation, and never one clock (P0.5 §4.3).
//   • A suggestion-producing run is labelled as such; its marks are never shown as evidence.
//
// Reuses the already-honest presentation helpers from ./visionActivity rather than forking
// them, so the rail's status vocabulary matches the rest of the Differential surface.
import { statusPresentation, humanStage, scrubTechnical, OPERATION_LABEL } from './visionActivity';

export const SOURCE = { RUN: 'run', SESSION: 'session' };

// The operations whose runs mint suggestions (P4-A producers: SAM refine + semantic read).
// A run of one of these produces marks that arrive for REVIEW, never as evidence.
const SUGGESTION_OPERATIONS = new Set(['refine', 'semantic_read']);

export function isSuggestionRun(run) {
    return !!run && SUGGESTION_OPERATIONS.has(String(run.operation || ''));
}

// A run is "live" — worth polling — ONLY while running/pending AND not stale. A stale active
// record has stopped reporting (Inv 13): it is terminal for the purpose of the poll, and the
// rail says so instead of spinning forever.
export function isRunLive(run) {
    if (!run) return false;
    const s = String(run.status || '').toLowerCase();
    return (s === 'running' || s === 'pending') && !run.stale;
}

// Everything that is not live is terminal-for-display: a finished status, OR a stale active
// record. Absence is neither (there is simply no run) — callers test `run == null` for that.
export function isRunTerminal(run) {
    return !!run && !isRunLive(run);
}

function toMs(v) {
    if (v == null) return null;
    if (typeof v === 'number') return v;
    const n = Date.parse(v);
    return Number.isNaN(n) ? null : n;
}
// For SORT only: a missing time sinks to the end without claiming a position.
function sortMs(v) {
    const m = toMs(v);
    return m == null ? Number.POSITIVE_INFINITY : m;
}

// The run's REAL stage events, in STORED (arrival) order. That order is observation, not
// causation — the contract is explicit that stored order is "not a causal claim", so the rail
// renders it as a sequence and never as "X caused Y". Absent fields stay null → "—" (Inv 8).
export function runEvents(run) {
    if (!run || !Array.isArray(run.events)) return [];
    return run.events.map((e, i) => ({
        source: SOURCE.RUN,
        key: e.event_id || `${run.run_id || 'run'}-ev-${i}`,
        runId: e.run_id || run.run_id || null,
        stageId: e.stage_id || null,
        stage: e.stage_id ? humanStage(e.stage_id) : null,
        status: e.status || null,
        // Only a model the event's provenance actually recorded is shown (Inv 8).
        model: (e.provenance && e.provenance.model) || null,
        adapter: e.adapter || null,
        latencyMs: typeof e.latency_ms === 'number' ? e.latency_ms : null,
        at: e.observed_at || e.completed_at || e.started_at || null,
        // Raw stored error text is scrubbed before it can reach a curator's eye (R2).
        error: e.error ? scrubTechnical(e.error) : null,
    }));
}

// The run-level outcome + provenance line, shown once a run is terminal (or interrupted).
// Duration is real elapsed time from two recorded stamps, or null when either is missing —
// never a guess, and never a running clock the rail would have to animate.
export function runOutcome(run) {
    if (!run) return null;
    const started = toMs(run.started_at);
    const done = toMs(run.completed_at);
    const durationMs = (started != null && done != null && done >= started) ? done - started : null;
    return {
        present: statusPresentation(run),   // { key, label, tone }
        live: isRunLive(run),
        terminal: isRunTerminal(run),
        operation: run.operation || null,
        operationLabel: OPERATION_LABEL[run.operation] || run.operation || null,
        initiator: run.initiator || null,
        actualSource: run.actual_source || null,
        terminalReason: run.terminal_reason || null,
        telemetryDegraded: !!run.telemetry_degraded,
        isSuggestionRun: isSuggestionRun(run),
        stale: !!run.stale,
        stalenessSeconds: typeof run.staleness_seconds === 'number' ? run.staleness_seconds : null,
        durationMs,
        runId: run.run_id || null,
        eventCount: Array.isArray(run.events) ? run.events.length : 0,
    };
}

// 2c — a stalled run says how long it has been silent, in REAL seconds. Never an animation.
export function stalenessNote(run) {
    if (!run) return null;
    const s = String(run.status || '').toLowerCase();
    if ((s === 'running' || s === 'pending') && run.stale && typeof run.staleness_seconds === 'number') {
        return `No events for ${run.staleness_seconds}s`;
    }
    return null;
}

// 2d — the session's REAL circulation events, read-only from the store. A LOCAL, this-session
// voice, deliberately NOT unified with backend run events:
//   • accept — a suggestion the curator accepted (a user_confirmed mark deriving from one).
//   • recall — the recall currently being performed (the store keeps only the live one; there
//     is no recorded recall HISTORY — see the P5F marker, we do not invent one).
export function sessionEvents({ marks = [], recall = null } = {}) {
    const out = [];
    for (const m of marks || []) {
        if (m && m.source === 'user_confirmed' && m.derived_from) {
            out.push({
                source: SOURCE.SESSION,
                kind: 'accept',
                key: `accept-${m.id}`,
                at: m.created_at || null,
                markId: m.id,
                role: m.role || null,
                label: m.label || null,
                producer: (m.provenance && m.provenance.producer) || null,
                runId: (m.provenance && m.provenance.run_id) || null,
            });
        }
    }
    if (recall && (recall.markId || recall.perceptId)) {
        out.push({
            source: SOURCE.SESSION,
            kind: 'recall',
            key: `recall-${recall.markId || recall.perceptId}`,
            at: recall.startedAt || null,
            markId: recall.markId || null,
            perceptId: recall.perceptId || null,
            live: true,
        });
    }
    return out.sort((a, b) => sortMs(a.at) - sortMs(b.at));
}

// One list, two styles. Run events keep their stored arrival order among themselves; session
// events are merged in by best-available timestamp. The two clocks are NOT reconciled — a
// missing time sinks to the end rather than claiming a moment, and the caller labels each row
// with its `source` so a local judgement is never read in the register of a backend record.
export function timeline(run, session = []) {
    const rows = [...runEvents(run), ...(session || [])];
    return rows
        .map((r, i) => ({ ...r, _i: i }))
        .sort((a, b) => {
            const d = sortMs(a.at) - sortMs(b.at);
            return d !== 0 ? d : a._i - b._i;
        });
}

// 2b — the accepted marks a given run produced (its suggestions the curator confirmed). Tapping
// a run event highlights exactly these. A read-only store lookup; no mutation, no new link.
export function acceptedMarksForRun(runId, marks = []) {
    if (!runId) return [];
    return (marks || []).filter(
        (m) => m && m.source === 'user_confirmed' && m.provenance && m.provenance.run_id === runId,
    );
}

// Collapsed-summary text — honest about the four states the rail can be in, and nothing more.
export function railSummary({ postId, unreadable, run, outcome }) {
    if (!postId) return 'no image';
    if (unreadable) return 'couldn’t read the run';
    if (!run) return 'nothing recorded yet';
    if (outcome && outcome.live) return 'observing…';
    return outcome ? outcome.present.label.toLowerCase() : 'recorded';
}

// Millisecond duration → a compact, honest label. Never rounds a missing value into a number.
export function durationLabel(ms) {
    if (ms == null) return '—';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    return `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
}
