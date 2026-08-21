// PERCEPTUAL-FORMS-001E — the ten Extent forms, and the views a person can look at them through.
//
// A view is a small declaration plus a `build(payload, ctx)` that returns layers. It declares:
//
//   surface        stage · compare · sheet · diagram · panel. Which component draws it, and —
//                  more importantly — that a node-link diagram and an image stage are different
//                  places, so a graph cannot be letterboxed onto pixels by accident.
//   projections    the contract projection kinds this view draws. Asserted against the form
//                  registry at module load: a view that draws something its form never declared
//                  cannot be registered at all.
//   alternatives   how competing readings are shown. `one_at_a_time` is the default wherever a
//                  form carries a hypothesis, because merging alternatives into one overlay is
//                  the specific thing the build forbids.
//
// WHAT NONE OF THESE DO. No view decides its own evidence class — `shared.evidenceFor` reads it
// off the record's partition, the form's declared projection mode, and the partition part. A view
// that wanted to draw an inferred completion as measured would have to lie to the record first.

import {
    ringsFromRle, ringsFromBox, ringsFromRingPoints, ringsCentroid, fieldCells, thresholdCells,
    isoSegments, layoutTree,
} from '../formGeometry';
import { resolveEndpoint } from '../fixtures/endpointGeometry';
import {
    ringLayer, cellLayer, pointLayer, pathLayer, diagramLayer, readingLayer, absent, orEmpty,
} from './shared';

const ART = 'art_extent_1';
const FRAG_ART = 'art_fragments_1';

/** An instance's two possible geometries, and which one is really there. */
const geometryOf = (inst) => ({
    mask: ringsFromRle(inst.mask_rle),
    box: ringsFromBox(inst.box),
});

const named = (inst, fallback) => inst.naming?.text || fallback;

/* ══ extent.hard_mask ═════════════════════════════════════════════════════ */

const hardMask = (formKey) => {
    const instanceLayers = (payload, kind, { useBox = false, filled = true } = {}) =>
        payload.instances.map((inst) => {
            const g = geometryOf(inst);
            const chosen = useBox ? g.box : g.mask;
            const source = { artifact_id: ART, instance_id: inst.instance_id };
            if (!chosen) {
                return absent({
                    layer_id: `${kind}:${inst.instance_id}`,
                    label: named(inst, inst.instance_id),
                    form: formKey,
                    source,
                    why: useBox
                        ? 'this instance declares no box'
                        : 'this instance carries no mask. Its declared box is on the Box view — '
                          + 'drawing the box here would put a rectangle where a segmentation '
                          + 'belongs, which is the whole failure this laboratory watches for',
                });
            }
            return ringLayer({
                id: `${kind}:${inst.instance_id}`,
                label: named(inst, inst.instance_id),
                formKey,
                kind,
                rings: chosen.rings,
                raster: chosen.raster,
                source,
                // The basis is what the geometry IS. An instance with only a box is `box` basis
                // however the run was labelled, and the ceiling that implies travels with it.
                basis: useBox ? 'box' : (g.mask ? 'mask' : 'box'),
                status: 'measured',
                partition: 'visible_measured',
                filled,
                measurements: { area: inst.area, confidence: inst.confidence },
            });
        });

    return [
        {
            key: 'fill',
            label: 'Mask fill',
            hint: 'the decoded run-length mask, filled at its own raster',
            surface: 'stage',
            projections: ['mask_fill'],
            build: (payload) => ({
                layers: orEmpty(instanceLayers(payload, 'mask_fill'),
                    { formKey, payload, label: 'masks', id: 'mask_fill' }),
            }),
        },
        {
            key: 'outline',
            label: 'Outline',
            hint: 'the same boundary unfilled — traced in this browser, because the payload '
                + 'carries no ring',
            surface: 'stage',
            projections: ['mask_outline'],
            build: (payload) => ({
                layers: orEmpty(instanceLayers(payload, 'mask_outline', { filled: false }),
                    { formKey, payload, label: 'outlines', id: 'mask_outline' }),
            }),
        },
        {
            key: 'focus',
            label: 'Focus',
            hint: 'the selected instance lit, the rest receded — nothing is removed',
            surface: 'stage',
            projections: ['mask_fill'],
            focuses: true,
            build: (payload) => ({
                layers: orEmpty(instanceLayers(payload, 'mask_fill'),
                    { formKey, payload, label: 'masks', id: 'mask_fill' }),
            }),
        },
        {
            key: 'box',
            label: 'Declared box',
            hint: 'the box the record declares, which is a projection of the mask and not the mask',
            surface: 'stage',
            projections: ['box_outline'],
            build: (payload) => ({
                layers: orEmpty(
                    instanceLayers(payload, 'box_outline', { useBox: true, filled: false }),
                    { formKey, payload, label: 'boxes', id: 'box_outline' }),
            }),
        },
        {
            key: 'points',
            label: 'Refinement points',
            hint: 'the foreground and background clicks a person placed',
            surface: 'stage',
            projections: ['point_markers'],
            build: (payload) => {
                const withPoints = payload.instances.filter((i) => Array.isArray(i.points));
                if (!withPoints.length) {
                    return {
                        layers: [absent({
                            layer_id: 'point_markers:none',
                            label: 'Refinement points',
                            form: formKey,
                            why: 'no instance in this record carries refinement points. These are '
                                + 'written by extent.refine, and nothing here was refined — an '
                                + 'empty point layer is a fact about the provenance, not a gap',
                        })],
                    };
                }
                return {
                    layers: withPoints.map((inst) => pointLayer({
                        id: `point_markers:${inst.instance_id}`,
                        label: named(inst, inst.instance_id),
                        formKey,
                        kind: 'point_markers',
                        points: inst.points,
                        source: { artifact_id: ART, instance_id: inst.instance_id },
                        basis: 'manual',
                        status: 'measured',
                        partition: 'visible_measured',
                    })),
                };
            },
        },
        {
            key: 'contact_sheet',
            label: 'Contact sheet',
            hint: 'one cropped thumbnail per instance, numbered in record order',
            surface: 'sheet',
            projections: ['contact_sheet'],
            build: (payload) => {
                const layers = payload.instances.map((inst, i) => {
                    const g = geometryOf(inst);
                    const chosen = g.mask || g.box;
                    if (!chosen) {
                        return absent({
                            layer_id: `contact_sheet:${inst.instance_id}`,
                            label: `${i + 1}. ${named(inst, inst.instance_id)}`,
                            form: formKey,
                            source: { artifact_id: ART, instance_id: inst.instance_id },
                            why: 'this instance carries neither a mask nor a box, so there is '
                                + 'nothing to crop to',
                        });
                    }
                    return ringLayer({
                        id: `contact_sheet:${inst.instance_id}`,
                        label: `${i + 1}. ${named(inst, inst.instance_id)}`,
                        formKey,
                        kind: 'contact_sheet',
                        rings: chosen.rings,
                        raster: chosen.raster,
                        source: { artifact_id: ART, instance_id: inst.instance_id },
                        basis: g.mask ? 'mask' : 'box',
                        status: 'measured',
                        partition: 'visible_measured',
                        measurements: { area: inst.area },
                    });
                });
                const filled = orEmpty(layers,
                    { formKey, payload, label: 'thumbnails', id: 'contact_sheet' });
                return { layers: filled,
                    items: filled.map((l) => ({ layer: l, crop: cropFor(l) })) };
            },
        },
        {
            key: 'before_after',
            label: 'Before / after',
            hint: 'two records of the same form, side by side, neither drawn over the other',
            surface: 'compare',
            projections: ['before_after'],
            needs: ['comparison'],
            build: (payload, ctx) => comparePair(formKey, 'before_after', payload, ctx,
                (p) => instanceLayers(p, 'before_after')),
        },
        {
            key: 'ab_overlay',
            label: 'A/B overlay',
            hint: 'both records on one stage — the second is drawn as derived, because the '
                + 'comparison is this browser\'s work and not a measurement',
            surface: 'stage',
            projections: ['ab_overlay'],
            needs: ['comparison'],
            build: (payload, ctx) => {
                const base = payload.instances.map((inst) => overlayLayer(
                    formKey, 'ab_overlay', 'A', inst, 'visible_measured'));
                if (!ctx?.comparison) {
                    return {
                        layers: [...base, absent({
                            layer_id: 'ab_overlay:B',
                            label: 'B',
                            form: formKey,
                            why: 'no second record is selected. Pick one in the compare control — '
                                + 'an A/B overlay with one side is just A, drawn misleadingly',
                        })],
                    };
                }
                const other = ctx.comparison.payload.instances.map((inst) => overlayLayer(
                    formKey, 'ab_overlay', 'B', inst, 'exact_derivation'));
                return { layers: [...base, ...other] };
            },
        },
        {
            key: 'difference',
            label: 'Difference',
            hint: 'what each record has that the other does not, by instance id',
            surface: 'panel',
            projections: ['difference_overlay'],
            needs: ['comparison'],
            build: (payload, ctx) => {
                if (!ctx?.comparison) {
                    return {
                        layers: [absent({
                            layer_id: 'difference_overlay:none',
                            label: 'Difference',
                            form: formKey,
                            why: 'no second record is selected, and a difference against nothing '
                                + 'is the record itself',
                        })],
                    };
                }
                const a = new Set(payload.instances.map((i) => i.instance_id));
                const b = new Set(ctx.comparison.payload.instances.map((i) => i.instance_id));
                const rows = [
                    { label: 'only in A', value: [...a].filter((i) => !b.has(i)).join(', ') || 'nothing' },
                    { label: 'only in B', value: [...b].filter((i) => !a.has(i)).join(', ') || 'nothing' },
                    { label: 'in both', value: [...a].filter((i) => b.has(i)).join(', ') || 'nothing' },
                ];
                return {
                    layers: [readingLayer({
                        id: 'difference_overlay:sets',
                        label: `A ▲ ${ctx.comparison.label}`,
                        formKey,
                        rows,
                        partition: 'exact_derivation',
                        note: 'compared by instance id only. Two instances with the same id and '
                            + 'different geometry are counted as the same instance here, which is '
                            + 'a set difference and not a geometric one',
                    })],
                };
            },
        },
    ];
};

