# Track A — Data-model unification (research + plan only)

**Read first:** `architecture-lab/vision-initiative/00-brief.md`, `architecture-lab/07-purpose-lens.md`.
**Do not edit code.** Write `responses/track-A-datamodel.findings.md`.

## Mission
There are two systems that mark parts of an image — `bounding_box_tags` (manual pixel rects) and `region_annotations` (auto polygons + notes). Propose **one** region model that subsumes both, so annotation stops being duplicated.

## Read
- `backend/schemas/post.py` (BoundingBox, region_annotations, RegionAnnotationsRequest, RegionDetectRequest, LocalContextRequest).
- `backend/routers/posts.py` + `anatomy.py` — every read/write of `bounding_box_tags` and `region_annotations`.
- `backend/services/segmentation_service.py` (region shape it emits), `anatomy_catalog_service.py` (what it aggregates).
- Frontend consumers: `BoundingBoxEditor.jsx` (writes bounding_box_tags), `RegionDetectorModal.jsx` + Unconceal branch (region_annotations), `PostDetailPage.jsx`.

## Answer
1. **Field-by-field comparison** of the two models (coords: pixel vs normalized; polygon vs rect; label/category; user notes/priority; provenance manual vs auto).
2. **A single unified `region` schema** covering: id, source (`manual|auto`), label, category, box (normalized), optional polygon, confidence, user note ("how it affects me"), prioritised flag, parent (for sub-parts). Show it.
3. **Migration**: how existing `bounding_box_tags` data maps into it; what the anatomy catalog needs to keep working.
4. **Blast radius**: every endpoint/component that must change (list, don't edit).
5. Coordinate note: normalized coords unify manual + auto and survive resize — confirm feasibility.

## Output contract → `responses/track-A-datamodel.findings.md`
Comparison table · unified schema · migration plan · blast-radius list · open questions for Adarsh.
