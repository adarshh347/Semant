import React, { useState } from 'react';
import EpistemicBadge from './EpistemicBadge.jsx';

/**
 * INQUIRY WORKBENCH — the provisional reading, and the label it never loses.
 *
 * This is the most persuasive paragraph on the page. It is a good contemporary VLM looking at
 * pictures and saying what it thinks, which is exactly what the plan wants it to be — abundant,
 * intelligent, and *interpretive at strongest*. The whole architecture exists because a paragraph
 * like this is normally the ONLY output, and one persuasive paragraph is not inspectable.
 *
 * So the badge is not decoration and is not placed at the bottom. It sits in the header, above
 * the first line, and the contract has already refused to let a `measured` status reach it. Where
 * a cap was applied the fact is shown rather than swallowed: an upstream role claiming to have
 * measured something is a defect somebody needs to see, and a silent downgrade would hide it just
 * as effectively as a silent promotion would hide the epistemic problem.
 *
 * The model receipt is available and closed by default — who produced this is provenance, and a
 * reader meeting the reading should meet the reading.
 */
export default function ProvisionalReading({ reading }) {
    const [open, setOpen] = useState(false);
    if (!reading || !reading.text) return null;

    const statusField = { value: reading.status, known: true };

    return (
        <section className="iw-panel iw-reading" aria-label="Provisional reading">
            <header className="iw-reading-head">
                <h2 className="iw-h2">What Semant thinks it is looking at</h2>
                <EpistemicBadge field={statusField} />
            </header>

            {reading.capped_from ? (
                <p className="iw-capped" role="status" data-capped-from={reading.capped_from}>
                    This reading arrived claiming <code>{reading.capped_from}</code>. A scene
                    reading cannot be stronger than interpretive — it is shown as interpretive,
                    and the mismatch is reported here rather than hidden.
                </p>
            ) : null}

            <p className="iw-reading-text">{reading.text}</p>

            <p className="iw-quiet iw-reading-note">
                A reading about the images, not a measurement of them. Nothing below rests on this
                paragraph — the claims do, and they are shown separately so you can disagree with
                one without discarding the rest.
            </p>

            <button
                type="button"
                className="iw-expand"
                aria-expanded={open}
                onClick={() => setOpen((v) => !v)}
            >
                {open ? 'Hide' : 'Show'} model receipt
            </button>

            {open ? (
                <dl className="iw-receipt-list">
                    <div><dt>role</dt><dd>{reading.source || '—'}</dd></div>
                    <div><dt>model</dt><dd>{reading.model || '—'}</dd></div>
                    {Object.entries(reading.provenance || {}).map(([k, v]) => (
                        <div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>
                    ))}
                </dl>
            ) : null}
        </section>
    );
}