const overlayLayer = (formKey, kind, side, inst, partition) => {
    const g = geometryOf(inst);
    const chosen = g.mask || g.box;
    const source = { artifact_id: ART, instance_id: inst.instance_id, side };
    if (!chosen) {
        return absent({
            layer_id: `${kind}:${side}:${inst.instance_id}`,
            label: `${side} · ${named(inst, inst.instance_id)}`,
            form: formKey,
            source,
            why: 'this instance carries neither a mask nor a box',
        });
    }
    return ringLayer({
        id: `${kind}:${side}:${inst.instance_id}`,
        label: `${side} · ${named(inst, inst.instance_id)}`,
        formKey,
        kind,
        rings: chosen.rings,
        raster: chosen.raster,
        source,
        basis: g.mask ? 'mask' : 'box',
        status: 'measured',
        partition,
        filled: side === 'A',
    });
};

/** A comparison view's two sides, or an honest single side when nothing is selected. */
const comparePair = (formKey, kind, payload, ctx, build) => {
    const sides = [{ key: 'A', label: ctx?.scenarioLabel || 'this record', layers: build(payload) }];
    if (!ctx?.comparison) {
        sides.push({
            key: 'B',
            label: 'nothing selected',
            layers: [absent({
                layer_id: `${kind}:B`,
                label: 'the second record',
                form: formKey,
                why: 'pick a second record in the compare control. Two panes with one record in '
                    + 'them would read as a comparison that found no change',
            })],
        });
    } else {
        sides.push({
            key: 'B',
            label: ctx.comparison.label,
            layers: build(ctx.comparison.payload),
        });
    }
    return { layers: sides.flatMap((s) => s.layers), sides };
};

