// CIRCUIT-001 P2D-A — `visual_mark`: Semant's renderer-independent truth for instruments.
//
// Implements `CIRCUIT-001-P2D-interface-contract.md` §1–2. Lane B emits against these names.
//
// The rule this module exists to hold, from the P2C decision:
//
//     No renderer object is ever truth. A Konva Line or a Fabric Path is a VIEW of a
//     visual_mark. Serialising a library's scene graph would make its schema our ontology.
//
// Pure. No React, no fetch, no renderer, no clock it does not accept. Fails closed exactly as
// `perceptualActions.normalizeAction` does: an invalid mark comes back as `null`, never as a
// partial object, because a caller that receives an object will render it.

import {
    SOURCES as ACTION_SOURCES,
    FIELD_ROLES, TRACE_ROLES, RELATION_ROLES,
} from './perceptualActions';

// ── families ─────────────────────────────────────────────────────────────────

export const MARK_TYPES = [
    'brush_field', 'trace_mark', 'relation_mark', 'frame_mark', 'collection_mark',
];

/**
 * Mark sources are a SUPERSET of the action sources — reused, not forked (contract §2's
 * "do not invent a fourth dialect"). The two additions exist because a mark can be
 * something an action never is:
 *   `model_refined` — the human drew it and a model tightened it. Distinct from both `user`
 *                     (untouched by a model) and `user_confirmed` (the model drew it first).
 *   `imported`      — it came from outside this session's circuit.
 * A test asserts the superset relation so the two vocabularies cannot drift apart.
 */
export const MARK_SOURCES = [
    'user', 'system', 'model_suggested', 'model_refined', 'user_confirmed', 'imported', 'fixture',
];

/**
 * Mark statuses are their OWN vocabulary — a mark's life is not an action's life.
 *   draft      being made right now
 *   staged     made or armed, not committed
 *   suggested  a model proposed it; quarantined
 *   previewed  looked at, not accepted
 *   committed  real evidence
 *   dismissed  refused
 *   superseded replaced — and still recoverable, because silent replacement is how a
 *              citation re-points unnoticed (P1F/P1G)
 *   blocked    cannot proceed; the reason must be stated
 */
export const MARK_STATUSES = [
    'draft', 'staged', 'suggested', 'previewed', 'committed', 'dismissed', 'superseded', 'blocked',
];

export const GEOMETRY_KINDS = [
    'freehand_path', 'polygon', 'soft_mask', 'raster_mask', 'bounding_box',
    'vector', 'curve', 'polyline', 'derived', 'unresolved',
];

// ── role vocabularies ────────────────────────────────────────────────────────
// The first three are P2B's, imported rather than retyped. `trace_role` adds the two the
// contract names beyond P2B's eight; `frame_role` and `collection_role` are new families.

const keys = (list) => list.map((r) => r.key);

export const FIELD_ROLE_KEYS = keys(FIELD_ROLES);
export const TRACE_ROLE_KEYS = [...keys(TRACE_ROLES), 'rhythm', 'return_path'];
export const RELATION_ROLE_KEYS = keys(RELATION_ROLES);
export const FRAME_ROLE_KEYS = [
    'aperture', 'boundary', 'crop', 'threshold', 'field_boundary', 'external_limit',
];
export const COLLECTION_ROLE_KEYS = [
    'percept_constellation', 'evidence_set', 'comparison_set', 'motif_set',
    'contradiction_set', 'field_cluster', 'manuscript_citation_set',
];

/** type → the role vocabulary that type's `role` must belong to. */
export const ROLE_VOCABULARY = {
    brush_field: FIELD_ROLE_KEYS,
    trace_mark: TRACE_ROLE_KEYS,
    relation_mark: RELATION_ROLE_KEYS,
    frame_mark: FRAME_ROLE_KEYS,
    collection_mark: COLLECTION_ROLE_KEYS,
};

/** The payload key each action family carries its role under. */
export const ACTION_ROLE_KEY = {
    brush_field: 'field_role',
    trace_direction: 'trace_role',
    connect_marks: 'relation_role',
};

/** Which mark family an action family becomes. Absent → the action makes no mark. */
export const ACTION_TO_MARK_TYPE = {
    brush_field: 'brush_field',
    trace_direction: 'trace_mark',
    connect_marks: 'relation_mark',
};

const humanRole = (k) => String(k || '').replace(/_/g, ' ');
export const roleLabel = (type, key) => {
    const src = { brush_field: FIELD_ROLES, trace_mark: TRACE_ROLES, relation_mark: RELATION_ROLES }[type];
    return src?.find((r) => r.key === key)?.label || humanRole(key);
};

// ── ids ──────────────────────────────────────────────────────────────────────
// Minted like `groundId()`: a base36 timestamp plus a monotonic tail, so two marks made in
// the same millisecond cannot collide.

