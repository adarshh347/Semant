import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Scan, Star, Sparkles, Plus, Eye, Check } from 'lucide-react';
import { API_URL } from '../config/api';
import './VisualPane.css';

const BASE = `${API_URL}/api/v1/posts`;
const AUTOSAVE_MS = 800;

// Sūkṣma subdivision modes. "General" is always available; the rest steer the
// fine pass toward a particular kind of anatomy.
const MODES = [
    { key: 'general', label: 'General' },
    { key: 'garment', label: 'Garments' },
    { key: 'body', label: 'Body' },
    { key: 'texture', label: 'Textures' },
    { key: 'material', label: 'Materials' },
    { key: 'composition', label: 'Composition' },
];

const isAnchor = (r) => (r.depth || 0) === 0;
const isCreator = (r) => r.actor === 'creator';
const hasNote = (r) => !!(r.user_note || '').trim();

/**
 * The unified Visual pane (Darshan Track D).
 *
 * One live surface where you see an image, mark its parts, and say how each affects
 * you. It replaces three disconnected homes: the neon pixel-space BoundingBoxEditor,
 * the auto-anatomy surface trapped in a modal, and the Aletheia reading exiled to a
 * tab on the far side of the split.
 *
 * Everything lives on one normalized SVG (`viewBox 0 0 100 100`), so auto polygons and
 * hand-drawn creator rects are the same kind of thing — a `Region` — and marks survive
 * a resize instead of drifting, which the old pixel boxes did.
 *
 * The mess problem is real once Fashionpedia yields dozens of parts, so nothing is
 * shown all at once: anchors first, fine parts on demand, labels only where you're
 * looking, and selecting anything dims everything else.
 */
