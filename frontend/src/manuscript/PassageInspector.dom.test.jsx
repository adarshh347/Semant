import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PassageInspector from './PassageInspector';

/**
 * CIRCUIT-001 P2C-MS — the Passage Inspector, mounted.
 *
 * `manuscriptField.test.js` owns the derivations. This owns the boundary: that
 * the inspector actually hears the chip event the editor already emits, that
 * every act renders WITHOUT a button, and that nothing it renders mutates
 * anything.
 *
 * The last one is the point of the gate. A preview surface whose buttons quietly
 * work is worse than no surface at all.
 */

const GROUND = (id, extra = {}) => ({ id, ground_type: 'region', label: id, region_id: `reg_${id}`, ...extra });
const REGION = (id) => ({ id, label: id, box: { x: 0, y: 0, w: 0.2, h: 0.2 } });

const PERCEPT = {
    id: 'pctx_1',
    kind: 'expression',
    expression: 'the upper head turns away',
    ground_ids: ['g1', 'g2'],
    ground_roles: { g1: 'anchor', g2: 'counterforce' },
};

const STORE = (over = {}) => ({
    percepts: [PERCEPT],
    grounds: [GROUND('g1'), GROUND('g2')],
    regions: [REGION('reg_g1'), REGION('reg_g2')],
    mentions: [],
    ...over,
});

let container, root;

async function mount(props = {}) {
    await act(async () => {
        root.render(<PassageInspector store={STORE()} blocks={[]} {...props} />);
    });
}

/** Fire the event a percept chip already emits when clicked (regionRefInline). */
async function focusChip(perceptId = 'pctx_1', regionIds = ['g1', 'g2']) {
    await act(async () => {
        window.dispatchEvent(new CustomEvent('semant:region-focus', {
            detail: { perceptId, regionIds },
        }));
    });
}

const text = () => container.textContent;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
});

describe('resting state', () => {
    it('renders quietly with nothing selected', async () => {
        await mount();
        expect(container.querySelector('.passage-inspector.is-resting')).toBeTruthy();
        expect(text()).toMatch(/Select a sentence, or a percept chip/);
    });

    it('offers no actions when nothing is selected', async () => {
        await mount();
        expect(container.querySelectorAll('.pi-action').length).toBe(0);
    });
});

describe('a percept chip opens into what it rests on', () => {
    it('hears the chip event the editor already emits', async () => {
        await mount();
        await focusChip();
        expect(container.querySelector('.passage-inspector.is-resting')).toBeFalsy();
        expect(text()).toMatch(/the upper head turns away/);
    });

    it('shows the expression, its grounds, and its roles', async () => {
        await mount();
        await focusChip();
        const keys = [...container.querySelectorAll('.pi-section dt')].map((d) => d.textContent);
        expect(keys).toContain('expression');
        expect(keys).toContain('cited grounds');
        expect(keys).toContain('ground roles');
    });

    it('renders NO evidence row when the evidence is healthy', async () => {
        // Degradation-only. A healthy percept carries no health marks at all.
        await mount();
        await focusChip();
        const keys = [...container.querySelectorAll('.pi-section dt')].map((d) => d.textContent);
        expect(keys).not.toContain('evidence');
        expect(text()).not.toMatch(/verified|healthy/i);
    });

    it('states a degradation, without explaining it, when a ground is gone', async () => {
        await mount({ store: STORE({ regions: [REGION('reg_g1')] }) });
        await focusChip();
        expect(text()).toMatch(/1 of 2 cited grounds no longer resolves/);
        expect(text()).not.toMatch(/replaced|because/i);
    });

    it('marks the evidence row as a judgement, in a different voice from records', async () => {
        await mount({ store: STORE({ regions: [] }) });
        await focusChip();
        const ev = [...container.querySelectorAll('.pi-section')]
            .find((s) => s.querySelector('dt')?.textContent === 'evidence');
        expect(ev.className).toMatch(/pi-voice-judgement/);
        const expr = [...container.querySelectorAll('.pi-section')]
            .find((s) => s.querySelector('dt')?.textContent === 'expression');
        expect(expr.className).toMatch(/pi-voice-record/);
    });

    it('reports a citation that no longer resolves, as a fact about the store', async () => {
        await mount({ store: STORE({ percepts: [] }) });
        await focusChip('pctx_gone');
        expect(text()).toMatch(/no longer resolves in the workspace/);
        expect(container.querySelector('.pi-judgement')).toBeTruthy();
    });

    it('derives "in the writing" from mentions', async () => {
        await mount({ store: STORE({ mentions: [{ perceptId: 'pctx_1', blockId: 'b1' }] }) });
        await focusChip();
        expect(text()).toMatch(/1 passage/);
    });

    it('says not yet in the writing when nothing cites it', async () => {
        await mount();
        await focusChip();
        expect(text()).toMatch(/not yet in the writing/);
    });

    it('ignores a focus event carrying no percept — that is region focus, not a chip', async () => {
        await mount();
        await act(async () => {
            window.dispatchEvent(new CustomEvent('semant:region-focus', {
                detail: { perceptId: null, regionIds: ['reg_1'] },
            }));
        });
        expect(container.querySelector('.passage-inspector.is-resting')).toBeTruthy();
    });
});

describe('preview-only actions do not mutate', () => {
    it('renders acts for a chip with NO button and NO link', async () => {
        await mount();
        await focusChip();
        const acts = container.querySelectorAll('.pi-action');
        expect(acts.length).toBeGreaterThan(0);
        expect(container.querySelectorAll('.pi-actions button').length).toBe(0);
        expect(container.querySelectorAll('.pi-actions a').length).toBe(0);
        for (const a of acts) expect(a.getAttribute('data-wired')).toBe('false');
    });

    it('says the execution path is not wired', async () => {
        await mount();
        await focusChip();
        expect(text()).toMatch(/Preview only — execution path not wired yet/);
    });

    it('mutates nothing in the store when an act is clicked', async () => {
        const store = STORE();
        const before = JSON.stringify(store);
        await mount({ store });
        await focusChip();
        await act(async () => {
            container.querySelector('.pi-action').click();
        });
        expect(JSON.stringify(store)).toBe(before);
    });

    it('offers the return leg to Differential as a proposal', async () => {
        await mount();
        await focusChip();
        const types = [...container.querySelectorAll('.pi-action')].map((a) => a.getAttribute('data-action-type'));
        expect(types).toContain('revise_cited_percept');
        expect(types).toContain('recall_percept');
    });

    it('never renders a dispatch affordance', async () => {
        await mount();
        await focusChip();
        const types = [...container.querySelectorAll('.pi-action')].map((a) => a.getAttribute('data-action-type'));
        expect(types).not.toContain('ask_model_reading');
        expect(text()).not.toMatch(/\bsend to model\b|\bask the model\b/i);
    });
});

describe('the inspector claims nothing it cannot show', () => {
    it('never claims a dispatch happened', async () => {
        await mount();
        await focusChip();
        expect(text()).not.toMatch(/sent|dispatched/i);
    });

    it('is labelled for assistive technology', async () => {
        await mount();
        expect(container.querySelector('[aria-label="Passage inspector"]')).toBeTruthy();
    });
});
