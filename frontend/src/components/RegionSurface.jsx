import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Sparkles, Star, Scan, Plus, Eye, Check, MoreHorizontal, AlertCircle, Expand } from 'lucide-react';
import { API_URL } from '../config/api';
import RegionOverlay from './RegionOverlay';
import RegionLightbox from './RegionLightbox';
import './RegionSurface.css';

const BASE = `${API_URL}/api/v1/posts`;
const AUTOSAVE_MS = 800;

// Sūkṣma subdivision modes. Backend machinery — demoted into a quiet menu, because the
// user feels the result, not the vocabulary the model was steered with.
const MODES = [
    { key: 'general', label: 'General' },
    { key: 'garment', label: 'Garments' },
    { key: 'body', label: 'Body' },
    { key: 'texture', label: 'Textures' },
    { key: 'material', label: 'Materials' },
    { key: 'composition', label: 'Composition' },
];

// Above this many regions the surface opens in the quiet map: 40 hairline outlines read
// as texture, 40 filled polygons read as noise.
const QUIET_THRESHOLD = 12;

const MAPS = [
    { key: 'quiet', label: 'Quiet', hint: 'Low-weight markers; hover to reveal a part' },
    { key: 'outline', label: 'Outline', hint: 'Exact polygon borders' },
    { key: 'focus', label: 'Focus', hint: 'The selected part; everything else recedes' },
];

const isAnchor = (r) => (r.depth || 0) === 0;
const hasNote = (r) => !!(r.user_note || '').trim();
const regionName = (r) => r.label || r.part || r.category || 'part';

/**
 * RegionSurface — the premium unified region view (Darshan Track D, Phase 1).
 *
 * Three problems drove this, all visible in Adarsh's screenshots:
 *
 *   1. **The overlay didn't sit on the image.** `preserveAspectRatio="none"` stretched
 *      the viewBox across the stage, while the <img> letterboxed inside it — so the
 *      "earrings" polygon landed on a cheekbone. Here the SVG carries the image's
 *      NATURAL pixel viewBox and letterboxes with `xMidYMid meet` inside the same box
 *      the image does. They cannot disagree.
 *
 *   2. **40 parts shout.** Three maps: quiet (hairline markers), outline (exact
 *      borders), focus (one part, the rest near-invisible). Plus the category filter,
 *      which is how numerosity actually splits.
 *
 *   3. **The panel was a control wall.** The taxonomy is machinery; it's now a quiet
 *      menu. What's foregrounded is the felt unit — a part, what the reading says of it,
 *      and what it does to you.
 *
 * Self-contained: it owns its data fetching and saving, responds to its OWN width via
 * container queries (a pane is not a viewport), and mounts anywhere.
 */
