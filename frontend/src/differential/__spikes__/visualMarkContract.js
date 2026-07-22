/**
 * visualMarkContract — LOCAL STUB of the P2D interface contract (Lane B).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS AND WHY IT MUST NOT SURVIVE
 *
 * The binding spec named by the Lane B brief —
 *   `Build specs/CIRCUIT-001-P2D-interface-contract.md`
 * — did NOT exist on this lane's base commit (01d0300), and neither did any
 * `visualMarks.js` in `frontend/src/differential/`. Lane A is authoring both in
 * parallel. Per the brief's instruction ("otherwise stub the signatures locally
 * and note any signature you wished were different"), this module reimplements
 * the contract from its published ancestor —
 *   `Build specs/CIRCUIT-001-P2C-OH-open-harvest-perceptual-instruments.md` §4
 * — which is the source §4.1–§4.6 the interface contract is derived from, plus
 * the `derived_from` acceptance edge that §3.5.1 (Label Studio
 * `parent_prediction`) prescribes and the Lane B brief names explicitly.
 *
 * **Every divergence between this stub and Lane A's real module is Lane A's to
 * win.** This file is a test double for a renderer experiment, not an ontology
 * proposal. Signature friction is recorded in the spike report, §"Contract
 * friction notes for Lane A" — not resolved here.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE ONE RULE THIS MODULE ENFORCES MECHANICALLY (contract §6 / OH §4 rule zero)
 *
 *   No renderer object is ever truth.
 *
 * `serializeMark` is a WHITELIST, not a blacklist. A Konva.Line, a Fabric.Path,
 * an SVGPathElement or a DOM node cannot reach serialized output by being
 * forgotten — only a key named in the schema is copied, and every copied value
 * is walked by `assertPlainData` which throws on any non-plain value. A
 * blacklist ("strip `_konvaNode`") is the version of this that silently fails
 * the first time somebody names the field something else.
 */

// ── vocabulary (P2B's, verbatim — OH §4 rule one: do not invent a fourth) ────

export const MARK_TYPES = [
    'brush_field', 'trace_mark', 'relation_mark', 'region_ref', 'frame_ref',
];

/** OH §4.1 `source`. The P2B five plus the two the mark layer needs. */
export const MARK_SOURCES = [
    'user', 'system', 'model_suggested', 'user_confirmed', 'model_refined', 'fixture',
];

/** OH §4.1 `status`. `superseded` is the one that earns its place. */
export const MARK_STATUSES = ['draft', 'staged', 'committed', 'dismissed', 'superseded'];

/** OH §4.2 — the twelve P2B field roles. */
export const FIELD_ROLES = [
    'light_field', 'shadow_field', 'atmosphere_field', 'material_field',
    'pressure_zone', 'gaze_field', 'negative_space', 'threshold', 'fold',
    'rhythm', 'background_recession', 'external_limit',
];

/** OH §4.3 — the eight P2B trace roles. */
export const TRACE_ROLES = [
    'gaze_address', 'gesture', 'fall_of_light', 'architectural_axis',
    'movement', 'implied_address', 'comparison_path', 'force_direction',
];

/** OH §4.4 — the nine P2B relation roles. */
export const RELATION_ROLES = [
    'similarity', 'contrast', 'kinship', 'motif_echo', 'support',
    'tension', 'contradiction', 'temporal_suggestion', 'address_relation',
];

export const GEOMETRY_KINDS = [
    'freehand_path', 'polygon', 'soft_mask', 'raster_mask',
    'vector', 'curve', 'polyline', 'derived', 'unresolved',
];

/** OH §4.5 — four layer types, and `suggestion` is the point. */
export const LAYER_TYPES = ['evidence', 'suggestion', 'recall', 'scratch'];

/** OH §4.2 — the wash ceiling. A style that exceeds it is clamped, not refused. */
export const OPACITY_CEILING = 0.32;

// ── id minting (grounds.js `groundId()` shape — monotonic tail, no collision) ─

let markSeq = 0;
let layerSeq = 0;

