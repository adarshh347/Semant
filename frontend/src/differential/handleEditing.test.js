import { describe, it, expect } from 'vitest';
import {
    hitAnchor, hitSegment, projectOnSegment, moveAnchor, insertAnchor,
    removeAnchor, translatePoints, scalePoints, pointsBBox,
    editablePoints, withEditedPoints, syncAnchors, applyPointEdit, isEditableGround,
    anchorForEndpoint,
} from './handleEditing';
import { makeVisualMark } from './visualMarks';

const line = [[0.2, 0.2], [0.5, 0.5], [0.8, 0.2]];

describe('hit testing on normalized geometry', () => {
    it('grabs the nearest anchor within tolerance, none outside', () => {
        expect(hitAnchor(line, [0.51, 0.49], 0.05)).toBe(1);
        expect(hitAnchor(line, [0.5, 0.9], 0.05)).toBe(-1);
    });

    it('aspect correction matches x and y tolerances in pixels', () => {
        const pts = [[0.5, 0.5]];
        expect(hitAnchor(pts, [0.53, 0.5], 0.04, 1.5)).toBe(-1);   // 0.045 px-equiv
        expect(hitAnchor(pts, [0.5, 0.53], 0.04, 1.5)).toBe(0);    // 0.03 px-equiv
    });

    it('finds the segment under the pointer and snaps onto it', () => {
        const hit = hitSegment(line, [0.35, 0.36], 0.05);
        expect(hit.index).toBe(0);
        expect(hit.at).toEqual(projectOnSegment([0.35, 0.36], line[0], line[1]).at);
    });
});

describe('edit operations preserve normalized invariants', () => {
    it('moveAnchor clamps to [0,1] and preserves pressure', () => {
        expect(moveAnchor([[0.2, 0.2, 0.5], [0.8, 0.8, 0.9]], 0, [1.4, -0.3])).toEqual([[1, 0, 0.5], [0.8, 0.8, 0.9]]);
    });

    it('insertAnchor interpolates pressure so the ribbon does not pinch', () => {
        const out = insertAnchor([[0, 0, 0.2], [1, 1, 0.8]], 0, [0.5, 0.5], 0.5);
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
        expect(tr[0][0]).toBeCloseTo(0.3, 9); expect(tr[0][2]).toBe(0.5);
        const bb = pointsBBox(p);
        const scaled = scalePoints(p, [bb.x, bb.y], 2, 2);
        expect(scaled[0]).toEqual([0.2, 0.2, 0.5]);   // origin fixed
        expect(scaled[1][2]).toBe(0.7);               // pressure kept
    });
});

describe('the Transformer answer: scale is a point rewrite, not a scaleX', () => {
    it('scalePoints bakes the transform into the stored points', () => {
        const grown = scalePoints([[0.2, 0.2], [0.4, 0.6]], [0.2, 0.2], 1.5, 1.5);
        expect(grown[1]).toEqual([0.5, 0.8]);
        expect(JSON.stringify(grown)).not.toMatch(/scale/i);
    });
});

describe('adapter reads/writes both Grounds and marks', () => {
    it('a path Ground exposes its points and writes them back', () => {
        const ground = { id: 'gnd_1', ground_type: 'path', points: line };
        expect(isEditableGround(ground)).toBe(true);
        expect(editablePoints(ground)).toBe(line);
        const moved = withEditedPoints(ground, moveAnchor(line, 2, [0.9, 0.1]));
        expect(moved.ground_type).toBe('path');
        expect(moved.points[2]).toEqual([0.9, 0.1]);
        expect(moved).not.toBe(ground);
    });

    it('a boundary Ground is editable; a field Ground is not', () => {
        expect(isEditableGround({ ground_type: 'boundary', points: line })).toBe(true);
        expect(isEditableGround({ ground_type: 'field', strokes: [] })).toBe(false);
    });

    it('a mark with polyline geometry edits through geometry', () => {
        const mark = makeVisualMark('trace_mark', { role: 'gaze_address', geometry: { kind: 'polyline', points: line } });
        expect(editablePoints(mark)).toBe(line);
        const out = withEditedPoints(mark, moveAnchor(line, 0, [0.1, 0.1]));
        expect(out.geometry.kind).toBe('polyline');
        expect(out.geometry.points[0]).toEqual([0.1, 0.1]);
    });

    it('a vector mark edits as a two-point line and writes from/to', () => {
        const g = { kind: 'vector', from: [0.1, 0.1], to: [0.9, 0.9] };
        expect(editablePoints(g)).toEqual([[0.1, 0.1], [0.9, 0.9]]);
        expect(withEditedPoints(g, [[0.1, 0.1], [0.7, 0.5]])).toEqual({ kind: 'vector', from: [0.1, 0.1], to: [0.7, 0.5] });
    });
});

