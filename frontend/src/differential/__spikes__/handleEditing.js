/**
 * handleEditing — editable-anchor arithmetic on normalized geometry.
 *
 * This is Spike 2's core (the null hypothesis: "close the handles gap with a few
 * hundred lines and no dependency"), and Spike 1 imports it too. That reuse is
 * itself a finding rather than a convenience: **the anchor math is
 * renderer-independent.** Konva's `Transformer` does not supply it, because
 * Transformer resizes a bounding box — it has no concept of "the third vertex of
 * this polyline". So a scene-graph library does not save you from writing this
 * file; it only changes what draws the dots.
 *
 * Reference pattern (read for shape, not copied): Excalidraw's linear-element
 * editor, MIT — drag a point, insert a midpoint, delete a point, all on raw
 * geometry with pointer events.
 *
 * EVERY function here is pure, takes and returns normalized `[x, y]` (or
 * `[x, y, pressure]`) points, and never touches the DOM. Hit tolerances arrive
 * already converted to normalized units by the caller, because tolerance is a
 * SCREEN quantity (a fingertip is ~10 CSS px regardless of zoom) and converting
 * it here would require this module to know about the content box — which is
 * `useStageGeometry`'s job and no one else's.
 */

const sq = (v) => v * v;

/** Squared distance between two normalized points, in an aspect-corrected space. */
function dist2(a, b, aspect = 1) {
    // Normalized space is anisotropic: 0.01 in x is a different number of pixels
    // from 0.01 in y unless the image is square. Hit testing that ignores this
    // makes handles on a 3:2 image easier to grab vertically than horizontally —
    // a small bug that feels like "the app is imprecise" rather than like a bug.
    return sq((a[0] - b[0]) * aspect) + sq(a[1] - b[1]);
}

/**
 * Which anchor is under the pointer? Returns an index, or -1.
 * Later points win ties, so the head of a trace is grabbable when it overlaps
 * an earlier vertex — the head is what a curator reaches for.
 */
export function hitAnchor(points, at, tol, aspect = 1) {
    const t2 = sq(tol);
    let best = -1;
    let bestD = Infinity;
    for (let i = 0; i < points.length; i++) {
        const d = dist2(points[i], at, aspect);
        if (d <= t2 && d <= bestD) { bestD = d; best = i; }
    }
    return best;
}

/** The closest point on segment a→b to `p`, plus the parameter t and distance. */
export function projectOnSegment(p, a, b, aspect = 1) {
    const ax = a[0] * aspect, ay = a[1];
    const bx = b[0] * aspect, by = b[1];
    const px = p[0] * aspect, py = p[1];
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const t = len2 === 0 ? 0 : Math.min(1, Math.max(0, ((px - ax) * dx + (py - ay) * dy) / len2));
    const cx = ax + dx * t, cy = ay + dy * t;
    return { t, at: [cx / aspect, cy], dist: Math.hypot(px - cx, py - cy) };
}

/**
 * Which SEGMENT is under the pointer? Returns `{ index, at, t }` or null, where
 * `index` is the segment from `points[index]` to `points[index+1]`.
 *
 * This is what makes midpoint insertion feel like editing a line rather than
 * like using a menu: you click the line where you want the new vertex, and it
 * appears exactly there — snapped onto the segment, not at the raw pointer, so
 * inserting a point never nudges the shape.
 */
export function hitSegment(points, at, tol, aspect = 1) {
    let best = null;
    for (let i = 0; i < points.length - 1; i++) {
        const pr = projectOnSegment(at, points[i], points[i + 1], aspect);
        if (pr.dist <= tol && (!best || pr.dist < best.dist)) {
            best = { index: i, at: pr.at, t: pr.t, dist: pr.dist };
        }
    }
    return best;
}

const clamp01 = (v) => Math.min(1, Math.max(0, v));

/** Move one anchor. Returns NEW points; pressure (if any) is preserved. */
export function moveAnchor(points, index, at) {
    if (index < 0 || index >= points.length) return points;
    const next = points.slice();
    const old = points[index];
    next[index] = old.length > 2
        ? [clamp01(at[0]), clamp01(at[1]), old[2]]
        : [clamp01(at[0]), clamp01(at[1])];
    return next;
}

/**
 * Insert an anchor into segment `segIndex`. Pressure, when the neighbours carry
 * it, is interpolated at `t` rather than defaulted — otherwise inserting a
 * midpoint into a tapered stroke punches a visible pinch into the ribbon.
 */
