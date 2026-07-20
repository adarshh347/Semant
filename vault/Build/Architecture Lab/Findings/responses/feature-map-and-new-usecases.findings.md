# Project feature map + new use-cases from open source

**Mode:** research only. No app code changed.
**Two questions this answers:** (1) *What are we actually going to build/refurbish?* — a grounded map of the whole project, marking each feature **BUILT · IN-FLIGHT · REMAINING**, so effort lands where the gap really is. (2) *What new use-cases can open source unlock?* — feasible additions, each tied to backend capability that already exists.
**Grounding:** read at working tree `0eb711e` — `frontend/src/**`, `backend/main.py`, `backend/routers/*`, `backend/services/*`, `backend/schemas/post.py`. Tracks A–F in `responses/`.

---

## 0. The headline the structure reveals

**The backend has already implemented most of the A/B/C/F contracts; the frontend is the lagging layer, and it's mid-catch-up.** This changes the whole framing from "what to build from scratch" to "what frontend surface exposes already-built intelligence."

Evidence (grounded in the tree):
- **Backend services now present:** `fashion_clip_service`, `fashion_segmentation_service` (Fashionpedia), `region_embedding_service` (Track A sidecar), `anuranana_service` (the taste graph), `taste_signal_service`, `lens_registry` (Track C context lenses), `editor_llm_service`. Plus `segmentation_service` (YOLO), `vision_service`, `persona_service`, `anatomy_catalog_service`.
- **Contracts shipped in `schemas/post.py`:** the unified **`Region`** model with `actor: auto|creator|audience`, `detector`, `part`, `attributes[]`, `embedding_id`, `depth`, `parent_id`, `block_id` — Track A/v2 **is implemented**. `bounding_box_tags` is removed from `PostUpdate`.
- **Endpoints live:** `POST /posts/{id}/detect-regions`, `/region-annotations`, `/enrich-regions`, `/aletheia-read`, `/local-context`; and a whole **`/api/v1/taste`** router — `consent`, `signals`, `portfolio`, `DELETE signals`, plus **`/taste/brand`** `trends` + `creator-matches`. Track F's two-sided plumbing exists server-side.
- **Frontend catch-up in progress (HEAD commits `feat(darshan)`):** `RegionSurface`, `RegionOverlay`, `RegionLightbox` (zoom/pan), `VisualPane` (Track D unified pane), `AletheiaHook` + `lib/tasteSession` + `ReadDeeperPage` (Track F consumer hook), `RegionSurfaceLab` (dev harness).
- **The gap, precisely:** the frontend `services/` layer still only has `anatomy/epic/persona/phrase/research` — **no taste service, no embedding/similarity consumption, no brand surface, and the new `Region` fields (`actor/part/attributes/embedding_id`) are barely surfaced.** The intelligence is built; the UI to wield it mostly isn't.

So: **most remaining work is frontend**, and much of it is *exposing* backend capability, not inventing it.

---

## 1. Feature map — by surface, with status

Status: **BUILT** (works) · **IN-FLIGHT** (commits landing now) · **REMAINING** (not started). Verdict from the harvest map: ADOPT/HARVEST/BUILD.

### A. Writing studio (Drishya right pane)
| Feature | Status | Backend ready? | Verdict |
|---|---|---|---|
| Block editor (TipTap per block, Path A) | BUILT | `story_block_service`, `text_blocks` | migrate → **BlockNote (Path B)** |
| Slash menu (context-aware) | BUILT | `editor_llm_service` (`/chat/vision`, `/rewrite/vision`, `/flow/expand-node`) | KEEP + grow |
| Inline AI `/draft` `/write` `/continue` | IN-FLIGHT | endpoints exist | BUILD glue + HARVEST Novel ghost-text |
| `/part` (insert a region) · `/lens` (insert a reading) | REMAINING | `Region`, `local_context.aletheia` exist | **BUILD** (custom blocks) |
| `origin`/range-level authorship | REMAINING (block-level hook exists) | `block_id` on Region links back | BUILD |
| Writer receives Track-C context pack (RAG) | REMAINING | `anuranana_service` + `region_embedding_service` ready | **BUILD** (the moat glue) |

