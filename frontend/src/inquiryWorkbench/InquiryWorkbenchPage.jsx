import React, { useCallback, useEffect, useRef, useState } from 'react';
import InquiryEntry from './InquiryEntry.jsx';
import ProvisionalReading from './ProvisionalReading.jsx';
import ClaimBlocks from './ClaimBlocks.jsx';
import ObservablePlan from './ObservablePlan.jsx';
import DecisionStream from './DecisionStream.jsx';
import DecisionCard from './DecisionCard.jsx';
import CapabilityActivity from './CapabilityActivity.jsx';
import EvidencePanel from './EvidencePanel.jsx';
import SynthesisView from './SynthesisView.jsx';
import TraceView from './TraceView.jsx';
import StageActivity from './StageActivity.jsx';
import ArtifactLedger from './ArtifactLedger.jsx';
import DiagnosisCard from './DiagnosisCard.jsx';
import SessionExport from './SessionExport.jsx';
import ScopePanel, { ScopeBadge } from './ScopePanel.jsx';
import { createInquiryClient } from './inquiryClient.js';
import {
    openDecision, outcomeCounts, STATE_LABEL, MODE_COPY,
    IS_AWAITING_USER, IS_TERMINAL_STATE, DEPLOYMENT_LABEL, DEPLOYMENT_COPY,
} from './inquiryContract.js';
import './inquiryWorkbench.css';

/**
 * INQUIRY WORKBENCH — the surface. Prompt and images in, a claim graph you can argue with in the
 * middle, an answer and its remainder out.
 *
 * ## One session, every panel a pure function of it
 *
 * Same discipline `/agent` settled on: state is a single normalised session and no panel holds a
 * second copy of the inquiry's truth. The client is injectable so the whole surface can be driven
 * by `createMockInquiryClient` in tests and by Lane D's routes in the browser, with no branch
 * inside any component — and that is also the Lane D swap point. When the routes land, nothing
 * here changes.
 *
 * ## A columnar workbench, not a node canvas
 *
 * The brief permits a small relation visual and prefers a readable column, and the reason holds up
 * under the content: what a person does here is READ a claim, decide whether they believe it, and
 * see what would have to be observed to settle it. That is reading work. A force-directed graph of
 * twelve nodes would be a picture of the data structure rather than of the argument, and the
 * relations that matter are already on each claim as a short list.
 *
 * ## Not routed until Lane D
 *
 * Nothing in this lane registers `/inquiry` in the router. Route registration is Lane D's, per the
 * board's additive-only rule, and this page is reachable only by importing it until then.
 */
