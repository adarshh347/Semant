# Track A — Data-model unification (v2, research + plan only)

**Read first:** `00-brief.md` (+ its v2 addendum), `01-strategy-two-sided.md`, `model-integration-plan.md`, `decisions-darshan.md`, `../07-purpose-lens.md`.
**Do not edit code.** Extend `responses/track-A-datamodel.findings.md` into a **v2** (the original pass predates the fashion revamp — the merge analysis holds; the schema must now be graph-ready).

## Why v2
The first Track A pass (findings @ `77a145a`) correctly concluded: **merge — retire `bounding_box_tags` (0 rows in prod), make `region_annotations` the one model.** That stands. But it predates: (a) the **fashion open-source stack** (Fashionpedia parts+attributes, FashionCLIP vectors), and (b) the project going **two-sided (B2B+B2C)**, which means the region model is also the atom of the **taste graph** shared by auto-detectors, creators, and audiences. Track A-v2 folds those in — additively, without reopening the merge.

## Locked going in (see `decisions-darshan.md` Part 1)
Field name stays `region_annotations` · `bounding_box_tags` hard-deprecated (no backfill) · strict `Region` with `extra='allow'` · manual marks save via existing `POST /region-annotations` · `block_id` field included now · dedup/precedence is Track B's · `parent_label` dropped for `parent_id`.

## Mission (v2)
Produce the **final unified `Region` schema** (below), the migration/retirement plan, and the blast radius — now including the graph-ready fields and the two-sided `actor` distinction.

## Read
- `backend/schemas/post.py`, `backend/routers/posts.py` + `anatomy.py` (every read/write of both region fields).
- `backend/services/segmentation_service.py`, `anatomy_catalog_service.py` (what it aggregates — the six catalog keys must survive verbatim).
- Frontend: `BoundingBoxEditor.jsx`, `RegionDetectorModal.jsx` + Unconceal branch of `PostDetailPage.jsx`.

## Answer (v2 deltas in bold)
1. **Confirm** the merge + retirement plan from v1 (no re-litigation; just carry it forward).
2. **Finalize the unified `Region` schema** including the v2 fields — `part` (Fashionpedia slot), `attributes: List[str]` (Fashionpedia 294-vocab), `embedding_id` (FashionCLIP taste-vector pointer, vector stored out-of-row — decide where: a sidecar collection vs Mongo field), and **the actor model**: resolve whether we keep both `source: manual|auto` and `actor: auto|creator|audience` or **collapse to a single `actor` field** (recommend collapse — say which). All additive + null-safe.
3. **Migration/retirement** — unchanged from v1 (0-row retirement); confirm the six catalog keys are preserved and the new fields don't perturb `aggregate_categories`.
4. **Blast radius** — the v1 list + where `attributes/part/embedding_id/actor` get set (which producer: YOLO=auto/detector:yolo, Fashionpedia=auto/detector:fashionpedia, creator marks=creator, audience taps=audience).
5. **Embedding storage** — recommend where FashionCLIP vectors live (out-of-row: a `region_embeddings` collection keyed by `embedding_id`, or a vector store) and how the catalog/RAG (Track C) reads them. Keep the vector OUT of the region document.
6. **Coordinate note** — confirmed in v1 (normalized unifies + survives resize); carry forward.

## Output contract → `responses/track-A-datamodel.findings.md` (v2 section appended)
Carried-forward merge decision · **final graph-ready `Region` schema** · actor-field resolution · embedding-storage plan · updated blast radius · questions for Adarsh.
