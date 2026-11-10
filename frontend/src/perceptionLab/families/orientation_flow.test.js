import { describe, expect, it } from 'vitest';
import { SLOT } from './orientation_flow';
import { checkedFamilySlots } from './registry';
import { axisReading, coherenceView, headlessMarks, localCells } from './orientationVisual';

const data = { metadata: { kind: 'axial_orientation_2d', shape: [12, 20, 2] },
    preview: { shape: [12, 20, 2], stride: 1,
        values: Array.from({ length: 240 }, () => [.6, .8]).flat(),
        valid: Array.from({ length: 240 }, (_, i) => i !== 126) } };

describe('Orientation saved-field display and declaration', () => {
    it('registers independent tangent, coherence and energy forms and one bounded prompt', () => {
        expect(checkedFamilySlots().orientation_flow).toBe(SLOT);
        expect(SLOT.operations.map((operation) => operation.key)).toEqual([
            'orientation_flow.tangent', 'orientation_flow.coherence', 'orientation_flow.energy']);
        expect(SLOT.promptIntents).toEqual(['show local orientation']);
    });
    it('draws equal-length headless marks, preserves invalid support and saved numbers', () => {
        const before = JSON.stringify(data);
        const marks = headlessMarks(data, 12);
        expect(marks).toHaveLength(1); // (6,6) is invalid, (18,6) remains
        expect(Math.hypot(marks[0].x2 - marks[0].x1, marks[0].y2 - marks[0].y1)).toBeCloseTo(8.4);
        expect(marks[0].coherence).toBe(1);
        expect(coherenceView(data).preview.values[0]).toBe(1);
        expect(coherenceView(data).preview.valid[126]).toBe(false);
        expect(JSON.stringify(data)).toBe(before);
    });
    it('reads axial angle modulo 180 rather than treating the carrier as a directed vector', () => {
        expect(axisReading([0, 1]).degrees).toBe(45);
        expect(axisReading([-1, 0]).degrees).toBe(90);
        expect(axisReading(null)).toBeNull();
    });
    it('constructs exact bounded summary support, clipped to the saved grid', () => {
        expect(localCells(data, [0, 0], 1)).toEqual([[0, 0], [1, 0], [0, 1], [1, 1]]);
    });
});
