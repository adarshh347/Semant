// CIRCUIT-001 P2B — the Perceptual Action Grammar.
//
// Semant's own vocabulary for "a thing a curator might do next in the image-writing circuit".
// It exists so that a suggestion — from a planner, a fixture, or later a model — arrives as a
// STRUCTURED, INSPECTABLE, EDITABLE, REFUSABLE object rather than as prose or as a mutation.
//
// The three rules that shape every line below:
//
//  1. **The model may suggest; Semant shapes; the user carries through.** Nothing in this
//     module executes anything. An action is a proposal with a provenance and a status. The
//     execution pathways live in the UI, are deterministic, and are user-confirmed.
//
//  2. **Fail closed.** An action that does not validate is not "mostly fine" — it is
//     refused. `normalizeAction` returns null; `validateActionList` drops it and says why.
//     This is the rehearsal runner's ordering (validate the manifest BEFORE spending
//     anything) moved into the product, and it is the whole reason the grammar is worth
//     having.
//
//  3. **A vocabulary, not a taxonomy.** The role lists here are candidates that must stay
//     usable before they are enumerable, and retirable (P1 addendum §6). They are not
//     stored on any record, they are not a classification of any image, and an unknown role
//     is a validation error rather than a silent coercion to a known one.
//
// ── HARNESS-001A: WHERE THE DATA NOW LIVES ───────────────────────────────────
//
// The closed sets, the per-action declarations and the laws moved OUT of this file and into
// `contracts/perceptual-action-grammar.v1.json`, because a second runtime now enforces them:
// the backend inquiry mind reads the same JSON. A vocabulary that lives in one language is a
// vocabulary the other language is free to paraphrase, and a paraphrased action name is a
// hallucination that merely looks like a typo.
//
// BEHAVIOUR DID NOT MOVE. Normalisation, label derivation, warnings, validation and the UI
// helpers are all still here, still exported under exactly the names they were, and every
// caller is untouched. The contract is data; this module is the frontend's enforcement of it.
//
// (The import path is `../contracts/…`, not `../../../contracts/…`: the Vercel project
// deploys by uploading `frontend/` as its source, so a bundle import from outside this tree
// builds green locally and fails in production. `frontend/src/contracts/` is a byte-identical
// mirror written by `scripts/contracts_sync.py`, and `contracts.parity.test.js` fails if it
// drifts from the canonical file at the repo root.)
//
// This module is pure. No React, no fetch, no store, no clock it does not accept.

import GRAMMAR from '../contracts/perceptual-action-grammar.v1.json';

export const GRAMMAR_SCHEMA_VERSION = GRAMMAR.schema_version;

// ── the closed sets ──────────────────────────────────────────────────────────

export const ACTION_TYPES = GRAMMAR.closed_sets.action_types;

/** What the action would touch. Drives grouping in the UI, nothing else. */
export const TARGETS = GRAMMAR.closed_sets.targets;

/**
 * Where the action came from. `model_suggested` exists so a suggestion can never be
 * laundered into looking like the curator's own decision — and `user_confirmed` is a
 * distinct value from `user`, because "I typed this" and "I approved this" are different
 * provenances and Codex would later need to tell them apart.
 */
export const SOURCES = GRAMMAR.closed_sets.sources;

export const STATUSES = GRAMMAR.closed_sets.statuses;

// ── the role vocabularies ────────────────────────────────────────────────────
// Deliberately overlapping with the Ground Role vocabulary in the P1 addendum §2.2: a
// brushed light field IS an atmosphere ground once it exists. The overlap is the point —
// the action names what will be made, in the language the made thing will use.

export const FIELD_ROLES = GRAMMAR.vocabularies.field_roles;
export const TRACE_ROLES = GRAMMAR.vocabularies.trace_roles;
export const RELATION_ROLES = GRAMMAR.vocabularies.relation_roles;
export const MANUSCRIPT_MODES = GRAMMAR.vocabularies.manuscript_modes;
export const CHALLENGE_TYPES = GRAMMAR.vocabularies.challenge_types;

export const GEOMETRY_MODES = GRAMMAR.closed_sets.geometry_modes;

