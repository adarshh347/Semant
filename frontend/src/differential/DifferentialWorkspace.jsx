import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ArrowLeft, MousePointer2, Brush, PenTool, Group, Waypoints, Frame, Eye, Check,
    Play, Undo2, X, Plus, Scan, Sparkles, Search,
} from 'lucide-react';
import RegionOverlay from '../components/RegionOverlay';
import GroundLayers from './GroundLayers';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from './useStageGeometry';
import useMaskRefine from './useMaskRefine';
import useSemanticRead from './useSemanticRead';
import SemanticReading from './SemanticReading';
import useFindSimilar from './useFindSimilar';
import FindSimilar from './FindSimilar';
import { makeGround, groundFromRegion, resolveGround } from './grounds';
import { useRecallPlayer } from './recall';
import './DifferentialWorkspace.css';

/**
 * Differential — the dedicated percept-construction workspace (v1).
 *
 * A full-workspace MODE inside PostDetailPage, not a route: the Chiasm shell
 * stays mounted (hidden) so unsaved Manuscript state survives enter/leave.
 *
 * A+B: shell, shared geometry, grounds/percepts round-trip, Soft Field loop.
 * C: spatial vocabulary (Path, Boundary, Frame, Region select).
 * D: compositional vocabulary — Collect (Constellation), Connect (Relation),
 *    and an accumulative tray for composing one Percept from several Grounds.
 */

const TOOLS = [
    { key: 'select', label: 'Select', icon: MousePointer2, hint: 'Point at parts — ⇧ to gather several' },
    { key: 'brush', label: 'Brush', icon: Brush, hint: 'Soft Field — paint where the light lives' },
    { key: 'trace', label: 'Trace', icon: PenTool, hint: 'Path or Boundary — draw a line' },
    { key: 'collect', label: 'Collect', icon: Group, hint: 'Constellation — gather grounds and points' },
    { key: 'connect', label: 'Connect', icon: Waypoints, hint: 'Relation — tie two grounds together' },
    { key: 'frame', label: 'Frame', icon: Frame, hint: 'The whole image as evidence' },
    { key: 'refine', label: 'Refine', icon: Scan, hint: 'Select a part, then click/drag to tighten it to an exact mask' },
    { key: 'read', label: 'Read', icon: Sparkles, hint: 'Ask the model to interpret the parts — name, qualify, relate; it never moves a mask' },
    { key: 'similar', label: 'Similar', icon: Search, hint: 'Find a selected part\'s visual neighbours — research to inspect, never facts' },
];

const PERCEPT_PROPERTIES = [
    'light', 'colour', 'material', 'movement', 'composition',
    'attention', 'atmosphere', 'repetition', 'contrast',
];

const GROUND_GLYPH = { field: '◐', path: '↝', boundary: '∥', frame: '▣', region: '◈', constellation: '⁘', relation: '⤝' };
const regionName = (r) => r?.label || r?.part || r?.category || 'part';

const groundTitle = (g, regions = []) => {
    if (!g) return '';
    if (g.label) return g.label;
    switch (g.ground_type) {
        case 'field': return `Soft field · ${(g.strokes || []).length} stroke${(g.strokes || []).length !== 1 ? 's' : ''}`;
        case 'path': return 'Path';
        case 'boundary': return 'Boundary';
        case 'frame': return 'Frame · whole image';
        case 'constellation': return `Constellation · ${(g.member_ids || []).length + (g.points || []).length} nodes`;
        case 'relation': return g.relation_label ? `Relation · ${g.relation_label}` : 'Relation';
        case 'region': {
            const r = regions.find((x) => x.id === g.region_id);
            return r ? regionName(r) : 'Region';
        }
        default: return g.ground_type;
    }
};

const MIN_SAMPLE_DIST = 0.004;

