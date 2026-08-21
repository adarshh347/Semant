// PERCEPTUAL-FORMS-001E — the nine Topology forms.
//
// THE STRUCTURAL FACT ABOUT TOPOLOGY, and everything here follows from it: a relation record
// carries NUMBERS and no geometry. `topology.pair_relation` reports a containment fraction and a
// clearance; it does not report the shape of the contact, because the contract keeps drawings out
// of the measurement block. Which is why all five of that form's projections are declared
// `derived` — every picture of a pair relation is computed in this browser, from the endpoint
// masks, and is a second thing beside the number.
//
// So this file does two jobs that must not blur:
//
//   1. draw the derived picture, stamped `derived`, from `geometry/projections.js` — the same
//      module the live Topology instrument uses, so the laboratory and the instrument cannot
//      disagree about what a contact band is;
//   2. put the derived number NEXT TO the producer's number and report the disagreement as a
//      disagreement. `agreement()` is generous on purpose: the point is not to grade a backend,
//      it is to catch the case where the band on screen describes a different pair than the
//      figure beside it.
//
// FOUR OF THE NINE FORMS DECLARE THEIR PROJECTIONS `direct` — contact locus, intersection area,
// clearance path and negative space carry their own geometry. Those forms exist so the browser's
// drawing stops being a substitute for a record and becomes a check against one, and the
// treatment follows automatically: `shared.evidenceFor` reads the mode off the registry, so the
// same contact band comes out dashed under `pair_relation` and solid under `contact_locus`.

import {
    ringsFromRle, isoSegments, layoutTree, layoutGraph, adjacencyMatrix,
} from '../formGeometry';
import { resolveEndpoint, resolvePair } from '../fixtures/endpointGeometry';
import {
    contactBandProjection, intersectionProjection, clearanceProjection, endpointPairProjection,
    deriveNegativeSpaceField, agreement,
} from '../../geometry/projections';
import { relationSentence, DIRECTED_KINDS } from '../../topologyView';
import {
    ringLayer, cellLayer, pointLayer, pathLayer, diagramLayer, readingLayer, absent,
} from './shared';

const endpointId = (ref) => `${ref?.artifact_id ?? '?'}#${ref?.instance_id ?? ref?.region_id ?? '?'}`;

/**
 * The sentence a relation makes, in identities rather than in names.
 *
 * `relationSentence` throws on a kind it does not know, and that is the behaviour wanted here:
 * rendering an unrecognised typed relation as "these two are related" would destroy the one thing
 * the topology organ produces, which is WHICH of the two is inside the other.
 */
const sentenceFor = (rel) => relationSentence(
    rel.kind, endpointId(rel.source), endpointId(rel.target));

/* ══ topology.pair_relation ═══════════════════════════════════════════════ */

