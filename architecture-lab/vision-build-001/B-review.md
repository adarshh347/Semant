# Increment B — vertical-slice review

**Date:** 2026-07-19 · **Branch:** `feat/vision-differential` · **PR:** #51 · **Mode:**
review only — no domain models added, no code changed. Scope: is B a complete vertical
slice, is B4 reachable outside the lab, what is the smallest integration into the real
Visual/Differential workflow, and do the six commits carry regressions or merge conflicts.

## 1. Vertical slice — functionally complete, but the entry point is lab-only

The slice **works end to end**: detect (B2 YOLO masks) → refine (B3 SAM2 point/box/mask)
→ preview → confirm (new `geometry_rev`, non-destructive) → persist → reload → recall
(renders registered on other surfaces). Backend 85 tests, frontend 68 tests, browser-
verified at two viewports. So the *capability* is a complete slice.

**But the product wiring is not.** The refinement UI is reachable **only** at the lab
route:

- `RefineSurface` is imported by exactly one file — `pages/RefineLab.jsx`.
- `RefineLab` is mounted at exactly one route — `main.jsx:48` `lab/refine/:postId`.
- No navigation, button, or tool in the real workflow (PostDetailPage / RegionSurface /
  DifferentialWorkspace) links to it. Grep confirms zero other references.

**Verdict:** B4 **is** currently confined to a laboratory route. The slice is complete as
a proof; it is not yet available where a curator actually works. That gap is the one
substantive thing to close before (or right after) merge — and it is small (§3).

## 2. The real workflow (where refinement belongs)

`PostDetailPage` (`components/PostDetailPage.jsx`) holds `workspaceMode: 'chiasm' |
'differential'`:
- **chiasm** → `RegionSurface` (line 1061), the Visual pane: auto-detection, selection,
  Dissect, and it already renders masks via `RegionOverlay`.
- **differential** → `DifferentialWorkspace` (line 889), the percept-construction
  workspace with the L5 tool rail (Select·Brush·Trace·Collect·Connect·Frame) and
  `GroundLayers` (which already renders multi-ring masks, evenodd).

Both surfaces already own **exactly** the machinery a refine mode needs:
- the shared stage-geometry contract (`useNaturalSize` / `useStageGeometry` / natural
  viewBox), so coordinate registration is free;
- per-tool pointer handling with `e.preventDefault()` for drag-prevention —
  `DifferentialWorkspace.onStagePointerDown` already does this for brush/trace
  (`differential/DifferentialWorkspace.jsx:162`), the same pattern B4 needed;
- mask rendering (RegionOverlay / GroundLayers) and a region-selection model;
- and B4's `/refine-region/preview|confirm|unload` endpoints already exist.

## 3. Smallest integration (recommended)

**No new surface, no new route, no new endpoints.** The refine loop that
`RefineSurface.jsx` already implements is transplanted onto an existing stage.

**Step A — extract the loop into a hook** (`useMaskRefine(postId, baseRegion)`), lifted
verbatim from `RefineSurface`: it owns `points/box/proposal/status`, the debounced
`preview` call, `confirm`, `cancel`, and the normalized pointer→prompt handlers. This
de-duplicates: both `RefineLab` (keep as the harness) and the product surface consume it.

**Step B — mount it on the Differential stage as a `refine` tool** (the most idiomatic
home — it is the percept workspace):
- add one `TOOLS` entry (`DifferentialWorkspace.jsx:25`), e.g. `{ key:'refine',
  label:'Refine', hint:'Tighten a part to an exact mask — click or drag' }`;
- in `onStagePointerDown/Move/Up`, add a `tool === 'refine'` branch (mirroring the
  existing `brush`/`trace` branches, incl. the `e.preventDefault()` on line 162) that
  feeds the hook a point (click) or box (drag);
- render `proposal.polygons` through the existing `GroundLayers`/`RegionOverlay` path
  (already supports evenodd masks — no new renderer);
- on confirm, POST `/refine-region/confirm` and refresh the region into the store (new
  `geometry_rev`); Select→Refine is the natural flow (pick a region, tighten its mask).

**Alternative (equally small)**: surface it in `RegionSurface` — when a region is
selected, a "Refine mask" affordance enters the same hook-driven mode. RegionSurface
already has selection + `RegionOverlay` masks + the detect action; refinement sits beside
detection where auto-masks are born.

**Effort:** one hook extraction + one tool branch (~a focused change), reusing the stage,
overlay, drag-prevention and endpoints already shipped. This is a UI-wiring increment, not
a rebuild — and it needs **no domain models**, so it fits the current constraint.

## 4. Commit inspection — regressions & conflicts

**Merge conflicts:** none. `git merge-tree --write-tree origin/main HEAD` produces a clean
tree (0 conflicts); branch is 0 behind / 11 ahead of main.

**Regression surface** — six shared files carry the cross-cutting edits; each is additive
or guarded:

| commit | shared edit | regression risk | assessment |
|---|---|---|---|
| A `ebf535b` | `schemas/post.py` +5 fields; RegionOverlay/GroundLayers mask branch | low | new fields are `Optional`/defaulted, `extra="allow"`; the mask `<path>` branch runs **only** when `region.polygons` exists — legacy box/single-polygon regions fall through to the unchanged rect/polygon path. |
| A `ebf535b` | `save_region_annotations` canonicalize | low | box-only regions only get a `geometry_provenance` stamp; geometry unchanged; curator fields untouched. |
| B2 `b0d4026` | `segmentation_service.segment_image_bytes` rewrite (-33/+~20) | low–moderate | now derives all geometry from native masks and returns `[]` when `r.masks is None`. YOLO-**seg** always emits masks, so no practical change; box/polygon/label fields preserved for legacy consumers. **The one behavioral change to note:** a hypothetical maskless YOLO result now yields no regions (previously box-only) — not reachable with the seg checkpoint. |
| B2 `b0d4026` | `detect_regions` clip guard + canonicalize pass | low | guard `if not f.get("mask_rle")` only *narrows* when clipping runs; fine VLM parts never carry masks, so existing behavior is preserved; the guard prevents future mask clipping. |
| B4 `525145b` | `posts.py` refine endpoints + `BaseModel` import + image cache | low | purely additive routes; the image cache is a single-entry dict scoped to refine. |
| B4 `525145b` | `main.jsx` +1 route | none | additive. |

Backend **85** and frontend **68** tests pass on the merged state. Heavy ML deps remain
lazy-imported/optional, so the slim API deploy is unaffected (orchestrator imports are
torch-free; verified).

**Two non-blocking observations (not regressions):**
- Detector inconsistency: YOLO anchors now carry `mask_rle`; the fashion (SegFormer-
  clothes) path still emits `polygon` only. Both render correctly (mask branch vs legacy
  polygon). Bringing the fashion segmenter to `mask_rle` is a natural follow-up, not a fix.
- The refiner holds ~812 MiB VRAM while resident; auto-`/refine-region/unload` on leaving
  refine mode should ride along with the §3 integration.

## Recommendation
Merge is safe (clean, green, additive). The one gap to close for a true product slice is
§3 — a small, model-free UI-wiring increment that puts refinement on the Differential (or
RegionSurface) stage via a `useMaskRefine` hook. Everything it needs already exists on
those surfaces.
