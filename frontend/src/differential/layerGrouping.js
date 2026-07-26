// CIRCUIT-001 QUALITY-001 (Q-C) — render-grouping: the layer surface Lane B never built.
//
// P2D shipped `visualLayers.js` — a complete `visual_layer` DATA model (visibility/opacity/lock/
// order + the suggestion QUARANTINE) — but its only specced binding to a render surface was
// "maps to a Konva Group", Konva was rejected in the P2D-B spike, and no SVG replacement was
// built. So every committed ground still lands in ONE flat `gl-evidence` group.
//
// This module supplies the missing piece: it partitions committed grounds into layers BY
// PRODUCER/ROLE (find_parts on one, each perceptual field-role its own, traces and relations
// their own) so the single-surface pile self-organizes. It is pure (no React, no DOM), so the
// grouping is unit-testable, and it renders nothing — `GroundLayers` maps its output to one SVG
// `<g>` per layer, and the persisted `visual_layers` array carries each layer's saved
// visibility/opacity across reloads.

// Stable per-layer identity + display order. Field roles get their own layers dynamically
// (keyed `field:<role>`), so a new perceptual producer needs no change here.
export const LAYER_META = {
    find_parts: { name: 'Parts', order: 10 },
    trace: { name: 'Traces', order: 20 },
    relation: { name: 'Relations', order: 30 },
    frame: { name: 'Frame', order: 40 },
    field: { name: 'Fields', order: 50 },
    other: { name: 'Other', order: 90 },
};

// Human labels for the known field roles (else the raw role is title-cased).
const FIELD_ROLE_NAMES = {
    material_field: 'Material', negative_space: 'Negative space', rhythm: 'Rhythm',
    pressure_zone: 'Pressure', recession: 'Recession', atmosphere_field: 'Atmosphere',
    light_field: 'Light', shadow_field: 'Shadow', background_recession: 'Recession',
};

const titleCase = (s) => String(s || '').replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/**
 * The layer a committed ground belongs on, by its producer/role — NOT a free choice.
 * A field ground splits by its role (each perceptual field is its own layer); everything else
 * groups by `ground_type`. Returns a stable string key.
 */
export function groundLayerKey(ground) {
    if (!ground || typeof ground !== 'object') return 'other';
    const t = ground.ground_type;
    if (t === 'region') return 'find_parts';
    if (t === 'field') return ground.role ? `field:${ground.role}` : 'field';
    if (t === 'path' || t === 'boundary') return 'trace';
    if (t === 'relation' || t === 'constellation') return 'relation';
    if (t === 'frame') return 'frame';
    return 'other';
}

function layerName(key) {
    if (key.startsWith('field:')) {
        const role = key.slice('field:'.length);
        return FIELD_ROLE_NAMES[role] || titleCase(role);
    }
    return (LAYER_META[key] || {}).name || titleCase(key);
}

function layerOrder(key) {
    if (key.startsWith('field:')) {
        // field roles sort together after the base 'field' slot, alphabetically & stably
        return LAYER_META.field.order + 1;
    }
    return (LAYER_META[key] || LAYER_META.other).order;
}

function clamp01(v, fallback) {
    if (typeof v !== 'number' || Number.isNaN(v)) return fallback;
    return Math.min(1, Math.max(0, v));
}

/**
 * Derive the ordered layer descriptors present in `grounds`, merging any SAVED per-layer state
 * (`saved` is an array of `{ key, visibility, opacity }`, e.g. from `post.visual_layers`). Only
 * layers that actually have grounds appear — an empty layer never clutters the panel. Each
 * descriptor: `{ key, name, order, visibility, opacity, count }`.
 */
export function deriveLayers(grounds = [], saved = []) {
    const savedByKey = Object.fromEntries(
        (Array.isArray(saved) ? saved : []).filter((s) => s && s.key).map((s) => [s.key, s]));
    const counts = new Map();
    for (const g of grounds || []) {
        const k = groundLayerKey(g);
        counts.set(k, (counts.get(k) || 0) + 1);
    }
    const layers = [...counts.keys()].map((key) => {
        const s = savedByKey[key] || {};
        return {
            key,
            name: layerName(key),
            order: layerOrder(key),
            visibility: s.visibility !== false,          // default visible
            opacity: clamp01(s.opacity, 1),
            count: counts.get(key),
        };
    });
    // stable: primary by order, then by key so field roles have a fixed sequence
    layers.sort((a, b) => (a.order - b.order) || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
    return layers;
}

/**
 * The persistable form of a layer set — just the saved state each layer carries across reload
 * (`key`, `visibility`, `opacity`, `order`). Mirrors how `visual_marks` persist: an opaque list
 * of dicts on the post, written by the same PATCH.
 */
export function persistableLayers(layers = []) {
    return (layers || []).map((l) => ({
        key: l.key, visibility: l.visibility !== false, opacity: clamp01(l.opacity, 1),
        order: Number.isFinite(l.order) ? l.order : 0,
    }));
}
