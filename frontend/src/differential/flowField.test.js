import { describe, it, expect } from 'vitest';
import { PRODUCERS } from './visualMarks';
import {
    FLOW_FIELD_KIND, isFlowField, normalizeFlowField, flowFieldCells, flowFieldStats, isAxialRole, AXIAL_TRACE_ROLES } from './flowField';

// A 2×2 flow_field: three live cells pointing right, one null cell.
const RIGHT = [1, 0, 1.0];
const NULL = [0, 0, 0];
const field2x2 = (cells) => ({ kind: FLOW_FIELD_KIND, cols: 2, rows: 2, cells });

describe('flowField — kind + validation', () => {
    it('isFlowField gates on the kind only', () => {
        expect(isFlowField({ kind: 'flow_field' })).toBe(true);
        expect(isFlowField({ kind: 'soft_mask' })).toBe(false);
        expect(isFlowField(null)).toBe(false);
    });

    it('normalizeFlowField accepts a well-formed field and re-unitizes directions', () => {
        const f = normalizeFlowField(field2x2([[3, 0, 0.5], RIGHT, RIGHT, NULL]));
        expect(f.cols).toBe(2);
        expect(f.rows).toBe(2);
        // [3,0,..] re-unitized to [1,0,..]
        expect(f.cells[0][0]).toBeCloseTo(1, 6);
        expect(f.cells[0][1]).toBeCloseTo(0, 6);
        expect(f.cells[0][2]).toBeCloseTo(0.5, 6);
    });

    it('collapses a zero-length or zero-magnitude cell to a null cell', () => {
        const f = normalizeFlowField(field2x2([[0, 0, 0.9], [1, 0, 0], RIGHT, RIGHT]));
        expect(f.cells[0]).toEqual([0, 0, 0]);   // no direction → null
        expect(f.cells[1]).toEqual([0, 0, 0]);   // no magnitude → null
    });

    it('clamps magnitude into [0,1]', () => {
        const f = normalizeFlowField(field2x2([[1, 0, 5], [1, 0, -2], RIGHT, RIGHT]));
        expect(f.cells[0][2]).toBe(1);
        expect(f.cells[1]).toEqual([0, 0, 0]);   // negative magnitude → null
    });

    it('refuses a malformed descriptor (bad dims / wrong count / bad cell)', () => {
        expect(normalizeFlowField({ kind: 'flow_field', cols: 0, rows: 2, cells: [] })).toBeNull();
        expect(normalizeFlowField(field2x2([RIGHT, RIGHT, RIGHT]))).toBeNull();   // 3 != 2*2
        expect(normalizeFlowField(field2x2([RIGHT, RIGHT, RIGHT, [1, 0]]))).toBeNull();   // short cell
        expect(normalizeFlowField({ kind: 'soft_mask' })).toBeNull();
    });
});

describe('flowField — drawable cells', () => {
    it('emits one sample per LIVE cell, at the cell centre, skipping null cells', () => {
        const cells = flowFieldCells(field2x2([RIGHT, RIGHT, RIGHT, NULL]));
        expect(cells).toHaveLength(3);                 // the null cell contributes nothing
        // first cell centre of a 2×2 lattice is (0.25, 0.25)
        expect(cells[0].cx).toBeCloseTo(0.25, 6);
        expect(cells[0].cy).toBeCloseTo(0.25, 6);
        expect(cells[0].dx).toBeCloseTo(1, 6);
        expect(cells[0].m).toBeCloseTo(1, 6);
    });

    it('returns [] for a missing or all-null field', () => {
        expect(flowFieldCells(null)).toEqual([]);
        expect(flowFieldCells(field2x2([NULL, NULL, NULL, NULL]))).toEqual([]);
    });
});

describe('flowField — stats (a reading, not geometry)', () => {
    it('coherence ~1 for parallel arrows, ~0 for opposed', () => {
        const parallel = flowFieldStats(field2x2([RIGHT, RIGHT, RIGHT, RIGHT]));
        expect(parallel.active).toBe(4);
        expect(parallel.coherence).toBeCloseTo(1, 4);

        const opposed = flowFieldStats(field2x2([[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1]]));
        expect(opposed.coherence).toBeLessThan(0.1);
    });

    it('counts total and active cells and reports mean magnitude', () => {
        const s = flowFieldStats(field2x2([[1, 0, 0.4], [1, 0, 0.6], RIGHT, NULL]));
        expect(s.cells).toBe(4);
        expect(s.active).toBe(3);
        expect(s.meanMagnitude).toBeCloseTo((0.4 + 0.6 + 1) / 3, 4);
    });

    it('is safe on a bad field', () => {
        expect(flowFieldStats(null)).toEqual({ cells: 0, active: 0, meanMagnitude: 0, coherence: 0 });
    });
});

describe('flowField — TRACE-002: axial vs directional roles', () => {
    it('both trace-lane orientation roles are axial', () => {
        expect(isAxialRole('architectural_axis')).toBe(true);
        expect(isAxialRole('external_limit')).toBe(true);
    });

    it('fall_of_light stays directional — the arrowhead is its content', () => {
        expect(isAxialRole('fall_of_light')).toBe(false);
    });

    it('an unknown or absent role is not assumed axial', () => {
        // Defaulting to axial would silently drop arrowheads from a future directional trace.
        expect(isAxialRole('gaze_address')).toBe(false);
        expect(isAxialRole(undefined)).toBe(false);
    });
});

describe('flowField — MOUNT-001: every flow_field producer is a known producer', () => {
    it('a producer that mints flow_field marks must be in the mark vocabulary', () => {
        // The bug this pins: validateMark REJECTS an unknown provenance.producer, so a producer
        // missing from PRODUCERS can mint marks the store will never accept — invisible, with no
        // loud failure anywhere between the backend producing it and the canvas not drawing it.
        for (const producer of ['fall_of_light', 'architectural_axis', 'external_limit']) {
            expect(PRODUCERS, `${producer} mints flow_field marks`).toContain(producer);
        }
    });

    it('every axial role has a producer of the same name', () => {
        // architectural_axis and external_limit are both role AND producer names; a mismatch
        // would render nothing while looking correct in the capability map.
        for (const role of AXIAL_TRACE_ROLES) expect(PRODUCERS).toContain(role);
    });
});
