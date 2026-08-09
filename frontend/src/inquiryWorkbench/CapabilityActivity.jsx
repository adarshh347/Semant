import React, { useState } from 'react';
import { OUTCOME_COPY } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — what was asked of a capability, and what came back.
 *
 * Six outcomes, six treatments, and they are six different facts about the world:
 *
 *     live            it ran and returned something
 *     simulated       a stand-in produced a shape; nothing was measured
 *     empty           it ran and returned nothing
 *     unavailable     it was not there, so nothing was attempted
 *     refused         the request was declined, with a reason
 *     capability_gap  nothing in Semant can do this at all
 *
 * A careless surface renders the last four identically, as absence, and the confusion is not
 * cosmetic — `empty` is a finding about the images, `unavailable` is a fact about the deployment,
 * and `capability_gap` is a fact about what Semant is. HARNESS-001C2 had to build an availability
 * GATE for exactly this: a fixture the instrument silently failed on contributed a column of
 * zeroes that read precisely like a robustness finding.
 *
 * So `attempted` is printed. It is the single field that separates "ran and found nothing" from
 * "never ran", and without it a reader has to trust the word.
 *
 * ## The SIMULATED label
 *
 * It sits inside the payload block, above the payload, in text — not in a tooltip, not in a
 * corner badge, and not only in the receipt header where a reader scrolling to the geometry would
 * pass it. `execution_mode: fixture` is the one thing about a Phase-1 receipt that a person must
 * not be able to miss, because the payload is a plausible-looking region and plausible-looking
 * regions are exactly what the whole program is built not to launder.
 */
export default function CapabilityActivity({ receipts = [] }) {
    if (!receipts.length) return null;

    return (
        <section className="iw-panel iw-capability" aria-label="Capability activity">
            <h2 className="iw-h2">What was asked of the instruments</h2>
            <ul className="iw-receipt-rows">
                {receipts.map((r) => <ReceiptRow key={r.receipt_id} receipt={r} />)}
            </ul>
        </section>
    );
}

export function ReceiptRow({ receipt: r }) {
    const [open, setOpen] = useState(false);
    const hasPayload = Object.keys(r.payload || {}).length > 0;

    return (
        <li
            className={`iw-receipt iw-receipt--${r.outcome}`}
            data-receipt-id={r.receipt_id}
            data-outcome={r.outcome}
        >
            <div className="iw-receipt-head">
                <span className="iw-capability-name">{r.capability || 'capability'}</span>
                <span className={`iw-outcome iw-outcome--${r.outcome}`} data-outcome={r.outcome}>
                    {r.outcome === 'unknown'
                        ? <>unknown: <span className="iw-badge-raw">{r.status.value}</span></>
                        : r.outcome.replace(/_/g, ' ')}
                </span>
            </div>

            <p className="iw-receipt-copy">
                {OUTCOME_COPY[r.outcome]
                    || 'This client does not recognise the status this receipt was reported with.'}
            </p>

            {r.detail ? <p className="iw-quiet iw-receipt-detail">{r.detail}</p> : null}

            <div className="iw-receipt-meta">
                {r.request_ref ? <span>for <code>{r.request_ref}</code></span> : null}
                {/* The field that separates "ran and found nothing" from "never ran". */}
                <span className="iw-attempted" data-attempted={String(r.attempted)}>
                    {r.attempted === true ? 'attempted' : null}
                    {r.attempted === false ? 'not attempted' : null}
                    {r.attempted === null ? 'whether it was attempted was not recorded' : null}
                </span>
                {/* A missing latency is an em dash. Rendering it as 0 ms would present a
                    measurement that was never taken as an instant one. */}
                <span className="iw-latency">
                    {r.latency_ms === null ? '—' : `${r.latency_ms} ms`}
                </span>
            </div>

            {hasPayload ? (
                <div className="iw-payload-block">
                    {/* PERMANENT, adjacent to the payload, and in text. */}
                    {r.simulated ? (
                        <p className="iw-simulated" data-simulated="true">
                            SIMULATED — not evidence
                        </p>
                    ) : null}

                    <button
                        type="button"
                        className="iw-expand"
                        aria-expanded={open}
                        onClick={() => setOpen((v) => !v)}
                    >
                        {open ? 'Hide' : 'Show'} what it returned
                    </button>

                    {open ? (
                        <>
                            {/* And again, beside the geometry itself. A reader who expanded the
                                payload from a long list should not have to remember which row
                                they opened. */}
                            {r.simulated ? (
                                <p className="iw-simulated iw-simulated--payload" data-simulated="true">
                                    SIMULATED — not evidence. This geometry was produced by a
                                    stand-in, not measured from the image, and it cannot support
                                    any claim.
                                </p>
                            ) : null}
                            <pre className="iw-payload">{JSON.stringify(r.payload, null, 2)}</pre>
                        </>
                    ) : null}
                </div>
            ) : null}

            {/* An empty result is a RESULT. It is never rendered as "nothing exists" — the
                instrument returned nothing, which is a fact about the instrument on this input. */}
            {r.outcome === 'empty' ? (
                <p className="iw-quiet iw-empty-note">
                    That is a result, not a failure to display. Whether the thing was there to be
                    found is unresolved, and nothing was guessed to fill the space.
                </p>
            ) : null}
        </li>
    );
}
