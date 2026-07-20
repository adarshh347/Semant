# VISION-CODE-AUDIT-001 — read-only visual-pipeline audit

**Date:** 2026-07-18 · **Mode:** investigation only (no code/config/data changed) ·
**Branch:** `feat/vision-differential` · **Scope:** the image → Region → Ground →
Percept pipeline, as it exists after `REGION-GEOMETRY-001` (commit `314cf94`).

**Headline finding.** The brief frames the system as "YOLO11n-seg for coarse anchors
+ a vision-model decomposition stage." That undersells what is already built. The
repo already contains most of the *Darshan* vision stack: **two** polygon-producing
segmenters (YOLO11n-seg **and** SegFormer-clothes) with a precedence merge, a
**live FashionCLIP** service (embeddings + zero-shot labels + domain routing), a
**Mongo vector sidecar** with cosine search, enrichment endpoints, and **polygon
rendering already default** in four frontend overlays. The next system is therefore
mostly an *adapter-and-orchestration* problem, not a green-field build — with three
genuine capability gaps (exact-mask refinement / SAM2, Fashionpedia attributes,
disciplined GPU/serverless orchestration) and a set of correctness/repro debts that
should be paid before adding models.

---

## 1. Current pipeline diagram

```
                         ┌─────────────────────────── UPLOAD (persistence #1) ───────────────────────────┐
  file / url / bulk  →   create_post / create_post_from_url / create_multiple_posts   (posts.py:107/181/269)
                         cloudinary.uploader.upload → post_collection.insert_one       (posts.py:113→125)
                         collection "posts": photo_url, photo_public_id, text_blocks, general_tags …
                         └───────────────────────────────────────────────────────────────────────────────┘
                                                        │
              POST /{post_id}/detect-regions  (async, posts.py:590 detect_regions)
                                                        │
   image re-acquisition ──► httpx GET photo_url from Cloudinary  (posts.py:618-621)   [NOT the upload bytes]
                                                        │
   decode / orient ──────► PIL Image.open(...).convert("RGB")   (per service)  ⚠ NO EXIF transpose anywhere
                                                        │
   domain routing ───────► _resolve_is_fashion → fashion_clip.classify_domain (posts.py:564-587, to_thread)
                                                        │                                → persists post.domain
   coarse seg (STHŪLA) ──► fashion_segmentation_service.segment_image_bytes  (SegFormer, to_thread 626)
                           segmentation_service.segment_image_bytes           (YOLO11n-seg, to_thread 629)
                           merge_with_precedence(garments, yolo)              (posts.py:635)
                           fallback: vision_service.detect_regions(url)       (posts.py:644-647, LLM anchors)
                                                        │
   fine decomp (SŪKṢMA) ─► vision_service.decompose_regions (Groq VLM)        (posts.py:655-657)
                                                        │
   geometry canon ───────► region_geometry.match_parent  (geometry-first)     (posts.py:663 → rg.py:126)
                           region_geometry.clip_box_to_parent (no-crush)       (posts.py:666 → rg.py:151)
                                                        │
   assemble ─────────────► regions = (anchors or []) + fine                    (posts.py:672)
                           preserve prioritised/weight/user_note/creator       (posts.py:677-694)
                                                        │
   persistence #2 ───────► update_one $set region_annotations (WHOLESALE)      (posts.py:695)
   response ─────────────► {regions, source, anchor_count, fine_count}         (posts.py:696)  [not post_helper]

  ── SEPARATE enrichment / embedding passes (never run on this corpus — 0 vectors stored) ──
   POST /{id}/enrich-regions (posts.py:871) → _compute_region_enrichment (823) → fashion_clip.embed_image
        → region_embedding_service.upsert_embedding → collection "region_embeddings"  (posts.py:903-905)
   POST /{id}/region-annotations (posts.py:773 save_region_annotations) → _embed_marked_regions (699, bg task)

  ── READ paths ──  post_helper (posts.py:69) exposes region_annotations, grounds, percepts, bounding_box_tags{}
  ── FRONTEND ──   RegionOverlay / GroundLayers / AletheiaHook / RegionDetectorModal render polygon-by-default;
                   crops (cldRegionCrop) are rectangular; PerceptCrop adds CSS clip-path polygon shaping.
```

