/**
 * INQUIRY WORKBENCH — the entry, mounted.
 *
 * No testing-library: the project has none as a dependency, and these are plain DOM queries
 * against a real root — the same shape as the existing `.dom.test.jsx` suites.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import InquiryEntry from './InquiryEntry.jsx';
import { DEFAULT_MODE } from './inquiryContract.js';

let container;
let root;

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

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];

const POSTS = [
    { id: 'post_altes_front', photo_url: '/x.jpg', title: 'Lustgarten front', region_annotations: [] },
    { id: 'post_altes_rotunda', photo_url: '/y.jpg', title: 'Rotunda', region_annotations: [{}] },
];

async function type(el, value) {
    const proto = el.tagName === 'TEXTAREA'
        ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    await act(async () => {
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
}

async function mount(props = {}) {
    await act(async () => {
        root.render(<InquiryEntry posts={POSTS} onStart={() => {}} {...props} />);
    });
}

describe('the entry asks for images and a question, and nothing else', () => {
    it('cannot start without both', async () => {
        await mount();
        expect($('.iw-start').disabled).toBe(true);
        await act(async () => { $('.iw-thumb').click(); });
        expect($('.iw-start').disabled).toBe(true);          // still no question
        await type($('.iw-prompt'), 'how does it gather?');
        expect($('.iw-start').disabled).toBe(false);
    });

    it('a whitespace-only prompt is not a question', async () => {
        await mount();
        await act(async () => { $('.iw-thumb').click(); });
        await type($('.iw-prompt'), '   ');
        expect($('.iw-start').disabled).toBe(true);
    });

    it('offers every image identically — no annotation gate, no filter, nothing disabled', async () => {
        await mount();
        // One post carries a region and one carries none. Nothing on this form distinguishes them:
        // the plan's Phase-1 exit is "select existing images and enter any prompt", and a filter
        // here would reintroduce the precondition the design removed.
        expect($$('.iw-thumb').length).toBe(2);
        expect($$('.iw-thumb[disabled]').length).toBe(0);
        expect(text()).not.toMatch(/annotat|marks|regions/i);
    });

    it('passes the selection, the trimmed prompt and the mode through', async () => {
        const onStart = vi.fn();
        await mount({ onStart });
        await act(async () => { $$('.iw-thumb')[0].click(); });
        await act(async () => { $$('.iw-thumb')[1].click(); });
        await type($('.iw-prompt'), '  what does the threshold do?  ');
        await act(async () => { $('[data-mode="step"]').click(); });
        await act(async () => { $('.iw-start').click(); });

        expect(onStart).toHaveBeenCalledWith({
            imageIds: ['post_altes_front', 'post_altes_rotunda'],
            prompt: 'what does the threshold do?',
            mode: 'step',
        });
    });

    it('toggles a selection off again', async () => {
        const onStart = vi.fn();
        await mount({ onStart });
        await act(async () => { $$('.iw-thumb')[0].click(); });
        await act(async () => { $$('.iw-thumb')[0].click(); });
        await type($('.iw-prompt'), 'q');
        expect($('.iw-start').disabled).toBe(true);
        expect($$('.iw-thumb')[0].getAttribute('aria-pressed')).toBe('false');
    });
});

describe('the interaction mode', () => {
    it('offers all three with a plain-language consequence, not just a name', async () => {
        await mount();
        const modes = $$('.iw-mode');
        expect(modes.map((m) => m.dataset.mode)).toEqual(['auto', 'consult', 'step']);
        for (const m of modes) {
            expect(m.querySelector('.iw-mode-hint').textContent.trim().length)
                .toBeGreaterThan(40);
        }
    });

    it('says out loud that auto still records and still stops at acceptance', async () => {
        await mount();
        const auto = $('[data-mode="auto"]').textContent;
        expect(auto).toMatch(/records every choice/i);
        expect(auto).toMatch(/stops before anything would be accepted/i);
    });

    it('defaults to consult and exposes the choice as a radio group', async () => {
        await mount();
        expect($(`[data-mode="${DEFAULT_MODE}"]`).getAttribute('aria-checked')).toBe('true');
        expect($('[role="radiogroup"]')).toBeTruthy();
        expect($$('[role="radio"]').length).toBe(3);
        await act(async () => { $('[data-mode="auto"]').click(); });
        expect($('[data-mode="auto"]').getAttribute('aria-checked')).toBe('true');
        expect($(`[data-mode="${DEFAULT_MODE}"]`).getAttribute('aria-checked')).toBe('false');
    });
});

describe('an unavailable API', () => {
    it('says so, and offers nothing in its place', async () => {
        await mount({ unavailable: 'GET /api/v1/inquiries — 404' });
        const box = $('[data-unavailable="api"]');
        expect(box).toBeTruthy();
        expect(box.textContent).toMatch(/not available/i);
        expect(box.textContent).toContain('GET /api/v1/inquiries — 404');
        // The guarantee, in the DOM: no fixture is standing in.
        expect(box.textContent).toMatch(/nothing is being shown in its place/i);
        expect($('.iw-claim')).toBeNull();
        expect($('.iw-reading')).toBeNull();
    });

    it('is absent when the API is fine', async () => {
        await mount();
        expect($('[data-unavailable="api"]')).toBeNull();
    });
});

describe('the form is reachable from a keyboard', () => {
    it('labels every control', async () => {
        await mount();
        expect($('form').getAttribute('aria-label')).toBe('Start an inquiry');
        expect($('.iw-prompt').getAttribute('aria-label')).toBe('Prompt');
        expect($('[role="radiogroup"]').getAttribute('aria-label')).toBe('Interaction mode');
        expect($('.iw-corpus').getAttribute('aria-label')).toBe('Choose images');
    });

    it('uses real buttons, so tab order and Enter come for free', async () => {
        await mount();
        for (const el of [...$$('.iw-thumb'), ...$$('.iw-mode'), $('.iw-start')]) {
            expect(el.tagName).toBe('BUTTON');
            expect(el.getAttribute('tabindex')).toBeNull();
        }
        expect($('.iw-start').type).toBe('submit');
    });
});
