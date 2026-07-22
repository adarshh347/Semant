# CIRCUIT-001 P2E-A — Visual Mark Persistence + Provenance Reconciliation + Contract v2

**Lane A. Additive backend + frontend. No migration, no collection change. No production data
mutated. No model call. No new dependency. No renderer.** Implements contract v2 (§7), committed
first at `2cc93e0` so Lane B2 could pull it.

**The one sentence:** a committed visual_mark now survives reload — a brush no longer evaporates —
the quarantine stays session-truth (a suggestion never touches the database), provenance has a
single authored home (the mark) with grounds/regions carrying only derived bridge fields, and an
accepted SAM mask is still visibly model-assisted after a reload.

---

## 1. Contract v2 — the five decisions

Committed at **`2cc93e0`** ahead of implementation. §§1–6 stay the frozen v1 baseline Lane B2 read
against at `3aa4b3e`; **§7 is the amendment layer and takes precedence.**

| # | decision | outcome |
|---|---|---|
| A | anchors `detached_from_ref` | **recorded** (settled upstream) — drag keeps the ref, freezes position, sets the flag |
| B | erase is geometry | **recorded** — `strokes[].op: add\|sub` is canonical mark data; compositing is a renderer detail |
| **C** | region-mask family | **`region_mask` added.** A segmented extent is not a perceptual field; `raster_mask` + `mask_ref` only, never inline pixels; role **optional**; explicit later conversion `region_mask → brush_field` mints a new perceptual mark |
| **D** | boundary | **stays `frame_mark` role `boundary`.** No new family without a distinct invariant |
| **E** | provenance home | **`visual_mark.provenance` is the ONLY authored provenance.** `mark_source`/`instrument_role`/`refined_from` on grounds/regions are DERIVED bridge fields, written only by helpers that read the mark; a drift test pins they cannot disagree |

## 2. Durable marks — `post.visual_marks`

Follows the grounds/percepts pattern exactly.

- **`backend/schemas/post.py`** — additive `visual_marks: Optional[List[dict]]` on `Post` and
  `PostUpdate`; PATCH `exclude_unset` verified clean (a payload of only `visual_marks` round-trips
  to exactly that).
- **`backend/routers/posts.py`** — `post_helper` returns `visual_marks` so the response model
  carries it. **No change to the PATCH route** — it already persists any `PostUpdate` field.
- **`frontend/src/state/regionStore.js`** — hydrates `post.visual_marks` beside grounds/percepts;
  the debounced meta-save PATCHes them.

**Persistence policy (contract v2 §7.3), enforced twice:**
- on **write**, `persistMeta` sends `persistableMarks(...)` — only `committed`/`superseded`;
- on **read**, hydration `normalizeMark`s each stored mark and keeps only persisted statuses.

So a suggestion cannot reach the database from either direction, and a stored mark that no longer
validates is **dropped on hydrate, not trusted** — the same fail-closed discipline as on the way
in. `superseded` persists because recoverability is the whole point of the status (P1F/P1G).

## 3. Store API surface (for Lane B2's tools)

Exact signatures, all on the object `useRegionState` returns:

```
addVisualMark(mark, { save = true }) → mark | null
    // adds/replaces by id; schedules a save ONLY when mark.status is persistable,
    // so a stream of drafts never thrashes the network.
updateVisualMark(id, patch, { save = true }) → mark | null
    // stamps updated_at; saves when the RESULT is persistable (a draft promoted to
    // committed writes; a committed mark superseded writes).
removeVisualMark(id, { save = true }) → void
    // saves the removal only if the removed mark was persisted.
visualMarksForGround(groundId) → mark[]      // marks whose linked_ground_ids include it
visualMarkById(id) → mark | null
visualMarks                                   // the live array
```

**The pattern Lane B2's tools follow at merge:** build the mark with `makeVisualMark`/
`regionMaskMark`/`actionToDraftMark`, `addVisualMark(mark, {save:false})` while it is a `draft`/
`staged`/`suggested`, then `updateVisualMark(id, {status:'committed'})` at the commit — that last
call is the one that persists.

## 4. Provenance reconciliation (decision E)

New helpers in `suggestionQuarantine.js` (the provenance home):

- `bridgeFieldsFromMark(mark)` → `{mark_id, mark_source, instrument_role, refined_from}`, derived
  purely from the mark.
- `reconcileBridgeFields(target, marks)` → the ground/region with its bridge fields rewritten from
  its most-recently-updated linked mark (a supersession becomes the truth); untouched when no mark
  links to it.
- `bridgeFieldsAgree(target, marks)` → the **drift check made runnable**. A test asserts it CATCHES
  a bridge field hand-authored to disagree with its mark — the exact §7.2-E violation — and passes
  when they agree or when there is no mark to disagree with.

This resolves P2D-A's flagged deviation (provenance lived in two places). The mark is the home; the
bridge fields are a convenience view, and they cannot lie.

## 5. SAM provenance round-trip (2c) — patched, no residue

The P2D-A report left cross-reload persistence as residue. **It is closed at the persistence
layer**, and without trusting the client:

- `RefineRequest` gains an additive optional `mark_id`.
- On confirm, the server **derives** the region's bridge fields from `base_id` — the same fact the
  frontend mark derives from — and persists them into `region_annotations`:
  `mark_source = "model_refined" if base_id else "user_confirmed"`, `refined_from = base_id`,
  `mark_id` echoed if supplied.
