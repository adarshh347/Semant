# Track A — Data-model unification: findings

**Mode:** deep read + plan. No app code changed.
**Lens:** Purpose → Structure. Drishya's job includes *marking an image part by part and tracing who saw what*. Two parallel "part" data models is the Foundation problem that blocks it (named in Lane 2 §2).
**Grounding:** line refs current as of `daa18e3`. Backend/service/frontend shapes cross-verified by direct read of `schemas/post.py`, `routers/posts.py`, `routers/anatomy.py`, `services/segmentation_service.py`, `services/vision_service.py`, `anatomy_catalog_service.py`, `BoundingBoxEditor.jsx`, `RegionDetectorModal.jsx`, `PostDetailPage.jsx`.

---

## 0. Headline (the recommendation, up front)

**MERGE — Option A. Retire `bounding_box_tags`; make `region_annotations` the one region model, with a `source: 'manual' | 'auto'` field.** This is not a close call, and one live-data fact makes it near-free:

> **There is zero `bounding_box_tags` data in the database** — 0 non-empty maps across 500 posts sampled. `region_annotations` has 4 posts / 77 regions (0 prioritised yet). The "manual" system is a fully-built editor writing to a field **nobody has used**.

So "unify" here means: keep the richer, normalized, resolution-independent model that already holds all real data, and re-point the manual editor at it. There is **no data-migration risk** (nothing to backfill), and the merge simultaneously **fixes a real bug**: manual boxes are stored in displayed-pixel space and silently drift when the pane is resized (Lane 2 just made the pane resizable — so this bug is now reachable). Normalized coords fix it for free.

Lanes 2 (cross-pane linking), 3 (Visual pane), and 6 (Unconceal) all depend on this call — they can now build against **one** id-keyed, normalized region array.

---

## 1. Field-by-field comparison

| Aspect | `bounding_box_tags` (manual) | `region_annotations` (auto + curator) |
|---|---|---|
| **Schema** | `Post.bounding_box_tags: Optional[dict[str, BoundingBox]]` — `post.py:37`; `BoundingBox{x,y,width,height}` **typed, pixel ints** — `post.py:8-12` | `Post.region_annotations: Optional[List[dict]]` — `post.py:46` — **untyped list, no server validation** |
| **Container** | dict keyed by **tag name** (`{tagName: box}`) | **array** of region objects, keyed by `id` |
| **Coords** | **pixels, displayed-image space** (`getBoundingClientRect`, raw px into CSS — `BoundingBoxEditor.jsx:42-49,316-319`) → **drifts on resize** | **normalized 0–1**, top-left origin (SVG `viewBox 0 0 100 100`, `×100` — `RegionDetectorModal.jsx:106-121`) → **resolution-independent** |
| **Box keys** | `x, y, **width, height**` | `box: { x, y, **w, h** }` |
| **Polygon** | ✗ none | ✓ `polygon: [[x,y]…]` normalized (YOLO-seg only; `≤48` pts) |
| **Label** | the map key (tag name) | `label` (catalog-critical; empty ⇒ region dropped from catalog) |
| **Category / semantics** | ✗ none | `category` (COCO→`figure/garment/object`, or LLM vocab); `material`; `description` |
| **Curator meaning** | ✗ none | `prioritised` (bool), `weight` (0–100), `user_note` ("how it affects me") |
| **Hierarchy** | ✗ flat | `depth` (0 anchor / 1 fine), `parent_id` (fine→anchor), `parent_label` (raw model string) |
| **Provenance** | implicit "manual" (never recorded) | implicit "auto" via id prefix (`seg_`/`region_`/`fine_`); `confidence` on YOLO |
| **Write path** | **only** `PATCH /posts/{id}` (`PostUpdate`, full-map replace) — `posts.py:623-643` | `POST /posts/{id}/detect-regions` (`479-553`, merge+preserve curator fields by id), `POST /posts/{id}/region-annotations` (`556-594`, verbatim save + persona roll-up). **Not** in `PostUpdate`. |
| **Read path** | `post_helper` `posts.py:72` → all responses | `post_helper` `posts.py:81` → all responses |
| **Frontend** | `BoundingBoxEditor.jsx` — axios PATCH full map; selection = `selectedTag` (name) | `RegionDetectorModal.jsx` — fetch POST; selection = `selectedId` (id) |
| **Live data** | **0 posts** | 4 posts / 77 regions |

