import { describe, it, expect } from 'vitest';
import { groundLayerKey, deriveLayers, persistableLayers } from './layerGrouping';

// CIRCUIT-001 Q-C — render-grouping is pure: masks partition by producer/role, and each layer's
// saved visibility/opacity merges onto the layers actually present.

describe('groundLayerKey — by producer/role', () => {
    it('regions are the find_parts layer', () => {
        expect(groundLayerKey({ ground_type: 'region' })).toBe('find_parts');
    });
    it('each field role is its own layer', () => {
        expect(groundLayerKey({ ground_type: 'field', role: 'material_field' })).toBe('field:material_field');
        expect(groundLayerKey({ ground_type: 'field', role: 'rhythm' })).toBe('field:rhythm');
        expect(groundLayerKey({ ground_type: 'field' })).toBe('field');
    });
    it('traces group together; relations group together', () => {
        expect(groundLayerKey({ ground_type: 'path' })).toBe('trace');
        expect(groundLayerKey({ ground_type: 'boundary' })).toBe('trace');
        expect(groundLayerKey({ ground_type: 'relation' })).toBe('relation');
        expect(groundLayerKey({ ground_type: 'constellation' })).toBe('relation');
    });
    it('frame is its own; anything unknown is other', () => {
        expect(groundLayerKey({ ground_type: 'frame' })).toBe('frame');
        expect(groundLayerKey({ ground_type: 'mystery' })).toBe('other');
        expect(groundLayerKey(null)).toBe('other');
    });
});

describe('deriveLayers — only present layers, saved state merged', () => {
    const grounds = [
        { id: 'a', ground_type: 'region' },
        { id: 'b', ground_type: 'region' },
        { id: 'c', ground_type: 'field', role: 'material_field' },
        { id: 'd', ground_type: 'relation' },
    ];

    it('emits one layer per distinct present key, with counts, in order', () => {
        const layers = deriveLayers(grounds, []);
        expect(layers.map((l) => l.key)).toEqual(['find_parts', 'relation', 'field:material_field']);
        expect(layers.find((l) => l.key === 'find_parts').count).toBe(2);
        // all default visible/opaque
        expect(layers.every((l) => l.visibility === true && l.opacity === 1)).toBe(true);
    });

    it('an empty layer never appears', () => {
        const layers = deriveLayers([{ id: 'a', ground_type: 'region' }], []);
        expect(layers.map((l) => l.key)).toEqual(['find_parts']);
    });

    it('merges saved visibility/opacity onto the present layers', () => {
        const saved = [{ key: 'find_parts', visibility: false, opacity: 0.4 }];
        const fp = deriveLayers(grounds, saved).find((l) => l.key === 'find_parts');
        expect(fp.visibility).toBe(false);
        expect(fp.opacity).toBe(0.4);
    });

    it('a saved key for an absent layer is harmless (ignored)', () => {
        const saved = [{ key: 'field:gone', visibility: false }];
        const keys = deriveLayers(grounds, saved).map((l) => l.key);
        expect(keys).not.toContain('field:gone');
    });
});

describe('persistableLayers — the saved shape', () => {
    it('keeps key/visibility/opacity/order, clamps opacity', () => {
        const out = persistableLayers([{ key: 'find_parts', visibility: false, opacity: 2, order: 10 }]);
        expect(out).toEqual([{ key: 'find_parts', visibility: false, opacity: 1, order: 10 }]);
    });
});
