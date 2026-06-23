import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { API_URL } from '../config/api';
import './UnconcealQueuePage.css';

const BASE = `${API_URL}/api/v1/posts`;

export default function UnconcealQueuePage() {
    const [params] = useSearchParams();
    const handle = params.get('handle');

    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [index, setIndex] = useState(0);
    const [loadingQueue, setLoadingQueue] = useState(true);

    const [aletheia, setAletheia] = useState(null);
    const [commentary, setCommentary] = useState('');
    const [loadingSuggest, setLoadingSuggest] = useState(false);
    const [feedPersona, setFeedPersona] = useState(true);
    const [saving, setSaving] = useState(false);
    const [savedCount, setSavedCount] = useState(0);
    const [error, setError] = useState('');

    const current = items[index];

    const loadQueue = useCallback(async () => {
        setLoadingQueue(true); setError('');
        try {
            const q = handle ? `?handle=${encodeURIComponent(handle)}&limit=100` : '?limit=100';
            const res = await fetch(`${BASE}/unconceal-queue${q}`);
            const data = await res.json();
            setItems(data.items || []);
            setTotal(data.total || 0);
            setIndex(0);
        } catch (e) { setError('Could not load the queue.'); }
        finally { setLoadingQueue(false); }
    }, [handle]);

    useEffect(() => { loadQueue(); }, [loadQueue]);

    const fetchSuggestion = useCallback(async (id) => {
        setLoadingSuggest(true); setAletheia(null); setCommentary(''); setError('');
        try {
            const res = await fetch(`${BASE}/${id}/unconceal-suggest`, { method: 'POST' });
            if (!res.ok) throw new Error();
            const data = await res.json();
            setAletheia(data.aletheia || null);
            setCommentary(data.draft_commentary || '');
        } catch (e) { setError('Aletheia could not read this image — you can still write your own.'); }
        finally { setLoadingSuggest(false); }
    }, []);

    // Auto-draft each item as it comes up.
    useEffect(() => {
        if (current) fetchSuggestion(current.id);
    }, [current?.id, fetchSuggestion]);

    const advance = () => setIndex(i => i + 1);

    const saveAndNext = async () => {
        if (!current) return;
        setSaving(true); setError('');
        try {
            const res = await fetch(`${BASE}/${current.id}/local-context`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ commentary, aletheia, feed_to_persona: feedPersona }),
            });
            if (!res.ok) throw new Error();
            setSavedCount(c => c + 1);
            advance();
        } catch (e) { setError('Could not save — try again.'); }
        finally { setSaving(false); }
    };

    const done = !loadingQueue && (items.length === 0 || index >= items.length);

    return (
        <div className="rq-page">
            <div className="rq-header">
                <div>
                    <span className="rq-eyebrow">Unconceal · review queue</span>
                    <h1 className="rq-title">
                        {handle ? <>Reviewing <span className="rq-handle">@{handle}</span></> : 'Unconceal the gallery'}
                    </h1>
                    <p className="rq-sub">
                        Aletheia drafts a reading for each image; you edit and approve. Each one attaches to the
                        image{handle ? <> and feeds <strong>@{handle}</strong>’s persona</> : ' and feeds its account persona'}.
                    </p>
                </div>
                <Link to={handle ? `/personas#${handle}` : '/personas'} className="rq-back">← Personas</Link>
            </div>

            {!done && !loadingQueue && (
                <div className="rq-progressbar">
                    <div className="rq-progress-fill" style={{ width: `${items.length ? (index / items.length) * 100 : 0}%` }} />
                    <span className="rq-progress-label">
                        {index + 1} of {items.length} loaded · {total} need context · {savedCount} done this session
                    </span>
                </div>
            )}

            {error && <p className="rq-error">{error}</p>}

            {loadingQueue ? (
                <div className="rq-empty"><span className="rq-spin" /> Loading queue…</div>
            ) : done ? (
                <div className="rq-empty rq-done">
                    <h3>{savedCount > 0 ? `Queue clear — ${savedCount} unconcealed this session.` : 'Nothing to review here.'}</h3>
                    <p>{total - savedCount > 0
                        ? `${total - savedCount} images still lack context elsewhere.`
                        : 'Every image in this scope has context.'}</p>
                    <div className="rq-done-actions">
                        <button className="btn btn-primary" onClick={loadQueue}>Reload queue</button>
                        <Link className="rq-back" to={handle ? `/personas#${handle}` : '/personas'}>Back to personas</Link>
                    </div>
                </div>
            ) : current && (
                <div className="rq-body">
                    <div className="rq-image-pane">
                        <img src={current.photo_url} alt="" className="rq-image" referrerPolicy="no-referrer" />
                        {current.instagram_handle && <span className="rq-img-handle">@{current.instagram_handle}</span>}
                    </div>

                    <div className="rq-controls">
                        <div className="rq-aletheia">
                            <div className="rq-block-head">
                                <span className="rq-kicker">Aletheia</span>
                                <button className="rq-regen" onClick={() => fetchSuggestion(current.id)} disabled={loadingSuggest}>
                                    {loadingSuggest ? <span className="rq-spin" /> : '↻'} Re-read
                                </button>
                            </div>
                            {loadingSuggest ? (
                                <p className="rq-muted"><span className="rq-spin" /> Letting the image emerge…</p>
                            ) : aletheia && (aletheia.lenses?.length || aletheia.concealed) ? (
                                <div className="rq-reading">
                                    {(aletheia.lenses || []).map((l, i) => (
                                        <div className="rq-lens" key={i}>
                                            <div className="rq-lens-head"><span>{l.name}</span><span>{l.intensity ?? 0}</span></div>
                                            <div className="rq-bar"><span className="rq-bar-fill" style={{ width: `${Math.max(0, Math.min(100, l.intensity ?? 0))}%` }} /></div>
                                            <p className="rq-lens-reading">{l.reading}</p>
                                        </div>
                                    ))}
                                    {aletheia.concealed && <p className="rq-foot"><strong>Concealed</strong> — {aletheia.concealed}</p>}
                                </div>
                            ) : <p className="rq-muted">No reading — write your own below.</p>}
                        </div>

                        <div className="rq-commentary">
                            <span className="rq-kicker">Your unconcealment <em>(LLM draft — edit freely)</em></span>
                            <textarea
                                className="rq-textarea"
                                value={commentary}
                                onChange={(e) => setCommentary(e.target.value)}
                                placeholder="What does this image do to you? What does it withhold?"
                            />
                        </div>

                        <div className="rq-actions">
                            {current.instagram_handle && (
                                <label className="rq-feed">
                                    <input type="checkbox" checked={feedPersona} onChange={(e) => setFeedPersona(e.target.checked)} />
                                    feed <strong>@{current.instagram_handle}</strong>
                                </label>
                            )}
                            <div className="rq-action-btns">
                                <button className="rq-skip" onClick={advance} disabled={saving}>Skip</button>
                                <button className="rq-save" onClick={saveAndNext} disabled={saving || (!commentary.trim() && !aletheia)}>
                                    {saving ? <span className="rq-spin" /> : null} Save &amp; next →
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