export function markId() {
    return `vm_${Date.now().toString(36)}_${(markSeq++).toString(36)}`;
}
export function layerId() {
    return `vl_${Date.now().toString(36)}_${(layerSeq++).toString(36)}`;
}
/** Test aid only — mirrors `_resetActionIds` in perceptualActions.js. */
export function _resetSpikeIds() { markSeq = 0; layerSeq = 0; }

// ── constructors ─────────────────────────────────────────────────────────────

/**
 * The common shape (OH §4.1). Every creation point flows through here so
 * provenance is always stamped — the same discipline `makeGround` enforces.
 */
export function makeVisualMark(type, fields = {}) {
    if (!MARK_TYPES.includes(type)) throw new Error(`Unknown visual_mark type: ${type}`);
    const now = fields.created_at || new Date().toISOString();
    return {
        id: markId(),
        type,
        role: null,
        label: '',
        source: 'user',
        status: 'draft',
        geometry: { kind: 'unresolved' },
        style: {},
        layer_id: null,
        linked_ground_ids: [],
        linked_percept_ids: [],
        linked_action_ids: [],
        // §3.5.1's `parent_prediction`, renamed. Non-null ⟹ this mark was
        // derived from another. `user_confirmed` is then a DERIVED fact, not a
        // boolean somebody has to remember to set.
        derived_from: null,
        provenance: { planner: null, prompt_excerpt: null, matched: [], model: null, run_id: null },
        created_at: now,
        updated_at: now,
        ...fields,
    };
}

export function makeBrushField(fields = {}) {
    return makeVisualMark('brush_field', {
        role: 'light_field',
        geometry: { kind: 'freehand_path', strokes: [] },
        style: { color: null, opacity: 0.28, softness: 0.6, width: 0.04 },
        suggested_by: null,
        confirmed_by: null,
        mask_ref: null,
        ...fields,
    });
}

export function makeTraceMark(fields = {}) {
    return makeVisualMark('trace_mark', {
        role: 'gaze_address',
        geometry: { kind: 'polyline', points: [] },
        style: { color: null, opacity: 1, softness: 0, width: 0.006 },
        anchors: { from: null, to: null },
        arrow: { head: 'chevron', at: 'end' },
        // OH §4.3 — the honesty field. A gaze often has no determinate terminus.
        ambiguous: false,
        ...fields,
    });
}

export function makeRelationMark(fields = {}) {
    return makeVisualMark('relation_mark', {
        role: 'contrast',
        // OH §4.4 — derived from its refs' centres at render time. NEVER stored.
        geometry: { kind: 'derived' },
        style: { color: null, opacity: 0.6, softness: 0, width: 0.004 },
        source_refs: [],
        target_refs: [],
        reason: '',
        ...fields,
    });
}

export function makeVisualLayer(fields = {}) {
    return {
        id: layerId(),
        name: 'Layer',
        layer_type: 'evidence',
        visibility: true,
        opacity: 1,
        locked: false,
        order: 0,
        mark_ids: [],
        provenance: { created_by: 'user', action_id: null },
        ...fields,
    };
}

/** An anchor (OH §4.3): `{ kind, ref, at }`. `at` is normalized 0..1. */
export function makeAnchor(kind, ref, at) {
    return { kind, ref: ref ?? null, at: at ? [round4(at[0]), round4(at[1])] : null };
}

// ── validation (fail-closed, in perceptualActions.js style) ──────────────────

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const inUnit = (v) => isNum(v) && v >= -0.5 && v <= 1.5;   // tolerate slight overdraw, refuse garbage
const round4 = (v) => Math.round(v * 1e4) / 1e4;

const ROLE_SET = {
    brush_field: FIELD_ROLES,
    trace_mark: TRACE_ROLES,
    relation_mark: RELATION_ROLES,
    region_ref: null,
    frame_ref: null,
};

function validPoint(p) {
    return Array.isArray(p) && p.length >= 2 && inUnit(p[0]) && inUnit(p[1])
        && (p.length < 3 || p[2] === undefined || isNum(p[2]));
}

