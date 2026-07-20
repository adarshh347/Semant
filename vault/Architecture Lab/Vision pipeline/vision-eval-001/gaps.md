# VISION-EVALSET-001 — gaps: fixtures & annotations still needed

What the eval pack still needs from you, and why each item was **not** produced here
(the mode forbids downloads, model runs, config/data changes; the stop condition
forbids running candidates).

## 1. Proposed image fixtures (15 slots)

The corpus is 7 confirmed + 15 proposed = 22. The confirmed 7 are real project images
(`fixtures/source/`). The 15 proposed slots need images that I could not source
without either downloading external images or eyeballing all 121 untagged posts. You
have those posts; pick from them (or add new). Selection criteria per slot:

| slot | what to find | acceptance test |
|---|---|---|
| GEN-04 tiny/irregular | many small scattered objects with ragged edges (e.g. a jewellery tray, a bead/coin spread, foliage) | ≥5 objects each <3% of frame, non-rectangular |
| FSH-01 full-body outfit | one person, head-to-toe, single coherent outfit | whole garment set visible, not cropped |
| FSH-02 two-people garments | two people whose garments overlap/touch | two distinct outfits, adjoining |
| FSH-03 lace/drape/translucent (photo) | a real garment photo with lace/fringe/sheer | a see-through or fringed edge present |
| FSH-04 patterned garment (flat) | a bold repeating textile pattern filling the frame | pattern legible, minimal occlusion |
| FSH-05 flat-lay / product-only | garments/accessories laid flat, no wearer | no person; ≥2 items |
| ARC-01 facade | a building facade: windows/doors/balconies grid | ≥6 repeated openings |
| ARC-02 columns/arches (exterior) | a colonnade/arcade | ≥3 columns or arches in a row |
| ARC-04 occluded by foliage | a building partly hidden by trees/plants | ≥25% of the building occluded |
| ARC-05 non-Western architecture | gopuram / stupa / pagoda / Islamic dome etc. | clearly non-Western vocabulary |
| ART-03 landscape of light | a landscape where light/atmosphere dominates over objects | no single hard subject |
| ART-04 abstract | abstract/semi-abstract work; object segmentation insufficient | no nameable objects |
| PER-04 implied movement | a still with strong implied motion (dancer, drapery mid-swing, blur) | motion readable from a frozen frame |

(FSH-02/03/04 are partially covered by confirmed images — see the manifest — so they
are optional-dedicated; the other 10 are genuinely open.)

**A cheaper path than viewing 121 posts one by one:** build a contact sheet. A
read-only script can pull each post's Cloudinary thumbnail into a grid image you skim
in one pass, then you hand back the post_ids per slot. I can generate that contact
sheet on request (read-only; no data change) — it was out of scope for this pass.

## 2. Gold reference masks (6–8 images) — NOT created here

The brief allows creating reference masks "only if existing repo tools can do so
without new dependencies." They were deliberately **not** created, for two reasons:

1. **The only in-repo mask tools ARE the candidates.** `segmentation_service`
   (YOLO11n-seg) and `fashion_segmentation_service` (SegFormer) are exactly the
   segmenters under evaluation. Using them to mint "ground truth" would (a) violate the
   stop condition ("do not run candidate models") and (b) be circular — you cannot score
   a model against masks it produced.
2. **Gold masks must be reviewed.** A reference mask is only gold after human review; I
   cannot supply that review.

**How to make them later (records for when you do):**
- Best: trace the 3–8 gold targets per image by hand in an SVG/mask editor, export a
  binary PNG mask per target at the source image's native resolution.
- Acceptable bootstrap: run a segmenter to *propose* outlines, then **you** correct and
  approve each — the approval is what makes it gold (mark `provenance: human-reviewed`).
- **Storage:** `fixtures/masks/<image_id>/<target_name>.png` (see
  `fixtures/masks/README.md`), one file per target, separate from source images, each
  with a provenance line (author, date, method, source image + dims).

## 3. Hardware / decision inputs the harness needs (from the code audit §5)

The benchmark harness and first candidates are gated on these — un-set today:
- GPU VRAM of the GTX 1650 (bounds SAM2-tiny vs serverless).
- Deploy-target GPU (any, or CPU-only AWS?) — decides in-process vs serverless.
- Chosen serverless provider (Modal / Replicate / Runpod).
- Working Groq vision model id (current `llama-4-scout` 404s — blocks the VLM-semantics
  column and any re-dissection).
- Ultralytics AGPL decision (enterprise licence vs permissive-detector swap).

## 4. EXIF test fixture — NOT obtainable from Cloudinary

The audit's P0-1 (no EXIF-orientation handling) **cannot** be tested with the confirmed
fixtures: Cloudinary bakes/strips orientation on delivery, so all seven arrive already
upright (`exif_orientation=none`). To exercise the defect you must supply an **original
rotated-EXIF file** (a phone photo taken sideways, un-processed) fed through the *upload*
path, not the Cloudinary re-fetch path. Please add one under `fixtures/source/` (e.g.
`exif_rot90_original.jpg`) with a note that it is a raw upload-path fixture.

## 5. Optional: pending domain labels

121 posts have no `domain` and no tags; the 6 with regions carry a first-cut
`classify_domain` guess, 4 of which are wrong (`fixtures/PROVENANCE.md`). If you want
domain-parsing scored at scale, the contact-sheet pass (§1) can also collect a
one-word human domain per sampled post — but that is curation, not something to infer.
