// PERCEPTUAL-FORMS-001E — payload geometry, and the places it refuses.
//
// Nineteen forms, and between them they carry six kinds of geometry: run-length masks, explicit
// rings, boxes, scalar cell fields, trees, and graphs. This module turns each into something a
// renderer can draw, and it is where the awkward truths about that conversion live.
//
// WHAT IS EXACT AND WHAT IS NOT — the same distinction `geometry/maskRaster.js` draws for the
// Extent instrument, kept because it is the one that matters:
//
//   EXACT      `ringsFromRle` (via the existing exact decoder and pixel-boundary tracer),
//              `ringsFromBox`, `ringsFromRingPoints`, `fieldCells`, `thresholdCells`.
//              These rearrange the payload. They add nothing.
//   DERIVED    `isoSegments` interpolates between cell centres. `layoutTree` and `layoutGraph`
//              invent positions outright — a graph node has no location, and giving it one is a
//              convenience for the eye that must never be mistaken for a measurement. Both
//              produce `diagram` coordinates for exactly that reason.
//
// WHY THE ISOLINES ARE SEGMENTS AND NOT CURVES. A soft field in this contract is 4×4, or 2×3.
// Marching squares over a grid that coarse produces a smooth closed contour that looks like a
// careful measurement of a boundary, and it is an interpolation of sixteen numbers. So the
// contour here is drawn as the individual crossings between adjacent cells — one short segment
// per crossing, unjoined — which is precisely as much as the field supports and looks it.
//
// PURE MODULE.

import { decodeRle, maskRings, maskBox, maskCentroid } from '../geometry/maskRaster';
import { form } from '../contract/perceptionLabContract';

/* ── masks, rings, boxes ─────────────────────────────────────────────────── */

/**
 * A COCO RLE → exact boundary rings, normalized against its own raster.
 *
 * Returns `null` rather than an empty ring list when there is no mask, because "this instance
 * carries no mask" and "this instance's mask is empty" are different findings and the second one
 * is a real measurement worth showing.
 */
export function ringsFromRle(rle) {
    const raster = decodeRle(rle);
    if (!raster) return null;
    return {
        rings: maskRings(raster),
        raster: { h: raster.h, w: raster.w },
        box: maskBox(raster),
        centroid: maskCentroid(raster),
        exact: true,
    };
}

/** A declared box as a four-point ring. Exact as a rectangle; a projection of whatever it bounds. */
export function ringsFromBox(box) {
    if (!box || ![box.x, box.y, box.w, box.h].every((v) => typeof v === 'number')) return null;
    return {
        rings: [[
            [box.x, box.y], [box.x + box.w, box.y],
            [box.x + box.w, box.y + box.h], [box.x, box.y + box.h],
        ]],
        raster: null,
        box: { ...box },
        centroid: { x: box.x + box.w / 2, y: box.y + box.h / 2 },
        exact: true,
    };
}

/**
 * The contract's explicit ring points, carried through unchanged.
 *
 * `extent.boundary_rings` and `extent.hole_set` are the two forms whose whole purpose is that the
 * boundary is RECORDED rather than traced in a browser. Touching these coordinates — smoothing,
 * resampling, closing an open ring — would erase the only difference between those forms and a
 * hard mask, so this function does nothing but check the shape and hand them back.
 */
export function ringsFromRingPoints(rings = []) {
    const usable = (rings || []).filter(
        (r) => Array.isArray(r?.points) && r.points.length >= 2);
    if (!usable.length) return null;
    return {
        rings: usable.map((r) => r.points.map(([x, y]) => [x, y])),
        windings: usable.map((r) => r.winding || 'outer'),
        ring_ids: usable.map((r) => r.ring_id),
        closed: usable.map((r) => r.closed !== false),
        raster: null,
        exact: true,
    };
}

/** The centroid of a ring set, for a label anchor. Unweighted — a label position, not a measure. */
export function ringsCentroid(rings = []) {
    let n = 0; let sx = 0; let sy = 0;
    for (const ring of rings) for (const [x, y] of ring) { sx += x; sy += y; n += 1; }
    return n ? { x: sx / n, y: sy / n } : null;
}

/* ── scalar fields ───────────────────────────────────────────────────────── */