export default function InquiryWorkbenchPage({ client = null, corpusClient = null }) {
    const inquiryClient = useRef(client || createInquiryClient()).current;

    const [session, setSession] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [conflict, setConflict] = useState(null);
    const [unavailable, setUnavailable] = useState('');
    //: What the backend declared it will serve. `null` until it answers, and `null` FOREVER if it
    //: cannot — a surface that defaulted to "available" would offer a control the server refuses.
    const [features, setFeatures] = useState(null);
    const unwatch = useRef(null);

    // THE CORPUS IS NO LONGER FETCHED HERE. It used to be one call — page 1, limit 24 — and that
    // single line was the whole reason the 002R rehearsal could not ask a question of most of the
    // archive. Paging, caching and selection now belong to `CorpusPicker`, which reaches the same
    // TanStack keys the Gallery uses rather than holding a second copy of the archive.

    useEffect(() => () => { unwatch.current?.(); }, []);

    // ONE PROBE, AND ITS FAILURE IS SILENT. This asks the listing route what this deployment
    // serves; a deployment that has not enabled the temporary scoped rehearsal, an older server
    // and an unreachable API all answer the same way — no control is offered — and none of them is
    // an error worth putting in front of a person who came here to ask a question.
    useEffect(() => {
        let alive = true;
        inquiryClient.features?.()
            .then((f) => { if (alive) setFeatures(f); })
            .catch(() => { /* nobody declared it; the entry offers nothing */ });
        return () => { alive = false; };
    }, [inquiryClient]);

    const listen = useCallback((sessionId) => {
        unwatch.current?.();
        unwatch.current = inquiryClient.watch(sessionId, {
            onSession: setSession,
            onError: (e) => setError(e?.message || 'Lost the session.'),
        });
    }, [inquiryClient]);

    const start = useCallback(async (input) => {
        setBusy(true);
        setError('');
        setUnavailable('');
        try {
            const first = await inquiryClient.start(input);
            if (!first?.session_id) throw new Error('The inquiry did not come back with an id.');
            setSession(first);
            listen(first.session_id);
        } catch (e) {
            // THE PRODUCTION UNAVAILABLE STATE, and the one place it would be tempting to fall
            // back to a fixture. A 404 or a dead connection on the start route means the inquiry
            // API is not deployed; the entry says exactly that and shows nothing in its place.
            // Substituting a fixture here would turn an outage into a working demonstration —
            // structurally the same lie as calling a simulated receipt evidence, one layer up.
            const status = e?.status;
            if (!status || status === 404 || status >= 500) {
                setUnavailable(status
                    ? `POST /api/v1/inquiries — ${status}. ${e.message}`
                    : `POST /api/v1/inquiries — ${e?.message || 'no response'}`);
            } else {
                setError(e?.message || 'Could not start the inquiry.');
            }
        } finally {
            setBusy(false);
        }
    }, [inquiryClient, listen]);

    const respond = useCallback(async (response) => {
        if (!session?.session_id) return;
        setBusy(true);
        setError('');
        setConflict(null);
        try {
            const next = await inquiryClient.respond(session.session_id, response);
            setSession(next);
            // The SAME session, resumed — so pick the watch back up rather than starting anything.
            listen(session.session_id);
        } catch (e) {
            if (e?.conflict) {
                // The person's input is NOT discarded: `DecisionCard` holds its own selection and
                // its response id, so refreshing the session under it leaves the choice intact and
                // the resubmit carries the same response id the first attempt did.
                let refreshed = false;
                if (e.session) {
                    setSession(e.session);
                    refreshed = true;
                } else {
                    try { setSession(await inquiryClient.get(session.session_id)); refreshed = true; }
                    catch { /* the message still explains it */ }
                }
                setConflict({ message: e.message || '', refreshed });
            } else {
                setError(e?.message || 'The decision did not go through.');
            }
        } finally {
            setBusy(false);
        }
    }, [inquiryClient, session, listen]);

    const reset = () => {
        unwatch.current?.();
        unwatch.current = null;
        setSession(null);
        setError('');
        setConflict(null);
    };

    if (!session) {
        return (
            <main className="iw-shell">
                <InquiryEntry
                    corpusClient={corpusClient}
                    busy={busy}
                    error={error}
                    unavailable={unavailable}
                    onStart={start}
                    features={features}
                />
            </main>
        );
    }

    const decision = openDecision(session);
    const awaiting = IS_AWAITING_USER(session.state.value);
    const working = !awaiting && !IS_TERMINAL_STATE(session.state.value);

    return (
        <main className="iw-shell iw-shell--session">
            <SessionHeader session={session} working={working} />

            {/* THE MACHINERY, above the reasoning and visible by default while it runs. The 002R
                rehearsal watched `Starting…` with no idea which of seven stages was taking it,
                while the backend recorded every transition. */}
            <StageActivity stages={session.stages} working={working} />

            {/* The open decision comes first when the inquiry is waiting on it — but everything
                that led here stays below, unhidden. A modal would frame the question as an
                interruption to the inquiry; it IS the inquiry, paused at the point where it
                stopped being able to proceed on its own. */}
            {awaiting && decision ? (
                <DecisionCard
                    decision={decision}
                    revision={session.revision}
                    busy={busy}
                    error={error}
                    conflict={conflict}
                    onRespond={respond}
                />
            ) : null}

            {/* A conflict can arrive with no card left to attach it to: the decision was answered
                somewhere else, so the refreshed session has closed it. That is a DUPLICATE rather
                than a stale write, and it needs the opposite advice — nothing here invites a
                resubmit, because the decision is no longer open. Dropping the message on the floor
                because its card had gone would leave the person's submit looking like it silently
                did nothing. */}
            {conflict && !(awaiting && decision) ? (
                <p className="iw-conflict" role="alert" data-conflict="answered">
                    <b>This decision was answered somewhere else.</b> {conflict.message}
                    {' '}
                    The session below is the current one, and it already carries the answer. Your
                    submission was not applied a second time.
                </p>
            ) : null}

            {error && !awaiting ? <p className="iw-error" role="alert">{error}</p> : null}

            {/* BEFORE THE PROSE. A collapsed diagnosis under a fluent paragraph is a diagnosis
                nobody reads, and the 002R rehearsal ended EXHAUSTED with a perceptive VLM
                paragraph on screen and no way to see that nothing had been compiled from it. */}
            <DiagnosisCard session={session} />

            {/* ABOVE THE PROSE, and for the diagnosis card's own reason. A bounded run produces
                FEWER claims and observables than an unbounded one, so a reader who meets the
                result before the bound reads a short answer as a finding about the images. This
                renders nothing at all on a full-coverage run. */}
            <ScopePanel session={session} />

            <ProvisionalReading reading={session.graph.reading} />
            <ClaimBlocks
                session={session}
                highlightRefs={decision ? decision.affected_refs : []}
            />
            <ObservablePlan
                session={session}
                highlightRefs={decision ? decision.affected_refs : []}
            />
            <DecisionStream records={session.decision_records} />
            <CapabilityActivity receipts={session.capability_receipts} />
            <NextActions session={session} onRestart={reset} />
            <ArtifactLedger session={session} />
            <EvidencePanel session={session} />
            <SynthesisView session={session} />
            <TraceView trace={session.trace} />
            <SessionExport session={session} />

            <button type="button" className="iw-expand iw-again" onClick={reset}>
                Ask something else
            </button>
        </main>
    );
}

