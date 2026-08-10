import React from 'react';
import { organ as organDefinition } from '../contract/perceptionLabContract';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the two switches that decide what may happen.
 *
 * `Isolation | Chain` decides whether the organ lock holds. `Direct | Prompt` decides who writes
 * the proposal. They are two switches and not four buttons, because they answer two independent
 * questions and a person has to be able to change one without changing the other — chain mode
 * with direct controls is a real and useful position.
 *
 * Each switch carries the CONSEQUENCE of the position it is in, in a sentence, next to it. The
 * consequence of isolation is that a prompt asking for a relation will be refused, and finding
 * that out from a refusal is worse than being told first.
 */
export default function ModeControls({ mode, arm, organ, onMode, onArm }) {
    const definition = organDefinition(organ);
    return (
        <section className="pl-panel" aria-label="Mode">
            <div className="pl-modes">
                <div className="pl-modegroup">
                    <span className="pl-modegroup-label" id="pl-mode-label">Scope</span>
                    <div className="pl-segmented" role="group" aria-labelledby="pl-mode-label">
                        <button type="button" className="pl-btn" aria-pressed={mode === 'isolation'}
                            data-mode="isolation" onClick={() => onMode('isolation')}>
                            Isolation
                        </button>
                        <button type="button" className="pl-btn" aria-pressed={mode === 'chain'}
                            data-mode="chain" onClick={() => onMode('chain')}>
                            Chain
                        </button>
                    </div>
                </div>

                <div className="pl-modegroup">
                    <span className="pl-modegroup-label" id="pl-arm-label">Arm</span>
                    <div className="pl-segmented" role="group" aria-labelledby="pl-arm-label">
                        <button type="button" className="pl-btn" aria-pressed={arm === 'direct'}
                            data-arm="direct" onClick={() => onArm('direct')}>
                            Direct
                        </button>
                        <button type="button" className="pl-btn" aria-pressed={arm === 'prompt'}
                            data-arm="prompt" onClick={() => onArm('prompt')}>
                            Prompt
                        </button>
                    </div>
                </div>
            </div>

            <p className="pl-panel-sub" data-mode-consequence={mode}>
                {mode === 'isolation'
                    ? `Locked to ${organ}. A prompt that names another organ's operation is `
                        + 'refused with organ_locked, not quietly redirected.'
                    : 'The organ boundary may be crossed. Each stage keeps its own artifact, '
                        + 'adapter, timing and refusal, and a crossing asks for confirmation '
                        + 'before it runs.'}
            </p>
            <p className="pl-panel-sub" data-arm-consequence={arm}>
                {arm === 'direct'
                    ? 'You choose the operation and its parameters. This establishes the organ '
                        + 'without testing language.'
                    : 'You speak within the selected organ. The planner proposes a typed plan '
                        + 'from a closed vocabulary; the same resolver and the same runner as '
                        + 'Direct.'}
            </p>
            <p className="pl-panel-sub">
                <strong>{definition.question}</strong>
            </p>
        </section>
    );
}
