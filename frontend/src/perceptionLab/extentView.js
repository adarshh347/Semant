// PERCEPTUAL-ORGANS-002 Lane E — an extent_set, read for drawing.
//
// The problem this file exists to solve, plainly:
//
//     The contract's extent instances carry `mask_rle` and `box`. They carry no polygons. The
//     app's one shape renderer — `RegionOverlay` — consumes normalized rings. Drawing the box
//     because the box is the thing that is already ring-shaped is exactly the WAVE2.5 failure
//     `curator/ProposalMasks.jsx` was written to warn about: the picture is a rectangle, the
//     measurement was per-pixel, and nobody on the surface can tell which they are looking at.
//
// So the mask is decoded exactly and its boundary traced exactly, and the rings are normalized
// against THE RASTER rather than the image. A 4×4 mask on a 1600×1200 photograph is a real thing
// Lane B produces, and it lands correctly because the normalization is against the grid the
// measurement was taken on. The raster shape is carried alongside so the inspector can say so:
// a mask that is coarse is not a mask that is wrong, but it is a mask whose edge is 300px thick
// and a person should be told that rather than shown a crisp line.
//
// PURE MODULE. Data in, drawable shapes and honest numbers out. No React, no DOM, no clock.

import {
    decodeRle, maskAnd, maskArea, maskAreaFraction, maskBox, maskOr, maskSub,
} from './geometry/maskRaster';
import { boxProjection, extentProjection } from './geometry/projections';

/** Named vs withheld vs uncertain — three states, and an absent name is none of them by default. */
export function namingState(instance) {
    if (!instance?.naming) {
        return {
            state: 'withheld',
            text: null,
            note: 'no name. The geometry came back and the reading did not — below the naming '
                + 'floor the mask survives and the word does not. This is not an unknown object.',
        };
    }
    if (instance.naming.epistemic_status === 'uncertain') {
        return {
            state: 'uncertain',
            text: instance.naming.text,
            note: 'a name offered without a claim. It is on the record as a guess and it is not '
                + 'the measurement.',
        };
    }
    return {
        state: 'interpretive',
        text: instance.naming.text,
        note: 'a reading of the mask, carrying its own status. A measured mask with an '
            + 'interpretive name is the ordinary case.',
    };
}

/**
 * Decode every instance once.
 *
 * `mask` is null when the instance is box-only, and that is left null rather than filled in from
 * the box. A box rasterized into a mask would make a box basis look per-pixel to everything
 * downstream, which is the one substitution the epistemics forbid.
 */
export function decodeInstances(artifact) {
    const payload = artifact?.measurement?.payload;
    if (payload?.variant !== 'extent_set') return [];
    return payload.instances.map((inst) => ({
        instance_id: inst.instance_id,
        artifact_id: artifact.identity.artifact_id,
        naming: namingState(inst),
        confidence: inst.confidence,
        area: inst.area,
        region_id: inst.region_id,
        geometry_rev: inst.geometry_rev,
        box: inst.box,
        mask: inst.mask_rle ? decodeRle(inst.mask_rle) : null,
        mask_rle: inst.mask_rle,
    }));
}

/**
 * Instances → regions `RegionOverlay` can draw.
 *
 * `basis` is a deliberate control rather than a fallback. On `mask` the exact boundary is traced;
 * on `box` the bounding rectangle is drawn AND labelled as one, so the difference between the two
 * bases is visible on the same shape in one toggle — which is the whole argument for why a
 * box-basis relation stays interpretive, made in pixels instead of in a tooltip.
 */
export function instanceRegions(instances, { basis = 'mask' } = {}) {
    return instances.map((inst) => {
        const drawn = basis === 'box' || !inst.mask
            ? (inst.mask ? boxProjection(inst.mask) : boxFromDeclared(inst.box))
            : extentProjection(inst.mask);
        return {
            id: inst.instance_id,
            polygons: drawn.available ? drawn.rings : [],
            box: inst.box,
            basis: inst.mask ? (basis === 'box' ? 'box' : 'mask') : 'box',
            exact: drawn.available ? drawn.exact === true : false,
            raster: drawn.raster || null,
            unavailable: drawn.available ? null : drawn.why,
            over_estimate_fraction: drawn.over_estimate_fraction ?? null,
            naming: inst.naming,
            geometry_rev: inst.geometry_rev,
        };
    });
}

/** A declared box with no mask behind it. Drawn, and never called exact. */
function boxFromDeclared(box) {
    if (!box) {
        return { derived: true, available: false, rings: [],
            why: 'this instance carries neither a mask nor a box' };
    }
    return {
        derived: true,
        available: true,
        exact: false,
        rings: [[
            [box.x, box.y], [box.x + box.w, box.y],
            [box.x + box.w, box.y + box.h], [box.x, box.y + box.h],
        ]],
        over_estimate_fraction: null,
    };
}

/**
 * How coarse the grid this was measured on actually is, in image pixels.
 *
 * Reported because it is the difference between an edge a person can trust and an edge that is
 * forty pixels thick. The surface draws the same crisp line either way; only this number says
 * which one it is.
 */
export function rasterCoarseness(instances, natural) {
    const withMask = instances.filter((i) => i.mask);
    if (!withMask.length || !natural) return null;
    const { h, w } = withMask[0].mask;
    return {
        raster: { h, w },
        cell_px: { x: natural.w / w, y: natural.h / h },
        coarse: natural.w / w > 4 || natural.h / h > 4,
    };
}

