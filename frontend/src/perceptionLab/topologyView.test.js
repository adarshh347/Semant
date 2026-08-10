// PERCEPTUAL-ORGANS-002 Lane E — typed relations stay typed, and endpoints resolve or say why.
//
// The suite is arranged around the two failures a topology surface is most likely to commit:
// losing the DIRECTION by rendering a typed relation as free text, and drawing a picture that is
// not the measurement without saying so.

import { describe, it, expect } from 'vitest';
import {
    DIRECTED_KINDS, PROJECTION_FOR_KIND, agreementFor, projectNegativeSpace, projectRelation,
    projectRelationSet, relationGraph, relationSentence, resolveEndpoint,
} from './topologyView';
import { encodeRle } from './geometry/maskRaster';
import { rasterizeShape } from './fixtures/scenes';
import { RELATION_KINDS } from './contract/perceptionLabContract';

const mask = (shape, h = 40, w = 40) => rasterizeShape(shape, h, w);

const extentSet = (id, instances) => ({
    identity: { artifact_id: id, artifact_kind: 'extent_set', identity_scope: 'session',
        derived_from: [], run_id: 'run_1', operation: 'extent.find_all' },
    measurement: { payload: { variant: 'extent_set', searched: 'shapes', instances,
        dropped_below_min_area: null, duplicates: [], comparison: null } },
    provenance: { completed_at: null, started_at: null },
});

const inst = (id, shape, extra = {}) => ({
    instance_id: id, mask_rle: encodeRle(mask(shape)), box: null, area: null, confidence: null,
    naming: null, region_id: null, geometry_rev: null, ...extra,
});

const ref = (artifact_id, instance_id, extra = {}) => ({
    artifact_id, instance_id, scope: 'session', region_id: null, geometry_rev: null, ...extra });

const relation = (kind, source, target, extra = {}) => ({
    relation_id: 'rel_1', kind, source, target,
    directed: DIRECTED_KINDS.has(kind), basis: 'mask', epistemic_status: 'measured',
    measurements: {}, stale: false, ...extra,
});

const outer = { kind: 'rect', x: 0.1, y: 0.1, w: 0.5, h: 0.5 };
const inner = { kind: 'rect', x: 0.2, y: 0.2, w: 0.2, h: 0.2 };
const touching = { kind: 'rect', x: 0.6, y: 0.1, w: 0.2, h: 0.5 };
const far = { kind: 'rect', x: 0.85, y: 0.85, w: 0.1, h: 0.1 };

const ledger = new Map([['art_1', extentSet('art_1', [
    inst('ext_outer', outer), inst('ext_inner', inner),
    inst('ext_touch', touching), inst('ext_far', far),
])]]);

describe('a typed relation keeps its type and its direction', () => {
    it('every declared relation kind has its own sentence', () => {
        for (const kind of RELATION_KINDS) {
            const s = relationSentence(kind, 'A', 'B');
            expect(s, kind).toBeTruthy();
            expect(s).toContain('A');
            expect(s).toContain('B');
        }
    });

    it('the sentences are distinct — no two kinds read the same', () => {
        const sentences = RELATION_KINDS.map((k) => relationSentence(k, 'A', 'B'));
        expect(new Set(sentences).size).toBe(RELATION_KINDS.length);
    });

    it('direction is in the words, not only in an arrowhead', () => {
        expect(relationSentence('nested_within', 'the disc', 'the frame'))
            .toBe('the disc is inside the frame');
        expect(relationSentence('contains', 'the disc', 'the frame'))
            .toBe('the disc contains the frame');
        // Reversing the endpoints reverses the claim, which is the whole point of a typed
        // directed relation and exactly what free text destroys.
        expect(relationSentence('nested_within', 'A', 'B'))
            .not.toBe(relationSentence('nested_within', 'B', 'A'));
    });

    it('an unknown kind throws rather than rendering generically', () => {
        expect(() => relationSentence('vaguely_near', 'A', 'B'))
            .toThrow(/rendered as generic text loses the one thing it measured/);
    });

    it('only the genuinely directed kinds are directed', () => {
        expect([...DIRECTED_KINDS].sort())
            .toEqual(['contains', 'in_front_of', 'nested_within']);
        expect(DIRECTED_KINDS.has('meets')).toBe(false);
        expect(DIRECTED_KINDS.has('overlaps')).toBe(false);
    });

    it('every relation kind asks for a declared projection', () => {
        for (const kind of RELATION_KINDS) {
            expect(PROJECTION_FOR_KIND[kind], kind).toBeTruthy();
        }
    });
});

