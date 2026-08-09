/**
 * INQUIRY CORPUS — the picker, mounted.
 *
 * The 002R rehearsal's finding, made into assertions: an inquiry must be askable of the whole
 * archive, a selection must survive paging and filtering, and a filter must say what it filtered.
 */
import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import CorpusPicker from './CorpusPicker.jsx';
import { createCorpusClient, createMockCorpusClient, CorpusRequestError } from './corpusClient.js';
import { PAGE_KEY, normalizePost } from './corpusSource.js';

let container;
let root;

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

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => { await act(async () => { el.click(); }); };

const post = (n, extra = {}) => ({
    id: `p${n}`,
    photo_url: `https://res.cloudinary.com/x/image/upload/v1/posts/p${n}.jpg`,
    text_blocks: [{ content: `<p>Image ${n}</p>` }],
    ...extra,
});

/** Three pages of two, the third short — the ordinary shape of a finite archive. */
const PAGES = [
    { posts: [post(1), post(2)], total_pages: 3, current_page: 1 },
    { posts: [post(3), post(4)], total_pages: 3, current_page: 2 },
    { posts: [post(5)], total_pages: 3, current_page: 3 },
];

/** The picker with selection state above it, exactly as `InquiryEntry` holds it. */
function Harness({ client, onSelected = null }) {
    const [selected, setSelected] = useState([]);
    onSelected?.(selected);
    return (
        <CorpusPicker
            client={client}
            selected={selected}
            onSelect={(p) => setSelected((prev) =>
                (prev.some((x) => x.id === p.id) ? prev : [...prev, p]))}
            onDeselect={(id) => setSelected((prev) => prev.filter((p) => p.id !== id))}
        />
    );
}

async function mount(clientOpts = {}, props = {}) {
    const client = createMockCorpusClient({ pages: PAGES, ...clientOpts });
    let latest = [];
    await act(async () => {
        root.render(<Harness client={client} onSelected={(s) => { latest = s; }} {...props} />);
    });
    return { client, selected: () => latest };
}

// ── paging to the end of the archive ────────────────────────────────────────

describe('browsing the whole corpus', () => {
    it('loads the first page on mount and offers the rest', async () => {
        const { client } = await mount();
        expect($$('.ic-tile')).toHaveLength(2);
        expect(client._requested).toEqual([{ tag: null, page: 1 }]);
        expect($('.ic-more').textContent).toContain('1 of 3 pages');
    });

    it('pages until the archive ends, then says so instead of offering more', async () => {
        await mount();
        await click($('.ic-more'));
        expect($$('.ic-tile')).toHaveLength(4);
        await click($('.ic-more'));
        expect($$('.ic-tile')).toHaveLength(5);

        // the end is a statement, not a button that quietly stops working
        expect($('.ic-more')).toBeNull();
        expect($('[data-corpus="complete"]').textContent)
            .toMatch(/That is the whole archive — 5 images/);
    });

    it('a page that comes back empty ends the corpus whatever the total claimed', async () => {
        await mount({ pages: [{ posts: [post(1)], total_pages: 9 }, { posts: [], total_pages: 9 }] });
        await click($('.ic-more'));
        expect($('[data-corpus="complete"]')).toBeTruthy();
    });

    it('a failed page keeps what already loaded and offers a retry', async () => {
        await mount({ failOnPage: 2 });
        await click($('.ic-more'));

        expect($('.ic-status--error').textContent).toMatch(/did not answer/);
        // the interesting failure is a HALF-loaded corpus; discarding page 1 would make it look
        // like a corpus that never started
        expect($$('.ic-tile')).toHaveLength(2);
        expect($('.ic-status--error').textContent).toMatch(/2 images already loaded are still here/);
        expect($('.ic-more').textContent).toContain('Try again');
    });

    it('de-duplicates a post that arrives on two pages', async () => {
        // Posts sort by `_id` descending, so an upload mid-session shifts every later page by one.
        await mount({
            pages: [
                { posts: [post(1), post(2)], total_pages: 2 },
                { posts: [post(2), post(3)], total_pages: 2 },
            ],
        });
        await click($('.ic-more'));
        expect($$('.ic-tile').map((t) => t.dataset.postId)).toEqual(['p1', 'p2', 'p3']);
    });
});

// ── selection across pages ──────────────────────────────────────────────────

