// PERCEPTUAL-ORGANS-002 Lane A — the Perception Lab contract, enforced in JavaScript.
//
// The twin of `backend/schemas/perception_lab.py` and
// `backend/services/perception_lab/definitions.py`, reading the same JSON contract and applying
// the same laws by the same names. It is a SECOND ENFORCEMENT of one contract, not a second
// contract: every closed set, every organ, every operation declaration and every message template
// comes from `perception-lab.v1.json`, and the parity tests fail the moment the two runtimes
// disagree about what an operation, an outcome or a refusal is.
//
// WHY THE FRONTEND NEEDS THIS AT ALL. The laboratory's whole claim is that a person can see the
// difference between a measurement and a drawing of it, between empty and unavailable and
// refused, between what the machine claims and what they themselves judged. Every one of those
// distinctions is a rendering decision, and a rendering decision made against a locally retyped
// list of statuses is a distinction that survives exactly until someone adds a status.
//
// OWNERSHIP. Lane A owns `frontend/src/perceptionLab/contract/` and nothing else under
// `perceptionLab/`. Lane E owns the rest of that subtree and imports from here; it must not edit
// this directory, and it must not retype any list this module exports.
//
// THE RULES CARRIED OVER FROM THE PYTHON, because they are why the seam holds:
//
//   1. FAIL CLOSED. `operation()` on an unknown key throws. A caller that got a stub back might
//      render a control for it, and a control for an operation nobody declared is a button that
//      lies about what this laboratory can do.
//
//   2. UNDECLARED PARAMETERS ARE DROPPED AND RECORDED, not silently ignored and not fatal. That
//      record is how a model planner is caught trying to hand the runner geometry it invented.
//
//   3. A DECLARED PARAMETER OF THE WRONG TYPE REFUSES. Clamping a string into a numeric bound
//      would be this module inventing the value.
//
// PURE MODULE. No fetch, no DOM, no React. Data in, verdict out.

import CONTRACT from '../../contracts/perception-lab.v1.json';

export { CONTRACT };

export const SCHEMA_VERSION = CONTRACT.schema_version;

const set = (name) => {
    const values = CONTRACT.closed_sets[name];
    if (!values) throw new Error(`perception-lab.v1.json declares no closed set "${name}"`);
    return Object.freeze([...values]);
};

export const ORGAN_FAMILIES = set('organ_families');
export const ENABLED_ORGAN_FAMILIES = set('enabled_organ_families');
export const SESSION_MODES = set('session_modes');
export const PLANNER_IDENTITIES = set('planner_identities');
export const EXECUTION_IDENTITIES = set('execution_identities');
export const RUN_OUTCOMES = set('run_outcomes');
export const STAGE_STATES = set('stage_states');
export const LIFECYCLE_STATES = set('lifecycle_states');
export const REVIEW_VERDICTS = set('review_verdicts');
export const EPISTEMIC_STATUSES = set('epistemic_statuses');
export const EPISTEMIC_BASES = set('epistemic_bases');
export const ARTIFACT_KINDS = set('artifact_kinds');
export const PAYLOAD_VARIANTS = set('payload_variants');
export const IDENTITY_SCOPES = set('identity_scopes');
export const PRODUCER_KINDS = set('producer_kinds');
export const CAPABILITY_STATES = set('capability_states');
export const COORDINATE_SYSTEMS = set('coordinate_systems');
export const PARAMETER_TYPES = set('parameter_types');
export const INPUT_KINDS = set('input_kinds');
export const LABEL_SOURCES = set('label_sources');
export const REFUSAL_CODES = set('refusal_codes');
export const PROJECTION_KINDS = set('projection_kinds');
export const PROJECTION_HINT_KEYS = set('projection_hint_keys');
export const MANUAL_TOOL_KINDS = set('manual_tool_kinds');
export const RELATION_KINDS = set('relation_kinds');

