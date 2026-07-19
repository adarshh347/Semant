# VISION-C — domain-profile evaluation manifest (C0)

**Date:** 2026-07-19 · The curated set for scoring the domain router + the four specialist
profiles (C1–C4). Builds on the `VISION-EVALSET-001` corpus
(`architecture-lab/vision-eval-001/`) — its 7 confirmed images (`fixtures/source/`) anchor
several domains; the rest are specified for sourcing from the curator's own posts (no
downloads here), exactly as eval-001 does. Target **10 images per domain**.

Router baseline recorded live (FashionCLIP multi-label `classify_domains`, gate 0.35):

| post | image | proposed {fashion, architecture, painting} | auto chosen |
|---|---|---|---|
| 695be77e | Pietà in St Peter's | fashion 0.00 · **arch 0.50** · **paint 0.46** | general, architecture, painting |
| 695be8ba | oil painting, lace bow | fashion 0.00 · arch 0.00 · **paint 0.99** | general, painting |
| 695be786 | carved sculpture (curator-overridden → painting) | — | general, painting (override) |

The Pietà is the reference **mixed-domain** case: it genuinely scores architecture AND
painting, so Auto proposes both — the multi-label contract, demonstrated on real data.

---

## General — 10
Single clear subject, multiple overlapping subjects, tiny/irregular, plus everyday photos.
- ✓ `b_product_695be786` (single ornate sculpture) · ✓ `g_dataset_001` (4 people overlapping)
- ✓ `a_5sculpt_695be6c9` (five-subject collage — the anchor-prison regression, C5)
- ~ 7 more: everyday product/object/scene photos from the curator's posts (criteria:
  clear foreground subject; no strong fashion/architecture/painting signal).

## Fashion — 10
- ✓ `g_dataset_001` (**multi-person**, overlapping saris/shirts — the C3 garment-attach case)
- ~ full-body single outfit · flat-lay/product-only · patterned garment · lace/drape ·
  two-people-overlapping-garments (dedicated) · 4 more real fashion posts.
- Router note: fashion prompt scores low on heritage/painting; needs true garment photos.

## Architecture — 10
- ✓ `e_arch_695be77e` (interior + ornament + a sculpture — nested evidence; also *mixed*)
- ~ facade with windows/doors/balconies · exterior colonnade/arcade · building occluded
  by foliage · non-Western vocabulary (gopuram/stupa/pagoda) · plain interior surfaces
  (wall/floor/ceiling) · 4 more. ADE20K classes the C2 checkpoint supports: wall, floor,
  ceiling, window, door, building, sky, etc.

## Painting / artwork — 10
- ✓ `d_fashion_695be8ba` (figurative oil, dissolving boundaries) · ✓ `f_product_695be7fa`
  (Vishnu lithograph — dense, non-Western) · ✓ `c_photo_695be794` (atmospheric, statue)
- ~ dense multi-figure · **abstract / semi-abstract** (object segmentation insufficient —
  the C4 "no useful automatic objects is not failure" case) · landscape-of-light · 4 more.

## Mixed fashion + architecture — 6 (subset, C5)
- ✓ `e_arch_695be77e` (architecture + sculpture; scores arch+paint) — reference.
- ~ a fashion portrait in an architectural interior (the canonical mixed case) · a runway
  in a built space · 4 more. Gate: selective scheduling, garments stay attached, no
  duplicate masks.

## Difficult negatives — 6
- Low-signal / ambiguous images where Auto should stay **general only** (no specialist
  over the gate): flat texture swatches, extreme close-ups, blurred/abstract photos.
- ✓ `a_5sculpt` doubles as the collage stress (five subjects must not collapse to one).

---

## How the set is used per gate
- **C1 general:** the General column → detect → exact mask → refine → recall.
- **C2 architecture:** the Architecture + mixed columns → SegFormer-ADE mask coverage,
  label utility, latency, memory, failure modes.
- **C3 fashion:** the Fashion + multi-person columns → garments attached by geometry, not
  label-parenting; masks save/refine/recall.
- **C4 painting:** the Painting column (esp. abstract) → both object-mask and non-object
  Ground workflows; "no objects" is a valid outcome.
- **C5 mixed/UX:** the Mixed + collage + negatives → selective scheduling, no anchor
  prison, no duplicate masks, no curator-data loss.

**Sourcing gap (honest):** the confirmed anchors (10 real images across the corpus) are
in-repo; the remaining ~40 slots are specified, not yet collected — same posture as
eval-001 §gaps. A read-only contact sheet of the curator's untagged posts (offered in
eval-001) fills them fastest. The router baseline above is real, not projected.
