import React, { useEffect, useRef, useState } from 'react';
import { FieldCanvas } from '../fields/FieldInspector';
import { pixelAt } from '../fields/fieldVisual';
import { axisReading, coherenceView, headlessMarks, localCells, orientationMeta } from './orientationVisual';
import './orientation_flow.css';

export function OrientationView({ data, source, view, spacing, opacity, selected, paths = [], onPoint }) {
    const [height, width] = data.metadata.shape;
    const meta = orientationMeta(data);
    const sourceSize = meta.source_working_size || [width, height];
    const axial = data.metadata.kind === 'axial_orientation_2d';
    const marks = headlessMarks(data, spacing);
    if (view !== 'headless_marks' || !axial) return <FieldCanvas
        data={coherenceView(data)} scale={meta.form === 'energy' ? [0, .05] : [0, 1]}
        view="grayscale" onPoint={onPoint} />;
    return <svg className="pl-orientation-view" viewBox={`-.5 -.5 ${width} ${height}`}
        preserveAspectRatio="none" style={{ aspectRatio: `${sourceSize[0]} / ${sourceSize[1]}` }}
        role="img" tabIndex={0} aria-label="Saved headless tangent marks. Click to select a field pixel; use seed controls for keyboard selection."
        onClick={(event) => onPoint?.(pixelAt(event.clientX, event.clientY,
            event.currentTarget.getBoundingClientRect(), data.metadata))}
        onKeyDown={(event) => { if (event.key === 'Enter' && selected) onPoint?.(selected); }}>
        {source?.photo_url ? <image href={source.photo_url} x="-.5" y="-.5"
            width={width} height={height} preserveAspectRatio="none" /> : null}
        <g opacity={opacity} className="pl-orientation-marks">
            {marks.map((mark, index) => <line key={index} x1={mark.x1} y1={mark.y1}
                x2={mark.x2} y2={mark.y2} vectorEffect="non-scaling-stroke" />)}</g>
        <g className="pl-orientation-paths">{paths.map((path, index) => <g key={index}>
            <polyline points={path.points.map((point) => point.join(',')).join(' ')}
                vectorEffect="non-scaling-stroke" />
            <circle cx={path.stop_point[0]} cy={path.stop_point[1]} r="2"
                vectorEffect="non-scaling-stroke"><title>{path.stop_reason}</title></circle>
        </g>)}</g>
        {selected ? <circle className="pl-orientation-seed" cx={selected[0]} cy={selected[1]} r="2.5"
            vectorEffect="non-scaling-stroke"><title>Selected seed</title></circle> : null}
    </svg>;
}

