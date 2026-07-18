import { describe, it, expect } from 'vitest';
import { polylineLength, taperedRibbon, centerlinePath, endChevron } from './freehandTaper.js';

const line = [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]]; // straight horizontal

describe('polylineLength', () => {
    it('sums segment lengths and returns cumulative offsets', () => {
        const { cum, total } = polylineLength(line);
        expect(total).toBeCloseTo(0.8);
        expect(cum).toEqual([0, expect.closeTo(0.4), expect.closeTo(0.8)]);
    });
    it('accepts {x,y} points too', () => {
        const { total } = polylineLength([{ x: 0, y: 0 }, { x: 0, y: 1 }]);
        expect(total).toBeCloseTo(1);
    });
});

describe('taperedRibbon', () => {
    it('produces a closed path with move + close', () => {
        const d = taperedRibbon(line, { maxWidth: 0.02 });
        expect(d.startsWith('M')).toBe(true);
        expect(d.trim().endsWith('Z')).toBe(true);
    });
    it('is empty for a degenerate (single-point) input', () => {
        expect(taperedRibbon([[0.5, 0.5]])).toBe('');
    });
});

describe('centerlinePath', () => {
    it('emits one M then Ls through the points', () => {
        const d = centerlinePath(line);
        expect(d).toMatch(/^M/);
        expect((d.match(/L/g) || []).length).toBe(2);
    });
});

describe('endChevron', () => {
    it('draws a two-legged arrowhead at the head, pointing along travel', () => {
        const d = endChevron(line, 0.03);
        // head is the last point (0.9, 0.5); the chevron passes through it
        expect(d).toContain('0.9000,0.5000');
        expect(d.split('L').length).toBe(3); // M l L head L r
    });
    it('is empty when there is no direction to point', () => {
        expect(endChevron([[0.5, 0.5]])).toBe('');
    });
});
