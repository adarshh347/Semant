// PERCEPTUAL-ORGANS-002 Lane E — a typed relation, resolved and made drawable.
//
// TWO PROBLEMS, AND THEY ARE DIFFERENT PROBLEMS.
//
// 1. RESOLUTION. A relation's endpoints are references — `{artifact_id, instance_id, scope,
//    region_id, geometry_rev}` — not masks. Resolving them can fail in ways that are findings
//    rather than errors: the artifact left the ledger, the instance is not in it, the geometry was
//    revised after the relation was measured. Each of those is a DANGLING or STALE state with its
//    own rendering, because a relation drawn between two endpoints that no longer mean what they
//    meant is a picture of something nobody measured.
//
// 2. PROJECTION. The relation carries `contact_pixels: 812` and no geometry. `projection.hints` is
//    clamped to seven presentational keys, so the band cannot arrive through there either. If the
//    band is going to appear on the image at all, this browser has to compute it — and the moment
//    it does, the drawing and the measurement are two different things that must not be allowed to
//    look like one. So every projection is stamped `derived: true, computed_by: 'lab_browser'`,
//    and `agreementFor` puts the derived number beside the producer's so a disagreement shows up
//    as a disagreement instead of as a picture.
//
// WHAT THIS FILE WILL NOT DO: resample. Two endpoints on different rasters cannot be intersected,
// and inventing a resample to make a band appear would be this file deciding what the measurement
// was. It returns the refusal instead, as a value, so a caller has to render it.
//
// PURE MODULE.

import { decodeRle } from './geometry/maskRaster';
import {
    agreement, clearanceProjection, contactBandProjection, endpointPairProjection,
    intersectionProjection, scalarWashProjection, deriveNegativeSpaceField,
} from './geometry/projections';

/** Which drawing a relation kind asks for. Typed, from the contract's own vocabulary. */
export const PROJECTION_FOR_KIND = Object.freeze({
    nested_within: 'endpoint_pair',
    contains: 'endpoint_pair',
    meets: 'contact_band',
    overlaps: 'intersection_area',
    disjoint: 'endpoint_pair',
    in_front_of: 'endpoint_pair',
    coplanar: 'endpoint_pair',
});

/** Whether a kind is directed, and therefore whether the arrow means anything. */
export const DIRECTED_KINDS = Object.freeze(
    new Set(['nested_within', 'contains', 'in_front_of']));

/**
 * The sentence for a kind, in the direction it was measured.
 *
 * A GENERIC RELATION IS A LOST RELATION. "these two are related" is what happens when a typed
 * measurement is rendered through free text, and it destroys the one thing the topology organ
 * produces: which of the two is inside the other. So each kind gets its own sentence, and the
 * direction is in the sentence rather than in an arrowhead somebody may not notice.
 */
export function relationSentence(kind, sourceName, targetName) {
    switch (kind) {
        case 'nested_within': return `${sourceName} is inside ${targetName}`;
        case 'contains': return `${sourceName} contains ${targetName}`;
        case 'meets': return `${sourceName} touches ${targetName}`;
        case 'overlaps': return `${sourceName} and ${targetName} overlap`;
        case 'disjoint': return `${sourceName} and ${targetName} are apart`;
        case 'in_front_of': return `${sourceName} is in front of ${targetName}`;
        case 'coplanar': return `${sourceName} and ${targetName} are at the same depth`;
        default: throw new Error(`no sentence for relation kind "${kind}" — a typed relation `
            + 'rendered as generic text loses the one thing it measured');
    }
}

/**
 * Resolve one endpoint reference against the ledger.
 *
 * Returns a state, always. `dangling` and `stale` are findings with renderings, not nulls to be
 * skipped: a relation whose endpoint has gone is exactly the thing a person needs to see, and
 * dropping it from the list would make the measurement look smaller than it was.
 */
