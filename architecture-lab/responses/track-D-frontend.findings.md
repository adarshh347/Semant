# Track D — Unified annotation UX (premium Visual pane): findings

**Mode:** deep read + plan. No app code changed.
**Lens (Purpose→Structure):** Drishya's Visual pane is where you *see an image, mark its parts, say how each affects you*. Today that one act is split across **three disconnected homes** with two visual languages — and the richer, cleaner one is trapped in a modal. Track D folds the three into one live pane and makes the modal's machinery the pane.
**Grounding:** line refs current as of `e19222a`. Verified by direct read of `BoundingBoxEditor.jsx` + `.css`, `RegionDetectorModal.jsx` + `.css`, and the Visual-pane / Unconceal structure of `PostDetailPage.jsx` (`:764-843`, `:1060-1140`, `:1198`).
**Consumes** (locked): one `Region` model (Track A — `actor=auto|creator|audience`, polygons for auto, rects for manual, `part`/`attributes[]`); Track B's **many parts + lazy on-tap SAM2/fine reveal** and **atmosphere-is-image-global**; Track C's **context-triggered, region-tied Aletheia reading** (per-lens `region_ids`) + the feed-hook + Écart-as-reading-act.
**Coordination:** `PostDetailPage.jsx` is **shared with the Drishya UI thread**. Research = zero edits = no conflict. **D's BUILD will edit it → must be serialized** (see §6).

---

## 0. Headline (up front)

**There are three region/reading homes today; unify them into one live Visual pane, and make the already-clean auto-anatomy modal the design source — not the neon manual editor.** The single most useful finding:

> **`RegionDetectorModal` is already 90% of the premium unified pane** — it renders true polygons/rects on one normalized SVG (`viewBox 0 0 100 100`, `:106-123`), groups anchors→fine parts (`:79-86`), does focus-select, prioritise, weight, per-part "how it affects me" notes, and a parts-list synced to the shapes — **all in design tokens** (`--line/--accent/--radius-*/--surface`, `RegionDetectorModal.css` throughout). It's just **trapped in a modal** and **duplicated** by a second, neon manual editor.

So Track D is mostly **un-modalling + merging**, not new invention:
1. **One surface:** promote `RegionDetectorModal`'s body into the live left pane; retire `BoundingBoxEditor`'s separate manual system; manual marks become `actor="creator"` rect-regions drawn on the *same* SVG. Retire the right-pane **Unconceal tab** — Aletheia + commentary fold into the Visual pane.
2. **Non-messy reveal of many parts** (load-bearing now Fashionpedia yields dozens): progressive coarse→fine, category/attribute filters, focus-one-dims-others, a parts panel synced to shapes, lazy "reveal more" (matches Track B's on-tap SAM2).
3. **Pick→comment→remember:** the modal's loop already exists (select → note → save → `region_annotations`); make it live and show saved state on return.
4. **Aletheia in-pane:** a calm reading strip whose per-lens `region_ids` (Track C) highlight the parts on the image — the reading and the geometry finally co-located.
5. **Premium via structure + a kill-list:** delete the glassmorphism/neon/emoji islands (all in `BoundingBoxEditor`), keep the token grammar the modal already follows. Clean enough that Track F's one-tap consumer variant **falls out of the same surface**.

---

## 1. The three homes today (what we're unifying)

| # | Home | Where | What it does | Visual language |
|---|---|---|---|---|
| **1. Manual boxes** | `BoundingBoxEditor` in the **left Visual pane** (`PostDetailPage:787-789`) | draw pixel rects, name them, resize handles, tags list | **pixel-space** boxes (`box.x`px `:316-319`), PATCHes `bounding_box_tags` (`:194,223,241` — the field Track A **retires**) | **neon + glass + emoji** (kill-list §5) |
| **2. Auto anatomy** | `RegionDetectorModal` — a **modal overlay** (`PostDetailPage:1198`) | detect anchors+fine, polygons on SVG, parts list, prioritise, weight, notes → `region_annotations` | **normalized** SVG (`:106`), grouped anchors/fine (`:79-86`) | **clean, tokenized** (design source) |
| **3. Reading + commentary** | right pane **"Unconceal" tab** (`PostDetailPage:1060-1140`) | run Aletheia (`runAletheia:597`), lens list, curator commentary, prioritised-region chips (`:1075-1081`), save `local_context` (`:610`) | tokenized, but **separated from the image** |

Three problems this split creates:
- **Two data models on screen** — manual `bounding_box_tags` (pixel, Track-A-retired) vs auto `region_annotations` (normalized). Track A already merged them into one `Region`; the UI hasn't caught up. **Home 1 must be rebuilt on `region_annotations` as `actor="creator"` regions** (this is the frontend half of Track A's §4 blast radius — the "largest change").
- **The good UI is a modal** — the auto-anatomy surface (Home 2) is richer and cleaner than the live pane, but you have to open a modal to get it. Un-modal it.
- **Reading is divorced from the image** — Aletheia (Home 3) is a *tab on the other side of the split*, so you read the image where you can't see your marks. Track C tied lenses to `region_ids`; that link is wasted unless the reading sits **on** the pane.

