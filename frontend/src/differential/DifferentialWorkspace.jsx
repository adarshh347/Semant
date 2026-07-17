import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ArrowLeft, MousePointer2, Brush, PenTool, Group, Waypoints, Frame, Eye, Check,
    Play, Undo2, X,
} from 'lucide-react';
import RegionOverlay from '../components/RegionOverlay';
import GroundLayers from './GroundLayers';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from './useStageGeometry';
import { makeGround, resolveGround } from './grounds';
import { useRecallPlayer } from './recall';
import './DifferentialWorkspace.css';

/**
 * Differential — the dedicated percept-construction workspace (v1).
 *
 * A full-workspace MODE inside PostDetailPage, not a route: unsaved Manuscript
 * content lives in PostDetailPage state, and a route change would unmount and
 * silently lose it. The Chiasm shell stays mounted (hidden) underneath.
 *
 * Increment A shipped the shell + architecture. Increment B ships the first
 * full circulation: Brush → Soft Field Ground → composer → expression Percept
 * → /percept Mention (in Chiasm) → recall. Trace/Collect/Connect/Frame land
 * with C–D.
 */

const TOOLS = [
    { key: 'select', label: 'Select', icon: MousePointer2, ready: true, hint: 'Point at evidence' },
    { key: 'brush', label: 'Brush', icon: Brush, ready: true, hint: 'Soft Field — paint where the light lives' },
    { key: 'trace', label: 'Trace', icon: PenTool, ready: false, hint: 'Path · Boundary' },
    { key: 'collect', label: 'Collect', icon: Group, ready: false, hint: 'Constellation' },
    { key: 'connect', label: 'Connect', icon: Waypoints, ready: false, hint: 'Relation' },
    { key: 'frame', label: 'Frame', icon: Frame, ready: false, hint: 'The whole image' },
];

export const PERCEPT_PROPERTIES = [
    'light', 'colour', 'material', 'movement', 'composition',
    'attention', 'atmosphere', 'repetition', 'contrast',
];

const regionName = (r) => r?.label || r?.part || r?.category || 'part';

const groundTitle = (g) => {
    if (g.label) return g.label;
    switch (g.ground_type) {
        case 'field': return `Soft field · ${(g.strokes || []).length} stroke${(g.strokes || []).length !== 1 ? 's' : ''}`;
        case 'region': return 'Region';
        default: return g.ground_type;
    }
};

// Minimum normalized pointer travel before we append another sample.
const MIN_SAMPLE_DIST = 0.004;