export const BASIS_CEILINGS = Object.freeze({ ...CONTRACT.epistemics.basis_ceilings });
export const REFUSALS = Object.freeze({ ...CONTRACT.refusals });
export const ABSENCE_SEMANTICS = Object.freeze(CONTRACT.absence_semantics);
export const RECORD_BLOCKS = Object.freeze(CONTRACT.records);
export const MESSAGES = Object.freeze({ ...CONTRACT.messages });

// A measurement is obtained by looking at THIS image; `sourced` is walled out. A label is a
// reading and may abstain, but may never become a finding. Both mirror the Python constants.
export const MEASUREMENT_STATUSES = Object.freeze(
    ['measured', 'visible', 'interpretive', 'uncertain']);
export const INTERPRETATION_STATUSES = Object.freeze(['interpretive', 'uncertain']);

// The law ids in the contract that THIS runtime enforces. The parity test asserts it covers every
// declared law, so adding a law to the contract fails the JS suite until JavaScript claims it —
// and the Python suite until Python does.
export const ENFORCED_LAWS = Object.freeze([
    'organ_registry_is_closed',
    'only_two_organs_are_enabled',
    'isolation_organ_lock',
    'planner_proposes_resolver_authorizes',
    'topology_declares_extent_inputs',
    'occlusion_declares_depth',
    'depth_is_declared_not_produced',
    'no_default_fabricates_evidence',
    'identity_is_not_rendering',
    'interpretation_is_not_review',
    'three_axes_never_substitute',
    'measurement_is_never_sourced',
    'basis_ceiling_is_the_existing_ruling',
    'replay_cannot_recompute',
    'empty_is_not_refused_is_not_unavailable',
    'references_resolve_through_ids',
]);

// ── the registry ────────────────────────────────────────────────────────────

const ORGANS_BY_FAMILY = Object.freeze(Object.fromEntries(
    CONTRACT.organs.map((o) => [o.family, Object.freeze(o)])));

const OPERATIONS_BY_KEY = Object.freeze(Object.fromEntries(
    CONTRACT.organs.flatMap((o) => (o.operations || []).map(
        (op) => [op.key, Object.freeze({ ...op, organ: o.family })]))));

export const ORGANS = ORGANS_BY_FAMILY;
export const OPERATIONS = OPERATIONS_BY_KEY;

export function organ(family) {
    const found = ORGANS_BY_FAMILY[family];
    if (!found) {
        throw new Error(
            `"${family}" is not a registered organ family. The eight are `
            + `${ORGAN_FAMILIES.join(', ')}, and there is no fallback.`);
    }
    return found;
}

export function operation(key) {
    const found = OPERATIONS_BY_KEY[key];
    if (!found) {
        throw new Error(
            `"${key}" is not a declared operation. Unknown keys are unsupported_operation, `
            + 'never a best guess at what was meant.');
    }
    return found;
}

export const isOrganEnabled = (family) => organ(family).enabled === true;
export const enabledOrgans = () => CONTRACT.organs.filter((o) => o.enabled);
export const operationsFor = (family) => organ(family).operations || [];

/** What an ENABLED organ can mint. `depth_field` is deliberately not in here. */
export function producibleArtifactKinds() {
    return Object.freeze([...new Set(
        enabledOrgans().flatMap((o) => o.produces_artifact_kinds || []))]);
}

// ── messages ────────────────────────────────────────────────────────────────

export function message(code, fields = {}) {
    const template = MESSAGES[code];
    if (!template) throw new Error(`no message template for "${code}"`);
    return template.replace(/\{(\w+)\}/g, (whole, key) => (
        Object.prototype.hasOwnProperty.call(fields, key) ? String(fields[key]) : whole));
}

const refusal = (code, { organ: organFamily, operation: op, missing = [], remedy = null,
    detail = {}, message: text }) => ({
    code, organ: organFamily, operation: op ?? null, message: text, missing, remedy, detail,
});

// ── gate 1: the organ lock ──────────────────────────────────────────────────

/**
 * Refuse an operation belonging to another organ. Returns null when it is allowed.
 *
 * `unsupported_operation` and `organ_locked` are two refusals because they mean two things to a
 * person: "there is no such thing", and "there is, and this session is not the place to ask".
 */
