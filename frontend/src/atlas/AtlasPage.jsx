import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import AtlasWorkspace from './AtlasWorkspace.jsx';
import { atlasService, authMessage, isAuthFailure } from './atlasService.js';
import { corpusService } from './corpusService.js';
import {
    corpusSummary, imagesFrom, move, saveBlocker, toggle as toggleImage,
} from './corpusDocument.js';
import { API_URL } from '../config/api';
import './atlas.css';

/**
 * ATLAS C1 — the route: pick a corpus, or open the canvas over one.
 *
 * The index is deliberately thin. Choosing a corpus is choosing a SEQUENCE — order is evidence,
 * and the order you tick these images in is the order they land on the canvas — so the picker
 * numbers the selection rather than presenting it as a set. There is no "select all", because a
 * canvas over every image you happen to own is a gallery, not an argument.
 *
 * An Atlas can also be opened over a run's corpus, which is the common path once a run has
 * already assembled and read a set of images: the canvas then shows exactly what that run spanned.
 */

function AtlasIndex() {
    const navigate = useNavigate();
    const [posts, setPosts] = useState([]);
    const [atlases, setAtlases] = useState([]);
    const [selected, setSelected] = useState([]);
    const [title, setTitle] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    // L1 — the saved walks. A corpus is a SEQUENCE somebody named; these are the ones they can
    // reopen without picking the images out of a gallery again.
    const [corpora, setCorpora] = useState([]);
    const [why, setWhy] = useState('');
    const [notes, setNotes] = useState({});
    const [saving, setSaving] = useState(false);
    // Told apart from "there is nothing here", which is what this page used to show instead.
    const [denied, setDenied] = useState('');

    useEffect(() => {
        let live = true;
        (async () => {
            let refused = '';
            try {
                // Trailing slash on purpose: without it FastAPI answers 307 and the request is
                // re-issued, and a redirect is exactly where an intermediary is most likely to
                // drop a custom `X-API-Key` header.
                const res = await fetch(`${API_URL}/api/v1/posts/?page=1&limit=24`);
                if (res.status === 401 || res.status === 403) {
                    refused = authMessage(res.status);
                } else if (res.ok) {
                    const data = await res.json();
                    if (live && Array.isArray(data?.posts)) setPosts(data.posts);
                }
            } catch { /* offline or unreachable — the existing-atlas list is still worth trying */ }

            try {
                const data = await corpusService.list();
                if (live) setCorpora(data?.corpora || []);
            } catch (e) {
                if (isAuthFailure(e)) refused = e.message;
            }

            try {
                const data = await atlasService.list();
                if (live) setAtlases(data?.atlases || []);
            } catch (e) {
                // A REFUSAL IS NOT AN EMPTY SHELF. "A fresh install has none" is a fine reason to
                // tolerate a failure here, but it is only true of some failures: a 401 means the
                // canvases exist and this browser was not allowed to see them, and rendering that
                // as an empty picker tells the curator their work is gone.
                if (isAuthFailure(e)) refused = e.message;
            }

            if (live && refused) setDenied(refused);
        })();
        return () => { live = false; };
    }, []);

    const toggle = (id) => setSelected((prev) => toggleImage(prev, id));
    const reorder = (id, delta) => setSelected((prev) => move(prev, id, delta));

    /**
     * Save the selection as a named walk (L1).
     *
     * SAVING AND OPENING ARE DIFFERENT ACTS, and both are offered. Opening a canvas over an ad-hoc
     * selection is still the fast path for a passing thought; saving is for a walk you mean to
     * come back to, re-sequence, and hand to a sensory pass and a writer as the same object. A
     * surface that only offered "open" would make every corpus disposable — which is what it was.
     */
    const saveCorpus = useCallback(async () => {
        if (saveBlocker(selected, title) || saving) return;
        setSaving(true);
        setError('');
        try {
            const doc = await corpusService.create({
                title: title.trim(), why: why.trim(), images: imagesFrom(selected, notes),
            });
            setCorpora((prev) => [doc, ...prev]);
            // The walk is saved and the picker is cleared: the next thing a curator does is
            // usually open it, and leaving the selection standing invites saving it twice.
            setSelected([]);
            setNotes({});
        } catch (err) {
            setError(err?.message || 'The walk was not saved.');
        } finally {
            setSaving(false);
        }
    }, [notes, saving, selected, title, why]);

    const openCorpus = useCallback(async (corpusId) => {
        if (busy) return;
        setBusy(true);
        setError('');
        try {
            const doc = await atlasService.create({ corpus_id: corpusId });
            navigate(`/atlas/${doc.id}`);
        } catch (err) {
            setError(err?.message || 'Could not open a canvas over that walk.');
            setBusy(false);
        }
    }, [busy, navigate]);

    const open = useCallback(async (e) => {
        e.preventDefault();
        if (selected.length < 1 || busy) return;
        setBusy(true);
        setError('');
        try {
            const doc = await atlasService.create({ title: title.trim(), post_ids: selected });
            navigate(`/atlas/${doc.id}`);
        } catch (err) {
            setError(err?.message || 'Could not open a canvas over those images.');
            setBusy(false);
        }
    }, [busy, navigate, selected, title]);

    return (
        <div className="atlas-index">
            <header className="atlas-index-head">
                <h1 className="atlas-title">The Atlas</h1>
                <p className="atlas-sub">
                    Several images on one canvas, wearing the percepts you have committed to them.
                    The order you pick is the order they land in — a corpus is a sequence, and the
                    sequence carries the argument.
                </p>
            </header>

            {denied && (
                <div className="atlas-banner is-error" role="alert">{denied}</div>
            )}

            {corpora.length > 0 && (
                <section className="atlas-existing" aria-label="Saved walks">
                    <h2 className="atlas-h2">Open a walk</h2>
                    <p className="atlas-sub">
                        A walk is an ORDERED corpus you named — the sequence is the argument, and
                        opening one lays its images out in that order.
                    </p>
                    <ul className="atlas-list">
                        {corpora.map(corpusSummary).map((c) => (
                            <li key={c.id}>
                                <button type="button" className="atlas-list-item"
                                    data-corpus={c.id} disabled={busy}
                                    onClick={() => openCorpus(c.id)}>
                                    <span className="atlas-list-title">{c.title}</span>
                                    <span className="atlas-list-meta">
                                        {c.count} image{c.count === 1 ? '' : 's'}, in order
                                        {/* Counted separately: an unexplained walk is still a
                                            walk, and folding this into the total would make it
                                            read as a defect rather than a prompt. */}
                                        {c.noted > 0 && ` · ${c.noted} noted`}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {atlases.length > 0 && (
                <section className="atlas-existing">
                    <h2 className="atlas-h2">Open one you have</h2>
                    <ul className="atlas-list">
                        {atlases.map((a) => (
                            <li key={a.id}>
                                <button type="button" className="atlas-list-item"
                                    onClick={() => navigate(`/atlas/${a.id}`)}>
                                    <span className="atlas-list-title">{a.title || a.id}</span>
                                    <span className="atlas-list-meta">
                                        {(a.nodes || []).length} image{(a.nodes || []).length === 1 ? '' : 's'}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            <form className="atlas-new" onSubmit={open} aria-label="Open a new Atlas">
                <h2 className="atlas-h2">Or start a new one</h2>
                <label className="atlas-label">
                    <span>What is this canvas for?</span>
                    <input className="atlas-input" value={title} maxLength={120}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="the walk from the Lustgarten to the rotunda" />
                </label>

                <fieldset className="atlas-field">
                    <legend className="atlas-legend">
                        Images {selected.length ? `· ${selected.length} chosen, in order` : ''}
                    </legend>
                    {posts.length === 0 ? (
                        <p className="atlas-empty">
                            {denied
                                ? 'Images could not be listed — see above.'
                                : 'No images loaded.'}
                        </p>
                    ) : (
                        <ul className="atlas-picker">
                            {posts.map((p) => {
                                const at = selected.indexOf(p.id);
                                return (
                                    <li key={p.id}>
                                        <button type="button"
                                            className={`atlas-pick${at >= 0 ? ' is-picked' : ''}`}
                                            aria-pressed={at >= 0}
                                            onClick={() => toggle(p.id)}>
                                            <img src={p.photo_url} alt="" loading="lazy" />
                                            {at >= 0 && <span className="atlas-pick-n">{at + 1}</span>}
                                        </button>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </fieldset>

                <label className="atlas-label">
                    <span>What is this SEQUENCE for? (optional, and the planner is told it)</span>
                    <input className="atlas-input" value={why} maxLength={240}
                        onChange={(e) => setWhy(e.target.value)}
                        placeholder="the approach, in the order a visitor walks it" />
                </label>

                {selected.length > 0 && (
                    <ol className="atlas-order" aria-label="The walk, in order">
                        {selected.map((id, i) => (
                            <li key={id} className="atlas-order-row" data-order-post={id}>
                                <span className="atlas-order-n">{i + 1}</span>
                                <input className="atlas-input atlas-order-note"
                                    value={notes[id] || ''} maxLength={200}
                                    aria-label={`Why image ${i + 1} sits here`}
                                    placeholder="why it sits here"
                                    onChange={(e) => setNotes((prev) => ({
                                        ...prev, [id]: e.target.value }))} />
                                <span className="atlas-order-move">
                                    <button type="button" aria-label={`Move image ${i + 1} earlier`}
                                        disabled={i === 0}
                                        onClick={() => reorder(id, -1)}>↑</button>
                                    <button type="button" aria-label={`Move image ${i + 1} later`}
                                        disabled={i === selected.length - 1}
                                        onClick={() => reorder(id, 1)}>↓</button>
                                </span>
                            </li>
                        ))}
                    </ol>
                )}

                {error && <p className="atlas-error" role="alert">{error}</p>}

                <div className="atlas-new-actions">
                    <button type="submit" className="atlas-go" disabled={selected.length < 1 || busy}>
                        {busy ? 'Opening…' : 'Open the canvas'}
                    </button>
                    {/* Saving and opening are different acts. Opening over an ad-hoc selection is
                        the fast path for a passing thought; saving is for a walk you mean to come
                        back to and hand on as the same object. */}
                    <button type="button" className="atlas-plain" data-save-corpus
                        disabled={Boolean(saveBlocker(selected, title)) || saving}
                        title={saveBlocker(selected, title) || 'Save this as a named, ordered walk'}
                        onClick={saveCorpus}>
                        {saving ? 'Saving…' : 'Save as a walk'}
                    </button>
                </div>
                {saveBlocker(selected, title) && (
                    // The reason, said out loud, rather than a dead button and a guess.
                    <p className="atlas-empty">{saveBlocker(selected, title)}</p>
                )}
            </form>
        </div>
    );
}

export default function AtlasPage() {
    const { atlasId } = useParams();
    // T1: the route opens the WORKSPACE, which owns the document and hands it to whichever mode is
    // on. The route knows nothing about modes — a mode is a lens, not a place.
    return atlasId ? <AtlasWorkspace atlasId={atlasId} /> : <AtlasIndex />;
}
