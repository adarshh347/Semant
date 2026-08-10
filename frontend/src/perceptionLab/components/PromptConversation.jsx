import React, { useState } from 'react';
import { organ as organDefinition } from '../contract/perceptionLabContract';
import { EmptyState, PlannerChip } from './Chips';
import { artifactSummary } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — speaking to the organ.
 *
 * THE REFERENCES PANEL IS THE POINT OF THIS COMPONENT. "those two", "that mask", "repeat that"
 * resolve through `active_artifact_id` and `selected_artifact_ids` and through nothing else, so
 * the surface shows — permanently, above the input, not in a tooltip — exactly which ids a
 * follow-up will carry. When that list is empty, the sentence says the follow-up will resolve to
 * nothing, because a person who says "do those two touch?" with nothing selected should find that
 * out before the refusal rather than from it.
 *
 * Each turn keeps the plan it produced and the planner that wrote it, INCLUDING a fallback that
 * did not get to wear the model's name.
 */
export default function PromptConversation({ organ, turns = [], plans = [], selectedIds = [],
    activeId = null, byId, onAsk, busy }) {
    const [text, setText] = useState('');
    const definition = organDefinition(organ);
    const planFor = (plan_id) => plans.find((p) => p.plan_id === plan_id) || null;

    const ask = (value, planner) => {
        const said = (value ?? text).trim();
        if (!said || busy) return;
        onAsk(said, planner);
        setText('');
    };

    return (
        <section className="pl-panel" aria-label="Prompt">
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Prompt</h2>
                <span className="pl-kicker">{organ}</span>
            </div>
            <p className="pl-panel-sub">{definition.question}</p>

            <div className="pl-field" data-references>
                <span className="pl-label">What a follow-up will resolve to</span>
                {selectedIds.length === 0 ? (
                    <p className="pl-panel-sub" data-no-references>
                        Nothing is selected. “that mask” and “those two” resolve through selected
                        ids, so a follow-up naming them will be refused as
                        <code> unknown_reference</code> rather than guessed at.
                    </p>
                ) : (
                    <ul className="pl-list">
                        {selectedIds.map((id) => (
                            <li key={id} className="pl-turn-refs" data-reference={id}>
                                <code>{id}</code>
                                {id === activeId ? ' · active' : ''}
                                {byId?.get(id) ? ` · ${artifactSummary(byId.get(id))}` : ''}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="pl-field">
                <label className="pl-label" htmlFor="pl-prompt">Say it</label>
                <textarea id="pl-prompt" className="pl-textarea" rows={2} value={text}
                    placeholder={definition.prompt_examples[0]}
                    onChange={(e) => setText(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
                    }} />
            </div>

            <div className="pl-btnrow">
                <button type="button" className="pl-btn pl-btn--primary" data-action="ask-model"
                    disabled={!text.trim() || !!busy} onClick={() => ask(undefined, 'model')}>
                    Ask the model planner
                </button>
                <button type="button" className="pl-btn" data-action="ask-rules"
                    disabled={!text.trim() || !!busy} onClick={() => ask(undefined, 'rules')}>
                    Ask the rules planner
                </button>
            </div>

            <div className="pl-examples" role="group" aria-label="Example phrases">
                {definition.prompt_examples.map((example) => (
                    <button key={example} type="button" className="pl-btn pl-btn--quiet"
                        data-example={example} disabled={!!busy}
                        onClick={() => ask(example, 'rules')}>
                        “{example}”
                    </button>
                ))}
            </div>

            <div className="pl-field">
                <span className="pl-label">This session’s turns</span>
                {turns.length === 0 ? (
                    <EmptyState title="Nothing has been asked yet"
                        hint="Every turn keeps the plan it produced and the planner that wrote
                            it, so a fallback can never be read as the model." />
                ) : (
                    <ul className="pl-turns">
                        {turns.map((turn) => {
                            const plan = planFor(turn.plan_id);
                            return (
                                <li key={turn.turn_id} className="pl-turn" data-turn={turn.turn_id}>
                                    <span className="pl-turn-text">“{turn.text}”</span>
                                    <span className="pl-turn-meta">
                                        {turn.at}
                                        {plan ? ` · ${plan.plan_id}` : ''}
                                    </span>
                                    {plan ? (
                                        <span className="pl-chiprow">
                                            <PlannerChip planner={plan.planner}
                                                fellBackFrom={plan.planner_fell_back_from} />
                                            {plan.refusals.map((r) => (
                                                <span key={r.code} className="pl-chip"
                                                    data-turn-refusal={r.code}>{r.code}</span>
                                            ))}
                                        </span>
                                    ) : null}
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </section>
    );
}