Grounds / Percepts (Differential v1) are **not** produced by this pipeline. They are
free-form `List[dict]` on the Post, written only through the generic `PATCH /{id}`
(`update_post`, posts.py:949), and deliberately kept out of `region_annotations`
because detect-regions wholesale-replaces that array.

---

## 2. Evidence table (file:symbol references)

| Concern | Symbol | Location |
|---|---|---|
| Upload (multipart) | `create_post` | `backend/routers/posts.py:107` |
| Upload (url/data-url) | `create_post_from_url` | `posts.py:181` |
| Dissection route | `detect_regions` (async) | `posts.py:590-696` |
| Image re-fetch | `httpx…get(photo_url)` | `posts.py:618-621` |
| Domain routing | `_resolve_is_fashion` → `classify_domain` | `posts.py:564` · `fashion_clip_service.py:170` |
| YOLO segmenter | `segment_image_bytes` / `_load_model` | `segmentation_service.py:55` / `:29` |
| YOLO model id / device | `_MODEL_NAME="yolo11n-seg.pt"` · `device="cpu"` | `segmentation_service.py:17` · `:67` |
| Fashion segmenter | `segment_image_bytes` / `_load` | `fashion_segmentation_service.py:255` / `:106` |
| Fashion model id | `_MODEL_NAME="mattmdjaga/segformer_b2_clothes"` | `fashion_segmentation_service.py:29` |
| Precedence merge | `merge_with_precedence` | `fashion_segmentation_service.py:312` |
| VLM decomposition | `VisionService.decompose_regions` | `vision_service.py:519-606` |
| VLM model id | `self.vision_model="meta-llama/llama-4-scout-17b-16e-instruct"` | `vision_service.py:28` |
| VLM prompt | `SOOKSHMA_PROMPT` (+ anchor/lens hints) | `vision_service.py:780-808` (`561-572`, `575-581`) |
| VLM parser | `_parse_subregions` | `vision_service.py:608-652` |
| Geometry contract | `match_parent` / `clip_box_to_parent` | `region_geometry.py:126` / `:151` |
| Unused converters | `unletterbox_normalized`,`pixels_to_normalized`,`xyxy_to_xywh` | `region_geometry.py:64/53/48` (tests-only) |
| Persistence #2 | `update_one $set region_annotations` | `posts.py:695` |
| Region schema | `Region` (extra="allow") | `backend/schemas/post.py:30-65` |
| Polygon field | `polygon: Optional[List[List[float]]]` | `post.py:44` |
| Legacy field | `bounding_box_tags` (read-only `{}`) | `post.py:94` · `posts.py:76` |
| Grounds/Percepts | `grounds`,`percepts: Optional[List[dict]]` | `post.py:109-110`,`117-118` |
| FashionCLIP encoder | `embed_image` / `_load` | `fashion_clip_service.py:110` / `:64` |
| Embedding sidecar | `upsert_embedding` / `search_similar` | `region_embedding_service.py:48` / `:102` |
| Embedding collection | `region_embeddings_collection` | `backend/database.py:78` |
| Sidecar indexes | `ensure_indexes` (B-tree only) | `region_embedding_service.py:23` · wired `main.py:6` |
| Enrichment | `enrich_regions` / `_compute_region_enrichment` | `posts.py:871` / `:823` |
| Frontend overlay | `RegionOverlay` (polygon default) | `frontend/src/components/RegionOverlay.jsx:37,61-69` |
| Ground renderer | `GroundLayers`/`RegionGround` | `frontend/src/differential/GroundLayers.jsx:179,163-176` |
| Stage geometry | `useStageGeometry`/`contentBox` | `frontend/src/differential/useStageGeometry.js:64,23` |
| Rectangular crop | `cldRegionCrop` | `frontend/src/lib/cloudinary.js:45-53` |
| Polygon CSS crop | `PerceptCrop` (clip-path) | `frontend/src/components/home/PerceptCrop.jsx:20-33` |
| Geometry tests | `test_region_geometry.py` (14, box-only) | `backend/tests/test_region_geometry.py` |

### Live data census (read-only query, 2026-07-18)

| Metric | Count |
|---|---|
| Posts total | 127 |
| Posts with regions | 6 |
| Regions total | 50 |
| — polygon (len>2) | **12** (yolo 5 + segformer 7) |
| — box-only | **38** (all `detector="vision"`, the VLM parts) |
| — `actor=auto` / `creator` / `audience` | 50 / **0** / **0** |
| — degenerate (w or h ≤ 0.011) | **3** (the REGION-GEOMETRY-001 crush slivers, still stored) |
| — carrying `embedding_id` | **0** |
| `region_embeddings` docs | **0** |
| Detectors present | `vision`:38, `segformer_clothes`:7, `yolo`:5 |

