import React, { useEffect, useState } from 'react';
import {
    STAGE_LABEL, STAGE_OUTCOME_COPY, EXECUTION_MODE_COPY, TRUNCATION_SOURCE_COPY,
    formatDuration, stageElapsedMs,
} from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the machinery, while it is running.
 *
 * The 002R rehearsal's whole visibility failure in one panel. A person selected four images, asked
 * a real question, and watched `Starting…` for a long time; the backend was recording every stage
 * transition the entire time and the client never read the list. This renders it.
 *
 * ## What it may not do
 *
 * No percentage and no estimated completion. The inquiry does not know how long a model call will
 * take and does not know how many claims will come back, so a bar would be inventing a denominator
 * and an ETA would be inventing a rate. What CAN be shown honestly is what has happened, what is
 * happening now, and how long the current thing has been going — which is the same discipline
 * `RunProgress` settled on for `/agent`, and for the same reason.
 *
 * "4 image readings plus one synthesis planned" appears only when the stage declares
 * `planned_calls`. A count this surface derived would be a guess wearing the backend's authority.
 *
 * ## Elapsed is not duration
 *
 * They are different words on screen and different fields underneath. `duration_ms` is what the
 * stage reported when it finished; elapsed is this client counting from `started_at`. A stage that
 * never said when it started shows neither, because a clock counting from an unknown origin is a
 * fabricated measurement — and the most believable kind.
 */

const TICK_MS = 1000;

export default function StageActivity({ stages = [], working = false, now = null, open = null }) {
    // Visible by default while working, and ALSO when a stage underperformed — the machinery is
    // reference material after an ordinary run and it is the first thing you want after a bad one.
    // Otherwise it collapses; it never disappears.
    //
    // `override` is null until the person touches the toggle, and only then does their choice win.
    // Initialising a `useState` from `working` would have frozen the panel at whatever the session
    // was doing on the first render, which is exactly wrong for a panel about a session that
    // changes state under it.
    const [override, setOverride] = useState(null);
    const [tick, setTick] = useState(() => (now === null ? Date.now() : now));

    const anyRunning = stages.some((s) => s.running);
    const anyFailed = stages.some((s) => s.underperformed);
    const expanded = override ?? (open === null ? (working || anyFailed) : open);

    useEffect(() => {
        // The clock runs only while something is actually running, and only when the caller did
        // not pin `now` — a test that pins it gets a still frame rather than a timer.
        if (now !== null || !anyRunning) return undefined;
        const id = setInterval(() => setTick(Date.now()), TICK_MS);
        return () => clearInterval(id);
    }, [now, anyRunning]);

    if (!stages.length) {
        return working ? (
            <section className="iw-panel iw-stages" aria-label="Stage activity">
                <h2 className="iw-h2">What it is doing</h2>
                <p className="iw-quiet" data-stages="none">
                    No stage has reported yet. This is the session before its first checkpoint, not
                    a session doing nothing.
                </p>
            </section>
        ) : null;
    }

    const at = now === null ? tick : now;

    return (
        <section className="iw-panel iw-stages" aria-label="Stage activity">
            <div className="iw-stages-head">
                <h2 className="iw-h2">What it is doing</h2>
                <button
                    type="button"
                    className="iw-expand"
                    aria-expanded={expanded}
                    onClick={() => setOverride(!expanded)}
                >
                    {expanded ? 'Hide' : `Show ${stages.length} stage`}
                    {expanded || stages.length === 1 ? '' : 's'}
                </button>
            </div>

            {expanded ? (
                <ol className="iw-stage-list">
                    {stages.map((s, i) => (
                        <StageRow key={s.event_id || i} stage={s} at={at} />
                    ))}
                </ol>
            ) : null}
        </section>
    );
}

