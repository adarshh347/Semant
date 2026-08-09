import React from 'react';
import {
    STAGE_LABEL, STAGE_OUTCOME_COPY, STAGE_NAMES, underperformingStages, formatDuration,
    downstreamOf, barrenAfter, earliestFailure,
} from './inquiryContract';

/**
 * INQUIRY WORKBENCH — when a run produced less than it should have, said first and said plainly.
 *
 * The 002R rehearsal ended `EXHAUSTED` with a long, perceptive VLM paragraph on screen and nothing
 * else. Everything a person needed in order to understand that was already in the record — which
 * stage failed, what entered it, what came out, what therefore never ran — and none of it was
 * shown. The gate's ruling was `REPAIR PHASE 1`, and this card is the part of the repair that
 * makes the failure legible instead of leaving a reader to infer it from a short answer.
 *
 * ## What it may not say
 *
 * Not "nothing new was found". That sentence describes an inquiry that looked and came back
 * empty-handed, and it is the wrong description of a compiler that stopped mid-output. The
 * difference matters because it points at different repairs: one is a question about the images,
 * the other is a budget in a model call.
 *
 * ## Open, and above the prose
 *
 * A collapsed diagnosis under a fluent paragraph is a diagnosis nobody reads. The useful partial
 * artifacts stay — below this, not instead of it — because a truncated run's reading is often
 * genuinely worth having, and hiding it would be its own dishonesty.
 */

export default function DiagnosisCard({ session }) {
    if (!session) return null;

    const stages = session.stages || [];
    const failed = underperformingStages(session);
    const stateBad = ['exhausted', 'refused', 'error'].includes(session.state.value);
    if (!failed.length && !stateBad) return null;

    const worst = earliestFailure(failed);

    const never = worst ? downstreamOf(worst.stage.value, stages) : [];
    const barren = worst ? barrenAfter(worst.stage.value, stages) : [];

    // Is the only prose on screen the theorist's reading? That is the exact shape of the 002R
    // rehearsal — an abundant paragraph standing in for an inquiry that never happened.
    const readingOnly = Boolean(session.graph.reading.text)
        && !session.synthesis
        && session.graph.claims.length === 0;

    const modes = [...new Set(stages
        .map((s) => s.execution_mode.value)
        .filter(Boolean))];

    return (
        <section className="iw-panel iw-diagnosis" aria-label="What went wrong" data-diagnosis="open">
            <h2 className="iw-diagnosis-head">
                {worst
                    ? <>This run stopped short at the {STAGE_LABEL[worst.stage.value]
                        ? STAGE_LABEL[worst.stage.value].toLowerCase() : worst.stage.value} stage.</>
                    : <>This run ended without completing.</>}
            </h2>

            {worst ? (
                <>
                    <p className="iw-diagnosis-what" data-failed-stage={worst.stage.value}>
                        <b>{worst.outcome.value}</b> —{' '}
                        {STAGE_OUTCOME_COPY[worst.outcome.value] || 'the stage reported an outcome '
                            + 'this client does not recognise.'}
                    </p>

                    {/* What entered and what emerged, from the stage's own counters. Never
                        inferred: a count this surface worked out would be a guess wearing the
                        backend's authority, and the numbers are the whole diagnosis. */}
                    <dl className="iw-diagnosis-io">
                        <div>
                            <dt>entered</dt>
                            <dd data-entered={String(worst.input_count)}>
                                {worst.input_count === null
                                    ? 'not recorded' : `${worst.input_count} objects`}
                            </dd>
                        </div>
                        <div>
                            <dt>emerged</dt>
                            <dd data-emerged={String(worst.output_count)}>
                                {worst.output_count === null
                                    ? 'not recorded' : `${worst.output_count} objects`}
                            </dd>
                        </div>
                        {worst.finish_reason ? (
                            <div>
                                <dt>finish reason</dt>
                                <dd data-finish={worst.finish_reason}>
                                    <code>{worst.finish_reason}</code>
                                    {worst.finish_reason === 'length' ? (
                                        <span className="iw-quiet">
                                            {' '}— it ran out of output budget, not out of things
                                            to say.
                                        </span>
                                    ) : null}
                                </dd>
                            </div>
                        ) : null}
                        {worst.actual_calls !== null || worst.planned_calls !== null ? (
                            <div>
                                <dt>calls</dt>
                                <dd>
                                    {worst.actual_calls === null ? '—' : worst.actual_calls}
                                    {worst.planned_calls !== null
                                        ? ` of ${worst.planned_calls} planned` : ''}
                                </dd>
                            </div>
                        ) : null}
                        <div>
                            <dt>took</dt>
                            <dd>{formatDuration(worst.duration_ms)}</dd>
                        </div>
                    </dl>

                    {worst.summary ? (
                        <p className="iw-diagnosis-summary">{worst.summary}</p>
                    ) : null}
                </>
            ) : null}

            {never.length || barren.length ? (
                <div className="iw-diagnosis-downstream" data-downstream="true">
                    <h3 className="iw-h3">What therefore did not happen</h3>
                    {never.length ? (
                        <p>
                            <b>Never ran:</b>{' '}
                            {never.map((n) => STAGE_LABEL[n] || n).join(', ')}.
                        </p>
                    ) : null}
                    {/* Ran-and-produced-nothing is a different fact from never-ran, and a reader
                        deciding what to fix needs to know which. */}
                    {barren.length ? (
                        <p>
                            <b>Ran and produced nothing:</b>{' '}
                            {barren.map((s) => `${STAGE_LABEL[s.stage.value] || s.stage.value} `
                                + `(${s.outcome.value})`).join(', ')}.
                        </p>
                    ) : null}
                </div>
            ) : null}

            {readingOnly ? (
                <p className="iw-diagnosis-reading-only" data-reading-only="true">
                    <b>The prose below is the scene reading, and only that.</b> No claim, observable
                    or decision was produced from it, so what you are about to read is one model's
                    impression of the pictures rather than an inquiry into them. It is kept because
                    it is often worth having — not because it answers the question.
                </p>
            ) : null}

            {session.stop_reason ? (
                <p className="iw-diagnosis-stop" data-stop-reason="true">{session.stop_reason}</p>
            ) : null}

            {session.gaps.length ? (
                <p className="iw-quiet">
                    Gaps recorded: {session.gaps.join('; ')}
                </p>
            ) : null}

            {/* Replay / live / fixture, so a disappointing run cannot be mistaken for a
                disappointing MODEL when it was a replay of a frozen one. */}
            <p className="iw-quiet iw-diagnosis-topology" data-topology-modes={modes.join(',')}>
                {modes.length
                    ? <>Stage execution: {modes.join(', ')}.</>
                    : <>No stage declared whether it ran live or from a fixture.</>}
                {' '}
                This phase&apos;s one capability is a declared simulation either way.
            </p>
        </section>
    );
}
