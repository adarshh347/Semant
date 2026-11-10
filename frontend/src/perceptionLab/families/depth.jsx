import React, { useEffect, useMemo, useState } from 'react';
import { Layers } from 'lucide-react';
import { FieldCanvas } from '../fields/FieldInspector';
import { initialDisplayScale } from '../fields/fieldVisual';
import { compatibleDepth, depthProfileSegments, parseDepthCells } from './depthVisual';

const form = { key: 'depth.relative_inverse_depth', label: 'Relative depth',
    quantity: 'estimated_relative_inverse_depth', views: ['near_far', 'grayscale', 'profile'] };
const operations = [{ key: 'depth.estimate', label: 'Estimate relative depth',
    form_key: form.key, producer_key: 'depth.anything_v2_small',
    question: 'What near/far organization does the whole-image depth model estimate?',
    summary: 'Raw relative inverse depth; larger values are nearer. Not metres.',
    adapters: ['depth.anything_v2_small'], inputs: [],
    parameters: [{ name: 'resolution', type: 'enum', required: false, enum: ['standard', 'compact'],
        description: 'Whole-image processor target: standard 518 or compact 392. Changes measurement resolution, not display.' },
    { name: 'alpha_min', type: 'integer', required: false, minimum: 1, maximum: 255,
        description: 'Source alpha below this threshold is unknown. Default 1.' }] }];

