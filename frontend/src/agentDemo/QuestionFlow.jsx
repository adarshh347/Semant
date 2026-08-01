import React, { useState } from 'react';

/**
 * AGENT-DEMO — the ask, the answer, and the run continuing. One thread, not a modal.
 *
 * A2/A3. The planner asks only when a step is genuinely blocked on a param a human could supply,
 * so the question arrives GROUNDED: it names the step it blocks and the param it needs, and its
 * options are the readings the corpus actually supports. Rendering those — rather than a bare
 * text box — is what keeps this an answerable question instead of a chat prompt.
 *
 * Deliberately inline in the run column, not a dialog. A modal would frame the question as an
 * interruption to the run; it IS the run, paused at the point where it stopped being able to
 * proceed honestly. The answer resumes the SAME run (same run_id), which is why the thread reads
 * continuously above and below this block.
 *
 * The free-text box stays available beside the options because the planner's options are its
 * best reading of the corpus, not a closed set of permissible human intentions.
 */
export default function QuestionFlow({ question, busy = false, error = '', onAnswer }) {
    const [text, setText] = useState('');
    if (!question) return null;

    const send = (value) => {
        const v = String(value ?? '').trim();
        if (!v || busy) return;
        onAnswer?.(v);
        setText('');
    };

    return (
        <section className="ad-question" aria-label="The run is asking you something">
            <h2 className="ad-h2 ad-question-text">{question.text}</h2>
            {question.why ? <p className="ad-question-why">{question.why}</p> : null}

            {(question.blocked_step_id || question.param) ? (
                <p className="ad-question-ground">
                    {question.param ? <>needs <code>{question.param}</code></> : null}
                    {question.param && question.blocked_step_id ? ' for ' : null}
                    {question.blocked_step_id ? <code>{question.blocked_step_id}</code> : null}
                </p>
            ) : null}

            {question.options.length ? (
                <ul className="ad-options">
                    {question.options.map((o) => (
                        <li key={o.value}>
                            <button
                                type="button"
                                className="ad-option"
                                data-value={o.value}
                                disabled={busy}
                                onClick={() => send(o.value)}
                            >
                                {o.label}
                            </button>
                        </li>
                    ))}
                </ul>
            ) : null}

            <form
                className="ad-answer-form"
                onSubmit={(e) => { e.preventDefault(); send(text); }}
            >
                <input
                    className="ad-input"
                    type="text"
                    value={text}
                    aria-label="Your answer"
                    placeholder="…or answer in your own words"
                    disabled={busy}
                    onChange={(e) => setText(e.target.value)}
                />
                <button className="ad-answer-send" type="submit" disabled={busy || !text.trim()}>
                    {busy ? 'Resuming…' : 'Answer'}
                </button>
            </form>

            {error ? <p className="ad-error" role="alert">{error}</p> : null}
        </section>
    );
}
