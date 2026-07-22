// CIRCUIT-001 P2B — the Perceptual Action Grammar.
//
// Semant's own vocabulary for "a thing a curator might do next in the image-writing
// circuit". It exists so that a suggestion — from a planner, a fixture, or later a model —
// arrives as a STRUCTURED, INSPECTABLE, EDITABLE, REFUSABLE object rather than as prose or
// as a mutation.
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
// This module is pure. No React, no fetch, no store, no clock it does not accept.

// ── the closed sets ──────────────────────────────────────────────────────────

export const ACTION_TYPES = [
    'find_parts',
    'brush_field',
    'trace_direction',
    'connect_marks',
    'compose_percept',
    'assign_ground_role',
    'start_manuscript',
    'challenge_percept',
    'ask_model_reading',
];

/** What the action would touch. Drives grouping in the UI, nothing else. */
export const TARGETS = ['image', 'ground', 'percept', 'manuscript', 'operation'];

/**
 * Where the action came from. `model_suggested` exists so a suggestion can never be
 * laundered into looking like the curator's own decision — and `user_confirmed` is a
 * distinct value from `user`, because "I typed this" and "I approved this" are different
 * provenances and Codex would later need to tell them apart.
 */
export const SOURCES = ['user', 'system', 'model_suggested', 'fixture', 'user_confirmed'];

export const STATUSES = ['proposed', 'previewed', 'applied', 'dismissed', 'blocked'];

// ── the role vocabularies ────────────────────────────────────────────────────
// Deliberately overlapping with the Ground Role vocabulary in the P1 addendum §2.2: a
// brushed light field IS an atmosphere ground once it exists. The overlap is the point —
// the action names what will be made, in the language the made thing will use.

export const FIELD_ROLES = [
    { key: 'light_field', label: 'Light field', hint: 'Where the light lives.' },
    { key: 'shadow_field', label: 'Shadow field', hint: 'Where it is withheld.' },
    { key: 'atmosphere_field', label: 'Atmosphere', hint: 'A condition, not an object.' },
    { key: 'material_field', label: 'Material', hint: 'What the surface is made of.' },
    { key: 'pressure_zone', label: 'Pressure', hint: 'Pushes on the reading without being its subject.' },
    { key: 'gaze_field', label: 'Gaze field', hint: 'The region a look inhabits.' },
    { key: 'negative_space', label: 'Negative space', hint: 'What is shaped by not being there.' },
    { key: 'threshold', label: 'Threshold', hint: 'Where something becomes something else.' },
    { key: 'fold', label: 'Fold', hint: 'Drapery, gathering, folded structure.' },
    { key: 'rhythm', label: 'Rhythm', hint: 'One of several repeating things; the repetition is the point.' },
    { key: 'background_recession', label: 'Recession', hint: 'What falls away behind.' },
    { key: 'external_limit', label: 'External limit', hint: 'Where the frame stops settling the question.' },
];

export const TRACE_ROLES = [
    { key: 'gaze_address', label: 'Gaze / address', hint: 'Where a look is directed.' },
    { key: 'gesture', label: 'Gesture', hint: 'A body\'s directed movement.' },
    { key: 'fall_of_light', label: 'Fall of light', hint: 'The direction light travels.' },
    { key: 'architectural_axis', label: 'Architectural axis', hint: 'A structural line through the image.' },
    { key: 'movement', label: 'Movement', hint: 'Implied motion.' },
    { key: 'implied_address', label: 'Implied address', hint: 'Directed at the viewer, without a gaze.' },
    { key: 'comparison_path', label: 'Comparison path', hint: 'Read this, then that.' },
    { key: 'force_direction', label: 'Force', hint: 'Pressure with a direction.' },
];

export const RELATION_ROLES = [
    { key: 'similarity', label: 'Similarity' },
    { key: 'contrast', label: 'Contrast' },
    { key: 'kinship', label: 'Kinship' },
    { key: 'motif_echo', label: 'Motif echo' },
    { key: 'support', label: 'Support' },
    { key: 'tension', label: 'Tension' },
    { key: 'contradiction', label: 'Contradiction' },
    { key: 'temporal_suggestion', label: 'Temporal suggestion' },
    { key: 'address_relation', label: 'Address relation' },
];

