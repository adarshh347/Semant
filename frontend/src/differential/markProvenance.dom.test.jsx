import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { summarizeProvenance } from './suggestionQuarantine';
import { makeVisualMark, normalizeMark } from './visualMarks';

/**
 * CIRCUIT-001 P2D-A — provenance rendered on the existing stack.
 *
 * The full Differential workspace is heavy to mount in a bare jsdom (canvas, ResizeObserver,
 * image geometry). The rendering under test — a provenance chip driven by `summarizeProvenance`
 * — is small and pure, so this mounts the exact JSX pattern the workspace uses rather than the
 * whole component. The behaviour that MATTERS (which label a source yields, that a suggestion
 * reads as unaccepted, that no confidence number leaks) is a property of `summarizeProvenance`,
 * which the node suite pins; here we prove that property survives being put on screen.
 */

// The chip exactly as DifferentialWorkspace renders it for a selected ground.
function ProvenanceChip({ mark }) {
    if (!mark) return null;
    const isModel = ['model_suggested', 'user_confirmed', 'model_refined'].includes(mark.source);
    return (
        <span className={`diff-chip diff-mark-prov-chip${isModel ? ' is-model' : ''}`}>
            {summarizeProvenance(mark)}
        </span>
    );
}

// The suggestion line exactly as the refine inspector renders it.
function SuggestionLine({ base }) {
    return (
        <p className="diff-mark-prov diff-mark-prov--suggested" role="status">
            {summarizeProvenance({ source: 'model_suggested' })}
            <span className="diff-prov-note"> — accepting keeps it as “{summarizeProvenance({ source: base ? 'model_refined' : 'user_confirmed' })}”.</span>
        </p>
    );
}

let container;
let root;

async function mount(node) {
    await act(async () => { root.render(node); });
}
const text = () => container.textContent || '';

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

describe('the provenance chip on a committed ground', () => {
    it('reads "Yours" quietly for the curator\'s own brush, with no model tint', async () => {
        const mark = normalizeMark({
            type: 'brush_field', role: 'light_field', source: 'user', status: 'committed',
            geometry: { kind: 'freehand_path' }, linked_ground_ids: ['gnd_1'],
        }, { now: 'T' });
        await mount(<ProvenanceChip mark={mark} />);
        expect(text()).toBe('Yours');
        expect(container.querySelector('.is-model')).toBe(null);
    });

    it('says the model\'s part out loud, and earns the tint, for a confirmed mark', async () => {
        const mark = normalizeMark({
            type: 'brush_field', role: 'material_field', source: 'user_confirmed', status: 'committed',
            geometry: { kind: 'raster_mask' }, derived_from: 'vm_s',
        }, { now: 'T' });
        await mount(<ProvenanceChip mark={mark} />);
        expect(text()).toBe('Model proposed · you accepted');
        expect(container.querySelector('.is-model')).toBeTruthy();
    });

    it('never renders a confidence number', async () => {
        for (const source of ['model_suggested', 'user_confirmed', 'model_refined', 'user']) {
            await mount(<ProvenanceChip mark={makeVisualMark('brush_field', { role: 'fold', source, derived_from: 'x' })} />);
            expect(text()).not.toMatch(/[0-9]/);
        }
    });
});

describe('the suggestion line in the refine inspector', () => {
    it('says the mask is a suggestion, not evidence, while proposed', async () => {
        await mount(<SuggestionLine base={null} />);
        const t = text().toLowerCase();
        expect(t).toContain('model suggestion');
        expect(t).toContain('not accepted');
    });

    it('promises user_confirmed for a fresh mask, model_refined when refining a region', async () => {
        await mount(<SuggestionLine base={null} />);
        expect(text()).toContain('you accepted');       // user_confirmed
        await mount(<SuggestionLine base={{ id: 'reg_1' }} />);
        expect(text()).toContain('model tightened');    // model_refined
    });

    it('carries the honest dashed treatment class, not an alarm class', async () => {
        await mount(<SuggestionLine base={null} />);
        const line = container.querySelector('.diff-mark-prov--suggested');
        expect(line).toBeTruthy();
        expect(line.className).not.toContain('error');
        expect(line.className).not.toContain('warn');
    });
});
