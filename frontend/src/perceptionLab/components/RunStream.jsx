import React from 'react';
import { ExecutionChip, OutcomeBanner, Refusal, StageChip, EmptyState } from './Chips';
import { duration } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — what happened, step by step.
 *
 * THE BADGE ON THIS PANEL IS THE RUN'S, NOT THE CLIENT'S. The header of the page says what the
 * laboratory is talking to; this says where THIS answer came from. They are different questions
 * and a page that answered both with one badge would be lying about one of them — a FIXTURE client
 * can still show you a run recorded LIVE, and a LIVE client's replay is not a live reading.
 *
 * `invoked` is a column rather than a footnote. It is the only field that separates "an adapter
 * ran on this image" from "the ledger was re-read", and a replay that quietly showed the recorded
 * durations would be indistinguishable from a fresh measurement. So the stream shows both times:
 * what this reading took, and — for a replay — when the measurement it is re-showing was made.
 *
 * THE DIGEST PAIR is at the bottom because it answers the question no other field does: did the
 * ground move under the run. Equal digests are stated, not left as an absence.
 */
export default function RunStream({ run, plan = null, onReplay, busy }) {
    if (!run) {
        return (
            <section className="pl-panel" aria-label="Run">
                <div className="pl-panel-head"><h2 className="pl-panel-title">Run</h2></div>
                <EmptyState title="Nothing has run in this session"
                    hint="A plan is read before it is run. When one does run, every stage lands
                        here with its own state, adapter, timing and whether it called anything." />
            </section>
        );
    }

    const attempts = run.stage_attempts || [];
    const digestHeld = run.source_digest_after === null
        || run.source_digest_after === run.source_digest_before;

    return (
        <section className="pl-panel" aria-label="Run" data-run-id={run.run_id}
            data-execution={run.execution_identity} data-outcome={run.outcome}>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Run</h2>
                <span className="pl-chiprow">
                    <ExecutionChip identity={run.execution_identity} />
                    <span className="pl-chip" title="the plan this run was asked to carry out">
                        {run.requested_plan_id}
                    </span>
                </span>
            </div>

            <OutcomeBanner outcome={run.outcome}>
                <span className="pl-outcome-hint" data-run-duration>
                    this reading took {duration(run.duration_ms)}
                    {run.completed_at === null
                        ? ' · it did not complete, so there is no end time' : ''}
                </span>
            </OutcomeBanner>

            {run.replay ? (
                <p className="pl-panel-sub" data-replay-of={run.replay.source_run_id}>
                    Re-shown from <code>{run.replay.source_run_id}</code>, measured{' '}
                    {run.replay.recorded_at}. <strong>No adapter can be called by a replay</strong>
                    {' '}— <code>adapter_callable: {String(run.replay.adapter_callable)}</code>.
                    The timings below are how long this reading took, not how long the measurement
                    took.
                </p>
            ) : null}

            {attempts.length === 0 ? (
                <p className="pl-panel-sub" data-no-attempts>
                    No stage was attempted. Nothing in this plan was authorized, so nothing looked
                    at the image — read the refusals below.
                </p>
            ) : (
                <div className="pl-scroll">
                    <table className="pl-table" data-stages>
                        <caption className="pl-visually-hidden">
                            Every stage of this run, with its state, adapter, whether it invoked
                            anything, and how long it took.
                        </caption>
                        <thead>
                            <tr>
                                <th scope="col">operation</th>
                                <th scope="col">state</th>
                                <th scope="col">adapter</th>
                                <th scope="col">invoked</th>
                                <th scope="col">took</th>
                                <th scope="col">detail</th>
                            </tr>
                        </thead>
                        <tbody>
                            {attempts.map((a) => (
                                <tr key={a.attempt_id} data-attempt={a.attempt_id}
                                    data-state={a.state}>
                                    <td><code>{a.operation}</code></td>
                                    <td><StageChip state={a.state} /></td>
                                    <td data-adapter={a.adapter || 'none'}>
                                        {a.adapter || <span className="pl-step-why">
                                            none — nothing was dispatched
                                        </span>}
                                    </td>
                                    <td data-invoked={String(a.invoked)}
                                        title={a.invoked
                                            ? 'an adapter was called for this stage'
                                            : 'nothing was called for this stage'}>
                                        {a.invoked ? 'yes' : 'no'}
                                    </td>
                                    <td data-duration={a.duration_ms === null
                                        ? 'unmeasured' : a.duration_ms}>
                                        {duration(a.duration_ms)}
                                    </td>
                                    <td className="pl-step-why">{a.detail}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {run.refusals?.length ? (
                <div className="pl-field" data-run-refusals>
                    <span className="pl-label">Refused, and it is a result</span>
                    {run.refusals.map((r, i) => <Refusal key={`${r.code}-${i}`} refusal={r} />)}
                </div>
            ) : null}

            <div className="pl-field">
                <span className="pl-label">The ground under this run</span>
                <dl className="pl-kv">
                    <dt>digest before</dt>
                    <dd data-digest-before>{run.source_digest_before}</dd>
                    <dt>digest after</dt>
                    <dd data-digest-after>
                        {run.source_digest_after === null
                            ? 'not read — the run did not reach the end'
                            : run.source_digest_after}
                    </dd>
                    <dt>held</dt>
                    <dd data-digest-held={String(digestHeld)}>
                        {digestHeld
                            ? 'the image did not change under this run'
                            : 'THE IMAGE CHANGED UNDER THIS RUN. Every measurement here is '
                                + 'against a source that is no longer what was read.'}
                    </dd>
                    <dt>artifacts</dt>
                    <dd data-artifact-count={run.artifact_ids.length}>
                        {run.artifact_ids.length
                            ? run.artifact_ids.join(', ')
                            : 'none — this run produced no record in the ledger'}
                    </dd>
                </dl>
            </div>

            {plan && plan.resolved_steps.length !== attempts.length ? (
                <p className="pl-panel-sub" data-stage-gap>
                    {plan.resolved_steps.length} stages were authorized and {attempts.length}{' '}
                    were attempted. The difference is not an error to be hidden: read the states
                    above.
                </p>
            ) : null}

            {onReplay ? (
                <div className="pl-btnrow">
                    <button type="button" className="pl-btn" data-action="replay-this"
                        disabled={!!busy} onClick={() => onReplay(run.run_id)}>
                        Re-open this run
                    </button>
                </div>
            ) : null}
        </section>
    );
}
