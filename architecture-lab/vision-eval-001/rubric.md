# VISION-EVALSET-001 — scoring rubric

Every candidate (segmenter, mask refiner, domain parser, perceptual analyzer, VLM) is
scored **per critical target** (`targets.yaml`) across five dimension groups. Each
dimension is a compact **0–3**; on top of the numeric score sit **hard gates** that
fail a result outright regardless of its score, because in a close-reading product a
confidently-wrong piece of evidence is worse than a missing one.

## The 0–3 scale (generic anchors)

| score | meaning |
|---|---|
| **0** | absent or wrong — the evidence is missing, or asserted where it does not exist |
| **1** | present but not usable — right idea, wrong extent/label; a curator must redo it |
| **2** | usable with minor edits — a curator would accept it after a small nudge |
| **3** | ship-quality — a curator would cite it unchanged |

Score to the *product need*, not to IoU alone. A 0.7-IoU mask that respects the
boundary a human cares about beats a 0.8-IoU mask that crushes a thin part.

## Hard gates (any one → HARD FAIL for that target, overrides the score)

`HF` in the matrix. These are the evidence-corruption modes REGION-GEOMETRY-001 exists
to prevent — a stack that trips any of them is not shippable no matter how well it
scores elsewhere:

- **HF-1 Anchor imprisonment** — a part parented into an anchor it is not ≥50% inside,
  or relocated toward an anchor it does not belong to.
- **HF-2 Crushed sliver** — a persisted box/mask driven degenerate (w or h ≤ 0.011)
  by clipping/normalization.
- **HF-3 Label-driven geometry mutation** — geometry moved/resized to match a label or
  parent name rather than the pixels.
- **HF-4 Fabricated boundary** — a hard mask asserted over evidence that has none
  (painterly dissolve, atmospheric field, engraved line-work). False precision.
- **HF-5 Persistence/render drift** — geometry that is correct in memory but wrong
  after store → reload → render → zoom (the shared stage-geometry contract violated).
- **HF-6 Wrong coordinate frame** — geometry computed against the wrong pixel frame
  (EXIF-untransposed, container-normalized, letterbox-inverted).
- **HF-7 Paratext-as-evidence** — text labels, captions, borders, signatures, UI
  chrome narrated or boxed as depicted content.

---

## 1. Geometry

| dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| boundary quality | none | very loose/leaky | mostly tight, minor bleed | follows the true edge |
| instance separation | all merged | some merged | one merge/split error | each subject its own instance |
| small/thin-part preservation | dropped | present but mangled | slightly clipped | thin part intact |
| multi-component & hole handling | flattened | one ring only | components ok, holes lost | components + holes preserved |
| no anchor imprisonment | HF-1 | — | — | parenting geometry-first |
| no crushed slivers | HF-2 | — | — | no degenerate output |
| mask stability after persist/render/zoom | HF-5 | drifts on zoom | tiny drift | pixel-stable |

## 2. Semantics

| dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| useful category/part name | wrong | generic ("object") | acceptable | precise, curator-grade |
| domain vocabulary | wrong domain | right domain, wrong terms | mostly right terms | native domain vocabulary |
| label–mask agreement | label names a different region | loose | mostly aligned | label describes exactly this mask |
| uncertainty honesty | confident + wrong | no uncertainty signal | flags some doubt | calibrated uncertainty |
| no label-driven geometry mutation | HF-3 | — | — | geometry independent of label |

Domain-vocabulary reference cases from the confirmed set: heritage sculpture and a
devotional lithograph must **not** be called `product` (both currently are); the Pietà
image is correctly `architecture` but no segmenter serves that vocabulary.

## 3. Perceptual analysis

| dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| texture/material usefulness | none | noisy | usable | names the material reading |
| luminous-map correspondence | none/boxed light (HF-4 if boxed as object) | vague | mostly matches | matches the felt light |
| depth-ordering usefulness | wrong order | flat | mostly ordered | correct fg/bg containment |
| repetition-candidate precision | none/false fires | many false fires | mostly precise | clean repetition set |
| measured-evidence vs interpretation | conflated | mostly conflated | mostly separated | measurement and reading kept distinct |

Perceptual targets are `analysis_layer`, **not** boxed regions — boxing a light field
or an atmosphere trips **HF-4**.

## 4. Product circulation

Does the evidence survive the whole Semant loop, not just the model call?

| dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| usable hover bbox derived from mask | none | loose | usable | tight, from the mask |
| correct alpha/context crop | wrong crop | rect only, wrong padding | rect ok | alpha/polygon crop with context |
| Differential selection/refinement | can't select | selects, can't refine | refines roughly | tap-to-refine to exact mask |
| Ground/Percept construction | breaks identity | new ids each run | stable, minor churn | stable ids, many-to-many intact |
| Mention/recall returns exact evidence | wrong evidence | approximate | close | recall replays the exact region |

Identity note: re-running a model must not rewrite unrelated regions or orphan
Grounds/Percepts/Mentions (the code audit flagged wholesale array replacement — a
circulation risk this dimension scores directly).

## 5. Runtime

| dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| cold latency | unusable | slow | acceptable | fast cold start |
| warm latency | unusable | slow | acceptable | interactive |
| peak VRAM/RAM | OOM / over budget | tight | within budget | comfortable headroom |
| swap increase | heavy swap | some | negligible | none |
| cleanup after unload | leaks | partial | mostly frees | fully released |
| failure & fallback behavior | crashes route | silent empty (bad) | degrades noisily | graceful, logged, falls back |

Record raw numbers in the matrix (ms, MB); the 0–3 is against the hardware budget set
by the audit's hardware decision (`../vision-code-audit-001.report.md` §5), which is a
prerequisite input — do not finalize runtime budgets before it lands.

---

## Aggregation

- **Per target:** 5 group sub-scores (mean of that group's dimensions, 0–3) + a HARD
  FAIL flag if any gate tripped.
- **Per image:** mean group scores across its targets; list every HARD FAIL.
- **Per candidate:** mean per-image, **plus** a hard-fail count. **Ranking rule:** a
  candidate with *any* HARD FAIL on the gold subset ranks below any candidate with
  none, regardless of mean. Evidence integrity is lexicographically first.
