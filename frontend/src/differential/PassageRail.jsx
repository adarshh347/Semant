// CIRCUIT-001 P5-B — the Passage Rail.
//
// The surface CS-001 asked for and P0 forbade as fabrication ("any rail today would be
// fabricated"). That objection is dead: runs are real, events are appended by real producers,
// provenance carries model + latency + run_id. This rail shows ONLY what was recorded — a
// witness, not a narrator (Invariant 9). Every honesty decision lives in ./passageRail (pure,
// node-tested); this file is thin JSX + one bounded poll.
//
// The poll (2a/2c): TanStack Query reads `vision-runs/latest` for the active operation and
// re-reads on `refetchInterval` ONLY while the run is live (running/pending & not stale). The
// moment a run is terminal, interrupted, or absent, the interval returns false — no idle poll,
// no spinner implying activity the record does not show.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { API_URL } from '../config/api';
import { latestUrl } from './visionActivity';
import {
    SOURCE, runOutcome, stalenessNote, sessionEvents, timeline,
    isRunLive, railSummary, durationLabel,
} from './passageRail';
import './PassageRail.css';

const POLL_MS = 3500; // bounded; scheduled by refetchInterval ONLY while a run is live.

function Dot({ tone }) {
    return <span className={`pr-dot pr-dot--${tone}`} aria-hidden="true" />;
}

// One field, or an honest dash. Absent telemetry is "—" (Inv 8) — never estimated, never hidden.
function Field({ label, value }) {
    return (
        <span className="pr-field">
            <span className="pr-field-k">{label}</span>
            <span className={`pr-field-v${value == null ? ' is-absent' : ''}`}>{value == null ? '—' : value}</span>
        </span>
    );
}

// A backend RUN event — a record. Observation order, not a causal chain.
function RunRow({ row, onTap }) {
    const tappable = !!row.runId && !!onTap;
    return (
        <li className={`pr-row pr-row--run${tappable ? ' is-tappable' : ''}`}>
            <button
                type="button"
                className="pr-row-btn"
                disabled={!tappable}
                onClick={() => tappable && onTap(row.runId)}
                title={tappable ? 'Show the marks this run produced that you accepted' : undefined}
            >
                <span className="pr-row-lead">
                    <span className="pr-src pr-src--run">run</span>
                    <span className="pr-row-stage">{row.stage || row.stageId || '—'}</span>
                    {row.status && <span className={`pr-row-status is-${row.status}`}>{row.status}</span>}
                </span>
                <span className="pr-row-meta">
                    {row.model && <span className="pr-chip">{row.model}</span>}
                    {row.adapter && !row.model && <span className="pr-chip pr-chip--adapter">{row.adapter}</span>}
                    <span className={`pr-lat${row.latencyMs == null ? ' is-absent' : ''}`}>
                        {row.latencyMs == null ? '—' : `${Math.round(row.latencyMs)} ms`}
                    </span>
                </span>
                {row.error && <span className="pr-row-err">{row.error}</span>}
            </button>
        </li>
    );
}

// A local SESSION event — this session's own circulation, in a visibly different voice from a
// backend record (P0.5 §4.3: a judgement is never shown in the register of an observation).
function SessionRow({ row, onTapMark }) {
    const isAccept = row.kind === 'accept';
    const tappable = !!row.markId && !!onTapMark;
    return (
        <li className={`pr-row pr-row--session pr-row--${row.kind}`}>
            <button
                type="button"
                className="pr-row-btn"
                disabled={!tappable}
                onClick={() => tappable && onTapMark(row.markId)}
                title={tappable ? 'Highlight this mark' : undefined}
            >
                <span className="pr-row-lead">
                    <span className="pr-src pr-src--session">this session</span>
                    <span className="pr-row-stage">
                        {isAccept ? 'Accepted a suggestion' : 'Recalling'}
                        {row.label ? ` · ${row.label}` : row.role ? ` · ${row.role}` : ''}
                    </span>
                    {isAccept && row.producer && <span className="pr-chip pr-chip--producer">{row.producer}</span>}
                    {!isAccept && row.live && <span className="pr-row-status is-live">live</span>}
                </span>
            </button>
        </li>
    );
}

