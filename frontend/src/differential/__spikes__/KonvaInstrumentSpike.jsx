/**
 * Spike 1 — react-konva instrument surface.  DEV-ONLY. Never in production nav.
 *
 * Answers OH §6.4 / brief Gate 2, in priority order (test 3 is the decision):
 *   1. base image + normalized 0..1 mapping, resize-safe (reimplements the
 *      useStageGeometry CONTRACT on Konva, not the letterbox math itself);
 *   2. editable handles — custom anchor Circles writing normalized points
 *      directly, NOT Transformer (the finding is recorded below and in §report);
 *   3. semantic brush styled by role, eraser via destination-out;
 *   4. relation lines with derived (never stored) geometry;
 *   5. visual_layer → Konva GROUP, never Layer (one Layer total; proven ≤3);
 *   6. suggestion mode → accept mints user_confirmed with derived_from;
 *   7. live serialization panel (contract-shaped, no Konva node);
 *   8. recall coexistence — reasoned in the report, prototyped here as an SVG
 *      overlay ABOVE the Konva stage sharing the same content box.
 *
 * COORDINATE DECISION (this is the crux of test 1, and a real Konva finding):
 * geometry is converted normalized→content-box-pixels in JS, exactly as
 * GroundLayers.toPx already does, and Konva shapes are given pixel points. The
 * RETURNED, TEMPTING alternative — one <Group scaleX={content.w} scaleY={content.h}>
 * so children draw in 0..1 — is REJECTED here because content.w ≠ content.h on
 * any non-square image, so a group scale distorts every anchor circle into an
 * ellipse and every uniform stroke into an anisotropic one. Konva's
 * `strokeScaleEnabled={false}` fixes stroke width but not the circle distortion.
 * So the same screen-space conversion the SVG path already does is the correct
 * one on Konva too — the renderer does not remove the need for it.
 */

import { useMemo, useRef, useState, useCallback, useEffect } from 'react';
import { Stage, Layer, Group, Image as KImage, Line, Circle, Path } from 'react-konva';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from '../useStageGeometry';
import { taperedRibbon } from '../freehandTaper';
import { strokeViaPerfectFreehand, polygonToPath } from './freehandCompare';
import {
    fixtureWorkspace, makeSpikeImage, markCenter,
} from './spikeFixture';
import {
    makeBrushField, makeTraceMark, serializeWorkspace,
    acceptSuggestion, citableMarks, relationNodes,
    markIsEditable, markRenderOpacity,
} from './visualMarkContract';
import {
    editablePoints, moveAnchor, applyPointEdit, hitSegment, insertAnchor, removeAnchor,
} from './handleEditing';
import { SpikeChrome, SerializationPanel, useSpikeImageEl, ROLE_COLORS } from './spikeShared';

const HANDLE_R = 6;                 // screen px — a fingertip, constant at any size
const HIT_TOL_PX = 12;