/** The crop a thumbnail uses — the layer's own extent, padded, clamped to the frame. */
function cropFor(l) {
    if (l.evidence === 'absent' || !l.draw?.rings?.length) return null;
    let x0 = 1; let y0 = 1; let x1 = 0; let y1 = 0;
    for (const ring of l.draw.rings) {
        for (const [x, y] of ring) {
            x0 = Math.min(x0, x); y0 = Math.min(y0, y);
            x1 = Math.max(x1, x); y1 = Math.max(y1, y);
        }
    }
    const pad = 0.06;
    return {
        x: Math.max(0, x0 - pad),
        y: Math.max(0, y0 - pad),
        w: Math.min(1, x1 + pad) - Math.max(0, x0 - pad),
        h: Math.min(1, y1 + pad) - Math.max(0, y0 - pad),
    };
}

/* ══ extent.boundary_rings ════════════════════════════════════════════════ */

const boundaryRings = (formKey) => {
    const ringLayers = (payload, kind, { split = false } = {}) => payload.boundaries.flatMap((b) => {
        const g = ringsFromRingPoints(b.rings);
        const source = { artifact_id: b.of?.artifact_id, instance_id: b.of?.instance_id };
        if (!g) {
            return [absent({
                layer_id: `${kind}:${source.instance_id}`,
                label: `boundary of ${source.instance_id}`,
                form: formKey,
                source,
                why: 'this boundary record carries no usable ring',
            })];
        }
        if (!split) {
            return [ringLayer({
                id: `${kind}:${source.instance_id}`,
                label: `boundary of ${source.instance_id}`,
                formKey,
                kind,
                rings: g.rings,
                raster: b.raster_shape ? { h: b.raster_shape[0], w: b.raster_shape[1] } : null,
                source,
                basis: 'mask',
                status: 'measured',
                // The ring is a deterministic function of a mask already recorded. It adds no
                // evidence, which is what `exact_derivation` means and why it is drawn dashed.
                partition: 'exact_derivation',
                filled: false,
                measurements: { rings: g.rings.length },
            })];
        }
        // One layer per ring, so outer and inner can be told apart, turned off, and counted.
        return g.rings.map((ring, i) => ringLayer({
            id: `${kind}:${source.instance_id}:${g.ring_ids[i]}`,
            label: `${g.windings[i]} ring · ${g.ring_ids[i]}`,
            formKey,
            kind,
            rings: [ring],
            raster: b.raster_shape ? { h: b.raster_shape[0], w: b.raster_shape[1] } : null,
            source: { ...source, ring_id: g.ring_ids[i], winding: g.windings[i] },
            basis: 'mask',
            status: 'measured',
            partition: 'exact_derivation',
            filled: false,
            note: g.windings[i] === 'inner'
                ? 'an INNER ring bounds a void. Drawn identically to the outer one it would '
                  + 'read as a second object rather than as a hole in the first'
                : 'the outer ring — the boundary of the extent itself',
        }));
    });

    return [
        {
            key: 'rings',
            label: 'Rings',
            hint: 'every recorded ring, as recorded — no smoothing, no resampling',
            surface: 'stage',
            projections: ['ring_outline'],
            build: (payload) => ({
                layers: orEmpty(ringLayers(payload, 'ring_outline'),
                    { formKey, payload, label: 'rings', id: 'ring_outline' }),
            }),
        },
        {
            key: 'winding',
            label: 'Outer / inner',
            hint: 'one layer per ring, so a void is not read as a second object',
            surface: 'stage',
            projections: ['ring_outline'],
            focuses: true,
            build: (payload) => ({
                layers: orEmpty(ringLayers(payload, 'ring_outline', { split: true }),
                    { formKey, payload, label: 'rings', id: 'ring_outline' }),
            }),
        },
        {
            key: 'edit',
            label: 'Editable boundary',
            hint: 'the same rings with a handle on every recorded vertex — fixture-only, nothing '
                + 'is saved',
            surface: 'stage',
            projections: ['ring_outline'],
            editable: 'vertices',
            build: (payload) => ({
                layers: orEmpty(ringLayers(payload, 'ring_outline', { split: true }),
                    { formKey, payload, label: 'rings', id: 'ring_outline' }),
            }),
        },
        {
            key: 'as_outline',
            label: 'As a plain outline',
            hint: 'the boundary drawn as an ordinary mask outline — direct here, because for this '
                + 'form the ring IS the record',
            surface: 'stage',
            projections: ['mask_outline'],
            build: (payload) => ({
                layers: orEmpty(ringLayers(payload, 'mask_outline'),
                    { formKey, payload, label: 'the boundary', id: 'mask_outline' }),
            }),
        },
    ];
};

/* ══ extent.hole_set ══════════════════════════════════════════════════════ */

const holeSet = (formKey) => {
    const holeLayers = (payload, kind) => payload.holes.map((hole) => {
        const g = ringsFromRle(hole.mask_rle) || ringsFromRingPoints(hole.rings);
        const source = {
            artifact_id: hole.outer?.artifact_id, instance_id: hole.outer?.instance_id,
            hole_id: hole.hole_id,
        };
        if (!g) {
            return absent({
                layer_id: `${kind}:${hole.hole_id}`,
                label: hole.hole_id,
                form: formKey,
                source,
                why: 'this hole record carries neither a mask nor a ring',
            });
        }
        return ringLayer({
            id: `${kind}:${hole.hole_id}`,
            label: `${hole.hole_id}${hole.enclosed ? '' : ' — not fully enclosed'}`,
            formKey,
            kind,
            rings: g.rings,
            raster: g.raster,
            source,
            basis: 'mask',
            status: 'measured',
            partition: 'exact_derivation',
            measurements: { area: hole.area, enclosed: hole.enclosed },
            note: hole.enclosed
                ? 'enclosed by the outer extent — a void, not a gap at the edge'
                : 'NOT fully enclosed. This is a bay in the boundary and the record says so; '
                  + 'drawn like an enclosed void it would assert a topology nobody measured',
        });
    });

    const parentLayer = (payload) => {
        const of = payload.holes[0]?.outer;
        const parent = of ? resolveEndpoint(of) : { resolved: false, why: 'no hole names an outer extent' };
        if (!parent.resolved) {
            return absent({
                layer_id: 'mask_outline:parent',
                label: 'the extent this hole is in',
                form: formKey,
                source: of,
                why: parent.why,
            });
        }
        return ringLayer({
            id: 'mask_outline:parent',
            label: `the extent this hole is in — ${parent.id}`,
            formKey,
            kind: 'mask_outline',
            rings: parent.rings,
            raster: parent.raster,
            source: of,
            basis: parent.basis,
            status: 'measured',
            filled: false,
        });
    };

    return [
        {
            key: 'hatch',
            label: 'Voids',
            hint: 'each recorded hole, hatched',
            surface: 'stage',
            projections: ['hole_fill'],
            build: (payload) => ({
                layers: orEmpty(holeLayers(payload, 'hole_fill'),
                    { formKey, payload, label: 'voids', id: 'hole_fill' }),
            }),
        },
        {
            key: 'void_focus',
            label: 'Void focus',
            hint: 'one hole lit, the others receded',
            surface: 'stage',
            projections: ['hole_fill'],
            focuses: true,
            build: (payload) => ({
                layers: orEmpty(holeLayers(payload, 'hole_fill'),
                    { formKey, payload, label: 'voids', id: 'hole_fill' }),
            }),
        },
        {
            key: 'parent_context',
            label: 'In its parent',
            hint: 'the hole inside the extent it perforates — the parent boundary is traced here, '
                + 'and is marked as this browser\'s work',
            surface: 'stage',
            projections: ['hole_fill', 'mask_outline'],
            build: (payload) => ({
                layers: [parentLayer(payload), ...orEmpty(holeLayers(payload, 'hole_fill'),
                    { formKey, payload, label: 'voids', id: 'hole_fill' })],
            }),
        },
    ];
};