const pairRelation = (formKey) => {
    const draw = (rel, kind) => {
        const pair = resolvePair(rel.source, rel.target);
        const id = `${kind}:${rel.relation_id}`;
        const source = { relation_id: rel.relation_id, source: rel.source, target: rel.target };
        if (!pair.both) {
            return [absent({
                layer_id: id, label: sentenceFor(rel), form: formKey, source, why: pair.why,
            })];
        }
        if (!pair.same_raster && kind !== 'endpoint_pair') {
            return [absent({
                layer_id: id,
                label: sentenceFor(rel),
                form: formKey,
                source,
                why: `the endpoints are on different rasters (${pair.source.raster?.h}×`
                    + `${pair.source.raster?.w} and ${pair.target.raster?.h}×`
                    + `${pair.target.raster?.w}). Resampling one to draw a ${kind} would invent `
                    + 'the very thing being drawn',
            })];
        }
        const a = pair.source.mask;
        const b = pair.target.mask;
        if (kind === 'contact_band') {
            const p = contactBandProjection(a, b,
                { tolerance_px: rel.measurements?.contact_tolerance_px ?? 1 });
            if (!p.available) {
                return [absent({ layer_id: id, label: sentenceFor(rel), form: formKey, source,
                    why: p.why })];
            }
            return [ringLayer({
                id,
                label: sentenceFor(rel),
                formKey,
                kind,
                rings: p.rings,
                raster: p.raster,
                source,
                basis: rel.basis,
                status: rel.epistemic_status,
                measurements: {
                    derived_contact_pixels: p.derived_contact_pixels,
                    tolerance_px: p.tolerance_px,
                    agreement: agreement(p.derived_contact_pixels,
                        rel.measurements?.contact_pixels),
                },
            })];
        }
        if (kind === 'intersection_area') {
            const p = intersectionProjection(a, b);
            if (!p.available) {
                return [absent({ layer_id: id, label: sentenceFor(rel), form: formKey, source,
                    why: p.why })];
            }
            return [ringLayer({
                id,
                label: sentenceFor(rel),
                formKey,
                kind,
                rings: p.rings,
                raster: p.raster,
                source,
                basis: rel.basis,
                status: rel.epistemic_status,
                measurements: {
                    derived_intersection_pixels: p.derived_intersection_pixels,
                    derived_iou: p.derived_iou,
                    agreement: agreement(p.derived_iou, rel.measurements?.intersection_area),
                },
                note: p.derived_intersection_pixels === 0
                    ? 'the exact pixel intersection is EMPTY. That is a measurement, and it is '
                      + 'worth reading against the relation kind above'
                    : null,
            })];
        }
        if (kind === 'mask_outline') {
            return [pair.source, pair.target].map((end, i) => ringLayer({
                id: `${id}:${i === 0 ? 'source' : 'target'}`,
                label: `${i === 0 ? 'source' : 'target'} · ${end.id}`,
                formKey,
                kind,
                rings: end.rings,
                raster: end.raster,
                source,
                basis: end.basis,
                status: rel.epistemic_status,
                filled: false,
            }));
        }
        // endpoint_pair — the anchors, and the arrow only where the record says directed.
        const useClearance = rel.kind === 'disjoint';
        const p = useClearance ? clearanceProjection(a, b)
            : endpointPairProjection(a, b, { directed: rel.directed });
        if (!p.available) {
            return [absent({ layer_id: id, label: sentenceFor(rel), form: formKey, source,
                why: p.why })];
        }
        return [pathLayer({
            id,
            label: sentenceFor(rel),
            formKey,
            kind: 'endpoint_pair',
            points: [[[p.from.x, p.from.y], [p.to.x, p.to.y]]],
            // AN ARROWHEAD IS A CLAIM OF ASYMMETRY. `meets` and `disjoint` are undirected, and an
            // arrow on one would assert an ordering the organ did not measure.
            arrow: DIRECTED_KINDS.has(rel.kind) && rel.directed,
            source,
            basis: rel.basis,
            status: rel.epistemic_status,
            measurements: {
                ...(useClearance ? {
                    derived_distance_fraction: p.derived_distance_fraction,
                    agreement: agreement(p.derived_distance_fraction,
                        rel.measurements?.separation ?? rel.measurements?.clearance),
                } : {}),
                stale: rel.stale,
            },
            note: useClearance
                ? 'the closest points of the two masks, and the gap between them'
                : 'centroid to centroid. The centroid of a crescent is outside it — this anchors '
                  + 'the pair and is not a claim about where either thing is',
        })];
    };

    const view = (key, label, hint, kind) => ({
        key,
        label,
        hint,
        surface: 'stage',
        projections: [kind],
        build: (payload, ctx) => {
            if (!payload.relations.length) return { layers: [noRelations(formKey, payload)] };
            const chosen = ctx?.focusId
                ? payload.relations.filter((r) => r.relation_id === ctx.focusId)
                : payload.relations;
            return { layers: chosen.flatMap((r) => draw(r, kind)) };
        },
    });

    return [
        view('endpoints', 'Endpoint pair', 'each pair anchored, with an arrowhead only where the '
            + 'record declares the relation directed', 'endpoint_pair'),
        view('contact', 'Contact band', 'the overlap of the two dilated masks, computed here at '
            + 'the producer\'s own tolerance', 'contact_band'),
        view('intersection', 'Intersection', 'the exact pixel intersection, computed here',
            'intersection_area'),
        view('outlines', 'Endpoint outlines', 'the two masks a relation stands between',
            'mask_outline'),
        {
            key: 'graph',
            label: 'Relation graph',
            hint: 'the relations as a graph — nodes are identities, never names, because two '
                + 'instances can share a label and are not the same thing',
            surface: 'diagram',
            projections: ['relation_graph'],
            build: (payload) => {
                if (!payload.relations.length) return { layers: [noRelations(formKey, payload)] };
                const ids = [...new Set(payload.relations.flatMap(
                    (r) => [endpointId(r.source), endpointId(r.target)]))];
                const g = layoutGraph(
                    ids.map((id) => ({
                        node_id: id,
                        resolved: resolveEndpoint({
                            artifact_id: id.split('#')[0], instance_id: id.split('#')[1],
                        }).resolved,
                    })),
                    payload.relations.map((r) => ({
                        edge_id: r.relation_id,
                        source_node_id: endpointId(r.source),
                        target_node_id: endpointId(r.target),
                        kind: r.kind,
                        directed: r.directed,
                        basis: r.basis,
                        epistemic_status: r.epistemic_status,
                        stale: r.stale,
                        sentence: sentenceFor(r),
                        measurements: r.measurements,
                    })));
                return {
                    layers: [diagramLayer({
                        id: 'relation_graph:all',
                        label: `${g.nodes.length} endpoints, ${g.edges.length} relations`,
                        formKey,
                        kind: 'relation_graph',
                        nodes: g.nodes,
                        edges: g.edges,
                        dangling: g.dangling,
                        isolated: g.isolated,
                        basis: 'mask',
                        status: 'measured',
                    })],
                };
            },
        },
        {
            key: 'list',
            label: 'Relations',
            hint: 'every relation as a sentence, with its measurements and its staleness',
            surface: 'panel',
            projections: [],
            build: (payload) => {
                if (!payload.relations.length) return { layers: [noRelations(formKey, payload)] };
                return {
                    layers: payload.relations.map((r) => readingLayer({
                        id: `list:${r.relation_id}`,
                        label: sentenceFor(r),
                        formKey,
                        basis: r.basis,
                        status: r.epistemic_status,
                        partition: 'visible_measured',
                        rows: [
                            { label: 'source', value: endpointId(r.source) },
                            { label: 'target', value: endpointId(r.target) },
                            { label: 'directed', value: r.directed },
                            ...Object.entries(r.measurements || {}).map(
                                ([k, v]) => ({ label: k.replace(/_/g, ' '), value: v })),
                        ],
                        note: r.stale
                            ? 'STALE. One endpoint has changed since this relation was measured, '
                              + 'so the number above describes geometry that is no longer there'
                            : null,
                    })),
                };
            },
        },
    ];
};

const noRelations = (formKey, payload) => absent({
    layer_id: 'relations:none',
    label: 'relations',
    form: formKey,
    why: `${payload.pairs_examined ?? 'The'} pairs were compared and none stood in any of the `
        + 'asked-for relations. That is a measurement — it is not a refusal and it is not an '
        + 'unavailable organ',
});

