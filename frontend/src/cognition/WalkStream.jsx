import React from 'react';

/**
 * COGNITION — the walk, as a stream you can read.
 *
 * Pure: it takes a WalkView and renders it. Every honesty rule this surface has to keep is a
 * rendering decision in this file, so they are all in one place and all reviewable together:
 *
 *   · REFUSALS RENDER. A refused crossing is a row with its reason and its gloss, not a gap. An
 *     agent hemmed in by eleven refusals must not look like one standing in an empty world.
 *   · STATUS IS VISIBLY DISTINCT. `measured` / `interpretive` / `proposed` get different marks,
 *     because a surface where they look alike is a surface where the difference stops mattering.
 *   · NO NARRATED ARRIVAL. A step says it arrived with an empty field. The destination's readings
 *     appear at the NEXT station, because that is where the agent looked.
 *   · AN INTRA-IMAGE STEP SAYS SO. Rendering a depth step as a cross-image analogy would
 *     misdescribe what the agent did.
 */

const statusClass = (status) => {
    if (status === 'measured') return 'cog-status cog-status--measured';
    if (status === 'interpretive') return 'cog-status cog-status--interpretive';
    if (status === 'proposed') return 'cog-status cog-status--proposed';
    return 'cog-status cog-status--other';
};

function Perception({ row }) {
    return (
        <li className="cog-percept">
            <span className={statusClass(row.epistemic)}>{row.epistemic}</span>
            <span className="cog-percept-said">{row.expression || row.detail}</span>
            <span className="cog-percept-meta">
                {row.organ} · {row.basis}
                {row.admissible ? '' : ' · estimate'}
            </span>
        </li>
    );
}

function Refusal({ row }) {
    return (
        <li className="cog-refusal" data-about={row.about}>
            <span className="cog-refusal-tag">could not ground — {row.reason}</span>
            <span className="cog-refusal-gloss">{row.gloss}</span>
            <span className="cog-percept-meta">
                → {row.to_node}
                {row.about === 'traveller' ? ' · about the traveller' : ' · about the crossing'}
            </span>
        </li>
    );
}

function Station({ station }) {
    const perceptions = station.perceptions || [];
    const horizon = station.horizon || { reachable: [], refused: [], tally: {} };
    const tally = horizon.tally || {};

    return (
        <li className="cog-station">
            <div className="cog-station-head">
                <span className="cog-node">{station.node_id}</span>
                <span className="cog-station-tally">
                    {perceptions.length} measured · {(horizon.reachable || []).length} reachable ·{' '}
                    {(horizon.refused || []).length} refused
                </span>
            </div>

            {perceptions.length > 0 ? (
                <ul className="cog-list">
                    {perceptions.map((row, i) => <Perception key={i} row={row} />)}
                </ul>
            ) : (
                /* An empty field is a real answer — "I looked from here and measured nothing" —
                   and it is not the same as not having looked. Said, not left blank. */
                <p className="cog-empty">
                    looked from here and measured nothing. That is a fact about this locus, not a
                    failure to look.
                </p>
            )}

            {(horizon.refused || []).length > 0 && (
                <div className="cog-refusals">
                    <h4 className="cog-sub">
                        refused — {tally.refused_edge || 0} about the crossing,{' '}
                        {tally.refused_traveller || 0} about the traveller
                    </h4>
                    <ul className="cog-list">
                        {horizon.refused.map((row, i) => <Refusal key={i} row={row} />)}
                    </ul>
                </div>
            )}

            {station.ended && (
                <p className="cog-ended">
                    the walk ended here — {station.ended.reason}
                </p>
            )}
        </li>
    );
}

function Step({ step }) {
    return (
        <li className={`cog-step ${step.crossed_image ? '' : 'cog-step--within'}`}>
            <div className="cog-step-arrow" aria-hidden="true" />
            <div className="cog-step-body">
                <span className="cog-step-kind">{step.kind}</span>
                <span className="cog-step-axis">
                    {step.relation || step.axis_ref}
                    {step.systematicity != null && ` · systematicity ${Number(step.systematicity).toFixed(2)}`}
                </span>
                <span className={statusClass(step.epistemic)}>{step.epistemic}</span>
                <span className="cog-step-rule">{step.rule}</span>
                {/* THE ARRIVAL, stated. `movement.step` empties the field; a surface that let a
                    reader assume otherwise would be narrating a destination nobody looked at. */}
                <span className="cog-step-arrival">{step.arrival_detail}</span>
            </div>
        </li>
    );
}

export default function WalkStream({ walk }) {
    if (!walk) return null;
    const stations = walk.stations || [];
    const steps = walk.steps || [];

    return (
        <section className="cog-walk">
            <header className="cog-walk-head">
                <h3 className="cog-walk-title">
                    {walk.temperament || 'no declared character'}
                </h3>
                {walk.character && (
                    <p className="cog-character">
                        {walk.character.detail}
                        <span className="cog-prefers">
                            prefers {walk.character.prefers.join(' → ')}
                        </span>
                    </p>
                )}
                <p className="cog-organs">
                    perceives through {(walk.organ_set || []).join(', ')}
                </p>
            </header>

            <ol className="cog-stream">
                {stations.map((station, i) => (
                    <React.Fragment key={station.node_id + i}>
                        <Station station={station} />
                        {steps[i] && <Step step={steps[i]} />}
                    </React.Fragment>
                ))}
            </ol>

            <footer className="cog-tally">
                {walk.tally.steps} step(s) — {walk.tally.within_one_picture} within one picture,{' '}
                {walk.tally.between_pictures} between pictures · {walk.tally.perceived} measured ·{' '}
                {walk.tally.refused} refused · {walk.tally.proposed} proposed
            </footer>
        </section>
    );
}
