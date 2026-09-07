/**
 * Instrument extent — the size of the mark, which is NOT the size of the view.
 *
 * Brush radius and boundary band width are **image-relative evidence geometry**:
 * they are stored normalized to image width and describe how much of the
 * anatomy a stroke claims. Zoom must never touch them. At 4× the cursor is
 * physically larger on screen because the same brush covers the same extent of
 * a larger picture — that is the correct behaviour, not a bug to compensate for.
 * A constant-screen-pixel brush would be a DIFFERENT instrument (its stored
 * radius would depend on how the curator happened to be looking), and it is not
 * being smuggled in here.
 *
 * Both instruments already had these values and both already had bracket keys;
 * what was missing was seeing and directly setting them.
 *
 * ── why the slider is logarithmic ───────────────────────────────────────────
 *
 * The useful range spans more than a decade (0.012 → 0.16 of image width). On a
 * linear track the bottom decade occupies under 6% of the travel, so every fine
 * radius — the ones a curator reaches for when working into a wrist or a hem at
 * high zoom, which is the whole reason the workbench exists — is crammed into a
 * few pixels of thumb movement. A log mapping gives equal travel to equal RATIO,
 * so a step is always the same proportional change and the fine end gets the
 * resolution it needs.
 */

/** The brush's safe range, as the bracket keys have always clamped it. */
export const BRUSH_RANGE = Object.freeze({ min: 0.012, max: 0.16 });

/** The boundary band's range, likewise from its existing bracket clamps. */
export const BAND_RANGE = Object.freeze({ min: 0.02, max: 0.2 });

/** One bracket press: the same 0.82 / 1.22 the keys have always applied. */
export const STEP_DOWN = 0.82;
export const STEP_UP = 1.22;

export const clampTo = (v, { min, max }) => Math.min(max, Math.max(min, v));

/** Slider position (0..1) → value. Equal travel gives equal ratio. */
export function positionToValue(t, range) {
    const p = Math.min(1, Math.max(0, t));
    return range.min * ((range.max / range.min) ** p);
}

/** Value → slider position (0..1). The exact inverse. */
export function valueToPosition(v, range) {
    const c = clampTo(v, range);
    return Math.log(c / range.min) / Math.log(range.max / range.min);
}

export const stepUp = (v, range) => clampTo(v * STEP_UP, range);
export const stepDown = (v, range) => clampTo(v * STEP_DOWN, range);

/**
 * How the extent reads to a person: a percentage of image WIDTH, because that is
 * the quantity actually stored. "4.5%" is a claim about the picture; a pixel
 * count would be a claim about the screen and would change with the window.
 */
export const extentLabel = (v) => `${(v * 100).toFixed(1)}% of image width`;
export const extentShort = (v) => `${(v * 100).toFixed(1)}%`;

/**
 * Three named reaches. Not a separate stored vocabulary — each preset is just a
 * value in the same continuous range, so a preset and a dragged slider produce
 * records that are indistinguishable, as they should be.
 */
export const BRUSH_PRESETS = Object.freeze([
    { key: 'fine', label: 'Fine', value: 0.018 },
    { key: 'medium', label: 'Medium', value: 0.045 },
    { key: 'broad', label: 'Broad', value: 0.1 },
]);

/** The preset a value currently sits on, or null when it sits between them. */
export function presetFor(v, presets = BRUSH_PRESETS) {
    const hit = presets.find((p) => Math.abs(p.value - v) < 1e-9);
    return hit ? hit.key : null;
}
