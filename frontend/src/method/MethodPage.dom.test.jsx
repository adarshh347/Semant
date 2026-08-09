/**
 * /method, mounted.
 *
 * The claims here are about what is ON SCREEN, which is why this needs a DOM.
 * Two of them carry the page:
 *
 *   1. The route resolves and the markdown becomes real elements. A `?raw`
 *      import that silently failed, or a markdown renderer that did not run,
 *      both still "render" — as the article's source text printed literally.
 *   2. The rehearsal loop is visible AS A LOOP. Its meaning is carried by the
 *      line breaks, one step per line. Markdown would collapse those seven
 *      lines into a single paragraph if the fenced block were ever lost, and
 *      the passage would still look fine while saying something else.
 *
 * No testing-library — plain DOM against a real root, the shape the other
 * `.dom.test.jsx` suites use.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import MethodPage from './MethodPage.jsx';

let container;
let root;
let realFetch;

// The seven steps, in the order the article states them.
const LOOP = [
    'theoretical proposition',
    '→ minimal capability',
    '→ bounded live rehearsal',
    '→ inspect evidence and failure',
    '→ preserve the receipt',
    '→ revise the theory and the infrastructure',
    '→ rehearse again',
];

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // This page must not talk to anything. Any call is a failure, so make one
    // loud rather than letting it fall through to a real request.
    realFetch = globalThis.fetch;
    globalThis.fetch = vi.fn(() => { throw new Error('MethodPage must not fetch'); });
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    globalThis.fetch = realFetch;
});

/** Mount through the real route path, so this covers routing and not just the component. */
async function mountRoute(path = '/method') {
    await act(async () => {
        root.render(
            <MemoryRouter initialEntries={[path]}>
                <Routes>
                    <Route path="method" element={<MethodPage />} />
                </Routes>
            </MemoryRouter>,
        );
    });
}

const text = () => container.textContent || '';

describe('/method — the route renders the article', () => {
    it('resolves at /method and renders the article title as a heading', async () => {
        await mountRoute();
        const h1 = container.querySelector('h1');
        expect(h1).toBeTruthy();
        expect(h1.textContent.trim()).toBe('Semant Is Built by Rehearsal');
    });

    it('renders the markdown as real elements, not its source text', async () => {
        await mountRoute();
        expect(container.querySelectorAll('.writing-body p').length).toBeGreaterThan(8);
        // the raw markers never reach the screen
        expect(text()).not.toContain('# Semant Is Built');
        expect(text()).not.toContain('```');
        expect(text()).not.toContain('> Can this organ');
    });

    it('renders the three rehearsal questions as blockquotes', async () => {
        await mountRoute();
        const quotes = [...container.querySelectorAll('.writing-body blockquote')];
        expect(quotes.length).toBe(3);
        expect(quotes[0].textContent).toContain('distinguish a fold from the garment');
    });

    it('sets a clear page title', async () => {
        await mountRoute();
        expect(document.title).toBe('Method — Semant');
    });

    it('makes no network call — the article is static', async () => {
        await mountRoute();
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });
});

describe('/method — the rehearsal loop', () => {
    it('renders the loop in its own pre-formatted block', async () => {
        await mountRoute();
        const pre = container.querySelector('pre.method-loop');
        expect(pre).toBeTruthy();
    });

    it('shows every step of the loop', async () => {
        await mountRoute();
        const pre = container.querySelector('pre.method-loop');
        for (const step of LOOP) {
            expect(pre.textContent, step).toContain(step);
        }
    });

    it('keeps the steps in order, one per line', async () => {
        // The line breaks ARE the loop. If the fenced block were lost, markdown
        // would join these into one paragraph — every step still "present",
        // the sequence gone.
        await mountRoute();
        const pre = container.querySelector('pre.method-loop');
        const lines = pre.textContent.split('\n').map((l) => l.trim()).filter(Boolean);
        expect(lines).toEqual(LOOP);
    });

    it('states the loop inside the article body, after its lead-in', async () => {
        await mountRoute();
        const body = container.querySelector('.writing-body');
        const pre = container.querySelector('pre.method-loop');
        expect(body.contains(pre)).toBe(true);
        expect(text()).toContain('The development loop is:');
        expect(text().indexOf('The development loop is:'))
            .toBeLessThan(text().indexOf('theoretical proposition'));
    });
});
