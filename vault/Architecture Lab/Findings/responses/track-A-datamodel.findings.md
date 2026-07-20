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

---
---

# v2 — graph-ready & two-sided (2026-07-08)

**Mode:** deep read + plan. No app code changed.
**Why v2:** the v1 pass (findings @ `77a145a`) predates two things — (a) the **fashion open-source stack** (Fashionpedia parts+attributes, FashionCLIP taste-vectors, SAM2), and (b) the project going **two-sided (B2B+B2C)**, so the region is no longer just an annotation — it is **the atom of the taste graph ("Ruchi")** shared by auto-detectors, creators, *and* audiences. This section folds those in **additively**, without reopening the merge.
**Read this pass:** `00-brief.md` (+ v2 addendum), `01-strategy-two-sided.md`, `model-integration-plan.md`, `decisions-darshan.md`, `07-purpose-lens.md`; re-grounded `schemas/post.py`, `routers/posts.py` (`detect-regions` `:479-553`, `region-annotations` `:556-594`), `anatomy_catalog_service.py` (aggregation keys).
**Lens (Purpose→Structure):** Drishya's job is *marking an image part by part, saying how it affects you, and tracing **who** saw it*. v1 gave the single truthful spine; v2's only new structural demand is that the spine also carry **provenance across two sides** (who marked it — auto/creator/audience) and **graph hooks** (Fashionpedia part/attributes, a FashionCLIP vector pointer) — all null-safe so nothing pre-graph breaks.

---

## v2.0 Carried forward from v1 (NOT re-litigated)

- **MERGE stands.** Retire `bounding_box_tags` (0 rows in prod), make `region_annotations` the one model. Field name **stays `region_annotations`** (zero catalog `$exists`/projection churn).
- **Retirement, not backfill.** Phases 0–3 from v1 §3 unchanged (stop initializing bbox on create/upload/bulk; drop from `PostUpdate`; read-only `{}` for one release; then delete `BoundingBox` + field).
- **Coordinates = normalized `{x,y,w,h}` 0–1, top-left**, rendered via SVG `viewBox 0 0 100 100` — unifies manual+auto and survives the now-resizable pane (v1 §5). Carried forward.
- **Strict `Region` Pydantic model with `extra='allow'`** (locked Q3): closes the "client sends anything, we persist it" gap at `region-annotations` while letting Track B/C add producer fields without a schema war.
- **Manual marks save through the existing full-array `POST /region-annotations`** (locked Q4). **`block_id` included now** (locked Q5). **`parent_id` canonical, `parent_label` dropped** (locked Q7). **Two-detector dedup/precedence is Track B's** (locked Q6) — Track A only guarantees one shape + a `detector` provenance tag.

The six catalog keys `anatomy_catalog_service` reads — `category, label, prioritised, weight` (summed **iff** `prioritised`), `user_note, material` (+ `box` in the images endpoint) — are **re-confirmed verbatim** against `anatomy_catalog_service.py:85-113,225-239`. The v2 fields below are all outside that set, so **`aggregate_categories` is untouched.**

---

## v2.1 Actor-field resolution — **COLLAPSE to a single `actor`** ✅

The prompt asks whether to keep both `source: manual|auto` and `actor: auto|creator|audience`, or collapse. **Recommendation: collapse to one field, `actor: auto | creator | audience`. Drop `source` entirely.**

Why collapse (not keep both):
- **They're the same axis.** `source` answers "human or machine?"; `actor` answers "which human, or machine?" — `actor` is strictly finer-grained and fully subsumes `source` (`auto`≡`source:auto`; `creator`+`audience` are the two ways `source:manual` can happen). Keeping both invites illegal/ambiguous pairs (`source:auto` + `actor:creator`? `source:manual` + `actor:audience`?) that every consumer would have to reconcile.
- **The two-sided graph needs the third value.** `source:manual|auto` **cannot** distinguish a creator's deliberate annotation from a one-tap audience signal — and that distinction *is* the two-sided model (§01-strategy §4: "multi-party… same schema, actor tag"). A boolean-ish `source` is the wrong shape the moment audience taps exist.
- **Provenance is not lost.** *Who* marked it → `actor`. *Which machine* (when `actor=auto`) → the existing `detector` field (`yolo | fashionpedia | sam2 | vision`). Two orthogonal, non-redundant fields cleanly replace the muddled pair.

