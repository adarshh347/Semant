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
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// T1 moved the document, both saves and the Differential path out of `AtlasCanvas` and up into
// `AtlasWorkspace`, so every mode shares one copy of them. These assertions are unchanged in
// substance — they were always about the Atlas SURFACE, which is what the workspace now is, and
// `AtlasCanvas` is now the renderer it hands nodes to.
import AtlasWorkspace from './AtlasWorkspace.jsx';
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
    saveNotes: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    ...over,
});

// ── the node ────────────────────────────────────────────────────────────────

describe('an image node', () => {
    it('shows the picture and counts what is committed on it', async () => {
        await mount(<AtlasImageNode data={nodeData()} />);
        expect(container.querySelector('.atlas-node-img').getAttribute('src'))
            .toBe('https://example.invalid/1.jpg');
        expect(container.textContent).toContain('2 percepts');
    });

    it('says so plainly when nothing has been committed yet', async () => {
        await mount(<AtlasImageNode data={nodeData({ grounds: [] })} />);
        expect(container.textContent).toContain('no committed percepts');
    });

    it('stays on the canvas when the image could not be read, and says why', async () => {
        await mount(<AtlasImageNode data={nodeData({
            readable: false, unreadableReason: 'post:ghost could not be read' })} />);
        const node = container.querySelector('.atlas-node');
        expect(node.getAttribute('data-readable')).toBe('false');
        expect(container.textContent).toContain('could not be read');
    });

    it('renders a withheld suggestion as visible text, never a tooltip', async () => {
        await mount(<AtlasImageNode data={nodeData({ withheld: 2 })} />);
        const note = container.querySelector('.atlas-node-withheld');
        expect(note).toBeTruthy();
        expect(note.textContent).toMatch(/2 suggestions not shown/);
        // and the count of what IS drawn does not silently include it
        expect(container.textContent).toContain('2 percepts');
    });

    it('offers nothing that could change a percept ON THE NODE', async () => {
        // C2 adds exactly one control, and what it does is LEAVE. There is still no brush, no
        // review chip and no Accept here — a second, smaller Differential is what that would be.
        await mount(<AtlasImageNode data={nodeData({ onOpen: () => {} })} />);
        const buttons = [...container.querySelectorAll('button')];
        expect(buttons).toHaveLength(1);
        expect(buttons[0].getAttribute('data-open-post')).toBe('p1');
        expect(container.querySelectorAll('input').length).toBe(0);
    });

    it('shows no way in until one is given', async () => {
        await mount(<AtlasImageNode data={nodeData()} />);
        expect(container.querySelectorAll('button').length).toBe(0);
    });
});

// ── C2: the way into the Differential ───────────────────────────────────────

describe('opening an image in the Differential', () => {
    it('hands back the post id the node stands for', async () => {
        const onOpen = vi.fn();
        await mount(<AtlasImageNode data={nodeData({ onOpen })} />);
        await act(async () => {
            container.querySelector('[data-open-post]').dispatchEvent(
                new MouseEvent('click', { bubbles: true }));
        });
        expect(onOpen).toHaveBeenCalledWith('p1');
    });

    it('carries the nodrag class, or React Flow eats the click', async () => {
        await mount(<AtlasImageNode data={nodeData({ onOpen: () => {} })} />);
        expect(container.querySelector('[data-open-post]').className).toContain('nodrag');
    });

    it('offers no way in on an image that could not be read', async () => {
        // A dead end dressed as an affordance. `flowNodesFromView` withholds the callback.
        await mount(<AtlasImageNode data={nodeData({
            readable: false, unreadableReason: 'post:ghost could not be read', onOpen: null })} />);
        expect(container.querySelector('[data-open-post]')).toBe(null);
    });
});

// ── the canvas ──────────────────────────────────────────────────────────────

