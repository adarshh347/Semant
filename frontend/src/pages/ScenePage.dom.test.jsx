/**
 * WAVE4 — the scene view, tested. The view with the loudest pixel-honesty claim and no suite.
 *
 * `ScenePage` states its one rule in its own header: a relation must look like what it IS —
 * solid where the geometry is a mask and the claim is measured, dashed where it rests on a box and
 * is only interpretive; hollow where nobody has accepted it, filled where a curator did. That rule
 * was carried entirely by a stylesheet nothing tested and a class expression nothing mounted.
 *
 * The failure it guards is not hypothetical and not generic. `cseg_golden_finial_7` scores
 * containment 1.000 against a VLM box while being IN FRONT OF it — the founding pathology — and it
 * is among the first relations this page draws. Rendering it like a measured relation would be that
 * pathology surviving every backend guard and arriving in CSS.
 *
 * Two things here are worth naming because they are what a DOM query alone would miss:
 *
 *   1. STROKE AND BADGE MUST AGREE. The stroke class comes from `rel.admissible`; the badge prints
 *      `rel.epistemic`. They are two different fields and nothing forced them to say the same
 *      thing — a relation could be drawn solid while its own badge read `interpretive`.
 *   2. THE TREATMENTS MUST DIFFER IN THE STYLESHEET. `is-measured` and `is-interpretive` landing on
 *      the same declarations is invisible to every class assertion in this file.
 *
 * Plain DOM against a real root, the shape the other `.dom.test.jsx` suites use.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import ScenePage from './ScenePage.jsx';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

const RING = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]];

const region = (id, over = {}) => ({
    id, label: id, box: { x: 0.1, y: 0.1, w: 0.3, h: 0.3 },
    has_mask: true, polygons: [RING], maker: { attributed: true, adapter: 'sam3' },
    ...over,
});

/** The founding pathology's own shape: a box-basis relation that must never look measured. */
const INTERPRETIVE = {
    kind: 'nesting', relation: 'nested_within',
    source: 'cseg_golden_finial_7', target: 'region_2',
    admissible: false, epistemic: 'interpretive', ledger_status: 'proposed',
    basis: 'box', detail: 'containment 1.000 against a box',
};

const MEASURED = {
    kind: 'occlusion', relation: 'in_front_of',
    source: 'cseg_lattice_window_0', target: 'cseg_wall_0',
    admissible: true, epistemic: 'measured', ledger_status: 'proposed',
    basis: 'mask', detail: 'ordering 0.9656',
};

const COMMITTED = {
    ...MEASURED, source: 'cseg_a', target: 'cseg_b', ledger_status: 'committed',
};

const scene = (relations, regions) => ({
    post_id: 'p1', photo_url: 'http://example/x.jpg',
    regions: regions || [
        region('cseg_golden_finial_7'), region('region_2', { has_mask: false, polygons: [] }),
        region('cseg_lattice_window_0'), region('cseg_wall_0'),
        region('cseg_a'), region('cseg_b'),
    ],
    relations,
    tallies: { by_kind: {}, by_epistemic: {}, by_ledger: {} },
    provenance_audit: { regions: 6, attributed: 6 },
    cache: { built_at: 'now', scenes: 1, kinds_built: ['nesting', 'occlusion'] },
    kinds_absent: [], kinds_none_here: [],
});

function stubScene(body) {
    vi.stubGlobal('fetch', vi.fn(async (url) => {
        const target = String(url);
        if (/\/scene\/$/.test(target)) return json([]);
        return json(body);
    }));
}

const json = (body) => ({ ok: true, status: 200, json: async () => body, text: async () => '' });

async function mount() {
    await act(async () => {
        root.render(
            <MemoryRouter initialEntries={['/scene/p1']}>
                <Routes><Route path="/scene/:postId" element={<ScenePage />} /></Routes>
            </MemoryRouter>,
        );
    });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });
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

const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => Array.from(container.querySelectorAll(sel));

/** Every kind is off by default except three, so a fixture has to turn its own kind on. */
async function showKind(label) {
    const chip = $$('.scene-chip').find((b) => b.textContent.includes(label));
    if (chip && chip.getAttribute('aria-pressed') === 'false') {
        await act(async () => { chip.click(); });
    }
}

// ── 1. a relation is drawn as what it is ───────────────────────────────────

