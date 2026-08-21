// PERCEPTUAL-FORMS-001E — the geometry, against the committed payloads.
//
// Every case here runs on a real fixture from `contracts/fixtures/perception-lab/forms/` rather
// than on a hand-made object, because the thing worth proving is that these renderers can draw
// the records the contract actually froze — not that they can draw the records a test author
// found convenient.

import { describe, it, expect } from 'vitest';
import {
    ringsFromRle, ringsFromBox, ringsFromRingPoints, ringsCentroid, fieldCells, thresholdCells,
    isoSegments, sweepStops, layoutTree, layoutGraph, adjacencyMatrix, examinationOf,
} from './formGeometry';
import { form } from '../contract/perceptionLabContract';
import { FORM_PAYLOADS, SCENARIOS } from './fixtures/formFixtures';

const P = FORM_PAYLOADS;

describe('masks, rings and boxes', () => {
    it('decodes the hard-mask RLE to exact boundary rings on its own raster', () => {
        const inst = P['extent.hard_mask'].instances[0];
        const g = ringsFromRle(inst.mask_rle);
        expect(g.raster).toEqual({ h: 8, w: 8 });
        expect(g.rings.length).toBeGreaterThan(0);
        expect(g.exact).toBe(true);
        // Every vertex is a pixel boundary of the 8×8 raster — an eighth, exactly. A ring whose
        // coordinates are not multiples of 1/8 has been smoothed or resampled by something.
        for (const ring of g.rings) {
            for (const [x, y] of ring) {
                expect(Math.abs(x * 8 - Math.round(x * 8))).toBeLessThan(1e-9);
                expect(Math.abs(y * 8 - Math.round(y * 8))).toBeLessThan(1e-9);
            }
        }
    });

    it('tells "no mask" apart from "an empty mask"', () => {
        // The second committed instance is box-only. Returning [] for it would make an instance
        // that was never masked look like one that was masked and found to cover nothing.
        expect(ringsFromRle(P['extent.hard_mask'].instances[1].mask_rle)).toBeNull();
        const empty = ringsFromRle({ size: [4, 4], counts: [16] });
        expect(empty).not.toBeNull();
        expect(empty.rings).toEqual([]);
    });

    it('draws a declared box as a closed four-point ring', () => {
        const g = ringsFromBox(P['extent.hard_mask'].instances[1].box);
        expect(g.rings[0]).toHaveLength(4);
        expect(g.centroid).toEqual({ x: 0.15000000000000002, y: 0.75 });
        expect(ringsFromBox(null)).toBeNull();
    });

    it('carries recorded ring points through untouched, with their winding', () => {
        // `extent.boundary_rings` exists precisely because the boundary is RECORDED rather than
        // traced here. Resampling it would erase the only difference from a hard mask.
        const b = P['extent.boundary_rings'].boundaries[0];
        const g = ringsFromRingPoints(b.rings);
        expect(g.rings).toEqual([
            [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
            [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]],
        ]);
        expect(g.windings).toEqual(['outer', 'inner']);
        expect(g.ring_ids).toEqual(['ring_outer', 'ring_void']);
    });

    it('refuses a ring set with nothing usable in it', () => {
        expect(ringsFromRingPoints([])).toBeNull();
        expect(ringsFromRingPoints([{ points: [[0, 0]] }])).toBeNull();
    });

    it('anchors a label at the mean vertex', () => {
        expect(ringsCentroid([[[0, 0], [1, 0], [1, 1], [0, 1]]])).toEqual({ x: 0.5, y: 0.5 });
        expect(ringsCentroid([])).toBeNull();
    });
});

