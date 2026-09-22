import React, { useEffect, useMemo, useRef, useState } from 'react';
import { pixelAt } from '../fields/fieldVisual';
import { labSwatch, pixelsFor } from './colourVisual';
import './colour.css';

const CHANNELS = [
    ['sRGB_R', 0, 1], ['sRGB_G', 0, 1], ['sRGB_B', 0, 1],
    ['Lab_L', 0, 100], ['Lab_a', -127, 127], ['Lab_b', -127, 127],
];

function convention(data) {
    try { return JSON.parse(data?.metadata?.value_convention || '{}'); }
    catch { return {}; }
}

export function ColourCanvas({ data, channel, opacity, viewRange, onPoint, onPath }) {
    const canvas = useRef(null);
    const trail = useRef([]);
    const [cursor, setCursor] = useState([0, 0]);
    useEffect(() => {
        if (!data || !canvas.current) return;
        const { width, height, bytes } = pixelsFor(data, channel, opacity, viewRange);
        const element = canvas.current;
        element.width = width; element.height = height;
        const context = element.getContext('2d');
        if (context && typeof ImageData !== 'undefined') {
            context.putImageData(new ImageData(bytes, width, height), 0, 0);
        }
    }, [data, channel, opacity, viewRange]);
    if (!data) return <p className="pl-panel-sub">Make a colour field to inspect saved values.</p>;
    const point = (event) => pixelAt(event.clientX, event.clientY,
        event.currentTarget.getBoundingClientRect(), data.metadata, data.preview);
    return <canvas ref={canvas} className="pl-colour-canvas" role="img" tabIndex={0}
        aria-label="Saved colour field. Click or press Enter to sample; drag to record a path. Arrow keys move the keyboard sample."
        onKeyDown={(event) => {
            const [height, width] = data.metadata.shape;
            const moves = { ArrowLeft: [-1, 0], ArrowRight: [1, 0],
                ArrowUp: [0, -1], ArrowDown: [0, 1] };
            if (moves[event.key]) {
                event.preventDefault();
                const [dx, dy] = moves[event.key];
                setCursor(([x, y]) => [Math.max(0, Math.min(width - 1, x + dx)),
                    Math.max(0, Math.min(height - 1, y + dy))]);
            } else if (event.key === 'Enter') { event.preventDefault(); onPoint?.(cursor); }
        }}
        onPointerDown={(event) => {
            event.currentTarget.setPointerCapture?.(event.pointerId);
            trail.current = [point(event)];
        }}
        onPointerMove={(event) => {
            if (!event.buttons || !trail.current.length) return;
            const next = point(event);
            if (trail.current.length < 4096 && String(next) !== String(trail.current.at(-1))) {
                trail.current.push(next);
            }
        }}
        onPointerUp={(event) => {
            const next = point(event);
            if (trail.current.length > 1) onPath?.(trail.current);
            else onPoint?.(next);
            trail.current = [];
        }} />;
}

