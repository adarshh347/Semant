import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useRecallPlayer } from './recall';
import { makeVisualMark } from './visualMarks';

/**
 * CIRCUIT-001 P3-A — the mark recall player. `playRecall` sets a perceptId,
 * `playMarkRecall` sets a markId; the DISPATCH (PostDetailPage) routes a chip's
 * `data-mark-id` to the latter. This test stands in for that route: a store whose
 * `recall.markId` names a mark makes the player perform the MARK — not a percept —
 * and degrade honestly when the mark is missing or detached.
 *
 * We drive `prefers-reduced-motion` so the player jumps straight to the settled
 * state (deterministic, no rAF timing) — the same escape hatch the player ships.
 */

const brush = (over = {}) => makeVisualMark('brush_field', {
    role: 'light_field', source: 'user', status: 'committed',
    geometry: { kind: 'freehand_path' }, label: 'the falling light', ...over,
}, { now: 't' });

const STORE = (recall, marks, over = {}) => ({
    recall, percepts: [], visualMarks: marks, regions: [], grounds: [],
    groundById: () => null, ...over,
});

let container, root, seen;
function Probe({ store }) {
    const player = useRecallPlayer(store);
    seen = player;
    return (
        <div
            data-active={String(player.active)}
            data-mark-recall={String(player.isMarkRecall)}
            data-caption={player.caption}
            data-mark-missing={String(player.markMissing)}
            data-mark-detached={String(player.markDetached)}
            data-perf={player.markPerformance || ''}
        />
    );
}
async function mount(store) {
    await act(async () => { root.render(<Probe store={store} />); });
}
const box = () => container.firstChild;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // settle immediately — no animation frames to chase
    window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} });
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); seen = null; });

describe('useRecallPlayer — recall.markId performs the mark', () => {
    it('performs a committed mark: mark recall, its caption, its bloom', async () => {
        const m = brush();
        await mount(STORE({ markId: m.id, startedAt: 1 }, [m]));
        expect(box().getAttribute('data-active')).toBe('true');
        expect(box().getAttribute('data-mark-recall')).toBe('true');
        expect(box().getAttribute('data-perf')).toBe('bloom');
        // the mark speaks its own label as the caption
        expect(box().getAttribute('data-caption')).toBe('the falling light');
        // and progress is available on the mark channel
        expect(seen.progressForMark(m.id)).toBeGreaterThan(0);
    });

    it('says markMissing when the cited mark is gone — no perform over nothing', async () => {
        await mount(STORE({ markId: 'vm_gone', startedAt: 1 }, []));
        expect(box().getAttribute('data-mark-missing')).toBe('true');
        expect(box().getAttribute('data-active')).toBe('false');
    });

    it('detaches honestly when a region_mask outlives its region', async () => {
        const rm = makeVisualMark('region_mask', {
            source: 'user', status: 'committed',
            geometry: { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 0 } },
            label: 'segmented head',
        }, { now: 't' });
        // no regions in the store → the mask's region is gone
        await mount(STORE({ markId: rm.id, startedAt: 1 }, [rm], { regions: [] }));
        expect(box().getAttribute('data-mark-detached')).toBe('true');
        expect(seen.markNote).toMatch(/Detached mark/);
    });

    it('a null recall is inert (no percept, no mark)', async () => {
        await mount(STORE(null, [brush()]));
        expect(box().getAttribute('data-active')).toBe('false');
        expect(box().getAttribute('data-mark-recall')).toBe('false');
    });
});
