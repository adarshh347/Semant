# VISION-EVALSET-001 — corpus manifest

**Date:** 2026-07-18 · **Mode:** evaluation documentation + fixtures only (no code,
config, package, model, or stored-post change). Runs parallel to `VISION-CODE-AUDIT-001`.

A small, deliberately hard corpus for comparing **segmentation · mask refinement ·
domain parsing · perceptual analyzers · VLM semantics** on evidence that matters to
Semant's image → Region → Ground → Percept circulation. Target **22 images**: **7
CONFIRMED** (real project images, staged under `fixtures/source/`, each viewed and
characterised) and **15 PROPOSED** (selection specified; to be filled from the
curator's own 121 untagged posts or added — never downloaded here). See `gaps.md`.

The corpus is chosen against Semant, not against COCO. Its hardest truth: the product
is a **fashion + art close-reading** tool, and its real library is **heritage
sculpture, painting, devotional prints and portrait photography** — exactly the images
a COCO-trained detector reads as "person" or "product." The confirmed set already
demonstrates this failure (see per-image notes and `fixtures/PROVENANCE.md`).

Legend: **✓C** confirmed/staged · **~P** proposed (criteria in `gaps.md`) · an image's
*primary slot* is counted once; the same image may recur as a *secondary* anchor for
perceptual dimensions (overlaps are allowed by design).

---

## Confirmed images (7) — staged in `fixtures/source/`

### CONF-a · `a_5sculpt_695be6c9.jpg` — 680×286 — **GEN-03 five-sculpture regression**
Five heritage heads (Solanki/Gupta/Pala/Amaravati/Gandhara) on black, labelled.
- **Why in corpus:** the REGION-GEOMETRY-001 defect image — one YOLO `person` anchor
  over the centre head, all fine parts sucked onto it, right-hand heads crushed to
  slivers. The single most important geometry regression Semant owns.
- **Stresses:** instance separation (5 near-identical subjects), no-anchor-imprisonment,
  no crushed slivers, wide-aspect letterbox mapping, and text-vs-object discrimination.
- **Secondary:** archetype for ART "sculpture/heritage comparison"; domain mislabel
  (`product` 0.97).

### CONF-b · `b_product_695be786.jpg` — 452×679 — **GEN-01 single clear subject**
One ornate carved female figure, raking side-light, dense ornament.
- **Why:** the "easy" slot that isn't — a single subject whose *evidence* is fine parts
  (jewelled hairdress, bangle, facial planes) and whose ground is a soft grey gradient a
  box will over-claim.
- **Stresses:** boundary quality on a curved lit form, small/thin-part preservation
  (hair jewels), mask-vs-box gain, label honesty (it is a *sculpture*, not a `product`).
- **Secondary:** PER strong light/shadow gradient; PER repeated-texture (ornament).

### CONF-g · `g_dataset_001.png` — 998×1192 — **GEN-02 multiple overlapping subjects**
Four people posing indoors, arms overlapping; a fifth face half-cut at right edge.
- **Why:** the only true multi-person, multi-garment photograph in the confirmed set —
  the fashion instance-separation case, plus a genuinely *tiny occluded* fifth face.
- **Stresses:** person/garment instance separation under occlusion, tiny-object recall
  (edge face), garment-vs-skin boundaries, patterned-garment handling (orange check
  sari + striped border).
- **Secondary:** FSH two-people-overlapping-garments; FSH patterned-garment; PER depth.

### CONF-d · `d_fashion_695be8ba.jpg` — 643×680 — **ART-01 figurative painting, dissolving boundaries**
Oil painting; a black lace/tulle bow at the throat; warm ochre ground; painterly edges.
- **Why:** the case object-segmentation is *wrong* for — brushwork has no hard contour,
  and the "correct" evidence is a material/luminous reading, not a mask. Also carries a
  translucent-lace boundary.
- **Stresses:** mask-is-insufficient honesty, translucent/lace boundary, no
  false-precise contour on painterly edges, warm palette reading.
- **Secondary:** FSH drape/lace/translucent; PER warm/atmospheric.

### CONF-f · `f_product_695be7fa.jpg` — 445×680 — **ART-02 dense multi-figure / non-Western print**
Lithograph of Vishnu on the serpent Śeṣa, seven-hooded canopy, Thai caption, aged paper.
- **Why:** non-Western devotional iconography as a line engraving — dense repeated
  elements (7 hoods, multiple arms/attributes), a semi-abstract radiating ground, and a
  domain the router calls `product` (0.94).
- **Stresses:** dense small-part separation (hoods, attributes), repetition precision
  (serpent scales/hoods), semi-abstract ground vs figure, domain vocabulary (devotional
  print, not product), no object-mask forced onto engraved line-work.
- **Secondary:** ART abstract/semi-abstract ground; PER repetition.

### CONF-e · `e_arch_695be77e.jpg` — 544×680 — **ARC-03 interior with wall/ceiling/openings**
Michelangelo's Pietà inside St Peter's — marble group in an ornate niche; light shaft.
- **Why:** a sculpture *inside* architecture — nested evidence (figure-group within
  altar within niche within wall), ornament, and a strong light shaft, in one frame.
- **Stresses:** part-within-part hierarchy (Pietà ⊂ altar ⊂ niche), architectural
  ornament/pilaster/arch reading, luminous-map correspondence (shaft), spatial ordering.
- **Secondary:** ARC historical ornament/columns/arches; ART sculpture; PER light.

### CONF-c · `c_photo_695be794.jpg` — 454×679 — **PER-03 foreground/background depth**
Weathered B&W stone statue of a woman against bare winter trees; atmospheric.
- **Why:** the depth/atmosphere anchor — a crisp lit foreground subject dissolving into a
  low-contrast branch-and-sky background; eroded surface texture.
- **Stresses:** figure/ground depth ordering, atmospheric (cool) distribution, weathered
  material texture usefulness, boundary quality where subject meets soft background.
- **Secondary:** ART landscape-of-light/atmosphere (partial); PER repeated texture (bark).

---

## Full slot coverage (target 22)

### General / stress — 4
| slot | need | image | status |
|---|---|---|---|
| GEN-01 | single clear subject | CONF-b | ✓C |
| GEN-02 | multiple overlapping subjects | CONF-g | ✓C |
| GEN-03 | five-sculpture collage regression | CONF-a | ✓C |
| GEN-04 | tiny objects & irregular boundaries | — | ~P |

### Fashion — 5
| slot | need | image | status |
|---|---|---|---|
| FSH-01 | one full-body outfit | — | ~P |
| FSH-02 | two people, overlapping garments | (CONF-g covers; dedicated preferred) | ~P |
| FSH-03 | drape / lace / fringe / translucent | (CONF-d lace covers; garment-photo preferred) | ~P |
| FSH-04 | patterned garment | (CONF-g sari covers; flat pattern preferred) | ~P |
| FSH-05 | flat lay / product-only | — | ~P |

### Architecture — 5
| slot | need | image | status |
|---|---|---|---|
| ARC-01 | facade with windows/doors/balconies | — | ~P |
| ARC-02 | historical ornament & columns/arches | (CONF-e interior covers; exterior colonnade preferred) | ~P |
| ARC-03 | interior with wall/floor/ceiling/openings | CONF-e | ✓C |
| ARC-04 | building partly occluded by foliage | — | ~P |
| ARC-05 | non-Western architectural vocabulary | — | ~P |

### Painting / artwork — 5
| slot | need | image | status |
|---|---|---|---|
| ART-01 | figurative painting, dissolving boundaries | CONF-d | ✓C |
| ART-02 | dense multi-figure composition | CONF-f | ✓C |
| ART-03 | landscape dominated by light/atmosphere | (CONF-c atmospheric, not a landscape) | ~P |
| ART-04 | abstract / semi-abstract | (CONF-f ground covers; dedicated preferred) | ~P |
| ART-05 | sculpture / heritage comparison | CONF-a (the five heads) | ✓C¹ |

¹ CONF-a is counted primarily as GEN-03; it is also the natural ART-05 archetype. If a
distinct heritage-comparison image is wanted, mark ART-05 ~P.

### Perceptual analyzers — 3–5 (overlaps allowed)
| slot | need | image | status |
|---|---|---|---|
| PER-01 | strong light/shadow gradient | CONF-b, CONF-e | ✓C |
| PER-02 | repeated texture / pattern | CONF-b, CONF-f, CONF-g | ✓C |
| PER-03 | clear foreground/background depth | CONF-c, CONF-g, CONF-e | ✓C |
| PER-04 | implied movement in a still | — | ~P |
| PER-05 | warm/cool / atmospheric distribution | CONF-d (warm), CONF-c/e (cool) | ✓C |

**Counted total:** 7 confirmed distinct images + 15 proposed slots = **22**. Confirmed
images fully satisfy 11 slots and partially cover 5 more; the perceptual group is
already well anchored. Proposed slots and how to fill them: `gaps.md`.

---

## Gold subset for reference masks
All **7 confirmed** images are the gold subset (brief asks for 6–8). Reference masks
are **not** created here — see `gaps.md` (creating them would mean running a candidate
model, which the stop condition forbids, and gold masks require human review). The
method and storage layout (`fixtures/masks/`) are specified there.
