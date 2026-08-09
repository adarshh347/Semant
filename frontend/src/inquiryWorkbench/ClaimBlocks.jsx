import React, { useState } from 'react';
import EpistemicBadge, { KindBadge } from './EpistemicBadge.jsx';
import { supportingEvidence, observablesForClaim } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the reading, taken apart.
 *
 * One block per claim, and the block is the unit a person can disagree with. That is the whole
 * argument of the compiler made visible: a paragraph can only be accepted or rejected whole,
 * while a graph of typed claims can be accepted in parts, and the parts carry different
 * epistemic weight.
 *
 * ## Inspect, never silently edit
 *
 * There is no input on a claim. A model claim is the model's, and a person who disagrees with one
 * makes an AMENDMENT through a decision — append-only, attributed to them, and unable to change
 * the claim's epistemic status. A text field here would look like the cheaper option and would
 * quietly destroy that: an edited model claim is indistinguishable from a model claim, and the
 * provenance is gone the moment it is saved.
 *
 * ## Why the source span is shown and not summarised
 *
 * Every claim carries the exact words it came from and whether those words were the PERSON'S or
 * the model's reading. The difference decides who is responsible for a claim, and it is the first
 * thing a reader wants when a claim looks wrong.
 */
export default function ClaimBlocks({ session, highlightRefs = [] }) {
    const claims = session?.graph?.claims || [];
    const edges = session?.graph?.claim_edges || [];
    if (!claims.length) return null;

    return (
        <section className="iw-panel iw-claims" aria-label="Claims">
            <header className="iw-claims-head">
                <h2 className="iw-h2">What that breaks into</h2>
                <p className="iw-quiet">
                    {claims.length} claims. Each is the compiler&apos;s, not yours — you can
                    inspect one, and redirect the inquiry through a decision, but nothing here
                    edits a claim in place.
                </p>
            </header>

            <ul className="iw-claim-list">
                {claims.map((c) => (
                    <ClaimBlock
                        key={c.claim_id}
                        claim={c}
                        session={session}
                        edges={edges.filter((e) => e.from_claim === c.claim_id
                            || e.to_claim === c.claim_id)}
                        highlighted={highlightRefs.includes(c.claim_id)}
                    />
                ))}
            </ul>
        </section>
    );
}

/**
 * Whose words a claim came from, said in a way that assigns responsibility.
 *
 * "from your question" and "from the reading" are not stylistic variants: one means the person
 * said it and the other means a model did. An unrecognised origin is named rather than folded
 * into either, for the same reason an unrecognised status is.
 */
function sourceOriginLabel(origin) {
    if (origin === 'prompt') return 'from your question';
    if (origin === 'reading') return 'from the reading';
    return origin ? `from ${origin}` : 'source not recorded';
}

export function ClaimBlock({ claim, session, edges = [], highlighted = false }) {
    const [open, setOpen] = useState(false);

    // Support comes from EVIDENCE objects only. A receipt cannot put a claim into this list
    // however confident its payload looks — the filter lives in the contract so no render site
    // has to remember it, and the Phase-1 fixture (one simulated receipt, zero evidence) is what
    // proves the two are actually different code paths.
    const support = supportingEvidence(session, claim.claim_id);
    const observables = observablesForClaim(session, claim.claim_id);

    return (
        <li
            className={`iw-claim${highlighted ? ' is-highlighted' : ''}`}
            data-claim-id={claim.claim_id}
            data-status={claim.status.known ? claim.status.value : 'unknown'}
        >
            <div className="iw-claim-head">
                <KindBadge field={claim.kind} />
                <EpistemicBadge field={claim.status} />
                {claim.author.value === 'user' ? (
                    <span className="iw-author iw-author--user">your direction</span>
                ) : null}
            </div>

            <p className="iw-claim-text">{claim.text}</p>

            {claim.source_span ? (
                <p className="iw-claim-source">
                    <span className="iw-claim-source-origin"
                          data-origin={claim.source_span.origin || 'unknown'}>
                        {sourceOriginLabel(claim.source_span.origin)}
                    </span>
                    <q className="iw-claim-source-text">{claim.source_span.text}</q>
                </p>
            ) : null}

            <div className="iw-claim-meta">
                {claim.image_scope.map((id) => (
                    <span className="iw-scope" key={id}>{id}</span>
                ))}
                {/* A confidence is the producer's own number and is labelled as such. It is NOT
                    evidence and never upgrades a status — SF-004-R2 §4.3 measured the cost of
                    reading one that way: a clean, well-formed, confident mask of the background. */}
                {claim.confidence !== null ? (
                    <span className="iw-confidence"
                          title="the model's own confidence. Not evidence, and it changes no status.">
                        model confidence {claim.confidence.toFixed(2)}
                    </span>
                ) : null}
            </div>

            <button
                type="button"
                className="iw-expand"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                {open ? 'Less' : 'Inspect'}
            </button>

            {open ? (
                <div className="iw-claim-detail">
                    {(claim.subject || claim.predicate || claim.object) ? (
                        <p className="iw-triple">
                            <span>{claim.subject || '—'}</span>
                            <span className="iw-triple-pred">{claim.predicate || '—'}</span>
                            <span>{claim.object || '—'}</span>
                        </p>
                    ) : null}

                    {claim.epistemic_demand ? (
                        <p className="iw-demand">
                            <b>To support this:</b> {claim.epistemic_demand}
                        </p>
                    ) : null}

                    {observables.length ? (
                        <p className="iw-quiet">
                            {observables.length} observable
                            {observables.length === 1 ? '' : 's'} requested —
                            {' '}{observables.map((o) => o.observable_id).join(', ')}
                        </p>
                    ) : null}

                    {/* The rule, stated where it would be broken. An empty list is not a defect
                        to be filled with the nearest available object. */}
                    {support.length ? (
                        <ul className="iw-claim-support">
                            {support.map((e) => (
                                <li key={e.evidence_id} data-evidence-id={e.evidence_id}>
                                    <EpistemicBadge field={e.epistemic_status} />
                                    {' '}{e.summary}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="iw-quiet iw-claim-nosupport">
                            Nothing has been measured for this claim.
                        </p>
                    )}

                    {edges.length ? (
                        <ul className="iw-claim-edges">
                            {edges.map((e) => (
                                <li key={e.edge_id} data-relation={e.relation}>
                                    <span className="iw-relation">{e.relation}</span>
                                    {' '}
                                    {e.from_claim === claim.claim_id
                                        ? <>→ <code>{e.to_claim}</code></>
                                        : <>← <code>{e.from_claim}</code></>}
                                    {e.note ? <span className="iw-quiet"> — {e.note}</span> : null}
                                </li>
                            ))}
                        </ul>
                    ) : null}
                </div>
            ) : null}
        </li>
    );
}