describe('a relation is drawn as what it is', () => {
    it('draws a box-basis relation as interpretive, never as measured', async () => {
        stubScene(scene([INTERPRETIVE]));
        await mount();
        await showKind('Nesting');

        const link = $('.scene-link--nesting');
        expect(link).not.toBeNull();
        expect(link.getAttribute('class')).toContain('is-interpretive');
        expect(link.getAttribute('class')).not.toContain('is-measured');
    });

    it('draws a mask-basis relation as measured', async () => {
        stubScene(scene([MEASURED]));
        await mount();

        const link = $('.scene-link--occlusion');
        expect(link.getAttribute('class')).toContain('is-measured');
        expect(link.getAttribute('class')).not.toContain('is-interpretive');
    });

    it('gives the two a different stroke, not a different shade of the same one', () => {
        // The class assertions above cannot see this: `is-measured` and `is-interpretive` landing
        // on identical declarations would satisfy every one of them while the page told a curator
        // an estimate and a measurement are the same thing.
        const css = fs.readFileSync(path.join(HERE, 'ScenePage.css'), 'utf8');
        const rule = (sel) => {
            const m = css.match(new RegExp(`${sel.replace(/[.\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`));
            return m ? m[1].replace(/\s+/g, ' ').trim() : null;
        };
        const measured = rule('.scene-link.is-measured line');
        const interpretive = rule('.scene-link.is-interpretive line');
        expect(measured).toBeTruthy();
        expect(interpretive).toBeTruthy();
        expect(measured).not.toBe(interpretive);
        // and the difference is the DASH — legible without colour, in print, in greyscale
        expect(interpretive).toMatch(/stroke-dasharray:\s*\d/);
        expect(measured).toMatch(/stroke-dasharray:\s*none/);
    });

    it('keeps a proposed marker hollow and a committed one filled', () => {
        const css = fs.readFileSync(path.join(HERE, 'ScenePage.css'), 'utf8');
        const rule = (sel) => {
            const m = css.match(new RegExp(`${sel.replace(/[.\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`));
            return m ? m[1].replace(/\s+/g, ' ').trim() : null;
        };
        const proposed = rule('.scene-link.is-proposed circle');
        const committed = rule('.scene-link.is-committed circle');
        expect(proposed).toMatch(/fill:\s*none/);
        expect(committed).toMatch(/fill:\s*(currentColor|var\()/);
        expect(proposed).not.toBe(committed);
    });

    it('classes a committed relation apart from a proposed one', async () => {
        stubScene(scene([MEASURED, COMMITTED]));
        await mount();

        expect($$('.scene-link.is-proposed')).toHaveLength(1);
        expect($$('.scene-link.is-committed')).toHaveLength(1);
    });
});

// ── 2. the stroke and the badge cannot disagree ────────────────────────────

describe('the stroke and the badge say the same thing', () => {
    it('carries the same status in the drawing and in the list', async () => {
        stubScene(scene([INTERPRETIVE]));
        await mount();
        await showKind('Nesting');

        // The drawing reads `admissible`; the list prints `epistemic`. Two fields, one claim —
        // a solid line beside a badge reading "interpretive" would be the page arguing with itself.
        const drawn = $('.scene-link').getAttribute('class').includes('is-measured')
            ? 'measured' : 'interpretive';
        const badge = $('.scene-badges b[data-status]').getAttribute('data-status');
        expect(badge).toBe(drawn);

        expect($('.scene-list li').getAttribute('class')).toContain('is-interpretive');
    });

    it('shows the basis the claim actually rests on', async () => {
        stubScene(scene([INTERPRETIVE]));
        await mount();
        await showKind('Nesting');
        expect($('.scene-basis').textContent).toBe('box');
    });
});

// ── 3. the overlay lands on the photograph ─────────────────────────────────

describe('the overlay is registered to the photograph', () => {
    it('uses the image\'s natural pixel space and letterboxes with it', async () => {
        stubScene(scene([MEASURED]));
        await mount();
        const img = $('.scene-frame img');
        Object.defineProperty(img, 'naturalWidth', { value: 1280, configurable: true });
        Object.defineProperty(img, 'naturalHeight', { value: 720, configurable: true });
        await act(async () => { img.dispatchEvent(new Event('load')); });

        const svg = $('.scene-overlay');
        expect(svg.getAttribute('viewBox')).toBe('0 0 1280 720');
        // `none` would stretch the viewBox while the image letterboxed inside it, and every
        // polygon would land somewhere the measurement never was.
        expect(svg.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
    });

    it('marks a region drawn from a box as a box, so an estimate is visible as one', async () => {
        stubScene(scene([INTERPRETIVE], [
            region('cseg_golden_finial_7'),
            region('region_2', { has_mask: false }),
        ]));
        await mount();

        expect($$('.scene-region.is-box')).toHaveLength(1);
        expect($$('.scene-region')).toHaveLength(2);
    });
});

// ── 4. absence is stated, and the two absences are different ───────────────

describe('an absence is stated as the kind of absence it is', () => {
    it('separates "never derived" from "derived and none here"', async () => {
        const body = scene([]);
        body.kinds_absent = ['adjacency'];
        body.kinds_none_here = ['occlusion'];
        stubScene(body);
        await mount();

        const warn = $('.scene-warn').textContent;
        expect(warn).toContain('never derived');
        expect(warn).toContain('adjacency');
        expect(warn).toMatch(/not\s+the same as evidence of absence/);
        // and the other absence is NOT filed under the first
        expect(warn).not.toContain('occlusion');
        expect(container.textContent).toMatch(/derived and none found here: occlusion/);
    });

    it('says a scene with no derived relations is unbuilt rather than empty', async () => {
        const body = scene([]);
        body.cache = { missing: true };
        stubScene(body);
        await mount();
        expect($('.scene-warn').textContent).toMatch(/nobody has run\s+the build/);
    });
});

// ── 5. the view only reads ─────────────────────────────────────────────────

describe('the scene view only reads', () => {
    it('makes no request that is not a GET', async () => {
        stubScene(scene([MEASURED]));
        await mount();
        // Guarded against the empty loop: with no calls every assertion below holds vacuously.
        expect(globalThis.fetch.mock.calls.length).toBeGreaterThan(0);
        for (const call of globalThis.fetch.mock.calls) {
            const method = (call[1] && call[1].method) || 'GET';
            expect(['GET', 'HEAD']).toContain(method);
        }
    });

    it('has no commit path in its source — that surface is the curator\'s', () => {
        const source = fs.readFileSync(path.join(HERE, 'ScenePage.jsx'), 'utf8');
        expect(source).not.toMatch(/\/commit/);
        expect(source).not.toMatch(/method:\s*'(POST|PUT|PATCH|DELETE)'/);
    });
});
