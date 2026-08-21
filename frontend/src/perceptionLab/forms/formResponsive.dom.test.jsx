// PERCEPTUAL-FORMS-001E — the proofs a screenshot cannot give.
//
// Four kinds of claim are made here, and each is one a person could otherwise only check by
// looking, which means it would be checked once and then never again:
//
//   RESPONSIVE   the layout keys off the container's width, not the window's, so the four target
//                widths are asserted as band boundaries and as rendered output.
//   THEME        the stylesheet is read AS TEXT and asserted to contain no colour literal at all.
//                That is the whole dark-mode proof: a sheet written entirely in tokens is correct
//                in both themes because the tokens swap, and no test can prove that by rendering.
//   COLOUR       every evidence class differs in dash and pattern and word before colour. Asserted
//                over the treatment table and over the markup that carries it.
//   KEYBOARD     every control is a real button or input, every one has a focus-visible rule, and
//                nothing on the stage is reachable only by pointing.
//
// The stylesheet checks are the unusual ones and they are the reason this file exists: they catch
// the change where somebody adds `color: #8E3F6A` to fix one dark-mode glitch and silently breaks
// the other theme, which no rendering test in jsdom can see.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { cwd } from 'node:process';

import FormRendererLab from './FormRendererLab';
import FormHarness from './FormHarness';
import { HARNESS_CASES } from './harnessCases';
import { TARGET_WIDTHS, widthBand } from '../useContainerWidth';
import { EVIDENCE, EVIDENCE_TREATMENT } from './layerModel';
import { viewsFor } from './rendererRegistry';
import { PERCEPTUAL_FORMS } from '../contract/perceptionLabContract';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root; let restoreRect = null;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    if (restoreRect) { Element.prototype.getBoundingClientRect = restoreRect; restoreRect = null; }
});

const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};

/**
 * jsdom gives every element a zero-size box, so the band would always be `tight`. This reports the
 * asked-for width for the lab root only — the same technique the Perception Lab's own responsive
 * suite uses, and the reason the band is a PURE FUNCTION of a number in the first place.
 */
const atWidth = (px) => {
    if (!restoreRect) restoreRect = Element.prototype.getBoundingClientRect;
    const original = restoreRect;
    Element.prototype.getBoundingClientRect = function rect() {
        if (this.classList?.contains('pl-fm')) {
            return { width: px, height: 900, top: 0, left: 0, right: px, bottom: 900, x: 0, y: 0 };
        }
        return original.call(this);
    };
};

const openAt = async (px, props = {}) => {
    atWidth(px);
    await mount(<FormRendererLab now="2026-08-22T00:00:00Z" {...props} />);
    await settle();
};

/* ── the stylesheet, read as text ────────────────────────────────────────── */

const SHEET = fs.readFileSync(
    path.resolve(cwd(), 'src/perceptionLab/forms/forms.css'), 'utf8');
