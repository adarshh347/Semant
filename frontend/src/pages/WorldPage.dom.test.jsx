/**
 * WAVE4 — the front door, mounted. The lies a landing page would tell.
 *
 * A landing page is the one place a person forms their idea of what they are looking at, so it is
 * the cheapest place in the system to undo three waves of care in a sentence. Four failures, made
 * runnable:
 *
 *   1. overselling — "the world Semant has built" where the truth is "nothing is committed"
 *   2. a hardcoded liveness claim — a door that fails when opened
 *   3. an unreachable surface rendered as a dimmer link rather than as not-a-door
 *   4. restructuring the nav the five views each added an entry to
 *
 * No testing-library — plain DOM against a real root, the shape the other `.dom.test.jsx` suites
 * use. `fetch` is stubbed per test, because what this page says depends entirely on what the
 * ledger answers.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import WorldPage from './WorldPage.jsx';

let container;
let root;
let realFetch;

const ok = (body) => Promise.resolve({ ok: true, json: async () => body });
const fail = () => Promise.resolve({ ok: false, json: async () => ({}) });

/** Every probe answers; the curator queue reports `total` for the filter it was given. */
function stubAll({ proposed = 13, committed = 0, unreachable = [] } = {}) {
    global.fetch = vi.fn((url) => {
        const path = String(url);
        if (unreachable.some((frag) => path.includes(frag))) return fail();
        if (path.includes('/curator/queue')) {
            return ok({ total: path.includes('committed=true') ? committed : proposed,
                        proposals: [], filter: {} });
        }
        return ok({});
    });
}

async function mount() {
    await act(async () => {
        // `<Link>` needs a router in context; the page is mounted the way the app mounts it.
        root.render(<MemoryRouter><WorldPage /></MemoryRouter>);
    });
    // let the probe promises settle
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

beforeEach(() => {
    realFetch = global.fetch;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
    global.fetch = realFetch;
    vi.restoreAllMocks();
});

describe('the front door does not oversell', () => {
    it('states that nothing has been committed, when nothing has', async () => {
        stubAll({ proposed: 13, committed: 0 });
        await mount();

        const text = container.textContent;
        expect(text).toContain('13');
        expect(text).toMatch(/Nothing has been accepted yet/i);
        // The claim it must never make.
        expect(text).not.toMatch(/the world Semant has built/i);
    });

    it('reads the number from the ledger rather than asserting it', async () => {
        // If someone commits something, the page says so without being edited.
        stubAll({ proposed: 40, committed: 7 });
        await mount();

        const text = container.textContent;
        expect(text).toContain('7');
        expect(text).not.toMatch(/Nothing has been accepted yet/i);
    });

    it('names both statuses, because they are not the same thing', async () => {
        stubAll();
        await mount();
        const text = container.textContent;
        expect(text).toContain('measured');
        expect(text).toContain('interpretive');
        expect(text).toContain('proposed');
        expect(text).toContain('committed');
    });

    it('says only a person commits', async () => {
        stubAll();
        await mount();
        expect(container.textContent).toMatch(/Nothing commits on its own/i);
    });
});

describe('liveness is probed, not declared', () => {
    it('links a surface whose backend answers', async () => {
        stubAll();
        await mount();
        const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
        expect(hrefs).toContain('/scene');
        expect(hrefs).toContain('/curator');
    });

    it('does not render a link for a surface that is not answering', async () => {
        stubAll({ unreachable: ['/society/'] });
        await mount();

        const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
        expect(hrefs).not.toContain('/society');
        // and it is present as a card, saying what it is
        expect(container.textContent).toContain('Society');
        expect(container.textContent).toMatch(/not answering/i);
    });

    it('marks an unreachable surface as not-a-door rather than a dim link', async () => {
        stubAll({ unreachable: ['/society/'] });
        await mount();

        const dead = container.querySelector('.world-card.is-unreachable');
        expect(dead).toBeTruthy();
        expect(dead.querySelector('a')).toBeNull();
        expect(dead.querySelector('[aria-disabled="true"]')).toBeTruthy();
    });

    it('probes every surface it advertises', async () => {
        stubAll();
        await mount();
        const called = global.fetch.mock.calls.map(([url]) => String(url));
        for (const fragment of ['/scene/', '/cognition/', '/society/', '/constellation/',
                                '/curator/']) {
            expect(called.some((u) => u.includes(fragment))).toBe(true);
        }
    });
});

describe('it is read-only', () => {
    it('issues no write of any kind', async () => {
        stubAll();
        await mount();
        for (const [, init] of global.fetch.mock.calls) {
            const method = String((init && init.method) || 'GET').toUpperCase();
            expect(['GET', 'HEAD']).toContain(method);
        }
    });
});
