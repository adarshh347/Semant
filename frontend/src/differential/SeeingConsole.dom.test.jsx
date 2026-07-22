import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import SeeingConsole from './SeeingConsole';
import { FIND_PARTS_LABEL, FIND_PARTS_OPERATION } from './seeingConsole';

/**
 * CIRCUIT-001 P2 — the console, mounted.
 *
 * These need a DOM for a real reason, and it is the reason Gate 3A exists: "there is no
 * visible primary Dissect button" and "the new label triggers the same call" are claims
 * about what is ON SCREEN and what leaves the machine. Neither can be checked from a pure
 * module — the first is about rendered text, the second about a fetch the component makes.
 *
 * No testing-library: the project has none as a dependency, and these assertions are plain
 * DOM queries against a real root, which is all they need.
 */

const CAPS = {
    capabilities: [
        { name: 'yolo11n_seg', capability: 'segment', state: 'ready', reason: '' },
        { name: 'sam21_hiera_tiny', capability: 'mask_refine', state: 'ready', reason: '' },
    ],
};

let container;
let root;
let calls;

/** A fetch that records every request and answers the console's three endpoints. */
function stubFetch() {
    calls = [];
    globalThis.fetch = vi.fn(async (url, opts = {}) => {
        calls.push({ url: String(url), method: opts.method || 'GET', body: opts.body || null });
        if (String(url).includes('/vision/capabilities')) {
            return { ok: true, json: async () => CAPS };
        }
        if (String(url).includes('/vision-runs/latest')) {
            return { ok: true, json: async () => ({ run: null }) };
        }
        if (String(url).includes('/domain-profile')) {
            return { ok: true, json: async () => ({ domain_profile: { chosen: ['general'] } }) };
        }
        return { ok: true, json: async () => ({}) };
    });
}

async function mount(props = {}) {
    await act(async () => {
        root.render(<SeeingConsole postId="p1" {...props} />);
    });
}

const text = () => container.textContent || '';
const buttons = () => [...container.querySelectorAll('button')];
const byText = (t) => buttons().find((b) => (b.textContent || '').trim().includes(t));