/**
 * A `ScalarField` payload → drawable cells, or a refusal.
 *
 * THE REFUSAL IS THE POINT. A field may live behind `data_ref` — a URI this page cannot read. The
 * available alternative is to draw a plausible gradient from the `statistics` block, and that
 * would be the most convincing false image this surface could produce: a smooth, confident wash
 * over the whole frame, derived from three numbers. So when the values are not present this
 * returns `{available: false, why}` and every caller renders the sentence instead of a picture.
 *
 * `value_range` from the payload is preferred over the observed min/max, because a field whose
 * values happen to span 0.2–0.4 inside a declared 0–1 range is a FLAT field, and rescaling it to
 * the observed span would redraw it as a dramatic one.
 */
export function fieldCells(field) {
    if (!field) return { available: false, why: 'this form carries no field' };
    const shape = field.field_shape;
    if (!Array.isArray(shape) || shape.length !== 2) {
        return { available: false, why: 'the field declares no shape' };
    }
    const [h, w] = shape;
    const values = field.inline_values;
    if (!Array.isArray(values) || values.length !== h * w) {
        return {
            available: false,
            shape: { h, w },
            why: field.data_ref
                ? `the ${h}×${w} field is held behind data_ref (${field.data_ref}) and is not on `
                  + 'this page. The statistics beside it are the measurement; a wash drawn from '
                  + 'them would be invented'
                : `the field declares a ${h}×${w} shape and carries no values for it`,
        };
    }
    const declared = Array.isArray(field.value_range) && field.value_range.length === 2
        ? field.value_range : null;
    let min = Infinity; let max = -Infinity; let sum = 0;
    for (const v of values) { if (v < min) min = v; if (v > max) max = v; sum += v; }
    const lo = declared ? declared[0] : min;
    const hi = declared ? declared[1] : max;
    const span = (hi - lo) || 1;
    const cells = [];
    for (let r = 0; r < h; r += 1) {
        for (let c = 0; c < w; c += 1) {
            const value = values[r * w + c];
            cells.push({
                row: r, col: c,
                x: c / w, y: r / h, w: 1 / w, h: 1 / h,
                value,
                intensity: Math.max(0, Math.min(1, (value - lo) / span)),
            });
        }
    }
    return {
        available: true,
        cells,
        shape: { h, w },
        observed: { min, max, mean: sum / values.length },
        range: { lo, hi, declared: !!declared },
        derivation: field.derivation ?? null,
        calibration: field.calibration ?? null,
        coordinate_system: field.coordinate_system ?? null,
    };
}

/**
 * Binarize a field at a threshold — and carry the threshold out with the result.
 *
 * The signature is the argument: there is no way to call this and end up holding cells without
 * also holding the number that made them. `layerModel.assertLayer` then refuses any binarized
 * layer whose threshold is missing, so the rule "never turn a scalar field into a binary mask
 * without showing the threshold" is enforced at two points and conventional at neither.
 */
export function thresholdCells(fieldResult, value, { source = 'chosen here' } = {}) {
    if (!fieldResult?.available) return { available: false, why: fieldResult?.why, threshold: null };
    const inside = fieldResult.cells.filter((c) => c.value >= value);
    return {
        available: true,
        cells: inside.map((c) => ({ ...c, intensity: 1 })),
        excluded: fieldResult.cells.length - inside.length,
        covered_fraction: fieldResult.cells.length ? inside.length / fieldResult.cells.length : 0,
        shape: fieldResult.shape,
        threshold: { value, source, applied: true },
    };
}

/**
 * Isolines as unjoined cell crossings — see the header for why they are not curves.
 *
 * A crossing is emitted on the edge between two horizontally or vertically adjacent cells whose
 * values straddle the level, positioned by linear interpolation along that edge. The segment
 * drawn is perpendicular to the edge and one third of a cell long: enough to read as a contour
 * mark, short enough that nobody mistakes the set for a closed boundary.
 */
export function isoSegments(fieldResult, levels = []) {
    if (!fieldResult?.available) return [];
    const { shape, cells } = fieldResult;
    const { h, w } = shape;
    const at = (r, c) => cells[r * w + c];
    const out = [];
    for (const level of levels) {
        for (let r = 0; r < h; r += 1) {
            for (let c = 0; c < w; c += 1) {
                const a = at(r, c);
                if (c + 1 < w) {
                    const b = at(r, c + 1);
                    if ((a.value - level) * (b.value - level) < 0) {
                        const t = (level - a.value) / (b.value - a.value);
                        const x = (c + 0.5 + t) / w;
                        const y = (r + 0.5) / h;
                        out.push({ level, x1: x, y1: y - 1 / (3 * h), x2: x, y2: y + 1 / (3 * h) });
                    }
                }
                if (r + 1 < h) {
                    const b = at(r + 1, c);
                    if ((a.value - level) * (b.value - level) < 0) {
                        const t = (level - a.value) / (b.value - a.value);
                        const y = (r + 0.5 + t) / h;
                        const x = (c + 0.5) / w;
                        out.push({ level, x1: x - 1 / (3 * w), y1: y, x2: x + 1 / (3 * w), y2: y });
                    }
                }
            }
        }
    }
    return out;
}

