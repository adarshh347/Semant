import React, { useMemo, useState } from 'react';
import { RUN_MODES, DEFAULT_MODE, canStartRun } from './runContract';

/**
 * AGENT-DEMO — the entry: a set of images, and a prompt. That is the whole input.
 *
 * ANNOTATION-INDEPENDENCE IS A UI CLAIM HERE, not only a backend one. Nothing on this form asks
 * whether a post has been annotated, and nothing sorts or filters by it. A post with zero
 * regions is offered exactly like one with forty, because the actuators produce evidence from
 * raw pixels and the prompt carries the intent. If this form ever grew an "annotated" filter it
 * would quietly reintroduce the precondition the whole design removed — so the only gate is
 * `canStartRun`, which asks for a corpus and an intention and nothing else.
 *
 * The zero-annotation count is shown deliberately rather than hidden: seeing "no marks yet"
 * beside a selectable image is the demo's argument, made in passing.
 */
export default function RunEntry({
    posts = [],
    busy = false,
    error = '',
    onStart,
    initialPrompt = '',
    initialMode = DEFAULT_MODE,
}) {
    const [selected, setSelected] = useState([]);
    const [tagText, setTagText] = useState('');
    const [prompt, setPrompt] = useState(initialPrompt);
    const [mode, setMode] = useState(initialMode);

    const tags = useMemo(
        () => tagText.split(',').map((t) => t.trim()).filter(Boolean),
        [tagText],
    );

    const ready = canStartRun({ imageIds: selected, tags, prompt });

    const toggle = (id) => setSelected((prev) =>
        prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);

    const submit = (e) => {
        e.preventDefault();
        if (!ready || busy) return;
        onStart?.({ imageIds: selected, tags, prompt: prompt.trim(), mode });
    };

    return (
        <form className="ad-entry" onSubmit={submit} aria-label="Start a run">
            <header className="ad-entry-head">
                <h1 className="ad-title">Give it images and a question.</h1>
                <p className="ad-sub">
                    Nothing needs to be annotated first — the run produces its own evidence from
                    the pictures, and your question is what it is looking for.
                </p>
            </header>

            <fieldset className="ad-field">
                <legend className="ad-legend">Images</legend>
                {posts.length === 0 ? (
                    <p className="ad-empty-note">
                        No images loaded. Name a tag below to select a corpus instead.
                    </p>
                ) : (
                    <ul className="ad-corpus" role="group" aria-label="Choose images">
                        {posts.map((p) => {
                            const on = selected.includes(p.id);
                            const marks = Array.isArray(p.region_annotations)
                                ? p.region_annotations.length : 0;
                            return (
                                <li key={p.id}>
                                    <button
                                        type="button"
                                        className={`ad-thumb${on ? ' is-on' : ''}`}
                                        aria-pressed={on}
                                        data-post-id={p.id}
                                        onClick={() => toggle(p.id)}
                                    >
                                        {p.photo_url
                                            ? <img src={p.photo_url} alt="" loading="lazy" />
                                            : <span className="ad-thumb-blank" aria-hidden="true" />}
                                        <span className="ad-thumb-meta">
                                            <span className="ad-thumb-title">
                                                {p.title || p.id}
                                            </span>
                                            {/* said plainly: an unannotated image is a fine input */}
                                            <span className="ad-thumb-marks">
                                                {marks === 0 ? 'no marks yet' : `${marks} marks`}
                                            </span>
                                        </span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </fieldset>

            <fieldset className="ad-field">
                <legend className="ad-legend">…or by tag</legend>
                <input
                    className="ad-input"
                    type="text"
                    value={tagText}
                    placeholder="altes-museum, schinkel"
                    aria-label="Tags, comma separated"
                    onChange={(e) => setTagText(e.target.value)}
                />
            </fieldset>

            <fieldset className="ad-field">
                <legend className="ad-legend">Your question</legend>
                <textarea
                    className="ad-prompt"
                    rows={3}
                    value={prompt}
                    aria-label="Prompt"
                    placeholder="How does this building turn a dispersed civic ground into a centralized interior?"
                    onChange={(e) => setPrompt(e.target.value)}
                />
            </fieldset>

            <fieldset className="ad-field ad-modes">
                <legend className="ad-legend">What should it do</legend>
                {RUN_MODES.map((m) => (
                    <button
                        key={m}
                        type="button"
                        className={`ad-mode${mode === m ? ' is-on' : ''}`}
                        aria-pressed={mode === m}
                        data-mode={m}
                        onClick={() => setMode(m)}
                    >
                        <span className="ad-mode-name">{m === 'explore' ? 'Explore' : 'Argue'}</span>
                        <span className="ad-mode-hint">
                            {m === 'explore'
                                ? 'Look, and show me what it finds.'
                                : 'Look, then write the case with the evidence beside it.'}
                        </span>
                    </button>
                ))}
            </fieldset>

            {error ? <p className="ad-error" role="alert">{error}</p> : null}

            <button className="ad-start" type="submit" disabled={!ready || busy}>
                {busy ? 'Starting…' : 'Begin'}
            </button>
        </form>
    );
}
