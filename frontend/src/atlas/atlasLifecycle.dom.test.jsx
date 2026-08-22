/**
 * ATLAS lifecycle — three ways in, and the thin controls beside what they act on.
 *
 * THE PROVEN DEFECT: `AtlasPage.openCorpus()` sent `{corpus_id}` to a client that destructured
 * only `title`, `post_ids` and `run_id`. The id was dropped on the floor, the server was asked for
 * an Atlas over `post_ids: []`, and a saved walk could not be opened. No seam test caught it,
 * because every test mocked the service and none looked at the wire. These look at the wire.
 *
 * Every fixture is synthetic.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AtlasPage from './AtlasPage.jsx';
import { completedRuns, splitArchived } from './atlasDocument.js';
import { atlasService, createBody } from './atlasService.js';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const click = async (el) => { await act(async () => { el.click(); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

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

const res = (status, body = {}) => ({
    ok: status >= 200 && status < 300, status, json: async () => body,
});

/** A fetch that routes by method + path, and records every request body it saw. */
function fakeFetch(handlers) {
    const calls = [];
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init = {}) => {
        const method = (init.method || 'GET').toUpperCase();
        const body = init.body ? JSON.parse(init.body) : null;
        calls.push({ method, url: String(url), body });
        for (const [m, re, fn] of handlers) {
            if (m === method && re.test(String(url))) return fn({ url: String(url), body });
        }
        return res(404, { detail: `unrouted ${method} ${url}` });
    });
    return { spy, calls };
}

const aWalk = (id = 'corpus_w', order = ['p3', 'p1', 'p2']) => ({
    id, title: 'the approach', why: '',
    images: order.map((p, n) => ({ post_id: p, position: n, note: n === 0 ? 'first' : '' })),
});
const anAtlas = (over = {}) => ({
    id: 'atlas_9', title: 'the approach', archived: false,
    corpus_ref: { kind: 'curated', corpus_id: 'corpus_w', post_ids: ['p3', 'p1', 'p2'] },
    nodes: ['p3', 'p1', 'p2'].map((p, n) => ({ node_id: `n${n}`, post_id: p })),
    ...over,
});

function Probe() {
    const { pathname } = useLocation();
    return <span data-path>{pathname}</span>;
}
const index = () => (
    <MemoryRouter initialEntries={['/atlas']}>
        <AtlasPage />
        <Probe />
    </MemoryRouter>
);
const pathNow = () => container.querySelector('[data-path]').textContent;

