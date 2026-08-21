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

// PERCEPTUAL-FORMS-001A — the perceptual-form grammar. A form is what was PERCEIVED; an operation
// is what was ASKED FOR, and the two registries have different arities in both directions. Nine of
// the nineteen forms are `deferred`: designed, validated, and unwritable.
export const PERCEPTUAL_FORMS = set('perceptual_forms');
export const FORM_STATES = set('form_states');
export const PRODUCER_CLASSES = set('producer_classes');
export const EPISTEMIC_PARTITIONS = set('epistemic_partitions');
export const RENDERER_MODES = set('renderer_modes');
export const COMPARISON_METHODS = set('comparison_methods');
export const FIELD_DERIVATIONS = set('field_derivations');
export const CALIBRATION_STATES = set('calibration_states');
export const GROUND_KINDS = set('ground_kinds');
export const RING_WINDINGS = set('ring_windings');
export const PARTITION_PARTS = set('partition_parts');
export const TRANSITION_CHANGES = set('transition_changes');

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
    'an_instance_is_named_with_its_artifact',
    // PERCEPTUAL-FORMS-001A — the form grammar
    'forms_and_operations_are_two_registries',
    'every_form_declares_what_it_needs',
    'form_state_gates_what_may_be_written',
    'partition_caps_the_status_independently_of_basis',
    'inference_is_never_visible',
    'a_form_is_never_its_renderer',
    'every_form_can_say_it_looked',
    'grouping_is_not_fusion',
    'a_hypothesis_is_not_curated_by_confidence',
    'a_transition_cites_both_revisions',
    'a_conditional_relation_keeps_its_condition',
    'a_pointed_at_raster_carries_its_digest',
    'old_records_remain_readable',
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

// ── PERCEPTUAL-FORMS-001A: the form registry ────────────────────────────────

const FORMS_BY_KEY = Object.freeze(Object.fromEntries(
    CONTRACT.perceptual_forms.map((f) => [f.key, Object.freeze(f)])));

/** `{artifact_kind: form}` for the three kinds that predate the grammar. */
const LEGACY_FORM_FOR_KIND = Object.freeze({
    ...CONTRACT.form_grammar.compatibility.legacy_form_for_kind,
});

export const FORMS = FORMS_BY_KEY;
export const PARTITION_CEILINGS = Object.freeze({
    ...CONTRACT.form_grammar.epistemic_partitions.ceilings,
});
export const FORM_GRAMMAR = Object.freeze(CONTRACT.form_grammar);

/** FAIL CLOSED, exactly as `operation()` does. A caller handed a stub might render a control. */
export function form(key) {
    const found = FORMS_BY_KEY[key];
    if (!found) {
        throw new Error(
            `"${key}" is not a registered perceptual form. The nineteen are `
            + `${PERCEPTUAL_FORMS.join(', ')}, and there is no fallback.`);
    }
    return found;
}

export const formsFor = (family) => CONTRACT.perceptual_forms.filter((f) => f.organ === family);
export const producibleForms = () => CONTRACT.perceptual_forms.filter(
    (f) => f.state !== 'deferred');
export const isFormProducible = (key) => form(key).state !== 'deferred';
export const isFormPromotable = (key) => form(key).state === 'enabled';
export const formForArtifactKind = (kind) => CONTRACT.perceptual_forms.find(
    (f) => f.artifact_kind === kind) || null;

/**
 * The form an artifact is in, whether or not it says so.
 *
 * A record written before this grammar existed carries no `identity.form`, and it still means
 * exactly what it meant — `legacy_form_for_kind` is the table that says which form that is. This
 * is the ONE place that lookup happens in this runtime, so "old records remain readable" is a
 * line rather than a convention repeated in six components. Returns null for a `refusal`, which
 * is the record of a question NOT answered and is therefore in no perceptual form at all.
 */
export function effectiveForm(artifact) {
    const declared = artifact?.identity?.form;
    if (declared) return declared;
    return LEGACY_FORM_FOR_KIND[artifact?.identity?.artifact_kind] ?? null;
}

const STATUS_ORDER = Object.freeze({ uncertain: 0, interpretive: 1, visible: 2, measured: 3 });

/**
 * The strongest status a claim in this form may carry, given everything that caps it.
 *
 * THREE CAPS, AND THE THIRD IS WHY THIS EXISTS. The basis ceiling and the partition ceiling are
 * properties of one record and are checked by `validateArtifact`. The third — that a derivation is
 * never stronger than the weakest artifact it derived FROM — needs the inputs in hand, which a
 * validator looking at one record does not have. Passing no input statuses is not the same as
 * passing strong ones: it means the caller is not composing.
 */
