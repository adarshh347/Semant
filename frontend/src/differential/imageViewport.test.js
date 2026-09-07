import { describe, it, expect } from 'vitest';
import {
    MIN_SCALE, MAX_SCALE, FIT_VIEW, ZOOM_STEP,
    clampScale, isFit, clampPan, zoomAbout, panBy, panTo,
    viewportToPlane, planeToViewport, planeToNormalized, normalizedToPlane,
    clientToNormalized, normalizedToClient,
    naturalScale, viewForBounds, visibleBounds, planeTransform, zoomLabel,
    panLimits, isPanClamped,
} from './imageViewport';
import { contentBox, pointerToNormalized } from './useStageGeometry';

// A landscape plate letterboxed into a taller viewport, and a portrait one into a
// wider viewport — the two cases where the painted image and the container differ.
const VP_L = { w: 800, h: 600 };
const NAT_L = { w: 2000, h: 1000 };
const BOX_L = contentBox(VP_L.w, VP_L.h, NAT_L.w, NAT_L.h);   // 800×400, y offset 100

const VP_P = { w: 800, h: 600 };
const NAT_P = { w: 1000, h: 2000 };
const BOX_P = contentBox(VP_P.w, VP_P.h, NAT_P.w, NAT_P.h);   // 300×600, x offset 250

const rect = (vp) => ({ left: 40, top: 25, width: vp.w, height: vp.h });
const view = (scale, x = 0, y = 0) => ({ scale, x, y, mode: scale === 1 && !x && !y ? 'fit' : 'free' });

describe('the fit box these tests rest on', () => {
    it('letterboxes landscape and portrait as the existing contract does', () => {
        expect(BOX_L).toEqual({ x: 0, y: 100, w: 800, h: 400 });
        expect(BOX_P).toEqual({ x: 250, y: 0, w: 300, h: 600 });
    });
});

describe('scale limits', () => {
    it('clamps to the declared range', () => {
        expect(clampScale(0.1)).toBe(MIN_SCALE);
        expect(clampScale(99)).toBe(MAX_SCALE);
        expect(clampScale(2.5)).toBe(2.5);
    });

    it('never zooms out past fit — the whole image is the floor', () => {
        expect(MIN_SCALE).toBe(1);
        expect(zoomAbout(FIT_VIEW, 0.4, null, VP_L, BOX_L).scale).toBe(1);
    });

    it('recognises the fit view, and only the fit view', () => {
        expect(isFit(FIT_VIEW)).toBe(true);
        expect(isFit(view(1, 5, 0))).toBe(false);
        expect(isFit(view(1.2))).toBe(false);
    });
});

describe('the two directions are exact inverses', () => {
    const cases = [
        ['fit', view(1)],
        ['zoomed, centred', view(3)],
        ['zoomed and panned', view(2.5, -120, 60)],
        ['max zoom', view(MAX_SCALE, 40, -40)],
    ];

    for (const [name, v] of cases) {
        it(`viewport↔plane round-trips at ${name}`, () => {
            for (const q of [{ x: 0, y: 0 }, { x: 400, y: 300 }, { x: 799, y: 599 }, { x: 123, y: 456 }]) {
                const back = planeToViewport(viewportToPlane(q, v, VP_L), v, VP_L);
                expect(back.x).toBeCloseTo(q.x, 9);
                expect(back.y).toBeCloseTo(q.y, 9);
            }
        });

        it(`client↔normalized round-trips at ${name}`, () => {
            const r = rect(VP_L);
            for (const pt of [{ x: 0.1, y: 0.2 }, { x: 0.5, y: 0.5 }, { x: 0.87, y: 0.34 }]) {
                const c = normalizedToClient(pt, r, v, BOX_L);
                const back = clientToNormalized(c.x, c.y, r, v, BOX_L);
                expect(back.x).toBeCloseTo(pt.x, 9);
                expect(back.y).toBeCloseTo(pt.y, 9);
            }
        });
    }

    it('plane↔normalized round-trips independent of the view', () => {
        for (const pt of [{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 0.33, y: 0.77 }]) {
            const back = planeToNormalized(normalizedToPlane(pt, BOX_L), BOX_L);
            expect(back.x).toBeCloseTo(pt.x, 9);
            expect(back.y).toBeCloseTo(pt.y, 9);
        }
    });
});