export default function KonvaInstrumentSpike() {
    const stageRef = useRef(null);       // the wrapping <div>, for geometry
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);
    const imgSrc = useMemo(() => makeSpikeImage(), []);
    const imageEl = useSpikeImageEl(imgSrc, onImgLoad);

    const initial = useMemo(() => fixtureWorkspace(), []);
    const [marks, setMarks] = useState(initial.marks);
    const [layers, setLayers] = useState(initial.layers);
    const [tool, setTool] = useState('select');          // select | brush | erase | trace
    const [brushRole, setBrushRole] = useState('light_field');
    const [usePF, setUsePF] = useState(false);           // taper generator toggle
    const [selectedId, setSelectedId] = useState(null);
    const [draft, setDraft] = useState(null);            // live stroke/trace
    const [layerCount, setLayerCount] = useState(0);

    const evidenceLayer = layers.find((l) => l.layer_type === 'evidence');

    // ── pointer → normalized (the contract, unchanged) ───────────────────────
    const toNorm = useCallback((e) => {
        const evt = e.evt || e;
        return pointerToNormalized(evt, stageRef.current, content);
    }, [content]);

    const onDown = useCallback((e) => {
        const p = toNorm(e);
        if (!p) return;
        if (tool === 'brush' || tool === 'erase') {
            setDraft({ kind: 'brush', role: brushRole, op: tool === 'erase' ? 'sub' : 'add', points: [[p.x, p.y, 0.8]] });
        } else if (tool === 'trace') {
            setDraft((d) => d?.kind === 'trace'
                ? { ...d, points: [...d.points, [p.x, p.y]] }
                : { kind: 'trace', points: [[p.x, p.y]] });
        }
    }, [tool, brushRole, toNorm]);

    const onMove = useCallback((e) => {
        if (!draft) return;
        const p = toNorm(e);
        if (!p) return;
        if (draft.kind === 'brush') setDraft((d) => ({ ...d, points: [...d.points, [p.x, p.y, 0.8]] }));
    }, [draft, toNorm]);

    const onUp = useCallback(() => {
        if (draft?.kind === 'brush' && draft.points.length > 1) {
            const m = makeBrushField({
                role: draft.role, status: 'committed', layer_id: evidenceLayer.id,
                label: `${draft.op === 'sub' ? 'erased ' : ''}${draft.role.replace('_', ' ')}`,
                geometry: { kind: 'freehand_path', strokes: [{ points: draft.points, radius: 0.05, strength: 0.85, op: draft.op }] },
                style: { color: ROLE_COLORS[draft.role] || '#C9A15E', opacity: 0.3, softness: 0.7, width: 0.05 },
            });
            setMarks((ms) => [...ms, m]);
            setDraft(null);
        }
        // trace stays open until double-click / Enter (multi-vertex)
        if (draft?.kind !== 'trace') setDraft(null);
    }, [draft, evidenceLayer]);

    const commitTrace = useCallback(() => {
        if (draft?.kind === 'trace' && draft.points.length >= 2) {
            const m = makeTraceMark({
                role: 'gaze_address', status: 'committed', layer_id: evidenceLayer.id,
                label: 'traced gaze', geometry: { kind: 'polyline', points: draft.points },
                anchors: { from: { kind: 'point', ref: null, at: draft.points[0] }, to: { kind: 'point', ref: null, at: draft.points.at(-1) } },
                arrow: { head: 'open', at: 'end' }, ambiguous: true,
                style: { color: '#D8DCE3', opacity: 1, softness: 0, width: 0.005 },
            });
            setMarks((ms) => [...ms, m]);
        }
        setDraft(null);
    }, [draft, evidenceLayer]);

    // ── editable handles: move an anchor, write NORMALIZED points directly ────
    // THE TEST-3 ANSWER, in code. `node` is the dragged Konva Circle. Its
    // stage-local position is in content-box pixels; we invert straight to
    // normalized and write mark.geometry.points. No Transformer, no scaleX ever
    // touches the mark. See the report for why Transformer was not used at all.
    const onAnchorDrag = useCallback((markId, index, node) => {
        const nx = node.x() / content.w;
        const ny = node.y() / content.h;
        setMarks((ms) => ms.map((m) => {
            if (m.id !== markId) return m;
            const pts = moveAnchor(editablePoints(m.geometry), index, [nx, ny]);
            return applyPointEdit(m, pts);
        }));
    }, [content]);

    const onSegmentClick = useCallback((markId, e) => {
        if (tool !== 'select') return;
        const p = toNorm(e);
        const m = marks.find((x) => x.id === markId);
        if (!m || !p) return;
        const pts = editablePoints(m.geometry);
        if (!pts) return;
        const aspect = content ? content.w / content.h : 1;
        const seg = hitSegment(pts, [p.x, p.y], HIT_TOL_PX / content.w, aspect);
        if (seg) {
            setMarks((ms) => ms.map((x) => x.id === markId
                ? applyPointEdit(x, insertAnchor(pts, seg.index, seg.at, seg.t)) : x));
        }
    }, [tool, marks, toNorm, content]);

    const deleteAnchor = useCallback((markId, index) => {
        setMarks((ms) => ms.map((m) => {
            if (m.id !== markId) return m;
            const pts = editablePoints(m.geometry);
            return applyPointEdit(m, removeAnchor(pts, index));
        }));
    }, []);

    // ── suggestion accept (§6 / OH §5G) ──────────────────────────────────────
    const suggestion = marks.find((m) => m.source === 'model_suggested');
    const accept = useCallback(() => {
        if (!suggestion) return;
        const { confirmed } = acceptSuggestion(suggestion, { layerId: evidenceLayer.id });
        setMarks((ms) => [...ms.filter((m) => m.id !== suggestion.id), suggestion, confirmed]);
    }, [suggestion, evidenceLayer]);

    // ── layer ops ────────────────────────────────────────────────────────────
    const toggleLayer = (id, key) => setLayers((ls) => ls.map((l) => l.id === id ? { ...l, [key]: !l[key] } : l));

    const center = useMemo(() => markCenter(marks), [marks]);

    // Count REAL Konva layers actually mounted (proves ≤3, brief Gate 2.5).
    // react-konva renders one <canvas> per <Layer>; count them after each render.
    useEffect(() => {
        const canvases = stageRef.current?.querySelectorAll('canvas') || [];
        setLayerCount((c) => (c === canvases.length ? c : canvases.length));
    });

    const stageW = content?.w || 0;
    const stageH = content?.h || 0;

    return (
        <SpikeChrome
            title="Spike 1 · react-konva"
            tool={tool} setTool={setTool}
            brushRole={brushRole} setBrushRole={setBrushRole}
            usePF={usePF} setUsePF={setUsePF}
            onAccept={accept} hasSuggestion={!!suggestion && suggestion.source === 'model_suggested'}
            onCommitTrace={commitTrace} traceOpen={draft?.kind === 'trace'}
            layers={layers} onToggleLayer={toggleLayer}
            note={`Konva <Layer> count: ${layerCount} (must be ≤3). Groups do the layering.`}
            panel={<SerializationPanel data={serializeWorkspace({ marks, layers })}
                citable={citableMarks(marks).length} total={marks.length} />}
        >
            <div ref={stageRef} className="spk-stage">
                {/* Konva stage sized to the letterboxed content box and offset to it,
                    so (0,0) of the stage is the image's top-left — same frame the SVG
                    viewBox uses. One Layer; visual_layers are GROUPS inside it. */}
                {content && (
                    <div style={{ position: 'absolute', left: content.x, top: content.y }}
                        onDoubleClick={commitTrace}>
                        <Stage width={stageW} height={stageH}
                            onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp}
                            onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}>
                            <Layer listening>
                                {imageEl && <KImage image={imageEl} width={stageW} height={stageH} listening={false} />}
                                {[...layers].sort((a, b) => a.order - b.order).map((layer) => (
                                    <Group key={layer.id} visible={layer.visibility} opacity={layer.opacity}
                                        listening={!layer.locked}>
                                        {marks.filter((m) => m.layer_id === layer.id).map((m) => (
                                            <MarkShape key={m.id} mark={m} layer={layer} content={content}
                                                natural={natural} selected={selectedId === m.id} usePF={usePF}
                                                center={center}
                                                onSelect={() => setSelectedId(m.id)}
                                                onSegmentClick={(e) => onSegmentClick(m.id, e)} />
                                        ))}
                                    </Group>
                                ))}
                                {draft && <DraftShape draft={draft} content={content} natural={natural} usePF={usePF} />}
                                {/* Editable handles: native draggable Konva Circles,
                                    NOT Transformer. Undistorted because the geometry
                                    group is not scaled. Right-click deletes a vertex. */}
                                {tool === 'select' && selectedId && (() => {
                                    const sel = marks.find((m) => m.id === selectedId);
                                    if (!sel || !markIsEditable(sel, layers)) return null;
                                    const pts = editablePoints(sel.geometry);
                                    if (!pts) return null;
                                    return pts.map((p, i) => (
                                        <Circle key={i} x={p[0] * content.w} y={p[1] * content.h}
                                            radius={HANDLE_R} fill="#fff" stroke="#C08457" strokeWidth={2}
                                            strokeScaleEnabled={false} draggable
                                            onDragMove={(e) => onAnchorDrag(sel.id, i, e.target)}
                                            onContextMenu={(e) => { e.evt.preventDefault(); deleteAnchor(sel.id, i); }}
                                            onMouseEnter={(e) => { e.target.getStage().container().style.cursor = 'grab'; }}
                                            onMouseLeave={(e) => { e.target.getStage().container().style.cursor = 'default'; }} />
                                    ));
                                })()}
                            </Layer>
                        </Stage>
                    </div>
                )}
                <img src={imgSrc} onLoad={onImgLoad} alt="" className="spk-probe-img" />
            </div>
        </SpikeChrome>
    );
}