Also noted (quirk to fix in build): the left pane's **"Image" / "Annotations" tabs** (`:769-782`) set `activeLeftTab` but nothing consumes it for rendering — `BoundingBoxEditor` mounts unconditionally (`:787-789`). It's a dead toggle; the unified pane replaces it with a real layer control (§2).

---

## 2. Unified surface structure + the many-parts reveal model

**The pane (one live surface, replacing left-pane tabs + the modal + the Unconceal tab):**

```
┌ Visual pane (post-detail-left) ─────────────────────────────┐
│ panel-header:  [Image · Regions]        [＋mark] [Dissect ▾] │  ← tabs→layer toggle + verbs in the actions slot (:784)
│ ┌──────────────────────────┬───────────────────────────┐   │
│ │  IMAGE + one SVG overlay │  PARTS PANEL (synced)      │   │
│ │  · auto polygons          │  · filter chips: category  │   │
│ │  · creator rects          │    / attribute / "moved me"│   │
│ │  · focus dims others      │  · anchor ▸ fine (grouped) │   │
│ │  · tap a part → selects   │  · ★ prioritise · • has-note│  │
│ │                           │  [＋ reveal more parts]     │   │  ← lazy on-tap SAM2/fine (Track B)
│ └──────────────────────────┴───────────────────────────┘   │
│ READING STRIP (Aletheia): fired lenses · tap a lens →       │  ← Track C reading, region-linked
│                            highlights its region_ids        │
│ SELECTED PART EDITOR: label · category/attributes · intensity│
│                       · "how does this affect you?" note    │
└─────────────────────────────────────────────────────────────┘
```