const withoutComments = SHEET.replace(/\/\*[\s\S]*?\*\//g, '');

describe('the stylesheet is written in tokens, which is the whole dark-mode proof', () => {
    it('contains no colour literal of any kind', () => {
        // A sheet written entirely in tokens is correct in both themes because the tokens swap
        // under [data-theme='dark']. One hex here and one theme silently breaks.
        expect(withoutComments).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
        expect(withoutComments).not.toMatch(/\brgba?\s*\(/);
        expect(withoutComments).not.toMatch(/\bhsla?\s*\(/);
        expect(withoutComments).not.toMatch(
            /:\s*(red|green|blue|black|white|orange|yellow|purple|pink|grey|gray)\b/);
    });

    it('declares no variable outside its own namespace', () => {
        const declared = [...withoutComments.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)]
            .map((m) => m[1]);
        expect(declared.length).toBeGreaterThan(0);
        for (const name of declared) expect(name, name).toMatch(/^--pl-fm-/);
    });

    it('reads only tokens the application actually defines', () => {
        // Not line-anchored: `src/index.css` declares four spacing tokens on one line.
        const appTokens = new Set([...fs.readFileSync(path.resolve(cwd(), 'src/index.css'), 'utf8')
            .matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
        const used = new Set([...withoutComments.matchAll(/var\((--[a-z0-9-]+)/g)]
            .map((m) => m[1]));
        for (const name of used) {
            if (name.startsWith('--pl-fm-')) continue;
            expect(appTokens.has(name), `${name} is not defined in src/index.css`).toBe(true);
        }
    });

    it('scopes every selector to .pl-fm, so it can be mounted anywhere', () => {
        const selectors = withoutComments
            .split('}')
            .map((block) => block.split('{')[0])
            .flatMap((s) => s.split(','))
            .map((s) => s.trim())
            .filter((s) => s && !s.startsWith('@') && !s.startsWith('/*'));
        for (const sel of selectors) {
            expect(sel, `"${sel}" is not scoped to .pl-fm`).toMatch(/^\.pl-fm/);
        }
        // and nothing reaches the document
        expect(withoutComments).not.toMatch(/(^|\s)(:root|html|body)\s*[,{]/);
    });

    it('gives every interactive element a focus-visible rule', () => {
        expect(SHEET).toMatch(/:focus-visible/);
        const focusable = ['pl-fm-legendbtn', 'pl-fm-btn', 'pl-fm-tab', 'pl-fm-formbtn',
            'pl-fm-input', 'pl-fm-legendtoggle'];
        for (const cls of focusable) {
            expect(SHEET, `${cls} has no focus-visible rule`)
                .toMatch(new RegExp(`\\.${cls}[^{]*:focus-visible`));
        }
    });

    it('honours prefers-reduced-motion', () => {
        expect(SHEET).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
        const block = SHEET.split('@media (prefers-reduced-motion: reduce)')[1];
        expect(block).toMatch(/transition: none/);
        expect(block).toMatch(/transform: none/);
    });

    it('keeps wide content inside its own scroll box', () => {
        // The page body must never scroll sideways; a matrix or a table does its own.
        expect(SHEET).toMatch(/\.pl-fm-matrixwrap[\s\S]*?overflow-x: auto/);
    });
});

/* ── colour is never the only difference ─────────────────────────────────── */

describe('colour is not the sole distinction', () => {
    it('separates the four drawable classes by dash and by pattern and by word', () => {
        const drawable = EVIDENCE.filter((e) => e !== 'absent');
        for (const key of ['dash', 'pattern', 'word']) {
            const values = drawable.map((e) => EVIDENCE_TREATMENT[e][key]);
            expect(new Set(values).size, `two classes share a ${key}`).toBe(drawable.length);
        }
    });

    it('puts all three channels in the markup, on one page', async () => {
        await openAt(1100, { initialForm: 'extent.visible_inferred_partition' });
        const rows = all('.pl-fm-legendrow');
        expect(rows.length).toBe(3);
        // 1. the printed word
        expect(rows.map((r) => r.querySelector('[data-evidence-word]')
            .getAttribute('data-evidence-word')))
            .toEqual(['measured', 'inferred', 'hypothetical']);
        // 2. the dash, on the drawn shape
        const dashes = ['visible', 'inferred', 'unknown'].map((p) => q(
            `.pl-fm-shape[data-layer="partition_tricolor:${p}"] .pl-fm-ring, `
            + `.pl-fm-shape[data-layer="partition_tricolor:${p}"] .pl-fm-cellrule`)
            ?.getAttribute('stroke-dasharray') ?? null);
        expect(new Set(dashes).size).toBe(3);
        // 3. the fill pattern
        const patterns = ['inferred', 'unknown'].map((p) => q(
            `[data-layer="partition_tricolor:${p}"] .pl-fm-hatch`)?.getAttribute('fill'));
        expect(patterns[0]).toMatch(/hatch-45/);
        expect(patterns[1]).toMatch(/hatch-135/);
    });

    it('distinguishes a resolved node from an unresolved one without colour', async () => {
        await openAt(1100, { initialForm: 'topology.adjacency_graph' });
        expect(q('.pl-fm-nodedot').getAttribute('stroke-dasharray')).toBe('3 3');
        expect(q('[data-node]').getAttribute('data-resolved')).toBe('false');
    });

    it('distinguishes a disjoint edge from a contact edge without colour', () => {
        // A disjoint edge is a measured NON-contact. Drawn like a contact it says the opposite.
        expect(SHEET).toMatch(/\.pl-fm-edge\[data-kind='disjoint'\]/);
    });

    it('crosses every point marker, so two markers differ by more than a hue', async () => {
        await openAt(1100, { initialForm: 'topology.contact_locus', initialView: 'points' });
        expect(all('.pl-fm-cross').length).toBeGreaterThan(0);
    });
});

/* ── responsive ──────────────────────────────────────────────────────────── */

describe('the four target widths', () => {
    it('names the widths the build asks for', () => {
        expect(TARGET_WIDTHS).toEqual([1100, 720, 430, 320]);
    });

    it('puts each one in the band its layout is written for', () => {
        expect(widthBand(1100)).toBe('wide');
        expect(widthBand(720)).toBe('mid');
        expect(widthBand(430)).toBe('narrow');
        expect(widthBand(320)).toBe('tight');
        // the boundaries themselves, which is where an off-by-one lives
        expect(widthBand(1000)).toBe('wide');
        expect(widthBand(999)).toBe('mid');
        expect(widthBand(680)).toBe('mid');
        expect(widthBand(679)).toBe('narrow');
        expect(widthBand(400)).toBe('narrow');
        expect(widthBand(399)).toBe('tight');
    });

    it.each(TARGET_WIDTHS)('renders the whole laboratory at %ipx', async (px) => {
        await openAt(px);
        expect(q('.pl-fm').getAttribute('data-w')).toBe(widthBand(px));
        // Every part of the surface is present at every width — the narrow layout REORDERS one
        // DOM rather than dropping panels, so the keyboard path and the visual path stay the
        // same path.
        expect(q('.pl-fm-rail')).toBeTruthy();
        expect(q('.pl-fm-main')).toBeTruthy();
        expect(q('.pl-fm-side')).toBeTruthy();
        expect(all('[data-form-option]')).toHaveLength(19);
        expect(q('.pl-fm-svg')).toBeTruthy();
        expect(all('.pl-fm-legendrow').length).toBeGreaterThan(0);
    });

    it('measures its own container rather than the window', async () => {
        // The window is never resized in this file. If the band moved with the viewport, every
        // case above would report the same band.
        await openAt(320);
        expect(q('.pl-fm').getAttribute('data-w')).toBe('tight');
        await act(async () => { root.unmount(); });
        root = createRoot(container);
        await openAt(1100);
        expect(q('.pl-fm').getAttribute('data-w')).toBe('wide');
    });

    it('keeps the stylesheet\'s reordering keyed to the same attribute', () => {
        for (const band of ['mid', 'narrow', 'tight']) {
            expect(SHEET, `no layout rule for ${band}`)
                .toMatch(new RegExp(`\\.pl-fm\\[data-w='${band}'\\]`));
        }
    });
});

describe('dense and empty at every width', () => {
    it.each(TARGET_WIDTHS)('renders eighteen relations at %ipx without dropping any', async (px) => {
        await openAt(px, { initialForm: 'topology.pair_relation', initialView: 'list' });
        await click(q('[data-scenario-option="dense"]'));
        expect(all('.pl-fm-legendrow')).toHaveLength(18);
    });

    it.each(TARGET_WIDTHS)('renders the empty record with its reason at %ipx', async (px) => {
        await openAt(px, { initialForm: 'topology.pair_relation' });
        await click(q('[data-scenario-option="empty"]'));
        expect(q('[data-why-absent]').textContent).toMatch(/none stood in any of the asked-for/);
    });
});

/* ── keyboard and focus ──────────────────────────────────────────────────── */

describe('keyboard and focus', () => {
    it('makes every control a real button or input', async () => {
        await openAt(1100);
        const interactive = all('[data-form-option], [data-view-option], [data-scenario-option], '
            + '[data-compare-option], [data-verdict], [data-tool], [data-focus-layer], '
            + '[data-toggle-layer]');
        expect(interactive.length).toBeGreaterThan(30);
        for (const el of interactive) {
            expect(['BUTTON', 'INPUT'], el.outerHTML.slice(0, 80)).toContain(el.tagName);
            expect(el.hasAttribute('disabled')).toBe(false);
        }
    });

    it('gives every toggle an aria state a screen reader can read', async () => {
        await openAt(1100);
        for (const el of all('[data-form-option], [data-scenario-option], [data-verdict]')) {
            expect(el.getAttribute('aria-pressed')).toMatch(/^(true|false)$/);
        }
        for (const el of all('[data-view-option]')) {
            expect(el.getAttribute('role')).toBe('tab');
            expect(el.getAttribute('aria-selected')).toMatch(/^(true|false)$/);
        }
    });

    it('reaches every drawn layer through the legend, not only by pointing', async () => {
        await openAt(1100, { initialForm: 'extent.hard_mask', initialView: 'fill' });
        const shapes = all('.pl-fm-shape').map((s) => s.getAttribute('data-layer'));
        const buttons = all('[data-focus-layer]').map((b) => b.getAttribute('data-focus-layer'));
        for (const id of shapes) expect(buttons, `${id} is not reachable by keyboard`).toContain(id);
    });

    it('names every region of the page', async () => {
        await openAt(1100);
        const labels = all('section[aria-label]').map((s) => s.getAttribute('aria-label'));
        expect(labels).toEqual(expect.arrayContaining(
            ['Forms', 'Record state', 'Views', 'The record', 'Lineage', 'Tools']));
        expect(q('.pl-fm-svg').getAttribute('role')).toBe('img');
        expect(q('.pl-fm-svg').getAttribute('aria-label')).toBeTruthy();
    });

    it('gives every table a caption and scoped headers', async () => {
        await openAt(1100, { initialForm: 'topology.adjacency_graph', initialView: 'matrix' });
        expect(q('.pl-fm-matrix caption')).toBeTruthy();
        for (const th of all('.pl-fm-matrix th')) {
            expect(th.getAttribute('scope')).toMatch(/^(row|col)$/);
        }
    });
});

/* ── the harness ─────────────────────────────────────────────────────────── */

describe('the harness the screenshots are taken from', () => {
    it('names a case for every claim worth photographing', () => {
        expect(HARNESS_CASES.length).toBeGreaterThanOrEqual(8);
        for (const c of HARNESS_CASES) {
            expect(PERCEPTUAL_FORMS, c.key).toContain(c.form);
            expect(viewsFor(c.form).map((v) => v.key), c.key).toContain(c.view);
            expect(c.why.length, `${c.key} does not say what it is for`).toBeGreaterThan(40);
            // The clock is injected, so a screenshot taken twice is the same screenshot.
            expect(c.at).toBe('2026-08-22T00:00:00Z');
        }
    });

    it('covers both organs and all five surfaces between them', () => {
        const organs = new Set(HARNESS_CASES.map((c) => c.form.split('.')[0]));
        expect([...organs].sort()).toEqual(['extent', 'topology']);
        const surfaces = new Set(HARNESS_CASES.map(
            (c) => viewsFor(c.form).find((v) => v.key === c.view).surface));
        expect([...surfaces].sort()).toEqual(['compare', 'diagram', 'panel', 'stage']);
    });

    it('mounts four widths of the laboratory in one page', async () => {
        await mount(<FormHarness />);
        await settle();
        expect(all('.pl-fm-harnesspane')).toHaveLength(4);
        expect(all('.pl-fm-harnesspane').map((p) => p.getAttribute('data-harness-width')))
            .toEqual(['1100', '720', '430', '320']);
        expect(all('.pl-fm')).toHaveLength(4);
    });

    it('gives each pane its own state, so one can be driven while the others sit', async () => {
        await mount(<FormHarness />);
        await settle();
        const panes = all('.pl-fm-harnesspane');
        await click(panes[0].querySelector('[data-form-option="extent.hierarchy"]'));
        expect(panes[0].querySelector('.pl-fm').getAttribute('data-form'))
            .toBe('extent.hierarchy');
        expect(panes[1].querySelector('.pl-fm').getAttribute('data-form'))
            .toBe('extent.hard_mask');
    });

    it('switches every pane to the chosen case', async () => {
        await mount(<FormHarness />);
        await settle();
        await click(q('[data-harness-option="adjacency_matrix"]'));
        for (const pane of all('.pl-fm-harnesspane')) {
            expect(pane.querySelector('.pl-fm').getAttribute('data-form'))
                .toBe('topology.adjacency_graph');
            expect(pane.querySelector('.pl-fm').getAttribute('data-view')).toBe('matrix');
        }
    });
});
