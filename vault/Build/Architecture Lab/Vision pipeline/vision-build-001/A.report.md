# VISION-BUILD-001 · Increment A — Canonical mask evidence — report

**Date:** 2026-07-19 · **Branch:** `feat/vision-differential` · **Scope:** Increment A
only. No models installed, no PyTorch env change, no model substitution, no B–F work,
no temporary orchestrator. Preconditions checked first: `VISION-CODE-AUDIT-001` complete;
`VISION-HARDWARE-001` run (`../vision-hardware-001.report.md`) — GPU present but unusable
(CPU-only torch), RAM critically tight; Increment A is CPU-only so it is unblocked.

## What was built

The authoritative segment identity is now a **mask**, carried as a COCO-style
uncompressed RLE. `polygons` (multi-ring: outer + holes + one ring per component), the
legacy single `polygon`, and the `box` are **derived** from it. Box-only/legacy regions
are retained explicitly — no mask is ever fabricated for them.

- **Schema** (`backend/schemas/post.py`, `Region`): added `mask_rle` (authoritative),
  `polygons` (derived rings), `geometry_rev` (bumps on each mask-identity derivation),
  `geometry_provenance` (`{kind, method, size, …}` lineage). `box` and legacy `polygon`
  documented as derived-when-mask-present. Additive + `extra="allow"` → existing
  documents validate unchanged.
- **One shared geometry service** (`backend/services/mask_geometry.py`) owns the whole
  chain: `rle_encode`/`rle_decode` (pure-python, exact, COCO column-major),
  `rle_area`, `rle_bbox_norm`, `polygons_to_bits` (scanline, even-odd so holes
  subtract), `bits_to_polygons` (cv2 contours with holes+components; pure fallback =
  per-component bounding-rect rings), `bbox_from_polygons`, `largest_ring`,
  `mask_to_crops` (alpha identity crop + rectangular context crop, PIL), and
  `canonicalize_geometry` — the single entry the save path calls.
- **Persistence seam** (`backend/routers/posts.py`, `save_region_annotations`): each
  saved region is run through `canonicalize_geometry` — mask-bearing regions get their
  derived forms + lineage; legacy box regions are stamped and left untouched. This is a
  model-free curator-save path; the model path (`detect_regions`) was **not** touched
  (that integration is Increment B).
- **Exact-mask frontend rendering:**
  - `frontend/src/lib/maskGeometry.js` — `hasMaskPolygons`, `ringsToPath` (rings →
    one SVG `<path>` with `fill-rule="evenodd"`).
  - `RegionOverlay.jsx` and `differential/GroundLayers.jsx` now draw the exact
    multi-ring path when present, falling back to the legacy single polygon, then to a
    rect. Both consume the existing `viewBox = natural, preserveAspectRatio="xMidYMid
    meet"` contract, so masks track the image at any stage size/zoom. Hover still uses
    the bbox; the selected/active shape shows its exact border.

## Changed / added files

| file | change |
|---|---|
| `backend/schemas/post.py` | Region: +`mask_rle`, +`polygons`, +`geometry_rev`, +`geometry_provenance` |
| `backend/services/mask_geometry.py` | **new** — the one geometry service (RLE↔mask↔polygon↔bbox↔crop) |
| `backend/routers/posts.py` | import + canonicalize in `save_region_annotations` (model-free) |
| `backend/tests/test_mask_geometry.py` | **new** — 31 synthetic round-trip / persistence / registration tests |
| `frontend/src/lib/maskGeometry.js` | **new** — `hasMaskPolygons`, `ringsToPath` (evenodd) |
| `frontend/src/lib/maskGeometry.test.js` | **new** — 5 render + coordinate-registration tests |
| `frontend/src/components/RegionOverlay.jsx` | render exact multi-ring mask path |
| `frontend/src/differential/GroundLayers.jsx` | render exact multi-ring mask path |
| `architecture-lab/vision-build-001/A-mask-roundtrip-evidence.png` | rendered evidence |

## Test evidence (the Increment A gate)