const keysOf = (list) => list.map((x) => x.key);
export const FIELD_ROLE_KEYS = keysOf(FIELD_ROLES);
export const TRACE_ROLE_KEYS = keysOf(TRACE_ROLES);
export const RELATION_ROLE_KEYS = keysOf(RELATION_ROLES);
export const MANUSCRIPT_MODE_KEYS = keysOf(MANUSCRIPT_MODES);
export const CHALLENGE_TYPE_KEYS = keysOf(CHALLENGE_TYPES);

/**
 * A named closed set, resolved to plain keys. A vocabulary resolves to its keys; a bare
 * closed set resolves to itself. This is the one indirection the contract introduces: an
 * action's `enums` name a set rather than repeating its members, so the members cannot
 * disagree with the vocabulary they came from.
 */
function closedSet(name) {
    const vocab = GRAMMAR.vocabularies[name];
    if (vocab) return keysOf(vocab);
    return GRAMMAR.closed_sets[name] || [];
}

// Falls back to the key, and to '' when there is no key. An absent role reaches here on
// the way to being REFUSED by `validateAction`, and label derivation must not throw before
// the refusal happens — a crash is not failing closed.
const labelIn = (list, key) => list.find((x) => x.key === key)?.label || (key == null ? '' : String(key));
export const fieldRoleLabel = (k) => labelIn(FIELD_ROLES, k);
export const traceRoleLabel = (k) => labelIn(TRACE_ROLES, k);
export const relationRoleLabel = (k) => labelIn(RELATION_ROLES, k);
export const manuscriptModeLabel = (k) => labelIn(MANUSCRIPT_MODES, k);
export const challengeTypeLabel = (k) => labelIn(CHALLENGE_TYPES, k);

// ── the spec table ───────────────────────────────────────────────────────────
// One row per family, read from the contract. `required` fails the action; `enums` fails the
// action; `optional` is carried through untouched. `needsGeometry` means the action CANNOT
// complete without the curator putting a mark on the image — it is not a warning, it is a
// fact about the act.

const SPEC = Object.fromEntries(Object.entries(GRAMMAR.actions).map(([type, row]) => [type, {
    target: row.target,
    required: row.required,
    optional: row.optional,
    enums: Object.fromEntries(Object.entries(row.enums || {}).map(([k, set]) => [k, closedSet(set)])),
    needsGeometry: !!row.needs_geometry,
    requiresConfirmation: !!row.requires_confirmation,
}]));

export const specFor = (type) => SPEC[type] || null;

// ── construction ─────────────────────────────────────────────────────────────

let _seq = 0;
/** Injectable so tests are deterministic and nothing here reaches for a global clock. */
export function actionId(prefix = 'act') {
    _seq += 1;
    return `${prefix}_${_seq.toString(36)}`;
}
export function _resetActionIds() { _seq = 0; }   // test aid only

/**
 * Canonicalise a raw proposal into a full action, or return null.
 *
 * Returning null rather than a partially-filled object is deliberate: a caller that gets an
 * object back may render it, and a half-valid action rendered as a card is exactly the
 * failure this grammar exists to prevent.
 */
export function normalizeAction(raw, { now = 0, idFn = actionId } = {}) {
    if (!raw || typeof raw !== 'object') return null;
    const type = raw.type;
    const spec = SPEC[type];
    if (!spec) return null;

    const action = {
        id: raw.id || idFn(),
        type,
        label: typeof raw.label === 'string' && raw.label.trim() ? raw.label.trim() : defaultLabel(type, raw.payload),
        intent: typeof raw.intent === 'string' ? raw.intent : '',
        source: SOURCES.includes(raw.source) ? raw.source : 'system',
        status: STATUSES.includes(raw.status) ? raw.status : 'proposed',
        // The spec decides, not the caller: a proposal cannot declare itself
        // confirmation-free and thereby skip the user.
        requiresConfirmation: spec.requiresConfirmation,
        target: spec.target,
        createdAt: typeof raw.createdAt === 'number' ? raw.createdAt : now,
        payload: { ...(raw.payload || {}) },
        warnings: Array.isArray(raw.warnings) ? [...raw.warnings] : [],
        provenance: {
            planner: null, promptExcerpt: null, matched: [], ...(raw.provenance || {}),
        },
    };

    const verdict = validateAction(action);
    if (!verdict.valid) return null;
    // Validation-time warnings ride along, deduped, so a card can show them.
    action.warnings = [...new Set([...action.warnings, ...verdict.warnings])];
    return action;
}