function ColourPanel({ client, session, source, lab, arm, onArm }) {
    const fields = useMemo(() => lab.ledger.filter((entry) =>
        entry.identity.artifact_kind === 'sample_grid'
        && entry.identity.organ_family === 'colour'), [lab.ledger]);
    const active = fields.find((entry) => entry.identity.artifact_id === lab.activeId)
        || fields.at(-1);
    const fallbackId = fields.at(-1)?.identity.artifact_id;
    const activeId = lab.activeId;
    const setActiveId = lab.setActiveId;
    useEffect(() => {
        if (!activeId && fallbackId) setActiveId(fallbackId);
    }, [activeId, setActiveId, fallbackId]);
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [channel, setChannel] = useState(3);
    const [opacity, setOpacity] = useState(1);
    const [rangeMode, setRangeMode] = useState('fixed');
    const [customLow, setCustomLow] = useState(0);
    const [customHigh, setCustomHigh] = useState(100);
    const [selected, setSelected] = useState(null);
    const [reading, setReading] = useState(null);
    const [otherId, setOtherId] = useState('');
    const [other, setOther] = useState(null);
    const [clusters, setClusters] = useState(4);
    const [samples, setSamples] = useState(128);
    const [seed, setSeed] = useState(0);
    const [rgb, setRgb] = useState({ r: 128, g: 128, b: 128 });
    const [restoredSource, setRestoredSource] = useState(null);
    const artifactId = active?.identity.artifact_id;
    useEffect(() => {
        if (source?.photo_url && source.image_digest === session?.source?.image_digest) {
            setRestoredSource(null); return undefined;
        }
        if (!session?.source?.post_id || !client.openSource) return undefined;
        let live = true;
        client.openSource(session.source.post_id).then(({ source: found }) => {
            if (live && found.image_digest === session.source.image_digest) {
                setRestoredSource(found);
            }
        }).catch((failure) => { if (live) setError(failure.message); });
        return () => { live = false; };
    }, [client, session?.source?.post_id, session?.source?.image_digest,
        source?.photo_url, source?.image_digest]);
    useEffect(() => {
        if (!session?.session_id || !artifactId || !client.fieldPreview) {
            setData(null); return undefined;
        }
        let live = true;
        setData(null); setReading(null); setError('');
        setOtherId(''); setOther(null);
        client.fieldPreview({ session_id: session.session_id, artifact_id: artifactId })
            .then((result) => { if (live) { setData(result); setChannel(
                convention(result).form === 'channels' ? 3 : 0); } })
            .catch((failure) => { if (live) setError(failure.message); });
        return () => { live = false; };
    }, [client, session?.session_id, artifactId]);
    const inspect = async (operation, points) => {
        if (!artifactId) return;
        try {
            setError('');
            const result = await client.consumeField({ session_id: session.session_id,
                artifact_id: artifactId, operation, points });
            setReading(result.derivation);
        } catch (failure) { setError(failure.message); }
    };
    const propose = (operation, parameters = {}) => lab.planDirectly(operation, parameters, []);
    const requestDistance = () => {
        if (!selected) { setError('Which saved field pixel should be the reference? Click the field first.'); return; }
        propose('colour.distance', { x: selected[0], y: selected[1] });
    };
    const meta = convention(data);
    const form = meta.form;
    const run = lab.runs.find((item) => item.run_id === active?.identity.run_id);
    const plan = lab.plans.find((item) => item.plan_id === run?.resolved_plan_id)
        || lab.plans.find((item) => item.plan_id === run?.requested_plan_id);
    const referenceStep = plan?.resolved_steps?.find((item) => item.step_id === active?.identity.step_id);
    const reference = referenceStep?.parameters || null;
    const displaySource = source?.photo_url && source.image_digest === session?.source?.image_digest
        ? source : restoredSource;
    const compatible = fields.filter((entry) => entry.identity.artifact_id !== artifactId
        && entry.measurement?.payload?.manifest?.metadata?.value_convention
        === data?.metadata?.value_convention
        && JSON.stringify(entry.measurement.payload.manifest.metadata.channels)
        === JSON.stringify(data.metadata.channels));
    const fixedRange = form === 'channels' ? CHANNELS[channel]?.slice(1) || [0, 1]
        : form === 'palette-membership' ? [0, Math.max(1, meta.actual_clusters - 1)] : [0, 200];
    const range = rangeMode === 'fixed' ? fixedRange : [customLow, customHigh];
    return <section className="pl-panel pl-colour" aria-label="Colour family">
        <div className="pl-panel-head"><h2 className="pl-panel-title">Colour fields</h2>
            <span className="pl-kicker">Image signal · CIELAB D65</span></div>
        <p className="pl-panel-sub">The original image stays intact. Its EXIF-oriented working copy
            is converted from an embedded ICC profile to sRGB, or assumed sRGB when no profile exists.
            Values describe image colour, not calibrated pigments or reflectance.</p>
        <div className="pl-btnrow">
            <button type="button" className="pl-btn pl-btn--primary" disabled={!!lab.busy}
                onClick={() => propose('colour.channels')}>Make colour field</button>
            <button type="button" className="pl-btn" disabled={!!lab.busy}
                onClick={requestDistance}>Distance from selected sample</button>
            {arm === 'form' ? <button type="button" className="pl-btn"
                onClick={() => onArm('direct')}>Show Direct controls</button> : null}
        </div>
        <div className="pl-colour-parameters">
            <label>Palette groups (1–8)<input type="number" min="1" max="8" value={clusters}
                onChange={(event) => setClusters(Number(event.target.value))} /></label>
            <label>Samples (1–128)<input type="number" min="1" max="128" value={samples}
                onChange={(event) => setSamples(Number(event.target.value))} /></label>
            <label>Seed<input type="number" min="0" max="2147483647" value={seed}
                onChange={(event) => setSeed(Number(event.target.value))} /></label>
            <button type="button" className="pl-btn" disabled={!!lab.busy}
                onClick={() => propose('colour.palette', { clusters, samples, seed })}>
                Make sampled palette</button>
        </div>
        <div className="pl-colour-parameters">
            {['r', 'g', 'b'].map((key) => <label key={key}>sRGB8 {key.toUpperCase()}
                <input type="number" min="0" max="255" value={rgb[key]}
                    onChange={(event) => setRgb({ ...rgb, [key]: Number(event.target.value) })} />
            </label>)}
            <button type="button" className="pl-btn" disabled={!!lab.busy}
                onClick={() => propose('colour.distance_rgb', rgb)}>
                Distance from supplied RGB</button>
        </div>
        <p className="pl-panel-sub">“Show the colour field” is a bounded prompt. “Compare colour
            to the selected sample” needs an explicit clicked reference; choose it here first.</p>
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
        {!fields.length ? <div className="pl-colour-empty"><span aria-hidden="true">◇</span>
            <h3>Colour has not been measured here</h3>
            <p>Choose “Make colour field” to create inspectable saved channels.</p></div> : <>
            <label>Saved colour result <select value={artifactId || ''}
                onChange={(event) => lab.setActiveId(event.target.value)}>
                {fields.map((entry) => <option key={entry.identity.artifact_id}
                    value={entry.identity.artifact_id}>{entry.identity.operation} ·
                    {entry.identity.artifact_id}</option>)}</select></label>
            {!data ? <p className="pl-panel-sub">Reading saved colour values…</p> : <>
                <p className="pl-panel-sub">{meta.working_profile} · source to field stride
                    {' '}{meta.sampling_step} · {data.metadata.shape.join(' × ')} ·
                    {' '}{data.execution_identity}. Measurement hash: <code>{data.measurement_hash}</code></p>
                <div className="pl-colour-controls">
                    {form === 'channels' ? <label>Channel <select value={channel}
                        onChange={(event) => setChannel(Number(event.target.value))}>
                        {CHANNELS.map(([name], index) => <option value={index} key={name}>{name}</option>)}
                    </select></label> : null}
                    <label>Wash opacity <input type="range" min="0" max="1" step="0.05"
                        value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /></label>
                    <label>Display scale <select value={rangeMode}
                        onChange={(event) => setRangeMode(event.target.value)}>
                        <option value="fixed">Fixed disclosed scale</option>
                        <option value="custom">Custom display only</option></select></label>
                    {rangeMode === 'custom' ? <><label>Low<input type="number" value={customLow}
                        onChange={(event) => setCustomLow(Number(event.target.value))} /></label>
                        <label>High<input type="number" value={customHigh}
                            onChange={(event) => setCustomHigh(Number(event.target.value))} /></label></> : null}
                </div>
                <p className="pl-panel-sub">View scale {range[0]}–{range[1]}
                    {form === 'distance' ? ' ΔE76 (Euclidean CIELAB distance)' : ''}.
                    Grey checker cells are invalid, not zero. View settings do not change saved data.</p>
                <div className="pl-colour-pair">
                    {displaySource?.photo_url ? <figure><img src={displaySource.photo_url}
                        alt="Original Lab source" />
                        <figcaption>Original source · {displaySource.image_digest}</figcaption></figure>
                        : <p className="pl-panel-sub">Original source preview is unavailable;
                            saved field values remain inspectable.</p>}
                    <figure><ColourCanvas data={data} channel={channel} opacity={opacity}
                        viewRange={range} onPoint={(point) => { setSelected(point); inspect('point', [point]); }}
                        onPath={(points) => { setSelected(points.at(-1)); inspect('path', points); }} />
                        <figcaption>Saved field preview · click for exact value or drag an explicit
                            profile. Selected field pixel: {selected?.join(', ') || 'none'}.</figcaption></figure>
                </div>
                {form === 'channels' ? <p className="pl-panel-sub">sRGB channels are encoded 0–1;
                    Lab L is 0–100 and a/b are opponent axes, approximately −127–127.
                    Near-neutral chroma (√(a²+b²) &lt; 2) is achromatic.</p> : null}
                {form === 'palette-membership' ? <div className="pl-colour-palette">
                    <p>Deterministic seed {meta.seed}; {meta.actual_samples} of
                        {' '}{meta.population_count} valid field pixels sampled;
                        {' '}{meta.actual_clusters} groups (requested {meta.requested_clusters}).
                        Groups describe sampled colour, not objects or pigments.</p>
                    <ol>{(meta.centres_lab || []).map((centre, index) => <li key={index}>
                        <span className="pl-colour-swatch" aria-hidden="true"
                            style={{ backgroundColor: labSwatch(centre) }} />
                        Group {index} · Lab {centre.map((number) => Number(number).toFixed(1)).join(', ')}
                        {' · '}{meta.population_counts[index]} field cells,
                        {' '}{meta.sample_counts[index]} samples
                    </li>)}</ol>
                    <details><summary>Source-linked sample locations (field x,y,group)</summary>
                        <pre>{JSON.stringify(meta.sample_locations, null, 2)}</pre></details>
                </div> : null}
                {form === 'distance' ? <p className="pl-panel-sub">Reference from the saved
                    resolved plan: {reference ? JSON.stringify(reference) : 'plan unavailable'}.
                    No threshold is part of the measurement.</p> : null}
                <label>Compare compatible saved result
                    <select value={otherId} onChange={async (event) => {
                        const id = event.target.value; setOtherId(id); setOther(null);
                        if (id) {
                            try { setOther(await client.fieldPreview({ session_id: session.session_id,
                                artifact_id: id })); } catch (failure) { setError(failure.message); }
                        }
                    }}><option value="">Choose a result with the same channels and convention</option>
                        {compatible.map((entry) => <option key={entry.identity.artifact_id}
                            value={entry.identity.artifact_id}>{entry.identity.operation} ·
                            {entry.identity.artifact_id}</option>)}</select></label>
                {other ? <><p className="pl-panel-sub">Both views use {range[0]}–{range[1]}
                    on the same channel. Comparison reads full saved numbers.</p>
                    <ColourCanvas data={other} channel={channel} opacity={opacity}
                        viewRange={range} />
                    <button type="button" className="pl-btn" onClick={async () => {
                        try {
                            const result = await client.consumeField({ session_id: session.session_id,
                                artifact_id: artifactId, operation: 'compare', points: [],
                                compare_artifact_id: otherId });
                            setReading(result.derivation);
                        } catch (failure) { setError(failure.message); }
                    }}>Compare saved values</button></> : null}
                {reading ? <div className="pl-field-reading" aria-live="polite"><strong>
                    {reading.form} · {reading.derivation_id}</strong>
                    <pre>{JSON.stringify(reading.measurements.result, null, 2)}</pre></div> : null}
            </>}
        </>}
    </section>;
}

