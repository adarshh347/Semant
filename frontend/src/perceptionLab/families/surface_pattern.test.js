import { describe, expect, it } from 'vitest';
import { descriptor, patchCells, similarity } from './patternConsumer';
import { SLOT } from './surface_pattern';

const data = { measurement_hash: 'same', metadata: {
    shape: [2, 3, 2], channels: [{ name: 'a' }, { name: 'b' }] },
preview: { shape: [2, 3, 2], stride: 1, valid: [true, true, true, true, false, true],
    values: [1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 0, 1] } };

describe('saved pattern consumer', () => {
    it('requires an explicit patch and keeps named channels', () => {
        expect(patchCells(0, 0, 2, 1, data.preview.shape)).toEqual([[0, 0], [1, 0]]);
        expect(() => patchCells(2, 0, 2, 1, data.preview.shape)).toThrow();
        const ref = descriptor(data, [[0, 0], [1, 0]]);
        expect(ref.means).toEqual([1, 0]);
        expect(ref.channels).toEqual(data.metadata.channels);
        const comparison = similarity(data, ref, 1, 1);
        expect(comparison.shape).toEqual([2, 3, 1]);
        expect(comparison.values[0]).toBe(1);
        expect(comparison.valid[4]).toBe(false);
    });
    it('refuses unrelated channel space and incomplete previews', () => {
        const ref = descriptor(data, [[0, 0]]);
        expect(() => similarity(data, { ...ref, fieldHash: 'other' }, 1, 1)).toThrow();
        expect(() => descriptor({ ...data, preview: { ...data.preview, stride: 2 } }, [[0, 0]])).toThrow();
    });
    it('declares a direct pattern instrument', () => {
        expect(SLOT.available).toBe(true);
        expect(SLOT.operations[0].prompt_intents).toEqual(['show texture at the selected scale']);
    });
});
