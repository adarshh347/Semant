/**
 * The image viewport — pure pan/zoom mathematics for the navigable workbench.
 *
 * THE ONE RULE THIS MODULE EXISTS TO ENFORCE: **the view is not the evidence.**
 *
 * A viewport transform changes ACCESS to pixels. It makes no claim. Brush radius
 * changes the spatial extent of authored evidence; brush intensity changes the
 * register within a field; pointer pressure is gestural input; layer opacity is
 * display. Zoom is an epistemic aid without being epistemic data — it permits more
 * exact attention and asserts nothing — so a mark drawn at 4× must persist the
 * same normalized coordinates it would have persisted at fit scale.
 *
 * The arithmetic is extracted from `components/RegionLightbox.jsx`, which proved it
 * on a read-only surface (pointer-anchored wheel zoom, pan clamped against the
 * PAINTED image rather than the container). Differential adds canvas fields,
 * editable handles, drafts, refine prompts, suggestions, recall and mutually
 * exclusive draw/pan gestures, so it needs the primitive rather than the component.
 * Extracted, not copied: two implementations of this arithmetic is exactly how an
 * overlay drifts from its pixels.
 *
 * ── the geometry ────────────────────────────────────────────────────────────
 *
 * Two nested boxes. The VIEWPORT is a fixed, clipped screen area that owns pointer
 * and wheel events. The PLANE fills it exactly (`inset: 0`) and carries ONE
 * transform, `translate(x, y) scale(s)` about its centre. Every spatial layer —
 * image, region SVG, ground canvas, ghosts, handles, cursors — is a child of that
 * one plane. Nothing computes a second transform for itself.
 *
 * Because a CSS transform does not change layout size, the plane's layout box
 * always equals the viewport's, so the letterboxed `content` box measured by
 * `useStageGeometry` is UNCHANGED by zoom. That is what makes this safe to bolt
 * onto the existing contract: at scale 1 with no pan, every layer lands exactly
 * where it landed before this module existed.
 *
 *   client point
 *     → viewport-local  (minus the viewport's client rect origin)
 *     → inverse translate
 *     → inverse scale about the centre
 *     → plane point   (=== the old, untransformed stage point)
 *     → normalized image point   (the existing letterbox math, untouched)
 */

export const MIN_SCALE = 1;
export const MAX_SCALE = 8;

/** One press of + or −. */
export const ZOOM_STEP = 1.4;

/** The whole composition, centred: the default, and what "Fit" returns to. */
export const FIT_VIEW = Object.freeze({ scale: 1, x: 0, y: 0, mode: 'fit' });