function Panel({ client, session, source, lab }) {
    const fields = (lab.ledger || []).filter((entry) => entry.identity?.organ_family === 'orientation_flow'
        && entry.identity?.artifact_kind === 'sample_grid');
    const active = fields.find((entry) => entry.identity.artifact_id === lab.activeId) || fields.at(-1);
    const id = active?.identity.artifact_id;
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [pending, setPending] = useState(false);
    const [parameters, setParameters] = useState({ derivative_sigma: 1, integration_sigma: 3, min_coherence: .15 });
    const [view, setView] = useState('headless_marks');
    const [spacing, setSpacing] = useState(12);
    const [opacity, setOpacity] = useState(.85);
    const [seed, setSeed] = useState([0, 0]);
    const [selected, setSelected] = useState(null);
    const [point, setPoint] = useState(null);
    const [reading, setReading] = useState(null);
    const [history, setHistory] = useState([]);
    const [traceSettings, setTraceSettings] = useState({ step_size: .5, max_steps: 512,
        max_length: 128, min_coherence: .15, max_turn_degrees: 60, directions: 'both' });
    const [radius, setRadius] = useState(4);
    const [otherId, setOtherId] = useState('');
    const [other, setOther] = useState(null);
    const requestEpoch = useRef(0);
    useEffect(() => {
        let live = true;
        requestEpoch.current += 1;
        setData(null); setReading(null); setPoint(null); setSelected(null); setError('');
        setOtherId(''); setOther(null); setHistory([]); setPending(false);
        if (!id || !client.fieldPreview) return undefined;
        client.fieldPreview({ session_id: session.session_id, artifact_id: id })
            .then((result) => { if (live) setData(result); })
            .catch((failure) => { if (live) setError(failure.message); });
        if (client.derivations) client.derivations({ session_id: session.session_id })
            .then((result) => { if (live) setHistory((result.derivations || []).filter(
                (item) => item.input_artifact_ids?.includes(id)
                    && ['field.orientation_flow.trace', 'field.orientation_flow.axial_summary'].includes(item.form))); })
            .catch((failure) => { if (live) setError(`Saved derived readings unavailable: ${failure.message}`); });
        return () => { live = false; requestEpoch.current += 1; };
    }, [client, id, session.session_id]);
    useEffect(() => {
        let live = true;
        setOther(null);
        if (otherId) client.fieldPreview({ session_id: session.session_id, artifact_id: otherId })
            .then((result) => { if (live) setOther(result); })
            .catch((failure) => { if (live) setError(failure.message); });
        return () => { live = false; };
    }, [client, id, otherId, session.session_id]);
    const consume = async (operation, points, settings = {}) => {
        if (!id || pending) return;
        const epoch = requestEpoch.current;
        setPending(true); setError('');
        try {
            const result = await client.consumeField({ session_id: session.session_id,
                artifact_id: id, operation, points, parameters: settings });
            if (epoch !== requestEpoch.current) return;
            if (operation === 'point') setPoint(result.derivation);
            else { setReading(result.derivation); setHistory((items) => [...items, result.derivation]); }
        } catch (failure) { if (epoch === requestEpoch.current) setError(failure.message); }
        finally { if (epoch === requestEpoch.current) setPending(false); }
    };
    const select = (value) => { if (!pending) { setSelected(value); setSeed(value); setPoint(null); consume('point', [value]); } };
    const meta = orientationMeta(data);
    const axial = data?.metadata.kind === 'axial_orientation_2d';
    const result = reading?.measurements?.result;
    const pointResult = point?.measurements?.result;
    const axis = axial && axisReading(pointResult?.values);
    const paths = result?.paths || [];
    const run = (lab.runs || []).find((item) => item.run_id === active?.identity.run_id);
    const runTime = run?.duration_ms;
    const compatible = fields.filter((entry) => entry.identity.artifact_id !== id
        && entry.measurement?.payload?.form_key === active?.measurement?.payload?.form_key);
    return <section className="pl-panel pl-orientation" aria-label="Orientation and flow instrument">
        <h2 className="pl-panel-title">Local orientation, without arrowheads</h2>
        <p className="pl-panel-sub">A CPU structure tensor measures one local tangent to image structure.
            0° and 180° are the same axis. This is not optical motion, stroke identity or the path of a painter’s hand.
            Crossings and weak/flat regions can have no supported axis. No mask or model is required.</p>
        <div className="pl-field-controls">{Object.entries(parameters).map(([key, value]) => <label key={key}>
            {key.replaceAll('_', ' ')}<input type="number" value={value}
                min={key === 'min_coherence' ? .01 : key === 'derivative_sigma' ? .5 : 1}
                max={key === 'min_coherence' ? 1 : key === 'derivative_sigma' ? 3 : 8}
                step={key === 'min_coherence' ? .05 : .5}
                onChange={(event) => setParameters({ ...parameters, [key]: Number(event.target.value) })} /></label>)}</div>
        <p className="pl-panel-sub">Derivative sigma smooths before differentiation; integration sigma sets
            the tensor neighbourhood, both in field pixels. Minimum coherence rejects weak axes, not unlikely objects.
            Measurement changes create new records. Whole-image grid: at most 256 pixels on the longest edge.</p>
        <div className="pl-btnrow">{SLOT.operations.map((operation) => <button key={operation.key}
            type="button" className="pl-btn" disabled={!!lab.busy}
            onClick={() => lab.planDirectly(operation.key, parameters, [])}>{operation.label}</button>)}</div>
        <p className="pl-panel-sub">Bounded prompt: “show local orientation”. Tracing requires an explicit
            point below; “trace from the selected point” is not yet connected to prompt context.</p>
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
        {!fields.length ? <div className="pl-orientation-empty"><span aria-hidden="true">◇</span>
            <h3>No saved direction field yet</h3><p>Choose a source, then “Show local orientation” to review and run its plan.</p></div>
            : <><label>Saved orientation result<select value={id || ''}
                onChange={(event) => lab.setActiveId(event.target.value)}>
                {fields.map((entry) => <option key={entry.identity.artifact_id}
                    value={entry.identity.artifact_id}>{entry.identity.operation} · {entry.identity.artifact_id}</option>)}</select></label>
            {!data ? <p className="pl-panel-sub">Reading saved field…</p> : <>
                <p className="pl-panel-sub">{data.execution_identity} · {active.provenance.producer} · CPU ·
                    {' '}{run?.outcome || 'saved result'} · {runTime == null ? 'run timing unavailable' : `${runTime.toFixed(1)} ms`}
                    {' · '}zero model calls · {data.metadata.shape.join(' × ')}.</p>
                <p className="pl-panel-sub">Record {id} · measurement hash <code>{data.measurement_hash}</code></p>
                <div className="pl-field-controls">
                    {axial ? <label>Saved-field view<select value={view} onChange={(event) => setView(event.target.value)}>
                        <option value="headless_marks">Headless tangent marks</option>
                        <option value="coherence_wash">Coherence wash</option></select></label> : null}
                    <label>Mark spacing (field pixels, display only)<input type="range" min="6" max="24" step="2"
                        value={spacing} onChange={(event) => setSpacing(Number(event.target.value))} /></label>
                    <label>Mark opacity (display only)<input type="range" min="0.1" max="1" step="0.05"
                        value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /></label>
                </div>
                <p className="pl-panel-sub">All marks have equal length, set only by display spacing; opacity is display-only.
                    Horizontal = 0°, downward diagonal = 45°, vertical = 90°, upward diagonal = 135°.
                    Coherence wash uses fixed 0–1 (dark–light), not confidence. Energy uses fixed 0–0.05 squared encoded-luma
                    gradient; clipping is display-only. Checker cells are invalid, not zero.</p>
                {!source?.photo_url ? <p className="pl-panel-sub">Source preview unavailable; saved axes and numerical consumers still work.</p> : null}
                <OrientationView data={data} source={source} view={view} spacing={spacing} opacity={opacity}
                    selected={selected} paths={paths} onPoint={select} />
                {axial && !data.preview.valid.some(Boolean) ? <p role="status">No supported axes at this scale. Try a smaller smoothing scale,
                    or inspect energy; this result does not assert horizontal orientation.</p> : null}
                <div className="pl-field-controls">{['x', 'y'].map((name, index) => <label key={name}>Seed {name}
                    <input type="number" min="0" max={data.metadata.shape[1-index] - 1}
                        value={seed[index]} onChange={(event) => setSeed(seed.map((v, i) => i === index ? Number(event.target.value) : v))} /></label>)}
                    <button className="pl-btn" type="button" disabled={pending} onClick={() => select(seed)}>Select and sample point</button></div>
                {pointResult ? <p className="pl-panel-sub" aria-live="polite">Point {pointResult.x}, {pointResult.y}: {pointResult.valid
                    ? axis ? `tangent ${axis.degrees.toFixed(2)}°; coherence ${axis.coherence.toFixed(4)}`
                        : `${pointResult.values.join(', ')} ${data.metadata.units}` : 'invalid / unknown'} · saved {point.derivation_id}</p> : null}
                {axial ? <><h3 className="pl-panel-title">Follow the saved field</h3>
                    <p className="pl-panel-sub">Select a point first. Seeds and limits below are saved with each derived path.
                        A path is constructed from saved numbers, not newly observed geometry. Circles mark stopping points.</p>
                    <div className="pl-field-controls">{[['step_size', .1, 1, .1], ['max_steps', 1, 2048, 1],
                        ['max_length', .1, 1024, 1], ['min_coherence', .01, 1, .05], ['max_turn_degrees', 1, 90, 1]]
                        .map(([key, min, max, step]) => <label key={key}>{key.replaceAll('_', ' ')}
                            <input type="number" value={traceSettings[key]} min={min} max={max} step={step}
                                onChange={(event) => setTraceSettings({ ...traceSettings, [key]: Number(event.target.value) })} /></label>)}
                        <label>Axis traversal<select value={traceSettings.directions}
                            onChange={(event) => setTraceSettings({ ...traceSettings, directions: event.target.value })}>
                            <option value="both">Both signs</option><option value="positive">Positive convention</option>
                            <option value="negative">Negative convention</option></select></label></div>
                    <button className="pl-btn" type="button" disabled={!selected || pending}
                        onClick={() => { setView('headless_marks'); consume('orientation_flow.trace', [selected], traceSettings); }}>
                        Follow the field from selected point</button>
                    <div className="pl-field-controls"><label>Summary radius (field cells)<input type="number" min="0" max="16"
                        value={radius} onChange={(event) => setRadius(Number(event.target.value))} /></label>
                        <button className="pl-btn" type="button" disabled={!selected || pending || !Number.isInteger(radius) || radius < 0 || radius > 16}
                            onClick={() => consume('orientation_flow.axial_summary', localCells(data, selected, radius),
                                { weighting: 'coherence', bins: 12 })}>Save local axial distribution</button></div>
                    <p className="pl-panel-sub">Summary uses the clipped square of unique cells around the selected point,
                        weighted by local coherence in doubled-angle space. Field values are never changed.</p>
                </> : null}
                {pending ? <p role="status">Reading saved numerical data…</p> : null}
                {history.length ? <label>Reopen saved trace or summary<select value={reading?.derivation_id || ''}
                    onChange={(event) => { const found = history.find((item) => item.derivation_id === event.target.value);
                        setReading(found);
                        if (found?.measurements.result.seeds) {
                            const saved = found.measurements.result;
                            setSelected(saved.seeds[0]); setSeed(saved.seeds[0]); setPoint(null);
                            if (saved.parameters) setTraceSettings(saved.parameters);
                            setView('headless_marks');
                        } }}>
                    <option value="">Choose a saved derived result</option>{history.map((item) => <option
                        key={item.derivation_id} value={item.derivation_id}>{item.form} · {item.derivation_id}</option>)}</select></label> : null}
                {reading ? <div className="pl-field-reading" aria-live="polite"><p>{reading.derivation_id} ·
                    {' '}{reading.duration_ms?.toFixed(1)} ms · saved-field consumer, zero producer calls.</p>
                    {result?.paths ? <ul>{result.paths.map((path, index) => <li key={index}>Seed {path.seed.join(', ')} ·
                        sign {path.direction_sign} · {path.steps} steps · {path.length_field_pixels.toFixed(2)} field pixels ·
                        stopped: {path.stop_reason.replaceAll('_', ' ')}</li>)}</ul> : null}
                    {result?.sample_count != null ? <><p>{result.valid_count}/{result.sample_count} valid cells ·
                        mean axis {result.mean_axis_degrees == null ? 'undefined' : `${result.mean_axis_degrees.toFixed(2)}°`} ·
                        axial concentration {result.axial_resultant_length?.toFixed(4) ?? 'undefined'} ·
                        mean local coherence {result.mean_local_coherence?.toFixed(4) ?? 'undefined'}.</p>
                        <p>Distribution ({result.weighting}-weighted): {result.histogram_weights.map((value, i) =>
                            `${result.bin_edges_degrees[i].toFixed(1)}–${result.bin_edges_degrees[i + 1].toFixed(1)}°: ${value.toFixed(2)}`).join(' · ')}</p></> : null}
                    <details><summary>Exact saved derivation and settings</summary><pre>{JSON.stringify(reading, null, 2)}</pre></details>
                </div> : null}
                <label>Compare another measurement, fixed display scale<select value={otherId}
                    onChange={(event) => setOtherId(event.target.value)}>
                    <option value="">Choose same form, different saved settings</option>{compatible.map((entry) =>
                        <option key={entry.identity.artifact_id} value={entry.identity.artifact_id}>{entry.identity.artifact_id}</option>)}</select></label>
                {other ? <><p className="pl-panel-sub">Comparison record {otherId}. Both views use the same glyph/scale settings.
                    Parameters: {JSON.stringify(orientationMeta(other).parameters)}</p>
                    <OrientationView data={other} source={source} view={view} spacing={spacing} opacity={opacity} /></> : null}
                <details><summary>Measurement parameters, coordinate mapping and raw saved field</summary>
                    <p>Field-pixel tangents map to source-pixel tangents with the inverse source-to-field linear transform.
                        Rounded grid dimensions are disclosed; the source overlay preserves the original aspect ratio.</p>
                    <pre>{JSON.stringify({ convention: meta, payload: active.measurement.payload }, null, 2)}</pre></details>
                <p className="pl-panel-sub">Use the Lab’s Save/export/import and separate human-review controls below.
                    Reopened or imported fields support the same trace and summary operations without source processing.</p>
            </>}</>}
    </section>;
}

