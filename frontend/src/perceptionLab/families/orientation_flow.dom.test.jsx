import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { SLOT } from './orientation_flow';

let root; let container;
beforeEach(() => {
    container = document.createElement('div'); document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
const click = async (element) => act(async () => element.dispatchEvent(new MouseEvent('click', { bubbles: true })));
const button = (label) => [...container.querySelectorAll('button')].find((element) => element.textContent === label);
const select = (label) => [...container.querySelectorAll('label')].find((element) => element.textContent.startsWith(label))?.querySelector('select');
const data = { metadata: { kind: 'axial_orientation_2d', shape: [4, 8, 2],
    value_convention: JSON.stringify({ form: 'tangent', source_working_size: [800, 400] }) },
preview: { shape: [4, 8, 2], stride: 1, values: Array.from({ length: 32 }, () => [1, 0]).flat(), valid: Array(32).fill(true) },
measurement_hash: 'sha256:saved-numbers', execution_identity: 'LIVE' };
const artifact = { identity: { artifact_id: 'art_orientation', organ_family: 'orientation_flow',
    artifact_kind: 'sample_grid', operation: 'orientation_flow.tangent' },
measurement: { payload: { form_key: 'orientation_flow.tangent' } }, provenance: { producer: 'structure-tensor-tangent-v1' } };

it('shows an actionable empty state and uses the normal planning seam', async () => {
    const lab = { ledger: [], planDirectly: vi.fn() };
    await act(async () => root.render(<SLOT.Panel client={{}} session={{ session_id: 'labs_test' }} lab={lab} />));
    expect(container.textContent).toContain('No saved direction field yet');
    await click(button('Show local orientation'));
    expect(lab.planDirectly).toHaveBeenCalledWith('orientation_flow.tangent',
        { derivative_sigma: 1, integration_sigma: 3, min_coherence: .15 }, []);
});

it('changes views without production and persists exact selected-point trace settings', async () => {
    const client = { fieldPreview: vi.fn(async () => data), derivations: vi.fn(async () => ({ derivations: [] })),
        consumeField: vi.fn(async ({ operation, points, parameters }) => ({ derivation: {
            derivation_id: 'der_saved', form: `field.${operation}`, duration_ms: 1,
            measurements: { result: operation === 'point' ? { x: 0, y: 0, valid: true, values: [1, 0] }
                : { seeds: points, parameters, paths: [{ seed: points[0], direction_sign: 1,
                    points: [[0, 0], [1, 0]], stop_point: [1, 0], steps: 2, length_field_pixels: 1, stop_reason: 'max_length' }] } } } })) };
    const lab = { ledger: [artifact], runs: [], planDirectly: vi.fn() };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 'labs_test' }} lab={lab} />));
    expect(button('Follow the field from selected point').disabled).toBe(true);
    await click(button('Select and sample point'));
    expect(container.textContent).toContain('tangent 0.00°; coherence 1.0000');
    await click(button('Follow the field from selected point'));
    expect(client.consumeField).toHaveBeenLastCalledWith({ session_id: 'labs_test', artifact_id: 'art_orientation',
        operation: 'orientation_flow.trace', points: [[0, 0]], parameters: { step_size: .5, max_steps: 512,
            max_length: 128, min_coherence: .15, max_turn_degrees: 60, directions: 'both' } });
    expect(container.querySelectorAll('polyline')).toHaveLength(1);
    expect(container.textContent).toContain('stopped: max length');
    await act(async () => { const element = select('Saved-field view'); element.value = 'coherence_wash';
        element.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.textContent).toContain('sha256:saved-numbers');
    expect(lab.planDirectly).not.toHaveBeenCalled();
});

it('reopens a saved trace from derivations without calling the producer', async () => {
    const trace = { derivation_id: 'der_reopened', form: 'field.orientation_flow.trace', input_artifact_ids: ['art_orientation'],
        measurements: { result: { seeds: [[2, 1]], paths: [{ seed: [2, 1], points: [[2, 1]], stop_point: [2, 1],
            direction_sign: 1, steps: 0, length_field_pixels: 0, stop_reason: 'invalid_support' }] } } };
    const client = { fieldPreview: vi.fn(async () => data), derivations: vi.fn(async () => ({ derivations: [trace] })) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 'labs_test' }}
        lab={{ ledger: [artifact] }} />));
    await act(async () => { const element = select('Reopen saved trace'); element.value = 'der_reopened';
        element.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.textContent).toContain('stopped: invalid support');
    expect(container.querySelector('polyline').getAttribute('points')).toBe('2,1');
    expect([...container.querySelectorAll('label')].find((element) =>
        element.textContent === 'Seed x').querySelector('input').value).toBe('2');
    expect(client.fieldPreview).toHaveBeenCalledTimes(1);
});

it('does not attach a late point reading to a different saved field', async () => {
    let finish;
    const second = { ...artifact, identity: { ...artifact.identity, artifact_id: 'art_second' } };
    const client = { fieldPreview: vi.fn(async () => data),
        consumeField: vi.fn(() => new Promise((resolve) => { finish = resolve; })) };
    const render = (activeId) => root.render(<SLOT.Panel client={client} session={{ session_id: 'labs_test' }}
        lab={{ ledger: [artifact, second], activeId }} />);
    await act(async () => render('art_orientation'));
    await click(button('Select and sample point'));
    expect(container.textContent).toContain('Reading saved numerical data…');
    await act(async () => render('art_second'));
    await act(async () => finish({ derivation: { derivation_id: 'der_old', measurements: {
        result: { x: 0, y: 0, valid: true, values: [1, 0] } } } }));
    expect(container.textContent).not.toContain('der_old');
    expect(container.textContent).not.toContain('tangent 0.00°');
    expect(button('Select and sample point').disabled).toBe(false);
});

it('discards a comparison preview after its selection is cleared', async () => {
    let finish;
    const second = { ...artifact, identity: { ...artifact.identity, artifact_id: 'art_second' } };
    const client = { fieldPreview: vi.fn(({ artifact_id }) => artifact_id === 'art_orientation'
        ? Promise.resolve(data) : new Promise((resolve) => { finish = resolve; })) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 'labs_test' }}
        lab={{ ledger: [artifact, second], activeId: 'art_orientation' }} />));
    const choose = async (value) => act(async () => { const element = select('Compare another measurement');
        element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })); });
    await choose('art_second');
    await choose('');
    await act(async () => finish(data));
    expect(container.textContent).not.toContain('Comparison record');
    expect(container.querySelectorAll('.pl-orientation-view')).toHaveLength(1);
});
