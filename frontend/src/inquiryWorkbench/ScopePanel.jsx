import React from 'react';
import { SCOPE_BANNER, SCOPE_LABEL, formatDuration } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the declared execution scope: the badge, and what it left out.
 *
 * HARNESS-003F. 003E's two live runs spent almost all of their running time waiting on an 8,000 TPM
 * allowance and produced no observable, no fork and no answer between them, so the vertical has
 * never once run end to end on live models. A vertical slice runs the whole chain over a declared
 * subset so the chain becomes testable — and the entire risk of that arrangement is that its result
 * reads like a reading.
 *
 * ## Why the badge is a word and not a colour
 *
 * The same argument the LIVE / REPLAY / FIXTURE badge already makes, one field along, and the
 * failure it prevents is worse here. A replay produces the objects it claims to; a slice produces
 * FEWER of them — fewer claims, fewer observables, sometimes none — so an unbadged slice does not
 * read as a bounded run, it reads as a THIN one, and a thin result is evidence about the images.
 *
 * So: a word, beside the state, on every session including the ones that failed, with no tooltip
 * and no colour carrying any part of the meaning.
 *
 * ## Why the exclusions are listed rather than counted
 *
 * `12 atoms not investigated` tells a reader the size of the gap. It does not tell them where it
 * is, and where it is is the only thing they can act on — the same decision 003E made about
 * unexamined batch pairs, and this panel prints those too where the plan carries them.
 */

/** The badge. Rendered wherever the deployment badge is, and under the same rules. */
export function ScopeBadge({ scope }) {
    if (!scope || !scope.bounded) return null;
    const kind = scope.mode.known ? scope.mode.value : 'unknown';
    const label = scope.mode.known
        ? (SCOPE_LABEL[kind] || kind.toUpperCase())
        : scope.mode.value.toUpperCase();
    return (
        <span
            className={`iw-scope iw-scope--${kind}`}
            data-scope={kind}
            data-recorded={String(scope.recorded)}
        >
            <b className="iw-scope-kind">{label}</b>
            <span className="iw-scope-line">{SCOPE_BANNER}</span>
        </span>
    );
}

/** `a of b`, with an em dash where the backend sent nothing rather than a zero it never claimed. */
function Ratio({ label, part, whole, name }) {
    if (part === null && whole === null) return null;
    return (
        <div className="iw-scope-stat" data-scope-stat={name}>
            <dt>{label}</dt>
            <dd>
                <b>{part === null ? '—' : part}</b>
                {' of '}
                {whole === null ? '—' : whole}
            </dd>
        </div>
    );
}

/**
 * `permitted` and `executed`, as a pair.
 *
 * `null` permitted is UNLIMITED and it prints as the word. A large number in that slot would leave
 * a reader guessing whether it was a bound nobody reached, and `0` permitted is a real and
 * deliberate configuration here — so unlimited and none may never render alike.
 */
function Bound({ label, allowed, sent, name }) {
    if (allowed === null && sent === null) return null;
    return (
        <div className="iw-scope-stat" data-scope-stat={name}>
            <dt>{label}</dt>
            <dd>
                <b>{sent === null ? '—' : sent}</b>
                {' sent, '}
                {allowed === null
                    ? <span data-unbounded="true">no limit</span>
                    : <>{allowed} permitted</>}
            </dd>
        </div>
    );
}

/** Which stage took longest, read off the ledger rather than asserted. */
function slowestStage(session) {
    const timed = (session.stages || []).filter((s) => typeof s.duration_ms === 'number');
    if (!timed.length) return null;
    return timed.reduce((worst, s) => (s.duration_ms > worst.duration_ms ? s : worst));
}

/**
 * Waiting, against work in the model — the one number 003D built the whole pacing record for.
 *
 * A run whose elapsed time is mostly waiting is not a slow run. It is a run inside a smaller
 * allowance than the work needs, and the two read alike in any single duration column while their
 * repairs are opposite. `null` where nothing paced anything, which is not the same as no wait.
 */
function waitingSplit(session) {
    const passes = session.graph?.passes || [];
    const waited = passes.reduce((n, p) => n + (p.waited_ms || 0), 0);
    const worked = passes.reduce((n, p) => n + (p.duration_ms || 0), 0);
    if (!waited && !worked) return null;
    return { waited, worked, dominant: waited > worked ? 'waiting' : 'model work' };
}

