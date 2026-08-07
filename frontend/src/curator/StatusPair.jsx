import React from 'react';
import {
    LEDGER_COMMITTED, LEDGER_PROPOSED, EPISTEMIC_MEASURED, EPISTEMIC_INTERPRETIVE,
} from './curatorService';

/**
 * WAVE4 — the two statuses, rendered as two things.
 *
 * This component exists because the failure it prevents is a *visual* one, and the read path's
 * guard cannot reach it. #172 made the API incapable of rendering `proposed` as `measured` — both
 * fields required, no defaults, derived on every read. None of that stops a UI from printing one
 * badge that says "measured" and letting a curator read it as settled.
 *
 *     epistemic      how the PRODUCER knows this        the organ's claim about its own work
 *     ledger_status  whether a HUMAN has agreed         the world's claim about the organ's
 *
 * They answer different questions and a `measured` + `proposed` row is not in tension: the organ
 * is sure and nobody has accepted it yet. So they are two badges, never one, and they are never
 * combined into a single word — there is no "settled", no "confirmed", no colour that means both.
 *
 * ## The visual grammar, and why it is not colour alone
 *
 *     epistemic     an OUTLINE badge — a claim about knowing, carried lightly
 *     ledger        a FILLED badge   — a fact about the world's record, and heavier once committed
 *
 * Filled-versus-outline is legible without colour vision, and the two badges never share a shape.
 * `proposed` is deliberately the quieter of the two: an unaccepted claim should not look like an
 * accomplishment, and this is the pixel-level version of the discipline the serializer keeps.
 */

const EPISTEMIC_COPY = {
    [EPISTEMIC_MEASURED]: 'computed from the image signal',
    [EPISTEMIC_INTERPRETIVE]: 'a reading about the image, not a measurement of it',
};

const LEDGER_COPY = {
    [LEDGER_PROPOSED]: 'nobody has accepted this yet',
    [LEDGER_COMMITTED]: 'a person committed this to the shared ledger',
};

export function EpistemicBadge({ epistemic }) {
    // `null` is a real answer from the backend — "this row cannot currently tell you" — and it is
    // shown as that rather than filled in with `uncertain`, which is a producer's word for a claim
    // it declines to vouch for and would be putting an opinion in the absence's mouth.
    if (!epistemic) {
        return (
            <span className="cur-badge cur-badge--epistemic cur-badge--unknown"
                  title="the mark carries no status — this row cannot tell you">
                no status on the mark
            </span>
        );
    }
    return (
        <span className={`cur-badge cur-badge--epistemic cur-badge--${epistemic}`}
              title={EPISTEMIC_COPY[epistemic] || epistemic}>
            {epistemic}
        </span>
    );
}

export function LedgerBadge({ ledgerStatus }) {
    const known = ledgerStatus === LEDGER_COMMITTED ? LEDGER_COMMITTED : LEDGER_PROPOSED;
    return (
        <span className={`cur-badge cur-badge--ledger cur-badge--${known}`}
              title={LEDGER_COPY[known]}>
            {known}
        </span>
    );
}

/**
 * Both, with the sentence that keeps them apart.
 *
 * The line under them is not decoration. "Measured privately, proposed publicly" is the whole
 * epistemic story of this system, and a curator who reads only the badges could reasonably
 * conclude the two disagree.
 */
export default function StatusPair({ epistemic, ledgerStatus, detail }) {
    const committed = ledgerStatus === LEDGER_COMMITTED;
    return (
        <div className="cur-statuspair">
            <div className="cur-statusrow">
                <span className="cur-statuslabel">the organ says</span>
                <EpistemicBadge epistemic={epistemic} />
            </div>
            <div className="cur-statusrow">
                <span className="cur-statuslabel">the ledger says</span>
                <LedgerBadge ledgerStatus={ledgerStatus} />
            </div>
            <p className="cur-statusgloss">
                {committed
                    ? 'A person accepted this. The kind of knowing did not change — a commit makes a claim durable, it cannot make an estimate into a measurement.'
                    : 'These are not in tension: the organ is sure of its own work, and the world has not agreed yet.'}
            </p>
            {detail ? <p className="cur-statusdetail">{detail}</p> : null}
        </div>
    );
}
