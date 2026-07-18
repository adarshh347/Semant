# VISION-EVALSET-001 — benchmark matrix (empty, ready for candidate runs)

**Do not run candidates yet.** Per the stop condition, the harness and first candidates
are decided by `VISION-CODE-AUDIT-001` + the hardware decision. This file is the
scaffold to fill *after* that.

Candidate columns are drawn from the code audit's role map (`SegmenterAdapter`,
`MaskRefiner`, `SemanticAnnotator`, `EmbeddingAdapter`, `DomainProfile`). Fill one
block per candidate run. Scores are **0–3** per rubric dimension group; **HF** = hard
fail (list which gate, e.g. `HF-2`). Leave cells blank until run.

## Candidate roster (fill as evaluated)

| # | candidate | role | provenance | status |
|---|---|---|---|---|
| C0 | current pipeline (YOLO11n-seg + SegFormer-clothes + Groq VLM) | baseline | in-repo | not run |
| C1 | _e.g. SAM2 (tap)_ | MaskRefiner | proposed | not run |
| C2 | _e.g. Fashionpedia / Fashionformer_ | Segmenter+Annotator | proposed | not run |
| C3 | _e.g. alt domain router_ | DomainProfile | proposed | not run |
| … | | | | |

## A. Geometry + Semantics + Perceptual (per image, per candidate)

One row per (image, candidate). Group columns = mean 0–3; HF column lists gates tripped.

| image | candidate | Geometry | Semantics | Perceptual | HARD FAILS | notes |
|---|---|---|---|---|---|---|
| CONF-a_5sculpt (GEN-03) | C0 | | | | | five-head separation; watch HF-1/HF-2 |
| CONF-a_5sculpt (GEN-03) | C1 | | | | | |
| CONF-b_sculpt (GEN-01) | C0 | | | | | ornament small-part; grey-ground bleed |
| CONF-g_people (GEN-02) | C0 | | | | | person/garment separation; edge face |
| CONF-d_painting (ART-01) | C0 | | | | | watch HF-4 (fabricated boundary) |
| CONF-f_vishnu (ART-02) | C0 | | | | | 7-hood count; line-art contour |
| CONF-e_pieta (ARC-03) | C0 | | | | | arch vocab gap; nesting |
| CONF-c_statue (PER-03) | C0 | | | | | depth order; low-contrast boundary |
| GEN-04 tiny/irregular | — | | | | | (fixture pending) |
| FSH-01 full-body | — | | | | | (fixture pending) |
| FSH-05 flat-lay | — | | | | | (fixture pending) |
| ARC-01 facade | — | | | | | (fixture pending) |
| ARC-02 columns/arches | — | | | | | (fixture pending) |
| ARC-04 occluded/foliage | — | | | | | (fixture pending) |
| ARC-05 non-Western arch | — | | | | | (fixture pending) |
| ART-03 landscape/light | — | | | | | (fixture pending) |
| ART-04 abstract | — | | | | | (fixture pending) |
| PER-04 implied movement | — | | | | | (fixture pending) |

## B. Product circulation (per gold image, per candidate)

Scored only on the gold subset (the 7 confirmed), since it needs the full store → render → recall loop.

| image | candidate | hover bbox | alpha/context crop | Diff. select/refine | Ground/Percept identity | Mention/recall | HARD FAILS |
|---|---|---|---|---|---|---|---|
| CONF-a_5sculpt | C0 | | | | | | |
| CONF-b_sculpt | C0 | | | | | | |
| CONF-g_people | C0 | | | | | | |
| CONF-d_painting | C0 | | | | | | |
| CONF-f_vishnu | C0 | | | | | | |
| CONF-e_pieta | C0 | | | | | | |
| CONF-c_statue | C0 | | | | | | |

## C. Runtime (per candidate, raw + 0–3)

| candidate | cold ms | warm ms | peak VRAM MB | peak RAM MB | swap Δ MB | cleanup on unload | fallback behavior | Runtime 0–3 |
|---|---|---|---|---|---|---|---|---|
| C0 | | | | | | | | |
| C1 | | | | | | | | |

## D. Summary ranking (fill last)

| candidate | mean Geometry | mean Semantics | mean Perceptual | mean Circulation | Runtime | **HARD FAIL count** | rank |
|---|---|---|---|---|---|---|---|
| C0 | | | | | | | |

**Ranking rule (from rubric):** any candidate with ≥1 HARD FAIL on the gold subset
ranks below any candidate with zero, regardless of means. Then order by mean, with
Geometry and Circulation weighted over Runtime for a v1 close-reading tool.
