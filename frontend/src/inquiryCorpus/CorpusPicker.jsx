import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { cldCrop, cldAt } from '../lib/cloudinary';
import {
    mergePosts, filterPosts, searchScopeNote, isComplete, shortId,
} from './corpusSource';
import './inquiryCorpus.css';

/**
 * INQUIRY CORPUS — choosing what the inquiry will read.
 *
 * The 002R rehearsal could choose from the twenty-four newest images and nothing else. This is the
 * whole archive, paged, with the selection surviving every page boundary.
 *
 * ## Selection lives above this component
 *
 * `selected` is an array of POSTS, not ids, and the parent owns it. Two reasons, and the second is
 * the one that mattered: an id-only selection cannot render a tray for an image whose page is no
 * longer loaded, so a person who picked something on page 1, paged to 4 and searched would watch
 * their own choices become bare hex strings. Holding the post means the tray is stable whatever
 * the grid is currently showing.
 *
 * ## Load more is a button, not a scroll sentinel
 *
 * The Archive uses an IntersectionObserver and should — it is an infinite reading surface. This is
 * a control inside a form: an observer here would fire while the person is reading the tray, and
 * "the corpus is 7 pages and you have 2" is information they are entitled to act on rather than
 * have decided for them. It is also the difference between a paging test that asserts an intent
 * and one that has to simulate a viewport.
 *
 * ## Opening an image cannot cost the draft
 *
 * The detail link is a real anchor with `target="_blank"`. An in-app route change would unmount the
 * entry form and take the prompt with it, and the directive's requirement is not "warn before
 * leaving" — it is that opening an image does not lose the draft. A new tab is the only way to
 * mean that literally.
 */