export function resolveEndpoint(ref, byId) {
    if (!ref) return { state: 'dangling', why: 'the relation carries no reference for this role' };
    const artifact = byId.get?.(ref.artifact_id);
    if (!artifact) {
        return {
            state: 'dangling',
            ref,
            why: `${ref.artifact_id} is not in this session's ledger. The relation was measured `
                + 'against something that is no longer here.',
        };
    }
    const payload = artifact.measurement.payload;
    if (payload?.variant !== 'extent_set') {
        return { state: 'dangling', ref, artifact,
            why: `${ref.artifact_id} is a ${payload?.variant}, not a set of extents` };
    }
    const instance = ref.instance_id
        ? payload.instances.find((i) => i.instance_id === ref.instance_id)
        : payload.instances[0];
    if (!instance) {
        return { state: 'dangling', ref, artifact,
            why: `${ref.instance_id} is no longer an instance of ${ref.artifact_id}` };
    }
    // A revision that moved after the relation was measured makes the number a statement about a
    // boundary that is not the one on screen.
    const stale = ref.geometry_rev !== null && ref.geometry_rev !== undefined
        && instance.geometry_rev !== null && instance.geometry_rev !== undefined
        && instance.geometry_rev !== ref.geometry_rev;
    return {
        state: stale ? 'stale' : 'resolved',
        ref,
        artifact,
        instance,
        mask: instance.mask_rle ? decodeRle(instance.mask_rle) : null,
        box: instance.box,
        name: instance.naming?.text || instance.instance_id,
        why: stale
            ? `this endpoint was measured at revision ${ref.geometry_rev} and is now at `
                + `${instance.geometry_rev}. The number describes a boundary that has moved.`
            : null,
    };
}

/**
 * A relation, resolved and projected.
 *
 * `basis` comes from the RELATION, not from a toggle: a relation measured on boxes is drawn on
 * boxes, because drawing it on masks would show a person a per-pixel picture of an interpretive
 * number. The stage may offer the other basis as a separate, labelled layer; it may not silently
 * upgrade this one.
 */
export function projectRelation(relation, byId) {
    const source = resolveEndpoint(relation.source, byId);
    const target = resolveEndpoint(relation.target, byId);
    const kind = relation.kind;
    const directed = DIRECTED_KINDS.has(kind);
    const base = {
        relation_id: relation.relation_id,
        kind,
        directed,
        declared_directed: relation.directed,
        basis: relation.basis,
        epistemic_status: relation.epistemic_status,
        measurements: relation.measurements || {},
        stale: relation.stale === true || source.state === 'stale' || target.state === 'stale',
        source,
        target,
        sentence: relationSentence(kind,
            source.name || source.ref?.instance_id || 'an absent endpoint',
            target.name || target.ref?.instance_id || 'an absent endpoint'),
    };

    if (source.state === 'dangling' || target.state === 'dangling') {
        return { ...base, drawable: false,
            why: [source.why, target.why].filter(Boolean).join(' ') };
    }
    if (!source.mask || !target.mask) {
        return { ...base, drawable: false,
            why: 'an endpoint carries no mask raster, so nothing about this relation can be '
                + 'placed on the image. The number stands; the picture does not.' };
    }

    const wanted = PROJECTION_FOR_KIND[kind];
    let projection;
    if (wanted === 'contact_band') {
        projection = contactBandProjection(source.mask, target.mask, {
            tolerance_px: relation.measurements?.contact_tolerance_px ?? 1 });
    } else if (wanted === 'intersection_area') {
        projection = intersectionProjection(source.mask, target.mask);
    } else if (kind === 'disjoint') {
        projection = clearanceProjection(source.mask, target.mask);
    } else {
        projection = endpointPairProjection(source.mask, target.mask, { directed });
    }

    return {
        ...base,
        drawable: projection.available,
        why: projection.available ? null : projection.why,
        projection,
        // Every relation also gets its endpoint pair, so direction is on the image and not only
        // in the sentence.
        endpoints: endpointPairProjection(source.mask, target.mask, { directed }),
        agreement: agreementFor(relation, projection),
    };
}