describe('an endpoint resolves, or says exactly how it did not', () => {
    it('resolves an instance to its mask and its name', () => {
        const e = resolveEndpoint(ref('art_1', 'ext_inner'), ledger);
        expect(e.state).toBe('resolved');
        expect(e.mask).toBeTruthy();
        expect(e.name).toBe('ext_inner');
    });

    it('an artifact that has left the ledger is dangling, not absent', () => {
        const e = resolveEndpoint(ref('art_gone', 'ext_1'), ledger);
        expect(e.state).toBe('dangling');
        expect(e.why).toMatch(/is not in this session's ledger/);
        expect(e.why).toMatch(/no longer here/);
    });

    it('an instance that has left its artifact is dangling too, and names itself', () => {
        const e = resolveEndpoint(ref('art_1', 'ext_vanished'), ledger);
        expect(e.state).toBe('dangling');
        expect(e.why).toMatch(/ext_vanished is no longer an instance of art_1/);
    });

    it('a geometry revision that moved makes the endpoint stale, not wrong', () => {
        const revised = new Map([['art_1', extentSet('art_1', [
            inst('ext_inner', inner, { region_id: 'reg_1', geometry_rev: 4 })])]]);
        const e = resolveEndpoint(ref('art_1', 'ext_inner', { geometry_rev: 2 }), revised);
        expect(e.state).toBe('stale');
        expect(e.mask).toBeTruthy();      // still drawable — the boundary just is not the one measured
        expect(e.why).toMatch(/measured at revision 2 and is now at 4/);
    });
});

describe('the projection is a drawing of the measurement, and says so', () => {
    it('a containment gets an endpoint pair with a direction', () => {
        const p = projectRelation(
            relation('nested_within', ref('art_1', 'ext_inner'), ref('art_1', 'ext_outer')),
            ledger);
        expect(p.drawable).toBe(true);
        expect(p.projection.projection_kind).toBe('endpoint_pair');
        expect(p.projection.derived).toBe(true);
        expect(p.projection.computed_by).toBe('lab_browser');
        expect(p.directed).toBe(true);
        expect(p.sentence).toBe('ext_inner is inside ext_outer');
    });

    it('an adjacency gets a contact band drawn at the producer’s own tolerance', () => {
        const p = projectRelation(
            relation('meets', ref('art_1', 'ext_outer'), ref('art_1', 'ext_touch'),
                { measurements: { contact_tolerance_px: 3 } }),
            ledger);
        expect(p.projection.projection_kind).toBe('contact_band');
        expect(p.projection.tolerance_px).toBe(3);
        expect(p.projection.derived).toBe(true);
        expect(p.directed).toBe(false);
    });

    it('an overlap gets the exact intersection', () => {
        const p = projectRelation(
            relation('overlaps', ref('art_1', 'ext_outer'), ref('art_1', 'ext_inner')),
            ledger);
        expect(p.projection.projection_kind).toBe('intersection_area');
        expect(p.projection.derived_intersection_pixels).toBeGreaterThan(0);
        expect(p.projection.rings.length).toBeGreaterThan(0);
    });

    it('a disjoint pair gets the clearance between the nearest points', () => {
        const p = projectRelation(
            relation('disjoint', ref('art_1', 'ext_inner'), ref('art_1', 'ext_far')),
            ledger);
        expect(p.projection.derived_distance_px).toBeGreaterThan(0);
        expect(p.projection.from).toBeTruthy();
        expect(p.projection.to).toBeTruthy();
    });

    it('a dangling endpoint is measured and not drawable, and the number still stands', () => {
        const p = projectRelation(
            relation('meets', ref('art_1', 'ext_outer'), ref('art_gone', 'ext_x'),
                { measurements: { contact_pixels: 812 } }),
            ledger);
        expect(p.drawable).toBe(false);
        expect(p.why).toMatch(/not in this session's ledger/);
        expect(p.measurements.contact_pixels).toBe(812);
        expect(p.sentence).toContain('ext_x');
    });

    it('a stale endpoint marks the relation stale without discarding it', () => {
        const revised = new Map([['art_1', extentSet('art_1', [
            inst('ext_a', outer, { region_id: 'r1', geometry_rev: 9 }),
            inst('ext_b', touching)])]]);
        const p = projectRelation(
            relation('meets', ref('art_1', 'ext_a', { geometry_rev: 1 }),
                ref('art_1', 'ext_b')), revised);
        expect(p.stale).toBe(true);
        expect(p.drawable).toBe(true);
    });

    it('refuses to draw across two rasters rather than resampling', () => {
        const mixed = new Map([['art_1', extentSet('art_1', [
            { ...inst('ext_a', outer) },
            { instance_id: 'ext_b', mask_rle: encodeRle(rasterizeShape(touching, 20, 20)),
                box: null, area: null, confidence: null, naming: null, region_id: null,
                geometry_rev: null },
        ])]]);
        const p = projectRelation(
            relation('meets', ref('art_1', 'ext_a'), ref('art_1', 'ext_b')), mixed);
        expect(p.drawable).toBe(false);
        expect(p.why).toMatch(/different rasters/);
        expect(p.why).toMatch(/would invent the contact/);
    });
});

describe('the derived number is put beside the producer’s', () => {
    it('agrees when they agree', () => {
        const p = projectRelation(
            relation('overlaps', ref('art_1', 'ext_outer'), ref('art_1', 'ext_inner')), ledger);
        const withRecorded = agreementFor(
            { measurements: { iou: p.projection.derived_iou } }, p.projection);
        expect(withRecorded.quantity).toBe('iou');
        expect(withRecorded.agrees).toBe(true);
    });

    it('disagrees loudly when the producer’s number is not what the pixels say', () => {
        const p = projectRelation(
            relation('overlaps', ref('art_1', 'ext_outer'), ref('art_1', 'ext_inner')), ledger);
        const bad = agreementFor({ measurements: { iou: 0.99 } }, p.projection);
        expect(bad.agrees).toBe(false);
    });

    it('does not compare two different quantities into a fake disagreement', () => {
        const p = projectRelation(
            relation('meets', ref('art_1', 'ext_outer'), ref('art_1', 'ext_touch')), ledger);
        // A contact band and an IoU are different questions; there is nothing to compare.
        expect(agreementFor({ measurements: { iou: 0.4 } }, p.projection)).toBe(null);
    });
});

describe('the graph is the same measurement, arranged by endpoint', () => {
    const set = {
        identity: { artifact_kind: 'topology_relation_set' },
        measurement: { payload: { variant: 'topology_relation_set', pairs_examined: 3,
            bounded_to: null, relations: [
                { ...relation('meets', ref('art_1', 'ext_outer'), ref('art_1', 'ext_touch')),
                    relation_id: 'rel_a' },
                { ...relation('nested_within', ref('art_1', 'ext_inner'),
                    ref('art_1', 'ext_outer')), relation_id: 'rel_b' },
                { ...relation('disjoint', ref('art_1', 'ext_outer'), ref('art_1', 'ext_far')),
                    relation_id: 'rel_c' },
            ] } },
    };

    it('counts a node’s degree, which is how one enormous mask becomes visible', () => {
        const graph = relationGraph(projectRelationSet(set, ledger));
        const outerNode = graph.nodes.find((n) => n.id === 'art_1#ext_outer');
        expect(outerNode.degree).toBe(3);
        expect(graph.nodes).toHaveLength(4);
        expect(graph.edges).toHaveLength(3);
    });

    it('keeps two identically-named instances as two nodes', () => {
        const twins = new Map([['art_1', extentSet('art_1', [
            inst('ext_1', inner, { naming: { text: 'drapery', source: 'adapter',
                epistemic_status: 'interpretive', confidence: 0.8 } }),
            inst('ext_2', touching, { naming: { text: 'drapery', source: 'adapter',
                epistemic_status: 'interpretive', confidence: 0.8 } }),
        ])]]);
        const twinSet = { identity: { artifact_kind: 'topology_relation_set' },
            measurement: { payload: { variant: 'topology_relation_set', pairs_examined: 1,
                bounded_to: null, relations: [
                    relation('meets', ref('art_1', 'ext_1'), ref('art_1', 'ext_2'))] } } };
        const graph = relationGraph(projectRelationSet(twinSet, twins));
        expect(graph.nodes).toHaveLength(2);
        expect(graph.nodes.every((n) => n.name === 'drapery')).toBe(true);
        expect(graph.nodes[0].id).not.toBe(graph.nodes[1].id);
    });

    it('carries the direction onto the edge, and only where it exists', () => {
        const graph = relationGraph(projectRelationSet(set, ledger));
        expect(graph.edges.find((e) => e.relation_id === 'rel_b').directed).toBe(true);
        expect(graph.edges.find((e) => e.relation_id === 'rel_a').directed).toBe(false);
    });
});

describe('the negative-space field', () => {
    const field = {
        identity: { artifact_kind: 'negative_space_field' },
        measurement: { payload: { variant: 'negative_space_field',
            figure_instance_ids: ['ext_inner'], max_distance_used: 0.25, field_shape: [40, 40],
            field_ref: { uri: 'labstore://x', digest: 'sha256:x',
                media_type: 'application/octet-stream', bytes: 6400 },
            statistics: { mean: 0.2, min: 0, max: 0.25 } } },
    };

    it('refuses to draw the measured field, because the values are not in the record', () => {
        const out = projectNegativeSpace(field, ledger);
        expect(out.measured.available).toBe(false);
        expect(out.measured.why).toMatch(/held behind `field_ref`/);
        expect(out.measured.why).toMatch(/a wash drawn from them would be invented/);
    });

    it('derives its own field from the figure masks, and says it derived it', () => {
        const out = projectNegativeSpace(field, ledger);
        expect(out.derived.available).toBe(true);
        expect(out.derived.derived).toBe(true);
        expect(out.derived.computed_by).toBe('lab_browser');
        expect(out.derived.cells.length).toBeGreaterThan(0);
    });

    it('says so when the figures are not in the ledger, rather than drawing nothing', () => {
        const orphan = { ...field, measurement: { payload: {
            ...field.measurement.payload, figure_instance_ids: ['ext_nowhere'] } } };
        const out = projectNegativeSpace(orphan, ledger);
        expect(out.derived.available).toBe(false);
        expect(out.derived.why).toMatch(/are not in this session's ledger/);
    });
});
