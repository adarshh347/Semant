import { describe, expect, it } from 'vitest';
import { fieldRgb } from '../fields/fieldVisual';
import { compatibleDepth, depthProfileSegments, parseDepthCells } from './depthVisual';

describe('saved relative-depth readers', () => {
    it('renders larger nearer as red/light and smaller farther as blue/dark', () => {
        expect(fieldRgb('scalar', [2], true, [2, 8], 'colour')).toEqual([0, 0, 255, 255]);
        expect(fieldRgb('scalar', [8], true, [2, 8], 'colour')).toEqual([255, 0, 0, 255]);
        expect(fieldRgb('scalar', [8], true, [2, 8], 'grayscale')).toEqual([255, 255, 255, 255]);
        expect(fieldRgb('scalar', [0], false, [2, 8], 'colour')).toEqual([110, 110, 110, 255]);
    });
    it('requires explicit integer native cells without silently interpreting blanks as zero', () => {
        expect(parseDepthCells(' 1,2; 4,8 ')).toEqual([[1, 2], [4, 8]]);
        ['', '1,', '1,2;', '-1,2', '1.5,2', 'NaN,1'].forEach((text) => expect(() => parseDepthCells(text)).toThrow());
    });
    it('breaks a profile across unknown cells and never edits its samples', () => {
        const samples = [{ valid: true, values: [2] }, { valid: false, values: null }, { valid: true, values: [8] }];
        const before = JSON.stringify(samples);
        expect(depthProfileSegments(samples, [2, 8])).toEqual([['0,100'], ['100,0']]);
        expect(depthProfileSegments(samples, [8, 2])).toEqual([]);
        expect(JSON.stringify(samples)).toBe(before);
    });
    it('refuses independent sources, scales and transforms for raw comparison', () => {
        const left = { shape: [2, 3, 1], kind: 'scalar', channels: ['inverse_depth'], frame: 'image', units: 'relative',
            source_digest: 'a', source_to_field: [1, 0, 0, 0, 1, 0, 0, 0, 1], value_convention: 'larger=nearer; standard' };
        expect(compatibleDepth(left, { ...left })).toBe(true);
        for (const [key, value] of Object.entries({ source_digest: 'b', value_convention: 'normalized', shape: [1, 3, 1],
            source_to_field: [2, 0, 0, 0, 2, 0, 0, 0, 1] })) expect(compatibleDepth(left, { ...left, [key]: value })).toBe(false);
    });
});