### B. Visual pane (annotation + reading)
| Feature | Status | Backend ready? | Verdict |
|---|---|---|---|
| Unified region surface (polygons+rects, one SVG) | IN-FLIGHT (`RegionSurface`/`RegionOverlay`/`VisualPane`) | `detect-regions`, `Region` | HARVEST-from-self, finishing |
| Full-screen zoom/pan lightbox | BUILT (`RegionLightbox`, hand-rolled) | — | optional **adopt react-zoom-pan-pinch** if deep-zoom grows |
| Delete legacy `BoundingBoxEditor` (pixel/neon) | REMAINING | `bounding_box_tags` retired server-side | **DELETE** |
| Many-parts reveal (coarse→fine, focus-dims, filters) | REMAINING | `depth`, `part`, `attributes`, `coarse_only` | BUILD (+ **TanStack Virtual** when dozens) |
| Reading strip in-pane (Aletheia, tap-lens→highlight region) | REMAINING | `/aletheia-read`, `lens_registry`, `region_ids` | **BUILD** (moat) |
| Pick→comment→remember (live, persistent, shows saved state) | PARTLY (modal loop exists) | `/region-annotations` | BUILD (moat) |
| `actor`/`part`/`attributes` badges + filter chips | REMAINING | fields on `Region` | BUILD small |

### C. Split shell / frame
| Feature | Status | Verdict |
|---|---|---|
| Resizable split + divider | BUILT (hand-rolled, no a11y/persist) | **ADOPT react-resizable-panels** |
| Panel headers (tabs + actions slot) | BUILT | refine → tabs-only + shared actions slot (Lane 2) |
| Shared cross-pane selection (`selectedRegionId`) | REMAINING | **BUILD** (+ **Zustand**) |

