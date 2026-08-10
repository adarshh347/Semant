// PERCEPTUAL-ORGANS-002 Lane E — projections, and the line between them and measurements.
//
// A topology artifact carries numbers: `contact_pixels`, `contact_fraction_of_source_perimeter`,
// `containment`, `scale_ratio`. It does NOT carry the shape of the contact band, because the band
// is a drawing and the contract keeps drawings out of the measurement block (`projection.hints`
// is clamped to seven presentational keys precisely so geometry cannot sneak in there).
//
// So the band on the image is computed HERE, from the two endpoint masks, in this browser. Which
// makes it a second thing, and the whole discipline of this file is refusing to let the two
// collapse:
//
//   1. every function returns `{ derived: true, ... }` and the components render nothing from
//      here without the "derived projection" treatment;
//   2. every return carries `basis` and `computed_by: 'lab_browser'`, so a person reading a
//      contact band knows it was drawn by the page and not by `adjacency_organ`;
//   3. `agreement()` compares the derived count against the producer's number and reports the
//      disagreement rather than hiding it. A band that does not match the measurement is a fact
//      about this pair worth seeing, not a bug to paper over;
//   4. NOTHING here writes back into an artifact. Callers hold projections beside artifacts.
//
// A projection also refuses. Two masks on different rasters cannot be intersected, and inventing
// a resample to make a picture appear would be this file deciding what the measurement was.
//
// PURE MODULE.

import {
    dilate, maskAnd, maskAreaFraction, maskArea, maskBox, maskCentroid, maskRings, maskSub,
    nearestPair,
} from './maskRaster';

const unavailable = (why) => ({ derived: true, available: false, why, rings: [] });

const projection = (kind, fields) => ({
    derived: true,
    available: true,
    computed_by: 'lab_browser',
    projection_kind: kind,
    ...fields,
});

/** The measured mask, as rings. Exact — the only entry here that is not an interpretation. */
export function extentProjection(mask) {
    if (!mask) return unavailable('this instance carries no mask raster');
    return projection('mask_fill', {
        rings: maskRings(mask),
        raster: { h: mask.h, w: mask.w },
        area_fraction: maskAreaFraction(mask),
        exact: true,
    });
}

/**
 * The bounding box of a mask, drawn as a box and named as one.
 *
 * Offered so a person can SEE the difference between the two bases on the same shape — the whole
 * argument for why a box-basis containment stays interpretive is visible in one toggle.
 */
export function boxProjection(mask) {
    if (!mask) return unavailable('this instance carries no mask raster');
    const box = maskBox(mask);
    if (!box) return unavailable('the mask is empty, so it has no box');
    return projection('box_outline', {
        rings: [[
            [box.x, box.y], [box.x + box.w, box.y],
            [box.x + box.w, box.y + box.h], [box.x, box.y + box.h],
        ]],
        box,
        over_estimate_fraction: box.w * box.h > 0
            ? 1 - (maskAreaFraction(mask) / (box.w * box.h)) : null,
        exact: false,
    });
}

/**
 * The contact band between two masks — the actual overlap of their dilations, not a line between
 * centroids. `contact_tolerance_px` comes from the MEASUREMENT so the drawing is made under the
 * producer's own tolerance rather than one this file picked.
 */
export function contactBandProjection(a, b, { tolerance_px = 1 } = {}) {
    if (!a || !b) return unavailable('a contact band needs both endpoint masks');
    if (a.h !== b.h || a.w !== b.w) {
        return unavailable(
            `the endpoints are on different rasters (${a.h}×${a.w} and ${b.h}×${b.w}); `
            + 'resampling one to draw a band would invent the contact');
    }
    const r = Math.max(1, Math.round(tolerance_px));
    const band = maskAnd(dilate(a, r), dilate(b, r));
    const px = maskArea(band);
    return projection('contact_band', {
        rings: maskRings(band),
        raster: { h: a.h, w: a.w },
        tolerance_px: r,
        derived_contact_pixels: px,
        touches: px > 0,
        exact: false,
    });
}

