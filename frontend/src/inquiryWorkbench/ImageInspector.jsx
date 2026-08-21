import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { InspectorContext, useImageInspector } from './imageInspectorContext.js';
import {
    imageCatalogue, inspectorTarget, danglingRefs, countCitations,
    CITATION_SURFACES, SURFACE_LABEL,
} from './imageInspector.js';

/**
 * INQUIRY WORKBENCH — the image reference, made openable.
 *
 * `<ImageRef refId="…"/>` renders where a bare `<code>` used to, and opens a sidebar showing the
 * picture and every object in the session that declared it rests on that picture.
 *
 * ## Temporary, and that is a property not a shortcut
 *
 * The sidebar holds view state and nothing else. It never writes to the session, never posts,
 * never enters the trace, and does not survive a reload — because everything it shows is already
 * IN the session, and a panel that persisted a "currently inspecting" field would have invented
 * the one piece of state on this screen that no producer recorded. Closing it loses nothing.
 *
 * The same reason it is not a modal. A modal would make looking at a picture an interruption to
 * reading the argument; the argument is largely ABOUT the picture, and the reader wants both.
 *
 * ## What it must never imply
 *
 * Putting a claim next to the image it names is the most persuasive layout on this surface, and
 * it is one caption away from a lie. Nothing here was verified against these pixels — the claims
 * are the theorist's reading, held `interpretive` — so the panel says so, once, in words, where
 * the two sit together. A surface that showed a claim beside its picture in silence would let
 * every reader supply the missing sentence themselves, and they would supply the wrong one.
 *
 * ## Degrading without a provider
 *
 * `ImageRef` outside a provider renders the plain token, unclickable. Half the components that
 * carry image references are mounted directly in their own tests, and a chip that threw or
 * rendered a dead button there would make the provider a hidden requirement of every panel.
 */

/**
 * Holds which reference is open, and renders the sidebar.
 *
 * One provider per session view. The `session` is passed down rather than re-derived per chip:
 * the catalogue is a single pass over the graph and every chip on the screen would otherwise
 * repeat it.
 */
export function ImageInspectorProvider({ session, children }) {
    const [openRef, setOpenRef] = useState(null);
    // WHERE FOCUS CAME FROM. A sidebar that takes focus and then drops it on the body when it
    // closes leaves a keyboard reader at the top of the document, several panels from the chip
    // they were reading.
    const opener = useRef(null);

    const inspect = useCallback((ref) => {
        opener.current = typeof document !== 'undefined' ? document.activeElement : null;
        setOpenRef(String(ref || ''));
    }, []);

    const close = useCallback(() => {
        setOpenRef(null);
        const back = opener.current;
        opener.current = null;
        if (back && typeof back.focus === 'function') back.focus();
    }, []);

    // The session can change under an open sidebar — it is streamed. The reference stays open and
    // the panel re-derives, so a stage that lands three more claims about this image ADDS them
    // rather than closing the panel out from under someone.
    const value = useMemo(
        () => ({ openRef, inspect, close, session }),
        [openRef, inspect, close, session],
    );

    return (
        <InspectorContext.Provider value={value}>
            {children}
            {openRef !== null
                ? <ImageInspector session={session} refId={openRef} onClose={close} />
                : null}
        </InspectorContext.Provider>
    );
}

/**
 * One image reference, as a button.
 *
 * `label` exists for the thumbnail case, where the click target is a picture rather than a token.
 */
export function ImageRef({ refId, children = null, className = '', title = '' }) {
    const ctx = useImageInspector();
    const ref = String(refId || '');
    const body = children ?? <code>{ref || '—'}</code>;

    if (!ctx || !ref) {
        return <span className={`iw-imgref is-inert ${className}`.trim()}>{body}</span>;
    }
    const open = ctx.openRef === ref;
    return (
        <button
            type="button"
            className={`iw-imgref ${className}`.trim()}
            data-image-ref={ref}
            // A TOGGLE, because it says it is one. `aria-pressed` on a control that never
            // un-presses tells a screen reader the second click will close this and then does
            // not — so the second click closes it.
            aria-pressed={open}
            title={open ? `Close ${ref}` : (title || `What rests on ${ref}`)}
            onClick={() => (open ? ctx.close() : ctx.inspect(ref))}
        >
            {body}
        </button>
    );
}

/** A list of refs, comma-joined — the shape `WhyHere` and the unit rows already print. */
export function ImageRefList({ refs = [], className = '' }) {
    if (!refs.length) return null;
    return (
        <span className={`iw-imgref-list ${className}`.trim()}>
            {refs.map((r, i) => (
                <React.Fragment key={`${r}-${i}`}>
                    {i ? ', ' : ''}
                    <ImageRef refId={r} />
                </React.Fragment>
            ))}
        </span>
    );
}

