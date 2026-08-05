import React from 'react';

import {
    STATUS_LABEL, dropClaim, dropPercept, emptyPlanReason, epistemicLabel, functionLabel,
    isEdited, moveClaim, planSummary, refusalLines, rewordClaim,
} from './atlasPlan.js';

/**
 * ATLAS C4 — plan mode's panel: ask for an argument, then keep, reorder, cut or reword it.
 *
 * THE PANEL PROPOSES STRUCTURE, NOT PROSE. There is nothing here that writes a sentence of the
 * article — that is C5. What a writer does on this surface is decide which claims are theirs,
 * in what order, resting on which evidence.
 *
 * WHAT AN EDIT CANNOT DO. There is no control here that adds a percept, changes an actuator, or
 * moves a percept to a different image. Every one of those would be proposing NEW evidence, and
 * new evidence has to go through the planner and the gate rather than through a form — a writer
 * who could hand-attach `light_field` to a claim would be asserting a binding nothing judged.
 * Cutting is safe in a way adding is not: dropping evidence can only weaken a claim, and the
 * re-bind on accept reports exactly how far.
 *
 * REFUSALS ARE NOT COLLAPSIBLE. The argument-level refusal, the empty-plan reason and every
 * unbound percept render as text at the same weight as the claims. A `<details>` around them
 * would be the honest thing to write and the dishonest thing to ship.
 */

function PerceptRow({ claim, percept, onDrop }) {
    return (
        <li className={`atlas-p-row${percept.bound ? '' : ' is-unbound'}`}
            data-step-id={percept.step_id} data-bound={percept.bound ? 'true' : 'false'}>
            <span className="atlas-p-fn">{functionLabel(percept.function)}</span>
            <span className="atlas-p-act">{percept.actuator}</span>
            {percept.bound ? (
                <span className="atlas-p-ep">{epistemicLabel(percept.epistemic)}</span>
            ) : (
                <span className="atlas-p-why">{percept.why || 'refused'}</span>
            )}
            {percept.spans_corpus && <span className="atlas-p-span">across the corpus</span>}
            {percept.image && !percept.spans_corpus && (
                <span className="atlas-p-img">on {percept.image}</span>
            )}
            <button type="button" className="atlas-p-cut"
                aria-label={`Remove ${percept.actuator} from claim ${claim.claim_id}`}
                onClick={() => onDrop(claim.claim_id, percept.step_id)}>cut</button>
        </li>
    );
}

