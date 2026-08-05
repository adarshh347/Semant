/**
 * ATLAS T1 — the mode framework and the Light Table, mounted.
 *
 * Three things have to hold on this surface or it is quietly dishonest, and none of them are about
 * layout:
 *
 *   1. A mode is a LENS. Switching must not refetch, must not lose an unsaved note, and must not
 *      strand an arrangement — because it is one document, seen two ways.
 *   2. An author note must never read as evidence. Not counted as a percept, not wearing an
 *      epistemic chip, and said in words on the surface.
 *   3. The two lanes never meet. A machine read may only reach the quarantine; a note may never
 *      become a percept, and nothing on this surface offers to make one.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasWorkspace from './AtlasWorkspace.jsx';
import AtlasLightTable from './AtlasLightTable.jsx';
import { MACHINE_READ_INTENTION, MODE_LIGHT_TABLE, flowNodesFromView } from './atlasDocument.js';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
    globalThis.DOMMatrixReadOnly = class { constructor() { this.m22 = 1; } };
}

// The real instrument loads a post over the network and mounts the whole workspace — far too heavy
// for jsdom, and not what is under test. What IS under test is what the Atlas hands it.
vi.mock('./AtlasDifferential.jsx', () => ({
    default: ({ postId, intention, onClose }) => (
        <div data-testid="focus" data-post-id={postId} data-intention={intention || ''}>
            <button type="button" data-testid="done" onClick={onClose}>done</button>
        </div>
    ),
}));

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
};
const type = async (el, text) => {
    // React tracks the DOM value on the node; the native setter is what makes onChange fire.
    const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value').set;
    await act(async () => {
        setter.call(el, text);
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
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

const aView = (over = {}) => ({
    id: 'atlas_1', title: 'the walk', edges: [], unreadable: [],
    nodes: [
        { node_id: 'n0', post_id: 'p1', x: 0, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/1.jpg', title: 'one',
            grounds: [{ id: 'g1' }], regions: [], marks: [], percepts: [], withheld: 0, notes: [] },
        { node_id: 'n1', post_id: 'p2', x: 540, y: 0, w: 420, h: 320, readable: true,
            image_ref: 'https://example.invalid/2.jpg', title: 'two',
            grounds: [], regions: [], marks: [], percepts: [], withheld: 0, notes: [] },
    ],
    ...over,
});

const fakeService = (over = {}) => ({
    view: vi.fn(async () => aView()),
    saveArrangement: vi.fn(async () => ({ atlas: { nodes: [] }, refused: [] })),
    saveNotes: vi.fn(async (id, patches) => ({
        // Echo what was asked for, as the real route does — the client trusts what came BACK.
        atlas: { nodes: patches.map((p) => ({ node_id: p.node_id, notes: p.notes })) },
        refused: [],
    })),
    ...over,
});

const toLightTable = async (service = fakeService()) => {
    await mount(<AtlasWorkspace atlasId="atlas_1" service={service} />);
    await click(container.querySelector(`.atlas-mode[data-mode="${MODE_LIGHT_TABLE}"]`));
    return service;
};

// ── 1. a mode is a lens over one document ───────────────────────────────────

describe('the mode switcher', () => {
    it('offers both ways of looking, with the current one marked', async () => {
        await mount(<AtlasWorkspace atlasId="atlas_1" service={fakeService()} />);
        const modes = [...container.querySelectorAll('.atlas-mode')];
        expect(modes).toHaveLength(2);
        expect(modes.filter((m) => m.getAttribute('aria-pressed') === 'true')).toHaveLength(1);
    });

    it('swaps the renderer and nothing else', async () => {
        await toLightTable();
        expect(container.querySelector('.lt-grid')).toBeTruthy();
        expect(container.querySelector('.atlas-canvas')).toBe(null);
        // Same document, still named on the surface.
        expect(container.textContent).toContain('the walk');
    });

    it('does not re-open the document — it is the same one, looked at differently', async () => {
        const service = await toLightTable();
        expect(service.view).toHaveBeenCalledTimes(1);
    });

    it('shows every image of the corpus in both modes', async () => {
        const service = await toLightTable();
        expect(container.querySelectorAll('.lt-cell')).toHaveLength(2);
        await click(container.querySelector('.atlas-mode[data-mode="canvas"]'));
        expect(service.view).toHaveBeenCalledTimes(1);
        expect(container.querySelectorAll('.react-flow__node')).toHaveLength(2);
    });

    it('keeps a note that has not reached the server yet across a switch', async () => {
        // The state lives in the workspace, above both modes. If it lived in the Light Table, this
        // sentence would be gone the moment a curator glanced at the canvas.
        await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'the light does the arguing');
        await click(container.querySelector('.atlas-mode[data-mode="canvas"]'));
        await click(container.querySelector(`.atlas-mode[data-mode="${MODE_LIGHT_TABLE}"]`));
        expect(container.querySelector('.lt-note-text').value)
            .toBe('the light does the arguing');
    });

    it('says "position asserts nothing" only where there is a position', async () => {
        // On the Canvas it is the rule a reader most tempts themselves to forget; on a grid in
        // corpus order it would be answering a question nobody asked.
        await mount(<AtlasWorkspace atlasId="atlas_1" service={fakeService()} />);
        expect(container.textContent).toMatch(/position is a thinking aid/i);
        await click(container.querySelector(`.atlas-mode[data-mode="${MODE_LIGHT_TABLE}"]`));
        expect(container.textContent).not.toMatch(/position is a thinking aid/i);
    });
});

// ── 2. the Light Table shows the ledger, read-only ──────────────────────────

describe('a Light Table cell', () => {
    it('shows the image and counts what is committed on it', async () => {
        await toLightTable();
        const cell = container.querySelector('.lt-cell');
        expect(cell.querySelector('.atlas-node-img').getAttribute('src'))
            .toBe('https://example.invalid/1.jpg');
        expect(cell.textContent).toContain('1 percept');
    });

    it('says plainly when nothing has been committed yet', async () => {
        await toLightTable();
        expect(container.querySelectorAll('.lt-cell')[1].textContent)
            .toContain('no committed percepts');
    });

    it('renders a withheld suggestion as visible text, never a tooltip', async () => {
        const withheld = aView();
        withheld.nodes[0].withheld = 2;
        await toLightTable(fakeService({ view: vi.fn(async () => withheld) }));
        expect(container.querySelector('.lt-withheld').textContent)
            .toMatch(/2 suggestions not shown/);
    });

    it('keeps an unreadable image in the grid and says why', async () => {
        const gone = aView();
        gone.nodes[0] = { node_id: 'n0', post_id: 'ghost', readable: false,
            unreadable_reason: 'post:ghost could not be read', notes: [] };
        await toLightTable(fakeService({ view: vi.fn(async () => gone) }));
        const cell = container.querySelector('.lt-cell[data-readable="false"]');
        expect(cell.textContent).toContain('could not be read');
    });

    it('offers no way in, and no machine read, on an image that could not be read', async () => {
        const gone = aView();
        gone.nodes[0] = { node_id: 'n0', post_id: 'ghost', readable: false,
            unreadable_reason: 'gone', notes: [] };
        await toLightTable(fakeService({ view: vi.fn(async () => gone) }));
        const cell = container.querySelector('.lt-cell[data-readable="false"]');
        expect(cell.querySelector('[data-open-post]')).toBe(null);
        expect(cell.querySelector('[data-read-post]')).toBe(null);
    });

    it('offers nothing that could commit a percept', async () => {
        // No brush, no review chip, no Accept. Evidence is made in the Differential; this surface
        // shows what the ledger holds and lets the writer say something of their own.
        await toLightTable();
        const cell = container.querySelector('.lt-cell');
        const labels = [...cell.querySelectorAll('button')].map((b) => b.textContent.trim());
        expect(labels.sort()).toEqual(['+ note', 'machine read', 'open →']);
    });
});

// ── 3. the author-notes lane ────────────────────────────────────────────────

describe('author notes', () => {
    it('says on the surface that they are not evidence', async () => {
        await toLightTable();
        const label = container.querySelector('.lt-notes-label');
        expect(label.textContent).toMatch(/Author notes/);
        expect(label.textContent).toMatch(/not evidence/i);
        expect(label.textContent).toMatch(/never cited/i);
    });

    it('wears none of the five epistemic chips', async () => {
        // The vocabulary grades how well a claim is GROUNDED. A note claims nothing, so giving it
        // even the weakest chip would file it inside a system it does not belong to.
        await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'a thought');
        const slot = container.querySelector('.lt-notes');
        expect(slot.textContent).not.toMatch(/grounded|uncertain|sourced|conjecture|external limit/i);
        expect(slot.querySelector('[class*="epistemic"], [class*="chip"]')).toBe(null);
    });

    it('is never added to the percept count', async () => {
        await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'a thought');
        // One committed ground across the corpus, before and after a note exists.
        expect(container.textContent).toContain('1 committed percept');
        expect(container.querySelector('.lt-cell').textContent).toContain('1 percept');
    });

    it('is counted and named separately in the header, as notes', async () => {
        await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'a thought');
        expect(container.textContent).toContain('1 author note');
    });

    it('saves what was typed, on its own route, carrying only text', async () => {
        const service = await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'the light does the arguing');
        await act(async () => { await new Promise((r) => setTimeout(r, 700)); });

        expect(service.saveNotes).toHaveBeenCalledTimes(1);
        const [atlasId, patches] = service.saveNotes.mock.calls[0];
        expect(atlasId).toBe('atlas_1');
        expect(patches[0].node_id).toBe('n0');
        expect(patches[0].notes[0].text).toBe('the light does the arguing');
        expect(Object.keys(patches[0].notes[0]).sort()).toEqual(['note_id', 'text']);
        // And it never travels on the arrangement route.
        expect(service.saveArrangement).not.toHaveBeenCalled();
    });

    it('shows a note the document already held', async () => {
        const withNote = aView();
        withNote.nodes[0].notes = [{ note_id: 'a', text: 'written last week' }];
        await toLightTable(fakeService({ view: vi.fn(async () => withNote) }));
        expect(container.querySelector('.lt-note-text').value).toBe('written last week');
    });

    it('deletes a note the writer emptied', async () => {
        const withNote = aView();
        withNote.nodes[0].notes = [{ note_id: 'a', text: 'take it back' }];
        const service = await toLightTable(fakeService({ view: vi.fn(async () => withNote) }));
        await type(container.querySelector('.lt-note-text'), '');
        await act(async () => { await new Promise((r) => setTimeout(r, 700)); });
        expect(service.saveNotes.mock.calls[0][1]).toEqual([{ node_id: 'n0', notes: [] }]);
    });

    it('says so when a note did not save, rather than leaving it looking saved', async () => {
        // The writer will close the tab on the strength of seeing their own sentence on screen.
        const service = await toLightTable(fakeService({
            saveNotes: vi.fn(async () => { throw new Error('notes route unreachable'); }),
        }));
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'x');
        await act(async () => { await new Promise((r) => setTimeout(r, 700)); });
        expect(service.saveNotes).toHaveBeenCalled();
        expect(container.querySelector('.atlas-banner.is-error').textContent)
            .toContain('notes route unreachable');
    });

    it('renders a refusal from the notes save as a sentence', async () => {
        await toLightTable(fakeService({
            saveNotes: vi.fn(async () => ({
                atlas: { nodes: [] },
                refused: [{ node_id: 'n0', reason: 'too_many_notes',
                    detail: 'an image holds at most 12 notes; 1 not saved' }],
            })),
        }));
        await click(container.querySelector('[data-add-note="n0"]'));
        await type(container.querySelector('.lt-note-text'), 'x');
        await act(async () => { await new Promise((r) => setTimeout(r, 700)); });
        expect(container.querySelector('.atlas-banner.is-refused').textContent)
            .toContain('1 not saved');
    });
});

// ── 4. the machine-read lane, and the wall between them ─────────────────────

describe('the machine read', () => {
    it('hands the image to the Differential with the act already chosen', async () => {
        await toLightTable();
        await click(container.querySelector('[data-read-post="p1"]'));
        const focus = container.querySelector('[data-testid="focus"]');
        expect(focus.getAttribute('data-post-id')).toBe('p1');
        expect(focus.getAttribute('data-intention')).toBe(MACHINE_READ_INTENTION);
    });

    it('is the same path as opening by hand, minus the intention', async () => {
        // One way in, not two. `open →` differs only in arriving with nothing asked for.
        await toLightTable();
        await click(container.querySelector('[data-open-post="p1"]'));
        expect(container.querySelector('[data-testid="focus"]').getAttribute('data-intention'))
            .toBe('');
    });

    it('asks the ledger what changed when the curator comes back', async () => {
        const service = await toLightTable();
        await click(container.querySelector('[data-read-post="p1"]'));
        expect(service.view).toHaveBeenCalledTimes(1);
        await click(container.querySelector('[data-testid="done"]'));
        expect(service.view).toHaveBeenCalledTimes(2);
        expect(container.querySelector('.lt-grid')).toBeTruthy();
    });

    it('shows an accepted percept as an overlay, and returns to the mode it left', async () => {
        // The T1 demo criterion's second half. The Atlas is never TOLD what was made — the second
        // read of the ledger is what carries it onto the surface — and the machine read must not
        // dump the curator back on a canvas they were not using.
        let call = 0;
        const service = fakeService({
            view: vi.fn(async () => {
                call += 1;
                const v = aView();
                if (call > 1) v.nodes[0].grounds = [{ id: 'g1' }, { id: 'g_new' }];
                return v;
            }),
        });
        await toLightTable(service);
        await click(container.querySelector('[data-read-post="p1"]'));
        await click(container.querySelector('[data-testid="done"]'));
        expect(container.querySelector('.lt-grid')).toBeTruthy();
        expect(container.textContent).toContain('2 committed percepts');
        expect(container.querySelector('.lt-cell').textContent).toContain('2 percepts');
    });

    it('cannot write an author note', async () => {
        // THE wall. A machine read returns through `/view`, and `/view` carries notes from the
        // ATLAS document — so a percept arriving from the Director has no path into the writer's
        // own voice. If it ever did, the writer could no longer tell which lines were theirs.
        const spoken = aView();
        spoken.nodes[0].notes = [{ note_id: 'mine', text: 'my own line' }];
        let call = 0;
        const service = fakeService({
            view: vi.fn(async () => {
                call += 1;
                const v = aView();
                v.nodes[0].notes = [{ note_id: 'mine', text: 'my own line' }];
                if (call > 1) v.nodes[0].grounds = [{ id: 'g1' }, { id: 'g_new' }];
                return v;
            }),
        });
        await toLightTable(service);
        await click(container.querySelector('[data-read-post="p1"]'));
        await click(container.querySelector('[data-testid="done"]'));
        const texts = [...container.querySelectorAll('.lt-note-text')].map((t) => t.value);
        expect(texts).toEqual(['my own line']);
        expect(service.saveNotes).not.toHaveBeenCalled();
        expect(spoken.nodes[0].notes).toHaveLength(1);
    });

    it('offers no way to turn a note into a percept', async () => {
        // The other direction of the same wall, checked where it would have to appear.
        await toLightTable();
        await click(container.querySelector('[data-add-note="n0"]'));
        const slot = container.querySelector('.lt-notes');
        const labels = [...slot.querySelectorAll('button')].map((b) => b.textContent.toLowerCase());
        expect(labels.some((l) => /accept|commit|promote|percept|evidence|cite/.test(l)))
            .toBe(false);
    });
});

// ── the renderer both modes share ───────────────────────────────────────────

describe('the shared percept renderer', () => {
    it('draws the Light Table cell from the same node data the canvas uses', async () => {
        // One renderer, two layouts. A second copy is how a percept ends up drawn 20px off in one
        // mode and not the other — a claim about a part of the picture nobody measured.
        const nodes = flowNodesFromView(aView());
        await mount(<AtlasLightTable nodes={nodes} onNotesChange={() => {}}
            onMachineRead={() => {}} />);
        expect(container.querySelectorAll('.lt-cell')).toHaveLength(2);
        expect(container.querySelector('.atlas-stage')).toBeTruthy();
    });

    it('says so when the Atlas has no images rather than showing an empty grid', async () => {
        await mount(<AtlasLightTable nodes={[]} onNotesChange={() => {}} onMachineRead={() => {}} />);
        expect(container.textContent).toMatch(/no images/i);
    });
});
