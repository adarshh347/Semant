# The writing showcase (`/writing`)

Essays as **static markdown, compiled into the frontend bundle.** No backend, no
Mongo, no API call. The section renders correctly with the backend down — which
is the whole point of a showcase.

## Publishing an article

1. Write/review the essay as markdown.
2. Save it as `src/writing/content/<slug>.md` with frontmatter (below).
3. Commit and push.
4. Vercel auto-deploys. It is live at `https://<domain>/writing/<slug>`.

That is the entire flow. There is no build step beyond `vite build`, no CMS, and
no admin UI — writing is editing repo files, which makes the section author-only
by its nature rather than by an auth check.

## Frontmatter

```markdown
---
title: "Perceptual Movement"
slug: "perceptual-movement"
date: "2026-07-18"
blurb: "One sentence for the index card."
series: "Thinking Within Images"
---

The body starts here. Standard markdown + GFM.
```

All five fields are strings, one per line. Notes:

- **`slug`** sets the URL. If omitted, the filename is used, so a file that
  forgets its frontmatter still resolves at a stable address.
- **`date`** is `YYYY-MM-DD` and drives ordering — the index is newest first.
- **`blurb`** shows on the index and under the article title.
- **`series`** is free text, shown as the eyebrow.

The parser (`articles.js`) is deliberately tiny: split on the first `---` block,
read `key: "value"` lines, strip matching quotes. It is **not** YAML. If an
article ever needs nesting, lists, or anchors, that is a signal the frontmatter
has outgrown a showcase — reconsider the shape rather than reaching for
gray-matter (which drags in a YAML engine and a Buffer polyfill).

## Rendering

`react-markdown` + `remark-gfm`. Styling lives in `writing.css` and is
token-driven (`--ink`, `--accent`, `--line`, `--font-display`), so light/dark
come for free. The measure is ~68ch, matching `MotivePage.css`.

Supported: headings, emphasis, lists, links, blockquotes (styled as
rule-bounded pull-quotes), code, hr, and GFM tables. Tables scroll inside their
own container so a wide table never makes the page scroll sideways.

## Files

| File | Role |
|---|---|
| `content/*.md` | the essays — the only files you touch to publish |
| `articles.js` | glob loader, frontmatter parser, date formatter |
| `WritingPage.jsx` | `/writing` — the index |
| `WritingArticlePage.jsx` | `/writing/:slug` — the reader |
| `writing.css` | editorial styling for both |
| `articles.test.js` | pins the parser and the ordering |

Routes are registered lazily in `src/main.jsx`; the nav link is in
`src/components/NavBar.jsx` (`TOOLS_LINKS`).