export function checkOrganLock(opKey, { selectedOrgan, mode }) {
    const owner = OPERATIONS_BY_KEY[opKey];
    if (!owner) {
        return refusal('unsupported_operation', {
            organ: selectedOrgan,
            operation: opKey,
            message: message('unsupported_operation', { operation: opKey, organ: selectedOrgan }),
            remedy: 'choose a declared operation of this organ',
        });
    }
    if (owner.organ === selectedOrgan) return null;
    // Chain mode permits the crossing. It does NOT permit it silently — the plan carrying this
    // step must set `requires_confirmation`, which `validatePlan` enforces.
    if (mode === 'chain') return null;
    return refusal('organ_locked', {
        organ: selectedOrgan,
        operation: opKey,
        message: message('organ_locked', {
            operation: opKey, organ: selectedOrgan, operation_organ: owner.organ,
        }),
        remedy: `switch to chain mode and confirm, or select the ${owner.organ} organ`,
        detail: { operation_organ: owner.organ },
    });
}

// ── gate 2: parameters ──────────────────────────────────────────────────────

const TYPE_CHECKS = {
    string: (v) => typeof v === 'string',
    integer: (v) => Number.isInteger(v),
    number: (v) => typeof v === 'number' && Number.isFinite(v),
    boolean: (v) => typeof v === 'boolean',
    enum: (v) => typeof v === 'string',
    string_list: (v) => Array.isArray(v) && v.every((x) => typeof x === 'string'),
    point_list: (v) => Array.isArray(v) && v.every((x) => Array.isArray(x) && x.length === 2),
    box: (v) => !!v && typeof v === 'object'
        && ['x', 'y', 'w', 'h'].every((k) => k in v),
    mask_rle: (v) => !!v && typeof v === 'object' && 'size' in v && 'counts' in v,
};

const invalid = (op, detail) => refusal('invalid_parameters', {
    organ: op.organ,
    operation: op.key,
    message: message('invalid_parameters', { operation: op.key, detail }),
    remedy: "read the operation's parameter declarations",
    detail: { why: detail },
});

/**
 * Clamp a planner's parameters to the operation's declaration.
 *
 * Returns `{ clean, dropped, clamped, refusal }`. Three outputs rather than one because the three
 * tell a reader three different things: what will run, what a planner tried to smuggle in, and
 * where a person's number met a bound.
 */
export function resolveParameters(opKey, params = {}) {
    const op = operation(opKey);
    const declared = Object.fromEntries((op.parameters || []).map((p) => [p.name, p]));
    const clean = {};
    const dropped = [];
    const clamped = [];

    for (const [name, raw] of Object.entries(params)) {
        const spec = declared[name];
        if (!spec) {
            dropped.push({ name, reason: `${opKey} declares no parameter "${name}"` });
            continue;
        }
        if (raw === null || raw === undefined) {
            dropped.push({ name, reason: 'null is absence, and absence is not a value to record' });
            continue;
        }
        let value = raw;
        if (!TYPE_CHECKS[spec.type](value)) {
            return { clean: {}, dropped, clamped, refusal: invalid(op, `"${name}" is not a ${spec.type}`) };
        }
        if (spec.type === 'enum' && !(spec.enum || []).includes(value)) {
            return {
                clean: {}, dropped, clamped,
                refusal: invalid(op, `"${name}" must be one of ${JSON.stringify(spec.enum)}`),
            };
        }
        if (spec.type === 'string' && spec.max_length && value.length > spec.max_length) {
            return {
                clean: {}, dropped, clamped,
                refusal: invalid(op, `"${name}" exceeds ${spec.max_length} characters`),
            };
        }
        if ((spec.type === 'string_list' || spec.type === 'point_list')
            && spec.max_items && value.length > spec.max_items) {
            if (!spec.clamp) {
                return {
                    clean: {}, dropped, clamped,
                    refusal: invalid(op, `"${name}" exceeds ${spec.max_items} items`),
                };
            }
            clamped.push({
                name, requested: value.length, applied: spec.max_items,
                bound: `max_items=${spec.max_items}`,
            });
            value = value.slice(0, spec.max_items);
        }
        if (spec.type === 'integer' || spec.type === 'number') {
            let bound = null;
            let bounded = value;
            if (spec.minimum !== undefined && spec.minimum !== null && value < spec.minimum) {
                bounded = spec.minimum; bound = `minimum=${spec.minimum}`;
            } else if (spec.maximum !== undefined && spec.maximum !== null && value > spec.maximum) {
                bounded = spec.maximum; bound = `maximum=${spec.maximum}`;
            }
            if (bound) {
                if (!spec.clamp) {
                    return {
                        clean: {}, dropped, clamped,
                        refusal: invalid(op, `"${name}" is outside ${bound}`),
                    };
                }
                clamped.push({ name, requested: value, applied: bounded, bound });
                value = bounded;
            }
        }
        clean[name] = value;
    }

    for (const [name, spec] of Object.entries(declared)) {
        if (spec.required && !(name in clean)) {
            return { clean: {}, dropped, clamped, refusal: invalid(op, `"${name}" is required`) };
        }
    }
    return { clean, dropped, clamped, refusal: null };
}

