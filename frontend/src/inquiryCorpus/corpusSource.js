/**
 * INQUIRY CORPUS — reading the archive, one page at a time.
 *
 * HARNESS-003C. The 002R rehearsal found that `/inquiry` fetched exactly
 * `GET /api/v1/posts?page=1&limit=24` and stopped, so an inquiry could only ever be asked of the
 * twenty-four newest images. This module is the paging half of the repair, and it is deliberately
 * pure — no React, no network — so the rules below are unit-assertable rather than only
 * observable through a rendered grid.
 *
 * ## The same store, not a second one
 *
 * `PAGE_KEY` reproduces `ArchiveGrid`'s TanStack key **exactly** — `['posts', 'archive', tag,
 * page]` — so a page the Archive has already fetched is a cache hit here and vice versa. The
 * board's rule is "do not fork a second archive store", and the strongest form of obeying it is
 * that the two surfaces cannot disagree about what page 3 contains, because there is only one
 * page 3. `PAGE_SIZE` is imported from `ArchiveGrid` for the same reason: two modules with their
 * own 50 would share a key while meaning different slices, which is worse than not sharing at all.
 *
 * ## There is no `title` on a post
 *
 * `post_helper` in `backend/routers/posts.py` returns id, photo_url, tags, text blocks, handles and
 * marks — and no `title`, and no `description`. The old entry form rendered `p.title || p.id`, so
 * every tile in the rehearsal was labelled with a Mongo ObjectId. `postLabel` derives something
 * readable from what the API actually sends, and falls back to a shortened id **labelled as an
 * id** rather than to a bare hex string that looks like it might be a name.
 */
import { PAGE_SIZE } from '../components/ArchiveGrid';

export { PAGE_SIZE };

/** `null` tag and `''` tag are the same request; both must produce the same cache key. */
export const tagScope = (tag) => (tag ? String(tag) : '__all__');

/** ArchiveGrid's key, reproduced exactly. Changing it here forks the store. */
export const PAGE_KEY = (tag, page) => ['posts', 'archive', tagScope(tag), page];

export function pageUrl(apiUrl, { tag = null, page = 1, limit = PAGE_SIZE } = {}) {
    let url = `${apiUrl}/api/v1/posts?page=${page}&limit=${limit}`;
    if (tag) url += `&tag=${encodeURIComponent(tag)}`;
    return url;
}

const arr = (v) => (Array.isArray(v) ? v : []);
const str = (v) => (typeof v === 'string' ? v : '');

/**
 * HTML out of a text block, plain text in.
 *
 * `text_blocks[].content` is HTML — `TextPostCard` builds a detached div to strip it. This does
 * the same job without a DOM, because this module is imported by node-environment suites too and
 * a label helper that needs a browser is a label helper the contract tests cannot check.
 */
export function plainText(html) {
    // ORDER MATTERS, and it is the whole reason this is not one chained replace.
    //
    // A tag becomes a space, so `<p>a</p><p>b</p>` does not read as `ab`. An INLINE tag then
    // leaves a gap before whatever punctuation followed it — `The Rotunda , from the stair`, which
    // a reader takes for a defect in the archive rather than in the stripper — so the gap is
    // closed. But that tidy must run BEFORE entities are decoded: a decoded `"` or `'` looks
    // exactly like closing punctuation, and running the two in the other order ate the legitimate
    // spaces in `b "d" 'e'`.
    const stripped = str(html)
        .replace(/<[^>]*>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/\s+/g, ' ')
        .replace(/\s+([,.;:!?%)\]}])/g, '$1');

    return stripped
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&amp;/g, '&')
        .trim();
}

const LABEL_MAX = 64;

/**
 * A readable name for a post, and an honest one.
 *
 * Order: the first text block that says anything → the tags → the source handle → the id. The
 * last case returns `{ label, isId: true }` so the tile can render it as `id 68f2…c41` rather than
 * as a title, which is the difference between "this image has no name" and "this image is called
 * 68f2…c41".
 */
