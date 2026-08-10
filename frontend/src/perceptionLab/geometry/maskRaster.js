// PERCEPTUAL-ORGANS-002 Lane E — mask rasters, and the rings drawn from them.
//
// WHY THIS EXISTS AT ALL. The contract says the mask RLE is the authoritative measurement and
// that "polygons and box are projections derived from the mask". `RegionOverlay` — the one place
// in this application where a shape is drawn — consumes normalized rings. Nothing in the
// Perception Lab contract carries rings. So either this module derives them from the RLE, or the
// laboratory draws the bounding box instead and a person looks at a rectangle believing they are
// looking at a segmentation.
//
// That second option is the WAVE2.5 failure with a nicer surface, so: exact decode, exact
// boundary, and a `derived` flag on everything that leaves here.
//
// WHAT IS EXACT AND WHAT IS NOT.
//
//   - `decodeRle` is exact. COCO uncompressed RLE, column-major runs beginning with zeros.
//   - `maskRings` is exact: it walks the actual pixel boundary of the raster. It approximates
//     nothing — the staircase IS the mask at that raster. Collinear runs are merged, which
//     changes the vertex count and not one boundary position.
//   - Everything under `derive*` is a PROJECTION computed in this browser. It is drawn so a
//     person can see where a measurement lives; it is not the measurement, it may not agree
//     with the producer's own arithmetic to the pixel, and every caller labels it as derived.
//
// COORDINATES. Rings come out normalized [0,1] against the RASTER, which is the same normalized
// image space the stage-geometry contract uses (`useStageGeometry`), so a 200×150 mask raster on
// a 1600×1200 image lands correctly without anybody rescaling anything. A coarse raster is a real
// fact about the measurement, and `MaskRaster.h/w` is carried so the inspector can say so.
//
// PURE MODULE. No DOM, no React, no fetch.

/** @typedef {{ h: number, w: number, data: Uint8Array }} MaskRaster */

/** An all-zero raster of the given shape. */
export function emptyRaster(h, w) {
    return { h, w, data: new Uint8Array(h * w) };
}

/**
 * COCO uncompressed RLE → a row-major byte raster.
 *
 * `counts` are run lengths in COLUMN-major order and the first run is of zeros. A counts list
 * that does not fill h*w is not an error: the remainder is zero, which is how a hand-authored
 * fixture describes a small mark in a large frame. A run that overshoots is clipped rather than
 * throwing, because a raster that renders slightly short is a better failure than a lab that
 * cannot open the artifact at all — `rleFillsRaster` reports the discrepancy for the inspector.
 */
export function decodeRle(rle) {
    if (!rle || !Array.isArray(rle.size) || !Array.isArray(rle.counts)) return null;
    const [h, w] = rle.size;
    if (!Number.isInteger(h) || !Number.isInteger(w) || h <= 0 || w <= 0) return null;
    const data = new Uint8Array(h * w);
    let i = 0;            // running index in COLUMN-major order
    let value = 0;        // the first run is zeros
    const total = h * w;
    for (const run of rle.counts) {
        const n = Math.max(0, Math.min(Number(run) || 0, total - i));
        if (value) {
            for (let k = 0; k < n; k++) {
                const j = i + k;
                const col = Math.floor(j / h);
                const row = j - col * h;
                data[row * w + col] = 1;
            }
        }
        i += n;
        value ^= 1;
        if (i >= total) break;
    }
    return { h, w, data };
}

/** Whether the counts covered the whole raster — an honest note, not a validity test. */
export function rleFillsRaster(rle) {
    if (!rle || !Array.isArray(rle.size) || !Array.isArray(rle.counts)) return false;
    const [h, w] = rle.size;
    const sum = rle.counts.reduce((a, b) => a + (Number(b) || 0), 0);
    return sum === h * w;
}

/** Re-encode a raster as COCO uncompressed RLE. The round trip is asserted in the suite. */
export function encodeRle(mask) {
    const { h, w, data } = mask;
    const counts = [];
    let value = 0;
    let run = 0;
    for (let col = 0; col < w; col++) {
        for (let row = 0; row < h; row++) {
            const v = data[row * w + col] ? 1 : 0;
            if (v === value) { run++; } else { counts.push(run); value = v; run = 1; }
        }
    }
    counts.push(run);
    return { size: [h, w], counts };
}

