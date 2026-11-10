import React, { useState } from 'react';
import { FieldCanvas } from '../fields/FieldInspector';
import { normalGlyphs, readPreviewNormal, validateNormalPreview } from './surfaceFormVisual';
import './surface_form.css';

/** Read-only component. Its presence does not register a live producer/form. */
export default function SurfaceNormalPreview({ data }) {
    const [point, setPoint] = useState([0, 0]);
    const [reading, setReading] = useState(null);
    const [error, setError] = useState(null);
    let validData;
    try { validData = validateNormalPreview(data); } catch (failure) {
        return <p className="pl-error" role="alert">{failure.message}</p>;
    }
    const glyphs = normalGlyphs(validData);
    const [height, width] = validData.preview.shape;
    const inspect = (cell) => {
        try { setReading({ data: validData, ...readPreviewNormal(validData, ...cell) });
            setPoint(cell); setError(null); }
        catch (failure) { setReading(null); setError({ data: validData, message: failure.message }); }
    };
    return <section className="pl-field pl-normal-preview" aria-label="Read-only normal field preview">
        <h3 className="pl-panel-title">{data.execution_identity || 'UNVERIFIED'} · surface direction encoding</h3>
        <p className="pl-panel-sub">{data.execution_identity === 'FIXTURE'
            ? 'Analytical vectors only: not a model estimate or evidence of live producer quality.'
            : 'Saved vector display only; this reader does not run or admit a normal model.'}</p>
        <p className="pl-panel-sub">Fixed component scale −1 to +1. Red = camera X (right),
            green = camera Y (down), blue = camera Z (away from camera); right-handed.
            Midtone encodes zero. These colours encode directions, not the object’s colour.
            Grey cells are unknown, not zero vectors. No camera calibration is implied.</p>
        <div className="pl-field-pair">
            <figure><FieldCanvas data={validData} scale={[-1, 1]} view="colour" onPoint={inspect} />
                <figcaption>Normal colour · the same stored vectors</figcaption></figure>
            <figure><svg className="pl-normal-glyphs" viewBox={`0 0 ${width} ${height}`}
                role="img" aria-label="Camera normal XY projections; Z is encoded by colour, not arrow length">
                {glyphs.map((glyph) => <g key={`${glyph.fieldX},${glyph.fieldY}`}>
                    <title>{`${glyph.fieldX},${glyph.fieldY}: [${glyph.vector.join(', ')}]`}</title>
                    <line x1={glyph.x} y1={glyph.y} x2={glyph.endX} y2={glyph.endY}
                        className="pl-normal-shaft" />
                    <circle cx={glyph.endX} cy={glyph.endY} r="0.065"
                        fill={`rgb(${glyph.colour.join(',')})`} className="pl-normal-tip" />
                </g>)}
            </svg><figcaption>Sparse directed XY projections; coloured endpoint = tip.
                A camera-facing normal has no XY length. Z sign is visible in blue.</figcaption></figure>
        </div>
        <p className="pl-panel-sub">Sample locations use image pixels, not camera coordinates.
            Preview stride: {data.preview.stride} field pixels. No interpolation or extra detail is created.</p>
        <div className="pl-field-controls">
            {['x', 'y'].map((axis, index) => <label key={axis}>Field {axis}
                <input type="number" min="0" max={data.metadata.shape[1 - index] - 1}
                    step={data.preview.stride} value={point[index]}
                    onChange={(event) => setPoint(point.map((value, i) => i === index
                        ? Number(event.target.value) : value))} />
            </label>)}
            <button type="button" className="pl-btn" onClick={() => inspect(point)}>
                Read preview vector</button>
        </div>
        {error?.data === validData ? <p className="pl-error" role="alert">{error.message}</p> : null}
        {reading?.data === validData ? <p className="pl-panel-sub" aria-live="polite">
            {reading.x},{reading.y}: {reading.valid
                ? `[${reading.vector.join(', ')}] · directed unit camera normal`
                : 'invalid / unknown; no direction'}</p> : null}
        <p className="pl-panel-sub">Angular change compares directions in degrees; it is not physical
            curvature. No profile is persisted by this read-only preview.</p>
    </section>;
}
