import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import InstrumentHandles from './InstrumentHandles';
import {
    acceptSuggestion, dismissSuggestion, quarantineSuggestion, isSuggestion, canCiteMark,
} from './suggestionQuarantine';
import { makeVisualMark } from './visualMarks';

/**
 * CIRCUIT-001 P2E-B — the editable-anchor overlay, and the suggestion quarantine
 * flow, proven on the real Lane A modules.
 *
 * The overlay is the interaction surface: it turns pointer gestures on handles
 * into calls back to the workspace. The point math is `handleEditing.js` (node
 * suite); here we prove the DOM wiring — a handle grabs, a drag emits normalized
 * coords, a midpoint inserts, a right-click removes, and a locked layer is inert.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const NAT = { w: 1000, h: 1000 };   // square: normalized == viewBox px / 1000
// The overlay injects the converter; with a square image and a 1000-px viewBox,
// a client point maps to itself/1000. We fake it directly, since jsdom has no layout.
const clientToNormalized = (cx, cy) => ({ x: cx / 1000, y: cy / 1000 });

const points = [[0.2, 0.2], [0.5, 0.5], [0.8, 0.2]];

function handles() { return [...container.querySelectorAll('.ih-handle')]; }
function mids() { return [...container.querySelectorAll('.ih-mid')]; }

describe('InstrumentHandles — the editable-anchor overlay', () => {
    it('renders one handle per point and one midpoint per segment', async () => {
        await mount(<InstrumentHandles natural={NAT} points={points}
            clientToNormalized={clientToNormalized} onMove={() => {}} onInsert={() => {}} onRemove={() => {}} />);
        expect(handles()).toHaveLength(3);
        expect(mids()).toHaveLength(2);
        // handle centres land at natural-pixel positions of the normalized points
        expect(handles()[2].getAttribute('cx')).toBe('800');
        expect(handles()[2].getAttribute('cy')).toBe('200');
    });

    it('grabbing a handle and dragging emits normalized coords via onMove', async () => {
        const onMove = vi.fn();
        await mount(<InstrumentHandles natural={NAT} points={points}
            clientToNormalized={clientToNormalized} onMove={onMove} onInsert={() => {}} onRemove={() => {}} />);
        await act(async () => {
            handles()[2].dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 800, clientY: 200 }));
            window.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: 900, clientY: 100 }));
            window.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
        });
        expect(onMove).toHaveBeenCalledWith(2, [0.9, 0.1]);
        // after pointerup the drag is released — a further move does nothing
        onMove.mockClear();
        await act(async () => { window.dispatchEvent(new PointerEvent('pointermove', { clientX: 100, clientY: 100 })); });
        expect(onMove).not.toHaveBeenCalled();
    });

    it('clicking a midpoint inserts a vertex on that segment', async () => {
        const onInsert = vi.fn(() => 1);
        await mount(<InstrumentHandles natural={NAT} points={points}
            clientToNormalized={clientToNormalized} onMove={() => {}} onInsert={onInsert} onRemove={() => {}} />);
        await act(async () => {
            mids()[0].dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 350, clientY: 350 }));
        });
        expect(onInsert).toHaveBeenCalledWith(0, [0.35, 0.35], 0.5);
    });

    it('right-clicking a handle removes it', async () => {
        const onRemove = vi.fn();
        await mount(<InstrumentHandles natural={NAT} points={points}
            clientToNormalized={clientToNormalized} onMove={() => {}} onInsert={() => {}} onRemove={onRemove} />);
        await act(async () => {
            handles()[1].dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
        });
        expect(onRemove).toHaveBeenCalledWith(1);
    });

    it('a locked layer makes handles inert: no move, no insert, no remove', async () => {
        const onMove = vi.fn(); const onInsert = vi.fn(); const onRemove = vi.fn();
        await mount(<InstrumentHandles natural={NAT} points={points} locked
            clientToNormalized={clientToNormalized} onMove={onMove} onInsert={onInsert} onRemove={onRemove} />);
        expect(mids()).toHaveLength(0);                       // no insert hints when locked
        await act(async () => {
            handles()[0].dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: 200, clientY: 200 }));
            window.dispatchEvent(new PointerEvent('pointermove', { clientX: 500, clientY: 500 }));
            handles()[0].dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
        });
        expect(onMove).not.toHaveBeenCalled();
        expect(onRemove).not.toHaveBeenCalled();
    });
});

describe('suggestion quarantine flow, exactly as the workspace drives it', () => {
    const brushSuggestion = () => quarantineSuggestion(makeVisualMark('brush_field', {
        role: 'gaze_field', label: 'a field the model proposes', source: 'model_suggested',
        geometry: { kind: 'freehand_path', strokes: [{ points: [[0.5, 0.3, 0.6], [0.6, 0.4, 0.9]], radius: 0.06, strength: 0.7, op: 'add' }] },
    }, { now: 'T' }));

    const pending = (marks) => marks.filter((m) => (
        isSuggestion(m) && m.status !== 'dismissed' && !marks.some((x) => x.derived_from === m.id)
    ));

    it('a suggestion is pending, uncitable, and not counted', () => {
        const s = brushSuggestion();
        expect(isSuggestion(s)).toBe(true);
        expect(canCiteMark(s)).toBe(false);
        expect(pending([s])).toHaveLength(1);
    });

    it('Accept mints a user_confirmed mark with derived_from; the suggestion leaves the queue', () => {
        const s = brushSuggestion();
        const { accepted, suggestion } = acceptSuggestion(s);
        expect(accepted.source).toBe('user_confirmed');
        expect(accepted.status).toBe('committed');
        expect(accepted.derived_from).toBe(s.id);
        expect(canCiteMark(accepted)).toBe(true);
        expect(suggestion).toBe(s);                           // untouched (Label Studio rule)
        // the workspace keeps both; the pending filter drops the suggestion once a descendant exists
        const marks = [s, accepted];
        expect(pending(marks)).toHaveLength(0);
    });

    it('Dismiss removes it from the queue and it never becomes citable', () => {
        const s = brushSuggestion();
        const dismissed = dismissSuggestion(s);
        expect(dismissed.status).toBe('dismissed');
        expect(canCiteMark(dismissed)).toBe(false);
        expect(pending([dismissed])).toHaveLength(0);
    });
});
