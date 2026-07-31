import { readFileSync } from 'node:fs';
import { describe, it, expect } from 'vitest';
import {
    SOURCE, isRunLive, isRunTerminal, isSuggestionRun, runEvents, runOutcome,
    stalenessNote, sessionEvents, timeline, acceptedMarksForRun, railSummary, durationLabel,
} from './passageRail';

/**
 * CIRCUIT-001 P5-B — the Passage Rail derivation. The rail is a witness (Invariant 9): these
 * prove it can only report what the record holds. Every assertion maps to an anti-spec hotspot
 * (P0.5 §4.3 + CIRCULATION-SPINE Invariants 8/9/12/13) — absent telemetry stays "—", a stalled
 * run stops the poll instead of spinning, and backend records never mix voices with local events.
 */

const runningRun = (over = {}) => ({
    run_id: 'run_1', operation: 'dissect', status: 'running', stale: false,
    started_at: '2026-07-24T10:00:00Z',
    events: [
        { event_id: 'e1', stage_id: 'dissect.receive', status: 'succeeded', latency_ms: 12.4, adapter: 'router', observed_at: '2026-07-24T10:00:01Z', provenance: { model: 'yolo11n_seg' } },
        { event_id: 'e2', stage_id: 'dissect.segment.general', status: 'running', observed_at: '2026-07-24T10:00:02Z' }, // no latency, no model
    ],
    ...over,
});
const terminalRun = (over = {}) => ({
    run_id: 'run_2', operation: 'dissect', status: 'succeeded', stale: false,
    started_at: '2026-07-24T10:00:00Z', completed_at: '2026-07-24T10:00:03.5Z',
    initiator: 'curator', actual_source: 'live',
    events: [{ event_id: 'e1', stage_id: 'dissect.complete', status: 'succeeded', latency_ms: 8, observed_at: '2026-07-24T10:00:03Z' }],
    ...over,
});

// ── Inv 9 / Inv 13 — live vs terminal vs stalled ──────────────────────────────
describe('live/terminal gating — a stalled run is NOT live (Inv 13)', () => {
    it('a running, non-stale run is live and worth polling', () => {
        expect(isRunLive(runningRun())).toBe(true);
        expect(isRunTerminal(runningRun())).toBe(false);
    });
    it('a running BUT stale run is terminal-for-poll — we stop, never spin forever', () => {
        const stalled = runningRun({ stale: true, staleness_seconds: 47 });
        expect(isRunLive(stalled)).toBe(false);
        expect(isRunTerminal(stalled)).toBe(true);
        expect(stalenessNote(stalled)).toBe('No events for 47s');
    });
    it('a finished run is terminal; absence is neither live nor terminal', () => {
        expect(isRunLive(terminalRun())).toBe(false);
        expect(isRunTerminal(terminalRun())).toBe(true);
        expect(isRunLive(null)).toBe(false);
        expect(isRunTerminal(null)).toBe(false);
        expect(stalenessNote(terminalRun())).toBeNull();
    });
});

// ── Inv 8 — absent telemetry stays null → the view renders "—", never a guess ──
describe('run events keep arrival order and never invent absent fields (Inv 8)', () => {
    it('maps stored events in order; missing model/latency stay null', () => {
        const evs = runEvents(runningRun());
        expect(evs.map((e) => e.stageId)).toEqual(['dissect.receive', 'dissect.segment.general']); // stored order
        expect(evs[0].model).toBe('yolo11n_seg');
        expect(evs[0].latencyMs).toBe(12.4);
        expect(evs[1].model).toBeNull();       // not recorded → null → "—"
        expect(evs[1].latencyMs).toBeNull();
        evs.forEach((e) => expect(e.source).toBe(SOURCE.RUN));
    });
    it('duration is real elapsed time, or null when a stamp is missing — never estimated', () => {
        expect(runOutcome(terminalRun()).durationMs).toBe(3500);
        expect(runOutcome(runningRun()).durationMs).toBeNull();     // no completed_at
        expect(durationLabel(null)).toBe('—');
        expect(durationLabel(3500)).toBe('3.5 s');
        expect(durationLabel(8)).toBe('8 ms');
    });
});

// ── suggestion runs label themselves; their marks are never evidence ───────────
describe('a suggestion-producing run is labelled as such', () => {
    it('refine + semantic_read are suggestion runs; dissect is not', () => {
        expect(isSuggestionRun({ operation: 'refine' })).toBe(true);
        expect(isSuggestionRun({ operation: 'semantic_read' })).toBe(true);
        expect(isSuggestionRun({ operation: 'dissect' })).toBe(false);
        expect(runOutcome(runningRun({ operation: 'refine' })).isSuggestionRun).toBe(true);
    });
});

// ── 2d — two sources, two voices, one list, but never one clock ────────────────
const acceptedMark = (over = {}) => ({
    id: 'vm_a', source: 'user_confirmed', derived_from: 'vm_sugg', role: 'gaze_address',
    label: 'the held line', created_at: '2026-07-24T10:00:05Z',
    provenance: { model: 'sam', producer: 'sam_refine', run_id: 'run_2' }, ...over,
});