**The asymmetry is total:** `region_annotations` is a strict superset of `bounding_box_tags` in every dimension except one — the tag-name-as-key affordance — and it's already the model with data, normalization, polygons, semantics, and curator meaning. `bounding_box_tags` contributes nothing the other lacks, and carries a coordinate bug.

### Producer shapes (what writes into `region_annotations`)
- **YOLO-seg** (`segmentation_service.py:92-100`, cap 12): `{id:"seg_N", label:<COCO>, category:figure|garment|object, box:{x,y,w,h}norm, polygon:[[x,y]]norm, confidence, description}`.
- **Vision-LLM anchors** (`vision_service.py:433-439`, fallback, cap 10): `{id:"region_N", label, category, box:{x,y,w,h}norm, description}` (no polygon/confidence).
- **Vision-LLM fine parts / Sūkṣma** (`vision_service.py:556-565`, cap 16): `{id:"fine_N", label, category, parent_label, material, box:{x,y,w,h}norm, description, depth:1}`.
- **Router-added at detect** (`posts.py:531-550`): `parent_id`, `depth` default, and curator fields `prioritised:False, weight:0, user_note:""` (preserved across re-detect by matching `id`).

### Catalog dependency (must not break)
`anatomy_catalog_service.py` reads **only** these keys per region: `category`, `label` (empty ⇒ skip), `prioritised`, `weight` (**summed only when `prioritised` truthy**), `user_note`, `material`, and `box` (images endpoint only). It never reads `id/box/polygon/depth/parent` for aggregation. **Any unified schema must keep those six key names and that `weight`-gated-by-`prioritised` semantics.**

---

## 2. Unified region schema

One field, one array, one coordinate convention. Keep the storage field name **`region_annotations`** (lowest blast radius — see §4/Q1) and add `source`. Make it a **typed Pydantic model** to close the current no-validation gap, but permissive (`extra='allow'`) during Track B/C evolution.

```python
class RegionBox(BaseModel):
    x: float; y: float; w: float; h: float          # normalized 0–1, top-left origin

class Region(BaseModel):
    id: str = Field(default_factory=lambda: f"reg_{uuid.uuid4()}")
    source: str = "auto"                             # 'manual' | 'auto'   ← the unifying field
    detector: Optional[str] = None                   # 'yolo' | 'vision' | None (auto provenance)
    label: str = ""                                  # display name       (catalog-critical)
    category: str = "other"                          # coarse vocab       (catalog-critical)
    box: RegionBox                                   # normalized         (unifies manual+auto)
    polygon: Optional[List[List[float]]] = None      # normalized, seg only
    confidence: Optional[float] = None               # auto only
    material: str = ""                               # (catalog-critical)
    description: str = ""
    depth: int = 0                                   # 0 anchor/whole · 1 fine part
    parent_id: Optional[str] = None                  # fine → anchor (replaces parent_label)
    prioritised: bool = False                        # curator "affected me" (catalog-critical)
    weight: int = 0                                  # 0–100, summed iff prioritised (catalog-critical)
    user_note: str = ""                              # "how it affects me"  (catalog-critical)
    block_id: Optional[str] = None                   # OPTIONAL forward-link to a story block
```