/** Sensible sweep stops for a field, inside its declared range. Deterministic, never random. */
export function sweepStops(fieldResult, count = 5) {
    if (!fieldResult?.available) return [];
    const { lo, hi } = fieldResult.range;
    const span = hi - lo;
    return Array.from({ length: count },
        (_, i) => Math.round((lo + (span * (i + 1)) / (count + 1)) * 1000) / 1000);
}

/* ── trees and graphs: diagram space, and it says so ─────────────────────── */

/**
 * Lay out a parent-linked node list.
 *
 * `nodes` need only `node_id` and `parent_node_id`. Positions are in `diagram` coordinates —
 * [0,1] on both axes with no relation to any pixel — and every caller stamps the layer's
 * coordinate system accordingly so the stage cannot accept one.
 *
 * A node whose declared parent is not in the list is treated as a root AND flagged: a containment
 * tree with a dangling parent is a real finding about the record, and silently re-rooting it
 * would hide the break.
 */
export function layoutTree(nodes = [], { rootIds = null } = {}) {
    const byId = new Map(nodes.map((n) => [n.node_id, n]));
    const dangling = nodes
        .filter((n) => n.parent_node_id && !byId.has(n.parent_node_id))
        .map((n) => ({ node_id: n.node_id, missing_parent: n.parent_node_id }));
    const isRoot = (n) => !n.parent_node_id || !byId.has(n.parent_node_id);
    const declaredRoots = Array.isArray(rootIds) && rootIds.length
        ? rootIds.filter((id) => byId.has(id)) : null;
    const roots = declaredRoots || nodes.filter(isRoot).map((n) => n.node_id);
    const childrenOf = new Map();
    for (const n of nodes) {
        if (isRoot(n) && !roots.includes(n.node_id)) continue;
        if (isRoot(n)) continue;
        const list = childrenOf.get(n.parent_node_id) || [];
        list.push(n.node_id);
        childrenOf.set(n.parent_node_id, list);
    }
    // Nodes the declared roots do not reach. Named, not dropped.
    const reached = new Set();
    let leafIndex = 0;
    let maxDepth = 0;
    const placed = new Map();
    const walk = (id, depth) => {
        if (reached.has(id)) return null;              // a cycle: stop, and report it below
        reached.add(id);
        maxDepth = Math.max(maxDepth, depth);
        const kids = (childrenOf.get(id) || []).map((k) => walk(k, depth + 1)).filter((v) => v !== null);
        const x = kids.length
            ? kids.reduce((a, b) => a + b, 0) / kids.length
            : (leafIndex += 1) - 0.5;
        placed.set(id, { depth, x });
        return x;
    };
    for (const r of roots) walk(r, 0);
    const unreached = nodes.filter((n) => !reached.has(n.node_id)).map((n) => n.node_id);
    const spanX = Math.max(leafIndex, 1);
    const spanY = Math.max(maxDepth, 1);
    const positioned = nodes
        .filter((n) => placed.has(n.node_id))
        .map((n) => {
            const p = placed.get(n.node_id);
            return {
                ...n,
                x: p.x / spanX,
                y: spanY ? (p.depth / spanY) * 0.86 + 0.07 : 0.5,
                depth: p.depth,
            };
        });
    const edges = positioned
        .filter((n) => n.parent_node_id && placed.has(n.parent_node_id))
        .map((n) => {
            const p = positioned.find((q) => q.node_id === n.parent_node_id);
            return {
                edge_id: `${n.parent_node_id}->${n.node_id}`,
                from: { x: p.x, y: p.y },
                to: { x: n.x, y: n.y },
                source_node_id: n.parent_node_id,
                target_node_id: n.node_id,
                // A containment tree edge is DIRECTED and the direction is the claim: the parent
                // contains the child, not the other way round. Drawn with an arrowhead for that
                // reason, and tested for it.
                directed: true,
                occupancy_of_parent: n.occupancy_of_parent ?? null,
            };
        });
    return { nodes: positioned, edges, roots, dangling, unreached, depth: maxDepth };
}

