// P2.2 fixture harness (NOT production). Renders the REAL VisionActivityRail with a stubbed
// fetch so every state can be rendered in a browser at real inspector widths. Fixture-rendered.
import React from 'react';
import { createRoot } from 'react-dom/client';
import '../src/index.css';
import VisionActivityRail from '../src/differential/VisionActivityRail.jsx';

const min = (n) => new Date(Date.now() - n * 60000).toISOString();
const ev = (stage_id, o = {}) => ({
  stage_id, status: 'succeeded', latency_ms: null, adapter: null,
  fallbacks: [], dependencies: [], error: null, ...o,
});
const run = (operation, o = {}) => ({
  run_id: 'r_' + operation, operation, status: 'succeeded', stale: false,
  created_at: min(3), updated_at: min(2), completed_at: min(2),
  terminal_reason: 'ok', error: null, telemetry_degraded: false,
  requested_profile: {}, result_summary: {}, events: [], ...o,
});

// Fixture universes keyed by postId → operation → run|null
const FIX = {
  resting: { dissect: null, refine: null, semantic_read: null, find_similar: null },
  success: {
    dissect: run('dissect', {
      actual_source: 'segformer_clothes+yolo',
      result_summary: { anchor_count: 4, region_count: 4 },
      events: [ev('dissect.receive'), ev('dissect.fetch_image', { latency_ms: 250 }),
        ev('dissect.route_domain'), ev('dissect.segment.fashion', { adapter: 'segformer_clothes', latency_ms: 402 }),
        ev('dissect.segment.general', { adapter: 'yolo11_seg', latency_ms: 88 }),
        ev('dissect.merge_anchors', { dependencies: ['dissect.segment.general'] }),
        ev('dissect.persist_regions'), ev('dissect.complete')],
    }),
    refine: null,
    semantic_read: run('semantic_read', {
      requested_profile: { region_ids: ['seg_0', 'fseg_1', 'fseg_0'] },
      result_summary: { assertions: 4, status: 'succeeded' },
      events: [ev('semantic_read.receive'), ev('semantic_read.fetch_image', { latency_ms: 133 }),
        ev('semantic_read.run', { adapter: 'semantic_pass', latency_ms: 1840 }),
        ev('semantic_read.merge_curator_state'), ev('semantic_read.persist_semantics'), ev('semantic_read.complete')],
    }),
    find_similar: run('find_similar', {
      requested_profile: { region_id: 'seg_0' },
      result_summary: { neighbours: 5, space: 'visual_identity', status: 'ready' },
      events: [ev('find_similar.receive'), ev('find_similar.route_space'), ev('find_similar.scope'),
        ev('find_similar.fetch_image', { latency_ms: 40 }),
        ev('find_similar.retrieve', { adapter: 'dinov2_vits14', latency_ms: 210 }), ev('find_similar.complete')],
    }),
  },
  trouble: {
    dissect: run('dissect', {
      status: 'partial', terminal_reason: 'fine_decomposition_degraded', actual_source: 'yolo',
      events: [ev('dissect.receive'), ev('dissect.segment.general', { adapter: 'yolo11_seg', latency_ms: 91 }),
        ev('dissect.fallback.detect', { adapter: 'vision_service.detect_regions', fallbacks: ['vision'] }),
        ev('dissect.decompose_fine', { status: 'failed', error: 'groq: 503 upstream unavailable' }),
        ev('dissect.persist_regions'), ev('dissect.complete', { status: 'partial' })],
    }),
    refine: run('refine', {
      status: 'cancelled', terminal_reason: 'request_cancelled',
      requested_profile: { region_id: 'seg_0', geometry_rev: 3 },
      events: [ev('refine.receive'), ev('refine.propose', { adapter: 'sam2', latency_ms: 320 })],
    }),
    semantic_read: run('semantic_read', {
      status: 'failed', terminal_reason: 'route_exception',
      error: 'RuntimeError at /home/adarsh/app/semantic_pass.py: POST https://res.cloudinary.com/x/y token ghp_ABCDEF1234567890abcdef failed',
      events: [ev('semantic_read.receive'), ev('semantic_read.fetch_image', { latency_ms: 140 })],
    }),
    find_similar: run('find_similar', {
      status: 'running', stale: true, staleness_seconds: 300, completed_at: null, terminal_reason: null,
      requested_profile: { region_id: 'seg_2' },
      events: [ev('find_similar.receive'), ev('find_similar.route_space')],
    }),
  },
};

// Stub fetch: /api/v1/posts/{postId}/vision-runs/latest?operation={op}
const realFetch = window.fetch;
window.fetch = async (url) => {
  const u = String(url);
  const m = u.match(/\/posts\/([^/]+)\/vision-runs\/latest\?operation=([a-z_]+)/);
  if (m) {
    const [, postId, op] = m;
    const universe = FIX[postId] || FIX.resting;
    return { ok: true, json: async () => ({ run: universe[op] ?? null }) };
  }
  return realFetch ? realFetch(url) : { ok: false, json: async () => ({}) };
};

const regions = [
  { id: 'seg_0', category: 'top' }, { id: 'fseg_0', category: 'sleeve' },
  { id: 'fseg_1', category: 'collar' }, { id: 'seg_2', category: 'skirt' },
];

function Column({ label, postId, width }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ font: '600 0.6rem/1 Inter, sans-serif', letterSpacing: '0.08em',
        textTransform: 'uppercase', color: '#9A909E', marginBottom: 6 }}>{label}</div>
      <aside className="diff-inspector" style={{
        width, boxSizing: 'border-box', containerName: 'diff', containerType: 'inline-size',
        display: 'flex', flexDirection: 'column', gap: '1rem', padding: '1rem',
        background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 10,
        minHeight: 260, overflowY: 'auto',
      }}>
        {/* a representative panel above, to prove the rail sits quietly at the bottom */}
        <div className="diff-insp-refine" style={{ flex: '0 0 auto' }}>
          <span className="diff-eyebrow">Read</span>
          <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--ink-muted)' }}>
            (representative active tool panel)
          </p>
        </div>
        <VisionActivityRail postId={postId} regions={regions} actionStatus={{}} />
      </aside>
    </div>
  );
}

function App() {
  React.useEffect(() => {
    // auto-open every rail except the first (resting) so states are visible in one shot
    const t = setTimeout(() => {
      document.querySelectorAll('[data-open="1"] .va-toggle').forEach((b) => b.click());
    }, 60);
    return () => clearTimeout(t);
  }, []);
  return (
    <div style={{ display: 'flex', gap: 28, alignItems: 'flex-start', flexWrap: 'wrap',
      padding: 28, background: 'var(--bg)', minHeight: '100vh' }}>
      <Column label="Resting (collapsed default)" postId="resting" width={280} />
      <div data-open="1"><Column label="Multi-op · success" postId="success" width={280} /></div>
      <div data-open="1"><Column label="Partial · cancelled · failed · stale" postId="trouble" width={280} /></div>
      <div data-open="1"><Column label="Narrow pane (208px)" postId="trouble" width={208} /></div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
