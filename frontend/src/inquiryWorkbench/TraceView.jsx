import React, { useState } from 'react';

/**
 * INQUIRY WORKBENCH — the trace: who moved this, from where to where, and why.
 *
 * Append-only, in the order it happened, with the actor KIND on every row. The board's phase gate
 * is "every automatic or human decision is present in the trace", and the thing that makes that
 * checkable rather than decorative is that a reader can see a model, the system and a person in
 * one column and tell which is which without reading the reason.
 *
 * Closed by default and opened by a button, because a trace is what you consult when something
 * looks wrong — not the first thing a reader should meet. It never disappears, though, including
 * on a completed session: an inquiry whose reasoning becomes unavailable once it succeeds is
 * exactly as inspectable as one persuasive paragraph.
 */

const ACTOR_COPY = { model: 'model', system: 'system', user: 'you' };

export default function TraceView({ trace = [], defaultOpen = false }) {
    const [open, setOpen] = useState(defaultOpen);
    if (!trace.length) return null;

    return (
        <section className="iw-panel iw-trace" aria-label="Trace">
            <div className="iw-trace-head">
                <h2 className="iw-h2">Trace</h2>
                <button
                    type="button"
                    className="iw-expand"
                    aria-expanded={open}
                    onClick={() => setOpen((v) => !v)}
                >
                    {open ? 'Hide' : `Show ${trace.length} steps`}
                </button>
            </div>

            {open ? (
                <ol className="iw-trace-list">
                    {trace.map((e, i) => {
                        const kind = e.actor_kind.known ? e.actor_kind.value : 'unknown';
                        return (
                            <li
                                className={`iw-trace-event iw-trace-event--${kind}`}
                                key={e.event_id || i}
                                data-actor-kind={kind}
                                data-event-id={e.event_id}
                            >
                                <div className="iw-trace-line">
                                    <span className={`iw-actor iw-actor--${kind}`}>
                                        {kind === 'unknown'
                                            ? <>unknown actor
                                                (<span className="iw-badge-raw">
                                                    {e.actor_kind.value}
                                                </span>)</>
                                            : ACTOR_COPY[kind]}
                                    </span>
                                    <span className="iw-trace-actor-name">{e.actor}</span>
                                    {e.at
                                        ? <time className="iw-trace-at" dateTime={e.at}>{e.at}</time>
                                        : null}
                                    {e.revision !== null
                                        ? <span className="iw-trace-rev">rev {e.revision}</span>
                                        : null}
                                </div>
                                {e.transition
                                    ? <p className="iw-trace-transition">{e.transition}</p>
                                    : null}
                                {e.reason ? <p className="iw-quiet">{e.reason}</p> : null}
                                {e.refs.length ? (
                                    <p className="iw-quiet iw-trace-refs">
                                        {e.refs.map((r) => <code key={r}>{r}</code>)
                                            .reduce((acc, el, i2) =>
                                                (i2 ? [...acc, ', ', el] : [el]), [])}
                                    </p>
                                ) : null}
                            </li>
                        );
                    })}
                </ol>
            ) : null}
        </section>
    );
}