So the spine field the v1 findings introduced as `source` is **renamed and widened to `actor`**. Since v1's `source` was never shipped (0 manual rows; auto regions never carried it), there is nothing to migrate — existing 77 regions simply default `actor="auto"`.

| `actor` value | Who / what | `detector` | Write path |
|---|---|---|---|
| `auto` | a detector produced it | `yolo` \| `fashionpedia` \| `sam2` \| `vision` | `POST /detect-regions` |
| `creator` | the curator marked/annotated it deliberately (old "manual" + prioritise/note) | `null` | `POST /region-annotations` (existing full-array save) |
| `audience` | a low-friction consumer signal (tap / dwell / fork / save-reason) | `null` | **future** B2C capture endpoint (Track F) — schema-ready now, unwritten |

---

## v2.2 Final graph-ready `Region` schema

One field (`region_annotations`), one array, one coordinate convention. Typed, `extra='allow'`. All v2 additions are optional/defaulted → **null-safe on the existing 77 regions**.

```python
class RegionBox(BaseModel):
    x: float; y: float; w: float; h: float           # normalized 0–1, top-left origin

class Region(BaseModel):
    id: str = Field(default_factory=lambda: f"reg_{uuid.uuid4()}")
    # ── provenance (two-sided) ───────────────────────────────────────────
    actor: str = "auto"              # auto | creator | audience   ← the one provenance spine
    detector: Optional[str] = None   # yolo | fashionpedia | sam2 | vision  (only when actor=auto)
    # ── geometry (normalized; unifies manual+auto, survives resize) ───────
    box: RegionBox
    polygon: Optional[List[List[float]]] = None       # normalized, seg only (YOLO/SAM2)
    confidence: Optional[float] = None                # auto only
    # ── semantics (catalog-critical keys kept verbatim) ──────────────────
    label: str = ""                                   # display name        (catalog key)
    category: str = "other"                           # coarse vocab        (catalog key)
    material: str = ""                                #                     (catalog key)
    description: str = ""
    # ── fashion graph (Fashionpedia) — NEW, additive ─────────────────────
    part: Optional[str] = None                        # Fashionpedia apparel-part slot (≠ coarse category)
    attributes: List[str] = []                        # Fashionpedia 294-attribute vocab
    # ── taste vector (FashionCLIP) — NEW, pointer only, vector OUT of row ─
    embedding_id: Optional[str] = None                # → region_embeddings collection (§v2.4)
    # ── hierarchy ────────────────────────────────────────────────────────
    depth: int = 0                                    # 0 anchor/whole · 1 fine part
    parent_id: Optional[str] = None                   # fine → anchor (replaces parent_label)
    # ── curator meaning (catalog-critical) ───────────────────────────────
    prioritised: bool = False                         # "affected me"       (catalog key)
    weight: int = 0                                   # 0–100, summed iff prioritised (catalog key)
    user_note: str = ""                               # "how it affects me" (catalog key)
    # ── cross-surface link ───────────────────────────────────────────────
    block_id: Optional[str] = None                    # region → story block (optional; Lane 2 Option B)
```

Deltas from the v1 schema (§2): `source` → **`actor`** (widened, v2.1); `detector` vocab widened to include `fashionpedia|sam2`; **+`part`**, **+`attributes`**, **+`embedding_id`**. Everything else identical. The catalog's six keys sit untouched in the middle blocks.

---

## v2.3 Migration / retirement — **unchanged (0-row retirement)**