function Panel({ client, session, lab, source }) {
    const fields = useMemo(() => lab.ledger.filter((item) => item.identity?.organ_family === 'depth'
        && item.identity?.artifact_kind === 'sample_grid'), [lab.ledger]);
    const [selected, setSelected] = useState('');
    const artifact = fields.find((item) => item.identity.artifact_id === selected) || fields.at(-1);
    const id = artifact?.identity.artifact_id;
    const [data, setData] = useState(null);
    const [view, setView] = useState('colour');
    const [scale, setScale] = useState([0, 1]);
    const [cells, setCells] = useState('');
    const [reading, setReading] = useState(null);
    const [error, setError] = useState('');
    const [otherId, setOtherId] = useState('');
    const [other, setOther] = useState(null);
    const [busy, setBusy] = useState(false);
    useEffect(() => {
        let active = true;
        setData(null); setReading(null); setOther(null); setOtherId(''); setError(''); setCells('');
        if (id) client.fieldPreview({ session_id: session.session_id, artifact_id: id })
            .then((result) => { if (active) { setData(result); setScale(initialDisplayScale(result)); } })
            .catch((failure) => { if (active) setError(failure.message); });
        return () => { active = false; };
    }, [client, session.session_id, id]);
    useEffect(() => {
        let active = true; setOther(null);
        if (otherId) client.fieldPreview({ session_id: session.session_id, artifact_id: otherId })
            .then((result) => { if (active) setOther(result); })
            .catch((failure) => { if (active) setError(failure.message); });
        return () => { active = false; };
    }, [client, session.session_id, otherId]);
    const consume = async (operation, points = null) => {
        setBusy(true); setError('');
        try {
            const result = await client.consumeField({ session_id: session.session_id, artifact_id: id,
                operation, points: points || (operation === 'compare' ? [] : parseDepthCells(cells)),
                compare_artifact_id: operation === 'compare' ? otherId : null });
            setReading(result.derivation);
        } catch (failure) { setError(failure.message); } finally { setBusy(false); }
    };
    const samples = reading?.measurements.result?.samples || [];
    const segments = depthProfileSegments(samples, scale);
    const validScale = scale.every(Number.isFinite) && scale[1] > scale[0];
    const compatible = other && data && compatibleDepth(data.metadata, other.metadata);
    return <section className="pl-panel" aria-label="Depth forms">
        <h2 className="pl-panel-title">Relative depth, not distance</h2>
        <p className="pl-panel-sub">Depth Anything V2 Small estimates the whole image. Larger raw values mean nearer;
            smaller values mean farther. No camera calibration, metres, hidden surfaces or physical ground truth.
            Painted space can be unreliable.</p>
        <p className="pl-panel-sub">Use Direct “Estimate relative depth” or the bounded prompt “estimate relative depth”.
            The plan is shown before Run. To change measurement detail choose standard (518) or compact (392).
            Sampling, reopening and import read saved numbers and never run the model.</p>
        {!fields.length ? <div className="pl-empty"><Layers aria-hidden="true" />
            <h3 className="pl-panel-title">No saved depth field</h3>
            <p>Choose Estimate relative depth below, review the proposed operation, then Run.
                Missing local weights are reported as unavailable; no fixture is substituted.</p>
        </div> : <>
            <label>Saved depth field <select value={id || ''} onChange={(e) => setSelected(e.target.value)}>
                {fields.map((item) => <option key={item.identity.artifact_id} value={item.identity.artifact_id}>
                    {item.identity.artifact_id}</option>)}
            </select></label>
            {!data ? <p className="pl-panel-sub">{error ? 'Saved field unavailable; inspect the error below.' : 'Reading saved depth numbers…'}</p> : <>
                <p className="pl-panel-sub">{data.execution_identity} · {artifact.provenance.producer}
                    {' · '}native field {data.metadata.shape[1]} × {data.metadata.shape[0]}
                    {' · '}preview stride {data.preview.stride || 1}. Display scaling adds no geometric detail.</p>
                <p className="pl-panel-sub">Source: {data.metadata.source_digest}<br />Saved hash: {data.measurement_hash}</p>
                <div className="pl-field-controls">
                    <label>Depth view <select value={view} onChange={(e) => setView(e.target.value)}>
                        <option value="colour">Near/far colour</option><option value="grayscale">Grayscale</option>
                    </select></label>
                    <label>Far display limit <input type="number" value={scale[0]} onChange={(e) => setScale([Number(e.target.value), scale[1]])} /></label>
                    <label>Near display limit <input type="number" value={scale[1]} onChange={(e) => setScale([scale[0], Number(e.target.value)])} /></label>
                </div>
                <p className="pl-panel-sub">Legend: {view === 'colour' ? 'blue = farther, red = nearer' : 'dark = farther, light = nearer'}.
                    Grey checker cells are unknown, not zero. Shared display interval {scale[0]}–{scale[1]} model-relative units,
                    initially valid-preview min/max. Only the display is normalized; saved values and hash are unchanged.</p>
                {!validScale ? <p className="pl-error" role="alert">Near display limit must be greater than far limit.</p> : <div className="pl-field-pair">
                    {source?.photo_url ? <figure><img src={source.photo_url} alt="Depth source image" /><figcaption>Whole-image source</figcaption></figure> : null}
                    <figure><FieldCanvas data={data} scale={scale} view={view} onPoint={(point) => consume('point', [point])} />
                        <figcaption>Saved native depth · click to save an exact point reading</figcaption></figure>
                </div>}
                <label>Native-field cells: x,y; x,y <input value={cells} onChange={(e) => setCells(e.target.value)} placeholder="0,0; 1,0; 2,0" /></label>
                <p className="pl-panel-sub">Keyboard sampling uses exact native-field coordinates, not source/display pixels.
                    A profile follows your explicit cells in order, without inventing interpolated points.
                    ROI means summarize only those cells, not separately inferred crops.</p>
                <div className="pl-field-controls">
                    <button className="pl-btn" type="button" disabled={busy || !cells.trim()} onClick={() => consume('depth.profile')}>Save depth profile</button>
                    <button className="pl-btn" type="button" disabled={busy || !cells.trim()} onClick={() => consume('depth.regional_summary')}>Save regional summary</button>
                </div>
                <label>Compare saved depth <select value={otherId} onChange={(e) => setOtherId(e.target.value)}>
                    <option value="">Select a saved field</option>{fields.filter((item) => item.identity.artifact_id !== id).map((item) =>
                        <option key={item.identity.artifact_id} value={item.identity.artifact_id}>{item.identity.artifact_id}</option>)}
                </select></label>
                <p className="pl-panel-sub">Comparison is numerical repeatability on the same source, grid, transform and convention only.
                    Equal display ranges do not establish physical comparability. Changing processor resolution changes the grid and refuses raw subtraction.</p>
                {other ? <><p className="pl-panel-sub">Both maps use the same display interval.</p>
                    {validScale ? <FieldCanvas data={other} scale={scale} view={view} /> : null}
                    {!compatible ? <p className="pl-error">Incompatible saved fields: source, quantity, scale convention or grid differs.</p> : null}
                    <button className="pl-btn" type="button" disabled={busy || !compatible} onClick={() => consume('compare')}>Compare saved numbers</button></> : null}
                {reading ? <div className="pl-field-reading" aria-live="polite">
                    <h3>{reading.form} · {reading.derivation_id}</h3>
                    {samples.length ? <><p>{samples.filter((sample) => sample.valid).length} valid of {samples.length} explicit samples.
                        Higher profile values mean nearer, not a distance travelled.</p>
                        <svg className="pl-field-canvas" viewBox="0 0 100 100" role="img" aria-label="Saved relative inverse-depth profile">
                            {segments.map((points, index) => <polyline key={index} points={points.join(' ')} fill="none" stroke="currentColor" strokeWidth="1" />)}
                        </svg></> : reading.measurements.result?.mean ? <p>Regional mean: {reading.measurements.result.mean.join(', ')} model-relative units;
                            {' '}{reading.measurements.result.valid_count} valid of {reading.measurements.result.sample_count} requested cells.</p> : null}
                    <details open><summary>Saved numerical reading</summary><pre>{JSON.stringify(reading.measurements.result, null, 2)}</pre></details>
                </div> : null}
                <details><summary>Convention, source transform and raw record</summary>
                    <p>{data.metadata.value_convention}</p><pre>{JSON.stringify(artifact, null, 2)}</pre>
                </details>
            </>}
        </>}
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
    </section>;
}

export const SLOT = Object.freeze({ family: 'depth', label: 'Depth', available: true,
    reason: 'Pinned local Depth Anything V2 Small; larger values nearer, never metres.',
    forms: [form], operations, views: form.views, promptIntents: ['estimate relative depth'], Panel });
