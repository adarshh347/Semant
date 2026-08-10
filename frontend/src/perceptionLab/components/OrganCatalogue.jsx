import React from 'react';
import { CONTRACT, isOrganEnabled } from '../contract/perceptionLabContract';
import { CapabilityChip } from './Chips';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — all eight families, two of them open.
 *
 * The six that are closed are LISTED, with their question, and disabled. That is the whole reason
 * this is a catalogue rather than a two-item switch: a person needs to see that Colour and Depth
 * are registered and deliberately not in this phase, because the alternative is a laboratory that
 * looks complete and is not, and a later phase that arrives as a surprise.
 *
 * A disabled entry keeps its ink. Greying the six into near-invisibility would hide exactly the
 * thing this catalogue is for.
 */
export default function OrganCatalogue({ selected, onSelect, capabilities = {} }) {
    return (
        <section className="pl-panel" aria-label="Organ catalogue">
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Organs</h2>
                <span className="pl-kicker">2 of 8 enabled</span>
            </div>
            <p className="pl-panel-sub">
                Eight perceptual families are registered. This phase opens Extent and Topology; the
                rest are declared and closed, not missing.
            </p>
            <ul className="pl-organs" role="group" aria-label="Choose an organ">
                {CONTRACT.organs.map((organ) => {
                    const enabled = isOrganEnabled(organ.family);
                    return (
                        <li key={organ.family}>
                            <button type="button"
                                className="pl-organ"
                                data-organ={organ.family}
                                data-enabled={enabled}
                                aria-pressed={enabled ? selected === organ.family : undefined}
                                disabled={!enabled}
                                onClick={() => enabled && onSelect(organ.family)}>
                                <span className="pl-organ-name">
                                    {organ.family.replace('_', ' ')}
                                </span>
                                <span className="pl-organ-q">{organ.question}</span>
                                {enabled ? (
                                    <span className="pl-chiprow">
                                        {(organ.adapters || []).map((a) => (
                                            <CapabilityChip key={a.key} adapter={a.key}
                                                state={capabilities[a.key]
                                                    || a.capability_state} />
                                        ))}
                                    </span>
                                ) : (
                                    <span className="pl-organ-off">
                                        registered, and not enabled in this phase
                                    </span>
                                )}
                            </button>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}
