import React from 'react';
import EpistemicBadge from './EpistemicBadge.jsx';
import { isEvidenceGrade, claimById } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — evidence, and the things that are not it.
 *
 * The panel splits its input rather than filtering it. Objects that pass `isEvidenceGrade` are
 * evidence; objects that do not are shown BELOW, under a heading that says why they are not, and
 * neither list is allowed to be silently empty.
 *
 * Filtering would have been shorter and is the wrong shape. An inquiry whose evidence list is
 * empty because everything was simulated looks identical to one where nothing was ever requested,
 * and those are opposite situations for a reader deciding whether to trust the answer. Keeping
 * the disqualified objects visible, with the reason, is what makes the difference legible.
 *
 * In Phase 1 the top list is expected to be empty and the bottom one to hold the fixture receipt.
 * That is not a degraded rendering — it is the correct picture of a phase whose only capability is
 * a simulation.
 */
export default function EvidencePanel({ session }) {
    const all = session?.evidence || [];
    const receipts = session?.capability_receipts || [];
    if (!all.length && !receipts.length) return null;

    const evidence = all.filter(isEvidenceGrade);
    const disqualified = all.filter((e) => !isEvidenceGrade(e));
    const simulatedReceipts = receipts.filter((r) => r.simulated);

    return (
        <section className="iw-panel iw-evidence" aria-label="Evidence">
            <h2 className="iw-h2">Evidence</h2>

            {evidence.length ? (
                <ul className="iw-evidence-list">
                    {evidence.map((e) => (
                        <li
                            className="iw-evidence-item"
                            key={e.evidence_id}
                            data-evidence-id={e.evidence_id}
                        >
                            <div className="iw-evidence-head">
                                <EpistemicBadge field={e.epistemic_status} />
                                {e.verdict ? (
                                    <span
                                        className={`iw-verdict iw-verdict--${e.verdict.outcome.known
                                            ? e.verdict.outcome.value : 'unknown'}`}
                                        data-verdict={e.verdict.outcome.value}
                                    >
                                        {e.verdict.outcome.known
                                            ? e.verdict.outcome.value
                                            : `unknown: ${e.verdict.outcome.value}`}
                                    </span>
                                ) : (
                                    <span className="iw-verdict iw-verdict--none">no verdict</span>
                                )}
                            </div>
                            <p className="iw-evidence-summary">{e.summary}</p>
                            {e.verdict?.note
                                ? <p className="iw-quiet iw-verdict-note">{e.verdict.note}</p>
                                : null}
                            <p className="iw-quiet iw-evidence-serves">
                                {e.claim_refs.map((ref) => {
                                    const c = claimById(session, ref);
                                    return (
                                        <span className="iw-serves" key={ref}>
                                            serves <code>{ref}</code>
                                            {c ? ` — ${c.text}` : ''}
                                        </span>
                                    );
                                })}
                            </p>
                        </li>
                    ))}
                </ul>
            ) : (
                <p className="iw-quiet iw-evidence-none" data-evidence-count="0">
                    Nothing here has been measured. No evidence object was created in this session.
                </p>
            )}

            {(disqualified.length || simulatedReceipts.length) ? (
                <div className="iw-not-evidence" data-not-evidence="true">
                    <h3 className="iw-h3">Returned, but not evidence</h3>
                    <ul className="iw-not-evidence-list">
                        {simulatedReceipts.map((r) => (
                            <li key={r.receipt_id} data-receipt-id={r.receipt_id}>
                                <span className="iw-simulated" data-simulated="true">
                                    SIMULATED — not evidence
                                </span>
                                {' '}
                                <code>{r.capability}</code> returned a shape for{' '}
                                <code>{r.request_ref}</code>. It supports no claim and satisfies no
                                criterion.
                            </li>
                        ))}
                        {disqualified.map((e) => (
                            <li key={e.evidence_id} data-evidence-id={e.evidence_id}>
                                <code>{e.evidence_id}</code> — {e.summary || 'no summary'}{' '}
                                <span className="iw-quiet">
                                    {e.simulated
                                        ? '(produced by a fixture)'
                                        : '(not marked usable as evidence)'}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </section>
    );
}
