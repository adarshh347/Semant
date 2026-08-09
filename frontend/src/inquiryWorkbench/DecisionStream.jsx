import React from 'react';

/**
 * INQUIRY WORKBENCH — every choice that was made, in one chronology.
 *
 * Automatic choices and human ones share this list. That is the board's rule made structural
 * rather than promised: *auto mode means no interruption, not invisible agency*. A system record
 * gets the same row, the same size and the same detail as a user record, and the ONLY difference
 * is the sentence naming who chose — which is the fact a reader is actually after.
 *
 * The failure this prevents is specific. A surface that showed user decisions prominently and
 * logged automatic ones somewhere quieter would make auto mode look like a mode in which nothing
 * was decided, when it is the mode in which the most was decided without asking.
 */

const DECIDER_COPY = {
    user: 'You chose',
    system: 'Semant chose, without asking',
    model: 'A model chose',
};

const ACTION_COPY = {
    select: 'selected',
    reject: 'rejected',
    skip: 'skipped',
    redirect: 'redirected the inquiry',
    amend: 'amended',
};

export default function DecisionStream({ records = [] }) {
    if (!records.length) return null;

    return (
        <section className="iw-panel iw-decisions" aria-label="Decisions">
            <h2 className="iw-h2">What has been decided</h2>
            <ol className="iw-decision-list">
                {records.map((r) => (
                    <DecisionRecordRow key={r.record_id || r.decision_id} record={r} />
                ))}
            </ol>
        </section>
    );
}

export function DecisionRecordRow({ record: r }) {
    const decider = r.decider.known ? r.decider.value : 'unknown';
    const action = r.action.known ? ACTION_COPY[r.action.value] : `did "${r.action.value}"`;

    return (
        <li
            className={`iw-decision iw-decision--${decider}`}
            data-decider={decider}
            data-decision-id={r.decision_id}
        >
            <div className="iw-decision-head">
                <span className={`iw-decider iw-decider--${decider}`}>
                    {decider === 'unknown'
                        ? <>an actor this client does not recognise
                            (<span className="iw-badge-raw">{r.decider.value}</span>)</>
                        : DECIDER_COPY[decider]}
                </span>
                {r.at ? <time className="iw-decision-at" dateTime={r.at}>{r.at}</time> : null}
            </div>

            {r.question ? <p className="iw-decision-q">{r.question}</p> : null}

            <p className="iw-decision-choice">
                {action}
                {r.selected_label ? <> <b>{r.selected_label}</b></> : null}
            </p>

            {/* Free text is the person's own words and is attributed as a DIRECTION. It is not a
                finding, it cannot upgrade a claim, and the label says so in the DOM rather than
                in a tooltip — "your direction", never "visual finding". */}
            {r.free_text ? (
                <p className="iw-decision-free">
                    <span className="iw-author iw-author--user">your direction</span>
                    <q>{r.free_text}</q>
                </p>
            ) : null}

            {r.rationale ? <p className="iw-quiet iw-decision-why">{r.rationale}</p> : null}

            {r.affected_refs.length ? (
                <p className="iw-quiet iw-decision-refs">
                    changed {r.affected_refs.map((ref) => <code key={ref}>{ref}</code>)
                        .reduce((acc, el, i) => (i ? [...acc, ', ', el] : [el]), [])}
                </p>
            ) : null}
        </li>
    );
}
