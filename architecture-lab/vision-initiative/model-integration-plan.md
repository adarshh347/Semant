# Model-integration plan — the concrete stack

**Status:** research + plan. No code. Feeds Track B (segmentation) and Track C (Aletheia/vectors), referenced by `01-strategy-two-sided.md`.
**Purpose:** turn "adopt Fashionpedia / FashionCLIP / SAM" from a suggestion into a **concrete, staged integration** with roles, deploy shape, cost/latency, and where each model lands in the pipeline. Answers Adarsh's "new set of model integrations needs a proper updated plan."

---

## 0. The stack at a glance

| # | Model | Job in Darshan | Replaces / adds to | Deploy | Cost | Verdict |
|---|---|---|---|---|---|---|
| 1 | **YOLO11n-seg** (current) | fast coarse person/object anchor | keep as cheap first pass | on-device, ~6MB | free | **Keep** as anchor only |
| 2 | **Fashionpedia Attribute-Mask-RCNN** *(or DeepFashion2 seg)* | garment part + attribute segmentation (the domain spine) | replaces COCO-only `_category` for fashion | server (GPU pref) | model hosting | **Adopt** — core upgrade |
| 3 | **SAM2** | class-agnostic masks for arbitrary regions (drape, texture, atmosphere zones) + **video** | adds "beyond objects" + reel path | server (GPU) | heavier | **Adopt, phased** (image first, video later) |
| 4 | **FashionCLIP** | image+text vectors → taste-vector, zero-shot attribute labels, retrieval/RAG | upgrades catalog from counts → vectors; feeds Track C | server (CPU-OK for inference) | light | **Adopt early** — highest ROI/effort |
| 5 | **Vision-LLM (Groq llama-4-scout, current)** | felt-reading, naming ambiguous parts, story | keep as the *semantic/aesthetic* layer | API | per-call | **Keep**, re-role (see §3) |

**One-line division of labour:** *geometry* from YOLO+Fashionpedia+SAM2, *vectors* from FashionCLIP, *meaning/prose* from the vision-LLM. Today the LLM does all three badly; the plan gives each job the right tool.

---

## 1. The pipeline, rewired

```
image ─┬─ YOLO11n-seg ............ coarse anchors (person/object)         [on-device, ~ms]
       ├─ Fashionpedia Mask-RCNN . garment parts + attributes (fashion)   [server]
       ├─ SAM2 (prompted) ........ arbitrary regions: drape/texture zones [server, on-demand]
       │                            (prompts can come from taps or anchors)
       ▼
   regions[]  ── FashionCLIP ───► per-region vectors + zero-shot attribute labels  [server, light]
       │                            └─► taste graph (Track A embedding field)
       ▼
   vision-LLM (Aletheia) ── felt-reading per part, lenses, story  ── RAG over taste graph (FashionCLIP)
```

Key changes vs today:
- Fashionpedia replaces the hand-written Sūkṣma `garment` vocabulary (`vision_service.py:644-650`) with an **expert ontology + a real segmenter** — the LLM stops *guessing* garment part boxes (`vision_service.py:547-565`) and instead *reads meaning* over real masks.
- FashionCLIP makes taste a **vector**, upgrading `anatomy_catalog_service`'s frequency+intensity counts (`anatomy_catalog_service.py:100-136`) into a queryable space (similarity, match-scores, RAG).
- SAM2 covers what no class list can (the fold, the fall of light) and later the video/reel path.

---

## 2. Staged adoption (lowest-risk order)

**Phase 1 — FashionCLIP first (cheapest, highest leverage).**
- No training; HF weights. Add an inference endpoint that returns a vector + top-k zero-shot attribute labels per region.
- Immediately: (a) better semantic labels than COCO, (b) the taste-vector for the graph, (c) RAG retrieval for grounded writing. Validates the "taste as vector" claim with the least deploy weight.
- *Track A needs:* an optional `embedding` field/ref on `Region` (§Track A addendum).

**Phase 2 — Fashionpedia segmentation (the domain spine).**
- Stand up Attribute-Mask-RCNN (or DeepFashion2 seg if lighter/better in practice — evaluate both; note **FashionFail** documents real OOD failure cases, so budget for a fallback to LLM naming when confidence is low).
- Maps its 27 categories / 19 parts / 294 attributes into the Track A `category/part/attributes[]` fields.
- Roles: gives *true part masks*; the LLM now only *reads*, doesn't *locate*.

**Phase 3 — SAM2 for arbitrary regions (image).**
- Prompted by user taps (Track D pick) or by anchors, to mask non-catalog regions (drape, texture patch, light field). Class-agnostic → fills the "not just objects" purpose.

**Phase 4 — SAM2 video + replay signals (the reel path, B2C/Track F).**
- Promptable video segmentation with memory-bounded streaming makes "which part of which frame" real; pair with replay/dwell signals for the audience taste capture. **Heaviest; explicitly later.**

---

## 3. Re-roling the vision-LLM (keep, don't discard)

The LLM stops being the geometry guesser and becomes the **aesthetic/semantic brain**:
- **Felt-reading per part** (Aletheia) over real masks — its actual strength.
- **Naming ambiguous/low-confidence regions** the CV models miss or when Fashionpedia fails OOD.
- **Story generation** (Sutradhar), now grounded via FashionCLIP-RAG.
- Domain detection (fashion vs architecture) can be a cheap FashionCLIP zero-shot call *or* an LLM call — evaluate in Track B.

---

## 4. Deploy & cost reality (for Track B to detail)

- Current backend runs YOLO on-device, LLM via Groq API, and notes a Render deploy where torch/ultralytics may be absent (`segmentation_service.py:8-11` fallback). **Fashionpedia + SAM2 need GPU-ish serving** — this is a real infra step: a small GPU inference service (or a hosted endpoint / Replicate-style) the backend calls, with the on-device YOLO + LLM as graceful fallback when the seg service is down. Track B must produce the cost/latency table and the fallback ladder.
- FashionCLIP inference is light enough to run alongside the API backend; embeddings cache per region (immutable once computed) — cheap after first pass.
- Region caps, coarse→fine on demand, and confidence thresholds (already patterns in the code) carry over.

---

## 5. What each track takes from this doc
- **Track B** owns §1–§4: benchmark Fashionpedia vs DeepFashion2, the SAM2 prompt strategy, the deploy/fallback ladder, the domain-detection call.
- **Track C** owns FashionCLIP-as-taste-vector + RAG grounding, and re-roling the LLM to reading.
- **Track A** must add the `embedding` ref + `attributes[]` + `actor/source` fields so the outputs above have a home.
- **Track F** owns Phase 4 (video/reel) + the audience-signal capture.

## Sources
- [Fashionpedia](https://fashionpedia.github.io/home/) · [paper (arXiv 2004.12276)](https://arxiv.org/abs/2004.12276) · [FashionFail — OOD failure cases (arXiv 2404.08582)](https://arxiv.org/pdf/2404.08582)
- [DeepFashion2](https://github.com/switchablenorms/DeepFashion2) · [FashionCLIP (HF)](https://huggingface.co/patrickjohncyh/fashion-clip) · [FashionCLIP (GitHub)](https://github.com/patrickjohncyh/fashion-clip)
- [SAM 2 (arXiv 2408.00714)](https://arxiv.org/html/2408.00714v1) · [SAM2 overview](https://www.emergentmind.com/topics/segmentation-anything-model-2-sam2)