// ── gate 3: inputs ──────────────────────────────────────────────────────────

/**
 * Refuse when a declared input did not resolve, with the code that input declares.
 *
 * `forExecution` is the occlusion case in one boolean. At plan time a missing depth field is
 * fine — the person is composing. At run time it is `missing_depth_artifact`.
 */
export function checkInputs(opKey, refs = [], { forExecution = false } = {}) {
    const op = operation(opKey);
    const counts = {};
    for (const ref of refs) counts[ref.role] = (counts[ref.role] || 0) + 1;

    for (const spec of op.inputs || []) {
        const count = counts[spec.role] || 0;
        const needed = spec.required || (forExecution && spec.required_for_execution === true);
        if (count === 0 && needed) {
            return refusal(spec.refusal_when_missing, {
                organ: op.organ,
                operation: op.key,
                message: message(spec.refusal_when_missing, { operation: op.key }),
                missing: [spec.role],
                remedy: spec.description,
                detail: {
                    role: spec.role, artifact_kinds: spec.artifact_kinds,
                    min: spec.min, max: spec.max,
                },
            });
        }
        if (count && count < spec.min) {
            return refusal(spec.refusal_when_missing, {
                organ: op.organ,
                operation: op.key,
                message: `${op.key} needs at least ${spec.min} ${spec.role} inputs; ${count} resolved`,
                missing: [spec.role],
                remedy: spec.description,
                detail: { role: spec.role, min: spec.min, resolved: count },
            });
        }
        if (count > spec.max) {
            return refusal('invalid_parameters', {
                organ: op.organ,
                operation: op.key,
                message: `${op.key} accepts at most ${spec.max} ${spec.role} inputs; ${count} given`,
                remedy: spec.description,
                detail: { role: spec.role, max: spec.max, given: count },
            });
        }
    }
    const roles = new Set((op.inputs || []).map((i) => i.role));
    const unknown = Object.keys(counts).filter((r) => !roles.has(r)).sort();
    if (unknown.length) {
        return invalid(op, `${op.key} declares no input role ${JSON.stringify(unknown)}`);
    }
    return null;
}

// ── gate 4: capability ──────────────────────────────────────────────────────

/**
 * Refuse when the adapter this operation would use is not running here. The table comes from the
 * CALLER — the frontend learns capability state from the backend, never from this file.
 */
export function checkCapability(opKey, { adapter = null, states = {} } = {}) {
    const op = operation(opKey);
    const candidates = adapter ? [adapter] : (op.adapters || []);
    if (!candidates.length) return null;
    const usable = candidates.filter((a) => (states[a] || 'unknown_until_runtime') !== 'unavailable');
    if (usable.length) return null;
    return refusal('capability_unavailable', {
        organ: op.organ,
        operation: op.key,
        message: message('capability_unavailable', { adapter: candidates.join(', ') }),
        missing: candidates,
        remedy: 'choose another adapter, or run where the model lives',
        detail: { adapters: candidates },
    });
}