export default function DifferentialWorkspace({ post, store, onExit }) {
    const [tool, setTool] = useState('select');
    const [traceSub, setTraceSub] = useState('path');
    const [untouched, setUntouched] = useState(false);
    const [brushRadius, setBrushRadius] = useState(0.045);
    const [bandWidth, setBandWidth] = useState(0.06);
    const [draft, setDraft] = useState(null);
    const [picked, setPicked] = useState(() => new Set());   // multi-selected region ids (Select)
    const [tray, setTray] = useState(() => new Set());       // accumulative ground gather
    const [composer, setComposer] = useState(null);          // { groundIds, expression, properties }
    const [brushCursor, setBrushCursor] = useState(null);
    const stageRef = useRef(null);
    const drawingRef = useRef(false);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);

    const {
        regions, selectedId, selectRegion, hoveredId, setHoveredId,
        grounds, percepts, saveState, metaSaveState,
        addGround, removeGround, groundById, selectedGroundId, selectGround,
        setHoveredGroundId, focusGroundIds,
        addExpressionPercept, playRecall, clearRecall, recall,
        updateRegion, addRegion,
    } = store;

    const recallPlayer = useRecallPlayer(store);

    // ── Refine (VISION-B5) — exact-mask refinement of the selected part ────────
    const postId = post?._id || post?.id;
    const selectedRegion = regions.find((r) => r.id === selectedId) || null;
    // baseRegion is only meaningful while refining; passing the selection lets
    // Select → Refine upgrade that part's mask in place.
    const refine = useMaskRefine(postId, tool === 'refine' ? selectedRegion : null);
    const [refineBox, setRefineBox] = useState(null);   // live box draft (normalized)
    const refineDrag = useRef(null);

    // ── Similar (VISION-E · E5) — a selected part's visual neighbours (research, not fact) ──
    const similar = useFindSimilar(postId, tool === 'similar' ? selectedId : null);

    // ── Read (VISION-D · D4) — the VLM interprets the candidate masks (never geometry) ──
    const reading = useSemanticRead(postId, post?.semantics || null);
    // "needs better evidence" hands the curator straight to Refine on that part.
    const readingToRefine = useCallback((cid) => {
        selectRegion(cid);
        switchTool('refine');
    }, [selectRegion]);   // eslint-disable-line react-hooks/exhaustive-deps -- switchTool stable

    const expressionPercepts = useMemo(
        () => (percepts || []).filter((p) => String(p.id || '').startsWith('pctx_')),
        [percepts],
    );

    const composing = tool === 'collect' || tool === 'connect';

    // ── draft, shaped for the layers ─────────────────────────────────────────
    const draftForLayers = useMemo(() => {
        if (!draft) return null;
        if (draft.kind === 'field') {
            const strokes = draft.live ? [...draft.strokes, draft.live] : draft.strokes;
            return { kind: 'field', strokes };
        }
        if (draft.kind === 'path' || draft.kind === 'boundary') {
            return { kind: draft.kind, points: draft.points, band_width: draft.band_width };
        }
        // constellation/relation drafts render as their own ground preview
        return { kind: draft.kind, member_ids: draft.member_ids, points: draft.points || [] };
    }, [draft]);

    // Feed the composition draft into GroundLayers as a live ground, so its
    // halos/connector appear as you gather.
    const groundsForLayers = useMemo(() => {
        if (draftForLayers && (draftForLayers.kind === 'constellation' || draftForLayers.kind === 'relation')) {
            return [...grounds, { id: '__draft__', ground_type: draftForLayers.kind, ...draftForLayers }];
        }
        return grounds;
    }, [grounds, draftForLayers]);

    const draftFocus = useMemo(
        () => ((draft?.kind === 'constellation' || draft?.kind === 'relation') ? new Set(['__draft__', ...(draft.member_ids || [])]) : focusGroundIds),
        [draft, focusGroundIds],
    );

    const hasDrawDraft = draft && (draft.kind === 'field'
        ? (draft.strokes.length > 0 || draft.live)
        : (draft.kind === 'path' || draft.kind === 'boundary') ? draft.points.length > 1 : false);
    const hasCompDraft = draft && (draft.kind === 'constellation' || draft.kind === 'relation')
        && ((draft.member_ids || []).length + (draft.points || []).length) > 0;

    // ── tool switching ───────────────────────────────────────────────────────
    const switchTool = useCallback((key) => {
        setPicked(new Set());
        setDraft(key === 'collect' ? { kind: 'constellation', member_ids: [], points: [] }
            : key === 'connect' ? { kind: 'relation', member_ids: [], relation_label: '' }
                : null);
        setTool(key);
    }, []);

    // A region-adapter Ground for a region, created once (dedupe by region_id).
    const ensureRegionGround = useCallback((regionId) => {
        const existing = grounds.find((g) => g.ground_type === 'region' && g.region_id === regionId);
        if (existing) return existing.id;
        const r = regions.find((x) => x.id === regionId);
        return addGround(groundFromRegion(regionId, { label: r ? regionName(r) : '' })).id;
    }, [grounds, regions, addGround]);

    const toggleMember = useCallback((groundId) => {
        setDraft((d) => {
            if (!d || (d.kind !== 'constellation' && d.kind !== 'relation')) return d;
            const has = d.member_ids.includes(groundId);
            return { ...d, member_ids: has ? d.member_ids.filter((x) => x !== groundId) : [...d.member_ids, groundId] };
        });
    }, []);

    // ── gestures ─────────────────────────────────────────────────────────────
    const onStagePointerDown = (e) => {
        if (untouched) return;
        const p = pointerToNormalized(e, stageRef.current, content);
        if (!p) return;
        // Refine (VISION-B5): a click plants a point (⇧ = negative), a drag draws a box.
        // Own the gesture so the image never pans while prompting.
        if (tool === 'refine') {
            e.preventDefault();
            e.currentTarget.setPointerCapture?.(e.pointerId);
            refineDrag.current = { x0: p.x, y0: p.y, moved: false };
            setRefineBox(null);
            return;
        }
        // Drawing tools own the gesture — stop the browser's native image-drag /
        // text-selection from hijacking the press-drag (the "brush moves the image"
        // bug). draggable=false + user-drag CSS below are the belt; this is the braces.
        if (tool === 'brush' || tool === 'trace') e.preventDefault();
        if (tool === 'brush') {
            e.currentTarget.setPointerCapture?.(e.pointerId);
            drawingRef.current = true;
            setDraft((d) => ({
                kind: 'field',
                strokes: d?.kind === 'field' ? d.strokes : [],
                live: { points: [[p.x, p.y, e.pressure || 0]], radius: brushRadius, strength: 0.8, op: e.altKey ? 'sub' : 'add' },
            }));
        } else if (tool === 'trace') {
            e.currentTarget.setPointerCapture?.(e.pointerId);
            drawingRef.current = true;
            setDraft({ kind: traceSub, points: [[p.x, p.y, e.pressure || 0]], band_width: bandWidth });
        } else if (tool === 'collect' && e.target.tagName === 'IMG') {
            // an empty tap plants a raw point in the constellation
            setDraft((d) => (d?.kind === 'constellation' ? { ...d, points: [...(d.points || []), { x: p.x, y: p.y }] } : d));
        }
    };

    const onStagePointerMove = (e) => {
        const p = pointerToNormalized(e, stageRef.current, content);
        if (tool === 'brush') setBrushCursor(p);
        if (tool === 'refine' && refineDrag.current) {
            if (!p) return;
            const d = refineDrag.current;
            if (Math.hypot(p.x - d.x0, p.y - d.y0) > 0.012) {
                d.moved = true;
                setRefineBox({ x0: d.x0, y0: d.y0, x1: p.x, y1: p.y });
            }
            return;
        }
        if (!drawingRef.current || !p) return;
        if (tool === 'brush') {
            setDraft((d) => {
                if (!d?.live) return d;
                const last = d.live.points[d.live.points.length - 1];
                if (Math.hypot(p.x - last[0], p.y - last[1]) < MIN_SAMPLE_DIST) return d;
                return { ...d, live: { ...d.live, points: [...d.live.points, [p.x, p.y, e.pressure || 0]] } };
            });
        } else if (tool === 'trace') {
            setDraft((d) => {
                if (!d?.points) return d;
                const last = d.points[d.points.length - 1];
                if (Math.hypot(p.x - last[0], p.y - last[1]) < MIN_SAMPLE_DIST) return d;
                return { ...d, points: [...d.points, [p.x, p.y, e.pressure || 0]] };
            });
        }
    };

    const onStagePointerUp = (e) => {
        if (tool === 'refine' && refineDrag.current) {
            const d = refineDrag.current; refineDrag.current = null;
            const p = pointerToNormalized(e, stageRef.current, content);
            if (d.moved && p) refine.setBoxPrompt({ x0: d.x0, y0: d.y0, x1: p.x, y1: p.y });
            else if (p) refine.addPoint(p.x, p.y, e.shiftKey ? 0 : 1);
            setRefineBox(null);
            return;
        }
        endStroke(e);
    };

    const endStroke = useCallback(() => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        setDraft((d) => {
            if (!d) return d;
            if (d.kind === 'field') {
                const strokes = d.live && d.live.points.length > 1 ? [...d.strokes, d.live] : d.strokes;
                return { ...d, strokes, live: null };
            }
            if (d.kind === 'path' || d.kind === 'boundary') return d.points.length > 1 ? d : null;
            return d;
        });
    }, []);

    const clearDraft = useCallback(() => {
        setDraft(composing
            ? (tool === 'collect' ? { kind: 'constellation', member_ids: [], points: [] } : { kind: 'relation', member_ids: [], relation_label: '' })
            : null);
        drawingRef.current = false;
    }, [composing, tool]);

    const undoStroke = useCallback(() => {
        setDraft((d) => (d?.kind === 'field' ? { ...d, strokes: d.strokes.slice(0, -1) } : d));
    }, []);

    const openComposer = useCallback((groundIds) => {
        setComposer({ groundIds: Array.isArray(groundIds) ? groundIds : [groundIds], expression: '', properties: [] });
    }, []);

    // ── commits ──────────────────────────────────────────────────────────────
    const commitDraft = useCallback(() => {
        if (!draft) return;
        let ground = null;
        if (draft.kind === 'field') {
            const strokes = draft.live ? [...draft.strokes, draft.live] : draft.strokes;
            if (!strokes.length) return;
            ground = addGround(makeGround('field', { strokes }));
        } else if (draft.kind === 'path') {
            if (draft.points.length < 2) return;
            ground = addGround(makeGround('path', { points: draft.points, arrowhead: true }));
        } else if (draft.kind === 'boundary') {
            if (draft.points.length < 2) return;
            ground = addGround(makeGround('boundary', { points: draft.points, band_width: draft.band_width }));
        } else if (draft.kind === 'constellation') {
            if (!hasCompDraft) return;
            ground = addGround(makeGround('constellation', { member_ids: draft.member_ids, points: draft.points || [] }));
        } else if (draft.kind === 'relation') {
            if ((draft.member_ids || []).length < 2) return;
            ground = addGround(makeGround('relation', { member_ids: draft.member_ids, relation_label: draft.relation_label || '' }));
        }
        setDraft(null);
        setTool('select');
        if (ground) { selectGround(ground.id); openComposer(ground.id); }
    }, [draft, hasCompDraft, addGround, selectGround, openComposer]);

    const commitFrame = useCallback(() => {
        const evidence = [...tray];
        if (selectedGroundId && !evidence.includes(selectedGroundId)) evidence.push(selectedGroundId);
        // Don't multiply whole-image frames: reuse one already holding this same
        // evidence set, so repeated clicks re-open its composer rather than pile up.
        const key = [...evidence].sort().join(',');
        const existing = grounds.find(
            (g) => g.ground_type === 'frame' && [...(g.evidence_ids || [])].sort().join(',') === key,
        );
        const ground = existing || addGround(makeGround('frame', { whole: true, evidence_ids: evidence }));
        selectGround(ground.id);
        openComposer(ground.id);
    }, [tray, selectedGroundId, grounds, addGround, selectGround, openComposer]);

    const composeFromRegions = useCallback(() => {
        const ids = picked.size ? [...picked] : (selectedId ? [selectedId] : []);
        if (!ids.length) return;
        const groundIds = ids.map((rid) => ensureRegionGround(rid));
        setPicked(new Set());
        openComposer(groundIds);
    }, [picked, selectedId, ensureRegionGround, openComposer]);

    const composeFromTray = useCallback(() => {
        if (!tray.size) return;
        openComposer([...tray]);
        setTray(new Set());
    }, [tray, openComposer]);

    const savePercept = useCallback(() => {
        if (!composer) return;
        const expression = composer.expression.trim();
        if (!expression) return;
        const p = addExpressionPercept({
            expression, ground_ids: composer.groundIds, properties: composer.properties,
        });
        setComposer(null);
        playRecall(p.id);
    }, [composer, addExpressionPercept, playRecall]);

    // ── refine commit / cancel / session release ─────────────────────────────
    // Confirm saves the new geometry revision (the endpoint persists) and refreshes
    // the region in the store IN PLACE — no reload, still inside Differential. Cancel
    // changes nothing on the server.
    const confirmRefine = useCallback(async () => {
        const data = await refine.confirm();
        const r = data?.region;
        if (!r) return;
        if (regions.some((x) => x.id === r.id)) updateRegion(r.id, r, { save: false });
        else addRegion(r, { save: false });
        selectRegion(r.id);
    }, [refine, regions, updateRegion, addRegion, selectRegion]);

    // Release the SAM session when refinement mode ends…
    const wasRefine = useRef(false);
    useEffect(() => {
        if (wasRefine.current && tool !== 'refine') { refine.clear(); refine.release(); }
        wasRefine.current = tool === 'refine';
        // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine methods only
    }, [tool, refine.clear, refine.release]);
    // …and when the workspace unmounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine.release only
    useEffect(() => () => { refine.release(); }, [refine.release]);

    // ── region click (tool-aware) ───────────────────────────────────────────
    const handleRegionClick = useCallback((id, e) => {
        if (tool === 'select' || tool === 'similar') {
            if (e?.shiftKey && tool === 'select') setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
            else setPicked(new Set([id]));
            selectRegion(id);
            selectGround(null);
        } else if (composing) {
            toggleMember(ensureRegionGround(id));
        }
    }, [tool, composing, selectRegion, selectGround, toggleMember, ensureRegionGround]);

    const addToTray = useCallback((groundId) => {
        setTray((s) => { const n = new Set(s); n.add(groundId); return n; });
    }, []);

    // ── keyboard ─────────────────────────────────────────────────────────────
    useEffect(() => {
        const down = (e) => {
            if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return;
            if (tool === 'refine') {
                if (e.key === 'Enter') { e.preventDefault(); confirmRefine(); return; }
                if (e.key === 'Escape') { refine.clear(); return; }
            }
            if (e.code === 'KeyO' && !e.repeat) setUntouched(true);
            else if (e.key === 'Escape') {
                if (recall) clearRecall();
                else if (composer) setComposer(null);
                else if (hasDrawDraft || hasCompDraft) clearDraft();
                else if (picked.size) setPicked(new Set());
                else if (tray.size) setTray(new Set());
                else { selectRegion(null); selectGround(null); setHoveredId(null); }
            } else if (tool === 'brush' && e.key === '[') setBrushRadius((r) => Math.max(0.012, r * 0.82));
            else if (tool === 'brush' && e.key === ']') setBrushRadius((r) => Math.min(0.16, r * 1.22));
            else if (tool === 'trace' && traceSub === 'boundary' && e.key === '[') setBandWidth((w) => Math.max(0.02, w * 0.82));
            else if (tool === 'trace' && traceSub === 'boundary' && e.key === ']') setBandWidth((w) => Math.min(0.2, w * 1.22));
            else if (e.key.toLowerCase() === 'b') switchTool('brush');
            else if (e.key.toLowerCase() === 'v') switchTool('select');
            else if (e.key.toLowerCase() === 't') switchTool('trace');
            else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undoStroke(); }
        };
        const up = (e) => { if (e.code === 'KeyO') setUntouched(false); };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
        // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine.clear only
    }, [recall, clearRecall, composer, hasDrawDraft, hasCompDraft, picked, tray, clearDraft, undoStroke, switchTool, tool, traceSub, selectRegion, selectGround, setHoveredId, confirmRefine, refine.clear]);

    const saving = saveState === 'saving' || metaSaveState === 'saving';
    const saved = saveState === 'saved' || metaSaveState === 'saved';

    const selected = regions.find((r) => r.id === selectedId) || null;
    const selectedGround = grounds.find((g) => g.id === selectedGroundId) || null;
    const focusId = hoveredId || selectedId;
    const litIds = composing && draft?.member_ids?.length
        ? new Set(grounds.filter((g) => g.ground_type === 'region' && draft.member_ids.includes(g.id)).map((g) => g.region_id))
        : (picked.size ? picked : null);

    const detachedGrounds = grounds.filter((g) => resolveGround(g, { regions, grounds })?.detached);
    const brushing = tool === 'brush' && !untouched;
    const tracing = tool === 'trace' && !untouched;
    const drawingTool = brushing || tracing;

    const memberSet = new Set(draft?.member_ids || []);

    return (
        <div className="diff-root" data-tool={tool}>
            {/* ── top bar ── */}
            <header className="diff-topbar">
                <button type="button" className="diff-back" onClick={onExit}
                    title="Back to Chiasm — the Manuscript is exactly as you left it">
                    <ArrowLeft size={15} /> Chiasm
                </button>
                <div className="diff-identity">
                    <span className="diff-eyebrow">Differential</span>
                    {post?.instagram_handle && <span className="diff-handle">@{post.instagram_handle}</span>}
                </div>
                <div className="diff-topbar-right">
                    <button type="button" className={`diff-untouched${untouched ? ' on' : ''}`}
                        onClick={() => setUntouched((u) => !u)} title="See the untouched image (hold O)">
                        <Eye size={14} /> <span>Untouched</span>
                    </button>
                    <span className={`diff-save diff-save--${saving ? 'saving' : saved ? 'saved' : 'idle'}`}>
                        {saving && 'saving…'}
                        {!saving && saved && <><Check size={12} /> saved</>}
                    </span>
                </div>
            </header>

            <div className="diff-body">
                {/* ── tool rail ── */}
                <nav className="diff-tools" aria-label="Perceptual operations">
                    {TOOLS.map((t) => (
                        <button key={t.key} type="button"
                            className={`diff-tool${tool === t.key ? ' on' : ''}`}
                            aria-pressed={tool === t.key}
                            title={`${t.label} — ${t.hint}`}
                            onClick={() => { if (t.key === 'frame') commitFrame(); else switchTool(t.key); }}>
                            <t.icon size={16} />
                            <span className="diff-tool-label">{t.label}</span>
                        </button>
                    ))}
                </nav>

                {/* ── stage ── */}
                <main className="diff-stage-col">
                    {tracing && (
                        <div className="diff-subtools" role="radiogroup" aria-label="Trace mode">
                            <button type="button" role="radio" aria-checked={traceSub === 'path'}
                                className={`diff-subtool${traceSub === 'path' ? ' on' : ''}`}
                                onClick={() => setTraceSub('path')}>Path</button>
                            <button type="button" role="radio" aria-checked={traceSub === 'boundary'}
                                className={`diff-subtool${traceSub === 'boundary' ? ' on' : ''}`}
                                onClick={() => setTraceSub('boundary')}>Boundary</button>
                            {traceSub === 'boundary' && (
                                <label className="diff-band">band
                                    <input type="range" min="0.02" max="0.2" step="0.005" value={bandWidth}
                                        onChange={(e) => setBandWidth(Number(e.target.value))} />
                                </label>
                            )}
                        </div>
                    )}

                    <div className={
                        `diff-stage${untouched ? ' is-untouched' : ''}`
                        + `${drawingTool ? ' is-drawing' : ''}`
                        + `${recallPlayer.receding ? ' is-recalling' : ''}`}
                        ref={stageRef}
                        style={natural ? { '--diff-ar': `${natural.w} / ${natural.h}` } : undefined}
                        onPointerDown={onStagePointerDown}
                        onPointerMove={onStagePointerMove}
                        onPointerUp={onStagePointerUp}
                        onPointerLeave={() => { endStroke(); setBrushCursor(null); }}
                        // Belt-and-braces against the native image drag stealing the gesture.
                        onDragStart={(e) => e.preventDefault()}>
                        <img src={post.photo_url} alt="" referrerPolicy="no-referrer" onLoad={onImgLoad}
                            draggable={false} />
                        {!untouched && (
                            <>
                                <RegionOverlay
                                    natural={natural} regions={regions} viewMap="quiet"
                                    selectedId={selectedId} activeId={hoveredId} focusId={focusId} litIds={litIds}
                                    onSelect={(tool === 'select' || composing || tool === 'similar') ? handleRegionClick : undefined}
                                    onActivate={(tool === 'select' || tool === 'similar') ? setHoveredId : undefined}
                                    className="diff-svg"
                                    interactive={tool !== 'refine'}
                                    proposal={tool === 'refine' ? refine.proposal : null}
                                    prompt={tool === 'refine' ? { points: refine.points, box: refineBox || refine.box } : null}
                                />
                                <GroundLayers
                                    grounds={groundsForLayers} regions={regions} natural={natural} content={content}
                                    focusGroundIds={draftFocus}
                                    recall={recallPlayer.active ? recallPlayer : null}
                                    draft={draftForLayers?.kind === 'field' || draftForLayers?.kind === 'path' || draftForLayers?.kind === 'boundary' ? draftForLayers : null}
                                />
                            </>
                        )}
                        {brushing && brushCursor && content && (
                            <span className="diff-brush-cursor" style={{
                                left: content.x + brushCursor.x * content.w,
                                top: content.y + brushCursor.y * content.h,
                                width: brushRadius * content.w * 2, height: brushRadius * content.w * 2,
                            }} />
                        )}
                        {recallPlayer.caption && <p className="diff-recall-caption">{recallPlayer.caption}</p>}
                    </div>
                    <p className="diff-stage-hint">
                        {untouched ? 'The untouched image. Release O to see your evidence again.'
                            : brushing ? 'Paint where it lives. [ ] size · ⌥ lifts paint away · Esc clears the draft.'
                                : tracing ? (traceSub === 'path'
                                    ? 'Draw a path — a directed line through what moves you. Esc clears it.'
                                    : 'Draw a boundary — the seam where one thing becomes another. [ ] widen the band.')
                                    : tool === 'collect' ? 'Click grounds and empty points to gather a constellation.'
                                        : tool === 'connect' ? 'Click two or more grounds to tie them into a relation.'
                                            : tool === 'refine' ? (selectedRegion
                                                ? 'Refine — click the part to grow the mask, ⇧-click to subtract, or drag a box. Enter confirms · Esc clears.'
                                                : 'Refine — Select a part first, then click/drag to tighten it to an exact mask.')
                                                : tool === 'read' ? 'Read — ask the model to interpret the parts in the inspector. It names, qualifies and relates them; it never moves a mask.'
                                                    : tool === 'similar' ? 'Similar — select a part; its visual neighbours appear in the inspector as research to inspect (source, exact mask, distance, space), never as facts.'
                                                        : 'Select parts (⇧ to gather several), or take a tool: Brush (B), Trace (T), Collect, Connect, Frame.'}
                    </p>
                </main>

                {/* ── inspector ── */}
                <aside className="diff-inspector">
                    {/* refine (VISION-B5) — exact-mask refinement of the selected part */}
                    {tool === 'refine' && (
                        <div className="diff-insp-refine">
                            <span className="diff-eyebrow">Refine mask</span>
                            <p className="diff-insp-hint">
                                {selectedRegion
                                    ? <>Tightening <strong>{regionName(selectedRegion)}</strong> — the exact mask replaces its box.</>
                                    : 'No part selected — this makes a new mask. (Select a part first for Select → Refine.)'}
                            </p>
                            <div className="diff-refine-status" aria-live="polite">
                                {refine.status === 'loading' && (<><span className="diff-refine-spin" /> refining…</>)}
                                {refine.status === 'ok' && `proposed · ${Math.round((refine.proposal.confidence || 0) * 100)}% · rev ${refine.proposal.geometry_rev}`}
                                {refine.status === 'empty' && 'no confident mask yet — add a point or drag a box'}
                                {refine.status === 'error' && <span className="diff-refine-err">refiner error: {refine.error}</span>}
                                {refine.status === 'confirmed' && <span className="diff-refine-ok">saved ✓</span>}
                                {refine.status === 'idle' && (selectedRegion ? 'click the part, or drag a box' : 'select a part first')}
                            </div>
                            <div className="diff-refine-actions">
                                <button type="button" className="diff-mini" onClick={() => refine.clear()} disabled={!refine.hasPrompt}>Clear</button>
                                <button type="button" className="diff-mini" onClick={() => { refine.clear(); switchTool('select'); }}>Cancel</button>
                                <button type="button" className="diff-mini diff-mini--primary" onClick={confirmRefine} disabled={refine.status !== 'ok'}>Confirm</button>
                            </div>
                        </div>
                    )}
                    {/* read (VISION-D · D4) — the VLM reading of the candidate masks */}
                    {tool === 'read' && (
                        <SemanticReading
                            semantics={reading.semantics} status={reading.status}
                            error={reading.error} busyId={reading.busyId} regions={regions}
                            onRead={(intent, force) => reading.read({ intent, force })}
                            onCancel={reading.cancel} onCurate={reading.curate}
                            onFocusRegion={(id) => { selectRegion(id); selectGround(null); }}
                            onHoverRegion={setHoveredId} onRefine={readingToRefine}
                        />
                    )}
                    {/* similar (VISION-E · E5) — visual neighbours of the selected part */}
                    {tool === 'similar' && (
                        <FindSimilar
                            regionName={selectedRegion ? regionName(selectedRegion) : null}
                            status={similar.status} error={similar.error} results={similar.results}
                            meta={similar.meta} cropUrl={similar.cropUrl}
                            onFind={similar.find} onReindex={similar.reindex} onCancel={similar.cancel}
                        />
                    )}
                    {/* draw draft (field/path/boundary) */}
                    {hasDrawDraft && !composer && (
                        <div className="diff-insp-draft">
                            <span className="diff-eyebrow">Draft {draft.kind}</span>
                            <p className="diff-insp-hint">
                                {draft.kind === 'field'
                                    ? `${draftForLayers.strokes.length} stroke${draftForLayers.strokes.length !== 1 ? 's' : ''} — still yours to shape.`
                                    : 'A line, still yours to shape.'}
                            </p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={commitDraft}>Keep this {draft.kind}</button>
                                {draft.kind === 'field' && (
                                    <button type="button" className="diff-quiet" onClick={undoStroke} title="Undo the last stroke (⌘Z)">
                                        <Undo2 size={13} /> Undo
                                    </button>
                                )}
                                <button type="button" className="diff-quiet" onClick={clearDraft}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* composition draft (constellation/relation) */}
                    {composing && !composer && (
                        <div className="diff-insp-draft">
                            <span className="diff-eyebrow">{tool === 'collect' ? 'Constellation' : 'Relation'}</span>
                            <p className="diff-insp-hint">
                                {(draft?.member_ids || []).length} ground{(draft?.member_ids || []).length !== 1 ? 's' : ''}
                                {tool === 'collect' && (draft?.points || []).length > 0 && ` · ${draft.points.length} point${draft.points.length !== 1 ? 's' : ''}`}
                                {' '}gathered — click grounds below or on the image.
                            </p>
                            {tool === 'connect' && (
                                <input className="diff-relation-label" placeholder="How are they related? (optional)"
                                    value={draft?.relation_label || ''}
                                    onChange={(e) => setDraft((d) => ({ ...d, relation_label: e.target.value }))} />
                            )}
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    disabled={tool === 'connect' ? (draft?.member_ids || []).length < 2 : !hasCompDraft}
                                    onClick={commitDraft}>
                                    Keep this {tool === 'collect' ? 'constellation' : 'relation'}
                                </button>
                                <button type="button" className="diff-quiet" onClick={clearDraft}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* composer */}
                    {composer && (
                        <div className="diff-composer">
                            <div className="diff-composer-head">
                                <span className="diff-eyebrow">Percept</span>
                                <button type="button" className="diff-icon-btn" onClick={() => setComposer(null)}
                                    title="Later — the grounds stay; compose when ready">
                                    <X size={13} />
                                </button>
                            </div>
                            <p className="diff-composer-ask">What do you notice?</p>
                            <textarea autoFocus className="diff-composer-input" placeholder="Say it as you saw it…"
                                value={composer.expression}
                                onChange={(e) => setComposer((c) => ({ ...c, expression: e.target.value }))}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); savePercept(); }
                                    if (e.key === 'Escape') { e.stopPropagation(); setComposer(null); }
                                }} />
                            <div className="diff-composer-props">
                                {PERCEPT_PROPERTIES.map((prop) => (
                                    <button key={prop} type="button"
                                        className={`diff-prop${composer.properties.includes(prop) ? ' on' : ''}`}
                                        onClick={() => setComposer((c) => ({
                                            ...c,
                                            properties: c.properties.includes(prop)
                                                ? c.properties.filter((x) => x !== prop) : [...c.properties, prop],
                                        }))}>
                                        {prop}
                                    </button>
                                ))}
                            </div>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    disabled={!composer.expression.trim()} onClick={savePercept}>Keep this percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setComposer(null)}>Later</button>
                            </div>
                            <p className="diff-insp-hint">
                                Grounded in: {composer.groundIds.map((id) => groundTitle(groundById(id), regions)).join(' · ')}
                            </p>
                        </div>
                    )}

                    {/* the tray — accumulative multi-ground percepts */}
                    {tray.size > 0 && !composer && (
                        <div className="diff-insp-tray">
                            <span className="diff-eyebrow">Gathered · {tray.size}</span>
                            <p className="diff-insp-hint">{[...tray].map((id) => groundTitle(groundById(id), regions)).join(' · ')}</p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={composeFromTray}>Compose a percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setTray(new Set())}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* picked regions (Select) */}
                    {!composer && !hasDrawDraft && !composing && picked.size > 0 && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">{picked.size} part{picked.size !== 1 ? 's' : ''} gathered</span>
                            <p className="diff-insp-hint">{[...picked].map((id) => regionName(regions.find((r) => r.id === id))).join(' · ')}</p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={composeFromRegions}>Compose a percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setPicked(new Set())}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* a single selected Ground */}
                    {!composer && !hasDrawDraft && !composing && picked.size === 0 && selectedGround && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">{selectedGround.ground_type} · evidence</span>
                            <h3 className="diff-insp-name">{groundTitle(selectedGround, regions)}</h3>
                            <div className="diff-insp-meta">
                                <span className="diff-chip">{selectedGround.actor}</span>
                                {selectedGround.detector && <span className="diff-chip">{selectedGround.detector}</span>}
                                {selectedGround.ground_type === 'frame' && (selectedGround.evidence_ids || []).length > 0 && (
                                    <span className="diff-chip diff-chip--dim">{selectedGround.evidence_ids.length} inside</span>
                                )}
                            </div>
                            {selectedGround.ground_type === 'frame' && (
                                <p className="diff-insp-hint">
                                    The whole image as one piece of evidence — for a percept about the
                                    whole composition, not a single part. The brackets mark its edge.
                                </p>
                            )}
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={() => openComposer(selectedGround.id)}>Compose a percept</button>
                                <button type="button" className="diff-quiet" onClick={() => addToTray(selectedGround.id)}>
                                    <Plus size={13} /> Gather
                                </button>
                                <button type="button" className="diff-quiet" onClick={() => removeGround(selectedGround.id)}>Remove</button>
                            </div>
                        </div>
                    )}

                    {!composer && !hasDrawDraft && !composing && picked.size === 0 && !selectedGround && !selected && grounds.length === 0 && tray.size === 0 && (
                        <div className="diff-insp-empty">
                            <span className="diff-eyebrow">Inspector</span>
                            <p>Nothing under attention. Select parts, take the Brush (<kbd>B</kbd>) or Trace
                                (<kbd>T</kbd>), or press <kbd>O</kbd> for the untouched photograph.</p>
                        </div>
                    )}

                    {/* the grounds so far — clickable to select, ⁘/⤝ to gather */}
                    {grounds.length > 0 && !composer && (
                        <div className="diff-insp-grounds">
                            <span className="diff-eyebrow">Grounds</span>
                            {grounds.map((g) => {
                                const inDraft = composing && memberSet.has(g.id);
                                return (
                                    <div key={g.id}
                                        className={`diff-ground-row${selectedGroundId === g.id ? ' is-sel' : ''}${inDraft ? ' is-member' : ''}`}
                                        onMouseEnter={() => setHoveredGroundId(g.id)}
                                        onMouseLeave={() => setHoveredGroundId(null)}>
                                        <button type="button" className="diff-ground-main"
                                            onClick={() => (composing ? toggleMember(g.id) : selectGround(g.id === selectedGroundId ? null : g.id))}>
                                            <span className="diff-ground-glyph" aria-hidden>
                                                {composing ? (inDraft ? '☑' : '☐') : (GROUND_GLYPH[g.ground_type] || '◇')}
                                            </span>
                                            <span className="diff-ground-name">{groundTitle(g, regions)}</span>
                                        </button>
                                        {!composing && (
                                            <button type="button" className="diff-ground-add" title="Gather for a percept"
                                                onClick={(e) => { e.stopPropagation(); addToTray(g.id); }}>
                                                <Plus size={12} />
                                            </button>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* the percepts so far — each replays on demand */}
                    {expressionPercepts.length > 0 && (
                        <div className="diff-insp-percepts">
                            <span className="diff-eyebrow">Percepts</span>
                            {expressionPercepts.map((p) => (
                                <div key={p.id} className="diff-percept-row">
                                    <button type="button" className="diff-icon-btn diff-percept-play"
                                        title="Replay this noticing on the image" onClick={() => playRecall(p.id)}>
                                        <Play size={12} />
                                    </button>
                                    <span className="diff-percept-text">{p.expression}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {detachedGrounds.length > 0 && (
                        <div className="diff-insp-detached">
                            <span className="diff-eyebrow">Detached evidence</span>
                            {detachedGrounds.map((g) => (
                                <p key={g.id} className="diff-detached-row">
                                    {g.label || g.ground_type} — its part was replaced by a re-dissect
                                </p>
                            ))}
                        </div>
                    )}

                    <footer className="diff-insp-counts">
                        {regions.length} part{regions.length !== 1 ? 's' : ''} ·{' '}
                        {grounds.length} ground{grounds.length !== 1 ? 's' : ''} ·{' '}
                        {expressionPercepts.length} percept{expressionPercepts.length !== 1 ? 's' : ''}
                    </footer>
                </aside>
            </div>
        </div>
    );
}