export function postLabel(post) {
    const p = post && typeof post === 'object' ? post : {};

    for (const block of arr(p.text_blocks)) {
        const text = plainText(block && block.content);
        if (text) {
            return {
                label: text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX - 1)}…` : text,
                isId: false,
                source: 'text_block',
            };
        }
    }

    const tags = arr(p.general_tags).map(str).filter(Boolean);
    if (tags.length) return { label: tags.join(', '), isId: false, source: 'general_tags' };

    const handle = str(p.instagram_handle) || arr(p.instagram_handles).map(str).find(Boolean) || '';
    if (handle) return { label: handle, isId: false, source: 'handle' };

    const id = str(p.id);
    return { label: shortId(id) || 'no id', isId: true, source: 'id' };
}

export function shortId(id) {
    const s = str(id);
    if (s.length <= 12) return s;
    return `${s.slice(0, 6)}…${s.slice(-4)}`;
}

/**
 * Where this image came from, as far as the record knows.
 *
 * Not decoration: the person is choosing what an inquiry will read, and "an Instagram repost with
 * no local context" and "an upload with four annotated regions" are different things to ask a
 * question of. Every part is omitted when absent rather than rendered as a zero.
 */
export function provenanceHint(post) {
    const p = post && typeof post === 'object' ? post : {};
    const parts = [];

    const handle = str(p.instagram_handle) || arr(p.instagram_handles).map(str).find(Boolean) || '';
    if (handle) parts.push(handle.startsWith('@') ? handle : `@${handle}`);
    else if (str(p.source_account)) parts.push(str(p.source_account));
    else if (str(p.source_url)) parts.push('linked source');

    const marks = arr(p.region_annotations).length;
    if (marks) parts.push(`${marks} mark${marks === 1 ? '' : 's'}`);

    if (str(p.domain)) parts.push(str(p.domain));

    return parts.join(' · ');
}

/** A post as the picker reads it. The raw record is kept for the detail link and the tray. */
export function normalizePost(raw) {
    const p = raw && typeof raw === 'object' ? raw : {};
    const named = postLabel(p);
    return {
        id: str(p.id),
        photo_url: str(p.photo_url),
        label: named.label,
        label_is_id: named.isId,
        label_source: named.source,
        provenance: provenanceHint(p),
        tags: arr(p.general_tags).map(str).filter(Boolean),
        raw: p,
    };
}

/**
 * A page response → what the picker needs. `total_pages` is the API's own number, kept as null
 * when absent so "we do not know how long the archive is" never renders as "the archive is empty".
 */
export function normalizePage(raw) {
    const d = raw && typeof raw === 'object' ? raw : {};
    const total = Number(d.total_pages);
    return {
        posts: arr(d.posts).filter((p) => p && p.photo_url).map(normalizePost),
        total_pages: Number.isFinite(total) && total >= 0 ? total : null,
        current_page: Number.isFinite(Number(d.current_page)) ? Number(d.current_page) : null,
    };
}

/**
 * Add a page to what is loaded, de-duplicating by id and preserving order.
 *
 * De-duplication matters more here than in the Archive: posts are sorted by `_id` descending and
 * an upload during a session shifts every later page by one, so page 2 can legitimately re-deliver
 * an item from page 1. Rendering it twice would give React two children with the same key.
 */
export function mergePosts(loaded, incoming) {
    const seen = new Set(arr(loaded).map((p) => p.id));
    const out = [...arr(loaded)];
    for (const p of arr(incoming)) {
        if (!p.id || seen.has(p.id)) continue;
        seen.add(p.id);
        out.push(p);
    }
    return out;
}

/**
 * Filter over what is LOADED. The caller is responsible for saying so — see
 * `searchScopeNote`, which exists precisely so no screen can show a filtered grid without the
 * sentence explaining what it filtered.
 */
export function filterPosts(posts, query) {
    const q = str(query).trim().toLowerCase();
    if (!q) return arr(posts);
    return arr(posts).filter((p) =>
        p.label.toLowerCase().includes(q)
        || p.id.toLowerCase().includes(q)
        || p.tags.some((t) => t.toLowerCase().includes(q))
        || p.provenance.toLowerCase().includes(q));
}

/**
 * The sentence that keeps a filter honest.
 *
 * A search box over a partially-loaded corpus is a trap: it looks like it searched the archive and
 * it searched the fraction that happens to be in memory, so "no results" reads as "the archive
 * does not contain this". The note is returned by the same module that does the filtering so the
 * two cannot drift, and it is rendered unconditionally while a query is active.
 */
export function searchScopeNote({ loadedCount, pagesLoaded, totalPages, done }) {
    const of = totalPages === null
        ? 'an archive of unknown length'
        : `${totalPages} page${totalPages === 1 ? '' : 's'}`;
    if (done) {
        return `Searching all ${loadedCount} images in the archive.`;
    }
    return `Searching the ${loadedCount} images loaded so far — `
        + `${pagesLoaded} of ${of}. Load more to search the rest.`;
}

/** Everything loaded, or the API said there is no more. */
export function isComplete({ pagesLoaded, totalPages, lastPageEmpty }) {
    if (lastPageEmpty) return true;
    if (totalPages === null) return false;
    return pagesLoaded >= totalPages;
}