### D. Top chrome / nav
| Feature | Status | Verdict |
|---|---|---|
| Slim rail + disclosure, overflow, pencil-edit (Lane 1) | BUILT (#19) | KEEP |
| Global ⌘K command palette | REMAINING | **ADOPT cmdk** |

### E. Consumer / feed (Track F)
| Feature | Status | Backend ready? | Verdict |
|---|---|---|---|
| Aletheia-in-feed hook (1 lens + 1 fork, consent, portfolio) | IN-FLIGHT (`AletheiaHook`, `ReadDeeperPage`, `tasteSession`) | `/taste/*` all live | finishing — BUILD |
| Signal capture (dwell/tap/fork) | PARTLY (tap/fork in hook) | `/taste/signals` batch | BUILD dwell + batching |
| Taste portfolio ("your eye leans…") | PARTLY (portfolio in hook) | `/taste/portfolio` | BUILD richer view |
| Feed/gallery that hosts the hook at scale | REMAINING (`GalleryPage` basic) | paginated posts | HARVEST masonry + **Virtual** |
| Brand layer (trends, creator-matches) | REMAINING (frontend) | `/taste/brand/*` **live** | **BUILD** (net-new surface) |

### F. Cross-cutting Foundation
| Primitive | Status | Verdict |
|---|---|---|
| Design tokens (leaky: `--space-5`, hardcoded hex, neon/glass) | PARTLY | HARDEN (Surface pass) |
| Button/menu/dialog/toast primitives | ad hoc | **ADOPT Radix/shadcn** |
| Server-state caching / optimistic updates | none (manual fetch) | **ADOPT TanStack Query** |
| Loading/empty/error/edge coverage | inconsistent | BUILD to rubric §3.4 |

**Reading of the map:** the **moat features** (reading strip↔region link, pick→comment→remember, context-pack RAG, `/part`+`/lens`, taste portfolio, brand layer) are where the real building is — and the backend is already waiting for most of them. The **generic features** (editor engine, panes, palette, primitives, server-state) are where adoption retires hand-rolled code. That's the harvest philosophy landing on the actual repo.

---

## 2. New use-cases open source can unlock

Each is tied to a capability the backend **already** exposes, so it's feasible, not fantasy. Ordered by leverage-to-effort.

### 2.1 Command palette as the spine (cmdk) — *near-term, cheap*
⌘K to jump to any image, run any slash verb, switch lens, toggle regions. Backend needs nothing new. Gives the Linear/Raycast "instant, keyboard-first" feel and unifies navigation + AI. **Effort: low. Leverage: high.**

### 2.2 Visual similarity / "more like this drape" (FashionCLIP vectors) — *the sleeping asset*
`region_embedding_service` + the `region_embeddings` sidecar already compute FashionCLIP vectors per region; `anuranana_service` is the taste graph. Add a vector-search endpoint (or reuse brand matching) and a frontend explorer: **tap a region → "find images that share this taste."** This turns accrued embeddings into a discovery loop and is the visible payoff of the whole taste-graph investment. OSS: any ANN store behind Track A's `embedding_id` pointer (Atlas Vector Search / Qdrant / pgvector). **Effort: medium (mostly backend endpoint + a feed view). Leverage: very high — it makes the moat *visible*.**

### 2.3 Deep-zoom close-reading (react-zoom-pan-pinch / OpenSeadragon) — *fits the thesis literally*
The pitch is "the fold of the fabric, the fall of light." A deep-zoom canvas lets a curator zoom to a cuff/hem and read *that*. `RegionLightbox` already started this hand-rolled; a lib adds pinch/touch, bounds, and (OpenSeadragon) tiled gigapixel images. Region overlays stay pinned through zoom. **Effort: low–medium. Leverage: high for the fashion niche.**

### 2.4 Brand intelligence dashboard (recharts/visx over `/taste/brand/*`) — *revenue surface, endpoints already live*
`/taste/brand/trends` and `/taste/brand/creator-matches` **exist and return data today** with no frontend. A charts library over them = "trend-with-reason" + "match creators to a campaign by aesthetic taste" — the B2B monetization surface from Track F, unlocked mostly by *building the view*. **Effort: medium. Leverage: high (this is the business model).**

### 2.5 Shareable taste-signature page — *growth loop*
`/taste/portfolio` returns a person's accrued taste. Render it as a public, beautiful "taste signature" page ("your eye leans toward asymmetric drape, matte texture, muted palettes"). Reciprocity ("taste given back, not harvested") + a viral artifact. OSS: just the feed/card + share meta. **Effort: low. Leverage: medium-high (acquisition).**

### 2.6 Collaborative / multiplayer close-reading (Yjs via BlockNote/Liveblocks) — *later, but native to two-sided*
BlockNote ships Yjs collaboration. Two curators read one image together; or threaded comments on a reading. The two-sided premise makes shared readings natural. **Effort: high (infra). Leverage: medium — a v2 differentiator, not MVP.**

### 2.7 Local-first / offline drafts (Yjs + IndexedDB) — *trust/data-safety*
The rubric's cross-cutting "trust & data-safety" gap: never lose a reading. Yjs persistence gives autosave/offline drafts. **Effort: medium. Leverage: medium (maturity signal).**

### 2.8 Reels/video close-reading timeline (SAM2 keyframe — Track B video) — *when video lands*
Track B plans SAM2 keyframe tracking; the frontend use-case is a scrubber that reads "which slice of a reel is loved." OSS: a lightweight video timeline + the existing signal ladder, time-indexed. **Effort: high. Leverage: high once video is in scope (Track F Fork 3).**

### 2.9 Auto-palette / colour lens (Vibrant.js) — *small delight*
Extract a palette per image/region as an atmosphere attribute feeding a colour lens. Cheap, client-side, complements Aletheia's mood reading. **Effort: low. Leverage: low-medium.**

---

## 3. What NOT to add (guardrails)
- **No second editor framework** alongside BlockNote/TipTap (rejects Lexical/Plate/Editor.js) — one engine.
- **No annotation *tool* (Label Studio) as a dependency** — harvest mechanics only; our `Region`/`actor` contract must win.
- **No heavy global-state framework (Redux)** — TanStack Query (server) + Zustand (client) cover it.
- **No vector-DB lock-in in product code** — always behind Track A's `embedding_id` pointer.
- **Don't harvest the moat** — Aletheia, taste graph, felt-meaning, provenance stay bespoke.

---

## Questions for Adarsh
1. **Where's the frontend gap most painful right now** — the Visual pane finish (Track D), the writer's context-pack/`/part`+`/lens` (moat), or the consumer hook/feed (Track F)? Decides which REMAINING cluster I map into a build plan next.
2. **Surface the sleeping asset?** Is the **visual-similarity explorer** (2.2) worth prioritising — it's the most visible payoff of the embedding/taste-graph work already done — or does it wait behind the creator studio?
3. **Brand dashboard now?** `/taste/brand/*` endpoints are live with no UI. Build the B2B surface (2.4) this cycle, or keep it dark until the creator+consumer loop is proven?
4. **Deep-zoom:** adopt a zoom lib for close-reading (2.3) or keep the hand-rolled `RegionLightbox`?
5. **Adoption sequence:** OK to start with the cheap Foundation adopts (cmdk, Radix, react-resizable-panels, TanStack Query) in parallel with the moat builds, since they don't touch the same files?

*Research only — no app code touched. Core finding: the backend already ships the A/B/C/F contracts and endpoints; the frontend is the lagging, mid-catch-up layer, so most remaining work is UI that exposes built intelligence (moat = BUILD) plus retiring hand-rolled Foundation (editor/panes/palette/state = ADOPT). The biggest untapped use-case is the visual-similarity explorer that makes the taste graph visible.*
