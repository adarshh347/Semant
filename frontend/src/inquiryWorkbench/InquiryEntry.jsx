import React, { useCallback, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { INTERACTION_MODES, DEFAULT_MODE, MODE_COPY, canStartInquiry } from './inquiryContract';
import CorpusPicker from '../inquiryCorpus/CorpusPicker.jsx';
import UploadAndInclude from '../inquiryCorpus/UploadAndInclude.jsx';
import { createCorpusClient } from '../inquiryCorpus/corpusClient.js';

/**
 * The picker, wired to the app's shared TanStack cache.
 *
 * A separate component because `useQueryClient()` is a hook and throws without a provider, so it
 * cannot be called conditionally in `InquiryEntry` — but a component that calls it can be rendered
 * conditionally, which is what lets a test drive the picker with an injected client and the
 * browser get the real cache-sharing one.
 */
function ConnectedCorpusPicker(props) {
    const queryClient = useQueryClient();
    const client = useMemo(() => createCorpusClient({ queryClient }), [queryClient]);
    return <CorpusPicker client={client} {...props} />;
}

/**
 * INQUIRY WORKBENCH — the entry: images, a question, and how much you want to be asked.
 *
 * The corpus is the WHOLE archive, paged, through the same TanStack keys the Gallery uses — the
 * 002R rehearsal could choose from the twenty-four newest images and nothing else, which meant an
 * inquiry could not be asked of most of the corpus. The selection gate is unchanged:
 * `canStartInquiry` is the ONLY thing this form consults, so no future field can quietly become
 * mandatory without that function being where it happened. Nothing here asks whether a post
 * carries regions, percepts or annotations — the plan's Phase-1 exit says "select existing images
 * and enter any prompt", and a filter would reintroduce a precondition the design removed.
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
    corpusClient = null,
    busy = false,
    error = '',
    unavailable = '',
    onStart,
    initialPrompt = '',
    initialMode = DEFAULT_MODE,
    openUpload = null,
}) {
    // POSTS, not ids. An id-only selection cannot render a tray for an image whose page is no
    // longer loaded, and after HARNESS-003C the corpus is paged — so a person who picked on page
    // one and paged to four would watch their own choices turn back into hex strings.
    const [selected, setSelected] = useState([]);
    const [uploaded, setUploaded] = useState([]);
    const [prompt, setPrompt] = useState(initialPrompt);
    const [mode, setMode] = useState(initialMode);

    const imageIds = useMemo(() => selected.map((p) => p.id), [selected]);

    const ready = useMemo(
        () => canStartInquiry({ imageIds, prompt }),
        [imageIds, prompt],
    );

    const select = useCallback((post) => setSelected((prev) =>
        (prev.some((p) => p.id === post.id) ? prev : [...prev, post])), []);

    const deselect = useCallback((id) => setSelected((prev) =>
        prev.filter((p) => p.id !== id)), []);

    /**
     * A freshly uploaded image joins the selection AND the grid.
     *
     * The grid too, not only the tray: a new post lands at the top of page 1 in the API's
     * `_id`-descending order, so waiting for a refetch would leave the person's own upload
     * invisible in the very list they are choosing from. `injected` puts it in front, and the
     * picker's own de-duplication removes the copy when the page it belongs to eventually loads.
     */
    const include = useCallback((posts) => {
        setUploaded((prev) => [...posts, ...prev.filter(
            (p) => !posts.some((q) => q.id === p.id))]);
        setSelected((prev) => {
            const have = new Set(prev.map((p) => p.id));
            return [...prev, ...posts.filter((p) => !have.has(p.id))];
        });
    }, []);

    const submit = (e) => {
        e.preventDefault();
        if (!ready || busy) return;
        onStart?.({ imageIds, prompt: prompt.trim(), mode, posts: selected });
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
                <UploadAndInclude onUploaded={include} openUpload={openUpload} />
                {corpusClient ? (
                    <CorpusPicker
                        client={corpusClient}
                        selected={selected}
                        onSelect={select}
                        onDeselect={deselect}
                        injected={uploaded}
                    />
                ) : (
                    <ConnectedCorpusPicker
                        selected={selected}
                        onSelect={select}
                        onDeselect={deselect}
                        injected={uploaded}
                    />
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
