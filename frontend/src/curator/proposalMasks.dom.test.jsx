/**
 * WAVE4 — the two masks on the photograph, mounted. The lies a geometry panel would tell.
 *
 * This panel sits at the seam where a person's judgement becomes durable, so the failures are
 * expensive in a way the same bug elsewhere is not:
 *
 *   1. a shape drawn where a measurement is missing — a box standing in for a mask, which is the
 *      WAVE2.5 failure arriving at the moment it would be committed
 *   2. a second renderer — a curator and an editor looking at "the same" mask through different
 *      code, so what is committed is not what was measured
 *   3. an overlay that reads as accepted, at the one screen where accepting is a button away
 *   4. front and back drawn alike, which is the whole claim
 *
 * Plain DOM against a real root, the shape the other `.dom.test.jsx` suites use. `fetchScene` is
 * injected, so nothing here depends on a network or on the scene route's availability.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import ProposalMasks from './ProposalMasks.jsx';

let container;
let root;

const RING = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.4]];
const BIG = [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]];

const region = (id, polygons, extra = {}) => ({
    id, label: '', box: { x: 0.1, y: 0.1, w: 0.3, h: 0.3 },
    has_mask: polygons.length > 0, polygons,
    maker: { kind: 'model', attributed: true, adapter: 'sam3', detail: 'drawn by sam3' },
    ...extra,
});

const scene = (regions) => ({
    post_id: 'p1', photo_url: 'http://example/x.jpg', regions,
    relations: [], tallies: {}, provenance_audit: {}, cache: {}, kinds_absent: [],
    kinds_none_here: [],
});

const proposal = (over = {}) => ({
    proposal_id: 'pr1', kind: 'occlusion_supersedes_containment', post_id: 'p1',
    mark_id: 'vm_occ_1', epistemic: 'measured', ledger_status: 'proposed',
    subject: { front_region_id: 'front', back_region_id: 'back' },
    evidence: { basis: 'mask', ordering_separation: 0.9656 },
    ...over,
});

const bothMasked = () => scene([region('front', [RING]), region('back', [BIG])]);

async function mount(props) {
    await act(async () => { root.render(<ProposalMasks {...props} />); });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

/** The overlay only renders once the image reports its natural size. */
async function loadImage(w = 1280, h = 720) {
    const img = container.querySelector('img');
    if (!img) return;
    Object.defineProperty(img, 'naturalWidth', { value: w, configurable: true });
    Object.defineProperty(img, 'naturalHeight', { value: h, configurable: true });
    await act(async () => { img.dispatchEvent(new Event('load')); });
}

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
});

describe('the masks are drawn, and they are the real ones', () => {
    it('draws both regions over the photograph', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();

        expect(container.querySelector('img').getAttribute('src')).toBe('http://example/x.jpg');
        expect(container.querySelectorAll('.cm-svg .rs-shape')).toHaveLength(2);
    });

    it('uses the image\'s natural pixel space, so the overlay tracks the photograph', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage(1280, 720);

        const svg = container.querySelector('.cm-svg');
        expect(svg.getAttribute('viewBox')).toBe('0 0 1280 720');
        expect(svg.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
    });

    it('draws the mask outline rather than the bounding box', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();
        // A <path> is the mask; a <rect> is what a box-only region would get.
        expect(container.querySelectorAll('.cm-svg path')).toHaveLength(2);
        expect(container.querySelectorAll('.cm-svg rect')).toHaveLength(0);
    });
});

describe('front and back are distinguishable, because that is the claim', () => {
    it('lights the front region and grounds the one behind', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();

        expect(container.querySelectorAll('.cm-svg .rs-shape.is-lit')).toHaveLength(1);
        expect(container.querySelectorAll('.cm-svg .rs-shape.is-dim')).toHaveLength(1);
    });

    it('names each region by its role in the relation', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();

        const roles = [...container.querySelectorAll('.cm-role')].map((li) => li.textContent);
        expect(roles.some((t) => t.includes('in front') && t.includes('front'))).toBe(true);
        expect(roles.some((t) => t.includes('behind') && t.includes('back'))).toBe(true);
    });

    it('shows who drew each mask', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();
        expect(container.textContent).toContain('sam3');
    });
});

describe('no shape is drawn where a measurement is missing', () => {
    it('degrades to a stated absence when a region has no outline', async () => {
        const half = scene([region('front', []), region('back', [BIG])]);
        await mount({ proposal: proposal(), fetchScene: async () => half });

        expect(container.querySelector('.cm-svg')).toBeNull();
        expect(container.querySelector('.cm-note--absent')).toBeTruthy();
        expect(container.textContent).toMatch(/bounding box drawn in their place/i);
    });

    it('degrades when a region named by the proposal is gone from the post', async () => {
        const orphan = scene([region('back', [BIG])]);
        await mount({ proposal: proposal(), fetchScene: async () => orphan });

        expect(container.querySelector('.cm-svg')).toBeNull();
        expect(container.textContent).toMatch(/not in this post any more/i);
    });

    it('degrades when the proposal names no regions at all', async () => {
        await mount({ proposal: proposal({ subject: {} }), fetchScene: async () => bothMasked() });
        expect(container.querySelector('.cm-svg')).toBeNull();
        expect(container.textContent).toMatch(/does not name two regions/i);
    });

    it('degrades when the scene route does not answer', async () => {
        await mount({
            proposal: proposal(),
            fetchScene: async () => { throw new Error('502'); },
        });
        expect(container.querySelector('.cm-svg')).toBeNull();
        expect(container.textContent).toMatch(/did not answer/i);
    });
});

describe('the overlay never implies the proposal is accepted', () => {
    it('carries the proposal\'s two statuses as data, not as decoration', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();

        const fig = container.querySelector('.cm-figure');
        expect(fig.getAttribute('data-epistemic')).toBe('measured');
        expect(fig.getAttribute('data-ledger')).toBe('proposed');
        expect(fig.getAttribute('data-basis')).toBe('mask');
    });

    it('marks a box-basis proposal so the stroke can say it is an estimate', async () => {
        await mount({
            proposal: proposal({ epistemic: 'interpretive',
                                 evidence: { basis: 'box' } }),
            fetchScene: async () => bothMasked(),
        });
        await loadImage();

        const fig = container.querySelector('.cm-figure');
        expect(fig.getAttribute('data-epistemic')).toBe('interpretive');
        expect(fig.getAttribute('data-basis')).toBe('box');
    });

    it('says in words that nothing here is accepted', async () => {
        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();
        expect(container.textContent).toMatch(/Nothing here is accepted/i);
    });
});

describe('one renderer', () => {
    it('draws through the shared RegionOverlay rather than a second implementation', async () => {
        // Asserted structurally, read from disk so the assertion cannot go vacuous the way a
        // `?raw` import that quietly fails would: the module imports the shared overlay, and
        // renders no <svg> of its own. A private renderer would satisfy neither.
        // `import.meta.url` is not a file: URL under vitest's transform, so resolve from the
        // project root the runner is started in.
        const source = readFileSync(
            resolve(process.cwd(), 'src/curator/ProposalMasks.jsx'), 'utf8');
        expect(source).toMatch(/from '\.\.\/components\/RegionOverlay'/);
        expect(source).not.toMatch(/<svg/);

        await mount({ proposal: proposal(), fetchScene: async () => bothMasked() });
        await loadImage();
        expect(container.querySelectorAll('.rs-shape').length).toBe(2);
    });
});
