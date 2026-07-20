# Differential v1 — build spec (repo-grounded)

**To:** Claude Code — the Differential build session. **Mode:** build, incremental, gated.
**Companion:** the full "Build Differential v1" product spec (pasted in chat / provided by Adarsh). This document is its *repo-grounded half*: the audit is already done, the integration points are named, the architectural decisions are made. Where this doc and generic reasoning disagree, this doc wins — it was written against the code on disk.

## What is being built

**Differential** is the dedicated percept-construction workspace (the user-facing successor to "Field" for authoring). The core model:

```
Ground  = how visual evidence occupies the image
Percept = a durable act of noticing, grounded in one or more Grounds
Mention = a textual use of that Percept
Recall  = the visual re-performance of the Percept from its Mention

image → Ground → Percept → Mention → recall on the image
```

The circulation — not annotation — is the product. v1 must close the full loop AND ship working first versions of all seven perceptual operations: **Select · Brush · Trace (with Boundary sub-mode) · Collect · Connect · Frame** → Region, Soft Field, Path, Boundary, Constellation, Relation, Frame.

## Locked decisions (do not re-litigate)

1. **Naming:** user-facing workspace = **Differential**. New components/comments say Differential. Internal legacy filenames (RegionSurface, regionStore, "Field" in old comments) may stay where renaming is risky — leave a `LEGACY-NAMES` note in the implementation report. No repo-wide string replace.
2. **Differential is a full-workspace mode inside `PostDetailPage`, NOT a new route.** Reason found in code: unsaved Manuscript content lives in `PostDetailPage` component state (`editedBlocks`); a route change unmounts it and silently loses writing. A `workspaceMode: 'chiasm' | 'differential'` state that swaps the layout shell (Differential = image-dominant, Manuscript hidden/parked but state intact) preserves everything and gives a reliable return. Chiasm's normal state stays quiet — no permanent six-tool rail there; it gets an obvious "Open Differential" entry + existing overlays/recall/Mention behavior.
3. **Region is preserved, not absorbed.** Grounds reference Regions via an adapter (`{ ground_type:'region', region_id }`) — no duplication of geometry, no destructive migration of `region_annotations`. Existing Region ids, `Region.block_id`, `data-region-ids` chips, detection, persona rollup, embeddings all keep working untouched.
4. **Provenance:** `actor = auto | creator | audience`, `detector = yolo | fashionpedia | sam2 | vision | null`. A detector is not an actor. New creator-made Grounds: `actor:'creator', detector:null`.
5. **Percept↔Ground↔Mention cardinality is many-to-many-to-many.** The existing `ensurePercept` one-creator-percept-per-region rule serves the old attention-percepts (`pct_actor_regionId`) — keep it for back-compat, but **expression Percepts are a new kind** (`pctx_…` ids, `expression` + `ground_ids[]`), with no per-ground uniqueness. Existing `perceptMentions.test.js` must keep passing.
6. **Spatial primitives vs compositions:** Region/Soft Field/Path/Boundary/Frame are spatial Ground records; Constellation and Relation are compositional records over member Ground ids (+ optional raw points for Constellation). Don't force a dishonest flat geometry union.
7. **No SAM, no OpenSeadragon, no W3C interop, no Atlas/Codex in this build** (design extension points only). No find-similar requirement — manual Collect must work standalone; embeddings wiring is optional if trivially clean.
8. **Not an interruptive composer after every gesture.** Support both rhythms: immediate ("What do you notice?" after a commit) and accumulative (a Ground tray / current-collection set; compose one Percept from several Grounds later). Cancel never destroys deliberately created Grounds.

## Integration map (audit complete — verify quickly, then build)

**Frontend (`frontend/`, React 19 + Vite, no TS):**