export const MANUSCRIPT_MODES = [
    { key: 'description', label: 'Description' },
    { key: 'art_critique', label: 'Critique' },
    { key: 'philosophical_note', label: 'Philosophical note' },
    { key: 'youtube_script', label: 'Script' },
    { key: 'research_note', label: 'Research note' },
    { key: 'caption', label: 'Caption' },
    { key: 'question_list', label: 'Questions' },
];

export const CHALLENGE_TYPES = [
    { key: 'contradiction', label: 'Contradiction' },
    { key: 'missing_ground', label: 'Missing evidence' },
    { key: 'external_claim', label: 'External claim' },
    { key: 'overreach', label: 'Overreach' },
    { key: 'alternative_reading', label: 'Alternative reading' },
];

export const GEOMETRY_MODES = ['soft_field', 'polygon', 'freehand', 'vector', 'curve', 'unresolved'];

const keysOf = (list) => list.map((x) => x.key);
export const FIELD_ROLE_KEYS = keysOf(FIELD_ROLES);
export const TRACE_ROLE_KEYS = keysOf(TRACE_ROLES);
export const RELATION_ROLE_KEYS = keysOf(RELATION_ROLES);
export const MANUSCRIPT_MODE_KEYS = keysOf(MANUSCRIPT_MODES);
export const CHALLENGE_TYPE_KEYS = keysOf(CHALLENGE_TYPES);

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
// One row per family. `required` fails the action; `enums` fails the action; `optional` is
// carried through untouched. `needsGeometry` means the action CANNOT complete without the
// curator putting a mark on the image — it is not a warning, it is a fact about the act.

const SPEC = {
    find_parts: {
        target: 'operation',
        required: [],
        optional: ['way_of_looking', 'vocabulary', 'grain', 'source_label', 'reason'],
        enums: {},
        needsGeometry: false,
        requiresConfirmation: false,   // deterministic, reversible by re-running
    },
    brush_field: {
        target: 'image',
        required: ['field_role', 'label'],
        optional: ['target_hint', 'geometry_mode', 'color', 'softness', 'opacity', 'requires_refinement', 'reason'],
        enums: { field_role: FIELD_ROLE_KEYS, geometry_mode: GEOMETRY_MODES },
        needsGeometry: true,
        requiresConfirmation: true,
    },
    trace_direction: {
        target: 'image',
        required: ['trace_role', 'label'],
        optional: ['from_hint', 'to_hint', 'geometry_mode', 'requires_user_anchor', 'reason'],
        enums: { trace_role: TRACE_ROLE_KEYS, geometry_mode: GEOMETRY_MODES },
        needsGeometry: true,
        requiresConfirmation: true,
    },
    connect_marks: {
        target: 'ground',
        required: ['relation_role'],
        optional: ['source_refs', 'target_refs', 'label', 'reason'],
        enums: { relation_role: RELATION_ROLE_KEYS },
        needsGeometry: true,           // the curator picks which marks are connected
        requiresConfirmation: true,
    },
    compose_percept: {
        target: 'percept',
        required: ['draft_text'],
        optional: [
            'intent', 'ground_refs', 'proposed_ground_refs', 'action_refs',
            'suggested_ground_roles', 'external_claim_warning', 'reason',
        ],
        enums: {},
        needsGeometry: false,
        requiresConfirmation: true,
    },
    assign_ground_role: {
        target: 'percept',
        required: ['ground_id', 'role'],
        optional: ['percept_id', 'draft_percept_ref', 'reason'],
        enums: {},                     // roles are validated against groundRoles at the seam
        needsGeometry: false,
        requiresConfirmation: true,
    },
    start_manuscript: {
        target: 'manuscript',
        required: ['mode'],
        optional: ['draft', 'cited_percept_refs', 'action_refs', 'insertion_mode', 'reason'],
        enums: { mode: MANUSCRIPT_MODE_KEYS, insertion_mode: ['staged', 'unsaved'] },
        needsGeometry: false,
        requiresConfirmation: true,
    },
    challenge_percept: {
        target: 'percept',
        required: ['percept_ref', 'challenge_type'],
        optional: ['prompt', 'reason'],
        enums: { challenge_type: CHALLENGE_TYPE_KEYS },
        needsGeometry: false,
        requiresConfirmation: true,
    },
    ask_model_reading: {
        target: 'operation',
        required: ['requested_reading_type'],
        optional: ['model_family_hint', 'packet_ref', 'reason'],
        enums: {},
        needsGeometry: false,
        requiresConfirmation: true,
    },
};

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