describe('scalar fields', () => {
    const soft = P['extent.soft_field'].field;

    it('lays a 4×4 field out as sixteen cells, in the declared range', () => {
        const f = fieldCells(soft);
        expect(f.available).toBe(true);
        expect(f.cells).toHaveLength(16);
        expect(f.shape).toEqual({ h: 4, w: 4 });
        expect(f.range).toEqual({ lo: 0, hi: 1, declared: true });
        expect(f.derivation).toBe('direct_probability');
        expect(f.calibration.state).toBe('calibrated');
        // row-major, matching the payload's own ordering
        expect(f.cells[0]).toMatchObject({ row: 0, col: 0, value: 1, x: 0, y: 0, w: 0.25, h: 0.25 });
        expect(f.cells[15]).toMatchObject({ row: 3, col: 3, value: 0, intensity: 0 });
    });

    it('scales to the DECLARED range, not the observed one', () => {
        // A field whose values span 0.2–0.4 inside a declared 0–1 range is a flat field. Rescaling
        // it to its own span redraws it as a dramatic one, which is the most common way a wash
        // lies without any single number being wrong.
        const flat = { field_shape: [1, 2], value_range: [0, 1], derivation: 'manual_paint',
            inline_values: [0.2, 0.4] };
        const f = fieldCells(flat);
        expect(f.cells.map((c) => c.intensity)).toEqual([0.2, 0.4]);
        const undeclared = fieldCells({ ...flat, value_range: null });
        expect(undeclared.cells.map((c) => c.intensity)).toEqual([0, 1]);
        expect(undeclared.range.declared).toBe(false);
    });

    it('refuses a field held behind a data_ref instead of inventing a gradient', () => {
        const f = fieldCells(SCENARIOS['extent.soft_field'].withheld.field);
        expect(f.available).toBe(false);
        expect(f.shape).toEqual({ h: 4, w: 4 });
        expect(f.why).toMatch(/held behind data_ref/);
        expect(f.why).toMatch(/would be invented/);
    });

    it('refuses a shapeless field and a field with the wrong number of values', () => {
        expect(fieldCells(null).available).toBe(false);
        expect(fieldCells({ field_shape: [2, 2], inline_values: [1, 2] }).available).toBe(false);
        expect(fieldCells({ inline_values: [1] }).why).toMatch(/no shape/);
    });

    it('handles the non-square field the density form carries', () => {
        const f = fieldCells(P['extent.density_field'].field);
        expect(f.shape).toEqual({ h: 2, w: 3 });
        expect(f.cells).toHaveLength(6);
        expect(f.range).toEqual({ lo: 0, hi: 3, declared: true });
        expect(f.cells[2]).toMatchObject({ row: 0, col: 2, value: 1.8 });
    });
});

describe('thresholding a field', () => {
    const f = fieldCells(P['extent.soft_field'].field);

    it('carries the threshold out with the cells it made', () => {
        // There is no way to call this and end up holding binary cells without the number that
        // made them — which is half of why the "no mask without a threshold" rule is enforceable.
        const t = thresholdCells(f, 0.5, { source: 'threshold_would_be, from the payload' });
        expect(t.threshold).toEqual({ value: 0.5, source: 'threshold_would_be, from the payload',
            applied: true });
        expect(t.cells.every((c) => c.value >= 0.5)).toBe(true);
        expect(t.cells).toHaveLength(10);
        expect(t.excluded).toBe(6);
        expect(t.covered_fraction).toBeCloseTo(10 / 16, 10);
    });

    it('moves with the threshold', () => {
        expect(thresholdCells(f, 0.05).cells).toHaveLength(15);
        expect(thresholdCells(f, 1.01).cells).toHaveLength(0);
    });

    it('passes an unavailable field straight through as unavailable', () => {
        const withheld = fieldCells(SCENARIOS['extent.soft_field'].withheld.field);
        const t = thresholdCells(withheld, 0.5);
        expect(t.available).toBe(false);
        expect(t.threshold).toBeNull();
        expect(t.why).toMatch(/data_ref/);
    });
});