describe('at fit it is arithmetically the existing contract', () => {
    // This is what makes the new path safe to adopt unconditionally: nothing about
    // an unzoomed stage changes when the viewport is introduced.
    it('agrees with pointerToNormalized for landscape', () => {
        const r = rect(VP_L);
        const stageEl = { getBoundingClientRect: () => r };
        for (const [cx, cy] of [[40, 125], [440, 325], [500, 200], [839, 524]]) {
            const old = pointerToNormalized({ clientX: cx, clientY: cy }, stageEl, BOX_L);
            const now = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_L);
            expect(now.x).toBeCloseTo(old.x, 12);
            expect(now.y).toBeCloseTo(old.y, 12);
        }
    });

    it('agrees with pointerToNormalized for portrait', () => {
        const r = rect(VP_P);
        const stageEl = { getBoundingClientRect: () => r };
        for (const [cx, cy] of [[290, 25], [440, 325], [700, 400]]) {
            const old = pointerToNormalized({ clientX: cx, clientY: cy }, stageEl, BOX_P);
            const now = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_P);
            expect(now.x).toBeCloseTo(old.x, 12);
            expect(now.y).toBeCloseTo(old.y, 12);
        }
    });

    it('clamps out-of-image pointers to [0,1] like the old path, and reports raw when asked', () => {
        const r = rect(VP_L);
        expect(clientToNormalized(0, 0, r, FIT_VIEW, BOX_L)).toEqual({ x: 0, y: 0 });
        const raw = clientToNormalized(0, 0, r, FIT_VIEW, BOX_L, { clamp: false });
        expect(raw.y).toBeLessThan(0);   // above the letterboxed image
    });
});

