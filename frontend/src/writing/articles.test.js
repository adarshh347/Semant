import { describe, it, expect } from 'vitest';
import { articles, getArticle, parseFrontmatter, formatDate } from './articles.js';

/**
 * The writing showcase — pure-module guarantees.
 *
 * The whole section rests on two claims: the frontmatter splitter reads the
 * five flat fields correctly, and the index is ordered newest-first. Both are
 * checkable without a DOM, which is where this project prefers to check things.
 */

describe('parseFrontmatter', () => {
    it('splits the leading --- block and strips surrounding quotes', () => {
        const { meta, body } = parseFrontmatter(
            '---\ntitle: "A Title"\nslug: "a-title"\ndate: "2026-01-02"\n---\n# Heading\n\nBody.',
        );
        expect(meta).toEqual({ title: 'A Title', slug: 'a-title', date: '2026-01-02' });
        expect(body).toBe('# Heading\n\nBody.');
    });

    it('leaves the body alone when there is no frontmatter', () => {
        const { meta, body } = parseFrontmatter('# Just markdown\n');
        expect(meta).toEqual({});
        expect(body).toBe('# Just markdown');
    });

    it('does not treat a --- rule inside the body as frontmatter', () => {
        // A horizontal rule mid-article must not be mistaken for a fence, or the
        // article would silently lose everything above it.
        const { meta, body } = parseFrontmatter('Opening line.\n\n---\n\nAfter the rule.');
        expect(meta).toEqual({});
        expect(body).toContain('Opening line.');
        expect(body).toContain('After the rule.');
    });

    it('keeps a colon inside a value', () => {
        const { meta } = parseFrontmatter('---\nblurb: "One thing: and another"\n---\nx');
        expect(meta.blurb).toBe('One thing: and another');
    });
});

describe('formatDate', () => {
    it('renders an ISO date in long form, UTC-stable', () => {
        expect(formatDate('2026-07-18')).toBe('18 July 2026');
    });
    it('returns empty for a missing date rather than "Invalid Date"', () => {
        expect(formatDate('')).toBe('');
        expect(formatDate(undefined)).toBe('');
    });
});

describe('the compiled article set', () => {
    it('loads every markdown file in content/', () => {
        expect(articles.length).toBeGreaterThanOrEqual(3);
    });

    it('gives every article a slug, a title and a non-empty body', () => {
        for (const a of articles) {
            expect(a.slug, `slug for ${a.title}`).toBeTruthy();
            expect(a.title).toBeTruthy();
            expect(a.body.length).toBeGreaterThan(200);
            // the frontmatter fence must never survive into the rendered body
            expect(a.body.startsWith('---')).toBe(false);
        }
    });

    it('orders newest first', () => {
        const dates = articles.map((a) => a.date);
        expect(dates).toEqual([...dates].sort().reverse());
    });

    it('has unique slugs, so no article can shadow another', () => {
        const slugs = articles.map((a) => a.slug);
        expect(new Set(slugs).size).toBe(slugs.length);
    });

    it('resolves a known slug and refuses an unknown one', () => {
        expect(getArticle(articles[0].slug)).toBeTruthy();
        expect(getArticle('no-such-essay')).toBe(null);
    });
});
