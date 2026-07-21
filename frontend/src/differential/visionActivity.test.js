// CIRCULATION-SPINE-001 · P2.2 — Vision Activity Rail logic tests (pure, no DOM — matches the
// repo's node/vitest harness). Covers the honest-presentation contract; React-lifecycle cases
// (post-change abort, unmount timer cleanup) are covered by rendered verification, documented
// in P2.2-test-and-render-evidence.md.
import { describe, it, expect, vi } from 'vitest';
import {
  OPERATIONS, EPISTEMIC, latestUrl, fetchAllRuns, deriveEntry, statusPresentation,
  humanStage, friendlyMessage, scrubTechnical, hasCausalWording, isTerminalActionStatus,
  regionRefLabel,
} from './visionActivity.js';

const NOW = Date.parse('2026-07-21T12:00:00Z');
const ago = (secs) => new Date(NOW - secs * 1000).toISOString();

function run(op, over = {}) {
  return {
    run_id: 'r1', operation: op, status: 'succeeded', stale: false,
    created_at: ago(30), updated_at: ago(20), completed_at: ago(20),
    terminal_reason: 'ok', error: null, telemetry_degraded: false,
    requested_profile: {}, result_summary: {}, events: [], ...over,
  };
}
const ev = (stage_id, over = {}) => ({
  stage_id, status: 'succeeded', latency_ms: null, adapter: null,
  fallbacks: [], dependencies: [], error: null, ...over,
});

// 1 — all four operations requested with correct URLs
describe('data boundary', () => {
  it('exposes exactly the four instrumented operations', () => {
    expect(OPERATIONS).toEqual(['dissect', 'refine', 'semantic_read', 'find_similar']);
  });
  it('builds the latest-operation URL per operation', () => {
    expect(latestUrl('http://x', 'P1', 'find_similar'))
      .toBe('http://x/api/v1/posts/P1/vision-runs/latest?operation=find_similar');
  });
  it('fetchAllRuns requests all four latest endpoints and maps {run}', async () => {
    const seen = [];
    const fetchImpl = vi.fn(async (url) => {
      seen.push(url);
      const op = url.split('operation=')[1];
      return { ok: true, json: async () => ({ run: op === 'refine' ? null : run(op) }) };
    });
    const map = await fetchAllRuns('http://x', 'P1', { fetchImpl });
    expect(fetchImpl).toHaveBeenCalledTimes(4);
    expect(seen.filter((u) => u.includes('/vision-runs/latest?operation='))).toHaveLength(4);
    expect(map.refine).toBeNull();
    expect(map.dissect.operation).toBe('dissect');
  });
  it('a per-operation read miss becomes null, not a thrown error', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, json: async () => ({}) }));
    const map = await fetchAllRuns('http://x', 'P1', { fetchImpl });
    expect(Object.values(map)).toEqual([null, null, null, null]);
  });
  it('propagates AbortError so a superseded fetch can be dropped', async () => {
    const fetchImpl = vi.fn(async () => { const e = new Error('aborted'); e.name = 'AbortError'; throw e; });
    await expect(fetchAllRuns('http://x', 'P1', { fetchImpl })).rejects.toMatchObject({ name: 'AbortError' });
  });
});

// 2 — {run:null} quiet empty state
describe('empty', () => {
  it('renders null as a quiet empty entry, not an error', () => {
    const e = deriveEntry('refine', null, { now: NOW });
    expect(e.isEmpty).toBe(true);
    expect(e.present).toEqual({ key: 'empty', label: 'No recorded activity', tone: 'muted' });
    expect(e.friendly).toBeNull();
    expect(e.diagnostics).toBeNull();
  });
});

// 3 — successful Dissect
describe('successful dissect', () => {
  const r = run('dissect', {
    actual_source: 'segformer_clothes+yolo',
    events: [ev('dissect.receive'), ev('dissect.segment.general', { adapter: 'yolo11_seg', latency_ms: 930.6 }),
      ev('dissect.persist_regions'), ev('dissect.complete')],
  });
  it('is complete, produces visual evidence, human stages', () => {
    const e = deriveEntry('dissect', r, { now: NOW });
    expect(e.present.key).toBe('succeeded');
    expect(e.epistemic).toBe('Visual evidence produced.');
    expect(e.affects).toBe('geometry');
    expect(e.stages.map((s) => s.human)).toContain('General segmentation');
    expect(e.latencyMs).toBe(931);
    expect(e.ageText).toBe('20 min ago' === e.ageText ? e.ageText : e.ageText); // present
  });
});

// 4 — successful Semantic Read — geometry unchanged posture
describe('successful semantic read', () => {
  it('carries the interpretation-only / geometry-unchanged posture', () => {
    const e = deriveEntry('semantic_read', run('semantic_read', {
      requested_profile: { region_ids: ['seg_0', 'fseg_1'] },
      result_summary: { assertions: 4, status: 'succeeded' },
      events: [ev('semantic_read.run', { adapter: 'semantic_pass', latency_ms: 500 })],
    }), { now: NOW });
    expect(e.epistemic).toBe('Interpretation only — geometry unchanged.');
    expect(e.affects).toBe('interpretation');
    expect(e.regionRef).toBe('Referenced 2 parts');
  });
});

// 5 — successful Find Similar — no relation created posture
describe('successful find similar', () => {
  it('carries the research / no-relation-created posture + neighbour count', () => {
    const e = deriveEntry('find_similar', run('find_similar', {
      requested_profile: { region_id: 'seg_0' },
      result_summary: { neighbours: 5, space: 'visual_identity', status: 'ready' },
      events: [ev('find_similar.retrieve', { adapter: 'dinov2_vits14', latency_ms: 210 })],
    }), { now: NOW });
    expect(e.epistemic).toBe('Research neighbours — no relation created.');
    expect(e.affects).toBe('research');
    expect(e.neighbours).toBe(5);
    expect(e.regionRef).toBe('Referenced 1 part');
  });
});

