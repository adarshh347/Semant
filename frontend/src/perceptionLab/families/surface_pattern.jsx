import React, { useEffect, useMemo, useState } from 'react';
import { FieldCanvas } from '../fields/FieldInspector';
import { patchCells, descriptor, similarity } from './patternConsumer';
import './surface_pattern.css';

const channels = [6, 12].flatMap((scale) => [0, 45, 90, 135]
    .map((angle) => `lambda${scale}_theta${angle}`));

function channelData(data, name) {
    const index = data.metadata.channels.findIndex((entry) => entry.name === name);
    if (index < 0) return null;
    const [height, width, count] = data.preview.shape;
    return { metadata: { ...data.metadata, kind: 'scalar', shape: [height, width, 1],
        channels: [data.metadata.channels[index]] },
    preview: { ...data.preview, shape: [height, width, 1],
        values: Array.from({ length: height * width }, (_, i) => data.preview.values[i * count + index]) } };
}

function Panel({ client, session, source, lab }) {
    const artifact = [...(lab.ledger || [])].reverse().find((item) =>
        item.identity?.organ_family === 'surface_pattern' && item.measurement?.payload?.form_key
        === 'surface_pattern.response_bank');
    const [data, setData] = useState(null);
    const [error, setError] = useState('');
    const [first, setFirst] = useState(channels[0]);
    const [second, setSecond] = useState(channels[4]);
    const [patch, setPatch] = useState({ x: 0, y: 0, width: 8, height: 8 });
    const [reference, setReference] = useState(null);
    const [comparison, setComparison] = useState(null);
    const [saved, setSaved] = useState(null);
    const artifactId = artifact?.identity?.artifact_id;
    useEffect(() => {
        if (!artifactId) { setData(null); return; }
        let active = true;
        client.fieldPreview({ session_id: session.session_id,
            artifact_id: artifactId }).then((result) => {
            if (active) { setData(result); setError(''); setReference(null); setComparison(null); }
        }).catch((failure) => { if (active) setError(failure.message); });
        return () => { active = false; };
    }, [client, session.session_id, artifactId]);
    const firstMap = useMemo(() => data && channelData(data, first), [data, first]);
    const secondMap = useMemo(() => data && channelData(data, second), [data, second]);
    const makeReference = async () => {
        try {
            const points = patchCells(patch.x, patch.y, patch.width, patch.height, data.preview.shape);
            const result = descriptor(data, points);
            const persisted = await client.consumeField({ session_id: session.session_id,
                artifact_id: artifact.identity.artifact_id, operation: 'roi', points });
            setSaved(persisted.derivation);
            setReference({ ...result, bounds: { ...patch } }); setComparison(null); setError('');
        } catch (failure) { setError(failure.message); }
    };
    return <section className="pl-panel" aria-label="Surface pattern instrument">
        <h2 className="pl-panel-title">Inspect pattern at different scales</h2>
        <p className="pl-panel-sub">Run the CPU pattern operation in Direct. A response measures
            how strongly a named filter responds here. It does not identify material or measure
            physical roughness. Wavelengths are 6 and 12 pixels on the resized working grid.</p>
        {error ? <p className="pl-error" role="alert">{error}</p> : null}
        {!data ? <p className="pl-panel-sub">No saved pattern field yet. Choose the source and run
            “Inspect pattern at different scales.”</p> : <>
            <p className="pl-panel-sub">Saved field {artifact.identity.artifact_id} · {data.measurement_hash}
                {' · '}{data.metadata.shape.join(' × ')} · CPU, zero model calls.
                Source to field resampling is recorded in the raw field metadata.</p>
            <div className="pl-field-controls">
                {[[first, setFirst], [second, setSecond]].map(([value, setter], index) =>
                    <label key={index}>View {index + 1} channel <select value={value}
                        onChange={(event) => setter(event.target.value)}>
                        {data.metadata.channels.map((item) => <option key={item.name} value={item.name}>
                            {item.name}</option>)}</select></label>)}
            </div>
            <p className="pl-panel-sub">Both maps use fixed response range 0–0.1; clipping is display only.
                Angle names describe filter orientation. The field cannot resolve detail smaller than its grid.</p>
            <div className="pl-field-pair">
                {source?.photo_url ? <figure><img src={source.photo_url} alt="Selected source" />
                    <figcaption>Source image</figcaption></figure> : null}
                {firstMap ? <figure><div className="pl-pattern-map">
                    <FieldCanvas data={firstMap} scale={[0, .1]} view="grayscale" />
                    {reference ? <span className="pl-pattern-support" aria-label="Reference patch support"
                        style={{ left: `${reference.bounds.x / data.preview.shape[1] * 100}%`,
                            top: `${reference.bounds.y / data.preview.shape[0] * 100}%`,
                            width: `${reference.bounds.width / data.preview.shape[1] * 100}%`,
                            height: `${reference.bounds.height / data.preview.shape[0] * 100}%` }} /> : null}
                    </div><figcaption>{first} · response strength</figcaption></figure> : null}
                {secondMap ? <figure><FieldCanvas data={secondMap} scale={[0, .1]} view="grayscale" />
                    <figcaption>{second} · response strength</figcaption></figure> : null}
            </div>
            <h3 className="pl-panel-title">Compare pattern to a selected patch</h3>
            <p className="pl-panel-sub">Choose exact field cells. The reference descriptor is the
                mean of each named channel over the valid support. Comparison uses cosine similarity
                of those same channels in same-sized local patches.</p>
            <div className="pl-field-controls">{['x', 'y', 'width', 'height'].map((key) =>
                <label key={key}>{key} <input type="number" min={key === 'x' || key === 'y' ? 0 : 1}
                    value={patch[key]} onChange={(event) => setPatch({ ...patch,
                        [key]: Number(event.target.value) })} /></label>)}</div>
            <button className="pl-btn" type="button" onClick={makeReference}>Save patch profile</button>
            {reference ? <><p className="pl-panel-sub pl-pattern-profile">Reference: {reference.support.length} cells;
                saved ROI derivation {saved?.derivation_id}. Channel means: {reference.means.map(
                    (value, i) => `${reference.channels[i].name} ${value.toFixed(5)}`).join(' · ')}</p>
                <button className="pl-btn" type="button" onClick={() => {
                    try { setComparison(similarity(data, reference, reference.bounds.width, reference.bounds.height));
                        setError(''); } catch (failure) { setError(failure.message); }
                }}>Compare saved field to patch</button></> : null}
            {comparison ? <figure><FieldCanvas data={{ metadata: { ...data.metadata,
                kind: 'scalar', shape: comparison.shape }, preview: comparison }}
                scale={[0, 1]} view="grayscale" /><figcaption>Preview comparison · cosine 0–1;
                spatial result is not yet persisted by the shared consumer API</figcaption></figure> : null}
        </>}
    </section>;
}

export const SLOT = Object.freeze({ family: 'surface_pattern', label: 'Surface pattern',
    available: true, reason: 'CPU Gabor response bank available',
    forms: [{ key: 'surface_pattern.response_bank', label: 'Multiscale pattern response',
        quantity: 'local_gabor_response_rms', views: ['selected_scale', 'paired_scales', 'profile'] }],
    operations: [{ key: 'surface_pattern.inspect_scales', label: 'Inspect pattern at different scales',
        form_key: 'surface_pattern.response_bank', producer_key: 'surface_pattern.cpu_gabor',
        question: 'Where do named scale filters respond in this image?',
        summary: 'Measure an encoded-luma Gabor response bank.',
        adapters: ['surface_pattern.cpu_gabor'], inputs: [], produces: ['sample_grid'],
        requires_confirmation: true,
        parameters: [{ name: 'scale_set', type: 'enum', required: false,
            enum: ['fine_and_coarse', 'fine', 'coarse'],
            description: 'Choose 6-pixel, 12-pixel, or both working-grid wavelengths.' }],
        prompt_intents: ['show texture at the selected scale'] }],
    views: ['selected_scale', 'paired_scales', 'profile'],
    promptIntents: ['show texture at the selected scale'], Panel });