// ── the fields the frontend reads, and reading them ─────────────────────────

export const FRONTEND_CONSUMED_FIELDS = Object.freeze(CONTRACT.frontend_consumed_fields);

/** The dotted paths this record type's UI depends on. A backend that drops one breaks a test. */
export function consumedFields(recordType) {
    const fields = FRONTEND_CONSUMED_FIELDS[recordType];
    if (!fields) throw new Error(`no frontend_consumed_fields declared for "${recordType}"`);
    return Object.freeze([...fields]);
}

/** Resolve `"provenance.adapter"` against a record. Returns `undefined` for an absent path. */
export function readPath(record, path) {
    return path.split('.').reduce(
        (node, key) => (node === null || node === undefined ? undefined : node[key]), record);
}

/** Which declared paths a record is missing. Empty means the backend still speaks this contract. */
export function missingConsumedFields(recordType, record) {
    return consumedFields(recordType).filter((p) => readPath(record, p) === undefined);
}

// ── validators: the same laws, said in JavaScript ───────────────────────────

const fail = (list, msg) => { list.push(msg); return list; };

/**
 * Validate a `PerceptualArtifact` against the separations. Returns an array of problems; empty
 * means it holds. Deliberately NOT a boolean: a UI that must render "why this is malformed" needs
 * the sentences, and a boolean would make it invent them.
 */
export function validateArtifact(artifact) {
    const out = [];
    if (!artifact || typeof artifact !== 'object') return fail(out, 'not an object');
    for (const block of ['identity', 'measurement', 'projection', 'interpretation', 'lifecycle',
        'provenance']) {
        if (!artifact[block] || typeof artifact[block] !== 'object') {
            fail(out, `missing the ${block} block`);
        }
    }
    if (out.length) return out;

    const { identity, measurement, projection, interpretation, lifecycle } = artifact;

    if (!ORGAN_FAMILIES.includes(identity.organ_family)) {
        fail(out, `unknown organ family "${identity.organ_family}"`);
    } else if (!isOrganEnabled(identity.organ_family)) {
        fail(out, `the ${identity.organ_family} organ is disabled; it cannot have produced this`);
    } else {
        const producible = organ(identity.organ_family).produces_artifact_kinds || [];
        if (!producible.includes(identity.artifact_kind)) {
            fail(out, `the ${identity.organ_family} organ produces `
                + `${producible.join(', ')}, not "${identity.artifact_kind}"`);
        }
    }
    if (!OPERATIONS_BY_KEY[identity.operation]) {
        fail(out, `"${identity.operation}" is not a declared operation`);
    } else if (OPERATIONS_BY_KEY[identity.operation].organ !== identity.organ_family) {
        fail(out, `"${identity.operation}" belongs to the `
            + `${OPERATIONS_BY_KEY[identity.operation].organ} organ`);
    }
    if (!IDENTITY_SCOPES.includes(identity.identity_scope)) {
        fail(out, `unknown identity scope "${identity.identity_scope}"`);
    }

    if (identity.artifact_kind !== measurement.payload_variant) {
        fail(out, `artifact_kind "${identity.artifact_kind}" and payload_variant `
            + `"${measurement.payload_variant}" are different things`);
    }
    const carriers = [measurement.payload, measurement.data_ref].filter(
        (c) => c !== null && c !== undefined);
    if (carriers.length !== 1) fail(out, 'a measurement carries exactly one of payload / data_ref');
    if (!MEASUREMENT_STATUSES.includes(measurement.epistemic_status)) {
        fail(out, `"${measurement.epistemic_status}" is not obtainable by looking at this image`);
    }
    if (!EPISTEMIC_BASES.includes(measurement.epistemic_basis)) {
        fail(out, `unknown epistemic basis "${measurement.epistemic_basis}"`);
    } else {
        const order = { uncertain: 0, interpretive: 1, visible: 2, measured: 3 };
        const ceiling = BASIS_CEILINGS[measurement.epistemic_basis];
        if (order[measurement.epistemic_status] > order[ceiling]) {
            fail(out, `a ${measurement.epistemic_basis}-basis measurement may claim at most `
                + `${ceiling}, not ${measurement.epistemic_status}`);
        }
    }

    if (!PROJECTION_KINDS.includes(projection.projection_kind)) {
        fail(out, `unknown projection kind "${projection.projection_kind}"`);
    }
    const strayHints = Object.keys(projection.hints || {})
        .filter((k) => !PROJECTION_HINT_KEYS.includes(k)).sort();
    if (strayHints.length) {
        fail(out, `projection hints may not carry ${JSON.stringify(strayHints)} — a projection `
            + 'is how a measurement is shown, never something that could stand in for it');
    }

    if (!INTERPRETATION_STATUSES.includes(interpretation.epistemic_status)) {
        fail(out, `an interpretation may be ${INTERPRETATION_STATUSES.join(', ')}; `
            + `"${interpretation.epistemic_status}" is a claim about the image signal`);
    }
    if (!LABEL_SOURCES.includes(interpretation.label_source)) {
        fail(out, `unknown label source "${interpretation.label_source}"`);
    }

    if (!LIFECYCLE_STATES.includes(lifecycle.status)) {
        fail(out, `unknown lifecycle state "${lifecycle.status}"`);
    }
    if ('review' in artifact || 'reviews' in artifact || 'verdict' in artifact) {
        fail(out, 'a verdict is a separate record — an artifact that carries one is an artifact '
            + 'whose measurement will be read as having been judged correct');
    }
    return out;
}

