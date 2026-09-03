/**
 * Brush intensity — the internal anatomy of ONE field (Differential v1).
 *
 * A soft field already answers "where is it?" and "what kind of field is it?".
 * It could not answer a third question the hand was already asking: *within this
 * field, which passages carry different degrees of the noticing?* The neck, the
 * passage below the neckline and the answering hand do different work in one
 * reading; flattening them into a single wash forces the prose to recover a
 * distinction the mark itself already knew.
 *
 * THE LOAD-BEARING DISTINCTIONS — four quantities that must not be confused:
 *
 *   `radius`            spatial reach of the brush.
 *   point pressure      the gesture, as the hardware reported it.
 *   `strength`          a continuous RENDER alpha; every stroke has carried 0.8.
 *   `intensity_level`   the curator's authored SEMANTIC claim. 1|2|3|4.
 *
 * Only the last is a claim. Deriving it from pressure would make accidental
 * hardware input epistemically meaningful and would make mouse, trackpad, stylus
 * and accessibility input disagree about what the curator said.
 *
 * WHY FOUR, AND NOT A SLIDER. `0.63` has no stable perceptual grammar — a curator
 * cannot say why it is not `0.58`, prose cannot cite an unbounded set of values,
 * and continuous values invite mistaken equivalence with opacity, confidence,
 * importance or model certainty. A finite ordinal language is testable, teachable
 * and replayable. This does not assert that perceptual intensity IS four-valued;
 * it establishes a learnable instrument from which later evidence can show whether
 * levels collapse, divide, or need another axis entirely.
 *
 * Higher does NOT mean truer, more certain, or more important. It means only
 * *more intense within this curator's present field-reading*. Levels are ordered
 * INSIDE a mark, never compared across images.
 *
 * This module is the single home of the vocabulary, its validation and its render
 * recipes, so interaction (DifferentialWorkspace), rendering (fieldCanvas) and the
 * tests all read the same constants instead of three drifting copies.
 */

/** The vocabulary. Names are aids, not ontology — a percept may name its own. */
export const BRUSH_INTENSITY_LEVELS = [
    { level: 1, key: 'trace', label: 'Trace', hint: 'peripheral, incipient, or faint participation' },
    { level: 2, key: 'supporting', label: 'Supporting', hint: 'a secondary passage that sustains the reading' },
    { level: 3, key: 'structural', label: 'Structural', hint: 'a passage doing clear compositional work' },
    { level: 4, key: 'dominant', label: 'Dominant', hint: 'the passage the reading most strongly turns on' },
];

export const INTENSITY_LEVELS = BRUSH_INTENSITY_LEVELS.map((l) => l.level);

/** New brush sessions start here. */
export const DEFAULT_INTENSITY_LEVEL = 3;

/**
 * What a stroke written before this vocabulary existed is READ as. 3, because it
 * is the level whose recipe reproduces the historical `strength: 0.8` appearance
 * exactly — so no archived field changes how it looks the day this ships.
 */
export const LEGACY_INTENSITY_LEVEL = 3;

/** The historical per-stroke render alpha. Neutral point for the recipes below. */
export const DEFAULT_STRENGTH = 0.8;

const BY_LEVEL = new Map(BRUSH_INTENSITY_LEVELS.map((l) => [l.level, l]));

/**
 * Validation by REJECTION, never by rounding. `3.5` is not "about 4" — it is an
 * authored value this vocabulary does not contain, and rounding it would let an
 * invalid claim masquerade as a valid one. `true` is not 1 and `'3'` is not 3:
 * a strict check is what keeps a coerced type out of the persisted record.
 */
export function isIntensityLevel(value) {
    return value === 1 || value === 2 || value === 3 || value === 4;
}

/** The level, or `null` when the value is absent or not in the vocabulary. */
export function normalizeIntensityLevel(value) {
    return isIntensityLevel(value) ? value : null;
}

export const intensityMeta = (level) => BY_LEVEL.get(level) || null;
export const intensityLabel = (level) => BY_LEVEL.get(level)?.label || String(level);

