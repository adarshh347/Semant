import React, { useEffect, useState } from 'react';
import { EmptyState } from '../components/Chips';

/**
 * PERCEPTUAL-FORMS-001H — the DETERMINISTIC RECIPE level: a bounded sequence over direct forms.
 *
 * WHAT MAKES THIS A DIFFERENT LEVEL AND NOT A SHORTCUT. A recipe performs the same direct acts a
 * person could perform one at a time, in a fixed order, with the bounds written down beforehand.
 * It reaches the same resolver and the same adapter; the only thing it removes is the retyping.
 *
 * EVERY STEP STAYS ON SCREEN, before it runs and after. A study that showed a spinner and then an
 * answer would make the middle of it unobservable, which is the whole reason the laboratory
 * exists. Operation steps and derivation steps are drawn differently because they cost
 * differently: one may reach a model, and one reads records and calls nothing.
 *
 * READINESS IS ASKED BEFORE ANYTHING IS SPENT. Four of the seven studies cannot write their final
 * record in this deployment, and the reason is shown next to the button rather than discovered at
 * the last step with every model call already made.
 *
 * A DECISION POINT IS NOT A CONFIRMATION DIALOG. Each one carries why a person is needed, and the
 * tray prints that sentence — Lane G's loader refuses a decision point without one precisely so
 * this panel always has something to print.
 */
export default function RecipeTray({ bench, onPlan }) {
    const [openKey, setOpenKey] = useState(null);
    const [bindings, setBindings] = useState({});

    useEffect(() => {
        (bench.recipes || []).forEach((r) => {
            if (bench.readiness[r.key] === undefined) bench.checkRecipe(r.key);
        });
        // The catalogue is stable; readiness is a property of THIS session and is re-asked when
        // the recipe list arrives. Re-asking on every render would be a request per keystroke.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [bench.recipes]);

    if (!bench.available) {
        return (
            <section className="pl-panel fb" aria-label="Deterministic recipe">
                <EmptyState title="This wire has no recipe catalogue" hint={bench.unavailable} />
            </section>
        );
    }
    if (!bench.recipes) {
        return (
            <section className="pl-panel fb" aria-label="Deterministic recipe">
                <EmptyState title="Reading the recipe catalogue"
                    hint="Seven studies and no studies look the same in a list." />
            </section>
        );
    }

    return (
        <section className="pl-panel fb" aria-label="Deterministic recipe">
            <header className="fb-head">
                <h2 className="pl-panel-title">Deterministic recipe</h2>
                <p className="pl-panel-sub">
                    A bounded sequence of the same direct acts, in a fixed order, with the bounds
                    declared before it runs. It reaches the same resolver and the same adapter a
                    pressed control does; what it removes is the retyping, not a gate.
                </p>
            </header>

            <ul className="fb-recipes">
                {bench.recipes.map((recipe) => {
                    const ready = bench.readiness[recipe.key];
                    const open = openKey === recipe.key;
                    return (
                        <li key={recipe.key} className="fb-recipe" data-recipe={recipe.key}
                            data-ready={String(ready?.ready ?? 'unknown')}>
                            <button type="button" className="fb-recipe-head"
                                aria-expanded={open}
                                onClick={() => setOpenKey(open ? null : recipe.key)}>
                                <span className="fb-recipe-label">{recipe.label}</span>
                                <span className="pl-chip" data-organ={recipe.organ}>
                                    {recipe.organ} · {recipe.mode}
                                </span>
                                <span className="pl-chip" data-bound="model">
                                    ≤{recipe.bounds.max_model_calls} model calls
                                </span>
                                {ready ? (
                                    <span className="pl-chip" data-ready={String(ready.ready)}>
                                        {ready.ready ? 'ready' : 'blocked'}
                                    </span>
                                ) : null}
                            </button>
                            <p className="fb-recipe-question">{recipe.question}</p>

                            {ready && !ready.ready ? (
                                <ul className="fb-reasons" aria-label="Why this cannot finish here">
                                    {ready.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                                </ul>
                            ) : null}

                            {open ? (
                                <div className="fb-recipe-body">
                                    <ol className="fb-steps">
                                        {recipe.steps.map((step) => (
                                            <li key={step.id} className="fb-step"
                                                data-kind={step.kind} data-step={step.id}>
                                                <span className="pl-chip" data-kind={step.kind}>
                                                    {step.kind}
                                                </span>
                                                <code>{step.operation || step.produces}</code>
                                                <p className="fb-step-why">{step.why}</p>
                                                {step.asks_for.length ? (
                                                    <p className="fb-step-asks">
                                                        asks you for: {step.asks_for.join(', ')}
                                                    </p>
                                                ) : null}
                                            </li>
                                        ))}
                                    </ol>

                                    <ul className="fb-decisions" aria-label="Where you decide">
                                        {recipe.decision_points.map((point, i) => (
                                            <li key={i} data-at={point.at}>
                                                <strong>{point.asks}</strong>
                                                <p>{point.why_a_person}</p>
                                                <p className="fb-options">
                                                    {point.options.join(' · ')}
                                                </p>
                                            </li>
                                        ))}
                                    </ul>

                                    <ul className="fb-stops" aria-label="How it stops">
                                        {recipe.stop_conditions.map((stop, i) => (
                                            <li key={i} data-outcome={stop.outcome}>
                                                <span className="pl-chip" data-outcome={stop.outcome}>
                                                    {stop.outcome}
                                                </span>
                                                {stop.when} — {stop.reason}
                                            </li>
                                        ))}
                                    </ul>

                                    {Object.keys(recipe.asks_for).length ? (
                                        <div className="fb-bindings">
                                            {Object.entries(recipe.asks_for).map(([step, names]) =>
                                                names.filter((n) => n === 'concept').map((name) => (
                                                    <label key={`${step}.${name}`} className="fb-label">
                                                        {step} · {name}
                                                        <input type="text" className="fb-input"
                                                            value={bindings[step]?.[name] || ''}
                                                            onChange={(e) => setBindings((held) => ({
                                                                ...held,
                                                                [step]: { ...(held[step] || {}),
                                                                    [name]: e.target.value },
                                                            }))} />
                                                    </label>
                                                )))}
                                        </div>
                                    ) : null}

                                    <button type="button" className="pl-btn" data-action="plan"
                                        disabled={bench.busy}
                                        onClick={() => onPlan(recipe.key, bindings)}>
                                        Propose this study
                                    </button>
                                    <p className="fb-note">
                                        Nothing runs when you press this. The plan comes back for
                                        you to look at, and a study that crosses organs asks for
                                        confirmation before it runs.
                                    </p>
                                </div>
                            ) : null}
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}
