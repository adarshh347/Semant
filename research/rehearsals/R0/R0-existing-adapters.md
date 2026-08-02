# R0 — Existing adapters the harness may reuse (no duplicate pipelines)

The instrumented harness (R1+) must call **existing** read paths, never re-implement a model
pipeline. This is the inventory of stable seams, with the rule that none may grant semantic output
authority over canonical geometry.

## Image + geometry
- **Image fetch/decode:** `posts.py::_fetch_post_image_cached(post_id, post)` (one-image cache) or
  `_fetch_post_image`. Read-only.
- **Geometry projections:** `mask_geometry.py` — `rle_decode`, `rle_bbox_norm`, `mask_to_crops`
  (identity `alpha_crop` + `context_crop`), `canonicalize_geometry`. Pure; the source of the E1
  identity/context crops.
- **Evidence crops:** `evidence_projection.project_region(region, image)` → identity + context
  crops + deterministic `projection_hash`. Reuse for "context breathing" trials without new code.

## Detection / refinement (GPU, via ModelManager — governs residency + unload)
- **Segment:** `YoloSegmenterAdapter` (`Capability.SEGMENT`). **Refine:** `Sam2RefinerAdapter` /
  `refine_session.preview(image_bytes, {box|points}, base_id, base_rev)` (cached image embedding —
  the seam F3 used for box→mask). **Arch:** `SegFormerAdeAdapter`. **Domain route:**
  `fashion_clip_service.classify_domains`.
- Never call these for *rehearsal* geometry writes — instrumented mode reads/derives only.

## Semantic reading (geometry-forbidden)
- `semantic_provider.SemanticProvider().interpret(image_b64, allowed_ids, prompt)` → typed
  `SemanticResponse` (candidate-id bound, `extra="forbid"`). Reuse for any "ask the image" trial;
  output is a proposal, never geometry.

## Embeddings / retrieval (research evidence, never truth)
- **Encode:** `dinov2_service.get_encoder()` (`encode_image`, `pool_region`, `encode_crop`);
  `fashion_clip_service.embed_image`. **Store:** `region_embedding_service`
  (`make_embedding_id`, `upsert_embedding`, `search_similar(space=…)`, `is_stale`,
  `cosine_same_space` — raises across spaces).
- **Route + search:** `retrieval_service.route(...)`, `find_similar_service.find_similar_for_region`
  (on-demand index, staleness, cross-post neighbours). This is the "Madeleine return" / constellation
  recall seam — call it, don't rebuild it.
- **Orchestration:** `evidence_embedding_service.embed_post_regions` (whole-image once + mask-pool).

## Ground / Percept / recall (frontend — for prototype mode only)
- `differential/grounds.js` (`makeGround`, `groundFromRegion`, `resolveGround`, bbox helpers);
  `state/perceptMentions.js` (`makeExpressionPercept`, `upsertPercept`, Mention helpers,
  `mentionsFromBlocks`); `differential/recall.js` (`buildRecallScript`, `useRecallPlayer`);
  `state/regionStore.js` (persist/persistMeta PATCH). Prototype trials reuse these hooks — no second
  percept/recall implementation.
- **Writer:** `blocknote/Manuscript.jsx` (`insertRegionChip`, `insertPartBlock`, RefPicker),
  `blockConvert.js` (lossless `text_blocks` ⇄ BlockNote). The `data-*` chip contract is the Mention's
  only durable form — extend it, don't fork it.

## Writer LLM + grounding (verify health first — see risks)
- `editor_llm_service` (`generate_post_suggestion`, `chat_with_vision`, `rewrite_with_vision`) and
  `anuranana_service.build_context_pack` / `grounding_for_image`. **Caveat:** targets Groq
  `llama-4-maverick` (vision) — likely dead (Vision D found Groq dropped vision). Any rehearsal that
  needs generated prose must first confirm this path or route through the OpenRouter semantic
  provider instead. Do **not** silently repoint.

## Backend access + recovery scaffolding
- Collections via `backend.database` (module-level: `post_collection`, `region_embeddings_collection`).
- **Recovery/ledger (F):** `vision_recovery` (`backup_scope`, `restore_post`, `Ledger`,
  `curator_identity_hash`/`curator_only_hash`), `vision_capabilities` (skip guard),
  `indexing_service` (resumable, `plan_batch`). Reuse the ledger/backup pattern if any trial ever
  needs to write — but R1–R4 write only to `runs/` on disk.

## Rule
Adapters are called through their existing signatures in imaginative/instrumented mode. If a
rehearsal seems to need a *new* pipeline, that is a **finding** (a contract/service candidate), not a
license to build it in the harness.
