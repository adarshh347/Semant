// PERCEPTUAL-ORGANS-002 Lane E — the raster layer, which every drawn mask depends on.
//
// If `decodeRle` is wrong the laboratory shows a person a shape that is not the measurement, and
// every honesty claim above it is decoration. These are the arithmetic tests; the DOM suites
// assume they hold.

import { describe, it, expect } from 'vitest';
import {
    decodeRle, encodeRle, rleFillsRaster, emptyRaster, maskRings, maskArea, maskAreaFraction,
    maskAnd, maskOr, maskSub, maskNot, dilate, maskCentroid, maskBox, nearestPair,
} from './maskRaster';

/** A raster from ASCII rows — '#' is on. Readable fixtures beat hand-counted RLE. */
const raster = (rows) => {
    const h = rows.length;
    const w = rows[0].length;
    const m = emptyRaster(h, w);
    rows.forEach((row, r) => [...row].forEach((ch, c) => { m.data[r * w + c] = ch === '#' ? 1 : 0; }));
    return m;
};

const rowsOf = (m) => Array.from({ length: m.h }, (_, r) => Array.from(
    { length: m.w }, (_, c) => (m.data[r * m.w + c] ? '#' : '.')).join(''));

describe('decodeRle — column-major runs, first run zeros', () => {
    it('decodes a single column run into the right pixels', () => {
        // 3 rows × 4 cols. Skip 3 (all of column 0), then 3 on (all of column 1).
        const m = decodeRle({ size: [3, 4], counts: [3, 3, 6] });
        expect(rowsOf(m)).toEqual(['.#..', '.#..', '.#..']);
    });

    it('decodes a run that crosses a column boundary', () => {
        // Skip 2, then 3 on: rows 2 of col 0, then rows 0-1 of col 1.
        const m = decodeRle({ size: [3, 2], counts: [2, 3, 1] });
        expect(rowsOf(m)).toEqual(['.#', '.#', '#.']);
    });

    it('round-trips any raster through encode → decode', () => {
        const m = raster(['..##..', '.####.', '.#..#.', '.####.']);
        expect(rowsOf(decodeRle(encodeRle(m)))).toEqual(rowsOf(m));
    });

    it('leaves the remainder zero when the counts do not fill the raster, and says so', () => {
        // The Lane A extent fixture is exactly this shape: 6 short runs in a 1200x1600 frame.
        const rle = { size: [1200, 1600], counts: [0, 240, 1420, 260, 1400, 280] };
        expect(rleFillsRaster(rle)).toBe(false);
        const m = decodeRle(rle);
        expect(maskArea(m)).toBe(240 + 260 + 280);
        expect(rleFillsRaster(encodeRle(m))).toBe(true);
    });

    it('clips an overshooting run instead of writing out of bounds', () => {
        const m = decodeRle({ size: [2, 2], counts: [0, 9999] });
        expect(maskArea(m)).toBe(4);
    });

    it('returns null for something that is not an RLE', () => {
        expect(decodeRle(null)).toBe(null);
        expect(decodeRle({ size: [0, 0], counts: [] })).toBe(null);
        expect(decodeRle({ counts: [1] })).toBe(null);
    });
});