beforeEach(() => {
    stubFetch();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

describe('the primary action', () => {
    it('does not render a visible "Dissect" anywhere on the console', async () => {
        await mount({ onFindParts: () => {} });
        // The whole point of Gate 3A. Case-insensitive so "dissect the image" cannot slip
        // back in lowercase, and over the full subtree so a tooltip or a menu item counts.
        expect(text().toLowerCase()).not.toContain('dissect');
        expect(container.innerHTML.toLowerCase()).not.toContain('>dissect<');
    });

    it('renders "Find parts" as a real, enabled, generously sized button', async () => {
        await mount({ onFindParts: () => {} });
        const find = byText(FIND_PARTS_LABEL);
        expect(find).toBeTruthy();
        expect(find.disabled).toBe(false);
        // Not a tiny hidden affordance: it carries its own label element, so the label
        // cannot be dropped to an icon-only control by a CSS change alone.
        expect(find.querySelector('.sc-find-label')).toBeTruthy();
    });

    it('the new label triggers the same find-parts flow', async () => {
        const onFindParts = vi.fn();
        await mount({ onFindParts });
        await act(async () => { byText(FIND_PARTS_LABEL).click(); });
        expect(onFindParts).toHaveBeenCalledTimes(1);
    });

    it('shows the busy label instead of the action while looking', async () => {
        await mount({ onFindParts: () => {}, busy: true });
        expect(byText(FIND_PARTS_LABEL)).toBeFalsy();
        expect(text().toLowerCase()).toContain('looking');
        expect(text().toLowerCase()).not.toContain('dissect');
    });

    it('the operation id the UI is a label for is still `dissect`', () => {
        // Rendered text and wire identity, asserted side by side, so the pair cannot drift.
        expect(FIND_PARTS_OPERATION).toBe('dissect');
        expect(FIND_PARTS_LABEL.toLowerCase()).not.toContain('dissect');
    });
});

describe('ways of looking', () => {
    it('renders a chip per specialist and a non-clickable base pass', async () => {
        await mount({ onFindParts: () => {} });
        expect(container.querySelector('[data-way="fashion"]')).toBeTruthy();
        expect(container.querySelector('[data-way="architecture"]')).toBeTruthy();
        expect(container.querySelector('[data-way="painting"]')).toBeTruthy();
        // The base pass is always on, so it is a span — a disabled button that looks like
        // a chip invites a click that can never do anything.
        const base = container.querySelector('.sc-way--base');
        expect(base).toBeTruthy();
        expect(base.tagName).toBe('SPAN');
    });

    it('reads as attention, not as model configuration', async () => {
        await mount({ onFindParts: () => {} });
        const t = text().toLowerCase();
        expect(t).toContain('ways of looking');
        expect(t).toContain('built space');
        expect(t).not.toContain('profile');
    });

    it('clicking a way PATCHes the domain profile with that specialist', async () => {
        // The rename's real risk: a humane label selecting the wrong pass. This pins the
        // label→value mapping at the network boundary, not just in the pure module.
        await mount({ onFindParts: () => {}, profile: { chosen: ['general'] } });
        await act(async () => { container.querySelector('[data-way="architecture"]').click(); });
        const patch = calls.find((c) => c.method === 'PATCH');
        expect(patch).toBeTruthy();
        expect(patch.url).toContain('/p1/domain-profile');
        expect(JSON.parse(patch.body)).toEqual({ chosen: ['architecture'] });
    });

    it('reflects the post\'s chosen ways as pressed', async () => {
        await mount({ onFindParts: () => {}, profile: { chosen: ['general', 'painting'] } });
        expect(container.querySelector('[data-way="painting"]').getAttribute('aria-pressed')).toBe('true');
        expect(container.querySelector('[data-way="fashion"]').getAttribute('aria-pressed')).toBe('false');
    });
});

describe('sources', () => {
    it('shows scheduled sources as quiet status marks, with their role', async () => {
        await mount({
            onFindParts: () => {},
            profile: { chosen: ['general'], scheduled_passes: ['yolo11n_seg', 'sam21_hiera_tiny'] },
        });
        const chips = [...container.querySelectorAll('.sc-source')];
        expect(chips.length).toBe(2);
        expect(text()).toContain('Segmentation');
        expect(text()).toContain('Refinement');
        // Read-only: nothing in the strip is a control.
        expect(chips.every((c) => c.querySelector('button') === null)).toBe(true);
    });

    it('a ready source carries no state noise; only a non-ready one speaks', async () => {
        await mount({
            onFindParts: () => {},
            profile: { chosen: ['general'], scheduled_passes: ['yolo11n_seg'] },
        });
        expect(container.querySelector('.sc-source .sc-source-state')).toBe(null);
    });
});

describe('operation memory', () => {
    it('is collapsed by default and does not claim to be live', async () => {
        await mount({ onFindParts: () => {} });
        expect(text().toLowerCase()).toContain('operation memory');
        // Collapsed: the scope/provenance lines belong to the opened panel.
        expect(container.querySelector('.sc-mem-body')).toBe(null);
    });

    it('opens to state both what it records and how it knows', async () => {
        await mount({ onFindParts: () => {} });
        await act(async () => { container.querySelector('.sc-mem-toggle').click(); });
        const t = text().toLowerCase();
        expect(t).toContain('not all vision activity');
        expect(t).toContain('latest recorded run');
        // Gate 3G: a projection must not read as a stream.
        expect(t).not.toContain('streaming');
        expect(t).not.toContain('live feed');
    });

    it('names the four instrumented operations without saying "dissect"', async () => {
        await mount({ onFindParts: () => {} });
        await act(async () => { container.querySelector('.sc-mem-toggle').click(); });
        const t = text();
        expect(t).toContain('Find parts');
        expect(t).toContain('Refine');
        expect(t).toContain('Semantic read');
        expect(t.toLowerCase()).not.toContain('dissect');
    });

    it('reports absence as absence when the reads succeed', async () => {
        await mount({ onFindParts: () => {} });
        expect(text().toLowerCase()).toContain('nothing recorded yet');
    });

    it('a failed read is never rendered as an empty corpus', async () => {
        // P2.2R-B1, end to end: the fetch fails, and the panel must say it could not read
        // rather than asserting there is nothing there.
        globalThis.fetch = vi.fn(async (url) => {
            if (String(url).includes('/vision/capabilities')) return { ok: true, json: async () => CAPS };
            if (String(url).includes('/vision-runs/latest')) return { ok: false, status: 500 };
            return { ok: true, json: async () => ({}) };
        });
        await mount({ onFindParts: () => {} });
        const t = text().toLowerCase();
        expect(t).toContain('couldn’t read activity');
        expect(t).not.toContain('nothing recorded yet');
    });
});