const STATUS_WORD = (s) => (s && s.value ? s.value : '');

/**
 * The sidebar.
 *
 * Exported on its own so it can be mounted without a provider in tests — the resolution states
 * are the interesting part and they should not need a click to reach.
 */
export function ImageInspector({ session, refId, onClose }) {
    const target = useMemo(() => inspectorTarget(session, refId), [session, refId]);
    const panel = useRef(null);

    // ESCAPE, and focus into the panel on open. Bound on the document rather than the panel: the
    // sidebar is not modal, so the reader may well be scrolled into the ledger with focus on a
    // ledger control when they decide they are done with it.
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
        document.addEventListener('keydown', onKey);
        panel.current?.focus();
        return () => document.removeEventListener('keydown', onKey);
    }, [onClose, refId]);

    const { entry, resolved, citations } = target;
    const total = countCitations(citations);

    return (
        <aside
            className="iw-inspector"
            ref={panel}
            tabIndex={-1}
            aria-label={`What rests on ${target.ref}`}
            data-image-inspector={target.ref}
            data-resolved={String(resolved)}
            data-citation-count={total}
        >
            <header className="iw-inspector-head">
                <div className="iw-inspector-title">
                    <code className="iw-inspector-ref">{target.ref}</code>
                    {entry?.title ? <b>{entry.title}</b> : null}
                </div>
                <button
                    type="button"
                    className="iw-expand iw-inspector-close"
                    data-inspector-close="true"
                    onClick={() => onClose?.()}
                >
                    Close
                </button>
            </header>

            {resolved
                ? <ResolvedImage entry={entry} />
                : <UnresolvedRef refId={target.ref} count={total} />}

            <CitationLedger citations={citations} total={total} resolved={resolved} />
        </aside>
    );
}

/** The picture, and every declared fact about the picture itself. */
function ResolvedImage({ entry }) {
    return (
        <div className="iw-inspector-image" data-post-id={entry.post_id}>
            {entry.image_url
                ? <img src={entry.image_url} alt={entry.title || entry.post_id} loading="lazy" />
                : (
                    // NOT a broken `<img>`. A url the session never carried and a url that failed
                    // to load look identical to a reader once the browser has drawn its own
                    // placeholder, and they send you to opposite repairs.
                    <p className="iw-inspector-blank" data-no-url="true">
                        This session carries no url for this image. Nothing was fetched and failed;
                        there was nothing to fetch.
                    </p>
                )}

            <dl className="iw-inspector-facts">
                <div>
                    <dt>read</dt>
                    <dd data-readable={String(entry.readable)}>
                        {entry.readable === true ? 'yes — the run fetched and read it.' : null}
                        {entry.readable === false
                            ? 'no. The run could not read this image, so anything below that '
                              + 'names it was written without it.'
                            : null}
                        {entry.readable === null
                            ? 'not recorded. No post record declared whether this was read, which '
                              + 'is not the same as a record saying it was.'
                            : null}
                    </dd>
                </div>
                {entry.note ? <div><dt>note</dt><dd>{entry.note}</dd></div> : null}
                {/* The fingerprint, for the reason the ledger prints it: the phase's claim is that
                    no source post changed, and a comparison is evidence where a tick is an
                    assurance. */}
                {entry.fingerprint ? (
                    <div>
                        <dt>fingerprint</dt>
                        <dd><code>{entry.fingerprint.slice(0, 16)}…</code></dd>
                    </div>
                ) : null}
                {!entry.in_posts ? (
                    <div>
                        <dt>read ledger</dt>
                        <dd data-not-in-posts="true">
                            This image was handed to the reading stage and does not appear in the
                            list of posts the run recorded reading. That is an inconsistency
                            upstream, not a display gap.
                        </dd>
                    </div>
                ) : null}
            </dl>
        </div>
    );
}

/** A reference naming a picture the session does not carry. */
function UnresolvedRef({ refId, count }) {
    return (
        <p className="iw-inspector-unresolved" role="alert" data-unresolved={refId}>
            <b>This names an image the session does not carry.</b>
            {' '}
            {count > 0
                ? `${count} object${count === 1 ? '' : 's'} below cite it, so the reference was `
                  + 'produced by something that could see it. The catalogue this session sent has '
                  + 'no entry with that id — an inconsistency upstream, shown rather than dropped.'
                : 'Nothing cites it either, so there is nothing here to show and nothing to '
                  + 'repair from this panel alone.'}
        </p>
    );
}

/**
 * What rests on it, by surface.
 *
 * Every surface prints its count including zero, and a zero gets a sentence. A surface that
 * rendered nothing when empty would leave a reader unable to tell "no claim names this picture"
 * from "the claims have not arrived yet", which are the two states this whole workbench exists to
 * keep apart.
 */
