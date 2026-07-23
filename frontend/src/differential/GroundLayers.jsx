import React, { useEffect, useRef } from 'react';
import { paintFields } from './fieldCanvas';
import { resolveGround, groundCenter } from './grounds';
import { taperedRibbon, centerlinePath, endChevron } from './freehandTaper';
import { perfectFreehandRibbon } from './freehandStroke';
import { hasMaskPolygons, ringsToPath } from '../lib/maskGeometry';

// CIRCUIT-001 P2E-B (2d): the freehand ribbon generator, chosen at render.
// perfect-freehand when the toggle is on (smoother, pressure-expressive), the
// vendored taperedRibbon as the fallback (its ~20× smaller polygon is the
// rollback reason the spike measured). Same signature either way.
const ribbon = (px, maxWidth, usePF) =>
    (usePF ? perfectFreehandRibbon : taperedRibbon)(px, { maxWidth });

// CIRCUIT-001 P2E-B (2b): the one SVG tax the spike named — a 1-px line is
// unclickable, so an editable ground gets a fat TRANSPARENT companion path that
// receives the pointer even though the parent <svg> is pointerEvents:none.
const HIT_WIDTH = 0.025;   // of natural width — ~a fingertip on screen

/**
 * GroundLayers — the shared Ground renderer (Differential v1).
 *
 * Two layers slaved to the stage-geometry contract:
 *   - canvas: Soft Field only (radial-gradient wash);
 *   - svg: Path · Boundary · Frame · Region (+ Constellation/Relation in D),
 *     viewBox in natural pixels, `xMidYMid meet` — the same letterbox as the
 *     image, so shapes cannot drift.
 *
 * Consumed by BOTH surfaces: the Differential stage (all grounds + the draft)
 * and the Chiasm pane (recall-only — nothing shows unless a Percept performs).
 * Per-type recall signatures live here: Path travels, Boundary shimmers, Frame
 * fades whole then evidence, Region illuminates.
 */

// Opacity discipline (spec ceilings): field wash ≤0.32 (in fieldCanvas),
// boundary veil ≤0.2, region fill ≤0.12. Path/Frame are legible marks.
const BOUNDARY_VEIL = 0.2;
const REGION_FILL = 0.12;

function groundAlpha(g, { focusGroundIds, recall, recallOnly }) {
    const focused = !!focusGroundIds && focusGroundIds.has(g.id);
    if (recall?.active) {
        const p = recall.progressFor(g.id);
        if (p > 0) return { on: true, progress: p, recalling: true };
        return recallOnly ? { on: false, progress: 0 } : { on: true, progress: 1, dim: 0.25 };
    }
    if (recallOnly) return { on: false, progress: 0 };
    const dim = focusGroundIds && !focusGroundIds.has(g.id) ? 0.3 : 1;
    return { on: true, progress: 1, dim, focused };
}

// Normalized points → natural-pixel points, so the taper math and stroke widths
// land in the viewBox's own units (no distorting group scale).
const toPx = (points, natural) =>
    (points || []).map((p) => {
        const [x, y, pr] = Array.isArray(p) ? p : [p.x, p.y, p.p];
        return [x * natural.w, y * natural.h, pr];
    });

function PathGround({ g, natural, state, usePF }) {
    const { progress, dim = 1 } = state;
    const px = toPx(g.points, natural);
    const body = ribbon(px, 0.02 * natural.w, usePF);
    const center = centerlinePath(px);
    const chevron = endChevron(px, 0.028 * natural.w);
    const traveling = progress < 1;
    return (
        <g className="gl-path" style={{ opacity: dim }}>
            {/* the body reveals as the line travels */}
            <path d={body} className="gl-path-ribbon" style={{ opacity: 0.85 * progress }} />
            <path d={center} className="gl-path-center" pathLength={1} vectorEffect="non-scaling-stroke"
                style={{ strokeDasharray: 1, strokeDashoffset: 1 - progress }} />
            {!traveling && <path d={chevron} className="gl-path-chevron" vectorEffect="non-scaling-stroke" />}
        </g>
    );
}

// A transparent wide hit-path for an editable ground (path/boundary), so a thin
// line is grabbable. pointerEvents:stroke overrides the parent svg's 'none'.
function GroundHitPath({ g, natural, onPick }) {
    const px = toPx(g.points, natural);
    if (px.length < 2) return null;
    const d = centerlinePath(px);
    return (
        <path d={d} fill="none" stroke="transparent" strokeWidth={HIT_WIDTH * natural.w}
            strokeLinecap="round" strokeLinejoin="round"
            style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
            onPointerDown={(e) => { e.stopPropagation(); onPick?.(g.id, e); }} />
    );
}

function BoundaryGround({ g, natural, state }) {
    const { progress, dim = 1 } = state;
    const px = toPx(g.points, natural);
    const center = centerlinePath(px);
    const band = Math.max(2, (g.band_width || 0.06) * natural.w);
    // shimmer: width + opacity breathe with progress
    const shimmer = 0.7 + 0.3 * Math.sin(progress * Math.PI);
    return (
        <g className="gl-boundary" style={{ opacity: dim }}>
            <path d={center} className="gl-boundary-band" filter="url(#gl-blur)"
                style={{ strokeWidth: band * shimmer, opacity: BOUNDARY_VEIL * progress }} />
            <path d={center} className="gl-boundary-center" pathLength={1} vectorEffect="non-scaling-stroke"
                style={{ strokeDasharray: 1, strokeDashoffset: 1 - progress, opacity: 0.55 * progress }} />
        </g>
    );
}