const parameters = [
    { name: 'derivative_sigma', type: 'number', required: false, minimum: .5, maximum: 3,
        description: 'Gaussian presmoothing in field pixels, default 1.' },
    { name: 'integration_sigma', type: 'number', required: false, minimum: 1, maximum: 8,
        description: 'Tensor neighbourhood in field pixels, default 3.' },
    { name: 'min_coherence', type: 'number', required: false, minimum: .01, maximum: 1,
        description: 'Minimum anisotropy for an axis, default 0.15; not confidence.' },
];
export const SLOT = Object.freeze({ family: 'orientation_flow', label: 'Orientation / flow', available: true,
    reason: 'CPU tensor tangent, coherence and energy; not optical motion.',
    forms: [
        { key: 'orientation_flow.tangent', label: 'Local axial tangent', quantity: 'coherence_weighted_axial_tangent',
            views: ['headless_marks', 'coherence_wash', 'trace'] },
        { key: 'orientation_flow.coherence', label: 'Tensor coherence', quantity: 'structure_tensor_anisotropy', views: ['coherence_wash'] },
        { key: 'orientation_flow.energy', label: 'Gradient energy', quantity: 'structure_tensor_trace', views: ['energy_wash'] },
    ],
    operations: [['tangent', 'Show local orientation'], ['coherence', 'Measure tensor coherence'],
        ['energy', 'Measure gradient energy']].map(([key, label]) => ({ key: `orientation_flow.${key}`, label,
        form_key: `orientation_flow.${key}`, producer_key: `orientation_flow.${key}`, question: label,
        summary: 'Bounded CPU structure tensor on encoded-sRGB luma; no SAM or learned model.',
        parameters, adapters: [`orientation_flow.${key}`], inputs: [],
        prompt_intents: key === 'tangent' ? ['show local orientation'] : [] })),
    views: ['headless_marks', 'coherence_wash', 'energy_wash', 'trace'],
    promptIntents: ['show local orientation'], Panel });