describe('isolines', () => {
    const f = fieldCells(P['extent.soft_field'].field);

    it('emits one short unjoined mark per crossing, not a smooth contour', () => {
        // A closed curve through sixteen numbers looks like a measured boundary. These are the
        // crossings and nothing else, which is exactly as much as a 4×4 field supports.
        const segs = isoSegments(f, [0.5]);
        expect(segs.length).toBeGreaterThan(0);
        for (const s of segs) {
            const len = Math.hypot(s.x2 - s.x1, s.y2 - s.y1);
            expect(len).toBeCloseTo(2 / (3 * 4), 10);
            expect(s.level).toBe(0.5);
        }
    });

    it('puts each crossing between the two cells that straddle the level', () => {
        const seg = isoSegments(fieldCells({
            field_shape: [1, 2], value_range: [0, 1], inline_values: [0, 1],
        }), [0.5]);
        expect(seg).toHaveLength(1);
        // cell centres at x = 0.25 and 0.75; the half-way crossing is at 0.5
        expect(seg[0].x1).toBeCloseTo(0.5, 10);
    });

    it('emits nothing for a level no pair straddles, and nothing for an absent field', () => {
        expect(isoSegments(f, [2])).toEqual([]);
        expect(isoSegments({ available: false }, [0.5])).toEqual([]);
    });

    it('offers deterministic sweep stops inside the declared range', () => {
        expect(sweepStops(f, 3)).toEqual([0.25, 0.5, 0.75]);
        expect(sweepStops(fieldCells(P['extent.density_field'].field), 2)).toEqual([1, 2]);
        expect(sweepStops({ available: false })).toEqual([]);
    });
});

describe('trees', () => {
    it('lays the committed hierarchy out by depth, in diagram space', () => {
        const t = layoutTree(P['extent.hierarchy'].nodes,
            { rootIds: P['extent.hierarchy'].root_node_ids });
        expect(t.nodes.map((n) => n.node_id)).toEqual(['palace', 'courtyard', 'garden', 'fountain']);
        expect(t.nodes.map((n) => n.depth)).toEqual([0, 1, 2, 3]);
        expect(t.depth).toBe(3);
        for (const n of t.nodes) {
            expect(n.x).toBeGreaterThanOrEqual(0);
            expect(n.x).toBeLessThanOrEqual(1);
            expect(n.y).toBeGreaterThanOrEqual(0);
            expect(n.y).toBeLessThanOrEqual(1);
        }
    });

    it('draws every tree edge directed, parent to child', () => {
        // A containment tree edge IS the claim: the parent contains the child. An undirected line
        // between them says only that they are related, which is a weaker and different finding.
        const t = layoutTree(P['topology.containment_tree'].nodes,
            { rootIds: P['topology.containment_tree'].root_node_ids });
        expect(t.edges).toHaveLength(2);
        expect(t.edges.every((e) => e.directed)).toBe(true);
        expect(t.edges.map((e) => `${e.source_node_id}->${e.target_node_id}`))
            .toEqual(['piazza->fountain', 'piazza->figures']);
        expect(t.edges[0].occupancy_of_parent).toBe(0.04);
    });

    it('reports a dangling parent instead of silently re-rooting the node', () => {
        const t = layoutTree([
            { node_id: 'a', parent_node_id: null },
            { node_id: 'b', parent_node_id: 'ghost' },
        ]);
        expect(t.dangling).toEqual([{ node_id: 'b', missing_parent: 'ghost' }]);
    });

    it('names nodes the declared roots never reach', () => {
        const t = layoutTree([
            { node_id: 'a', parent_node_id: null },
            { node_id: 'orphan', parent_node_id: null },
        ], { rootIds: ['a'] });
        expect(t.unreached).toEqual(['orphan']);
        expect(t.nodes.map((n) => n.node_id)).toEqual(['a']);
    });

    it('terminates on a cycle rather than recursing forever', () => {
        const t = layoutTree([
            { node_id: 'a', parent_node_id: 'b' },
            { node_id: 'b', parent_node_id: 'a' },
        ], { rootIds: ['a'] });
        expect(t.nodes.length).toBeLessThanOrEqual(2);
    });

    it('lays a fifteen-node dense tree out without collapsing it to one column', () => {
        const dense = SCENARIOS['topology.containment_tree'].dense;
        const t = layoutTree(dense.nodes, { rootIds: dense.root_node_ids });
        expect(t.nodes).toHaveLength(15);
        expect(new Set(t.nodes.map((n) => n.x)).size).toBeGreaterThan(4);
        expect(t.depth).toBeGreaterThanOrEqual(3);
    });
});