/* ══ extent.soft_field ════════════════════════════════════════════════════ */

const softField = (formKey) => {
    const fieldOf = (payload) => fieldCells(payload.field);
    const source = (payload) => ({
        artifact_id: payload.of_instance?.artifact_id,
        instance_id: payload.of_instance?.instance_id,
    });

    const washLayer = (payload, kind = 'scalar_wash') => {
        const f = fieldOf(payload);
        if (!f.available) {
            return absent({
                layer_id: `${kind}:field`,
                label: 'the field',
                form: formKey,
                source: source(payload),
                why: f.why,
            });
        }
        return cellLayer({
            id: `${kind}:field`,
            label: `${f.shape.h}×${f.shape.w} field`,
            formKey,
            kind,
            cells: f.cells,
            raster: f.shape,
            range: f.range,
            derivation: f.derivation,
            calibration: f.calibration,
            source: source(payload),
            basis: 'mask',
            status: 'measured',
            partition: 'visible_measured',
        });
    };

    return [
        {
            key: 'wash',
            label: 'Heat wash',
            hint: 'the field as the cell grid it is — every cell boundary visible, because the '
                + 'resolution is part of the measurement',
            surface: 'stage',
            projections: ['scalar_wash'],
            build: (payload) => ({ layers: [washLayer(payload)] }),
        },
        {
            key: 'isolines',
            label: 'Isolines',
            hint: 'the crossings between adjacent cells, unjoined — a smooth contour through '
                + 'sixteen numbers would look like a measured boundary',
            surface: 'stage',
            projections: ['density_contours'],
            build: (payload, ctx) => {
                const f = fieldOf(payload);
                if (!f.available) {
                    return {
                        layers: [absent({
                            layer_id: 'density_contours:field',
                            label: 'isolines',
                            form: formKey,
                            source: source(payload),
                            why: f.why,
                        })],
                    };
                }
                const levels = ctx?.levels
                    ?? [payload.threshold_would_be ?? (f.range.lo + f.range.hi) / 2];
                return {
                    layers: [layerForSegments(formKey, f, levels, source(payload))],
                };
            },
        },
        {
            key: 'threshold',
            label: 'Threshold sweep',
            hint: 'the field cut at a threshold — the number is on screen, and the cells stay '
                + 'cells so nobody reads the result as a traced mask',
            surface: 'stage',
            projections: ['scalar_wash'],
            sweeps: true,
            build: (payload, ctx) => {
                const f = fieldOf(payload);
                if (!f.available) {
                    return {
                        layers: [absent({
                            layer_id: 'scalar_wash:threshold',
                            label: 'threshold sweep',
                            form: formKey,
                            source: source(payload),
                            why: f.why,
                        })],
                    };
                }
                const chosen = ctx?.threshold;
                const value = typeof chosen === 'number' ? chosen : payload.threshold_would_be;
                const src = typeof chosen === 'number'
                    ? 'chosen on this page, and applied here only'
                    : 'threshold_would_be, recorded by the producer';
                const t = thresholdCells(f, value, { source: src });
                return {
                    layers: [
                        // The full wash stays underneath. A threshold view that shows ONLY what
                        // survived hides how close the excluded cells were, which is the single
                        // most useful thing a sweep can show.
                        cellLayer({
                            id: 'scalar_wash:under',
                            label: 'the whole field, under the cut',
                            formKey,
                            kind: 'scalar_wash',
                            cells: f.cells,
                            raster: f.shape,
                            range: f.range,
                            derivation: f.derivation,
                            calibration: f.calibration,
                            source: source(payload),
                            basis: 'mask',
                            status: 'measured',
                            partition: 'visible_measured',
                        }),
                        cellLayer({
                            id: 'scalar_wash:above',
                            label: `cells at or above ${value}`,
                            formKey,
                            kind: 'scalar_wash',
                            cells: t.cells,
                            raster: f.shape,
                            range: f.range,
                            derivation: f.derivation,
                            calibration: f.calibration,
                            source: source(payload),
                            basis: 'mask',
                            status: 'measured',
                            partition: 'exact_derivation',
                            binarized: true,
                            threshold: t.threshold,
                            note: `${t.cells.length} of ${f.cells.length} cells survive; `
                                + `${t.excluded} do not. The contract declares no projection for `
                                + '"a field cut into an extent", so this stays a cell grid rather '
                                + 'than becoming a mask nobody measured',
                        }),
                    ],
                };
            },
        },
    ];
};

