# Track D — Unified annotation UX (premium Visual pane) (research + plan only)

**Read first:** `00-brief.md`, `07-purpose-lens.md`. **Do not edit code.** Write `responses/track-D-frontend.findings.md`.

## Mission
Merge the two annotation UIs (manual Visual-pane + Unconceal anatomy) into **one premium, dynamic Visual pane**. When segmentation returns many parts, they must NOT look messy — and beyond non-messy, the surface must be **dynamic**: each part pickable → commentable → remembered.

## Read
- `frontend/src/components/BoundingBoxEditor.jsx` + `.css` (manual boxes, resize, tags list, glassmorphism/emoji islands).
- `frontend/src/components/RegionDetectorModal.jsx` (auto anatomy: detect, chips, prioritise, notes).
- Unconceal branch of `PostDetailPage.jsx` (anatomy + aletheia + commentary).
- Lane 3 + Lane 6 findings if present in `responses/`.

## Answer
1. **One surface:** how manual marks + auto segments coexist on the live image (both are "regions"; polygons for auto, rects for manual). Retire the separate Unconceal tab — where do Aletheia + commentary go in the unified pane?
2. **Non-messy reveal of many parts:** progressive/coarse→fine, category filters, focus-one-dims-others, a side "parts panel" list synced with on-image shapes, hover/pick highlighting. Propose the interaction model.
3. **Dynamic loop:** pick a part → comment ("how it affects me") → it's remembered (persist per Track A model) → shows its saved state on return. Design the pick→comment→remember cycle.
4. **Premium feel (structure that enables it):** since the Visual pane is "solely the visual thing," what structural choices let it feel sophisticated (true polygon shapes, calm layering, motion) — flag surface for later but get the structure right now. Kill the emoji/glassmorphism islands.
5. **Where Aletheia surfaces** in the unified pane (a reading panel? per-region lens hints?).

## Output contract → `responses/track-D-frontend.findings.md`
Unified-surface structure · many-parts reveal model · pick→comment→remember flow · Aletheia placement · premium-enabling structure + kill-list · questions for Adarsh.