Two facts jump out: **(a)** the embedding pipeline has *never run on this corpus* —
zero vectors, zero `embedding_id`s, so all of Track C's retrieval is inert today;
**(b)** re-dissection has *not* run since REGION-GEOMETRY-001 — the 3 crushed slivers
are still in Mongo (consistent with the Groq 404 blocking re-dissection).

---

## 3. Contract violations & data risks (P0 / P1 / P2)

### P0 — must fix before adding models

- **P0-1 · No EXIF orientation handling anywhere.** Decode is bare
  `Image.open().convert("RGB")` (`segmentation_service.py:65`,
  `fashion_segmentation_service.py:269`, `fashion_clip_service.py:84`); grep for
  `exif_transpose`/`exif` across `backend/` = 0 hits. A rotated-EXIF phone JPEG is
  decoded un-transposed, so **every** box/polygon/embedding is computed against the
  wrong pixel frame. This is a silent, systematic geometry corruption that will scale
  with a mobile/consumer corpus and will poison embeddings too. Fix once, centrally,
  at the single decode seam.
- **P0-2 · Embeddings declared "live" but never populated.** 0 of 50 regions have an
  `embedding_id`; `region_embeddings` is empty. `upsert_embedding`'s own docstring
  still says "STUB" (`region_embedding_service.py:61`) though the body is functional.
  Any Track C retrieval / "taste graph" feature is currently a no-op. Before building
  on it: run the backfill and add one round-trip test (there is none — see P1-4).

### P1 — correctness / reproducibility / integrity

- **P1-1 · Nothing is version-pinned.** `requirements.txt`, `backend/requirements.txt`,
  `requirements-ml.txt` are all bare names, no `==`. Installed reality is a snapshot
  (torch 2.13.0+cpu, torchvision 0.28.0, transformers 5.13.0, ultralytics 8.4.90,
  opencv 5.0.0.93, pydantic 2.13.4, numpy 2.4.4). Adding SAM2/Fashionpedia into an
  unpinned env is how you get a silent breaking upgrade of torch/transformers.
- **P1-2 · Two OpenCV distributions installed at once.** Both `opencv-python` **and**
  `opencv-python-headless` == 5.0.0.93 are present, despite `requirements-ml.txt`
  deliberately specifying only `-headless` (its comment warns about this). Two cv2
  builds in one env is a known import/segfault hazard.
- **P1-3 · No inference timeout, no concurrency cap.** Model calls are offloaded via
  `asyncio.to_thread` (`posts.py:626-629`) but unbounded — a burst saturates the
  default executor, and a slow/hung inference has no deadline (only the 30 s HTTP
  fetch is bounded). This is the exact place a `ModelManager` + queue belongs.
- **P1-4 · No polygon/mask tests at all.** All 14 `test_region_geometry.py` cases
  assert on axis-aligned boxes; the pipeline that produces per-pixel masks/contours
  (YOLO `.xyn`, SegFormer `findContours`/`approxPolyDP`) and the embeddings have zero
  round-trip coverage. Mask work would be flying blind.
- **P1-5 · VLM invents top-level geometry, persisted verbatim.** Geometry-first
  parenting protects *children* (clip-no-crush), but a fine part with no genuine
  anchor (≥50% overlap) keeps the model-estimated box as-is (`posts.py:664` `if
  parent:` else top-level; boxes only frame-clamped in `_parse_subregions:628-633`).
  On the current corpus that is **38 of 50 regions** (`detector="vision"`), none
  validated against pixels. This is the residual honesty gap REGION-GEOMETRY-001
  called out, now quantified.
- **P1-6 · detect-regions wholesale-replaces `region_annotations`.** `posts.py:695`
  overwrites the whole array; only `prioritised/weight/user_note` + creator-actor rows
  are carried forward (`posts.py:677-694`). Auto geometry, polygons and any prior
  embedding linkage are dropped on every re-run. There is no per-region upsert and no
  provenance/revision record of what changed.

### P2 — hygiene / latent