No change from v1 §3. Re-confirmed this pass:
- **Nothing to backfill** — 0 `bounding_box_tags` rows; the best-effort pixel→normalized mapper in v1 §3 stays a contingency only.
- **Existing 77 regions validate as-is** — every new v2 field is optional/defaulted (`actor="auto"`, `part=None`, `attributes=[]`, `embedding_id=None`), and `extra='allow'` tolerates any stray `parent_label`/`source` until the next re-detect rewrites the array.
- **Catalog untouched** — `aggregate_categories` (`anatomy_catalog_service.py:66,84-113`) queries `{"region_annotations": {"$exists": True}}` and reads only the six keys + box; none of `actor/detector/part/attributes/embedding_id/block_id` are read, so **no query, projection, or aggregation change**. Verified against the file this pass.

---

## v2.4 Embedding storage — **sidecar `region_embeddings` collection, keyed by `embedding_id`**

**Keep the vector OUT of the region document** (and out of the `posts` document entirely). Store FashionCLIP vectors in a dedicated collection:

```
region_embeddings   (one doc per embedded region)
  _id            : ObjectId
  embedding_id   : str        # the stable pointer stored on Region.embedding_id (indexed, unique)
  vector         : [float]    # FashionCLIP image/text embedding (e.g. 512-d)
  model          : str        # "fashion-clip"  (version the space so re-embeds are safe)
  dim            : int
  post_id        : str        # backref (for cascade cleanup + provenance)
  region_id      : str        # backref
  created_at     : datetime
```

