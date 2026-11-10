import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import FieldInspector from './FieldInspector';
import fixture from './fixtures/foundation-field.v1.json';

let host; let root;
beforeEach(() => { host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });
const artifact = (id) => ({ identity: { artifact_id: id }, provenance: { producer: 'fixture' }, measurement: { payload: {} } });
const render = async (client, id = 'a', sessionId = 's') => {
    await act(async () => root.render(<FieldInspector client={client} sessionId={sessionId}
        artifact={artifact(id)} fields={['a', 'b', 'c'].map(artifact)} />));
};
const clickField = async () => { await act(async () => host.querySelector('svg').dispatchEvent(new MouseEvent('click', { bubbles: true }))); };
const reading = (id) => ({ derivation: { form: 'field.point', derivation_id: id, measurements: { result: { value: id } } } });

it('never displays an old field reading after switching source/session', async () => {
    let resolve;
    const client = { fieldPreview: vi.fn(async () => fixture), consumeField: vi.fn(() => new Promise((done) => { resolve = done; })) };
    await render(client);
    await clickField();
    await render(client, 'b', 'new-session');
    await act(async () => resolve(reading('old-reading')));
    expect(host.textContent).not.toContain('old-reading');
});

it('keeps the newest requested reading when responses arrive out of order', async () => {
    const pending = [];
    const client = { fieldPreview: vi.fn(async () => fixture), consumeField: vi.fn(() => new Promise((done) => pending.push(done))) };
    await render(client);
    await clickField(); await clickField();
    await act(async () => pending[1](reading('new-reading')));
    await act(async () => pending[0](reading('old-reading')));
    expect(host.textContent).toContain('new-reading');
    expect(host.textContent).not.toContain('old-reading');
});

it('does not restore a comparison that was deselected while its preview loaded', async () => {
    let resolve;
    const client = { fieldPreview: vi.fn(({ artifact_id: id }) => id === 'a'
        ? Promise.resolve(fixture) : new Promise((done) => { resolve = done; })) };
    await render(client);
    const select = [...host.querySelectorAll('select')].at(-1);
    await act(async () => { select.value = 'b'; select.dispatchEvent(new Event('change', { bubbles: true })); });
    await act(async () => { select.value = ''; select.dispatchEvent(new Event('change', { bubbles: true })); });
    await act(async () => resolve(fixture));
    expect(host.textContent).not.toContain('Compare saved values');
});
