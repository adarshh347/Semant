import { describe, expect, it } from 'vitest';
import { checkedFamilySlots } from './registry';
import { SLOT } from './colour';
import { labSwatch, pixelsFor } from './colourVisual';

const field = (form, values, valid = [true, true]) => ({
    metadata: { kind: form === 'channels' ? 'multichannel' : 'scalar',
        shape: [1, 2, form === 'channels' ? 6 : 1],
        value_convention: JSON.stringify({ form, actual_clusters: 2 }) },
    preview: { shape: [1, 2, form === 'channels' ? 6 : 1],
        stride: 1, values, valid },
});

describe('colour family contract and saved-value displays', () => {
    it('registers four operations and exact bounded intents', () => {
        expect(checkedFamilySlots().colour).toBe(SLOT);
        expect(SLOT.operations.map((op) => op.key)).toEqual([
            'colour.channels', 'colour.palette', 'colour.distance', 'colour.distance_rgb']);
        expect(SLOT.operations[2].parameters.map((p) => p.name)).toEqual(['x', 'y']);
        expect(SLOT.promptIntents).toContain('compare colour to the selected sample');
    });

    it('renders selected channel and invalid cells without changing the record', () => {
        const saved = field('channels', [1, 0, 0, 53, 80, 67, 0, 0, 0, 0, 0, 0],
            [true, false]);
        const before = JSON.stringify(saved);
        const lightness = pixelsFor(saved, 3, 1, [0, 100]);
        const chroma = pixelsFor(saved, 4, .5, [-127, 127]);
        expect(lightness.bytes[0]).not.toBe(chroma.bytes[0]);
        expect(lightness.bytes[3]).toBe(255);
        expect(chroma.bytes[3]).toBe(128);
        expect(lightness.bytes[7]).toBe(255);
        expect(JSON.stringify(saved)).toBe(before);
    });

    it('uses a disclosed fixed distance scale, independent of source pixels', () => {
        const saved = field('distance', [0, 200]);
        const output = pixelsFor(saved, 0, 1, [0, 200]);
        expect(output.bytes[0]).toBe(0);
        expect(output.bytes[4]).toBe(255);
    });

    it('makes approximate display swatches from saved Lab centres', () => {
        expect(labSwatch([100, 0, 0])).toBe('rgb(255, 255, 255)');
        expect(labSwatch([0, 0, 0])).toBe('rgb(0, 0, 0)');
    });
});