let _seq = 0;
export function markId() {
    return `vm_${Date.now().toString(36)}_${(_seq++).toString(36)}`;
}
export function _resetMarkIds() { _seq = 0; }   // test aid only

// ── construction ─────────────────────────────────────────────────────────────

const isStr = (v) => typeof v === 'string';
const nonEmpty = (v) => isStr(v) && v.trim().length > 0;
const arr = (v) => (Array.isArray(v) ? [...v] : []);

/**
 * Build a canonical mark. Does NOT validate — `normalizeMark` is the checked door.
 * Exported because Lane B needs a constructor it can call with known-good input.
 */
export function makeVisualMark(type, fields = {}, { now = null, idFn = markId } = {}) {
    const ts = now ?? new Date().toISOString();
    return {
        id: fields.id || idFn(),
        type,
        role: fields.role ?? null,
        label: isStr(fields.label) ? fields.label : '',
        source: fields.source || 'user',
        status: fields.status || 'draft',
        geometry: fields.geometry && typeof fields.geometry === 'object'
            ? { ...fields.geometry } : { kind: 'unresolved' },
        style: fields.style && typeof fields.style === 'object' ? { ...fields.style } : {},
        linked_ground_ids: arr(fields.linked_ground_ids),
        linked_percept_ids: arr(fields.linked_percept_ids),
        linked_action_ids: arr(fields.linked_action_ids),
        // Lineage points BACK. Acceptance and refinement mint a new mark; they never
        // overwrite the one they came from (contract §4.2).
        derived_from: fields.derived_from ?? null,
        provenance: {
            planner: null, prompt_excerpt: null, model: null, matched: [],
            // The slot exists and stays null: P1E left run identity under-specified and
            // P1G found the stored field is literally None. No causal claim is made.
            run_id: null,
            ...(fields.provenance || {}),
        },
        created_at: fields.created_at || ts,
        updated_at: fields.updated_at || ts,
        warnings: arr(fields.warnings),
    };
}

/**
 * The checked door. Returns a canonical mark or **null**.
 *
 * Null rather than a partial object, for the same reason `normalizeAction` does it: a caller
 * that gets an object back will render it, and a half-valid mark rendered as evidence is
 * exactly what this model exists to prevent.
 */
export function normalizeMark(raw, { now = null, idFn = markId } = {}) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    if (!MARK_TYPES.includes(raw.type)) return null;
    const mark = makeVisualMark(raw.type, raw, { now, idFn });
    const verdict = validateMark(mark);
    if (!verdict.valid) return null;
    mark.warnings = [...new Set([...mark.warnings, ...verdict.warnings])];
    return mark;
}

// ── validation ───────────────────────────────────────────────────────────────

/** @returns {{valid: boolean, errors: string[], warnings: string[]}} */
export function validateMark(mark) {
    const errors = [];
    const warnings = [];
    if (!mark || typeof mark !== 'object' || Array.isArray(mark)) {
        return { valid: false, errors: ['not an object'], warnings };
    }

    if (!MARK_TYPES.includes(mark.type)) errors.push(`unknown mark type: ${String(mark.type)}`);
    if (!nonEmpty(mark.id)) errors.push('missing id');
    if (!MARK_SOURCES.includes(mark.source)) errors.push(`unknown source: ${String(mark.source)}`);
    if (!MARK_STATUSES.includes(mark.status)) errors.push(`unknown status: ${String(mark.status)}`);
    if (!isStr(mark.label)) errors.push('label must be a string (may be empty)');

    // An unknown role is an ERROR, not a coercion. A vocabulary is only worth having if a
    // word outside it fails — otherwise a planner's mistake becomes invisible.
    const vocab = ROLE_VOCABULARY[mark.type];
    if (vocab) {
        if (mark.role == null) errors.push(`${mark.type}: role is required`);
        else if (!vocab.includes(mark.role)) {
            errors.push(`${mark.type}: role "${mark.role}" is not in the vocabulary`);
        }
    }

    const geom = mark.geometry;
    if (!geom || typeof geom !== 'object') errors.push('geometry must be an object');
    else if (!GEOMETRY_KINDS.includes(geom.kind)) {
        errors.push(`unknown geometry kind: ${String(geom.kind)}`);
    }

    for (const k of ['linked_ground_ids', 'linked_percept_ids', 'linked_action_ids', 'warnings']) {
        if (!Array.isArray(mark[k])) errors.push(`${k} must be an array`);
    }
    if (mark.derived_from != null && !nonEmpty(mark.derived_from)) {
        errors.push('derived_from must be a mark id or null');
    }

    // ── the discipline checks — product rules, not schema ──

    // Contract §6: no confidence on a mark. A confirmed mark must not inherit a number that
    // stopped meaning anything the moment a human took responsibility for it.
    if (mark.provenance && 'confidence' in mark.provenance) {
        errors.push('provenance.confidence is forbidden — no confidence scores on marks');
    }
    if (mark.provenance && mark.provenance.run_id != null) {
        errors.push('provenance.run_id must stay null — no causal run claims');
    }
    // Contract §4.1: a model suggestion may never arrive already committed.
    if (mark.source === 'model_suggested' && mark.status === 'committed') {
        errors.push('a model_suggested mark may not be committed — accept it to mint a new one');
    }
    // Contract §4.2: anything the model touched must say what it came from.
    if ((mark.source === 'user_confirmed' || mark.source === 'model_refined') && !mark.derived_from) {
        errors.push(`${mark.source} requires derived_from — lineage points back, never overwrites`);
    }

    if (geom && geom.kind === 'unresolved') warnings.push('No geometry yet — needs a mark from you.');
    if (mark.source === 'model_suggested') warnings.push('Suggested by a model — not evidence until you accept it.');

    return { valid: errors.length === 0, errors, warnings: [...new Set(warnings)] };
}