const layerForSegments = (formKey, f, levels, source) => {
    const segments = isoSegments(f, levels);
    if (!segments.length) {
        return absent({
            layer_id: 'density_contours:field',
            label: 'isolines',
            form: formKey,
            source,
            why: `no pair of adjacent cells straddles ${levels.join(', ')}, so this field crosses `
                + 'that level nowhere. An empty contour layer is a measurement',
        });
    }
    return pathLayer({
        id: 'density_contours:field',
        label: `crossings at ${levels.join(', ')}`,
        formKey,
        kind: 'density_contours',
        points: segments.flatMap((s) => [[[s.x1, s.y1], [s.x2, s.y2]]]),
        source,
        basis: 'mask',
        status: 'measured',
        partition: 'exact_derivation',
        measurements: { crossings: segments.length, levels: levels.join(', ') },
    });
};

/* ══ extent.fragment_set ══════════════════════════════════════════════════ */

const fragmentSet = (formKey) => {
    const fragLayers = (payload, kind, ctx) => payload.fragments.map((frag, i) => {
        const g = ringsFromRle(frag.mask_rle) || ringsFromBox(frag.box);
        const group = ctx?.membership?.[frag.fragment_id] ?? null;
        const source = { artifact_id: FRAG_ART, instance_id: frag.fragment_id, index: i + 1 };
        if (!g) {
            return absent({
                layer_id: `${kind}:${frag.fragment_id}`,
                label: `${i + 1}. ${frag.fragment_id}`,
                form: formKey,
                source,
                why: 'this fragment carries neither a mask nor a box',
            });
        }
        return ringLayer({
            id: `${kind}:${frag.fragment_id}`,
            label: `${i + 1}. ${frag.fragment_id}${group ? ` → ${group}` : ''}`,
            formKey,
            kind,
            rings: g.rings,
            raster: g.raster,
            source: { ...source, proposed_group: group },
            basis: frag.mask_rle ? 'mask' : 'box',
            status: 'measured',
            partition: 'visible_measured',
            measurements: { area: frag.area },
            note: group
                ? `a person on this page proposed moving this fragment into "${group}". The `
                  + 'proposal is not in the record and nothing here writes it there'
                : null,
        });
    });

    return [
        {
            key: 'islands',
            label: 'Numbered islands',
            hint: 'every separable piece, numbered in record order — unity is NOT asserted',
            surface: 'stage',
            projections: ['fragment_cluster'],
            build: (payload, ctx) => ({
                layers: orEmpty(fragLayers(payload, 'fragment_cluster', ctx),
                    { formKey, payload, label: 'fragments', id: 'fragment_cluster' }),
            }),
        },
        {
            key: 'component_focus',
            label: 'Component focus',
            hint: 'one piece lit, the others receded',
            surface: 'stage',
            projections: ['mask_fill'],
            focuses: true,
            build: (payload, ctx) => ({
                layers: orEmpty(fragLayers(payload, 'mask_fill', ctx),
                    { formKey, payload, label: 'fragments', id: 'mask_fill' }),
            }),
        },
        {
            key: 'links',
            label: 'Proposed links',
            hint: 'the fragments, plus any grouping a hypothesis proposes over them — the '
                + 'proposal is dotted and the pieces are solid',
            surface: 'stage',
            projections: ['fragment_cluster'],
            needs: ['hypothesis'],
            build: (payload, ctx) => {
                const base = orEmpty(fragLayers(payload, 'fragment_cluster', ctx),
                    { formKey, payload, label: 'fragments', id: 'fragment_cluster' });
                const hyp = ctx?.hypothesisPayload;
                if (!hyp) {
                    return {
                        layers: [...base, absent({
                            layer_id: 'fragment_cluster:link',
                            label: 'proposed links',
                            form: formKey,
                            why: 'this record proposes no grouping. `unity_asserted` is '
                                + `${payload.unity_asserted}, and a fragment set that asserted `
                                + 'unity would be a different form — extent.fused_hypothesis. '
                                + 'Load one in the hypothesis control to see its proposal drawn '
                                + 'over these pieces',
                        })],
                    };
                }
                const centres = new Map();
                for (const l of base) {
                    if (l.draw?.rings?.length) {
                        centres.set(l.source.instance_id, ringsCentroid(l.draw.rings));
                    }
                }
                const links = (hyp.hypotheses || []).flatMap((h) => {
                    const pts = h.members
                        .map((m) => centres.get(m.instance_id))
                        .filter(Boolean);
                    if (pts.length < 2) return [];
                    return [pathLayer({
                        id: `fragment_cluster:link:${h.hypothesis_id}`,
                        label: `${h.hypothesis_id} — proposes these are one thing`,
                        formKey,
                        kind: 'fragment_cluster',
                        points: [pts.map((p) => [p.x, p.y])],
                        hypothesisId: h.hypothesis_id,
                        basis: 'declared',
                        status: h.epistemic_status,
                        note: 'a LINE BETWEEN CENTROIDS, and nothing more. It is not the shape of '
                            + 'the proposed connection — no record carries that — and it is drawn '
                            + 'dotted so it cannot be read as one',
                    })];
                });
                return { layers: [...base, ...links] };
            },
        },
    ];
};

/* ══ extent.fused_hypothesis ══════════════════════════════════════════════ */