const LABEL_RULES = GRAMMAR.default_labels;
const VOCAB_LABEL = {
    field_roles: fieldRoleLabel,
    trace_roles: traceRoleLabel,
    relation_roles: relationRoleLabel,
    manuscript_modes: manuscriptModeLabel,
    challenge_types: challengeTypeLabel,
};

function defaultLabel(type, payload = {}) {
    const rule = LABEL_RULES[type];
    if (!rule) return type;
    if (rule.literal) return rule.literal;
    // `lower` keeps this total: a payload missing its role still yields a string, so the
    // action can reach `validateAction` and be refused there rather than crashing here.
    const toLabel = VOCAB_LABEL[rule.vocabulary] || ((k) => String(k || ''));
    const role = String(toLabel((payload || {})[rule.role_key]) || '').toLowerCase();
    return `${rule.prefix || ''}${role || rule.fallback}${rule.suffix || ''}`;
}

// ── validation ───────────────────────────────────────────────────────────────

const isNonEmptyString = (v) => typeof v === 'string' && v.trim().length > 0;

const MSG = GRAMMAR.messages;
/** `{type}`/`{key}`/`{value}` filled from the contract's message templates. */
const fill = (template, vars) =>
    String(template).replace(/\{(\w+)\}/g, (_m, k) => (k in vars ? String(vars[k]) : `{${k}}`));

