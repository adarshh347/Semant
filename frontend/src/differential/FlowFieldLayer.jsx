import React from 'react';
import { flowFieldCells } from './flowField';
import './FlowFieldLayer.css';

/**
 * FlowFieldLayer (CIRCUIT-001 GEOM-001) — draws a `flow_field` mark as a lattice of short arrows.
 *
 * The read-only renderer for the dense direction kind. Additive by design: it owns its own SVG,
 * slaved to the SAME stage-geometry contract GroundLayers uses (viewBox in natural-image px,
 * `preserveAspectRatio="xMidYMid meet"`), and does NOT touch the region / soft_field renderers.
 * A `fall_of_light` mark shows which way the light travels at every cell — an arrow per cell,
 * its length and opacity carrying the cell's magnitude so a strong rake reads over a faint drift.
 *
 * Honesty: a null cell (no local direction) draws nothing — an absent arrow is absence, not a
 * zero-length stub. A missing / malformed field renders as an empty group, never a guess. Editing
 * (dragging the field) is deferred; this gate is display only.
 */
export default function FlowFieldLayer({
    mark = null,
    geometry = null,
    natural = null,
    focused = true,
    opacity = 1,
    className = '',
}) {
    const geom = geometry || mark?.geometry || null;
    const cells = flowFieldCells(geom);
    if (!natural || !natural.w || !natural.h || cells.length === 0) return null;

    const geo = geom;                                 // validated by flowFieldCells above
    const cellW = natural.w / geo.cols;
    const cellH = natural.h / geo.rows;
    // One isotropic length in px so an arrow never skews with the image aspect. Magnitude drives
    // both length (a weak cell is short) and stroke opacity (a weak cell is faint).
    const maxLen = 0.42 * Math.min(cellW, cellH);
    const head = maxLen * 0.34;                        // arrowhead barb length

    return (
        <svg
            className={`ff-layer ${focused ? 'is-focused' : 'is-resting'} ${className}`.trim()}
            viewBox={`0 0 ${natural.w} ${natural.h}`}
            preserveAspectRatio="xMidYMid meet"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                     pointerEvents: 'none', opacity }}
            aria-hidden="true"
            data-testid="flow-field-layer"
        >
            <g className="ff-arrows">
                {cells.map((c) => {
                    const x = c.cx * natural.w;
                    const y = c.cy * natural.h;
                    const len = maxLen * (0.35 + 0.65 * c.m);
                    // shaft: centred on the cell, pointing along (dx, dy)
                    const x1 = x - c.dx * len * 0.5;
                    const y1 = y - c.dy * len * 0.5;
                    const x2 = x + c.dx * len * 0.5;
                    const y2 = y + c.dy * len * 0.5;
                    // arrowhead: two barbs swept back from the tip
                    const hl = Math.min(head, len * 0.6);
                    const ang = Math.atan2(c.dy, c.dx);
                    const bx1 = x2 - hl * Math.cos(ang - 0.5);
                    const by1 = y2 - hl * Math.sin(ang - 0.5);
                    const bx2 = x2 - hl * Math.cos(ang + 0.5);
                    const by2 = y2 - hl * Math.sin(ang + 0.5);
                    return (
                        <g key={`${c.col}-${c.row}`} className="ff-arrow"
                           style={{ opacity: 0.3 + 0.7 * c.m }}>
                            <line className="ff-shaft" x1={x1} y1={y1} x2={x2} y2={y2}
                                  vectorEffect="non-scaling-stroke" />
                            <path className="ff-head" d={`M ${x2} ${y2} L ${bx1} ${by1} M ${x2} ${y2} L ${bx2} ${by2}`}
                                  vectorEffect="non-scaling-stroke" />
                        </g>
                    );
                })}
            </g>
        </svg>
    );
}
