// CIRCUIT-001 P2D-A — `visual_layer`: the layer model Semant never had.
//
// Implements `CIRCUIT-001-P2D-interface-contract.md` §3. Data model only — there is no
// layer-manager UI in P2D, and this module renders nothing.
//
// P2C §1.5 found Semant has NO layer concept: z-order is implicit (canvas element before svg
// element) and the only per-mark state is transient attention narrowing. This adds the
// missing structural layer — visibility, opacity, lock, order — while keeping attention
// narrowing SEPARATE, because a transient derived dim and a stored curator decision are
// different things and must not collapse into one number.
//
// Binding on Lane B (contract §3): a visual_layer maps to a Konva **Group**, never a Konva
// **Layer** — Konva caps real layers at 3-5 because each is a real <canvas>.

export const LAYER_TYPES = ['evidence', 'suggestion', 'recall', 'scratch'];

/**
 * `recall` is a SYSTEM layer: transient performance, not a curator surface. It may not be
 * locked, reordered or saved — the same discipline that keeps recall from being mistaken for
 * stored state anywhere else in the circuit.
 */
export const SYSTEM_LAYER_TYPES = ['recall'];
export const isSystemLayer = (layer) => SYSTEM_LAYER_TYPES.includes(layer?.layer_type);

let _seq = 0;
export function layerId() {
    return `vl_${Date.now().toString(36)}_${(_seq++).toString(36)}`;
}
export function _resetLayerIds() { _seq = 0; }   // test aid only

// The four the product ships with, in render order. `suggestion` sits ABOVE `evidence` so a
// proposal is visible over the marks it might replace; `recall` is on top because a
// performance briefly owns the eye; `scratch` is the bottom working surface.
const DEFAULT_LAYER_SPECS = [
    { layer_type: 'scratch', name: 'Working', order: 0 },
    { layer_type: 'evidence', name: 'Evidence', order: 1 },
    { layer_type: 'suggestion', name: 'Suggestions', order: 2 },
    { layer_type: 'recall', name: 'Recall', order: 3, locked: true },
];

export function normalizeLayer(raw, { idFn = layerId } = {}) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
    if (!LAYER_TYPES.includes(raw.layer_type)) return null;
    const system = SYSTEM_LAYER_TYPES.includes(raw.layer_type);
    const layer = {
        id: raw.id || idFn(),
        name: typeof raw.name === 'string' && raw.name.trim() ? raw.name : raw.layer_type,
        layer_type: raw.layer_type,
        visibility: raw.visibility !== false,          // default visible
        opacity: clamp01(raw.opacity, 1),
        // A system layer is always locked, whatever the caller passed.
        locked: system ? true : !!raw.locked,
        order: Number.isFinite(raw.order) ? raw.order : 0,
        mark_ids: Array.isArray(raw.mark_ids) ? [...raw.mark_ids] : [],
        provenance: { created_by: 'system', action_id: null, ...(raw.provenance || {}) },
    };
    return validateLayer(layer).valid ? layer : null;
}

export function validateLayer(layer) {
    const errors = [];
    if (!layer || typeof layer !== 'object') return { valid: false, errors: ['not an object'] };
    if (!LAYER_TYPES.includes(layer.layer_type)) errors.push(`unknown layer_type: ${String(layer.layer_type)}`);
    if (typeof layer.id !== 'string' || !layer.id) errors.push('missing id');
    if (typeof layer.visibility !== 'boolean') errors.push('visibility must be boolean');
    if (typeof layer.locked !== 'boolean') errors.push('locked must be boolean');
    if (!(layer.opacity >= 0 && layer.opacity <= 1)) errors.push('opacity must be 0..1');
    if (!Array.isArray(layer.mark_ids)) errors.push('mark_ids must be an array');
    if (isSystemLayer(layer) && !layer.locked) errors.push('a recall (system) layer must be locked');
    return { valid: errors.length === 0, errors };
}

