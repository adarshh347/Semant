import React, { useEffect, useMemo, useRef, useState } from 'react';

/**
 * INQUIRY WORKBENCH — the open decision.
 *
 * The existing `/agent` question flow was read first and does not fit. It asks for one EXECUTION
 * PARAMETER — a blocked step needs a `lens`, here are the readings the corpus supports — so its
 * options are values and its whole grounding line is "needs `param` for `step`". This card
 * carries semantic ALTERNATIVES: each option is a different investigation with a different
 * downstream consequence, and the consequence is the thing a person is actually choosing between.
 * Reusing the parameter UI would have meant either dropping the consequences or bolting them onto
 * a component owned by another surface, so this is a new component and the brief anticipated it.
 *
 * ## Preview before submit
 *
 * Selecting an option does not send it. It shows what that option does to the rest of the inquiry
 * and waits. A decision whose consequence is only legible after it is irreversible is not a
 * decision a person made.
 *
 * ## The response id is stable across a retry
 *
 * Generated once per decision and held in a ref, so a 409 followed by a resubmit carries the SAME
 * `response_id`. That is what lets the server tell a stale write from a duplicate one — if the
 * retry minted a fresh id, a response that in fact landed before the conflict would be applied
 * twice, and an append-only history would record two decisions where a person made one.
 */

let seq = 0;
const nextResponseId = () => `res_${(seq += 1)}_${Math.floor(Date.now() % 1e7).toString(36)}`;

export default function DecisionCard({
    decision,
    revision = null,
    busy = false,
    error = '',
    conflict = null,
    autoFocus = true,
    onRespond,
}) {
    const [optionId, setOptionId] = useState('');
    const [freeText, setFreeText] = useState('');
    const headingRef = useRef(null);
    const responseId = useRef('');

    // One response id per decision, minted once and reused by every attempt at it.
    const key = decision?.decision_id || '';
    useMemo(() => { responseId.current = key ? nextResponseId() : ''; }, [key]);

    // `awaiting_user` should move focus to the open decision — but WITHOUT hiding what came
    // before, so the card is focused in place rather than trapping focus in a dialog. A modal
    // would frame the question as an interruption to the inquiry; it is the inquiry, paused.
    useEffect(() => {
        if (autoFocus && headingRef.current) headingRef.current.focus();
    }, [autoFocus, key]);

    if (!decision) return null;

    const selected = decision.options.find((o) => o.option_id === optionId) || null;
    const trimmed = freeText.trim();
    // Free text is an AMENDMENT — the person's own direction — and is never dressed as a
    // selection. Choosing an option and writing a redirect are two different actions and the body
    // says which one this was.
    const action = trimmed && !selected ? 'amend' : 'select';
    const canSubmit = Boolean(selected || trimmed) && !busy;

    const submit = (e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onRespond?.({
            decisionId: decision.decision_id,
            responseId: responseId.current,
            optionId: selected ? selected.option_id : '',
            freeText: trimmed,
            action,
            expectedRevision: revision,
        });
    };

    return (
        <section
            className="iw-panel iw-decision-card"
            aria-label="A decision is open"
            data-decision-id={decision.decision_id}
        >
            <h2
                className="iw-decision-question"
                tabIndex={-1}
                ref={headingRef}
            >
                {decision.question}
            </h2>

            {decision.why_now ? <p className="iw-decision-why-now">{decision.why_now}</p> : null}

            {decision.affected_refs.length ? (
                <p className="iw-quiet iw-decision-affects">
                    affects {decision.affected_refs.map((r) => <code key={r}>{r}</code>)
                        .reduce((acc, el, i) => (i ? [...acc, ', ', el] : [el]), [])}
                </p>
            ) : null}

            <form onSubmit={submit}>
                <ul className="iw-options" role="radiogroup" aria-label="Options">
                    {decision.options.map((o) => (
                        <li key={o.option_id}>
                            <button
                                type="button"
                                role="radio"
                                aria-checked={optionId === o.option_id}
                                className={`iw-option${optionId === o.option_id ? ' is-on' : ''}`}
                                data-option-id={o.option_id}
                                disabled={busy}
                                onClick={() => setOptionId(
                                    optionId === o.option_id ? '' : o.option_id)}
                            >
                                <span className="iw-option-label">
                                    {o.label}
                                    {o.recommended
                                        ? <span className="iw-recommended">recommended</span>
                                        : null}
                                </span>
                                {o.consequence
                                    ? <span className="iw-option-consequence">{o.consequence}</span>
                                    : null}
                            </button>
                        </li>
                    ))}
                </ul>

                {/* The preview. Nothing has been sent yet and the copy says so. */}
                {selected ? (
                    <p className="iw-preview" role="status" data-preview-for={selected.option_id}>
                        <b>If you send this:</b>{' '}
                        {selected.consequence || 'No consequence was described for this option.'}
                        {' '}
                        <span className="iw-quiet">Nothing has been sent yet.</span>
                    </p>
                ) : null}

                {decision.allow_free_text ? (
                    <div className="iw-free">
                        <label className="iw-legend" htmlFor="iw-free-text">
                            …or redirect it in your own words
                        </label>
                        <textarea
                            id="iw-free-text"
                            className="iw-free-text"
                            rows={2}
                            value={freeText}
                            disabled={busy}
                            placeholder="Narrow it to the west end and ignore the rest."
                            onChange={(e) => setFreeText(e.target.value)}
                        />
                        {trimmed ? (
                            <p className="iw-quiet iw-free-note">
                                This is recorded as <b>your direction</b> — appended, attributed to
                                you, and unable to change how any claim is held. It is not a
                                finding about the images.
                            </p>
                        ) : null}
                    </div>
                ) : null}

                {/* A 409 does not discard the input above. The selection and the text are still
                    in state, the card explains what happened, and the same response id goes out
                    again on resubmit. */}
                {conflict ? (
                    <p className="iw-conflict" role="alert" data-conflict="stale">
                        <b>This session moved on while you were deciding.</b>{' '}
                        {conflict.message}
                        {' '}
                        {conflict.refreshed
                            ? 'The view above has been refreshed. Your choice is still selected — '
                              + 'send it again if it still applies.'
                            : 'Your choice is still selected. Re-read the session and send it '
                              + 'again if it still applies.'}
                    </p>
                ) : null}

                {error && !conflict ? <p className="iw-error" role="alert">{error}</p> : null}

                <button className="iw-submit" type="submit" disabled={!canSubmit}>
                    {busy ? 'Sending…' : (action === 'amend' ? 'Send your direction' : 'Send')}
                </button>

                {revision !== null ? (
                    <p className="iw-quiet iw-revision">
                        answering revision {revision}
                    </p>
                ) : null}
            </form>
        </section>
    );
}
