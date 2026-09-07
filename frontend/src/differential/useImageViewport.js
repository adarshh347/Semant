import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    FIT_VIEW, MIN_SCALE, MAX_SCALE, ZOOM_STEP,
    zoomAbout, panBy as panByPure, clientToNormalized as clientToNormalizedPure,
    naturalScale, viewForBounds, visibleBounds, planeTransform, zoomLabel, isFit,
} from './imageViewport';

/**
 * The viewport a curator looks through — transient session state, never evidence.
 *
 * Owns `{ scale, x, y, mode }` for one image workbench and arbitrates NAVIGATION
 * gestures against AUTHORING gestures. The arithmetic all lives in
 * `imageViewport.js`; this hook is the React edge — state, listeners, and the one
 * decision that matters:
 *
 *   **a navigation gesture must never append a brush point, and an authoring
 *   gesture must never move the plane.**
 *
 * The grammar (desktop):
 *   - primary drag                  → the active tool performs
 *   - Space held + primary drag     → pan, tool stays armed
 *   - middle-button drag            → pan
 *   - H                             → latch/unlatch a Hand tool (discoverability,
 *                                     and the path for anyone without a middle
 *                                     button or a trackpad)
 *   - Ctrl/Cmd + wheel, or pinch    → zoom about the pointer
 *   - plain wheel                   → the PAGE scrolls, untouched
 *
 * Requiring a modifier for wheel-zoom inline is deliberate: the stage sits in a
 * scrolling column, and a surface that swallows the wheel traps the reader on it.
 * Browsers report a trackpad pinch as `wheel` with `ctrlKey`, so pinch works
 * without a second code path.
 *
 * Releasing Space returns to the previous tool IMMEDIATELY — the pan is a
 * modifier, not a mode switch, so no tool state is ever mutated by navigating.
 */
