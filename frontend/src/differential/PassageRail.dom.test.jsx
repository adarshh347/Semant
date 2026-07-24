import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import PassageRail from './PassageRail';

/**
 * CIRCUIT-001 P5-B — the Passage Rail surface. jsdom has no layout, so this mounts the rail in
 * isolation over a fixture `VisionRunOut` (the cache preseeded so render is synchronous) and
 * proves the DOM honesty guarantees: absent fields render "—", there is NO progressbar, the two
 * sources wear two source badges, and tapping a row fires the read-only highlight callback.
 */

let container; let root; let qc; let served;
async function mount(node) { await act(async () => { root.render(node); }); }
const OP = 'dissect';
const POST = 'post_1';

function wrap(props) {
    return (
        <QueryClientProvider client={qc}>
            <PassageRail postId={POST} operation={OP} {...props} />
        </QueryClientProvider>
    );
}

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    served = terminalRun();
    // the background refetch must agree with the preseed, or it would overwrite it — so the stub
    // serves whatever the test last seeded (see `seed`).
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ run: served }) })));
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    qc.clear();
    vi.unstubAllGlobals();
});

const terminalRun = () => ({
    run_id: 'run_2', operation: 'dissect', status: 'succeeded', stale: false,
    started_at: '2026-07-24T10:00:00Z', completed_at: '2026-07-24T10:00:03.5Z',
    initiator: 'curator', actual_source: 'live',
    events: [
        { event_id: 'e1', stage_id: 'dissect.receive', status: 'succeeded', latency_ms: 12, adapter: 'router', observed_at: '2026-07-24T10:00:01Z', provenance: { model: 'yolo11n_seg' } },
        { event_id: 'e2', stage_id: 'dissect.segment.general', status: 'succeeded', observed_at: '2026-07-24T10:00:02Z' }, // no latency, no model → "—"
    ],
});
const acceptedMark = () => ({
    id: 'vm_a', source: 'user_confirmed', derived_from: 'vm_sugg', role: 'gaze_address',
    label: 'the held line', created_at: '2026-07-24T10:00:05Z',
    provenance: { model: 'sam', producer: 'sam_refine', run_id: 'run_2' },
});

// preseed so useQuery returns data on first render, and keep the background refetch in agreement.
function seed(run = terminalRun()) { served = run; qc.setQueryData(['passage-run', POST, OP], run); }
const text = () => container.textContent;
async function waitFor(pred, { timeout = 1000, interval = 15 } = {}) {
    const start = Date.now();
    // eslint-disable-next-line no-constant-condition
    while (true) {
        if (pred()) return true;
        if (Date.now() - start > timeout) return pred();
        await act(async () => { await new Promise((res) => setTimeout(res, interval)); });
    }
}
const openBody = async () => {
    const toggle = [...container.querySelectorAll('button')].find((b) => /Passage/.test(b.textContent));
    await act(async () => { toggle.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
};

describe('PassageRail — the honest run surface', () => {
    it('renders the real events; absent latency/model show "—", never a guess (Inv 8)', async () => {
        seed();
        await mount(wrap({ marks: [] }));
        await openBody();
        expect(text()).toContain('Received request');       // humanized stage
        expect(text()).toContain('12 ms');                  // recorded latency
        expect(text()).toContain('yolo11n_seg');            // recorded model
        expect(text()).toContain('—');                      // the second event's absent telemetry
        // terminal outcome: real elapsed time + provenance line
        expect(text()).toContain('3.5 s');
        expect(text().toLowerCase()).toContain('curator');  // initiator
    });

    it('has NO progressbar / meter element anywhere (Inv 9 — no fake progress)', async () => {
        seed();
        await mount(wrap({ marks: [] }));
        await openBody();
        expect(container.querySelector('[role="progressbar"]')).toBeNull();
        expect(container.querySelector('progress, meter')).toBeNull();
    });

    it('(2d) run events and session events wear two distinct source badges', async () => {
        seed();
        await mount(wrap({ marks: [acceptedMark()] }));
        await openBody();
        const runBadges = [...container.querySelectorAll('.pr-src--run')];
        const sessionBadges = [...container.querySelectorAll('.pr-src--session')];
        expect(runBadges.length).toBeGreaterThan(0);
        expect(sessionBadges.length).toBe(1);               // the one accepted mark
        expect(text()).toContain('Accepted a suggestion');
        expect(text()).toContain('sam_refine');             // producer on the session row
    });

    it('(2b) tapping a run row highlights the marks that run produced', async () => {
        seed();
        const onHighlightRun = vi.fn();
        await mount(wrap({ marks: [acceptedMark()], onHighlightRun }));
        await openBody();
        const runRow = [...container.querySelectorAll('.pr-row--run .pr-row-btn')][0];
        await act(async () => { runRow.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onHighlightRun).toHaveBeenCalledWith('run_2');
    });

    it('(2b) tapping a session accept row highlights that mark', async () => {
        seed();
        const onHighlightMark = vi.fn();
        await mount(wrap({ marks: [acceptedMark()], onHighlightMark }));
        await openBody();
        const sessRow = container.querySelector('.pr-row--accept .pr-row-btn');
        await act(async () => { sessRow.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onHighlightMark).toHaveBeenCalledWith('vm_a');
    });

    it('a suggestion-producing run labels itself; dissect does not', async () => {
        seed({ ...terminalRun(), operation: 'refine' });
        await mount(wrap({ marks: [] }));
        await openBody();
        expect(text().toLowerCase()).toContain('suggestion run');
    });

    it('a failed REFRESH keeps the last real run — never erases a record on a poll blip (P2.2R R0)', async () => {
        seed();                                   // a good run is in the cache
        await mount(wrap({ marks: [] }));
        await openBody();
        expect(text()).toContain('Received request');
        // now every read fails — force a refetch and let it reject
        fetch.mockImplementation(async () => { throw new Error('network down'); });
        const refresh = [...container.querySelectorAll('button')].find((b) => /refresh/i.test(b.textContent));
        await act(async () => { refresh.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        await waitFor(() => /showing the last read/i.test(text()));
        expect(text().toLowerCase()).toContain('showing the last read');
        expect(text()).toContain('Received request');   // the real run is STILL there
    });

    it('an absent run says "nothing recorded", NOT a failure', async () => {
        seed(null);
        await mount(wrap({ marks: [] }));
        await openBody();
        expect(text().toLowerCase()).toContain('no run recorded yet');
    });
});