/**
 * The derived number against the producer's, where the two are comparable.
 *
 * Only where they measure the same quantity. Comparing a derived contact-band area with a
 * producer's IoU would manufacture a disagreement out of two different questions, which is a
 * worse failure than not checking at all.
 */
export function agreementFor(relation, projection) {
    if (!projection?.available) return null;
    const m = relation.measurements || {};
    if (projection.projection_kind === 'contact_band'
        && typeof m.contact_pixels === 'number') {
        return { quantity: 'contact_pixels', ...agreement(
            projection.derived_contact_pixels, m.contact_pixels) };
    }
    if (projection.projection_kind === 'intersection_area' && typeof m.iou === 'number') {
        return { quantity: 'iou', ...agreement(projection.derived_iou, m.iou) };
    }
    // Only the clearance projection measures a distance; a plain endpoint pair anchors two
    // centroids and measures nothing, so there is nothing to agree or disagree with.
    if (typeof projection.derived_distance_fraction === 'number'
        && typeof m.distance_fraction === 'number') {
        return { quantity: 'distance_fraction', ...agreement(
            projection.derived_distance_fraction, m.distance_fraction) };
    }
    return null;
}

/** Every relation of an artifact, resolved and projected, in the order they were measured. */
export function projectRelationSet(artifact, byId) {
    const payload = artifact?.measurement?.payload;
    if (payload?.variant !== 'topology_relation_set') return [];
    return payload.relations.map((r) => projectRelation(r, byId));
}

/**
 * The graph over a set of relations: nodes are endpoints, edges are typed relations.
 *
 * A NODE IS AN ENDPOINT IDENTITY, not a name. Two instances that happen to be called "drapery"
 * are two nodes, because collapsing them by label would merge two measurements into one edge and
 * the graph would assert a relation nobody measured.
 */
export function relationGraph(projected) {
    const nodes = new Map();
    const addNode = (endpoint) => {
        const id = endpoint.ref
            ? `${endpoint.ref.artifact_id}#${endpoint.ref.instance_id || '*'}`
            : 'absent';
        if (!nodes.has(id)) {
            nodes.set(id, {
                id,
                name: endpoint.name || endpoint.ref?.instance_id || 'absent endpoint',
                state: endpoint.state,
                degree: 0,
            });
        }
        nodes.get(id).degree += 1;
        return id;
    };
    const edges = projected.map((p) => ({
        relation_id: p.relation_id,
        kind: p.kind,
        directed: p.directed,
        basis: p.basis,
        stale: p.stale,
        drawable: p.drawable,
        from: addNode(p.source),
        to: addNode(p.target),
        sentence: p.sentence,
    }));
    return { nodes: [...nodes.values()], edges };
}

/**
 * The negative-space wash, or the refusal to draw one.
 *
 * `NegativeSpaceFieldPayload` carries `field_ref` and statistics, and no values — the backend's
 * schema forbids inlining them. So `scalarWashProjection` refuses, and a wash appears only when
 * this browser derives one from the figure masks and says, on the wash, that it did.
 */
export function projectNegativeSpace(artifact, byId) {
    const payload = artifact?.measurement?.payload;
    if (payload?.variant !== 'negative_space_field') return null;
    const measured = scalarWashProjection(payload);
    const figures = payload.figure_instance_ids
        .map((instanceId) => {
            for (const candidate of byId.values?.() || []) {
                const p = candidate.measurement.payload;
                if (p?.variant !== 'extent_set') continue;
                const inst = p.instances.find((i) => i.instance_id === instanceId);
                if (inst?.mask_rle) return decodeRle(inst.mask_rle);
            }
            return null;
        })
        .filter(Boolean);
    return {
        measured,
        derived: figures.length
            ? deriveNegativeSpaceField(figures, {
                max_distance: payload.max_distance_used,
                statistics: payload.statistics,
            })
            : { derived: true, available: false,
                why: 'the figures this field was computed over are not in this session\'s '
                    + 'ledger, so nothing here can be re-derived' },
        statistics: payload.statistics,
        field_ref: payload.field_ref,
    };
}
