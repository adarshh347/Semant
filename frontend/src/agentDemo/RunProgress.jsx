import React from 'react';
import { IS_LIVE, IS_BLOCKED_ON_HUMAN, stopSummary } from './runContract';

const STATUS_TEXT = {
    pending: 'Starting…',
    running: 'Looking…',
    awaiting_answer: 'Waiting on you',
    complete: 'Complete',
    stopped: 'Stopped',
};

/**
 * AGENT-DEMO — the loop as it advances, round by round.
 *
 * NO PROGRESS BAR, deliberately, and it is the same rule the passage rail holds: the loop does
 * not know how many rounds it will take, so any bar would be inventing a denominator. A run that
 * re-plans twice is not "60% done". What can honestly be shown is what has HAPPENED — the rounds
 * that closed, what each planned, and the weakest link it came out with — plus a live marker
 * that says the thing is still moving without claiming to know how far.
 *
 * `weakest_link` is rendered as the run's own confidence floor rather than a score: it is the
 * least-supported thing the round rests on, which is the number a reader should actually watch.
 */
export default function RunProgress({ view }) {
    if (!view) return null;
    const live = IS_LIVE(view.status);
    const stop = stopSummary(view);

    return (
        <section className="ad-progress" aria-label="Run progress">
            <header className="ad-progress-head">
                <span
                    className={`ad-status ad-status--${view.status}`}
                    role="status"
                    data-status={view.status}
                >
                    {live ? <span className="ad-pulse" aria-hidden="true" /> : null}
                    {STATUS_TEXT[view.status] || view.status}
                </span>
                {view.weakest_link !== null ? (
                    <span className="ad-weakest" title="The least-supported link this run rests on">
                        weakest link <b>{view.weakest_link.toFixed(2)}</b>
                    </span>
                ) : null}
            </header>

            <p className="ad-intention">{view.intention}</p>

            {view.rounds.length === 0 ? (
                <p className="ad-quiet">
                    {live ? 'Planning the first round…' : 'No rounds ran.'}
                </p>
            ) : (
                <ol className="ad-rounds">
                    {view.rounds.map((r, i) => {
                        const steps = Array.isArray(r?.plan?.steps) ? r.plan.steps : [];
                        return (
                            <li className="ad-round" key={r?.round ?? i} data-round={r?.round ?? i + 1}>
                                <div className="ad-round-head">
                                    <span className="ad-round-n">Round {r?.round ?? i + 1}</span>
                                    {typeof r?.weakest_link === 'number' ? (
                                        <span className="ad-round-weak">{r.weakest_link.toFixed(2)}</span>
                                    ) : null}
                                </div>
                                {steps.length ? (
                                    <ul className="ad-steps">
                                        {steps.map((s, j) => (
                                            <li className="ad-step" key={`${s}-${j}`}>{s}</li>
                                        ))}
                                    </ul>
                                ) : null}
                                {r?.note ? <p className="ad-round-note">{r.note}</p> : null}
                            </li>
                        );
                    })}
                </ol>
            )}

            {IS_BLOCKED_ON_HUMAN(view.status) ? (
                <p className="ad-quiet">The loop stopped to ask you something.</p>
            ) : null}

            {stop ? (
                <p className={`ad-stop ad-stop--${stop.tone}`} role="status">{stop.text}</p>
            ) : null}
        </section>
    );
}
