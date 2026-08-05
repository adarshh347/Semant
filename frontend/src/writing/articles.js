/**
 * The writing showcase — static articles, compiled in.
 *
 * There is deliberately no backend here. The essays are author-only and few, so
 * they live as markdown in the repo and ship with the frontend build: drop a
 * reviewed `<slug>.md` into `content/`, commit, push, and Vercel deploys it.
 * That also keeps the section entirely off the API — it renders with the
 * backend down, which is the point of a showcase.
 *
 * `eager: true` means the markdown is inlined at build time, so the list page
 * needs no async state and an article is never a loading spinner.
 */

const modules = import.meta.glob('./content/*.md', {
    query: '?raw',
    import: 'default',
    eager: true,
});

/**
 * Split the leading `---` block off a markdown file and read its `key: "value"`
 * lines.
 *
 * Intentionally NOT gray-matter: that pulls in a YAML engine and a Buffer
 * polyfill for a format that is, here, five flat string fields. Anything
 * needing real YAML (nesting, lists, anchors) is a sign the frontmatter has
 * outgrown a showcase and should be reconsidered rather than parsed harder.
 */
export function parseFrontmatter(raw) {
    const text = String(raw).replace(/^﻿/, '');
    const match = /^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(text);
    if (!match) return { meta: {}, body: text.trim() };

    const meta = {};
    for (const line of match[1].split(/\r?\n/)) {
        const kv = /^\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$/.exec(line);
        if (!kv) continue;
        let value = kv[2].trim();
        const quoted =
            (value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"));
        if (quoted && value.length >= 2) value = value.slice(1, -1);
        meta[kv[1]] = value;
    }
    return { meta, body: text.slice(match[0].length).trim() };
}

/** `2026-07-18` → `18 July 2026`. Returns '' for a missing/unparseable date. */
export function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(`${iso}T00:00:00Z`);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
    });
}

/**
 * Every article, newest first. The filename is the fallback slug so a file that
 * forgets its frontmatter still resolves at a stable URL rather than at
 * `/writing/undefined`.
 */
export const articles = Object.entries(modules)
    .map(([path, raw]) => {
        const { meta, body } = parseFrontmatter(raw);
        const fileSlug = path.split('/').pop().replace(/\.md$/, '');
        return {
            ...meta,
            slug: meta.slug || fileSlug,
            title: meta.title || fileSlug,
            body,
        };
    })
    .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));

export const getArticle = (slug) => articles.find((a) => a.slug === slug) || null;
