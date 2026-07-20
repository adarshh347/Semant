# Home + Gallery archive revamp (+ Manuscript UI fixes)

**Mode:** research + plan. No app code changed.
**Grounding:** `GalleryPage.jsx` (prev/next, 50/page, raw axios), `HomePage.jsx` (43 lines, unused as entry — index route is Landing), Manuscript tags/block code in `PostDetailPage.jsx`. Taste **v1.3** (plum, editorial). OSS licences/patterns web-verified.

---

## 0. The reframe
Three separate problems the current entry conflates:
1. **The entry is a *tool* page.** `GalleryPage` stacks an upload form + a tag-analysis tool + a flat 50-at-a-time grid. That's a workbench, not a front door.
2. **The archive can't browse at scale.** ~5,700 images (114 pages × 50), reachable only by Prev/Next. That's the wrong pattern for an *archive*.
3. **The pager races.** `fetchPosts` fires a plain axios call per click and `setCurrentPage(response.current_page)` echoes the response — so fast clicks fire overlapping requests, the last to resolve wins (out of order), and `currentPage` fights the echo. That's the "hallucination."

**The move:** a **dynamic Home** becomes the entry (a bento of sections → Chiasm, Gallery, Read, taste widgets); the **Gallery becomes a proper image archive** (virtualized, infinite-scroll, justified grid, lightbox); upload and tag-analysis move *off* the archive into an action + a filter. Gallery is *one destination*, not the whole door.

---

## 1. The Home (new entry) — a restrained bento
Bento grid is the 2026 pattern for exactly this: a modular home of differently-sized tiles, each one type of content. Kept editorial per taste v1.3 (plum, whitespace, one accent, ≤1 idea/tile — *not* the gradient-bento-slop).