describe('maskRings — the exact pixel boundary', () => {
    it('traces one square as one ring of four corners, in normalized coords', () => {
        const m = raster(['....', '.##.', '.##.', '....']);
        const rings = maskRings(m);
        expect(rings).toHaveLength(1);
        expect(rings[0]).toHaveLength(4);
        expect(rings[0]).toEqual(expect.arrayContaining([[0.25, 0.25], [0.75, 0.75]]));
    });

    it('emits a second ring for a hole, which evenodd then cuts out', () => {
        const m = raster(['#####', '#...#', '#.#.#', '#...#', '#####']);
        const rings = maskRings(m);
        // outer boundary, the hole around the centre dot, and the dot itself
        expect(rings.length).toBeGreaterThanOrEqual(3);
    });

    it('emits one ring per disconnected component', () => {
        const m = raster(['#..#', '#..#', '....']);
        expect(maskRings(m)).toHaveLength(2);
    });

    it('merges collinear vertices without moving the boundary', () => {
        const wide = raster(['######', '######']);
        const rings = maskRings(wide);
        expect(rings[0]).toHaveLength(4);              // not 16
        const xs = rings[0].map(([x]) => x);
        const ys = rings[0].map(([, y]) => y);
        expect(Math.min(...xs)).toBe(0);
        expect(Math.max(...xs)).toBe(1);
        expect(Math.min(...ys)).toBe(0);
        expect(Math.max(...ys)).toBe(1);
    });

    it('gives an empty mask no rings at all — nothing is drawn for nothing', () => {
        expect(maskRings(raster(['...', '...']))).toEqual([]);
        expect(maskRings(null)).toEqual([]);
    });

    it('normalizes against the RASTER, so a coarse mask still lands on the image', () => {
        const coarse = raster(['##', '##']);            // 2×2 raster, fully on
        const fine = raster(['####', '####', '####', '####']);
        expect(maskRings(coarse)).toEqual(maskRings(fine));
    });
});

describe('set arithmetic', () => {
    const a = raster(['##.', '##.']);
    const b = raster(['.##', '.##']);

    it('and / or / sub / not', () => {
        expect(rowsOf(maskAnd(a, b))).toEqual(['.#.', '.#.']);
        expect(rowsOf(maskOr(a, b))).toEqual(['###', '###']);
        expect(rowsOf(maskSub(a, b))).toEqual(['#..', '#..']);
        expect(rowsOf(maskNot(a))).toEqual(['..#', '..#']);
    });

    it('refuses to combine rasters of different shapes rather than resampling one', () => {
        expect(maskAnd(a, raster(['#']))).toBe(null);
        expect(maskSub(a, raster(['#']))).toBe(null);
    });

    it('area and area fraction', () => {
        expect(maskArea(a)).toBe(4);
        expect(maskAreaFraction(a)).toBeCloseTo(4 / 6);
    });
});

describe('dilate', () => {
    it('grows by r in every direction and clips at the border', () => {
        const m = raster(['...', '.#.', '...']);
        expect(rowsOf(dilate(m, 1))).toEqual(['###', '###', '###']);
    });
    it('r=0 is a copy, not the same buffer', () => {
        const m = raster(['#.']);
        const d = dilate(m, 0);
        d.data[1] = 1;
        expect(m.data[1]).toBe(0);
    });
});

describe('centroid, box and nearest pair', () => {
    it('centroid of a centred square is the centre', () => {
        expect(maskCentroid(raster(['....', '.##.', '.##.', '....']))).toEqual({ x: 0.5, y: 0.5 });
    });
    it('an empty mask has no centroid and no box', () => {
        expect(maskCentroid(raster(['..']))).toBe(null);
        expect(maskBox(raster(['..']))).toBe(null);
    });
    it('the box is the tight bound, and over-states a diagonal shape', () => {
        const diag = raster(['#..', '.#.', '..#']);
        expect(maskBox(diag)).toEqual({ x: 0, y: 0, w: 1, h: 1 });
        expect(maskAreaFraction(diag)).toBeCloseTo(3 / 9);
    });
    it('nearest pair measures the real gap between two shapes', () => {
        const a = raster(['#....', '#....']);
        const b = raster(['....#', '....#']);
        const near = nearestPair(a, b);
        // Centre-to-centre, which is the length of the line the surface actually draws. The
        // three empty pixels between them are the gap; the drawn segment spans four.
        expect(near.distance_px).toBe(4);
        expect(near.from.x).toBeCloseTo(0.1);
        expect(near.to.x).toBeCloseTo(0.9);
    });
    it('nearest pair refuses across rasters and on an empty mask', () => {
        expect(nearestPair(raster(['#.']), raster(['#']))).toBe(null);
        expect(nearestPair(raster(['#.']), raster(['..']))).toBe(null);
    });
});