describe('pointer-anchored zoom keeps the pixel under the cursor', () => {
    /**
     * THE PHASE-0 INVARIANT, stated as it actually holds.
     *
     * "The pixel stays under the cursor" and "pan can never lose the image" are not
     * jointly satisfiable near an edge — honouring the anchor there would require
     * showing pixels the image does not have. So on each axis EITHER the normalized
     * point is preserved, OR the pan is pressed against its limit on that axis and
     * the image edge was held instead. Asserting only the first half would be a
     * guard that passes by looking away from the interesting case.
     */
    const expectAnchored = (before, after, v, axis, key) => {
        if (isPanClamped(v, axis, VP_L, BOX_L)) {
            expect(panLimits(v.scale, VP_L, BOX_L)[axis]).toBeGreaterThanOrEqual(0);
        } else {
            expect(after[key]).toBeCloseTo(before[key], 6);
        }
    };

    const anchors = [[440, 325], [100, 150], [760, 500], [400, 300]];

    for (const [cx, cy] of anchors) {
        it(`holds for an anchor at (${cx}, ${cy})`, () => {
            const r = rect(VP_L);
            const before = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_L);
            const anchor = { x: cx - r.left, y: cy - r.top };
            const v = zoomAbout(FIT_VIEW, 3, anchor, VP_L, BOX_L);
            const after = clientToNormalized(cx, cy, r, v, BOX_L);
            expectAnchored(before, after, v, 'x', 'x');
            expectAnchored(before, after, v, 'y', 'y');
        });
    }

    it('holds exactly, on both axes, for an anchor away from the edges', () => {
        // The unclamped case, asserted with no escape hatch.
        const r = rect(VP_L);
        const [cx, cy] = [440, 325];
        const before = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_L);
        const v = zoomAbout(FIT_VIEW, 3, { x: cx - r.left, y: cy - r.top }, VP_L, BOX_L);
        expect(isPanClamped(v, 'x', VP_L, BOX_L)).toBe(false);
        const after = clientToNormalized(cx, cy, r, v, BOX_L);
        expect(after.x).toBeCloseTo(before.x, 6);
    });

    it('holds across a chain of zooms, as a wheel gesture produces', () => {
        // A wheel gesture is a CHAIN: each notch starts from the pan the last one
        // left. This is the case that distinguishes the correct compensation
        // (`d(1-k) + t·k`) from the shorter `d(1-k) + t`, which is exact only when
        // the view was unpanned and drifts a little on every notch after.
        //
        // CLAMPING IS NOT REVERSIBLE, and that is why `everClamped` tracks the whole
        // chain rather than the final view. A 400px-tall plate in a 600px viewport
        // cannot pan vertically at all below 1.5×, so y is pinned for the first
        // notches; by the end the pan is interior again, but the anchor it lost
        // while pinned does not come back. Checking only the final state would call
        // that a defect.
        const r = rect(VP_L);
        const [cx, cy] = [520, 260];
        const before = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_L);
        const anchor = { x: cx - r.left, y: cy - r.top };
        let v = FIT_VIEW;
        const everClamped = { x: false, y: false };
        for (let i = 0; i < 8; i++) {
            v = zoomAbout(v, v.scale * 1.15, anchor, VP_L, BOX_L);
            for (const axis of ['x', 'y']) {
                if (isPanClamped(v, axis, VP_L, BOX_L)) everClamped[axis] = true;
            }
        }
        const after = clientToNormalized(cx, cy, r, v, BOX_L);
        expect(v.scale).toBeGreaterThan(2);
        // x is never pinned on this plate, so it must be exact — this is the half
        // that fails against the uncorrected formula.
        expect(everClamped.x).toBe(false);
        expect(after.x).toBeCloseTo(before.x, 6);
        expect(everClamped.y).toBe(true);
    });

    it('a horizontally-pannable plate holds BOTH axes across a chain', () => {
        // The portrait plate can pan vertically from the start, so nothing is pinned
        // and the chain must be exact on both axes.
        const r = rect(VP_P);
        const [cx, cy] = [440, 325];
        const before = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_P);
        const anchor = { x: cx - r.left, y: cy - r.top };
        let v = FIT_VIEW;
        for (let i = 0; i < 6; i++) v = zoomAbout(v, v.scale * 1.2, anchor, VP_P, BOX_P);
        expect(isPanClamped(v, 'y', VP_P, BOX_P)).toBe(false);
        const after = clientToNormalized(cx, cy, r, v, BOX_P);
        expect(after.y).toBeCloseTo(before.y, 6);
    });

    it('zoom, pan, then zoom again — the second zoom respects the pan it inherits', () => {
        // The direct regression for the missing `t·k` term.
        const r = rect(VP_L);
        const anchor = { x: 400, y: 300 };
        let v = zoomAbout(FIT_VIEW, 3, anchor, VP_L, BOX_L);
        v = panBy(v, -150, 40, VP_L, BOX_L);
        expect(v.x).not.toBe(0);
        const [cx, cy] = [600, 320];
        const before = clientToNormalized(cx, cy, r, v, BOX_L);
        v = zoomAbout(v, 4.2, { x: cx - r.left, y: cy - r.top }, VP_L, BOX_L);
        const after = clientToNormalized(cx, cy, r, v, BOX_L);
        expectAnchored(before, after, v, 'x', 'x');
        expectAnchored(before, after, v, 'y', 'y');
    });

    it('holds zooming back out again', () => {
        const r = rect(VP_L);
        const [cx, cy] = [300, 400];
        const anchor = { x: cx - r.left, y: cy - r.top };
        let v = zoomAbout(FIT_VIEW, 5, anchor, VP_L, BOX_L);
        const at5 = clientToNormalized(cx, cy, r, v, BOX_L);
        v = zoomAbout(v, 2, anchor, VP_L, BOX_L);
        const at2 = clientToNormalized(cx, cy, r, v, BOX_L);
        expectAnchored(at5, at2, v, 'x', 'x');
        expectAnchored(at5, at2, v, 'y', 'y');
    });

    it('substitutes the edge ONLY where the clamp binds, never silently elsewhere', () => {
        // An anchor high in a letterboxed landscape plate: the vertical pan wants
        // more than the image can give, so y is held at the limit while x is honoured.
        const r = rect(VP_L);
        const [cx, cy] = [100, 150];
        const before = clientToNormalized(cx, cy, r, FIT_VIEW, BOX_L);
        const v = zoomAbout(FIT_VIEW, 3, { x: cx - r.left, y: cy - r.top }, VP_L, BOX_L);
        expect(isPanClamped(v, 'y', VP_L, BOX_L)).toBe(true);
        expect(isPanClamped(v, 'x', VP_L, BOX_L)).toBe(false);
        const after = clientToNormalized(cx, cy, r, v, BOX_L);
        expect(after.x).toBeCloseTo(before.x, 6);          // honoured
        expect(after.y).not.toBeCloseTo(before.y, 6);      // edge held instead
        expect(v.y).toBe(panLimits(3, VP_L, BOX_L).y);
    });

    it('is a no-op at the scale ceiling rather than drifting the pan', () => {
        const v = zoomAbout(FIT_VIEW, MAX_SCALE, { x: 100, y: 100 }, VP_L, BOX_L);
        expect(zoomAbout(v, MAX_SCALE * 2, { x: 700, y: 20 }, VP_L, BOX_L)).toBe(v);
    });
});

