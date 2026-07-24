# SEMANT-LANDING-002 — frontend implementation report

**Date:** 2026-07-24 · **Branch:** `docs/semant-landing-001` (continued) · **Commit:** `5bf4a21` `feat(site): build Semant perception engineering landing page`
**Precedes:** the docs pass `SEMANT-LANDING-001` (spec, copy, six articles, visual/hero spec — commit `dad646d`). Built from that copy + the "Great Arrival" visual spec.

## What was built
The React landing page and the `/notes` feature-article system, replacing the earlier fashion-first "See · Read · Write" motive landing at `/`.

**Files (14, exact-staged):**
- `frontend/src/pages/LandingPage.jsx` *(replaced)* — perception-engineering landing, componentised: `GreatArrival` (inline SVG hero) · `Hero` · `WhatSemantDoes` · `WorkbenchEngine` · `AudienceCards` · `PerceptionEngineering` · `ResearchPhilosophy` · `FeatureArticles` · `ProductForms` · `FooterAfterimage`. Keeps the `useReveal` IntersectionObserver pattern.
- `frontend/src/pages/LandingPage.css` *(replaced)* — self-scoped deep-twilight design system (product UI keeps Paper + Plum); the **"Great Arrival" cinematic hero** as pure CSS/SVG animation (thread draw-on via `stroke-dashoffset`, head bloom, connection reach, figure lift, ribbon, idle breath); status chips; cards; responsive.
- `frontend/src/components/MiniMarkdown.jsx` *(new)* — small dependency-free markdown renderer (front-matter strip, headings, lists, blockquote, hr, inline bold/italic/code); no `dangerouslySetInnerHTML`.
- `frontend/src/content/fieldNotes.js` *(new)* — the six notes' metadata + raw bodies via Vite `?raw`; single source for the landing grid and the article pages.
- `frontend/src/content/field-notes/01–06.md` *(new, 6)* — the canonical vault essays copied verbatim into the app.
- `frontend/src/pages/FieldNotesPage.jsx` + `FieldNotePage.jsx` + `FieldNotes.css` *(new)* — the `/notes` index and `/notes/:slug` article view (prev/next nav, scroll-reset, unknown-slug fallback).
- `frontend/src/main.jsx` *(edited)* — two lazy imports + routes `notes` and `notes/:slug`.

## Routing & CTAs (no broken links)
- `/` → new LandingPage. `/notes` → index. `/notes/:slug` → article.
- Hero CTAs: **Explore the Workbench** → `/home` · **Read the Technical Notes** → `/notes/perceptual-action-grammar` · **View Research Horizons** → `/notes`. Footer CTAs → `/home`, `/notes`. All targets are real routes.

## Visual direction
Sophisticated minimalist doodle on deep twilight; one red thread (the figure's ribbon + one tail thread); large negative space; Fraunces headline + Inter body (existing tokens). Hero authored so the **non-animated state is the composed afterimage still** → that is the `prefers-reduced-motion` fallback (motion is opt-in, matching the existing landing's discipline).

## Honesty
Status chips (`built` / `emerging` / `horizon`) carried on every workbench/engine/form/article card, consistent with SEMANT-LANDING-001 §8. No claim of live dispatch, agents, or persistent memory as shipped.

## Tests / build
- `eslint` on all new files — **0 problems**.
- `vite build` — **clean** (the >500 kB warning is pre-existing, from `partRefBlock`, unrelated to this change). New chunks: `LandingPage` ~15 kB, `fieldNotes` ~34 kB (raw article text, gzip ~12 kB), `FieldNotePage`/`FieldNotesPage` small.
- `vitest run` — **749 passed / 45 files** (canvas `getContext` messages are pre-existing jsdom noise, not failures). No test touched or broken.

## Caveats / next
- Not visually screenshot-verified in a browser this pass (headless env); recommend a quick visual QA of the hero motion + narrow-screen layout.
- `frontend/src/assets/background.jpeg` is now unreferenced by the landing (the old hero image); left in place, safe to prune later.
- In-app article bodies are copies of the vault essays; when a vault note changes, re-copy into `src/content/field-notes/` (or wire a shared loader) to avoid drift.
- Navbar is unchanged and still renders over the twilight hero; a landing-specific transparent nav treatment is a possible polish.
- Not pushed; no PR opened.
