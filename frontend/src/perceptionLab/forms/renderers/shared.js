// PERCEPTUAL-FORMS-001E — the constructors every renderer uses.
//
// Nineteen forms and forty-odd views, and if each one built its own layer object then "the
// declaration is mandatory" would be true forty times over and enforced once per author's memory.
// These are the constructors instead: each takes the payload's own facts and produces a layer that
// `assertLayer` will accept, with the evidence class DERIVED from the record rather than passed in
// by whoever was writing the view.
//
// That last point is the whole reason this file exists. `evidenceFor` reads the contract's
// partition, the form's own declaration of whether a projection is `direct` or `derived`, and the
// part a partition payload assigned — and returns one answer. A view cannot get the treatment
// wrong by writing the wrong string, because it does not write the string.

import {
    layer, absentLayer, EVIDENCE_FOR_PARTITION, EVIDENCE_FOR_PART,
} from '../layerModel';
import { form } from '../../contract/perceptionLabContract';
import { examinationOf } from '../formGeometry';

/**
 * The mode a form declares for one of its projections: `direct` or `derived`.
 *
 * Looked up rather than remembered. `mask_outline` is `derived` under `extent.hard_mask` — the
 * browser traces it, because the payload carries no ring — and `direct` under
 * `extent.boundary_rings`, whose entire purpose is that the ring is recorded. The same drawing,
 * two different kinds of claim, and the difference is in the registry.
 */
export function projectionMode(formKey, kind) {
    const declared = (form(formKey).renderer_projections || []).find((p) => p.kind === kind);
    return declared ? declared.mode : null;
}

export function projectionNote(formKey, kind) {
    const declared = (form(formKey).renderer_projections || []).find((p) => p.kind === kind);
    return declared?.note ?? null;
}

/** Throw when a view tries to draw a projection its form never declared. */
export function assertDeclared(formKey, kind) {
    if (!projectionMode(formKey, kind)) {
        throw new Error(
            `${formKey} does not declare the "${kind}" projection. The contract lists `
            + `${(form(formKey).renderer_projections || []).map((p) => p.kind).join(', ')}, and a `
            + 'drawing nobody declared is a drawing nobody can say is faithful');
    }
    return kind;
}

/**
 * The one place an evidence class is decided.
 *
 * PRECEDENCE, weakest wins, because every one of these is a cap and a cap cannot be outvoted:
 *
 *   1. an explicit partition PART        the record said this region is inferred
 *   2. the record's epistemic partition  the record said what kind of act made it
 *   3. the projection's declared mode    `derived` means this browser drew it
 *   4. measured                          nothing above applies: the producer reported it
 *
 * A `derived` projection of an `inferred_completion` is inferred, not derived: tracing a boundary
 * around an assertion does not turn the assertion into arithmetic.
 */
export function evidenceFor({ formKey, kind, partition = null, part = null, hypothesisId = null }) {
    if (part) return EVIDENCE_FOR_PART[part];
    if (hypothesisId) return 'hypothetical';
    if (partition && EVIDENCE_FOR_PARTITION[partition]) {
        const fromPartition = EVIDENCE_FOR_PARTITION[partition];
        if (fromPartition !== 'measured') return fromPartition;
    }
    if (kind && formKey && projectionMode(formKey, kind) === 'derived') return 'derived';
    return partition ? EVIDENCE_FOR_PARTITION[partition] : 'measured';
}

/** A ring layer on the image. The commonest thing this laboratory draws. */
export function ringLayer({
    id, label: text, formKey, kind, rings, raster = null, source = null, basis = null,
    status = null, partition = null, part = null, hypothesisId = null, note = null,
    measurements = null, filled = true, exact = true,
}) {
    assertDeclared(formKey, kind);
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind, partition, part, hypothesisId }),
        coordinate_system: 'image_normalized',
        basis,
        epistemic_status: status,
        hypothesis_id: hypothesisId,
        part,
        raster,
        projection_kind: kind,
        draw: { kind: 'rings', rings, filled, exact },
        note: note ?? projectionNote(formKey, kind),
        measurements,
    });
}

/** A scalar field, drawn as the cell grid it is. */
export function cellLayer({
    id, label: text, formKey, kind, cells, raster, source = null, basis = null, status = null,
    partition = null, part = null, hypothesisId = null, threshold = null, binarized = false,
    calibration = null, range = null, note = null, derivation = null,
}) {
    assertDeclared(formKey, kind);
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind, partition, part, hypothesisId }),
        coordinate_system: 'raster_cells',
        basis,
        epistemic_status: status,
        hypothesis_id: hypothesisId,
        part,
        raster,
        threshold,
        binarized,
        calibration,
        projection_kind: kind,
        draw: { kind: 'cells', cells, range, derivation },
        note: note ?? projectionNote(formKey, kind),
    });
}

