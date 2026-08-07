import React from 'react';

/**
 * WAVE4 — the producer's own numbers, shown and not summarised.
 *
 * A curator deciding whether a "nesting" is really an occlusion needs the ordering statistic, the
 * floor it must clear, the depth grid it was read at, and the containment it contradicts. This
 * renders those and computes nothing: no score, no confidence bar, no "strong / weak" label.
 *
 * The temptation is real and it is the one the whole surface exists to resist. An ordering of
 * 0.9822 against a floor of 0.95 *looks* like something a progress bar could express — and a bar
 * would be this component deciding how convincing the evidence is, which is the curator's
 * judgement and the reason the loop has a human in it at all.
 *
 * ## Absent is shown absent
 *
 * A field the proposal does not carry is rendered as missing, never as zero and never omitted. A
 * row silently dropped is a curator deciding without a number they would have wanted; a zero is
 * worse, because it reads as a measurement.
 */

/** Field order and labels for the occlusion kind — the only kind filed today. */
const OCCLUSION_ROWS = [
    ['ordering_separation', 'ordering statistic',
     'P(a cell of the front region reads nearer than a cell of the back one), ties at half'],
    ['separation_floor', 'the floor it must clear',
     'chosen legible-and-arbitrary before any sweep, and still not derived'],
    ['ordering_ceiling', 'the ceiling this pair could reach',
     'a part’s cells sit inside its container’s, so every part-cell meets itself as a tie: the ordering is capped at 1 − k/(2n)'],
    ['depth_grid', 'depth grid',
     'the count of occlusions in this corpus is a function of the resolution used to look'],
    ['basis', 'basis', 'mask is measured geometry; box is an estimate of an extent'],
    ['front_cells', 'cells, front region', null],
    ['back_cells', 'cells, back region', null],
];

function Missing() {
    return <span className="cur-ev-missing">not carried by this proposal</span>;
}

function value(row) {
    if (row === null || row === undefined || row === '') return <Missing />;
    if (typeof row === 'number') return <span className="cur-ev-num">{formatNumber(row)}</span>;
    return <span className="cur-ev-str">{String(row)}</span>;
}

function formatNumber(n) {
    if (Number.isInteger(n)) return String(n);
    // Four places: the ordering statistic separates classes in its third and fourth digit
    // (0.9822 superseded against 0.9775 standing), and rounding to two would erase the
    // distinction this whole surface is about.
    return n.toFixed(4);
}

/**
 * A RATIO always keeps its four places, even when it lands on a round number.
 *
 * Caught on the live queue: a containment of exactly 1.0 rendered as `1` beside a nesting index of
 * `0.9958`, and the pair read as though one were a count and the other a measurement. They are both
 * measurements. `Number.isInteger` is the right rule for a cell count and the wrong one for a
 * quantity that happens to have hit its ceiling.
 */
function formatRatio(n) {
    return typeof n === 'number' ? n.toFixed(4) : String(n);
}

export default function EvidenceTable({ evidence, subject }) {
    const ev = evidence || {};
    const contradicts = ev.contradicts || null;

    return (
        <div className="cur-evidence">
            {subject && subject.claim ? (
                <p className="cur-ev-claim">{subject.claim}</p>
            ) : null}

            <table className="cur-ev-table">
                <tbody>
                    {OCCLUSION_ROWS.map(([key, label, note]) => (
                        <tr key={key}>
                            <th scope="row">
                                {label}
                                {note ? <span className="cur-ev-note">{note}</span> : null}
                            </th>
                            <td>{value(ev[key])}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {contradicts ? (
                <div className="cur-ev-contradicts">
                    <h4>what this contradicts</h4>
                    <p>
                        The nestedness organ measured <code>{contradicts.relation}</code> on the{' '}
                        <code>{contradicts.basis}</code> basis — containment{' '}
                        <strong>{formatRatio(contradicts.containment)}</strong>, nesting index{' '}
                        <strong>{formatRatio(contradicts.nesting_index)}</strong>. Both readings are
                        measured; they are about different things, and depth says the extents overlap
                        in the image plane while the regions sit at different distances.
                    </p>
                </div>
            ) : null}

            {ev.detail ? <p className="cur-ev-detail">{ev.detail}</p> : null}
        </div>
    );
}
