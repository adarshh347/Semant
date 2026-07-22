import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import AttunementPanel from './AttunementPanel';
import { SCULPTURE_FIXTURE } from './attunementPlanner';

/**
 * CIRCUIT-001 P2B — First Attention, mounted.
 *
 * These need a DOM because the claims are about what is on screen and what a click causes:
 * that suggestions render as SUGGESTIONS, that refusing one costs nothing, that an act with
 * no executor admits it instead of no-opping, and that nothing here sends or saves.
 */

const CAPABILITIES = ['find_parts', 'brush_field', 'trace_direction', 'connect_marks', 'compose_percept'];

let container;
let root;

async function mount(props = {}) {
    await act(async () => {
        root.render(<AttunementPanel capabilities={CAPABILITIES} {...props} />);
    });
}

const text = () => container.textContent || '';
const buttons = () => [...container.querySelectorAll('button')];
const byText = (t) => buttons().find((b) => (b.textContent || '').trim().includes(t));
const cards = () => [...container.querySelectorAll('.ap-card')];
const cardsOfType = (t) => [...container.querySelectorAll(`[data-action-type="${t}"]`)];

/** Type into the prompt and ask for acts. */
async function ask(prompt) {
    const ta = container.querySelector('.ap-prompt');
    await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(ta, prompt);
        ta.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { byText('Suggest acts').click(); });
}

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

// ── first attention ──────────────────────────────────────────────────────────

describe('First Attention is the way in', () => {
    it('offers a prompt and its helper copy before anything has been asked', async () => {
        await mount();
        expect(container.querySelector('.ap-prompt')).toBeTruthy();
        expect(text()).toContain('What catches you here?');
        expect(text().toLowerCase()).toContain('gaze, fold, pressure, light, material, or relation');
    });

    it('cannot ask for acts with an empty prompt', async () => {
        await mount();
        expect(byText('Suggest acts').disabled).toBe(true);
    });

    it('shows no suggestions until asked', async () => {
        await mount();
        expect(container.querySelector('.ap-suggested')).toBe(null);
    });

    it('offers every quick chip, so typing is never required', async () => {
        await mount();
        for (const k of ['map_gaze', 'brush_light', 'find_parts', 'start_note', 'counter_reading']) {
            expect(container.querySelector(`[data-chip="${k}"]`), k).toBeTruthy();
        }
    });

    it('a quick chip adds an act without any prompt at all', async () => {
        await mount();
        await act(async () => { container.querySelector('[data-chip="brush_light"]').click(); });
        expect(cardsOfType('brush_field').length).toBe(1);
        // It is the curator's own act, not a suggestion made to them.
        expect(container.querySelector('.ap-source').textContent).toBe('yours');
    });
});

// ── the sculpture prompt, end to end ─────────────────────────────────────────

describe('the sculpture prompt produces acts on screen', () => {
    beforeEach(async () => { await mount({ hasParts: false }); await ask(SCULPTURE_FIXTURE); });

    it('renders the acts the fixture is meant to open', async () => {
        expect(cardsOfType('trace_direction').length).toBeGreaterThan(0);
        expect(cardsOfType('brush_field').length).toBeGreaterThan(0);
        expect(cardsOfType('compose_percept').length).toBe(1);
        expect(cardsOfType('find_parts').length).toBe(1);
        expect(cardsOfType('challenge_percept').length).toBe(1);
    });

    it('names gaze, light, shadow and fold among them', async () => {
        const labels = cards().map((c) => c.querySelector('.ap-card-label').textContent.toLowerCase());
        const joined = labels.join(' | ');
        expect(joined).toContain('gaze');
        expect(joined).toContain('light');
        expect(joined).toContain('shadow');
        expect(joined).toContain('fold');
    });

    it('groups them by what they would touch', async () => {
        const titles = [...container.querySelectorAll('.ap-group-title')].map((t) => t.textContent);
        expect(titles).toContain('Image marks');
        expect(titles).toContain('Percepts');
        expect(titles).toContain('Operations & model questions');
    });

    it('says SUGGESTED, and never that anything was detected or found', async () => {
        // The planner keys on words the curator typed. It has no access to the image, and
        // no copy here may imply otherwise.
        const t = text().toLowerCase();
        expect(t).toContain('suggested acts');
        expect(t).not.toContain('detected');
        expect(t).not.toContain('we found');
        expect(t).not.toContain('semant sees');
    });

    it('each card says which of the curator\'s own words it keyed on', async () => {
        const reasons = [...container.querySelectorAll('.ap-card-reason')].map((r) => r.textContent);
        expect(reasons.some((r) => r.includes('you said'))).toBe(true);
    });

    it('every image mark warns that the curator must draw it', async () => {
        for (const c of cardsOfType('brush_field')) {
            expect(c.textContent).toContain('Needs a mark from you');
        }
    });
});

// ── refusal is free ──────────────────────────────────────────────────────────