/** Returns `{ ok, errors }`. Never throws — a malformed mark is data, not a crash. */
export function validateVisualMark(mark) {
    const errors = [];
    const push = (m) => errors.push(m);

    if (!mark || typeof mark !== 'object') return { ok: false, errors: ['mark is not an object'] };
    if (!mark.id || typeof mark.id !== 'string') push('id missing');
    if (!MARK_TYPES.includes(mark.type)) push(`unknown type: ${mark.type}`);
    if (!MARK_SOURCES.includes(mark.source)) push(`unknown source: ${mark.source}`);
    if (!MARK_STATUSES.includes(mark.status)) push(`unknown status: ${mark.status}`);

    const roles = ROLE_SET[mark.type];
    if (roles && mark.role != null && !roles.includes(mark.role)) push(`role not in ${mark.type} vocabulary: ${mark.role}`);

    const g = mark.geometry;
    if (!g || !GEOMETRY_KINDS.includes(g.kind)) {
        push(`unknown geometry kind: ${g?.kind}`);
    } else if (g.kind === 'freehand_path') {
        if (!Array.isArray(g.strokes)) push('freehand_path needs strokes[]');
        else for (const s of g.strokes) {
            if (!Array.isArray(s?.points)) { push('stroke needs points[]'); break; }
            if (!s.points.every(validPoint)) { push('stroke point out of normalized range'); break; }
        }
    } else if (g.kind === 'polyline' || g.kind === 'curve') {
        if (!Array.isArray(g.points)) push(`${g.kind} needs points[]`);
        else if (!g.points.every(validPoint)) push(`${g.kind} point out of normalized range`);
    } else if (g.kind === 'vector') {
        if (!validPoint(g.from) || !validPoint(g.to)) push('vector needs normalized from/to');
    } else if (g.kind === 'derived') {
        if (Object.keys(g).length > 1) push('derived geometry must carry no stored coordinates');
    }

    // OH §4.4 — a relation's geometry is derived, never stored. Enforced here
    // rather than by convention, because "a second truth that goes stale the
    // moment a member moves" is precisely the failure the rule names.
    if (mark.type === 'relation_mark' && mark.geometry?.kind !== 'derived') {
        push('relation_mark geometry must be kind:derived');
    }

    // §3.5.1 — `user_confirmed` is derived, not asserted.
    if (mark.source === 'user_confirmed' && !mark.derived_from) {
        push('user_confirmed requires derived_from (a confirmation with no parent is a laundered suggestion)');
    }
    // A suggestion is a proposal. It cannot already be evidence.
    if (mark.source === 'model_suggested' && mark.status === 'committed') {
        push('model_suggested may never hold status:committed');
    }

    return { ok: errors.length === 0, errors };
}

export function validateVisualLayer(layer) {
    const errors = [];
    if (!layer || typeof layer !== 'object') return { ok: false, errors: ['layer is not an object'] };
    if (!layer.id) errors.push('id missing');
    if (!LAYER_TYPES.includes(layer.layer_type)) errors.push(`unknown layer_type: ${layer.layer_type}`);
    if (typeof layer.visibility !== 'boolean') errors.push('visibility must be boolean');
    if (typeof layer.locked !== 'boolean') errors.push('locked must be boolean');
    if (!isNum(layer.opacity) || layer.opacity < 0 || layer.opacity > 1) errors.push('opacity out of 0..1');
    if (!Array.isArray(layer.mark_ids)) errors.push('mark_ids must be an array');
    // OH §4.5 — recall is transient performance. It must not be lockable.
    if (layer.layer_type === 'recall' && layer.locked) errors.push('recall layer must not be lockable');
    return { ok: errors.length === 0, errors };
}

// ── the no-renderer-object guarantee (contract §6) ───────────────────────────

/**
 * Walk a value and throw on anything that is not plain JSON data.
 *
 * This is what makes the whitelist total. A Konva node survives a naive
 * `JSON.parse(JSON.stringify(x))` round-trip as `{}` — silently emptied rather
 * than caught — so structural cloning is NOT a sufficient guard. Only an
 * explicit prototype check catches a class instance.
 */