export const maskArea = (mask) => {
    let n = 0;
    for (let i = 0; i < mask.data.length; i++) if (mask.data[i]) n++;
    return n;
};

/** Area as a fraction of the raster — comparable across rasters, unlike a pixel count. */
export const maskAreaFraction = (mask) => (mask.h * mask.w ? maskArea(mask) / (mask.h * mask.w) : 0);

const sameShape = (a, b) => a && b && a.h === b.h && a.w === b.w;

const combine = (a, b, fn) => {
    if (!sameShape(a, b)) return null;
    const out = emptyRaster(a.h, a.w);
    for (let i = 0; i < a.data.length; i++) out.data[i] = fn(a.data[i], b.data[i]) ? 1 : 0;
    return out;
};

export const maskAnd = (a, b) => combine(a, b, (x, y) => x && y);
export const maskOr = (a, b) => combine(a, b, (x, y) => x || y);
export const maskSub = (a, b) => combine(a, b, (x, y) => x && !y);
export const maskNot = (a) => {
    const out = emptyRaster(a.h, a.w);
    for (let i = 0; i < a.data.length; i++) out.data[i] = a.data[i] ? 0 : 1;
    return out;
};

/** Square-structuring-element dilation by `r` pixels. Used only for derived contact bands. */
export function dilate(mask, r) {
    if (!r || r <= 0) return { h: mask.h, w: mask.w, data: Uint8Array.from(mask.data) };
    const { h, w, data } = mask;
    const out = emptyRaster(h, w);
    for (let row = 0; row < h; row++) {
        for (let col = 0; col < w; col++) {
            if (!data[row * w + col]) continue;
            const r0 = Math.max(0, row - r);
            const r1 = Math.min(h - 1, row + r);
            const c0 = Math.max(0, col - r);
            const c1 = Math.min(w - 1, col + r);
            for (let rr = r0; rr <= r1; rr++) {
                for (let cc = c0; cc <= c1; cc++) out.data[rr * w + cc] = 1;
            }
        }
    }
    return out;
}

/** Normalized centroid of the on-pixels, or null for an empty mask. */
export function maskCentroid(mask) {
    const { h, w, data } = mask;
    let sx = 0; let sy = 0; let n = 0;
    for (let row = 0; row < h; row++) {
        for (let col = 0; col < w; col++) {
            if (!data[row * w + col]) continue;
            sx += col + 0.5; sy += row + 0.5; n++;
        }
    }
    if (!n) return null;
    return { x: sx / n / w, y: sy / n / h };
}

/** Normalized tight bounding box of the on-pixels, or null. A BOX, and labelled as one. */
export function maskBox(mask) {
    const { h, w, data } = mask;
    let x0 = w; let y0 = h; let x1 = -1; let y1 = -1;
    for (let row = 0; row < h; row++) {
        for (let col = 0; col < w; col++) {
            if (!data[row * w + col]) continue;
            if (col < x0) x0 = col;
            if (col > x1) x1 = col;
            if (row < y0) y0 = row;
            if (row > y1) y1 = row;
        }
    }
    if (x1 < 0) return null;
    return { x: x0 / w, y: y0 / h, w: (x1 + 1 - x0) / w, h: (y1 + 1 - y0) / h };
}

// ── the boundary ────────────────────────────────────────────────────────────

const key = (x, y) => `${x},${y}`;

/**
 * The exact pixel boundary of a raster, as normalized rings.
 *
 * Every edge between an on-pixel and an off-pixel (or the raster border) is emitted with the
 * interior on its left, then the edges are stitched head-to-tail into closed rings. Holes come
 * out with the opposite winding, which is precisely what `fill-rule="evenodd"` in
 * `maskGeometry.ringsToPath` wants — so the rings from here drop straight into `RegionOverlay`
 * and holes cut out without this module knowing anything about holes.
 *
 * At a diagonal pinch two rings meet at one vertex; the walk takes edges in insertion order,
 * which splits the pinch consistently. Either split traces the same boundary.
 */