describe('a selection that survives the corpus moving under it', () => {
    it('keeps images picked on page 1 after paging to page 3', async () => {
        const { selected } = await mount();
        await click($('[data-post-id="p1"]'));
        await click($('.ic-more'));
        await click($('[data-post-id="p3"]'));
        await click($('.ic-more'));
        await click($('[data-post-id="p5"]'));

        expect(selected().map((p) => p.id)).toEqual(['p1', 'p3', 'p5']);
        expect($('[data-selected-count]').textContent).toBe('3 selected');
        expect($$('.ic-tray-item').map((n) => n.dataset.trayId)).toEqual(['p1', 'p3', 'p5']);
    });

    it('keeps a selected image in the tray when a filter hides it from the grid', async () => {
        // The tray holds POSTS, not ids. An id-only selection could not render this row at all.
        const { selected } = await mount();
        await click($('[data-post-id="p1"]'));
        const search = $('.ic-search');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                .set.call(search, 'Image 2');
            search.dispatchEvent(new Event('input', { bubbles: true }));
        });

        expect($$('.ic-tile').map((t) => t.dataset.postId)).toEqual(['p2']);
        expect($('[data-tray-id="p1"]')).toBeTruthy();
        expect(selected().map((p) => p.id)).toEqual(['p1']);
    });

    it('deselects from the tile and from the tray', async () => {
        const { selected } = await mount();
        await click($('[data-post-id="p1"]'));
        await click($('[data-post-id="p2"]'));
        await click($('[data-post-id="p1"]'));          // toggle off from the grid
        expect(selected().map((p) => p.id)).toEqual(['p2']);

        await click($('[data-tray-id="p2"] .ic-remove'));
        expect(selected()).toEqual([]);
        expect($('.ic-tray')).toBeNull();
    });

    it('marks a selected tile for assistive tech, not only with a colour', async () => {
        await mount();
        expect($('[data-post-id="p1"]').getAttribute('aria-pressed')).toBe('false');
        await click($('[data-post-id="p1"]'));
        expect($('[data-post-id="p1"]').getAttribute('aria-pressed')).toBe('true');
    });
});

// ── the honest filter ───────────────────────────────────────────────────────

describe('filtering says what it filtered', () => {
    const typeQuery = async (q) => {
        const search = $('.ic-search');
        await act(async () => {
            Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                .set.call(search, q);
            search.dispatchEvent(new Event('input', { bubbles: true }));
        });
    };

    it('names the loaded fraction while the corpus is incomplete', async () => {
        await mount();
        await typeQuery('image');
        const note = $('[data-scope-note="true"]');
        expect(note.textContent).toBe(
            'Searching the 2 images loaded so far — 1 of 3 pages. Load more to search the rest.');
    });

    it('says it searched everything once the corpus is complete', async () => {
        await mount();
        await click($('.ic-more'));
        await click($('.ic-more'));
        await typeQuery('image');
        expect($('[data-scope-note="true"]').textContent)
            .toBe('Searching all 5 images in the archive.');
    });

    it('an empty result says nothing LOADED matches, not that nothing exists', async () => {
        await mount();
        await typeQuery('nothing-like-this');
        expect($('.ic-empty').textContent).toBe('Nothing loaded so far matches that.');
        expect(text()).not.toMatch(/not in the archive|does not exist/i);
        // and the scope note is still there to say why
        expect($('[data-scope-note="true"]')).toBeTruthy();
    });

    it('shows no scope note when nothing is being filtered', async () => {
        await mount();
        expect($('[data-scope-note="true"]')).toBeNull();
    });
});

// ── naming, provenance and the detail link ──────────────────────────────────

