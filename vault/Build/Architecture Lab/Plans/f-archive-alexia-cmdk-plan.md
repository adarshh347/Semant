# Prompt F — plan: the Archive, Alexia (extension), cmdk

Source: `vault/prompts/f-prompt.md` + 2 screenshots + code read. Three independent areas — none touch `PostDetailPage.jsx`, so all are parallel-safe with the Drishya/Track D threads.

---
## 1. The Archive (gallery) — `pages/GalleryPage.jsx`
Screenshot problems: the tag filter is a heavy flat purple-gray **box** with chunky white pills ("feels so bad"); Grid is boring; date-less/sequence timeline wanted; the "Wall" mode is unbuilt.

### 1a. Sequence-based timeline (not dates)
Uploads are bursty — many in a day, none for a week. So order/group by **upload sequence / session**, not calendar dates. Leverage the planned **`source_group`** (reels/carousels are natural sequences): show quiet sequence dividers ("Sequence · 40 frames from a reel") instead of "March 3." Infinite scroll stays (it's good).

### 1b. Kill Grid; keep Scroll; build the Wall
Two modes, not three: **Scroll** (the infinite editorial feed) + **the Wall** (below). Remove Grid.

### 1c. The Wall = a CLIP-similarity field (the taste graph, visible)
This is the marquee feature. Render the gallery as a **UMAP/t-SNE field of the FashionCLIP embeddings you already store** (`region_embeddings`) — similar images cluster, so the wall *is* your eye laid out in space. Inspiration: **PixPlot** (Yale DHLab, "Visualizing Image Fields") and its lighter CLIP-based fork **CLIP-Plot** — a WebGL viewer for UMAP-clustered images. Approach: backend computes a 2D projection (UMAP over the CLIP vectors) + HDBSCAN clusters; frontend renders a pannable/zoomable canvas/WebGL wall; click → open the image; hover → the reading. This literally makes **Anuraṇana** (the taste graph) navigable — the "resurfacing / third thing" made spatial.

### 1d. Redesign the tag section (name it)
The heavy box → a light, editorial **filter rail**: quiet inline chips (not a boxed slab), the active one emphasised, whitespace not a purple card. Naming options (each tag is a way *into* the archive): **"Threads"** (Sūtra vocabulary — each tag a thread through the wall), **"Lenses"**, or **"Facets."** Recommend **Threads**. Name the Wall mode: **"Field"** or **"Constellation"** (tie to Anuraṇana).

---
## 2. Alexia (the extension) — `chrome-extension/content.js`
Screenshot: 4 chunky mismatched pills — Brainstorm (black), Save (coral), Split→Save (navy), Save all (green). Old, loud, four colour languages, always popping up.

### 2a. Button redesign — one quiet language
Collapse the 4 loud coloured pills into **one compact, consistent toolbar** in a single visual language (one surface, one accent, icons + subtle labels), revealed on image hover. Not four carnival colours.

### 2b. Silencing (they pop up everywhere)
Add a **toggle + keyboard shortcut** to mute the overlay when not collecting (e.g. Alt+S to hide/show), persisted in `chrome.storage`. Download-any-image stays; it just isn't always shouting.

### 2c. The queue mess (the real bug — analyse + fix)
Today the **Insta save-queue and the split/carousel queue are two separate systems** that *supersede each other* — collecting from two sides at once collides (`renderQueueView` replaces on any other render, `queueViewOpen` guard). Fix: **one unified queue** for all capture sources (single save, carousel "Save all", video split), each item tagged by source. It must be **minimizable** (a small floating chip that expands), look good, and survive simultaneous multi-source capture without one clobbering the other. This is the "multitasking is messy" critique — root cause is two queues; the fix is one.

---
## 3. cmdk — `components/CommandPalette.jsx`
Today: basic ⌘K (Navigate / Tools / Upload / theme). Make it the **fast spine** (Raycast/Linear-grade):
- **Search posts + tags** inline (jump to any image/thread).
- **Actions:** run Dissect, open persona, toggle map, jump to a region, recent images.
- Grouped, keyboarded, with recents. It already uses the `cmdk` lib + a `semant:open-command` event — extend, don't rebuild.

---
## Coordination
All three are separate files (GalleryPage / chrome-extension / CommandPalette) — no `PostDetailPage.jsx` collision. Can run as three parallel sessions. The Wall's backend (UMAP projection endpoint over `region_embeddings`) is the one cross-cutting piece → coordinate with the vision-pipeline thread.
