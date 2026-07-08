# Track B — Segmentation intelligence & optimality: findings

**Mode:** deep read + plan + web research. No app code changed.
**Lens (Purpose→Structure):** Drishya reads an image *part by part* and says *how each part feels*. That needs **domain-aware geometry** (real garment parts, arbitrary drape/texture zones — not COCO objects) feeding a **re-roled LLM that only reads, never locates**. Today the LLM does geometry *and* meaning, badly at the first.
**Grounding:** line refs current as of `b013689`. Pipeline cross-verified by direct read of `segmentation_service.py`, `vision_service.py`, `routers/posts.py` (`detect-regions` `:479-553`), `schemas/post.py` (`RegionDetectRequest` `:114-120`). Output must populate the locked v2 `Region` schema (`responses/track-A-datamodel.findings.md` §v2.2): `category` (coarse, catalog-critical), `part`, `attributes[]`, `material`, `box`, `polygon`, `confidence`, `detector`; vectors out-of-row via `embedding_id`.
**Within locked context** (`decisions-darshan.md`): phased full-stack (FashionCLIP → Fashionpedia → SAM2); video IN scope this cycle; YOLO stays cheap anchor; LLM re-roled to reading/naming; image loop must stay independently shippable.

---

## 0. Headline (up front)

**Rewire the pipeline from "YOLO anchor + LLM guesses everything" to "a domain-routed geometry stack (YOLO → Fashionpedia/SAM2) + FashionCLIP vectors + LLM-as-reader."** Three moves, in the locked phase order:

1. **FashionCLIP first** — cheapest, highest leverage. It is *not* a segmenter; it is the **domain router + zero-shot labeler + taste-vectorizer**. Ship it before any heavy seg model: it immediately (a) picks the decomposition vocabulary (fashion/architecture/photography), (b) labels/attributes each existing region better than COCO, (c) fills `embedding_id`. Runs CPU-OK alongside the API. **This is the one phase with no infra cost.**
2. **Fashionpedia (Attribute-Mask-RCNN / Fashionformer) second** — the domain spine for fashion. It replaces the LLM's *hallucinated* garment-part boxes (`vision_service.py:547-565`) with a real 27-category / 294-attribute segmenter. Needs GPU serving → the first real infra step. **Benchmark it against DeepFashion2 before committing** (§4).
3. **SAM2 third (image), then video** — class-agnostic masks for what no catalog names: the fold, the fall of light, an atmosphere zone; then the reel path. Heaviest; GPU-mandatory; **prompted, never dense** (§5).

Throughout: **YOLO11n-seg stays as the free on-device coarse anchor and the fallback floor**; the **vision-LLM stops estimating boxes** and becomes the reader/namer for low-confidence and non-catalog regions. FashionFail's documented OOD failures make the **low-confidence → LLM-naming fallback mandatory, not optional** (§7 ladder).

Everything below keeps the coarse `category` field stable (catalog-critical) and writes new geometry into the *same* normalized `region_annotations` array Track A locked.

---

## 1. Current-pipeline map (what exists, grounded)

Two-stage anatomy, orchestrated in `POST /posts/{id}/detect-regions` (`posts.py:479-553`):

**Stage 1 · STHŪLA (coarse anchors).**
- Primary: `segmentation_service.segment_image_bytes` (`:55`) — Ultralytics **YOLO11n-seg**, on-device CPU (`device="cpu"` `:67`), `conf=0.30`, `max_regions=12`, `retina_masks=True`. Emits `{id:"seg_N", label:<COCO>, category, box{x,y,w,h}norm, polygon[[x,y]]norm (≤48 pts, `_simplify` `:47`), confidence, description}` (`:92-100`), sorted by box area (`:103`).
- `_category` (`:37-44`) collapses **80 COCO classes → 3 buckets**: `person→figure`; `{tie,handbag,backpack,umbrella,suitcase}→garment`; everything else→`object`. **This is the whole domain vocabulary today — and it is COCO, not fashion.**
- Fallback: if ultralytics/torch absent or nothing found (`:510-513`), `vision_service.detect_regions` (`:372`, cap 10) becomes the anchor source; `source` flips `"segmentation"→"vision"`.
- Deps lazy-imported + model cached (`:29-34`); `segment_image_bytes` returns `None` on any failure → caller falls back (`:105-107`). **Render deploy likely has no torch → vision-LLM is the de-facto anchor in prod.**

