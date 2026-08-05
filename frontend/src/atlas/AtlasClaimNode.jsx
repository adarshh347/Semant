import React from 'react';
import { Handle, Position } from '@xyflow/react';

import { STATUS_LABEL, epistemicLabel, functionLabel } from './atlasPlan.js';

/**
 * ATLAS C4 — one sub-claim, on the canvas, with lines to the evidence that would carry it.
 *
 * A REFUSED CLAIM STAYS ON THE CANVAS, struck through, with the gate's own reason under it. It is
 * the single most important thing this node draws. An argument whose third claim could not be
 * evidenced is a fact about the corpus, and a plan that quietly dropped it would leave a shorter
 * argument that looks complete — which is exactly the shape a writer would go on to draft from.
 *
 * WHAT IS DRAWN AND WHAT IS ONLY WRITTEN. Bound percepts get lines to their images. Everything
 * else — a refused percept, a comparative percept that spans the corpus, an unknown function —
 * is written here in words. A greyed line is still a line, and would put the shape of a supported
 * argument on a canvas whose refusals nobody would then read.
 *
 * A VERDICT SURVIVES ONLY AS LONG AS THE PLAN IT WAS COMPUTED FROM. Edit the claim and its status
 * is marked stale rather than recomputed here: deciding what evidence carries is the gate's job,
 * and a canvas that guessed would be a second, disagreeing planner.
 */
export default function AtlasClaimNode({ data }) {
    const { claim, index, total } = data;
    const struck = Boolean(claim.struck);
    const bound = (claim.percepts || []).filter((p) => p.bound);
    const unbound = (claim.percepts || []).filter((p) => !p.bound);

    return (
        <div className={`atlas-claim${struck ? ' is-struck' : ''}${claim.dirty ? ' is-dirty' : ''}`}
            data-claim-id={claim.claim_id}
            data-status={claim.status}
            data-struck={struck ? 'true' : 'false'}
            style={{ width: 360 }}>

            <div className="atlas-claim-head">
                <span className="atlas-claim-n">{index + 1}<span className="atlas-claim-of">/{total}</span></span>
                <span className={`atlas-claim-status is-${claim.status}`}>
                    {STATUS_LABEL[claim.status] || claim.status}
                </span>
            </div>

            {/* Struck through in the markup, not only in CSS: a screen reader must hear that this
                claim was refused, and a stylesheet that failed to load must not silently promote
                it back into the argument. */}
            <p className="atlas-claim-text">
                {struck ? <s>{claim.text}</s> : claim.text}
            </p>

            {claim.dirty && (
                <p className="atlas-claim-stale" role="note">
                    edited — this verdict is from before the edit; accepting re-binds it
                </p>
            )}

            {struck && (
                <p className="atlas-claim-why" role="note">
                    {claim.reason === 'no_percept_could_be_produced'
                        ? 'no percept proposed for this claim can be produced from these images'
                        : claim.reason}
                </p>
            )}

            {bound.length > 0 && (
                <ul className="atlas-claim-percepts">
                    {bound.map((p) => (
                        <li key={p.step_id} className={`atlas-percept is-${p.function}`}
                            data-step-id={p.step_id} data-bound="true">
                            <span className="atlas-percept-fn">{functionLabel(p.function)}</span>
                            <span className="atlas-percept-act">{p.actuator}</span>
                            <span className="atlas-percept-ep">{epistemicLabel(p.epistemic)}</span>
                            {/* A comparative percept has no single image to point a line at, so it
                                says where it lives instead of being drawn at one of them. */}
                            {p.spans_corpus && (
                                <span className="atlas-percept-span">across the corpus</span>
                            )}
                        </li>
                    ))}
                </ul>
            )}

            {unbound.length > 0 && (
                <ul className="atlas-claim-unbound">
                    {unbound.map((p) => (
                        <li key={p.step_id} data-step-id={p.step_id} data-bound="false">
                            <span className="atlas-percept-act">{p.actuator}</span>
                            {' — '}
                            <span className="atlas-percept-why">{p.why || 'refused'}</span>
                        </li>
                    ))}
                </ul>
            )}

            {(claim.caveats || []).map((c) => (
                <p className="atlas-claim-caveat" role="note" key={c}>{c}</p>
            ))}

            {!struck && (
                <p className="atlas-claim-reach">
                    reaches <strong>{epistemicLabel(claim.achieved_status)}</strong>
                    {claim.downgraded && `, aimed for ${epistemicLabel(claim.target_status)}`}
                </p>
            )}

            {/* The lines leave from here. `isConnectable` is false: a writer draws no bindings by
                hand — a binding is something the gate granted, not something anyone can assert. */}
            <Handle type="source" position={Position.Right} isConnectable={false}
                className="atlas-handle" />
        </div>
    );
}