/* ══ topology.contact_locus ═══════════════════════════════════════════════ */

const contactLocus = (formKey) => {
    const bandLayer = (locus) => {
        const g = ringsFromRle(locus.mask_rle);
        const source = { locus_id: locus.locus_id, source: locus.source, target: locus.target };
        if (!g) {
            return absent({
                layer_id: `contact_band:${locus.locus_id}`,
                label: locus.locus_id,
                form: formKey,
                source,
                why: 'this locus carries no mask. The contact pixel count beside it is still the '
                    + 'measurement — the shape of the contact is what is missing',
            });
        }
        const raster = locus.raster_shape
            ? { h: locus.raster_shape[0], w: locus.raster_shape[1] } : g.raster;
        const capacity = raster ? raster.h * raster.w : null;
        return ringLayer({
            id: `contact_band:${locus.locus_id}`,
            label: `${endpointId(locus.source)} ↔ ${endpointId(locus.target)}`,
            formKey,
            kind: 'contact_band',
            rings: g.rings,
            raster,
            source,
            basis: locus.basis,
            status: locus.epistemic_status,
            partition: 'visible_measured',
            measurements: { contact_pixels: locus.contact_pixels },
            note: capacity && locus.contact_pixels > capacity
                ? `${locus.contact_pixels} contact pixels are recorded on a ${raster.h}×${raster.w} `
                  + `raster, which holds ${capacity}. The count and the mask were measured at `
                  + 'different resolutions; only one of them is drawable, and the drawing is the '
                  + 'coarser of the two'
                : null,
        });
    };

    return [
        {
            key: 'band',
            label: 'Contact band',
            hint: 'the recorded locus — measured by the producer, not traced here',
            surface: 'stage',
            projections: ['contact_band'],
            build: (payload) => ({
                layers: payload.loci.length
                    ? payload.loci.map(bandLayer)
                    : [absent({
                        layer_id: 'contact_band:none',
                        label: 'contact',
                        form: formKey,
                        why: `${payload.pairs_examined ?? 'The'} pairs were examined for contact `
                            + 'and none of them touch',
                    })],
            }),
        },
        {
            key: 'points',
            label: 'Contact samples',
            hint: 'the sampled points along the locus — a sample is not the locus',
            surface: 'stage',
            projections: ['point_markers'],
            build: (payload) => ({
                layers: payload.loci.length ? payload.loci.map((locus) => (locus.points?.length
                    ? pointLayer({
                        id: `point_markers:${locus.locus_id}`,
                        label: `${locus.points.length} samples on ${locus.locus_id}`,
                        formKey,
                        kind: 'point_markers',
                        points: locus.points,
                        raster: locus.raster_shape
                            ? { h: locus.raster_shape[0], w: locus.raster_shape[1] } : null,
                        source: { locus_id: locus.locus_id },
                        basis: locus.basis,
                        status: locus.epistemic_status,
                        partition: 'visible_measured',
                        note: `${locus.points.length} points stand for ${locus.contact_pixels} `
                            + 'contact pixels. They mark where the contact was sampled and do not '
                            + 'bound it',
                    })
                    : absent({
                        layer_id: `point_markers:${locus.locus_id}`,
                        label: locus.locus_id,
                        form: formKey,
                        why: 'this locus records no sample points',
                    }))) : [absent({
                    layer_id: 'point_markers:none',
                    label: 'contact samples',
                    form: formKey,
                    why: 'no locus is recorded, so nothing was sampled',
                })],
            }),
        },
    ];
};

/* ══ topology.intersection_area ═══════════════════════════════════════════ */

const intersectionArea = (formKey) => [
    {
        key: 'area',
        label: 'Intersection',
        hint: 'the recorded overlap — direct, because this form carries the mask',
        surface: 'stage',
        projections: ['intersection_area'],
        build: (payload) => ({
            layers: payload.intersections.length ? payload.intersections.map((isect) => {
                const g = ringsFromRle(isect.mask_rle);
                const source = {
                    intersection_id: isect.intersection_id,
                    source: isect.source,
                    target: isect.target,
                };
                if (!g) {
                    return absent({
                        layer_id: `intersection_area:${isect.intersection_id}`,
                        label: isect.intersection_id,
                        form: formKey,
                        source,
                        why: 'this intersection carries no mask',
                    });
                }
                return ringLayer({
                    id: `intersection_area:${isect.intersection_id}`,
                    label: `${endpointId(isect.source)} ∩ ${endpointId(isect.target)}`,
                    formKey,
                    kind: 'intersection_area',
                    rings: g.rings,
                    raster: isect.raster_shape
                        ? { h: isect.raster_shape[0], w: isect.raster_shape[1] } : g.raster,
                    source,
                    basis: isect.basis,
                    status: isect.epistemic_status,
                    partition: 'visible_measured',
                    measurements: {
                        intersection_area: isect.intersection_area,
                        fraction_of_source: isect.fraction_of_source,
                        fraction_of_target: isect.fraction_of_target,
                    },
                    note: 'the two fractions are not interchangeable. An overlap that is 83% of '
                        + 'one thing and 21% of the other is asymmetric, and reporting one number '
                        + 'would pick a side',
                });
            }) : [absent({
                layer_id: 'intersection_area:none',
                label: 'intersections',
                form: formKey,
                why: `${payload.pairs_examined ?? 'The'} pairs were intersected and every `
                    + 'intersection is empty',
            })],
        }),
    },
    {
        key: 'endpoints',
        label: 'Both sides',
        hint: 'the two masks the overlap sits between',
        surface: 'stage',
        projections: ['mask_fill'],
        build: (payload) => ({
            layers: payload.intersections.length
                ? payload.intersections.flatMap((isect) => {
                    const pair = resolvePair(isect.source, isect.target);
                    return [['source', pair.source], ['target', pair.target]].map(([role, end]) => (
                        end.resolved
                            ? ringLayer({
                                id: `mask_fill:${isect.intersection_id}:${role}`,
                                label: `${role} · ${end.id}`,
                                formKey,
                                kind: 'mask_fill',
                                rings: end.rings,
                                raster: end.raster,
                                source: { intersection_id: isect.intersection_id, role },
                                basis: end.basis,
                                status: isect.epistemic_status,
                                partition: 'visible_measured',
                            })
                            : absent({
                                layer_id: `mask_fill:${isect.intersection_id}:${role}`,
                                label: `${role} · ${end.id}`,
                                form: formKey,
                                source: { intersection_id: isect.intersection_id, role },
                                why: end.why,
                            })));
                })
                : [absent({
                    layer_id: 'mask_fill:none',
                    label: 'the two sides',
                    form: formKey,
                    why: 'no intersection is recorded, so there is no pair to draw',
                })],
        }),
    },
];