const parameter = (name, description, minimum, maximum) => ({ name, type: 'integer',
    required: true, description, minimum, maximum });
const declared = (key, form_key, label, parameters, prompt_intents = []) => ({
    key, form_key, producer_key: key, label, question: label, summary: label,
    parameters, prompt_intents, adapters: [key], inputs: [],
});

export const SLOT = Object.freeze({ family: 'colour', label: 'Colour', available: true,
    reason: 'Deterministic image-colour fields; not calibrated pigment measurements.',
    forms: [
        { key: 'colour.channels', label: 'Colour channels', quantity: 'sRGB and CIELAB image signal', views: ['channel'] },
        { key: 'colour.palette', label: 'Sampled palette', quantity: 'sampled colour groups', views: ['palette'] },
        { key: 'colour.distance', label: 'Reference colour distance', quantity: 'CIELAB ΔE76', views: ['distance'] },
    ],
    operations: [
        declared('colour.channels', 'colour.channels', 'Make colour field', [],
            ['show the colour field']),
        declared('colour.palette', 'colour.palette', 'Make sampled palette', [
            parameter('clusters', 'Requested groups', 1, 8),
            parameter('samples', 'Requested samples', 1, 128),
            parameter('seed', 'Deterministic seed', 0, 2147483647),
        ]),
        declared('colour.distance', 'colour.distance', 'Distance from selected pixel', [
            parameter('x', 'Selected field-pixel x', 0, 511),
            parameter('y', 'Selected field-pixel y', 0, 511),
        ], ['compare colour to the selected sample']),
        declared('colour.distance_rgb', 'colour.distance', 'Distance from supplied RGB', [
            ...['r', 'g', 'b'].map((key) => parameter(key, `sRGB8 ${key}`, 0, 255)),
        ]),
    ],
    views: ['channel', 'palette', 'distance'],
    promptIntents: ['show the colour field', 'compare colour to the selected sample'],
    Panel: ColourPanel });
