import { describe, it, expect } from 'vitest';
import {
    BRUSH_RANGE, BAND_RANGE, BRUSH_PRESETS, STEP_UP, STEP_DOWN,
    clampTo, positionToValue, valueToPosition, stepUp, stepDown,
    extentLabel, extentShort, presetFor,
} from './instrumentScale';

describe('the ranges are the ones the bracket keys already enforced', () => {
    it('keeps the brush range unchanged', () => {
        expect(BRUSH_RANGE).toEqual({ min: 0.012, max: 0.16 });
    });

    it('keeps the boundary band range unchanged', () => {
        expect(BAND_RANGE).toEqual({ min: 0.02, max: 0.2 });
    });

    it('keeps the bracket step factors unchanged', () => {
        expect(STEP_DOWN).toBe(0.82);
        expect(STEP_UP).toBe(1.22);
    });
});

describe('the slider mapping', () => {
    for (const [name, range] of [['brush', BRUSH_RANGE], ['band', BAND_RANGE]]) {
        it(`round-trips value↔position across the ${name} range`, () => {
            for (const t of [0, 0.13, 0.5, 0.87, 1]) {
                expect(valueToPosition(positionToValue(t, range), range)).toBeCloseTo(t, 9);
            }
        });

        it(`anchors the ${name} ends exactly`, () => {
            expect(positionToValue(0, range)).toBeCloseTo(range.min, 12);
            expect(positionToValue(1, range)).toBeCloseTo(range.max, 12);
            expect(valueToPosition(range.min, range)).toBe(0);
            expect(valueToPosition(range.max, range)).toBeCloseTo(1, 12);
        });

        it(`is monotonic across the ${name} range`, () => {
            let prev = -Infinity;
            for (let t = 0; t <= 1; t += 0.05) {
                const v = positionToValue(t, range);
                expect(v).toBeGreaterThan(prev);
                prev = v;
            }
        });
    }

    // The reason for the log mapping: on a linear track the fine decade would get
    // ~6% of the travel, which is where precise work at high zoom actually lives.
    it('gives the fine end far more travel than a linear track would', () => {
        const half = positionToValue(0.5, BRUSH_RANGE);
        const linearHalf = (BRUSH_RANGE.min + BRUSH_RANGE.max) / 2;
        expect(half).toBeLessThan(linearHalf);
        expect(half).toBeCloseTo(Math.sqrt(BRUSH_RANGE.min * BRUSH_RANGE.max), 9);
    });

    it('gives equal travel to equal ratio, so a step is always proportional', () => {
        const a = positionToValue(0.2, BRUSH_RANGE);
        const b = positionToValue(0.4, BRUSH_RANGE);
        const c = positionToValue(0.6, BRUSH_RANGE);
        expect(b / a).toBeCloseTo(c / b, 9);
    });

    it('clamps a position outside the track rather than extrapolating', () => {
        expect(positionToValue(-5, BRUSH_RANGE)).toBeCloseTo(BRUSH_RANGE.min, 12);
        expect(positionToValue(9, BRUSH_RANGE)).toBeCloseTo(BRUSH_RANGE.max, 12);
    });
});

describe('stepping matches the bracket keys and never escapes the range', () => {
    it('steps by the historical factors', () => {
        expect(stepDown(0.045, BRUSH_RANGE)).toBeCloseTo(0.045 * 0.82, 12);
        expect(stepUp(0.045, BRUSH_RANGE)).toBeCloseTo(0.045 * 1.22, 12);
    });

    it('cannot be driven below the floor or above the ceiling', () => {
        let v = 0.045;
        for (let i = 0; i < 50; i++) v = stepDown(v, BRUSH_RANGE);
        expect(v).toBe(BRUSH_RANGE.min);
        for (let i = 0; i < 50; i++) v = stepUp(v, BRUSH_RANGE);
        expect(v).toBe(BRUSH_RANGE.max);
    });

    it('clamps an out-of-range value on the way in', () => {
        expect(clampTo(99, BRUSH_RANGE)).toBe(BRUSH_RANGE.max);
        expect(clampTo(-1, BAND_RANGE)).toBe(BAND_RANGE.min);
    });
});

describe('the extent reads as a claim about the picture, not the screen', () => {
    it('is a percentage of image width', () => {
        expect(extentShort(0.045)).toBe('4.5%');
        expect(extentLabel(0.045)).toBe('4.5% of image width');
    });

    it('says "of image width" so it cannot be read as a pixel count', () => {
        // A pixel figure would change with the window; the stored datum does not.
        expect(extentLabel(0.012)).toContain('of image width');
    });
});

describe('presets are values in the same range, not a second vocabulary', () => {
    it('all sit inside the brush range', () => {
        for (const p of BRUSH_PRESETS) {
            expect(p.value).toBeGreaterThanOrEqual(BRUSH_RANGE.min);
            expect(p.value).toBeLessThanOrEqual(BRUSH_RANGE.max);
        }
    });

    it('ascend', () => {
        const vals = BRUSH_PRESETS.map((p) => p.value);
        expect(vals).toEqual([...vals].sort((a, b) => a - b));
    });

    it('report which one a value sits on, and null between them', () => {
        expect(presetFor(0.018)).toBe('fine');
        expect(presetFor(0.045)).toBe('medium');
        expect(presetFor(0.1)).toBe('broad');
        expect(presetFor(0.037)).toBeNull();
    });

    it('produce a record indistinguishable from a dragged slider', () => {
        // A preset is not a stored kind — it is just a value, so nothing downstream
        // can tell how the curator arrived at it.
        const dragged = positionToValue(valueToPosition(0.045, BRUSH_RANGE), BRUSH_RANGE);
        expect(dragged).toBeCloseTo(0.045, 12);
    });
});
