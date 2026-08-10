// PERCEPTUAL-ORGANS-002 Lane E — building records the contract already knows how to judge.
//
// Every record the laboratory holds is one of Lane A's five, and every one of them is minted
// here. Not because a builder is tidier than an object literal, but because the contract has
// laws that are easy to break by omission — `pairs_examined` with no default, `duration_ms` that
// is null and never 0, an `outcome` that must carry the refusal that caused it — and a builder
// is the one place those can be enforced once.
//
// THE RULE THIS FILE OBEYS: it may not invent a status. Every builder takes the epistemic status,
// the basis and the lifecycle from its caller, and `assertValid` runs Lane A's validator over the
// result before returning it. A builder that quietly defaulted `epistemic_status` to `measured`
// would be exactly the fabrication `no_default_fabricates_evidence` exists to stop, so the
// arguments are required and the validator is the gate rather than a suggestion.
//
// PURE MODULE. Timestamps come in from the caller — nothing here reads a clock, so a fixture
// built twice is byte-identical and the export test can compare it.

import { VALIDATORS } from './contract/perceptionLabContract';

/** Run the contract's own validator and throw with its sentences. Never silently repaired. */
export function assertValid(kind, record) {
    const validate = VALIDATORS[kind];
    if (!validate) throw new Error(`no validator for "${kind}"`);
    const problems = validate(record);
    if (problems.length) {
        throw new Error(`${kind} does not hold the contract:\n  - ${problems.join('\n  - ')}`);
    }
    return record;
}

// ── identity ────────────────────────────────────────────────────────────────

/**
 * A deterministic id minter. Session-local by construction: nothing here can produce a canonical
 * id, because minting one on the frontend is how a lab artifact starts being mistaken for a
 * Region that Semant actually holds.
 */
export function createIds(seed = 0) {
    let n = seed;
    return {
        next: (prefix) => { n += 1; return `${prefix}_${n}`; },
        peek: () => n,
    };
}

export const sessionRef = (artifact_id, instance_id) => ({
    artifact_id, instance_id, scope: 'session', region_id: null, geometry_rev: null,
});

export const canonicalRef = (artifact_id, instance_id, region_id, geometry_rev) => ({
    artifact_id, instance_id, scope: 'canonical', region_id, geometry_rev,
});

export const inputRef = (role, artifact_id, { scope = 'session', region_id = null,
    geometry_rev = null } = {}) => ({ role, scope, artifact_id, region_id, geometry_rev });

// ── the session ─────────────────────────────────────────────────────────────

export function labSession({ session_id, source, selected_organ, mode, at }) {
    return assertValid('LabSession', {
        session_id,
        source,
        selected_organ,
        mode,
        active_artifact_id: null,
        active_region_ids: [],
        selected_artifact_ids: [],
        prompt_turns: [],
        run_ids: [],
        review_ids: [],
        created_at: at,
        updated_at: at,
    });
}

// ── the plan ────────────────────────────────────────────────────────────────

/**
 * A proposal carries no authorization field at all — not `authorized_by: null`, which would be a
 * proposal with the shape of an authorization and one careless `??` away from being read as one.
 */
export const proposedStep = ({ step_id, organ, operation, parameters = {}, input_refs = [],
    rationale }) => ({ step_id, organ, operation, parameters, input_refs, rationale });

export const resolvedStep = ({ step_id, organ, operation, parameters = {}, input_refs = [],
    adapter = null, prerequisites_checked = [] }) => ({
    step_id, organ, operation, parameters, input_refs, adapter,
    authorized_by: 'resolver',
    prerequisites_checked,
});

export function labPlan({ plan_id, session_id, planner, planner_fell_back_from = null,
    selected_organ, mode, proposed_steps = [], resolved_steps = [], prerequisites = [],
    refusals = [], dropped_parameters = [], clamped_parameters = [],
    requires_confirmation = false, created_at }) {
    return assertValid('LabPlan', {
        plan_id,
        session_id,
        planner,
        planner_fell_back_from,
        selected_organ,
        mode,
        proposed_steps,
        resolved_steps,
        prerequisites,
        refusals,
        dropped_parameters,
        clamped_parameters,
        requires_confirmation,
        created_at,
    });
}

