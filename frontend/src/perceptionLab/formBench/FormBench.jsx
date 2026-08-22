import React, { useMemo, useState } from 'react';
import { viewsFor } from '../forms';
import SafeView from './drawing';
import { thresholdsOf } from './thresholds';
import { EmptyState } from '../components/Chips';

/**
 * PERCEPTUAL-FORMS-001H — the DIRECT FORM level: choose a form, a producer, inputs and a drawing.
 *
 * THE PRIMARY TESTING SURFACE, and everything about it is arranged so a person can tell what they
 * are looking at:
 *
 *   THE PRODUCER IS CHOSEN AND NAMED. Every producer says whether it is a model, code or a
 *   person's hand, which checkpoint it would load and which revision it is pinned at. One that is
 *   not running says WHY and what would change it — the previous rehearsal lost time to a bare
 *   `unavailable` over a checkpoint that was already on the disk.
 *
 *   A FORM THAT CANNOT BE WRITTEN SAYS WHICH ABSENCE IT IS. Deferred, no-operation and
 *   capability-unavailable are three different next actions, and sixteen of the nineteen forms are
 *   in the second — computable, renderable, and unable to become an artifact.
 *
 *   TWO DRAWINGS AT ONCE. Every form declares several views and they are not decorations: the
 *   rings view and the winding view of one boundary answer different questions, and a surface that
 *   showed one at a time would make a person hold the other in their head.
 *
 *   A THRESHOLD IS ALWAYS ON SCREEN. Where a payload carries one — a soft field's cut, a density
 *   field's bandwidth, a fusion's weight — it is printed beside the drawing, because a scalar that
 *   decides what is drawn and is not shown is a decision nobody made.
 *
 * NOTHING HERE ACCEPTS A HYPOTHESIS. The controls compose the person's decision and send it; the
 * producer refuses or records it. There is no button on this panel that turns a hypothesis into
 * anything else, and there is no route behind one.
 */