/** Read a dotted path out of a payload without throwing on a missing branch. */
function atPath(obj, path) {
    return String(path).split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

/** Does this law's `when` clause hold for this action? The whole interpreter, in one place. */
function lawApplies(law, action, spec) {
    const w = law.when || {};
    const payload = action.payload || {};
    if (w.action != null && action.type !== w.action) return false;
    if (w.needs_geometry != null && !!spec.needsGeometry !== w.needs_geometry) return false;
    if (Array.isArray(w.source_in) && !w.source_in.includes(action.source)) return false;
    if (w.payload_path_is_true != null && atPath(payload, w.payload_path_is_true) !== true) return false;
    if (w.payload_key_truthy != null && !payload[w.payload_key_truthy]) return false;
    if (w.payload_key_outside_set != null) {
        const { key, set } = w.payload_key_outside_set;
        const value = payload[key];
        if (value == null || closedSet(set).includes(value)) return false;
    }
    return true;
}

/**
 * @returns {{valid:boolean, errors:string[], warnings:string[]}}
 * Errors refuse the action. Warnings travel WITH it and are shown on the card — they are
 * how a proposal admits its own weakness rather than hiding it.
 */
export function validateAction(action) {
    const errors = [];
    const warnings = [];

    if (!action || typeof action !== 'object') return { valid: false, errors: [MSG.not_an_object], warnings };
    const spec = SPEC[action.type];
    if (!spec) {
        return { valid: false,
                 errors: [fill(MSG.unknown_action_type, { type: String(action.type) })], warnings };
    }

    if (!isNonEmptyString(action.id)) errors.push(MSG.missing_id);
    if (!isNonEmptyString(action.label)) errors.push(MSG.missing_label);
    if (!SOURCES.includes(action.source)) errors.push(fill(MSG.unknown_source, { value: String(action.source) }));
    if (!STATUSES.includes(action.status)) errors.push(fill(MSG.unknown_status, { value: String(action.status) }));
    if (!TARGETS.includes(action.target)) errors.push(fill(MSG.unknown_target, { value: String(action.target) }));
    if (action.target !== spec.target) {
        errors.push(fill(MSG.target_mismatch, { value: action.target, type: action.type }));
    }
    if (typeof action.createdAt !== 'number') errors.push(MSG.created_at_not_a_number);

    const payload = action.payload || {};
    for (const key of spec.required) {
        const v = payload[key];
        const present = Array.isArray(v) ? v.length > 0 : (typeof v === 'string' ? isNonEmptyString(v) : v != null);
        if (!present) errors.push(fill(MSG.payload_required, { type: action.type, key }));
    }
    for (const [key, allowed] of Object.entries(spec.enums)) {
        if (payload[key] != null && !allowed.includes(payload[key])) {
            errors.push(fill(MSG.payload_not_in_vocabulary,
                             { type: action.type, key, value: payload[key] }));
        }
    }

    // ── the discipline checks. These are not schema; they are the product's rules, and they
    // now live in the contract as data so the backend enforces the same ones by the same
    // names — including the one that matters most: a model may never author a challenge
    // (P1 addendum §3.1, P0.5 §4.1), the human's veto over the circuit.
    for (const law of GRAMMAR.laws) {
        if (!lawApplies(law, action, spec)) continue;
        (law.kind === 'error' ? errors : warnings).push(law.message);
    }

    return { valid: errors.length === 0, errors, warnings: [...new Set(warnings)] };
}

/**
 * Validate a list, keeping the good and reporting the bad.
 * @returns {{actions: object[], rejected: {index:number, errors:string[], raw:any}[]}}
 */
export function validateActionList(list) {
    const actions = [];
    const rejected = [];
    (Array.isArray(list) ? list : []).forEach((a, index) => {
        const verdict = validateAction(a);
        if (verdict.valid) actions.push(a);
        else rejected.push({ index, errors: verdict.errors, raw: a });
    });
    return { actions, rejected };
}

// ── reading an action ────────────────────────────────────────────────────────

export const actionNeedsGeometry = (action) => !!SPEC[action?.type]?.needsGeometry;

/**
 * Can this action be carried out right now, by this UI?
 *
 * `capabilities` is the set of action types the mounted surface has a real executor for.
 * Anything outside it is preview-only — and the UI must SAY so rather than render an Apply
 * button that quietly does nothing. A silent no-op is worse than an admitted gap: it
 * teaches the curator that the suggestions are theatre.
 */
export function actionCanApplyNow(action, capabilities = []) {
    if (!action || action.status === 'dismissed' || action.status === 'applied') return false;
    // Never, in this gate — declared in the contract so both runtimes read one list.
    if (GRAMMAR.never_applies.includes(action.type)) return false;
    return capabilities.includes(action.type);
}

export function actionToHumanLabel(action) {
    if (!action) return '';
    return action.label || defaultLabel(action.type, action.payload);
}

/** One short line: why this was suggested. Never a claim about the image. */
export function actionToShortReason(action) {
    if (!action) return '';
    const p = action.payload || {};
    if (isNonEmptyString(p.reason)) return p.reason;
    if (isNonEmptyString(action.intent)) return action.intent;
    const m = action.provenance?.matched;
    if (Array.isArray(m) && m.length) return `you said “${m.join('”, “')}”`;
    return '';
}

/** Group for display. Order is fixed so cards do not reshuffle between renders. */
export function groupActionsByTarget(actions = []) {
    const groups = TARGETS.map((t) => ({ target: t, actions: [] }));
    const byTarget = Object.fromEntries(groups.map((g) => [g.target, g]));
    for (const a of actions) if (byTarget[a.target]) byTarget[a.target].actions.push(a);
    return groups.filter((g) => g.actions.length > 0);
}

export const TARGET_LABEL = GRAMMAR.target_labels;

/**
 * A compact, honest sentence about a set of proposals.
 * Says "suggested", never "found" — these are acts to consider, not facts detected.
 */
export function summarizeActions(actions = []) {
    const live = actions.filter((a) => a.status !== 'dismissed');
    if (!live.length) return 'no suggested acts';
    const needsMark = live.filter(actionNeedsGeometry).length;
    const bits = [`${live.length} suggested act${live.length === 1 ? '' : 's'}`];
    if (needsMark) bits.push(`${needsMark} need${needsMark === 1 ? 's' : ''} a mark from you`);
    return bits.join(' · ');
}

/** Immutable status transition. Returns a new list; never mutates the input. */
export function setActionStatus(actions = [], id, status) {
    if (!STATUSES.includes(status)) return actions;
    return actions.map((a) => (a.id === id ? { ...a, status } : a));
}
