/**
 * ATLAS C3 — the draw gesture, mounted.
 *
 * `atlasRelation.test.js` pins what an edge IS; this pins what the gesture DOES. Two things have
 * to hold or the surface is quietly dishonest:
 *
 *   a refusal draws the attempted line and persists nothing
 *   a success re-reads the ledger rather than trusting what it sent
 *
 * React Flow lays nothing out in jsdom, so no edge element is ever emitted here — the drawn line
 * is verified in a real browser. What is testable is the CONTRACT: what `onConnect` sends, what it
 * does with each answer, and what it refuses before asking.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlowProvider } from '@xyflow/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasWorkspace from './AtlasWorkspace.jsx';
import { MODE_PLAN } from './atlasDocument.js';
import AtlasImageNode from './AtlasImageNode.jsx';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
        constructor(cb) { this.cb = cb; }
        observe(el) { this.cb([{ target: el, contentRect: { width: 420, height: 320 } }], this); }
        unobserve() {} disconnect() {}
    };
}
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
    globalThis.DOMMatrixReadOnly = class { constructor() { this.m22 = 1; } };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
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

const anEdge = (over = {}) => ({
    edge_id: 'edge_1', kind: 'relation', mark_id: 'vm_rel_1',
    source_node: 'n0', target_node: 'n1', spans: ['p1', 'p2'],
    live: true, role: 'kinship', label: 'echoes', epistemic: 'interpretive',
    sources: [{ post_id: 'p1', mark_ref: 'm1' }, { post_id: 'p2', mark_ref: 'm2' }],
    missing_reason: null, ...over,
});

const aView = (over = {}) => ({
    id: 'atlas_1', title: 'the walk', edges: [], plan: null, unreadable: [],
    nodes: [
        { node_id: 'n0', post_id: 'p1', x: 0, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/1.jpg', title: 'one',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
        { node_id: 'n1', post_id: 'p2', x: 540, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/2.jpg', title: 'two',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0 },
    ],
    ...over,
});

const fakeService = (over = {}) => ({
    view: vi.fn(async () => aView()),
    saveArrangement: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    saveNotes: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    proposePlan: vi.fn(async () => ({ claims: [], connectors: [], counts: {}, refusals: [] })),
    acceptPlan: vi.fn(async () => ({ plan: null })),
    clearPlan: vi.fn(async () => ({ plan: null })),
    drawRelation: vi.fn(async () => ({ atlas: {}, edge: anEdge() })),
    removeRelation: vi.fn(async () => ({ removed: 'edge_1' })),
    ...over,
});

/** Reach the canvas's own `onConnect` — jsdom cannot perform the drag React Flow listens for. */
const connect = async (connection) => {
    const el = container.querySelector('.react-flow');
    const key = Object.keys(el).find((k) => k.startsWith('__reactProps$'))
        || Object.keys(el).find((k) => k.startsWith('__reactFiber$'));
    let fiber = el[key.startsWith('__reactFiber$') ? key : Object.keys(el)
        .find((k) => k.startsWith('__reactFiber$'))];
    let found = null;
    for (let i = 0; fiber && i < 40 && !found; i += 1) {
        if (typeof fiber.memoizedProps?.onConnect === 'function') found = fiber.memoizedProps.onConnect;
        fiber = fiber.return;
    }
    expect(found).toBeTruthy();
    await act(async () => { await found(connection); });
};

// ── the node offers the gesture ─────────────────────────────────────────────

describe('an image node', () => {
    it('offers a draggable source handle — the one affordance on this canvas', async () => {
        await mountNode(<AtlasImageNode data={{
            nodeId: 'n0', postId: 'p1', title: 'x', imageRef: 'https://example.invalid/1.jpg',
            readable: true, unreadableReason: '', grounds: [], regions: [], marks: [],
            percepts: [], withheld: 0, w: 420, h: 320,
        }} />);
        const draw = container.querySelector('.atlas-handle.is-draw');
        expect(draw).toBeTruthy();
        expect(draw.className).toContain('source');
        // and the layout handle a binding lands on is still there, separately
        expect(container.querySelectorAll('.react-flow__handle').length).toBe(2);
    });
});