/**
 * LIVE, REPLAY or FIXTURE — beside the state, in words, permanently.
 *
 * NOT A TOOLTIP AND NOT A COLOUR. The 002R rehearsal was run against a replay server and said so
 * in a receipt three panels down, which is the right fact in the wrong place: a screenshot of a
 * replay is the same picture as a screenshot of a live run to anyone who does not open the
 * provenance. Every one of the four states below is printed as a WORD, including the one that says
 * nobody declared it — because a badge that renders as nothing when the answer is missing puts a
 * replay and a live run back on one screen.
 *
 * `undeclared` is not styled as a weaker `live`. It is its own treatment, and it says out loud that
 * the absence of an answer is not an answer.
 */
export function DeploymentBadge({ deployment }) {
    if (!deployment) return null;
    const kind = deployment.kind.known ? deployment.kind.value : 'undeclared';
    const label = deployment.kind.known
        ? DEPLOYMENT_LABEL[kind]
        : deployment.kind.value.toUpperCase();
    return (
        <span
            className={`iw-deployment iw-deployment--${kind}`}
            data-deployment={kind}
            data-declared={String(deployment.declared)}
            title={deployment.detail || DEPLOYMENT_COPY[kind]}
        >
            <b className="iw-deployment-kind">{label}</b>
            {/* Unreachable is its own word, and only ever appears on a live binding: it means the
                models are bound and the provider did not answer, which is a different thing from a
                deployment that binds no model at all. */}
            {deployment.reachable === false ? (
                <span className="iw-deployment-flag" data-unreachable="true">
                    provider unreachable
                </span>
            ) : null}
        </span>
    );
}