export function insertAnchor(points, segIndex, at, t = 0.5) {
    if (segIndex < 0 || segIndex >= points.length - 1) return points;
    const a = points[segIndex], b = points[segIndex + 1];
    const p = (a.length > 2 && b.length > 2)
        ? [clamp01(at[0]), clamp01(at[1]), a[2] + (b[2] - a[2]) * t]
        : [clamp01(at[0]), clamp01(at[1])];
    const next = points.slice();
    next.splice(segIndex + 1, 0, p);
    return next;
}

/**
 * Remove an anchor — but never below two, because a polyline with one point is
 * not a shorter line, it is a mark that has silently stopped existing while
 * still occupying a row in the inspector. Refusing is the honest failure.
 */
export function removeAnchor(points, index) {
    if (points.length <= 2) return points;
    if (index < 0 || index >= points.length) return points;
    const next = points.slice();
    next.splice(index, 1);
    return next;
}

/** Translate the whole polyline (drag the body, not a vertex). */
export function translatePoints(points, dx, dy) {
    return points.map((p) => (p.length > 2
        ? [clamp01(p[0] + dx), clamp01(p[1] + dy), p[2]]
        : [clamp01(p[0] + dx), clamp01(p[1] + dy)]));
}

/** Axis-aligned bounds in normalized space: `{ x, y, w, h }`. */
export function pointsBBox(points) {
    if (!points?.length) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of points) {
        if (p[0] < x0) x0 = p[0];
        if (p[0] > x1) x1 = p[0];
        if (p[1] < y0) y0 = p[1];
        if (p[1] > y1) y1 = p[1];
    }
    return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/**
 * Scale a polyline about a fixed corner — the operation a bounding-box resize
 * handle performs, expressed as a POINT REWRITE.
 *
 * This function is the whole Transformer answer in three lines. A scene graph's
 * transformer multiplies a node's `scaleX/scaleY` and leaves the underlying
 * points alone; that is fine for a rectangle and wrong for us, because the next
 * thing Semant does with the mark is serialize it, and a serialized polyline
 * whose truth lives in an unserialized scale factor is a mark that renders
 * correctly and stores incorrectly. Rewriting the points means there is never a
 * transform to forget to bake.
 */
export function scalePoints(points, origin, sx, sy) {
    return points.map((p) => {
        const x = clamp01(origin[0] + (p[0] - origin[0]) * sx);
        const y = clamp01(origin[1] + (p[1] - origin[1]) * sy);
        return p.length > 2 ? [x, y, p[2]] : [x, y];
    });
}

/**
 * Read the editable points out of any contract geometry, and write them back.
 * The pair exists so the editor never branches on `geometry.kind`: a `vector` is
 * a two-point polyline for editing purposes, and pretending otherwise means
 * every operation above needs a second implementation.
 */
export function editablePoints(geometry) {
    if (!geometry) return null;
    if (geometry.kind === 'polyline' || geometry.kind === 'curve') return geometry.points || [];
    if (geometry.kind === 'vector') return [geometry.from, geometry.to];
    return null;
}

export function withEditedPoints(geometry, points) {
    if (geometry.kind === 'polyline' || geometry.kind === 'curve') return { ...geometry, points };
    if (geometry.kind === 'vector') return { ...geometry, from: points[0], to: points[points.length - 1] };
    return geometry;
}

/**
 * Keep a trace's `anchors` agreeing with its geometry after an edit.
 *
 * A `point` anchor's `at` IS the endpoint, so it must follow. A `ground`/
 * `region`/`percept` anchor's `at` is a cached position for a ref that owns the
 * real location, so dragging the endpoint away from it is a genuine question —
 * and this function answers it by DETACHING (ref preserved, `at` updated) rather
 * than by silently moving the referenced thing or silently keeping a stale `at`.
 * The detachment is visible in the serialized record, which is the point.
 */
export function syncAnchors(anchors, points) {
    const sync = (a, at) => {
        if (!a) return null;
        if (a.kind === 'point') return { ...a, at: [at[0], at[1]] };
        const moved = !a.at || Math.hypot(a.at[0] - at[0], a.at[1] - at[1]) > 1e-6;
        return moved ? { ...a, at: [at[0], at[1]], detached_from_ref: true } : a;
    };
    return {
        from: sync(anchors?.from, points[0]),
        to: sync(anchors?.to, points[points.length - 1]),
    };
}

/**
 * The whole edit, applied to a mark. Returns a NEW mark (never mutates), with
 * `updated_at` bumped and anchors re-synced.
 */
export function applyPointEdit(mark, points, { now = null } = {}) {
    return {
        ...mark,
        geometry: withEditedPoints(mark.geometry, points),
        ...(mark.anchors ? { anchors: syncAnchors(mark.anchors, points) } : null),
        updated_at: now || new Date().toISOString(),
    };
}