export default function DifferentialWorkspace({ post, store, onExit }) {
    const [tool, setTool] = useState('select');
    const [untouched, setUntouched] = useState(false); // O — the image, unannotated
    const [brushRadius, setBrushRadius] = useState(0.045);
    const [draftStrokes, setDraftStrokes] = useState([]);   // committed-to-draft strokes
    const [liveStroke, setLiveStroke] = useState(null);     // the stroke under the pointer
    const [hoverPt, setHoverPt] = useState(null);           // brush cursor ring
    // The composer — "What do you notice?" Opens after a Ground commits
    // (immediate rhythm); closing it never destroys the Ground (accumulative).
    const [composer, setComposer] = useState(null);         // { groundId, expression, properties }
    const stageRef = useRef(null);
    const drawingRef = useRef(false);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);

    const {
        regions, selectedId, selectRegion, hoveredId, setHoveredId,
        grounds, percepts, saveState, metaSaveState,
        addGround, removeGround, selectedGroundId, selectGround,
        setHoveredGroundId, focusGroundIds,
        addExpressionPercept, playRecall, clearRecall, recall,
    } = store;

    const recallPlayer = useRecallPlayer(store);

    const expressionPercepts = useMemo(
        () => (percepts || []).filter((p) => String(p.id || '').startsWith('pctx_')),
        [percepts],
    );

    const draftAll = useMemo(
        () => (liveStroke ? [...draftStrokes, liveStroke] : draftStrokes),
        [draftStrokes, liveStroke],
    );

    // ── brush gestures ────────────────────────────────────────────────────────
    const onStagePointerDown = (e) => {
        if (tool !== 'brush' || untouched) return;
        const p = pointerToNormalized(e, stageRef.current, content);
        if (!p) return;
        e.currentTarget.setPointerCapture?.(e.pointerId);
        drawingRef.current = true;
        setLiveStroke({
            points: [[p.x, p.y, e.pressure || 0]],
            radius: brushRadius,
            strength: 0.8,
            op: e.altKey ? 'sub' : 'add',
        });
    };

    const onStagePointerMove = (e) => {
        if (tool === 'brush') {
            const p = pointerToNormalized(e, stageRef.current, content);
            setHoverPt(p);
            if (drawingRef.current && p) {
                setLiveStroke((s) => {
                    if (!s) return s;
                    const last = s.points[s.points.length - 1];
                    if (Math.hypot(p.x - last[0], p.y - last[1]) < MIN_SAMPLE_DIST) return s;
                    return { ...s, points: [...s.points, [p.x, p.y, e.pressure || 0]] };
                });
            }
        }
    };

    const endStroke = useCallback(() => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        setLiveStroke((s) => {
            if (s && s.points.length > 1) setDraftStrokes((d) => [...d, s]);
            return null;
        });
    }, []);

    const undoStroke = useCallback(() => setDraftStrokes((d) => d.slice(0, -1)), []);
    const clearDraft = useCallback(() => { setDraftStrokes([]); setLiveStroke(null); drawingRef.current = false; }, []);

    /** Commit the draft as a field Ground, then invite the noticing. */
    const commitField = useCallback(() => {
        if (!draftStrokes.length) return;
        const ground = addGround(makeGround('field', { strokes: draftStrokes }));
        clearDraft();
        selectGround(ground.id);
        setComposer({ groundId: ground.id, expression: '', properties: [] });
    }, [draftStrokes, addGround, clearDraft, selectGround]);

    const savePercept = useCallback(() => {
        if (!composer) return;
        const expression = composer.expression.trim();
        if (!expression) return;
        const p = addExpressionPercept({
            expression,
            ground_ids: [composer.groundId],
            properties: composer.properties,
        });
        setComposer(null);
        playRecall(p.id);   // the noticing performs itself once, as confirmation
    }, [composer, addExpressionPercept, playRecall]);

    // ── keyboard ─────────────────────────────────────────────────────────────
    useEffect(() => {
        const down = (e) => {
            if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return;
            if (e.code === 'KeyO' && !e.repeat) setUntouched(true);
            else if (e.key === 'Escape') {
                if (recall) clearRecall();
                else if (composer) setComposer(null);       // the Ground survives
                else if (draftAll.length) clearDraft();      // a draft is not yet a Ground
                else { selectRegion(null); selectGround(null); setHoveredId(null); }
            } else if (e.key === '[') setBrushRadius((r) => Math.max(0.012, r * 0.82));
            else if (e.key === ']') setBrushRadius((r) => Math.min(0.16, r * 1.22));
            else if (e.key.toLowerCase() === 'b') setTool('brush');
            else if (e.key.toLowerCase() === 'v') setTool('select');
            else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && draftStrokes.length) {
                e.preventDefault(); undoStroke();
            }
        };
        const up = (e) => { if (e.code === 'KeyO') setUntouched(false); };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
    }, [recall, clearRecall, composer, draftAll.length, draftStrokes.length, clearDraft, undoStroke, selectRegion, selectGround, setHoveredId]);

    const saving = saveState === 'saving' || metaSaveState === 'saving';
    const saved = saveState === 'saved' || metaSaveState === 'saved';

    const selected = regions.find((r) => r.id === selectedId) || null;
    const selectedGround = grounds.find((g) => g.id === selectedGroundId) || null;
    const focusId = hoveredId || selectedId;

    const detachedGrounds = grounds.filter(
        (g) => resolveGround(g, { regions, grounds })?.detached,
    );

    const composerGround = composer ? grounds.find((g) => g.id === composer.groundId) : null;

    const brushing = tool === 'brush' && !untouched;

    return (
        <div className="diff-root" data-tool={tool}>
            {/* ── top bar — compact: return · identity · image state · saves ── */}
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
                    <button type="button"
                        className={`diff-untouched${untouched ? ' on' : ''}`}
                        onClick={() => setUntouched(u => !u)}
                        title="See the untouched image (hold O)">
                        <Eye size={14} /> <span>Untouched</span>
                    </button>
                    <span className={`diff-save diff-save--${saving ? 'saving' : saved ? 'saved' : 'idle'}`}>
                        {saving && 'saving…'}
                        {!saving && saved && <><Check size={12} /> saved</>}
                    </span>
                </div>
            </header>

            <div className="diff-body">
                {/* ── tool rail — L5: inline tools, no box ── */}
                <nav className="diff-tools" aria-label="Perceptual operations">
                    {TOOLS.map(({ key, label, icon: Icon, ready, hint }) => (
                        <button key={key} type="button"
                            className={`diff-tool${tool === key ? ' on' : ''}`}
                            disabled={!ready}
                            aria-pressed={tool === key}
                            title={`${label} — ${hint}`}
                            onClick={() => ready && setTool(key)}>
                            <Icon size={16} />
                            <span className="diff-tool-label">{label}</span>
                        </button>
                    ))}
                </nav>

                {/* ── stage — image-dominant; every layer shares the geometry ── */}
                <main className="diff-stage-col">
                    <div className={
                        `diff-stage${untouched ? ' is-untouched' : ''}`
                        + `${brushing ? ' is-brushing' : ''}`
                        + `${recallPlayer.receding ? ' is-recalling' : ''}`}
                        ref={stageRef}
                        style={natural ? { '--diff-ar': `${natural.w} / ${natural.h}` } : undefined}
                        onPointerDown={onStagePointerDown}
                        onPointerMove={onStagePointerMove}
                        onPointerUp={endStroke}
                        onPointerLeave={() => { endStroke(); setHoverPt(null); }}>
                        <img src={post.photo_url} alt="" referrerPolicy="no-referrer" onLoad={onImgLoad} />
                        {!untouched && (
                            <>
                                <RegionOverlay
                                    natural={natural}
                                    regions={regions}
                                    viewMap="quiet"
                                    selectedId={selectedId}
                                    activeId={hoveredId}
                                    focusId={focusId}
                                    onSelect={tool === 'select' ? selectRegion : undefined}
                                    onActivate={tool === 'select' ? setHoveredId : undefined}
                                    className="diff-svg"
                                />
                                <GroundLayers
                                    grounds={grounds}
                                    content={content}
                                    focusGroundIds={focusGroundIds}
                                    recall={recallPlayer.active ? recallPlayer : null}
                                    draftStrokes={draftAll}
                                />
                            </>
                        )}
                        {/* brush cursor — a quiet ring, dashed while subtracting */}
                        {brushing && hoverPt && content && (
                            <span className="diff-brush-cursor" style={{
                                left: content.x + hoverPt.x * content.w,
                                top: content.y + hoverPt.y * content.h,
                                width: brushRadius * content.w * 2,
                                height: brushRadius * content.w * 2,
                            }} />
                        )}
                        {/* recall caption — the expression, spoken over the image */}
                        {recallPlayer.caption && (
                            <p className="diff-recall-caption">{recallPlayer.caption}</p>
                        )}
                    </div>
                    <p className="diff-stage-hint">
                        {untouched
                            ? 'The untouched image. Release O to see your evidence again.'
                            : tool === 'brush'
                                ? 'Paint where it lives. [ and ] size the brush · hold ⌥ to lift paint away · Esc clears the draft.'
                                : 'Select a part, or take the Brush (B) and paint a soft field of attention.'}
                    </p>
                </main>

                {/* ── inspector — contextual, quiet ── */}
                <aside className="diff-inspector">
                    {/* draft — editable before it becomes evidence */}
                    {draftAll.length > 0 && (
                        <div className="diff-insp-draft">
                            <span className="diff-eyebrow">Draft field</span>
                            <p className="diff-insp-hint">{draftAll.length} stroke{draftAll.length !== 1 ? 's' : ''} — still yours to shape.</p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={commitField}>
                                    Keep this field
                                </button>
                                <button type="button" className="diff-quiet" onClick={undoStroke} title="Undo the last stroke (⌘Z)">
                                    <Undo2 size={13} /> Undo
                                </button>
                                <button type="button" className="diff-quiet" onClick={clearDraft}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* composer — what do you notice? */}
                    {composer && (
                        <div className="diff-composer">
                            <div className="diff-composer-head">
                                <span className="diff-eyebrow">Percept</span>
                                <button type="button" className="diff-icon-btn" onClick={() => setComposer(null)}
                                    title="Later — the field stays; compose when ready">
                                    <X size={13} />
                                </button>
                            </div>
                            <p className="diff-composer-ask">What do you notice?</p>
                            <textarea
                                autoFocus
                                className="diff-composer-input"
                                placeholder="Say it as you saw it…"
                                value={composer.expression}
                                onChange={(e) => setComposer((c) => ({ ...c, expression: e.target.value }))}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); savePercept(); }
                                    if (e.key === 'Escape') { e.stopPropagation(); setComposer(null); }
                                }}
                            />
                            <div className="diff-composer-props">
                                {PERCEPT_PROPERTIES.map((prop) => (
                                    <button key={prop} type="button"
                                        className={`diff-prop${composer.properties.includes(prop) ? ' on' : ''}`}
                                        onClick={() => setComposer((c) => ({
                                            ...c,
                                            properties: c.properties.includes(prop)
                                                ? c.properties.filter((x) => x !== prop)
                                                : [...c.properties, prop],
                                        }))}>
                                        {prop}
                                    </button>
                                ))}
                            </div>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    disabled={!composer.expression.trim()} onClick={savePercept}>
                                    Keep this percept
                                </button>
                                <button type="button" className="diff-quiet" onClick={() => setComposer(null)}>
                                    Later
                                </button>
                            </div>
                            {composerGround && (
                                <p className="diff-insp-hint">Grounded in: {groundTitle(composerGround)}</p>
                            )}
                        </div>
                    )}

                    {/* selection — a part, or a ground */}
                    {!composer && selectedGround && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">{selectedGround.ground_type} · evidence</span>
                            <h3 className="diff-insp-name">{groundTitle(selectedGround)}</h3>
                            <div className="diff-insp-meta">
                                <span className="diff-chip">{selectedGround.actor}</span>
                                {selectedGround.detector && <span className="diff-chip">{selectedGround.detector}</span>}
                            </div>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    onClick={() => setComposer({ groundId: selectedGround.id, expression: '', properties: [] })}>
                                    Compose a percept
                                </button>
                                <button type="button" className="diff-quiet"
                                    onClick={() => removeGround(selectedGround.id)}>
                                    Remove
                                </button>
                            </div>
                        </div>
                    )}
                    {!composer && !selectedGround && selected && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">Region · evidence</span>
                            <h3 className="diff-insp-name">{regionName(selected)}</h3>
                            <div className="diff-insp-meta">
                                <span className="diff-chip">{selected.actor || 'auto'}</span>
                                {selected.detector && <span className="diff-chip">{selected.detector}</span>}
                                {selected.category && <span className="diff-chip diff-chip--dim">{selected.category}</span>}
                                {selected.material && <span className="diff-chip diff-chip--dim">{selected.material}</span>}
                            </div>
                            {(selected.user_note || '').trim() && (
                                <p className="diff-insp-note">“{selected.user_note}”</p>
                            )}
                        </div>
                    )}
                    {!composer && !selectedGround && !selected && draftAll.length === 0 && (
                        <div className="diff-insp-empty">
                            <span className="diff-eyebrow">Inspector</span>
                            <p>Nothing under attention. Take the Brush (<kbd>B</kbd>) and paint
                                where the image holds you, or press <kbd>O</kbd> for the untouched photograph.</p>
                        </div>
                    )}

                    {/* the grounds so far */}
                    {grounds.length > 0 && (
                        <div className="diff-insp-grounds">
                            <span className="diff-eyebrow">Grounds</span>
                            {grounds.map((g) => (
                                <button key={g.id} type="button"
                                    className={`diff-ground-row${selectedGroundId === g.id ? ' is-sel' : ''}`}
                                    onClick={() => selectGround(g.id === selectedGroundId ? null : g.id)}
                                    onMouseEnter={() => setHoveredGroundId(g.id)}
                                    onMouseLeave={() => setHoveredGroundId(null)}>
                                    <span className="diff-ground-glyph" aria-hidden>◐</span>
                                    <span className="diff-ground-name">{groundTitle(g)}</span>
                                </button>
                            ))}
                        </div>
                    )}

                    {/* the percepts so far — each replays on demand */}
                    {expressionPercepts.length > 0 && (
                        <div className="diff-insp-percepts">
                            <span className="diff-eyebrow">Percepts</span>
                            {expressionPercepts.map((p) => (
                                <div key={p.id} className="diff-percept-row">
                                    <button type="button" className="diff-icon-btn diff-percept-play"
                                        title="Replay this noticing on the image"
                                        onClick={() => playRecall(p.id)}>
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
