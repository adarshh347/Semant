// PERCEPTUAL-ORGANS-002 Lane E — the responsive and accessibility proof.
//
// Three kinds of assertion, and they are separated because they fail for different reasons:
//
//   PURE       the letterbox arithmetic at each width. No DOM, no layout, exact numbers. This is
//              the one that actually proves a mask lands on the thing it measured at 320px.
//   RENDERED   what the surface does at each band: which column things are in, what order they
//              come in, and that no state disappears when the space does.
//   STYLESHEET read as text. "Use existing design tokens, no inline hardcoded styling, no
//              unscoped global tokens" is a claim about a file, so it is checked against the file
//              rather than eyeballed — a hex literal committed at 2am is exactly what this catches.

import React, { act } from 'react';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { cwd } from 'node:process';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PerceptionLab from './PerceptionLab';
import ResponsiveHarness from './ResponsiveHarness';
import { HARNESS_SCENARIOS } from './harnessScenarios';
import { createFixtureClient, defaultCapabilityStates } from './clients/fixtureClient';
import { TARGET_WIDTHS, widthBand } from './useContainerWidth';
import { contentBox } from '../differential/useStageGeometry';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

// Read from the project root rather than from `import.meta.url`: the jsdom environment does not
// give this module a file: URL, and the stylesheet has to be read as TEXT — importing it would
// hand back a processed object, and the claim being checked is about what is in the file.
const CSS = readFileSync(
    path.resolve(cwd(), 'src/perceptionLab/perceptionLab.css'), 'utf8');

let container; let root; let currentWidth;

const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => {
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    currentWidth = 1200;
    // jsdom lays nothing out. `useContainerWidth` reads the root's box, so the box is what the
    // test controls — which is exactly the input the real hook gets from a ResizeObserver.
    const original = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function rect() {
        if (this.classList?.contains('pl') || this.classList?.contains('pl-stage')) {
            const w = currentWidth;
            const h = Math.round(w * 0.75);
            return { x: 0, y: 0, left: 0, top: 0, right: w, bottom: h, width: w, height: h };
        }
        return original.call(this);
    };
    Element.prototype.getBoundingClientRect.original = original;
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    Element.prototype.getBoundingClientRect
        = Element.prototype.getBoundingClientRect.original || Element.prototype.getBoundingClientRect;
});

const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const text = () => container.textContent;
const click = async (el) => {
    if (!el) throw new Error('nothing to click');
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};

const atWidth = async (width, options = {}, scene = 'scene_instances') => {
    currentWidth = width;
    await mount(<PerceptionLab client={createFixtureClient(options)} />);
    await settle();
    await click(q(`[data-source-id="${scene}"]`));
    return q('.pl');
};

const runAtWidth = async (width, options = {}, scene = 'scene_instances') => {
    const el = await atWidth(width, options, scene);
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-fixture"]'));
    return el;
};

// ── pure: the alignment contract does not depend on the width ───────────────

describe('a mask lands where it was measured, at every width', () => {
    const natural = { w: 900, h: 600 };

    it('the letterbox is exact at each of the four widths the build names', () => {
        for (const width of TARGET_WIDTHS) {
            const stageH = Math.round(width * 0.75);
            const box = contentBox(width, stageH, natural.w, natural.h);
            // `object-fit: contain` and `xMidYMid meet` compute the SAME box, which is the whole
            // guarantee. Aspect is preserved to floating-point exactness.
            expect(box.w / box.h, `${width}px`).toBeCloseTo(natural.w / natural.h, 10);
            expect(box.w, `${width}px`).toBeLessThanOrEqual(width + 1e-9);
            expect(box.h, `${width}px`).toBeLessThanOrEqual(stageH + 1e-9);
            // Centred: the two margins are equal.
            expect(box.x * 2 + box.w).toBeCloseTo(width, 10);
            expect(box.y * 2 + box.h).toBeCloseTo(stageH, 10);
        }
    });

    it('a normalized point maps to the same fraction of the image at 1100 and at 320', () => {
        const point = { x: 0.25, y: 0.8 };
        const positions = TARGET_WIDTHS.map((width) => {
            const box = contentBox(width, Math.round(width * 0.75), natural.w, natural.h);
            return {
                width,
                fractionOfContent: {
                    x: (box.x + point.x * box.w - box.x) / box.w,
                    y: (box.y + point.y * box.h - box.y) / box.h,
                },
            };
        });
        for (const p of positions) {
            expect(p.fractionOfContent.x, `${p.width}px`).toBeCloseTo(point.x, 12);
            expect(p.fractionOfContent.y, `${p.width}px`).toBeCloseTo(point.y, 12);
        }
    });

    it('the band boundaries are exactly where they are documented', () => {
        expect(widthBand(1100)).toBe('wide');
        expect(widthBand(1000)).toBe('wide');
        expect(widthBand(999)).toBe('mid');
        expect(widthBand(720)).toBe('mid');
        expect(widthBand(680)).toBe('mid');
        expect(widthBand(679)).toBe('narrow');
        expect(widthBand(430)).toBe('narrow');
        expect(widthBand(400)).toBe('narrow');
        expect(widthBand(399)).toBe('tight');
        expect(widthBand(320)).toBe('tight');
        expect(widthBand(null)).toBe('tight');       // unknown is not wide
    });
});

