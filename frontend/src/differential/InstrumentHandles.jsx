import React, { useRef } from 'react';

/**
 * InstrumentHandles — the editable-anchor overlay (CIRCUIT-001 P2E-B, 2c).
 *
 * Renders draggable vertex handles + midpoint-insert hints over the currently
 * edited geometry (a path/boundary Ground's points, or an in-progress draft).
 * It is a thin VIEW: all point arithmetic lives in `handleEditing.js`, and this
 * component only turns pointer gestures into calls back to the workspace, which
 * owns the geometry and the keep/cancel idiom.
 *
 * Coordinate contract: the overlay is an SVG whose viewBox is the natural-image
 * pixel box with `xMidYMid meet` — the SAME letterbox as the base image and
 * `GroundLayers`, so a handle at `[nx*natW, ny*natH]` lands exactly on the mark.
 * The svg itself is `pointerEvents:none`; only the handles receive the pointer,
 * so drawing/panning underneath is never blocked.
 *
 * `clientToNormalized(clientX, clientY)` is injected — the workspace already owns
 * the one sanctioned pointer→normalized converter (`useStageGeometry`), and this
 * module must not reimplement the letterbox math (the "earrings on a cheekbone"
 * rule).
 */
export default function InstrumentHandles({
    natural,
    points,
    clientToNormalized,
    onMove,               // (index, [nx, ny]) → void
    onInsert,             // (segIndex, [nx, ny], t) → void, returns the new index to grab
    onRemove,             // (index) → void
    locked = false,       // a locked layer shows handles greyed and inert
    handleScale = 0.011,  // of natural width
}) {
    const dragging = useRef(null);   // { index } while a handle is held

    if (!natural || !Array.isArray(points) || points.length < 1) return null;
    const r = Math.max(3, handleScale * natural.w);

    const endDrag = () => {
        dragging.current = null;
        window.removeEventListener('pointermove', onWindowMove);
        window.removeEventListener('pointerup', endDrag);
    };
    const onWindowMove = (ev) => {
        if (dragging.current == null) return;
        const p = clientToNormalized(ev.clientX, ev.clientY);
        if (p) onMove(dragging.current.index, [p.x, p.y]);
    };
    const beginDrag = (index, e) => {
        if (locked) return;
        e.stopPropagation();
        e.preventDefault();
        dragging.current = { index };
        window.addEventListener('pointermove', onWindowMove);
        window.addEventListener('pointerup', endDrag);
    };

    const midpoints = [];
    for (let i = 0; i < points.length - 1; i++) {
        const a = points[i], b = points[i + 1];
        midpoints.push({ segIndex: i, x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2 });
    }

    return (
        <svg
            className="ih-overlay"
            viewBox={`0 0 ${natural.w} ${natural.h}`}
            preserveAspectRatio="xMidYMid meet"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 6 }}
            aria-hidden="true"
        >
            {/* live preview of the reshaped centerline — so the new shape is legible
                while dragging, before Keep writes it back to the ground. */}
            {points.length > 1 && (
                <path
                    d={points.map((p, i) => `${i ? 'L' : 'M'}${(p[0] * natural.w).toFixed(2)},${(p[1] * natural.h).toFixed(2)}`).join(' ')}
                    className="ih-preview" fill="none" stroke="var(--accent, #C08457)"
                    strokeOpacity={0.9} strokeWidth={Math.max(1.5, 0.004 * natural.w)}
                    strokeLinecap="round" strokeLinejoin="round" strokeDasharray="4 4"
                    vectorEffect="non-scaling-stroke" />
            )}
            {/* midpoint-insert hints — click the line to add a vertex, then drag it */}
            {!locked && midpoints.map((m) => (
                <circle key={`mid-${m.segIndex}`} className="ih-mid"
                    cx={m.x * natural.w} cy={m.y * natural.h} r={r * 0.6}
                    style={{ pointerEvents: 'all', cursor: 'copy' }}
                    onPointerDown={(e) => {
                        if (locked) return;
                        e.stopPropagation(); e.preventDefault();
                        const p = clientToNormalized(e.clientX, e.clientY);
                        const at = p ? [p.x, p.y] : [m.x, m.y];
                        const newIndex = onInsert(m.segIndex, at, 0.5);
                        if (typeof newIndex === 'number') beginDrag(newIndex, e);
                    }} />
            ))}
            {/* vertex handles — drag to reshape, right-click to delete */}
            {points.map((p, i) => (
                <circle key={`h-${i}`} className={`ih-handle${locked ? ' is-locked' : ''}`}
                    cx={p[0] * natural.w} cy={p[1] * natural.h} r={r}
                    style={{ pointerEvents: locked ? 'none' : 'all', cursor: locked ? 'not-allowed' : 'grab' }}
                    onPointerDown={(e) => beginDrag(i, e)}
                    onContextMenu={(e) => { if (locked) return; e.preventDefault(); e.stopPropagation(); onRemove(i); }} />
            ))}
        </svg>
    );
}