/** Validate a `LabRun`. Same shape of return as `validateArtifact`. */
export function validateRun(run) {
    const out = [];
    if (!run || typeof run !== 'object') return fail(out, 'not an object');
    if (!EXECUTION_IDENTITIES.includes(run.execution_identity)) {
        fail(out, `unknown execution identity "${run.execution_identity}"`);
    }
    if (!RUN_OUTCOMES.includes(run.outcome)) {
        fail(out, `unknown outcome "${run.outcome}"`);
    }
    const attempts = run.stage_attempts || [];
    for (const a of attempts) {
        if (!STAGE_STATES.includes(a.state)) fail(out, `unknown stage state "${a.state}"`);
        if (typeof a.invoked !== 'boolean') fail(out, `stage ${a.attempt_id} does not say whether it invoked`);
    }
    if (run.execution_identity !== 'LIVE') {
        const called = attempts.filter((a) => a.invoked).map((a) => a.attempt_id);
        if (called.length) {
            fail(out, `a ${run.execution_identity} run invoked ${JSON.stringify(called)}. Only `
                + 'LIVE may call an adapter; this run has nothing to call.');
        }
    }
    if (run.execution_identity === 'REPLAY') {
        if (!run.replay) fail(out, 'a REPLAY run names the run it replays, or it is not a replay');
        else if (run.replay.adapter_callable !== false) {
            fail(out, 'replay provenance must declare adapter_callable false');
        }
    } else if (run.replay) {
        fail(out, `a ${run.execution_identity} run carries no replay provenance`);
    }

    const refusals = run.refusals || [];
    for (const r of refusals) {
        if (!REFUSAL_CODES.includes(r.code)) fail(out, `unknown refusal code "${r.code}"`);
    }
    if (run.outcome === 'refused' && !refusals.length) {
        fail(out, "outcome 'refused' carries the typed refusal that caused it");
    }
    if (run.outcome === 'unavailable'
        && !refusals.some((r) => r.code === 'capability_unavailable')) {
        fail(out, "outcome 'unavailable' carries a capability_unavailable refusal naming what is "
            + 'not running — otherwise it is indistinguishable from having found nothing');
    }
    if ((run.outcome === 'ready' || run.outcome === 'empty') && refusals.length) {
        fail(out, `outcome "${run.outcome}" with a refusal attached is two answers`);
    }
    if (run.outcome === 'ready' && !(run.artifact_ids || []).length) {
        fail(out, "outcome 'ready' produced no artifact");
    }
    if (run.source_digest_after && run.source_digest_after !== run.source_digest_before
        && !refusals.some((r) => r.code === 'source_mutated')) {
        fail(out, 'the source digest changed during the run and nothing said so');
    }
    return out;
}