/** Validate a list; keep the good, report the bad by index. */
export function validateMarkList(list) {
    const marks = [];
    const rejected = [];
    (Array.isArray(list) ? list : []).forEach((m, index) => {
        const v = validateMark(m);
        if (v.valid) marks.push(m); else rejected.push({ index, errors: v.errors, raw: m });
    });
    return { marks, rejected };
}

// ── the action bridge ────────────────────────────────────────────────────────

/** The role an action carries, or null if its family makes no mark. */
export function markRoleFromAction(action) {
    if (!action || typeof action !== 'object') return null;
    const key = ACTION_ROLE_KEY[action.type];
    if (!key) return null;
    return action.payload?.[key] ?? null;
}

/**
 * A P2B action → a draft mark, or **null**.
 *
 * Null for every family that does not put a mark on the image, and — explicitly —
 * **`ask_model_reading` can never yield a mark at all**. An ask is not a mark: nothing has
 * been sent, nothing has come back, and a mark minted from one would be evidence for a
 * question nobody answered. Contract §4 and P2B's own `actionCanApplyNow` both refuse it;
 * this is the third refusal, at the bridge.
 *
 * The mark arrives with `geometry.kind: 'unresolved'` because the planner has no access to
 * the image. The curator's hand supplies geometry; `actionToDraftMark` supplies only role,
 * label, style and lineage.
 */
export function actionToDraftMark(action, { now = null, idFn = markId } = {}) {
    if (!action || typeof action !== 'object') return null;
    if (action.type === 'ask_model_reading') return null;

    const type = ACTION_TO_MARK_TYPE[action.type];
    if (!type) return null;

    const role = markRoleFromAction(action);
    const p = action.payload || {};

    return normalizeMark({
        type,
        role,
        label: isStr(p.label) ? p.label : '',
        source: MARK_SOURCES.includes(action.source) ? action.source : 'system',
        status: 'draft',
        geometry: { kind: 'unresolved' },
        style: {
            ...(p.color ? { color: p.color } : {}),
            ...(typeof p.softness === 'number' ? { softness: p.softness } : {}),
            ...(typeof p.opacity === 'number' ? { opacity: p.opacity } : {}),
        },
        // The originating act travels with the mark. P2B dropped everything but `label` at
        // commit; this is the field that closes that gap.
        linked_action_ids: action.id ? [action.id] : [],
        provenance: {
            planner: action.provenance?.planner ?? null,
            prompt_excerpt: action.provenance?.promptExcerpt ?? null,
            matched: arr(action.provenance?.matched),
        },
    }, { now, idFn });
}

// ── reading a mark ───────────────────────────────────────────────────────────

export const isMarkType = (m, type) => !!m && m.type === type;

/** The geometry-bearing families. A relation/collection derives its shape from its refs. */
export const markHasOwnGeometry = (m) =>
    !!m && !['derived', 'unresolved'].includes(m.geometry?.kind);

/** A short, honest description for a chip. Never a claim about the image. */
export function markSummary(mark) {
    if (!mark) return '';
    const bits = [roleLabel(mark.type, mark.role)];
    if (mark.label) bits.push(`“${mark.label}”`);
    if (mark.geometry?.kind === 'unresolved') bits.push('no geometry yet');
    return bits.filter(Boolean).join(' · ');
}

/** Immutable status transition. Returns a new list; never mutates the input. */
export function setMarkStatus(marks = [], id, status, { now = null } = {}) {
    if (!MARK_STATUSES.includes(status)) return marks;
    const ts = now ?? new Date().toISOString();
    return marks.map((m) => (m.id === id ? { ...m, status, updated_at: ts } : m));
}

// Re-exported so a consumer never reaches past this module for the action vocabulary.
export { ACTION_SOURCES };