export function StageRow({ stage: s, at }) {
    const name = s.stage.known ? s.stage.value : 'unknown';
    const outcome = s.outcome.known ? s.outcome.value : 'unknown';
    const elapsed = stageElapsedMs(s, at);

    return (
        <li
            className={`iw-stage iw-stage--${outcome}${s.running ? ' is-running' : ''}`}
            data-stage={name}
            data-outcome={outcome}
            data-event-id={s.event_id}
        >
            <div className="iw-stage-head">
                {s.running ? <span className="iw-pulse" aria-hidden="true" /> : null}
                <span className="iw-stage-name">
                    {s.stage.known
                        ? (STAGE_LABEL[name] || name)
                        : <>a stage this client does not recognise
                            (<span className="iw-badge-raw">{s.stage.value}</span>)</>}
                </span>
                <span className={`iw-stage-outcome iw-stage-outcome--${outcome}`}>
                    {s.outcome.known
                        ? outcome
                        : <>unknown: <span className="iw-badge-raw">{s.outcome.value}</span></>}
                </span>

                {/* ELAPSED, only while running, and never confused with a reported duration. */}
                {s.running && elapsed !== null ? (
                    <span className="iw-stage-elapsed" data-elapsed="true">
                        {formatDuration(elapsed)} elapsed
                    </span>
                ) : null}

                {/* The stage's own number, only when it gave one. */}
                {/* The em dash needs a name. A screen reader on a bare `—` hears "dash" and
                    learns nothing; the visible label would be noise beside seven rows of numbers,
                    so it is there for assistive tech and not for the eye. */}
                {!s.running ? (
                    <span className="iw-stage-duration" data-duration={String(s.duration_ms)}>
                        <span className="iw-sr">
                            {s.duration_ms === null ? 'duration not reported' : 'took'}
                        </span>
                        {formatDuration(s.duration_ms)}
                    </span>
                ) : null}
            </div>

            <p className="iw-stage-copy">
                {s.outcome.known
                    ? STAGE_OUTCOME_COPY[outcome]
                    : 'This client does not recognise the outcome this stage reported.'}
            </p>

            {s.detail ? <p className="iw-quiet iw-stage-detail">{s.detail}</p> : null}
            {s.summary ? <p className="iw-quiet iw-stage-summary">{s.summary}</p> : null}

            {/* THE BACKEND'S OWN SENTENCE about its own work — "2 images in → 8 reading blocks
                out". Preferred over anything assembled here, because the nouns are the half that
                makes the numbers readable and this surface guessing them would be inventing the
                units. */}
            {s.counts_line ? (
                <p className="iw-stage-counts" data-counts-line="true">{s.counts_line}</p>
            ) : null}

            {/* Substages, as the stage reported them. */}
            {s.substages.length ? (
                <ul className="iw-substages" data-substages={s.substages.length}>
                    {s.substages.map((sub, i) => (
                        <li key={sub.substage_id || i} data-substage-id={sub.substage_id}>
                            <span className="iw-substage-label">{sub.label}</span>
                            {sub.total !== null ? (
                                <span className="iw-substage-of">
                                    {sub.index === null ? '?' : sub.index + 1} of {sub.total}
                                </span>
                            ) : null}
                            {sub.outcome.value
                                ? <span className="iw-quiet">{sub.outcome.value}</span> : null}
                            <span className="iw-quiet">{formatDuration(sub.duration_ms)}</span>
                        </li>
                    ))}
                </ul>
            ) : null}

            {/* The forward-guess fallback, for a producer that reports progress without the
                array. Never rendered beside the array — that would be one fact twice. */}
            {!s.substages.length && s.image_total !== null ? (
                <p className="iw-stage-images" data-image-progress="true">
                    image {s.image_index === null ? '?' : s.image_index + 1} of {s.image_total}
                    {s.substage ? <> — {s.substage}</> : null}
                </p>
            ) : null}

            <div className="iw-stage-meta">
                {s.role ? <span className="iw-stage-role">{s.role}</span> : null}
                {s.model ? <span className="iw-stage-model">{s.model}</span> : null}
                {s.provider ? <span>{s.provider}</span> : null}
                {s.execution_mode.value ? (
                    <span
                        className={`iw-exec iw-exec--${s.execution_mode.known
                            ? s.execution_mode.value : 'unknown'}`}
                        data-execution-mode={s.execution_mode.value}
                        title={EXECUTION_MODE_COPY[s.execution_mode.value] || ''}
                    >
                        {s.execution_mode.value}
                    </span>
                ) : null}

                {/* CALL TOPOLOGY, as declared. Never derived: "4 image readings plus one
                    synthesis" is the backend's claim about its own plan, and a count this surface
                    worked out from the image list would be a guess wearing that authority. */}
                {s.call_topology ? (
                    <span className="iw-stage-topology" data-topology={s.call_topology}>
                        {s.call_topology.replace(/_/g, ' ')}
                    </span>
                ) : null}
                {s.planned_calls !== null ? (
                    <span className="iw-stage-calls" data-planned-calls={s.planned_calls}>
                        {s.actual_calls !== null
                            ? `${s.actual_calls} of ${s.planned_calls} calls`
                            : `${s.planned_calls} calls planned`}
                    </span>
                ) : null}
                {s.planned_calls === null && s.actual_calls !== null ? (
                    <span className="iw-stage-calls">{s.actual_calls} calls</span>
                ) : null}

                {s.input_count !== null ? (
                    <span className="iw-stage-io">in {s.input_count}</span>
                ) : null}
                {s.output_count !== null ? (
                    <span className="iw-stage-io">out {s.output_count}</span>
                ) : null}

                {/* `finish_reason: length` is the single most consequential field the live runs
                    produced, and it belongs beside the stage rather than in a receipt nobody
                    expands. */}
                {s.finish_reason ? (
                    <span className="iw-stage-finish" data-finish-reason={s.finish_reason}>
                        finish: {s.finish_reason}
                    </span>
                ) : null}

                {/* `unknown` is NOT `none`. The first says nothing could be consulted; the second
                    says something was consulted and said no. Rendering them alike would report an
                    UNCHECKED stage as a verified-untruncated one — the contract says so in as
                    many words, and it is the easiest of these to collapse by accident. */}
                {s.truncation_source.value && s.truncation_source.value !== 'none' ? (
                    <span
                        className={`iw-truncation iw-truncation--${s.truncation_source.known
                            ? s.truncation_source.value : 'unrecognised'}`}
                        data-truncation-source={s.truncation_source.value}
                    >
                        truncation: {s.truncation_source.value.replace(/_/g, ' ')}
                    </span>
                ) : null}
            </div>

            {s.output_refs.length ? (
                <p className="iw-quiet iw-stage-refs">
                    produced {s.output_refs.map((r) => <code key={r}>{r}</code>)
                        .reduce((acc, el, i) => (i ? [...acc, ', ', el] : [el]), [])}
                </p>
            ) : null}

            {s.calls.length ? (
                <ul className="iw-stage-calls-list">
                    {s.calls.map((c, i) => (
                        <li key={c.call_id || i} data-call-id={c.call_id}>
                            <span>{c.label || c.call_id || `call ${i + 1}`}</span>
                            <span className="iw-quiet">{formatDuration(c.duration_ms)}</span>
                            {c.finish_reason
                                ? <span className="iw-quiet">{c.finish_reason}</span> : null}
                        </li>
                    ))}
                </ul>
            ) : null}
        </li>
    );
}
