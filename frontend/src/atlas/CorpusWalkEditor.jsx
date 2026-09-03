import React, { useCallback, useEffect, useState } from 'react';

import { corpusService } from './corpusService.js';
import { refusalText, rowsAfterPatch, walkRows } from './corpusDocument.js';

/**
 * ATLAS L1 — editing a saved walk, in place, over the routes that already exist.
 *
 * Thin on purpose. Every control here is one PATCH the server already understood — retitle,
 * move, re-note, drop — and one DELETE. Nothing here opens a canvas, and nothing here can touch a
 * post: a walk is an ORDERING of images somebody already has.
 *
 * REFUSALS ARE SAID, NOT SWALLOWED. A PATCH applies what it can and returns what it could not
 * (`{corpus, refused}`); the row is redrawn from the corpus that came back, so what the curator
 * sees is what was stored, and the refusal is printed under it.
 */
export default function CorpusWalkEditor({ corpus, onChange, onDelete, onClose }) {
    const [rows, setRows] = useState(null);          // null until the view has answered
    const [title, setTitle] = useState(corpus?.title || '');
    const [notes, setNotes] = useState({});
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [refused, setRefused] = useState('');
    const [confirming, setConfirming] = useState(false);

    useEffect(() => {
        let live = true;
        (async () => {
            try {
                const view = await corpusService.view(corpus.id);
                if (!live) return;
                const next = walkRows(view);
                setRows(next);
                setNotes(Object.fromEntries(next.map((r) => [r.postId, r.note])));
            } catch (err) {
                if (live) { setError(err?.message || 'The walk could not be loaded.'); setRows([]); }
            }
        })();
        return () => { live = false; };
    }, [corpus.id]);

    const patch = useCallback(async (body) => {
        if (busy) return;
        setBusy(true);
        setError('');
        setRefused('');
        try {
            const result = await corpusService.patch(corpus.id, body);
            setRows((prev) => rowsAfterPatch(prev, result.corpus));
            setRefused(refusalText(result.refused));
            onChange?.(result.corpus);
        } catch (err) {
            setError(err?.message || 'The walk was not changed.');
        } finally {
            setBusy(false);
        }
    }, [busy, corpus.id, onChange]);

    const rename = (e) => {
        e.preventDefault();
        if (title.trim() && title.trim() !== corpus.title) patch({ title: title.trim() });
    };
    const saveNote = (postId) => {
        const current = rows?.find((r) => r.postId === postId)?.note || '';
        const next = (notes[postId] || '').trim();
        if (next !== current) patch({ note_for: postId, note: next });
    };

    const forget = async () => {
        if (busy) return;
        setBusy(true);
        setError('');
        try {
            await corpusService.remove(corpus.id);
            onDelete?.(corpus.id);
        } catch (err) {
            setError(err?.message || 'The walk was not forgotten.');
            setBusy(false);
        }
    };

    const count = rows?.length || 0;

    return (
        <div className="atlas-walk" data-walk-editor={corpus.id}>
            <form className="atlas-inline" onSubmit={rename} aria-label="Rename the walk">
                <input className="atlas-input" value={title} maxLength={120}
                    aria-label="The walk's name" disabled={busy}
                    onChange={(e) => setTitle(e.target.value)} />
                <button type="submit" className="atlas-plain"
                    disabled={busy || !title.trim() || title.trim() === corpus.title}>
                    Rename
                </button>
                <button type="button" className="atlas-plain" onClick={onClose} disabled={busy}>
                    Done
                </button>
            </form>

            {rows === null ? (
                <p className="atlas-empty">Loading the walk…</p>
            ) : count === 0 ? (
                <p className="atlas-empty">This walk holds no images.</p>
            ) : (
                <ol className="atlas-order" aria-label="The walk, in order">
                    {rows.map((r, i) => (
                        <li key={r.postId} className="atlas-order-row" data-walk-post={r.postId}>
                            <span className="atlas-order-n">{i + 1}</span>
                            {r.readable && r.imageRef
                                ? <img className="atlas-walk-thumb" src={r.imageRef} alt="" loading="lazy" />
                                : <span className="atlas-walk-thumb is-unreadable"
                                    title={r.unreadableReason || 'could not be read'}>?</span>}
                            <input className="atlas-input atlas-order-note"
                                value={notes[r.postId] ?? ''} maxLength={200} disabled={busy}
                                aria-label={`Why image ${i + 1} sits here`}
                                placeholder="why it sits here"
                                onChange={(e) => setNotes((prev) => ({
                                    ...prev, [r.postId]: e.target.value }))}
                                onBlur={() => saveNote(r.postId)} />
                            <span className="atlas-order-move">
                                <button type="button" aria-label={`Move image ${i + 1} earlier`}
                                    disabled={busy || i === 0}
                                    onClick={() => patch({ move: r.postId, to: i - 1 })}>↑</button>
                                <button type="button" aria-label={`Move image ${i + 1} later`}
                                    disabled={busy || i === count - 1}
                                    onClick={() => patch({ move: r.postId, to: i + 1 })}>↓</button>
                                <button type="button" aria-label={`Drop image ${i + 1} from the walk`}
                                    disabled={busy || count < 2}
                                    title={count < 2 ? 'A walk keeps at least one image' : 'Drop from the walk'}
                                    onClick={() => patch({ remove: r.postId })}>×</button>
                            </span>
                        </li>
                    ))}
                </ol>
            )}

            {refused && <p className="atlas-empty" role="status">{refused}</p>}
            {error && <p className="atlas-error" role="alert">{error}</p>}

            <div className="atlas-walk-foot">
                {confirming ? (
                    <span className="atlas-confirm" role="group" aria-label="Forget this walk?">
                        <span className="atlas-empty">
                            Forget this walk? The images stay, and so does any canvas opened from it.
                        </span>
                        <button type="button" className="atlas-plain is-danger" data-forget-confirm
                            disabled={busy} onClick={forget}>Forget it</button>
                        <button type="button" className="atlas-plain" disabled={busy}
                            onClick={() => setConfirming(false)}>Keep it</button>
                    </span>
                ) : (
                    <button type="button" className="atlas-plain" data-forget
                        disabled={busy} onClick={() => setConfirming(true)}>
                        Forget this walk
                    </button>
                )}
            </div>
        </div>
    );
}