// A baseline set of routes: no posts, one walk, no atlases, no runs.
// Overrides first: the first handler that matches answers.
const baseline = (over = []) => fakeFetch([
    ...over,
    ['GET', /\/api\/v1\/posts\//, () => res(200, { posts: [] })],
    ['GET', /\/api\/v1\/corpora\/$/, () => res(200, { corpora: [aWalk()] })],
    ['GET', /\/api\/v1\/atlas\/(\?.*)?$/, () => res(200, { atlases: [] })],
    ['GET', /\/api\/v1\/runs\//, () => res(200, { runs: [] })],
]);

// ── the create body: exactly one source ─────────────────────────────────────

describe('createBody', () => {
    it('sends an explicit selection as post_ids, in order, and nothing else', () => {
        expect(createBody({ title: 'a walk', post_ids: ['p3', 'p1'] }))
            .toEqual({ title: 'a walk', post_ids: ['p3', 'p1'] });
    });

    it('sends a saved walk as corpus_id ALONE — no post_ids the browser made up', () => {
        const body = createBody({ corpus_id: 'corpus_w' });
        expect(body).toEqual({ title: '', corpus_id: 'corpus_w' });
        expect('post_ids' in body).toBe(false);
        expect('run_id' in body).toBe(false);
    });

    it('sends a run as run_id alone', () => {
        const body = createBody({ title: 't', run_id: 'run_1' });
        expect(body).toEqual({ title: 't', run_id: 'run_1' });
        expect('post_ids' in body).toBe(false);
    });

    it('does not sort or dedupe the selection — a corpus is a sequence', () => {
        expect(createBody({ post_ids: ['c', 'a', 'b'] }).post_ids).toEqual(['c', 'a', 'b']);
    });
});

describe('atlasService.create, on the wire', () => {
    const each = async (source) => {
        const { calls } = fakeFetch([['POST', /\/api\/v1\/atlas\/$/, () => res(201, anAtlas())]]);
        await atlasService.create(source);
        return calls[0];
    };

    it('POSTs the selection as post_ids', async () => {
        const { body } = await each({ title: 'x', post_ids: ['p2', 'p1'] });
        expect(body).toEqual({ title: 'x', post_ids: ['p2', 'p1'] });
    });

    it('POSTs the corpus id — the defect, pinned at the seam', async () => {
        const { body } = await each({ corpus_id: 'corpus_w' });
        expect(body).toEqual({ title: '', corpus_id: 'corpus_w' });
        expect(body.post_ids).toBeUndefined();
    });

    it('POSTs the run id', async () => {
        const { body } = await each({ run_id: 'run_1' });
        expect(body).toEqual({ title: '', run_id: 'run_1' });
    });

    it('carries the server’s own sentence when it refuses', async () => {
        fakeFetch([['POST', /\/api\/v1\/atlas\/$/,
            () => res(409, { detail: "corpus 'x' holds no images" })]]);
        await expect(atlasService.create({ corpus_id: 'x' })).rejects.toThrow(/holds no images/);
    });

    it('asks for the archived canvases only when told to', async () => {
        const { calls } = fakeFetch([['GET', /\/api\/v1\/atlas\//, () => res(200, { atlases: [] })]]);
        await atlasService.list();
        await atlasService.list({ includeArchived: true });
        expect(calls[0].url).toMatch(/\/api\/v1\/atlas\/$/);
        expect(calls[1].url).toMatch(/\/api\/v1\/atlas\/\?include_archived=true$/);
    });
});

// ── the mounted index: a saved walk opens, and the route follows the Atlas ──

describe('opening a saved walk from the index', () => {
    it('navigates only after a valid Atlas has come back, with corpus_id on the wire', async () => {
        let answer;
        const pending = new Promise((resolve) => { answer = resolve; });
        const { calls } = baseline([['POST', /\/api\/v1\/atlas\/$/, () => pending]]);
        await mount(index());

        const walk = container.querySelector('[data-corpus="corpus_w"]');
        expect(walk).toBeTruthy();
        await click(walk);

        const post = calls.find((c) => c.method === 'POST');
        expect(post.body).toEqual({ title: '', corpus_id: 'corpus_w' });
        expect(post.body.post_ids).toBeUndefined();
        // Still here: the server has not answered.
        expect(pathNow()).toBe('/atlas');
        expect(walk.disabled).toBe(true);

        await act(async () => { answer(res(201, anAtlas())); await pending; });
        await settle();
        expect(pathNow()).toBe('/atlas/atlas_9');
    });

    it('stays put and says why when the server refuses', async () => {
        baseline([['POST', /\/api\/v1\/atlas\/$/,
            () => res(409, { detail: "corpus 'corpus_w' holds no images" })]]);
        await mount(index());
        await click(container.querySelector('[data-corpus="corpus_w"]'));
        await settle();
        expect(pathNow()).toBe('/atlas');
        expect(container.querySelector('[data-shelf-error]').textContent).toMatch(/holds no images/);
        expect(container.querySelector('[data-corpus="corpus_w"]').disabled).toBe(false);
    });

    it('does not navigate on a 2xx that carries no Atlas', async () => {
        baseline([['POST', /\/api\/v1\/atlas\/$/, () => res(201, {})]]);
        await mount(index());
        await click(container.querySelector('[data-corpus="corpus_w"]'));
        await settle();
        expect(pathNow()).toBe('/atlas');
        expect(container.querySelector('[data-shelf-error]').textContent).toMatch(/no Atlas/);
    });
});

// ── a completed run is a way in; a running one is not ───────────────────────

describe('opening a run’s corpus', () => {
    const runs = [
        { run_id: 'run_done', status: 'complete', prompt: 'the colonnade', mode: 'explore' },
        { run_id: 'run_live', status: 'running', prompt: 'still going', mode: 'explore' },
        { run_id: 'run_halt', status: 'stopped', prompt: 'halted', mode: 'explore' },
    ];

    it('lists only the runs that finished', () => {
        expect(completedRuns(runs).map((r) => r.run_id)).toEqual(['run_done']);
        expect(completedRuns(null)).toEqual([]);
    });

    it('sends run_id alone and follows the Atlas', async () => {
        const { calls } = baseline([
            ['GET', /\/api\/v1\/runs\//, () => res(200, { runs })],
            ['POST', /\/api\/v1\/atlas\/$/, () => res(201, anAtlas({ id: 'atlas_r' }))],
        ]);
        await mount(index());
        expect(container.querySelector('[data-run="run_live"]')).toBe(null);
        await click(container.querySelector('[data-run="run_done"]'));
        await settle();
        expect(calls.find((c) => c.method === 'POST').body).toEqual({ title: '', run_id: 'run_done' });
        expect(pathNow()).toBe('/atlas/atlas_r');
    });

    it('renders no run section when there are none, rather than a placeholder', async () => {
        baseline();
        await mount(index());
        expect(container.querySelector('[aria-label="Completed runs"]')).toBe(null);
    });
});

// ── the Atlas lifecycle: rename, archive, restore, duplicate ────────────────

describe('the shelf', () => {
    it('splits what is out from what was put away, without losing either', () => {
        const { open, archived } = splitArchived([anAtlas(), anAtlas({ id: 'a2', archived: true })]);
        expect(open.map((a) => a.id)).toEqual(['atlas_9']);
        expect(archived.map((a) => a.id)).toEqual(['a2']);
    });

    it('renames over PATCH and redraws the row from what came back', async () => {
        const { calls } = baseline([
            ['GET', /\/api\/v1\/atlas\/\?include_archived=true$/, () => res(200, { atlases: [anAtlas()] })],
            ['PATCH', /\/api\/v1\/atlas\/atlas_9$/, ({ body }) => res(200, anAtlas({ title: body.title }))],
        ]);
        await mount(index());
        await click(container.querySelector('[data-atlas="atlas_9"] [data-rename]'));
        const input = container.querySelector('[data-atlas="atlas_9"] input');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'the approach, revisited');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => {
            container.querySelector('[data-atlas="atlas_9"] form').dispatchEvent(
                new Event('submit', { bubbles: true, cancelable: true }));
        });
        await settle();
        const patch = calls.find((c) => c.method === 'PATCH');
        expect(patch.body).toEqual({ title: 'the approach, revisited' });
        expect(container.querySelector('[data-atlas="atlas_9"] .atlas-list-title').textContent)
            .toBe('the approach, revisited');
    });

    it('archives over PATCH, moves the row to the put-away list, and restores it again', async () => {
        const { calls } = baseline([
            ['GET', /\/api\/v1\/atlas\/\?include_archived=true$/, () => res(200, { atlases: [anAtlas()] })],
            ['PATCH', /\/api\/v1\/atlas\/atlas_9$/, ({ body }) => res(200, anAtlas({ archived: body.archived }))],
        ]);
        await mount(index());
        await click(container.querySelector('[data-atlas="atlas_9"] [data-archive]'));
        await settle();
        expect(calls.filter((c) => c.method === 'PATCH').at(-1).body).toEqual({ archived: true });
        expect(container.querySelector('[aria-label="Your canvases"]')).toBe(null);
        const put = container.querySelector('.atlas-archived [data-atlas="atlas_9"]');
        expect(put).toBeTruthy();
        expect(container.querySelector('.atlas-archived summary').textContent).toMatch(/not gone/);

        await click(put.querySelector('[data-restore]'));
        await settle();
        expect(calls.filter((c) => c.method === 'PATCH').at(-1).body).toEqual({ archived: false });
        expect(container.querySelector('[aria-label="Your canvases"] [data-atlas="atlas_9"]')).toBeTruthy();
        expect(container.querySelector('.atlas-archived')).toBe(null);
    });

    it('duplicates over POST and shelves the copy beside the original', async () => {
        const { calls } = baseline([
            ['GET', /\/api\/v1\/atlas\/\?include_archived=true$/, () => res(200, { atlases: [anAtlas()] })],
            ['POST', /\/api\/v1\/atlas\/atlas_9\/duplicate$/,
                () => res(201, anAtlas({ id: 'atlas_10', duplicated_from: 'atlas_9' }))],
        ]);
        await mount(index());
        await click(container.querySelector('[data-atlas="atlas_9"] [data-duplicate]'));
        await settle();
        expect(calls.find((c) => /duplicate$/.test(c.url)).body).toEqual({});
        const rows = [...container.querySelectorAll('[aria-label="Your canvases"] [data-atlas]')];
        expect(rows.map((r) => r.getAttribute('data-atlas'))).toEqual(['atlas_10', 'atlas_9']);
        expect(rows[0].textContent).toMatch(/a copy/);
    });

    it('offers no delete for an Atlas', async () => {
        baseline([['GET', /\/api\/v1\/atlas\/\?include_archived=true$/, () => res(200, { atlases: [anAtlas()] })]]);
        await mount(index());
        const row = container.querySelector('[data-atlas="atlas_9"]');
        expect(row.textContent).not.toMatch(/delete/i);
    });

    it('says so when a lifecycle call is refused, and keeps the row', async () => {
        baseline([
            ['GET', /\/api\/v1\/atlas\/\?include_archived=true$/, () => res(200, { atlases: [anAtlas()] })],
            ['PATCH', /\/api\/v1\/atlas\/atlas_9$/, () => res(404, { detail: "no atlas 'atlas_9'" })],
        ]);
        await mount(index());
        await click(container.querySelector('[data-atlas="atlas_9"] [data-archive]'));
        await settle();
        expect(container.querySelector('[data-shelf-error]').textContent).toMatch(/no atlas/);
        expect(container.querySelector('[aria-label="Your canvases"] [data-atlas="atlas_9"]')).toBeTruthy();
    });
});

// ── a saved walk: edit, re-sequence, drop, forget — over the existing corpus routes ──

describe('editing a saved walk', () => {
    const view = (order) => ({
        ...aWalk('corpus_w', order),
        images: order.map((p, n) => ({
            post_id: p, position: n, note: n === 0 ? 'first' : '', readable: true,
            image_ref: `https://example.invalid/${p}.jpg`, title: p, committed: 0,
        })),
        unreadable: [],
    });
    let order;
    const wired = () => {
        order = ['p3', 'p1', 'p2'];
        return baseline([
            ['GET', /\/api\/v1\/corpora\/corpus_w\/view$/, () => res(200, view(order))],
            ['PATCH', /\/api\/v1\/corpora\/corpus_w$/, ({ body }) => {
                if (body.move) {
                    const from = order.indexOf(body.move);
                    const [m] = order.splice(from, 1);
                    order.splice(body.to, 0, m);
                }
                if (body.remove) order = order.filter((p) => p !== body.remove);
                const doc = aWalk('corpus_w', order);
                if (body.title) doc.title = body.title;
                if (body.note_for) doc.images.find((i) => i.post_id === body.note_for).note = body.note;
                return res(200, { corpus: doc, refused: body.note_for === 'ghost'
                    ? [{ reason: 'unknown_image', detail: "this corpus holds no image 'ghost'" }] : [] });
            }],
            ['DELETE', /\/api\/v1\/corpora\/corpus_w$/, () => res(200, { deleted: true, id: 'corpus_w' })],
        ]);
    };
    const openEditor = async () => {
        await mount(index());
        await click(container.querySelector('[data-walk="corpus_w"] [data-edit-walk]'));
        await settle();
        return container.querySelector('[data-walk-editor="corpus_w"]');
    };
    const postsShown = () => [...container.querySelectorAll('[data-walk-post]')]
        .map((li) => li.getAttribute('data-walk-post'));

    it('opens under its row, hydrated from the view, in the walk’s order', async () => {
        const { calls } = wired();
        const editor = await openEditor();
        expect(editor).toBeTruthy();
        expect(calls.some((c) => /corpus_w\/view$/.test(c.url))).toBe(true);
        expect(postsShown()).toEqual(['p3', 'p1', 'p2']);
        expect(editor.querySelectorAll('.atlas-walk-thumb').length).toBe(3);
    });

    it('re-sequences over PATCH {move, to} and redraws in the order that came back', async () => {
        const { calls } = wired();
        await openEditor();
        await click(container.querySelector('[data-walk-post="p3"] [aria-label="Move image 1 later"]'));
        await settle();
        expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ move: 'p3', to: 1 });
        expect(postsShown()).toEqual(['p1', 'p3', 'p2']);
        // The list behind it followed, so a later open goes over the new sequence.
        expect(container.querySelector('[data-corpus="corpus_w"]').textContent).toMatch(/3 images/);
    });

    it('drops over PATCH {remove} and closes the gap', async () => {
        const { calls } = wired();
        await openEditor();
        await click(container.querySelector('[data-walk-post="p1"] [aria-label="Drop image 2 from the walk"]'));
        await settle();
        expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ remove: 'p1' });
        expect(postsShown()).toEqual(['p3', 'p2']);
        expect(container.querySelector('[data-corpus="corpus_w"]').textContent).toMatch(/2 images/);
    });

    it('renames over PATCH {title}', async () => {
        const { calls } = wired();
        const editor = await openEditor();
        const input = editor.querySelector('[aria-label="The walk\'s name"]');
        await act(async () => {
            Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'the descent');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => {
            editor.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        });
        await settle();
        expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ title: 'the descent' });
        expect(container.querySelector('[data-corpus="corpus_w"] .atlas-list-title').textContent).toBe('the descent');
    });

    it('forgets only after a second, explicit gesture, and the row leaves', async () => {
        const { calls } = wired();
        const editor = await openEditor();
        await click(editor.querySelector('[data-forget]'));
        expect(calls.some((c) => c.method === 'DELETE')).toBe(false);
        expect(editor.textContent).toMatch(/The images stay/);
        await click(editor.querySelector('[data-forget-confirm]'));
        await settle();
        expect(calls.some((c) => c.method === 'DELETE' && /corpus_w$/.test(c.url))).toBe(true);
        expect(container.querySelector('[data-walk="corpus_w"]')).toBe(null);
    });

    it('will not drop the last image — a walk with none is not a walk', async () => {
        wired();
        order = ['p3'];
        await openEditor();
        expect(container.querySelector('[aria-label="Drop image 1 from the walk"]').disabled).toBe(true);
    });

    it('never touches a post: every call the editor makes goes to /corpora', async () => {
        const { calls } = wired();
        const editor = await openEditor();
        await click(container.querySelector('[data-walk-post="p3"] [aria-label="Move image 1 later"]'));
        await click(container.querySelector('[data-walk-post="p2"] [aria-label="Drop image 3 from the walk"]'));
        await click(editor.querySelector('[data-forget]'));
        await click(editor.querySelector('[data-forget-confirm]'));
        await settle();
        const writes = calls.filter((c) => c.method !== 'GET');
        expect(writes.length).toBeGreaterThan(0);
        expect(writes.every((c) => /\/api\/v1\/corpora\//.test(c.url))).toBe(true);
    });
});