Decisions baked in:
- **Coords = normalized `{x,y,w,h}`** (adopt `region_annotations`; drop `width/height` + pixels). Single convention manual & auto share; survives resize.
- **`source: manual|auto`** is the new spine field the brief/Track-A asks for. `detector` optionally records which auto pipeline (yolo vs vision) — useful when Track B dedups overlapping detectors.
- **`parent_id` canonical**, `parent_label` dropped (the router already resolves `parent_id` at `posts.py:531`; the raw string is redundant).
- **`block_id` (optional, null)** generalises the proven highlight↔block link (`Highlight.block_id`, `post.py:27`) to regions — this is exactly Lane 2's Option B ("a part points at the paragraph that discusses it"). Additive and null-safe; include the field now so the contract is stable, wire the behaviour later (Track D / Lane 2). See Q5.
- **All six catalog keys preserved** verbatim (`category,label,prioritised,weight,user_note,material` + `box`) → catalog keeps working with **no query change** (as long as the field name stays `region_annotations`).

---

## 3. Migration plan

Because **no `bounding_box_tags` data exists**, this is a retirement, not a backfill.

**Phase 0 — no-op backfill.** Nothing to convert. (If any manual boxes appear before cut-over, run the best-effort mapper below.)

**Phase 1 — additive schema.** Introduce the `Region`/`RegionBox` models; type `Post.region_annotations: List[Region]` (permissive). Producers (`segmentation_service`, `vision_service`) set `source:"auto"` + `detector`. No storage rename. Existing 77 regions validate as-is (all their keys are a subset of `Region`; `source` defaults to `"auto"`, `parent_label` tolerated via `extra='allow'` then dropped on next re-detect).

**Phase 2 — manual writes into the unified array.** Re-point `BoundingBoxEditor` to create `source:"manual"` regions (normalized box, `label=<user text>`, `category="manual"`/`"tag"`, `depth:0`) and persist them via the region-save path instead of the `bounding_box_tags` PATCH (see Q4).

**Phase 3 — deprecate the old field.** Stop initializing `bounding_box_tags:{}` on create/upload/bulk (`posts.py:113/232/274`); remove it from `PostUpdate` (`:50`); keep `Post.bounding_box_tags` readable (emits `{}`) for one release, then delete the field + `BoundingBox` model.

**Best-effort mapper (only if stray manual data ever appears).** Per `{tagName:{x,y,width,height}}` → `Region{source:"manual", label:tagName, category:"manual", box: {x/W, y/H, width/W, height/H}, depth:0, prioritised:false}` where `W,H` = image **natural** dims (fetched from Cloudinary/stored). ⚠️ Lossy by construction: stored bbox pixels are *displayed-space* at an unknown draw-time size (`BoundingBoxEditor.jsx:42-49`), so natural-dim normalization is an approximation — flag such regions `source:"manual"` for curator re-verification. **Moot today (0 rows).**