describe('pan can never lose the image', () => {
    it('permits no pan at all at fit scale', () => {
        expect(clampPan(500, 500, 1, VP_L, BOX_L)).toEqual({ x: 0, y: 0 });
        expect(panBy(FIT_VIEW, 300, -200, VP_L, BOX_L)).toMatchObject({ x: 0, y: 0 });
    });

    it('keeps a portrait image from sliding into its own letterbox', () => {
        // 300px wide painted in an 800px viewport: at 2× it is 600px, still narrower.
        expect(clampPan(999, 0, 2, VP_P, BOX_P).x).toBe(0);
        // Only past 800/300 ≈ 2.67 does sideways pan become possible.
        expect(clampPan(999, 0, 4, VP_P, BOX_P).x).toBeGreaterThan(0);
    });

    it('bounds against the painted image, not the container', () => {
        // Landscape: 400px tall painted in a 600px viewport. At 2× it is 800px, so
        // vertical pan is allowed to (800-600)/2 = 100 — not to the container's half.
        expect(clampPan(0, 999, 2, VP_L, BOX_L).y).toBe(100);
        expect(clampPan(0, -999, 2, VP_L, BOX_L).y).toBe(-100);
    });

    it('always keeps some image inside the viewport, at every scale and extreme drag', () => {
        for (const s of [1, 1.5, 2, 4, MAX_SCALE]) {
            for (const [dx, dy] of [[9e5, 9e5], [-9e5, -9e5], [9e5, -9e5]]) {
                const v = panTo(view(s), dx, dy, VP_L, BOX_L);
                const vis = visibleBounds(v, VP_L, BOX_L);
                expect(vis.w).toBeGreaterThan(0);
                expect(vis.h).toBeGreaterThan(0);
            }
        }
    });

    it('re-clamps when zooming out, so a pan legal at 4× cannot survive to fit', () => {
        const zoomed = panTo(view(4), 9e5, 9e5, VP_L, BOX_L);
        expect(zoomed.x).toBeGreaterThan(0);
        const out = zoomAbout(zoomed, 1, null, VP_L, BOX_L);
        expect(out).toMatchObject({ x: 0, y: 0, scale: 1 });
    });
});

describe('mode reports how the curator is looking', () => {
    it('is "fit" only when the whole image is shown', () => {
        expect(zoomAbout(FIT_VIEW, 2, null, VP_L, BOX_L).mode).toBe('free');
        expect(zoomAbout(view(2), 1, null, VP_L, BOX_L).mode).toBe('fit');
        expect(panBy(view(2), 30, 0, VP_L, BOX_L).mode).toBe('free');
    });

    it('labels itself for a person', () => {
        expect(zoomLabel(FIT_VIEW)).toBe('Fit');
        expect(zoomLabel(view(2.5))).toBe('250%');
        expect(zoomLabel(view(1.234))).toBe('123%');
    });
});

describe('100% is offered only when it means something', () => {
    it('is the scale where one image pixel is one CSS pixel', () => {
        // 2000px natural painted 800px wide → 1:1 at 2.5×.
        expect(naturalScale(BOX_L, NAT_L)).toBeCloseTo(2.5, 9);
    });

    it('is withheld when the image is already past 1:1 at fit', () => {
        const small = { w: 400, h: 200 };
        expect(naturalScale(BOX_L, small)).toBeNull();
    });

    it('is withheld when 1:1 would exceed the scale ceiling', () => {
        expect(naturalScale(BOX_L, { w: 100000, h: 50000 })).toBeNull();
    });
});