/** The question, the pictures and the mode — immutable, and above everything they produced. */
export function SessionHeader({ session, working = false }) {
    const state = session.state.known ? session.state.value : 'unknown';
    const mode = session.mode.known ? session.mode.value : '';

    return (
        <header className="iw-panel iw-session-head" aria-label="Question and images">
            <div className="iw-session-status">
                <span className={`iw-state iw-state--${state}`} role="status" data-state={state}>
                    {working ? <span className="iw-pulse" aria-hidden="true" /> : null}
                    {state === 'unknown'
                        ? <>a state this client does not recognise
                            (<span className="iw-badge-raw">{session.state.value}</span>)</>
                        : (STATE_LABEL[state] || state)}
                </span>
                <DeploymentBadge deployment={session.deployment} />
                {/* BESIDE THE DEPLOYMENT BADGE, and it survives every terminal state because it is
                    keyed on the session's declared scope rather than on anything a compilation
                    produced. See `ScopePanel`. */}
                <ScopeBadge scope={session.execution_scope} />
                {mode ? (
                    <span className="iw-mode-chip" data-mode={mode} title={MODE_COPY[mode].hint}>
                        {MODE_COPY[mode].title} mode
                    </span>
                ) : null}
                {session.revision !== null
                    ? <span className="iw-quiet">revision {session.revision}</span> : null}
            </div>

            {/* Byte-identical, and not editable here. The compiler's source spans index into this
                exact string. */}
            <p className="iw-session-prompt">{session.graph.prompt}</p>

            {session.graph.image_refs.length ? (
                <ul className="iw-session-images">
                    {session.graph.image_refs.map((img) => (
                        <li key={img.post_id} data-post-id={img.post_id}>
                            {img.image_url
                                ? <img src={img.image_url} alt="" loading="lazy" />
                                : <span className="iw-thumb-blank" aria-hidden="true" />}
                            <span className="iw-thumb-title">{img.title || img.post_id}</span>
                        </li>
                    ))}
                </ul>
            ) : null}

            {session.error ? <p className="iw-error" role="alert">{session.error}</p> : null}
        </header>
    );
}

/**
 * What a person can do about an outcome, said specifically.
 *
 * "Something went wrong, try again" is the wrong answer to all four of these, and to two of them
 * it is actively misleading. A capability gap will not resolve on a retry — nothing exists to
 * run — and re-issuing on an empty is how a phrase-conditioned empty becomes a sampling artifact
 * rather than the observation it is. So each outcome gets its own sentence, and none of them
 * suggests running the same thing again in the hope of a different answer.
 */
export function NextActions({ session, onRestart }) {
    const counts = outcomeCounts(session);
    const has = (k) => (counts[k] || 0) > 0;
    if (!has('empty') && !has('unavailable') && !has('refused') && !has('capability_gap')) {
        return null;
    }

    return (
        <section className="iw-panel iw-next" aria-label="What you can do about this">
            <h2 className="iw-h2">What you can do about this</h2>
            <ul className="iw-next-list">
                {has('empty') ? (
                    <li data-next="empty">
                        <b>An instrument returned nothing.</b> That is recorded as a result. Asking
                        the same thing again would turn the observation into a sampling artifact;
                        a differently-scoped question is a new inquiry, and it starts a new record.
                    </li>
                ) : null}
                {has('unavailable') ? (
                    <li data-next="unavailable">
                        <b>A capability was unavailable.</b> Nothing was attempted, so nothing was
                        learned about the images. The claims it would have served are still open
                        and are listed in the remainder.
                    </li>
                ) : null}
                {has('refused') ? (
                    <li data-next="refused">
                        <b>A request was refused.</b> The reason is on the receipt. A refusal is a
                        decision with grounds, not a failure to display.
                    </li>
                ) : null}
                {has('capability_gap') ? (
                    <li data-next="capability_gap">
                        <b>Semant cannot make one of these observable at all.</b> Retrying will not
                        change that — there is nothing to run. The claim stays in the remainder
                        until such a capability exists.
                    </li>
                ) : null}
            </ul>
            <button type="button" className="iw-expand" onClick={onRestart}>
                Start a different inquiry
            </button>
        </section>
    );
}