describe('session events derive from the store, read-only, in a distinct voice', () => {
    it('an accepted mark becomes an accept event carrying producer + run link', () => {
        const evs = sessionEvents({ marks: [acceptedMark()], recall: null });
        expect(evs).toHaveLength(1);
        expect(evs[0].source).toBe(SOURCE.SESSION);
        expect(evs[0].kind).toBe('accept');
        expect(evs[0].markId).toBe('vm_a');
        expect(evs[0].producer).toBe('sam_refine');
        expect(evs[0].runId).toBe('run_2');
    });
    it('a plain curator mark (no derived_from) is NOT a session accept event', () => {
        const plain = { id: 'vm_p', source: 'user', role: 'gesture' };
        expect(sessionEvents({ marks: [plain] })).toHaveLength(0);
    });
    it('the live recall performance is a session event; no recall HISTORY is invented', () => {
        const evs = sessionEvents({ marks: [], recall: { markId: 'vm_a', startedAt: 111 } });
        expect(evs).toHaveLength(1);
        expect(evs[0].kind).toBe('recall');
        expect(evs[0].live).toBe(true);
    });
    it('timeline merges run + session by time, tagging each row with its source', () => {
        const rows = timeline(terminalRun(), sessionEvents({ marks: [acceptedMark()] }));
        const sources = rows.map((r) => r.source);
        expect(sources).toContain(SOURCE.RUN);
        expect(sources).toContain(SOURCE.SESSION);
        // the accept (10:00:05) sorts AFTER the run's complete event (10:00:03)
        expect(rows[rows.length - 1].source).toBe(SOURCE.SESSION);
    });
});

// ── 2b — tapping a run highlights exactly the marks it produced (read-only lookup) ──
describe('acceptedMarksForRun links a run to the marks accepted from it', () => {
    it('returns only user_confirmed marks whose provenance.run_id matches', () => {
        const marks = [
            acceptedMark({ id: 'vm_a', provenance: { run_id: 'run_2' } }),
            acceptedMark({ id: 'vm_b', provenance: { run_id: 'other' } }),
            { id: 'vm_s', source: 'model_suggested', provenance: { run_id: 'run_2' } }, // a suggestion, not evidence
        ];
        const linked = acceptedMarksForRun('run_2', marks);
        expect(linked.map((m) => m.id)).toEqual(['vm_a']);
        expect(acceptedMarksForRun(null, marks)).toEqual([]);
    });
});

// ── Inv 12 — the summary scopes its claim to the four honest states ────────────
describe('railSummary is honest about which of four states the rail is in', () => {
    it('distinguishes no-image / unreadable / empty / observing / recorded', () => {
        expect(railSummary({ postId: null })).toBe('no image');
        expect(railSummary({ postId: 'p', unreadable: true })).toBe('couldn’t read the run');
        expect(railSummary({ postId: 'p', run: null })).toBe('nothing recorded yet');
        const live = runningRun();
        expect(railSummary({ postId: 'p', run: live, outcome: runOutcome(live) })).toBe('observing…');
        const done = terminalRun();
        expect(railSummary({ postId: 'p', run: done, outcome: runOutcome(done) })).toBe('complete');
    });
});

// ── the honesty boundaries, enforced by source (2c) ───────────────────────────
describe('2c — the rail cannot render a progress bar, a cancel, or a fake spinner', () => {
    const JSX = readFileSync(new URL('./PassageRail.jsx', import.meta.url), 'utf8');
    const CSS = readFileSync(new URL('./PassageRail.css', import.meta.url), 'utf8');
    const WS = readFileSync(new URL('./DifferentialWorkspace.jsx', import.meta.url), 'utf8');

    it('no progressbar role, no <progress>, no meter, no percent width anywhere', () => {
        expect(JSX).not.toMatch(/role=["']progressbar["']/);
        expect(JSX).not.toMatch(/<progress|<meter/);
        expect(JSX).not.toMatch(/width:\s*\$\{|width:\s*[`'"]\s*\d+%/); // no computed % width bar
        expect(CSS).not.toMatch(/@keyframes/);                          // no animation to fake activity
    });
    it('no cancel path — the rail never offers to stop a run it cannot stop', () => {
        expect(JSX.toLowerCase()).not.toMatch(/cancel|abort run|stop run/);
    });
    it('the poll re-reads ONLY while the run is live (refetchInterval → false otherwise)', () => {
        expect(JSX).toMatch(/refetchInterval:\s*\(query\)\s*=>\s*\(isRunLive\(query\.state\.data\)\s*\?\s*POLL_MS\s*:\s*false\)/);
    });
    it('the workspace follows the tool operation and highlights via the read-only recall channel', () => {
        expect(WS).toMatch(/const passageOperation =/);
        expect(WS).toMatch(/acceptedMarksForRun\(runId, visualMarks\)/);
        expect(WS).toMatch(/playMarkRecall/);
        expect(WS).toMatch(/\/\/ P5F:/);   // the multi-mark-highlight + runs-list gaps are marked
    });
});