/**
 * Duplicate, overlap and repeat metrics over one set — and, when a second set is given, across
 * the two.
 *
 * REPEAT IS NOT DUPLICATE, and collapsing them is how "the adapter is stable" gets asserted from
 * evidence that only shows it returned the same number of things:
 *
 *   duplicates   two instances IN ONE SET whose masks substantially coincide. A finding about the
 *                adapter's separation of instances.
 *   repeats      an instance in set A matched to one in set B. A finding about STABILITY across
 *                two runs of the same question, and it is only meaningful when the two sets came
 *                from the same image.
 *
 * Everything here is exact mask arithmetic on a shared raster. Sets on different rasters are
 * refused rather than resampled, and the refusal is returned as a value so a caller must render
 * it — a `null` would be silently drawn as "no duplicates".
 */
export function overlapMetrics(instances, other = null, { duplicateThreshold = 0.6,
    repeatThreshold = 0.5 } = {}) {
    const masked = instances.filter((i) => i.mask);
    const pairs = [];
    for (let i = 0; i < masked.length; i += 1) {
        for (let j = i + 1; j < masked.length; j += 1) {
            const iou = iouOf(masked[i].mask, masked[j].mask);
            if (iou === null) continue;
            pairs.push({ a: masked[i].instance_id, b: masked[j].instance_id, iou });
        }
    }
    const out = {
        pairs_examined: pairs.length,
        overlapping: pairs.filter((p) => p.iou > 0),
        duplicates: pairs.filter((p) => p.iou >= duplicateThreshold),
        // Stated, because a duplicate is a THRESHOLD and not a fact. This default is the one the
        // Extent façade records at; a panel quietly using a stricter one would disagree with the
        // artifact's own `duplicates` list and neither number would say why.
        duplicate_threshold: duplicateThreshold,
        repeat_threshold: repeatThreshold,
        repeats: null,
        refusal: null,
    };
    if (!other) return out;

    const otherMasked = other.filter((i) => i.mask);
    const mismatched = masked.length && otherMasked.length
        && (masked[0].mask.h !== otherMasked[0].mask.h
            || masked[0].mask.w !== otherMasked[0].mask.w);
    if (mismatched) {
        out.refusal = 'the two sets were measured on different rasters, so nothing here can be '
            + 'matched across them without a resample this laboratory will not perform';
        return out;
    }
    const matches = [];
    for (const a of masked) {
        let best = null;
        for (const b of otherMasked) {
            const iou = iouOf(a.mask, b.mask);
            if (iou === null) continue;
            if (!best || iou > best.iou) best = { a: a.instance_id, b: b.instance_id, iou };
        }
        matches.push(best || { a: a.instance_id, b: null, iou: 0 });
    }
    out.repeats = {
        matched: matches.filter((m) => m.iou >= repeatThreshold),
        unmatched: matches.filter((m) => m.iou < repeatThreshold),
        only_in_other: otherMasked
            .filter((b) => !matches.some(
                (m) => m.b === b.instance_id && m.iou >= repeatThreshold))
            .map((b) => b.instance_id),
        mean_iou: matches.length
            ? matches.reduce((s, m) => s + m.iou, 0) / matches.length : null,
    };
    return out;
}

function iouOf(a, b) {
    const inter = maskAnd(a, b);
    const union = maskOr(a, b);
    if (!inter || !union) return null;             // different rasters — never resampled
    const u = maskArea(union);
    return u ? maskArea(inter) / u : 0;
}

/**
 * Before and after, as three drawable pieces.
 *
 * A refinement that only showed the result would let a person believe the boundary was always
 * there. `added` and `removed` are exact set differences, so what the refiner actually did is on
 * the screen rather than inferred from two similar shapes.
 */
export function beforeAfter(before, after) {
    if (!before?.mask || !after?.mask) {
        return { available: false,
            why: 'a before/after comparison needs a mask on both sides' };
    }
    if (before.mask.h !== after.mask.h || before.mask.w !== after.mask.w) {
        return { available: false,
            why: `the two revisions are on different rasters (${before.mask.h}×${before.mask.w} `
                + `and ${after.mask.h}×${after.mask.w}); nothing can be differenced across them` };
    }
    const added = maskSub(after.mask, before.mask);
    const removed = maskSub(before.mask, after.mask);
    return {
        available: true,
        derived: true,
        computed_by: 'lab_browser',
        before: extentProjection(before.mask),
        after: extentProjection(after.mask),
        added: extentProjection(added),
        removed: extentProjection(removed),
        added_fraction: maskAreaFraction(added),
        removed_fraction: maskAreaFraction(removed),
        net_fraction: maskAreaFraction(after.mask) - maskAreaFraction(before.mask),
        box_moved: JSON.stringify(maskBox(before.mask)) !== JSON.stringify(maskBox(after.mask)),
    };
}

/**
 * The lineage of an artifact, walked back through `derived_from`.
 *
 * Geometry revision is the point. An identity that survived a refinement is the SAME instance at
 * a later revision, and one that was minted is a different thing wearing a similar shape. A chain
 * that showed only "derived from" without the revision could not tell those apart.
 */
export function lineageOf(artifact, byId, seen = new Set()) {
    if (!artifact || seen.has(artifact.identity.artifact_id)) return [];
    seen.add(artifact.identity.artifact_id);
    const instances = artifact.measurement.payload?.variant === 'extent_set'
        ? artifact.measurement.payload.instances : [];
    const node = {
        artifact_id: artifact.identity.artifact_id,
        operation: artifact.identity.operation,
        run_id: artifact.identity.run_id,
        at: artifact.provenance.completed_at || artifact.provenance.started_at,
        instances: instances.map((i) => ({
            instance_id: i.instance_id,
            geometry_rev: i.geometry_rev,
            region_id: i.region_id,
        })),
    };
    const parents = (artifact.identity.derived_from || [])
        .map((id) => byId.get?.(id))
        .filter(Boolean)
        .flatMap((parent) => lineageOf(parent, byId, seen));
    return [node, ...parents];
}