/**
 * Lay out a node/edge graph on a circle, in `diagram` coordinates.
 *
 * A circle rather than a force layout, because a force layout is nondeterministic and this whole
 * directory is fixture-driven: the same payload must produce the same picture on every run and in
 * every screenshot. It is also honest about being arbitrary — nobody looks at a ring of evenly
 * spaced nodes and believes the positions mean anything, which is the correct belief.
 */
export function layoutGraph(nodes = [], edges = []) {
    const n = nodes.length;
    const R = 0.36;
    const positioned = nodes.map((node, i) => {
        const angle = (-Math.PI / 2) + (2 * Math.PI * i) / Math.max(n, 1);
        return { ...node, x: 0.5 + R * Math.cos(angle), y: 0.5 + R * Math.sin(angle), index: i };
    });
    const byId = new Map(positioned.map((p) => [p.node_id, p]));
    const drawn = [];
    const dangling = [];
    for (const e of edges) {
        const a = byId.get(e.source_node_id);
        const b = byId.get(e.target_node_id);
        if (!a || !b) {
            dangling.push({
                edge_id: e.edge_id,
                missing: [!a && e.source_node_id, !b && e.target_node_id].filter(Boolean),
            });
            continue;
        }
        drawn.push({ ...e, from: { x: a.x, y: a.y }, to: { x: b.x, y: b.y } });
    }
    const degree = new Map(positioned.map((p) => [p.node_id, 0]));
    for (const e of drawn) {
        degree.set(e.source_node_id, degree.get(e.source_node_id) + 1);
        degree.set(e.target_node_id, degree.get(e.target_node_id) + 1);
    }
    return {
        nodes: positioned.map((p) => ({ ...p, degree: degree.get(p.node_id) })),
        edges: drawn,
        dangling,
        isolated: positioned.filter((p) => !degree.get(p.node_id)).map((p) => p.node_id),
    };
}

/**
 * The full adjacency matrix for a graph, including the pairs with no edge.
 *
 * `topology.adjacency_graph` records the edges it found; `pairs_examined` records how many pairs
 * were looked at. Those two numbers rarely match, and the difference is the set of pairs that
 * were examined and found to have no relation — which a node-link drawing renders as empty space
 * indistinguishable from "never checked". The matrix is the view where that distinction survives.
 */
export function adjacencyMatrix(nodes = [], edges = []) {
    const ids = nodes.map((n) => n.node_id);
    const byPair = new Map();
    for (const e of edges) {
        byPair.set(`${e.source_node_id}|${e.target_node_id}`, e);
        if (!e.directed) byPair.set(`${e.target_node_id}|${e.source_node_id}`, e);
    }
    return {
        ids,
        rows: ids.map((rowId) => ({
            node_id: rowId,
            cells: ids.map((colId) => ({
                row: rowId,
                col: colId,
                self: rowId === colId,
                edge: byPair.get(`${rowId}|${colId}`) || null,
            })),
        })),
        recorded_edges: edges.length,
    };
}

/**
 * The counter that says this form looked, read from the field the CONTRACT names.
 *
 * Every one of the nineteen forms declares an `absence.examined_field` — `searched`,
 * `pairs_examined`, `candidates_examined`, `figure_instance_ids` — because of the
 * `every_form_can_say_it_looked` law. Rendering results without it turns "examined six pairs,
 * two are related" into "there are two relations", which is a different and much stronger claim,
 * and turns an empty result into a blank panel that reads as a bug.
 *
 * THE FIELD NAME IS NOT RE-TYPED HERE. It is looked up per form, so a form whose counter is
 * renamed in the contract does not quietly stop being reported by a table in this file that
 * nobody thought to update. `empty_means` comes back with it: when the collection is empty, the
 * sentence a person should read is the one the contract already wrote for exactly that case.
 */
export function examinationOf(payload, formKey) {
    const declaration = formKey ? form(formKey) : null;
    const field = declaration?.absence?.examined_field;
    if (!field) return null;
    const raw = payload?.[field];
    if (raw === undefined || raw === null) return null;
    return {
        field,
        label: field.replace(/_/g, ' '),
        // A list-valued counter — `figure_instance_ids` — is reported by its length AND its
        // members, because "two figures" and "which two" are both part of what was examined.
        value: Array.isArray(raw) ? raw.length : raw,
        members: Array.isArray(raw) ? raw : null,
        empty_means: declaration.absence.empty_means ?? null,
        may_not_be_confused_with: declaration.absence.may_not_be_confused_with ?? [],
    };
}
