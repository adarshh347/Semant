import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import RefPicker from './RefPicker';
import { makeVisualMark } from '../differential/visualMarks';
import { quarantineSuggestion } from '../differential/suggestionQuarantine';

/**
 * CIRCUIT-001 P3-A — the citation seam. A mark chip is a claim of evidence, so the
 * picker must offer ONLY marks that can honestly be cited: committed, the curator's
 * own (or confirmed), with real geometry. `canCiteMark` is the filter and it lives in
 * exactly one place. A suggestion can never be offered — the proof that the quarantine
 * holds all the way to the Manuscript.
 */

const committed = (over = {}) => makeVisualMark('brush_field', {
    role: 'light_field', source: 'user', status: 'committed',
    geometry: { kind: 'freehand_path' }, label: 'the falling light', ...over,
}, { now: 't' });

const suggestion = () => quarantineSuggestion(makeVisualMark('brush_field', {
    role: 'shadow_field', source: 'model_suggested', geometry: { kind: 'freehand_path' },
    label: 'a model guess',
}, { now: 't' }), { now: 't' });

const draft = () => makeVisualMark('brush_field', {
    role: 'light_field', source: 'user', status: 'draft',
    geometry: { kind: 'unresolved' }, label: 'not drawn yet',
}, { now: 't' });

let container, root;
async function mount(marks, onPick = () => {}) {
    await act(async () => {
        root.render(
            <RefPicker kind="mark" x={0} y={0} regions={[]} lenses={[]} marks={marks}
                onPick={onPick} onClose={() => {}} />,
        );
    });
}
const rows = () => [...container.querySelectorAll('.ref-picker-item')];

beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

describe('RefPicker · mark — offers only citable marks', () => {
    it('offers a committed, citable mark', async () => {
        await mount([committed()]);
        expect(rows()).toHaveLength(1);
        expect(container.textContent).toMatch(/the falling light/);
    });

    it('NEVER offers a model suggestion (the quarantine holds)', async () => {
        await mount([committed(), suggestion()]);
        expect(rows()).toHaveLength(1);
        expect(container.textContent).not.toMatch(/a model guess/);
    });

    it('NEVER offers a draft with no geometry', async () => {
        await mount([committed(), draft()]);
        expect(rows()).toHaveLength(1);
        expect(container.textContent).not.toMatch(/not drawn yet/);
    });

    it('shows the empty state when no mark is citable — nothing to launder', async () => {
        await mount([suggestion(), draft()]);
        expect(rows()).toHaveLength(0);
        expect(container.textContent).toMatch(/No citable marks yet/);
    });

    it('picking a row hands back the raw mark (the object, for the insert seam)', async () => {
        let picked = null;
        const m = committed();
        await mount([m], (raw) => { picked = raw; });
        await act(async () => {
            container.querySelector('.ref-picker-item').dispatchEvent(
                new MouseEvent('mousedown', { bubbles: true }),
            );
        });
        expect(picked?.id).toBe(m.id);
    });
});
