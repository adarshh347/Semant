# The Field — projecting the archive by what the images look like

**To:** the **vision-pipeline thread** (`feat/vision-pipeline`) — you own embeddings, the pipeline, and this endpoint.
**From:** the frontend/archive thread (`feat/archive-threads`) — I own the canvas renderer.
**Status:** spec + coordination request. **Blocked on corpus coverage (§2).** No app code written for this yet.

## 1. The motive
The Archive's Scroll is ordered by *when it arrived*. The **Field** is the same corpus ordered by *what it looks like*: a pannable, zoomable canvas where every image sits where FashionCLIP thinks it belongs, and neighbours are visual rivals — the PixPlot / CLIP-Plot register, but on our own taste vectors. Click opens the image; hover shows its reading.

It's the one view that makes 7k images *legible as a body of taste* rather than a river. It also makes drift visible: the clusters ARE the motifs the curator keeps returning to.

## 2. The blocker — coverage (measured 2026-07-16)
| | |
|---|---|
| posts total | **7,176** |
| posts with region_embeddings | **19** (0.26%) |
| embedding vectors | 269 |
| model / dim | `fashion-clip` / 512 |
| posts with any `region_annotations` | 33 |

**A Field of 19 points is not a field.** UMAP at defaults (`n_neighbors=15`) barely has neighbours to work with, and HDBSCAN (`min_cluster_size≥5`) on 19 points returns mostly noise. The renderer is ~a day; the *data* is the feature.

**Prerequisite: backfill.** Segmentation + FashionCLIP across the corpus (or a defined slice) so coverage is high enough for the projection to mean anything. That's a pipeline batch job with real GPU/time/cost — the vision-pipeline thread's call, not something the frontend thread should trigger.

## 3. The endpoint contract (what the renderer needs)
`GET /api/v1/projection?tag=<optional>&model=fashion-clip`

```jsonc
{
  "meta": {
    "model": "fashion-clip", "dim": 512,
    "reducer": "umap", "params": { "n_neighbors": 15, "min_dist": 0.1, "metric": "cosine" },
    "clusterer": "hdbscan", "cluster_params": { "min_cluster_size": 25 },
    "count": 6841, "coverage": 0.95,
    "computed_at": "2026-07-16T…", "corpus_version": "<hash|count+max_id>"
  },
  "points": [
    { "post_id": "6a58…", "x": 0.4213, "y": -1.882, "cluster": 3 }   // x/y raw; renderer normalises
  ],
  "clusters": [
    { "id": 3, "size": 412, "label": "gold drape · warm interior", "exemplars": ["6a58…","6a41…"] },
    { "id": -1, "size": 233, "label": "unclustered" }
  ]
}
```

Notes on the contract:
- **One point per post, not per region.** A post has many region vectors (269/19 ≈ 14 each). Mean-pool a post's region vectors into one unit-normalised vector before reducing — we're plotting images, not parts. (A future `?by=region` mode could plot parts; not v1.)
- **`cluster: -1` = HDBSCAN noise.** Keep it, don't drop it — the renderer greys it back.
- **Thumbs are not your problem.** Send `post_id` only; the renderer already builds Cloudinary crop URLs (`cldCrop`) and has the LQIP pipeline.
- **`label`** is the nice-to-have: a cluster is far more useful named. Cheapest honest version = the most common `region_annotations.label` / `category` among its members; the Aletheia lens summary would be better. Ship unlabelled (`"cluster 3"`) rather than block on it.
- **Hover reading**: the renderer will pull `aletheia_cache` / region labels from the existing post endpoint on hover — no need to inline it here.

## 4. Computation + caching (why this can't be per-request)
UMAP over ~7k × 512 is seconds-to-minutes and single-threaded-ish; HDBSCAN adds more. **Never compute per request.**
- Precompute into a **`projections` collection**, one doc per `(scope, model, reducer params, corpus_version)`; the endpoint is a cache read.
- Recompute as a **background job** (reuse the `agent_runs` job pattern already in the repo) — on demand, and after a backfill lands.
- Invalidate on `corpus_version` (cheap: count + max `_id`).
- `?tag=` scopes: either project the tag's subset separately, or (simpler, and I'd prefer this) project **once globally** and let the renderer filter points client-side — the layout stays stable when you switch Threads, which is better UX and one job instead of N.

## 5. New dependencies — your call
- `umap-learn` → pulls **numba + llvmlite** (heavy, native).
- `hdbscan` → **scikit-learn** + Cython (or `sklearn.cluster.HDBSCAN`, sklearn ≥1.3, which avoids the separate package).
- Neither is installed today (the venv has numpy only, no sklearn).

Alternatives if that weight is unwelcome: PCA→t-SNE via `openTSNE`, or PCA-only for v1 (worse separation, near-zero deps). **This is a backend infra decision and it's yours.**

## 6. Coordination — who does what
| Piece | Owner |
|---|---|
| Embedding backfill across the corpus | **vision-pipeline** |
| `projections` collection + background job | **vision-pipeline** |
| `GET /api/v1/projection` (contract §3) | **vision-pipeline** |
| Cluster labelling | **vision-pipeline** (from regions/Aletheia) |
| Canvas/WebGL Field renderer, pan/zoom, hover reading, click→post | **frontend/archive** (me) |
| The JSON in §3 | **the seam — agree it before either side builds** |

Shared files: **none.** This touches `backend/routers/*` + a new service (yours) and `frontend/src/components/*` (mine). No `PostDetailPage.jsx` involvement. So both sides can build in parallel **once §3 is agreed and §2 is unblocked.**

## 7. Phasing
1. **Agree the contract (§3).** Cheap, unblocks parallel work.
2. **Backfill** embeddings (vision-pipeline) — the gate.
3. **Endpoint + job** against the real corpus.
4. **Renderer** — canvas/WebGL field, pan/zoom, LOD thumbs, hover reading, click → `/posts/:id`. I can build against a fixture matching §3 before 2–3 land, so the renderer is ready the day the data is.

## 8. Questions for Adarsh
1. **Backfill now or later?** The Field is worth little until coverage is high. Is a full segmentation+FashionCLIP pass over 7,176 images something you want to spend now?
2. **Dep weight** — is `umap-learn` + numba acceptable in the backend image, or do we start with a PCA/openTSNE v1?
3. **Should I build the renderer against a fixture now** (ready-when-data-is), or hold the whole Field until the backfill lands?
4. Global projection + client-side Thread filtering (my recommendation), or per-tag projections?
