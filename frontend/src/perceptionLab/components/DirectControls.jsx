import React, { useMemo, useState } from 'react';
import { availableOperations } from '../planning';
import { Refusal } from './Chips';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the Direct arm, built from the contract's own declarations.
 *
 * Every control here is generated from `operation.parameters`: its type, its bounds, whether it
 * is required, and its description. Nothing is hand-written per operation, which is not a
 * tidiness argument — it is the only way the controls cannot drift from what the resolver will
 * accept. A hand-built slider with the wrong maximum produces a clamp the person did not ask for
 * and cannot see the reason for.
 *
 * A CLOSED OPERATION IS SHOWN, DISABLED, WITH ITS REASON. `extent.find_named` when SAM 3 is not
 * running is not absent from this panel: it is present, unavailable, and carries
 * "sam3_concept is in the catalogue and is not running here". A missing button teaches nothing
 * about the deployment.
 *
 * Inputs are chosen from the session's SELECTED artifacts and nowhere else, which is the same
 * rule the prompt arm obeys. The two arms cannot differ about what an identity is.
 */

const ParameterField = ({ spec, value, onChange, operationKey }) => {
    const id = `pl-p-${operationKey}-${spec.name}`;
    const common = { id, className: 'pl-input', 'data-parameter': spec.name };
    const label = (
        <label className="pl-label" htmlFor={id}>
            {spec.name}
            {spec.required ? <span aria-hidden="true"> ·&nbsp;required</span> : null}
        </label>
    );
    let control = null;
    if (spec.type === 'enum') {
        control = (
            <select {...common} className="pl-select" value={value ?? ''}
                onChange={(e) => onChange(e.target.value || undefined)}>
                <option value="">
                    {spec.required ? 'choose…' : 'let the runtime choose, and record what it chose'}
                </option>
                {(spec.enum || []).map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
        );
    } else if (spec.type === 'boolean') {
        control = (
            <input {...common} type="checkbox" checked={!!value}
                onChange={(e) => onChange(e.target.checked)} />
        );
    } else if (spec.type === 'integer' || spec.type === 'number') {
        control = (
            <input {...common} type="number" value={value ?? ''}
                min={spec.minimum ?? undefined} max={spec.maximum ?? undefined}
                step={spec.type === 'integer' ? 1 : 'any'}
                onChange={(e) => onChange(e.target.value === ''
                    ? undefined
                    : (spec.type === 'integer' ? parseInt(e.target.value, 10)
                        : parseFloat(e.target.value)))} />
        );
    } else if (spec.type === 'string') {
        control = (
            <input {...common} type="text" value={value ?? ''} maxLength={spec.max_length}
                onChange={(e) => onChange(e.target.value || undefined)} />
        );
    } else {
        // point_list, box, mask_rle, string_list — authored by the stage tools, not typed here.
        return (
            <div className="pl-field">
                {label}
                <p className="pl-panel-sub" data-parameter={spec.name}>
                    {value
                        ? `supplied by the stage — ${describeGeometry(spec.type, value)}`
                        : `${spec.type}: drawn on the stage, not typed here.`}
                    {' '}{spec.description}
                </p>
            </div>
        );
    }
    return (
        <div className="pl-field">
            {label}
            {control}
            <p className="pl-panel-sub">{spec.description}</p>
        </div>
    );
};

const describeGeometry = (type, value) => {
    if (type === 'point_list') return `${value.length} points`;
    if (type === 'box') return `box at ${value.x?.toFixed?.(2)}, ${value.y?.toFixed?.(2)}`;
    if (type === 'mask_rle') return `a ${value.size?.join('×')} mask`;
    if (type === 'string_list') return value.join(', ');
    return 'supplied';
};

export default function DirectControls({ organ, mode, capabilities, selectedIds, ledger,
    stageParameters = {}, onPropose, busy }) {
    const operations = useMemo(
        () => availableOperations({ selectedOrgan: organ, mode, capabilityStates: capabilities }),
        [organ, mode, capabilities]);
    const [chosenKey, setChosenKey] = useState(operations[0]?.key || null);
    const [parameters, setParameters] = useState({});
    const [roleChoices, setRoleChoices] = useState({});

    const chosen = operations.find((o) => o.key === chosenKey) || operations[0] || null;
    if (!chosen) return null;

    const merged = { ...parameters, ...stageParameters[chosen.key] };

    const inputRefs = (chosen.inputs || []).flatMap((spec) => {
        const picked = roleChoices[spec.role] || [];
        return picked.map((artifact_id) => ({
            role: spec.role, scope: 'session', artifact_id, region_id: null, geometry_rev: null,
        }));
    });

    const selectable = ledger.filter((a) => selectedIds.includes(a.identity.artifact_id));

    return (
        <section className="pl-panel" aria-label="Direct controls">
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Direct</h2>
                <span className="pl-kicker">{organ}</span>
            </div>

            <div className="pl-field">
                <span className="pl-label" id="pl-op-label">Operation</span>
                <div className="pl-btnrow" role="group" aria-labelledby="pl-op-label">
                    {operations.map((op) => (
                        <button key={op.key} type="button" className="pl-btn"
                            data-operation={op.key}
                            aria-pressed={chosen.key === op.key}
                            disabled={!op.enabled}
                            title={op.enabled ? op.summary : op.refusal.message}
                            onClick={() => { setChosenKey(op.key); setParameters({}); }}>
                            {op.label}
                        </button>
                    ))}
                </div>
            </div>

            <p className="pl-panel-sub" data-operation-question>{chosen.question}</p>

            {!chosen.enabled ? <Refusal refusal={chosen.refusal} /> : null}

            {(chosen.parameters || []).map((spec) => (
                <ParameterField key={spec.name} spec={spec} operationKey={chosen.key}
                    value={merged[spec.name]}
                    onChange={(v) => setParameters((p) => ({ ...p, [spec.name]: v }))} />
            ))}

            {(chosen.inputs || []).map((spec) => (
                <fieldset className="pl-field" key={spec.role} data-input-role={spec.role}>
                    <legend className="pl-label">
                        {spec.role} · {spec.min}–{spec.max}
                        {spec.required ? ' · required' : ''}
                    </legend>
                    <p className="pl-panel-sub">{spec.description}</p>
                    {selectable.length === 0 ? (
                        <p className="pl-panel-sub" data-no-inputs>
                            Nothing is selected. An input resolves through a selected id — the
                            laboratory will not pick one for you.
                        </p>
                    ) : (
                        <ul className="pl-list">
                            {selectable.map((a) => {
                                const id = a.identity.artifact_id;
                                const on = (roleChoices[spec.role] || []).includes(id);
                                return (
                                    <li key={id}>
                                        <button type="button" className="pl-row"
                                            data-role-option={`${spec.role}:${id}`}
                                            aria-pressed={on}
                                            onClick={() => setRoleChoices((prev) => {
                                                const cur = prev[spec.role] || [];
                                                const next = on ? cur.filter((x) => x !== id)
                                                    : [...cur, id].slice(-spec.max);
                                                return { ...prev, [spec.role]: next };
                                            })}>
                                            <span className="pl-row-name">{id}</span>
                                            <span className="pl-row-meta">
                                                {a.identity.artifact_kind}
                                            </span>
                                        </button>
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </fieldset>
            ))}

            <div className="pl-btnrow">
                <button type="button" className="pl-btn pl-btn--primary"
                    data-action="propose"
                    disabled={!chosen.enabled || !!busy}
                    onClick={() => onPropose(chosen.key, stripUndefined(merged), inputRefs)}>
                    Propose a plan
                </button>
            </div>
            <p className="pl-panel-sub">
                A proposal is not a run. The plan below shows exactly what the resolver
                authorized, what it dropped, and what it refused, before anything executes.
            </p>
        </section>
    );
}

const stripUndefined = (o) => Object.fromEntries(
    Object.entries(o).filter(([, v]) => v !== undefined && v !== ''));