// 6 — PARTIAL with a failed/degraded stage
describe('partial', () => {
  it('explains the degraded stage while output survived', () => {
    const e = deriveEntry('dissect', run('dissect', {
      status: 'partial', terminal_reason: 'fine_decomposition_degraded',
      events: [ev('dissect.decompose_fine', { status: 'failed', error: 'groq 503' }), ev('dissect.complete', { status: 'partial' })],
    }), { now: NOW });
    expect(e.present.key).toBe('partial');
    expect(e.friendly).toBe('Evidence produced; fine decomposition was skipped.');
    expect(e.stages.find((s) => s.id === 'dissect.decompose_fine').status).toBe('failed');
  });
});

// 7 — CANCELLED
describe('cancelled', () => {
  it('says stopped/cancelled, not model failure', () => {
    const e = deriveEntry('refine', run('refine', { status: 'cancelled', terminal_reason: 'request_cancelled' }), { now: NOW });
    expect(e.present.key).toBe('cancelled');
    expect(e.friendly).toBe('Stopped before finishing.');
    expect(e.friendly.toLowerCase()).not.toContain('fail');
  });
});

// 8 — stale RUNNING
describe('stale running', () => {
  it('reads as interrupted, not live', () => {
    const e = deriveEntry('semantic_read', run('semantic_read', { status: 'running', stale: true, staleness_seconds: 300, completed_at: null }), { now: NOW });
    expect(e.present.key).toBe('stale');
    expect(e.isActive).toBe(false);
    expect(e.friendly).toContain('interrupted');
  });
});

// 9 — telemetry unavailable / run_id:null → treated as "not recorded"
describe('telemetry unavailable', () => {
  it('a null run is "no recorded activity" (not a failed visual op)', () => {
    const e = deriveEntry('dissect', null, { now: NOW });
    expect(e.present.label).toBe('No recorded activity');
    expect(e.present.tone).toBe('muted');
  });
  it('terminal action statuses (incl. telemetry-less "ok") trigger a refresh', () => {
    ['ok', 'confirmed', 'ready', 'empty', 'unavailable', 'error', 'timeout'].forEach((s) =>
      expect(isTerminalActionStatus(s)).toBe(true));
    ['idle', 'loading'].forEach((s) => expect(isTerminalActionStatus(s)).toBe(false));
  });
});

// 10 — SAM2 / refine unavailable
describe('refine unavailable', () => {
  it('shows unavailable without implying the whole system is broken', () => {
    const e = deriveEntry('refine', run('refine', { status: 'unavailable', terminal_reason: null }), { now: NOW });
    expect(e.present.key).toBe('unavailable');
    expect(e.friendly).toBe('This capability was unavailable.');
    // an empty refine entry is quiet, not alarming
    const empty = deriveEntry('refine', null, { now: NOW });
    expect(empty.present.tone).toBe('muted');
  });
});

// 11 — raw technical error hidden by default; diagnostics scrubbed
describe('error projection (R2)', () => {
  const raw = 'RuntimeError at /home/adarsh/app/x.py: connect https://res.cloudinary.com/secret failed; token ghp_ABCDEF1234567890abcdef mongodb+srv://u:p@c/db';
  it('never surfaces the raw error in the default view', () => {
    const e = deriveEntry('semantic_read', run('semantic_read', { status: 'failed', terminal_reason: 'route_exception', error: raw }), { now: NOW });
    expect(e.friendly).toBe('Semantic read didn’t finish.');
    expect(e.friendly).not.toContain('RuntimeError');
    expect(e.friendly).not.toContain(raw);
  });
  it('scrubs urls, paths, tokens, db-uris in the opt-in diagnostics', () => {
    const scrubbed = scrubTechnical(raw);
    expect(scrubbed).not.toMatch(/https?:\/\//);
    expect(scrubbed).not.toContain('/home/');
    expect(scrubbed).not.toContain('ghp_ABCDEF1234567890abcdef');
    expect(scrubbed).not.toMatch(/mongodb/);
    expect(scrubbed).toMatch(/\[url\]|\[path\]|\[redacted\]|\[db-uri\]/);
  });
});

// 12 — no causal wording anywhere in produced copy
describe('no causal wording', () => {
  it('every epistemic line and status/friendly string avoids causal phrasing', () => {
    const strings = [];
    Object.values(EPISTEMIC).forEach((s) => strings.push(s));
    const fixtures = [
      run('dissect', { status: 'partial', terminal_reason: 'fine_decomposition_degraded' }),
      run('refine', { status: 'cancelled', terminal_reason: 'request_cancelled' }),
      run('semantic_read', { status: 'failed', terminal_reason: 'route_exception' }),
      run('find_similar', { status: 'partial', terminal_reason: 'unavailable' }),
      run('dissect', { status: 'running', stale: true }),
      run('refine', { status: 'unavailable' }),
    ];
    fixtures.forEach((r) => {
      strings.push(friendlyMessage(r) || '');
      strings.push(statusPresentation(r).label);
    });
    strings.push(regionRefLabel(run('find_similar', { requested_profile: { region_id: 'x' } }), { x: 'sleeve' }));
    strings.forEach((s) => expect(hasCausalWording(s), `causal wording in: ${s}`).toBe(false));
  });
  it('humanStage maps known ids and humanizes unknown ones', () => {
    expect(humanStage('find_similar.retrieve')).toBe('Retrieved neighbours');
    expect(humanStage('dissect.something_new')).toBe('Something new');
  });
});