- `src/components/PostDetailPage.jsx` — Chiasm shell. Owns: `react-resizable-panels` split (`autoSaveId="chiasm-split"`), `useRegionState` store instance + `RegionStoreContext.Provider`, RefPicker wiring (`onRefTrigger`/`insertRef`), chip↔region DOM event listeners (`semant:region-hover`, `semant:region-focus`), `chipClickRef` delegated click handler, `manuscriptRef` imperative handle, `writeAboutRegion`, editedBlocks/save. **This is where `workspaceMode` lives and where Mention-focus→recall routing lands.**
- `src/components/RegionSurface.jsx` (+`.css`) — current image pane. The gold in it: the **coordinate contract** — stage with `aspect-ratio: var(--rs-ar)`, `object-fit: contain` image, `measure()` computing the letterboxed content box via ResizeObserver, SVG overlay with natural-pixel `viewBox` + `xMidYMid meet`. **Extract this contract into a shared hook/helper** (e.g. `differential/useStageGeometry.js` + explicit pointer→normalized converters) so the Differential stage and Chiasm pane share it, and later deep-zoom only swaps the container. Keep RegionSurface working in Chiasm.
- `src/components/RegionOverlay.jsx` — the one place region shapes draw (polygons/rects, `vector-effect: non-scaling-stroke`, dim/lit via `focusId`). Reuse inside Differential's stage for Region Grounds; extend focus to accept Sets.
- `src/state/regionStore.js` (`useRegionState`) — shared store: regions, aletheia, selection/hover/`focusIds`, client Percepts+Mentions, debounced persist (whole-array POST). Hydration keyed on `post.id` (`loadedFor` guard). **Extend, don't fork:** add `grounds`, `percepts` (expression kind), ground CRUD, `recall` state (`playRecall/clearRecall`), ground-aware focus.
- `src/state/perceptMentions.js` + `.test.js` — pure helpers, locked shapes, `mentionsFromBlocks` reconstruction. Add: `makeExpressionPercept({expression, ground_ids, properties, actor})`, `isExpressionPercept`, ground-aware queries. All existing tests must stay green.
- `src/components/blocknote/Manuscript.jsx` — `refSlashItems()` (add a `Percept` item → `onRefTrigger('percept')`), `insertRegionChip` imperative handle (works for percept chips as-is: `refKind:'percept'`, `regionIds` can carry ground ids, `perceptId` prop exists).
- `src/components/blocknote/regionRefInline.jsx` — chip already emits `data-percept-id` in markup and survives HTML round-trip. **Change needed:** the `emit()` CustomEvents only carry `regionIds`; include `perceptId` so a focused percept-Mention can trigger recall. Keep back-compat attrs.
- `src/components/RefPicker.jsx` — add `kind === 'percept'`: list expression Percepts (expression as title, ground-type glyphs as sub), `percepts` prop.
- `src/lib/cloudinary.js` — fractional `c_crop` helper already exists ("lifted percept crop") — use for Mention hover previews (bbox-union of a Percept's Grounds).
- Design system: `src/index.css` tokens (`--accent` plum, `--surface-*`, `--line`), RegionSurface.css token grammar ("hairlines, one accent, no glow/neon; borders only where earned"), container queries (`container-type: inline-size`), **gotcha:** global `button` padding in index.css squeezes icon buttons — RegionSurface neutralizes locally; do the same in Differential css. `motion` v12, `@floating-ui/dom`, `react-hotkeys-hook`, lucide are installed — no new runtime deps except (optionally) `perfect-freehand`; prefer vendoring a small taper helper if installs are awkward.

**Backend (`backend/`, FastAPI + Mongo):**

- `schemas/post.py` — `Region` (pydantic, `extra="allow"`, **`box` required**), `Post`, `PostUpdate` (currently only text_blocks/general_tags/highlights). `RegionAnnotationsRequest`.
- `routers/posts.py` — `post_helper()` serializer (~line 68; **new fields must be added here or the frontend never sees them**), `PATCH /{post_id}` uses `exclude_unset` (adding optional fields to `PostUpdate` is sufficient), `POST /{post_id}/region-annotations` (validates + `$set`s whole array, persona rollup, background embeddings), `POST /{post_id}/detect-regions`.

## Persistence decision (the important one)

**Store Grounds and Percepts in NEW post fields, not inside `region_annotations`:**

```python
# schemas/post.py
class Post(...):      grounds: Optional[List[dict]] = None
                      percepts: Optional[List[dict]] = None
class PostUpdate(...): grounds: Optional[List[dict]] = None
                       percepts: Optional[List[dict]] = None
# routers/posts.py post_helper(): add both keys
```

Why not piggyback on `region_annotations` (superficially tempting since `extra="allow"`):
1. `POST /detect-regions` **wholesale-replaces** `region_annotations` (`$set` at ~line 713) — every re-dissect would silently wipe Grounds.
2. Region machinery iterates that array (persona rollup, `_embed_marked_regions`, enrichment, anatomy catalog) — Grounds would leak into all of it.
3. The product spec explicitly forbids mutating Region semantics into a speculative union.

Mongo is schemaless; `List[dict]` keeps the backend change to ~6 lines with no migration. Save path: `PATCH /{post_id}` with `{grounds, percepts}` (debounced, same pattern as the store's existing persist). Ground records referencing a Region store only `region_id`; if a re-dissect replaces that Region id, the Ground degrades gracefully (renders nothing, listed as "detached evidence") — cover with a test.

**Ground record (normalized coords, natural-image space, top-left origin):**

```js
{ id:'gnd_…', ground_type:'field'|'path'|'boundary'|'constellation'|'relation'|'frame'|'region',
  actor:'creator', detector:null, label:'', note:'', created_at,
  // per type:
  region_id,                                        // region adapter
  strokes:[{points:[[x,y,p?]…], radius, strength, op:'add'|'sub'}],  // field
  points:[[x,y,p?]…], arrowhead:true,               // path
  points:[[x,y]…], band_width:0..1,                 // boundary
  member_ids:[…], points:[{x,y}…],                  // constellation
  member_ids:[…], relation_label:'' ,               // relation (free text, untyped allowed)
  whole:true, evidence_ids:[…] }                    // frame
```

**Expression Percept:** `{ id:'pctx_…', expression, ground_ids:[…], properties:[…], actor:'creator', created_at }` — properties optional (light, colour, material, movement, composition, attention, atmosphere, repetition, contrast). Mentions keep the existing shape; a percept-Mention sets `perceptId` and `form:'inline'`, chip markup already carries `data-percept-id`.

## Rendering (shared, reused by Differential AND Chiasm recall)

Two layers slaved to the shared stage-geometry contract, built as reusable components (`differential/GroundLayers` or similar), consumed by both surfaces:

- **SVG layer:** Region shapes (reuse RegionOverlay), Path (tapered outline via a small vendored freehand-taper helper + end chevron; travel animation = centerline `pathLength`/`stroke-dashoffset`), Boundary (feathered band: wide low-opacity stroke + blur filter + faint centerline; shimmer = opacity/width keyframes), Constellation marks (quiet halos), Relation emphasis (members co-illuminate; connector faint, hidden until focus), Frame (delicate inset double hairline, no full-image mask), hit targets.
- **Canvas layer:** Soft Field only — strokes stamped as radial-gradient brush passes into an alpha buffer, `destination-out` for subtract, tinted with the single `--accent`, drawn at low alpha. No rainbow. Bloom recall = radius/alpha ramp on redraw.
- **Focus treatment:** per the spec, skip fragile cross-layer SVG masking in v1 — recede the image gently (CSS filter/opacity on the `<img>`), render active Grounds above. Simpler and calmer; masking later.
- Opacity discipline as CSS tokens: fills ≤0.12, washes ≤0.35, veil ≤0.2. `O` (hold) = untouched original; `Esc` = clear recall/draft. `prefers-reduced-motion` → skip to composed final state everywhere.

## Recall (mandatory, reusable abstraction)

One module (e.g. `differential/recall.js`): `buildRecallScript(percept, resolveGround)` → staged timeline data; a hook/player applies CSS classes + canvas progress. Signatures: Region fade/illuminate · Field bloom · Path travel · Boundary shimmer · Constellation pulse together/sequential · Relation A, then B, then unite · Frame whole-image shift then evidence. Stages: recede → primary → supporting (stagger) → relation → expression caption. Short and legible, not theatrical. Preview in Differential (per-Percept ▶), full replay from Mention focus in Chiasm, quiet final state, cancel restores calm.

## Increments and gates (from the product spec, kept)

- **A — workspace + architecture:** `workspaceMode` in PostDetailPage; Differential shell (compact top bar: back to Chiasm, identity, untouched-image, save state; image-dominant stage; compact tool surface; contextual inspector); shared stage-geometry extraction; existing Regions render as Grounds; backend fields + persist round-trip. *Gate: Chiasm unchanged & green; enter/leave Differential loses no Manuscript/selection state.*
- **B — one full loop with Soft Field:** Brush (size `[`/`]`, additive, ⌥-subtract, pointer pressure, editable before commit) → Ground → composer → Percept persists → reload survives → `/percept` Mention inserted → Mention focus replays the light in Chiasm. *Gate: the circulation sentence works end-to-end.*
- **C — spatial vocabulary:** Path, Boundary (Trace sub-mode, adjustable band), Frame (one action, whole:true, attach evidence), Region select/multi-select into Percepts, unified Ground inspector, recall for each.
- **D — compositional vocabulary:** Collect (members = grounds and/or points, confirm/remove), Connect (members + optional free-text relation label), accumulative tray → multi-Ground Percepts, recall sequencing.
- **E — harden:** undo/cancel per gesture, keyboard + focus rings, responsive (container queries), reduced motion, visual refinement per token grammar, compatibility tests, screenshots.

Do not stop after B. B is the proof; v1 is the vocabulary.

## Verification

- **Tests (vitest, `npm test` in `frontend/`):** extend `perceptMentions.test.js` (expression percepts: many-per-ground, many-grounds-per-percept, many-mentions-per-percept); new `grounds.test.js` (each type round-trips serialize→hydrate; constellation/relation membership survives; region-adapter resolves; deleted member degrades gracefully); converter test still guarantees `data-*` chip survival.
- **Visual QA:** run the app; use the repo's `.agents/skills/playwright-cli` skill for screenshots. Capture the spec's checklist (Chiasm resting, Differential resting, each tool active, multi-Ground composition, each recall, Mention focus, narrow viewport, reduced motion). Check pointer mapping after pane resize (the letterbox math is the usual suspect).
- **Protocol:** `architecture-lab/workflow-protocol.md` applies — conventional commits, stop after each increment for review, handoff notes.

## Report (final deliverable)

Changed files; decisions taken vs this spec; compatibility approach; working vs v1-quality vs known limitations; exact test output; screenshot paths; LEGACY-NAMES list; next expansion point per Ground type (SAM for Select, edge assist for Boundary, similarity for Collect, etc.).