- These ride the existing `region_annotations` write, so an accepted model-assisted mask is
  **visibly model-assisted after reload**: the region carries `model_refined`/`user_confirmed`
  + lineage, and the bridge helpers surface it.

**No change to segmentation or refine behaviour.** The refiner suite (`test_vision_b3_refiner.py`)
stays green. Because the server derives `mark_source` itself, a stale client value can never make
the region disagree with reality — decision E holds across the network boundary.

## 6. `region_mask` (decision C), in `visualMarks.js`

- Sixth `MARK_TYPES` entry; `REGION_MASK_ROLE_KEYS = [segment, part, material_extent, anchor_extent]`;
  `OPTIONAL_ROLE_TYPES = {region_mask}`.
- **Validation:** geometry must be `raster_mask` with a `mask_ref.region_id`; **inline `pixels`/
  `rle`/`polygons`/`strokes`/`points` are rejected**; role is optional but a non-null role must be
  in the vocabulary (a `brush_field` role like `light_field` is refused — a mask has not been
  *read* as light).
- **Citability:** the standard rule (committed + `user`/`user_confirmed` + geometry not
  `unresolved`). An accepted region IS citable evidence; a `model_refined` mask is not citable on
  its own (tightened ≠ confirmed).
- `regionMaskMark({regionId, geometryRev, source, status, derivedFrom, model})` helper — the
  constructor Lane B2's confirm path should call.

## 7. Tests + build

| | |
|---|---|
| new tests | **48** — `regionMask` 15, `provenanceBridge` 9, `visualMarksPersistence.dom` 6, plus the P2D-A "every role" test updated for the constrained region_mask geometry (and 18 more across the round-trip/bridge cases) |
| full frontend suite | **548 passing** (was 484 at P2D-A; delta includes Lane B2's in-flight suites) |
| production build | ✅ clean |
| backend | schema round-trip verified; `posts.py` parses; **targeted `pytest -k "refine or p1f" → 24 passed**; no broad suite run |
| lint | my files clean |

Round-trip coverage: PATCH→reload→hydrate preserves a committed mark, its lineage, and its
provenance; a suggestion is excluded from the PATCH body AND absent after reload AND never citable;
an invalid stored mark is dropped on hydrate; a promoted draft persists; the bridge-drift check
catches an independently-authored bridge field.

## 8. Production-mutation status

**None.** No `refine-region/confirm`, no PATCH, no `detect_regions` against a real post. All
persistence was exercised through a stubbed `fetch` (frontend) and Pydantic round-trips (backend).

## 9. Files changed

**Backend (additive):** `backend/schemas/post.py` (`visual_marks` on Post + PostUpdate) ·
`backend/routers/posts.py` (`post_helper` echo; `RefineRequest.mark_id`; confirm derives + persists
region bridge fields).

**Frontend:** `differential/visualMarks.js` (region_mask family, validators, `regionMaskMark`,
`persistableMarks`) · `differential/suggestionQuarantine.js` (bridge helpers + drift check) ·
`state/regionStore.js` (hydrate/persist marks; store API) · `differential/visualMarks.test.js`
(region_mask geometry in the every-role test).

**New tests:** `differential/regionMask.test.js` · `differential/provenanceBridge.test.js` ·
`state/visualMarksPersistence.dom.test.jsx`.

**Not touched (other lanes):** `DifferentialWorkspace.jsx`, `AttunementPanel.*`, `PostDetailPage.jsx`,
`markStaging.*` (Lane B2, dirty); `Manuscript.jsx`, `PassageInspector.*`, `orchestrationSession.js`
(manuscript lane). `GroundLayers.jsx`, `fieldCanvas.js`, `freehandTaper.js`, `package.json` — per
ownership rules.

## 10. What Lane B2 / P2F must know

1. **The confirm-path mark type should migrate to `region_mask`.** P2D-A's `confirmRefine` (in the
   DifferentialWorkspace surface Lane B2 owns) still builds a `brush_field + material_field` mark for
   the SAM mask. Swap it for `regionMaskMark({regionId, geometryRev, source, derivedFrom, model})`.
   **This is now a one-liner** and I did not touch that file (yours, and dirty). The *durability* of
   SAM provenance does not depend on this — §5 closes it at the region level regardless — but the
   mark's honesty does.
2. **Persist at commit, not at arm.** `addVisualMark(draft, {save:false})` while staging;
   `updateVisualMark(id, {status:'committed'})` at merge is the write. A suggestion added to the
   store simply never persists — safe to render it quarantined.
3. **Never author a bridge field.** If a tool needs a ground to show provenance, call
   `reconcileBridgeFields(ground, store.visualMarks)` — do not set `mark_source` by hand. `bridgeFieldsAgree`
   is available as an assertion.
4. **`region_mask` geometry is `raster_mask` + `mask_ref` ONLY.** The validator rejects inline
   pixels; the mask stays on the Region.
5. **P2F candidate:** the `region_mask → brush_field` conversion act (contract v2 §7.2-C) — reading a
   segmented extent *as* a perceptual field is a curator act that mints a new mark `derived_from` the
   region_mask. Designed, not built.

## 11. Recommended next

**P2F — conversion + merge.** Wire Lane B2's tools to the store API at commit (they may already be,
in their worktree); implement `region_mask → brush_field` conversion; and run the bridge
reconciliation on ground display so provenance is visible everywhere a ground is, not only in the
refine inspector. Backend stays untouched after this gate.
