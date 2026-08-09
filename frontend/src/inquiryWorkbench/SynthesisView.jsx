import React, { useState } from 'react';
import EpistemicBadge from './EpistemicBadge.jsx';
import { claimById, isEvidenceGrade } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — the answer, and what it did not settle.
 *
 * Every section can be opened to show what supports it, so the prose may read as prose while
 * remaining accountable. The plan's requirement is that the UI can reveal what supports a
 * sentence, what complicates it, what was refused, which part stays interpretive, which part is
 * the person's direction and which part is imagined — and each of those is a separate visible
 * thing here rather than one "sources" list.
 *
 * ## The remainder is not a footer
 *
 * It renders as its own panel, at full weight, and it is deliberately not collapsible. What
 * measurement did not settle is the most easily-lost part of an inquiry and the part a fluent
 * answer most naturally absorbs — a paragraph that reads well is under no pressure to mention
 * what it skipped. Making it a peer of the answer rather than a footnote is the only structural
 * defence against that.
 *
 * ## Accepting an answer is not accepting a mark
 *
 * There is no control on this surface that commits anything. Reading an answer, agreeing with it
 * and closing the page changes no ledger, no post and no Atlas edge, and the note says so where a
 * person might otherwise assume that having reached the end of an inquiry means something was
 * recorded. Curator acceptance is a different action in a different surface, and conflating the
 * two is how a proposal becomes a fact without anyone deciding it should.
 */
export default function SynthesisView({ session }) {
    const synthesis = session?.synthesis;
    const remainder = session?.graph?.semantic_remainder || [];

    if (!synthesis && !remainder.length) return null;

    return (
        <>
            {synthesis ? (
                <section className="iw-panel iw-synthesis" aria-label="Answer">
                    <h2 className="iw-h2">The answer</h2>
                    {synthesis.sections.map((s) => (
                        <SynthesisSection key={s.section_id} section={s} session={session} />
                    ))}
                    {synthesis.note ? <p className="iw-quiet">{synthesis.note}</p> : null}

                    <p className="iw-quiet iw-not-accepted" data-not-accepted="true">
                        Reading this changes nothing in the shared record. No mark, percept or
                        Atlas edge has been committed by this inquiry — accepting an answer and
                        accepting a mark into the ledger are different actions, and this surface
                        cannot do the second.
                    </p>
                </section>
            ) : null}

            {remainder.length ? (
                <section className="iw-panel iw-remainder" aria-label="Semantic remainder">
                    <h2 className="iw-h2">What this did not settle</h2>
                    <ul className="iw-remainder-list">
                        {remainder.map((r) => (
                            <li
                                className="iw-remainder-item"
                                key={r.remainder_id}
                                data-remainder-id={r.remainder_id}
                            >
                                <p className="iw-remainder-text">{r.text}</p>
                                {r.why_unresolved
                                    ? <p className="iw-quiet iw-remainder-why">{r.why_unresolved}</p>
                                    : null}
                                {r.claim_refs.length ? (
                                    <p className="iw-quiet">
                                        {r.claim_refs.map((ref) => <code key={ref}>{ref}</code>)
                                            .reduce((acc, el, i) => (i ? [...acc, ', ', el] : [el]), [])}
                                    </p>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                </section>
            ) : null}
        </>
    );
}

export function SynthesisSection({ section, session }) {
    const [open, setOpen] = useState(false);

    const claims = section.claim_refs.map((r) => claimById(session, r)).filter(Boolean);
    const evidence = (session?.evidence || [])
        .filter((e) => section.evidence_refs.includes(e.evidence_id));
    const refusals = (session?.graph?.refusals || [])
        .filter((r) => section.refusal_refs.includes(r.refusal_id));
    const usable = evidence.filter(isEvidenceGrade);

    return (
        <article className="iw-section" data-section-id={section.section_id}>
            <div className="iw-section-head">
                {section.heading ? <h3 className="iw-h3">{section.heading}</h3> : null}
                <EpistemicBadge field={section.status} />
                {/* The person's direction is named as theirs, in the DOM, not implied by styling.
                    A redirect the person gave is not a finding about the images and never becomes
                    one by appearing inside the answer. */}
                {section.user_authored ? (
                    <span className="iw-author iw-author--user">your direction</span>
                ) : null}
            </div>

            <p className="iw-section-text">{section.text}</p>

            <button
                type="button"
                className="iw-expand"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                {open ? 'Hide' : 'What supports this'}
            </button>

            {open ? (
                <div className="iw-section-refs">
                    {claims.length ? (
                        <ul className="iw-ref-list iw-ref-list--claims">
                            {claims.map((c) => (
                                <li key={c.claim_id} data-claim-ref={c.claim_id}>
                                    <EpistemicBadge field={c.status} />
                                    {' '}{c.text}
                                </li>
                            ))}
                        </ul>
                    ) : null}

                    {usable.length ? (
                        <ul className="iw-ref-list iw-ref-list--evidence">
                            {usable.map((e) => (
                                <li key={e.evidence_id} data-evidence-ref={e.evidence_id}>
                                    <EpistemicBadge field={e.epistemic_status} />
                                    {' '}{e.summary}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="iw-quiet iw-section-noevidence">
                            No measurement supports this section.
                        </p>
                    )}

                    {refusals.length ? (
                        <ul className="iw-ref-list iw-ref-list--refusals">
                            {refusals.map((r) => (
                                <li key={r.refusal_id} data-refusal-ref={r.refusal_id}>
                                    refused — {r.reason}{r.detail ? `: ${r.detail}` : ''}
                                </li>
                            ))}
                        </ul>
                    ) : null}

                    {!claims.length && !usable.length && !refusals.length ? (
                        <p className="iw-quiet">
                            This section carries no references at all.
                        </p>
                    ) : null}
                </div>
            ) : null}
        </article>
    );
}