export default function useImageViewport(stageRef, { content, enabled = true } = {}) {
    const [view, setView] = useState(FIT_VIEW);
    const [viewport, setViewport] = useState(null);
    const [spaceHeld, setSpaceHeld] = useState(false);
    const [handTool, setHandTool] = useState(false);
    const [panning, setPanning] = useState(false);

    // The live view, for listeners that must not re-subscribe on every frame.
    const viewRef = useRef(view);
    viewRef.current = view;
    const geomRef = useRef({ viewport, content });
    geomRef.current = { viewport, content };

    const panFrom = useRef(null);
    const rafRef = useRef(0);
    const pendingPan = useRef(null);

    // ── measure the viewport (layout size; a transform never changes it) ────
    useEffect(() => {
        const el = stageRef.current;
        if (!el) return undefined;
        const measure = () => {
            const r = el.getBoundingClientRect();
            setViewport((v) => (v && v.w === r.width && v.h === r.height ? v : { w: r.width, h: r.height }));
        };
        measure();
        const ro = new ResizeObserver(measure);
        ro.observe(el);
        return () => ro.disconnect();
    }, [stageRef]);

    // A resize can strand a pan outside its new limits — re-clamp rather than
    // leaving the image floating against an edge that moved.
    useEffect(() => {
        if (!viewport || !content) return;
        setView((v) => (isFit(v) ? v : panByPure(v, 0, 0, viewport, content)));
    }, [viewport, content]);

    // ── the named destinations ──────────────────────────────────────────────
    const zoomTo = useCallback((next, anchor = null) => {
        const { viewport: vp, content: c } = geomRef.current;
        setView((v) => zoomAbout(v, next, anchor, vp, c));
    }, []);

    const zoomIn = useCallback(() => zoomTo(viewRef.current.scale * ZOOM_STEP), [zoomTo]);
    const zoomOut = useCallback(() => zoomTo(viewRef.current.scale / ZOOM_STEP), [zoomTo]);
    const fit = useCallback(() => setView(FIT_VIEW), []);

    const natural1to1 = useMemo(
        () => (n) => naturalScale(content, n), [content],
    );

    const zoomToBounds = useCallback((bounds) => {
        const { viewport: vp, content: c } = geomRef.current;
        if (!vp || !c) return;
        setView(viewForBounds(bounds, vp, c));
    }, []);

    /** THE sanctioned pointer path for every instrument on this stage. */
    const clientToNormalized = useCallback((clientX, clientY, opts) => {
        const el = stageRef.current;
        if (!el) return null;
        return clientToNormalizedPure(
            clientX, clientY, el.getBoundingClientRect(),
            viewRef.current, geomRef.current.content, opts,
        );
    }, [stageRef]);

    // ── gesture arbitration ─────────────────────────────────────────────────
    /** True when this pointer-down is a NAVIGATION gesture, not an authoring one. */
    const isPanRequest = useCallback(
        (e) => enabled && (e.button === 1 || spaceHeld || handTool),
        [enabled, spaceHeld, handTool],
    );

    /**
     * Call FIRST from the stage's pointerdown. Returns true when it claimed the
     * gesture, in which case the caller must return without touching any tool.
     */
    const beginPan = useCallback((e) => {
        if (!isPanRequest(e)) return false;
        e.preventDefault();
        e.currentTarget?.setPointerCapture?.(e.pointerId);
        panFrom.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
        setPanning(true);
        return true;
    }, [isPanRequest]);

    // Apply whatever the pointer last reported. Separated from the frame callback
    // so `endPan` can FLUSH rather than discard — see below.
    const applyPendingPan = useCallback(() => {
        const from = panFrom.current;
        const to = pendingPan.current;
        if (!from || !to) return;
        if (to.x === from.x && to.y === from.y) return;
        const { viewport: vp, content: c } = geomRef.current;
        setView((v) => panByPure(v, to.x - from.x, to.y - from.y, vp, c));
        panFrom.current = { ...from, x: to.x, y: to.y };
    }, []);

    /**
     * Call FIRST from pointermove. Returns true when a pan consumed it.
     * Coalesced onto an animation frame: a heavy post must not re-render React on
     * every raw pointer sample just to move a CSS transform.
     */
    const movePan = useCallback((e) => {
        if (!panFrom.current) return false;
        pendingPan.current = { x: e.clientX, y: e.clientY };
        if (!rafRef.current) {
            rafRef.current = requestAnimationFrame(() => {
                rafRef.current = 0;
                applyPendingPan();
            });
        }
        return true;
    }, [applyPendingPan]);

    /**
     * Call FIRST from pointerup / pointercancel / pointerleave.
     *
     * FLUSHES the pending frame instead of cancelling it. Cancelling would throw
     * away every move since the last frame — on a fast flick, or in a tab whose
     * rAF is throttled, that is the end of the gesture, so the plane would settle
     * a little behind where the hand left it. Coalescing is a performance device;
     * it must not lose the last thing the curator did.
     */
    const endPan = useCallback(() => {
        if (!panFrom.current) return false;
        if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = 0; }
        applyPendingPan();
        panFrom.current = null;
        pendingPan.current = null;
        setPanning(false);
        return true;
    }, [applyPendingPan]);

    // A pan must not survive the pointer being lost — losing capture, a context
    // menu, or the tab going away would otherwise leave the plane stuck to the
    // cursor with no button held.
    useEffect(() => {
        const stop = () => endPan();
        window.addEventListener('pointercancel', stop);
        window.addEventListener('blur', stop);
        return () => {
            window.removeEventListener('pointercancel', stop);
            window.removeEventListener('blur', stop);
        };
    }, [endPan]);

    useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

    // ── wheel ───────────────────────────────────────────────────────────────
    useEffect(() => {
        const el = stageRef.current;
        if (!el || !enabled) return undefined;
        const onWheel = (e) => {
            // Plain wheel belongs to the page. Ctrl/Cmd is the intent to zoom, and
            // is also what a trackpad pinch reports.
            if (!e.ctrlKey && !e.metaKey) return;
            e.preventDefault();
            const r = el.getBoundingClientRect();
            const factor = Math.exp(-e.deltaY * 0.002);
            const { viewport: vp, content: c } = geomRef.current;
            setView((v) => zoomAbout(
                v, v.scale * factor,
                { x: e.clientX - r.left, y: e.clientY - r.top }, vp, c,
            ));
        };
        el.addEventListener('wheel', onWheel, { passive: false });
        return () => el.removeEventListener('wheel', onWheel);
    }, [stageRef, enabled]);

    // ── Space / H ───────────────────────────────────────────────────────────
    useEffect(() => {
        if (!enabled) return undefined;
        const inText = (t) => !!t?.closest?.('input, textarea, [contenteditable="true"]');
        const down = (e) => {
            if (inText(e.target)) return;
            if (e.code === 'Space' || e.key === ' ') {
                // Space would otherwise scroll the page under the stage.
                e.preventDefault();
                setSpaceHeld(true);
            } else if (e.key === 'h' || e.key === 'H') {
                setHandTool((h) => !h);
            }
        };
        const up = (e) => {
            if (e.code === 'Space' || e.key === ' ') {
                setSpaceHeld(false);
                endPan();   // releasing mid-drag returns the tool at once
            }
        };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => {
            window.removeEventListener('keydown', down);
            window.removeEventListener('keyup', up);
        };
    }, [enabled, endPan]);

    const navigating = spaceHeld || handTool || panning;

    return {
        view,
        viewport,
        transform: planeTransform(view),
        label: zoomLabel(view),
        atFit: isFit(view),
        canZoomIn: view.scale < MAX_SCALE,
        canZoomOut: view.scale > MIN_SCALE,
        visible: visibleBounds(view, viewport, content),
        // destinations
        zoomTo, zoomIn, zoomOut, fit, zoomToBounds, naturalScale: natural1to1,
        // conversion
        clientToNormalized,
        // gesture arbitration — call each FIRST in the stage's handler
        beginPan, movePan, endPan, isPanRequest,
        navigating, panning, spaceHeld, handTool, setHandTool,
    };
}