export default function CorpusPicker({
    client,
    selected = [],
    onSelect,
    onDeselect,
    tag = null,
    autoLoad = true,
    injected = [],
}) {
    const [posts, setPosts] = useState([]);
    const [pagesLoaded, setPagesLoaded] = useState(0);
    const [totalPages, setTotalPages] = useState(null);
    const [status, setStatus] = useState('idle');    // idle | loading | error | done
    const [errorText, setErrorText] = useState('');
    const [query, setQuery] = useState('');
    const [preview, setPreview] = useState(null);
    const busy = useRef(false);

    const selectedIds = useMemo(() => new Set(selected.map((p) => p.id)), [selected]);

    const loadNext = useCallback(async () => {
        if (busy.current || status === 'done') return;
        busy.current = true;
        setStatus('loading');
        setErrorText('');
        const next = pagesLoaded + 1;
        try {
            const page = await client.page({ tag, page: next });
            setPosts((prev) => mergePosts(prev, page.posts));
            setPagesLoaded(next);
            if (page.total_pages !== null) setTotalPages(page.total_pages);
            const complete = isComplete({
                pagesLoaded: next,
                totalPages: page.total_pages,
                lastPageEmpty: page.posts.length === 0,
            });
            setStatus(complete ? 'done' : 'idle');
        } catch (e) {
            // A failed page does NOT discard the pages that loaded. The interesting failure is a
            // half-loaded corpus, and throwing away what arrived would make it look like a corpus
            // that never started.
            setErrorText(e?.message || 'The archive did not answer.');
            setStatus('error');
        } finally {
            busy.current = false;
        }
    }, [client, tag, pagesLoaded, status]);

    useEffect(() => {
        if (autoLoad && pagesLoaded === 0 && status === 'idle') loadNext();
    }, [autoLoad, pagesLoaded, status, loadNext]);

    // `injected` is what this session uploaded. It goes in FRONT of the loaded pages and is
    // de-duplicated by the same merge the pages use, so when the page a new post belongs to
    // eventually loads it does not appear twice.
    const all = useMemo(() => mergePosts(injected, posts), [injected, posts]);
    const shown = useMemo(() => filterPosts(all, query), [all, query]);
    const complete = status === 'done';

    const toggle = (post) => {
        if (selectedIds.has(post.id)) onDeselect?.(post.id);
        else onSelect?.(post);
    };

    return (
        <div className="ic-picker" data-pages-loaded={pagesLoaded}>
            <div className="ic-bar">
                <label className="ic-search-label" htmlFor="ic-search">Filter</label>
                <input
                    id="ic-search"
                    className="ic-search"
                    type="search"
                    value={query}
                    placeholder="name, tag, source or id"
                    onChange={(e) => setQuery(e.target.value)}
                />
                <span className="ic-count" data-selected-count={selected.length}>
                    {selected.length} selected
                </span>
            </div>

            {/* THE SCOPE NOTE. Rendered whenever a filter is active, without exception: a search
                box over a partly-loaded corpus otherwise reads as a search of the archive, and
                "no results" reads as "the archive does not contain this". */}
            {query.trim() ? (
                <p className="ic-scope" role="status" data-scope-note="true">
                    {searchScopeNote({
                        loadedCount: all.length, pagesLoaded, totalPages, done: complete,
                    })}
                </p>
            ) : null}

            {selected.length ? (
                <div className="ic-tray" aria-label="Selected images">
                    <h3 className="ic-tray-head">
                        Reading {selected.length} image{selected.length === 1 ? '' : 's'}
                    </h3>
                    <ul className="ic-tray-list">
                        {selected.map((p) => (
                            <li key={p.id} className="ic-tray-item" data-tray-id={p.id}>
                                {p.photo_url
                                    ? <img src={cldCrop(p.photo_url, 96, 96)} alt="" loading="lazy" />
                                    : <span className="ic-blank" aria-hidden="true" />}
                                <span className="ic-tray-meta">
                                    <span className={`ic-label${p.label_is_id ? ' is-id' : ''}`}>
                                        {p.label_is_id ? <>id {p.label}</> : p.label}
                                    </span>
                                    <span className="ic-tray-id">{shortId(p.id)}</span>
                                </span>
                                <button
                                    type="button"
                                    className="ic-remove"
                                    aria-label={`Remove ${p.label_is_id ? p.id : p.label}`}
                                    onClick={() => onDeselect?.(p.id)}
                                >
                                    ×
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}

            {shown.length === 0 && status !== 'loading' ? (
                <p className="ic-empty">
                    {query.trim()
                        ? 'Nothing loaded so far matches that.'
                        : 'No images in the archive.'}
                </p>
            ) : (
                <ul className="ic-grid" role="group" aria-label="Archive images">
                    {shown.map((p) => {
                        const on = selectedIds.has(p.id);
                        return (
                            <li key={p.id} className="ic-cell">
                                <button
                                    type="button"
                                    className={`ic-tile${on ? ' is-on' : ''}`}
                                    aria-pressed={on}
                                    data-post-id={p.id}
                                    onClick={() => toggle(p)}
                                >
                                    {p.photo_url
                                        ? <img src={cldCrop(p.photo_url, 240, 240)} alt="" loading="lazy" />
                                        : <span className="ic-blank" aria-hidden="true" />}
                                    <span className={`ic-label${p.label_is_id ? ' is-id' : ''}`}>
                                        {p.label_is_id ? <>id {p.label}</> : p.label}
                                    </span>
                                    {p.provenance
                                        ? <span className="ic-prov">{p.provenance}</span>
                                        : null}
                                </button>
                                <div className="ic-tile-actions">
                                    <button
                                        type="button"
                                        className="ic-peek"
                                        data-preview-for={p.id}
                                        onClick={() => setPreview(p)}
                                    >
                                        Preview
                                    </button>
                                    {/* A real new tab. An in-app navigation would unmount the
                                        entry form and take the prompt with it. */}
                                    <a
                                        className="ic-open"
                                        href={`/posts/${p.id}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        data-open-for={p.id}
                                    >
                                        Open ↗
                                    </a>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}

            <div className="ic-foot">
                {status === 'loading'
                    ? <span className="ic-status" role="status">Loading the archive…</span> : null}

                {status === 'error' ? (
                    <span className="ic-status ic-status--error" role="alert">
                        {errorText} {posts.length
                            ? `The ${posts.length} images already loaded are still here.`
                            : ''}
                    </span>
                ) : null}

                {complete ? (
                    <span className="ic-status ic-status--done" data-corpus="complete">
                        That is the whole archive — {all.length} image
                        {all.length === 1 ? '' : 's'}.
                    </span>
                ) : (
                    <button
                        type="button"
                        className="ic-more"
                        disabled={status === 'loading'}
                        onClick={loadNext}
                    >
                        {status === 'error' ? 'Try again' : 'Load more'}
                        {totalPages !== null
                            ? ` — ${pagesLoaded} of ${totalPages} pages` : null}
                    </button>
                )}
            </div>

            {preview ? (
                <div className="ic-preview" data-preview="open">
                    <div className="ic-preview-head">
                        <span className={`ic-label${preview.label_is_id ? ' is-id' : ''}`}>
                            {preview.label_is_id ? <>id {preview.label}</> : preview.label}
                        </span>
                        <button
                            type="button"
                            className="ic-preview-close"
                            onClick={() => setPreview(null)}
                        >
                            Close preview
                        </button>
                    </div>
                    {preview.photo_url
                        ? <img className="ic-preview-img" src={cldAt(preview.photo_url, 900)} alt="" />
                        : <p className="ic-empty">This post has no image URL.</p>}
                    <dl className="ic-preview-meta">
                        <div><dt>post id</dt><dd><code>{preview.id}</code></dd></div>
                        {preview.provenance
                            ? <div><dt>source</dt><dd>{preview.provenance}</dd></div> : null}
                        {preview.tags.length
                            ? <div><dt>tags</dt><dd>{preview.tags.join(', ')}</dd></div> : null}
                        <div>
                            <dt>name from</dt>
                            <dd>{preview.label_source.replace(/_/g, ' ')}</dd>
                        </div>
                    </dl>
                    <button
                        type="button"
                        className="ic-preview-pick"
                        onClick={() => toggle(preview)}
                    >
                        {selectedIds.has(preview.id) ? 'Remove from inquiry' : 'Add to inquiry'}
                    </button>
                </div>
            ) : null}
        </div>
    );
}
