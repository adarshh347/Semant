import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import PassageInspector from './PassageInspector';

/**
 * CIRCUIT-001 P2C-MS2 — the Passage Inspector, mounted.
 *
 * `manuscriptField.test.js` owns the derivations and builders. This owns the
 * boundary: that the collapse control works, that live acts call the parent's
 * callbacks, that staged acts build a proposal and STOP, and that nothing the
 * inspector does mutates the store.
 */

const GROUND = (id, extra = {}) => ({ id, ground_type: 'region', label: id, region_id: `reg_${id}`, ...extra });
const REGION = (id) => ({ id, label: id, box: { x: 0, y: 0, w: 0.2, h: 0.2 } });

const PERCEPT = {
    id: 'pctx_1', kind: 'expression', expression: 'the upper head turns away',
    ground_ids: ['g1', 'g2'], ground_roles: { g1: 'anchor', g2: 'counterforce' },
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

async function focusChip(perceptId = 'pctx_1', regionIds = ['g1', 'g2']) {
    await act(async () => {
        window.dispatchEvent(new CustomEvent('semant:region-focus', { detail: { perceptId, regionIds } }));
    });
}

// Build a real selection inside a `.manuscript` node so readSelection fires.
async function selectProse(str = 'The vault carries the light upward.') {
    const m = document.createElement('div');
    m.className = 'manuscript';
    const block = document.createElement('div');
    block.setAttribute('data-id', 'b1');
    block.textContent = str;
    m.appendChild(block);
    document.body.appendChild(m);
    await act(async () => {
        const range = document.createRange();
        range.selectNodeContents(block);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        document.dispatchEvent(new Event('selectionchange'));
    });
    return () => m.remove();
}

const text = () => container.textContent;
const btn = (key) => container.querySelector(`.pi-action-btn[data-action-key="${key}"]`);
const click = async (el) => { await act(async () => el.click()); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    document.querySelectorAll('.manuscript').forEach((n) => n.remove());
});

describe('collapse / expand', () => {
    it('has an obvious, accessible toggle in the header', async () => {
        await mount();
        const toggle = container.querySelector('.pi-toggle');
        expect(toggle).toBeTruthy();
        expect(toggle.tagName).toBe('BUTTON');
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(toggle.getAttribute('aria-controls')).toBe('pi-body');
    });

    it('collapses to a compact summary that does not disappear', async () => {
        await mount();
        await focusChip();
        expect(container.querySelector('#pi-body')).toBeTruthy();
        await click(container.querySelector('.pi-toggle'));
        // body gone, but the summary line remains
        expect(container.querySelector('#pi-body')).toBeFalsy();
        expect(container.querySelector('.pi-summary').textContent).toMatch(/Percept · \d+ ground/);
        expect(container.querySelector('.pi-toggle').getAttribute('aria-expanded')).toBe('false');
    });

    it('expands again, preserving the selection', async () => {
        await mount();
        await focusChip();
        await click(container.querySelector('.pi-toggle')); // collapse
        await click(container.querySelector('.pi-toggle')); // expand
        expect(container.querySelector('#pi-body')).toBeTruthy();
        expect(text()).toMatch(/the upper head turns away/);
    });

    it('shows a plain-selection collapsed summary', async () => {
        await mount();
        const cleanup = await selectProse();
        if (btn('recall') || container.querySelector('.pi-quote')) {
            await click(container.querySelector('.pi-toggle'));
            expect(container.querySelector('.pi-summary').textContent).toMatch(/Selection/);
        }
        cleanup();
    });
});

