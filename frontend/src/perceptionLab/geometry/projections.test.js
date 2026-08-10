// PERCEPTUAL-ORGANS-002 Lane E — projections stay projections.
//
// The load-bearing assertions here are not about geometry. They are that every value leaving this
// module is stamped `derived`, that a projection which cannot be computed REFUSES with a sentence
// instead of drawing something plausible, and that `agreement` reports a disagreement rather than
// smoothing it.

import { describe, it, expect } from 'vitest';
import { emptyRaster, maskArea } from './maskRaster';
import {
    extentProjection, boxProjection, contactBandProjection, intersectionProjection,
    differenceProjection, endpointPairProjection, clearanceProjection, scalarWashProjection,
    deriveNegativeSpaceField, agreement,
} from './projections';

const raster = (rows) => {
    const h = rows.length;
    const w = rows[0].length;
    const m = emptyRaster(h, w);
    rows.forEach((row, r) => [...row].forEach((ch, c) => { m.data[r * w + c] = ch === '#' ? 1 : 0; }));
    return m;
};

const A = raster(['####..', '####..', '####..', '......']);
const B = raster(['..####', '..####', '..####', '......']);
const FAR = raster(['.....#', '.....#', '......', '......']);
const OTHER_RASTER = raster(['##', '##']);

describe('every projection says it is one', () => {
    const all = [
        extentProjection(A),
        boxProjection(A),
        contactBandProjection(A, B),
        intersectionProjection(A, B),
        differenceProjection(A, B),
        endpointPairProjection(A, B),
        clearanceProjection(A, FAR),
    ];
    it('carries derived: true and names the machine that drew it', () => {
        for (const p of all) {
            expect(p.derived).toBe(true);
            expect(p.available).toBe(true);
            expect(p.computed_by).toBe('lab_browser');
            expect(p.projection_kind).toBeTruthy();
        }
    });
    it('marks which ones are exact arithmetic and which are estimates', () => {
        expect(extentProjection(A).exact).toBe(true);
        expect(intersectionProjection(A, B).exact).toBe(true);
        expect(boxProjection(A).exact).toBe(false);
        expect(contactBandProjection(A, B).exact).toBe(false);
    });
});

describe('a projection that cannot be computed refuses, with a reason', () => {
    it('refuses across rasters instead of resampling', () => {
        const band = contactBandProjection(A, OTHER_RASTER);
        expect(band.available).toBe(false);
        expect(band.rings).toEqual([]);
        expect(band.why).toMatch(/different rasters/);
        expect(band.why).toMatch(/invent/);
        expect(intersectionProjection(A, OTHER_RASTER).available).toBe(false);
        expect(clearanceProjection(A, OTHER_RASTER).available).toBe(false);
    });

    it('refuses to anchor a pair when an endpoint did not resolve — the dangling case', () => {
        const p = endpointPairProjection(A, null);
        expect(p.available).toBe(false);
        expect(p.why).toMatch(/one endpoint/);
        expect(endpointPairProjection(null, null).why).toMatch(/neither endpoint/);
    });

    it('refuses to wash a field it does not have, and says the statistics are not the field', () => {
        const p = scalarWashProjection({
            field_shape: [300, 400],
            field_ref: { uri: 'labstore://x' },
            statistics: { min: 0, max: 0.24, mean: 0.08 },
        });
        expect(p.available).toBe(false);
        expect(p.why).toMatch(/field_ref/);
        expect(p.why).toMatch(/invented/);
    });

    it('washes a field that IS in the payload', () => {
        const p = scalarWashProjection({ field_shape: [2, 2], values: [0, 1, 2, 3] });
        expect(p.available).toBe(true);
        expect(p.cells).toHaveLength(4);
        expect(p.cells[0].intensity).toBe(0);
        expect(p.cells[3].intensity).toBe(1);
    });

    it('derives a wash from the figure masks, and never calls it the measured field', () => {
        const p = deriveNegativeSpaceField([raster(['....', '.##.', '.##.', '....'])],
            { max_distance: 1, statistics: { min: 0, max: 0.4, mean: 0.2 } });
        expect(p.available).toBe(true);
        expect(p.exact).toBe(false);
        expect(p.derived).toBe(true);
        expect(p.why).toMatch(/field_ref/);
        expect(p.why).toMatch(/computed in this browser/);
        expect(p.cells).toHaveLength(16);
        expect(p.min).toBe(0);                       // the figure itself is at distance zero
        expect(typeof p.agrees_with_statistics).toBe('boolean');
    });

    it('the derived wash refuses on an empty or mismatched figure set', () => {
        expect(deriveNegativeSpaceField([]).available).toBe(false);
        expect(deriveNegativeSpaceField([A, OTHER_RASTER]).why).toMatch(/different rasters/);
    });

    it('an instance with no mask gets a stated absence, not a box', () => {
        expect(extentProjection(null).available).toBe(false);
        expect(boxProjection(null).available).toBe(false);
        expect(boxProjection(raster(['..', '..'])).why).toMatch(/empty/);
    });
});

describe('the numbers a projection derives', () => {
    it('the contact band is the overlap of the two dilations, under the measurement tolerance', () => {
        const touching = contactBandProjection(A, B, { tolerance_px: 1 });
        expect(touching.touches).toBe(true);
        expect(touching.tolerance_px).toBe(1);
        expect(touching.derived_contact_pixels).toBeGreaterThan(0);
        expect(touching.rings.length).toBeGreaterThan(0);
    });

    it('a wider tolerance finds contact where a tight one does not', () => {
        const gap = raster(['#...#', '#...#']);
        const left = raster(['#....', '#....']);
        const right = raster(['....#', '....#']);
        expect(contactBandProjection(left, right, { tolerance_px: 1 }).touches).toBe(false);
        expect(contactBandProjection(left, right, { tolerance_px: 2 }).touches).toBe(true);
        expect(maskArea(gap)).toBe(4);
    });

    it('the intersection is exact and its IoU is arithmetic on the two areas', () => {
        const inter = intersectionProjection(A, B);
        expect(inter.derived_intersection_pixels).toBe(6);       // cols 2-3, rows 0-2
        expect(inter.derived_iou).toBeCloseTo(6 / (12 + 12 - 6));
    });

    it('the difference keeps both sides apart', () => {
        const d = differenceProjection(A, B);
        expect(d.rings.length).toBe(1);
        expect(d.other_rings.length).toBe(1);
    });

    it('a box over-states a diagonal shape, and reports by how much', () => {
        const diag = raster(['#..', '.#.', '..#']);
        const box = boxProjection(diag);
        expect(box.box).toEqual({ x: 0, y: 0, w: 1, h: 1 });
        expect(box.over_estimate_fraction).toBeCloseTo(1 - 3 / 9);
    });

    it('an undirected pair is not drawn with a direction it did not measure', () => {
        expect(endpointPairProjection(A, B, { directed: false }).directed).toBe(false);
        expect(endpointPairProjection(A, B, { directed: true }).directed).toBe(true);
    });
});

describe('agreement — the derived drawing against the producer’s number', () => {
    it('agrees when they are close', () => {
        expect(agreement(100, 104).agrees).toBe(true);
    });
    it('reports the disagreement rather than hiding it', () => {
        const a = agreement(1184, 12);
        expect(a.agrees).toBe(false);
        expect(a.delta).toBe(1172);
        expect(a.measured).toBe(12);
        expect(a.derived).toBe(1184);
    });
    it('is null when there is nothing to compare', () => {
        expect(agreement(5, null)).toBe(null);
        expect(agreement(undefined, 5)).toBe(null);
    });
});