/** A stroke asserts a level only when it is additive. Erasing edits geometry. */
export const isAdditiveStroke = (stroke) => !!stroke && stroke.op !== 'sub';
export const isSubtractiveStroke = (stroke) => !!stroke && stroke.op === 'sub';

/**
 * The level a stroke was AUTHORED with — `null` for legacy, invalid, or
 * subtractive strokes. This is the read used when reporting what a curator said.
 */
export function authoredLevelOf(stroke) {
    if (!isAdditiveStroke(stroke)) return null;
    return normalizeIntensityLevel(stroke.intensity_level);
}

/**
 * The level a stroke is DRAWN at. Legacy and invalid values fall back to
 * `LEGACY_INTENSITY_LEVEL` so every field still renders — but this is a READ, and
 * nothing here writes back. A stroke without the field stays without it until a
 * curator authors one; reading an archive must never quietly re-save it.
 */
export function renderLevelOf(stroke) {
    return authoredLevelOf(stroke) ?? LEGACY_INTENSITY_LEVEL;
}

/** True when the stroke carries no honest authored level (renders as legacy). */
export const isLegacyStroke = (stroke) => isAdditiveStroke(stroke) && authoredLevelOf(stroke) === null;

/**
 * Stamp the selected level onto a NEW stroke. Subtractive strokes omit the key
 * entirely rather than carrying a level they do not assert — an erase alters the
 * accumulated mask across every level and makes no claim about any of them.
 */
export function withIntensity(stroke, level) {
    if (!stroke) return stroke;
    if (isSubtractiveStroke(stroke)) {
        const { intensity_level, ...rest } = stroke;   // eslint-disable-line no-unused-vars
        return rest;
    }
    const lv = normalizeIntensityLevel(level);
    if (lv === null) return stroke;
    return { ...stroke, intensity_level: lv };
}

/**
 * Which levels a field's ADDITIVE strokes actually use, ascending. Legacy strokes
 * report as `LEGACY_INTENSITY_LEVEL` because that is the register they perform at;
 * `levelsAuthoredBy` is the stricter read when only explicit claims count.
 */
export function levelsUsedBy(ground) {
    const seen = new Set();
    for (const s of ground?.strokes || []) {
        if (isAdditiveStroke(s)) seen.add(renderLevelOf(s));
    }
    return [...seen].sort((a, b) => a - b);
}

/** Only the levels a curator explicitly authored — legacy strokes excluded. */
export function levelsAuthoredBy(ground) {
    const seen = new Set();
    for (const s of ground?.strokes || []) {
        const lv = authoredLevelOf(s);
        if (lv !== null) seen.add(lv);
    }
    return [...seen].sort((a, b) => a - b);
}

/** How many additive strokes sit at each used level — the anatomy's weights. */
export function intensityAnatomy(ground) {
    const counts = new Map();
    let legacy = 0;
    for (const s of ground?.strokes || []) {
        if (!isAdditiveStroke(s)) continue;
        if (isLegacyStroke(s)) legacy += 1;
        const lv = renderLevelOf(s);
        counts.set(lv, (counts.get(lv) || 0) + 1);
    }
    return {
        levels: [...counts.keys()].sort((a, b) => a - b)
            .map((level) => ({ level, label: intensityLabel(level), count: counts.get(level) })),
        legacyCount: legacy,
    };
}

/** "levels 1, 2, 3" — the draft status fragment. Empty when nothing is painted. */
export function levelsSummary(strokes) {
    const used = levelsUsedBy({ strokes });
    return used.length ? `levels ${used.join(', ')}` : '';
}