Why sidecar, not a Mongo field on `Region`:
- **Region docs stay light & fast.** `region_annotations` is read on *every* post response (`post_helper`); a 512-float vector per region × up to 12–16 regions would bloat every list/detail payload for data the UI never renders.
- **Vectors are immutable & cacheable.** Once computed for a (region, model) pair they don't change; a sidecar lets them be written once and skipped on post edits.
- **Swappable backend behind a stable pointer.** `embedding_id` is the indirection: today it resolves to a `region_embeddings` doc; when Track C wants ANN search we point the *same id* at **MongoDB Atlas Vector Search** (add a `knnVector` index on `region_embeddings.vector` — no schema change, since it's already its own collection) or an external store (Qdrant/pgvector) without touching `Region` or `posts`. Recommend **Atlas Vector Search** if the cluster is on Atlas (keeps one datastore); a plain indexed collection now, vector-index later, otherwise.

How the catalog/RAG (Track C) reads them: aggregation stays label/count-based today (unchanged). When Track C adds vector similarity, it (a) collects `embedding_id`s from the regions it cares about, (b) `$lookup`/queries `region_embeddings`, (c) runs similarity / RAG retrieval. The taste graph "Ruchi" = `region_annotations` (meaning) **joined to** `region_embeddings` (geometry-of-taste) on `embedding_id`. **Producer:** the FashionCLIP inference step (Track C / model-plan Phase 1) writes the `region_embeddings` doc and stamps `embedding_id` back onto the region.

---

## v2.5 Blast radius — v1 list **+ where the new fields get set**

The v1 blast radius (§4) holds in full. **v2 additions** — who sets `actor/detector/part/attributes/embedding_id`:

| Field | Producer | Where (write site) |
|---|---|---|
| `actor="auto"`, `detector="yolo"` | YOLO11n-seg anchors | `segmentation_service.py:92-100` → surfaced via `detect-regions` `posts.py:514-515` |
| `actor="auto"`, `detector="vision"` | vision-LLM fallback anchors + fine parts | `vision_service.py:433-439,556-565` → `detect-regions` `:512,535` |
| `actor="auto"`, `detector="fashionpedia"` | **NEW** Fashionpedia Mask-RCNN (Track B, model-plan Phase 2) | new seg service, merged in `detect-regions` |
| `actor="auto"`, `detector="sam2"` | **NEW** SAM2 arbitrary-region masks (Track B, Phase 3; video Phase 4) | new seg service |
| `part`, `attributes[]` | **NEW** Fashionpedia (labels) / FashionCLIP zero-shot (attributes) | Track B/C producers; null on all non-fashion + legacy regions |
| `embedding_id` | **NEW** FashionCLIP inference (model-plan Phase 1) | writes `region_embeddings`, stamps id back |
| `actor="creator"` | curator marks/prioritise/note | `POST /region-annotations` `posts.py:556-594` (the v1 "manual" write path) |
| `actor="audience"` | **NEW** low-friction B2C signal (tap/dwell/fork/save-reason) | **future** Track F capture endpoint — field ready, no writer yet |

Endpoint-level notes (unchanged code, just where the stamps land):
- **`detect-regions` `posts.py:514-537`** — stamp `actor="auto"` + the right `detector` when building `anchors`/`fine`; drop `parent_label`; curator-field preservation by `id` (`:539-550`) already correct and must also preserve `actor="creator"` overrides if a creator edited an auto region (Track B precedence question).
- **`region-annotations` `posts.py:570`** — validate `request.regions` against `Region`; this is where `actor="creator"` regions (old manual marks) enter; persona roll-up (`:579-591`, reads `label/user_note/prioritised`) unchanged.
- **New sidecar** — a `region_embeddings` collection + its access helper (Track C) is the only genuinely new storage surface v2 adds.

Frontend blast radius is exactly v1 §4 (`BoundingBoxEditor` = largest change: normalized coords + write to region-save as `actor="creator"`; `RegionDetectorModal` minimal, optionally show an `actor`/`detector` badge). Nothing new for v2 there except optionally surfacing `part`/`attributes` chips (Track D).

---

## v2.6 Coordinate note — carried forward

Confirmed in v1 §5: normalized 0–1 + SVG `viewBox` unifies manual+auto and survives resize. SAM2/Fashionpedia masks are normalized the same way (polygons already normalized in the YOLO path) → they drop straight into `box`/`polygon` with no new convention. No change.

---

## Questions for Adarsh (v2)

The v1 seven are **locked** (`decisions-darshan.md` Part 1) — not reopened. New v2-only calls:

1. **Actor collapse** — confirm dropping `source` for a single **`actor: auto|creator|audience`** (my rec, v2.1). This is the one field-shape decision v2 makes; everything else is additive.
2. **Embedding store** — sidecar **`region_embeddings` collection** now, Atlas Vector Search index later (my rec, v2.4)? Or go straight to an external vector DB (Qdrant/pgvector) if you already know this cluster isn't on Atlas? (Either way `embedding_id` keeps `Region` insulated.)
3. **`part` vs `category`** — keep them as **two fields** (`category` = coarse catalog vocab that the taste catalog already aggregates on; `part` = Fashionpedia's finer apparel slot)? Or should Fashionpedia's part become the `category` and retire the coarse one? I recommend **two fields** — the catalog's six-key contract and cross-domain (non-fashion) regions both depend on the coarse `category` surviving.
4. **`attributes[]` in the catalog** — Track A just gives it a home (null-safe, not aggregated). Should the taste catalog eventually bucket on `attributes` too (richer than label counts), or does that wait for the FashionCLIP-vector catalog and stay out of the frequency aggregator? (Leaning: wait — vectors supersede attribute-counting.)
5. **Audience-write endpoint** — the `actor="audience"` path is Track F's. Confirm Track A's job ends at *"the field exists and is null-safe"* and the capture endpoint/rate-limiting/anti-abuse is entirely Track F (my assumption).

*Research only — no app code touched. v2 is purely additive over the v1 spine: one renamed provenance field (`actor`), three graph hooks (`part`, `attributes`, `embedding_id`), and one sidecar collection. The merge, retirement, coordinate, and catalog conclusions all stand unchanged.*