function defaultLabel(type, payload = {}) {
    // `lower` keeps this total: a payload missing its role still yields a string, so the
    // action can reach `validateAction` and be refused there rather than crashing here.
    const lower = (s) => String(s || '').toLowerCase();
    switch (type) {
        case 'find_parts': return 'Find parts';
        case 'brush_field': return `Brush ${lower(fieldRoleLabel(payload.field_role)) || 'a field'}`;
        case 'trace_direction': return `Trace ${lower(traceRoleLabel(payload.trace_role)) || 'a direction'}`;
        case 'connect_marks': return `Connect — ${lower(relationRoleLabel(payload.relation_role)) || 'a relation'}`;
        case 'compose_percept': return 'Compose a percept';
        case 'assign_ground_role': return 'Name what this ground does';
        case 'start_manuscript': return `Start a ${lower(manuscriptModeLabel(payload.mode)) || 'passage'}`;
        case 'challenge_percept': return 'Ask for a counter-reading';
        case 'ask_model_reading': return 'Ask the model to read this';
        default: return type;
    }
}

// ── validation ───────────────────────────────────────────────────────────────

const isNonEmptyString = (v) => typeof v === 'string' && v.trim().length > 0;

/**
 * @returns {{valid:boolean, errors:string[], warnings:string[]}}
 * Errors refuse the action. Warnings travel WITH it and are shown on the card — they are
 * how a proposal admits its own weakness rather than hiding it.
 */
export function validateAction(action) {
    const errors = [];
    const warnings = [];

    if (!action || typeof action !== 'object') return { valid: false, errors: ['not an object'], warnings };
    const spec = SPEC[action.type];
    if (!spec) return { valid: false, errors: [`unknown action type: ${String(action.type)}`], warnings };

    if (!isNonEmptyString(action.id)) errors.push('missing id');
    if (!isNonEmptyString(action.label)) errors.push('missing label');
    if (!SOURCES.includes(action.source)) errors.push(`unknown source: ${String(action.source)}`);
    if (!STATUSES.includes(action.status)) errors.push(`unknown status: ${String(action.status)}`);
    if (!TARGETS.includes(action.target)) errors.push(`unknown target: ${String(action.target)}`);
    if (action.target !== spec.target) errors.push(`target ${action.target} does not match ${action.type}`);
    if (typeof action.createdAt !== 'number') errors.push('createdAt must be a number');

    const payload = action.payload || {};
    for (const key of spec.required) {
        const v = payload[key];
        const present = Array.isArray(v) ? v.length > 0 : (typeof v === 'string' ? isNonEmptyString(v) : v != null);
        if (!present) errors.push(`${action.type}: payload.${key} is required`);
    }
    for (const [key, allowed] of Object.entries(spec.enums)) {
        if (payload[key] != null && !allowed.includes(payload[key])) {
            errors.push(`${action.type}: payload.${key} "${payload[key]}" is not in the vocabulary`);
        }
    }

    // ── the discipline checks. These are not schema; they are the product's rules. ──

    // A model may never author a challenge (P1 addendum §3.1, P0.5 §4.1). This is the
    // human's veto over the circuit, and it is the one rule here that is not about shape.
    if (action.type === 'challenge_percept' && action.source === 'model_suggested') {
        errors.push('challenge_percept may not be authored by a model');
    }

    // Nothing is sent in this gate, and an action that claims otherwise is refused rather
    // than quietly corrected — a silently-fixed dispatch flag is how a dispatch happens.
    if (action.type === 'ask_model_reading') {
        if (payload.dispatch && payload.dispatch.sent === true) {
            errors.push('ask_model_reading: dispatch.sent must be false — nothing is sent');
        }
        warnings.push('Proposed only — no model call is made.');
    }

    if (action.type === 'start_manuscript') {
        if (payload.insertion_mode && !['staged', 'unsaved'].includes(payload.insertion_mode)) {
            errors.push('start_manuscript: insertion_mode must be staged or unsaved');
        }
        warnings.push('Nothing is saved until you save it.');
    }

    if (action.type === 'compose_percept' && payload.external_claim_warning) {
        warnings.push('Rests on something the frame may not settle.');
    }

    if (spec.needsGeometry) {
        warnings.push('Needs a mark from you on the image.');
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
    if (action.type === 'ask_model_reading') return false;   // never, in this gate
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

export const TARGET_LABEL = {
    image: 'Image marks',
    ground: 'Evidence relations',
    percept: 'Percepts',
    manuscript: 'Manuscript',
    operation: 'Operations & model questions',
};

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