function FrameGround({ natural, state }) {
    const { progress, dim = 1 } = state;
    const inset = Math.round(Math.min(natural.w, natural.h) * 0.035);
    const gap = Math.max(4, Math.round(inset * 0.4));
    // corner brackets — a viewfinder read: "the whole composition is the evidence"
    const arm = Math.round(Math.min(natural.w, natural.h) * 0.09);
    const x0 = inset, y0 = inset, x1 = natural.w - inset, y1 = natural.h - inset;
    const bracket = (cx, cy, sx, sy) =>
        `M${cx + sx * arm},${cy} L${cx},${cy} L${cx},${cy + sy * arm}`;
    const corners = [
        bracket(x0, y0, 1, 1), bracket(x1, y0, -1, 1),
        bracket(x0, y1, 1, -1), bracket(x1, y1, -1, -1),
    ];
    return (
        <g className="gl-frame" style={{ opacity: dim * progress }}>
            {/* the double inset hairline */}
            <rect x={x0} y={y0} width={x1 - x0} height={y1 - y0} className="gl-frame-line" fill="none" />
            <rect x={x0 + gap} y={y0 + gap} width={x1 - x0 - gap * 2} height={y1 - y0 - gap * 2}
                className="gl-frame-line gl-frame-line--inner" fill="none" />
            {/* bold corner brackets — the part the eye actually catches */}
            {corners.map((d, i) => <path key={i} d={d} className="gl-frame-bracket" fill="none" />)}
        </g>
    );
}

// Member + raw-point centres for a composition, in natural pixels.
function compositionNodes(g, natural, ctx) {
    const nodes = [];
    for (const mid of g.member_ids || []) {
        const m = (ctx.grounds || []).find((x) => x.id === mid);
        const c = m ? groundCenter(m, ctx) : null;
        if (c) nodes.push([c.x * natural.w, c.y * natural.h]);
    }
    for (const p of g.points || []) {
        const [x, y] = Array.isArray(p) ? p : [p.x, p.y];
        nodes.push([x * natural.w, y * natural.h]);
    }
    return nodes;
}

function ConstellationGround({ g, natural, ctx, state }) {
    const { progress, dim = 1 } = state;
    const nodes = compositionNodes(g, natural, ctx);
    if (!nodes.length) return null;
    const r = Math.max(6, natural.w * 0.012);
    return (
        <g className="gl-constellation" style={{ opacity: dim }}>
            {nodes.map(([x, y], i) => {
                // sequential pulse: each node blooms in turn, then holds
                const local = Math.max(0, Math.min(1, progress * nodes.length - i));
                const pulse = 1 + 0.25 * Math.sin(local * Math.PI);
                return (
                    <circle key={i} cx={x} cy={y} r={r * pulse} className="gl-constellation-halo"
                        style={{ opacity: 0.55 * local }} vectorEffect="non-scaling-stroke" />
                );
            })}
        </g>
    );
}

function RelationGround({ g, natural, ctx, state }) {
    const { progress, dim = 1, recalling, focused } = state;
    const nodes = compositionNodes(g, natural, ctx);
    if (nodes.length < 2) return null;
    // members co-illuminate early; the connector "unites" them late during
    // recall, and at rest it stays hidden until the relation is focused.
    const memberLight = Math.min(1, progress * 1.6);
    const unite = recalling ? Math.max(0, (progress - 0.55) / 0.45) : (focused ? 1 : 0);
    const connector = nodes.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
    const r = Math.max(6, natural.w * 0.012);
    return (
        <g className="gl-relation" style={{ opacity: dim }}>
            <path d={connector} className="gl-relation-connector" pathLength={1} vectorEffect="non-scaling-stroke"
                style={{ strokeDasharray: 1, strokeDashoffset: 1 - unite, opacity: 0.5 * unite }} />
            {nodes.map(([x, y], i) => (
                <circle key={i} cx={x} cy={y} r={r} className="gl-relation-node"
                    style={{ opacity: 0.6 * memberLight }} vectorEffect="non-scaling-stroke" />
            ))}
        </g>
    );
}

function RegionGround({ region, natural, state }) {
    const { progress, dim = 1 } = state;
    if (!region) return null;
    const lit = progress > 0;
    const cls = `gl-region${lit ? ' is-lit' : ''}`;
    if (hasMaskPolygons(region)) {
        return <path d={ringsToPath(region.polygons, natural.w, natural.h)} fillRule="evenodd"
            className={cls} vectorEffect="non-scaling-stroke"
            style={{ opacity: dim, fillOpacity: REGION_FILL * progress }} />;
    }
    if (Array.isArray(region.polygon) && region.polygon.length > 2) {
        const pts = region.polygon.map(([x, y]) => `${x * natural.w},${y * natural.h}`).join(' ');
        return <polygon points={pts} className={cls} vectorEffect="non-scaling-stroke"
            style={{ opacity: dim, fillOpacity: REGION_FILL * progress }} />;
    }
    const b = region.box || {};
    return <rect className={cls} vectorEffect="non-scaling-stroke"
        x={b.x * natural.w} y={b.y * natural.h} width={b.w * natural.w} height={b.h * natural.h}
        style={{ opacity: dim, fillOpacity: REGION_FILL * progress }} />;
}