- **One SVG, two region kinds.** The modal already draws polygons *or* rects by shape presence (`RegionDetectorModal:112-121`). Auto regions carry `polygon`; creator marks carry only `box` → same loop renders both. `actor`/`detector` drive a subtle style difference (auto = hairline polygon, creator = dashed rect), not two systems.
- **Layer toggle, not dead tabs.** Replace Image|Annotations (`:769-782`) with a **regions on/off + density** control (the modal's `showAnnotations` idea, `BoundingBoxEditor:279`, but as a calm layer switch). Default: image clean, regions revealed on hover/enter.

**Non-messy reveal of many parts** (load-bearing — Fashionpedia yields dozens):
1. **Progressive coarse→fine.** Anchors first, fine parts on demand — the data model already separates `depth 0/1` (`:79-80`) and the API already has `coarse_only` (`RegionDetectorModal:166`). Show anchors calm; **"reveal more" expands fine parts / triggers on-tap SAM2** (Track B's lazy reveal) rather than dumping all at once.
2. **Focus-one-dims-others.** Already present (`is-sel` class + `labelVisible` shows labels only for anchors/prioritised/selected, `:88`). Generalize: selecting a part **dims all others** (opacity on non-selected shapes), so 40 parts never scream at once. This is the core "without mess" mechanic.
3. **Category / attribute filters.** New, needed for Fashionpedia's volume: chips over the parts panel filter by `category` (coarse) and `attributes[]` (fine). Labels stay hidden until filtered/hovered/selected.
4. **Parts panel synced to shapes.** The modal's grouped list (`:181-194`, `Row` `:247`) is exactly this — anchor ▸ indented fine, ★ prioritise, • has-note dot. Hover row ↔ highlight shape (bi-directional). Keep it; it's the antidote to on-image clutter (read the list, not 40 overlapping boxes).
5. **Labels on demand.** Never all labels at once (today `labelVisible` already gates this `:88`). Anchor labels faint; fine labels only on hover/select/filter.

---

## 3. Pick → comment → remember (the dynamic loop)

**The loop already exists in the modal — make it live and persistent.** Current flow (`RegionDetectorModal`): select a part (`setSelectedId`) → editor shows label/category/material/description → ★ prioritise (`togglePriority:54`) → intensity slider (`:212`) → "how does X affect you?" note (`:216-221`) → **Save anatomy** POSTs the whole array to `region-annotations` (`:63-66`).

Track D's deltas:
- **Live, not modal-gated.** The selected-part editor (`:196-222`) becomes a panel *in* the Visual pane — pick a shape on the live image, comment inline, no modal round-trip.
- **Remembered + shows saved state on return.** On reload, `post.region_annotations` already carries `prioritised/weight/user_note` (loaded at `PostDetailPage:115-118` for local_context; regions arrive on `post`). Surface saved state visibly: prioritised parts keep the ★ + a filled shape tint; parts with a note show the • dot (`:260`) **on the image too**, not just the list. Returning, you *see* which parts you've already spoken to.
- **Creator marks join the same loop.** Drawing a manual rect creates an `actor="creator"` region (normalized box — **fixes the pixel-drift bug** Track A flagged, now reachable since Lane 2 made the pane resizable) → identical pick→comment→remember. No separate "tag name" flow (retire `BoundingBoxEditor`'s name-the-box modal `:386-399`); the "label" is just the part's label field.
- **Save cadence.** Today it's a big "Save anatomy" button (`:238`). For a *live* pane, prefer autosave-on-blur per edited region via the same `region-annotations` endpoint (Track A locked the full-array save; per-region upsert is the noted later optimization). Flag as Q3 — full-array save on a live surface may want debouncing.

**The ladder (Track F design-source):** this deep loop's shallow rung is **one tap = prioritise** (no note, no slider). Keep prioritise a single tap (it already is, `togglePriority`) so the consumer variant = "tap parts you love" with the note/intensity hidden. The deep surface *contains* the lite one — Track F strips, doesn't rebuild.

---

## 4. Where Aletheia surfaces in the unified pane

**Retire the right-pane Unconceal tab (`PostDetailPage:838-843, 1060-1140`); Aletheia moves into the Visual pane as a calm reading strip below the image**, because Track C tied each lens to `region_ids` — the reading is only powerful *next to the parts it references*.

- **Reading strip (image-global reading).** The fired lenses (Track C's context-triggered set) render as a low, calm strip under the image (reuse the tokenized `uncon-aletheia` styling `:1088-1116`, not a separate tab). **Tapping a lens highlights its `region_ids`** on the SVG — the reading *points at the image*. Atmosphere/mood lives here as a lens (image-global, Track B/C lock), never as a region.
- **Per-region lens hint.** When a part is selected, if a lens references it (`region_ids` includes it), show that lens line in the part editor — "Drape reads this as…" — the felt-reading exactly where you comment. This is the reading↔mark co-location the split currently prevents.
- **Commentary.** The curator's own unconcealment (`commentary`, `saveLocalContext:610`) becomes a field in/under the reading strip — still saved to `local_context`, just no longer a distant tab.
- **Écart = this pane's reading act.** Per Track C, Écart is the pause Darshan opens; structurally that's *this surface* — image + reading + your marks in one calm frame. The feed-hook (Track F) is the same strip, stripped to one lens + one fork.
- **Right pane reclaims a tab.** Removing Unconceal leaves Story | Highlights (`:823-836`) — cleaner, and the reading is where it belongs. (Coordinate the tab removal with the Drishya thread — §6.)

---

## 5. Premium-enabling structure + the kill-list

The pane should feel sophisticated through **structure**, not decoration (surface polish flagged for later; get structure right now). The good news: **`RegionDetectorModal.css` already embodies the target grammar** — tokens, hairlines, pill radii, one accent. The work is mostly **deletion**, concentrated in `BoundingBoxEditor`.

**KILL-LIST (all in `BoundingBoxEditor`, grounded):**
| Kill | Where | Why |
|---|---|---|
| **Glassmorphism** (`backdrop-filter: blur()`) | `BoundingBoxEditor.css:19, 247, 372-375` (`.glassmorphism` on tag-form `:387` + tags-list `:403`) | frosted-glass islands violate the flat token grammar; nothing else in the app blurs |
| **Neon gradients** | `.css:77, 89, 132, 174, 187, 420, 462, 477` (purple `rgba(168,85,247)`, green `rgba(0,255,100)`, blue `rgba(59,130,246)`) | hardcoded neon, off the `--accent` palette; screams against the calm surface |
| **Neon glow shadows** | `.css:93, 161, 368, 401, 426` (`box-shadow: 0 0 20px rgba(...)`) | glow ≠ the app's `--shadow-*` tokens |
| **Emoji islands** | JSX stats bar 🏷️📊 (`:258-264`), ✂️ View Crops (`:271-277`), 👁️ toggle (`:283`), ✏️🗑️ corner badges (`:335, 342`), × delete (`:412`) | emoji as UI chrome; replace with lucide icons (the app's icon system, already used in the modal: `Star/Scan/Save/Sparkles`) |
| **Pixel-space boxes** | JSX `:316-319` (`${box.x}px`), resize in px (`:128-205`) | Track A retires pixel `bounding_box_tags`; regions are normalized. Drop the whole pixel-resize apparatus; reuse the SVG's normalized handles |
| **The `/crops` escape hatch** | `View Crops` link `:270-277` | separate page; regions are now in-pane. Confirm it's dead (Q5) |

**KEEP / adopt as the grammar (from the modal):**
- Border grammar respected: **only** the Visual/Content panes, the `panel-header` hairline, and the focused editing surface earn a border (the modal already does this — `.rd-note:focus` accent ring `:128`, hairline rows `:106`). The overlay shapes use `vectorEffect="non-scaling-stroke"` (`:116,121`) — crisp at any zoom, the premium tell.
- **True polygon shapes** (`:112-116`) over rectangles wherever `polygon` exists — the single biggest "premium" structural win (real segment outlines, not approximations).
- **Calm layering + motion (structure, polish later):** focus-dims-others (opacity transitions), reading-strip reveal, shape-highlight on row-hover. Flag the actual easing/timing as a Surface pass; get the *layers and states* right now.

**Net:** the unified pane inherits the modal's clean token CSS; `BoundingBoxEditor.css` (all the neon/glass) is largely deleted, not ported.

---

## 6. Shared-file build-coordination note (flag for Adarsh)

**`PostDetailPage.jsx` is edited by both this initiative and the Drishya UI thread.** Track D's *research* touched nothing. Track D's **build will make structural edits** to it:
- remove the left-pane Image/Annotations dead tabs (`:769-782`) → layer control;
- swap `BoundingBoxEditor` mount (`:787-789`) for the unified region surface;
- remove the right-pane **Unconceal tab** (`:838-843`) and its whole branch (`:1060-1140`);
- un-modal `RegionDetectorModal` (`:1198`) into the pane;
- keep the divider/SSOT (`:793-818`) and edit-narrow behavior (Lane 2) intact.

These overlap the exact regions Lanes 1/2/3 touch (panel headers, tabs, pane structure). **Serialize the build:** (a) `git pull` immediately before starting; (b) confirm no open Drishya PR is mid-flight on `PostDetailPage.jsx`; (c) land Track D's build as its own commit(s) after the current Drishya lane merges; (d) because it removes the Unconceal tab and rebuilds the Visual pane, it should **not** run concurrently with a Drishya lane editing the same file. Recommend Adarsh **scheduses D's build in a dedicated slot** on `feat/frontend` with the UI thread paused on that file.

---

## Questions for Adarsh

1. **Un-modal vs keep-modal.** I recommend promoting `RegionDetectorModal`'s body into the **live** Visual pane (no modal) — it's the whole "dynamic surface" premise. Any reason to keep detection in a modal (e.g. focus/perf on the detect call)? I lean fully in-pane, with detection as an async in-pane action.
2. **Manual marks — still needed?** With Fashionpedia + SAM2-on-tap producing most regions, is the freehand **draw-a-rect** creator mark still worth keeping (as `actor="creator"`), or does "creator marking" become **tap-an-auto-region + comment** only (no freehand)? I lean *keep a lightweight draw* for what detection misses, but it's the biggest scope lever.
3. **Save cadence on a live pane.** Full-array `region-annotations` save (Track A lock) vs autosave-on-blur per region (needs debouncing) vs an explicit Save. On a live surface I lean **autosave-on-blur, debounced**, but confirm — it changes the endpoint usage pattern.
4. **Reading strip placement.** Aletheia as a strip **under the image** (my rec — reading beside the marks) vs a collapsible side panel vs a toggle. Under-image keeps reading↔region co-located; a side panel fits more lenses. Which?
5. **`/crops` page + `bounding_box_tags` UI.** Confirm the `View Crops` route (`BoundingBoxEditor:270-277`) and the entire pixel manual system are retired (Track A retires the field). Anything downstream still reading crops?
6. **Build serialization (§6).** How do you want to sequence D's build against the Drishya thread on `PostDetailPage.jsx`? I recommend a dedicated slot with the UI thread paused on that file. Confirm the mechanism (pause / branch / merge-order).
7. **Consumer variant scope now?** The deep pane is the design source for Track F's one-tap surface. Do you want Track D's build to *also* extract the lite variant, or just keep the deep surface clean enough that F extracts it later? I lean the latter (don't build F's UI inside D).

*Research + plan only — no app code touched. The core insight: the premium unified pane is mostly **un-modalling the already-clean auto-anatomy surface and deleting the neon manual editor**, not new construction. The one hard dependency is Track A's `region_annotations`-as-one-model (creator marks included); the reading↔region link comes from Track C. Build touches the shared `PostDetailPage.jsx` → must be serialized (§6).*
