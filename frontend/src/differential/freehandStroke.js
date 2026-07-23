/**
 * freehandStroke — perfect-freehand (MIT) as a drop-in ribbon generator.
 *
 * CIRCUIT-001 P2E-B, deliverable 2d. The P2D-B spike measured perfect-freehand
 * against the vendored `taperedRibbon` on the heaviest real corpus stroke
 * (1194 points) and found it ~18–20× more pressure-responsive with a smoother
 * taper, at no STORAGE cost (raw input points stay the stored truth; the polygon
 * is regenerated at render) but a larger output polygon (~20–29× vertices — a
 * render cost, and the documented rollback reason for the toggle).
 *
 * This module exposes the SAME signature as `taperedRibbon(pointsPx, {maxWidth})`
 * so `GroundLayers` can swap one for the other behind a boolean, with
 * `taperedRibbon` as the fallback. Points are in NATURAL-PIXEL space (the
 * `GroundLayers.toPx` convention), because perfect-freehand's `streamline`/
 * `smoothing` are distance-based and behave differently in 0..1 units.
 *
 * Pure: points in, SVG path `d` string out. No renderer object, no DOM.
 */

import { getStroke } from 'perfect-freehand';

/**
 * perfect-freehand options tuned to sit close to `taperedRibbon`'s intent: grow
 * quickly to full width, taper to a point at the head, honour real pressure and
 * never fabricate it (`simulatePressure: false` — the corpus HAS pressure, and a
 * generator that invents it would look good dishonestly).
 */
export function pfOptions(maxWidth) {
    return {
        size: maxWidth,
        thinning: 0.62,
        smoothing: 0.5,
        streamline: 0.5,
        simulatePressure: false,
        last: true,
        start: { taper: 0, cap: true },
        end: { taper: maxWidth * 2, cap: true },
    };
}

/** Outline polygon (array of `[x,y]`) for a stroke, in natural-pixel space. */
export function freehandOutline(pointsPx, { maxWidth = 12 } = {}) {
    if (!pointsPx || pointsPx.length === 0) return [];
    // perfect-freehand wants [x, y, pressure]; our points are already that shape.
    return getStroke(pointsPx, pfOptions(maxWidth));
}

/** Polygon → closed SVG path `d`. */
export function outlineToPath(outline) {
    if (!outline || outline.length < 2) return '';
    const d = outline.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
    return `${d} Z`;
}

/**
 * The drop-in: same call shape as `taperedRibbon(pointsPx, { maxWidth })`,
 * returning a closed ribbon path `d`. A one-point stroke returns '' (nothing to
 * draw), matching `taperedRibbon`.
 */
export function perfectFreehandRibbon(pointsPx, { maxWidth = 12 } = {}) {
    return outlineToPath(freehandOutline(pointsPx, { maxWidth }));
}

/** Vertex count of an outline — the render-cost number the spike measured. */
export const outlineVertexCount = (outline) => (outline ? outline.length : 0);
