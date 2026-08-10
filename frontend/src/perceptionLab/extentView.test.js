// PERCEPTUAL-ORGANS-002 Lane E — reading an extent_set for drawing, without a DOM.
//
// The first suite is the one that matters most: a mask measured on a coarse raster must land on
// the image, and must say that its edge is coarse. Lane B's own fixture is used for it rather than
// a mask invented here, because the point is that the frontend reads what the backend produces.

import { describe, it, expect } from 'vitest';
import laneB from '../../../contracts/fixtures/perception-lab/artifact.extent-set-lane-b.json';
import {
    beforeAfter, decodeInstances, instanceRegions, lineageOf, namingState, overlapMetrics,
    rasterCoarseness,
} from './extentView';
import { encodeRle } from './geometry/maskRaster';
import { rasterizeShape } from './fixtures/scenes';

const raster = (shape, h = 40, w = 40) => rasterizeShape(shape, h, w);
const instance = (id, mask, extra = {}) => ({
    instance_id: id,
    mask_rle: encodeRle(mask),
    box: null,
    area: null,
    confidence: null,
    naming: null,
    region_id: null,
    geometry_rev: null,
    ...extra,
});
const setOf = (instances, id = 'art_1', extra = {}) => ({
    identity: { artifact_id: id, run_id: 'run_1', operation: 'extent.find_all',
        artifact_kind: 'extent_set', identity_scope: 'session', derived_from: [], ...extra },
    measurement: { payload: { variant: 'extent_set', searched: 'shapes', instances,
        dropped_below_min_area: null, duplicates: [], comparison: null },
    epistemic_basis: 'mask' },
    provenance: { completed_at: '2026-08-10T09:00:00.000Z', started_at: null },
});

describe('Lane B’s own extent set, read by this frontend', () => {
    const instances = decodeInstances(laneB);

    it('decodes both instances, one named and one not', () => {
        expect(instances).toHaveLength(2);
        expect(instances[0].naming.state).toBe('interpretive');
        expect(instances[0].naming.text).toBe('finial');
        expect(instances[1].naming.state).toBe('withheld');
        expect(instances[1].naming.text).toBe(null);
    });

    it('a withheld name is withheld, and the sentence says the geometry survived it', () => {
        expect(instances[1].naming.note).toMatch(/the mask survives and the word does not/);
        expect(instances[1].naming.note).toMatch(/not an unknown object/);
        // The measurement is intact: this is not a degraded instance.
        expect(instances[1].mask).toBeTruthy();
        expect(instances[1].confidence).toBe(0.34);
    });

    it('traces the exact boundary rather than drawing the box', () => {
        const [left] = instanceRegions(instances, { basis: 'mask' });
        expect(left.exact).toBe(true);
        expect(left.basis).toBe('mask');
        // Lane B's first instance is the left half of a 4×4 raster: a closed rectangle ring at
        // x ∈ [0, 0.5]. The box happens to agree here, which is exactly why the flag matters —
        // the shapes are identical and the CLAIMS are not.
        expect(left.polygons).toHaveLength(1);
        const xs = left.polygons[0].map(([x]) => x);
        expect(Math.min(...xs)).toBe(0);
        expect(Math.max(...xs)).toBe(0.5);
    });

    it('the box basis draws the same instance and refuses to call itself exact', () => {
        const [left] = instanceRegions(instances, { basis: 'box' });
        expect(left.basis).toBe('box');
        expect(left.exact).toBe(false);
    });

    it('says how coarse the grid the measurement was taken on actually is', () => {
        const note = rasterCoarseness(instances, { w: 1600, h: 1200 });
        expect(note.raster).toEqual({ h: 4, w: 4 });
        expect(note.cell_px).toEqual({ x: 400, y: 300 });
        expect(note.coarse).toBe(true);
    });

    it('a fine raster is not flagged as coarse', () => {
        const note = rasterCoarseness(instances, { w: 4, h: 4 });
        expect(note.coarse).toBe(false);
    });
});

describe('naming is three states, not a string or nothing', () => {
    it('an uncertain name is on the record as a guess', () => {
        const state = namingState({ naming: { text: 'drapery', source: 'adapter',
            epistemic_status: 'uncertain' } });
        expect(state.state).toBe('uncertain');
        expect(state.text).toBe('drapery');
        expect(state.note).toMatch(/without a claim/);
    });

    it('withheld and uncertain do not share a sentence', () => {
        expect(namingState({ naming: null }).note)
            .not.toBe(namingState({ naming: { text: 'x', epistemic_status: 'uncertain' } }).note);
    });
});

describe('a box-only instance is drawn as a box and never called a mask', () => {
    const boxOnly = {
        instance_id: 'ext_box', mask_rle: null, area: 0.1, confidence: null, naming: null,
        region_id: null, geometry_rev: null,
        box: { x: 0.1, y: 0.2, w: 0.3, h: 0.4 },
    };
    it('carries no mask raster, and the region says so', () => {
        const [region] = instanceRegions(decodeInstances(setOf([boxOnly])), { basis: 'mask' });
        expect(region.basis).toBe('box');
        expect(region.exact).toBe(false);
        expect(region.polygons[0]).toHaveLength(4);
    });

    it('the mask is left null rather than rasterized from the box', () => {
        // Filling it in would make a box basis look per-pixel to everything downstream.
        expect(decodeInstances(setOf([boxOnly]))[0].mask).toBe(null);
    });
});