describe('anchor sync makes ref detachment visible (contract v2 #1)', () => {
    it('a point anchor follows the endpoint, no flag', () => {
        const a = { from: { kind: 'point', ref: null, at: [0, 0] }, to: { kind: 'point', ref: null, at: [1, 1] } };
        const synced = syncAnchors(a, [[0, 0], [0.8, 0.6]]);
        expect(synced.to.at).toEqual([0.8, 0.6]);
        expect(synced.to.detached_from_ref).toBeUndefined();
    });

    it('dragging a ground-anchored endpoint sets detached_from_ref, keeps ref', () => {
        const a = { from: { kind: 'ground', ref: 'gnd_x', at: [0.2, 0.2] }, to: null };
        const synced = syncAnchors(a, [[0.5, 0.5], [1, 1]]);
        expect(synced.from.ref).toBe('gnd_x');
        expect(synced.from.at).toEqual([0.5, 0.5]);
        expect(synced.from.detached_from_ref).toBe(true);
    });

    it('applyPointEdit bumps updated_at and re-syncs anchors', () => {
        const mark = makeVisualMark('trace_mark', {
            role: 'gaze_address',
            geometry: { kind: 'polyline', points: [[0.1, 0.1], [0.9, 0.9]] },
        });
        mark.anchors = { from: { kind: 'ground', ref: 'gnd_z', at: [0.1, 0.1] }, to: null };
        const out = applyPointEdit(mark, [[0.3, 0.2], [0.9, 0.9]], { now: '2026-07-23T00:00:00Z' });
        expect(out.geometry.points[0]).toEqual([0.3, 0.2]);
        expect(out.anchors.from.detached_from_ref).toBe(true);
        expect(out.updated_at).toBe('2026-07-23T00:00:00Z');
    });
});

// ── CIRCUIT-001 P3-B (2a) — endpoint ref-anchoring ────────────────────────────
describe('anchorForEndpoint resolves a trace endpoint onto a reference', () => {
    const cands = [
        { kind: 'ground', ref: 'gnd_a', at: [0.30, 0.30] },
        { kind: 'region', ref: 'reg_b', at: [0.70, 0.70] },
    ];

    it('anchors to the nearest candidate within tolerance, freezing at to the endpoint', () => {
        const a = anchorForEndpoint([0.31, 0.29], cands, 0.05);
        expect(a.kind).toBe('ground');
        expect(a.ref).toBe('gnd_a');
        // `at` is the endpoint itself, not the candidate's cached centre.
        expect(a.at).toEqual([0.31, 0.29]);
    });

    it('picks the closer of two candidates', () => {
        const a = anchorForEndpoint([0.68, 0.72], cands, 0.1);
        expect(a.ref).toBe('reg_b');
    });

    it('an endpoint far from everything anchors to ITSELF (kind:point), never a wrong ref', () => {
        const a = anchorForEndpoint([0.02, 0.98], cands, 0.04);
        expect(a.kind).toBe('point');
        expect(a.ref).toBeUndefined();
        expect(a.at).toEqual([0.02, 0.98]);
    });

    it('a point anchor can later be promoted, and dragging away from a ref detaches it', () => {
        // land on the ground → ref anchor; then drag the endpoint away → detached.
        const landed = anchorForEndpoint([0.30, 0.30], cands, 0.05);
        expect(landed.kind).toBe('ground');
        const synced = syncAnchors({ from: landed, to: null }, [[0.6, 0.6], [1, 1]]);
        expect(synced.from.ref).toBe('gnd_a');
        expect(synced.from.detached_from_ref).toBe(true);
    });
});
