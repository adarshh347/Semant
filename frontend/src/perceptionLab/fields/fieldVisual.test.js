import { describe, expect, it } from 'vitest';
import fixture from './fixtures/foundation-field.v1.json';
import { checkedFamilySlots, FAMILY_KEYS } from '../families/registry';
import { fieldRgb, pixelAt, previewPixels } from './fieldVisual';

describe('saved field display', () => {
    it('changes only pixels when the display view changes', () => {
        const before = JSON.stringify(fixture);
        const colour = previewPixels(fixture, [0, 1], 'colour');
        const gray = previewPixels(fixture, [0, 1], 'grayscale');
        expect(colour.pixels).not.toEqual(gray.pixels);
        expect(JSON.stringify(fixture)).toBe(before);
        expect(fixture.measurement_hash).toBe(fixture.manifest.measurement_hash);
        expect(colour.pixels.slice(16, 20)).toEqual(new Uint8ClampedArray([110, 110, 110, 255]));
    });

    it('treats axial wraparound as the same line but directed reversal as different', () => {
        const nearZero = fieldRgb('axial_orientation_2d', [1, 0], true, [-1, 1], 'colour');
        const nearPi = fieldRgb('axial_orientation_2d', [1, -.0001], true, [-1, 1], 'colour');
        expect(nearZero[0]).toBe(nearPi[0]);
        const forward = fieldRgb('directed_vector_2d', [1, 0], true, [-1, 1], 'colour');
        const backward = fieldRgb('directed_vector_2d', [-1, 0], true, [-1, 1], 'colour');
        expect(forward).not.toEqual(backward);
    });

    it('maps a click to declared field pixel coordinates', () => {
        expect(pixelAt(30, 15, { left: 0, top: 0, width: 60, height: 20 },
            fixture.metadata)).toEqual([1, 1]);
        expect(pixelAt(30, 15, { left: 0, top: 0, width: 60, height: 20 },
            { shape: [8, 12, 1] }, { shape: [2, 3, 1], stride: 4 })).toEqual([4, 4]);
    });
});

it('refuses duplicate or out of order family modules', () => {
    const slots = FAMILY_KEYS.map((family) => ({ family, label: family,
        reason: 'unavailable', available: false, forms: [], operations: [], views: [],
        promptIntents: [], Panel: () => null }));
    expect(() => checkedFamilySlots(slots)).not.toThrow();
    slots[1] = { ...slots[1], family: 'colour' };
    expect(() => checkedFamilySlots(slots)).toThrow(/six fixed family slots/);
});