export default function AtlasPlanPanel({
    thesis, onThesis, onPlan, planning,
    plan, claims, onClaims, onAccept, onDiscard, accepting, accepted, error,
}) {
    const summary = plan ? planSummary(plan) : null;
    const refusals = refusalLines(plan);
    const emptyWhy = plan ? emptyPlanReason(plan) : '';
    const edited = plan ? isEdited(plan, claims) : false;

    return (
        <aside className="atlas-plan" aria-label="Plan mode">
            <form className="atlas-plan-ask" onSubmit={(e) => { e.preventDefault(); onPlan(); }}>
                <label className="atlas-label" htmlFor="atlas-thesis">
                    <span>What do you want to argue about these images?</span>
                </label>
                <textarea id="atlas-thesis" className="atlas-thesis" rows={3} value={thesis}
                    placeholder="the sequence disperses what the rotunda gathers"
                    onChange={(e) => onThesis(e.target.value)} />
                <button type="submit" className="atlas-go" disabled={planning || !thesis.trim()}>
                    {planning ? 'Planning…' : 'Plan'}
                </button>
                <p className="atlas-plan-note">
                    The planner proposes claims and where their evidence would come from. Every
                    percept is judged by the same gate the rest of the system uses — what cannot be
                    produced comes back refused, and stays in the plan saying so.
                </p>
            </form>

            {error && <p className="atlas-error" role="alert">{error}</p>}

            {plan && (
                <section className="atlas-plan-out" aria-label="The proposed argument">
                    <header className="atlas-plan-head">
                        <h2 className="atlas-h2">The argument</h2>
                        <p className="atlas-plan-counts">
                            {summary.claims} claim{summary.claims === 1 ? '' : 's'} ·{' '}
                            {summary.supported} carried · {summary.qualified} in part ·{' '}
                            {summary.refused} refused · {summary.connectors} binding
                            {summary.connectors === 1 ? '' : 's'} drawn
                        </p>
                        {/* Never softened. `complete` means every claim carried AND a
                            counter-reading was seeded, and it is the one word a writer would most
                            like to be wrong about. */}
                        <p className={`atlas-plan-complete is-${summary.complete}`}>
                            {summary.complete
                                ? 'complete — every claim is carried and a counter-reading is seeded'
                                : 'not complete — read the refusals below before drafting from this'}
                        </p>
                    </header>

                    {emptyWhy && <p className="atlas-banner is-empty" role="note">{emptyWhy}</p>}

                    {refusals.length > 0 && (
                        <ul className="atlas-banner is-refused" role="alert">
                            {refusals.map((line) => <li key={line}>{line}</li>)}
                        </ul>
                    )}

                    {edited && (
                        <p className="atlas-banner is-edited" role="note">
                            Edited since it was planned. The verdicts below are from the original
                            binding; accepting sends the structure back to be judged again.
                        </p>
                    )}

                    <ol className="atlas-claims">
                        {claims.map((claim, i) => (
                            <li key={claim.claim_id}
                                className={`atlas-claim-row${claim.struck ? ' is-struck' : ''}`}
                                data-claim-id={claim.claim_id} data-status={claim.status}>
                                <div className="atlas-claim-row-head">
                                    <span className={`atlas-claim-status is-${claim.status}`}>
                                        {STATUS_LABEL[claim.status] || claim.status}
                                    </span>
                                    <span className="atlas-claim-move">
                                        <button type="button" aria-label={`Move ${claim.claim_id} earlier`}
                                            disabled={i === 0}
                                            onClick={() => onClaims(moveClaim(claims, claim.claim_id, -1))}>↑</button>
                                        <button type="button" aria-label={`Move ${claim.claim_id} later`}
                                            disabled={i === claims.length - 1}
                                            onClick={() => onClaims(moveClaim(claims, claim.claim_id, 1))}>↓</button>
                                        <button type="button" aria-label={`Remove claim ${claim.claim_id}`}
                                            onClick={() => onClaims(dropClaim(claims, claim.claim_id))}>remove</button>
                                    </span>
                                </div>

                                <textarea className="atlas-claim-edit" rows={2} value={claim.text}
                                    aria-label={`Claim ${i + 1}`}
                                    onChange={(e) => onClaims(
                                        rewordClaim(claims, claim.claim_id, e.target.value))} />

                                {claim.dirty && (
                                    <p className="atlas-claim-stale" role="note">
                                        edited — re-bound on accept
                                    </p>
                                )}

                                {(claim.percepts || []).length > 0 && (
                                    <ul className="atlas-p-list">
                                        {claim.percepts.map((p) => (
                                            <PerceptRow key={p.step_id} claim={claim} percept={p}
                                                onDrop={(cid, sid) => onClaims(
                                                    dropPercept(claims, cid, sid))} />
                                        ))}
                                    </ul>
                                )}

                                {(claim.caveats || []).map((c) => (
                                    <p className="atlas-claim-caveat" role="note" key={c}>{c}</p>
                                ))}
                            </li>
                        ))}
                    </ol>

                    {claims.length > 0 && (
                        <div className="atlas-plan-actions">
                            <button type="button" className="atlas-go" onClick={onAccept}
                                disabled={accepting}>
                                {accepting ? 'Accepting…' : 'Accept this plan'}
                            </button>
                            <button type="button" className="atlas-plain" onClick={onDiscard}
                                disabled={accepting}>Discard</button>
                        </div>
                    )}

                    {accepted && (
                        <p className="atlas-plan-accepted" role="status">
                            Accepted and re-bound. It is on the Atlas as the seed for a draft —
                            structure and bindings only; no prose has been written.
                        </p>
                    )}
                </section>
            )}
        </aside>
    );
}
