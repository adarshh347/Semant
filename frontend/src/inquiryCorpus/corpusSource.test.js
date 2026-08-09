/**
 * INQUIRY CORPUS — the paging rules, asserted without a browser.
 */
import { describe, it, expect } from 'vitest';
import {
    PAGE_KEY, PAGE_SIZE, tagScope, pageUrl, plainText, postLabel, shortId, provenanceHint,
    normalizePost, normalizePage, mergePosts, filterPosts, searchScopeNote, isComplete,
} from './corpusSource.js';
import { PAGE_SIZE as ARCHIVE_PAGE_SIZE } from '../components/ArchiveGrid.jsx';

describe('the same store as the Archive', () => {
    it('reproduces ArchiveGrid\'s query key exactly', () => {
        // The board's rule is "do not fork a second archive store". The strongest form of obeying
        // it is that the two surfaces cannot disagree about what page 3 contains, and that is only
        // true while this key and ArchiveGrid's are the same array.
        expect(PAGE_KEY(null, 3)).toEqual(['posts', 'archive', '__all__', 3]);
        expect(PAGE_KEY('schinkel', 1)).toEqual(['posts', 'archive', 'schinkel', 1]);
    });

    it('treats no tag and an empty tag as the same scope', () => {
        expect(tagScope(null)).toBe('__all__');
        expect(tagScope('')).toBe('__all__');
        expect(tagScope(undefined)).toBe('__all__');
    });

    it('uses the Archive\'s page size, imported rather than repeated', () => {
        // Two modules with their own 50 would share a key while meaning different slices, which
        // is worse than not sharing at all.
        expect(PAGE_SIZE).toBe(ARCHIVE_PAGE_SIZE);
    });

    it('builds the posts URL the backend actually serves', () => {
        expect(pageUrl('http://x', { page: 2 }))
            .toBe(`http://x/api/v1/posts?page=2&limit=${PAGE_SIZE}`);
        expect(pageUrl('http://x', { page: 1, tag: 'altes museum' }))
            .toBe(`http://x/api/v1/posts?page=1&limit=${PAGE_SIZE}&tag=altes%20museum`);
    });
});

describe('naming a post that has no name', () => {
    it('prefers the first text block that says anything', () => {
        expect(postLabel({
            id: 'p1',
            text_blocks: [{ content: '   ' }, { content: '<p>The <b>Rotunda</b>, from the stair</p>' }],
            general_tags: ['altes'],
        })).toEqual({ label: 'The Rotunda, from the stair', isId: false, source: 'text_block' });
    });

    it('falls back to tags, then a handle, then the id', () => {
        expect(postLabel({ id: 'p', general_tags: ['schinkel', 'berlin'] }).label)
            .toBe('schinkel, berlin');
        expect(postLabel({ id: 'p', instagram_handle: '@archivist' }).label).toBe('@archivist');
        expect(postLabel({ id: 'p', instagram_handles: ['', 'second'] }).label).toBe('second');
    });

    it('marks an id-derived label AS an id', () => {
        // `post_helper` returns no `title` and no `description`, so the old entry form rendered
        // every tile as a bare ObjectId that looked like it might be a name. `isId` is what lets
        // the tile say "id 68f2…3c41" instead.
        const named = postLabel({ id: '68f2a1b9c4d5e6f708192a3c41' });
        expect(named).toEqual({ label: '68f2a1…3c41', isId: true, source: 'id' });
    });

    it('truncates a long block rather than letting it become the tile', () => {
        const long = postLabel({ id: 'p', text_blocks: [{ content: 'x'.repeat(200) }] });
        expect(long.label.length).toBe(64);
        expect(long.label.endsWith('…')).toBe(true);
    });

    it('survives a post with nothing at all', () => {
        expect(postLabel(null)).toEqual({ label: 'no id', isId: true, source: 'id' });
        expect(shortId('')).toBe('');
        expect(shortId('short')).toBe('short');
    });
});

describe('stripping a text block', () => {
    it('removes tags and collapses whitespace without a DOM', () => {
        expect(plainText('<p>one</p>\n<p>  two </p>')).toBe('one two');
        expect(plainText('a &amp; b &lt;c&gt; &quot;d&quot; &#39;e&#39;&nbsp;f'))
            .toBe('a & b <c> "d" \'e\' f');
        expect(plainText(null)).toBe('');
    });
});

describe('the provenance hint', () => {
    it('names the source, the marks and the domain, omitting what is absent', () => {
        expect(provenanceHint({
            instagram_handle: 'archivist', region_annotations: [{}, {}], domain: 'architecture',
        })).toBe('@archivist · 2 marks · architecture');
        expect(provenanceHint({ source_url: 'https://x' })).toBe('linked source');
        expect(provenanceHint({ region_annotations: [{}] })).toBe('1 mark');
        expect(provenanceHint({})).toBe('');
    });

    it('never renders a zero count', () => {
        expect(provenanceHint({ region_annotations: [] })).toBe('');
        expect(provenanceHint({ region_annotations: [] })).not.toContain('0');
    });
});