export default function VisualPane({ post, showRegions = true, onPostChange }) {
    const [regions, setRegions] = useState(post.region_annotations || []);
    const [selectedId, setSelectedId] = useState(null);
    const [hoveredId, setHoveredId] = useState(null);
    const [lensRegionIds, setLensRegionIds] = useState(null); // Set | null (reading-strip hover)

    const [detecting, setDetecting] = useState(false);
    const [mode, setMode] = useState('general');
    const [lens, setLens] = useState('');
    const [error, setError] = useState('');

    const [revealFine, setRevealFine] = useState(false);
    const [catFilter, setCatFilter] = useState(new Set());
    const [movedOnly, setMovedOnly] = useState(false);

    const [drawing, setDrawing] = useState(false);      // "+ mark" armed
    const [draft, setDraft] = useState(null);           // rect being dragged

    const [aletheia, setAletheia] = useState(post.local_context?.aletheia || null);
    const [reading, setReading] = useState(false);
    const [commentary, setCommentary] = useState(post.local_context?.commentary || '');
    const [feedPersona, setFeedPersona] = useState(true);
    const [ctxBusy, setCtxBusy] = useState(false);

    const [saveState, setSaveState] = useState('idle');  // idle | saving | saved
    const saveTimer = useRef(null);
    const stageRef = useRef(null);
    const regionsRef = useRef(regions);
    regionsRef.current = regions;

    // --- persistence ---------------------------------------------------------------
    // Autosave on blur, debounced (locked D3). The endpoint takes the whole array, so
    // a burst of edits must collapse into one write rather than racing each other.
    const persist = useCallback(async (next) => {
        setSaveState('saving');
        try {
            const res = await fetch(`${BASE}/${post.id}/region-annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regions: next, feed_to_persona: feedPersona }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            onPostChange?.(data.post);
            setSaveState('saved');
            setTimeout(() => setSaveState(s => (s === 'saved' ? 'idle' : s)), 1600);
        } catch {
            setError('Could not save your marks.');
            setSaveState('idle');
        }
    }, [post.id, feedPersona, onPostChange]);

    const scheduleSave = useCallback(() => {
        clearTimeout(saveTimer.current);
        saveTimer.current = setTimeout(() => persist(regionsRef.current), AUTOSAVE_MS);
    }, [persist]);

    // A pending edit must not be lost because the pane unmounted.
    useEffect(() => () => clearTimeout(saveTimer.current), []);

    const update = (id, patch, { save = false } = {}) => {
        setRegions(rs => {
            const next = rs.map(r => (r.id === id ? { ...r, ...patch } : r));
            regionsRef.current = next;
            return next;
        });
        if (save) scheduleSave();
    };

    const togglePriority = (id) => {
        const r = regions.find(x => x.id === id);
        if (!r) return;
        update(id, { prioritised: !r.prioritised, weight: !r.prioritised ? (r.weight || 60) : 0 });
        setSelectedId(id);
        scheduleSave();   // one tap is the shallow rung of the ladder — it must stick on its own
    };

    // --- detection -----------------------------------------------------------------
    const detect = useCallback(async (opts = {}) => {
        setDetecting(true); setError('');
        try {
            const res = await fetch(`${BASE}/${post.id}/detect-regions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: opts.mode ?? mode, lens: opts.lens ?? lens,
                    coarse_only: !!opts.coarseOnly,
                }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setRegions(data.regions || []);
            regionsRef.current = data.regions || [];
            setSelectedId(null);
        } catch {
            setError('Detection failed — is the backend running?');
        } finally { setDetecting(false); }
    }, [post.id, mode, lens]);

    // --- the reading (Aletheia, deep) ----------------------------------------------
    const runAletheia = async () => {
        setReading(true); setError('');
        try {
            const res = await fetch(`${BASE}/${post.id}/aletheia-read`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ depth: 'deep' }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setAletheia(data.aletheia);
        } catch {
            setError('Aletheia could not read this image.');
        } finally { setReading(false); }
    };

    const saveLocalContext = async () => {
        setCtxBusy(true); setError('');
        try {
            const res = await fetch(`${BASE}/${post.id}/local-context`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ commentary, aletheia, feed_to_persona: feedPersona }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            onPostChange?.(data.post);
        } catch {
            setError('Could not save the context.');
        } finally { setCtxBusy(false); }
    };

    // --- freehand creator marks (D2: lightweight, for what detection misses) --------
    // Normalized from the outset: a creator rect is a Region like any other, so it can
    // never drift against the image the way the retired pixel boxes did.
    const pointAt = (e) => {
        const box = stageRef.current.getBoundingClientRect();
        return {
            x: Math.min(1, Math.max(0, (e.clientX - box.left) / box.width)),
            y: Math.min(1, Math.max(0, (e.clientY - box.top) / box.height)),
        };
    };

    const onStageDown = (e) => {
        if (!drawing) return;
        const p = pointAt(e);
        setDraft({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    };
    const onStageMove = (e) => {
        if (!draft) return;
        const p = pointAt(e);
        setDraft(d => ({ ...d, x1: p.x, y1: p.y }));
    };
    const onStageUp = () => {
        if (!draft) return;
        const box = {
            x: Math.min(draft.x0, draft.x1), y: Math.min(draft.y0, draft.y1),
            w: Math.abs(draft.x1 - draft.x0), h: Math.abs(draft.y1 - draft.y0),
        };
        setDraft(null);
        setDrawing(false);
        if (box.w < 0.01 || box.h < 0.01) return;   // a stray click is not a mark
        const region = {
            id: `reg_creator_${Date.now()}`,
            actor: 'creator', detector: null, box, label: 'my mark',
            category: 'other', material: '', description: '', attributes: [],
            depth: 0, prioritised: false, weight: 0, user_note: '',
        };
        const next = [...regionsRef.current, region];
        setRegions(next); regionsRef.current = next;
        setSelectedId(region.id);
        scheduleSave();
    };

    // --- what is visible -----------------------------------------------------------
    const categories = useMemo(
        () => [...new Set(regions.map(r => r.category).filter(Boolean))].sort(),
        [regions],
    );

    const filtersActive = catFilter.size > 0 || movedOnly;

    const visible = useMemo(() => {
        let rs = regions;
        if (movedOnly) rs = rs.filter(r => r.prioritised || hasNote(r));
        if (catFilter.size) rs = rs.filter(r => catFilter.has(r.category));
        // Progressive coarse→fine: fine parts stay folded away until asked for, or when
        // a filter/selection is already narrowing the field.
        //
        // Two things always survive the fold, because hiding them would break the very
        // promises this pane makes. A part you have already prioritised or written a
        // note on must be there when you come back — "remember" means you SEE it, not
        // that a counter knows it. And a part the hovered lens cites must be on screen,
        // or the reading has nothing to point at. Explicit filters still win; only the
        // default folding yields.
        if (!revealFine && !filtersActive) {
            rs = rs.filter(r =>
                isAnchor(r) || r.id === selectedId || r.parent_id === selectedId
                || r.prioritised || hasNote(r) || lensRegionIds?.has(r.id));
        }
        return rs;
    }, [regions, movedOnly, catFilter, revealFine, filtersActive, selectedId, lensRegionIds]);

    const fineHidden = regions.filter(r => !isAnchor(r)).length
        - visible.filter(r => !isAnchor(r)).length;

    // Focus: an explicit selection, or the regions a hovered lens points at. Everything
    // else recedes — this is what keeps forty parts from screaming at once.
    const focusIds = useMemo(() => {
        if (lensRegionIds?.size) return lensRegionIds;
        if (hoveredId) return new Set([hoveredId]);
        if (selectedId) return new Set([selectedId]);
        return null;
    }, [lensRegionIds, hoveredId, selectedId]);

    const labelVisible = (r) =>
        focusIds?.has(r.id) || (!focusIds && (isAnchor(r) || r.prioritised)) || (filtersActive && !focusIds);

    const selected = regions.find(r => r.id === selectedId);
    const prioritisedCount = regions.filter(r => r.prioritised).length;
    const notedCount = regions.filter(hasNote).length;

    // The lens that speaks about the selected part — the reading, exactly where you comment.
    const lensForSelected = (aletheia?.lenses || []).find(
        l => (l.region_ids || []).includes(selectedId),
    );

    const anchors = visible.filter(isAnchor);
    const fine = visible.filter(r => !isAnchor(r));
    const grouped = anchors.map(a => ({ anchor: a, children: fine.filter(f => f.parent_id === a.id) }));
    const orphanFine = fine.filter(f => !anchors.some(a => a.id === f.parent_id));

    const shapeClass = (r) => [
        'vp-shape',
        isCreator(r) ? 'vp-shape--creator' : `vp-shape--${isAnchor(r) ? 'anchor' : 'fine'}`,
        r.prioritised ? 'is-pri' : '',
        selectedId === r.id ? 'is-sel' : '',
        focusIds && !focusIds.has(r.id) ? 'is-dim' : '',
    ].filter(Boolean).join(' ');

    return (
        <div className="vp">
            {/* ── stage: image + one normalized SVG for every region kind ───────────── */}
            <div className="vp-stage-wrap">
                <div
                    className={`vp-stage${drawing ? ' is-drawing' : ''}`}
                    ref={stageRef}
                    onMouseDown={onStageDown}
                    onMouseMove={onStageMove}
                    onMouseUp={onStageUp}
                    onMouseLeave={() => draft && onStageUp()}
                >
                    <img src={post.photo_url} alt="" referrerPolicy="no-referrer" />

                    {showRegions && (
                        <svg className="vp-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                            {[...anchors, ...fine].map(r => {
                                const poly = Array.isArray(r.polygon) && r.polygon.length > 2;
                                const common = {
                                    className: shapeClass(r),
                                    vectorEffect: 'non-scaling-stroke',
                                    onClick: () => setSelectedId(r.id),
                                    onMouseEnter: () => setHoveredId(r.id),
                                    onMouseLeave: () => setHoveredId(null),
                                };
                                if (poly) {
                                    return <polygon key={r.id} {...common}
                                        points={r.polygon.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')} />;
                                }
                                const b = r.box || {};
                                return <rect key={r.id} {...common}
                                    x={b.x * 100} y={b.y * 100} width={b.w * 100} height={b.h * 100} />;
                            })}
                            {draft && (
                                <rect className="vp-draft"
                                    x={Math.min(draft.x0, draft.x1) * 100} y={Math.min(draft.y0, draft.y1) * 100}
                                    width={Math.abs(draft.x1 - draft.x0) * 100}
                                    height={Math.abs(draft.y1 - draft.y0) * 100}
                                    vectorEffect="non-scaling-stroke" />
                            )}
                        </svg>
                    )}

                    {/* saved state, visible on the image itself: ★ prioritised, • has a note */}
                    {showRegions && visible.filter(hasNote).map(r => (
                        <span key={`dot-${r.id}`} className="vp-note-dot"
                            title={r.user_note}
                            style={{ left: `${(r.box.x + r.box.w) * 100}%`, top: `${r.box.y * 100}%` }}
                            onClick={() => setSelectedId(r.id)} />
                    ))}

                    {showRegions && visible.filter(labelVisible).map(r => (
                        <span key={`lab-${r.id}`}
                            className={`vp-label${isAnchor(r) ? '' : ' vp-label--fine'}`
                                + `${r.prioritised ? ' is-pri' : ''}${selectedId === r.id ? ' is-sel' : ''}`}
                            style={{ left: `${r.box.x * 100}%`, top: `${r.box.y * 100}%` }}
                            onClick={() => setSelectedId(r.id)}>
                            {r.label}{r.prioritised ? ' ★' : ''}
                        </span>
                    ))}

                    {detecting && <div className="vp-busy"><span className="vp-spin" /> Dissecting…</div>}
                    {drawing && <div className="vp-draw-hint">Drag to mark a part detection missed</div>}
                </div>

                {/* ── reading strip, directly under the image ───────────────────────── */}
                <div className="vp-reading">
                    <div className="vp-block-head">
                        <span className="vp-kicker">Aletheia · the reading</span>
                        <button className="vp-ghost" onClick={runAletheia} disabled={reading}>
                            {reading ? <span className="vp-spin" /> : <Sparkles size={14} />}
                            {aletheia ? 'Re-read' : 'Read the image'}
                        </button>
                    </div>

                    {aletheia?.lenses?.length ? (
                        <>
                            <div className="vp-lenses">
                                {aletheia.lenses.map((l, i) => (
                                    <button key={i} type="button" className="vp-lens"
                                        onMouseEnter={() => setLensRegionIds(new Set(l.region_ids || []))}
                                        onMouseLeave={() => setLensRegionIds(null)}
                                        onClick={() => (l.region_ids || [])[0] && setSelectedId(l.region_ids[0])}
                                        title={(l.region_ids || []).length
                                            ? `Highlights ${l.region_ids.length} part(s)` : 'No parts cited'}>
                                        <span className="vp-lens-head">
                                            <span className="vp-lens-name">{l.name}</span>
                                            <span className="vp-lens-pct">{l.intensity ?? 0}</span>
                                        </span>
                                        <span className="vp-bar">
                                            <span className="vp-bar-fill"
                                                style={{ width: `${Math.max(0, Math.min(100, l.intensity ?? 0))}%` }} />
                                        </span>
                                        <span className="vp-lens-reading">{l.reading}</span>
                                        {l.evidence && <span className="vp-lens-ev">seen in: {l.evidence}</span>}
                                    </button>
                                ))}
                            </div>
                            {aletheia.tension && <p className="vp-foot"><strong>Tension</strong> — {aletheia.tension}</p>}
                            {aletheia.concealed && <p className="vp-foot"><strong>Concealed</strong> — {aletheia.concealed}</p>}
                        </>
                    ) : (
                        <p className="vp-muted">No reading yet — let Aletheia read the image, then hover a lens to see the parts it rests on.</p>
                    )}

                    <div className="vp-commentary">
                        <span className="vp-kicker">Your unconcealment</span>
                        <textarea className="vp-textarea"
                            placeholder="What does this image do to you? What does it withhold?"
                            value={commentary} onChange={e => setCommentary(e.target.value)} />
                        <div className="vp-ctx-actions">
                            {post.instagram_handle && (
                                <label className="vp-feed">
                                    <input type="checkbox" checked={feedPersona}
                                        onChange={e => setFeedPersona(e.target.checked)} />
                                    feed <strong>@{post.instagram_handle}</strong>
                                </label>
                            )}
                            <button className="vp-primary" onClick={saveLocalContext}
                                disabled={ctxBusy || (!commentary.trim() && !aletheia)}>
                                {ctxBusy ? <span className="vp-spin" /> : <Check size={14} />} Attach context
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── side: verbs, filters, parts, and the selected-part editor ─────────── */}
            <aside className="vp-side">
                <div className="vp-verbs">
                    <div className="vp-modes">
                        {MODES.map(m => (
                            <button key={m.key} className={`vp-mode${mode === m.key ? ' on' : ''}`}
                                disabled={detecting}
                                onClick={() => { setMode(m.key); detect({ mode: m.key }); }}>{m.label}</button>
                        ))}
                    </div>
                    <div className="vp-lens-row">
                        <input className="vp-input" value={lens} onChange={e => setLens(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && detect()}
                            placeholder="Intention (optional): the way the fabric folds…" />
                        <button className="vp-primary" onClick={() => detect()} disabled={detecting}>
                            <Sparkles size={14} /> Dissect
                        </button>
                    </div>
                    <div className="vp-verb-row">
                        <button className="vp-ghost" onClick={() => detect({ coarseOnly: true })} disabled={detecting}>
                            <Scan size={14} /> Coarse only
                        </button>
                        <button className={`vp-ghost${drawing ? ' on' : ''}`} onClick={() => setDrawing(d => !d)}>
                            <Plus size={14} /> {drawing ? 'Cancel mark' : 'Mark a part'}
                        </button>
                        <span className={`vp-save-state vp-save-state--${saveState}`}>
                            {saveState === 'saving' && 'saving…'}
                            {saveState === 'saved' && <><Check size={12} /> saved</>}
                        </span>
                    </div>
                </div>

                {/* filters — the antidote to Fashionpedia's volume */}
                {(categories.length > 1 || prioritisedCount > 0) && (
                    <div className="vp-filters">
                        <button className={`vp-chip${movedOnly ? ' on' : ''}`} onClick={() => setMovedOnly(v => !v)}>
                            <Star size={11} fill={movedOnly ? 'currentColor' : 'none'} /> moved me
                        </button>
                        {categories.map(c => (
                            <button key={c} className={`vp-chip${catFilter.has(c) ? ' on' : ''}`}
                                onClick={() => setCatFilter(s => {
                                    const n = new Set(s); n.has(c) ? n.delete(c) : n.add(c); return n;
                                })}>{c}</button>
                        ))}
                        {filtersActive && (
                            <button className="vp-chip vp-chip--clear"
                                onClick={() => { setCatFilter(new Set()); setMovedOnly(false); }}>clear</button>
                        )}
                    </div>
                )}

                <div className="vp-list">
                    {!regions.length && !detecting && <p className="vp-muted">No parts yet — dissect the image.</p>}
                    {grouped.map(({ anchor, children }) => (
                        <div key={anchor.id} className="vp-group">
                            <Row r={anchor} {...{ selectedId, setSelectedId, togglePriority, setHoveredId }} />
                            {children.map(c => (
                                <Row key={c.id} r={c} indent {...{ selectedId, setSelectedId, togglePriority, setHoveredId }} />
                            ))}
                        </div>
                    ))}
                    {orphanFine.map(c => (
                        <Row key={c.id} r={c} {...{ selectedId, setSelectedId, togglePriority, setHoveredId }} />
                    ))}

                    {fineHidden > 0 && (
                        <button className="vp-reveal" onClick={() => setRevealFine(true)}>
                            <Eye size={13} /> Reveal {fineHidden} more part{fineHidden !== 1 ? 's' : ''}
                        </button>
                    )}
                </div>

                {selected ? (
                    <div className="vp-editor">
                        <div className="vp-editor-head">
                            <strong>{selected.label}</strong>
                            <button className={`vp-pri${selected.prioritised ? ' on' : ''}`}
                                onClick={() => togglePriority(selected.id)}>
                                <Star size={13} fill={selected.prioritised ? 'currentColor' : 'none'} />
                                {selected.prioritised ? 'Affected me' : 'Mark as affecting'}
                            </button>
                        </div>
                        <div className="vp-tags">
                            {selected.category && <span className="vp-tag">{selected.category}</span>}
                            {selected.material && <span className="vp-tag vp-tag--mat">{selected.material}</span>}
                            {isCreator(selected) && <span className="vp-tag vp-tag--mine">your mark</span>}
                            {(selected.attributes || []).slice(0, 4).map(a => (
                                <span key={a} className="vp-tag vp-tag--attr">{a}</span>
                            ))}
                        </div>

                        {/* the reading, exactly where you comment */}
                        {lensForSelected && (
                            <p className="vp-lens-hint">
                                <strong>{lensForSelected.name}</strong> reads this as — {lensForSelected.reading}
                            </p>
                        )}

                        {selected.prioritised && (
                            <div className="vp-weight">
                                <label>Intensity <strong>{selected.weight || 0}</strong></label>
                                <input type="range" min="0" max="100" value={selected.weight || 0}
                                    onChange={e => update(selected.id, { weight: Number(e.target.value) })}
                                    onMouseUp={scheduleSave} onKeyUp={scheduleSave} />
                            </div>
                        )}

                        <textarea className="vp-note"
                            placeholder={`How does “${selected.label}” affect you? What does it do?`}
                            value={selected.user_note || ''}
                            onChange={e => update(selected.id, { user_note: e.target.value })}
                            onBlur={scheduleSave} />
                    </div>
                ) : (
                    <p className="vp-muted vp-pick">Select a part to say how it affects you.</p>
                )}

                <div className="vp-counts">
                    <span>{prioritisedCount} prioritised</span>
                    <span>{notedCount} noted</span>
                    <span>{regions.length} parts</span>
                </div>
                {error && <p className="vp-error">{error}</p>}
            </aside>
        </div>
    );
}

function Row({ r, indent, selectedId, setSelectedId, togglePriority, setHoveredId }) {
    return (
        <div
            className={`vp-row${indent ? ' vp-row--child' : ''}${selectedId === r.id ? ' is-sel' : ''}${r.prioritised ? ' is-pri' : ''}`}
            onClick={() => setSelectedId(r.id)}
            onMouseEnter={() => setHoveredId(r.id)}
            onMouseLeave={() => setHoveredId(null)}
        >
            <button className="vp-star" title="This affected me"
                onClick={(e) => { e.stopPropagation(); togglePriority(r.id); }}>
                <Star size={14} fill={r.prioritised ? 'currentColor' : 'none'} />
            </button>
            <span className="vp-row-meta">
                <span className="vp-row-label">{r.label}</span>
                <span className="vp-row-cat">{r.category}{r.material ? ` · ${r.material}` : ''}</span>
            </span>
            {hasNote(r) && <span className="vp-row-dot" title="has a note" />}
        </div>
    );
}