export default function FormBench({ bench, onDerive }) {
    const [formKey, setFormKey] = useState('extent.boundary_rings');
    const [selected, setSelected] = useState([]);
    const [producerKey, setProducerKey] = useState(null);
    const [left, setLeft] = useState(null);
    const [right, setRight] = useState(null);

    const forms = useMemo(() => bench.forms || [], [bench.forms]);
    const entry = useMemo(() => forms.find((f) => f.form === formKey) || null, [forms, formKey]);
    const derivable = new Set(bench.derivable || []);
    const inputs = bench.inputsFor(formKey);
    const produced = useMemo(
        () => [...bench.derivations].reverse().find((d) => d.form === formKey) || null,
        [bench.derivations, formKey]);

    const views = useMemo(() => {
        try { return viewsFor(formKey).map((v) => v.key); } catch { return []; }
    }, [formKey]);

    if (!bench.available) {
        return (
            <section className="pl-panel fb" aria-label="Direct form">
                <EmptyState title="This wire has no form catalogue" hint={bench.unavailable} />
            </section>
        );
    }
    if (!forms.length) {
        return (
            <section className="pl-panel fb" aria-label="Direct form">
                <EmptyState title="Reading the form catalogue"
                    hint="Nineteen forms and zero forms look the same in a list, so nothing is
                        drawn until the catalogue answers." />
            </section>
        );
    }

    const chosen = entry?.producers?.find((p) => p.key === producerKey) || null;
    const canDerive = derivable.has(formKey) && inputs.length > 0;

    return (
        <section className="pl-panel fb" aria-label="Direct form" data-form={formKey}>
            <header className="fb-head">
                <h2 className="pl-panel-title">Direct form</h2>
                <p className="pl-panel-sub">
                    One form, one producer, one set of inputs. This is the primary testing surface:
                    it establishes what a form IS without also testing whether a sequence or a
                    sentence reached it.
                </p>
            </header>

            <div className="fb-row">
                <label className="fb-label" htmlFor="fb-form">Form</label>
                <select id="fb-form" className="fb-select" value={formKey}
                    onChange={(e) => { setFormKey(e.target.value); setProducerKey(null); }}>
                    {forms.map((f) => (
                        <option key={f.form} value={f.form}>
                            {f.label} — {f.form}{f.can_be_produced_here ? '' : ' (not here)'}
                        </option>
                    ))}
                </select>
            </div>

            {entry ? (
                <>
                    <p className="fb-question"><strong>{entry.question}</strong></p>
                    <p className="fb-state" data-state={entry.state}
                        data-writable={String(entry.writable_as_artifact)}>
                        <span className="pl-chip" data-state={entry.state}>{entry.state}</span>
                        <span className="pl-chip" data-writable={String(entry.writable_as_artifact)}>
                            {entry.writable_as_artifact
                                ? 'may be written as an artifact'
                                : 'cannot become an artifact'}
                        </span>
                        {entry.carries_hypothesis ? (
                            <span className="pl-chip" data-hypothesis="true">carries a hypothesis</span>
                        ) : null}
                    </p>
                    {entry.blocked_by.length ? (
                        <p className="fb-blocked" role="note">
                            <strong>{entry.blocked_by.join(' · ')}</strong> — {entry.note}
                        </p>
                    ) : null}

                    <div className="fb-row">
                        <span className="fb-label" id="fb-producer-label">Producer</span>
                        <ul className="fb-producers" aria-labelledby="fb-producer-label">
                            {entry.producers.map((p) => (
                                <li key={p.key} className="fb-producer" data-kind={p.kind}
                                    data-state={p.state}>
                                    <label>
                                        <input type="radio" name="fb-producer"
                                            value={p.key} checked={producerKey === p.key}
                                            onChange={() => setProducerKey(p.key)} />
                                        <span className="fb-producer-key">{p.key}</span>
                                        <span className="pl-chip" data-kind={p.kind}>{p.kind}</span>
                                        <span className="pl-chip" data-state={p.state}>{p.state}</span>
                                    </label>
                                    <p className="fb-producer-detail">
                                        {p.label}
                                        {p.model ? ` · ${p.model}` : ' · no checkpoint'}
                                        {p.revision ? ` @ ${p.revision}` : ' · no revision'}
                                    </p>
                                    {p.reason ? (
                                        <p className="fb-producer-reason">
                                            {p.reason}{p.remedy ? ` → ${p.remedy}` : ''}
                                        </p>
                                    ) : null}
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="fb-row">
                        <span className="fb-label" id="fb-input-label">Inputs</span>
                        {inputs.length ? (
                            <ul className="fb-inputs" aria-labelledby="fb-input-label">
                                {inputs.map((a) => (
                                    <li key={a.identity.artifact_id}>
                                        <label>
                                            <input type="checkbox"
                                                value={a.identity.artifact_id}
                                                checked={selected.includes(a.identity.artifact_id)}
                                                onChange={(e) => setSelected((held) => (
                                                    e.target.checked
                                                        ? [...held, a.identity.artifact_id]
                                                        : held.filter(
                                                            (k) => k !== a.identity.artifact_id)))} />
                                            {a.identity.artifact_id} · {a.identity.artifact_kind}
                                        </label>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="fb-empty">
                                This form reads {entry.accepted_input_forms.join(', ') || 'the image'}
                                {' '}and this session holds none. Measure one first.
                            </p>
                        )}
                    </div>

                    <div className="fb-actions">
                        <button type="button" className="pl-btn" data-action="derive"
                            disabled={!canDerive || !selected.length || bench.busy}
                            onClick={() => onDerive(formKey, selected)}>
                            Produce this form
                        </button>
                        {!derivable.has(formKey) ? (
                            <span className="fb-note">
                                No producer in this deployment computes {formKey}. Nothing is
                                substituted.
                            </span>
                        ) : null}
                        {chosen && chosen.state !== 'available' ? (
                            <span className="fb-note" data-refused="true">
                                {chosen.key} is {chosen.state}: {chosen.reason}
                            </span>
                        ) : null}
                    </div>
                </>
            ) : null}

            {produced ? (
                <ProducedForm record={produced} views={views} left={left} right={right}
                    onLeft={setLeft} onRight={setRight} />
            ) : (
                <EmptyState title="Nothing derived yet for this form"
                    hint="A form that has not been produced and a form that produced nothing are
                        two different answers, and this panel will say which." />
            )}
        </section>
    );
}

function ProducedForm({ record, views, left, right, onLeft, onRight }) {
    const options = views;
    const first = left || options[0] || null;
    const second = right || options[1] || options[0] || null;
    const thresholds = thresholdsOf(record);
    return (
        <div className="fb-produced" data-derivation={record.derivation_id}>
            <p className="fb-receipt">
                <span className="pl-chip" data-kind={record.producer_kind}>
                    {record.producer_kind}
                </span>
                <span className="pl-chip">{record.producer}</span>
                {record.producer_revision
                    ? <span className="pl-chip">@ {record.producer_revision}</span> : null}
                <span className="pl-chip" data-ceiling={record.ceiling}>
                    ceiling {record.ceiling}
                </span>
                <span className="pl-chip" data-basis={record.basis}>basis {record.basis}</span>
                <span className="pl-chip" data-producible={String(record.producible)}>
                    {record.producible ? 'producible' : 'deferred'}
                </span>
            </p>

            {record.refusals?.length ? (
                <ul className="fb-refusals" aria-label="Refusals">
                    {record.refusals.map((r, i) => (
                        <li key={i} data-code={r.code}>
                            <strong>{r.code}</strong> — {r.message}
                            {r.remedy ? <em> {r.remedy}</em> : null}
                        </li>
                    ))}
                </ul>
            ) : null}

            {record.omitted?.length ? (
                <ul className="fb-omitted" aria-label="Left out">
                    {record.omitted.map((o, i) => (
                        <li key={i} data-reason={o.reason}>
                            <strong>{o.reason}</strong> · {o.what} — {o.detail}
                        </li>
                    ))}
                </ul>
            ) : null}

            {thresholds.length ? (
                <dl className="fb-thresholds" aria-label="Scalars that decide the drawing">
                    {thresholds.map(([name, value]) => (
                        <div key={name}>
                            <dt>{name}</dt>
                            <dd>{String(value)}</dd>
                        </div>
                    ))}
                </dl>
            ) : null}

            <div className="fb-compare">
                {[[first, onLeft, 'left'], [second, onRight, 'right']].map(([view, onPick, side]) => (
                    <div className="fb-pane" key={side} data-side={side} data-view={view || 'none'}>
                        <label className="fb-label">
                            {side === 'left' ? 'Drawing A' : 'Drawing B'}
                            <select className="fb-select" value={view || ''}
                                onChange={(e) => onPick(e.target.value)}>
                                {options.map((k) => <option key={k} value={k}>{k}</option>)}
                            </select>
                        </label>
                        <div className="fb-canvas">
                            {record.payload && view
                                ? <SafeView form={record.form} view={view}
                                    payload={record.payload} />
                                : <p className="fb-empty">No payload to draw.</p>}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