/** The exact pixel intersection. Exact as arithmetic; still a drawing of the measurement. */
export function intersectionProjection(a, b) {
    if (!a || !b) return unavailable('an intersection needs both endpoint masks');
    if (a.h !== b.h || a.w !== b.w) {
        return unavailable(`the endpoints are on different rasters (${a.h}×${a.w} and ${b.h}×${b.w})`);
    }
    const inter = maskAnd(a, b);
    const px = maskArea(inter);
    return projection('intersection_area', {
        rings: maskRings(inter),
        raster: { h: a.h, w: a.w },
        derived_intersection_pixels: px,
        derived_iou: (() => {
            const union = maskArea(a) + maskArea(b) - px;
            return union ? px / union : null;
        })(),
        exact: true,
    });
}

/** Source-only and target-only regions — what an overlap leaves behind on each side. */
export function differenceProjection(a, b) {
    if (!a || !b || a.h !== b.h || a.w !== b.w) return unavailable('a difference needs two masks on one raster');
    return projection('difference_overlay', {
        rings: maskRings(maskSub(a, b)),
        other_rings: maskRings(maskSub(b, a)),
        raster: { h: a.h, w: a.w },
        exact: true,
    });
}

/**
 * The two endpoints as anchors plus the direction between them.
 *
 * `directed` decides whether an arrowhead is drawn at all. An undirected `meets` rendered with an
 * arrow would assert an asymmetry the organ did not measure.
 */
export function endpointPairProjection(a, b, { directed = false } = {}) {
    const from = a ? maskCentroid(a) : null;
    const to = b ? maskCentroid(b) : null;
    if (!from || !to) {
        return unavailable(from || to
            ? 'one endpoint did not resolve to a mask, so the pair cannot be anchored'
            : 'neither endpoint resolved to a mask');
    }
    return projection('endpoint_pair', {
        rings: [],
        from,
        to,
        directed,
        exact: false,
    });
}

/** The measured clearance for a disjoint pair: the closest points, and the gap between them. */
export function clearanceProjection(a, b) {
    if (!a || !b) return unavailable('a clearance needs both endpoint masks');
    if (a.h !== b.h || a.w !== b.w) return unavailable('the endpoints are on different rasters');
    const near = nearestPair(a, b);
    if (!near) return unavailable('one of the endpoints is empty');
    return projection('endpoint_pair', {
        rings: [],
        from: near.from,
        to: near.to,
        derived_distance_px: near.distance_px,
        derived_distance_fraction: near.distance_fraction,
        directed: false,
        exact: false,
    });
}

/**
 * A negative-space scalar field as a coarse cell grid for the wash.
 *
 * The artifact stores the field behind a `field_ref` (a URI the lab cannot read) or inline in
 * `values`. When only the ref is present this refuses rather than drawing a plausible gradient —
 * a wash invented from statistics would be the single most convincing lie this surface could tell.
 */
export function scalarWashProjection(payload) {
    const shape = payload?.field_shape;
    const values = payload?.values;
    if (!Array.isArray(shape) || shape.length !== 2) return unavailable('the field declares no shape');
    if (!Array.isArray(values) || values.length !== shape[0] * shape[1]) {
        return unavailable(
            'the field itself is held behind `field_ref` and is not in this payload. The '
            + 'statistics above are the measurement; a wash drawn from them would be invented.');
    }
    const [h, w] = shape;
    let min = Infinity; let max = -Infinity;
    for (const v of values) { if (v < min) min = v; if (v > max) max = v; }
    const span = max - min || 1;
    const cells = [];
    for (let r = 0; r < h; r++) {
        for (let c = 0; c < w; c++) {
            cells.push({
                x: c / w, y: r / h, w: 1 / w, h: 1 / h,
                value: values[r * w + c],
                intensity: (values[r * w + c] - min) / span,
            });
        }
    }
    return projection('scalar_wash', { rings: [], cells, shape: { h, w }, min, max, exact: true });
}

