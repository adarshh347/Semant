import React, { useCallback, useState } from 'react';
import { Sparkle, X, Eye } from 'lucide-react';
import { planFromPrompt, quickAction, QUICK_CHIPS } from './attunementPlanner';
import {
    groupActionsByTarget, summarizeActions, setActionStatus,
    actionCanApplyNow, actionNeedsGeometry, actionToShortReason,
    TARGET_LABEL, fieldRoleLabel, traceRoleLabel, relationRoleLabel,
    manuscriptModeLabel, challengeTypeLabel,
} from './perceptualActions';
import './AttunementPanel.css';

/**
 * AttunementPanel — CIRCUIT-001 P2B. First Attention, and the acts it opens.
 *
 * The premise: a curator should be able to begin from what caught them, not from an
 * operation. "Find parts" remains, and becomes one act among several rather than the door.
 *
 * Three things this panel must never do, each of which it would be easy to do:
 *
 *  1. **Never say "detected".** The planner keys on words the curator typed. A card says
 *     *you said "lighting"* — it does not say Semant saw light. The distance between those
 *     two sentences is the whole honesty of the feature.
 *
 *  2. **Never silently no-op.** An act the mounted surface cannot carry out renders as
 *     *Preview only — execution path not wired yet*, with no Apply button. An Apply that
 *     quietly does nothing teaches the curator that the whole panel is theatre.
 *
 *  3. **Never draw for you.** Every image mark is staged, not made: applying one arms the
 *     tool and carries the label; the geometry is the curator's hand. The card says so.
 *
 * All derivation is in ./perceptualActions and ./attunementPlanner (both node-tested); this
 * file is JSX and one piece of local state.
 */

const PROMPT_HELP = 'Name a gaze, fold, pressure, light, material, or relation — Semant will turn it into suggested acts.';

/** The payload lines worth showing on a card, per family. Never the raw object. */
function payloadFacts(action) {
    const p = action.payload || {};
    const facts = [];
    switch (action.type) {
        case 'find_parts':
            if (p.way_of_looking) facts.push(['way of looking', p.way_of_looking]);
            break;
        case 'brush_field':
            facts.push(['role', fieldRoleLabel(p.field_role)]);
            if (p.target_hint) facts.push(['where', p.target_hint]);
            if (p.geometry_mode) facts.push(['as', p.geometry_mode.replace(/_/g, ' ')]);
            break;
        case 'trace_direction':
            facts.push(['role', traceRoleLabel(p.trace_role)]);
            if (p.from_hint) facts.push(['from', p.from_hint]);
            if (p.to_hint) facts.push(['to', p.to_hint]);
            break;
        case 'connect_marks':
            facts.push(['relation', relationRoleLabel(p.relation_role)]);
            break;
        case 'compose_percept':
            if (p.intent) facts.push(['act', p.intent]);
            break;
        case 'start_manuscript':
            facts.push(['as', manuscriptModeLabel(p.mode)]);
            facts.push(['saving', 'nothing until you save']);
            break;
        case 'challenge_percept':
            facts.push(['asks for', challengeTypeLabel(p.challenge_type)]);
            break;
        case 'ask_model_reading':
            facts.push(['reading', p.requested_reading_type || '—']);
            facts.push(['dispatch', 'not sent']);
            break;
        default: break;
    }
    return facts;
}

function ActionCard({ action, canApply, onApply, onPreview, onDismiss }) {
    const reason = actionToShortReason(action);
    const facts = payloadFacts(action);
    const staged = action.status === 'previewed';
    const applied = action.status === 'applied';

    return (
        <article
            className={`ap-card is-${action.status}`}
            data-action-type={action.type}
            data-action-id={action.id}
        >
            <header className="ap-card-head">
                {action.payload?.color && (
                    <span className="ap-swatch" style={{ background: action.payload.color }} aria-hidden="true" />
                )}
                <h4 className="ap-card-label">{action.label}</h4>
                <span className={`ap-source ap-source--${action.source}`}>
                    {action.source === 'user' ? 'yours' : 'suggested'}
                </span>
            </header>

            {reason && <p className="ap-card-reason">{reason}</p>}

            {facts.length > 0 && (
                <dl className="ap-facts">
                    {facts.map(([k, v]) => (
                        <div key={k} className="ap-fact">
                            <dt>{k}</dt><dd>{v}</dd>
                        </div>
                    ))}
                </dl>
            )}

            {action.type === 'compose_percept' && action.payload.draft_text && (
                <blockquote className="ap-draft">{action.payload.draft_text}</blockquote>
            )}

            {action.warnings.length > 0 && (
                <ul className="ap-warnings">
                    {action.warnings.map((w) => <li key={w}>{w}</li>)}
                </ul>
            )}

            {applied ? (
                <p className="ap-state ap-state--applied">Carried through.</p>
            ) : staged ? (
                <p className="ap-state ap-state--staged">
                    {actionNeedsGeometry(action)
                        ? 'Ready — make the mark on the image.'
                        : 'Staged. Nothing is saved.'}
                </p>
            ) : !canApply ? (
                /* The honest admission. Better than an Apply button that does nothing. */
                <p className="ap-state ap-state--preview">
                    Preview only — execution path not wired yet.
                </p>
            ) : null}

            <div className="ap-card-actions">
                {canApply && !applied && (
                    <button type="button" className="ap-apply" onClick={() => onApply(action)}>
                        {actionNeedsGeometry(action) ? 'Arm this' : 'Apply'}
                    </button>
                )}
                {!applied && (
                    <button type="button" className="ap-preview" onClick={() => onPreview(action)}>
                        <Eye size={12} /> Preview
                    </button>
                )}
                <button
                    type="button" className="ap-dismiss"
                    aria-label={`Dismiss: ${action.label}`}
                    onClick={() => onDismiss(action)}
                >
                    <X size={12} />
                </button>
            </div>
        </article>
    );
}

