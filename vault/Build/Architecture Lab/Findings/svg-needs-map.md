# SVG needs-map — brand-svg-dispersal Phase 2 audit

**Branch:** `feat/brand-svg` · **Date:** 2026-07-23 · **Method:** grep + read of `frontend/src` (plus a parallel thorough sweep). Every candidate below was **confirmed in code** with a file:line — none assumed. **Status:** audit complete, *stopped for review before building the dynamic set* (per the build spec).

## Legend
- **Status** — `ASCII/EMOJI` (unicode/emoji glyph used as an icon) · `GENERIC` (lucide/CSS spinner where a branded mark belongs) · `BARE` (unstyled text, no visual) · `DONE` (already a bespoke on-brand SVG — verify plum tokens only).
- **Scope** — `🟢 SHELL` build here on this branch (presentational / new brand component, no Field/editor edits) · `🟡 FIELD` requires touching Chiasm/Field/editor files → **out of scope for this branch**, needs another session or an explicit go-ahead. The build spec's own rule ("no Chiasm/editor/Field-logic files") collides with several Phase-2 candidates; that collision is the main thing to resolve in review.

---

## A. Dynamic / runtime (the interesting ones)

| # | Surface | file:line | Now | Belongs | Status | Scope |
|---|---------|-----------|-----|---------|--------|-------|
| A1 | **Dissect "Dissecting the image…"** | `components/RegionSurface.jsx:365` | `<span className="rs-spin" /> Dissecting the image…` (CSS border-spinner, `DifferentialWorkspace.css:671`) | **Perceptual-scan**: region marks resolving over the frame — SVG + CSS, reduced-motion → static. *The canonical "dynamic pattern" example.* | GENERIC | 🟡 FIELD (RegionSurface is a Field surface) — new component `differential/glyphs/PerceptualScan.jsx` is 🟢, but wiring it in is 🟡 |
| A2 | **Passage / run-stream rail** | `differential/VisionActivityRail.jsx:34` (`StatusMark`, `va-entry--empty` → "No recorded activity") | text status marks, driven by **real recorded activity** | **Stage-pulse** SVG that animates *only on real stage completion*. Rail is already Invariant-9-clean (says "No recorded activity" rather than faking progress) — a branded `StatusMark` SVG can drop in without inventing state. | GENERIC | 🟡 FIELD |
| A3 | **Recall replay** | `differential/recall.js` + `differential/GroundLayers.jsx:18,70` | **Already** per-type SVG signatures: Path chevron travels, Boundary shimmers, Frame — all driven by real `progress`/`state`. | Largely **already built**. The spec's "pulsing region/return glyph" is essentially this. No new work; verify plum tokens. | **DONE** | 🟡 FIELD (do not touch) |
| A4 | **Gallery / Feed loading skeletons** | `components/ArchiveWall.jsx:206`, `ArchiveGrid.jsx:205` ("Loading the archive…"); `pages/TextFeedPage.jsx:34` ("Loading feed...") | bare text | Branded **shimmer** skeleton (TanStack Query is already wired), not a spinner or bare text. | BARE | 🟢 SHELL (Archive/Feed are presentational lists) |

**Other generic spinners found** (all CSS border-spin, candidates to route through a shared branded loader): `hook-spin` (`AletheiaHook.css:112`), `rf-spin` (`RefineSurface.css:120` / `RefineSurface.jsx:118,161`), `rd-spin` (`RegionDetectorModal.css:141`), `rs-spin` (`DifferentialWorkspace.css:671`), `icon-spin` (`ChatbotPanel.css:401`), `rq-spin` (`UnconcealQueuePage.jsx:107`). A small `<MarkLoader inline/>` variant (already built this branch) can replace most.

---

## B. Empty states (branded plum line motifs — region-mark language, not clip-art)