/** Validate a `LabSession` — including that its organ is one a person can actually use. */
export function validateSession(session) {
    const out = [];
    if (!session || typeof session !== 'object') return fail(out, 'not an object');
    if (!ORGAN_FAMILIES.includes(session.selected_organ)) {
        fail(out, `unknown organ family "${session.selected_organ}"`);
    } else if (!isOrganEnabled(session.selected_organ)) {
        fail(out, `the ${session.selected_organ} organ is registered and not enabled in this `
            + 'phase. Selecting it would give a person a laboratory with nothing behind the glass.');
    }
    if (!SESSION_MODES.includes(session.mode)) fail(out, `unknown mode "${session.mode}"`);
    return out;
}

/** Validate a `LabPlan` — the organ lock, and the confirmation a crossing owes a person. */
export function validatePlan(plan) {
    const out = [];
    if (!plan || typeof plan !== 'object') return fail(out, 'not an object');
    if (!PLANNER_IDENTITIES.includes(plan.planner)) fail(out, `unknown planner "${plan.planner}"`);
    if (plan.planner_fell_back_from && plan.planner_fell_back_from === plan.planner) {
        fail(out, 'a planner cannot have fallen back from itself');
    }
    if (!SESSION_MODES.includes(plan.mode)) fail(out, `unknown mode "${plan.mode}"`);

    const proposed = plan.proposed_steps || [];
    const resolved = plan.resolved_steps || [];
    for (const step of resolved) {
        if (step.authorized_by !== 'resolver') {
            fail(out, `resolved step ${step.step_id} claims authority from `
                + `"${step.authorized_by}". Only the resolver authorizes.`);
        }
        const op = OPERATIONS_BY_KEY[step.operation];
        if (!op) fail(out, `"${step.operation}" is not a declared operation`);
        else if (op.organ !== step.organ) {
            fail(out, `"${step.operation}" belongs to the ${op.organ} organ, not ${step.organ}`);
        }
    }
    for (const step of proposed) {
        if ('authorized_by' in step) {
            fail(out, `proposed step ${step.step_id} carries an authorization field. A proposal `
                + 'has no authority to claim.');
        }
    }
    if (plan.mode === 'isolation') {
        for (const step of resolved) {
            if (step.organ !== plan.selected_organ) {
                fail(out, `isolation mode is locked to ${plan.selected_organ}; resolved step `
                    + `${step.step_id} is ${step.organ}. A prompt may not change organs.`);
            }
        }
        const locked = (plan.refusals || []).some((r) => r.code === 'organ_locked');
        for (const step of proposed) {
            if (step.organ !== plan.selected_organ && !locked) {
                fail(out, `proposed step ${step.step_id} leaves the locked organ and the plan `
                    + 'carries no organ_locked refusal');
            }
        }
    }
    if (plan.mode === 'chain') {
        const organs = new Set(resolved.map((s) => s.organ));
        if (organs.size > 1 && plan.requires_confirmation !== true) {
            fail(out, 'a chain crossing the organ boundary requires confirmation');
        }
    }
    return out;
}

/** Validate a `LabReview` — and that it stayed one axis. */
export function validateReview(review) {
    const out = [];
    if (!review || typeof review !== 'object') return fail(out, 'not an object');
    if (!REVIEW_VERDICTS.includes(review.verdict)) {
        fail(out, `unknown verdict "${review.verdict}"`);
    }
    for (const forbidden of ['epistemic_status', 'lifecycle', 'status', 'basis']) {
        if (forbidden in review) {
            fail(out, `a review carries no ${forbidden}. Saying "correct" does not make a `
                + 'box-basis containment measured, and does not make the artifact kept.');
        }
    }
    return out;
}

export const VALIDATORS = Object.freeze({
    LabSession: validateSession,
    LabPlan: validatePlan,
    LabRun: validateRun,
    PerceptualArtifact: validateArtifact,
    LabReview: validateReview,
});