**Catalog continuity.** Zero changes required: `aggregate_categories` / `get_images_for_category` query on `region_annotations` existence and read `category/label/prioritised/weight/user_note/material/box` — all preserved. The only new arrivals are `source:"manual"` regions, which aggregate identically (they carry the same keys; unprioritised manual marks simply don't add intensity, matching current semantics).

---

## 4. Blast radius (list — not edited)

**Backend — schema (`schemas/post.py`)**
- `BoundingBox` (`:8-12`) → retire (Phase 3). `Post.bounding_box_tags` (`:37`), `PostUpdate.bounding_box_tags` (`:50`) → deprecate then remove.
- `Post.region_annotations` (`:46`) → type as `List[Region]`. Add `Region`/`RegionBox` models. `RegionAnnotationsRequest.regions` (`:110`) → `List[Region]`.

**Backend — routers (`routers/posts.py`)**
- `post_helper` bbox read `:72` → drop (or keep emitting `{}` transitionally); region read `:81` unchanged.
- create/upload/bulk bbox init `:113 / :232 / :274` → remove.
- `PATCH /posts/{id}` `update_post :623-643` → remove the bbox write path (it's the only bbox writer).
- `POST /detect-regions :479-553` → set `source:"auto"`/`detector`; drop `parent_label`; otherwise unchanged (curator-field preservation by id already correct).
- `POST /region-annotations :556-594` → now also the manual-mark save target; validate against `Region`; persona roll-up (`:581-583`, reads `label/user_note/prioritised`) unchanged.

**Backend — anatomy (`routers/anatomy.py`, `anatomy_catalog_service.py`)**
- **No change** if field name stays `region_annotations` and the six keys persist. (If renamed to `regions` → update the `$exists` queries `:66/:216` and projections `:80/:217`.) `persona_service.add_region_correspondence` — unchanged.

**Backend — services**
- `segmentation_service.py:92-100` / `vision_service.py:433-439,556-565` → add `source`/`detector`; keep normalized box/polygon. `parent_label`→rely on router `parent_id`.

**Frontend**
- `BoundingBoxEditor.jsx` — **largest change**: read/write the unified array (`source:"manual"`), store **normalized** `{x,y,w,h}` (convert mouse px → normalized by container/natural size; render normalized → px), select by `id` not tag name, POST to region-save instead of PATCH bbox map. Fixes resize drift. Coverage/count stats recompute over regions.
- `RegionDetectorModal.jsx` — minimal; already normalized on `region_annotations`. Optional: show `source` badge (manual vs auto), tolerate `source` field.
- `PostDetailPage.jsx` — Visual-pane stats now count regions; Unconceal anatomy chips (`region_annotations.filter(prioritised)`, `:1075-1081`) unchanged. (Track D later merges both panes onto the one array.)
- **No other frontend reader** of `post.bounding_box_tags` exists outside `BoundingBoxEditor` (grep-confirmed).

**Cross-lane**
- **Lane 2** — Option B (region `block_id` → story) becomes buildable once `block_id` lands.
- **Lane 3** (Visual) & **Lane 6** (Unconceal) — both own the editors above; they build against one array. This schema is the shared contract they've been waiting on.

---

## 5. Coordinate feasibility (confirming Track-A Q5)

**Confirmed: normalized 0–1 unifies manual + auto and survives resize.** `region_annotations` already proves it in production — `RegionDetectorModal` renders via an SVG `viewBox="0 0 100 100" preserveAspectRatio="none"`, so the browser scales normalized coords to whatever size the image is displayed at, resolution-independently. Adopting the same for manual marks not only unifies the two — it **removes** `BoundingBoxEditor`'s displayed-pixel drift bug (its boxes are absolute CSS px tied to draw-time render size). The only manual-side work is dividing mouse deltas by the container size at capture instead of storing raw px — a few lines, no new dependency.

---

## Questions for Adarsh

1. **Field name** — keep storage as `region_annotations` (zero catalog/query churn; my recommendation) or rename to `regions` (cleaner, but touches catalog `$exists` queries + every consumer)?
2. **Retire `bounding_box_tags` outright?** With 0 rows in prod, I recommend hard-deprecating it (no backfill, remove from `PostUpdate`, delete after one read-only release). Any reason to keep the manual pixel-rect field alive?
3. **Type strictness** — make `region_annotations` a strict Pydantic `Region` model now (closes the "client sends anything, we persist it" gap at `posts.py:570`), or keep it permissive `List[dict]` while Track B/C are still changing the producer shapes? I lean strict-but-`extra='allow'`.
4. **Manual write path** — route new manual marks through the existing `POST /region-annotations` (full-array save, consistent with the auto path), or add a small per-region upsert endpoint? `BoundingBoxEditor` today does a full-map PATCH; either works, but this decides how much of that component is rewritten.
5. **`block_id` now or later?** Include the optional region→block link field in the schema now (stable contract; enables Lane 2 Option B and `/part` slash-insert later) even though nothing writes it yet — or leave it out until Track D needs it?
6. **Two auto detectors, one array** — YOLO-seg and the vision-LLM fallback can both emit anchors for the same image (currently the LLM is only a fallback when YOLO returns nothing). When Track B makes segmentation domain-aware, do overlapping detections need dedup/precedence, or is that explicitly Track B's problem (Track A just guarantees they share one shape + `detector` provenance)?
7. **`parent_label` drop** — confirm we canonicalize on `parent_id` (already resolved server-side) and drop the raw `parent_label` string.

*Research only — no app code touched. This is the data spine E→A→(B/C/D) hangs on; awaiting your calls before any build.*