/* ══ topology.clearance_path ══════════════════════════════════════════════ */

const clearancePath = (formKey) => [
    {
        key: 'path',
        label: 'Clearance path',
        hint: 'the recorded shortest route between two extents that do not touch',
        surface: 'stage',
        projections: ['path_overlay'],
        build: (payload) => ({
            layers: payload.paths.length ? payload.paths.map((p) => {
                const source = { path_id: p.path_id, source: p.source, target: p.target };
                if (!Array.isArray(p.path) || p.path.length < 2) {
                    return absent({
                        layer_id: `path_overlay:${p.path_id}`,
                        label: p.path_id,
                        form: formKey,
                        source,
                        why: 'this record carries a separation and fewer than two path points, so '
                            + 'there is a distance and no route to draw it along',
                    });
                }
                return pathLayer({
                    id: `path_overlay:${p.path_id}`,
                    label: `${endpointId(p.source)} → ${endpointId(p.target)}`,
                    formKey,
                    kind: 'path_overlay',
                    points: [p.path],
                    source,
                    basis: p.basis,
                    status: p.epistemic_status,
                    partition: 'visible_measured',
                    measurements: { separation: p.separation, points: p.path.length },
                });
            }) : [absent({
                layer_id: 'path_overlay:none',
                label: 'clearance',
                form: formKey,
                why: `${payload.pairs_examined ?? 'The'} pairs were measured and every one of `
                    + 'them touches, so no clearance exists to record',
            })],
        }),
    },
    {
        key: 'endpoints',
        label: 'Closest points',
        hint: 'the two points the separation was measured between',
        surface: 'stage',
        projections: ['point_markers'],
        build: (payload) => ({
            layers: payload.paths.length ? payload.paths.map((p) => pointLayer({
                id: `point_markers:${p.path_id}`,
                label: `closest points of ${p.path_id}`,
                formKey,
                kind: 'point_markers',
                points: [p.from_point, p.to_point].filter(Boolean),
                source: { path_id: p.path_id },
                basis: p.basis,
                status: p.epistemic_status,
                partition: 'visible_measured',
                note: `separation ${p.separation} — measured between these two points and not `
                    + 'between the centroids',
            })) : [absent({
                layer_id: 'point_markers:none',
                label: 'closest points',
                form: formKey,
                why: 'no path is recorded, so no pair of closest points was measured',
            })],
        }),
    },
];

/* ══ topology.containment_tree ════════════════════════════════════════════ */

const containmentTree = (formKey) => {
    const nodesOf = (payload) => payload.nodes.map((n) => ({
        ...n,
        endpoint_label: endpointId(n.endpoint),
        resolved: resolveEndpoint(n.endpoint).resolved,
    }));

    return [
        {
            key: 'tree',
            label: 'Tree',
            hint: 'containment as a tree — every edge is directed, because "contains" is not '
                + 'symmetric and an undirected line would say only that two things are related',
            surface: 'diagram',
            projections: ['hierarchy_tree'],
            build: (payload) => {
                if (!payload.nodes.length) return { layers: [noTree(formKey, payload)] };
                const t = layoutTree(nodesOf(payload), { rootIds: payload.root_node_ids });
                return {
                    layers: [diagramLayer({
                        id: 'hierarchy_tree:tree',
                        label: `${t.nodes.length} nodes, ${t.depth + 1} deep`,
                        formKey,
                        kind: 'hierarchy_tree',
                        nodes: t.nodes,
                        // THE SENTENCE, not only the arrowhead. "contains" is not symmetric, an
                        // arrowhead is small, and the direction IS the measurement.
                        edges: t.edges.map((e) => ({
                            ...e,
                            sentence: `${e.source_node_id} contains ${e.target_node_id}`
                                + (e.occupancy_of_parent !== null
                                    ? `, filling ${e.occupancy_of_parent} of it` : ''),
                        })),
                        dangling: t.dangling,
                        unreached: t.unreached,
                        basis: 'mask',
                        status: 'measured',
                        partition: 'exact_derivation',
                    })],
                };
            },
        },
        {
            key: 'graph',
            label: 'As a graph',
            hint: 'the same containment drawn without a root — which is what it is before '
                + 'somebody chooses one',
            surface: 'diagram',
            projections: ['relation_graph'],
            build: (payload) => {
                if (!payload.nodes.length) return { layers: [noTree(formKey, payload)] };
                const g = layoutGraph(nodesOf(payload), payload.nodes
                    .filter((n) => n.parent_node_id)
                    .map((n) => ({
                        edge_id: `${n.parent_node_id}->${n.node_id}`,
                        source_node_id: n.parent_node_id,
                        target_node_id: n.node_id,
                        kind: 'contains',
                        directed: true,
                        basis: n.basis,
                        epistemic_status: n.epistemic_status,
                        sentence: `${n.parent_node_id} contains ${n.node_id}`,
                        measurements: { occupancy_of_parent: n.occupancy_of_parent },
                    })));
                return {
                    layers: [diagramLayer({
                        id: 'relation_graph:tree',
                        label: `${g.nodes.length} nodes, ${g.edges.length} containments`,
                        formKey,
                        kind: 'relation_graph',
                        nodes: g.nodes,
                        edges: g.edges,
                        dangling: g.dangling,
                        isolated: g.isolated,
                        basis: 'mask',
                        status: 'measured',
                        partition: 'exact_derivation',
                    })],
                };
            },
        },
    ];
};

