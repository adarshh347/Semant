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

function deferred() {
    let resolve; let reject;
    const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    return { promise, resolve, reject };
}
function savedReading(id) {
    return { form: 'field.depth.profile', derivation_id: id, input_artifact_ids: ['a'],
        measurements: { result: { samples: [{ valid: true, values: [3] }] } } };
}
async function startProfile() {
    const input = container.querySelector('input[placeholder="0,0; 1,0; 2,0"]');
    await act(async () => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '1,0');
        input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const button = [...container.querySelectorAll('button')].find((element) => element.textContent === 'Save depth profile');
    await act(async () => button.click());
}

it.each(['success', 'failure'])('ignores stale consumer %s and finally after switching session/field', async (outcome) => {
    const oldRequest = deferred(); const newRequest = deferred();
    const client = { fieldPreview: vi.fn(async () => data),
        consumeField: vi.fn().mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 'old-session' }} lab={{ ledger: [artifact] }} />));
    await startProfile();
    const nextArtifact = { ...artifact, identity: { ...artifact.identity, artifact_id: 'new-field' } };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 'new-session' }} lab={{ ledger: [nextArtifact] }} />));
    expect(container.textContent).not.toContain('Saving a reading');
    await startProfile();
    await act(async () => {
        if (outcome === 'success') oldRequest.resolve({ derivation: savedReading('stale-reading') });
        else oldRequest.reject(new Error('stale-error'));
    });
    expect(container.textContent).not.toContain('stale-reading');
    expect(container.textContent).not.toContain('stale-error');
    expect(container.textContent).toContain('Saving a reading');
    await act(async () => newRequest.resolve({ derivation: savedReading('current-reading') }));
    expect(container.textContent).toContain('current-reading');
    expect(container.textContent).not.toContain('Saving a reading');
    expect(client.consumeField).toHaveBeenLastCalledWith(expect.objectContaining({ session_id: 'new-session', artifact_id: 'new-field' }));
});

it('allows only one pending point consumer even for same-tick repeated map clicks', async () => {
    const request = deferred();
    const client = { fieldPreview: vi.fn(async () => data), consumeField: vi.fn(() => request.promise) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 's' }} lab={{ ledger: [artifact] }} />));
    const map = container.querySelector('svg[aria-label^="scalar field"]');
    await act(async () => {
        map.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 0, clientY: 0 }));
        map.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 0, clientY: 0 }));
    });
    expect(client.consumeField).toHaveBeenCalledTimes(1);
    await act(async () => request.resolve({ derivation: savedReading('point-result') }));
    expect(container.textContent).toContain('point-result');
});

it('merges late saved history without replacing the newly created reading', async () => {
    const history = deferred(); const newest = savedReading('newest-reading');
    const client = { fieldPreview: vi.fn(async () => data), derivations: vi.fn(() => history.promise),
        consumeField: vi.fn(async () => ({ derivation: newest })) };
    await act(async () => root.render(<SLOT.Panel client={client} session={{ session_id: 's' }} lab={{ ledger: [artifact] }} />));
    await startProfile();
    await act(async () => history.resolve({ derivations: [savedReading('older-reading'), newest] }));
    expect(container.querySelector('.pl-field-reading h3').textContent).toContain('newest-reading');
    const choices = [...container.querySelectorAll('option')].filter((option) => option.value === 'newest-reading');
    expect(choices).toHaveLength(1);
    expect(container.textContent).toContain('older-reading');
});
