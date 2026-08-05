/**
 * ATLAS T2 — the Scout, mounted: what confirming a ghost actually does.
 *
 * `atlasScout.test.js` pins what a candidate IS. This pins the one thing the whole gate rests on:
 *
 *   CONFIRMING A GHOST IS THE SAME CALL AS DRAWING A LINE BY HAND.
 *
 * If it were not — if confirming had a path of its own — that path would be a way to draw a
 * relation between two photographs without `compare_views` having looked at either, and the
 * model's hunch would become evidence by being clicked. So the tests below check the CALL, not
 * just the outcome: `drawRelation` and nothing else, with the candidate's own pair.
 *
 * React Flow lays nothing out in jsdom, so no ghost element is emitted here — the drawn line is
 * verified in a real browser. What is testable is the contract.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ReactFlowProvider } from '@xyflow/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasCanvas from './AtlasCanvas.jsx';

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
const mount = async (node) => {
    await act(async () => { root.render(<ReactFlowProvider>{node}</ReactFlowProvider>); });
};
const click = async (el) => {
    expect(el).toBeTruthy();
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
};

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

const node = (id, post, x) => ({
    node_id: id, post_id: post, x, y: 0, w: 420, h: 320, readable: true,
    image_ref: `https://example.invalid/${post}.jpg`, title: post,
    grounds: [], regions: [], marks: [], percepts: [], withheld: 0,
});

const aView = (over = {}) => ({
    id: 'atlas_1', title: 'the walk', edges: [], plan: null, unreadable: [],
    nodes: [node('n0', 'p1', 0), node('n1', 'p2', 540), node('n2', 'p3', 1080)],
    ...over,
});

const twoCandidates = {
    candidates: [
        { from: 'n0', to: 'n1', rationale: 'both hold a curved rail' },
        { from: 'n1', to: 'n2', rationale: 'the crowd repeats the balustrade' },
    ],
    dropped: [],
};

const fakeService = (over = {}) => ({
    view: vi.fn(async () => aView()),
    saveArrangement: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    proposePlan: vi.fn(async () => ({ claims: [], connectors: [], counts: {}, refusals: [] })),
    acceptPlan: vi.fn(async () => ({ plan: null })),
    clearPlan: vi.fn(async () => ({ plan: null })),
    drawRelation: vi.fn(async () => ({ atlas: {}, edge: anEdge() })),
    removeRelation: vi.fn(async () => ({ removed: 'edge_1' })),
    scout: vi.fn(async () => twoCandidates),
    ...over,
});

const openWithCandidates = async (service = fakeService()) => {
    await mount(<AtlasCanvas atlasId="atlas_1" service={service} />);
    await click(container.querySelector('[data-scout]'));
    return service;
};

// ── asking ──────────────────────────────────────────────────────────────────

describe('asking the Scout', () => {
    it('offers the action in the header, worded as a suggestion', async () => {
        // "Suggest", never "Find": the Scout has not looked at a photograph and cannot find
        // anything in one.
        await mount(<AtlasCanvas atlasId="atlas_1" service={fakeService()} />);
        const button = container.querySelector('[data-scout]');
        expect(button.textContent).toMatch(/suggest/i);
        expect(button.textContent).not.toMatch(/find/i);
    });

    it('lists each candidate with its own rationale', async () => {
        await openWithCandidates();
        const items = [...container.querySelectorAll('.atlas-scout-item')];
        expect(items).toHaveLength(2);
        expect(items[0].textContent).toContain('both hold a curved rail');
    });

    it('says on the surface that nothing proposed is a relation yet', async () => {
        await openWithCandidates();
        expect(container.querySelector('.atlas-scout').textContent)
            .toMatch(/nothing here is a relation yet/i);
        expect(container.querySelector('.atlas-scout').textContent)
            .toMatch(/can refuse/i);
    });

    it('persists nothing when it asks', async () => {
        const service = await openWithCandidates();
        expect(service.scout).toHaveBeenCalledWith('atlas_1');
        expect(service.drawRelation).not.toHaveBeenCalled();
        expect(service.saveArrangement).not.toHaveBeenCalled();
    });

    it('shows what the Scout was not allowed to propose', async () => {
        // Never swallowed: how often a model invents an image is what tells a writer how far to
        // trust the next batch.
        const service = fakeService({
            scout: vi.fn(async () => ({
                candidates: [{ from: 'n0', to: 'n1', rationale: 'kept' }],
                dropped: [{ reason: 'unknown_node', from: 'n0', to: 'n9' },
                    { reason: 'named_a_relation', from: 'n1', to: 'n2' }],
            })),
        });
        await openWithCandidates(service);
        const note = container.querySelector('.atlas-banner.is-dropped');
        expect(note.textContent).toMatch(/named an image not on this Atlas/);
        expect(note.textContent).toMatch(/Only the comparison may do that/);
    });

    it('says a dead scout is dead rather than showing an empty canvas', async () => {
        const service = fakeService({
            scout: vi.fn(async () => ({
                refused: { reason: 'model_unavailable', detail: 'GROQ_API_KEY unset' } })),
        });
        await openWithCandidates(service);
        expect(container.querySelector('[role="alert"]').textContent)
            .toMatch(/could not be reached/);
        expect(container.querySelectorAll('.atlas-scout-item')).toHaveLength(0);
    });

    it('clears the previous batch when a new ask refuses', async () => {
        // Stale hunches under a fresh refusal would read as this run's answer.
        let call = 0;
        const service = fakeService({
            scout: vi.fn(async () => {
                call += 1;
                return call === 1 ? twoCandidates
                    : { refused: { reason: 'nothing_proposed', detail: 'nothing allowed' } };
            }),
        });
        await openWithCandidates(service);
        expect(container.querySelectorAll('.atlas-scout-item')).toHaveLength(2);
        await click(container.querySelector('[data-scout]'));
        expect(container.querySelectorAll('.atlas-scout-item')).toHaveLength(0);
    });
});

// ── THE gate: confirming runs the real comparison ───────────────────────────

describe('confirming a candidate', () => {
    it('calls C3’s draw path — the same one the drag gesture uses', async () => {
        const service = await openWithCandidates();
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        expect(service.drawRelation).toHaveBeenCalledTimes(1);
        expect(service.drawRelation).toHaveBeenCalledWith('atlas_1',
            { source_node: 'n0', target_node: 'n1' });
    });

    it('sends the pair and NOTHING the model said about it', async () => {
        // The rationale is a hunch. Passing it to the gate would let the model's wording reach
        // `compare_views` as an instruction about what to find.
        const service = await openWithCandidates();
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        const body = service.drawRelation.mock.calls[0][1];
        expect(Object.keys(body).sort()).toEqual(['source_node', 'target_node']);
        expect(JSON.stringify(body)).not.toContain('curved rail');
    });

    it('re-reads the ledger rather than trusting what it sent', async () => {
        const service = await openWithCandidates();
        expect(service.view).toHaveBeenCalledTimes(1);
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        expect(service.view).toHaveBeenCalledTimes(2);
    });

    it('carries a real comparative percept when it grounds', async () => {
        // The gate's own answer, which is the only thing that makes this an edge rather than a
        // hunch: an edge with a mark id is a `compare_views` percept in the ledger.
        let call = 0;
        const service = fakeService({
            view: vi.fn(async () => {
                call += 1;
                return call === 1 ? aView() : aView({ edges: [anEdge()] });
            }),
        });
        await openWithCandidates(service);
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        expect(service.drawRelation).toHaveBeenCalled();
        expect(container.textContent).toMatch(/1 relation drawn/);
        // and the ghost is gone — a duplicate claim in a weaker style beside a real one
        expect(container.querySelector('[data-candidate="n0~n1"]')).toBe(null);
    });

    it('vanishes with the gate’s reason when the comparison refuses', async () => {
        const service = fakeService({
            drawRelation: vi.fn(async () => ({ refused: {
                reason: 'gate_refused', source_node: 'n0', target_node: 'n1',
                detail: 'these two images carry no marks to compare' } })),
        });
        await openWithCandidates(service);
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        // the ghost is answered and gone
        expect(container.querySelector('[data-candidate="n0~n1"]')).toBe(null);
        // and the reason is on screen, not swallowed
        expect(container.textContent).toMatch(/no marks to compare/);
        // nothing was drawn
        expect(container.textContent).not.toMatch(/1 relation drawn/);
    });

    it('leaves the other candidates alone', async () => {
        const service = await openWithCandidates();
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        expect(container.querySelector('[data-candidate="n1~n2"]')).toBeTruthy();
    });

    it('says so rather than silently failing when the gate cannot be reached', async () => {
        const service = fakeService({
            drawRelation: vi.fn(async () => { throw new Error('relations route unreachable'); }),
        });
        await openWithCandidates(service);
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        expect(container.textContent).toMatch(/relations route unreachable/);
    });
});

// ── dismissing persists nothing ─────────────────────────────────────────────

describe('dismissing a candidate', () => {
    it('removes it without asking the gate anything', async () => {
        const service = await openWithCandidates();
        await click(container.querySelector('[data-dismiss="n0~n1"]'));
        expect(container.querySelector('[data-candidate="n0~n1"]')).toBe(null);
        expect(service.drawRelation).not.toHaveBeenCalled();
    });

    it('writes nothing anywhere — there was never anything to undo', async () => {
        const service = await openWithCandidates();
        await click(container.querySelector('[data-dismiss="n0~n1"]'));
        await click(container.querySelector('[data-dismiss="n1~n2"]'));
        expect(service.drawRelation).not.toHaveBeenCalled();
        expect(service.saveArrangement).not.toHaveBeenCalled();
        expect(service.acceptPlan).not.toHaveBeenCalled();
        // and the view was read once, on open — dismissing is not a ledger event
        expect(service.view).toHaveBeenCalledTimes(1);
    });
});

// ── the wall, stated as a test ──────────────────────────────────────────────

describe('there is no way to persist a ghost without grounding it', () => {
    it('offers exactly two things to do with a candidate, and one of them runs the gate',
        async () => {
            await openWithCandidates();
            const item = container.querySelector('[data-candidate="n0~n1"]');
            const labels = [...item.querySelectorAll('button')].map((b) => b.textContent.trim());
            expect(labels).toEqual(['confirm', 'dismiss']);
        });

    it('never reaches any service method that could store an edge directly', async () => {
        // The Scout's own route cannot write (proved in the backend suite). This is the client
        // half: whatever a curator does with a candidate, only `drawRelation` is ever called.
        const service = await openWithCandidates();
        await click(container.querySelector('[data-confirm="n0~n1"]'));
        await click(container.querySelector('[data-dismiss="n1~n2"]'));
        const called = Object.entries(service)
            .filter(([, fn]) => fn.mock?.calls?.length)
            .map(([name]) => name)
            .sort();
        expect(called).toEqual(['drawRelation', 'scout', 'view']);
    });
});