const noTree = (formKey, payload) => absent({
    layer_id: 'tree:none',
    label: 'the tree',
    form: formKey,
    why: `${payload.pairs_examined ?? 'The'} pairs were compared for nesting and nothing `
        + 'contained anything',
});

/* ══ topology.adjacency_graph ═════════════════════════════════════════════ */

const adjacencyGraph = (formKey) => {
    const laidOut = (payload) => layoutGraph(
        payload.nodes.map((n) => ({
            ...n,
            endpoint_label: endpointId(n.endpoint),
            resolved: resolveEndpoint(n.endpoint).resolved,
        })),
        payload.edges.map((e) => ({
            ...e,
            sentence: `${e.source_node_id} ${e.kind} ${e.target_node_id}`,
        })));

    return [
        {
            key: 'graph',
            label: 'Graph',
            hint: 'the recorded adjacency, node and link',
            surface: 'diagram',
            projections: ['relation_graph'],
            build: (payload) => {
                if (!payload.nodes.length) {
                    return {
                        layers: [absent({
                            layer_id: 'relation_graph:none',
                            label: 'the graph',
                            form: formKey,
                            why: `every one of ${payload.pairs_examined ?? 'the'} pairs was `
                                + 'compared and nothing touches anything',
                        })],
                    };
                }
                const g = laidOut(payload);
                return {
                    layers: [diagramLayer({
                        id: 'relation_graph:all',
                        label: `${g.nodes.length} nodes, ${g.edges.length} edges`,
                        formKey,
                        kind: 'relation_graph',
                        nodes: g.nodes,
                        edges: g.edges,
                        dangling: g.dangling,
                        isolated: g.isolated,
                        basis: 'mask',
                        status: 'measured',
                        partition: 'exact_derivation',
                    })],
                };
            },
        },
        {
            key: 'matrix',
            label: 'Matrix',
            hint: 'every pair, including the ones examined and found unrelated — which the '
                + 'node-link drawing renders as empty space indistinguishable from "never checked"',
            surface: 'diagram',
            projections: ['relation_graph'],
            build: (payload) => {
                if (!payload.nodes.length) {
                    return {
                        layers: [absent({
                            layer_id: 'relation_graph:matrix',
                            label: 'the matrix',
                            form: formKey,
                            why: 'no node is recorded, so there is no pair to tabulate',
                        })],
                    };
                }
                const m = adjacencyMatrix(payload.nodes, payload.edges);
                const possible = (m.ids.length * (m.ids.length - 1)) / 2;
                return {
                    layers: [diagramLayer({
                        id: 'relation_graph:matrix',
                        label: `${m.recorded_edges} recorded of ${payload.pairs_examined} examined`,
                        formKey,
                        kind: 'relation_graph',
                        nodes: payload.nodes,
                        edges: payload.edges,
                        matrix: m,
                        basis: 'mask',
                        status: 'measured',
                        partition: 'exact_derivation',
                        note: `${m.ids.length} nodes make ${possible} pairs; the record says `
                            + `${payload.pairs_examined} were examined and ${m.recorded_edges} `
                            + 'carry an edge. A blank cell here means examined and unrelated',
                    })],
                };
            },
        },
        {
            key: 'contact',
            label: 'Contact bands',
            hint: 'where each edge touches on the image — computed here, from the endpoint masks',
            surface: 'stage',
            projections: ['contact_band'],
            build: (payload) => ({
                layers: payload.edges.length ? payload.edges.map((e) => {
                    const src = payload.nodes.find((n) => n.node_id === e.source_node_id);
                    const tgt = payload.nodes.find((n) => n.node_id === e.target_node_id);
                    const pair = resolvePair(src?.endpoint, tgt?.endpoint);
                    const id = `contact_band:${e.edge_id}`;
                    if (!pair.both) {
                        return absent({
                            layer_id: id,
                            label: e.edge_id,
                            form: formKey,
                            source: { edge_id: e.edge_id },
                            why: pair.why,
                        });
                    }
                    const p = contactBandProjection(pair.source.mask, pair.target.mask);
                    if (!p.available) {
                        return absent({ layer_id: id, label: e.edge_id, form: formKey,
                            why: p.why });
                    }
                    return ringLayer({
                        id,
                        label: `${e.source_node_id} ${e.kind} ${e.target_node_id}`,
                        formKey,
                        kind: 'contact_band',
                        rings: p.rings,
                        raster: p.raster,
                        source: { edge_id: e.edge_id },
                        basis: e.basis,
                        status: e.epistemic_status,
                        measurements: {
                            derived_contact_pixels: p.derived_contact_pixels,
                            agreement: agreement(p.derived_contact_pixels,
                                e.measurements?.contact_pixels),
                        },
                        note: e.locus_artifact_id
                            ? `this edge cites a recorded locus (${e.locus_artifact_id}). THAT `
                              + 'record is the measurement; this band is the browser\'s drawing, '
                              + 'and the two are worth comparing'
                            : null,
                    });
                }) : [absent({
                    layer_id: 'contact_band:none',
                    label: 'contact bands',
                    form: formKey,
                    why: 'this graph records no edge, so there is no contact to draw',
                })],
            }),
        },
    ];
};

