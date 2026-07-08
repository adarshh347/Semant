# Track B — Segmentation intelligence & optimality (research + plan only)

**Read first:** `00-brief.md`. **Do not edit code.** Write `responses/track-B-segmentation.findings.md`. You MAY use web search for model options.

## Mission
Today's segmentation is YOLO11n-seg = COCO objects only (person/handbag), plus an LLM semantic layer. The purpose needs **domain-aware** decomposition: fashion, architecture, photography — and not just objects but **textures, materials, light, atmosphere**. Plan the intelligent pipeline.

## Read
- `backend/services/segmentation_service.py` (YOLO anchors + polygons, `_category`).
- `backend/services/vision_service.py` — `detect_regions`, `decompose_regions`, the Sūkṣma per-mode vocabularies (garment/body/texture/material/composition), `SOOKSHMA_PROMPT`.
- `RegionDetectRequest` (mode/lens/coarse_only).

## Answer
1. **Division of labour:** what should YOLO (geometry/anchors/polygons) do vs the vision-LLM (semantic naming, textures, atmosphere)? Where is each strong/weak? Is COCO YOLO even the right anchor for fashion/architecture?
2. **Domain-awareness:** how to detect the image's domain (fashion vs architecture vs photography) and pick the right decomposition vocabulary automatically. Extend the Sūkṣma modes.
3. **Beyond components:** how to segment/name non-object aspects — textures, materials, light quality, colour fields, atmosphere/mood zones. Which of these are true spatial regions vs image-global attributes (and how to represent each).
4. **Model options** (web-search allowed): alternatives/additions to YOLO for open-vocabulary or domain segmentation (e.g. SAM/SAM2 for class-agnostic masks, open-vocab detectors, CLIP-guided regions) — with cost/latency/on-device trade-offs vs the current free on-device YOLO.
5. **Optimality:** batching, caching, region caps, coarse→fine on demand, confidence thresholds — keep it fast and cheap.
6. **Feed-forward:** what structured output best feeds Track C (Aletheia) and the inline writing AI.

## Output contract → `responses/track-B-segmentation.findings.md`
Current-pipeline map · YOLO-vs-LLM division · domain-detection plan · texture/material/atmosphere representation · model options table (with trade-offs) · optimality plan · questions for Adarsh.

---

## Addendum (v2 strategy — 2026-07-08)
Read `model-integration-plan.md` — it is now the spine of this track. Don't re-discover the landscape; **plan the concrete adoption**: benchmark **Fashionpedia Attribute-Mask-RCNN vs DeepFashion2** for garment parts+attributes; **SAM2** for arbitrary regions (drape/texture/atmosphere) and the later **video/reel** path; **FashionCLIP** as semantic labeler + vectorizer; keep YOLO as cheap anchor and the vision-LLM re-roled to *reading only*. Deliver the **deploy/cost/latency table + fallback ladder** (GPU seg service with on-device YOLO+LLM fallback), and the **domain-detection** call (FashionCLIP zero-shot vs LLM). Note FashionFail OOD failures → design a low-confidence fallback.