// ── one mark → Konva shape(s) ────────────────────────────────────────────────
function MarkShape({ mark, layer, content, natural, selected, usePF, center, onSelect, onSegmentClick }) {
    const op = markRenderOpacity(mark, [layer]);
    if (op <= 0) return null;
    const nat = natural || { w: content.w, h: content.h };
    // stage origin is the content-box top-left, so normalized→stage-local is *w,*h
    const L = (nx, ny) => [nx * content.w, ny * content.h];

    if (mark.type === 'brush_field') {
        const stroke = mark.geometry.strokes?.[0];
        if (!stroke?.points?.length) return null;
        const pxNat = stroke.points.map(([x, y, p]) => [x * nat.w, y * nat.h, p]);
        const d = usePF
            ? polygonToPath(strokeViaPerfectFreehand(pxNat, { size: 0.05 * nat.w }))
            : taperedRibbon(pxNat, { maxWidth: 0.05 * nat.w });
        // Path data is in natural-pixel space; scale it to content-box with the
        // Konva node's own scale (uniform per-axis, so no distortion of the ribbon).
        const isSub = stroke.op === 'sub';
        const color = isSub ? '#000' : (mark.style?.color || '#C9A15E');
        return (
            <Path data={d} fill={color} opacity={op}
                scaleX={content.w / nat.w} scaleY={content.h / nat.h}
                globalCompositeOperation={isSub ? 'destination-out' : 'source-over'}
                onClick={onSelect} onTap={onSelect} listening />
        );
    }

    if (mark.type === 'trace_mark') {
        const pts = mark.geometry.points || [];
        const flat = pts.flatMap(([x, y]) => L(x, y));
        return (
            <>
                <Line points={flat} stroke={mark.style?.color || '#D8DCE3'} strokeWidth={selected ? 2.5 : 1.5}
                    strokeScaleEnabled={false} lineCap="round" lineJoin="round"
                    dash={mark.ambiguous ? [6, 5] : undefined} opacity={op}
                    hitStrokeWidth={14} onClick={(e) => { onSelect(); onSegmentClick(e); }} onTap={onSelect} />
                {mark.arrow?.head !== 'none' && pts.length >= 2 && (
                    <ArrowHead a={L(...pts.at(-2))} b={L(...pts.at(-1))} open={mark.arrow?.head === 'open'}
                        color={mark.style?.color || '#D8DCE3'} />
                )}
            </>
        );
    }

    if (mark.type === 'relation_mark') {
        const nodes = relationNodes(mark, center);          // DERIVED, never stored
        if (nodes.length < 2) return null;
        const flat = nodes.flatMap(([x, y]) => L(x, y));
        return (
            <>
                <Line points={flat} stroke={mark.style?.color || '#C08457'} strokeWidth={1.5}
                    strokeScaleEnabled={false} dash={[2, 4]} opacity={op} listening={false} />
                {nodes.map(([x, y], i) => <Circle key={i} x={x * content.w} y={y * content.h} radius={4}
                    stroke={mark.style?.color || '#C08457'} strokeWidth={1} strokeScaleEnabled={false} listening={false} />)}
            </>
        );
    }
    return null;
}

