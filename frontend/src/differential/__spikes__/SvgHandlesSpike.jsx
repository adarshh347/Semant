/**
 * Spike 2 — the NULL HYPOTHESIS.  DEV-ONLY. Never in production nav.
 *
 * The claim under test (brief Gate 3): editable anchors — drag an endpoint,
 * insert/remove a midpoint, reshape — on the EXISTING SVG overlay approach, with
 * pointer events + `useStageGeometry`, and ZERO new dependencies. If a few
 * hundred lines close the handles gap, then Konva's case must be made on
 * something OTHER than "SVG can't do handles".
 *
 * Reference pattern (shape, not code): Excalidraw's linear-element editor (MIT).
 *
 * Everything that draws marks (brush ribbon, trace, relation, region) is the
 * SAME code path GroundLayers already uses: an SVG with the natural-pixel
 * viewBox and `preserveAspectRatio="xMidYMid meet"`. The ONLY thing this spike
 * adds over production is the handle layer — which is the whole point.
 *
 * LoC honesty: the substantive new code here is the handle layer + pointer
 * routing (this file minus the mark-drawing, which is shared/existing). The math
 * is entirely in handleEditing.js and is renderer-independent — Spike 1 imports
 * the identical module, which is itself the finding.
 */

import { useMemo, useRef, useState, useCallback } from 'react';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from '../useStageGeometry';
import { taperedRibbon } from '../freehandTaper';
import { strokeViaPerfectFreehand, polygonToPath } from './freehandCompare';
import { fixtureWorkspace, makeSpikeImage, markCenter } from './spikeFixture';
import {
    makeBrushField, makeTraceMark, serializeWorkspace,
    acceptSuggestion, citableMarks, relationNodes, markIsEditable, markRenderOpacity,
} from './visualMarkContract';
import {
    editablePoints, moveAnchor, insertAnchor, removeAnchor, applyPointEdit,
    hitAnchor, hitSegment,
} from './handleEditing';
import { SpikeChrome, SerializationPanel, ROLE_COLORS } from './spikeShared';

const HIT_TOL_PX = 12;

