# Home — the widget dashboard (creative design)

**Mode:** design + plan. No app code. Direction: a **curated Semant dashboard**, not a link grid or a KPI board — glanceable, editorial, plum (taste v1.3), every tile an on-ramp *into the work*. See the mockup for the visual target.

## Design principles (so a dashboard doesn't become slop)
- **Every tile is a door, not a decoration.** Each earns its place by getting you somewhere (a reading, the archive, a taste view) or telling you something you'll act on.
- **Editorial, not enterprise.** Serif tile titles, muted body, ONE plum accent per tile, generous gutters (identical throughout — the bento rule), flat cards on paper. No gradient/glass/KPI-gauge clutter.
- **Tile size = importance, not data volume.** "Continue in Chiasm" is the 2×2 hero tile; stats are a small 1×1.
- **The brand motif carries through:** the region-mark glyph (◈) on percept chips, plum region-marks, cool diagram pastels for image placeholders — the home *looks like* the product.

## The widget catalog
| Widget | Size | What it shows | Door to |
|---|---|---|---|
| **Hero strip** | full | wordmark + the wedge line + one ink-pill CTA | Enter Chiasm / Upload |
| **Continue in Chiasm** | 2×2 | recent in-progress readings (thumb · title · "4 percepts · 240 words") | resume a Chiasm session |
| **Your taste · Anuraṇana** | 2×1 | "your eye leans toward asymmetric drape…" + motif chips | the taste portfolio |
| **Read** | 1×1 | one Aletheia hook (image + lens + a fork) | the feed |
| **The Archive** | 1×1 | a live 3-image mosaic + "5,700 images →" | the Gallery archive |
| **Parts you recently noticed** | 3×1 | recent Percept chips (◈ restrained shoulder drape…) | jump to that percept/region |
| **This week** | 1×1 | glanceable numbers (readings · words · percepts) — the one dark tile for contrast | — |
| *(later)* **You keep noticing…** | 1×1 | a recurring-motif recall (Anuraṇana pattern) | a cross-post thread |
| *(later)* **Epics** | 1×1 | collections | epics |

## Curated vs customizable — two builds
1. **Curated (recommended first):** a fixed, hand-tuned bento (CSS grid + plum tokens). Fast, always looks right, no dep. Responsive 4→2→1 cols.
2. **Customizable (later, if wanted):** the user drags/resizes/rearranges tiles → **react-grid-layout** (or Muuri) with a persisted layout (`localStorage`/backend). This is the "make it yours" dashboard — real complexity (drag state, breakpoints, empty states), so ship curated first, add arrangement only if it becomes a goal.

## OSS to build it
| Need | Tool | Note |
|---|---|---|
| Bento layout | **CSS grid + tokens** | the default; bento is a pattern, not a lib (Tailwind bento kits excluded) |
| Draggable/resizable tiles | **react-grid-layout** / Muuri | only for the *customizable* build |
| Horizontal strips (Continue, reels) | **Embla Carousel** | headless, swipe/snap, you style it |
| Archive mosaic + taste thumbs | **react-photo-album** | reuse the archive's justified layout at tile scale |
| Taste snapshot viz | **Recharts** / **visx** | only if the taste tile wants a chart vs chips |
| Blur-up image loads | **Cloudinary LQIP** | you're already on Cloudinary — no new pipeline |
| Live tile data | **TanStack Query** | already in; each tile = a small cached query |
All MIT, CSS-agnostic → inherit plum tokens, no Tailwind.

## Creative moves worth trying (tasteful, not gimmicky)
- **Region-mark motif** as the home's signature (◈ on percept chips, thin plum outlines on hover).
- **Time-of-day tint** — the hero's one accent-soft wash shifts subtly morning/evening (a quiet living detail).
- **Continue tiles show a real crop** clipped to a marked region (SVG clipPath) — the "lifted percept" motif previewing the Chiasm idea on the home.
- **Motion (later, Motion lib):** tiles fade/rise on load (8–16px, `--ease`), reduced-motion safe — never bouncy.

## Ownership / sequencing
Home dashboard = the **OSS/app-shell session** (`feat/oss-foundation`, owns pages) — same track as the Gallery archive, no Chiasm files. Build order: curated bento + real tile data (Continue/Archive/Read/Taste/Stats) → Embla strips + Cloudinary blur-up → (optional) customizable arrangement.

## Decisions for Adarsh
1. **Curated vs customizable** home — curated first (my rec), or invest in drag-to-arrange (react-grid-layout) now?
2. **Taste tile:** motif chips (simpler, on-brand) vs a small chart?
3. Which widgets are v1 (I'd ship: Hero · Continue · Taste · Archive · Read · This-week) vs later (You-keep-noticing · Epics)?
