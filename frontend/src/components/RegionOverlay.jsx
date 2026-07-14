import React from 'react';

/**
 * The region overlay (Darshan Track D) — the one place shapes are drawn.
 *
 * Shared by the in-pane surface and the full-screen lightbox, so "how a region looks"
 * is decided once. The alignment contract lives here:
 *
 *   the viewBox is the image's NATURAL pixel space, and `xMidYMid meet` letterboxes the
 *   overlay exactly as `object-fit: contain` letterboxes the image.
 *
 * Because both letterbox identically inside the same box, the overlay tracks the image
 * at any stage size, any aspect, and — since a CSS transform on the shared parent moves
 * both together — at any zoom. `preserveAspectRatio="none"` would stretch the viewBox to
 * the stage instead, which drifts by ~129px on a contain-fitted stage.
 */

const shapeClassFor = (r, { viewMap, selectedId, activeId, focusId }) => {
    const cls = ['rs-shape', `rs-shape--${viewMap}`];
    if (r.actor === 'creator') cls.push('rs-shape--creator');
    if (r.prioritised) cls.push('is-pri');
    if (selectedId === r.id) cls.push('is-sel');
    if (activeId === r.id) cls.push('is-active');
    if (viewMap === 'focus' && focusId && focusId !== r.id) cls.push('is-dim');
    if (viewMap !== 'focus' && focusId === r.id) cls.push('is-lit');
    return cls.join(' ');
};

export default function RegionOverlay({
    natural, regions, viewMap, selectedId, activeId, focusId,
    onSelect, onActivate, draft = null, className = 'rs-svg',
}) {
    if (!natural) return null;

    return (
        <svg
            className={className}
            viewBox={`0 0 ${natural.w} ${natural.h}`}
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
        >
            {regions.map(r => {
                const common = {
                    className: shapeClassFor(r, { viewMap, selectedId, activeId, focusId }),
                    vectorEffect: 'non-scaling-stroke',
                    onClick: (e) => { e.stopPropagation(); onSelect?.(r.id); },
                    onMouseEnter: () => onActivate?.(r.id),
                    onMouseLeave: () => onActivate?.(null),
                };
                // Polygons by default — the true segment outline. A rect only where the
                // detector gave us no polygon (a creator's freehand mark, or legacy data).
                if (Array.isArray(r.polygon) && r.polygon.length > 2) {
                    const pts = r.polygon
                        .map(([x, y]) => `${x * natural.w},${y * natural.h}`).join(' ');
                    return <polygon key={r.id} {...common} points={pts} />;
                }
                const b = r.box || {};
                return <rect key={r.id} {...common}
                    x={b.x * natural.w} y={b.y * natural.h}
                    width={b.w * natural.w} height={b.h * natural.h} />;
            })}
            {draft && (
                <rect className="rs-draft" vectorEffect="non-scaling-stroke"
                    x={Math.min(draft.x0, draft.x1) * natural.w}
                    y={Math.min(draft.y0, draft.y1) * natural.h}
                    width={Math.abs(draft.x1 - draft.x0) * natural.w}
                    height={Math.abs(draft.y1 - draft.y0) * natural.h} />
            )}
        </svg>
    );
}
