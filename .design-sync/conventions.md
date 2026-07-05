## Drishtikone — "Editorial Gallery" conventions

A warm, literary design system: paper/ink neutrals, a heritage terracotta accent,
Fraunces (display serif) + Inter (UI sans). Light + dark. Styling is driven by
**global CSS classes + CSS custom-property tokens** — not by component props.

### Setup / wrapping
Load `styles.css` once at the app root (it `@import`s the fonts, the tokens, and
all component styles). Two contexts are required for the components to work:

```jsx
import { ThemeProvider } from 'frontend';              // sets data-theme + persists it
import { BrowserRouter } from 'react-router-dom';       // NavBar / cards render <Link>s

<ThemeProvider><BrowserRouter>{app}</BrowserRouter></ThemeProvider>
```

Theme is switched by `ThemeToggle` (or by setting `data-theme="dark"` on
`<html>`). Every color/shadow token has a dark value under `[data-theme='dark']`,
so tokens flip automatically — never hard-code hex; use the tokens below.

### Styling idiom — use these, don't invent new names
Style layout with **tokens** (`var(--*)`) and reach for the **component classes**
for common UI. All names below exist in the shipped stylesheets.

Tokens (from `tokens/theme.css`):
- Color: `--bg` `--surface` `--surface-2` `--surface-hover` · `--ink` `--ink-muted`
  `--ink-subtle` `--ink-inverse` · `--accent` `--accent-deep` `--accent-soft`
  `--accent-ink` · `--line` `--line-strong` · `--info`
- Type: `--font-display` (Fraunces) `--font-sans` (Inter) `--font-mono` ·
  sizes `--fs-display` `--fs-h1` `--fs-h2` `--fs-h3` `--fs-body-lg` `--fs-small`
  `--fs-caption` · `--tracking-tight` `--tracking-wide`
- Space (4px scale): `--space-1 2 3 4 6 8 12 16 24`
- Radius: `--radius-sm md lg xl pill` · Shadow: `--shadow-sm md lg xl` ·
  Motion: `--ease`

Component classes (from `_ds_bundle.css`):
- Buttons: `.btn` + `.btn-primary` `.btn-secondary` `.btn-ghost`, sizes `.btn-lg`
  `.btn-sm`. (A bare `<button>` is already styled.)
- Chips/tags: `.chip` `.chip-accent`, feed tags `.tag-pill`
- Surfaces: `.card`, `.eyebrow` (uppercase accent kicker)
- Gallery: `.gallery-grid` wraps `.gallery-item` tiles (3:4, hover-lift)
- Layout: `.app-layout` `.app-content` `.page-header`

Headings (`h1`–`h3`) are auto-styled in Fraunces; body copy in Inter.

### Where the truth lives
Read before styling: `tokens/theme.css` (tokens + base + button/chip/card
primitives), `_ds_bundle.css` (gallery/feed/layout classes), and each component's
`components/<group>/<Name>/<Name>.prompt.md` + `.d.ts`.

### Idiomatic snippet
```jsx
import { PostCard } from 'frontend';

<section className="app-content">
  <p className="eyebrow">Recent work</p>
  <h2>The Gallery</h2>
  <div className="gallery-grid">
    {posts.map(p => <PostCard key={p.id} post={p} />)}
  </div>
  <button className="btn btn-primary btn-lg">Upload</button>
</section>
```