export const clampScale = (s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

/** At scale 1 with no pan the curator is looking at the whole image. */
export const isFit = (view) => !!view && view.scale === 1 && view.x === 0 && view.y === 0;

const withMode = (v) => ({ ...v, mode: isFit(v) ? 'fit' : 'free' });

/**
 * Bound the pan so the image can never be flung off-screen.
 *
 * Bounded against the PAINTED image, not the viewport: an image narrower than its
 * viewport (a portrait plate in a wide column) must not pan sideways at all until
 * it is zoomed past the viewport's width. Bounding against the container would let
 * a curator drag a portrait image into its own letterbox and lose it.
 */
export function panLimits(scale, viewport, content) {
    if (!viewport || !content) return null;
    return {
        x: Math.max(0, (content.w * scale - viewport.w) / 2),
        y: Math.max(0, (content.h * scale - viewport.h) / 2),
    };
}

export function clampPan(x, y, scale, viewport, content) {
    const lim = panLimits(scale, viewport, content);
    if (!lim) return { x, y };
    // `+ 0` normalises the -0 that Math.max(-0, …) yields, so a fit view compares
    // equal to FIT_VIEW instead of being a distinct-but-identical object.
    return {
        x: Math.min(lim.x, Math.max(-lim.x, x)) + 0,
        y: Math.min(lim.y, Math.max(-lim.y, y)) + 0,
    };
}

/** Is the pan pressed against its limit on this axis? (Within a sub-pixel epsilon.) */
export function isPanClamped(view, axis, viewport, content) {
    const lim = panLimits(view.scale, viewport, content);
    if (!lim) return false;
    return Math.abs(Math.abs(view[axis]) - lim[axis]) < 1e-6;
}

/**
 * Zoom to `nextScale`, keeping `anchor` (a VIEWPORT-LOCAL point) over the same
 * pixel of the image. Pass `anchor: null` to zoom about the centre.
 *
 * The derivation, because getting it slightly wrong is silent and cumulative.
 * Forward, about the centre `c`, with pan `t`:  `q = c + (p - c) * s + t`.
 * Hold `q` fixed while `s → s' = k·s` and solve for the new pan:
 *
 *     t' = d(1 - k) + t·k        where d = q - c
 *
 * The `t·k` term is load-bearing and easy to lose: `t' = d(1 - k) + t` agrees for a
 * single zoom from an unpanned view (`t = 0`) and drifts on every one after, so a
 * wheel gesture — which is a CHAIN of small zooms, each starting from the pan the
 * last one left — walks the image out from under the cursor a little per notch.
 * `components/RegionLightbox.jsx` carries that shorter form; this is the corrected
 * one, and `holds across a chain of zooms` is the test that tells them apart.
 *
 * WHERE THE TWO REQUIREMENTS COLLIDE, THE CLAMP WINS — and it is worth being exact
 * about this rather than claiming an invariant that does not hold. "Keep the pixel
 * under the cursor" and "pan can never lose the image" are not jointly satisfiable
 * near an edge: honouring the anchor there would require showing pixels the image
 * does not have. So the anchor is preserved on each axis EXCEPT where the pan
 * limit binds, and on that axis the image edge is held instead. Anchoring is a
 * convenience; a viewport showing empty space beside a floating image is a broken
 * surface. `isPanClamped` reports exactly when this substitution happened, so the
 * behaviour is testable rather than a surprise.
 */
export function zoomAbout(view, nextScale, anchor, viewport, content) {
    const s = clampScale(nextScale);
    if (s === view.scale) return view;
    if (!anchor || !viewport) {
        return withMode({ scale: s, ...clampPan(view.x, view.y, s, viewport, content) });
    }
    const dx = anchor.x - viewport.w / 2;
    const dy = anchor.y - viewport.h / 2;
    const k = s / view.scale;
    return withMode({
        scale: s,
        ...clampPan(
            dx * (1 - k) + view.x * k,
            dy * (1 - k) + view.y * k,
            s, viewport, content,
        ),
    });
}

/** Pan by a screen-pixel delta, clamped. */
export function panBy(view, dx, dy, viewport, content) {
    return withMode({
        scale: view.scale,
        ...clampPan(view.x + dx, view.y + dy, view.scale, viewport, content),
    });
}

/** Pan to an absolute offset, clamped. */
export function panTo(view, x, y, viewport, content) {
    return withMode({ scale: view.scale, ...clampPan(x, y, view.scale, viewport, content) });
}

// ── the two directions, and nothing else may implement them ─────────────────

/** Viewport-local point → plane point (the untransformed stage point). */
export function viewportToPlane(q, view, viewport) {
    if (!q || !viewport) return null;
    const cx = viewport.w / 2;
    const cy = viewport.h / 2;
    return {
        x: cx + (q.x - cx - view.x) / view.scale,
        y: cy + (q.y - cy - view.y) / view.scale,
    };
}

/** Plane point → viewport-local point. The exact inverse of the above. */
export function planeToViewport(p, view, viewport) {
    if (!p || !viewport) return null;
    const cx = viewport.w / 2;
    const cy = viewport.h / 2;
    return {
        x: cx + (p.x - cx) * view.scale + view.x,
        y: cy + (p.y - cy) * view.scale + view.y,
    };
}

/** Plane point → normalized image coords. The existing letterbox math. */
export function planeToNormalized(p, content, { clamp = true } = {}) {
    if (!p || !content) return null;
    const x = (p.x - content.x) / content.w;
    const y = (p.y - content.y) / content.h;
    if (!clamp) return { x, y };
    return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
}

/** Normalized image coords → plane point. */
export function normalizedToPlane(pt, content) {
    if (!pt || !content) return null;
    return { x: content.x + pt.x * content.w, y: content.y + pt.y * content.h };
}

/**
 * THE SANCTIONED POINTER PATH. A client point (from any pointer/wheel event) to
 * normalized image coords, through the viewport transform.
 *
 * `rect` is the viewport's own `getBoundingClientRect()`. At `FIT_VIEW` this is
 * arithmetically identical to the pre-zoom `pointerToNormalized`, which is what
 * lets it replace that call unconditionally.
 */
export function clientToNormalized(clientX, clientY, rect, view, content, { clamp = true } = {}) {
    if (!rect || !content) return null;
    const viewport = { w: rect.width, h: rect.height };
    const q = { x: clientX - rect.left, y: clientY - rect.top };
    return planeToNormalized(viewportToPlane(q, view, viewport), content, { clamp });
}

/** Normalized image coords → client point. For hit-testing and cursor placement. */
export function normalizedToClient(pt, rect, view, content) {
    if (!pt || !rect || !content) return null;
    const viewport = { w: rect.width, h: rect.height };
    const q = planeToViewport(normalizedToPlane(pt, content), view, viewport);
    return { x: q.x + rect.left, y: q.y + rect.top };
}

// ── named destinations ──────────────────────────────────────────────────────

/**
 * The scale at which one natural image pixel occupies one CSS pixel ("100%").
 * Returns null when that is not a meaningful destination — an image smaller than
 * its viewport is ALREADY past 1:1 at fit, and offering "100%" as a zoom-OUT
 * would be a lie about what the button does.
 */
export function naturalScale(content, natural) {
    if (!content?.w || !natural?.w) return null;
    const s = natural.w / content.w;
    if (s <= 1 || s > MAX_SCALE) return null;
    return s;
}

/**
 * A view that brings `bounds` (normalized, {x,y,w,h}) to fill the viewport.
 * Used by "zoom to selection" and, later, recall-directed framing.
 */
export function viewForBounds(bounds, viewport, content, { padding = 0.12 } = {}) {
    if (!bounds || !viewport || !content || bounds.w <= 0 || bounds.h <= 0) return FIT_VIEW;
    const planeW = bounds.w * content.w;
    const planeH = bounds.h * content.h;
    const s = clampScale(Math.min(
        (viewport.w * (1 - padding)) / planeW,
        (viewport.h * (1 - padding)) / planeH,
    ));
    const centre = normalizedToPlane(
        { x: bounds.x + bounds.w / 2, y: bounds.y + bounds.h / 2 }, content,
    );
    // Put that plane point at the viewport centre: t = -(p - c) * s.
    const x = -(centre.x - viewport.w / 2) * s;
    const y = -(centre.y - viewport.h / 2) * s;
    return withMode({ scale: s, ...clampPan(x, y, s, viewport, content) });
}

/** The normalized rectangle currently visible — for a navigator/minimap. */
export function visibleBounds(view, viewport, content) {
    if (!viewport || !content) return null;
    const tl = planeToNormalized(viewportToPlane({ x: 0, y: 0 }, view, viewport), content, { clamp: false });
    const br = planeToNormalized(
        viewportToPlane({ x: viewport.w, y: viewport.h }, view, viewport), content, { clamp: false },
    );
    const x0 = Math.max(0, tl.x), y0 = Math.max(0, tl.y);
    const x1 = Math.min(1, br.x), y1 = Math.min(1, br.y);
    return { x: x0, y: y0, w: Math.max(0, x1 - x0), h: Math.max(0, y1 - y0) };
}

/** The CSS transform for the plane. One string, one place. */
export const planeTransform = (view) =>
    `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;

/** How the zoom reads to a person: "Fit", or a rounded percentage. */
export const zoomLabel = (view) => (isFit(view) ? 'Fit' : `${Math.round(view.scale * 100)}%`);
