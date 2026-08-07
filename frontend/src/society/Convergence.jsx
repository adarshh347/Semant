import React, { useState } from 'react';
import WalkStream from '../cognition/WalkStream.jsx';

/**
 * SOCIETY — the journeys beside the encounter.
 *
 * The society route walks each member to the meeting and (since WAVE4 · journeys) hands back the
 * whole walk. This draws them, so "earned by travel" stops being a sentence in a docstring and
 * becomes the thing on screen: several beings each travel, each by its own character, and converge.
 *
 * IT REUSES `WalkStream` RATHER THAN RE-RENDERING A WALK. That is the point of the component
 * boundary: refusals, arrival, status marks and the intra-image distinction are all decided in one
 * place, so this surface cannot quietly render a refusal differently from the way /cognition does.
 * A second walk renderer would be a second set of honesty rules, and the one that drifted would be
 * the one nobody was reading.
 *
 * The walks are COLLAPSED by default. Three full streams above the partition would bury the
 * encounter, and the encounter is what the page is for — but they are one click away and the
 * summary line says what is inside, so nothing is hidden, only folded.
 */

function Arrival({ walk }) {
    const last = (walk.stations || [])[(walk.stations || []).length - 1];
    return (
        <p className="soc-arrival">
            arrived at <span className="cog-node">{last?.node_id}</span>
            {' — '}{walk.tally.steps} step(s), {walk.tally.perceived} measured,{' '}
            {walk.tally.refused} refused on the way
        </p>
    );
}

function Journey({ walk, open, onToggle }) {
    return (
        <li className="soc-journey">
            <button className="soc-journey-head" type="button" onClick={onToggle}
                    aria-expanded={open}>
                <span className="soc-member-id">{walk.agent_id}</span>
                <span className="soc-journey-char">
                    {walk.temperament || 'no declared character'}
                </span>
                <span className="cog-percept-meta">{(walk.organ_set || []).join(', ')}</span>
                <span className="soc-journey-toggle">{open ? '−' : '+'}</span>
            </button>

            {/* WHY THIS AGENT IS HERE, said whether or not the walk is expanded. A collapsed
                journey must still account for the arrival — otherwise folding it would hide the
                one thing the convergence is claiming. */}
            <Arrival walk={walk} />
            {walk.character && (
                <p className="soc-journey-detail">{walk.character.detail}</p>
            )}

            {open && <WalkStream walk={walk} />}
        </li>
    );
}

export default function Convergence({ walks, nodeId }) {
    const entries = Object.entries(walks || {});
    const [open, setOpen] = useState({});
    if (entries.length === 0) return null;

    return (
        <section className="soc-convergence">
            <h2 className="soc-h2">how they got here</h2>
            <p className="soc-convergence-lede">
                Each of these walked to <span className="cog-node">{nodeId}</span> along crossings it
                could stand on. A group that had not travelled would have been refused a meeting —
                so the partition below rests on these.
            </p>
            <ul className="soc-journeys">
                {entries.map(([agentId, walk]) => (
                    <Journey key={agentId} walk={walk} open={!!open[agentId]}
                             onToggle={() => setOpen((o) => ({ ...o, [agentId]: !o[agentId] }))} />
                ))}
            </ul>
            <p className="soc-converge-arrow" aria-hidden="true">↓</p>
        </section>
    );
}