// ── render recipes ──────────────────────────────────────────────────────────
//
// FOUR EXPLICIT NAMED RECIPES, one per level. Two channels move together — the
// body alpha and the contour — because alpha ALONE collapses: a light wash
// disappears into light pixels, and the four levels stop being distinguishable
// on exactly the images where the distinction matters most. The contour is the
// channel that survives a bright background, so it carries the difference there.
//
// HUE IS NOT A CHANNEL HERE. Hue already identifies the field/layer role; four
// hues would multiply two meanings into one colour and make neither readable.
// All four recipes take whatever accent the layer supplies.
//
// `core` is the alpha stamped into the mask; `body` the alpha of the composite
// pass; `rimBlur` the contour's tightness; `rimBoost` an OPTIONAL second pass that
// deepens the contour (and, with it, slightly the core) where alpha alone would
// not separate the top register from the one below it. Level 3 is tuned to
// reproduce today's appearance EXACTLY (core 0.8 = the historical `strength`,
// body 0.46 = the historical WASH_ALPHA, rimBlur 3.5 = the historical RIM_BLUR,
// no boost), which is what makes it the honest legacy default.
export const INTENSITY_RECIPES = Object.freeze({
    1: Object.freeze({ level: 1, name: 'trace', core: 0.30, body: 0.26, rimBlur: 2.2, rimBoost: 0 }),
    2: Object.freeze({ level: 2, name: 'supporting', core: 0.55, body: 0.36, rimBlur: 2.8, rimBoost: 0 }),
    3: Object.freeze({ level: 3, name: 'structural', core: 0.80, body: 0.46, rimBlur: 3.5, rimBoost: 0 }),
    4: Object.freeze({ level: 4, name: 'dominant', core: 1.00, body: 0.60, rimBlur: 4.2, rimBoost: 0.22 }),
});

export const recipeFor = (level) => INTENSITY_RECIPES[level] || INTENSITY_RECIPES[LEGACY_INTENSITY_LEVEL];

/**
 * The alpha one stroke stamps into the mask.
 *
 * `strength` stays the renderer parameter it has always been and is NOT replaced
 * by the level; it is normalized against its historical default so that at level
 * 3 this returns `strength` itself. That identity is the backward-compatibility
 * proof: every archived stroke — including producer strokes written at 0.4 or
 * 1.0 — stamps exactly the alpha it stamped before this module existed.
 */
export function stampAlphaFor(stroke, level = null) {
    const lv = level ?? renderLevelOf(stroke);
    const strength = Number.isFinite(stroke?.strength) ? stroke.strength : DEFAULT_STRENGTH;
    const scaled = recipeFor(lv).core * (strength / DEFAULT_STRENGTH);
    return Math.max(0, Math.min(1, scaled));
}

/**
 * THE COMPOSITING POLICY, as data — so it can be tested without a canvas.
 *
 * The old renderer stamped every stroke into ONE buffer and tinted the result at
 * one uniform alpha. Per-stroke differences survived only as mask alpha and the
 * contour was cast once around the combined silhouette, so four levels would have
 * flattened into one wash — the exact failure this vocabulary exists to prevent.
 *
 * So: one pass PER USED LEVEL, in ASCENDING order, each with its own recipe. Draw
 * order is therefore a function of the level, never of authoring order — two
 * curators who paint the same anatomy in a different sequence get the same image.
 *
 * Every pass carries the ground's FULL subtractive set. An erase edits the field's
 * geometry, so it must cut every level it crosses; applying it to only the level
 * selected when the curator erased would leave the other levels uncut and the
 * field would not honestly show what was taken away.
 */
export function intensityPasses(ground) {
    const strokes = ground?.strokes || [];
    const subs = strokes.filter(isSubtractiveStroke);
    const byLevel = new Map();
    for (const s of strokes) {
        if (!isAdditiveStroke(s)) continue;
        const lv = renderLevelOf(s);
        if (!byLevel.has(lv)) byLevel.set(lv, []);
        byLevel.get(lv).push(s);
    }
    return [...byLevel.keys()].sort((a, b) => a - b).map((level) => ({
        level,
        recipe: recipeFor(level),
        add: byLevel.get(level),
        sub: subs,
    }));
}