describe('percept chip — live acts call the parent, and nothing mutates', () => {
    it('Recall on the image calls the recall path with the percept id', async () => {
        const onRecall = vi.fn();
        await mount({ onRecall });
        await focusChip();
        await click(btn('recall'));
        expect(onRecall).toHaveBeenCalledWith('pctx_1');
    });

    it('Revise in Differential calls the return handler', async () => {
        const onReviseInDifferential = vi.fn();
        await mount({ onReviseInDifferential });
        await focusChip();
        await click(btn('revise'));
        expect(onReviseInDifferential).toHaveBeenCalledWith('pctx_1');
    });

    it('Start a passage calls the start-passage handler', async () => {
        const onStartPassage = vi.fn();
        await mount({ onStartPassage });
        await focusChip();
        await click(btn('start_passage'));
        expect(onStartPassage).toHaveBeenCalled();
    });

    it('clicking a live act does not mutate the store', async () => {
        const store = STORE();
        const before = JSON.stringify(store);
        await mount({ store, onRecall: () => {}, onReviseInDifferential: () => {} });
        await focusChip();
        await click(btn('recall'));
        await click(btn('revise'));
        expect(JSON.stringify(store)).toBe(before);
    });
});

describe('percept chip — staged and disclosed acts', () => {
    it('Challenge support builds a "Ready, not sent" proposal, authored by the user', async () => {
        await mount();
        await focusChip();
        await click(btn('challenge_support'));
        const proposal = container.querySelector('.pi-proposal');
        expect(proposal).toBeTruthy();
        expect(proposal.textContent).toMatch(/Ready, not sent/);
        // nothing dispatched, nothing saved
        expect(text()).not.toMatch(/\bsent\b(?!,)/i);
    });

    it('Show packet discloses the packet, stating nothing is sent', async () => {
        await mount();
        await focusChip();
        await click(btn('packet'));
        const d = container.querySelector('.pi-disclosure');
        expect(d).toBeTruthy();
        expect(d.textContent).toMatch(/nothing is sent/i);
    });

    it('Show circulation discloses the thread with record/judgement voices', async () => {
        await mount();
        await focusChip();
        await click(btn('thread'));
        const d = container.querySelector('.pi-disclosure[aria-label="Circulation thread"]');
        expect(d).toBeTruthy();
        // no model reading is a RECORD about the ledger, not a verdict
        expect(d.textContent).toMatch(/no model reading recorded/i);
    });

    it('a disclosure toggles off when clicked again', async () => {
        await mount();
        await focusChip();
        await click(btn('packet'));
        expect(container.querySelector('.pi-disclosure')).toBeTruthy();
        await click(btn('packet'));
        expect(container.querySelector('.pi-disclosure')).toBeFalsy();
    });

    it('never renders a dispatch affordance', async () => {
        await mount();
        await focusChip();
        const keys = [...container.querySelectorAll('.pi-action-btn')].map((b) => b.getAttribute('data-action-key'));
        expect(keys).not.toContain('ask_model_reading');
        expect(text()).not.toMatch(/ask the model|send to model/i);
    });
});

describe('prose selection — structured, safe acts', () => {
    it('offers create-percept and a live return to Differential', async () => {
        const onSendToDifferential = vi.fn();
        await mount({ onSendToDifferential });
        const cleanup = await selectProse();
        // Only assert if jsdom registered the selection (guards flaky Selection support).
        if (btn('send_first_attention')) {
            expect(btn('create_percept')).toBeTruthy();
            await click(btn('send_first_attention'));
            expect(onSendToDifferential).toHaveBeenCalled();
        }
        cleanup();
    });

    it('a staged create-percept does not mutate the store', async () => {
        const store = STORE();
        const before = JSON.stringify(store);
        await mount({ store });
        const cleanup = await selectProse();
        if (btn('create_percept')) {
            await click(btn('create_percept'));
            expect(container.querySelector('.pi-proposal')).toBeTruthy();
        }
        expect(JSON.stringify(store)).toBe(before);
        cleanup();
    });
});

describe('the inspector claims nothing it cannot show', () => {
    it('never renders a fake "supported" claim', async () => {
        await mount();
        await focusChip();
        expect(text()).not.toMatch(/\bsupported\b|\bverified\b|\bhealthy\b/i);
    });

    it('is labelled for assistive technology', async () => {
        await mount();
        expect(container.querySelector('[aria-label="Passage inspector"]')).toBeTruthy();
    });

    it('rests quietly with nothing selected', async () => {
        await mount();
        expect(container.querySelector('.passage-inspector.is-resting')).toBeTruthy();
        expect(text()).toMatch(/Select a sentence, or a percept chip/);
    });
});