export function maskRings(mask) {
    if (!mask) return [];
    const { h, w, data } = mask;
    const on = (r, c) => (r >= 0 && r < h && c >= 0 && c < w ? data[r * w + c] : 0);
    /** @type {Map<string, Array<[number, number]>>} */
    const edges = new Map();
    const push = (x0, y0, x1, y1) => {
        const k = key(x0, y0);
        const list = edges.get(k);
        if (list) list.push([x1, y1]); else edges.set(k, [[x1, y1]]);
    };
    for (let r = 0; r < h; r++) {
        for (let c = 0; c < w; c++) {
            if (!on(r, c)) continue;
            if (!on(r - 1, c)) push(c, r, c + 1, r);              // top,    →
            if (!on(r, c + 1)) push(c + 1, r, c + 1, r + 1);      // right,  ↓
            if (!on(r + 1, c)) push(c + 1, r + 1, c, r + 1);      // bottom, ←
            if (!on(r, c - 1)) push(c, r + 1, c, r);              // left,   ↑
        }
    }

    const rings = [];
    for (const startKey of [...edges.keys()]) {
        while ((edges.get(startKey) || []).length) {
            const [sx, sy] = startKey.split(',').map(Number);
            const ring = [[sx, sy]];
            let cx = sx; let cy = sy;
            // Bounded by the edge count: every step consumes one edge.
            for (;;) {
                const list = edges.get(key(cx, cy));
                if (!list || !list.length) break;
                const [nx, ny] = list.shift();
                if (!list.length) edges.delete(key(cx, cy));
                cx = nx; cy = ny;
                if (cx === sx && cy === sy) break;
                ring.push([cx, cy]);
            }
            if (ring.length > 2) rings.push(ring);
        }
    }
    return rings.map((ring) => simplify(ring).map(([x, y]) => [x / w, y / h]));
}

/** Drop the middle vertex of any three collinear points. Boundary positions do not move. */
function simplify(ring) {
    const out = [];
    const n = ring.length;
    for (let i = 0; i < n; i++) {
        const [px, py] = ring[(i - 1 + n) % n];
        const [x, y] = ring[i];
        const [nx, ny] = ring[(i + 1) % n];
        const collinear = (x - px) * (ny - y) === (y - py) * (nx - x);
        if (!collinear) out.push([x, y]);
    }
    return out.length > 2 ? out : ring;
}

/**
 * The closest pair of on-pixels between two rasters, with the CENTRE-TO-CENTRE separation in
 * raster pixels and as a fraction of the raster diagonal — the length of the line a clearance
 * projection draws, not the count of empty pixels between the two shapes. Returns null when
 * either is empty or the shapes differ.
 *
 * O(|A| · |B|) on the boundary pixels only. The lab's rasters are small by construction, and a
 * clearance line drawn from an approximate nearest pair would be a picture of the wrong gap.
 */
export function nearestPair(a, b) {
    if (!sameShape(a, b)) return null;
    // Only boundary pixels can be the closest pair, and there are far fewer of them.
    const edgeOf = (m) => {
        const pts = [];
        const { h, w, data } = m;
        const at = (r, c) => (r >= 0 && r < h && c >= 0 && c < w ? data[r * w + c] : 0);
        for (let r = 0; r < h; r++) {
            for (let c = 0; c < w; c++) {
                if (!data[r * w + c]) continue;
                if (!at(r - 1, c) || !at(r + 1, c) || !at(r, c - 1) || !at(r, c + 1)) pts.push([c, r]);
            }
        }
        return pts;
    };
    const pa = edgeOf(a);
    const pb = edgeOf(b);
    if (!pa.length || !pb.length) return null;
    let best = Infinity; let ba = null; let bb = null;
    for (const [ax, ay] of pa) {
        for (const [bx, by] of pb) {
            const d = (ax - bx) ** 2 + (ay - by) ** 2;
            if (d < best) { best = d; ba = [ax, ay]; bb = [bx, by]; }
        }
    }
    const px = Math.sqrt(best);
    const diag = Math.sqrt(a.h * a.h + a.w * a.w);
    return {
        from: { x: (ba[0] + 0.5) / a.w, y: (ba[1] + 0.5) / a.h },
        to: { x: (bb[0] + 0.5) / a.w, y: (bb[1] + 0.5) / a.h },
        distance_px: px,
        distance_fraction: diag ? px / diag : 0,
    };
}
