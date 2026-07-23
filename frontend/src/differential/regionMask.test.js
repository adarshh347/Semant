import { describe, it, expect, beforeEach } from 'vitest';
import {
    normalizeMark, regionMaskMark, REGION_MASK_ROLE_KEYS, _resetMarkIds,
} from './visualMarks';
import { canCiteMark } from './suggestionQuarantine';

/**
 * CIRCUIT-001 P2E — region_mask family (contract v2 §7.2-C).
 *
 * A segmented extent is not a perceptual field. This pins that region_mask is honest about
 * being a reference to a Region's mask — raster_mask + mask_ref, never inline pixels — with
 * an OPTIONAL role, and cites like any other committed evidence.
 */

const rm = (fields) => normalizeMark({
    type: 'region_mask',
    geometry: { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 2 } },
    ...fields,
}, { now: 'T' });

beforeEach(() => { _resetMarkIds(); });

describe('region_mask geometry is a reference, never pixels', () => {
    it('accepts raster_mask with a mask_ref', () => {
        expect(rm({})).toBeTruthy();
    });

    it('rejects any other geometry kind', () => {
        expect(rm({ geometry: { kind: 'polygon' } })).toBe(null);
        expect(rm({ geometry: { kind: 'freehand_path' } })).toBe(null);
        expect(rm({ geometry: { kind: 'soft_mask' } })).toBe(null);
    });

    it('rejects a raster_mask with no region_id', () => {
        expect(rm({ geometry: { kind: 'raster_mask', mask_ref: {} } })).toBe(null);
        expect(rm({ geometry: { kind: 'raster_mask' } })).toBe(null);
    });

    it('rejects inline pixels, rle, polygons, strokes or points on the geometry', () => {
        const base = { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 0 } };
        for (const banned of ['pixels', 'rle', 'polygons', 'strokes', 'points']) {
            expect(rm({ geometry: { ...base, [banned]: [1, 2, 3] } }), banned).toBe(null);
        }
    });
});

describe('region_mask role is optional', () => {
    it('is valid with no role — a segmented extent has no perceptual reading yet', () => {
        expect(rm({ role: null })?.role).toBe(null);
        expect(rm({})?.role ?? null).toBe(null);
    });

    it('accepts a segmentation role from its own vocabulary', () => {
        for (const role of REGION_MASK_ROLE_KEYS) expect(rm({ role }), role).toBeTruthy();
    });

    it('still rejects a perceptual role that belongs to another family', () => {
        // "light_field" is a brush_field role; a region_mask has not been read as light.
        expect(rm({ role: 'light_field' })).toBe(null);
    });
});

describe('region_mask citability is the standard rule', () => {
    it('a committed, user-owned region_mask is citable evidence', () => {
        expect(canCiteMark(rm({ source: 'user', status: 'committed' }))).toBe(true);
    });

    it('a committed user_confirmed region_mask (SAM accepted) is citable', () => {
        expect(canCiteMark(rm({ source: 'user_confirmed', status: 'committed', derived_from: 'vm_s' }))).toBe(true);
    });

    it('a model_refined region_mask is not citable on its own — tightened is not confirmed', () => {
        expect(canCiteMark(rm({ source: 'model_refined', status: 'committed', derived_from: 'vm_s' }))).toBe(false);
    });

    it('a proposed (suggested) region_mask is never citable', () => {
        expect(canCiteMark(rm({ source: 'model_suggested', status: 'suggested' }))).toBe(false);
    });
});

describe('regionMaskMark helper', () => {
    it('builds a valid reference from a region id + rev, role null by default', () => {
        const m = regionMaskMark({ regionId: 'reg_9', geometryRev: 3, source: 'user', status: 'committed' }, { now: 'T' });
        expect(m.type).toBe('region_mask');
        expect(m.geometry.mask_ref).toEqual({ region_id: 'reg_9', geometry_rev: 3 });
        expect(m.role).toBe(null);
        expect(m.geometry.pixels).toBeUndefined();
    });

    it('carries the model forward and the lineage back when confirming a SAM mask', () => {
        const m = regionMaskMark({
            regionId: 'reg_9', source: 'model_refined', status: 'committed',
            derivedFrom: 'vm_s', model: 'sam2',
        }, { now: 'T' });
        expect(m.source).toBe('model_refined');
        expect(m.derived_from).toBe('vm_s');
        expect(m.provenance.model).toBe('sam2');
    });
});