Sections (tiles), largest = most important:
- **Continue in Chiasm** (2×2) — your in-progress readings/manuscripts (recent posts you've attended). The primary on-ramp to the actual work.
- **The Archive** (2×1) — a peek into Gallery + "browse all" → the archive.
- **Read** (1×2) — the Aletheia feed hook (Track F).
- **Your taste** (1×1) — a taste-portfolio snapshot (Anuraṇana) — "your eye leans toward…".
- **Recent readings / Epics** (1×1 each) — quiet secondary tiles.
- One calm hero line (the wedge) up top; a single ink-pill CTA.

No Tailwind → build the bento with **CSS grid + plum tokens** (shadcn/Aceternity bento are Tailwind-locked → reference the *layout idea*, not the code). Responsive: 3–4 cols desktop → 2 tablet → 1 mobile (stack).

---

## 2. The Gallery = a real image archive
### 2a. Fix the pager (the race) — change the pattern, not just patch it
- **Replace Prev/Next with infinite scroll** via TanStack Query **`useInfiniteQuery`** (the OSS session already added Query). Query keys pages, dedupes in-flight requests, and returns them in order — the out-of-order race disappears structurally. An `IntersectionObserver` sentinel fetches the next page as you scroll.
- If a pager is kept anywhere, use **`placeholderData: keepPreviousData`** + latest-request-wins so a fast click can't show a stale page. But infinite scroll is the right archive pattern.

### 2b. Browse thousands smoothly — virtualized justified grid
- **Layout:** a **justified/masonry grid** (Google-Photos feel) — `react-photo-album` computes a justified layout (rows of similar height) from varying aspect ratios.
- **Virtualization:** only render what's on screen — `react-visual-grid` (built-in virtualization + masonry, renders thousands) *or* `react-photo-album` + **TanStack Virtual** (this is where OSS "item 2" folds in). Either keeps 5k+ images at 60fps.
- **Lightbox:** **PhotoSwipe** (framework-agnostic, zoom/swipe) for full-view — or reuse our own RegionLightbox styling for brand consistency.
- **Click a photo → open Chiasm** on it (the archive's job is to get you *into the work*).

### 2c. De-clutter the archive
- **Upload** → an action (the ⌘K palette already has it, or a modal via the Radix Dialog), not a form pinned above every browse.
- **Tag-analysis / story-gen** → a filter/tool surface, not on the archive page.
- **Tags** stay as **filter chips** (already there) + add search. The archive is *just* the archive.

### OSS picks (all CSS-agnostic / own-styles → no Tailwind issue)
| Need | Pick | Licence | Note |
|---|---|---|---|
| Justified/masonry layout | **react-photo-album** | MIT | Google-Photos justified rows from aspect ratios |
| Virtualized masonry (alt, all-in-one) | **react-visual-grid** | MIT | built-in virtualization, thousands of imgs |
| Virtualization engine | **TanStack Virtual** | MIT | pairs with react-photo-album (folds in OSS item 2) |
| Lightbox | **PhotoSwipe** | MIT | zoom/swipe full-view (or reuse RegionLightbox) |
| Infinite data | **TanStack Query `useInfiniteQuery`** | MIT | already in; fixes the race structurally |
| Bento home | CSS grid + tokens | — | shadcn/Aceternity bento are Tailwind-locked → reference only |

---

## 3. Manuscript UI fixes (Chiasm session — touches PostDetailPage)
### 3a. Tags section — stop it floating above / eating the writing
Today the TAGS block sits above the writing and, expanded, shows POPULAR chips + an Add-tag input that consumes most of the pane. Fix (per Lane 4's "sticky/collapsible, reachable while writing"): **move tags to a thin, collapsed strip at the *bottom* of the Manuscript** (a quiet metadata footer), expandable into a **bounded** popover/panel (max-height, its own scroll) that **never pushes the writing** — it overlays or occupies a fixed small height, then collapses. Writing space is sacred; tags are status, not content.

### 3b. Block behaviour — make prose flow, don't chunk
"The moment I press Enter another block is created" reads jarring because (a) block-to-block spacing is too large (consecutive paragraphs look like separate cards, not flowing prose) and (b) an empty block can appear eagerly. In the BlockNote Manuscript:
- **Enter = a new paragraph block is standard** (Notion/BlockNote paradigm) — keep it, but **tighten the inter-block rhythm** so consecutive paragraphs read as continuous prose, not chunks (a CSS/spacing pass on the block gap).
- **Shift+Enter = soft line break** within a block (for a break without a new block).
- **Structural blocks** (heading/quote/list) come from the **`/` menu**, not from Enter — so Enter never *changes* block type, only continues prose.
- **Don't seed/leave stray empty blocks**; clear an empty trailing block on blur. (BlockNote handles most of this; the work is spacing + Shift+Enter + not over-seeding.)
This is a taste + editor-config pass, small, and lands with/after BlockNote Phase 3.

---

## 4. Sequencing & ownership
- **OSS / app-shell session** (`feat/oss-foundation`, owns Gallery/Feed/App shell) → **Home bento + Gallery archive** (§1–2). This *absorbs* OSS batch item 2 (Virtual) and effectively supersedes item 3 (hotkeys — a quick add or defer). No Chiasm files.
- **Chiasm session** (owns PostDetailPage) → **Manuscript UI fixes** (§3), folded into/after BlockNote Phase 3.
- Two tracks, no shared files — same clean partition as before.

---

## Questions for Adarsh
1. **Archive browse:** infinite scroll (my rec) vs keep a pager (fixed with keepPreviousData)? Infinite scroll is the archive-native pattern.
2. **Layout:** justified rows (react-photo-album, Google-Photos feel) vs masonry columns (Pinterest feel)? For fashion/art I lean **justified**.
3. **Home tiles:** the set above (Continue in Chiasm · Archive · Read · Your taste · Epics) — add/cut any?
4. **Lightbox:** PhotoSwipe vs reuse our RegionLightbox for brand consistency?
