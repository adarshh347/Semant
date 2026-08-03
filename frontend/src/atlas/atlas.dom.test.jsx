/**
 * ATLAS C1 — the canvas, mounted.
 *
 * The unit tests pin what a save carries; these pin what a curator SEES. Three things have to
 * render or the surface is quietly dishonest: an image that could not be read, a suggestion the
 * canvas declined to draw, and a save that refused.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlowProvider } from '@xyflow/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasCanvas from './AtlasCanvas.jsx';
import AtlasImageNode from './AtlasImageNode.jsx';

// jsdom has no ResizeObserver; React Flow and `useStageGeometry` both want one.
if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
        observe() {} unobserve() {} disconnect() {}
    };
}
// React Flow measures its pane; jsdom reports zeroes and warns. Neither affects what we assert.
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
    globalThis.DOMMatrixReadOnly = class { constructor() { this.m22 = 1; } };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
// A node mounted on its own still needs React Flow's store: C4 gave the image node a target
// handle, which is where a claim's binding connector lands.
const mountNode = async (node) => mount(<ReactFlowProvider>{node}</ReactFlowProvider>);

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

const nodeData = (over = {}) => ({
    nodeId: 'n0', postId: 'p1', title: 'the façade',
    imageRef: 'https://example.invalid/1.jpg', readable: true, unreadableReason: '',
    grounds: [{ id: 'g1' }, { id: 'g2' }], regions: [], marks: [], percepts: [],
    withheld: 0, w: 420, h: 320, ...over,
});

const aView = (over = {}) => ({
    id: 'atlas_1', title: 'the walk', edges: [], unreadable: [],
    nodes: [
        { node_id: 'n0', post_id: 'p1', x: 0, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/1.jpg', title: 'one',
            grounds: [{ id: 'g1' }], regions: [], marks: [], percepts: [], withheld: 0 },
        { node_id: 'n1', post_id: 'p2', x: 540, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/2.jpg', title: 'two',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
    ],
    ...over,
});

const fakeService = (over = {}) => ({
    view: vi.fn(async () => aView()),
    saveArrangement: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    ...over,
});

// ── the node ────────────────────────────────────────────────────────────────

describe('an image node', () => {
    it('shows the picture and counts what is committed on it', async () => {
        await mountNode(<AtlasImageNode data={nodeData()} />);
        expect(container.querySelector('.atlas-node-img').getAttribute('src'))
            .toBe('https://example.invalid/1.jpg');
        expect(container.textContent).toContain('2 percepts');
    });

    it('says so plainly when nothing has been committed yet', async () => {
        await mountNode(<AtlasImageNode data={nodeData({ grounds: [] })} />);
        expect(container.textContent).toContain('no committed percepts');
    });

    it('stays on the canvas when the image could not be read, and says why', async () => {
        await mountNode(<AtlasImageNode data={nodeData({
            readable: false, unreadableReason: 'post:ghost could not be read' })} />);
        const node = container.querySelector('.atlas-node');
        expect(node.getAttribute('data-readable')).toBe('false');
        expect(container.textContent).toContain('could not be read');
    });

    it('renders a withheld suggestion as visible text, never a tooltip', async () => {
        await mountNode(<AtlasImageNode data={nodeData({ withheld: 2 })} />);
        const note = container.querySelector('.atlas-node-withheld');
        expect(note).toBeTruthy();
        expect(note.textContent).toMatch(/2 suggestions not shown/);
        // and the count of what IS drawn does not silently include it
        expect(container.textContent).toContain('2 percepts');
    });

    it('offers nothing that could change a percept — this gate is read-only', async () => {
        await mountNode(<AtlasImageNode data={nodeData()} />);
        expect(container.querySelectorAll('button').length).toBe(0);
        expect(container.querySelectorAll('input').length).toBe(0);
    });
});

// ── the canvas ──────────────────────────────────────────────────────────────

describe('the canvas', () => {
    it('opens an Atlas and reports what is on it', async () => {
        const service = fakeService();
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        expect(service.view).toHaveBeenCalledWith('atlas_1');
        expect(container.textContent).toContain('the walk');
        expect(container.textContent).toContain('2 images');
        expect(container.textContent).toContain('1 committed percept');
    });

    it('says on the surface that position asserts nothing', async () => {
        await mount(<AtlasCanvas atlasId="atlas_1" service={fakeService()} />);
        expect(container.textContent).toMatch(/position is a thinking aid/i);
    });

    it('names the images the corpus could not read', async () => {
        const service = fakeService({
            view: async () => aView({ unreadable: ['gone'] }),
        });
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        const banner = container.querySelector('.atlas-banner.is-unreadable');
        expect(banner).toBeTruthy();
        expect(banner.textContent).toMatch(/could not be read/);
        expect(banner.textContent).toMatch(/stays on the canvas/);
    });

    it('reports a failure to open rather than showing an empty canvas', async () => {
        const service = fakeService({ view: async () => { throw new Error('nope'); } });
        await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
        expect(container.querySelector('[role="alert"]').textContent).toContain('nope');
    });

    it('draws no edges — a relation is a percept, and that is C3', async () => {
        await mount(<AtlasCanvas atlasId="atlas_1" service={fakeService()} />);
        expect(container.querySelectorAll('.react-flow__edge').length).toBe(0);
    });
});
