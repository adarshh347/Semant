# OSS tools brainstorm — Home · Archive · Editor

**Mode:** research only. A menu of open-source tools for the three areas, each with role · licence · fit · verdict, then a recommended stack. All are MIT and **CSS-agnostic** (no Tailwind needed). Companion to `home-and-archive-revamp.findings.md`.

---

## Area A — The Archive (browse thousands of images)
| Tool | Role | Verdict |
|---|---|---|
| **TanStack Query `useInfiniteQuery`** | data + the race fix (ordered, deduped, infinite scroll) | **core** — already in the app; makes the prev/next race impossible |
| **react-photo-album** | justified/masonry **layout** from varying aspect ratios (Google-Photos feel) | **core** — computes the grid; pairs with a virtualizer |
| **TanStack Virtual** | **virtualization** — render only on-screen rows | **core** — 5k+ images at 60fps (this is OSS "item 2") |
| **react-visual-grid** | all-in-one virtualized masonry (alt to the two above) | alt — simpler but less control; pick this *or* photo-album+Virtual |
| **ThumbHash** (or BlurHash) | compact **blur-up placeholder** while the image loads | **premium feel** — no grey pop-in; needs a tiny hash per image (or use **Cloudinary's LQIP/blur** since you already use Cloudinary — no new backend) |
| **yet-another-react-lightbox** | modern React **full-view lightbox** (zoom/swipe) — by react-photo-album's author, composes cleanly | **recommended lightbox** — or reuse our RegionLightbox for brand consistency |
| PhotoSwipe | framework-agnostic lightbox | alt to YARL |
| native `loading="lazy"` + IntersectionObserver | lazy image loading | use this; no lib needed (skip react-lazy-load-image) |

**Recommended archive stack:** `useInfiniteQuery` + **react-photo-album** + **TanStack Virtual** + **ThumbHash/Cloudinary-LQIP** + **yet-another-react-lightbox**. That's a Google-Photos-grade archive: infinite, virtualized, justified, blur-up, zoomable.

---

## Area B — The Home (dynamic entry)
| Tool | Role | Verdict |
|---|---|---|
| **CSS grid + tokens** (no dep) | the **bento** layout, hand-built to taste v1.3 | **default** — bento is a *pattern*, not a lib; shadcn/Aceternity bento are Tailwind-locked (reference only) |
| **react-grid-layout** / **Muuri** | **draggable, resizable, user-arrangeable** widget grid | **optional/defer** — only if the home should be *user-customizable* (real complexity; static bento first) |
| **Embla Carousel** | lightweight horizontal strips (swipe/snap) | **recommended** for "Continue in Chiasm" rows, reel/carousel posts (you have `carousel`/`video-frame` tags) — headless, you style it |
| Nuka Carousel | batteries-included carousel | alt to Embla (heavier) |
| **Recharts** / **visx** | the "Your taste" snapshot widget (Anuraṇana viz) | when the taste tile needs a chart |

**Recommended home stack:** static **CSS-grid bento** + **Embla** for horizontal strips + a small chart lib for the taste tile. Add **react-grid-layout** only if "arrange your own home" becomes a goal.

---

## Area C — Upload (move it off the archive)
| Tool | Role | Verdict |
|---|---|---|
| **Uppy** | modular uploader — drag-drop, progress, webcam, cloud (Drive/Dropbox), resumable | **recommended** — replaces the bare form with a real upload UX, launched from ⌘K / a Radix Dialog |
| Radix Dialog + a small dropzone | minimal upload modal | enough if Uppy feels heavy; you already have Radix Dialog |

---

## Area D — Editor / block smoothness (the honest answer: no new dependency)
The "Enter makes another block" feel is **not a missing library** — it's the block-editor paradigm plus tuning. The OSS here is what you already chose:
- **BlockNote** (have it) — the smoothness is **config + CSS**: tighten inter-block spacing so prose flows, `Shift+Enter` = soft line break, structural blocks only via `/`, don't over-seed empty blocks.
- **Novel** — *reference* for the ghost-text/inline-AI interaction (harvest the UX, not the package).
- No third editor engine (Lexical/Plate rejected earlier — wrong family).

So: don't add a tool here; tune BlockNote (folds into Manuscript Phase 3, per the revamp plan §3b).

---

## How much to actually adopt (don't take it all)
1. **Now (core archive):** useInfiniteQuery + react-photo-album + TanStack Virtual + a lightbox. Fixes the real problems (race + scale + browse).
2. **Polish (soon):** ThumbHash/Cloudinary-LQIP placeholders; Embla strips on the Home.
3. **Optional/defer:** Uppy (nicer upload), react-grid-layout (customizable home), a chart lib (taste widget).
4. **No new dep:** the editor smoothness (tune BlockNote), lazy-loading (native).

Everything MIT, CSS-agnostic — they inherit the plum tokens, no Tailwind.

## Decisions for Adarsh
1. **Placeholders:** ThumbHash (needs a hash per image) vs Cloudinary's built-in LQIP/blur (zero backend, since you're already on Cloudinary)? I lean **Cloudinary LQIP** — free, no pipeline.
2. **Lightbox:** yet-another-react-lightbox vs reuse our RegionLightbox (brand-consistent)?
3. **Home:** static bento now, or invest in a **customizable** widget home (react-grid-layout) later?
4. **Upload:** Uppy vs a simple Radix-Dialog dropzone?