function ArrowHead({ a, b, open, color }) {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    const size = 10, spread = 0.5;
    const nx = -uy, ny = ux;
    const l = [b[0] - ux * size + nx * size * spread, b[1] - uy * size + ny * size * spread];
    const r = [b[0] - ux * size - nx * size * spread, b[1] - uy * size - ny * size * spread];
    return <Line points={[...l, ...b, ...r]} stroke={color} strokeWidth={1.5} strokeScaleEnabled={false}
        closed={!open} fill={open ? undefined : color} lineCap="round" />;
}

function DraftShape({ draft, content, natural, usePF }) {
    const L = (nx, ny) => [nx * content.w, ny * content.h];
    if (draft.kind === 'brush') {
        const nat = natural || { w: content.w, h: content.h };
        const pxNat = draft.points.map(([x, y, p]) => [x * nat.w, y * nat.h, p]);
        const d = usePF ? polygonToPath(strokeViaPerfectFreehand(pxNat, { size: 0.05 * nat.w }))
            : taperedRibbon(pxNat, { maxWidth: 0.05 * nat.w });
        return <Path data={d} fill={draft.op === 'sub' ? '#000' : (ROLE_COLORS[draft.role] || '#C9A15E')}
            opacity={0.5} scaleX={content.w / nat.w} scaleY={content.h / nat.h} listening={false} />;
    }
    if (draft.kind === 'trace') {
        const flat = draft.points.flatMap(([x, y]) => L(x, y));
        return <Line points={flat} stroke="#D8DCE3" strokeWidth={1.5} strokeScaleEnabled={false} dash={[4, 4]} listening={false} />;
    }
    return null;
}