/* ══ topology.negative_space_field ════════════════════════════════════════ */

const negativeSpace = (formKey) => {
    /** The measured field: behind `field_ref`, and therefore not on this page. */
    const measured = (payload) => absent({
        layer_id: 'scalar_wash:measured',
        label: `the measured ${(payload.field_shape || []).join('×')} field`,
        form: formKey,
        why: 'the negative_space_field payload holds its field behind `field_ref` and carries no '
            + 'inline values — unlike every other field in this grammar, which has an '
            + '`inline_values` escape hatch. So this form\'s declared `scalar_wash` projection '
            + 'cannot be drawn by any runtime that cannot fetch that ref, and this one cannot. '
            + 'The statistics beside it ARE the measurement',
    });

    /** The browser's own field, from the figure masks. Derived, never confused with the above. */
    const derivedField = (payload) => {
        const figures = (payload.figure_instance_ids || []).map((id) => resolveEndpoint(
            id.includes('#')
                ? { artifact_id: id.split('#')[0], instance_id: id.split('#')[1] }
                : { artifact_id: 'art_extent_1', instance_id: id }));
        const masks = figures.filter((f) => f.resolved && f.mask).map((f) => f.mask);
        if (!masks.length) {
            return absent({
                layer_id: 'density_contours:derived',
                label: 'a field computed here',
                form: formKey,
                why: `none of the named figures (${(payload.figure_instance_ids || []).join(', ')}) `
                    + 'resolves to a mask in this fixture set, so there is no complement to run a '
                    + 'distance transform over',
            });
        }
        const p = deriveNegativeSpaceField(masks, {
            max_distance: payload.max_distance_used ?? 1,
            statistics: payload.statistics,
        });
        if (!p.available) {
            return absent({ layer_id: 'density_contours:derived', label: 'a field computed here',
                form: formKey, why: p.why });
        }
        return cellLayer({
            id: 'density_contours:derived',
            label: `a ${p.shape.h}×${p.shape.w} field computed in this browser`,
            formKey,
            // The form's DERIVED projection. The direct one is the wash, and the wash is the
            // thing that is absent — which is exactly the pairing this view exists to show.
            kind: 'density_contours',
            cells: p.cells,
            raster: p.shape,
            range: { lo: p.min, hi: p.max, declared: false },
            derivation: 'distance_transform',
            basis: 'mask',
            status: 'measured',
            note: `${p.why} Truncated at the same max_distance_used the record declares `
                + `(${payload.max_distance_used}). Against the record's own statistics it `
                + `${p.agrees_with_statistics === null ? 'has nothing to compare'
                    : p.agrees_with_statistics ? 'agrees' : 'DISAGREES'}`,
        });
    };

    return [
        {
            key: 'wash',
            label: 'The field',
            hint: 'the measured field beside the one this browser can compute — the difference '
                + 'between them is the whole point of the view',
            surface: 'stage',
            projections: ['scalar_wash', 'density_contours'],
            build: (payload) => ({ layers: [measured(payload), derivedField(payload)] }),
        },
        {
            key: 'contours',
            label: 'Contours',
            hint: 'crossings of the browser-computed field, unjoined',
            surface: 'stage',
            projections: ['density_contours'],
            build: (payload, ctx) => {
                const d = derivedField(payload);
                if (d.evidence === 'absent') return { layers: [d] };
                const f = {
                    available: true, cells: d.draw.cells, shape: d.raster, range: d.draw.range,
                };
                const levels = ctx?.levels ?? [(f.range.lo + f.range.hi) / 2];
                const segments = isoSegments(f, levels);
                if (!segments.length) {
                    return {
                        layers: [absent({
                            layer_id: 'density_contours:crossings',
                            label: 'contours',
                            form: formKey,
                            why: `the computed field crosses ${levels.join(', ')} nowhere`,
                        })],
                    };
                }
                return {
                    layers: [pathLayer({
                        id: 'density_contours:crossings',
                        label: `${segments.length} crossings at `
                            + `${levels.map((l) => l.toFixed(3)).join(', ')}`,
                        formKey,
                        kind: 'density_contours',
                        points: segments.map((s) => [[s.x1, s.y1], [s.x2, s.y2]]),
                        basis: 'mask',
                        status: 'measured',
                        note: 'these contour the field THIS BROWSER computed, not the field the '
                            + 'producer measured',
                    })],
                };
            },
        },
        {
            key: 'statistics',
            label: 'Statistics',
            hint: 'the numbers the record does carry — which are the measurement',
            surface: 'panel',
            projections: [],
            build: (payload) => ({
                layers: [readingLayer({
                    id: 'statistics:field',
                    label: 'the recorded statistics',
                    formKey,
                    basis: 'mask',
                    status: 'measured',
                    partition: 'visible_measured',
                    rows: [
                        { label: 'figures', value: (payload.figure_instance_ids || []).join(', ') },
                        { label: 'max distance used', value: payload.max_distance_used },
                        { label: 'field shape', value: (payload.field_shape || []).join('×') },
                        ...Object.entries(payload.statistics || {}).map(
                            ([k, v]) => ({ label: k.replace(/_/g, ' '), value: v })),
                    ],
                })],
            }),
        },
    ];
};