export default function RegionSurface({ post, aletheia = null, onPostChange, store = null }) {
    const [regionsInt, setRegionsInt] = useState(post.region_annotations || []);
    const [selectedIdInt, setSelectedIdInt] = useState(null);
    const [activeId, setActiveId] = useState(null);      // keyboard cursor / hover

    const [viewMap, setViewMap] = useState(
        (post.region_annotations || []).length > QUIET_THRESHOLD ? 'quiet' : 'outline');
    const [category, setCategory] = useState('all');
    const [revealFine, setRevealFine] = useState(false);

    const [mode, setMode] = useState('general');
    const [lens, setLens] = useState('');
    const [overflowOpen, setOverflowOpen] = useState(false);
    const [drawing, setDrawing] = useState(false);
    const [draft, setDraft] = useState(null);

    const [status, setStatus] = useState('idle');        // idle | detecting | error
    const [error, setError] = useState('');
    const [saveState, setSaveState] = useState('idle');  // idle | saving | saved

    const [natural, setNatural] = useState(null);        // {w,h} — the image's own pixels
    const [content, setContent] = useState(null);        // the rendered, letterboxed box
    const [fullscreen, setFullscreen] = useState(false); // Phase 2 — the lightbox

    const stageRef = useRef(null);
    const imgRef = useRef(null);
    const listRef = useRef(null);
    const saveTimer = useRef(null);
    const regionsRef = useRef(regionsInt);
    regionsRef.current = regionsInt;

    // ── Data layer ───────────────────────────────────────────────────────────
    // The shared store when mounted in Chiasm (the single source both panes read),
    // internal state when standalone (the lab). Selection + hover + regions live in
    // ONE place per mount; the store is the only channel to Manuscript.
    const regions = store ? store.regions : regionsInt;
    const selectedId = store ? store.selectedId : selectedIdInt;
    const setSelectedId = store ? store.selectRegion : setSelectedIdInt;
    const setHovered = store ? store.setHoveredId : () => {};
    const commitRegions = store
        ? store.setRegions
        : (next) => { regionsRef.current = typeof next === 'function' ? next(regionsRef.current) : next; setRegionsInt(regionsRef.current); };
    // A Percept is created only on a DELIBERATE attention signal — mark-affecting,
    // a note, a freehand mark, /part — never on hover or render. Idempotent (one
    // creator percept per region), so repeated signals don't multiply.
    const attend = store ? store.ensurePercept : () => {};
    // Move the keyboard/hover cursor AND tell the store what the eye is on (drives
    // the region→Manuscript highlight). This is a glance, not attention.
    const activate = (id) => { setActiveId(id); setHovered(id); };

    // --- geometry: where the image ACTUALLY is inside the stage ---------------------
    // `object-fit: contain` letterboxes. Labels and the freehand tool live in HTML, so
    // they need that rendered box in CSS pixels; the SVG gets it for free from the
    // matching viewBox + preserveAspectRatio.
    const measure = useCallback(() => {
        const stage = stageRef.current;
        if (!stage || !natural) return;
        const { width: sw, height: sh } = stage.getBoundingClientRect();
        if (!sw || !sh) return;
        const scale = Math.min(sw / natural.w, sh / natural.h);
        const dw = natural.w * scale;
        const dh = natural.h * scale;
        setContent({ x: (sw - dw) / 2, y: (sh - dh) / 2, w: dw, h: dh });
    }, [natural]);

    useEffect(() => {
        measure();
        const stage = stageRef.current;
        if (!stage) return;
        const ro = new ResizeObserver(measure);
        ro.observe(stage);
        return () => ro.disconnect();
    }, [measure]);

    const onImgLoad = (e) => {
        setNatural({ w: e.target.naturalWidth, h: e.target.naturalHeight });
    };

    // --- persistence: autosave on blur, debounced -----------------------------------
    const persistInt = useCallback(async (next) => {
        setSaveState('saving');
        try {
            const res = await fetch(`${BASE}/${post.id}/region-annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regions: next, feed_to_persona: true }),
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
    }, [post.id, onPostChange]);

    const scheduleSaveInt = useCallback(() => {
        clearTimeout(saveTimer.current);
        saveTimer.current = setTimeout(() => persistInt(regionsRef.current), AUTOSAVE_MS);
    }, [persistInt]);

    useEffect(() => () => clearTimeout(saveTimer.current), []);

    // When the store owns the data it also owns saving; the internal path is the
    // lab-standalone fallback.
    const scheduleSave = store ? store.scheduleSave : scheduleSaveInt;
    const update = store
        ? store.updateRegion
        : (id, patch) => commitRegions(rs => rs.map(r => (r.id === id ? { ...r, ...patch } : r)));

    const togglePriority = (id) => {
        const r = regions.find(x => x.id === id);
        if (!r) return;
        const next = !r.prioritised;
        update(id, { prioritised: next, weight: next ? (r.weight || 60) : 0 });
        setSelectedId(id);
        if (next) attend(r);   // marking a part as affecting IS attention → a Percept
        scheduleSave();   // one tap is the shallow rung — it must stick on its own
    };

    // --- detection -------------------------------------------------------------------
    const detect = useCallback(async (opts = {}) => {
        setStatus('detecting'); setError(''); setOverflowOpen(false);
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
            const next = data.regions || [];
            commitRegions(next);
            setSelectedId(null); activate(null);
            setViewMap(next.length > QUIET_THRESHOLD ? 'quiet' : 'outline');
            setStatus('idle');
        } catch {
            setError('Dissection failed — is the backend running?');
            setStatus('error');
        }
    }, [post.id, mode, lens]);

    // --- freehand creator marks (normalized from the outset) -------------------------
    const pointAt = (e) => {
        if (!content) return null;
        const box = stageRef.current.getBoundingClientRect();
        // Map the pointer into the IMAGE's box, not the stage's — outside it, no mark.
        const x = (e.clientX - box.left - content.x) / content.w;
        const y = (e.clientY - box.top - content.y) / content.h;
        return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
    };

    const onStageDown = (e) => {
        if (!drawing) return;
        const p = pointAt(e);
        if (p) setDraft({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    };
    const onStageMove = (e) => {
        if (!draft) return;
        const p = pointAt(e);
        if (p) setDraft(d => ({ ...d, x1: p.x, y1: p.y }));
    };
    const onStageUp = () => {
        if (!draft) return;
        const box = {
            x: Math.min(draft.x0, draft.x1), y: Math.min(draft.y0, draft.y1),
            w: Math.abs(draft.x1 - draft.x0), h: Math.abs(draft.y1 - draft.y0),
        };
        setDraft(null); setDrawing(false);
        if (box.w < 0.01 || box.h < 0.01) return;    // a stray click is not a mark
        const region = {
            id: `reg_creator_${Date.now()}`, actor: 'creator', detector: null, box,
            label: 'my mark', category: 'other', material: '', description: '',
            attributes: [], depth: 0, prioritised: false, weight: 0, user_note: '',
        };
        commitRegions(rs => [...rs, region]);
        setSelectedId(region.id);
        attend(region);   // a freehand mark is a deliberate act of attention → a Percept
        scheduleSave();
    };

    // --- what is visible --------------------------------------------------------------
    const categories = useMemo(
        () => [...new Set(regions.map(r => r.category).filter(Boolean))].sort(), [regions]);

    const filtering = category !== 'all';

    const visible = useMemo(() => {
        let rs = regions;
        if (filtering) rs = rs.filter(r => r.category === category);
        // Progressive coarse→fine. A part you already spoke to always survives the fold —
        // "remember" has to mean you SEE it — and so does anything the reading cites.
        if (!revealFine && !filtering) {
            rs = rs.filter(r => isAnchor(r) || r.id === selectedId || r.parent_id === selectedId
                || r.prioritised || hasNote(r));
        }
        return rs;
    }, [regions, filtering, category, revealFine, selectedId]);

    const hiddenFine = regions.filter(r => !isAnchor(r)).length
        - visible.filter(r => !isAnchor(r)).length;

    const focusId = activeId || selectedId;
    const selected = regions.find(r => r.id === selectedId);
    const prioritisedCount = regions.filter(r => r.prioritised).length;

    // The lens that speaks about a part — the reading, in the row, where you comment.
    const lensFor = useCallback((id) =>
        (aletheia?.lenses || []).find(l => (l.region_ids || []).includes(id)), [aletheia]);

    // A label shows when you're looking at that part, or when a filter already narrowed
    // the field. Never all at once.
    const labelVisible = (r) =>
        focusId === r.id || (filtering && !focusId) || (viewMap === 'outline' && r.prioritised);

    // --- keyboard: roving cursor through the parts -----------------------------------
    const onListKeyDown = (e) => {
        const ids = visible.map(r => r.id);
        if (!ids.length) return;
        const i = ids.indexOf(activeId);
        let next = null;
        if (e.key === 'ArrowDown') next = ids[Math.min(ids.length - 1, i < 0 ? 0 : i + 1)];
        else if (e.key === 'ArrowUp') next = ids[Math.max(0, i < 0 ? 0 : i - 1)];
        else if (e.key === 'Home') next = ids[0];
        else if (e.key === 'End') next = ids[ids.length - 1];
        else if (e.key === 'Enter' || e.key === ' ') {
            if (activeId) { e.preventDefault(); setSelectedId(activeId); }
            return;
        } else if (e.key === '*') { togglePriority(activeId); return; }
        else return;
        e.preventDefault();
        activate(next);
        listRef.current?.querySelector(`[data-rid="${next}"]`)?.scrollIntoView({ block: 'nearest' });
    };

    const busy = status === 'detecting';

    // Clicking the photograph itself (not a region, not while marking) opens it full
    // screen. Regions stop their own clicks, so selecting a part never triggers this.
    const onStageClick = (e) => {
        if (!drawing && e.target.tagName === 'IMG') setFullscreen(true);
    };

    return (
        <div className="rs-root">
            <div className="rs">
                {/* ── stage ─────────────────────────────────────────────────────────── */}
                <section className="rs-stage-col">
                    <div
                        className={`rs-stage${drawing ? ' is-drawing' : ''}`}
                        ref={stageRef}
                        // The stage takes the image's own aspect, so a portrait photo
                        // fills its box instead of floating in a wide letterbox.
                        style={natural ? { '--rs-ar': `${natural.w} / ${natural.h}` } : undefined}
                        onMouseDown={onStageDown}
                        onMouseMove={onStageMove}
                        onMouseUp={onStageUp}
                        onMouseLeave={() => draft && onStageUp()}
                        onClick={onStageClick}
                    >
                        <img ref={imgRef} src={post.photo_url} alt="" referrerPolicy="no-referrer"
                            onLoad={onImgLoad} />

                        {/* The overlay carries the image's own pixel space and letterboxes
                            exactly as the image does — shared with the lightbox. */}
                        <RegionOverlay
                            natural={natural} regions={visible} viewMap={viewMap}
                            selectedId={selectedId} activeId={activeId} focusId={focusId}
                            onSelect={setSelectedId} onActivate={activate} draft={draft}
                        />

                        {!drawing && (
                            <button className="rs-expand" onClick={() => setFullscreen(true)}
                                title="See the image full screen" aria-label="See the image full screen">
                                <Expand size={15} />
                            </button>
                        )}

                        {/* Labels + saved-state dots live in HTML, positioned against the
                            image's rendered box so they track the letterboxing too. */}
                        {content && visible.filter(hasNote).map(r => (
                            <span key={`dot-${r.id}`} className="rs-note-dot" title={r.user_note}
                                style={{
                                    left: content.x + (r.box.x + r.box.w) * content.w,
                                    top: content.y + r.box.y * content.h,
                                }}
                                onClick={() => setSelectedId(r.id)} />
                        ))}
                        {content && visible.filter(labelVisible).map(r => (
                            <span key={`lab-${r.id}`}
                                className={`rs-label${r.prioritised ? ' is-pri' : ''}${selectedId === r.id ? ' is-sel' : ''}`}
                                style={{
                                    left: content.x + r.box.x * content.w,
                                    top: content.y + r.box.y * content.h,
                                }}
                                onClick={() => setSelectedId(r.id)}>
                                {regionName(r)}{r.prioritised ? ' ★' : ''}
                            </span>
                        ))}

                        {busy && (
                            <div className="rs-busy" role="status">
                                <span className="rs-spin" /> Dissecting the image…
                            </div>
                        )}
                        {drawing && <p className="rs-hint-float">Drag to mark a part detection missed</p>}
                    </div>

                    {/* map switch — how much the anchors weigh on the eye */}
                    <div className="rs-maps" role="radiogroup" aria-label="Region view">
                        {MAPS.map(m => (
                            <button key={m.key} role="radio" aria-checked={viewMap === m.key}
                                className={`rs-map${viewMap === m.key ? ' on' : ''}`}
                                title={m.hint}
                                onClick={() => setViewMap(m.key)}>{m.label}</button>
                        ))}
                        <span className="rs-count">
                            {visible.length}/{regions.length} parts
                            {prioritisedCount > 0 && <> · {prioritisedCount}★</>}
                        </span>
                    </div>
                </section>

                {/* ── panel ─────────────────────────────────────────────────────────── */}
                <aside className="rs-panel">
                    {/* the taxonomy, demoted: a quiet menu, not a wall */}
                    <div className="rs-verbs">
                        <label className="rs-sr" htmlFor="rs-mode">Dissection vocabulary</label>
                        <select id="rs-mode" className="rs-select" value={mode} disabled={busy}
                            onChange={e => setMode(e.target.value)}>
                            {MODES.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
                        </select>
                        <button className="rs-primary" onClick={() => detect()} disabled={busy}
                            title="Dissect the image into its parts">
                            {busy ? <span className="rs-spin" /> : <Sparkles size={14} />}
                            {/* the label hides when the pane is cramped; the icon carries it */}
                            <span className="rs-primary-label">Dissect</span>
                        </button>
                        <div className="rs-overflow-wrap">
                            <button className="rs-icon" aria-label="More actions"
                                aria-expanded={overflowOpen} disabled={busy}
                                onClick={() => setOverflowOpen(o => !o)}>
                                <MoreHorizontal size={15} />
                            </button>
                            {overflowOpen && (
                                <div className="rs-overflow" role="menu">
                                    <button role="menuitem" onClick={() => detect({ coarseOnly: true })}>
                                        <Scan size={13} /> Coarse only
                                    </button>
                                    <button role="menuitem"
                                        onClick={() => { setDrawing(true); setOverflowOpen(false); }}>
                                        <Plus size={13} /> Mark a part
                                    </button>
                                    <input className="rs-lens" value={lens} placeholder="Intention (optional)…"
                                        onChange={e => setLens(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && detect()} />
                                </div>
                            )}
                        </div>
                        <span className={`rs-save rs-save--${saveState}`}>
                            {saveState === 'saving' && 'saving…'}
                            {saveState === 'saved' && <><Check size={12} /> saved</>}
                        </span>
                    </div>

                    {/* categories: not decoration — the filter that splits numerosity */}
                    {categories.length > 1 && (
                        <div className="rs-filter">
                            <label className="rs-sr" htmlFor="rs-cat">Filter parts by category</label>
                            <select id="rs-cat" className="rs-select rs-select--quiet" value={category}
                                onChange={e => { setCategory(e.target.value); setActiveId(null); }}>
                                <option value="all">All parts ({regions.length})</option>
                                {categories.map(c => (
                                    <option key={c} value={c}>
                                        {c} ({regions.filter(r => r.category === c).length})
                                    </option>
                                ))}
                            </select>
                        </div>
                    )}

                    {error && (
                        <p className="rs-error" role="alert">
                            <AlertCircle size={13} /> {error}
                            <button className="rs-retry" onClick={() => detect()}>Retry</button>
                        </p>
                    )}

                    {/* the felt unit, foregrounded */}
                    {busy ? (
                        <div className="rs-skeleton" aria-hidden="true">
                            {[0, 1, 2, 3].map(i => <div key={i} className="rs-skel-row" />)}
                        </div>
                    ) : !regions.length ? (
                        <div className="rs-empty">
                            <p className="rs-muted">No parts yet.</p>
                            <p className="rs-muted rs-dim">Dissect the image to see its anatomy, then say what each part does to you.</p>
                        </div>
                    ) : (
                        <div className="rs-list" role="listbox" tabIndex={0} ref={listRef}
                            aria-label="Parts of the image" aria-activedescendant={activeId || undefined}
                            onKeyDown={onListKeyDown} onBlur={() => activate(null)}>
                            {visible.map(r => {
                                const lens = lensFor(r.id);
                                return (
                                    <div key={r.id} id={r.id} data-rid={r.id} role="option"
                                        aria-selected={selectedId === r.id}
                                        className={`rs-row${selectedId === r.id ? ' is-sel' : ''}`
                                            + `${activeId === r.id ? ' is-active' : ''}`
                                            + `${r.prioritised ? ' is-pri' : ''}`
                                            + `${!isAnchor(r) ? ' rs-row--fine' : ''}`}
                                        onMouseEnter={() => activate(r.id)}
                                        onMouseLeave={() => activate(null)}
                                        onClick={() => setSelectedId(r.id)}>
                                        <button className="rs-star" tabIndex={-1}
                                            aria-label={r.prioritised ? `Unmark ${regionName(r)}` : `${regionName(r)} affected me`}
                                            onClick={(e) => { e.stopPropagation(); togglePriority(r.id); }}>
                                            <Star size={14} fill={r.prioritised ? 'currentColor' : 'none'} />
                                        </button>
                                        <div className="rs-row-body">
                                            <span className="rs-row-name">{regionName(r)}</span>
                                            {lens && (
                                                <span className="rs-row-reading">
                                                    <em>{lens.name}</em> — {lens.reading}
                                                </span>
                                            )}
                                            {hasNote(r) && <span className="rs-row-note">“{r.user_note}”</span>}
                                        </div>
                                    </div>
                                );
                            })}
                            {hiddenFine > 0 && (
                                <button className="rs-reveal" onClick={() => setRevealFine(true)}>
                                    <Eye size={13} /> Reveal {hiddenFine} more part{hiddenFine !== 1 ? 's' : ''}
                                </button>
                            )}
                        </div>
                    )}

                    {/* pick → comment → remember */}
                    {selected ? (
                        <div className="rs-editor">
                            <div className="rs-editor-head">
                                <strong>{regionName(selected)}</strong>
                                <button className={`rs-pri${selected.prioritised ? ' on' : ''}`}
                                    onClick={() => togglePriority(selected.id)}>
                                    <Star size={12} fill={selected.prioritised ? 'currentColor' : 'none'} />
                                    {selected.prioritised ? 'Affected me' : 'Mark as affecting'}
                                </button>
                            </div>
                            {selected.prioritised && (
                                <div className="rs-weight">
                                    <label htmlFor="rs-int">Intensity <strong>{selected.weight || 0}</strong></label>
                                    <input id="rs-int" type="range" min="0" max="100" value={selected.weight || 0}
                                        onChange={e => update(selected.id, { weight: Number(e.target.value) })}
                                        onMouseUp={scheduleSave} onKeyUp={scheduleSave} />
                                </div>
                            )}
                            <textarea className="rs-note"
                                aria-label={`How does ${regionName(selected)} affect you?`}
                                placeholder={`How does “${regionName(selected)}” affect you?`}
                                value={selected.user_note || ''}
                                onChange={e => update(selected.id, { user_note: e.target.value })}
                                onBlur={() => { scheduleSave(); if ((selected.user_note || '').trim()) attend(selected); }} />
                        </div>
                    ) : (
                        regions.length > 0 && <p className="rs-muted rs-pick">Select a part to say how it affects you.</p>
                    )}
                </aside>
            </div>

            {/* Phase 2 — the dedicated "see the image properly" surface. Same overlay,
                same maps, at full size with zoom and pan. */}
            {fullscreen && natural && (
                <RegionLightbox
                    post={post}
                    regions={visible}
                    natural={natural}
                    aletheia={aletheia}
                    viewMap={viewMap}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    onClose={() => setFullscreen(false)}
                />
            )}
        </div>
    );
}