- **Backend:** `pytest backend/tests` → **52 passed** (was 21; +31 in
  `test_mask_geometry.py`). Covers, as synthetic masks: **rectangle, concave (L),
  disconnected components, holes, edge-touching, 2×2 and 1×1**. Assertions:
  - RLE→mask→RLE is **byte-exact** for every case; area & runs verified.
  - normalized bbox matches the pixel extents exactly.
  - mask→polygon→mask **IoU ≥ 0.80** (rectangle … tiny); two-components yields ≥2
    rings; **the hole stays open** after re-rasterizing the derived rings (cv2 path).
  - `mask_rle` survives `Region` model + `json.dumps` (BSON-safe) and decodes identically.
  - `canonicalize_geometry`: mask → derives polygons/legacy-polygon/box + `rev=1` +
    provenance `kind=mask`; **legacy box is retained untouched** (`mask_rle` stays None,
    `kind=legacy-box`); polygons+size → authoritative RLE.
  - **coordinate registration:** the same shape at 20² and 60² gives an identical
    normalized bbox.
- **Frontend:** `vitest run` → **68 passed** (+5 in `maskGeometry.test.js`): `ringsToPath`
  scaling, one closed subpath per ring (holes/components), degenerate-ring dropping, and
  **registration across stage resize** (a point lands on the same image fraction at
  800×600 and 1600×1200; contain-fit scale equal on both axes). `eslint` clean on all
  changed files.
- **Rendered evidence** (`A-mask-roundtrip-evidence.png`): a synthetic square-with-hole
  **plus a disconnected disc**, four panels — (1) original mask, (2) the derived-polygon
  **even-odd rasterization** (what the SVG `<path fill-rule="evenodd">` draws), (3) diff
  (agreement in plum, mismatch in red — only faint boundary), (4) the **alpha crop** over
  a checker so transparency reads: the hole is transparent and the disc is separate.
  3 rings, IoU **0.9955**, 23 boundary px mismatch.

**Gate result: PASS.** Synthetic masks with holes/multiple components survive
persistence and render/crop round trips; all existing box regions remain usable
(retained explicitly, geometry untouched).

## Known information loss (honest limits)

1. **Polygon derivation is an approximation of the mask, by design.** The RLE is the
   exact identity; `polygons` are a render aid. cv2 contours are traced on a 4× upsample
   to keep the pixel-center→boundary error sub-pixel (IoU ≥ 0.995 on the demo), and
   `approxPolyDP` simplification (when a tol > 0 is passed) trades a little fidelity for
   payload size. Re-deriving from the RLE is always available.
2. **Without cv2 (slim deploy only), `bits_to_polygons` degrades to one bounding-rect
   ring per connected component** — components are preserved, holes and concavity are
   not. The RLE (identity) is unaffected; only the render aid coarsens. cv2 is present
   in this environment, so the gate exercised the accurate path.
3. **`mask_to_crops` scales the mask to the image with nearest-neighbour** — a ½-pixel
   alpha edge on very small masks. Acceptable for crops; not part of identity.
4. **No detector writes masks yet.** `detect_regions` and the segmenters still emit
   boxes/single polygons; wiring them to emit `mask_rle` is Increment B (it touches the
   model path, deliberately out of scope here). Today masks enter only via the curator
   save path once a producer supplies one.

## B–F remain BLOCKED — recorded per request

Increments B–F must not start until all three land:

1. **`VISION-MODEL-MATRIX-001`** — the fixed roster. Does not exist in the repo;
   without it there is no roster to honor and no substitution guard.
2. **`VISION-ORCHESTRATOR-001`** — the planner/scheduler/router/cache skeleton that
   Increment B plugs the chosen refiner into. Does not exist.
3. **A verified CUDA or serverless runtime decision.** `VISION-HARDWARE-001` confirms
   PyTorch is CPU-only (`2.13.0+cpu`, `cuda_available=False`) so the GTX 1650 (4 GB) is
   currently unusable, and system RAM is ~1 GiB free while already swapping 4.6 GiB.
   Local heavy-model serving is not viable as configured; the CUDA-rebuild-vs-serverless
   call (see `vision-initiative/pre-build-decisions.md` B1) must be made and verified.

## Stopping for review
Increment A is complete and committed on `feat/vision-differential`. Not merged (Adarsh
merges). Awaiting review before any further increment; B–F stay blocked as above.
