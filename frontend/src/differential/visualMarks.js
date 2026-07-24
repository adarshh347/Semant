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
    // P2E contract v2 §7.2-C: a segmented extent is not a perceptual field. `region_mask`
    // names what was segmented; the perceptual reading is a later, explicit act.
    'region_mask',
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
    // P4 contract v3: a label suggestion references a region WITHOUT authoring pixels — the
    // VLM's law (it never draws). `region_ref` points at an existing region's mask by id.
    'region_ref',
];

// ── contract v3: first-class instrument fields (CIRCUIT-001 P4) ────────────────
// P3-B carried these inside `geometry` verbatim so as not to touch the P2D contract. P4
// promotes them to validated schema. What P3-B persisted must still validate — the checks
// below accept exactly the shapes `handleEditing.syncAnchors` / the trace tool write.

// A trace endpoint anchors to a reference or to itself. `point` → `at` IS the endpoint;
// a ref kind (`ground`/`region`/`percept`/`mark`) → `ref` owns the real position, `at` is a
// cached copy, and `detached_from_ref` records a drag that froze it (contract v2 decision #1).
export const ANCHOR_KINDS = ['point', 'ground', 'region', 'percept', 'mark'];

// A brush stroke either adds paint or erases it. Erase is DATA, not a compositing detail
// (contract v2 decision B) — so `op` travels with the stroke and validates here.
export const STROKE_OPS = ['add', 'sub'];

// Who produced a mark. Only a real producer (or a fixture, in tests) may carry a run_id;
// a curator's own mark names no producer. The suggestion-provenance shape (contract v3 §P4).
// P5-A adds `find_similar`: a visual-neighbour search is a producer whose suggestions cross the
// border to another post (a cross-post `region_ref`).
export const PRODUCERS = ['sam_refine', 'semantic_read', 'planner', 'find_similar', 'fixture'];

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
// A region_mask's role is OPTIONAL (contract v2 §7.2-C): a segmented extent has no perceptual
// role until a curator gives it one. If present it names WHAT was segmented, not how it reads.
export const REGION_MASK_ROLE_KEYS = ['segment', 'part', 'material_extent', 'anchor_extent'];

/** type → the role vocabulary that type's `role` must belong to. */
export const ROLE_VOCABULARY = {
    brush_field: FIELD_ROLE_KEYS,
    trace_mark: TRACE_ROLE_KEYS,
    relation_mark: RELATION_ROLE_KEYS,
    frame_mark: FRAME_ROLE_KEYS,
    collection_mark: COLLECTION_ROLE_KEYS,
    region_mask: REGION_MASK_ROLE_KEYS,
};

/** Families whose `role` is optional — `region_mask` alone, so far. */
export const OPTIONAL_ROLE_TYPES = new Set(['region_mask']);

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
            // P4 contract v3: run identity is now REAL. The CIRCULATION-SPINE run substrate
            // (`vision_runs` + `vision_run_service`) landed, so a producer mark carries the id
            // of the run that made it. `null` still means "no producer / a curator's own mark".
            // The deliberate `run_id: null` of P2D ends here (see contract §P4).
            run_id: null,
            producer: null,     // one of PRODUCERS, or null for a curator's mark
            adapter: null,      // e.g. 'sam2', 'semantic_pass' — the concrete transport
            latency_ms: null,   // wall time the producer took, when known
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

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isPoint = (p) => Array.isArray(p) && p.length >= 2 && isNum(p[0]) && isNum(p[1]);

/**
 * Validate one trace anchor (contract v3). Returns an error string, or null when valid.
 * Mirrors exactly what `handleEditing.syncAnchors` / the trace tool write:
 *   { kind, at:[nx,ny], ref?, detached_from_ref? }
 * A `point` anchor needs no ref (it anchors to itself); a ref kind needs a non-empty ref.
 */