export default function PassageRail({
    postId,
    operation = 'dissect',
    marks = [],
    recall = null,
    onHighlightMark = null,
    onHighlightRun = null,
}) {
    const [open, setOpen] = useState(false);

    // 2a/2c — the bounded poll. One read of `latest`; re-read only while the run is live.
    const { data: run = null, isError, isFetching, refetch } = useQuery({
        queryKey: ['passage-run', postId, operation],
        enabled: !!postId,
        queryFn: async ({ signal }) => {
            const res = await fetch(latestUrl(API_URL, postId, operation), { signal });
            if (!res.ok) throw new Error(`vision-runs/latest ${res.status}`);
            const body = await res.json();
            return body.run ?? null;   // { run: null } — a real absence, not a failure.
        },
        // The whole anti-idle-poll rule in one line: keep re-reading only while the run is live.
        refetchInterval: (query) => (isRunLive(query.state.data) ? POLL_MS : false),
        refetchOnWindowFocus: false,
    });

    const outcome = useMemo(() => runOutcome(run), [run]);
    const staleNote = useMemo(() => stalenessNote(run), [run]);
    const session = useMemo(() => sessionEvents({ marks, recall }), [marks, recall]);
    const rows = useMemo(() => timeline(run, session), [run, session]);
    // A failed READ with no prior run is unreadable. A failed REFRESH that still has the last
    // real run is NOT unreadable — erasing a real record because a poll blipped would itself be a
    // lie of omission (P2.2R R0). We keep the last read and say the refresh failed.
    const unreadable = isError && !run;
    const staleRead = isError && !!run;
    const summary = railSummary({ postId, unreadable, run, outcome });
    const tone = unreadable ? 'unreadable' : outcome ? outcome.present.tone : 'muted';

    return (
        <section className={`pr${open ? ' is-open' : ''}`} aria-label="Passage">
            <button type="button" className="pr-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
                <span className="pr-eyebrow">Passage</span>
                <span className={`pr-summary is-${tone}`}>
                    <Dot tone={tone} />{summary}
                </span>
                <span className="pr-caret" aria-hidden="true">{open ? '▾' : '▸'}</span>
            </button>

            {open && (
                <div className="pr-body">
                    {/* Two lines that bound the claim (Inv 12): WHAT this shows, and that it invents
                        nothing. Without them a projection reads like a live feed. */}
                    <p className="pr-scope">
                        The latest <strong>{outcome?.operationLabel || operation}</strong> run for this image, and
                        this session’s own circulation. If it wasn’t recorded, it isn’t shown.
                    </p>

                    {unreadable && (
                        <p className="pr-note pr-note--unreadable">Couldn’t read the run — this is a read failure, not an empty record.</p>
                    )}
                    {staleRead && (
                        <p className="pr-note pr-note--unreadable">Couldn’t refresh — showing the last read of this run.</p>
                    )}
                    {!isError && !run && (
                        <p className="pr-note pr-note--empty">No run recorded yet for this image.</p>
                    )}

                    {run && outcome && (
                        <div className={`pr-run is-${outcome.present.tone}`}>
                            <button
                                type="button"
                                className="pr-run-head"
                                disabled={!outcome.runId || !onHighlightRun}
                                onClick={() => outcome.runId && onHighlightRun?.(outcome.runId)}
                                title={outcome.runId ? 'Highlight the marks you accepted from this run' : undefined}
                            >
                                <Dot tone={outcome.present.tone} />
                                <span className="pr-run-op">{outcome.operationLabel}</span>
                                <span className={`pr-run-status is-${outcome.present.tone}`}>{outcome.present.label}</span>
                                {outcome.isSuggestionRun && (
                                    <span className="pr-tag pr-tag--suggestion" title="This run proposes marks for review — they are never evidence until you accept them.">
                                        suggestion run
                                    </span>
                                )}
                            </button>

                            {/* 2c — a stalled run states its silence in real seconds. No animation. */}
                            {staleNote && <p className="pr-stale">{staleNote}</p>}
                            {outcome.telemetryDegraded && <p className="pr-note pr-note--degraded">Some telemetry was not recorded.</p>}

                            {rows.length > 0 ? (
                                <ol className="pr-timeline">
                                    {rows.map((row) =>
                                        row.source === SOURCE.RUN
                                            ? <RunRow key={row.key} row={row} onTap={onHighlightRun} />
                                            : <SessionRow key={row.key} row={row} onTapMark={onHighlightMark} />,
                                    )}
                                </ol>
                            ) : (
                                <p className="pr-note pr-note--empty">No events recorded on this run.</p>
                            )}
                            {/* The two clocks are never reconciled into one claim (P0.5 §4.3). */}
                            {session.length > 0 && rows.length > 0 && (
                                <p className="pr-clocks">Run events and this session’s events keep separate clocks.</p>
                            )}

                            {/* 2a — terminal outcome: real elapsed time + a provenance line. No progress bar
                                anywhere: nothing records a fraction, so the rail renders a sequence, not a percent. */}
                            {outcome.terminal && (
                                <div className="pr-outcome">
                                    <Field label="outcome" value={outcome.present.label} />
                                    <Field label="took" value={durationLabel(outcome.durationMs)} />
                                    <Field label="asked by" value={outcome.initiator} />
                                    <Field label="ran on" value={outcome.actualSource} />
                                    {outcome.terminalReason && <Field label="reason" value={outcome.terminalReason} />}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Session events with no run to hang under still deserve their timeline. */}
                    {!run && session.length > 0 && (
                        <ol className="pr-timeline">
                            {session.map((row) => <SessionRow key={row.key} row={row} onTapMark={onHighlightMark} />)}
                        </ol>
                    )}

                    <div className="pr-foot">
                        <button type="button" className="pr-refresh" onClick={() => refetch()} disabled={isFetching}>
                            {isFetching ? 'reading…' : 'Refresh'}
                        </button>
                    </div>
                </div>
            )}
        </section>
    );
}