const fusedHypothesis = (formKey) => {
    const memberLayers = (h) => h.members.map((m) => {
        const r = resolveEndpoint(m);
        if (!r.resolved) {
            return absent({
                layer_id: `fragment_cluster:${h.hypothesis_id}:${m.instance_id}`,
                label: m.instance_id,
                form: formKey,
                source: m,
                why: r.why,
            });
        }
        return ringLayer({
            id: `fragment_cluster:${h.hypothesis_id}:${m.instance_id}`,
            label: `${m.instance_id} — visible`,
            formKey,
            kind: 'fragment_cluster',
            rings: r.rings,
            raster: r.raster,
            source: m,
            basis: r.basis,
            status: 'measured',
            // THE MEMBER IS MEASURED. The grouping is not. Drawing both as one hypothesis-tinted
            // blob would erase the only solid thing in this record.
            partition: 'visible_measured',
        });
    });

    const proposalLayer = (h) => {
        const pts = h.members
            .map((m) => resolveEndpoint(m))
            .filter((r) => r.resolved && r.centroid)
            .map((r) => [r.centroid.x, r.centroid.y]);
        if (pts.length < 2) {
            return absent({
                layer_id: `hypothesis_stack:${h.hypothesis_id}`,
                label: `${h.hypothesis_id} — the proposed connection`,
                form: formKey,
                why: 'fewer than two members resolved, so there is no connection to draw between '
                    + 'them. The grounds below are still the record',
            });
        }
        return pathLayer({
            id: `hypothesis_stack:${h.hypothesis_id}`,
            label: `${h.hypothesis_id} — proposed connection`,
            formKey,
            kind: 'hypothesis_stack',
            points: [pts],
            hypothesisId: h.hypothesis_id,
            basis: 'declared',
            status: h.epistemic_status,
            measurements: { weight: h.weight, asserts_hidden_extent: h.asserts_hidden_extent },
            note: h.asserts_hidden_extent
                ? 'this hypothesis ASSERTS HIDDEN EXTENT — it claims pixels behind the occluder '
                  + 'that nothing measured. The line is a link between what was seen, not the '
                  + 'shape of what is claimed; no record carries that shape'
                : 'a grouping proposal over measured members',
        });
    };

    return [
        {
            key: 'fusion',
            label: 'Fusion',
            hint: 'the visible pieces solid, the proposed connection dotted — one hypothesis at '
                + 'a time',
            surface: 'stage',
            projections: ['fragment_cluster', 'hypothesis_stack'],
            alternatives: 'one_at_a_time',
            build: (payload, ctx) => {
                const chosen = pick(payload.hypotheses, ctx?.hypothesisId, 'hypothesis_id');
                if (!chosen) {
                    return { layers: [emptyHypotheses(formKey, payload)] };
                }
                return { layers: [...memberLayers(chosen), proposalLayer(chosen)] };
            },
        },
        {
            key: 'grounds',
            label: 'Grounds',
            hint: 'what the hypothesis rests on, enumerated — each ground names its kind and its '
                + 'strength, and a hypothesis with no grounds says so',
            surface: 'panel',
            projections: ['hypothesis_stack'],
            alternatives: 'one_at_a_time',
            build: (payload, ctx) => {
                const chosen = pick(payload.hypotheses, ctx?.hypothesisId, 'hypothesis_id');
                if (!chosen) return { layers: [emptyHypotheses(formKey, payload)] };
                return {
                    layers: [readingLayer({
                        id: `hypothesis_stack:grounds:${chosen.hypothesis_id}`,
                        label: `${chosen.hypothesis_id} — grounds`,
                        formKey,
                        hypothesisId: chosen.hypothesis_id,
                        status: chosen.epistemic_status,
                        rows: (chosen.grounds || []).length
                            ? chosen.grounds.map((g) => ({
                                label: g.kind.replace(/_/g, ' '),
                                value: g.detail,
                                strength: g.strength,
                                cites: g.cites,
                            }))
                            : [{ label: 'no grounds', value: 'this hypothesis enumerates nothing '
                                + 'that supports it, which the contract permits and a reader '
                                + 'should weigh accordingly' }],
                    })],
                };
            },
        },
    ];
};

const emptyHypotheses = (formKey, payload) => absent({
    layer_id: 'hypothesis_stack:none',
    label: 'hypotheses',
    form: formKey,
    why: `this record proposes none. ${payload.fragments_considered ?? 'The'} fragments were `
        + 'considered and no grouping was supportable — which is a finding, not a failure',
});

const pick = (list, id, idField) => {
    if (!list?.length) return null;
    return (id && list.find((x) => x[idField] === id)) || list[0];
};

/* ══ extent.visible_inferred_partition ════════════════════════════════════ */

const partition = (formKey) => {
    const regionLayers = (payload, kind) => payload.regions.map((region) => {
        const source = {
            artifact_id: payload.of?.artifact_id, instance_id: payload.of?.instance_id,
            part: region.part,
        };
        // THE CONDITION TRAVELS WITH EVERY PART, including the measured one. This payload's
        // `conditioned_on` says the whole partition holds only if that hypothesis holds — so the
        // `visible` region is a measurement OF A SCENE THAT MAY NOT BE THE CASE, and the legend
        // has to be able to say so. It does not change the treatment (the PART decides that);
        // it changes what the row underneath the drawing reads.
        const hypothesisId = payload.conditioned_on ?? null;
        const g = ringsFromRle(region.mask_rle);
        if (g) {
            return ringLayer({
                id: `${kind}:${region.part}`,
                label: `${region.part} — ${Math.round((region.coverage ?? 0) * 100)}% of the extent`,
                formKey,
                kind,
                rings: g.rings,
                raster: g.raster,
                source,
                basis: 'mask',
                status: region.epistemic_status,
                // The PART decides the treatment. The record already said which pixels are
                // asserted rather than seen; the drawing may not disagree with it.
                part: region.part,
                hypothesisId,
                measurements: { coverage: region.coverage },
            });
        }
        const f = fieldCells(region.field);
        if (f.available) {
            return cellLayer({
                id: `${kind}:${region.part}`,
                label: `${region.part} — a ${f.shape.h}×${f.shape.w} field, not a mask`,
                formKey,
                kind: 'scalar_wash',
                cells: f.cells,
                raster: f.shape,
                range: f.range,
                derivation: f.derivation,
                calibration: f.calibration,
                source,
                basis: 'mask',
                status: region.epistemic_status,
                part: region.part,
                hypothesisId,
                note: 'this part of the partition is graded, not binary. It carries a field and '
                    + 'no mask, and drawing it as a solid region would give it an edge the record '
                    + 'does not have',
            });
        }
        return absent({
            layer_id: `${kind}:${region.part}`,
            label: region.part,
            form: formKey,
            source,
            why: f.why || 'this part carries neither a mask nor a field',
        });
    });

    return [
        {
            key: 'tricolor',
            label: 'Visible · inferred · unknown',
            hint: 'three parts, three treatments — solid, hatched, and a graded field',
            surface: 'stage',
            projections: ['partition_tricolor', 'scalar_wash'],
            build: (payload) => ({
                layers: orEmpty(regionLayers(payload, 'partition_tricolor'),
                    { formKey, payload, label: 'the partition', id: 'partition_tricolor' }),
            }),
        },
        {
            key: 'part_focus',
            label: 'One part',
            hint: 'one part lit, the others receded',
            surface: 'stage',
            projections: ['partition_tricolor', 'scalar_wash'],
            focuses: true,
            build: (payload) => ({
                layers: orEmpty(regionLayers(payload, 'partition_tricolor'),
                    { formKey, payload, label: 'the partition', id: 'partition_tricolor' }),
            }),
        },
        {
            key: 'coverage',
            label: 'Coverage',
            hint: 'how much of the extent each part claims, and what it was conditioned on',
            surface: 'panel',
            projections: [],
            build: (payload) => ({
                layers: [readingLayer({
                    id: 'coverage:parts',
                    label: 'coverage by part',
                    formKey,
                    rows: [
                        ...payload.regions.map((r) => ({
                            label: r.part,
                            value: r.coverage,
                            status: r.epistemic_status,
                        })),
                        {
                            label: 'conditioned on',
                            value: payload.conditioned_on
                                ?? 'nothing — this partition stands on its own',
                        },
                        {
                            label: 'sums to',
                            value: payload.regions.reduce((a, r) => a + (r.coverage ?? 0), 0),
                        },
                    ],
                    note: payload.conditioned_on
                        ? `every claim here holds only if "${payload.conditioned_on}" holds. `
                          + 'Reading the coverage without the condition promotes a conditional '
                          + 'measurement into an unconditional one'
                        : null,
                })],
            }),
        },
    ];
};