export default function SvgHandlesSpike() {
    const stageRef = useRef(null);
    const svgRef = useRef(null);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);
    const imgSrc = useMemo(() => makeSpikeImage(), []);

    const initial = useMemo(() => fixtureWorkspace(), []);
    const [marks, setMarks] = useState(initial.marks);
    const [layers, setLayers] = useState(initial.layers);
    const [tool, setTool] = useState('select');
    const [brushRole, setBrushRole] = useState('light_field');
    const [usePF, setUsePF] = useState(false);
    const [selectedId, setSelectedId] = useState(null);
    const [draft, setDraft] = useState(null);
    const drag = useRef(null);            // { markId, index }

    const evidenceLayer = layers.find((l) => l.layer_type === 'evidence');
    const nat = natural || { w: 900, h: 600 };
    const aspect = content ? content.w / content.h : 1;
    const tolNorm = content ? HIT_TOL_PX / content.w : 0.02;

    const toNorm = useCallback((e) => pointerToNormalized(e, stageRef.current, content), [content]);

    // ── pointer routing on the SVG surface ───────────────────────────────────
    const onDown = useCallback((e) => {
        const p = toNorm(e);
        if (!p) return;
        if (tool === 'select') {
            // Grab a handle of the selected mark, or insert a midpoint on its line.
            const sel = marks.find((m) => m.id === selectedId);
            if (sel && markIsEditable(sel, layers)) {
                const pts = editablePoints(sel.geometry);
                if (pts) {
                    const hi = hitAnchor(pts, [p.x, p.y], tolNorm, aspect);
                    if (hi >= 0) { drag.current = { markId: sel.id, index: hi }; return; }
                    const seg = hitSegment(pts, [p.x, p.y], tolNorm, aspect);
                    if (seg) {
                        setMarks((ms) => ms.map((m) => m.id === sel.id
                            ? applyPointEdit(m, insertAnchor(pts, seg.index, seg.at, seg.t)) : m));
                        drag.current = { markId: sel.id, index: seg.index + 1 };
                        return;
                    }
                }
            }
            return;
        }
        if (tool === 'brush' || tool === 'erase') {
            setDraft({ kind: 'brush', role: brushRole, op: tool === 'erase' ? 'sub' : 'add', points: [[p.x, p.y, 0.8]] });
        } else if (tool === 'trace') {
            setDraft((d) => d?.kind === 'trace' ? { ...d, points: [...d.points, [p.x, p.y]] } : { kind: 'trace', points: [[p.x, p.y]] });
        }
    }, [tool, brushRole, marks, selectedId, layers, toNorm, tolNorm, aspect]);

    const onMove = useCallback((e) => {
        const p = toNorm(e);
        if (!p) return;
        if (drag.current) {
            const { markId, index } = drag.current;
            setMarks((ms) => ms.map((m) => m.id === markId
                ? applyPointEdit(m, moveAnchor(editablePoints(m.geometry), index, [p.x, p.y])) : m));
            return;
        }
        if (draft?.kind === 'brush') setDraft((d) => ({ ...d, points: [...d.points, [p.x, p.y, 0.8]] }));
    }, [draft, toNorm]);

    const onUp = useCallback(() => {
        drag.current = null;
        if (draft?.kind === 'brush' && draft.points.length > 1) {
            setMarks((ms) => [...ms, makeBrushField({
                role: draft.role, status: 'committed', layer_id: evidenceLayer.id,
                label: `${draft.op === 'sub' ? 'erased ' : ''}${draft.role.replace('_', ' ')}`,
                geometry: { kind: 'freehand_path', strokes: [{ points: draft.points, radius: 0.05, strength: 0.85, op: draft.op }] },
                style: { color: ROLE_COLORS[draft.role] || '#C9A15E', opacity: 0.3, softness: 0.7, width: 0.05 },
            })]);
            setDraft(null);
        }
        if (draft?.kind !== 'trace') setDraft(null);
    }, [draft, evidenceLayer]);

    const commitTrace = useCallback(() => {
        if (draft?.kind === 'trace' && draft.points.length >= 2) {
            setMarks((ms) => [...ms, makeTraceMark({
                role: 'gaze_address', status: 'committed', layer_id: evidenceLayer.id, label: 'traced gaze',
                geometry: { kind: 'polyline', points: draft.points },
                anchors: { from: { kind: 'point', ref: null, at: draft.points[0] }, to: { kind: 'point', ref: null, at: draft.points.at(-1) } },
                arrow: { head: 'open', at: 'end' }, ambiguous: true,
                style: { color: '#D8DCE3', opacity: 1, softness: 0, width: 0.005 },
            })]);
        }
        setDraft(null);
    }, [draft, evidenceLayer]);

    const deleteAnchor = useCallback((markId, index, e) => {
        e.preventDefault(); e.stopPropagation();
        setMarks((ms) => ms.map((m) => m.id === markId
            ? applyPointEdit(m, removeAnchor(editablePoints(m.geometry), index)) : m));
    }, []);

    const suggestion = marks.find((m) => m.source === 'model_suggested');
    const accept = useCallback(() => {
        if (!suggestion) return;
        const { confirmed } = acceptSuggestion(suggestion, { layerId: evidenceLayer.id });
        setMarks((ms) => [...ms, confirmed]);
    }, [suggestion, evidenceLayer]);

    const toggleLayer = (id, key) => setLayers((ls) => ls.map((l) => l.id === id ? { ...l, [key]: !l[key] } : l));
    const center = useMemo(() => markCenter(marks), [marks]);
    const P = (nx, ny) => [nx * nat.w, ny * nat.h];   // normalized → natural px (viewBox units)

    const selected = marks.find((m) => m.id === selectedId);
    const selPts = selected && markIsEditable(selected, layers) ? editablePoints(selected.geometry) : null;

    return (
        <SpikeChrome
            title="Spike 2 · SVG handles (null hypothesis · zero new deps)"
            tool={tool} setTool={setTool} brushRole={brushRole} setBrushRole={setBrushRole}
            usePF={usePF} setUsePF={setUsePF}
            onAccept={accept} hasSuggestion={!!suggestion}
            onCommitTrace={commitTrace} traceOpen={draft?.kind === 'trace'}
            layers={layers} onToggleLayer={toggleLayer}
            note="Handles are SVG circles on the existing overlay. Drag endpoint · click line to insert · right-click handle to delete. No new dependency."
            panel={<SerializationPanel data={serializeWorkspace({ marks, layers })}
                citable={citableMarks(marks).length} total={marks.length} />}
        >
            <div ref={stageRef} className="spk-stage">
                <img src={imgSrc} onLoad={onImgLoad} alt="" className="spk-svg-img" />
                <svg ref={svgRef} className="spk-svg-stage" viewBox={`0 0 ${nat.w} ${nat.h}`}
                    preserveAspectRatio="xMidYMid meet"
                    onDoubleClick={commitTrace}
                    onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp}
                    style={{ cursor: tool === 'select' ? 'default' : 'crosshair' }}>
                    <defs>
                        <pattern id="spk-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                            <line x1="0" y1="0" x2="0" y2="6" stroke="#C0576A" strokeWidth="1.5" />
                        </pattern>
                    </defs>
                    {[...layers].sort((a, b) => a.order - b.order).map((layer) => (
                        <g key={layer.id} style={{ display: layer.visibility ? '' : 'none', opacity: layer.opacity }}>
                            {marks.filter((m) => m.layer_id === layer.id).map((m) => (
                                <SvgMark key={m.id} mark={m} layer={layer} nat={nat} P={P} center={center}
                                    usePF={usePF} selected={selectedId === m.id} onSelect={() => setSelectedId(m.id)} />
                            ))}
                        </g>
                    ))}
                    {draft && <SvgDraft draft={draft} nat={nat} usePF={usePF} />}

                    {/* THE HANDLE LAYER — the whole null-hypothesis experiment. */}
                    {tool === 'select' && selPts && (() => {
                        // Handle radius in viewBox (natural-px) units so it stays a
                        // consistent on-screen size — ~1% of the image width.
                        const hr = 0.011 * nat.w;
                        return (
                            <g className="spk-handles">
                                {/* midpoint hints — "click the line to add a point" made discoverable */}
                                {selPts.slice(0, -1).map((p, i) => {
                                    const mx = (p[0] + selPts[i + 1][0]) / 2, my = (p[1] + selPts[i + 1][1]) / 2;
                                    return <circle key={`m${i}`} className="spk-svg-mid" cx={mx * nat.w} cy={my * nat.h} r={hr * 0.6} />;
                                })}
                                {selPts.map((p, i) => (
                                    <circle key={i} className="spk-svg-handle" cx={p[0] * nat.w} cy={p[1] * nat.h}
                                        r={hr} vectorEffect="non-scaling-stroke"
                                        onContextMenu={(e) => deleteAnchor(selectedId, i, e)} />
                                ))}
                            </g>
                        );
                    })()}
                </svg>
            </div>
        </SpikeChrome>
    );
}