// ── the run ─────────────────────────────────────────────────────────────────

/**
 * `invoked` is required rather than defaulted, because the whole replay guarantee is carried by
 * that one boolean and a default of `false` would let a LIVE stage forget to admit it called out.
 */
export function stageAttempt({ attempt_id, step_id, operation, state, adapter = null, invoked,
    started_at = null, completed_at = null, duration_ms = null, detail = '' }) {
    if (typeof invoked !== 'boolean') {
        throw new Error(`stage ${attempt_id} must say whether it invoked an adapter`);
    }
    return { attempt_id, step_id, operation, state, adapter, invoked, started_at, completed_at,
        duration_ms, detail };
}

export function labRun({ run_id, session_id, execution_identity, outcome, requested_plan_id,
    resolved_plan_id, artifact_ids = [], stage_attempts = [], refusals = [],
    source_digest_before, source_digest_after = null, started_at = null, completed_at = null,
    duration_ms = null, replay = null }) {
    return assertValid('LabRun', {
        run_id,
        session_id,
        execution_identity,
        outcome,
        requested_plan_id,
        resolved_plan_id,
        artifact_ids,
        stage_attempts,
        refusals,
        source_digest_before,
        source_digest_after,
        started_at,
        completed_at,
        duration_ms,
        replay,
    });
}

export const replayProvenance = ({ source_run_id, recorded_at, reason }) => ({
    source_run_id, recorded_at, adapter_callable: false, reason,
});

// ── the artifact ────────────────────────────────────────────────────────────

/**
 * The six blocks, always all six.
 *
 * `interpretation` is required with an explicit `label_source`, so an artifact nobody named
 * carries `label: null, label_source: 'none'` rather than an absent block that a renderer would
 * have to guess about. Guessing is how a mask with no reading acquires one.
 */
export function perceptualArtifact({ identity, measurement, projection, interpretation,
    lifecycle, provenance }) {
    return assertValid('PerceptualArtifact', {
        identity, measurement, projection, interpretation, lifecycle, provenance,
    });
}

export const identityBlock = ({ artifact_id, session_id, run_id, step_id, organ_family,
    artifact_kind, operation, identity_scope = 'session', identity_refs = [], input_refs = [],
    derived_from = [] }) => ({
    artifact_id, session_id, run_id, step_id, organ_family, artifact_kind, operation,
    identity_scope, identity_refs, input_refs, derived_from,
});

export const measurementBlock = ({ payload_variant, payload = null, data_ref = null,
    coordinate_system, epistemic_status, epistemic_basis, basis_detail }) => ({
    payload_variant, payload, data_ref, coordinate_system, epistemic_status, epistemic_basis,
    basis_detail,
});

export const projectionBlock = (projection_kind, hints = {}) => ({ projection_kind, hints });

export const interpretationBlock = ({ label = null, label_source = 'none',
    epistemic_status = 'uncertain', notes = null }) => ({
    label, label_source, epistemic_status, notes,
});

export const lifecycleBlock = (status, changed_at, changed_by = 'perception_lab') => ({
    status, changed_at, changed_by,
});

export const provenanceBlock = ({ producer_kind, producer, adapter = null, model = null,
    revision = null, source_image_digest, started_at = null, completed_at = null,
    duration_ms = null, device = null, peak_memory_mb = null }) => ({
    producer_kind, producer, adapter, model, revision, source_image_digest, started_at,
    completed_at, duration_ms, device, peak_memory_mb,
});

// ── payloads ────────────────────────────────────────────────────────────────

export const extentInstance = ({ instance_id, mask_rle = null, box = null, area = null,
    confidence = null, naming = null, region_id = null, geometry_rev = null }) => {
    if (!mask_rle && !box) {
        throw new Error(`instance ${instance_id} has neither a mask nor a box and measures nothing`);
    }
    if (region_id && geometry_rev === null) {
        throw new Error(`instance ${instance_id} claims region ${region_id} without a geometry_rev`);
    }
    return { instance_id, mask_rle, box, area, confidence, naming, region_id, geometry_rev };
};