export function assertPlainData(value, path = '$') {
    if (value === null || value === undefined) return value;
    const t = typeof value;
    if (t === 'string' || t === 'boolean') return value;
    if (t === 'number') {
        if (!Number.isFinite(value)) throw new Error(`non-finite number at ${path}`);
        return value;
    }
    if (t === 'function' || t === 'symbol' || t === 'bigint') {
        throw new Error(`non-serializable ${t} at ${path}`);
    }
    if (Array.isArray(value)) {
        value.forEach((v, i) => assertPlainData(v, `${path}[${i}]`));
        return value;
    }
    // The whole point: a Konva.Line, a Fabric.Path, an SVGPathElement and an
    // HTMLCanvasElement all fail here, and all of them would have passed a
    // `typeof x === 'object'` check.
    const proto = Object.getPrototypeOf(value);
    if (proto !== Object.prototype && proto !== null) {
        throw new Error(`renderer/class object at ${path}: ${value.constructor?.name || 'unknown'}`);
    }
    for (const [k, v] of Object.entries(value)) assertPlainData(v, `${path}.${k}`);
    return value;
}

/** The serialized keys, per type. Anything not listed here cannot get out. */
const COMMON_KEYS = [
    'id', 'type', 'role', 'label', 'source', 'status', 'geometry', 'style',
    'layer_id', 'linked_ground_ids', 'linked_percept_ids', 'linked_action_ids',
    'derived_from', 'provenance', 'created_at', 'updated_at',
];
const TYPE_KEYS = {
    brush_field: ['suggested_by', 'confirmed_by', 'mask_ref'],
    trace_mark: ['anchors', 'arrow', 'ambiguous'],
    relation_mark: ['source_refs', 'target_refs', 'reason'],
    region_ref: ['region_id'],
    frame_ref: ['whole', 'evidence_ids'],
};

const GEOMETRY_KEYS = {
    freehand_path: ['kind', 'strokes'],
    polygon: ['kind', 'rings'],
    soft_mask: ['kind', 'strokes'],
    raster_mask: ['kind', 'mask_ref'],
    vector: ['kind', 'from', 'to'],
    curve: ['kind', 'points', 'tension'],
    polyline: ['kind', 'points'],
    derived: ['kind'],
    unresolved: ['kind'],
};

function pick(obj, keys) {
    const out = {};
    for (const k of keys) if (obj && obj[k] !== undefined) out[k] = obj[k];
    return out;
}

function serializeGeometry(g) {
    if (!g || !GEOMETRY_KEYS[g.kind]) return { kind: 'unresolved' };
    const out = pick(g, GEOMETRY_KEYS[g.kind]);
    // Coordinates are rounded on the way out, not on the way in: a drag emits
    // hundreds of intermediate positions and rounding each one would quantize
    // the gesture. Rounding at the serialization boundary keeps the live edit
    // smooth and the stored record small and diffable.
    if (out.points) out.points = out.points.map(roundPoint);
    if (out.from) out.from = roundPoint(out.from);
    if (out.to) out.to = roundPoint(out.to);
    if (out.strokes) {
        out.strokes = out.strokes.map((s) => ({
            points: (s.points || []).map(roundPoint),
            radius: round4(s.radius ?? 0.04),
            strength: round4(s.strength ?? 0.85),
            op: s.op === 'sub' ? 'sub' : 'add',
        }));
    }
    return out;
}

function roundPoint(p) {
    const [x, y, pr] = Array.isArray(p) ? p : [p.x, p.y, p.p];
    return pr === undefined || pr === null ? [round4(x), round4(y)] : [round4(x), round4(y), round4(pr)];
}

/**
 * Mark → plain contract-shaped JSON. Whitelist; asserts plainness; throws on a
 * renderer object rather than quietly dropping it.
 */
export function serializeMark(mark) {
    const keys = [...COMMON_KEYS, ...(TYPE_KEYS[mark?.type] || [])];
    const out = pick(mark, keys);
    out.geometry = serializeGeometry(mark?.geometry);
    return assertPlainData(out, `mark(${mark?.id})`);
}

const LAYER_KEYS = ['id', 'name', 'layer_type', 'visibility', 'opacity', 'locked', 'order', 'mark_ids', 'provenance'];
export function serializeLayer(layer) {
    return assertPlainData(pick(layer, LAYER_KEYS), `layer(${layer?.id})`);
}

