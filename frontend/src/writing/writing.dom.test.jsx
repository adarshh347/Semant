import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import WritingPage from './WritingPage.jsx';
import WritingArticlePage from './WritingArticlePage.jsx';
import { articles } from './articles.js';

/**
 * The writing showcase, mounted.
 *
 * These need a DOM for the reason the project's other `.dom` suites do: the
 * claims are about what is ON SCREEN. "The index lists every essay" and "the
 * markdown becomes real headings and paragraphs, not literal `##`" cannot be
 * checked from the pure module — react-markdown either ran or it did not.
 *
 * No testing-library: the project has none, and these are plain DOM queries.
 */

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // jsdom declares window.scrollTo but throws "Not implemented" when called.
    // The reader legitimately scrolls to the top between articles, so stub it
    // here rather than making the component defensive about a real browser API.
    window.scrollTo = () => {};
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const text = () => container.textContent || '';

async function mountIndex() {
    await act(async () => {
        root.render(<MemoryRouter><WritingPage /></MemoryRouter>);
    });
}

async function mountArticle(slug) {
    await act(async () => {
        root.render(
            <MemoryRouter initialEntries={[`/writing/${slug}`]}>
                <Routes>
                    <Route path="/writing/:slug" element={<WritingArticlePage />} />
                </Routes>
            </MemoryRouter>,
        );
    });
}

describe('/writing — the index', () => {
    it('lists every compiled essay, with a link to each', async () => {
        await mountIndex();
        const links = [...container.querySelectorAll('a.writing-card')];
        expect(links.length).toBe(articles.length);
        expect(links.length).toBeGreaterThanOrEqual(3);
        for (const a of articles) {
            expect(text()).toContain(a.title);
            expect(links.some((l) => l.getAttribute('href') === `/writing/${a.slug}`)).toBe(true);
        }
    });

    it('renders titles newest-first, matching the module order', async () => {
        await mountIndex();
        const titles = [...container.querySelectorAll('.writing-card-title')].map(
            (n) => n.textContent.trim(),
        );
        expect(titles).toEqual(articles.map((a) => a.title));
    });

    it('shows a human date, not the raw ISO string', async () => {
        await mountIndex();
        expect(text()).toContain('July 2026');
        expect(text()).not.toContain('2026-07-18');
    });
});

describe('/writing/:slug — the reader', () => {
    it('renders the markdown as real elements, not literal syntax', async () => {
        await mountArticle('perceptual-movement');
        // headings and paragraphs actually exist …
        expect(container.querySelector('.writing-body h2')).toBeTruthy();
        expect(container.querySelectorAll('.writing-body p').length).toBeGreaterThan(3);
        // … and the raw markers never reach the screen
        expect(text()).not.toContain('## ');
        expect(text()).not.toMatch(/\*\*[A-Za-z]/);
    });

    it('never leaks the frontmatter fence into the article', async () => {
        // The failure this guards is silent and ugly: a mis-split would print
        // `title: "…" slug: "…"` at the top of the essay.
        await mountArticle('conceptual-movement');
        expect(text()).not.toContain('slug:');
        expect(text()).not.toContain('series: "');
    });

    it('renders a blockquote as a pull-quote', async () => {
        await mountArticle('perceptual-movement');
        expect(container.querySelector('.writing-body blockquote')).toBeTruthy();
    });

    it('sets the document title for sharing, and carries a back-link', async () => {
        await mountArticle('beyond-the-llm-centric-picture');
        expect(document.title).toContain('Semant');
        expect(document.title.toLowerCase()).toContain('llm-centric');
        const back = container.querySelector('a.writing-back');
        expect(back).toBeTruthy();
        expect(back.getAttribute('href')).toBe('/writing');
    });

    it('offers a next article rather than a dead end', async () => {
        await mountArticle(articles[articles.length - 1].slug);
        const next = container.querySelector('a.writing-foot-link');
        expect(next).toBeTruthy();
        expect(next.getAttribute('href')).toBe(`/writing/${articles[0].slug}`);
    });

    it('an unknown slug says so instead of throwing', async () => {
        await mountArticle('no-such-essay');
        expect(text().toLowerCase()).toContain('not found');
        expect(container.querySelector('a.writing-back')).toBeTruthy();
    });
});