/**
 * A negative-space wash computed HERE from the figure masks.
 *
 * The measured field is behind `field_ref` and this page cannot read it, so the alternative to
 * this function is a topology instrument that can measure negative space and never show it. The
 * answer is not to pretend: this is a Chebyshev distance transform over the complement of the
 * supplied masks, run in the browser, truncated at the SAME `max_distance_used` the artifact
 * recorded — and every caller renders it under "derived here, not the measured field".
 *
 * `agrees_with_statistics` compares its own min/max/mean against the artifact's, which is the
 * closest thing to a check on the real field that this side of the wire can perform.
 */
export function deriveNegativeSpaceField(masks, { max_distance = 1, statistics = null } = {}) {
    const present = (masks || []).filter(Boolean);
    if (!present.length) return unavailable('no figure mask resolved, so there is no complement');
    const { h, w } = present[0];
    if (present.some((m) => m.h !== h || m.w !== w)) {
        return unavailable('the figures are on different rasters; their complement is undefined');
    }
    const INF = h + w;
    const dist = new Float64Array(h * w);
    for (let i = 0; i < h * w; i++) dist[i] = present.some((m) => m.data[i]) ? 0 : INF;
    // Two passes of the chamfer transform with a chessboard metric.
    for (let r = 0; r < h; r++) {
        for (let c = 0; c < w; c++) {
            const i = r * w + c;
            if (!dist[i]) continue;
            let best = dist[i];
            if (r > 0) best = Math.min(best, dist[i - w] + 1);
            if (c > 0) best = Math.min(best, dist[i - 1] + 1);
            if (r > 0 && c > 0) best = Math.min(best, dist[i - w - 1] + 1);
            if (r > 0 && c < w - 1) best = Math.min(best, dist[i - w + 1] + 1);
            dist[i] = best;
        }
    }
    for (let r = h - 1; r >= 0; r--) {
        for (let c = w - 1; c >= 0; c--) {
            const i = r * w + c;
            let best = dist[i];
            if (r < h - 1) best = Math.min(best, dist[i + w] + 1);
            if (c < w - 1) best = Math.min(best, dist[i + 1] + 1);
            if (r < h - 1 && c < w - 1) best = Math.min(best, dist[i + w + 1] + 1);
            if (r < h - 1 && c > 0) best = Math.min(best, dist[i + w - 1] + 1);
            dist[i] = best;
        }
    }
    const diag = Math.sqrt(h * h + w * w);
    const cells = [];
    let min = Infinity; let max = -Infinity; let sum = 0;
    for (let r = 0; r < h; r++) {
        for (let c = 0; c < w; c++) {
            const v = Math.min(dist[r * w + c] / diag, max_distance);
            if (v < min) min = v;
            if (v > max) max = v;
            sum += v;
            cells.push({ x: c / w, y: r / h, w: 1 / w, h: 1 / h, value: v });
        }
    }
    const span = max - min || 1;
    for (const cell of cells) cell.intensity = (cell.value - min) / span;
    const own = { min, max, mean: sum / cells.length };
    return projection('scalar_wash', {
        rings: [],
        cells,
        shape: { h, w },
        min,
        max,
        statistics: own,
        exact: false,
        agrees_with_statistics: statistics
            ? ['min', 'max', 'mean'].every((k) => typeof statistics[k] !== 'number'
                || Math.abs(statistics[k] - own[k]) <= 0.1)
            : null,
        why: 'computed in this browser from the figure masks. The measured field is behind '
            + '`field_ref` and is not on this page.',
    });
}

/**
 * Does the drawing agree with the number the producer reported?
 *
 * Returns null when there is nothing to compare. `within` is deliberately generous: the point is
 * not to grade the backend, it is to catch the case where the band a person is looking at is
 * describing a different pair than the number beside it.
 */
export function agreement(derivedValue, measuredValue, { tolerance = 0.25 } = {}) {
    if (typeof derivedValue !== 'number' || typeof measuredValue !== 'number') return null;
    const scale = Math.max(Math.abs(measuredValue), 1);
    const delta = derivedValue - measuredValue;
    return {
        derived: derivedValue,
        measured: measuredValue,
        delta,
        agrees: Math.abs(delta) / scale <= tolerance,
    };
}
