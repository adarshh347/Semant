import React, { useEffect, useRef, useState } from 'react';
import {
    ArrowLeft, MousePointer2, Brush, PenTool, Group, Waypoints, Frame, Eye, Check,
} from 'lucide-react';
import RegionOverlay from '../components/RegionOverlay';
import useStageGeometry, { useNaturalSize } from './useStageGeometry';
import { resolveGround } from './grounds';
import './DifferentialWorkspace.css';

/**
 * Differential — the dedicated percept-construction workspace (v1, increment A).
 *
 * A full-workspace MODE inside PostDetailPage, not a route: unsaved Manuscript
 * content lives in PostDetailPage state, and a route change would unmount and
 * silently lose it. The Chiasm shell stays mounted (hidden) underneath; this
 * surface swaps in over it and hands back with everything intact.
 *
 * Increment A ships the architecture: the shell (top bar · tool rail · stage ·
 * inspector), the shared stage-geometry contract, existing Regions rendered as
 * evidence, and the grounds/percepts persistence round-trip. The perceptual
 * operations land in B–D; only Select is live here.
 */

const TOOLS = [
    { key: 'select', label: 'Select', icon: MousePointer2, ready: true, hint: 'Point at evidence' },
    { key: 'brush', label: 'Brush', icon: Brush, ready: false, hint: 'Soft Field (next increment)' },
    { key: 'trace', label: 'Trace', icon: PenTool, ready: false, hint: 'Path · Boundary' },
    { key: 'collect', label: 'Collect', icon: Group, ready: false, hint: 'Constellation' },
    { key: 'connect', label: 'Connect', icon: Waypoints, ready: false, hint: 'Relation' },
    { key: 'frame', label: 'Frame', icon: Frame, ready: false, hint: 'The whole image' },
];

const regionName = (r) => r?.label || r?.part || r?.category || 'part';

export default function DifferentialWorkspace({ post, store, onExit }) {
    const [tool, setTool] = useState('select');
    const [untouched, setUntouched] = useState(false); // O — the image, unannotated
    const stageRef = useRef(null);
    const [natural, onImgLoad] = useNaturalSize();
    // The shared contract: content is where the letterboxed image actually sits.
    // The canvas + HTML layers (B+) position against it; the SVG matches by viewBox.
    const { content } = useStageGeometry(stageRef, natural);
    void content;

    const {
        regions, selectedId, selectRegion, hoveredId, setHoveredId,
        grounds, percepts, saveState, metaSaveState,
    } = store;

    // O (hold or tap): see the untouched photograph. Esc: put attention down.
    useEffect(() => {
        const down = (e) => {
            if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return;
            if (e.code === 'KeyO' && !e.repeat) setUntouched(true);
            if (e.key === 'Escape') { selectRegion(null); setHoveredId(null); }
        };
        const up = (e) => { if (e.code === 'KeyO') setUntouched(false); };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
    }, [selectRegion, setHoveredId]);

    const saving = saveState === 'saving' || metaSaveState === 'saving';
    const saved = saveState === 'saved' || metaSaveState === 'saved';

    const selected = regions.find((r) => r.id === selectedId) || null;
    const focusId = hoveredId || selectedId;

    // Grounds that reference a region that no longer exists — listed, not hidden:
    // detached evidence is a fact about the archive, not an error to swallow.
    const detachedGrounds = grounds.filter(
        (g) => resolveGround(g, { regions, grounds })?.detached,
    );

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
                {/* ── tool rail — the seven operations; only Select is live in A ── */}
                <nav className="diff-tools" aria-label="Perceptual operations">
                    {TOOLS.map(({ key, label, icon: Icon, ready, hint }) => (
                        <button key={key} type="button"
                            className={`diff-tool${tool === key ? ' on' : ''}`}
                            disabled={!ready}
                            aria-pressed={tool === key}
                            title={ready ? `${label} — ${hint}` : `${label} — ${hint}`}
                            onClick={() => ready && setTool(key)}>
                            <Icon size={16} />
                            <span className="diff-tool-label">{label}</span>
                        </button>
                    ))}
                </nav>

                {/* ── stage — image-dominant; overlay letterboxes with the image ── */}
                <main className="diff-stage-col">
                    <div className={`diff-stage${untouched ? ' is-untouched' : ''}`}
                        ref={stageRef}
                        style={natural ? { '--diff-ar': `${natural.w} / ${natural.h}` } : undefined}>
                        <img src={post.photo_url} alt="" referrerPolicy="no-referrer" onLoad={onImgLoad} />
                        {!untouched && (
                            <RegionOverlay
                                natural={natural}
                                regions={regions}
                                viewMap="quiet"
                                selectedId={selectedId}
                                activeId={hoveredId}
                                focusId={focusId}
                                onSelect={selectRegion}
                                onActivate={setHoveredId}
                                className="diff-svg"
                            />
                        )}
                    </div>
                    <p className="diff-stage-hint">
                        {untouched
                            ? 'The untouched image. Release O to see your evidence again.'
                            : 'Select a part. Brush, Trace, Collect, Connect and Frame arrive with the next increments.'}
                    </p>
                </main>

                {/* ── inspector — contextual, quiet ── */}
                <aside className="diff-inspector">
                    {selected ? (
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
                            <p className="diff-insp-hint">
                                This part is visual evidence — a Ground. Composing Percepts from it
                                begins with the Brush increment.
                            </p>
                        </div>
                    ) : (
                        <div className="diff-insp-empty">
                            <span className="diff-eyebrow">Inspector</span>
                            <p>Nothing under attention. Select a part on the image, or press
                                <kbd>O</kbd> to see the photograph untouched.</p>
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
                        {percepts.length} percept{percepts.length !== 1 ? 's' : ''}
                    </footer>
                </aside>
            </div>
        </div>
    );
}
