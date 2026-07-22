/**
 * Spike 3 — `perfect-freehand` (MIT, 1.2.3) vs the vendored `freehandTaper.js`.
 *
 * Both are pure points-in / polygon-out functions. There is **zero ontology risk
 * here**: neither one decides what a mark means, only what its outline is. That
 * is exactly the category the P2C rule calls an implementation choice —
 * "open-source libraries provide mechanics" — so this spike is a measurement,
 * not a judgement about Semant's model.
 *
 * FAIRNESS NOTE, and it matters for reading the numbers:
 *
 * Both are fed points in NATURAL PIXEL space, not normalized 0..1 — the same
 * conversion `GroundLayers.jsx:41 toPx` already performs before calling
 * `taperedRibbon`. `perfect-freehand`'s `streamline` and `smoothing` are
 * distance-based, so running it in 0..1 units with a `size` of 0.05 silently
 * changes its behaviour rather than merely rescaling it. Comparing the two in
 * different unit systems would have produced a confident, meaningless result.
 */

import { getStroke } from 'perfect-freehand';
import { taperedRibbon, polylineLength } from '../freehandTaper';

/** Normalized [x,y,p] → natural-pixel [x,y,p]. Mirrors GroundLayers' `toPx`. */
export const toPx = (points, natural) => points.map((p) => {
    const [x, y, pr] = Array.isArray(p) ? p : [p.x, p.y, p.p];
    return [x * natural.w, y * natural.h, pr];
});

/**
 * `perfect-freehand` defaults chosen to sit as close to `freehandTaper`'s
 * intent as its options allow, so the comparison is of QUALITY and not of
 * tuning. `taperedRibbon` grows quickly to full width and tapers to a point at
 * the head; `thinning` + `end.taper` is that shape's nearest expression.
 */
export const PF_DEFAULTS = {
    size: 16,
    thinning: 0.6,
    smoothing: 0.5,
    streamline: 0.5,
    simulatePressure: false,      // the corpus HAS pressure; do not fabricate it
    start: { taper: 0, cap: true },
    end: { taper: 40, cap: true },
};

/** Outline polygon (array of [x,y]) from perfect-freehand. */
export function strokeViaPerfectFreehand(pxPoints, options = {}) {
    return getStroke(pxPoints, { ...PF_DEFAULTS, ...options });
}

/** Polygon → SVG path `d`, closed. */
export function polygonToPath(poly) {
    if (!poly?.length) return '';
    return poly.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ') + ' Z';
}

/**
 * `taperedRibbon` returns a path string, not a polygon, so vertex count is
 * recovered by counting commands. Counting is not cosmetic: output size is one
 * of the three things this spike measures, and a ribbon that needs 4× the
 * vertices for the same stroke costs that on every render and every serialize.
 */
export function countPathVertices(d) {
    return (d.match(/[ML]/g) || []).length;
}

/** Median wall-clock ms over `runs`, discarding a warmup. Median, not mean:
 *  one GC pause in a 30-run sample moves a mean by more than the effect being
 *  measured. */
export function timeIt(fn, runs = 30) {
    fn(); fn();                                   // warm the JIT
    const samples = [];
    for (let i = 0; i < runs; i++) {
        const t0 = performance.now();
        fn();
        samples.push(performance.now() - t0);
    }
    samples.sort((a, b) => a - b);
    return {
        median: samples[Math.floor(samples.length / 2)],
        min: samples[0],
        max: samples[samples.length - 1],
    };
}

/**
 * Does the outline actually respond to pressure?
 *
 * The test: hand the same path twice — once with real per-point pressure, once
 * with pressure flattened to a constant — and measure how much the outline
 * moves. A generator that ignores pressure returns ~0 here, and that is a
 * finding no amount of looking at a screenshot settles reliably.
 */
export function pressureSensitivity(pxPoints, produce) {
    const flat = pxPoints.map(([x, y]) => [x, y, 0.5]);
    const a = produce(pxPoints);
    const b = produce(flat);
    const n = Math.min(a.length, b.length);
    if (!n) return 0;
    let sum = 0;
    for (let i = 0; i < n; i++) sum += Math.hypot(a[i][0] - b[i][0], a[i][1] - b[i][1]);
    return sum / n;
}

/** Parse a `taperedRibbon` path back into a polygon, so both can be measured
 *  by the same yardstick (bbox, pressure sensitivity, vertex count). */
export function pathToPolygon(d) {
    const out = [];
    const re = /[ML]\s*(-?[\d.]+),(-?[\d.]+)/g;
    let m;
    while ((m = re.exec(d))) out.push([parseFloat(m[1]), parseFloat(m[2])]);
    return out;
}

export function polygonBBox(poly) {
    if (!poly?.length) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of poly) {
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/**
 * Run the whole comparison for one stroke.
 * `points` are NORMALIZED; `natural` is the image's pixel size.
 */
export function compareTaper(points, natural, { size = null, runs = 20 } = {}) {
    const px = toPx(points, natural);
    const maxWidth = 0.02 * natural.w;
    const pfSize = size ?? maxWidth;

    const pfProduce = (pts) => strokeViaPerfectFreehand(pts, { size: pfSize });
    const ftProduce = (pts) => pathToPolygon(taperedRibbon(pts, { maxWidth }));

    const pfPoly = pfProduce(px);
    const ftPath = taperedRibbon(px, { maxWidth });
    const ftPoly = pathToPolygon(ftPath);

    const { total } = polylineLength(px);

    return {
        input: { points: px.length, arcLengthPx: Math.round(total), hasPressure: px.some((p) => p[2] != null) },
        perfectFreehand: {
            vertices: pfPoly.length,
            pathChars: polygonToPath(pfPoly).length,
            bbox: polygonBBox(pfPoly),
            pressureSensitivityPx: pressureSensitivity(px, pfProduce),
            timing: timeIt(() => pfProduce(px), runs),
            d: polygonToPath(pfPoly),
        },
        freehandTaper: {
            vertices: countPathVertices(ftPath),
            pathChars: ftPath.length,
            bbox: polygonBBox(ftPoly),
            pressureSensitivityPx: pressureSensitivity(px, ftProduce),
            timing: timeIt(() => ftProduce(px), runs),
            d: ftPath,
        },
    };
}
