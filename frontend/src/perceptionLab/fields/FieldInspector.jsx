import React, { useEffect, useRef, useState } from 'react';
import { fieldRgb, pixelAt, previewPixels } from './fieldVisual';
import './fieldInspector.css';

export function FieldCanvas({ data, scale, view, onPoint }) {
    const canvas = useRef(null);
    useEffect(() => {
        if (!data || !canvas.current) return;
        const { width, height, pixels } = previewPixels(data, scale, view);
        const element = canvas.current;
        element.width = width; element.height = height;
        const context = element.getContext('2d');
        if (context && typeof ImageData !== 'undefined') {
            context.putImageData(new ImageData(pixels, width, height), 0, 0);
        }
    }, [data, scale, view]);
    if (!data) return <p className="pl-panel-sub">No saved field is selected.</p>;
    const [height, width, channels] = data.preview.shape;
    if (height * width <= 256) {
        return <svg className="pl-field-canvas" viewBox={`0 0 ${width} ${height}`}
            role="img" aria-label={`${data.metadata.kind} field. Click to sample its saved values.`}
            onClick={(event) => onPoint?.(pixelAt(event.clientX, event.clientY,
                event.currentTarget.getBoundingClientRect(), data.metadata, data.preview))}>
            {data.preview.valid.map((valid, index) => {
                const [red, green, blue] = fieldRgb(data.metadata.kind,
                    data.preview.values.slice(index * channels, (index + 1) * channels),
                    valid, scale, view);
                return <rect key={index} x={index % width} y={Math.floor(index / width)}
                    width="1" height="1" fill={`rgb(${red}, ${green}, ${blue})`} />;
            })}
        </svg>;
    }
    return <canvas ref={canvas} className="pl-field-canvas" role="img"
        aria-label={`${data.metadata.kind} field. Click to sample its saved values.`}
        onClick={(event) => onPoint?.(pixelAt(event.clientX, event.clientY,
            event.currentTarget.getBoundingClientRect(), data.metadata, data.preview))} />;
}

export default function FieldInspector({ client, sessionId, artifact, fields = [], source = null }) {
    const [data, setData] = useState(null);
    const [other, setOther] = useState(null);
    const [otherId, setOtherId] = useState('');
    const [view, setView] = useState('colour');
    const [low, setLow] = useState(0);
    const [high, setHigh] = useState(1);
    const [sample, setSample] = useState(null);
    const [path, setPath] = useState('');
    const [error, setError] = useState('');
    const id = artifact?.identity?.artifact_id;
    useEffect(() => {
        if (!id || !client.fieldPreview) return;
        let active = true;
        setData(null); setError(''); setOther(null); setOtherId('');
        client.fieldPreview({ session_id: sessionId, artifact_id: id })
            .then((found) => { if (active) setData(found); })
            .catch((failure) => { if (active) setError(failure.message); });
        return () => { active = false; };
    }, [client, sessionId, id]);
    const scale = [low, high];
    const consume = async (operation, points = [], compareId = null) => {
        try {
            setError('');
            const result = await client.consumeField({ session_id: sessionId, artifact_id: id,
                operation, points, compare_artifact_id: compareId });
            setSample(result.derivation);
        } catch (failure) { setError(failure.message); }
    };
    const parsePath = () => path.split(';').map((pair) => pair.trim().split(',').map(Number));
    return <section className="pl-panel pl-field" aria-label="Saved field inspection">
        <h2 className="pl-panel-title">Saved field</h2>
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
        {!data ? <p className="pl-panel-sub">{error || 'Reading saved numbers…'}</p> : <>
            <p className="pl-panel-sub">{data.execution_identity} · {artifact.provenance.producer}
                {' · '}{data.metadata.kind} · {data.metadata.shape.join(' × ')}
                {' · '}{data.metadata.frame}</p>
            <p className="pl-panel-sub">Measurement hash: <code>{data.measurement_hash}</code></p>
            <p className="pl-panel-sub">Display controls only. The saved values and hash stay fixed.
                Change measurement parameters in the family panel to create another result.</p>
            <div className="pl-field-controls">
                <label>View <select value={view} onChange={(event) => setView(event.target.value)}>
                    <option value="colour">Colour / direction</option>
                    <option value="grayscale">Grayscale</option>
                    <option value="magnitude">Magnitude</option>
                </select></label>
                <label>Scale minimum <input type="number" value={low}
                    onChange={(event) => setLow(Number(event.target.value))} /></label>
                <label>Scale maximum <input type="number" value={high}
                    onChange={(event) => setHigh(Number(event.target.value))} /></label>
            </div>
            <p className="pl-panel-sub">Fixed display scale for both views: {low} to {high}
                {' '}{data.metadata.units}. Grey checker cells are invalid, not zero.</p>
            <div className="pl-field-pair">
                {source?.photo_url ? <figure><img src={source.photo_url} alt="Lab source" />
                    <figcaption>Source image · {source.image_digest}</figcaption></figure> : null}
                <figure><FieldCanvas data={data} scale={scale} view={view}
                    onPoint={(point) => consume('point', [point])} />
                    <figcaption>Saved field display · click a cell to read exact values</figcaption></figure>
            </div>
            {data.metadata.kind === 'normal_camera_3d' ? <p className="pl-panel-sub">
                Normal legend: red = camera X, green = camera Y, blue = camera Z;
                midtone means zero, bright means positive. Camera axes are not image XY axes.
            </p> : null}
            <p className="pl-panel-sub">Channels: {data.metadata.channels.map((channel) =>
                `${channel.name} (${channel.quantity}, ${channel.unit})`).join(' · ')}</p>
            <label>Explicit sample path or ROI cells, x,y; x,y
                <input value={path} onChange={(event) => setPath(event.target.value)}
                    placeholder="0,0; 1,0; 2,0" />
            </label>
            <div className="pl-field-controls">
                <button type="button" className="pl-btn" disabled={!path.trim()}
                    onClick={() => consume('path', parsePath())}>Sample path</button>
                <button type="button" className="pl-btn" disabled={!path.trim()}
                    onClick={() => consume('roi', parsePath())}>Summarize ROI cells</button>
            </div>
            <label>Compare saved field
                <select value={otherId} onChange={async (event) => {
                    const next = event.target.value; setOtherId(next); setOther(null);
                    if (next) {
                        try { setOther(await client.fieldPreview({ session_id: sessionId,
                            artifact_id: next })); } catch (failure) { setError(failure.message); }
                    }
                }}>
                    <option value="">Choose a compatible saved field</option>
                    {fields.filter((entry) => entry.identity.artifact_id !== id).map((entry) =>
                        <option value={entry.identity.artifact_id} key={entry.identity.artifact_id}>
                            {entry.identity.artifact_id}</option>)}
                </select>
            </label>
            {other ? <><FieldCanvas data={other} scale={scale} view={view} />
                <button type="button" className="pl-btn" onClick={() => consume('compare', [], otherId)}>
                    Compare saved values</button></> : null}
            {sample ? <div aria-live="polite" className="pl-field-reading">
                <strong>{sample.form} · {sample.derivation_id}</strong>
                <pre>{JSON.stringify(sample.measurements.result, null, 2)}</pre>
            </div> : null}
            <details><summary>Raw field metadata and reference</summary>
                <pre>{JSON.stringify(artifact.measurement.payload, null, 2)}</pre>
            </details>
        </>}
    </section>;
}