export default function GroundLayers({
    grounds = [],
    regions = [],
    natural = null,
    content = null,
    focusGroundIds = null,
    recall = null,
    recallOnly = false,
    draft = null,           // { kind:'field'|'path'|'boundary', strokes?, points? }
    usePerfectFreehand = false,   // P2E-B (2d): swap the freehand ribbon generator
    interactive = false,          // P2E-B (2b): render hit-paths for editable grounds
    onPickGround = null,          // (groundId, event) → the workspace opens an edit
    editingGroundId = null,       // hide the hit-path for the ground currently being edited
}) {
    const canvasRef = useRef(null);

    // ── canvas layer: Soft Field ────────────────────────────────────────────
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const fields = [];
        for (const g of grounds) {
            if (g.ground_type !== 'field') continue;
            const s = groundAlpha(g, { focusGroundIds, recall, recallOnly });
            if (s.on) fields.push({ ground: g, alpha: s.dim ?? 1, progress: s.progress });
        }
        if (draft?.kind === 'field' && draft.strokes?.length) {
            fields.push({ ground: { strokes: draft.strokes }, alpha: 1, progress: 1 });
        }
        paintFields(canvas, fields, content);
    }, [grounds, content, focusGroundIds, recall, recallOnly, draft]);

    if (!content || !natural) return null;

    // ── svg layer: Path · Boundary · Frame · Region ─────────────────────────
    const svgGrounds = grounds.filter((g) => g.ground_type !== 'field');
    const draftPoints = (draft?.kind === 'path' || draft?.kind === 'boundary') ? draft.points : null;

    return (
        <>
            <canvas
                ref={canvasRef}
                className="gl-canvas"
                style={{
                    position: 'absolute', left: content.x, top: content.y,
                    width: content.w, height: content.h, pointerEvents: 'none',
                }}
                aria-hidden="true"
            />
            <svg
                className="gl-svg"
                viewBox={`0 0 ${natural.w} ${natural.h}`}
                preserveAspectRatio="xMidYMid meet"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
                aria-hidden="true"
            >
                <defs>
                    <filter id="gl-blur" x="-20%" y="-20%" width="140%" height="140%">
                        <feGaussianBlur stdDeviation={Math.max(2, natural.w * 0.006)} />
                    </filter>
                </defs>
                {svgGrounds.map((g) => {
                    const state = groundAlpha(g, { focusGroundIds, recall, recallOnly });
                    if (!state.on) return null;
                    if (g.ground_type === 'path') return <PathGround key={g.id} g={g} natural={natural} state={state} usePF={usePerfectFreehand} />;
                    if (g.ground_type === 'boundary') return <BoundaryGround key={g.id} g={g} natural={natural} state={state} />;
                    if (g.ground_type === 'frame') return <FrameGround key={g.id} natural={natural} state={state} />;
                    if (g.ground_type === 'region') {
                        const region = resolveGround(g, { regions, grounds })?.region;
                        return <RegionGround key={g.id} region={region} natural={natural} state={state} />;
                    }
                    if (g.ground_type === 'constellation') {
                        return <ConstellationGround key={g.id} g={g} natural={natural} ctx={{ regions, grounds }} state={state} />;
                    }
                    if (g.ground_type === 'relation') {
                        return <RelationGround key={g.id} g={g} natural={natural} ctx={{ regions, grounds }} state={state} />;
                    }
                    return null;
                })}

                {/* the in-progress trace draft */}
                {draftPoints && draftPoints.length > 1 && (
                    draft.kind === 'path'
                        ? <path d={ribbon(toPx(draftPoints, natural), 0.02 * natural.w, usePerfectFreehand)}
                            className="gl-path-ribbon gl-draft" />
                        : <path d={centerlinePath(toPx(draftPoints, natural))} className="gl-boundary-band gl-draft"
                            filter="url(#gl-blur)"
                            style={{ strokeWidth: Math.max(2, (draft.band_width || 0.06) * natural.w), opacity: BOUNDARY_VEIL }} />
                )}

                {/* P2E-B (2b): hit-paths for editable grounds. Only when interactive,
                    and never for the ground currently being edited (its own handles own
                    the pointer then). This is the whole SVG "hit-test tax". */}
                {interactive && onPickGround && svgGrounds.map((g) => (
                    (g.ground_type === 'path' || g.ground_type === 'boundary') && g.id !== editingGroundId
                        ? <GroundHitPath key={`hit-${g.id}`} g={g} natural={natural} onPick={onPickGround} />
                        : null
                ))}
            </svg>
        </>
    );
}