/* ══ topology.transition ══════════════════════════════════════════════════ */

const transition = (formKey) => {
    const sideLayers = (t, which) => {
        const rel = t[which];
        const pair = resolvePair(rel.source, rel.target);
        return [['source', pair.source, rel.source], ['target', pair.target, rel.target]]
            .map(([role, end, ref]) => {
                const id = `before_after:${t.transition_id}:${which}:${role}`;
                if (!end.resolved) {
                    return absent({
                        layer_id: id, label: `${which} · ${role}`, form: formKey, source: ref,
                        why: end.why,
                    });
                }
                return ringLayer({
                    id,
                    label: `${which} · ${role} · ${end.id} @rev ${ref.geometry_rev}`,
                    formKey,
                    kind: 'before_after',
                    rings: end.rings,
                    raster: end.raster,
                    source: { ...ref, side: which, role },
                    basis: end.basis,
                    status: 'measured',
                    partition: 'exact_derivation',
                    filled: which === 'after',
                    note: end.stale
                        ? `this endpoint is cited at geometry_rev ${ref.geometry_rev}, and the `
                          + 'fixture set carries revision 0 only. What is drawn is NOT the '
                          + 'geometry this half of the transition was measured against'
                        : null,
                });
            });
    };

    return [
        {
            key: 'before_after',
            label: 'Before / after',
            hint: 'the two revisions in separate panes — a transition drawn on one stage would '
                + 'show a shape that existed at neither revision',
            surface: 'compare',
            projections: ['before_after'],
            build: (payload, ctx) => {
                if (!payload.transitions.length) {
                    return {
                        layers: [absent({
                            layer_id: 'before_after:none',
                            label: 'transitions',
                            form: formKey,
                            why: `${payload.revisions_compared ?? 'The'} revisions were compared `
                                + 'and no relation changed',
                        })],
                    };
                }
                const t = payload.transitions.find((x) => x.transition_id === ctx?.focusId)
                    ?? payload.transitions[0];
                const sides = [
                    { key: 'before', label: `before — ${t.before.kind}`,
                        layers: sideLayers(t, 'before') },
                    { key: 'after', label: `after — ${t.after.kind}`,
                        layers: sideLayers(t, 'after') },
                ];
                return { layers: sides.flatMap((s) => s.layers), sides };
            },
        },
        {
            key: 'diff',
            label: 'What changed',
            hint: 'the kind, the measurements and the revisions on both sides — a transition '
                + 'that cites only one revision is not a transition',
            surface: 'panel',
            projections: ['transition_diff'],
            build: (payload) => ({
                layers: payload.transitions.length
                    ? payload.transitions.map((t) => readingLayer({
                        id: `transition_diff:${t.transition_id}`,
                        label: `${t.transition_id} — ${t.change}`,
                        formKey,
                        partition: 'exact_derivation',
                        status: 'measured',
                        rows: [
                            { label: 'kind', value: `${t.before.kind} → ${t.after.kind}` },
                            { label: 'source revision',
                                value: `${t.before.source.geometry_rev} → ${t.after.source.geometry_rev}` },
                            { label: 'target revision',
                                value: `${t.before.target.geometry_rev} → ${t.after.target.geometry_rev}` },
                            ...unionKeys(t.before.measurements, t.after.measurements).map((k) => ({
                                label: k.replace(/_/g, ' '),
                                value: `${fmt(t.before.measurements?.[k])} → `
                                    + `${fmt(t.after.measurements?.[k])}`,
                            })),
                        ],
                        note: differentMeasurements(t)
                            ? 'the two halves report DIFFERENT measurements, because the relation '
                              + 'kind changed. There is no before-and-after number here, and '
                              + 'inventing a zero for the missing side would manufacture a trend'
                            : null,
                    }))
                    : [absent({
                        layer_id: 'transition_diff:none',
                        label: 'what changed',
                        form: formKey,
                        why: `${payload.revisions_compared ?? 'The'} revisions were compared and `
                            + 'no relation changed',
                    })],
            }),
        },
    ];
};

const unionKeys = (a, b) => [...new Set([...Object.keys(a || {}), ...Object.keys(b || {})])];
const fmt = (v) => (v === undefined ? 'not measured' : String(v));
const differentMeasurements = (t) => Object.keys(t.before.measurements || {}).join()
    !== Object.keys(t.after.measurements || {}).join();

/* ══ topology.uncertain_relation_set ══════════════════════════════════════ */