describe('the canvas', () => {
    it('opens an Atlas and reports what is on it', async () => {
        const service = fakeService();
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
        expect(service.view).toHaveBeenCalledWith('atlas_1');
        expect(container.textContent).toContain('the walk');
        expect(container.textContent).toContain('2 images');
        expect(container.textContent).toContain('1 committed percept');
    });

    it('says on the surface that position asserts nothing', async () => {
        await mount(<AtlasWorkspace atlasId="atlas_1" service={fakeService()} />);
        expect(container.textContent).toMatch(/position is a thinking aid/i);
    });

    it('names the images the corpus could not read', async () => {
        const service = fakeService({
            view: async () => aView({ unreadable: ['gone'] }),
        });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
        const banner = container.querySelector('.atlas-banner.is-unreadable');
        expect(banner).toBeTruthy();
        expect(banner.textContent).toMatch(/could not be read/);
        // "on the Atlas", not "on the canvas": T1 shows this banner in every mode, and an
        // unreadable image stays in the Light Table's grid for the same reason it stays on the
        // canvas — dropping it would quietly shrink the corpus.
        expect(banner.textContent).toMatch(/stays on the Atlas/);
    });

    it('reports a failure to open rather than showing an empty canvas', async () => {
        const service = fakeService({ view: async () => { throw new Error('nope'); } });
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
        expect(container.querySelector('[role="alert"]').textContent).toContain('nope');
    });

    it('draws no edges — a relation is a percept, and that is C3', async () => {
        await mount(<AtlasWorkspace atlasId="atlas_1" service={fakeService()} />);
        expect(container.querySelectorAll('.react-flow__edge').length).toBe(0);
    });
});

// ── C2: the round trip ──────────────────────────────────────────────────────
// The real `AtlasDifferential` loads a post over the network and mounts the whole workspace —
// far too heavy for jsdom, and not what is under test here. What IS under test is the canvas's
// half of the contract: hand the instrument a post id, and on return ask the LEDGER what changed.

vi.mock('./AtlasDifferential.jsx', () => ({
    default: ({ postId, intention, onClose }) => (
        <div data-testid="focus" data-post-id={postId} data-intention={intention || ''}>
            <button type="button" data-testid="done" onClick={onClose}>done</button>
        </div>
    ),
}));

const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
};

describe('the canvas ⇄ the Differential', () => {
    const openFirst = async (service) => {
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
        await click(container.querySelector('[data-open-post]'));
    };

    it('gives the instrument the viewport, for the image that was asked for', async () => {
        await openFirst(fakeService());
        const focus = container.querySelector('[data-testid="focus"]');
        expect(focus).toBeTruthy();
        expect(focus.getAttribute('data-post-id')).toBe('p1');
        // The canvas steps aside rather than sitting live underneath, competing for gestures.
        expect(container.querySelector('.atlas-canvas')).toBe(null);
    });

    it('asks the ledger what changed when the curator comes back', async () => {
        const service = fakeService();
        await openFirst(service);
        expect(service.view).toHaveBeenCalledTimes(1);
        await click(container.querySelector('[data-testid="done"]'));
        expect(service.view).toHaveBeenCalledTimes(2);
        expect(container.querySelector('.atlas-canvas')).toBeTruthy();
    });

    it('shows a percept accepted in the Differential as an overlay on the node', async () => {
        // The C2 demo criterion. The Atlas is never TOLD what was made — the second read of the
        // ledger is what carries the new percept onto the canvas.
        let call = 0;
        const service = fakeService({
            view: vi.fn(async () => {
                call += 1;
                if (call === 1) return aView();
                const after = aView();
                after.nodes[0].grounds = [{ id: 'g1' }, { id: 'g_new' }];
                return after;
            }),
        });
        await openFirst(service);
        await click(container.querySelector('[data-testid="done"]'));
        // 1 (p1) + 0 (p2) before; 2 + 0 after.
        expect(container.textContent).toContain('2 committed percepts');
        expect(container.textContent).toContain('2 percepts');
    });

    it('does not undo an arrangement the curator is still mid-drag on', async () => {
        // The refresh replaces `data`, never `position`. Taking positions from the refetch would
        // snap a node back to the last save and discard a drag still inside its debounce.
        const service = fakeService();
        await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
        const before = container.querySelector('.react-flow__node').style.transform;
        await click(container.querySelector('[data-open-post]'));
        await click(container.querySelector('[data-testid="done"]'));
        expect(container.querySelector('.react-flow__node').style.transform).toBe(before);
    });

    it('says so if the ledger cannot be re-read, rather than showing stale overlays as fresh',
        async () => {
            let call = 0;
            const service = fakeService({
                view: vi.fn(async () => {
                    call += 1;
                    if (call === 1) return aView();
                    throw new Error('ledger unreachable');
                }),
            });
            await openFirst(service);
            await click(container.querySelector('[data-testid="done"]'));
            expect(container.querySelector('.atlas-banner.is-error').textContent)
                .toContain('ledger unreachable');
        });
});