export function derivedCeiling(formKey, { basis, partition, inputStatuses = [] }) {
    const declaration = form(formKey);
    const caps = [BASIS_CEILINGS[basis], PARTITION_CEILINGS[partition],
        declaration.epistemic_ceiling];
    if (partition === 'exact_derivation' || partition === 'interpretive_grouping') {
        caps.push(...inputStatuses);
    }
    return caps.reduce((weakest, c) => (STATUS_ORDER[c] < STATUS_ORDER[weakest] ? c : weakest));
}

// ── gate 5: the input form ──────────────────────────────────────────────────

/**
 * Refuse a supplied artifact whose FORM the consuming form does not read.
 *
 * This is NOT `unknown_reference`. The artifact resolved perfectly well; it is the wrong kind of
 * answer. Telling a person "no such artifact" when they supplied a soft field where a hard mask
 * was wanted sends them looking for a selection bug that is not there.
 */
export function checkInputForms(formKey, supplied = [], { operation: opKey = null } = {}) {
    const declaration = form(formKey);
    const accepted = declaration.accepted_input_forms || [];
    const wrong = supplied.filter((s) => !accepted.includes(s));
    if (!wrong.length) return null;
    return refusal('unsupported_form', {
        organ: declaration.organ,
        operation: opKey,
        message: message('unsupported_form', {
            operation: opKey || declaration.key,
            form: wrong.join(', '),
            accepted: accepted.join(', ') || 'no artifact',
        }),
        missing: [...accepted],
        remedy: 'supply one of the declared input forms, or ask the question the supplied form '
            + 'can answer',
        detail: { form: declaration.key, supplied: wrong, accepted: [...accepted] },
    });
}

// ── gate 6: may this form be written at all ─────────────────────────────────