export default function AttunementPanel({
    hasParts = false,
    wayOfLooking = 'general',
    capabilities = [],
    onApplyAction = null,
}) {
    const [prompt, setPrompt] = useState('');
    const [actions, setActions] = useState([]);
    const [planned, setPlanned] = useState(false);

    const suggest = useCallback((text) => {
        const t = String(text ?? prompt).trim();
        if (!t) return;
        const { actions: next } = planFromPrompt(t, {
            hasParts, wayOfLooking, now: Date.now(),
        });
        setActions(next);
        setPlanned(true);
    }, [prompt, hasParts, wayOfLooking]);

    const addQuick = useCallback((kind) => {
        const a = quickAction(kind, { now: Date.now(), wayOfLooking });
        if (!a) return;                       // unknown chip: nothing, rather than something plausible
        setActions((cur) => [a, ...cur]);
        setPlanned(true);
    }, [wayOfLooking]);

    // Dismiss marks status and re-renders. It changes NOTHING outside this panel — no
    // store write, no fetch — which is what makes refusing a suggestion free.
    const dismiss = useCallback((action) => {
        setActions((cur) => setActionStatus(cur, action.id, 'dismissed'));
    }, []);

    const preview = useCallback((action) => {
        setActions((cur) => setActionStatus(cur, action.id, 'previewed'));
    }, []);

    const apply = useCallback((action) => {
        const outcome = onApplyAction?.(action);
        // The executor decides what happened. `armed` means the tool is ready and the
        // curator's hand completes it; `applied` means it is done.
        setActions((cur) => setActionStatus(cur, action.id, outcome === 'armed' ? 'previewed' : 'applied'));
    }, [onApplyAction]);

    const live = actions.filter((a) => a.status !== 'dismissed');
    const groups = groupActionsByTarget(live);

    return (
        <section className="ap" aria-label="First attention">
            <div className="ap-first">
                <span className="ap-eyebrow">First attention</span>
                <label className="ap-prompt-wrap">
                    <span className="ap-sr">What catches you here?</span>
                    <textarea
                        className="ap-prompt"
                        rows={3}
                        placeholder="What catches you here?"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); suggest(); }
                        }}
                    />
                </label>
                <p className="ap-help">{PROMPT_HELP}</p>
                <div className="ap-first-actions">
                    <button
                        type="button" className="ap-suggest"
                        disabled={!prompt.trim()} onClick={() => suggest()}
                    >
                        <Sparkle size={14} /> Suggest acts
                    </button>
                </div>
                <div className="ap-chips">
                    {QUICK_CHIPS.map((c) => (
                        <button
                            key={c.key} type="button" className="ap-chip"
                            data-chip={c.key} onClick={() => addQuick(c.key)}
                        >
                            {c.label}
                        </button>
                    ))}
                </div>
            </div>

            {planned && (
                <div className="ap-suggested">
                    <div className="ap-suggested-head">
                        {/* "Suggested acts", never "detected". The planner keys on words the
                            curator typed; it has no access to the image at all. */}
                        <span className="ap-eyebrow">Suggested acts</span>
                        <span className="ap-summary">{summarizeActions(live)}</span>
                    </div>

                    {live.length === 0 ? (
                        <p className="ap-empty">
                            Nothing here Semant recognises yet — try naming a gaze, a light, a
                            fold, or a relation.
                        </p>
                    ) : (
                        groups.map((g) => (
                            <div key={g.target} className="ap-group">
                                <h5 className="ap-group-title">{TARGET_LABEL[g.target]}</h5>
                                {g.actions.map((a) => (
                                    <ActionCard
                                        key={a.id}
                                        action={a}
                                        canApply={actionCanApplyNow(a, capabilities)}
                                        onApply={apply}
                                        onPreview={preview}
                                        onDismiss={dismiss}
                                    />
                                ))}
                            </div>
                        ))
                    )}
                </div>
            )}
        </section>
    );
}