describe('what a tile tells you about the image', () => {
    it('renders a derived name, and marks an id-derived one AS an id', async () => {
        await mount({
            pages: [{
                posts: [
                    post(1),
                    { id: '68f2a1b9c4d5e6f708192a3c41', photo_url: 'https://x/y.jpg' },
                ],
                total_pages: 1,
            }],
        });
        expect($('[data-post-id="p1"] .ic-label').textContent).toBe('Image 1');
        const bare = $('[data-post-id="68f2a1b9c4d5e6f708192a3c41"] .ic-label');
        // `post_helper` returns no title and no description; the old form rendered a raw ObjectId
        // that looked like it might be a name.
        expect(bare.textContent).toBe('id 68f2a1…3c41');
        expect(bare.className).toContain('is-id');
    });

    it('shows a provenance hint when the record has one, and nothing when it does not', async () => {
        await mount({
            pages: [{
                posts: [
                    post(1, { instagram_handle: 'archivist', region_annotations: [{}, {}] }),
                    post(2),
                ],
                total_pages: 1,
            }],
        });
        expect($('[data-post-id="p1"] .ic-prov').textContent).toBe('@archivist · 2 marks');
        expect($('[data-post-id="p2"] .ic-prov')).toBeNull();
    });

    it('opens the image detail in a new tab, so the draft cannot be lost', async () => {
        // An in-app route change would unmount the entry form and take the prompt with it. The
        // requirement is not "warn before leaving" — it is that opening an image does not lose the
        // draft, and a new tab is the only way to mean that literally.
        await mount();
        const open = $('[data-open-for="p1"]');
        expect(open.tagName).toBe('A');
        expect(open.getAttribute('href')).toBe('/posts/p1');
        expect(open.getAttribute('target')).toBe('_blank');
        expect(open.getAttribute('rel')).toBe('noreferrer');
    });

    it('previews an image large, with its id and where its name came from', async () => {
        const { selected } = await mount();
        await click($('[data-preview-for="p1"]'));
        const preview = $('[data-preview="open"]');
        expect(preview.querySelector('.ic-preview-img').getAttribute('src')).toContain('w_900');
        expect(preview.textContent).toContain('p1');
        expect(preview.textContent).toContain('text block');

        await click($('.ic-preview-pick'));
        expect(selected().map((p) => p.id)).toEqual(['p1']);
        expect($('.ic-preview-pick').textContent).toBe('Remove from inquiry');

        await click($('.ic-preview-close'));
        expect($('[data-preview="open"]')).toBeNull();
    });
});

// ── the shared store, proved rather than asserted ───────────────────────────

describe('the picker reads the Archive\'s cache, not a second copy', () => {
    it('serves a page the Archive already fetched without touching the network', async () => {
        const queryClient = new QueryClient({
            defaultOptions: { queries: { retry: false } },
        });
        // Exactly what `ArchiveGrid` would have written after browsing page 1.
        queryClient.setQueryData(PAGE_KEY(null, 1), {
            posts: [post(9)], total_pages: 1, current_page: 1,
        });

        const fetchImpl = vi.fn();
        const client = createCorpusClient({ queryClient, fetchImpl });

        await act(async () => {
            root.render(
                <QueryClientProvider client={queryClient}>
                    <Harness client={client} />
                </QueryClientProvider>);
        });

        expect($$('.ic-tile')).toHaveLength(1);
        expect($('[data-post-id="p9"]')).toBeTruthy();
        expect(fetchImpl).not.toHaveBeenCalled();
    });

    it('fetches a page nobody has, under the key the Archive would use', async () => {
        const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
        const fetchImpl = vi.fn(async () => ({
            ok: true, status: 200, json: async () => ({ posts: [post(1)], total_pages: 1 }),
        }));
        const client = createCorpusClient({ queryClient, fetchImpl, apiUrl: 'http://api' });

        await act(async () => {
            root.render(
                <QueryClientProvider client={queryClient}>
                    <Harness client={client} />
                </QueryClientProvider>);
        });

        expect(fetchImpl.mock.calls[0][0]).toBe('http://api/api/v1/posts?page=1&limit=50');
        // …and it landed in the cache the Archive reads
        expect(queryClient.getQueryData(PAGE_KEY(null, 1))).toEqual({
            posts: [post(1)], total_pages: 1,
        });
    });

    it('refuses to be built without the shared client, rather than opening a private one', () => {
        // A client that silently fell back to a private fetch would be the second archive store
        // the board forbids, arriving by accident on whichever screen forgot to pass one.
        expect(() => createCorpusClient({})).toThrow(/queryClient/);
    });

    it('reports a failed page as a typed error carrying the status', async () => {
        const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
        const fetchImpl = vi.fn(async () => ({ ok: false, status: 502, statusText: 'Bad Gateway' }));
        const client = createCorpusClient({ queryClient, fetchImpl });
        const err = await client.page({ page: 1 }).catch((e) => e);
        expect(err).toBeInstanceOf(CorpusRequestError);
        expect(err.status).toBe(502);
    });
});

// ── the module's own boundaries ─────────────────────────────────────────────

describe('normalisation reaches the DOM', () => {
    it('renders a Cloudinary crop rather than the full-size original', async () => {
        await mount();
        expect($('[data-post-id="p1"] img').getAttribute('src')).toContain('c_fill,g_auto,w_240,h_240');
    });

    it('a post with no image never reaches the grid', async () => {
        await mount({ pages: [{ posts: [post(1), { id: 'p2' }], total_pages: 1 }] });
        expect($$('.ic-tile')).toHaveLength(1);
        expect(normalizePost({ id: 'p2' }).photo_url).toBe('');
    });
});