/** The whole workspace, in the shape the serialization panel shows. */
export function serializeWorkspace({ marks = [], layers = [] }) {
    return {
        layers: [...layers].sort((a, b) => a.order - b.order).map(serializeLayer),
        marks: marks.map(serializeMark),
    };
}

// ── suggestion quarantine (OH §5G — the load-bearing workflow) ───────────────

/** A suggestion is never evidence. This is the single predicate the UI asks. */
export function isCitable(mark) {
    return !!mark
        && mark.source !== 'model_suggested'
        && mark.status === 'committed';
}

/** Marks that may be counted, cited, recalled. Everything else is quarantined. */
export const citableMarks = (marks = []) => marks.filter(isCitable);

/**
 * Accept a `model_suggested` mark: mint a NEW `user_confirmed` mark pointing
 * back at it, and leave the suggestion untouched (§3.5.1 — "Predictions cannot
 * be modified and are always read-only").
 *
 * Returns `{ confirmed, suggestion }`. The suggestion is returned unchanged and
 * deliberately NOT marked dismissed: it stays a readable, distinct record of
 * what the model actually proposed, which is what makes "what exactly did the
 * human change?" answerable.
 */
export function acceptSuggestion(suggestion, { layerId: targetLayerId = null, now = null } = {}) {
    if (!suggestion || suggestion.source !== 'model_suggested') {
        throw new Error('acceptSuggestion: not a model_suggested mark');
    }
    const stamp = now || new Date().toISOString();
    const confirmed = makeVisualMark(suggestion.type, {
        ...structuredCloneish(suggestion),
        id: markId(),
        source: 'user_confirmed',
        status: 'committed',
        derived_from: suggestion.id,
        layer_id: targetLayerId ?? suggestion.layer_id,
        confirmed_by: 'user',
        created_at: stamp,
        updated_at: stamp,
    });
    return { confirmed, suggestion };
}

/** Structural copy that keeps only data — reuses the same guard as serialize. */
function structuredCloneish(mark) {
    return JSON.parse(JSON.stringify(serializeMark(mark)));
}

/**
 * Supersede rather than replace (OH §4.1). P1F/P1G established that silent
 * replacement is how a citation re-points without anyone noticing.
 */
export function supersedeMark(oldMark, nextFields = {}, { now = null } = {}) {
    const stamp = now || new Date().toISOString();
    const next = makeVisualMark(oldMark.type, {
        ...structuredCloneish(oldMark),
        id: markId(),
        derived_from: oldMark.id,
        status: 'committed',
        created_at: stamp,
        updated_at: stamp,
        ...nextFields,
    });
    return { next, superseded: { ...oldMark, status: 'superseded', updated_at: stamp } };
}

// ── derived relation geometry (OH §4.4 — computed, never stored) ─────────────

/**
 * Connector nodes for a relation, in NORMALIZED coords, resolved at call time.
 * `centerOf(ref)` is injected exactly the way `groundRoleList` injects `resolve`
 * — this module stays free of resolution concerns.
 */
export function relationNodes(mark, centerOf) {
    const refs = [...(mark.source_refs || []), ...(mark.target_refs || [])];
    const out = [];
    for (const r of refs) {
        const c = centerOf(r);
        if (c && inUnit(c[0]) && inUnit(c[1])) out.push([c[0], c[1]]);
    }
    return out;
}

// ── layer helpers ────────────────────────────────────────────────────────────

/** Is this mark editable right now? A locked or hidden layer says no. */
export function markIsEditable(mark, layers) {
    const layer = layers.find((l) => l.id === mark.layer_id);
    if (!layer) return true;                       // unlayered marks stay editable
    return layer.visibility && !layer.locked;
}

/** Effective render opacity: layer opacity × the mark's own style opacity. */
export function markRenderOpacity(mark, layers) {
    const layer = layers.find((l) => l.id === mark.layer_id);
    if (layer && !layer.visibility) return 0;
    const own = Math.min(mark.style?.opacity ?? 1, mark.type === 'brush_field' ? OPACITY_CEILING : 1);
    return own * (layer?.opacity ?? 1);
}

export const marksOnLayer = (marks, layerId) => marks.filter((m) => m.layer_id === layerId);
