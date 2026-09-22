import React, { useEffect, useMemo, useState } from 'react';
import { FieldCanvas } from '../fields/FieldInspector';

const forms = [
    { key: 'illumination.image_luminance', label: 'Image luminance',
        quantity: 'image-relative linear-light Y', views: ['grayscale', 'false_colour', 'contours'] },
    { key: 'illumination.estimated_shading', label: 'Estimated shading',
        quantity: 'model-estimated relative grayscale shading', views: ['grayscale', 'false_colour', 'contours'] },
];
const operations = [
    { key: forms[0].key, label: forms[0].label, form_key: forms[0].key,
        producer_key: 'illumination.luminance_producer', parameters: { alpha_min: { type: 'integer' } } },
    { key: forms[1].key, label: forms[1].label, form_key: forms[1].key,
        producer_key: 'illumination.shading_producer', parameters: { alpha_min: { type: 'integer' } } },
];

function Contours({ data, levels }) {
    const [height, width] = data.preview.shape;
    const values = data.preview.values;
    const valid = data.preview.valid;
    const marks = [];
    for (let y = 0; y < height - 1; y += 1) {
        for (let x = 0; x < width - 1; x += 1) {
            const i = y * width + x;
            if (!valid[i] || !valid[i + 1] || !valid[i + width]) continue;
            levels.forEach((level) => {
                if ((values[i] < level) !== (values[i + 1] < level)) {
                    marks.push(<path key={`${i}-h-${level}`} d={`M ${x + .5} ${y} v 1`} />);
                }
                if ((values[i] < level) !== (values[i + width] < level)) {
                    marks.push(<path key={`${i}-v-${level}`} d={`M ${x} ${y + .5} h 1`} />);
                }
            });
        }
    }
    return <svg className="pl-field-canvas" viewBox={`0 0 ${width} ${height}`}
        role="img" aria-label={`Contours at ${levels.join(', ')} in saved relative units`}>
        <g fill="none" stroke="currentColor" strokeWidth="0.12">{marks}</g>
    </svg>;
}

