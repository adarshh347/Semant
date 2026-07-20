# VISION-E — Evidence embeddings & visual retrieval — increment report

**Branch:** `feat/vision-e-embeddings` (off `main` after PR #54) · **Date:** 2026-07-19 ·
**Gates:** E0–E6, all PASS.

## The one idea

Give confirmed visual evidence a **model-versioned, disposable representation** that supports
useful, inspectable retrieval without confusing similarity with truth. The Region's exact mask
stays the evidence identity; embeddings are rebuildable projections of it, and neighbours are
research the curator weighs — never facts, never auto-created links.

## Commits per gate

| Gate | Commit | Summary |
|------|--------|---------|
| **E0** | `317875f` | Versioned evidence-embedding contract on the ONE sidecar (role, space, hashes, invalidation) |
| **E1** | `a610d8f` | Canonical identity + context crops through `mask_geometry` |
| **E2** | `2c66427` | DINOv2 ViT-S/14 shared patch features + mask pooling, via ModelManager |
| **E3** | `f4f8e3b` | Retrieval spaces + query routing (DINOv2/FashionCLIP; OpenCLIP deferred) |
| **E4** | `6c68b74` | Retrieval evaluation across the dissected corpus (successes + failures) |
| **E5** | `79f9855` | Curator "Find similar" in the Differential (browser-verified) |
| **E6** | `24d0a52` | Resumable indexing boundary + dry-run F estimate (no backfill) |

## Models, checkpoints, licenses, dimensions

| model | checkpoint | license | dim | role in E |
|-------|-----------|---------|-----|-----------|
| **DINOv2 ViT-S/14** | `facebook/dinov2-small` | **Apache-2.0** | 384 | primary visual space (identity/context/whole); FP32 on the GTX 1650 (faster + exact vs FP16, agreement 1.00000) |
| **FashionCLIP** | `patrickjohncyh/fashion-clip` (ViT-B/32) | see model card | 512 | fashion space (reused, not duplicated; Fashionpedia *segments*, FashionCLIP *represents*) |
| OpenCLIP | — | — | — | **DEFERRED** — not installed; added only if it beats DINOv2 on text↔evidence (E4 could not show that on this corpus) |

## Sidecar schema & invalidation contract (E0)

ONE store — `region_embeddings` (LOCKED). Each row: `embedding_id` (deterministic per
post/region/model/**role**), `vector`, `model`, `checkpoint`, `dim`, `role`
(identity|context|whole_image|patch_features), **`space`** = `model|role|version|dim`, `post_id`,
`region_id`, `geometry_rev`, `preprocessing_version`, `crop_version`, `source_content_hash`,
`mask_hash`, `route` (mask_pool|crop_cls|whole_cls), `normalized`, `storage`, `status`, `error`,
`stale_reason`, `created_at`. Contract enforced in code:

- vectors never stored in post documents (pointer only); legacy rows stay readable (additive);
- **no cross-space comparison** — every cosine flows through `cosine_same_space`, which *raises*
  across spaces;
- a **semantic label edit never invalidates** a visual embedding; geometry/source/mask/model/
  preprocessing changes do (`is_stale`, named reason);
- deterministic ids + upsert ⇒ no duplicate rows; deleted evidence never becomes another Region.

## Identity/context crops (E1)

`evidence_projection.project_region` → identity (exact mask over neutral bg, deterministic pad,
never a bbox crop when a mask exists) and context (1.8× bbox, records `target_mask_box`).
Deterministic `projection_hash`; geometry moves it, labels don't. Box-only legacy preserved with
`source="box-legacy"`. Evidence PNGs: `E1-evidence/` (Pietà person/wall/floor).

## Performance / cache / storage (E2, GTX 1650)

Whole-image encode: warm **23 ms**, peak **107 MiB** VRAM; full post (3 regions → 7 vectors)
**309 ms**; **clean unload** 100→16 MiB. Whole image encoded **once** per post; identity vectors
**pooled** from the shared grid (no re-encode). Content-cached by `feature_key`. ~1.5 KB/vector
raw (~3 KB as Mongo JSON).

## Retrieval evaluation (E4) — honest

93 DINOv2 + 4 FashionCLIP vectors over all 9 dissected posts. `visual_identity` same-label@5 =
**55%** (useful), @1 = 21% (noisy). **Successes:** `face→face 0.88`, `crown→Gupta crown 0.76`,
`top→jacket 0.99`. **Failure categories (from the data):** material/colour dominance
(`crown→face 0.85` on one sculpture), same-image contamination (cross-post@1 only 4/38),
wall↔floor confusion, and a thin/skewed corpus (fashion = 4 vectors, one image). Per-space
defaults chosen from this: identity is default but top-k is **research, not truth**; offer
exclude-same-post; context secondary; no fused ranking. Montages: `E4-evidence/`.

## Browser evidence — real curator route (E5)

`localhost:5199` → sculpture post → Differential → **Similar** → click *Gupta face*: on-demand
**indexed** → neighbours (person/crown/faces + **cross-post** results from another post) each with
evidence crop, similarity %, `dinov2_vits14·identity` space and provenance → **hover recalls the
neighbour's exact mask in its source image** → **Open source** (new tab, workspace preserved) →
return. Self excluded; no Motif/Relation created; no console errors. Screenshot:
`E5-evidence/find-similar-panel.png`.

## Dry-run corpus backfill estimate (E6)

Corpus **127 posts / 9 dissected / 42 regions**. Needs-indexing-now = **0** (store already fresh —
idempotency proven live). Full re-embed of the dissected corpus: 93 vectors, **~4.3 s**, ~279 KB.
**Increment-F projection** (all 127 posts dissected @ ~4.7 regions): **~1,312 vectors, ~60 s GPU
(~1 min), ~3.8 MB**. No automatic backfill was launched.

## Verification
Backend **203 passed** (E-suite: E0 7, E1 9, E2 7, E3 9, E5 5, E6 5 + shared). Frontend
`npm run build` clean. Live DINOv2 on the GTX 1650; browser-verified Find-similar.

## Readiness / blockers for Increment F
- **Ready:** store, projections, DINOv2, spaces/routing, retrieval + UX, idempotent/resumable
  indexing — the embedding backfill is ~1 min of GPU.
- **Blocker for a *useful* corpus:** only 9/127 posts are dissected — a corpus-wide embedding
  backfill helps only once posts are dissected, so **F should pair dissection with embedding**.
  The thin, single-domain corpus is also why OpenCLIP stays deferred.

## Forbidden in E — confirmed absent
No DTD/MINC heads, no Depth Anything, no material classifiers, no automatic Motif creation, no
Atlas graph construction, **no corpus-wide backfill**. Increment F not started.

**Not merged — awaiting review.**