| # | Surface | file:line | Now | Status | Scope |
|---|---------|-----------|-----|--------|-------|
| B1 | Feed empty | `pages/TextFeedPage.jsx:44` — "No posts with stories found yet." (inline-styled `<p>`) | BARE | 🟢 SHELL |
| B2 | Epics empty | `pages/EpicsPage.jsx:48` — `.empty-state` "No Epics Yet" | BARE | 🟢 SHELL |
| B3 | Region/Field "no parts" | `components/RegionSurface.jsx:461` — `.rs-empty` "No parts yet." | BARE | 🟡 FIELD |
| B4 | Chatbot empty | `components/ChatbotPanel.jsx:226` — lucide `<MessageSquare size={48}>` **+ literal 💡 emoji at :230** | GENERIC + EMOJI | 🟡 FIELD (editor panel) |
| B5 | Research empty | `pages/ResearchPage.jsx:459` `.research-empty`; `:14` "Not yet inferred." | BARE | 🟢 SHELL |
| B6 | Anatomy empty | `pages/AnatomyPage.jsx:194,311` `.anatomy-empty` | BARE | 🟢 SHELL |
| B7 | Unconceal queue empty/done | `pages/UnconcealQueuePage.jsx:107,109` (`rq-spin` + `rq-done`) | GENERIC | 🟢 SHELL |
| B8 | RefPicker empty | `components/RefPicker.jsx:111` `.ref-picker-empty` | BARE | 🟡 FIELD (ref-insert) |
| B9 | Home "Continue" tile empty | `components/home/ContinueTile.jsx:57` "Nothing in progress yet." | BARE | 🟢 SHELL |
| — | **Gallery empty / Manuscript empty story / no-percepts / /you taste** — *no dedicated empty branch found*: Gallery leans on the Archive "Loading…" text; Manuscript seeds a paragraph (`PostDetailPage.jsx:475`) so it's never blank; `/you` is a `PlaceholderPage`. These are **not** current gaps — note for future, don't fabricate. | — | INFO | — |

---

## C. Field / Differential glyphs (ASCII → SVG)

| # | Surface | file:line | Now | Belongs | Scope |
|---|---------|-----------|-----|---------|-------|
| C1 | **`GROUND_GLYPH`** per `ground_type` | `differential/DifferentialWorkspace.jsx:48` | `{ field:'◐', path:'↝', boundary:'∥', frame:'▣', region:'◈', constellation:'⁘', relation:'⤝' }` + `:778` `☑/☐/◇` | 7 bespoke plum SVG icons → `differential/glyphs/` (new files 🟢, wiring 🟡) | 🟡 FIELD |
| C2 | Same map, **RefPicker** copy | `components/RefPicker.jsx:8–9,47` | duplicate ASCII `GROUND_GLYPHS` | reuse the C1 set (single source) | 🟡 FIELD |
| C3 | **Percept `◈` chip mark** | `components/ArchiveGrid.jsx:187` (`arch-seq-mark`), `components/ArchiveTimeline.jsx:126` (`arch-tl-seqmark`), `components/home/TasteTile.jsx:41` | literal `◈` | a small `<PerceptMark/>` SVG (region-mark language) | 🟢 SHELL (Archive/Home) / 🟡 for any Field use |
| C4 | Dissect / Refine / tool icons in `.diff-tools` | `differential/DifferentialWorkspace.jsx:471` | lucide-react icons | bespoke plum tool glyphs | 🟡 FIELD |

---

## D. Motif / decoration

| # | Surface | file:line | Now | Status |
|---|---------|-----------|-----|--------|
| D1 | **See·Read·Write explainer cards** | `pages/LandingPage.jsx:64,80,97` (`SeeMotif`/`ReadMotif`/`WriteMotif`) | **Already** thick-line + one-plum-accent hand-drawn SVGs, per taste spec §7 | **DONE** — verify tokens only (🟢). *Spec candidate already satisfied.* |
| D2 | Region-mark section divider / chip motif | `ArchiveGrid.jsx:187`, `ArchiveTimeline.jsx:126` use `◈` as a "Sequence · N frames" divider | replace with C3 `<PerceptMark/>` | 🟢 SHELL |
| D3 | Home bento tile accents | `components/home/*Tile.jsx` (`TasteTile` uses `◈`) | light plum mark accents | 🟢 SHELL |

---

## E. Marketing — pitch page → `/about`

