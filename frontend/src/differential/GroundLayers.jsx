import React, { useEffect, useRef } from 'react';
import { paintFields } from './fieldCanvas';
import { resolveGround } from './grounds';
import { taperedRibbon, centerlinePath, endChevron } from './freehandTaper';

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
    if (recall?.active) {
        const p = recall.progressFor(g.id);
        if (p > 0) return { on: true, progress: p };
        return recallOnly ? { on: false, progress: 0 } : { on: true, progress: 1, dim: 0.25 };
    }
    if (recallOnly) return { on: false, progress: 0 };
    const dim = focusGroundIds && !focusGroundIds.has(g.id) ? 0.3 : 1;
    return { on: true, progress: 1, dim };
}

// Normalized points → natural-pixel points, so the taper math and stroke widths
// land in the viewBox's own units (no distorting group scale).
const toPx = (points, natural) =>
    (points || []).map((p) => {
        const [x, y, pr] = Array.isArray(p) ? p : [p.x, p.y, p.p];
        return [x * natural.w, y * natural.h, pr];
    });

function PathGround({ g, natural, state }) {
    const { progress, dim = 1 } = state;
    const px = toPx(g.points, natural);
    const ribbon = taperedRibbon(px, { maxWidth: 0.02 * natural.w });
    const center = centerlinePath(px);
    const chevron = endChevron(px, 0.028 * natural.w);
    const traveling = progress < 1;
    return (
        <g className="gl-path" style={{ opacity: dim }}>
            {/* the body reveals as the line travels */}
            <path d={ribbon} className="gl-path-ribbon" style={{ opacity: 0.85 * progress }} />
            <path d={center} className="gl-path-center" pathLength={1} vectorEffect="non-scaling-stroke"
                style={{ strokeDasharray: 1, strokeDashoffset: 1 - progress }} />
            {!traveling && <path d={chevron} className="gl-path-chevron" vectorEffect="non-scaling-stroke" />}
        </g>
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
    const inset = Math.round(Math.min(natural.w, natural.h) * 0.03);
    const gap = Math.max(3, Math.round(inset * 0.35));
    const common = { fill: 'none', className: 'gl-frame-line' };
    return (
        <g className="gl-frame" style={{ opacity: dim * progress }}>
            <rect x={inset} y={inset} width={natural.w - inset * 2} height={natural.h - inset * 2} {...common} />
            <rect x={inset + gap} y={inset + gap}
                width={natural.w - (inset + gap) * 2} height={natural.h - (inset + gap) * 2} {...common} />
        </g>
    );
}

function RegionGround({ region, natural, state }) {
    const { progress, dim = 1 } = state;
    if (!region) return null;
    const lit = progress > 0;
    const cls = `gl-region${lit ? ' is-lit' : ''}`;
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
                    if (g.ground_type === 'path') return <PathGround key={g.id} g={g} natural={natural} state={state} />;
                    if (g.ground_type === 'boundary') return <BoundaryGround key={g.id} g={g} natural={natural} state={state} />;
                    if (g.ground_type === 'frame') return <FrameGround key={g.id} natural={natural} state={state} />;
                    if (g.ground_type === 'region') {
                        const region = resolveGround(g, { regions, grounds })?.region;
                        return <RegionGround key={g.id} region={region} natural={natural} state={state} />;
                    }
                    return null;
                })}

                {/* the in-progress trace draft */}
                {draftPoints && draftPoints.length > 1 && (
                    draft.kind === 'path'
                        ? <path d={taperedRibbon(toPx(draftPoints, natural), { maxWidth: 0.02 * natural.w })}
                            className="gl-path-ribbon gl-draft" />
                        : <path d={centerlinePath(toPx(draftPoints, natural))} className="gl-boundary-band gl-draft"
                            filter="url(#gl-blur)"
                            style={{ strokeWidth: Math.max(2, (draft.band_width || 0.06) * natural.w), opacity: BOUNDARY_VEIL }} />
                )}
            </svg>
        </>
    );
}