describe('duplicates are within a set; repeats are across two', () => {
    const a = raster({ kind: 'rect', x: 0.1, y: 0.1, w: 0.3, h: 0.3 });
    const nearlyA = raster({ kind: 'rect', x: 0.105, y: 0.105, w: 0.3, h: 0.3 });
    const far = raster({ kind: 'rect', x: 0.7, y: 0.7, w: 0.2, h: 0.2 });

    it('finds a near-duplicate pair inside one set', () => {
        const m = overlapMetrics(decodeInstances(setOf([
            instance('one', a), instance('two', nearlyA), instance('three', far)])));
        expect(m.pairs_examined).toBe(3);
        expect(m.duplicates).toHaveLength(1);
        expect(m.duplicates[0].iou).toBeGreaterThan(0.9);
        expect(m.overlapping).toHaveLength(1);
    });

    it('a set with no overlap reports zero rather than nothing', () => {
        const m = overlapMetrics(decodeInstances(setOf([instance('one', a), instance('two', far)])));
        expect(m.pairs_examined).toBe(1);
        expect(m.duplicates).toEqual([]);
        expect(m.overlapping).toEqual([]);
    });

    it('matches a second run against the first and names what only one of them found', () => {
        const first = decodeInstances(setOf([instance('a1', a), instance('a2', far)]));
        const second = decodeInstances(setOf([instance('b1', nearlyA)], 'art_2'));
        const m = overlapMetrics(first, second);
        expect(m.repeats.matched.map((x) => x.a)).toEqual(['a1']);
        expect(m.repeats.unmatched.map((x) => x.a)).toEqual(['a2']);
        expect(m.repeats.only_in_other).toEqual([]);
        expect(m.repeats.mean_iou).toBeGreaterThan(0);
    });

    it('refuses to match two sets measured on different rasters', () => {
        const first = decodeInstances(setOf([instance('a1', raster(
            { kind: 'rect', x: 0.1, y: 0.1, w: 0.4, h: 0.4 }, 40, 40))]));
        const second = decodeInstances(setOf([instance('b1', raster(
            { kind: 'rect', x: 0.1, y: 0.1, w: 0.4, h: 0.4 }, 20, 20))], 'art_2'));
        const m = overlapMetrics(first, second);
        expect(m.repeats).toBe(null);
        expect(m.refusal).toMatch(/different rasters/);
        expect(m.refusal).toMatch(/will not perform/);
    });
});

describe('before and after', () => {
    const base = raster({ kind: 'rect', x: 0.2, y: 0.2, w: 0.3, h: 0.3 });
    const grown = raster({ kind: 'rect', x: 0.2, y: 0.2, w: 0.4, h: 0.3 });

    it('says what was added and what was removed, not only the result', () => {
        const [before] = decodeInstances(setOf([instance('ext_1', base)]));
        const [after] = decodeInstances(setOf([instance('ext_1', grown)]));
        const change = beforeAfter(before, after);
        expect(change.available).toBe(true);
        expect(change.derived).toBe(true);
        expect(change.added_fraction).toBeGreaterThan(0);
        expect(change.removed_fraction).toBe(0);
        expect(change.net_fraction).toBeCloseTo(change.added_fraction, 10);
        expect(change.box_moved).toBe(true);
    });

    it('refuses across rasters rather than resampling', () => {
        const [before] = decodeInstances(setOf([instance('ext_1', raster(
            { kind: 'rect', x: 0.2, y: 0.2, w: 0.3, h: 0.3 }, 40, 40))]));
        const [after] = decodeInstances(setOf([instance('ext_1', raster(
            { kind: 'rect', x: 0.2, y: 0.2, w: 0.3, h: 0.3 }, 20, 20))]));
        expect(beforeAfter(before, after).why).toMatch(/different rasters/);
    });

    it('needs a mask on both sides and says which one is missing', () => {
        expect(beforeAfter(null, null).why).toMatch(/needs a mask on both sides/);
    });
});

describe('lineage carries the revision, not only the derivation', () => {
    it('walks derived_from and keeps each instance’s geometry_rev', () => {
        const base = setOf([instance('ext_1', raster({ kind: 'rect', x: 0.1, y: 0.1, w: 0.2, h: 0.2 }))],
            'art_base');
        const refined = setOf(
            [instance('ext_1', raster({ kind: 'rect', x: 0.1, y: 0.1, w: 0.3, h: 0.2 }),
                { region_id: 'reg_9', geometry_rev: 3 })],
            'art_refined', { operation: 'extent.refine', derived_from: ['art_base'] });
        const byId = new Map([['art_base', base], ['art_refined', refined]]);
        const chain = lineageOf(refined, byId);
        expect(chain.map((n) => n.artifact_id)).toEqual(['art_refined', 'art_base']);
        expect(chain[0].instances[0].geometry_rev).toBe(3);
        expect(chain[1].instances[0].geometry_rev).toBe(null);
        // The SAME instance id at two revisions: a refinement, not a new thing.
        expect(chain[0].instances[0].instance_id).toBe(chain[1].instances[0].instance_id);
    });

    it('does not loop on a cycle', () => {
        const a = setOf([], 'art_a', { derived_from: ['art_b'] });
        const b = setOf([], 'art_b', { derived_from: ['art_a'] });
        const byId = new Map([['art_a', a], ['art_b', b]]);
        expect(lineageOf(a, byId).map((n) => n.artifact_id)).toEqual(['art_a', 'art_b']);
    });
});
