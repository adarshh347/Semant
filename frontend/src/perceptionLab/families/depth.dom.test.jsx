import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { SLOT } from './depth';

let container; let root;
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
const artifact = { identity: { artifact_id: 'a', organ_family: 'depth', artifact_kind: 'sample_grid' },
    provenance: { producer: 'injected test producer' } };
const data = { execution_identity: 'FIXTURE', measurement_hash: 'fixed-hash', metadata: { kind: 'scalar',
    shape: [2, 3, 1], source_digest: 'source-hash', value_convention: 'larger=nearer' },
    preview: { shape: [2, 3, 1], values: [1, 2, 3, 0, 5, 6], valid: [true, true, true, false, true, true], stride: 1 } };

it('offers a guiding empty state and discloses estimates rather than distances', async () => {
    await act(async () => root.render(<SLOT.Panel client={{}} session={{ session_id: 's' }} lab={{ ledger: [] }} />));
    expect(container.textContent).toContain('No saved depth field');
    expect(container.textContent).toContain('no fixture is substituted');
    expect(container.textContent).toContain('Painted space can be unreliable');
});

it('reads saved values, switches views without producer calls and persists declared profile', async () => {
    const client = { fieldPreview: vi.fn(async () => data), consumeField: vi.fn(async () => ({ derivation: {
        form: 'depth.profile', derivation_id: 'd', measurements: { result: { samples: [{ valid: true, values: [2] }] } } } })) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 's' }} lab={{ ledger: [artifact] }} />));
    expect(container.textContent).toContain('FIXTURE');
    expect(container.textContent).toContain('fixed-hash');
    const view = [...container.querySelectorAll('select')].find((element) => element.textContent.includes('Grayscale'));
    await act(async () => { view.value = 'grayscale'; view.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(container.textContent).toContain('dark = farther, light = nearer');
    expect(client.fieldPreview).toHaveBeenCalledTimes(1);
    const input = container.querySelector('input[placeholder="0,0; 1,0; 2,0"]');
    await act(async () => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '1,0; 2,1');
        input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const button = [...container.querySelectorAll('button')].find((element) => element.textContent === 'Save depth profile');
    await act(async () => button.click());
    expect(client.consumeField).toHaveBeenCalledWith(expect.objectContaining({ operation: 'depth.profile', points: [[1, 0], [2, 1]] }));
    expect(container.textContent).toContain('depth.profile · d');
    expect(container.textContent).toContain('fixed-hash');
});

it('reopens persisted profiles without calling a producer or creating another derivation', async () => {
    const saved = { form: 'field.depth.profile', derivation_id: 'restored-profile', input_artifact_ids: ['a'],
        measurements: { result: { samples: [{ valid: true, values: [3] }] } } };
    const client = { fieldPreview: vi.fn(async () => data), consumeField: vi.fn(),
        derivations: vi.fn(async () => ({ derivations: [saved] })) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 's' }} lab={{ ledger: [artifact] }} />));
    expect(container.textContent).toContain('restored-profile');
    expect(container.textContent).toContain('1 valid of 1 explicit samples');
    expect(client.consumeField).not.toHaveBeenCalled();
});
