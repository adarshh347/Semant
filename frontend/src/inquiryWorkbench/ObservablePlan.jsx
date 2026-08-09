import React, { useState } from 'react';
import { claimById } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — how Semant could investigate, and where it cannot.
 *
 * An observable is a REQUEST: a claim, an observable kind, the ground forms that could carry an
 * answer, and the capability classes that could produce one. It is deliberately not a tool name.
 * The operationalizer's discipline (plan §4) is that `centralized geometry` asks for dominant
 * extent and radial distribution rather than jumping straight to a segmenter, and this panel is
 * where that discipline is either visible or lost.
 *
 * ## The gap is a first-class row
 *
 * `unavailable` and `capability_gap` are rendered here, in line, with the same weight as an
 * available one — not filtered out, not greyed into the background. The reason is the honest
 * form of the thing this whole program is trying to avoid: a plan that shows only what it can do
 * reads as a complete plan. Showing the requests nothing can currently serve is how a reader
 * learns what Semant does not have, and HARNESS-001C2 is the standing example of why that
 * matters — a fold phrase and a scope phrase returned the same extent, and only a named gap
 * (`instrument_class_gap`) explains it.
 *
 * `residual_interpretation` is shown for the same reason: what stays interpretive even if every
 * requested measurement succeeds is the sentence a reader most needs and the one a capable-looking
 * plan is most likely to omit.
 */

const AVAILABILITY_COPY = {
    available: 'A capability could serve this.',
    unavailable: 'The capability exists but is not being used in this phase.',
    capability_gap: 'Nothing in Semant can make this observable.',
};

export default function ObservablePlan({ session, highlightRefs = [] }) {
    const observables = session?.graph?.observables || [];
    if (!observables.length) return null;

    return (
        <section className="iw-panel iw-observables" aria-label="How Semant could investigate">
            <header>
                <h2 className="iw-h2">How Semant could investigate</h2>
                <p className="iw-quiet">
                    What would have to become observable for each claim to gain support — and
                    where nothing can currently do it.
                </p>
            </header>

            <ul className="iw-obs-list">
                {observables.map((o) => (
                    <ObservableRow
                        key={o.observable_id}
                        observable={o}
                        claim={claimById(session, o.claim_ref)}
                        highlighted={highlightRefs.includes(o.observable_id)}
                    />
                ))}
            </ul>
        </section>
    );
}

export function ObservableRow({ observable: o, claim, highlighted = false }) {
    const [open, setOpen] = useState(false);
    const availability = o.availability.known ? o.availability.value : 'unknown';

    return (
        <li
            className={`iw-obs iw-obs--${availability}${highlighted ? ' is-highlighted' : ''}`}
            data-observable-id={o.observable_id}
            data-availability={availability}
        >
            <div className="iw-obs-head">
                <span className="iw-obs-kind">{(o.observable_kind || 'observable').replace(/_/g, ' ')}</span>
                <span className={`iw-availability iw-availability--${availability}`}>
                    {availability === 'unknown'
                        ? <>unknown: <span className="iw-badge-raw">{o.availability.value}</span></>
                        : availability.replace(/_/g, ' ')}
                </span>
            </div>

            {o.target ? <p className="iw-obs-target">{o.target}</p> : null}

            {claim ? (
                <p className="iw-quiet iw-obs-serves">
                    serves <code>{claim.claim_id}</code> — {claim.text}
                </p>
            ) : null}

            <p className="iw-quiet iw-obs-availability-copy">
                {AVAILABILITY_COPY[availability]
                    || 'This client does not recognise the availability this was reported with.'}
                {o.gap_reason ? ` ${o.gap_reason}` : ''}
            </p>

            <div className="iw-obs-tags">
                {o.capability_classes.map((c) => (
                    <span className="iw-tag iw-tag--capability" key={c}>{c}</span>
                ))}
                {o.ground_forms.map((g) => (
                    <span className="iw-tag iw-tag--ground" key={g}>{g}</span>
                ))}
            </div>

            {o.alternatives.length ? (
                <ul className="iw-alt-list">
                    {o.alternatives.map((a) => (
                        <li
                            key={a.alternative_id}
                            className={`iw-alt${a.available === false ? ' is-unavailable' : ''}`}
                            data-alternative-id={a.alternative_id}
                        >
                            <span className="iw-alt-label">{a.label}</span>
                            {a.consequence
                                ? <span className="iw-alt-consequence">{a.consequence}</span>
                                : null}
                            {/* `available === false` is a statement; `null` is silence. They are
                                not the same and the second must not be printed as the first. */}
                            {a.available === false
                                ? <span className="iw-alt-flag">not available</span> : null}
                            {a.available === null
                                ? <span className="iw-alt-flag iw-alt-flag--unknown">
                                    availability not stated
                                </span> : null}
                        </li>
                    ))}
                </ul>
            ) : null}

            <button
                type="button"
                className="iw-expand"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                {open ? 'Less' : 'Conditions'}
            </button>

            {open ? (
                <dl className="iw-obs-conditions">
                    {o.success_condition
                        ? <div><dt>counts as an answer</dt><dd>{o.success_condition}</dd></div> : null}
                    {o.ambiguity_condition
                        ? <div><dt>would be ambiguous</dt><dd>{o.ambiguity_condition}</dd></div> : null}
                    {o.refusal_condition
                        ? <div><dt>would be refused</dt><dd>{o.refusal_condition}</dd></div> : null}
                    {o.residual_interpretation ? (
                        <div className="iw-residual">
                            <dt>stays interpretive regardless</dt>
                            <dd>{o.residual_interpretation}</dd>
                        </div>
                    ) : null}
                </dl>
            ) : null}
        </li>
    );
}
