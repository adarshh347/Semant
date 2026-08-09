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
import { createMockCorpusClient } from '../inquiryCorpus/corpusClient.js';

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

const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];

// One page of two, one of them annotated — the picker must not treat them differently.
const PAGES = [{
    posts: [
        {
            id: 'post_altes_front', photo_url: '/x.jpg', region_annotations: [],
            text_blocks: [{ content: 'Lustgarten front' }],
        },
        {
            id: 'post_altes_rotunda', photo_url: '/y.jpg', region_annotations: [{}],
            text_blocks: [{ content: 'Rotunda' }],
        },
    ],
    total_pages: 1,
}];

async function type(el, value) {
    const proto = el.tagName === 'TEXTAREA'
        ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    await act(async () => {
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
}

async function mount(props = {}) {
    const client = createMockCorpusClient({ pages: PAGES });
    await act(async () => {
        root.render(<InquiryEntry corpusClient={client} onStart={() => {}} {...props} />);
    });
    return client;
}

describe('the entry asks for images and a question, and nothing else', () => {
    it('cannot start without both', async () => {
        await mount();
        expect($('.iw-start').disabled).toBe(true);
        await act(async () => { $('.ic-tile').click(); });
        expect($('.iw-start').disabled).toBe(true);          // still no question
        await type($('.iw-prompt'), 'how does it gather?');
        expect($('.iw-start').disabled).toBe(false);
    });

    it('a whitespace-only prompt is not a question', async () => {
        await mount();
        await act(async () => { $('.ic-tile').click(); });
        await type($('.iw-prompt'), '   ');
        expect($('.iw-start').disabled).toBe(true);
    });

    it('offers every image identically — no annotation gate, no filter, nothing disabled', async () => {
        await mount();
        // One post carries a region and one carries none. Neither is excluded, ordered differently
        // or disabled: the plan's Phase-1 exit is "select existing images and enter any prompt",
        // and a gate here would reintroduce the precondition the design removed. The mark COUNT is
        // shown as provenance now — knowing what you are about to read is not a precondition for
        // reading it — so the assertion is about selectability rather than about the word.
        expect($$('.ic-tile').length).toBe(2);
        expect($$('.ic-tile[disabled]').length).toBe(0);
        expect($$('.ic-tile').every((t) => t.getAttribute('aria-pressed') === 'false')).toBe(true);
    });

    it('passes the selection, the trimmed prompt and the mode through', async () => {
        const onStart = vi.fn();
        await mount({ onStart });
        await act(async () => { $$('.ic-tile')[0].click(); });
        await act(async () => { $$('.ic-tile')[1].click(); });
        await type($('.iw-prompt'), '  what does the threshold do?  ');
        await act(async () => { $('[data-mode="step"]').click(); });
        await act(async () => { $('.iw-start').click(); });

        expect(onStart).toHaveBeenCalledWith(expect.objectContaining({
            imageIds: ['post_altes_front', 'post_altes_rotunda'],
            prompt: 'what does the threshold do?',
            mode: 'step',
        }));
        // the posts travel with the ids, so the session header can name what was read
        expect(onStart.mock.calls[0][0].posts.map((p) => p.id))
            .toEqual(['post_altes_front', 'post_altes_rotunda']);
    });

    it('toggles a selection off again', async () => {
        const onStart = vi.fn();
        await mount({ onStart });
        await act(async () => { $$('.ic-tile')[0].click(); });
        await act(async () => { $$('.ic-tile')[0].click(); });
        await type($('.iw-prompt'), 'q');
        expect($('.iw-start').disabled).toBe(true);
        expect($$('.ic-tile')[0].getAttribute('aria-pressed')).toBe('false');
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
        expect($('.ic-grid').getAttribute('aria-label')).toBe('Archive images');
        expect($('.ic-search-label').getAttribute('for')).toBe('ic-search');
    });

    it('uses real buttons, so tab order and Enter come for free', async () => {
        await mount();
        for (const el of [...$$('.ic-tile'), ...$$('.iw-mode'), $('.iw-start')]) {
            expect(el.tagName).toBe('BUTTON');
            expect(el.getAttribute('tabindex')).toBeNull();
        }
        expect($('.iw-start').type).toBe('submit');
    });
});
