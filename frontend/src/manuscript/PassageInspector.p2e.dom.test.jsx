import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PassageInspector from './PassageInspector';
import { makeVisualMark } from '../differential/visualMarks';
import { quarantineSuggestion } from '../differential/suggestionQuarantine';

/**
 * CIRCUIT-001 P2E — the Manuscript can inspect the visual marks behind a percept's
 * evidence (Gate 4). Read-only, session-only, and honest about both.
 */

const GROUND = (id) => ({ id, ground_type: 'region', label: id, region_id: `reg_${id}` });
const REGION = (id) => ({ id, label: id, box: { x: 0, y: 0, w: 0.2, h: 0.2 } });
const PERCEPT = {
    id: 'pctx_1', kind: 'expression', expression: 'the upper head', ground_ids: ['g1', 'g2'],
};

const committedMark = (gid) => makeVisualMark('brush_field', {
    role: 'light_field', source: 'user', status: 'committed',
    geometry: { kind: 'freehand_path' }, linked_ground_ids: [gid],
}, { now: 't' });

const suggestionMark = (gid) => quarantineSuggestion(makeVisualMark('brush_field', {
    role: 'shadow_field', source: 'model_suggested', geometry: { kind: 'freehand_path' },
    linked_ground_ids: [gid],
}, { now: 't' }), { now: 't' });

const STORE = (marks = []) => ({
    percepts: [PERCEPT], grounds: [GROUND('g1'), GROUND('g2')],
    regions: [REGION('reg_g1'), REGION('reg_g2')], mentions: [], visualMarks: marks,
});

let container, root;
async function mount(store) {
    await act(async () => { root.render(<PassageInspector store={store} blocks={[]} />); });
}
async function focusChip(perceptId = 'pctx_1') {
    await act(async () => {
        window.dispatchEvent(new CustomEvent('semant:region-focus', { detail: { perceptId, regionIds: ['g1', 'g2'] } }));
    });
}
const text = () => container.textContent || '';
const marks = () => [...container.querySelectorAll('.pi-mark')];

beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

describe('visual marks behind a percept', () => {
    it('shows a committed mark as SAVED, not the stale "session-only" (P3-A)', async () => {
        await mount(STORE([committedMark('g1')]));
        await focusChip();
        expect(container.querySelector('.pi-marks')).toBeTruthy();
        // Marks are durable now — a committed mark says "Saved", never "session-only".
        expect(text()).toMatch(/Saved/);
        expect(text()).not.toMatch(/Session — not saved/);
        expect(marks()[0].getAttribute('data-persisted')).toBe('true');
        expect(marks()).toHaveLength(1);
    });

    it('shows a session-only suggestion as "not saved" (durability is per mark)', async () => {
        await mount(STORE([suggestionMark('g1')]));
        await focusChip();
        // A suggestion is not persistable — it must still say so, honestly.
        expect(text()).toMatch(/Session — not saved/);
        expect(marks()[0].getAttribute('data-persisted')).toBe('false');
    });

    it('shows a committed user mark as citable, provenance "Yours"', async () => {
        await mount(STORE([committedMark('g1')]));
        await focusChip();
        const m = marks()[0];
        expect(m.getAttribute('data-citable')).toBe('true');
        expect(m.textContent).toMatch(/Yours/);
        expect(m.textContent).toMatch(/citable/);
    });

    it('shows a model suggestion as a suggestion, and NOT citable', async () => {
        await mount(STORE([suggestionMark('g1')]));
        await focusChip();
        const m = marks()[0];
        expect(m.className).toMatch(/is-suggestion/);
        expect(m.getAttribute('data-citable')).toBe('false');
        expect(m.textContent).toMatch(/Model suggestion/);
        expect(m.textContent).toMatch(/not citable/);
    });

    it('renders a user mark and a suggestion differently in the same list', async () => {
        await mount(STORE([committedMark('g1'), suggestionMark('g2')]));
        await focusChip();
        expect(marks()).toHaveLength(2);
        expect(container.querySelectorAll('.pi-mark.is-suggestion')).toHaveLength(1);
    });

    it('shows nothing when the percept has no marks — no fake evidence', async () => {
        await mount(STORE([committedMark('g9')])); // linked to a ground this percept does not cite
        await focusChip();
        expect(container.querySelector('.pi-marks')).toBeFalsy();
    });

    it('does not claim evidence support anywhere', async () => {
        await mount(STORE([committedMark('g1')]));
        await focusChip();
        expect(text()).not.toMatch(/\bsupported\b|\bverified\b|\bproven\b/i);
    });

    it('degrades quietly when the store carries no marks field', async () => {
        await mount({ percepts: [PERCEPT], grounds: [GROUND('g1')], regions: [], mentions: [] });
        await focusChip();
        expect(container.querySelector('.pi-marks')).toBeFalsy();
    });
});
