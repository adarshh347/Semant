import React, { act, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import useImageViewport from './useImageViewport';
import ViewportBar from './ViewportBar';
import InstrumentExtent from './InstrumentExtent';
import { BRUSH_RANGE, BRUSH_PRESETS, BAND_RANGE, valueToPosition } from './instrumentScale';
import { contentBox } from './useStageGeometry';
import { FIT_VIEW, clientToNormalized } from './imageViewport';

/**
 * The workbench as a curator meets it: does a navigation gesture ever paint, does
 * an authoring gesture ever move the plane, and do the layers stay registered.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // jsdom has no layout: every element measures 0×0, so the hook would never see
    // a viewport. Give the stage a real box.
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function () {
        if (this.classList?.contains('stage')) {
            return { left: 40, top: 25, width: 800, height: 600, right: 840, bottom: 625, x: 40, y: 25 };
        }
        return { left: 0, top: 0, width: 0, height: 0, right: 0, bottom: 0, x: 0, y: 0 };
    });
    window.ResizeObserver = class { observe() {} disconnect() {} unobserve() {} };
    window.requestAnimationFrame = (cb) => { cb(); return 1; };
    window.cancelAnimationFrame = () => {};
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

const NAT = { w: 2000, h: 1000 };
const CONTENT = contentBox(800, 600, NAT.w, NAT.h);   // 800×400 at y=100

const pointer = (type, init) => new window.PointerEvent(type, {
    bubbles: true, cancelable: true, pointerId: 1, button: 0, ...init,
});

/**
 * A miniature of the workspace's stage: the same arbitration order (navigation
 * first, then the tool), the same plane, the same conversion path.
 */
function Stage({ onPaint = () => {}, tool = 'brush' }) {
    const stageRef = useRef(null);
    const vp = useImageViewport(stageRef, { content: CONTENT });
    return (
        <>
            <ViewportBar
                label={vp.label} atFit={vp.atFit}
                canZoomIn={vp.canZoomIn} canZoomOut={vp.canZoomOut}
                onZoomIn={vp.zoomIn} onZoomOut={vp.zoomOut} onFit={vp.fit}
                naturalAvailable={!!vp.naturalScale(NAT)}
                onNatural={() => vp.zoomTo(vp.naturalScale(NAT))}
                handTool={vp.handTool} onToggleHand={() => vp.setHandTool((h) => !h)}
            />
            <div
                ref={stageRef}
                className={`stage diff-stage${vp.navigating ? ' is-navigable' : ''}${vp.panning ? ' is-panning' : ''}`}
                onPointerDown={(e) => {
                    if (vp.beginPan(e)) return;
                    const p = vp.clientToNormalized(e.clientX, e.clientY);
                    if (p && tool === 'brush') onPaint(p);
                }}
                onPointerMove={(e) => {
                    if (vp.movePan(e)) return;
                    const p = vp.clientToNormalized(e.clientX, e.clientY);
                    if (p && tool === 'brush' && e.buttons) onPaint(p);
                }}
                onPointerUp={() => { if (vp.endPan()) return; }}
            >
                <div className="diff-plane" style={{ transform: vp.transform }}>
                    <img alt="" />
                </div>
            </div>
            <span className="probe-transform">{vp.transform}</span>
            <span className="probe-scale">{String(vp.view.scale)}</span>
            <span className="probe-pan">{`${vp.view.x},${vp.view.y}`}</span>
        </>
    );
}

const stageEl = () => container.querySelector('.stage');
const plane = () => container.querySelector('.diff-plane');
const scale = () => Number(container.querySelector('.probe-scale').textContent);
const pan = () => container.querySelector('.probe-pan').textContent;
const btn = (label) => [...container.querySelectorAll('button')]
    .find((b) => b.getAttribute('aria-label') === label);

const fire = async (el, ev) => { await act(async () => { el.dispatchEvent(ev); }); };
const key = async (type, init) => {
    await act(async () => { window.dispatchEvent(new window.KeyboardEvent(type, { bubbles: true, ...init })); });
};

describe('one plane, one transform', () => {
    it('puts every spatial layer inside a single transformed plane', async () => {
        await mount(<Stage />);
        expect(plane()).not.toBeNull();
        expect(plane().contains(container.querySelector('img'))).toBe(true);
        // Exactly one transformed box — a second is how drift enters.
        expect(container.querySelectorAll('.diff-plane')).toHaveLength(1);
    });

    it('is identity-shaped at fit, so an unzoomed stage is untouched', async () => {
        await mount(<Stage />);
        expect(plane().style.transform).toBe('translate(0px, 0px) scale(1)');
    });

    it('moves the plane, never the stage', async () => {
        await mount(<Stage />);
        await act(async () => { btn('Zoom in').click(); });
        expect(plane().style.transform).toContain('scale(1.4)');
        expect(stageEl().style.transform).toBe('');
    });
});

describe('navigation never paints', () => {
    it('Space-drag pans and lays down no point', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} />);
        await act(async () => { btn('Zoom in').click(); });   // pannable
        await key('keydown', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        await fire(stageEl(), pointer('pointermove', { clientX: 460, clientY: 330, buttons: 1 }));
        await fire(stageEl(), pointer('pointerup', { clientX: 460, clientY: 330 }));
        expect(onPaint).not.toHaveBeenCalled();
        expect(pan()).not.toBe('0,0');
    });

    it('middle-button drag pans and lays down no point', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} />);
        await act(async () => { btn('Zoom in').click(); });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300, button: 1 }));
        await fire(stageEl(), pointer('pointermove', { clientX: 500, clientY: 300, buttons: 4 }));
        await fire(stageEl(), pointer('pointerup', { clientX: 500, clientY: 300, button: 1 }));
        expect(onPaint).not.toHaveBeenCalled();
        expect(pan()).not.toBe('0,0');
    });

    it('the latched Hand tool pans without abandoning the brush', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} />);
        await act(async () => { btn('Zoom in').click(); });
        await act(async () => { btn('Hand tool — drag to pan').click(); });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        await fire(stageEl(), pointer('pointermove', { clientX: 470, clientY: 300, buttons: 1 }));
        expect(onPaint).not.toHaveBeenCalled();
    });

    it('H latches and unlatches the Hand', async () => {
        await mount(<Stage />);
        expect(btn('Hand tool — drag to pan').getAttribute('aria-pressed')).toBe('false');
        await key('keydown', { key: 'h' });
        expect(btn('Hand tool — drag to pan').getAttribute('aria-pressed')).toBe('true');
        await key('keydown', { key: 'h' });
        expect(btn('Hand tool — drag to pan').getAttribute('aria-pressed')).toBe('false');
    });
});