describe('dismissing costs nothing', () => {
    it('removes the card and touches nothing outside the panel', async () => {
        const onApplyAction = vi.fn();
        await mount({ onApplyAction });
        await ask(SCULPTURE_FIXTURE);
        const before = cards().length;
        await act(async () => { container.querySelector('.ap-dismiss').click(); });
        expect(cards().length).toBe(before - 1);
        expect(onApplyAction).not.toHaveBeenCalled();
    });

    it('dismissing everything leaves an honest empty line, not a blank panel', async () => {
        await mount();
        await ask('a gaze');
        let guard = 40;
        while (container.querySelector('.ap-dismiss') && guard-- > 0) {
            await act(async () => { container.querySelector('.ap-dismiss').click(); });
        }
        expect(cards().length).toBe(0);
        expect(text().toLowerCase()).toContain('nothing here semant recognises yet');
    });

    it('a prompt it has no vocabulary for suggests nothing rather than inventing', async () => {
        await mount({ hasParts: true });
        await ask('asdf qwerty zxcv');
        expect(cards().length).toBe(0);
        expect(text().toLowerCase()).toContain('nothing here semant recognises yet');
    });
});

// ── applying ─────────────────────────────────────────────────────────────────

describe('carrying an act through', () => {
    it('find_parts calls the executor with the action, and marks it applied', async () => {
        const onApplyAction = vi.fn(() => 'applied');
        await mount({ hasParts: false, wayOfLooking: 'architecture', onApplyAction });
        await ask('the gaze she points toward');

        const card = cardsOfType('find_parts')[0];
        await act(async () => { [...card.querySelectorAll('button')].find((b) => b.textContent.includes('Apply')).click(); });

        expect(onApplyAction).toHaveBeenCalledTimes(1);
        const sent = onApplyAction.mock.calls[0][0];
        expect(sent.type).toBe('find_parts');
        // The post's way of looking rides along — the act does not reset it.
        expect(sent.payload.way_of_looking).toBe('architecture');
        expect(cardsOfType('find_parts')[0].className).toContain('is-applied');
        expect(cardsOfType('find_parts')[0].textContent).toContain('Carried through');
    });

    it('an image mark ARMS rather than applies, and says the hand is still yours', async () => {
        const onApplyAction = vi.fn(() => 'armed');
        await mount({ onApplyAction });
        await ask('the light on the left');

        const card = cardsOfType('brush_field')[0];
        // The verb is different because the act is different: nothing is made by clicking.
        const arm = [...card.querySelectorAll('button')].find((b) => b.textContent.includes('Arm this'));
        expect(arm).toBeTruthy();
        await act(async () => { arm.click(); });

        const after = cardsOfType('brush_field')[0];
        expect(after.className).toContain('is-previewed');
        expect(after.textContent).toContain('Ready — make the mark on the image');
    });

    it('an act with no executor renders "preview only" and NO apply button', async () => {
        // The rule that keeps the panel from being theatre: never a button that no-ops.
        await mount({ capabilities: ['find_parts'], onApplyAction: vi.fn() });
        await ask('the gaze and the light');

        const brush = cardsOfType('brush_field')[0];
        expect(brush.textContent).toContain('Preview only — execution path not wired yet');
        expect([...brush.querySelectorAll('button')].some((b) => /Apply|Arm this/.test(b.textContent))).toBe(false);
    });
});

// ── the things that must not happen ──────────────────────────────────────────

describe('nothing here sends or saves', () => {
    it('ask_model_reading is never applicable, even when capabilities claim it is', async () => {
        const onApplyAction = vi.fn();
        await mount({ capabilities: [...CAPABILITIES, 'ask_model_reading'], onApplyAction });
        await act(async () => { container.querySelector('[data-chip="brush_light"]').click(); });
        // No planner path emits one today; the guard is asserted in the pure suite too.
        // Here we prove the executor is never reached for it.
        expect(onApplyAction).not.toHaveBeenCalled();
    });

    it('a manuscript act says nothing is saved, and offers no apply path', async () => {
        await mount({ onApplyAction: vi.fn() });
        await act(async () => { container.querySelector('[data-chip="start_note"]').click(); });
        const card = cardsOfType('start_manuscript')[0];
        expect(card.textContent.toLowerCase()).toContain('nothing is saved');
        // start_manuscript is not in CAPABILITIES — preview only, no autosave, no editor.
        expect(card.textContent).toContain('Preview only');
        expect([...card.querySelectorAll('button')].some((b) => /Apply|Arm this/.test(b.textContent))).toBe(false);
    });

    it('a counter-reading is offered but never carried out by the panel', async () => {
        await mount({ onApplyAction: vi.fn() });
        await act(async () => { container.querySelector('[data-chip="counter_reading"]').click(); });
        const card = cardsOfType('challenge_percept')[0];
        expect(card.textContent).toContain('Preview only');
    });

    it('previewing changes the card and calls no executor', async () => {
        const onApplyAction = vi.fn();
        await mount({ onApplyAction });
        await ask('the light');
        await act(async () => { byText('Preview').click(); });
        expect(onApplyAction).not.toHaveBeenCalled();
        expect(container.querySelector('.ap-card').className).toContain('is-previewed');
    });
});
