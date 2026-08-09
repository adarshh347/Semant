import React, { useMemo, useState } from 'react';
import { INTERACTION_MODES, DEFAULT_MODE, MODE_COPY, canStartInquiry } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the entry: images, a question, and how much you want to be asked.
 *
 * The corpus source is the same one `/agent` uses (`GET /api/v1/posts`), and the selection gate
 * is the same shape: `canStartInquiry` is the ONLY thing this form consults, so no future field
 * can quietly become mandatory without that function being where it happened. Nothing here asks
 * whether a post carries regions, percepts or annotations — the plan's Phase-1 exit says "select
 * existing images and enter any prompt", and a filter would reintroduce a precondition the design
 * removed.
 *
 * ## The mode is the one field that is not obvious
 *
 * `auto | consult | step` decides how often a person is interrupted, which is a real choice with
 * real consequences and is therefore explained in plain language rather than named and left. The
 * copy for each is a sentence about what will HAPPEN to you, not a definition of the word — and
 * the auto blurb says out loud that auto still records every choice and still stops before
 * anything is accepted, because the failure mode of an "automatic" mode is a person assuming it
 * went and did things quietly.
 */
export default function InquiryEntry({
    posts = [],
    busy = false,
    error = '',
    unavailable = '',
    onStart,
    initialPrompt = '',
    initialMode = DEFAULT_MODE,
}) {
    const [selected, setSelected] = useState([]);
    const [prompt, setPrompt] = useState(initialPrompt);
    const [mode, setMode] = useState(initialMode);

    const ready = useMemo(
        () => canStartInquiry({ imageIds: selected, prompt }),
        [selected, prompt],
    );

    const toggle = (id) => setSelected((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

    const submit = (e) => {
        e.preventDefault();
        if (!ready || busy) return;
        onStart?.({ imageIds: selected, prompt: prompt.trim(), mode });
    };

    return (
        <form className="iw-entry" onSubmit={submit} aria-label="Start an inquiry">
            <header className="iw-entry-head">
                <h1 className="iw-title">A question, and the pictures to ask it of.</h1>
                <p className="iw-sub">
                    Semant reads the images, breaks its own reading into claims you can inspect,
                    and shows you what it would have to observe to support each one. Where a fork
                    would genuinely change the inquiry, it stops and asks.
                </p>
            </header>

            {/* THE PRODUCTION UNAVAILABLE STATE. Not a fixture, not a demo — the page says the
                API is missing and offers nothing in its place. A surface that substituted a
                fixture here would turn an outage into a convincing demonstration. */}
            {unavailable ? (
                <p className="iw-unavailable" role="status" data-unavailable="api">
                    <b className="iw-unavailable-head">The inquiry API is not available.</b>
                    <span className="iw-unavailable-detail">{unavailable}</span>
                    <span className="iw-quiet">
                        Nothing is being shown in its place. There is no offline mode here — a
                        fixture standing in for an absent backend would look exactly like a
                        working one.
                    </span>
                </p>
            ) : null}

            <fieldset className="iw-field">
                <legend className="iw-legend">Images</legend>
                {posts.length === 0 ? (
                    <p className="iw-quiet">No images loaded.</p>
                ) : (
                    <ul className="iw-corpus" role="group" aria-label="Choose images">
                        {posts.map((p) => {
                            const on = selected.includes(p.id);
                            return (
                                <li key={p.id}>
                                    <button
                                        type="button"
                                        className={`iw-thumb${on ? ' is-on' : ''}`}
                                        aria-pressed={on}
                                        data-post-id={p.id}
                                        onClick={() => toggle(p.id)}
                                    >
                                        {p.photo_url
                                            ? <img src={p.photo_url} alt="" loading="lazy" />
                                            : <span className="iw-thumb-blank" aria-hidden="true" />}
                                        <span className="iw-thumb-title">{p.title || p.id}</span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </fieldset>

            <fieldset className="iw-field">
                <legend className="iw-legend">Your question</legend>
                <textarea
                    className="iw-prompt"
                    rows={3}
                    value={prompt}
                    aria-label="Prompt"
                    placeholder="How does this building turn a dispersed civic ground into a centralized interior?"
                    onChange={(e) => setPrompt(e.target.value)}
                />
            </fieldset>

            <fieldset className="iw-field iw-modes">
                <legend className="iw-legend">How often should it ask you</legend>
                <div className="iw-mode-list" role="radiogroup" aria-label="Interaction mode">
                    {INTERACTION_MODES.map((m) => (
                        <button
                            key={m}
                            type="button"
                            role="radio"
                            aria-checked={mode === m}
                            className={`iw-mode${mode === m ? ' is-on' : ''}`}
                            data-mode={m}
                            onClick={() => setMode(m)}
                        >
                            <span className="iw-mode-name">{MODE_COPY[m].title}</span>
                            <span className="iw-mode-hint">{MODE_COPY[m].hint}</span>
                        </button>
                    ))}
                </div>
            </fieldset>

            {error ? <p className="iw-error" role="alert">{error}</p> : null}

            <button className="iw-start" type="submit" disabled={!ready || busy}>
                {busy ? 'Starting…' : 'Begin'}
            </button>
        </form>
    );
}
