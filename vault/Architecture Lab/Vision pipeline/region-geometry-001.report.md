# REGION-GEOMETRY-001 — report

**Date:** 2026-07-18. **Class:** data-integrity defect in the Region coordinate
pipeline (not CSS, not — primarily — ML). **Traced post:** `695be6c9a9ea58f1b6aef5e0`
(the five-sculpture image, 680×286, aspect 2.378).

## Where the wrong coordinate frame entered

Nowhere in the coordinate *frame* — the boxes are, and always were, normalized
`{x,y,w,h}` in `[0,1]` against the source image's natural pixels, top-left origin.
No letterbox inversion bug, no wrong normalization divisor, no EXIF rotation, no
`xyxy`/`xywh` confusion. Hypotheses #1 and #2 are **falsified** for this data.

The corruption is hypothesis #3 — **label↔geometry association drift** — with a
specific mechanism. The two-stage pipeline assumes every fine part lives inside a
coarse anchor:

1. **Coarse (STHŪLA):** YOLO/segmentation found **one** `person` anchor, sitting
   only on the centre (Gupta) figure — it under-segmented a five-subject collage.
2. **Fine (SŪKṢMA):** the vision LLM named 9 parts across all five sculptures, but
   the prompt told it to *"subdivide INSIDE these — your sub-parts' boxes must sit
   within the parent box,"* biasing every box toward the one anchor.
3. **`_match_parent`** matched **every** part to that single anchor **by label**
   (all parts claim parent "person"; there is only one "person" anchor) —
   geometry ignored.
4. **`_clip_box_to_parent`** then force-pulled every part inside the anchor's box.
   Parts whose true home is outside it (Amaravati, Gandhara on the right) were
   clamped to the anchor's padded right edge (`x=0.5148`) and their width crushed
   to the `0.01` minimum. Stored evidence, verbatim:
   `Amaravati face (0.5148, …, 0.01, …)`, `Gandhara face (0.5148, …, 0.01, …)`.

The debug overlay (`region-overlay-stored.png`) shows it plainly: the blue anchor
is on Gupta; every red part box is crammed onto Gupta/Pala; the Amaravati and
Gandhara sculptures carry no correct boxes at all.

## Why zoom stayed stable despite wrong placement

Because the renderer is **correct**. It draws the stored normalized boxes through
one stable frame (SVG `viewBox` = natural pixels, `preserveAspectRatio="xMidYMid
meet"`, matching `object-fit: contain`). Zoom is a CSS transform on the whole
stage, so it scales image and overlay together — no per-element drift. The geometry
is "rendered correctly but intrinsically wrong": the values were corrupted at
persistence, three stages upstream of the renderer.

## Was the ML prediction correct?

Partly, and the pipeline made it impossible to tell for the worst cases. The
crushed parts (`x=0.5148, w=0.01`) prove the model placed them to the *right* of
the anchor (x ≥ 0.5148) — i.e. roughly toward their real sculptures — and the clip
destroyed that. For the parts that survived (Solanki/Gupta, inside the anchor), the
model *did* mislocate "Solanki face" onto the Gupta figure — but it was under
explicit instruction to stay inside the Gupta anchor, so that is a prompt artefact
as much as a model error. Net: the dominant, systematic corruption is the
pipeline; residual spatial accuracy on a five-way collage is a separate, honest ML
concern the fix does not claim to solve.

## The repair

One canonical geometry module, `backend/services/region_geometry.py`, owns the
contract and every transform:

- **Parenting is geometry-first.** `match_parent` links a part to an anchor only
  when the part is genuinely (≥ 50%) inside it; a matching label is a tie-breaker
  among qualifying anchors, **never** a way to adopt an out-of-anchor part. On an
  under-segmented image a part with no genuine container returns `None` — a
  top-level fine region living in the full frame, which is the correct outcome.
- **Clipping never destroys geometry.** `clip_box_to_parent` runs only for a
  genuine child, trims only the overflow, and — as a backstop — if clipping would
  drive a box degenerate it keeps the original instead of emitting a sliver.
- **The decompose prompt** now asks for boxes in the **full image frame**, with the
  coarse boxes as *hints* (which "can MISS objects entirely"), and explicitly:
  "if several subjects are present, give each its own parts at its own location —
  do not cluster every part onto one subject."
- `routers/posts.py` `_match_parent` / `_clip_box_to_parent` delegate to the module,
  so detection, crops (`cldRegionCrop`), overlays (`RegionOverlay`), Differential
  Grounds and recall all consume the one contract.

The persistence format was already correct, so no storage migration of the format
is needed; conversions (`pixels_to_normalized`, `xyxy_to_xywh`,
`unletterbox_normalized`) are provided so any future producer converts to the
contract exactly once, before persistence.

## What happens to already-corrupted Regions

The original model boxes were **not stored** (only the post-clip result), so
migration/reprojection is **not reversible** — you cannot recover the truth from
the stored data. An audit (`scratchpad/audit_corruption.py`) fingerprints the
clip-crush (degenerate slivers · parts pinned to a shared edge · parts whose box
sits <50% inside their claimed parent) and finds the blast radius is small: of **5
posts** that use region detection, **3 are corrupted** — `695be6c9…` (worst: 3
slivers, 5 mis-parented), `695be786…`, `695be8ba…`.

**Decision: targeted re-dissection** of those three via the now-fixed pipeline (not
migration, which is impossible; not silent stale-invalidation, which loses the
curator's prioritisation/notes that re-dissection preserves). Re-dissection is a
curator/model action, so it is **not** auto-run here. Note: a live re-dissection is
currently also blocked by an unrelated environment issue — the configured Groq
vision model `meta-llama/llama-4-scout-17b-16e-instruct` returns 404
(deprecated/no access); that must be repointed before re-dissection can run.

## Verification

- **Unit** (`backend/tests/test_region_geometry.py`, 14 tests, all green): round-trip
  invariant `source px → normalized → px → normalized` for landscape / portrait /
  square / HD; a four-corners-plus-centre fixture; letterbox inversion; `xyxy→xywh`;
  overlap fraction; geometry-first parenting (label never overrides geometry;
  tightest genuine container wins; out-of-anchor part → `None`); clip nudges a
  genuine child and **refuses to crush**; and the **five-sculpture regression** —
  off-anchor parts keep their true boxes, are not relocated, and never go degenerate.
- **Visual** (`region-overlay-FIXED.png`): the actual fixed `region_geometry` run
  over full-frame part boxes + the real single anchor places **every** named
  face/crown on **its own sculpture**, with **0 crushed slivers** — versus the
  stored overlay where all parts pile onto Gupta/Pala.
- **Full backend suite:** 21 passed.

Not manually adjusted: no per-image coordinate edits, no renderer offsets. The
image is fixed by fixing the pipeline (then re-dissecting), exactly as required.