describe('authoring never moves the plane', () => {
    it('a primary drag paints and leaves the pan untouched', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} />);
        await act(async () => { btn('Zoom in').click(); });
        const before = pan();
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        await fire(stageEl(), pointer('pointermove', { clientX: 460, clientY: 330, buttons: 1 }));
        expect(onPaint).toHaveBeenCalled();
        expect(pan()).toBe(before);
    });
});

describe('releasing Space returns the tool at once', () => {
    it('ends the pan and paints again on the next press', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} />);
        await act(async () => { btn('Zoom in').click(); });
        await key('keydown', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        await key('keyup', { code: 'Space', key: ' ' });
        expect(stageEl().className).not.toContain('is-navigable');
        onPaint.mockClear();
        await fire(stageEl(), pointer('pointerdown', { clientX: 420, clientY: 310 }));
        expect(onPaint).toHaveBeenCalled();
    });

    it('never mutates the tool — panning is a modifier, not a mode switch', async () => {
        const onPaint = vi.fn();
        await mount(<Stage onPaint={onPaint} tool="brush" />);
        await key('keydown', { code: 'Space', key: ' ' });
        await key('keyup', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        expect(onPaint).toHaveBeenCalledTimes(1);
    });
});

describe('coalescing must not lose the end of a gesture', () => {
    // Pan moves are coalesced onto an animation frame for performance. If the
    // gesture ends before that frame runs — a fast flick, or a throttled tab —
    // cancelling the frame would drop every move since the last one and settle the
    // plane behind where the hand left it. `endPan` flushes instead.
    it('applies the final move even when no frame ran', async () => {
        const frames = [];
        window.requestAnimationFrame = (cb) => { frames.push(cb); return frames.length; };
        window.cancelAnimationFrame = () => {};
        await mount(<Stage />);
        await act(async () => { btn('Zoom in').click(); });
        await key('keydown', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        const before = pan();
        // Two moves, and deliberately NO frame is allowed to run.
        await fire(stageEl(), pointer('pointermove', { clientX: 450, clientY: 300, buttons: 1 }));
        await fire(stageEl(), pointer('pointermove', { clientX: 500, clientY: 300, buttons: 1 }));
        expect(pan()).toBe(before);
        await fire(stageEl(), pointer('pointerup', { clientX: 500, clientY: 300 }));
        expect(pan()).not.toBe(before);
    });
});

describe('a lost pointer cannot leave the plane stuck to the cursor', () => {
    it('a window pointercancel ends the pan', async () => {
        await mount(<Stage />);
        await act(async () => { btn('Zoom in').click(); });
        await key('keydown', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        expect(stageEl().className).toContain('is-panning');
        await act(async () => { window.dispatchEvent(new window.Event('pointercancel')); });
        expect(stageEl().className).not.toContain('is-panning');
    });

    it('a window blur ends the pan', async () => {
        await mount(<Stage />);
        await act(async () => { btn('Zoom in').click(); });
        await key('keydown', { code: 'Space', key: ' ' });
        await fire(stageEl(), pointer('pointerdown', { clientX: 400, clientY: 300 }));
        await act(async () => { window.dispatchEvent(new window.Event('blur')); });
        expect(stageEl().className).not.toContain('is-panning');
    });
});

describe('coordinates are invariant to the view', () => {
    // The load-bearing claim: a mark drawn at 4× persists what it would have
    // persisted at fit. The view changes access to pixels, never the evidence.
    it('the same image point is reported from the client point that shows it', async () => {
        const painted = [];
        await mount(<Stage onPaint={(p) => painted.push(p)} />);
        await fire(stageEl(), pointer('pointerdown', { clientX: 440, clientY: 325 }));
        const atFit = painted.at(-1);

        // Zoom about that very point; the pixel stays under the cursor, so pressing
        // the same client point must report the same normalized coordinates.
        await act(async () => { btn('Zoom in').click(); });
        await act(async () => { btn('Zoom in').click(); });
        expect(scale()).toBeGreaterThan(1);
        await fire(stageEl(), pointer('pointerdown', { clientX: 440, clientY: 325 }));
        const zoomed = painted.at(-1);

        // The stage's client rect is offset (left 40, top 25), so client (440,325)
        // is viewport-local (400,300) — the centre the zoom buttons anchor on. The
        // pixel there is the same pixel before and after.
        const centreAtFit = clientToNormalized(
            440, 325, { left: 40, top: 25, width: 800, height: 600 }, FIT_VIEW, CONTENT,
        );
        expect(centreAtFit).toEqual({ x: 0.5, y: 0.5 });
        expect(atFit.x).toBeCloseTo(centreAtFit.x, 6);
        expect(zoomed.x).toBeCloseTo(centreAtFit.x, 6);
        expect(zoomed.y).toBeCloseTo(centreAtFit.y, 6);
    });
});

describe('the viewport bar', () => {
    it('reads "Fit" until the curator leaves it', async () => {
        await mount(<Stage />);
        expect(container.querySelector('.diff-vp-scale').textContent).toContain('Fit');
        await act(async () => { btn('Zoom in').click(); });
        expect(container.querySelector('.diff-vp-scale').textContent).toContain('140%');
    });

    it('announces the zoom politely rather than assertively', async () => {
        await mount(<Stage />);
        const live = container.querySelector('.diff-vp-scale');
        expect(live.getAttribute('aria-live')).toBe('polite');
    });

    it('disables Fit when already fitted, and zoom-out at the floor', async () => {
        await mount(<Stage />);
        const fitBtn = btn('Fit the whole image');
        expect(fitBtn.disabled).toBe(true);
        expect(btn('Zoom out').disabled).toBe(true);
        await act(async () => { btn('Zoom in').click(); });
        expect(btn('Fit the whole image').disabled).toBe(false);
    });

    it('returns to fit without touching anything else', async () => {
        await mount(<Stage />);
        await act(async () => { btn('Zoom in').click(); });
        await act(async () => { btn('Fit the whole image').click(); });
        expect(scale()).toBe(1);
        expect(pan()).toBe('0,0');
    });

    it('offers 100% only when 1:1 is a real destination', async () => {
        await mount(<Stage />);
        // 2000px natural painted 800px wide → 1:1 at 2.5×, so it is offered.
        expect(btn('Zoom to natural pixel size')).toBeTruthy();
        await act(async () => { btn('Zoom to natural pixel size').click(); });
        expect(scale()).toBeCloseTo(2.5, 6);
    });

    it('every control carries a name', async () => {
        await mount(<Stage />);
        for (const b of container.querySelectorAll('.diff-viewport-bar button')) {
            expect(b.getAttribute('aria-label')).toBeTruthy();
        }
    });
});

describe('the extent control', () => {
    function Harness({ initial = 0.045, range = BRUSH_RANGE, presets = BRUSH_PRESETS, label = 'Size' }) {
        const [v, setV] = React.useState(initial);
        return (
            <>
                <InstrumentExtent label={label} value={v} onChange={setV} range={range} presets={presets} />
                <span className="probe-v">{String(v)}</span>
            </>
        );
    }
    const val = () => Number(container.querySelector('.probe-v').textContent);
    const slider = () => container.querySelector('.diff-extent-slider');

    it('shows the value as a percentage of image width', async () => {
        await mount(<Harness />);
        expect(container.querySelector('.diff-extent-value').textContent).toBe('4.5%');
    });

    it('tells a screen reader the real extent, not the track position', async () => {
        await mount(<Harness />);
        expect(slider().getAttribute('aria-valuetext')).toBe('4.5% of image width');
        // The raw value is a 0..1 position, which would be meaningless read aloud.
        expect(slider().value).toBe(String(valueToPosition(0.045, BRUSH_RANGE)));
    });

    it('steps by the same factor as the bracket keys', async () => {
        await mount(<Harness />);
        await act(async () => { btn('Increase size').click(); });
        expect(val()).toBeCloseTo(0.045 * 1.22, 12);
        await act(async () => { btn('Decrease size').click(); });
        // Not exactly back to 0.045: 1.22 × 0.82 = 1.0004. That asymmetry is
        // inherited verbatim from the bracket keys — the point of sharing one step
        // helper is that the buttons drift exactly as the keys always have, rather
        // than the two controls disagreeing about where the value ended up.
        expect(val()).toBeCloseTo(0.045, 4);
        expect(val()).toBe(0.045 * 1.22 * 0.82);
    });

    it('disables its buttons at the ends of the range', async () => {
        await mount(<Harness initial={BRUSH_RANGE.min} />);
        expect(btn('Decrease size').disabled).toBe(true);
        expect(btn('Increase size').disabled).toBe(false);
    });

    it('offers presets that set ordinary values', async () => {
        await mount(<Harness />);
        const fine = [...container.querySelectorAll('.diff-extent-preset')].find((b) => b.textContent === 'Fine');
        await act(async () => { fine.click(); });
        expect(val()).toBe(0.018);
        expect(fine.getAttribute('aria-pressed')).toBe('true');
    });

    it('shows a neutral swatch for keyboard users, sized by the extent', async () => {
        // `key` forces a fresh instance: re-rendering the same component type would
        // keep its existing state and silently compare a value against itself.
        await mount(<Harness key="min" initial={BRUSH_RANGE.min} />);
        const small = parseInt(container.querySelector('.diff-extent-swatch').style.width, 10);
        await mount(<Harness key="max" initial={BRUSH_RANGE.max} />);
        const big = parseInt(container.querySelector('.diff-extent-swatch').style.width, 10);
        expect(big).toBeGreaterThan(small);
        expect(small).toBeGreaterThanOrEqual(4);   // the finest setting is still visible
    });

    it('serves the boundary band with the same instrument and no presets', async () => {
        await mount(<Harness initial={0.06} range={BAND_RANGE} presets={null} label="Band width" />);
        expect(container.querySelector('.diff-extent-label').textContent).toBe('Band width');
        expect(container.querySelector('.diff-extent-presets')).toBeNull();
        expect(slider().getAttribute('aria-valuetext')).toBe('6.0% of image width');
    });

    it('offers no free-form decimal entry', async () => {
        await mount(<Harness />);
        expect(container.querySelector('input[type="number"]')).toBeNull();
        expect(container.querySelector('input[type="text"]')).toBeNull();
    });
});
