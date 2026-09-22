import React, { useEffect, useMemo, useState } from 'react';
import { FieldCanvas } from '../fields/FieldInspector';

const forms = [
    { key: 'illumination.image_luminance', label: 'Image luminance',
        quantity: 'image-relative linear-light Y', views: ['grayscale', 'false_colour', 'contours'] },
    { key: 'illumination.estimated_shading', label: 'Estimated shading',
        quantity: 'model-estimated relative grayscale shading', views: ['grayscale', 'false_colour', 'contours'] },
];
const operations = forms.map((form, index) => {
    const producer = index ? 'illumination.shading_producer' : 'illumination.luminance_producer';
    return { key: form.key, label: form.label, form_key: form.key, producer_key: producer,
        question: index ? 'What shading does Intrinsic estimate?' : 'What linear-light brightness is in this image?',
        summary: form.quantity, adapters: [producer], inputs: [],
        parameters: [{ name: 'alpha_min', type: 'integer', required: false,
            minimum: 1, maximum: 255,
            description: 'Pixels below this source alpha are unknown. Default 1.' }] };
});

function Contours({ data, levels }) {
    const [height, width] = data.preview.shape;
    const values = data.preview.values;
    const valid = data.preview.valid;
    const marks = [];
    // Preview contours only: bound the SVG on large source images.
    const stride = Math.max(1, Math.ceil(Math.sqrt(width * height / 16384)));
    for (let y = 0; y < height - stride; y += stride) {
        for (let x = 0; x < width - stride; x += stride) {
            const i = y * width + x;
            let complete = true;
            for (let dy = 0; dy <= stride && complete; dy += 1) {
                for (let dx = 0; dx <= stride; dx += 1) {
                    if (!valid[i + dy * width + dx]) { complete = false; break; }
                }
            }
            if (!complete) continue;
            levels.forEach((level) => {
                if ((values[i] < level) !== (values[i + stride] < level)) {
                    marks.push(<path key={`${i}-h-${level}`} d={`M ${x + stride / 2} ${y} v ${stride}`} />);
                }
                if ((values[i] < level) !== (values[i + stride * width] < level)) {
                    marks.push(<path key={`${i}-v-${level}`} d={`M ${x} ${y + stride / 2} h ${stride}`} />);
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
        setData(null); setProfile(null); setError('');
        if (!id) return;
        let active = true;
        client.fieldPreview({ session_id: session.session_id, artifact_id: id })
            .then((result) => {
                if (!active) return;
                const values = result.preview.values.filter((value, index) =>
                    result.preview.valid[index] && Number.isFinite(value)).sort((a, b) => a - b);
                const ceiling = values[Math.floor((values.length - 1) * .98)] || 1;
                setLow(0); setHigh(Math.max(.01, Number(ceiling.toPrecision(3))));
                setData(result);
            })
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
    const profileSegments = [];
    let segment = [];
    samples.forEach((s, i) => {
        if (s.valid) segment.push(`${(i / Math.max(1, samples.length - 1)) * 100},${100 - (s.values[0] - low) / (high - low || 1) * 100}`);
        else if (segment.length) { profileSegments.push(segment); segment = []; }
    });
    if (segment.length) profileSegments.push(segment);
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
                <p className="pl-panel-sub">Display limits {low}–{high} in this form’s relative units; upper limit starts at the saved preview’s 98th percentile. Equal ranges do not calibrate luminance and shading to each other.</p>
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
                        {profileSegments.map((points, index) => <polyline key={index} points={points.join(' ')}
                            fill="none" stroke="currentColor" strokeWidth="1" />)}
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
