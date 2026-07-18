import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import RegionOverlay from './RegionOverlay';
import './RegionLightbox.css';

const MIN_SCALE = 1;
const MAX_SCALE = 8;
const MAPS = ['quiet', 'outline', 'focus'];

const regionName = (r) => r.label || r.part || r.category || 'part';

/**
 * Full-screen image with the regions overlaid (Darshan Track D · Phase 2).
 *
 * The dedicated "see the image properly" surface: the photo fills the viewport, and you
 * can zoom to a cuff or a hem and pan around it. The in-pane surface stays `contain`, so
 * nothing is ever cut there; detail lives here.
 *
 * **Why the annotations stay glued to the pixels.** The image and the SVG live in one
 * transformed box (`.rl-canvas`), sized to the image's aspect so it contains no
 * letterbox at all. Zoom and pan are a single CSS transform on that box, which moves
 * both children identically — the overlay cannot drift from the image, at any scale,
 * because nothing ever transforms one without the other.
 *
 * Zoom is anchored on the pointer, the way every map does it: the pixel under the cursor
 * stays under the cursor. Panning is clamped so the image can never be flung off-screen.
 */
export default function RegionLightbox({
    post, regions, natural, aletheia = null,
    viewMap: initialMap = 'outline', selectedId, onSelect, onClose,
}) {
    // Scale and offset are ONE state. Zooming about the pointer derives the new offset
    // from the old scale, so splitting them across two updaters would let React's
    // double-invoked updaters apply the pan twice.
    const [view, setView] = useState({ scale: 1, x: 0, y: 0 });
    const { scale } = view;
    const offset = { x: view.x, y: view.y };
    const [viewMap, setViewMap] = useState(initialMap);
    const [activeId, setActiveId] = useState(null);
    const [dragging, setDragging] = useState(false);

    const stageRef = useRef(null);
    const canvasRef = useRef(null);
    const dialogRef = useRef(null);
    const dragFrom = useRef(null);
    const restoreFocus = useRef(null);

    const focusId = activeId || selectedId;
    const selected = regions.find(r => r.id === selectedId);
    const lensFor = (aletheia?.lenses || []).find(l => (l.region_ids || []).includes(selectedId));

    // Where the image is actually painted inside the canvas (object-fit: contain). Layout
    // sizes, not transformed ones — this is the box zoom and pan reason about.
    const contentBox = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas || !natural) return null;
        const cw = canvas.offsetWidth, ch = canvas.offsetHeight;
        const s = Math.min(cw / natural.w, ch / natural.h);
        const w = natural.w * s, h = natural.h * s;
        return { w, h, x: (cw - w) / 2, y: (ch - h) / 2 };
    }, [natural]);

    // Kept in state for label placement. A transform doesn't change layout size, so the
    // observer only fires on real resizes, not on every zoom frame.
    const [box, setBox] = useState(null);
    useEffect(() => {
        const update = () => setBox(contentBox());
        update();
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ro = new ResizeObserver(update);
        ro.observe(canvas);
        return () => ro.disconnect();
    }, [contentBox]);

    // Panning must not be able to lose the image. Bound against the PAINTED image, not
    // the canvas: an image narrower than the stage should not pan sideways at all until
    // it is zoomed past the stage's width.
    const clamp = useCallback((x, y, s) => {
        const box = contentBox();
        if (!box) return { x, y };
        const canvas = canvasRef.current;
        const maxX = Math.max(0, (box.w * s - canvas.offsetWidth) / 2);
        const maxY = Math.max(0, (box.h * s - canvas.offsetHeight) / 2);
        return {
            x: Math.min(maxX, Math.max(-maxX, x)),
            y: Math.min(maxY, Math.max(-maxY, y)),
        };
    }, [contentBox]);

    const zoomTo = useCallback((nextScale, anchor) => {
        setView(v => {
            const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, nextScale));
            if (s === v.scale) return v;
            const canvas = canvasRef.current;
            if (!anchor || !canvas) {
                const c = clamp(v.x, v.y, s);
                return { scale: s, ...c };
            }
            // Keep the pixel under the cursor under the cursor: the canvas centre is the
            // transform origin, so a point `d` from it moves to `d * s/prev`.
            const rect = canvas.getBoundingClientRect();
            const dx = anchor.x - (rect.left + rect.width / 2);
            const dy = anchor.y - (rect.top + rect.height / 2);
            const k = s / v.scale;
            const c = clamp(v.x - dx * (k - 1), v.y - dy * (k - 1), s);
            return { scale: s, ...c };
        });
    }, [clamp]);

    const reset = () => setView({ scale: 1, x: 0, y: 0 });

    // --- wheel zoom (non-passive, so preventDefault actually holds) ------------------
    useEffect(() => {
        const stage = stageRef.current;
        if (!stage) return;
        const onWheel = (e) => {
            e.preventDefault();
            const factor = Math.exp(-e.deltaY * 0.0015);
            zoomTo(scale * factor, { x: e.clientX, y: e.clientY });
        };
        stage.addEventListener('wheel', onWheel, { passive: false });
        return () => stage.removeEventListener('wheel', onWheel);
    }, [scale, zoomTo]);

    // --- keyboard + focus management --------------------------------------------------
    useEffect(() => {
        restoreFocus.current = document.activeElement;
        dialogRef.current?.focus();
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';   // the page behind must not scroll

        const onKey = (e) => {
            if (e.key === 'Escape') { e.preventDefault(); onClose(); }
            else if (e.key === '+' || e.key === '=') zoomTo(scale * 1.4, null);
            else if (e.key === '-' || e.key === '_') zoomTo(scale / 1.4, null);
            else if (e.key === '0') reset();
            else if (e.key === 'm') setViewMap(m => MAPS[(MAPS.indexOf(m) + 1) % MAPS.length]);
        };
        window.addEventListener('keydown', onKey);
        return () => {
            window.removeEventListener('keydown', onKey);
            document.body.style.overflow = prevOverflow;
            // Return the user to where they were, not to the top of the document.
            if (restoreFocus.current instanceof HTMLElement) restoreFocus.current.focus();
        };
    }, [onClose, scale, zoomTo]);

    // --- drag to pan -------------------------------------------------------------------
    const onPointerDown = (e) => {
        if (scale <= 1) return;                 // nothing to pan at fit-scale
        setDragging(true);
        dragFrom.current = { x: e.clientX - offset.x, y: e.clientY - offset.y };
        // Pointer capture is a nicety (drag can leave the stage); a synthetic pointer has
        // nothing to capture, and it must never take the drag down with it.
        try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* no live pointer */ }
    };
    const onPointerMove = (e) => {
        // Gate on the ref, not the `dragging` state: a pointermove can arrive in the same
        // tick as its pointerdown, before React has committed the state, and the drag
        // would be dropped. `dragging` exists only to pick the cursor.
        if (!dragFrom.current) return;
        setView(v => ({
            scale: v.scale,
            ...clamp(e.clientX - dragFrom.current.x, e.clientY - dragFrom.current.y, v.scale),
        }));
    };
    const onPointerUp = (e) => {
        setDragging(false); dragFrom.current = null;
        try { e.currentTarget.releasePointerCapture?.(e.pointerId); } catch { /* never captured */ }
    };

    // Portal to <body>. `.rl` is `position: fixed; inset: 0`, but it mounts inside
    // `.rs-root`, which sets `container-type: inline-size` — that applies `layout`
    // containment, which makes `.rs-root` the containing block for fixed-positioned
    // descendants. Left inline, `inset: 0` resolves against the Field pane (offset from
    // and often taller than the viewport), so the "full-screen" stage is not the screen:
    // a portrait image contains into an over-tall stage and only its middle slice sits in
    // view, with body-scroll locked and pan gated off at fit — the reported crop. Escaping
    // to <body> removes every containment ancestor, so fixed means the viewport again.
    return createPortal(
        <div className="rl" role="dialog" aria-modal="true" aria-label="Full-screen image with regions"
            ref={dialogRef} tabIndex={-1}
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>

            <header className="rl-bar">
                <div className="rl-maps" role="radiogroup" aria-label="Region view">
                    {MAPS.map(m => (
                        <button key={m} role="radio" aria-checked={viewMap === m}
                            className={`rl-chip${viewMap === m ? ' on' : ''}`}
                            onClick={() => setViewMap(m)}>{m}</button>
                    ))}
                </div>
                <div className="rl-zoom">
                    <button className="rl-icon" aria-label="Zoom out" onClick={() => zoomTo(scale / 1.4, null)}
                        disabled={scale <= MIN_SCALE}><ZoomOut size={15} /></button>
                    <span className="rl-scale" aria-live="polite">{Math.round(scale * 100)}%</span>
                    <button className="rl-icon" aria-label="Zoom in" onClick={() => zoomTo(scale * 1.4, null)}
                        disabled={scale >= MAX_SCALE}><ZoomIn size={15} /></button>
                    <button className="rl-icon" aria-label="Reset zoom" onClick={reset} disabled={scale === 1}>
                        <Maximize2 size={14} />
                    </button>
                </div>
                <button className="rl-icon rl-close" aria-label="Close full screen (Esc)" onClick={onClose}>
                    <X size={17} />
                </button>
            </header>

            <div
                className={`rl-stage${scale > 1 ? ' is-pannable' : ''}${dragging ? ' is-dragging' : ''}`}
                ref={stageRef}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                onDoubleClick={(e) => (scale > 1 ? reset() : zoomTo(2.5, { x: e.clientX, y: e.clientY }))}
            >
                {/* One transformed box holds the image AND the overlay. They cannot drift
                    apart, because nothing ever moves one without the other. */}
                <div
                    className="rl-canvas"
                    ref={canvasRef}
                    style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }}
                >
                    <img src={post.photo_url} alt="" referrerPolicy="no-referrer" draggable={false} />
                    <RegionOverlay
                        className="rl-svg"
                        natural={natural}
                        regions={regions}
                        viewMap={viewMap}
                        selectedId={selectedId}
                        activeId={activeId}
                        focusId={focusId}
                        onSelect={onSelect}
                        onActivate={setActiveId}
                    />
                    {/* Labels ride inside the same transformed box, so they move with the
                        image — but they're placed on the PAINTED image, not the canvas,
                        which is wider when the photo letterboxes. Only the part you're
                        looking at is named; 40 labels are noise. Counter-scaled so the
                        text stays legible as you zoom in. */}
                    {focusId && box && regions.filter(r => r.id === focusId).map(r => (
                        <span key={r.id} className="rl-label"
                            style={{
                                left: box.x + r.box.x * box.w,
                                top: box.y + r.box.y * box.h,
                                transform: `translate(0, -115%) scale(${1 / scale})`,
                                transformOrigin: 'left bottom',
                            }}>
                            {regionName(r)}
                        </span>
                    ))}
                </div>
            </div>

            <footer className="rl-foot">
                {selected ? (
                    <div className="rl-caption">
                        <strong>{regionName(selected)}</strong>
                        {lensFor && <span className="rl-lens"><em>{lensFor.name}</em> — {lensFor.reading}</span>}
                        {(selected.user_note || '').trim() && <span className="rl-note">“{selected.user_note}”</span>}
                    </div>
                ) : (
                    <p className="rl-hint">
                        Scroll or double-click to zoom · drag to pan · <kbd>m</kbd> cycles the map · <kbd>Esc</kbd> closes
                    </p>
                )}
            </footer>
        </div>,
        document.body,
    );
}