export default function ScopePanel({ session }) {
    const scope = session?.execution_scope;
    if (!scope || !scope.bounded) return null;
    const slowest = slowestStage(session);
    const split = waitingSplit(session);

    return (
        <section className="iw-panel iw-scope-panel" aria-label="What this run investigated"
                 data-scope-panel={scope.mode.value}>
            <h2 className="iw-h2">What this run investigated</h2>

            {/* THE HEADLINE, AND IT IS THE NEGATIVE ONE. `full_coverage` is read from the record
                rather than derived from the mode — the backend's schema refuses a slice that claims
                complete coverage, and recomputing the answer here would be a second opinion free to
                disagree with it. */}
            <p className="iw-scope-verdict" data-full-coverage={String(scope.full_coverage)}>
                {scope.full_coverage === false
                    ? <><b>full_coverage: false.</b> {SCOPE_BANNER}</>
                    : <><b>full_coverage: {String(scope.full_coverage)}.</b> This run reports
                        coverage it was not asked to bound.</>}
            </p>

            {!scope.recorded ? (
                <p className="iw-scope-unrecorded" data-scope-unrecorded="true">
                    This run was <b>asked</b> for as a scoped rehearsal and no compilation recorded
                    what it selected — it did not get that far. Nothing here is a complete reading,
                    and the absence of a selection record is not the absence of a bound.
                </p>
            ) : null}

            <dl className="iw-scope-stats">
                <Ratio name="source-units" label="Source units investigated"
                       part={scope.selected_source_units} whole={scope.total_source_units} />
                <Ratio name="atoms" label="Semantic atoms investigated"
                       part={scope.atoms_investigated} whole={scope.selected_atoms} />
                <Ratio name="claims" label="Claims investigated"
                       part={scope.claims_investigated} whole={scope.selected_claims} />
                <Bound name="relation-batches" label="Relation requests"
                       allowed={scope.relation_batches_allowed}
                       sent={scope.relation_batches_sent} />
                <Bound name="operationalizer-batches" label="Operationalization requests"
                       allowed={scope.operationalizer_batches_allowed}
                       sent={scope.operationalizer_batches_sent} />
                <Bound name="reconciliation-rounds" label="Cross-batch rounds"
                       allowed={scope.reconciliation_rounds_allowed}
                       sent={scope.reconciliation_rounds_sent} />
                {scope.allowance_tokens !== null ? (
                    <div className="iw-scope-stat" data-scope-stat="allowance">
                        <dt>Sized against</dt>
                        <dd><b>{scope.allowance_tokens}</b> tokens per minute</dd>
                    </div>
                ) : null}
            </dl>

            {slowest || split ? (
                <dl className="iw-scope-stats iw-scope-timing">
                    {slowest ? (
                        <div className="iw-scope-stat" data-scope-stat="slowest-stage">
                            <dt>Longest stage</dt>
                            <dd>
                                <b>{slowest.stage.value}</b>{' '}
                                {formatDuration(slowest.duration_ms)}
                            </dd>
                        </div>
                    ) : null}
                    {split ? (
                        <div className="iw-scope-stat" data-scope-stat="waiting-split">
                            <dt>Where the time went</dt>
                            <dd>
                                <b data-dominant={split.dominant}>{split.dominant}</b>{' '}
                                — {formatDuration(split.waited)} waiting for provider capacity,{' '}
                                {formatDuration(split.worked)} in the model
                            </dd>
                        </div>
                    ) : null}
                </dl>
            ) : null}

            {session.stop_reason ? (
                <p className="iw-scope-stop" data-scope-stop="true">
                    <b>Why it stopped.</b> {session.stop_reason}
                </p>
            ) : null}

            {/* IN FULL. A count is the size of the gap; this is where it is. */}
            {scope.exclusions.length ? (
                <details className="iw-scope-excluded" open>
                    <summary>
                        {scope.exclusions.length} thing
                        {scope.exclusions.length === 1 ? '' : 's'} this run did not investigate
                    </summary>
                    <ul className="iw-scope-exclusions">
                        {scope.exclusions.map((e) => (
                            <li key={`${e.kind}:${e.ref}`} data-exclusion={e.kind}>
                                <code className="iw-scope-ref">{e.ref}</code>
                                <span className="iw-scope-kind-tag">{e.kind || 'item'}</span>
                                <span className="iw-scope-reason">{e.reason}</span>
                            </li>
                        ))}
                    </ul>
                </details>
            ) : null}

            {scope.notes.length ? (
                <ul className="iw-scope-notes">
                    {scope.notes.map((n) => <li key={n}>{n}</li>)}
                </ul>
            ) : null}
        </section>
    );
}
