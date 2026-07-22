import { describe, it, expect } from 'vitest';
import { compareTaper, toPx, strokeViaPerfectFreehand, pathToPolygon, countPathVertices, polygonBBox } from './freehandCompare';
import { taperedRibbon } from '../freehandTaper';
import { synthesizeHeavyStroke } from './spikeFixture';

const NATURAL = { w: 3024, h: 4032 };   // a real phone frame, portrait

describe('Spike 3 — perfect-freehand vs freehandTaper on the heaviest real stroke', () => {
    const heavy = synthesizeHeavyStroke();

    it('the synthetic stroke matches the corpus shape (OH §1.10)', () => {
        expect(heavy.points).toHaveLength(1194);
        expect(heavy.points.every(([x, y]) => x >= 0 && x <= 1 && y >= 0 && y <= 1)).toBe(true);
        expect(heavy.points.every((p) => p.length === 3)).toBe(true);
    });

    it('both produce a closed outline covering the same region', () => {
        const r = compareTaper(heavy.points, NATURAL);
        const a = r.perfectFreehand.bbox;
        const b = r.freehandTaper.bbox;
        // Same gesture ⇒ same footprint to within a stroke width.
        const tol = 0.05 * NATURAL.w;
        expect(Math.abs(a.x - b.x)).toBeLessThan(tol);
        expect(Math.abs(a.w - b.w)).toBeLessThan(tol);
        expect(Math.abs(a.h - b.h)).toBeLessThan(tol);
    });

    it('both respond to pressure — neither discards it', () => {
        const r = compareTaper(heavy.points, NATURAL);
        // `simulatePressure: false` is set deliberately: the corpus HAS pressure
        // and a generator that fabricates it would score well here dishonestly.
        expect(r.perfectFreehand.pressureSensitivityPx).toBeGreaterThan(0);
        expect(r.freehandTaper.pressureSensitivityPx).toBeGreaterThan(0);
    });

    it('records the numbers this spike exists to produce', () => {
        const r = compareTaper(heavy.points, NATURAL, { runs: 25 });
        // Not thresholds — measurements. The assertions are only that the
        // measurement ran; the values go in the report.
        expect(r.perfectFreehand.vertices).toBeGreaterThan(0);
        expect(r.freehandTaper.vertices).toBeGreaterThan(0);
        expect(r.perfectFreehand.timing.median).toBeGreaterThanOrEqual(0);
        console.log('SPIKE3 heavy(1194pts) →', JSON.stringify({
            pf: { v: r.perfectFreehand.vertices, chars: r.perfectFreehand.pathChars, ms: +r.perfectFreehand.timing.median.toFixed(3), press: +r.perfectFreehand.pressureSensitivityPx.toFixed(2) },
            ft: { v: r.freehandTaper.vertices, chars: r.freehandTaper.pathChars, ms: +r.freehandTaper.timing.median.toFixed(3), press: +r.freehandTaper.pressureSensitivityPx.toFixed(2) },
            input: r.input,
        }));
    });

    it('and for a short, ordinary stroke too', () => {
        const short = [[0.28, 0.30, 0.4], [0.31, 0.33, 0.7], [0.34, 0.37, 0.9], [0.36, 0.42, 1.0], [0.37, 0.47, 0.9], [0.36, 0.52, 0.7], [0.34, 0.56, 0.4]];
        const r = compareTaper(short, NATURAL, { runs: 25 });
        console.log('SPIKE3 short(7pts) →', JSON.stringify({
            pf: { v: r.perfectFreehand.vertices, ms: +r.perfectFreehand.timing.median.toFixed(4) },
            ft: { v: r.freehandTaper.vertices, ms: +r.freehandTaper.timing.median.toFixed(4) },
        }));
        expect(r.perfectFreehand.vertices).toBeGreaterThan(3);
    });
});

describe('output stays plain data', () => {
    it('perfect-freehand returns arrays of numbers, not objects', () => {
        const px = toPx([[0.1, 0.1, 0.5], [0.5, 0.5, 0.9], [0.9, 0.2, 0.3]], NATURAL);
        const poly = strokeViaPerfectFreehand(px);
        expect(Array.isArray(poly)).toBe(true);
        expect(poly.every((p) => Array.isArray(p) && p.every((n) => typeof n === 'number'))).toBe(true);
    });

    it('the taperedRibbon path parses back to the polygon it drew', () => {
        const px = toPx([[0.1, 0.1, 0.5], [0.5, 0.5, 0.9], [0.9, 0.2, 0.3]], NATURAL);
        const d = taperedRibbon(px, { maxWidth: 0.02 * NATURAL.w });
        const poly = pathToPolygon(d);
        expect(poly.length).toBe(countPathVertices(d));
        expect(polygonBBox(poly).w).toBeGreaterThan(0);
    });
});