/** Exactly the four system layers, normalized. */
export function createDefaultLayers({ idFn = layerId } = {}) {
    return DEFAULT_LAYER_SPECS.map((spec) => normalizeLayer(spec, { idFn }));
}

// ── membership ───────────────────────────────────────────────────────────────

/**
 * Which layer a mark belongs on, by its source/status — NOT a free choice.
 * A `model_suggested`/`suggested`/`previewed` mark belongs on `suggestion` and nowhere else;
 * that is the quarantine, expressed as a placement rule so a mark cannot be filed onto
 * `evidence` by mistake.
 */
export function layerCanContainMark(layer, mark) {
    if (!layer || !mark) return false;
    const quarantined = mark.source === 'model_suggested'
        || mark.status === 'suggested' || mark.status === 'previewed';
    if (quarantined) return layer.layer_type === 'suggestion';
    if (layer.layer_type === 'suggestion') return false;   // nothing else belongs here
    if (layer.layer_type === 'recall') return false;       // recall membership is transient, set by the player
    return true;                                           // evidence or scratch
}

/**
 * Assign a mark to a layer, returning a NEW layer set. Refuses a placement that
 * `layerCanContainMark` forbids, and refuses to add to a locked non-recall layer. Removes
 * the mark from any other layer first, so a mark lives on exactly one.
 */
export function assignMarkToLayer(layers, markOrId, targetLayerId, { mark = null } = {}) {
    const id = typeof markOrId === 'string' ? markOrId : markOrId?.id;
    const theMark = mark || (typeof markOrId === 'object' ? markOrId : null);
    const target = (layers || []).find((l) => l.id === targetLayerId);
    if (!id || !target) return layers;
    if (theMark && !layerCanContainMark(target, theMark)) return layers;
    if (target.locked && !isSystemLayer(target)) return layers;
    return (layers || []).map((l) => {
        if (l.id === targetLayerId) {
            return l.mark_ids.includes(id) ? l : { ...l, mark_ids: [...l.mark_ids, id] };
        }
        if (l.mark_ids.includes(id)) return { ...l, mark_ids: l.mark_ids.filter((m) => m !== id) };
        return l;
    });
}

// ── view + mutation (all immutable) ──────────────────────────────────────────

export const getVisibleLayers = (layers = []) =>
    [...layers].filter((l) => l.visibility).sort((a, b) => a.order - b.order);

export function toggleLayerVisibility(layers = [], id) {
    return layers.map((l) => (l.id === id ? { ...l, visibility: !l.visibility } : l));
}

export function setLayerOpacity(layers = [], id, opacity) {
    const o = clamp01(opacity, null);
    if (o == null) return layers;
    return layers.map((l) => (l.id === id ? { ...l, opacity: o } : l));
}

export function lockLayer(layers = [], id) {
    return layers.map((l) => (l.id === id ? { ...l, locked: true } : l));
}

export function unlockLayer(layers = [], id) {
    // A system layer cannot be unlocked — its lock is structural, not a preference.
    return layers.map((l) => (l.id === id && !isSystemLayer(l) ? { ...l, locked: false } : l));
}

/**
 * Reorder to the given id sequence, rewriting `order` to match. A system layer keeps its
 * place: recall is always on top, so any sequence that would move it is ignored for it.
 */
export function reorderLayers(layers = [], orderedIds = []) {
    const byId = Object.fromEntries((layers || []).map((l) => [l.id, l]));
    const movable = orderedIds.filter((id) => byId[id] && !isSystemLayer(byId[id]));
    const system = (layers || []).filter(isSystemLayer);
    const seq = [...movable, ...system.map((l) => l.id)];
    return seq
        .map((id, i) => (byId[id] ? { ...byId[id], order: i } : null))
        .filter(Boolean);
}

function clamp01(v, fallback) {
    if (typeof v !== 'number' || Number.isNaN(v)) return fallback;
    return Math.min(1, Math.max(0, v));
}