- **P2-1 · `.env` has an unparseable line.** `python-dotenv could not parse statement
  starting at line 32` (observed when running any backend script). Silent — a var on
  that line may not be loading. Worth a look (the file is open in your IDE).
- **P2-2 · Dead coordinate converters.** `unletterbox_normalized`,
  `pixels_to_normalized`, `xyxy_to_xywh` (`region_geometry.py:48-88`) are invoked only
  by tests; no producer uses them. Fine as a future contract, but they imply a
  canvas/letterbox frame that the live path never enters — don't mistake them for
  active safeguards.
- **P2-3 · detect-regions re-downloads from Cloudinary every call** (`posts.py:618`)
  rather than reusing upload bytes — extra latency + a network dependency inside the
  hot path.
- **P2-4 · Python runtime mismatch:** venv is 3.12.3, `runtime.txt` declares 3.12.10.
- **P2-5 · Two divergent requirements files** (root vs `backend/`) list different
  packages (root has `pymongo`/`gunicorn`/`pydantic-settings`; backend/ doesn't).

### Licensing risk (called out separately — it's a business risk, not a bug)

- **Ultralytics 8.4.90 is AGPL-3.0** (verified in dist-info METADATA), and the bundled
  `yolo11n-seg.pt` weights (repo root, ~6 MB) fall under the same terms. AGPL's network
  clause obliges you to offer complete corresponding source to users of a networked
  service, or hold an Ultralytics Enterprise License. Everything else in the stack is
  permissive (torch BSD, transformers/groq Apache-2.0, opencv Apache-2.0). **This is
  the single copyleft exposure** and should be a conscious decision (enterprise license,
  or swap YOLO for a permissively-licensed detector) before commercial launch.

---

## 4. Integration seams & dependency constraints

### 4.1 The five target roles → what exists today

| Target role (VISION-STACK-001) | Current implementation | Gap / debt |
|---|---|---|
| **DomainProfile** | `fashion_clip.classify_domain` (fashion/arch/photo/food/product), `_DOMAIN_PROMPTS` (`fashion_clip_service.py:43-49`); `post.domain` persisted (`posts.py:586`) | **Implicit, not an object.** No registry mapping domain→(segmenter, annotator, lens) — the fashion path is hard-wired via `_resolve_is_fashion` boolean + `if is_fashion` at `posts.py:626`. Formalize into a profile/registry. |
| **SegmenterAdapter** | Two concrete segmenters + `merge_with_precedence`; each is a module with `is_available()`/`segment_image_bytes(bytes)→List[dict]` | **Two implementations, no shared interface type.** They already share a de-facto contract (bytes→normalized region dicts, three-way None/[]/list). Extract a Protocol; register per domain. This is an adapter boundary, **not** a rewrite. |
| **MaskRefiner** | **MISSING.** No SAM2, no tap-to-refine, no mask upgrade path | Planned as serverless/on-demand (`pre-build-decisions.md` B5: "on-demand tap, never dense-on-upload"). New adapter; feeds `Region.polygon`. |
| **SemanticAnnotator** | `vision_service.decompose_regions` (Groq VLM, labels+parent+box+material) + `fashion_clip.label_region` (zero-shot part/attributes) | Two annotators, no shared interface; VLM also (over)produces geometry — an annotator should annotate, not invent boxes (P1-5). Fashionpedia attributes = future annotator. |
| **EmbeddingAdapter** | `fashion_clip.embed_image` + `region_embedding_service` sidecar (upsert/get/search, model+dim persisted) | **Fully built, zero data (P0-2).** Search is brute-force cosine over a Mongo scan (`search_similar:102`), B-tree indexes only — **not** Atlas Vector Search/FAISS. Fine at 50 regions; needs a real index before scale. |

### 4.2 The smallest clean interface

All five roles already funnel through **narrow, uniform call-sites**, so the seam is
an *interface extraction*, not surgery:

- **Segmenter Protocol** — `is_available() -> bool`, `segment(bytes) -> list[Region] |
  None` (the two services already match this). A `DomainProfile` object holds an
  ordered list of segmenters + the precedence rule; `detect_regions` asks the profile
  instead of branching on `is_fashion`. Insertion point: `posts.py:624-647`.
- **Annotator Protocol** — `annotate(crop|image, region) -> {label, part,
  attributes, material}` with **no geometry authorship**. VLM and FashionCLIP become
  two implementations; MaskRefiner is a separate `refine(region, image) -> polygon`.
- **ModelManager + queue** — wrap the singleton loaders (`segmentation_service._load_model`,
  `fashion_segmentation_service._load`, `fashion_clip._load`) behind one manager that
  owns device selection and an `asyncio.Semaphore`; serialize the `to_thread` calls at
  `posts.py:626-629` through it. No route/schema/geometry change required (P1-3).
- **EmbeddingAdapter** already *is* the interface (`embed_image` + sidecar); only the
  backing index changes when scale demands.

### 4.3 Dependency constraints for candidate integrations

- **torch is a CPU-only wheel** (`2.13.0+cpu`, `cuda_available=False`) — the local
  GTX 1650 is idle. SAM2/Fashionpedia on GPU need either a CUDA torch build locally or
  the already-decided **serverless-first** path (`pre-build-decisions.md` B1,
  `infra-hardware-plan.md`). Don't mix a CUDA rebuild into the unpinned env (P1-1).
- **SAM2 on Apple MPS is broken** (documented in `infra-hardware-plan.md`) → SAM2 and
  video are serverless regardless of machine.
- **Pin before you add.** Introduce a pinned lockfile *first*, then add SAM2/Fashionpedia
  behind the `requirements-ml.txt` optional group with its own CPU/GPU index.
- **AGPL** (§3) constrains shipping YOLO in a commercial network service.

---

## 5. Hardware profile still required from the user

Detected read-only on this dev box: **GPU** NVIDIA GeForce GTX 1650 (present);
**CPU** AMD Ryzen 5 5600H, 12 logical cores; **torch** CPU-only build (GPU unused).
Still needed from you:

1. **GTX 1650 VRAM** — almost certainly 4 GB, but confirm. It bounds what runs
   locally: SAM2-tiny (image-only) borderline; SAM2 base+/large and Fashionpedia at
   throughput do **not** fit → serverless.
2. **Deploy-target hardware** — does production have *any* GPU, or is it the AWS
   CPU-only plan from `infra-hardware-plan.md`? This decides whether *any* heavy model
   can run in-process vs. must be a serverless call.
3. **M4 Mac Mini status** — the plan assumes a 16 GB M4 "in ~1 month" as primary dev.
   Has it arrived? It changes local Fashionpedia feasibility (but not SAM2, MPS-broken).
4. **Serverless account chosen** — Modal / Replicate / Runpod? (B1 settled on
   serverless-first but no provider is wired in code yet.)
5. **Do you hold, or intend to buy, an Ultralytics Enterprise License** — or should we
   plan a permissive-detector swap? (§3.)
6. **Groq account model access** — which vision models does your key actually list?
   (Needed to un-block re-dissection — see §7 / P1-5 and the delta below.)

---

## 6. Exact delta: existing capability → VISION-STACK-001 (Darshan)

The target is the vision-initiative "Darshan" stack (`architecture-lab/vision-initiative/`).
Mapping its intended capability against what's in the tree:

| Capability | Status | Evidence / gap |
|---|---|---|
| Coarse anchors (YOLO) | ✅ Built | `segmentation_service.py` |
| Garment segmentation (SegFormer-clothes, Phase 2a) | ✅ Built | `fashion_segmentation_service.py`, polygons + precedence merge |
| Polygon masks (single outer ring) | ✅ Built + rendered | producers + 4 frontend overlays; 12/50 regions have polygons |
| Multi-component polygons / holes | ❌ Missing | `List[List[float]]` = one ring; `RETR_EXTERNAL` + largest-contour only (`fashion_segmentation_service.py:182-185`) |
| Domain routing (fashion vs not) | ✅ Built (implicit) | `classify_domain`; **no** DomainProfile object/registry |
| Semantic annotation (VLM + zero-shot) | ✅ Built | `decompose_regions` + `label_region`; VLM currently also authors geometry (P1-5) |
| Fashionpedia attributes (294) / Phase 2b | ❌ Missing | planned serverless/M4; `attributes[]` empty from SegFormer by design |
| **Exact-mask refinement / SAM2 (MaskRefiner)** | ❌ Missing | no code; planned on-demand-tap (B5) |
| Embeddings (FashionCLIP) + sidecar | ✅ Built, **inert** | encoder + store + search all present; **0 vectors, 0 embedding_ids** (P0-2) |
| Vector index at scale | ❌ Missing | brute-force cosine scan; B-tree indexes only, no Atlas/FAISS |
| Disciplined model orchestration (ModelManager, queue, timeouts, device) | ❌ Missing | singletons + unbounded `to_thread`, CPU-pinned (P1-3) |
| Serverless GPU path | ❌ Missing | decided (B1) but no provider client in code |
| EXIF-correct decode | ❌ Missing | P0-1 |
| Video spike (keyframe→SAM2 track) | ❌ Missing | planned (B6), out of scope for image loop |
| Re-dissection un-blocked | ❌ Blocked | Groq `llama-4-scout` 404 → `decompose_regions` returns `[]` silently; 3 slivers still stored |
| Grounds/Percepts identity (Differential) | ✅ Built, decoupled | free-form dicts via `PATCH`, kept out of `region_annotations` — safe from re-dissection |

**In one line:** the *decision-light* layer (segment, label, embed, route, render) is
**built**; the *heavy/exact* layer (SAM2 mask refinement, Fashionpedia attributes,
GPU/serverless orchestration, vector index) is **absent**; and there is a correctness
tax (EXIF, pinning, tests, timeouts, dead embeddings) to pay before extending.

---

## 7. Recommended first build slice (no implementation here)

Ordered so each slice de-risks the next and none breaks Region/Ground/Percept identity.

1. **Correctness foundation (before any model work).** Central EXIF-correct decode
   (P0-1); a pinned lockfile + resolve the double-OpenCV (P1-1/P1-2); first
   polygon/mask + embedding round-trip tests (P1-4). Cheap, high-leverage, and every
   later slice depends on the geometry being right.
2. **Un-block + backfill what's already built.** Confirm a working Groq vision model
   id (§5.6) to un-block re-dissection; run the embedding backfill so the sidecar is
   non-empty (P0-2). This turns two already-built-but-inert systems (fine decomposition,
   taste vectors) live *without new models*.
3. **Extract the adapter seam (no behavior change).** `SegmenterAdapter` Protocol +
   `DomainProfile` registry replacing the `is_fashion` branch; strip geometry authorship
   out of the VLM annotator (make top-level VLM boxes suggestions, not truth — P1-5).
   Pure refactor, guarded by slice-1 tests.
4. **ModelManager + queue** around the singleton loaders: one device policy, a
   concurrency semaphore, an inference timeout (P1-3). Also the natural home for a
   serverless call later.
5. **MaskRefiner (SAM2) as an on-demand adapter** — tap-to-refine a chosen region to an
   exact mask, serverless GPU, writing `Region.polygon` (upgrade-in-place, ID
   preserved). This is the first genuinely *new* capability, and it lands cleanly only
   because slices 1–4 gave it a decode contract, a test net, an adapter slot, and an
   orchestration home.

**Not now:** Fashionpedia attributes, multi-component polygons/holes, a real vector
index, and video — each waits on either the M4/serverless hardware decision (§5) or a
scale threshold this 50-region corpus is nowhere near.

### Migration / provenance note (Q8)

- **Refinable in place, IDs preserved:** all 50 regions (re-run annotation/embedding
  keyed by existing `id`; `make_embedding_id` is deterministic so backfill is
  idempotent). The 3 degenerate slivers need re-dissection, not migration (original
  model boxes were never stored — see REGION-GEOMETRY-001).
- **What re-dissection destroys today:** `detect_regions` wholesale-replaces
  `region_annotations`, carrying over only `prioritised/weight/user_note` + creator
  rows (`posts.py:677-694`). It does **not** touch Grounds/Percepts/Mentions (separate
  fields) or the embedding sidecar (separate collection) — those survive. But auto
  polygons and `embedding_id` linkage on auto regions are dropped.
- **Provenance fields to add before model changes:** a per-region `revision`/`updated_at`
  + `model_version` (segmenter/annotator/embedding model + version), and a per-region
  **upsert** endpoint so re-running one model doesn't rewrite the whole array. Without
  these you cannot tell which model produced which region, nor refine one region
  without risking the rest.

---

*Investigation only. No code, config, model, or data was modified. Read-only DB census
run via `scratchpad/count_regions.py` (find/aggregate only). Five parallel read-only
code investigators + direct service-layer review; all file:line references verified
against the working tree at commit `314cf94` + main merge on `feat/vision-differential`.*