describe('framing a region', () => {
    it('brings the bounds to the centre of the viewport', () => {
        const bounds = { x: 0.6, y: 0.1, w: 0.1, h: 0.2 };
        const v = viewForBounds(bounds, VP_L, BOX_L);
        const centre = { x: bounds.x + bounds.w / 2, y: bounds.y + bounds.h / 2 };
        const q = planeToViewport(normalizedToPlane(centre, BOX_L), v, VP_L);
        // Clamping may hold it off-centre near an edge, but it must be on screen.
        expect(q.x).toBeGreaterThanOrEqual(0);
        expect(q.x).toBeLessThanOrEqual(VP_L.w);
        expect(q.y).toBeGreaterThanOrEqual(0);
        expect(q.y).toBeLessThanOrEqual(VP_L.h);
    });

    it('zooms in for a small region and respects the ceiling', () => {
        expect(viewForBounds({ x: 0.4, y: 0.4, w: 0.1, h: 0.1 }, VP_L, BOX_L).scale).toBeGreaterThan(1);
        expect(viewForBounds({ x: 0.5, y: 0.5, w: 0.0005, h: 0.0005 }, VP_L, BOX_L).scale).toBe(MAX_SCALE);
    });

    it('returns fit for a degenerate or missing rectangle', () => {
        expect(viewForBounds(null, VP_L, BOX_L)).toBe(FIT_VIEW);
        expect(viewForBounds({ x: 0, y: 0, w: 0, h: 0 }, VP_L, BOX_L)).toBe(FIT_VIEW);
    });
});

describe('the visible rectangle', () => {
    it('is the whole image at fit', () => {
        const vis = visibleBounds(FIT_VIEW, VP_L, BOX_L);
        expect(vis).toMatchObject({ x: 0, y: 0 });
        expect(vis.w).toBeCloseTo(1, 9);
        expect(vis.h).toBeCloseTo(1, 9);
    });

    it('shrinks as the curator zooms in', () => {
        const at4 = visibleBounds(view(4), VP_L, BOX_L);
        expect(at4.w).toBeLessThan(0.4);
        expect(at4.h).toBeLessThan(1);
    });

    it('never reports area outside the image', () => {
        const v = panTo(view(2), -9e5, -9e5, VP_L, BOX_L);
        const vis = visibleBounds(v, VP_L, BOX_L);
        expect(vis.x).toBeGreaterThanOrEqual(0);
        expect(vis.y).toBeGreaterThanOrEqual(0);
        expect(vis.x + vis.w).toBeLessThanOrEqual(1 + 1e-9);
        expect(vis.y + vis.h).toBeLessThanOrEqual(1 + 1e-9);
    });
});

describe('the transform string', () => {
    it('is one translate and one scale, in that order', () => {
        expect(planeTransform(view(2, 10, -5))).toBe('translate(10px, -5px) scale(2)');
    });

    it('is identity-shaped at fit, so an unzoomed plane is untouched', () => {
        expect(planeTransform(FIT_VIEW)).toBe('translate(0px, 0px) scale(1)');
    });
});

describe('degenerate inputs return quietly rather than throwing', () => {
    it('survives a missing viewport or content box', () => {
        expect(clampPan(5, 5, 2, null, BOX_L)).toEqual({ x: 5, y: 5 });
        expect(viewportToPlane({ x: 1, y: 1 }, FIT_VIEW, null)).toBeNull();
        expect(planeToNormalized(null, BOX_L)).toBeNull();
        expect(clientToNormalized(1, 1, null, FIT_VIEW, BOX_L)).toBeNull();
        expect(visibleBounds(FIT_VIEW, VP_L, null)).toBeNull();
        expect(naturalScale(null, NAT_L)).toBeNull();
    });

    it('ZOOM_STEP is a real step', () => {
        expect(ZOOM_STEP).toBeGreaterThan(1);
    });
});