function SvgMark({ mark, layer, nat, P, center, usePF, selected, onSelect }) {
    const op = markRenderOpacity(mark, [layer]);
    if (op <= 0) return null;
    const isSuggestion = mark.source === 'model_suggested';
    const wrap = (child) => isSuggestion
        ? <g className="spk-suggestion" opacity={op} onClick={onSelect}>{child}</g>
        : <g opacity={op} onClick={onSelect}>{child}</g>;

    if (mark.type === 'brush_field') {
        const stroke = mark.geometry.strokes?.[0];
        if (!stroke?.points?.length) return null;
        const px = stroke.points.map(([x, y, p]) => [x * nat.w, y * nat.h, p]);
        const d = usePF ? polygonToPath(strokeViaPerfectFreehand(px, { size: 0.05 * nat.w }))
            : taperedRibbon(px, { maxWidth: 0.05 * nat.w });
        const isSub = stroke.op === 'sub';
        return wrap(<>
            {/* subtractive strokes read as a hatched "removed" region rather than
                punching a real hole — the SVG surface has no destination-out, so
                erase is modeled as data (op:'sub') and shown, not composited. */}
            <path d={d} fill={isSub ? 'url(#spk-hatch)' : (mark.style?.color || '#C9A15E')}
                stroke={isSub ? '#C0576A' : 'none'} strokeWidth={isSub ? 1 : 0}
                fillOpacity={isSub ? 0.5 : 0.55} vectorEffect="non-scaling-stroke" />
            {isSuggestion && <SuggestionRing px={px} nat={nat} />}
        </>);
    }
    if (mark.type === 'trace_mark') {
        const pts = mark.geometry.points || [];
        const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${(x * nat.w).toFixed(1)},${(y * nat.h).toFixed(1)}`).join(' ');
        return wrap(<>
            {/* FINDING: SVG hit testing is on the visible stroke only (~2px), which
                is unclickable. Konva ships `hitStrokeWidth` for exactly this; on
                SVG you add a fat TRANSPARENT companion path. This is the null
                hypothesis's one genuine ergonomic tax vs a scene graph. */}
            <path d={d} stroke="transparent" strokeWidth={0.02 * nat.w} fill="none"
                vectorEffect="non-scaling-stroke" style={{ cursor: 'pointer' }} />
            <path className={`spk-svg-trace${mark.ambiguous ? ' is-ambiguous' : ''}`} d={d}
                stroke={mark.style?.color || '#D8DCE3'} strokeWidth={selected ? 3 : 2} vectorEffect="non-scaling-stroke" />
            {mark.arrow?.head !== 'none' && pts.length >= 2 && <SvgArrow a={P(...pts.at(-2))} b={P(...pts.at(-1))}
                open={mark.arrow?.head === 'open'} color={mark.style?.color || '#D8DCE3'} nat={nat} />}
        </>);
    }
    if (mark.type === 'relation_mark') {
        const nodes = relationNodes(mark, center);
        if (nodes.length < 2) return null;
        const d = nodes.map(([x, y], i) => `${i ? 'L' : 'M'}${(x * nat.w).toFixed(1)},${(y * nat.h).toFixed(1)}`).join(' ');
        return wrap(<>
            <path d={d} stroke={mark.style?.color || '#C08457'} strokeWidth={1.5} strokeDasharray="2 4"
                fill="none" vectorEffect="non-scaling-stroke" />
            {nodes.map(([x, y], i) => <circle key={i} cx={x * nat.w} cy={y * nat.h} r={4} fill="none"
                stroke={mark.style?.color || '#C08457'} vectorEffect="non-scaling-stroke" />)}
        </>);
    }
    return null;
}

function SuggestionRing({ px, nat }) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const [x, y] of px) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    const pad = 0.03 * nat.w;
    return <rect className="spk-suggestion-ring" x={x0 - pad} y={y0 - pad} width={x1 - x0 + pad * 2} height={y1 - y0 + pad * 2}
        rx={pad} vectorEffect="non-scaling-stroke" />;
}

function SvgArrow({ a, b, open, color, nat }) {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
    const size = 0.025 * nat.w, spread = 0.5;
    const l = `${b[0] - ux * size + nx * size * spread},${b[1] - uy * size + ny * size * spread}`;
    const r = `${b[0] - ux * size - nx * size * spread},${b[1] - uy * size - ny * size * spread}`;
    return <path d={`M${l} L${b[0]},${b[1]} L${r}${open ? '' : ' Z'}`} fill={open ? 'none' : color}
        stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />;
}

function SvgDraft({ draft, nat, usePF }) {
    if (draft.kind === 'brush') {
        const px = draft.points.map(([x, y, p]) => [x * nat.w, y * nat.h, p]);
        const d = usePF ? polygonToPath(strokeViaPerfectFreehand(px, { size: 0.05 * nat.w }))
            : taperedRibbon(px, { maxWidth: 0.05 * nat.w });
        return <path d={d} fill={draft.op === 'sub' ? '#C0576A' : (ROLE_COLORS[draft.role] || '#C9A15E')} fillOpacity={0.4} />;
    }
    if (draft.kind === 'trace') {
        const d = draft.points.map(([x, y], i) => `${i ? 'L' : 'M'}${x * nat.w},${y * nat.h}`).join(' ');
        return <path d={d} fill="none" stroke="#D8DCE3" strokeWidth={2} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />;
    }
    return null;
}