**Stage 2 · SŪKṢMA (fine parts).** `vision_service.decompose_regions` (`:446`, cap 16) — the **vision-LLM (`llama-4-scout-17b`, `:26`)** subdivides each anchor semantically, steered by `mode` + free-text `lens`. Six hand-written vocabularies in `MODE_FOCUS` (`:635-673`): `general | garment | body | texture | material | composition`; prompt `SOOKSHMA_PROMPT` (`:676`) with fine categories `garment|garment-detail|body-part|hair|skin|accessory|texture|material|edge|light|plane|object|other` (`:689-690`) and a `material` field (`:561`). Boxes are **model-estimated** (`:562`) — no detector grounds them. Router links each fine part to its anchor via `_match_parent` (`:529`), clips into parent box (`:532`), sets `depth:1`.

**Merge & persist** (`:535-552`): `regions = anchors + fine`; curator fields (`prioritised/weight/user_note`) preserved by matching `id`; saved to `region_annotations`. `RegionDetectRequest` (`schemas:114-120`) exposes `mode|lens|coarse_only`.

**Aletheia** (`brainstorm_image` `:269`, `ALETHEIA_PROMPT` `:594`) is a **separate, whole-image** call (3 lenses + MCQ forks) — not region-linked today. That link is Track C's; Track B just needs to hand it region structure (§9).

### The three weaknesses this track fixes
| Weakness | Evidence | Fix |
|---|---|---|
| **Vocabulary is COCO, not domain** | `_category` `:37-44` → 3 buckets; only 5 COCO classes map to "garment" | Fashionpedia parts/attributes (§4); domain routing (§3) |
| **Fine geometry is hallucinated** | `decompose_regions` boxes model-estimated `:562`; "Boxes are model-estimated" `:467` | Real masks from Fashionpedia + SAM2; LLM stops locating (§2) |
| **No taste vector / no attributes** | nothing writes `embedding_id`/`attributes`; `category` is 3-valued | FashionCLIP vectorizer + zero-shot attributes (§2, §9) |

---

## 2. Division of labour — YOLO vs CV models vs LLM

**Principle (locked): *geometry from CV, vectors from FashionCLIP, meaning/prose from the LLM.*** Today the LLM does all three and is weakest at geometry.

| Job | Owner | Why it's the right tool | Where it's weak → who covers |
|---|---|---|---|
| **Coarse anchor** (is there a person/object? where, roughly) | **YOLO11n-seg** (keep) | free, on-device, ~ms, real polygons; already integrated | COCO-only; misses non-COCO domains → Fashionpedia/SAM2/open-vocab fill |
| **Garment parts + attributes** (collar, sleeve, hem; 294 attrs) | **Fashionpedia Attr-Mask-RCNN** (add, GPU) | expert 27-cat/294-attr ontology + real masks; SOTA (Fashionformer) | OOD failure (FashionFail) → low-conf falls to LLM naming |
| **Arbitrary regions** (drape, texture patch, light field, atmosphere zone) | **SAM2** (add, GPU, prompted) | class-agnostic masks for what no class list names; + video | no semantics (masks only) → LLM/FashionCLIP name them |
| **Taste vector + zero-shot labels + domain routing** | **FashionCLIP** (add, CPU-OK) | image+text embeddings; labels without training; cheap | not a localizer → pairs with the segmenters above |
| **Reading / naming ambiguous parts / felt-meaning / prose** | **vision-LLM** (keep, **re-roled**) | genuine strength: aesthetic/semantic reading | must stop estimating boxes → geometry comes from CV now |

