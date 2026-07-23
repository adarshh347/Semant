# Brand SVG dispersal + SVG-system discovery — build spec

**To:** Claude Code (a fresh **`feat/brand-svg`** branch off `origin/main`, isolated worktree; the SVG work is app-shell — keep out of Chiasm/editor files being edited by other sessions). **Mode:** build.
**Identity:** Paper + Plum (taste spec v1.2/1.3). Mark = **"The Ground"** (a perceptual world holding a durable region + a return point). Serif = Fraunces; accent plum `#5E2B50` (dark `#C08BB4`). One accent per view; ink pill = primary action; **replace emoji/ASCII glyphs and generic spinners with branded SVG**.
**Assets:** the production logo set exists (mark, mark-mono, mark-reversed, favicon, lockup(+reversed), wordmark, social-card 1200×630) — Adarsh has `semant-brand-kit.zip`. The canonical **mark source** is embedded at the end of this spec; recreate the set into `frontend/public/brand/` + `frontend/src/assets/brand/` if the zip isn't dropped in.

## Phase 1 — Disperse the logo set to every page (the "site-wide identity" pass)
1. **Favicon + touch icons + title:** replace the old favicon and any `Drishtikone` remnants — `frontend/index.html`: `<link rel="icon" href="/brand/semant-favicon.svg">`, apple-touch-icon, `<title>Semant …</title>`, theme-color `#FAF7F5`.
2. **OG/social meta:** add `og:image`/`twitter:image` = `semant-social-card` (1200×630), `og:title`/`description` from the pitch (thesis line). Site-wide.
3. **Nav logo:** `components/NavBar.jsx` — the mark + "Semant" Fraunces wordmark as the logo (a shared `<SemantMark/>` component in `src/components/brand/`), used on every page; reversed variant when on a dark surface.
4. **404 / error boundary + route Suspense fallback** (`App.jsx` `RouteFallback`): a small centered **mark loader** (the mark with a gentle draw/pulse; `prefers-reduced-motion` → static), not a generic spinner.
5. Verify: favicon shows in the tab; nav logo on every route; social card resolves; no `Drishtikone`/old-logo strings. Screenshot. **Stop for review.**

## Phase 2 — Discover + build the SVG system (audit-first)
**First audit** the app for every place a bespoke SVG belongs (grep + read); produce a short `svg-needs-map.md` under the branch, then build them as a small themed set in `src/components/brand/` + `src/differential/glyphs/`. Candidate map to verify and extend (do NOT assume — confirm each in code):

- **Dynamic / runtime** (the interesting ones):
  - **Dissect "Dissecting the image…"** (`RegionSurface.jsx:365`) → a **perceptual-scan** animation: region marks resolving over the frame (SVG + CSS, reduced-motion safe). *This is the "dynamic pattern" example.*
  - **Orchestration / Passage Rail** (per the CS-001 P0 packet — a future run-stream): a **stage-pulse pattern** SVG that animates only on *real* events (do not fabricate progress — Invariant 9; drive it from actual stage completion, else keep it static). Provide the component; wire to real data only.
  - **Recall replay** (`differential/recall.js`) → a pulsing region/return glyph.
  - Gallery/Feed **loading skeletons** (already on TanStack Query) → branded shimmer, not a spinner.
- **Empty states** (branded, hand-drawn plum line motifs — the region-mark language, not clip-art): Gallery empty, Feed empty, Manuscript empty story, no-percepts / no-grounds in the Field, `/you` (taste) empty, Epics empty, Home dashboard tiles.
- **Field / Differential glyphs:** upgrade `GROUND_GLYPH` (`DifferentialWorkspace.jsx` / `grounds.js` — currently `◇/☑/☐` ASCII) to a real SVG icon per `ground_type` (region · field · path · boundary · constellation · relation · frame); a **percept** glyph replacing the `◈` chip character; Dissect/Refine/tool icons in `.diff-tools`.
- **Motif / decoration:** the region-mark as a section divider / chip motif; the See·Read·Write explainer cards on the landing (flat cool-pastel cards + one hand-drawn line each, per taste spec §7); Home bento tile accents.
- **Marketing:** wire the **pitch page** (Adarsh's `semant-pitch.html`) into the app as `/about` (or `/perceptual-medium`), reusing the plum tokens; add its thesis/unit/protocol/possibility SVGs as reusable components.

Build in small commits (one surface each), plum-themed, reduced-motion safe, no emoji/ASCII glyphs left. Screenshot each. Update the needs-map as you find more. **Stop after the audit for review before building the dynamic ones.**

## Rules
- Fresh `feat/brand-svg` off `main`, isolated worktree, **no Chiasm/editor/Field-logic files** (only presentational/shell + new brand components). CI green; conventional commits; own issue + PR (needs the `test` check).
- Invariant 9: any animated "progress" SVG must reflect **real** backend/runtime state or remain decorative-static — never fake orchestration progress.

## Canonical mark source (drop into /brand/semant-mark.svg)
```svg
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Semant">
  <rect x="3" y="3" width="52" height="52" rx="12" fill="none" stroke="#5E2B50" stroke-width="3.4"/>
  <rect x="14" y="20" width="26" height="22" rx="6" transform="rotate(-9 27 31)" fill="#5E2B50"/>
  <line x1="42" y1="42" x2="55" y2="55" stroke="#5E2B50" stroke-width="2.6" stroke-linecap="round"/>
  <circle cx="58" cy="58" r="4.4" fill="none" stroke="#5E2B50" stroke-width="2.6"/>
</svg>
```
Favicon uses a paper-tile version; reversed uses `#FAF7F5` on `#4A2140`; mono uses `#17121A`. Accept the mark as a `currentColor`-drivable component so it inherits context where needed.