// ── the percept's use of a field's anatomy ──────────────────────────────────
//
// Phrases live on the PERCEPT, never on the ground — the same rule, and the same
// reason, as `groundRoles.js`. The same painted field may be "answering hand" in
// one reading and something else entirely in another; writing the phrase onto
// `post.grounds` would let the second percept overwrite the first, and the
// evidence record would start carrying an interpretation.
//
// `ground_roles` could not host these: it is typed `Dict[str, str]` — groundId to
// a role STRING — so a nested per-level map would break its declared shape. This
// is a sibling key instead, which rides the backend's `extra="allow"` carrier and
// its emit-only-what-was-set serializer: no migration, and a percept that never
// names a level stays byte-identical to one written before the key existed.

/** Level keys are STRINGS in the record, because JSON object keys are strings. */
const levelKey = (level) => String(level);

/**
 * Read a percept's intensity readings as { groundId: { "1": phrase } }.
 * Tolerates every historical shape: absent, null, or an array left by a writer
 * that did not know better.
 */
export function intensityReadingsOf(percept) {
    const raw = percept?.ground_intensity_readings;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    const out = {};
    for (const [gid, byLevel] of Object.entries(raw)) {
        if (!gid || !byLevel || typeof byLevel !== 'object' || Array.isArray(byLevel)) continue;
        const clean = {};
        for (const [lk, phrase] of Object.entries(byLevel)) {
            if (!isIntensityLevel(Number(lk))) continue;
            if (typeof phrase !== 'string' || !phrase.trim()) continue;
            clean[levelKey(Number(lk))] = phrase;
        }
        if (Object.keys(clean).length) out[gid] = clean;
    }
    return out;
}

/** This percept's phrases for one cited ground: { "1": phrase }. */
export const readingsFor = (percept, groundId) => intensityReadingsOf(percept)[groundId] || {};

/**
 * Set (or with an empty string, clear) one phrase. Returns a NEW percept; never
 * mutates, and never touches the ground record.
 *
 * Two refusals, both load-bearing: a percept may not name a level in a ground it
 * did not cite, and may not name a level that ground's additive strokes do not
 * actually use. The second is what keeps the anatomy honest — a phrase for a
 * level nobody painted is a reading of evidence that is not there.
 */
export function setIntensityReading(percept, groundId, level, phrase, ground = null) {
    if (!percept || !groundId) return percept;
    if (!(percept.ground_ids || []).includes(groundId)) return percept;
    if (!isIntensityLevel(level)) return percept;
    if (ground && !levelsUsedBy(ground).includes(level)) return percept;

    const all = intensityReadingsOf(percept);
    const forGround = { ...(all[groundId] || {}) };
    const text = typeof phrase === 'string' ? phrase.trim() : '';
    if (text) forGround[levelKey(level)] = text;
    else delete forGround[levelKey(level)];

    const next = { ...all };
    if (Object.keys(forGround).length) next[groundId] = forGround;
    else delete next[groundId];

    // Drop the key entirely when empty, so a percept that never named a level is
    // byte-identical to one whose phrases were all cleared.
    if (!Object.keys(next).length) {
        const { ground_intensity_readings, ...rest } = percept;  // eslint-disable-line no-unused-vars
        return rest;
    }
    return { ...percept, ground_intensity_readings: next };
}

/**
 * Drop anything a ground can no longer support — a level whose strokes were
 * erased away, or a ground the percept no longer cites. Used on the write path so
 * a stale phrase never outlives the evidence it claims to read.
 */
export function pruneIntensityReadings(readings, { ground_ids = [], groundById = () => null } = {}) {
    const out = {};
    for (const [gid, byLevel] of Object.entries(readings || {})) {
        if (!ground_ids.includes(gid)) continue;
        const used = levelsUsedBy(groundById(gid));
        const clean = {};
        for (const [lk, phrase] of Object.entries(byLevel || {})) {
            const lv = Number(lk);
            if (!isIntensityLevel(lv) || !used.includes(lv)) continue;
            const text = typeof phrase === 'string' ? phrase.trim() : '';
            if (text) clean[levelKey(lv)] = text;
        }
        if (Object.keys(clean).length) out[gid] = clean;
    }
    return out;
}
