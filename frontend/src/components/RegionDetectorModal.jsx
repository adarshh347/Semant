import React, { useState, useEffect, useCallback } from 'react';
import { X, Scan, Star, Save, Sparkles } from 'lucide-react';
import { API_URL } from '../config/api';
import './RegionDetectorModal.css';

const BASE = `${API_URL}/api/v1/posts`;

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

export default function RegionDetectorModal({ post, onClose, onSaved }) {
    const [regions, setRegions] = useState(post.region_annotations || []);
    const [selectedId, setSelectedId] = useState(null);
    const [detecting, setDetecting] = useState(false);
    const [saving, setSaving] = useState(false);
    const [feedPersona, setFeedPersona] = useState(true);
    const [error, setError] = useState('');
    const [mode, setMode] = useState('general');
    const [lens, setLens] = useState('');
    const [meta, setMeta] = useState(null);

    const detect = useCallback(async (opts = {}) => {
        const useMode = opts.mode ?? mode;
        const useLens = opts.lens ?? lens;
        setDetecting(true); setError('');
        try {
            const res = await fetch(`${BASE}/${post.id}/detect-regions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: useMode, lens: useLens, coarse_only: !!opts.coarseOnly }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setRegions(data.regions || []);
            setMeta({ anchors: data.anchor_count, fine: data.fine_count, source: data.source });
        } catch (e) { setError('Detection failed — is the backend running?'); }
        finally { setDetecting(false); }
    }, [post.id, mode, lens]);

    // Auto-detect on open if we have nothing cached yet (general fine pass).
    useEffect(() => { if (!regions.length) detect(); /* eslint-disable-next-line */ }, []);

    const update = (id, patch) =>
        setRegions(rs => rs.map(r => r.id === id ? { ...r, ...patch } : r));

    const togglePriority = (id) => {
        const r = regions.find(x => x.id === id);
        update(id, { prioritised: !r.prioritised, weight: !r.prioritised ? (r.weight || 60) : 0 });
        setSelectedId(id);
    };

    const save = async () => {
        setSaving(true); setError('');
        try {
            const res = await fetch(`${BASE}/${post.id}/region-annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regions, feed_to_persona: feedPersona }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            onSaved?.(data.post);
            onClose?.();
        } catch (e) { setError('Could not save.'); }
        finally { setSaving(false); }
    };

    const selected = regions.find(r => r.id === selectedId);
    const prioritisedCount = regions.filter(r => r.prioritised).length;

    const anchors = regions.filter(r => (r.depth || 0) === 0);
    const fineParts = regions.filter(r => (r.depth || 0) === 1);
    // Group fine parts under their parent anchor for the indented list.
    const grouped = anchors.map(a => ({
        anchor: a,
        children: fineParts.filter(f => f.parent_id === a.id),
    }));
    const orphanFine = fineParts.filter(f => !anchors.some(a => a.id === f.parent_id));

    const labelVisible = (r) => (r.depth || 0) === 0 || r.prioritised || selectedId === r.id;

    return (
        <div className="rd-backdrop" onClick={onClose}>
            <div className="rd-modal" onClick={e => e.stopPropagation()}>
                <div className="rd-head">
                    <div>
                        <span className="rd-kicker">Sūkṣma · fine anatomy</span>
                        <h3 className="rd-title">Dissect the image into its parts</h3>
                    </div>
                    <button className="rd-close" onClick={onClose}><X size={20} /></button>
                </div>

                <div className="rd-body">
                    {/* Image with clickable overlay shapes */}
                    <div className="rd-stage">
                        <div className="rd-image-wrap">
                            <img src={post.photo_url} alt="" referrerPolicy="no-referrer" />
                            <svg className="rd-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                                {/* anchors first (under), fine parts on top so they stay clickable */}
                                {[...anchors, ...fineParts].map(r => {
                                    const depth = r.depth || 0;
                                    const cls = `rd-shape rd-shape--${depth === 0 ? 'anchor' : 'fine'}`
                                        + `${r.prioritised ? ' is-pri' : ''}${selectedId === r.id ? ' is-sel' : ''}`;
                                    const hasPoly = Array.isArray(r.polygon) && r.polygon.length > 2;
                                    if (hasPoly) {
                                        const pts = r.polygon.map(([x, y]) => `${x * 100},${y * 100}`).join(' ');
                                        return <polygon key={r.id} className={cls} points={pts}
                                            vectorEffect="non-scaling-stroke" onClick={() => setSelectedId(r.id)} />;
                                    }
                                    const b = r.box || {};
                                    return <rect key={r.id} className={cls} x={b.x * 100} y={b.y * 100}
                                        width={b.w * 100} height={b.h * 100}
                                        vectorEffect="non-scaling-stroke" onClick={() => setSelectedId(r.id)} />;
                                })}
                            </svg>
                            {regions.filter(labelVisible).map(r => {
                                const b = r.box || {};
                                return (
                                    <span
                                        key={r.id}
                                        className={`rd-seg-label rd-seg-label--${(r.depth || 0) === 0 ? 'anchor' : 'fine'}`
                                            + `${r.prioritised ? ' is-pri' : ''}${selectedId === r.id ? ' is-sel' : ''}`}
                                        style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%` }}
                                        onClick={() => setSelectedId(r.id)}
                                    >
                                        {r.label}{r.prioritised ? ' ★' : ''}
                                    </span>
                                );
                            })}
                            {detecting && <div className="rd-detecting"><span className="rd-spin" /> Dissecting…</div>}
                        </div>

                        {/* Mode + intention controls */}
                        <div className="rd-controls">
                            <div className="rd-modes">
                                {MODES.map(m => (
                                    <button
                                        key={m.key}
                                        className={`rd-mode${mode === m.key ? ' on' : ''}`}
                                        onClick={() => { setMode(m.key); detect({ mode: m.key }); }}
                                        disabled={detecting}
                                    >{m.label}</button>
                                ))}
                            </div>
                            <div className="rd-lens-row">
                                <input
                                    className="rd-lens"
                                    placeholder="Intention (optional): e.g. the way the fabric folds at the waist…"
                                    value={lens}
                                    onChange={e => setLens(e.target.value)}
                                    onKeyDown={e => { if (e.key === 'Enter') detect(); }}
                                />
                                <button className="rd-detect-btn" onClick={() => detect()} disabled={detecting}>
                                    <Sparkles size={15} /> Dissect
                                </button>
                            </div>
                            <div className="rd-stage-actions">
                                <button className="rd-ghost" onClick={() => detect({ coarseOnly: true })} disabled={detecting}>
                                    <Scan size={14} /> Coarse only
                                </button>
                                {meta && (
                                    <span className="rd-hint">
                                        {meta.anchors} whole · {meta.fine} fine parts
                                        {meta.source ? ` · ${meta.source}` : ''}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Region list (grouped by anchor) + selected editor */}
                    <div className="rd-side">
                        <div className="rd-list">
                            {regions.length === 0 && !detecting && <p className="rd-muted">No parts yet.</p>}
                            {grouped.map(({ anchor, children }) => (
                                <div key={anchor.id} className="rd-group">
                                    <Row r={anchor} {...{ selectedId, setSelectedId, togglePriority }} />
                                    {children.map(c => (
                                        <Row key={c.id} r={c} indent {...{ selectedId, setSelectedId, togglePriority }} />
                                    ))}
                                </div>
                            ))}
                            {orphanFine.map(c => (
                                <Row key={c.id} r={c} {...{ selectedId, setSelectedId, togglePriority }} />
                            ))}
                        </div>

                        {selected ? (
                            <div className="rd-editor">
                                <div className="rd-editor-head">
                                    <strong>{selected.label}</strong>
                                    <button className={`rd-pri-toggle${selected.prioritised ? ' on' : ''}`} onClick={() => togglePriority(selected.id)}>
                                        <Star size={13} fill={selected.prioritised ? 'currentColor' : 'none'} /> {selected.prioritised ? 'Affected me' : 'Mark as affecting'}
                                    </button>
                                </div>
                                <div className="rd-tags">
                                    {selected.category && <span className="rd-tag">{selected.category}</span>}
                                    {selected.material && <span className="rd-tag rd-tag--mat">{selected.material}</span>}
                                </div>
                                {selected.description && <p className="rd-desc">{selected.description}</p>}
                                {selected.prioritised && (
                                    <div className="rd-weight">
                                        <label>Intensity <strong>{selected.weight || 0}</strong></label>
                                        <input type="range" min="0" max="100" value={selected.weight || 0}
                                            onChange={e => update(selected.id, { weight: Number(e.target.value) })} />
                                    </div>
                                )}
                                <textarea
                                    className="rd-note"
                                    placeholder={`How does “${selected.label}” affect you? What does it do?`}
                                    value={selected.user_note || ''}
                                    onChange={e => update(selected.id, { user_note: e.target.value })}
                                />
                            </div>
                        ) : (
                            <p className="rd-muted rd-pick">Select a part to describe how it affects you.</p>
                        )}
                    </div>
                </div>

                <div className="rd-foot">
                    {error && <span className="rd-error">{error}</span>}
                    <span className="rd-count">{prioritisedCount} part{prioritisedCount !== 1 ? 's' : ''} prioritised</span>
                    {post.instagram_handle && (
                        <label className="rd-feed">
                            <input type="checkbox" checked={feedPersona} onChange={e => setFeedPersona(e.target.checked)} />
                            feed <strong>@{post.instagram_handle}</strong>
                        </label>
                    )}
                    <button className="rd-save" onClick={save} disabled={saving}>
                        {saving ? <span className="rd-spin" /> : <Save size={15} />} Save anatomy
                    </button>
                </div>
            </div>
        </div>
    );
}

function Row({ r, indent, selectedId, setSelectedId, togglePriority }) {
    return (
        <div
            className={`rd-row${indent ? ' rd-row--child' : ''}${selectedId === r.id ? ' is-sel' : ''}${r.prioritised ? ' is-pri' : ''}`}
            onClick={() => setSelectedId(r.id)}
        >
            <button className="rd-star" onClick={(e) => { e.stopPropagation(); togglePriority(r.id); }} title="This affected me">
                <Star size={15} fill={r.prioritised ? 'currentColor' : 'none'} />
            </button>
            <span className="rd-row-meta">
                <span className="rd-row-label">{r.label}</span>
                <span className="rd-row-cat">{r.category}{r.material ? ` · ${r.material}` : ''}</span>
            </span>
            {r.user_note && <span className="rd-row-dot" title="has a note" />}
        </div>
    );
}