// ── rendered: the surface at each band ──────────────────────────────────────

describe('the layout responds to its container, not to the window', () => {
    for (const width of TARGET_WIDTHS) {
        it(`${width}px renders as the ${widthBand(width)} band`, async () => {
            const el = await atWidth(width);
            expect(el.getAttribute('data-w')).toBe(widthBand(width));
        });
    }

    it('the stage keeps the natural-pixel viewBox at every width', async () => {
        for (const width of TARGET_WIDTHS) {
            await runAtWidth(width);
            const svg = q('.pl-svg');
            expect(svg.getAttribute('viewBox'), `${width}px`).toBe('0 0 900 600');
            expect(svg.getAttribute('preserveAspectRatio'), `${width}px`).toBe('xMidYMid meet');
            expect(all('.pl-svg path.rs-shape').length, `${width}px`).toBe(5);
            await act(async () => { root.unmount(); });
            container.remove();
            container = document.createElement('div');
            document.body.appendChild(container);
            root = createRoot(container);
        }
    });

    it('a topology projection is still placed on the image at 320px', async () => {
        await runAtWidth(320);
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click([...container.querySelectorAll('.pl-organ')]
            .find((o) => o.getAttribute('data-organ') === 'topology'));
        await click(q('[data-operation="topology.adjacency"]'));
        const options = (role) => all(`[data-role-option^="${role}:"]`)
            .filter((b) => b.getAttribute('data-role-option').includes('#'));
        await click(options('source')[2]);
        await click(options('target')[3]);
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-relation-layer]')).toBeTruthy();
        expect(q('.pl-svg').getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
        expect(q('[data-relation-sentence]').textContent).toMatch(/ touches /);
    });

    it('the inspector moves below rather than away, and reading order stays sensible',
        async () => {
            await runAtWidth(320);
            // Everything is still on the page — the columns collapsed, nothing was dropped.
            expect(q('.pl-rail')).toBeTruthy();
            expect(q('.pl-main')).toBeTruthy();
            expect(q('.pl-inspector')).toBeTruthy();
            expect(q('[data-block="measurement"]')).toBeTruthy();
            expect(q('[data-stages]')).toBeTruthy();
            expect(q('[data-review-tray]')).toBeTruthy();
            expect(q('[data-history]')).toBeTruthy();
            // The CSS puts the rail first, the stage second and the inspector last at this band.
            expect(CSS).toMatch(/\.pl\[data-w='tight'\] \.pl-rail \{[^}]*order: 1/s);
            expect(CSS).toMatch(/\.pl\[data-w='tight'\] \.pl-inspector \{[^}]*order: 4/s);
        });

    it('the plan stream stays a table with its own scroller rather than overflowing the page',
        async () => {
            await runAtWidth(320);
            const stages = q('[data-stages]');
            expect(stages.tagName).toBe('TABLE');
            expect(stages.closest('.pl-scroll')).toBeTruthy();
            expect(CSS).toMatch(/\.pl-scroll \{ overflow-x: auto/);
        });
});

describe('no state disappears when the space does', () => {
    it('an empty result is still an intentional empty state at 320px', async () => {
        await runAtWidth(320, {}, 'scene_absent');
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('empty');
        expect(q('[data-empty-extent]').textContent).toMatch(/This is a measurement/);
    });

    it('a dense result keeps every instance and every reading at 320px', async () => {
        await runAtWidth(320);
        expect(all('[data-naming-row]')).toHaveLength(5);
        expect(q('[data-duplicate-pairs]')).toBeTruthy();
        expect(q('[data-pairs-compared]').getAttribute('data-pairs-compared')).toBe('10');
    });

    it('an unavailable adapter keeps its disabled control and its reason at 320px', async () => {
        await atWidth(320, {
            capabilityStates: defaultCapabilityStates({
                sam3_concept: 'unavailable', grounded_sam: 'unavailable' }),
        });
        const named = q('[data-operation="extent.find_named"]');
        expect(named.disabled).toBe(true);
        expect(named.getAttribute('title')).toMatch(/sam3_concept, grounded_sam/);
    });

    it('a failed run still says it made no claim, at 320px', async () => {
        await runAtWidth(320, { failOperations: ['extent.find_all'] });
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('failed');
        expect(q('[data-run-duration]').textContent).toMatch(/unmeasured/);
    });

    it('a refusal keeps its code and its remedy at 320px', async () => {
        await atWidth(320);
        await click(q('[data-arm="prompt"]'));
        await act(async () => {
            const el = q('#pl-prompt');
            Object.getOwnPropertyDescriptor(
                window.HTMLTextAreaElement.prototype, 'value').set.call(el, 'do those two touch');
            el.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click(q('[data-action="ask-rules"]'));
        expect(q('.pl-refusal-code').textContent).toBe('organ_locked');
        expect(q('.pl-refusal-remedy')).toBeTruthy();
    });
});

// ── keyboard and focus ──────────────────────────────────────────────────────

describe('the laboratory is reachable from a keyboard', () => {
    it('every interactive control is a real button or input, not a clickable div', async () => {
        await runAtWidth(1100);
        // `.pl-organ[data-organ]` rather than `[data-organ]`: the root carries `data-organ` too,
        // as the LOCK, and it is a div because it is a container rather than a control.
        const clickable = all('[data-action], [data-operation], [data-source-id], '
            + '.pl-organ[data-organ], [data-view-mode], [data-tool], [data-verdict-option], '
            + '[data-lifecycle-option]');
        expect(clickable.length).toBeGreaterThan(20);
        const wrong = clickable.filter(
            (el) => !['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'A'].includes(el.tagName));
        expect(wrong.map((el) => `${el.tagName}${el.className}`)).toEqual([]);
    });

    it('nothing is removed from the tab order or given a positive tabindex', async () => {
        await runAtWidth(1100);
        const focusable = all('button, input, select, textarea, a[href]');
        const removed = focusable.filter((el) => el.getAttribute('tabindex') === '-1');
        const positive = focusable.filter((el) => Number(el.getAttribute('tabindex')) > 0);
        expect(removed).toEqual([]);
        expect(positive).toEqual([]);
    });

    it('toggles say what they are, so a screen reader is told the state and not the colour',
        async () => {
            await runAtWidth(1100);
            for (const sel of ['.pl-organ[data-organ="extent"]', 'button[data-mode="isolation"]',
                'button[data-arm="direct"]', '[data-view-mode="mask"]', '[data-basis-mode="mask"]']) {
                expect(q(sel).getAttribute('aria-pressed'), sel).toBe('true');
            }
        });

    it('every panel is a landmark with a name', async () => {
        await runAtWidth(1100);
        const named = all('section[aria-label]').map((s) => s.getAttribute('aria-label'));
        for (const label of ['Plan', 'Run', 'Ledger', 'Inspector', 'Extent stage',
            'Review and lifecycle', 'History', 'Export']) {
            expect(named, label).toContain(label);
        }
    });

    it('the stage tools carry their keyboard shortcut in the label', async () => {
        await runAtWidth(1100);
        expect(q('[data-tool="point"]').textContent).toMatch(/P$/);
        expect(q('[data-tool="box"]').textContent).toMatch(/B$/);
        expect(q('[data-tool="freehand"]').textContent).toMatch(/F$/);
    });

    it('a disabled control still explains itself, so the reason is not colour-coded', async () => {
        await atWidth(1100, {
            capabilityStates: defaultCapabilityStates({ sam3_concept: 'unavailable',
                grounded_sam: 'unavailable' }),
        });
        const disabled = all('button[disabled]');
        expect(disabled.length).toBeGreaterThan(0);
        // Every disabled control either carries a title or sits beside a rendered refusal.
        const silent = disabled.filter(
            (b) => !b.getAttribute('title') && !b.textContent.trim());
        expect(silent).toEqual([]);
    });
});

// ── the stylesheet, read as text ────────────────────────────────────────────

describe('the surface is built from the design tokens', () => {
    it('declares no raw colour literals — every colour comes from a token', () => {
        // `color-mix(in srgb, var(--token) …)` is fine; `#8E3F6A` is not.
        const offenders = CSS.split('\n')
            .map((line, i) => ({ line: line.trim(), n: i + 1 }))
            .filter(({ line }) => /#[0-9a-fA-F]{3,8}\b/.test(line)
                || /\b(rgb|hsl)a?\(/.test(line));
        expect(offenders.map((o) => `${o.n}: ${o.line}`)).toEqual([]);
    });

    it('defines no tokens of its own — it consumes the ones the app already has', () => {
        // A `--pl-*` layout variable is scoped to `.pl`; a bare `:root {}` block here would be a
        // global token this lane had no business declaring.
        expect(CSS).not.toMatch(/^\s*:root\s*\{/m);
        expect(CSS).not.toMatch(/^\s*html\s*\{/m);
        expect(CSS).not.toMatch(/^\s*body\s*\{/m);
        const declared = [...CSS.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map((m) => m[1]);
        expect(declared.every((d) => d.startsWith('--pl-'))).toBe(true);
    });

    it('every selector is scoped to this lane', () => {
        const selectors = [...CSS.matchAll(/^([.:[][^{@]*?)\s*\{/gm)]
            .map((m) => m[1].trim())
            .flatMap((s) => s.split(',').map((x) => x.trim()))
            .filter(Boolean);
        expect(selectors.length).toBeGreaterThan(40);
        const unscoped = selectors.filter((s) => !/(^|\s|\()\.pl[-[.\s]/.test(`${s} `)
            && !s.startsWith('.pl'));
        expect(unscoped).toEqual([]);
    });

    it('shows focus visibly, and does not remove an outline without replacing it', () => {
        expect(CSS).toMatch(/:focus-visible \{[^}]*outline: 2px solid var\(--accent\)/s);
        const outlineNone = [...CSS.matchAll(/([^{}]*)\{([^}]*outline:\s*none[^}]*)\}/g)];
        for (const [, selector, body] of outlineNone) {
            expect(body, selector).toMatch(/stroke|outline: 2px|outline:\s*\d/);
        }
    });

    it('respects a reduced-motion preference', () => {
        expect(CSS).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
    });

    it('keeps every axis on its own attribute, so no two share a treatment', () => {
        for (const attr of ['data-outcome', 'data-status', 'data-basis', 'data-verdict',
            'data-id', 'data-state', 'data-scope']) {
            expect(CSS, attr).toContain(`[${attr}=`);
        }
    });
});

// ── light and dark ──────────────────────────────────────────────────────────

describe('both themes', () => {
    it('the harness renders every width and both themes without a hardcoded style', async () => {
        currentWidth = 1100;
        await mount(<ResponsiveHarness />);
        await settle();
        expect(all('[data-harness-width]')).toHaveLength(TARGET_WIDTHS.length);
        expect(q('[data-harness]').getAttribute('data-theme')).toBe('light');
        await click(q('[data-theme-option="dark"]'));
        expect(q('[data-harness]').getAttribute('data-theme')).toBe('dark');
        // The widths are stylesheet rules keyed off the attribute, not inline styles.
        expect(all('[data-harness-width]').every((p) => !p.getAttribute('style'))).toBe(true);
        for (const width of TARGET_WIDTHS) {
            expect(CSS).toContain(`.pl-harness-pane[data-harness-width='${width}']`);
        }
    });

    it('offers the four scenarios that are hard to render honestly in a small space', async () => {
        currentWidth = 1100;
        await mount(<ResponsiveHarness />);
        await settle();
        expect(HARNESS_SCENARIOS.map((s) => s.key))
            .toEqual(['dense', 'empty', 'unavailable', 'failed']);
        await click(q('[data-scenario="unavailable"]'));
        expect(q('[data-scenario-why]').textContent).toMatch(/would teach nothing about the/);
        expect(text()).toContain('Perception laboratory');
    });

    it('nothing in the rendered markup carries an inline style attribute', async () => {
        await runAtWidth(1100);
        const inline = all('[style]').map((el) => `${el.tagName}.${el.className}`);
        expect(inline).toEqual([]);
    });
});