**Is COCO-YOLO the right anchor?** For **fashion**: only as a cheap *person/figure* locator — its garment vocabulary is 5 classes, useless for parts, so Fashionpedia supersedes it there. For **architecture/photography**: COCO barely applies at all → the anchor should be **SAM2 (prompted by taps/grid) or an open-vocab detector** (Grounding DINO / YOLO-World, §7), with YOLO kept only as the free floor when the GPU stack is down. **Recommendation:** keep YOLO as the always-on cheap anchor + fallback; route to the right domain model on top; never let COCO's 3-bucket `category` be the final word — it becomes a *fallback* category only.

---

## 3. Domain-detection — **FashionCLIP zero-shot, LLM as tiebreaker**

The pipeline must auto-pick a decomposition vocabulary (fashion vs architecture vs photography vs general). Two options:

- **FashionCLIP zero-shot** (recommended): one cheap embedding call, score the image against a small prompt set ("a fashion/outfit photo", "an interior/architecture photo", "a landscape/portrait photograph", "a product shot"). Returns a domain + confidence in ~one CPU inference. It's already the model we're adding in Phase 1, so **domain routing is free** — no extra model. Caveat: FashionCLIP is *fashion-tuned*, so it's sharp at "is this fashion?" but weaker at discriminating architecture-vs-photography; use a **general CLIP (ViT-B/32) or the LLM** for the non-fashion split.
- **LLM one-liner**: a cheap `analyze_image` classification call. More flexible vocab, but an API round-trip + cost per image; better as a **tiebreaker** when CLIP domain confidence is low (< threshold).

**Plan:** FashionCLIP/CLIP zero-shot picks the domain (cached per post); if confidence < τ, one LLM classification call decides; the chosen domain selects the `mode` vocabulary. **Extend `RegionDetectRequest.mode`** (`schemas:114-120`) from the current 6 flat modes to a **domain → mode tree**: `fashion → {garment, body, material, texture}`, `architecture → {structure, material, light, plane}`, `photography → {composition, light, atmosphere, subject}`, plus `general`. `mode` stays an override; domain-detection just sets its default. This is additive to the schema Track A locked (mode is request-only, not stored on `Region`).

---

## 4. Fashionpedia vs DeepFashion2 — benchmark plan (decide before adopting)

Both are standard fashion benchmarks; they optimize different things. Grounded facts:

| | **Fashionpedia** | **DeepFashion2** |
|---|---|---|
| Classes | **27** (incl. fine parts: collar, sleeve, pocket) | **13** (whole garments) |
| Attributes | **294** localized attributes | none (categories + landmarks/pose) |
| Mask complexity | **most complex boundaries** of fashion datasets (best silhouettes) | simpler; zoomed-in single garments |
| Image framing | whole ensemble / full outfit | zoomed-in garment |
| SOTA baseline | **Fashionformer** (unified seg+attr, current SOTA); Attribute-Mask-RCNN (official baseline) | Match-RCNN (det+retrieval) |
| Best for | **part-level anatomy + attributes** (our exact need) | retrieval / re-ID / commercial matching |

**Verdict going in:** **Fashionpedia is the better fit** — the whole point is *parts + attributes* (`part`/`attributes[]` in the Region schema), and Fashionpedia is the only one with 294 localized attributes and part-level masks. DeepFashion2 is stronger for *retrieval* (a later taste-graph / taste-match feature, Track F), not part decomposition.

