import React, { useState } from 'react';
import { EmptyState, ExecutionChip, OutcomeChip, PlannerChip } from './Chips';
import { duration } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — every run this session has made, and the way back into each one.
 *
 * A LABORATORY THAT SHOWS ONLY ITS LATEST ANSWER IS A DEMO. The whole point of asking the same
 * question twice is being able to put the two answers beside each other, and that requires the
 * earlier one to still be reachable — with its own execution identity, its own timings, and its
 * own outcome, rather than as a row that says "run 3".
 *
 * Three things a person can do from here, and they are three different acts:
 *
 *   REOPEN    make an old run's artifacts active again. Nothing runs. The ledger is re-read.
 *   REPLAY    a NEW run record with `execution_identity: REPLAY` and `adapter_callable: false`,
 *             which exists so that "I looked at this again" is itself in the history.
 *   COMPARE   mark a run as the comparison side, which is what turns the repeat metrics from a
 *             statement about one answer into a statement about stability.
 *
 * Reopen and replay are deliberately not one button. Reopening changes what is on screen; replay
 * adds a record. Collapsing them would mean that reading the history rewrote it.
 */
export default function HistoryPanel({ session, runs = [], plans = [], byId, onReopen, onReplay,
    onCompare, comparisonRunId = null, busy }) {
    const [open, setOpen] = useState(true);
    if (!session) return null;

    const planFor = (plan_id) => plans.find((p) => p.plan_id === plan_id) || null;

    return (
        <section className="pl-panel" aria-label="History" data-history>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">History</h2>
                <span className="pl-chiprow">
                    <span className="pl-chip" data-run-count={runs.length}>
                        {runs.length} run{runs.length === 1 ? '' : 's'}
                    </span>
                    <button type="button" className="pl-btn pl-btn--quiet" data-toggle-history
                        aria-expanded={open} onClick={() => setOpen((v) => !v)}>
                        {open ? 'collapse' : 'expand'}
                    </button>
                </span>
            </div>

            <dl className="pl-kv" data-session-identity>
                <dt>session</dt><dd><code>{session.session_id}</code></dd>
                <dt>opened against</dt>
                <dd data-session-digest>{session.source.image_digest}</dd>
                <dt>source</dt>
                <dd>{session.source.origin} · {session.source.natural_width}×
                    {session.source.natural_height}</dd>
            </dl>

            {!open ? null : runs.length === 0 ? (
                <EmptyState title="Nothing has run yet"
                    hint="Every run lands here with its own identity and outcome, including the
                        ones that refused, so an earlier answer is always reachable." />
            ) : (
                <ul className="pl-list" data-run-history>
                    {[...runs].reverse().map((run) => {
                        const plan = planFor(run.requested_plan_id);
                        return (
                            <li key={run.run_id} className="pl-step" data-history-run={run.run_id}
                                data-history-outcome={run.outcome}>
                                <span className="pl-chiprow">
                                    <ExecutionChip identity={run.execution_identity} />
                                    <OutcomeChip outcome={run.outcome} />
                                    {plan ? (
                                        <PlannerChip planner={plan.planner}
                                            fellBackFrom={plan.planner_fell_back_from} />
                                    ) : null}
                                    {comparisonRunId === run.run_id ? (
                                        <span className="pl-chip" data-is-comparison>
                                            the comparison side
                                        </span>
                                    ) : null}
                                </span>
                                <span className="pl-step-op">
                                    <code>{run.run_id}</code> ·{' '}
                                    {(plan?.resolved_steps || []).map((s) => s.operation)
                                        .join(', ') || 'nothing authorized'}
                                </span>
                                <span className="pl-step-why">
                                    {run.started_at} · {duration(run.duration_ms)} ·{' '}
                                    {run.artifact_ids.length} artifact
                                    {run.artifact_ids.length === 1 ? '' : 's'}
                                    {run.replay
                                        ? ` · re-shown from ${run.replay.source_run_id}` : ''}
                                    {run.source_digest_after
                                        && run.source_digest_after !== run.source_digest_before
                                        ? ' · THE IMAGE CHANGED UNDER THIS RUN' : ''}
                                </span>
                                <span className="pl-btnrow">
                                    <button type="button" className="pl-btn pl-btn--quiet"
                                        data-action="reopen" data-reopen={run.run_id}
                                        disabled={!run.artifact_ids.length || !!busy}
                                        title="make this run's artifacts active again. Nothing
                                            runs; the ledger is re-read."
                                        onClick={() => onReopen(run)}>
                                        Reopen
                                    </button>
                                    <button type="button" className="pl-btn pl-btn--quiet"
                                        data-action="replay" data-replay={run.run_id}
                                        disabled={!!busy}
                                        title="record a REPLAY run. Nothing can be called by it,
                                            and the fact that you looked again is itself in the
                                            history."
                                        onClick={() => onReplay(run.run_id)}>
                                        Replay
                                    </button>
                                    <button type="button" className="pl-btn pl-btn--quiet"
                                        data-action="compare" data-compare={run.run_id}
                                        aria-pressed={comparisonRunId === run.run_id}
                                        disabled={!run.artifact_ids.length || !!busy}
                                        title="use this run as the comparison side, which is what
                                            turns the repeat metrics into a statement about
                                            stability"
                                        onClick={() => onCompare(
                                            comparisonRunId === run.run_id ? null : run.run_id)}>
                                        Compare against
                                    </button>
                                </span>
                                {run.artifact_ids.length ? (
                                    <span className="pl-step-why" data-history-artifacts>
                                        {run.artifact_ids.map((artifactId) => {
                                            const a = byId?.get(artifactId);
                                            return (
                                                <code key={artifactId}
                                                    data-history-artifact={artifactId}>
                                                    {artifactId}
                                                    {a ? ` (${a.identity.artifact_kind})` : ''}{' '}
                                                </code>
                                            );
                                        })}
                                    </span>
                                ) : null}
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
