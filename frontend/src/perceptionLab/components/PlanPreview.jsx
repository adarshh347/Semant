import React from 'react';
import { EmptyState, PlannerChip, Refusal } from './Chips';
import { num } from '../display';
import { checkInputs } from '../contract/perceptionLabContract';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the plan, before anything runs.
 *
 * Four lists, and each is here because leaving it out is a specific way to mislead:
 *
 *   PROPOSED   what the planner asked for, including the steps that were refused. A crossing
 *              proposal that is neither run nor shown is a crossing that was quietly dropped.
 *   RESOLVED   what the resolver authorized — with the adapter it chose and the gates it ran.
 *              A resolved step is visibly a different KIND of thing from a proposal, because
 *              only one of them carries `authorized_by: resolver`.
 *   REFUSED    the typed refusals, in full, with their remedy.
 *   DROPPED / CLAMPED  what the planner tried to hand the runner and what a bound did to a
 *              number. This is where a model planner is caught inventing geometry, and it is
 *              worthless if it is only in a log.
 *
 * The run buttons live at the bottom because a plan is read before it is run, and a plan that
 * `requires_confirmation` says so on the button rather than beside it.
 */
export default function PlanPreview({ plan, onRun, onReplay, busy, canRunLive = true }) {
    if (!plan) {
        return (
            <section className="pl-panel" aria-label="Plan">
                <div className="pl-panel-head"><h2 className="pl-panel-title">Plan</h2></div>
                <EmptyState title="No plan yet"
                    hint="Propose one from the Direct controls, or ask for one in the prompt.
                        Nothing runs until a plan is on this page." />
            </section>
        );
    }

    const runnable = plan.resolved_steps.length > 0;

    /**
     * The gate that has not run yet.
     *
     * A plan is resolved for COMPOSING. Some inputs are optional to plan and required to run —
     * occlusion's depth field is the whole reason that distinction exists — so the execution-time
     * check is run here, over the contract, and its answer is shown BEFORE the button rather than
     * discovered after it. This is not a prediction: it is the same `checkInputs` the run will
     * call, with the same flag.
     */
    const willRefuse = plan.resolved_steps
        .map((step) => ({ step, refusal: checkInputs(step.operation, step.input_refs,
            { forExecution: true }) }))
        .filter((r) => r.refusal);

    return (
        <section className="pl-panel" aria-label="Plan" data-plan-id={plan.plan_id}>
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Plan</h2>
                <span className="pl-chiprow">
                    <PlannerChip planner={plan.planner}
                        fellBackFrom={plan.planner_fell_back_from} />
                    <span className="pl-chip" data-plan-mode={plan.mode}>{plan.mode}</span>
                    <span className="pl-chip" data-plan-organ={plan.selected_organ}>
                        {plan.selected_organ}
                    </span>
                </span>
            </div>

            <div className="pl-field">
                <span className="pl-label">Proposed</span>
                {plan.proposed_steps.length === 0 ? (
                    <p className="pl-panel-sub" data-no-proposals>
                        The planner proposed nothing. It reads a closed vocabulary and does not
                        guess.
                    </p>
                ) : (
                    <ul className="pl-steps">
                        {plan.proposed_steps.map((step) => (
                            <li key={step.step_id} className="pl-step" data-role="proposed"
                                data-step={step.step_id}>
                                <span className="pl-step-op">
                                    {step.operation}
                                    <span className="pl-chip" data-step-organ={step.organ}>
                                        {step.organ}
                                    </span>
                                </span>
                                <span className="pl-step-why">{step.rationale}</span>
                                {Object.keys(step.parameters || {}).length ? (
                                    <span className="pl-step-why" data-proposed-parameters>
                                        asked for: {JSON.stringify(step.parameters)}
                                    </span>
                                ) : null}
                                <span className="pl-step-why">
                                    a proposal carries no authority — it has no
                                    <code> authorized_by </code>field to set
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="pl-field">
                <span className="pl-label">Resolved</span>
                {plan.resolved_steps.length === 0 ? (
                    <p className="pl-panel-sub" data-no-resolved>
                        Nothing was authorized. Read the refusals below — this plan will not run.
                    </p>
                ) : (
                    <ul className="pl-steps">
                        {plan.resolved_steps.map((step) => (
                            <li key={step.step_id} className="pl-step" data-role="resolved"
                                data-resolved-step={step.step_id}>
                                <span className="pl-step-op">{step.operation}</span>
                                <span className="pl-step-why">
                                    adapter: {step.adapter || 'chosen at runtime and recorded'}
                                </span>
                                <span className="pl-step-why">
                                    parameters: {JSON.stringify(step.parameters)}
                                </span>
                                <span className="pl-step-why" data-authorized-by={step.authorized_by}>
                                    authorized by {step.authorized_by} · gates:{' '}
                                    {step.prerequisites_checked.join(', ')}
                                </span>
                                {step.input_refs.length ? (
                                    <span className="pl-step-why">
                                        inputs: {step.input_refs.map(
                                            (r) => `${r.role}=${r.artifact_id || r.region_id}`).join(', ')}
                                    </span>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {plan.refusals.length ? (
                <div className="pl-field" data-refusals>
                    <span className="pl-label">Refused</span>
                    {plan.refusals.map((r, i) => (
                        <Refusal key={`${r.code}-${i}`} refusal={r} />
                    ))}
                </div>
            ) : null}

            {plan.dropped_parameters.length ? (
                <div className="pl-field" data-dropped>
                    <span className="pl-label">Dropped parameters</span>
                    <ul className="pl-list">
                        {plan.dropped_parameters.map((d, i) => (
                            <li key={`${d.name}-${i}`} className="pl-step-why"
                                data-dropped-parameter={d.name}>
                                <code>{d.name}</code> — {d.reason}
                            </li>
                        ))}
                    </ul>
                    <p className="pl-panel-sub">
                        Recorded rather than ignored. This is where a planner trying to hand the
                        runner geometry it invented becomes visible.
                    </p>
                </div>
            ) : null}

            {plan.clamped_parameters.length ? (
                <div className="pl-field" data-clamped>
                    <span className="pl-label">Clamped parameters</span>
                    <ul className="pl-list">
                        {plan.clamped_parameters.map((c, i) => (
                            <li key={`${c.name}-${i}`} className="pl-step-why"
                                data-clamped-parameter={c.name}>
                                <code>{c.name}</code>: asked {num(c.requested)}, ran{' '}
                                {num(c.applied)} — {c.bound}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}

            {willRefuse.length ? (
                <div className="pl-field" data-will-refuse>
                    <span className="pl-label">Authorized to compose, and it will refuse when run</span>
                    {willRefuse.map(({ step, refusal }) => (
                        <div key={step.step_id} data-will-refuse-step={step.step_id}>
                            <Refusal refusal={refusal} />
                        </div>
                    ))}
                    <p className="pl-panel-sub">
                        This is a legitimate thing to have on screen. The input is optional to plan
                        and required to run, so the request can be assembled now and the refusal is
                        stated now rather than sprung on the button. Running it records the refusal
                        in the ledger, with its run and its provenance.
                    </p>
                </div>
            ) : null}

            {plan.prerequisites.length ? (
                <div className="pl-field" data-prerequisites>
                    <span className="pl-label">Before it runs</span>
                    <ul className="pl-list">
                        {plan.prerequisites.map((p, i) => (
                            <li key={i} className="pl-step-why">{p}</li>
                        ))}
                    </ul>
                </div>
            ) : null}

            <div className="pl-btnrow">
                <button type="button" className="pl-btn pl-btn--primary" data-action="run-fixture"
                    disabled={!runnable || !!busy}
                    onClick={() => onRun(plan.plan_id, 'FIXTURE')}>
                    {plan.requires_confirmation
                        ? 'Confirm and run from fixtures' : 'Run from fixtures'}
                </button>
                <button type="button" className="pl-btn" data-action="run-live"
                    disabled={!runnable || !!busy || !canRunLive}
                    title={canRunLive ? 'call the adapters'
                        : 'this client has no live adapters to call'}
                    onClick={() => onRun(plan.plan_id, 'LIVE')}>
                    {plan.requires_confirmation ? 'Confirm and run LIVE' : 'Run LIVE'}
                </button>
                {onReplay ? (
                    <button type="button" className="pl-btn pl-btn--quiet" data-action="replay-last"
                        disabled={!!busy} onClick={onReplay}>
                        Replay the last run
                    </button>
                ) : null}
            </div>
            {plan.requires_confirmation ? (
                <p className="pl-panel-sub" data-requires-confirmation>
                    This plan asks for confirmation before it runs — it crosses the organ
                    boundary, or contains an operation that declares it.
                </p>
            ) : null}
        </section>
    );
}
