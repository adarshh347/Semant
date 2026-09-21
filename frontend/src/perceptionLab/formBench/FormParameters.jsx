import React from 'react';
import { CONTRACT } from '../contract/perceptionLabContract';

/** The contract supplies types, bounds, units and initial values to both runtimes. */
export default function FormParameters({ form, values, onChange }) {
    return (CONTRACT.form_parameters[form] || []).map((spec) => {
        const value = values[spec.name] ?? spec.initial;
        const id = `fb-param-${spec.name}`;
        const disabled = spec.required_when && Object.entries(spec.required_when)
            .some(([key, expected]) => values[key] !== expected);
        const props = { id, className: 'pl-input', disabled, 'data-parameter': spec.name };
        let control;
        if (spec.type === 'boolean') {
            control = <input {...props} type="checkbox" checked={!!value}
                onChange={(e) => onChange(spec.name, e.target.checked)} />;
        } else if (spec.type === 'enum') {
            control = <select {...props} value={value}
                onChange={(e) => onChange(spec.name, e.target.value)}>
                {spec.enum.map((v) => <option key={v}>{v}</option>)}
            </select>;
        } else if (spec.type === 'integer_pair') {
            control = <div className="fb-row">{['rows', 'columns'].map((axis, i) => (
                <label key={axis}>{axis}
                    <input {...props} id={`${id}-${axis}`} aria-label={`Grid ${axis}`}
                        type="number" min={spec.minimum} max={spec.maximum} step="1"
                        value={value?.[i] ?? ''} onChange={(e) => {
                            const next = [...value]; next[i] = e.target.value === '' ? '' : Number(e.target.value);
                            onChange(spec.name, next);
                        }} />
                </label>
            ))}</div>;
        } else {
            control = <input {...props} type="number" min={spec.exclusive_minimum}
                max={spec.maximum} step="any" value={value ?? ''}
                onChange={(e) => onChange(spec.name, e.target.value === '' ? undefined : Number(e.target.value))} />;
        }
        return <div className="pl-field" key={spec.name}>
            <label className="pl-label" htmlFor={id}>{spec.name}{spec.units ? ` · ${spec.units}` : ''}</label>
            {control}<p className="pl-panel-sub">{spec.description}</p>
        </div>;
    });
}
