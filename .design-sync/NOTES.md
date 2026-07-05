# design-sync notes — Drishtikone (frontend/)

## What this DS is
The `frontend/` **Vite React app** (plain JSX, no TypeScript, no per-component
dist). Its design-system value is (1) the "Editorial Gallery" token + CSS system
and (2) a set of presentational components. Synced as the **package shape** in
**synth-entry mode** via a hand-written barrel (see below).

## Build setup (how the converter is pointed at an app, not a library)
- **Barrel entry**: `frontend/_ds-barrel.mjs` — named-re-exports every
  `src/components/*.jsx` default export (the converter's synth `export *` can't
  forward default exports), plus `ThemeProvider` and `MemoryRouter` for the
  preview provider. `cfg.entry` points at it; `--entry ./frontend/_ds-barrel.mjs`.
  **Regenerate it when components are added/removed** (the loop in the git history
  of this file / just re-run the generator: for each `src/components/*.jsx`,
  `export { default as <Name> } from './<path>'`). `componentSrcMap` must list the
  same set.
- **`--node-modules ./frontend/node_modules`**, `cfg.pkg="frontend"`,
  `cfg.globalName="Drishtikone"`. PKG_DIR walks up from the barrel to
  `frontend/package.json`.
- **Styling closure**: local token package `frontend/_ds/tokens/`
  (`cfg.tokensPkg="../_ds/tokens"`, `tokensGlob="*.css"`) holds `theme.css`
  (remote Google-Fonts @import + a **copy of `src/index.css`**) and `aliases.css`
  (defines `--bg-card --text-main --text-muted --accent-secondary --space-5/7/14
  --fs-h4`, which some component CSS references but the app never defined).
  `cfg.cssEntry="src/App.css"` appends the layout/feature classes. Component CSS
  (8 files) is auto-collected by esbuild.
- **Provider**: `{ThemeProvider > MemoryRouter}` — every component needs router
  context; `ThemeToggle` needs theme context.
- **Fonts**: remote Google Fonts `@import` in `theme.css` → `[FONT_REMOTE]`
  (informational). Families: Fraunces, Inter, Spline Sans Mono, Noto Sans
  Devanagari.

## Render check
No playwright/chromium cache; drove the **system Chrome** via
`DS_CHROMIUM_PATH=/usr/bin/google-chrome` with the `playwright` JS driver
installed into `.ds-sync/` (browser download skipped). Re-use this on re-sync.

## Authored previews (graded good)
PostCard, PostFeedCard, TextPostCard, NavBar, ThemeToggle. Images are inline SVG
data-URIs (`.design-sync/previews/_img.ts`) — CSP-safe, no network. The other 14
components ship the floor card (data-fetching panels/modals/editors + PostDetailPage;
they need a live backend to render meaningfully). Author more on any re-sync.

## Known render warns (expected — not new)
- `[FONT_REMOTE]` Fraunces/Inter/Spline Sans Mono — fonts load at runtime via the
  remote @import. Expected.

## Findings worth surfacing (app CSS, not sync bugs)
- `.feed-card` / `.text-post-card` use **hardcoded dark colors** (`rgba(42,42,45,.7)`,
  `#eee`, `#444`) instead of tokens — so PostFeedCard/TextPostCard render as dark
  cards in both themes. Faithful to the real component; flag to the app team.

## Re-sync risks (watch-list)
- **`frontend/_ds/tokens/theme.css` is a generated copy of `src/index.css`.** If
  `index.css` changes, regenerate it (fonts @import header + `cat src/index.css`)
  or the token closure goes stale. cpSync can't follow a symlink, hence the copy.
- **`_ds-barrel.mjs` + `componentSrcMap` are hand-maintained.** A new component in
  `src/components/` won't sync until added to both.
- `aliases.css` values were chosen to fit the existing scale — revisit if the app
  defines those tokens for real.
- Preview images are synthetic SVGs, not real photography.