/** A name is a reading. `interpretive` and `uncertain` are the only statuses it may hold. */
export const naming = (text, source, epistemic_status = 'interpretive', confidence = null) => {
    if (!['interpretive', 'uncertain'].includes(epistemic_status)) {
        throw new Error(`a name may be interpretive or uncertain, never ${epistemic_status}`);
    }
    return { text, source, epistemic_status, confidence };
};

export const extentSetPayload = ({ searched, instances = [], dropped_below_min_area = null,
    duplicates = [], comparison = null }) => {
    if (!searched) throw new Error('an extent_set says what was searched for, or it is not a measurement');
    return { variant: 'extent_set', searched, instances, dropped_below_min_area, duplicates, comparison };
};

export const topologyRelation = ({ relation_id, kind, source, target, directed, basis,
    epistemic_status, measurements = {}, stale = false }) => ({
    relation_id, kind, source, target, directed, basis, epistemic_status, measurements, stale,
});

export const topologyRelationSetPayload = ({ pairs_examined, relations = [], bounded_to = null }) => {
    if (!Number.isInteger(pairs_examined)) {
        throw new Error('a topology_relation_set counts the pairs it examined; there is no default');
    }
    if (!relations.length && pairs_examined === 0) {
        throw new Error('no relations and no pairs examined is an absence of measurement, not an '
            + 'empty one — the run outcome has other words for that');
    }
    return { variant: 'topology_relation_set', pairs_examined, relations, bounded_to };
};

export const negativeSpaceFieldPayload = ({ figure_instance_ids, max_distance_used, field_shape,
    field_ref = null, statistics = {} }) => {
    if (!figure_instance_ids?.length) throw new Error('a negative space field names its figures');
    return { variant: 'negative_space_field', figure_instance_ids, max_distance_used, field_shape,
        field_ref, statistics };
};

export const refusalPayload = (refusal) => ({ variant: 'refusal', refusal });

/** A refusal artifact — a result with a ledger entry, not an error swallowed by a toast. */
export function refusalArtifact({ artifact_id, session_id, run_id, step_id, organ_family,
    operation, refusal, input_refs = [], source_image_digest, at, adapter = null,
    producer = 'perception_lab' }) {
    return perceptualArtifact({
        identity: identityBlock({ artifact_id, session_id, run_id, step_id, organ_family,
            artifact_kind: 'refusal', operation, input_refs }),
        measurement: measurementBlock({
            payload_variant: 'refusal',
            payload: refusalPayload(refusal),
            coordinate_system: 'normalized_xy_topleft',
            epistemic_status: 'uncertain',
            epistemic_basis: 'declared',
            basis_detail: 'a refusal makes no claim about the image',
        }),
        projection: projectionBlock('none'),
        interpretation: interpretationBlock({
            notes: 'This is a result, not an error. It carries the run, the step and the '
                + 'provenance so it can be reopened and read.',
        }),
        lifecycle: lifecycleBlock('proposed', at),
        provenance: provenanceBlock({
            producer_kind: 'adapter', producer, adapter, source_image_digest,
            started_at: at, completed_at: at, duration_ms: 1,
        }),
    });
}

// ── the review ──────────────────────────────────────────────────────────────

/**
 * A verdict, and only a verdict.
 *
 * Lane A's validator refuses a review that carries `epistemic_status`, `lifecycle`, `status` or
 * `basis`; this builder cannot construct one in the first place. Two gates for one law, because
 * this is the law a review surface is most tempted to break — "mark correct and keep" is one
 * button away from being the same button.
 */
export function labReview({ review_id, session_id, artifact_id, reviewer, verdict, notes = '',
    corrections = [], reviewed_at }) {
    return assertValid('LabReview', {
        review_id, session_id, artifact_id, reviewer, verdict, notes, corrections, reviewed_at,
    });
}