describe('graphs', () => {
    const g = P['topology.adjacency_graph'];

    it('places nodes on a deterministic circle in diagram space', () => {
        const a = layoutGraph(g.nodes, g.edges);
        const b = layoutGraph(g.nodes, g.edges);
        expect(a.nodes.map((n) => [n.x, n.y])).toEqual(b.nodes.map((n) => [n.x, n.y]));
        // A ring of evenly spaced nodes is visibly arbitrary, which is the correct impression:
        // a graph node has no location and a force layout would not be reproducible anyway.
        for (const n of a.nodes) {
            expect(Math.hypot(n.x - 0.5, n.y - 0.5)).toBeCloseTo(0.36, 10);
        }
    });

    it('counts degree, including the disjoint edge', () => {
        const a = layoutGraph(g.nodes, g.edges);
        expect(a.edges).toHaveLength(3);
        expect(a.nodes.map((n) => n.degree)).toEqual([2, 2, 2]);
        expect(a.isolated).toEqual([]);
    });

    it('reports an edge whose endpoint is not in the node list', () => {
        const a = layoutGraph(g.nodes, [...g.edges,
            { edge_id: 'ghost', source_node_id: 'pier_1', target_node_id: 'pier_9' }]);
        expect(a.dangling).toEqual([{ edge_id: 'ghost', missing: ['pier_9'] }]);
        expect(a.edges).toHaveLength(3);
    });

    it('names an isolated node rather than leaving it as empty space', () => {
        const a = layoutGraph([...g.nodes, { node_id: 'pier_4' }], g.edges);
        expect(a.isolated).toEqual(['pier_4']);
    });

    it('builds a matrix in which "examined and unrelated" is visible', () => {
        // Three nodes, three edges — but `pairs_examined` is 6. The node-link drawing renders the
        // other three as empty space, indistinguishable from "never checked". The matrix does not.
        const m = adjacencyMatrix(g.nodes, g.edges);
        expect(m.ids).toEqual(['pier_1', 'pier_2', 'pier_3']);
        expect(m.rows).toHaveLength(3);
        expect(m.rows[0].cells[0].self).toBe(true);
        expect(m.rows[0].cells[1].edge.kind).toBe('meets');
        expect(m.rows[1].cells[0].edge.kind).toBe('meets');   // undirected: filled both ways
        expect(m.rows[0].cells[2].edge.kind).toBe('disjoint');
        expect(m.recorded_edges).toBe(3);
        expect(g.pairs_examined).toBe(6);
    });
});

describe('every form can say it looked', () => {
    it('finds the counter on all nineteen payloads, at the field the contract names', () => {
        for (const [key, payload] of Object.entries(P)) {
            const e = examinationOf(payload, key);
            expect(e, key).not.toBeNull();
            expect(e.field, key).toBe(form(key).absence.examined_field);
            expect(e.empty_means, key).toBeTruthy();
        }
    });

    it('reads the counter each form uses, without re-typing the field name', () => {
        expect(examinationOf(P['extent.hard_mask'], 'extent.hard_mask')).toMatchObject({
            field: 'searched', label: 'searched',
            value: 'every separable instance in the whole image',
        });
        expect(examinationOf(P['topology.pair_relation'], 'topology.pair_relation'))
            .toMatchObject({ field: 'pairs_examined', label: 'pairs examined', value: 3 });
        expect(examinationOf(P['extent.density_field'], 'extent.density_field'))
            .toMatchObject({ field: 'members_counted', value: 3 });
    });

    it('counts a list-valued counter by its length and keeps the members', () => {
        // `topology.negative_space_field` names `figure_instance_ids`. "Two figures" and "which
        // two" are both part of what was examined, so both come back.
        const e = examinationOf(P['topology.negative_space_field'], 'topology.negative_space_field');
        expect(e).toMatchObject({ field: 'figure_instance_ids', value: 2 });
        expect(e.members).toEqual(['inst_left_building', 'inst_right_building']);
    });

    it('survives the empty scenario, which is the case it exists for', () => {
        const e = examinationOf(SCENARIOS['topology.pair_relation'].empty, 'topology.pair_relation');
        expect(e).toMatchObject({ field: 'pairs_examined', value: 3 });
        expect(e.empty_means).toMatch(/none stood in any/);
        expect(e.may_not_be_confused_with.length).toBeGreaterThan(0);
    });

    it('returns null when a payload does not carry the field its form declares', () => {
        expect(examinationOf({ variant: 'x' }, 'extent.hard_mask')).toBeNull();
        expect(examinationOf(P['extent.hard_mask'], null)).toBeNull();
    });
});