| Item | Finding | Status |
|------|---------|--------|
| E1 | Wire `semant-pitch.html` in as `/about` (or `/perceptual-medium`) with thesis/unit/protocol/possibility SVGs | **`semant-pitch.html` is NOT in the repo** (`find` across the repo returns nothing; no `/about` route). **Blocked** — needs Adarsh to drop the file, or a go-ahead to author the route from the pitch copy. | 🟢 SHELL when unblocked |

---

## Recommended build order (in-scope 🟢 first)

**Shell-safe, buildable on this branch now** (one small commit each, plum-themed, reduced-motion-safe, screenshot each):
1. **C3 `<PerceptMark/>`** — retires the most-repeated `◈` (Archive grid, timeline, TasteTile). High visibility, zero Field risk.
2. **B1/B2/B5/B6/B7/B9 empty states** — a shared `<EmptyState mark=… />` with a plum region-mark line motif; swaps the bare `<p>`s.
3. **A4 branded skeletons** + inline `<MarkLoader/>` replacing the shell-side spinners (`rq-spin`, Archive/Feed "Loading…").
4. **D2/D3** motif accents once C3 lands.

**Needs review / coordination before building (🟡 FIELD — collides with the "no Chiasm/editor/Field-logic files" rule):**
- **A1** perceptual-scan (RegionSurface), **A2** stage-pulse (VisionActivityRail), **C1/C2/C4** ground/tool glyphs (DifferentialWorkspace, RefPicker), **B3/B4/B8** Field/editor empty states. Build the *new* SVG components under `differential/glyphs/` here if desired, but **wiring them into Field files must wait** for a session that owns those files (they're being edited elsewhere per the spec).

**Blocked:** **E1** pitch/`/about` — awaiting `semant-pitch.html`.

## Invariant-9 note
Only **A2** (stage-pulse) is an animated *progress* SVG. `VisionActivityRail` already drives off **real recorded activity** and shows "No recorded activity" when empty — so a branded StatusMark can replace the current mark **without** inventing progress. Keep it that way: any pulse animates on a real stage-completion event or stays decorative-static. `A3`/recall is already real-state-driven.

## What changed the spec's assumptions
- **D1 (landing See·Read·Write motifs) and A3 (recall replay) are already bespoke SVGs** — not gaps. Building would duplicate.
- **Correction on Manuscript:** there *is* an empty-story branch after all — `PostDetailPage.jsx:1179` `story-empty` uses a generic lucide `PenLine`, and highlights-empty `:1248` uses lucide `Underline` (both 🟡 FIELD/editor). Gallery still has **no** empty branch (delegates to Archive "Loading…"); `/you` is a placeholder.
- The real, unglamorous bulk of the work is **empty states + the `◈`/ground ASCII glyphs + spinners**, split cleanly by the SHELL/FIELD line above.
- **Cross-cutting:** two divergent glyph systems name the same seven Ground types — the unicode `GROUND_GLYPH` map (`DifferentialWorkspace.jsx:48`, `RefPicker.jsx:7`) *and* the lucide `.diff-tools` rail (`DifferentialWorkspace.jsx:31–40`). One bespoke SVG ground-glyph set should unify both **plus** the scattered `◈` motif everywhere in the appendix.

---

## Appendix — full sweep inventory (exhaustive backing, line-referenced)

*Corroborated by a thorough second-pass sweep. This is the long tail behind the curated tables above; use it as the build checklist. Scope still governed by the SHELL/FIELD line.*

### i. The `◈` "region-mark" motif — done as a unicode char everywhere (→ one `<PerceptMark/>`)
`components/home/HeroTile.jsx:14` · `home/TasteTile.jsx:41` · `home/ReadTile.jsx:39` · `home/PerceptsTile.jsx:50` · `home/ContinueTile.jsx:78` · `components/ArchiveGrid.jsx:187` · `components/ArchiveTimeline.jsx:126` · `components/PostDetailPage.jsx:1050` (tab label 🟡) · `components/blocknote/partRefBlock.jsx:54` (🟡) · `components/blocknote/Manuscript.jsx:56,106` + `:89 ✶`, `:112 ▣`, `:118 ◎`, `:124 ✦` (slash/mention menu 🟡) · `pages/BlockNoteLab.jsx:55`. Home grid + `HomePage.css:3` are themed on this glyph (🟢 for Home/Archive; 🟡 for BlockNote/PostDetail).

### ii. Generic spinners (CSS border-spin) → shared branded loader
`RefineSurface.css:120` (🟡) · `AletheiaHook.css:112` (🟢) · `RegionSurface.css:184` (🟡) · `EpicsPage.css:180` → `EpicsPage.jsx:44` (🟢) · `RegionDetectorModal.css:141` (🟡) · `PostDetailPage.css:2009` (🟡) · `UnconcealQueuePage.css:68` (🟢) · `DifferentialWorkspace.css:665,795` (🟡) · `ChatbotPanel.css:401` (🟡) · `AnatomyPage.css:434` (🟢) · `PersonasPage.css:76` (🟢) · `ResearchPage.css:96` (🟢) · `ImageSelectorModal.css:68` (🟡) · `EpicEditorPage.jsx:93` (🟢) · lucide `Loader2` at `differential/FindSimilar.jsx:92` (🟡).

### iii. Bare "Loading…" text (no mark)
`PostDetailPage.jsx:879` (🟡) · `RefineLab.jsx:29` · `RegionSurfaceLab.jsx:77` · `PersonasPage.jsx:131` · `TextFeedPage.jsx:34` · `HighlightsPage.jsx:34` · `ArchiveGrid.jsx:205` · `ArchiveWall.jsx:206` · `VisionActivityRail.jsx:160` (🟡). **Home-tile loading (all plain text):** `home/TasteTile.jsx:34` · `home/ReadTile.jsx:23` · `home/ContinueTile.jsx:53` · `home/WeekTile.jsx:35` · `home/PerceptsTile.jsx:38` (all 🟢). Only real skeleton: `RegionSurface.jsx:458` `.rs-skel-row` / `.rs-shimmer` (unbranded, 🟡).

### iv. Additional empty states not in §B
`PostDetailPage.jsx:1179` story-empty (lucide `PenLine`, 🟡) · `:1248` highlights-empty (lucide `Underline`, 🟡) · `DifferentialWorkspace.jsx:757` `diff-insp-empty` "Nothing under attention" (🟡) · `PersonasPage.jsx:239` "No personas yet" (🟢) · `home/PerceptsTile.jsx:55` / `home/TasteTile.jsx:47` / `home/ContinueTile.jsx:55` (Home tiles, 🟢) · `blocknote/partRefBlock.jsx:26` empty crop (🟡).

### v. `.diff-tools` rail — full lucide inventory (`DifferentialWorkspace.jsx:31–40`, 🟡)
Select `MousePointer2` · Brush `Brush` · Trace `PenTool` · Collect `Group` · Connect `Waypoints` · Frame `Frame` · Refine `Scan` · Read `Sparkles` · Similar `Search`. Same ops carry unicode ground-glyphs in `GROUND_GLYPH` → unify. Also Dissect/Refine CTAs: `RegionDetectorModal.jsx:162` `Sparkles`, `SemanticReading.jsx:200` `Scan`, `RegionSurface.jsx:403`.

### vi. Emoji / status glyphs as icons (no emoji left, per spec)
`PhraseGenerator.jsx:64,104` ✨ (🟡) · `UntaggedImagesSidebar.jsx:197` 🔄 (🟡) · `ChatbotPanel.jsx:55` 🎯, `:230` 💡 (🟡) · `pages/ManuscriptLab.jsx:29` ☾/☀ (🟢) · status ticks `✓` at `RefineSurface.jsx:122`, `DifferentialWorkspace.jsx:586`, `ImageSelectorModal.jsx:81`, `PersonasPage.jsx:143` · `✕` `UntaggedImagesSidebar.jsx:112` · `↻` `UnconcealQueuePage.jsx:131` · `★` `RegionSurface.jsx:359,381`, `RegionDetectorModal.jsx:134`, `AnatomyPage.jsx:223`.

### vii. Landing extras (beyond the done D1 motifs)
`LandingPage.jsx:50` `HERO_REGIONS` overlay is plain CSS boxes (`:167`) not SVG — a hand-drawn plum region-bracket could replace · CTA arrows unicode `:156 →`, `:159 ↓`, `:272 →` · the problem/payoff/room sections (`:181–274`) are type-only, each could carry a small line motif. All 🟢.
