import React, { useState } from 'react';
import fixture from './fixtures/foundation-field.v1.json';
import { FieldCanvas } from './FieldInspector';

export default function FieldFixtureDemo() {
    const [view, setView] = useState('colour');
    const [point, setPoint] = useState(null);
    const value = point ? fixture.preview.values[point[1] * 3 + point[0]] : null;
    const valid = point ? fixture.preview.valid[point[1] * 3 + point[0]] : null;
    return <details className="pl-panel pl-fixture-demo" data-execution-identity="FIXTURE">
        <summary>FIXTURE-only field foundation demo</summary>
        <p className="pl-panel-sub">Synthetic 3 × 2 scalar values. No family producer or model
            ran. This checks two displays and point reading of the same saved numbers.</p>
        <p className="pl-panel-sub">Hash: <code>{fixture.measurement_hash}</code></p>
        <label>Display view <select value={view} onChange={(event) => setView(event.target.value)}>
            <option value="colour">Colour</option><option value="grayscale">Grayscale</option>
        </select></label>
        <FieldCanvas data={fixture} scale={[0, 1]} view={view} onPoint={setPoint} />
        <p aria-live="polite">{point ? `${point.join(', ')}: ${valid ? value : 'invalid / unknown'}`
            : 'Click a field cell to inspect its saved value.'}</p>
    </details>;
}
