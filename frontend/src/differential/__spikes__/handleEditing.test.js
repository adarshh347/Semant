import { describe, it, expect } from 'vitest';
import {
    hitAnchor, hitSegment, projectOnSegment, moveAnchor, insertAnchor,
    removeAnchor, translatePoints, scalePoints, pointsBBox,
    editablePoints, withEditedPoints, syncAnchors, applyPointEdit,
} from './handleEditing';
import { makeTraceMark, makeAnchor, serializeMark } from './visualMarkContract';

const line = [[0.2, 0.2], [0.5, 0.5], [0.8, 0.2]];

describe('hit testing on normalized geometry', () => {
    it('grabs the nearest anchor within tolerance, none outside', () => {
        expect(hitAnchor(line, [0.51, 0.49], 0.05)).toBe(1);
        expect(hitAnchor(line, [0.5, 0.9], 0.05)).toBe(-1);
    });

    it('aspect correction makes x and y tolerances match in pixels', () => {
        // On a 3:2 image (aspect 1.5), a point 0.03 away in x is 1.5× the pixels
        // of 0.03 in y. With correction, the x-offset point falls outside a tol
        // that the equal y-offset point sits inside.
        const pts = [[0.5, 0.5]];
        expect(hitAnchor(pts, [0.53, 0.5], 0.04, 1.5)).toBe(-1);   // 0.045 px-equiv
        expect(hitAnchor(pts, [0.5, 0.53], 0.04, 1.5)).toBe(0);    // 0.03 px-equiv
    });

    it('finds the segment under the pointer and snaps onto it', () => {
        const hit = hitSegment(line, [0.35, 0.36], 0.05);
        expect(hit.index).toBe(0);
        // snapped point sits ON segment 0, not at the raw pointer
        const pr = projectOnSegment([0.35, 0.36], line[0], line[1]);
        expect(hit.at).toEqual(pr.at);
    });
});

describe('edit operations preserve normalized invariants', () => {
    it('moveAnchor clamps to [0,1] and preserves pressure', () => {
        const p = [[0.2, 0.2, 0.5], [0.8, 0.8, 0.9]];
        const moved = moveAnchor(p, 0, [1.4, -0.3]);
        expect(moved[0]).toEqual([1, 0, 0.5]);
    });

    it('insertAnchor interpolates pressure so the ribbon does not pinch', () => {
        const p = [[0, 0, 0.2], [1, 1, 0.8]];
        const out = insertAnchor(p, 0, [0.5, 0.5], 0.5);
        expect(out).toHaveLength(3);
        expect(out[1][2]).toBeCloseTo(0.5, 6);
    });

    it('removeAnchor refuses to go below two points', () => {
        expect(removeAnchor([[0, 0], [1, 1]], 0)).toHaveLength(2);
        expect(removeAnchor(line, 1)).toHaveLength(2);
    });

    it('translate and scale stay in range and keep pressure', () => {
        const p = [[0.2, 0.2, 0.5], [0.6, 0.6, 0.7]];
        const tr = translatePoints(p, 0.1, -0.1);
        expect(tr[0][0]).toBeCloseTo(0.3, 9); expect(tr[0][1]).toBeCloseTo(0.1, 9); expect(tr[0][2]).toBe(0.5);
        expect(tr[1][0]).toBeCloseTo(0.7, 9); expect(tr[1][1]).toBeCloseTo(0.5, 9); expect(tr[1][2]).toBe(0.7);
        const bb = pointsBBox(p);
        const scaled = scalePoints(p, [bb.x, bb.y], 2, 2);
        expect(scaled[0]).toEqual([0.2, 0.2, 0.5]);              // origin fixed
        expect(scaled[1][2]).toBe(0.7);                          // pressure kept
    });
});

describe('Transformer answer: a scale is a point rewrite, not a scaleX factor', () => {
    it('scalePoints bakes the transform into the stored points immediately', () => {
        const mark = makeTraceMark({
            geometry: { kind: 'polyline', points: [[0.2, 0.2], [0.4, 0.6]] },
        });
        const bb = pointsBBox(mark.geometry.points);
        const grown = scalePoints(mark.geometry.points, [bb.x, bb.y], 1.5, 1.5);
        const edited = applyPointEdit(mark, grown);
        const out = serializeMark(edited);
        // The serialized mark carries the new coordinates directly — there is no
        // scaleX/scaleY anywhere in the record to forget to bake.
        expect(JSON.stringify(out)).not.toMatch(/scale/i);
        expect(out.geometry.points[1]).toEqual([0.5, 0.8]);
    });
});

describe('geometry adapter unifies vector and polyline editing', () => {
    it('a vector edits as a two-point line and writes back to from/to', () => {
        const g = { kind: 'vector', from: [0.1, 0.1], to: [0.9, 0.9] };
        const pts = editablePoints(g);
        expect(pts).toEqual([[0.1, 0.1], [0.9, 0.9]]);
        const moved = moveAnchor(pts, 1, [0.7, 0.5]);
        expect(withEditedPoints(g, moved)).toEqual({ kind: 'vector', from: [0.1, 0.1], to: [0.7, 0.5] });
    });
});

describe('anchor sync makes ref detachment visible', () => {
    it('a point anchor follows the endpoint', () => {
        const a = { from: makeAnchor('point', null, [0, 0]), to: makeAnchor('point', null, [1, 1]) };
        const synced = syncAnchors(a, [[0, 0], [0.8, 0.6]]);
        expect(synced.to.at).toEqual([0.8, 0.6]);
        expect(synced.to.detached_from_ref).toBeUndefined();
    });

    it('dragging a ground-anchored endpoint marks it detached, ref preserved', () => {
        const a = { from: makeAnchor('ground', 'gnd_x', [0.2, 0.2]), to: null };
        const synced = syncAnchors(a, [[0.5, 0.5], [1, 1]]);
        expect(synced.from.ref).toBe('gnd_x');           // ref survives
        expect(synced.from.at).toEqual([0.5, 0.5]);       // position updated
        expect(synced.from.detached_from_ref).toBe(true); // and it SAYS so
    });
});