function Panel({ client, session, lab, source }) {
    const artifacts = useMemo(() => lab.ledger.filter((item) =>
        item.identity?.organ_family === 'illumination'
            && item.identity?.artifact_kind === 'sample_grid'), [lab.ledger]);
    const [selectedId, setSelectedId] = useState('');
    const chosen = artifacts.find((item) => item.identity.artifact_id === selectedId)
        || artifacts.at(-1);
    const [data, setData] = useState(null);
    const [view, setView] = useState('grayscale');
    const [low, setLow] = useState(0);
    const [high, setHigh] = useState(1);
    const [path, setPath] = useState('');
    const [profile, setProfile] = useState(null);
    const [error, setError] = useState('');
    const id = chosen?.identity.artifact_id;
    useEffect(() => {
        if (!id) { setData(null); return; }
        let active = true;
        client.fieldPreview({ session_id: session.session_id, artifact_id: id })
            .then((result) => { if (active) setData(result); })
            .catch((failure) => { if (active) setError(failure.message); });
        return () => { active = false; };
    }, [client, session.session_id, id]);
    const quantity = chosen?.measurement?.payload?.form_key;
    const isShading = quantity === forms[1].key;
    const samplePath = async () => {
        try {
            const points = path.split(';').map((pair) => pair.trim().split(',').map(Number));
            if (points.some((point) => point.length !== 2 || point.some((n) => !Number.isInteger(n)))) {
                throw new Error('Use integer image coordinates: x,y; x,y');
            }
            setError('');
            const result = await client.consumeField({ session_id: session.session_id,
                artifact_id: id, operation: 'path', points });
            setProfile(result.derivation);
        } catch (failure) { setError(failure.message); }
    };
    const samples = profile?.measurements?.result || [];
    const validSamples = samples.filter((s) => s.valid).map((s) => s.values[0]);
    const profilePoints = samples.map((s, i) => s.valid
        ? `${(i / Math.max(1, samples.length - 1)) * 100},${100 - (s.values[0] - low) / (high - low || 1) * 100}`
        : null).filter(Boolean).join(' ');
    return <section className="pl-panel" aria-label="Illumination forms">
        <h2 className="pl-panel-title">Two different quantities</h2>
        <div className="pl-field-pair">
            <div><h3>Image luminance</h3><p className="pl-panel-sub">Linear-light brightness computed from the prepared sRGB image. Encoded RGB brightness is different. This operation makes zero model calls.</p></div>
            <div><h3>Estimated shading</h3><p className="pl-panel-sub">Intrinsic paper_weights grayscale model estimate. Relative scale, no calibrated physical units. A model failure cannot become luminance.</p></div>
        </div>
        <p className="pl-panel-sub">Choose the matching Direct control, or use the exact prompt “show image brightness” / “estimate shading”. Review its proposed operation before Run.</p>
        {artifacts.length ? <>
            <label>Saved form <select value={id || ''} onChange={(event) => { setSelectedId(event.target.value); setProfile(null); }}>
                {artifacts.map((item) => <option key={item.identity.artifact_id} value={item.identity.artifact_id}>
                    {item.measurement.payload.form_key} · {item.identity.artifact_id}</option>)}
            </select></label>
            {data ? <>
                <p className="pl-panel-sub">{isShading ? 'Estimated shading' : 'Image luminance'} · {data.metadata.shape.join(' × ')} · {data.metadata.value_convention}</p>
                <p className="pl-panel-sub">Measurement {data.measurement_hash}. Views and display range leave this saved record intact.</p>
                <div className="pl-field-controls">
                    <label>View <select value={view} onChange={(event) => setView(event.target.value)}>
                        <option value="grayscale">Grayscale</option><option value="colour">False colour</option><option value="contours">Contours</option>
                    </select></label>
                    <label>Display minimum <input type="number" value={low} onChange={(e) => setLow(Number(e.target.value))} /></label>
                    <label>Display maximum <input type="number" value={high} onChange={(e) => setHigh(Number(e.target.value))} /></label>
                </div>
                <p className="pl-panel-sub">Fixed display limits {low}–{high} in this form’s relative units. Equal ranges do not calibrate luminance and shading to each other.</p>
                <div className="pl-field-pair">
                    {source?.photo_url ? <figure><img src={source.photo_url} alt="Selected source" /><figcaption>Source image</figcaption></figure> : null}
                    <figure>{view === 'contours'
                        ? <Contours data={data} levels={[low + (high - low) * .25, low + (high - low) * .5, low + (high - low) * .75]} />
                        : <FieldCanvas data={data} scale={[low, high]} view={view} />}
                    <figcaption>{view === 'contours' ? 'Contours at 25%, 50%, 75% of declared display interval' : `${view} view of saved field`}</figcaption></figure>
                </div>
                <label>Sample profile: x,y; x,y <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="0,0; 20,10" /></label>
                <button type="button" className="pl-btn" disabled={!path.trim()} onClick={samplePath}>Save profile from field</button>
                {profile ? <div className="pl-field-reading"><strong>{quantity} · {profile.derivation_id}</strong>
                    <p>{validSamples.length} valid of {samples.length} samples. The path cites saved artifact {id}.</p>
                    <svg className="pl-field-canvas" viewBox="0 0 100 100" role="img" aria-label="Saved numeric profile">
                        <polyline points={profilePoints} fill="none" stroke="currentColor" strokeWidth="1" />
                    </svg><details><summary>Profile values</summary><pre>{JSON.stringify(samples, null, 2)}</pre></details></div> : null}
            </> : <p className="pl-panel-sub">Reading saved field…</p>}
        </> : <p className="pl-panel-sub">No illumination form saved yet. Choose one of the two operations below.</p>}
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
    </section>;
}

export const SLOT = Object.freeze({ family: 'illumination', label: 'Illumination', available: true,
    reason: 'Luminance is ready; shading requires the pinned Intrinsic checkpoint at run time.',
    forms, operations, views: ['grayscale', 'false_colour', 'contours'],
    promptIntents: ['show image brightness', 'estimate shading'], Panel });
