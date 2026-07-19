import React from 'react';
import { hasMaskPolygons, ringsToPath } from '../lib/maskGeometry';

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

const shapeClassFor = (r, { viewMap, selectedId, activeId, focusId, litIds }) => {
    const cls = ['rs-shape', `rs-shape--${viewMap}`];
    if (r.actor === 'creator') cls.push('rs-shape--creator');
    if (r.prioritised) cls.push('is-pri');
    if (selectedId === r.id) cls.push('is-sel');
    if (activeId === r.id) cls.push('is-active');
    // A multi-select set (Differential region-pick) lights several at once and
    // dims the rest; otherwise the single focusId drives the narrowing.
    if (litIds) {
        if (litIds.has(r.id)) cls.push('is-lit'); else cls.push('is-dim');
    } else {
        // Attention narrows: when a region is focused (row/chip hover, selection),
        // the unrelated ones recede in every map — not only in the 'focus' map.
        if (focusId && focusId !== r.id) cls.push('is-dim');
        if (focusId === r.id) cls.push('is-lit');
    }
    return cls.join(' ');
};

export default function RegionOverlay({
    natural, regions, viewMap, selectedId, activeId, focusId, litIds = null,
    onSelect, onActivate, draft = null, className = 'rs-svg',
    // VISION-B5: an exact-mask refine proposal + its point/box prompt, rendered through
    // this same registered overlay. `interactive={false}` lets refine gestures fall
    // through to the stage instead of being caught by the region shapes.
    proposal = null, prompt = null, interactive = true,
}) {
    if (!natural) return null;

    const mk = Math.max(4, natural.w * 0.011);

    return (
        <svg
            className={className}
            viewBox={`0 0 ${natural.w} ${natural.h}`}
            preserveAspectRatio="xMidYMid meet"
            aria-hidden="true"
            style={interactive ? undefined : { pointerEvents: 'none' }}
        >
            {regions.map(r => {
                const common = {
                    className: shapeClassFor(r, { viewMap, selectedId, activeId, focusId, litIds }),
                    vectorEffect: 'non-scaling-stroke',
                    // The event rides along so a caller can read shiftKey for multi-select.
                    onClick: (e) => { e.stopPropagation(); onSelect?.(r.id, e); },
                    onMouseEnter: () => onActivate?.(r.id),
                    onMouseLeave: () => onActivate?.(null),
                };
                // Canonical mask (multi-ring: outer + holes, all components) → one
                // evenodd <path>. This is the exact segment identity when present.
                if (hasMaskPolygons(r)) {
                    return <path key={r.id} {...common} fillRule="evenodd"
                        d={ringsToPath(r.polygons, natural.w, natural.h)} />;
                }
                // Legacy single-ring polygon — the true segment outline for older data.
                // A rect only where there is no polygon (freehand draft, or box-only data).
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
            {/* refine proposal (an exact mask preview) — dashed, registered here */}
            {proposal && hasMaskPolygons(proposal) && (
                <path className="rs-proposal" fillRule="evenodd" vectorEffect="non-scaling-stroke"
                    d={ringsToPath(proposal.polygons, natural.w, natural.h)} />
            )}
            {prompt && prompt.box && (
                <rect className="rs-boxprompt" vectorEffect="non-scaling-stroke"
                    x={Math.min(prompt.box.x0, prompt.box.x1) * natural.w}
                    y={Math.min(prompt.box.y0, prompt.box.y1) * natural.h}
                    width={Math.abs(prompt.box.x1 - prompt.box.x0) * natural.w}
                    height={Math.abs(prompt.box.y1 - prompt.box.y0) * natural.h} />
            )}
            {(prompt?.points || []).map((p, i) => (
                <g key={`pt${i}`} className={`rs-pt ${p.label ? 'is-pos' : 'is-neg'}`}
                    transform={`translate(${p.x * natural.w},${p.y * natural.h})`}>
                    <circle r={mk} vectorEffect="non-scaling-stroke" />
                    <line x1={-mk} y1="0" x2={mk} y2="0" vectorEffect="non-scaling-stroke" />
                    {p.label === 1 && <line x1="0" y1={-mk} x2="0" y2={mk} vectorEffect="non-scaling-stroke" />}
                </g>
            ))}
        </svg>
    );
}