describe('normalising a page', () => {
    it('drops posts with no image and keeps the raw record', () => {
        const page = normalizePage({
            posts: [
                { id: 'a', photo_url: 'u1', general_tags: ['t'] },
                { id: 'b' },                       // no photo_url — cannot be shown or read
            ],
            total_pages: 4,
            current_page: 1,
        });
        expect(page.posts.map((p) => p.id)).toEqual(['a']);
        expect(page.posts[0].raw.general_tags).toEqual(['t']);
        expect(page.total_pages).toBe(4);
    });

    it('reports an unknown total as null, never as zero', () => {
        // "we do not know how long the archive is" must not render as "the archive is empty".
        expect(normalizePage({ posts: [] }).total_pages).toBeNull();
        expect(normalizePage(undefined).total_pages).toBeNull();
        expect(normalizePage({ posts: [], total_pages: 0 }).total_pages).toBe(0);
    });

    it('survives rubbish', () => {
        expect(normalizePage('nope').posts).toEqual([]);
        expect(normalizePost(null).id).toBe('');
    });
});

describe('merging pages', () => {
    it('de-duplicates by id and preserves order', () => {
        // Posts sort by `_id` descending, so an upload mid-session shifts every later page by one
        // and page 2 can legitimately re-deliver an item from page 1.
        const merged = mergePosts(
            [{ id: 'a' }, { id: 'b' }],
            [{ id: 'b' }, { id: 'c' }],
        );
        expect(merged.map((p) => p.id)).toEqual(['a', 'b', 'c']);
    });

    it('ignores entries with no id rather than keying React on empty strings', () => {
        expect(mergePosts([], [{ id: '' }, { id: 'a' }]).map((p) => p.id)).toEqual(['a']);
    });
});

describe('filtering what is loaded', () => {
    const posts = [
        normalizePost({ id: 'p1', photo_url: 'u', text_blocks: [{ content: 'Rotunda interior' }] }),
        normalizePost({ id: 'p2', photo_url: 'u', general_tags: ['schinkel'] }),
        normalizePost({ id: 'p3', photo_url: 'u', instagram_handle: 'archivist' }),
    ];

    it('matches label, tag, source and id', () => {
        expect(filterPosts(posts, 'rotunda').map((p) => p.id)).toEqual(['p1']);
        expect(filterPosts(posts, 'SCHINKEL').map((p) => p.id)).toEqual(['p2']);
        expect(filterPosts(posts, 'archivist').map((p) => p.id)).toEqual(['p3']);
        expect(filterPosts(posts, 'p2').map((p) => p.id)).toEqual(['p2']);
    });

    it('an empty query is not a filter', () => {
        expect(filterPosts(posts, '   ')).toHaveLength(3);
    });
});

describe('the sentence that keeps a filter honest', () => {
    it('says how much of the archive was actually searched', () => {
        // A search box over a partly-loaded corpus is a trap: "no results" reads as "the archive
        // does not contain this".
        expect(searchScopeNote({ loadedCount: 100, pagesLoaded: 2, totalPages: 7, done: false }))
            .toBe('Searching the 100 images loaded so far — 2 of 7 pages. Load more to search the rest.');
    });

    it('says so plainly once everything is loaded', () => {
        expect(searchScopeNote({ loadedCount: 312, pagesLoaded: 7, totalPages: 7, done: true }))
            .toBe('Searching all 312 images in the archive.');
    });

    it('does not invent a length it was not told', () => {
        expect(searchScopeNote({ loadedCount: 50, pagesLoaded: 1, totalPages: null, done: false }))
            .toContain('an archive of unknown length');
    });
});

describe('knowing when the archive ends', () => {
    it('is complete at the declared last page', () => {
        expect(isComplete({ pagesLoaded: 7, totalPages: 7, lastPageEmpty: false })).toBe(true);
        expect(isComplete({ pagesLoaded: 6, totalPages: 7, lastPageEmpty: false })).toBe(false);
    });

    it('is complete when a page comes back empty, whatever the total said', () => {
        expect(isComplete({ pagesLoaded: 2, totalPages: 99, lastPageEmpty: true })).toBe(true);
    });

    it('is never complete on an unknown total', () => {
        expect(isComplete({ pagesLoaded: 3, totalPages: null, lastPageEmpty: false })).toBe(false);
    });
});

// ── this module's own boundaries ────────────────────────────────────────────

describe('the picker reuses rather than re-implements', () => {
    it('imports only the archive paging it shares and the Cloudinary helpers', async () => {
        const fs = await import('node:fs');
        const path = await import('node:path');
        const { fileURLToPath } = await import('node:url');
        const here = path.dirname(fileURLToPath(import.meta.url));

        // The board's rule for this lane is "do not fork a second archive store". These four are
        // the reuse that makes obeying it possible; anything else appearing here would be this
        // module quietly growing its own copy of a surface it is supposed to share.
        const allowed = /^(react|react-dom|node:|@tanstack\/react-query|\.\/|\.\.\/config\/api|\.\.\/lib\/cloudinary|\.\.\/components\/ArchiveGrid)/;
        const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

        const offenders = [];
        for (const f of fs.readdirSync(here)) {
            if (!/\.(js|jsx)$/.test(f) || f.includes('.test.')) continue;
            const src = strip(fs.readFileSync(path.join(here, f), 'utf8'));
            for (const m of src.matchAll(/from\s+['"]([^'"]+)['"]/g)) {
                if (!allowed.test(m[1])) offenders.push(`${f} → ${m[1]}`);
            }
        }
        expect(offenders).toEqual([]);
    });
});