/** Point markers on the image — refinement clicks, contact samples, path endpoints. */
export function pointLayer({
    id, label: text, formKey, kind, points, raster = null, source = null, basis = null,
    status = null, partition = null, note = null,
}) {
    assertDeclared(formKey, kind);
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind, partition }),
        coordinate_system: 'image_normalized',
        basis,
        epistemic_status: status,
        raster,
        projection_kind: kind,
        draw: { kind: 'points', points },
        note: note ?? projectionNote(formKey, kind),
    });
}

/** A polyline on the image — a clearance path, a proposed link between fragments. */
export function pathLayer({
    id, label: text, formKey, kind, points, arrow = false, source = null, basis = null,
    status = null, partition = null, hypothesisId = null, note = null, measurements = null,
}) {
    assertDeclared(formKey, kind);
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind, partition, hypothesisId }),
        coordinate_system: 'image_normalized',
        basis,
        epistemic_status: status,
        hypothesis_id: hypothesisId,
        projection_kind: kind,
        draw: { kind: 'path', points, arrow },
        note: note ?? projectionNote(formKey, kind),
        measurements,
    });
}

/**
 * A graph or a tree — in DIAGRAM space, which the stage refuses.
 *
 * The refusal is the safeguard. A node-link diagram letterboxed onto the image would put every
 * node at a pixel, and a person would read those positions as locations. They are not locations;
 * they are a circle this browser chose because a circle is reproducible.
 */
export function diagramLayer({
    id, label: text, formKey, kind, nodes, edges, source = null, basis = null, status = null,
    partition = null, hypothesisId = null, note = null, dangling = [], isolated = [],
    unreached = [], matrix = null,
}) {
    assertDeclared(formKey, kind);
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind, partition, hypothesisId }),
        coordinate_system: 'diagram',
        basis,
        epistemic_status: status,
        hypothesis_id: hypothesisId,
        projection_kind: kind,
        draw: { kind: 'diagram', nodes, edges, dangling, isolated, unreached, matrix },
        note: note ?? projectionNote(formKey, kind),
    });
}

/**
 * A layer that carries measurements and no geometry.
 *
 * Not a fallback. Several forms measure things that have no shape — `fraction_of_source`,
 * `occupancy_of_parent`, `counts_are_exact` — and a lab that only rendered what could be drawn
 * would drop them. `coordinate_system: 'none'` says so, and the stage leaves it to the panel.
 */
export function readingLayer({
    id, label: text, formKey, rows, source = null, basis = null, status = null, partition = null,
    hypothesisId = null, note = null,
}) {
    return layer({
        layer_id: id,
        label: text,
        form: formKey,
        source,
        evidence: evidenceFor({ formKey, kind: null, partition, hypothesisId }),
        coordinate_system: 'none',
        basis,
        epistemic_status: status,
        hypothesis_id: hypothesisId,
        draw: { kind: 'text', rows },
        note,
    });
}

/** The honest empty. Re-exported so a renderer imports one module, not two. */
export const absent = absentLayer;

/**
 * Layers, or — when there are none — the sentence the CONTRACT wrote for that exact case.
 *
 * `payload.instances.map(...)` over an empty list returns an empty list, and an empty list renders
 * as a blank stage. A blank stage reads as a bug: a person debugs their selection instead of
 * reading the finding, and the finding was "something looked for the named thing over this image
 * and found no instance of it", which is a measurement.
 *
 * So no renderer in this directory returns a bare `.map()`. `examinationOf` fetches the counter
 * the form declares and the `empty_means` sentence the form already wrote, and both go on screen
 * — along with `may_not_be_confused_with`, which names the states this one is not.
 */
export function orEmpty(layers, { formKey, payload, label = 'nothing to draw', id = 'empty' }) {
    if (layers.length) return layers;
    const looked = examinationOf(payload, formKey);
    const counter = looked
        ? `${looked.label}: ${Array.isArray(looked.members) ? looked.members.join(', ') : looked.value}. `
        : '';
    const notThese = looked?.may_not_be_confused_with?.length
        ? ` This is not ${looked.may_not_be_confused_with.join(', nor ')}.`
        : '';
    return [absentLayer({
        layer_id: `${id}:none`,
        label,
        form: formKey,
        why: `${counter}${looked?.empty_means ?? 'this record holds nothing of this kind'}.`
            + notThese,
    })];
}

/**
 * The sentence for an endpoint that did not resolve, phrased as a finding about the RECORD.
 *
 * "Could not render" describes the lab. "This relation names an instance no committed fixture
 * carries" describes the data, which is the thing a person opened this laboratory to inspect.
 */
export const unresolvedNote = (pair) => pair.why;