/** Refuse an attempt to WRITE a form that is registered and deferred. */
export function checkFormProducible(formKey, { operation: opKey = null } = {}) {
    const declaration = form(formKey);
    if (declaration.state !== 'deferred') return null;
    return refusal('form_not_producible', {
        organ: declaration.organ,
        operation: opKey,
        message: message('form_not_producible', { form: declaration.key }),
        missing: [declaration.key],
        remedy: 'wait for the phase that enables it, or produce a form that exists',
        detail: { form: declaration.key, state: declaration.state },
    });
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
            dropped.push({ name, reason: `${opKey} declares no parameter '${name}'` });
            continue;
        }
        if (raw === null || raw === undefined) {
            dropped.push({ name, reason: 'null is absence, and absence is not a value to record' });
            continue;
        }
        let value = raw;
        if (!TYPE_CHECKS[spec.type](value)) {
            return { clean: {}, dropped, clamped, refusal: invalid(op, `'${name}' is not a ${spec.type}`) };
        }
        if (spec.type === 'enum' && !(spec.enum || []).includes(value)) {
            return {
                clean: {}, dropped, clamped,
                refusal: invalid(op, `'${name}' must be one of [${(spec.enum || []).map((e) => `'${e}'`).join(', ')}]`),
            };
        }
        if (spec.type === 'string' && spec.max_length && value.length > spec.max_length) {
            return {
                clean: {}, dropped, clamped,
                refusal: invalid(op, `'${name}' exceeds ${spec.max_length} characters`),
            };
        }
        if ((spec.type === 'string_list' || spec.type === 'point_list')
            && spec.max_items && value.length > spec.max_items) {
            if (!spec.clamp) {
                return {
                    clean: {}, dropped, clamped,
                    refusal: invalid(op, `'${name}' exceeds ${spec.max_items} items`),
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
                        refusal: invalid(op, `'${name}' is outside ${bound}`),
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
            return { clean: {}, dropped, clamped, refusal: invalid(op, `'${name}' is required`) };
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
        return invalid(op, `${op.key} declares no input role [${unknown.map((r) => `'${r}'`).join(', ')}]`);
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
/**
 * The paths this record type's UI reads and must be able to find ABSENT.
 *
 * PERCEPTUAL-FORMS-001A. `identity.form` and `measurement.partition` are read by the Lab and are
 * optional on the wire: a record written before the form grammar existed carries neither key, and
 * it is still a record that has to render. Declaring the two facts separately is what lets every
 * fixture committed before this phase stay byte-identical instead of being back-filled with nulls
 * to satisfy a test — and deleting either field still breaks parity, because they remain consumed.
 */
export function optionalConsumedFields(recordType) {
    const declared = CONTRACT.form_grammar.compatibility.frontend_optional_fields || {};
    return Object.freeze([...(declared[recordType] || [])]);
}

export function missingConsumedFields(recordType, record) {
    const optional = new Set(optionalConsumedFields(recordType));
    return consumedFields(recordType).filter(
        (p) => !optional.has(p) && readPath(record, p) === undefined);
}

// ── validators: the same laws, said in JavaScript ───────────────────────────

const fail = (list, msg) => { list.push(msg); return list; };

// ── references: one type, two depths ────────────────────────────────────────

/**
 * The rules of `contract.references.InputRef`, in the language that emits them.
 *
 * THIS IS THE FUNCTION A2 EXISTS FOR. The laboratory shipped for a while with an `instance_id`
 * that the frontend wrote and the backend schema rejected, and nothing said so until a request
 * reached a Python validator — a whole class of "the panel is blank in production" that a shared
 * rule stated in both runtimes cannot produce.
 *
 * `artifact_id` alone still means the whole artifact. That is not a leniency for old records: it
 * is a different question with a different answer, and `pairs_examined` on a topology run is the
 * field that would lie if the two collapsed.
 */
export function validateInputRef(ref, where = 'an input ref') {
    const out = [];
    if (!ref || typeof ref !== 'object') return fail(out, `${where} is not an object`);
    const named = [ref.artifact_id, ref.region_id].filter(Boolean).length;
    if (named !== 1) {
        fail(out, `${where} names exactly one of artifact_id / region_id`);
    }
    // Exactly one problem per defect, in the order Python raises them: an instance beside a
    // region is a DIFFERENT mistake from an instance beside nothing, and reporting both for one
    // ref would make the two runtimes' answers impossible to compare line for line.
    if (ref.instance_id && !ref.artifact_id && !ref.region_id) {
        fail(out, `${where} names an instance with no artifact. An instance id is unique inside `
            + 'one artifact and nowhere else, so one recorded alone names nothing');
    }
    if (ref.instance_id && ref.region_id) {
        fail(out, `${where} names an instance inside a canonical region. A Region is already `
            + 'exactly one shape; an instance within it would be a second geometry wearing one id');
    }
    if (ref.region_id && (ref.geometry_rev === null || ref.geometry_rev === undefined)) {
        fail(out, `${where} cites a region without a geometry_rev, which is not a reference`);
    }
    return out;
}

/** What a refusal calls this reference. `art_3#inst_2` and `art_3` are different references. */
export function referenceOf(ref) {
    if (!ref?.artifact_id) return String(ref?.region_id ?? '');
    return ref.instance_id ? `${ref.artifact_id}#${ref.instance_id}` : ref.artifact_id;
}

/**
 * Whether a session declared what a ref names — the reference law, at instance depth.
 *
 * `declared` is `{ artifacts, instances, regions }` of Sets, where `instances` holds composite
 * `"artifact#instance"` keys rather than bare ids: every extent set numbers its own instances
 * from 1, so two selected sets both holding `inst_1` is the normal case, not the exotic one.
 *
 * A REGION REF IS CHECKED TOO, against `active_region_ids`. The first draft of this function
 * returned `true` for regions on the grounds that they were declared elsewhere, and the
 * cross-language parity loop caught it on its first run: Python's `SessionView.knows` was
 * refusing exactly the ref this admitted. One law, both runtimes — including the branch nobody
 * was thinking about when they wrote it.
 */
export function sessionKnows(ref, declared) {
    if (!ref?.artifact_id) return Boolean(declared?.regions?.has(String(ref?.region_id)));
    if (!declared?.artifacts?.has(ref.artifact_id)) return false;
    if (!ref.instance_id) return true;
    return Boolean(declared.instances?.has(referenceOf(ref)));
}

/** The three id sets a session declares, in the shape `sessionKnows` reads. */
export function declaredReferences(session) {
    const artifacts = new Set(session?.selected_artifact_ids || []);
    if (session?.active_artifact_id) artifacts.add(session.active_artifact_id);
    const instances = new Set((session?.selected_instance_refs || [])
        .filter((r) => r?.artifact_id && r?.instance_id)
        .map((r) => `${r.artifact_id}#${r.instance_id}`));
    return { artifacts, instances, regions: new Set(session?.active_region_ids || []) };
}

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
    for (const ref of identity.input_refs || []) {
        for (const problem of validateInputRef(ref, `input ref "${referenceOf(ref)}"`)) {
            fail(out, problem);
        }
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

    // ── PERCEPTUAL-FORMS-001A ──────────────────────────────────────────────
    //
    // Everything below runs only once a form is in play. A `refusal` has none — it is the record
    // of a question NOT answered — so `effectiveForm` returns null for it and these are skipped.
    if (identity.form && !PERCEPTUAL_FORMS.includes(identity.form)) {
        fail(out, `unknown perceptual form "${identity.form}"`);
    } else {
        const formKey = effectiveForm(artifact);
        if (!identity.form && identity.artifact_kind !== 'refusal' && !formKey) {
            fail(out, `an artifact of kind "${identity.artifact_kind}" must declare its `
                + 'identity.form; only the three kinds that predate the form grammar may omit it');
        }
        const declaration = formKey ? FORMS_BY_KEY[formKey] : null;
        if (declaration) {
            if (identity.form && declaration.artifact_kind !== identity.artifact_kind) {
                fail(out, `form "${formKey}" is carried by artifact kind `
                    + `"${declaration.artifact_kind}", not "${identity.artifact_kind}"`);
            }
            if (identity.form && declaration.organ !== identity.organ_family) {
                fail(out, `form "${formKey}" belongs to the ${declaration.organ} organ`);
            }
            if (declaration.state === 'deferred') {
                fail(out, `${formKey} is registered and deferred; nothing in this phase writes one`);
            }
            if (declaration.state === 'experimental' && lifecycle.status === 'promoted') {
                fail(out, `${formKey} is experimental and may be kept inside the laboratory, `
                    + 'never promoted into Semant');
            }
            if (declaration.carries_hypothesis
                && (lifecycle.status === 'kept' || lifecycle.status === 'promoted')) {
                fail(out, `${formKey} carries a hypothesis and may not be ${lifecycle.status}; `
                    + 'resolving it produces a new artifact of a resolved form');
            }
            if (!(declaration.admissible_bases || []).includes(measurement.epistemic_basis)) {
                fail(out, `${formKey} is measured from `
                    + `${(declaration.admissible_bases || []).join(', ')}, not from `
                    + `"${measurement.epistemic_basis}"`);
            }
            if (STATUS_ORDER[measurement.epistemic_status]
                > STATUS_ORDER[declaration.epistemic_ceiling]) {
                fail(out, `the ${formKey} form reaches ${declaration.epistemic_ceiling}, not `
                    + `${measurement.epistemic_status}`);
            }
            const drawable = (declaration.renderer_projections || []).map((p) => p.kind);
            if (projection.projection_kind !== 'none'
                && !drawable.includes(projection.projection_kind)) {
                fail(out, `${formKey} declares the projections ${drawable.join(', ')}; `
                    + `"${projection.projection_kind}" is not one of them, and a drawing nobody `
                    + 'declared is a drawing nobody can say is faithful');
            }
        }
    }
    if (measurement.partition !== null && measurement.partition !== undefined) {
        if (!EPISTEMIC_PARTITIONS.includes(measurement.partition)) {
            fail(out, `unknown epistemic partition "${measurement.partition}"`);
        } else {
            const ceiling = PARTITION_CEILINGS[measurement.partition];
            if (STATUS_ORDER[measurement.epistemic_status] > STATUS_ORDER[ceiling]) {
                fail(out, `a ${measurement.partition} measurement may claim at most ${ceiling}, `
                    + `not ${measurement.epistemic_status} — citing measured inputs does not `
                    + 'raise it');
            }
            const derives = measurement.partition === 'exact_derivation'
                || measurement.partition === 'interpretive_grouping';
            if (derives && !(identity.input_refs || []).length) {
                fail(out, `a ${measurement.partition} cites no input. It rests on records already `
                    + 'made, and a record it cannot name is a record nobody can check it against');
            }
        }
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

    // The pair law. A selected instance whose artifact is not also declared is a reference
    // reachable from one field and invisible in the other, which is how a deselection gets
    // recorded and then disobeyed.
    const declared = declaredReferences(session);
    for (const ref of session.selected_instance_refs || []) {
        if (!ref?.artifact_id || !ref?.instance_id) {
            fail(out, 'a selected instance is an artifact/instance PAIR. A bare instance id names '
                + "every extent set's first mask at once");
        } else if (!declared.artifacts.has(ref.artifact_id)) {
            fail(out, `selected instance ${referenceOf(ref)} names an artifact this session has `
                + 'neither selected nor made active. Selecting an instance selects its artifact');
        }
    }
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
    // RESOLVED steps only. A PROPOSAL is allowed to be wrong — that is what the resolver is for,
    // and it records the refusal beside the proposal so the attempt stays visible. Failing the
    // whole plan record here would throw away both the refusal and the evidence, which is the
    // same argument this contract already makes about a planner's stray parameters.
    for (const step of resolved) {
        for (const ref of step.input_refs || []) {
            for (const problem of validateInputRef(
                ref, `${step.step_id}'s input ref "${referenceOf(ref)}"`)) fail(out, problem);
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