export function anchorError(a) {
    if (a == null) return null;                              // an absent endpoint anchor is fine
    if (typeof a !== 'object' || Array.isArray(a)) return 'anchor must be an object';
    if (!ANCHOR_KINDS.includes(a.kind)) return `anchor.kind "${String(a.kind)}" is not in the vocabulary`;
    if (a.at != null && !isPoint(a.at)) return 'anchor.at must be a normalized [x,y] point';
    if (a.kind !== 'point' && !nonEmpty(a.ref)) return `anchor.kind "${a.kind}" requires a ref`;
    if (a.detached_from_ref != null && typeof a.detached_from_ref !== 'boolean') {
        return 'anchor.detached_from_ref must be a boolean';
    }
    return null;
}

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
    // word outside it fails — otherwise a planner's mistake becomes invisible. `region_mask`
    // is the one family whose role is OPTIONAL (a segmented extent has no perceptual role yet):
    // null is allowed, but a NON-null role still has to be in the vocabulary.
    const vocab = ROLE_VOCABULARY[mark.type];
    if (vocab) {
        const optional = OPTIONAL_ROLE_TYPES.has(mark.type);
        if (mark.role == null) {
            if (!optional) errors.push(`${mark.type}: role is required`);
        } else if (!vocab.includes(mark.role)) {
            errors.push(`${mark.type}: role "${mark.role}" is not in the vocabulary`);
        }
    }

    const geom = mark.geometry;
    if (!geom || typeof geom !== 'object') errors.push('geometry must be an object');
    else if (!GEOMETRY_KINDS.includes(geom.kind)) {
        errors.push(`unknown geometry kind: ${String(geom.kind)}`);
    }

    // Contract v2 §7.2-C + v3: a region_mask points at an existing region and authors NOTHING
    // inline. It references that region one of two ways:
    //   - `raster_mask` + `mask_ref{region_id}` — a SEGMENTED extent (SAM/Dissect drew the mask);
    //   - `region_ref` + `region_ref{region_id}`  — a NAMING reference only, no mask authored
    //     (the VLM's law: it may say WHAT a region is, never draw one). P4 producer 2 mints these.
    // Never pixels, never a freehand path — the mask lives on the Region, the mark references it.
    if (mark.type === 'region_mask' && geom && typeof geom === 'object') {
        if (geom.kind === 'raster_mask') {
            if (!geom.mask_ref || !nonEmpty(geom.mask_ref.region_id)) {
                errors.push('region_mask (raster_mask) requires geometry.mask_ref.region_id');
            }
        } else if (geom.kind === 'region_ref') {
            const rr = geom.region_ref;
            // A naming reference authors NO mask — carrying a mask_ref here is a copy across the
            // border (P5-A: a crossing is a reference, never a copy). raster_mask is the ONLY
            // mode that owns a mask_ref.
            if (geom.mask_ref != null) {
                errors.push('region_ref geometry may not carry a mask_ref — it references, never copies');
            }
            if (!rr || !nonEmpty(rr.region_id)) {
                errors.push('region_mask (region_ref) requires geometry.region_ref.region_id');
            } else {
                // P5-A · the crossing. A region_ref MAY name a region on ANOTHER post — a
                // cross-post reference `{region_id, post_id, geometry_rev}`. Still no pixels
                // (a crossing is a reference, never a copy); only the border coordinates.
                if (rr.post_id != null && !nonEmpty(rr.post_id)) {
                    errors.push('region_ref.post_id must be a non-empty post id or absent');
                }
                if (rr.geometry_rev != null && !isNum(rr.geometry_rev)) {
                    errors.push('region_ref.geometry_rev must be a number (the rev at citation) or absent');
                }
            }
        } else {
            errors.push('region_mask geometry must be raster_mask or region_ref');
        }
        for (const banned of ['pixels', 'rle', 'polygons', 'strokes', 'points']) {
            if (geom[banned] != null) errors.push(`region_mask geometry may not carry inline ${banned}`);
        }
    }

    // Contract v3 first-class fields — validated wherever a geometry carries them, so a shape
    // P3-B wrote (anchors on a polyline/vector trace, ambiguous/arrowhead flags, strokes[].op)
    // is checked rather than passed through blind. Absent fields are always fine (back-compat).
    if (geom && typeof geom === 'object') {
        if (geom.anchors != null) {
            if (typeof geom.anchors !== 'object' || Array.isArray(geom.anchors)) {
                errors.push('geometry.anchors must be an object { from, to }');
            } else {
                for (const end of ['from', 'to']) {
                    const err = anchorError(geom.anchors[end]);
                    if (err) errors.push(`geometry.anchors.${end}: ${err}`);
                }
            }
        }
        if (geom.ambiguous != null && typeof geom.ambiguous !== 'boolean') {
            errors.push('geometry.ambiguous must be a boolean');
        }
        if (geom.arrowhead != null && typeof geom.arrowhead !== 'boolean') {
            errors.push('geometry.arrowhead must be a boolean');
        }
        if (geom.strokes != null && mark.type !== 'region_mask') {
            if (!Array.isArray(geom.strokes)) {
                errors.push('geometry.strokes must be an array');
            } else {
                geom.strokes.forEach((s, i) => {
                    if (s && s.op != null && !STROKE_OPS.includes(s.op)) {
                        errors.push(`geometry.strokes[${i}].op "${String(s.op)}" is not add|sub`);
                    }
                });
            }
        }
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
    // Contract v3 (P4): run identity is now real. `run_id` may be null (a curator's mark) or a
    // non-empty run id (a producer's). The P2D "must stay null" rule is retired — the run
    // substrate exists, so a produced suggestion finally carries its receipt.
    if (mark.provenance && mark.provenance.run_id != null && !nonEmpty(mark.provenance.run_id)) {
        errors.push('provenance.run_id must be a non-empty run id or null');
    }
    // A named producer must be one we recognise; and a real producer must own a run — a
    // suggestion that claims to come from the model without a run_id has lost its receipt.
    if (mark.provenance && mark.provenance.producer != null) {
        if (!PRODUCERS.includes(mark.provenance.producer)) {
            errors.push(`provenance.producer "${String(mark.provenance.producer)}" is not in the vocabulary`);
        } else if (mark.provenance.producer !== 'fixture' && !nonEmpty(mark.provenance.run_id)) {
            errors.push(`provenance.producer "${mark.provenance.producer}" requires a run_id`);
        }
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

/**
 * A region_mask mark for an accepted/proposed SAM segment. The mask itself lives on the
 * Region (`region_id` + `geometry_rev`); this only references it — never inline pixels
 * (contract v2 §7.2-C). Role is left null: a segmented extent has no perceptual reading
 * until a curator gives it one via the conversion path.
 */
export function regionMaskMark({
    regionId, geometryRev = 0, source = 'user', status = 'draft',
    derivedFrom = null, role = null, label = '', model = null, linkedGroundIds = [],
    runId = null, producer = null, adapter = null, latencyMs = null,
} = {}, { now = null, idFn = markId } = {}) {
    return normalizeMark({
        type: 'region_mask',
        role,
        label,
        source,
        status,
        derived_from: derivedFrom,
        geometry: { kind: 'raster_mask', mask_ref: { region_id: regionId, geometry_rev: geometryRev } },
        linked_ground_ids: arr(linkedGroundIds),
        provenance: { ...(model ? { model } : {}), run_id: runId, producer, adapter, latency_ms: latencyMs },
    }, { now, idFn });
}

/**
 * A region_ref mark: a NAMING reference to an existing region, authoring no mask (contract v3).
 * This is what a semantic-read label proposal becomes — the VLM says "region X is a collar"
 * without drawing anything. Defaults to a quarantined model suggestion.
 */
export function regionRefMark({
    regionId, source = 'model_suggested', status = 'suggested', role = null, label = '',
    model = null, runId = null, producer = 'semantic_read', adapter = null, latencyMs = null,
    derivedFrom = null, linkedGroundIds = [],
    // P5-A · the crossing. A region_ref may name a region on ANOTHER post — the reference then
    // carries the border coordinates `{post_id, geometry_rev}`. Same-post refs omit both.
    postId = null, geometryRev = null,
} = {}, { now = null, idFn = markId } = {}) {
    const region_ref = { region_id: regionId };
    if (postId != null) region_ref.post_id = postId;
    if (geometryRev != null) region_ref.geometry_rev = geometryRev;
    return normalizeMark({
        type: 'region_mask',
        role,
        label,
        source,
        status,
        derived_from: derivedFrom,
        geometry: { kind: 'region_ref', region_ref },
        linked_ground_ids: arr(linkedGroundIds),
        provenance: { model, run_id: runId, producer, adapter, latency_ms: latencyMs },
    }, { now, idFn });
}

// ── the crossing (CIRCUIT-001 P5-A) ────────────────────────────────────────────
// A cross-post mark is a REFERENCE, never a copy: a `region_ref` whose `region_ref` carries a
// `post_id` naming another post. These readers are the one place that recognises the border, so
// a chip, a recall, and a staleness check all agree on what "across the border" means.

/**
 * The border reference a cross-post `region_ref` mark carries, or **null** for a same-post mark.
 * `{ post_id, region_id, geometry_rev }` — the rev is the value AT CITATION, so a later drift on
 * the source is detectable (never hidden). Pure; reads only the mark.
 */
export function crossPostReference(mark) {
    const rr = mark?.geometry?.region_ref;
    if (!rr || !nonEmpty(rr.post_id)) return null;
    return {
        post_id: rr.post_id,
        region_id: rr.region_id ?? null,
        geometry_rev: isNum(rr.geometry_rev) ? rr.geometry_rev : null,
    };
}

/** True when a mark points across the border (references a region on another post). */
export const isCrossPostMark = (m) => !!crossPostReference(m);

// ── persistence policy (contract v2 §7.3) ─────────────────────────────────────
// Only committed and superseded marks persist. `superseded` because recoverability is the
// whole point of the status (P1F/P1G); everything else — draft/staged/suggested/previewed/
// dismissed — is session-only, so the quarantine never touches the database.
export const PERSISTED_STATUSES = new Set(['committed', 'superseded']);
export const isPersistableMark = (m) => !!m && PERSISTED_STATUSES.has(m.status);
export const persistableMarks = (marks = []) => (marks || []).filter(isPersistableMark);

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