**But benchmark before locking**, because deploy weight matters:
1. **Harness:** run both on a held-out set of ~50–100 *real Drishya posts* (the 4 posts/77 regions today + a curated fashion sample), plus a deliberate **OOD slice** (non-catalog, architecture, stylized) to reproduce FashionFail conditions.
2. **Metrics:** part-mask mAP + attribute F1 (Fashionpedia's own), **but weighted by what we actually render** — do the masks give *pickable, nameable* parts a curator recognizes? Add a qualitative "curator would tap this" score; segmentation quality that doesn't map to felt-parts is wasted.
3. **Cost axis:** model size, GPU VRAM, latency/image, cold-start — feed the §7 table.
4. **OOD behavior:** measure the false-confident rate on the OOD slice (FashionFail's finding: these models fail *confidently* out of distribution) → sets the fallback threshold τ in §7.
5. **Candidates to include:** Fashionformer (SOTA, unified — likely first choice), Attribute-Mask-RCNN (official, simpler to serve), and **Grounded-SAM / YOLO-World** as an *open-vocab* comparison for the non-fashion domains where neither fashion model applies.

Deliverable of the benchmark: one table → pick the fashion segmenter + confirm the open-vocab fallback for other domains.

---

## 5. SAM2 prompt strategy — image + video

SAM2 gives **class-agnostic masks** — exactly the "beyond objects" need (drape, texture, light, atmosphere zones). It has **no semantics** (masks only), so it always pairs with FashionCLIP/LLM for naming. It is **GPU-mandatory** (§7).

**Never run SAM2 in dense/"segment-everything" mode** — that's the expensive path and produces mask soup. Always **prompted**:

**Image:**
- **Anchor-prompted:** feed YOLO/Fashionpedia boxes as SAM2 box-prompts to *upgrade* coarse boxes into precise masks (refine, don't re-detect).
- **Tap-prompted (the Track D interaction):** a curator/audience tap becomes a point-prompt → one crisp mask on demand. This is the "pick → mask → comment → remember" loop, and it makes SAM2 **lazy/on-demand**, not a batch cost on every upload.
- **Grid-prompted (opt-in):** a coarse point grid only when the user explicitly asks "find more regions" — capped, coarse→fine.
- Name each SAM2 mask via FashionCLIP zero-shot (fast) or LLM (ambiguous); write `detector:"sam2"`, `polygon` from the mask, `category` from the namer.

**Video / reels (in scope this cycle):**
- SAM2's differentiator is **promptable video with memory** — mask an object/part in one frame, it **tracks across frames** (streaming, memory-bounded). This is what makes "which part of which frame is loved" real (the reel-slicing hook).
- **Strategy:** decode reel → sample keyframes (not every frame) → prompt SAM2 on a keyframe (tap or auto-anchor) → propagate masks forward → attach **replay/dwell signals** (Track F) to the tracked region, not the whole frame.
- **Reality (grounded):** SAM2 ~44 FPS streaming for simple single-object video, but **~13 FPS (Large, A40)** and **as low as 1.3–1.5 FPS with many point prompts**; ~5.5 GB VRAM. So video is **offline/async batch, GPU-served, keyframe-sampled** — never real-time in-request. Guardrail (locked): the **image loop must ship without video**; video is a separate async worker.

---

## 6. Texture / material / atmosphere — true spatial region vs image-global attribute

The purpose ("the fold of the fabric, the fall of light, the atmospheric melancholy") mixes three *different kinds* of thing. Representing them all as bounding boxes is wrong. Classify each:

| Aspect | Nature | Representation in the `Region` schema | Producer |
|---|---|---|---|
| **Material** (silk, denim, leather) | **property of a spatial part** | not its own region — the **`material` field** on the garment/part region (already exists `:561`) | Fashionpedia attr / FashionCLIP zero-shot / LLM |
| **Texture** (weave, sheen, wrinkle) | **spatial patch** (localizable) | a **region** with `polygon` (SAM2 mask), `category:"texture"`, `detector:"sam2"` — but only when a curator picks it (on-demand, §5) | SAM2 (mask) + LLM/FashionCLIP (name) |
| **Light / shadow** (the fall of light) | **spatial zone**, soft-edged | a **region**, `category:"light"`, SAM2 or LLM-estimated box; low-priority auto, better on tap | SAM2 / LLM |
| **Colour field / plane** (fg/mid/bg) | **spatial zone** | a **region**, `category:"plane"` (composition mode already has this `:668-672`) | SAM2 / LLM composition pass |
| **Atmosphere / mood** (melancholy) | **image-global, NOT spatial** | **NOT a region.** Belongs to **Aletheia's whole-image reading** (`brainstorm_image` lenses `:594-631`) — an image-level attribute, not a box | LLM (Aletheia, Track C) |

**Key call:** *atmosphere/mood is image-global* — forcing it into a box is the current LLM's temptation (`MODE_FOCUS["composition"]` half-does this). Keep felt-atmosphere at the **image level** (Aletheia), keep **material as a field**, and only **texture/light/plane become spatial regions — and only on demand (tap-prompted SAM2)** so we don't flood every image with soft-edged low-value boxes. This directly serves Track D's "reveal many segments without mess."

---

## 7. Model options — deploy / cost / latency + fallback ladder

**Grounded comparison** (web-sourced; verify exact numbers in the §4 benchmark):

| Model | Job | Deploy | VRAM / size | Latency | Cost | Verdict |
|---|---|---|---|---|---|---|
| **YOLO11n-seg** (current) | coarse anchor | **on-device CPU** | ~6 MB | ~ms; ~1145× faster than SAM2-b on CPU | **free** | **Keep** — cheap anchor + fallback floor |
| **FashionCLIP** (ViT-B/32) | vectors + zero-shot labels + domain routing | **CPU-OK**, alongside API | ~600 MB | ~10s–100s ms CPU/region | light; **no GPU** | **Adopt Phase 1** — highest ROI/effort |
| **Fashionpedia Attr-Mask-RCNN / Fashionformer** | garment parts + 294 attrs | **GPU** (or hosted/Replicate) | server-class | ~sub-sec–seconds/image GPU | model hosting | **Adopt Phase 2** — after benchmark |
| **SAM2** (image) | class-agnostic masks, prompted | **GPU** | ~5.5 GB (Large) | 13–44 FPS; **1.3 FPS w/ many prompts** | heavier | **Adopt Phase 3** — on-demand only |
| **SAM2** (video) | tracked masks for reels | **GPU**, async worker | ~5.5 GB+ | keyframe-batch, not real-time | heaviest | **Adopt Phase 4** — async, offline |
| **Grounding DINO / YOLO-World** (option) | open-vocab detection (non-fashion domains) | GPU (DINO) / edge-capable (YOLO-World) | mid | mid | mid | **Evaluate** as open-vocab fallback for architecture/photo |
| **vision-LLM** (llama-4-scout, current) | reading, naming, prose | API (Groq) | — | ~1–3 s/call | per-call | **Keep, re-roled** to reading/naming only |

**The fallback ladder (graceful degradation — this is the deploy contract):**

```
detect-regions(image, domain?)
  1. YOLO11n-seg on-device            → coarse anchors        [always; free]
  2. domain = FashionCLIP zero-shot   → pick vocabulary       [CPU]
  3a. fashion  → Fashionpedia seg     → parts + attributes    [GPU service]
  3b. other    → SAM2 / open-vocab    → arbitrary masks       [GPU service, prompted]
  4. FashionCLIP                      → embedding_id + labels [CPU]
  5. low-confidence OR OOD (FashionFail) OR GPU service DOWN
        → vision-LLM names/decomposes → LLM regions           [API fallback]
  6. everything down                  → YOLO anchors only     [floor]
```

- **GPU serving** = a small GPU inference service (self-host or hosted endpoint / Replicate-style) the FastAPI backend calls over HTTP; **on-device YOLO + LLM naming is the always-available fallback** when it's cold/down (the code already has the `segment_image_bytes → None → LLM` fallback wired at `posts.py:510-513` — extend the same pattern per rung).
- **FashionFail rung is mandatory:** these seg models fail *confidently* OOD, so gate on a confidence threshold τ (set from the §4 benchmark) — below τ, hand the region to the LLM to name rather than trust a wrong high-confidence label.
- **Cost control:** FashionCLIP embeddings are **immutable once computed** → cache per region (`embedding_id`), never recompute on edit. GPU seg runs **once per image at upload/detect**, not per view. SAM2 video is **async batch**, off the request path.

---

## 8. Optimality plan (fast & cheap)

Carry forward the patterns already in the code, extend for the new stack:

- **Caps** (keep): YOLO `max_regions=12` (`seg:55`), detect cap 10 (`vision:416`), decompose cap 16 (`vision:547`). Add a Fashionpedia part cap (~20) and a hard **total-regions cap** so Track D's reveal stays clean.
- **Coarse→fine on demand** (keep/extend): `coarse_only` (`RegionDetectRequest`) already skips Sūkṣma. Make **fine decomposition + SAM2 masks lazy** — run on tap/"reveal more", not on every upload. This is the single biggest cost lever + directly serves "reveal without mess."
- **Caching:** cache (a) FashionCLIP embeddings per region (immutable, keyed `embedding_id`), (b) domain classification per post, (c) Fashionpedia mask results per image hash (re-detect preserves curator fields by `id` `:539-550` — extend to preserve computed geometry too, so re-runs are cheap).
- **Batching:** batch FashionCLIP over all regions of an image in one forward pass; batch SAM2 video across sampled keyframes in the async worker.
- **Confidence thresholds:** YOLO `conf=0.30` (`:67`) stays; add Fashionpedia τ (from benchmark) gating the LLM fallback; drop regions with area < 0.01 (already done `:427,:551`).
- **Payload discipline:** keep `_simplify` polygon downsample (≤48 pts `:47`); **keep vectors out of the region doc** (Track A: sidecar `region_embeddings` by `embedding_id`) so `post_helper` responses stay light.
- **Async:** GPU seg and all video work run off the request path (background task / worker); the request returns YOLO anchors immediately and enriches when the GPU result lands (progressive reveal).

---

## 9. Feed-forward — what Track B hands Track C (Aletheia) + the writer

Track C turns regions into felt-readings and grounds the writer. Track B's structured output should give it:

1. **A populated `Region[]`** per the locked schema: `category` (coarse, catalog-critical), `part` (Fashionpedia slot), `attributes[]` (294-vocab), `material`, `box`+`polygon` (real masks), `confidence`, `detector` provenance, `parent_id`/`depth` hierarchy. This is the *what and where* Aletheia reads over.
2. **`embedding_id` per region** → the FashionCLIP taste-vector in the sidecar. This is what turns Track C's catalog from label-counts into **vector retrieval / RAG** (find similar parts across a curator's history to ground the writing). *(Attributes stay out of the frequency catalog — locked Q4; they power vector retrieval in Track C.)*
3. **A domain tag** per image (from §3) so Aletheia can pick **fashion-literate lenses** (silhouette, drape, era/reference, styling logic) instead of the generic 3 today (`ALETHEIA_PROMPT:594`).
4. **The region hierarchy** (anchor → fine parts via `parent_id`) so Aletheia can read at the right grain and the writer's `/part` slash-insert can cite a specific part.
5. **Confidence + `detector`** so Track C knows which regions are trustworthy geometry vs LLM-estimated (read cautiously).

**Boundary (clean):** Track B produces *geometry + labels + vectors + domain*. Track C owns *felt-meaning, lens selection, RAG, and the region↔Aletheia link*. Track A owns the *schema + embedding storage*. Track B does **not** decide dedup/precedence when two detectors overlap on the same image — that was **locked as Track B's problem** in Track A (v1 Q6), so it lands here: see Q6 below.

---

## Questions for Adarsh

1. **GPU serving path** — self-host a small GPU inference service, or a hosted/serverless endpoint (Replicate / HF Inference / Modal) the backend calls? This decides cost model (fixed GPU vs per-call) and latency (warm vs cold-start). I lean **hosted/serverless first** (no fixed GPU bill while data is tiny — 77 regions), self-host only when volume justifies it. Mirrors your Track-A "don't buy infra ahead of data" call.
2. **Fashion segmenter** — go in expecting **Fashionformer** (SOTA, unified seg+attr) as first choice with Attribute-Mask-RCNN as the simpler-to-serve fallback, and benchmark both on real Drishya posts? Or do you want a specific one locked without the bench?
3. **Non-fashion domains this cycle** — the locked wedge is fashion. Do architecture/photography get **real** domain models now (Grounding DINO / open-vocab), or just **SAM2 + LLM naming** (no dedicated model) until fashion is proven? I lean the latter — one deep domain first, others via the generic SAM2+LLM path.
4. **Dedup/precedence (inherited from Track A Q6)** — when YOLO + Fashionpedia + SAM2 overlap on the same image, what wins? Proposed rule: **Fashionpedia > SAM2 (tap) > YOLO** for garments; keep both only if IoU < τ; `detector` records provenance. Confirm this lives in Track B (it does per the lock) and that the rule is acceptable.
5. **SAM2 laziness** — confirm SAM2 masks + fine decomposition run **on-demand (tap / "reveal more")**, not on every upload. This is the main cost lever and shapes Track D's UX. (I strongly recommend on-demand.)
6. **Video scope this cycle** — how far? Full reel → keyframe → SAM2-track → replay-signal pipeline is real but the heaviest thing in the plan (async GPU worker). Do we build the **whole async video path now**, or land the **image loop + a video *spike*** (prove keyframe-track on one reel) this cycle and full pipeline next? The locked call is "video in scope"; I want to confirm depth vs a de-risking spike, given the "image loop stays independently shippable" guardrail.
7. **Atmosphere stays image-global** — confirm mood/atmosphere is an **Aletheia image-level reading, not a region** (§6), so we don't box the unboxable. (My recommendation; it also keeps the Visual pane clean.)

*Research + plan only — no app code touched. This plans the concrete adoption of the locked model stack onto the Track-A `Region` spine; the benchmark (§4) is the one open experiment before Phase 2. Sources below.*

---

### Sources
- [Fashionpedia dataset + ontology (arXiv 2004.12276)](https://arxiv.org/pdf/2004.12276) · [Fashionpedia API + Attribute-Mask-RCNN (GitHub)](https://github.com/KMnP/fashionpedia-api) · [Fashionpedia home](https://fashionpedia.github.io/home/)
- [Fashionformer — unified fashion seg+recognition SOTA (arXiv 2204.04654)](https://arxiv.org/pdf/2204.04654)
- [FashionFail — OOD failure cases (arXiv 2404.08582)](https://arxiv.org/html/2404.08582)
- [DeepFashion2 (CVPR 2019 PDF)](https://openaccess.thecvf.com/content_CVPR_2019/papers/Ge_DeepFashion2_A_Versatile_Benchmark_for_Detection_Pose_Estimation_Segmentation_and_CVPR_2019_paper.pdf)
- [SAM 2 (arXiv 2408.00714)](https://arxiv.org/html/2408.00714v2) · [SAM2 (GitHub)](https://github.com/facebookresearch/sam2) · [SAM 2 / speed & memory (Ultralytics)](https://docs.ultralytics.com/models/sam-2) · [SAM2 overview](https://www.emergentmind.com/topics/segmentation-anything-model-2-sam2)
- [FashionCLIP (HF)](https://huggingface.co/patrickjohncyh/fashion-clip) · [FashionCLIP (GitHub)](https://github.com/patrickjohncyh/fashion-clip)
- [Grounding DINO (GitHub)](https://github.com/idea-research/groundingdino) · [Zero-shot & open-vocab detection overview (CV-Tricks)](https://cv-tricks.com/how-to/understanding-popular-zero-shot-and-open-vocabulary-object-detection-models/)
