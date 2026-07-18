/**
 * Tiny freehand-taper helper (Differential v1 · increment C).
 *
 * A vendored stand-in for perfect-freehand: turns a normalized polyline into a
 * tapered ribbon outline, so a Path reads as a directed gesture (thin at the
 * tail, full through the body, drawn to a point at the head) rather than a flat
 * stroke. No new runtime dep — the spec calls for exactly this.
 *
 * All coordinates are normalized (0..1); callers multiply by the natural image
 * size for the SVG viewBox. Points may be [x, y] or [x, y, pressure].
 */

const xy = (p) => (Array.isArray(p) ? [p[0], p[1], p[2]] : [p.x, p.y, p.p]);

/** Cumulative arc length + total, for the taper profile and dash animations. */
export function polylineLength(points) {
    let total = 0;
    const cum = [0];
    for (let i = 1; i < points.length; i++) {
        const [x0, y0] = xy(points[i - 1]);
        const [x1, y1] = xy(points[i]);
        total += Math.hypot(x1 - x0, y1 - y0);
        cum.push(total);
    }
    return { cum, total };
}

// Resample so a fast drag (sparse points) still tapers smoothly.
function resample(points, step) {
    if (points.length < 2) return points.map(xy);
    const { cum, total } = polylineLength(points);
    if (total === 0) return [xy(points[0])];
    const out = [];
    let target = 0;
    let seg = 1;
    while (target <= total && seg < points.length) {
        while (seg < points.length && cum[seg] < target) seg++;
        if (seg >= points.length) break;
        const t = (target - cum[seg - 1]) / Math.max(1e-6, cum[seg] - cum[seg - 1]);
        const [ax, ay, ap = 0] = xy(points[seg - 1]);
        const [bx, by, bp = 0] = xy(points[seg]);
        out.push([ax + (bx - ax) * t, ay + (by - ay) * t, ap + (bp - ap) * t]);
        target += step;
    }
    out.push(xy(points[points.length - 1]));
    return out;
}

/**
 * SVG path `d` for a tapered ribbon around `points`.
 * width profile: eases up from `tailWidth`·max at the tail to max through the
 * body, then to a point at the head. Pressure, when present, modulates locally.
 */
export function taperedRibbon(points, { maxWidth = 0.02, tailWidth = 0.25 } = {}) {
    const pts = resample(points, Math.max(0.004, maxWidth * 0.5));
    if (pts.length < 2) return '';
    const n = pts.length;

    const widthAt = (i, pressure) => {
        const t = i / (n - 1);
        // grow in (ease), hold, taper to a point at the head
        const head = 1 - t;                      // 1 at tail → 0 at head
        const grow = Math.min(1, t / 0.18);      // reach full width quickly
        const profile = Math.min(grow, Math.pow(head, 0.7) / Math.pow(0.82, 0.7));
        const pr = pressure ? 0.6 + 0.4 * pressure : 1;
        return Math.max(0, maxWidth * (tailWidth + (1 - tailWidth) * profile) * pr);
    };

    const left = [];
    const right = [];
    for (let i = 0; i < n; i++) {
        const [x, y, p] = pts[i];
        const [px] = pts[Math.max(0, i - 1)];
        const prev = pts[Math.max(0, i - 1)];
        const next = pts[Math.min(n - 1, i + 1)];
        let dx = next[0] - prev[0];
        let dy = next[1] - prev[1];
        const len = Math.hypot(dx, dy) || 1;
        dx /= len; dy /= len;
        const nx = -dy, ny = dx;                 // unit normal
        const w = widthAt(i, p) / 2;
        left.push([x + nx * w, y + ny * w]);
        right.push([x - nx * w, y - ny * w]);
        void px;
    }

    const fwd = left.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(4)},${y.toFixed(4)}`).join(' ');
    const back = right.reverse().map(([x, y]) => `L${x.toFixed(4)},${y.toFixed(4)}`).join(' ');
    return `${fwd} ${back} Z`;
}

/** The plain centerline `d` — used for the travel animation (dashoffset). */
export function centerlinePath(points) {
    const pts = points.map(xy);
    if (!pts.length) return '';
    return pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(4)},${y.toFixed(4)}`).join(' ');
}

/** A small end chevron (arrowhead) at the head of a path, in normalized coords. */
export function endChevron(points, size = 0.03) {
    const pts = points.map(xy);
    if (pts.length < 2) return '';
    const [hx, hy] = pts[pts.length - 1];
    const [bx, by] = pts[pts.length - 2];
    let dx = hx - bx, dy = hy - by;
    const len = Math.hypot(dx, dy) || 1;
    dx /= len; dy /= len;
    const nx = -dy, ny = dx;
    const back = size, spread = size * 0.6;
    const l = [hx - dx * back + nx * spread, hy - dy * back + ny * spread];
    const r = [hx - dx * back - nx * spread, hy - dy * back - ny * spread];
    return `M${l[0].toFixed(4)},${l[1].toFixed(4)} L${hx.toFixed(4)},${hy.toFixed(4)} L${r[0].toFixed(4)},${r[1].toFixed(4)}`;
}