/* ══ extent.hierarchy ═════════════════════════════════════════════════════ */

const hierarchy = (formKey) => [
    {
        key: 'tree',
        label: 'Tree',
        hint: 'the nesting, as a tree in diagram space — these positions are not pixels',
        surface: 'diagram',
        projections: ['hierarchy_tree'],
        build: (payload) => {
            if (!payload.nodes.length) {
                return {
                    layers: [absent({
                        layer_id: 'hierarchy_tree:empty',
                        label: 'the tree',
                        form: formKey,
                        why: 'no node is recorded. The extents were compared for nesting and none '
                            + 'contained another',
                    })],
                };
            }
            const t = layoutTree(payload.nodes, { rootIds: payload.root_node_ids });
            return {
                layers: [diagramLayer({
                    id: 'hierarchy_tree:tree',
                    label: `${t.nodes.length} nodes, ${t.depth + 1} deep`,
                    formKey,
                    kind: 'hierarchy_tree',
                    nodes: t.nodes.map((n) => ({
                        ...n,
                        // A node may name an instance OR a canonical Region, and the two are not
                        // interchangeable: one is a measurement made in this session, the other
                        // is a Semant record with a revision of its own.
                        endpoint_label: n.instance
                            ? `${n.instance.artifact_id}#${n.instance.instance_id}`
                            : `${n.region?.region_id} (rev ${n.region?.geometry_rev}, ${n.region?.scope})`,
                        basis: n.basis,
                    })),
                    edges: t.edges,
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
        key: 'nested_focus',
        label: 'On the image',
        hint: 'each node drawn where its extent is — where the extent can be found',
        surface: 'stage',
        projections: ['mask_fill'],
        focuses: true,
        build: (payload) => ({
            layers: orEmpty(payload.nodes.map((n) => {
                const ref = n.instance || n.region;
                const r = resolveEndpoint(n.instance || { region_id: n.region?.region_id });
                if (!r.resolved) {
                    return absent({
                        layer_id: `mask_fill:${n.node_id}`,
                        label: n.node_id,
                        form: formKey,
                        source: ref,
                        why: r.why,
                    });
                }
                return ringLayer({
                    id: `mask_fill:${n.node_id}`,
                    label: `${n.node_id}${n.occupancy_of_parent !== null
                        ? ` — ${n.occupancy_of_parent} of its parent` : ' — root'}`,
                    formKey,
                    kind: 'mask_fill',
                    rings: r.rings,
                    raster: r.raster,
                    source: ref,
                    basis: n.basis,
                    status: 'measured',
                    partition: 'exact_derivation',
                    measurements: { occupancy_of_parent: n.occupancy_of_parent },
                });
            }), { formKey, payload, label: 'the nesting', id: 'mask_fill' }),
        }),
    },
];

/* ══ extent.density_field ═════════════════════════════════════════════════ */

const densityField = (formKey) => {
    const fieldOf = (payload) => fieldCells(payload.field);
    const wash = (payload, kind) => {
        const f = fieldOf(payload);
        if (!f.available) {
            return absent({
                layer_id: `${kind}:field`,
                label: 'the density field',
                form: formKey,
                why: f.why,
            });
        }
        return cellLayer({
            id: `${kind}:field`,
            label: `${f.shape.h}×${f.shape.w} density field`,
            formKey,
            kind,
            cells: f.cells,
            raster: f.shape,
            range: f.range,
            derivation: f.derivation,
            calibration: f.calibration,
            basis: 'mask',
            status: 'measured',
            partition: 'exact_derivation',
            note: payload.smoothing?.applied
                ? `SMOOTHED — ${payload.smoothing.method}, bandwidth ${payload.smoothing.bandwidth}. `
                  + 'The counts are exact and the field is not: smoothing moved mass between '
                  + 'cells, and a peak here is not a place three members were counted'
                : null,
        });
    };

    return [
        {
            key: 'wash',
            label: 'Scalar wash',
            hint: 'the density, cell by cell',
            surface: 'stage',
            projections: ['scalar_wash'],
            build: (payload) => ({ layers: [wash(payload, 'scalar_wash')] }),
        },
        {
            key: 'contours',
            label: 'Contours',
            hint: 'the crossings, unjoined',
            surface: 'stage',
            projections: ['density_contours'],
            build: (payload, ctx) => {
                const f = fieldOf(payload);
                if (!f.available) {
                    return {
                        layers: [absent({
                            layer_id: 'density_contours:field',
                            label: 'contours',
                            form: formKey,
                            why: f.why,
                        })],
                    };
                }
                const levels = ctx?.levels ?? [(f.range.lo + f.range.hi) / 2];
                return { layers: [layerForSegments(formKey, f, levels, null)] };
            },
        },
        {
            key: 'samples',
            label: 'Members counted',
            hint: 'which members this field counted, and whether each one can be found',
            surface: 'panel',
            projections: [],
            build: (payload) => ({
                layers: [readingLayer({
                    id: 'samples:members',
                    label: `${payload.members.length} members`,
                    formKey,
                    partition: 'exact_derivation',
                    rows: payload.members.map((m) => {
                        const r = resolveEndpoint(m);
                        return {
                            label: `${m.artifact_id}#${m.instance_id}`,
                            value: r.resolved ? 'resolves in this fixture set' : 'not on this page',
                            detail: r.resolved ? null : r.why,
                        };
                    }),
                    note: payload.counts_are_exact
                        ? 'the counts are exact; the FIELD is a smoothed rendering of them. Those '
                          + 'are two different claims and only the first is a count'
                        : 'the counts are not declared exact',
                })],
            }),
        },
    ];
};

/* ══ extent.hypothesis_set ════════════════════════════════════════════════ */

const hypothesisSet = (formKey) => {
    const altLayers = (alt, kind, { side = null } = {}) => {
        if (!alt.instances?.length) {
            return [absent({
                layer_id: `${kind}:${alt.alternative_id}`,
                label: `${alt.alternative_id} — weight ${alt.weight}`,
                form: formKey,
                source: { artifact_id: alt.artifact_id, alternative_id: alt.alternative_id },
                why: alt.artifact_id
                    ? `this alternative points at the whole artifact ${alt.artifact_id} rather `
                      + 'than at instances, and that artifact is not on this page'
                    : 'this alternative names no instances',
            })];
        }
        return alt.instances.map((m) => {
            const r = resolveEndpoint(m);
            const id = `${kind}:${alt.alternative_id}:${m.instance_id}${side ? `:${side}` : ''}`;
            if (!r.resolved) {
                return absent({
                    layer_id: id, label: m.instance_id, form: formKey, source: m, why: r.why,
                });
            }
            return ringLayer({
                id,
                label: `${alt.alternative_id} · ${m.instance_id}`,
                formKey,
                kind,
                rings: r.rings,
                raster: r.raster,
                source: m,
                basis: r.basis,
                // The CEILING of this form is `uncertain` and its only partition is
                // `unresolved_alternative`. However confident a weight looks, no member of an
                // unchosen reading may be drawn as measured.
                status: 'uncertain',
                hypothesisId: alt.alternative_id,
            });
        });
    };

    const noneNote = (payload) => absent({
        layer_id: 'hypothesis_stack:none',
        label: 'alternatives',
        form: formKey,
        why: `${payload.alternatives_considered ?? 'The'} alternatives were considered and only `
            + 'one reading survived — which is a resolved question and belongs in a resolved form',
    });

    return [
        {
            key: 'tabs',
            label: 'One at a time',
            hint: 'the default. Alternatives are held apart, because merging them into one '
                + 'overlay asserts a reading nobody chose',
            surface: 'stage',
            projections: ['hypothesis_stack'],
            alternatives: 'one_at_a_time',
            default: true,
            build: (payload, ctx) => {
                if (!payload.alternatives.length) return { layers: [noneNote(payload)] };
                const chosen = pick(payload.alternatives, ctx?.hypothesisId, 'alternative_id');
                return { layers: altLayers(chosen, 'hypothesis_stack') };
            },
        },
        {
            key: 'split',
            label: 'Split',
            hint: 'every alternative in its own pane — the same geometry, never superimposed',
            surface: 'compare',
            projections: ['hypothesis_stack'],
            alternatives: 'side_by_side',
            build: (payload) => {
                if (!payload.alternatives.length) return { layers: [noneNote(payload)] };
                const sides = payload.alternatives.map((alt) => ({
                    key: alt.alternative_id,
                    label: `${alt.alternative_id} · weight ${alt.weight}`,
                    layers: altLayers(alt, 'hypothesis_stack', { side: alt.alternative_id }),
                }));
                return { layers: sides.flatMap((s) => s.layers), sides };
            },
        },
        {
            key: 'layered',
            label: 'Layered',
            hint: 'all alternatives on one stage, ASKED FOR — every layer keeps its own '
                + 'hypothesis id and its own dotted treatment',
            surface: 'stage',
            projections: ['ab_overlay'],
            alternatives: 'layered',
            build: (payload) => {
                if (!payload.alternatives.length) return { layers: [noneNote(payload)] };
                return {
                    layers: payload.alternatives.flatMap((alt) => altLayers(alt, 'ab_overlay')),
                };
            },
        },
        {
            key: 'weights',
            label: 'Weights',
            hint: 'the question, the weights, and whether they are probabilities',
            surface: 'panel',
            projections: [],
            build: (payload) => ({
                layers: [readingLayer({
                    id: 'weights:alternatives',
                    label: payload.question ?? 'the alternatives',
                    formKey,
                    status: 'uncertain',
                    hypothesisId: payload.alternatives[0]?.alternative_id ?? 'none',
                    rows: payload.alternatives.map((a) => ({
                        label: a.alternative_id,
                        value: a.weight,
                        grounds: (a.grounds || []).map((g) => g.kind).join(', '),
                    })),
                    note: payload.weights_are_probabilities
                        ? 'the weights are probabilities and sum to one'
                        : 'THE WEIGHTS ARE NOT PROBABILITIES. They order the alternatives and '
                          + 'nothing more; reading 0.62 as "62% likely" is a claim this record '
                          + 'does not make',
                })],
            }),
        },
    ];
};

/** Every Extent form's views, keyed by form. */
export const EXTENT_VIEWS = Object.freeze({
    'extent.hard_mask': hardMask('extent.hard_mask'),
    'extent.boundary_rings': boundaryRings('extent.boundary_rings'),
    'extent.hole_set': holeSet('extent.hole_set'),
    'extent.soft_field': softField('extent.soft_field'),
    'extent.fragment_set': fragmentSet('extent.fragment_set'),
    'extent.fused_hypothesis': fusedHypothesis('extent.fused_hypothesis'),
    'extent.visible_inferred_partition': partition('extent.visible_inferred_partition'),
    'extent.hierarchy': hierarchy('extent.hierarchy'),
    'extent.density_field': densityField('extent.density_field'),
    'extent.hypothesis_set': hypothesisSet('extent.hypothesis_set'),
});
