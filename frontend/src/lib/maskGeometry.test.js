import { describe, it, expect } from 'vitest';
import { hasMaskPolygons, ringsToPath } from './maskGeometry';
import { contentBox, normalizedToStage } from '../differential/useStageGeometry';

describe('maskGeometry — mask polygon rendering (VISION-BUILD-001 Increment A)', () => {
    it('hasMaskPolygons detects real multi-ring geometry, ignores empty/legacy', () => {
        expect(hasMaskPolygons({ polygons: [[[0, 0], [1, 0], [1, 1]]] })).toBe(true);
        expect(hasMaskPolygons({ polygons: [] })).toBe(false);
        expect(hasMaskPolygons({ polygons: [[[0, 0], [1, 1]]] })).toBe(false); // <3 pts
        expect(hasMaskPolygons({ polygon: [[0, 0], [1, 0], [1, 1]] })).toBe(false); // legacy single
        expect(hasMaskPolygons({ box: { x: 0, y: 0, w: 1, h: 1 } })).toBe(false);
        expect(hasMaskPolygons(null)).toBe(false);
    });

    it('ringsToPath scales normalized rings into natural-pixel path space', () => {
        const d = ringsToPath([[[0, 0], [1, 0], [1, 1], [0, 1]]], 200, 100);
        expect(d).toBe('M0,0L200,0L200,100L0,100Z');
    });

    it('ringsToPath emits one closed subpath per ring (holes / components) for evenodd', () => {
        const outer = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]];
        const hole = [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]];
        const d = ringsToPath([outer, hole], 100, 100);
        expect((d.match(/M/g) || []).length).toBe(2);   // two subpaths
        expect((d.match(/Z/g) || []).length).toBe(2);   // both closed
        expect(d.startsWith('M10,10')).toBe(true);
    });

    it('drops degenerate rings and returns empty for nothing drawable', () => {
        expect(ringsToPath([[[0, 0], [1, 1]]], 100, 100)).toBe('');
        expect(ringsToPath(null, 100, 100)).toBe('');
    });

    // Coordinate registration: the SAME normalized point must land on the SAME image
    // pixel at two different stage sizes (the contain-fit contract the overlay relies on).
    it('registers geometry identically across stage resize', () => {
        const natW = 680, natH = 286;      // the five-sculpture aspect
        const pt = { x: 0.5148, y: 0.42 }; // a point that used to crush in REGION-GEOMETRY-001

        // Two very different stages, both wider/taller than the image's aspect.
        const small = contentBox(800, 600, natW, natH);
        const large = contentBox(1600, 1200, natW, natH);

        const a = normalizedToStage(pt, small);
        const b = normalizedToStage(pt, large);

        // Fraction of the *content box* is identical at both sizes → no drift.
        const fracA = { x: (a.left - small.x) / small.w, y: (a.top - small.y) / small.h };
        const fracB = { x: (b.left - large.x) / large.w, y: (b.top - large.y) / large.h };
        expect(fracA.x).toBeCloseTo(pt.x, 6);
        expect(fracA.y).toBeCloseTo(pt.y, 6);
        expect(fracB.x).toBeCloseTo(fracA.x, 6);
        expect(fracB.y).toBeCloseTo(fracA.y, 6);

        // And the content box is a true contain-fit (same scale both axes).
        expect(small.w / natW).toBeCloseTo(small.h / natH, 6);
        expect(large.w / natW).toBeCloseTo(large.h / natH, 6);
    });
});