function CitationLedger({ citations, total, resolved }) {
    return (
        <section className="iw-inspector-rests" aria-label="What rests on this image">
            <h3 className="iw-h3">
                What rests on this
                <span className="iw-inspector-total" data-total={total}>{total}</span>
            </h3>

            {/* ONCE, IN WORDS, where the picture and the claims sit together. */}
            <p className="iw-quiet iw-inspector-caveat" data-caveat="not-verified">
                Nothing below was checked against these pixels. These are the objects that
                <em> declared </em> they rest on this image; the reading they come from is held
                interpretive, and putting it beside the picture does not raise it.
            </p>

            {total === 0 && resolved ? (
                <p className="iw-inspector-uncited" data-uncited="true">
                    <b>Nothing in this session cites this image.</b> It was handed to the run and
                    produced no recorded thought — which is a finding about the run, not a panel
                    that failed to load.
                </p>
            ) : null}

            <ul className="iw-inspector-surfaces">
                {CITATION_SURFACES.map((surface) => (
                    <li
                        key={surface}
                        className={`iw-inspector-surface${citations[surface].length ? '' : ' is-empty'}`}
                        data-surface={surface}
                        data-count={citations[surface].length}
                    >
                        <div className="iw-inspector-surface-head">
                            <span className="iw-led-count">{citations[surface].length}</span>
                            <span className="iw-led-label">{SURFACE_LABEL[surface]}</span>
                        </div>
                        {citations[surface].length ? (
                            <ul className="iw-inspector-cites">
                                {citations[surface].map((c) => (
                                    <li key={c.id} data-cite-id={c.id}>
                                        <span className="iw-inspector-cite-head">
                                            {c.kind ? (
                                                <span className="iw-kind">
                                                    {c.kind.replace(/_/g, ' ')}
                                                </span>
                                            ) : null}
                                            <code>{c.id}</code>
                                            {STATUS_WORD(c.status) ? (
                                                <span className="iw-inspector-cite-status">
                                                    {STATUS_WORD(c.status)}
                                                </span>
                                            ) : null}
                                        </span>
                                        {c.text ? <p className="iw-led-text">{c.text}</p> : null}
                                    </li>
                                ))}
                            </ul>
                        ) : null}
                    </li>
                ))}
            </ul>
        </section>
    );
}

/**
 * The images nobody cited, and the references naming pictures that are not here.
 *
 * Rendered by the ledger rather than by the sidebar: these are properties of the SESSION, and a
 * reader only meets them if they happen to open the right chip otherwise. Returns nothing when
 * both are empty, which is the ordinary case.
 */
export function ImageAbsences({ session }) {
    const catalogue = useMemo(() => imageCatalogue(session), [session]);
    const uncited = catalogue.filter((e) => e.citation_count === 0);
    // The SAME selector the sidebar resolves through. Re-deriving "which refs do not resolve"
    // here would give this panel its own answer to the question the chips answer, and the two
    // would drift on the first change to either.
    const dangling = useMemo(() => danglingRefs(session).map((d) => ({
        ref: d.ref,
        citers: CITATION_SURFACES.flatMap((k) => d.citations[k].map((c) => c.id)),
    })), [session]);

    if (!uncited.length && !dangling.length) return null;

    return (
        <section className="iw-panel iw-image-absences" aria-label="Images and references that do not line up">
            <h2 className="iw-h2">Images and references that do not line up</h2>
            {uncited.length ? (
                <div data-absence="uncited" data-count={uncited.length}>
                    <p>
                        <b>{uncited.length} image{uncited.length === 1 ? ' was' : 's were'} handed
                        to this run and cited by nothing.</b> Not an error on its own — a reading
                        may simply have had nothing to say — but it is the difference between an
                        image that was considered and one that was carried.
                    </p>
                    <ul className="iw-inspector-cites">
                        {uncited.map((e) => (
                            <li key={e.post_id} data-uncited-post={e.post_id}>
                                <ImageRef refId={e.post_id} />
                                {e.title ? <span> {e.title}</span> : null}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
            {dangling.length ? (
                <div data-absence="dangling" data-count={dangling.length}>
                    <p>
                        <b>{dangling.length} reference{dangling.length === 1 ? '' : 's'} name
                        {dangling.length === 1 ? 's' : ''} an image this session does not
                        carry.</b> Something produced these while able to see the image, and the
                        catalogue that arrived has no entry for it.
                    </p>
                    <ul className="iw-inspector-cites">
                        {dangling.map((d) => (
                            <li key={d.ref} data-dangling-ref={d.ref}>
                                <ImageRef refId={d.ref} />
                                <span className="iw-quiet"> cited by {d.citers.join(', ')}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </section>
    );
}

export default ImageInspector;