const uncertainRelations = (formKey) => {
    const relLayers = (payload, kind, hypothesisId) => {
        const chosen = payload.relations.filter(
            (r) => !hypothesisId || r.conditioned_on === hypothesisId);
        if (!chosen.length) {
            return [absent({
                layer_id: `${kind}:none`,
                label: hypothesisId ? `nothing under ${hypothesisId}` : 'relations',
                form: formKey,
                why: hypothesisId
                    ? `no relation in this record is conditioned on ${hypothesisId}. The other `
                      + 'readings carry their own, and they are not interchangeable'
                    : `${payload.pairs_examined ?? 'The'} pairs were compared under every `
                      + 'hypothesis and none stood in a relation',
            })];
        }
        return chosen.flatMap((rel) => {
            const pair = resolvePair(rel.source, rel.target);
            const id = `${kind}:${rel.relation_id}`;
            const source = { relation_id: rel.relation_id, conditioned_on: rel.conditioned_on };
            if (!pair.both) {
                return [absent({ layer_id: id, label: sentenceFor(rel), form: formKey, source,
                    why: pair.why })];
            }
            const p = endpointPairProjection(pair.source.mask, pair.target.mask,
                { directed: rel.directed });
            if (!p.available) {
                return [absent({ layer_id: id, label: sentenceFor(rel), form: formKey, source,
                    why: p.why })];
            }
            return [pathLayer({
                id,
                label: `${sentenceFor(rel)} — if ${rel.conditioned_on}`,
                formKey,
                kind,
                points: [[[p.from.x, p.from.y], [p.to.x, p.to.y]]],
                arrow: DIRECTED_KINDS.has(rel.kind) && rel.directed,
                source,
                basis: rel.basis,
                status: rel.epistemic_status,
                hypothesisId: rel.conditioned_on,
                measurements: rel.measurements,
                note: 'THE CONDITION TRAVELS WITH THE CLAIM. This relation holds only if '
                    + `"${rel.conditioned_on}" holds; read without it, a conditional measurement `
                    + 'becomes an unconditional one',
            })];
        });
    };

    return [
        {
            key: 'by_hypothesis',
            label: 'One reading',
            hint: 'the default — the relations that hold under one reading, and only those',
            surface: 'stage',
            projections: ['hypothesis_stack'],
            alternatives: 'one_at_a_time',
            default: true,
            build: (payload, ctx) => {
                const chosen = ctx?.hypothesisId ?? payload.hypotheses?.[0]?.hypothesis_id ?? null;
                return { layers: relLayers(payload, 'hypothesis_stack', chosen) };
            },
        },
        {
            key: 'layered',
            label: 'All readings',
            hint: 'every reading at once, ASKED FOR — each relation keeps the hypothesis it is '
                + 'conditioned on and its own dotted treatment',
            surface: 'stage',
            projections: ['hypothesis_stack'],
            alternatives: 'layered',
            build: (payload) => ({ layers: relLayers(payload, 'hypothesis_stack', null) }),
        },
        {
            key: 'graph',
            label: 'Graph',
            hint: 'the conditional relations as a graph — each edge labelled with its condition',
            surface: 'diagram',
            projections: ['relation_graph'],
            build: (payload) => {
                if (!payload.relations.length) {
                    return { layers: relLayers(payload, 'hypothesis_stack', null) };
                }
                const ids = [...new Set(payload.relations.flatMap(
                    (r) => [endpointId(r.source), endpointId(r.target)]))];
                const g = layoutGraph(ids.map((id) => ({ node_id: id })),
                    payload.relations.map((r) => ({
                        edge_id: r.relation_id,
                        source_node_id: endpointId(r.source),
                        target_node_id: endpointId(r.target),
                        kind: r.kind,
                        directed: r.directed,
                        basis: r.basis,
                        epistemic_status: r.epistemic_status,
                        conditioned_on: r.conditioned_on,
                        sentence: `${sentenceFor(r)} — if ${r.conditioned_on}`,
                        measurements: r.measurements,
                    })));
                return {
                    layers: [diagramLayer({
                        id: 'relation_graph:conditional',
                        label: `${g.edges.length} conditional relations over `
                            + `${payload.hypotheses?.length ?? 0} readings`,
                        formKey,
                        kind: 'relation_graph',
                        nodes: g.nodes,
                        edges: g.edges,
                        dangling: g.dangling,
                        isolated: g.isolated,
                        hypothesisId: payload.hypotheses?.[0]?.hypothesis_id ?? 'unconditioned',
                        basis: 'mask',
                        status: 'interpretive',
                        note: 'EVERY EDGE HERE IS CONDITIONAL. The graph is not a picture of what '
                            + 'is true; it is a picture of what would be true under each reading, '
                            + 'and the readings are mutually exclusive',
                    })],
                };
            },
        },
        {
            key: 'hypotheses',
            label: 'The readings',
            hint: 'which hypotheses this record is conditioned on, and what each one weighs',
            surface: 'panel',
            projections: [],
            build: (payload) => ({
                layers: [readingLayer({
                    id: 'hypotheses:list',
                    label: `${payload.hypotheses?.length ?? 0} readings`,
                    formKey,
                    status: 'interpretive',
                    hypothesisId: payload.hypotheses?.[0]?.hypothesis_id ?? 'none',
                    rows: (payload.hypotheses || []).map((h) => ({
                        label: h.hypothesis_id,
                        value: h.weight,
                        detail: `held in ${h.artifact_id}`,
                        relations: payload.relations
                            .filter((r) => r.conditioned_on === h.hypothesis_id).length,
                    })),
                    note: 'a relation conditioned on a hypothesis this record does not list is a '
                        + 'dangling condition, and is shown as one rather than dropped',
                })],
            }),
        },
    ];
};

/** Every Topology form's views, keyed by form. */
export const TOPOLOGY_VIEWS = Object.freeze({
    'topology.pair_relation': pairRelation('topology.pair_relation'),
    'topology.contact_locus': contactLocus('topology.contact_locus'),
    'topology.intersection_area': intersectionArea('topology.intersection_area'),
    'topology.clearance_path': clearancePath('topology.clearance_path'),
    'topology.containment_tree': containmentTree('topology.containment_tree'),
    'topology.adjacency_graph': adjacencyGraph('topology.adjacency_graph'),
    'topology.negative_space_field': negativeSpace('topology.negative_space_field'),
    'topology.transition': transition('topology.transition'),
    'topology.uncertain_relation_set': uncertainRelations('topology.uncertain_relation_set'),
});