// ── the gesture ─────────────────────────────────────────────────────────────

describe('drawing a relation', () => {
    it('asks the server about the two nodes the line joined', async () => {
        const service = fakeService();
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'n0', target: 'n1' });

        expect(service.drawRelation).toHaveBeenCalledWith('atlas_1', {
            source_node: 'n0', target_node: 'n1' });
    });

    it('re-reads the ledger on success rather than trusting what it sent', async () => {
        // The edge's words come from the ledger. A client that assembled them from its own request
        // would be the one place this surface could disagree with what was actually committed.
        const service = fakeService({
            view: vi.fn()
                .mockResolvedValueOnce(aView())
                .mockResolvedValue(aView({ edges: [anEdge()] })),
        });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'n0', target: 'n1' });

        expect(service.view).toHaveBeenCalledTimes(2);
        expect(container.textContent).toContain('1 relation drawn');
    });

    it('draws the refusal and adds NO edge when the comparison cannot be grounded', async () => {
        const service = fakeService({
            drawRelation: vi.fn(async () => ({ refused: {
                reason: 'gate_refused', source_node: 'n0', target_node: 'n1',
                detail: "missing_input: 'compare_views' needs 2× mark and nothing in this plan",
            } })),
        });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'n0', target: 'n1' });

        // nothing was stored, so the view was NOT re-read and no relation is counted
        expect(service.view).toHaveBeenCalledTimes(1);
        expect(container.textContent).not.toContain('relation drawn');
    });

    it('never asks about a line from an image to itself', async () => {
        const service = fakeService();
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'n0', target: 'n0' });
        expect(service.drawRelation).not.toHaveBeenCalled();
    });

    it('never asks about a line touching a claim card', async () => {
        // A line from a claim to an image is a BINDING, and bindings are minted by the planner.
        const service = fakeService();
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'claim:c0', target: 'n1' });
        expect(service.drawRelation).not.toHaveBeenCalled();
    });

    it('reports a comparison that could not be run at all, on the same line', async () => {
        const service = fakeService({
            drawRelation: vi.fn(async () => { throw new Error('the engine is down'); }),
        });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        await connect({ source: 'n0', target: 'n1' });
        expect(container.textContent).not.toContain('relation drawn');
    });
});

// ── what the canvas says about what is on it ────────────────────────────────

describe('the header', () => {
    it('counts the relations drawn', async () => {
        const service = fakeService({ view: async () => aView({ edges: [anEdge()] }) });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        expect(container.textContent).toContain('1 relation drawn');
    });

    it('counts a relation that left the ledger SEPARATELY, never in the total', async () => {
        const service = fakeService({
            view: async () => aView({ edges: [anEdge(), anEdge({ edge_id: 'edge_2', live: false })] }),
        });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} initialMode={MODE_PLAN} />);
        expect(container.textContent).toContain('2 relations drawn');
        expect(container.textContent).toContain('1 no longer in the ledger');
    });

    it('claims no relations on a canvas where none were drawn', async () => {
        // The word itself appears in plan mode's header note (a binding is "not a relation
        // between images") and, since T2, in the Scout's "Suggest relations" action. So this
        // asserts the absence of the CLAIM rather than of the word: no count, and nothing about
        // the ledger. An offer to look is not a claim to have found.
        await mount(<AtlasWorkspace atlasId="atlas_1" service={fakeService()} initialMode={MODE_PLAN} />);
        expect(container.querySelector('.atlas-rel-count')).toBeNull();
        expect(container.textContent).not.toMatch(/\d+ relations? drawn/);
        expect(container.textContent).not.toContain('no longer in the ledger');
    });
});
