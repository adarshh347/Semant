# PERCEPTUAL-FORMS-001C — findings

**Date:** 2026-08-22 · **Machine:** Apple Silicon Mac mini, 16 GB unified, MPS, torch 2.13.0,
transformers 5.14.1 · **Budget:** ~10 GB accelerator memory · **Lane A contract:**
`perception-lab.v1`, merged at `cff9251`

Eighteen trials over ten synthetic controls. Every number below is in
`runs/<trial-id>.json` and every picture is in `previews/`.

---

## The matrix

| form | candidate | verdict | why, in one line |
|---|---|---|---|
| `extent.soft_field` | **ViTMatte small** (Apache-2.0, 103 MB, 25.8M) | **ADOPT AS EXPERIMENTAL** | recovers true coverage to 0.010–0.016 mean alpha error and invents no fringe on a crisp edge |
| `extent.soft_field` | SAM 2 raw mask logits (Apache-2.0, resident) | **REJECT** *for this form* | reports 5% of the true softness on the one control that is genuinely boundary-less |
| `extent.fused_hypothesis` | **DINOv2 ViT-S/14 affinity** (Apache-2.0, resident) | **ADOPT AS EXPERIMENTAL**, as one ground only | ranks two lookalikes above four true fragments; it measures resemblance, not unity |
| `extent.fused_hypothesis` | **Depth Anything V2 small** (Apache-2.0, resident) | **ADOPT AS EXPERIMENTAL**, as one ground only | supplies the occlusion ordering a fusion claim needs; never an Extent measurement |
| `extent.visible_inferred_partition` | pix2gestalt | **DEFER** — resources | 22–28 GB VRAM against a 10 GB budget. Not downloaded, not run, not integrated |
| `extent.visible_inferred_partition` | Amodal SAM (arXiv 2604.20748) | **DEFER** — no weights | a SAM adapter that would fit the budget; no public checkpoint found on 2026-08-22 |
| `extent.density_field` | DAVE / GeCo low-shot counters | **REJECT** *as a producer* | they need exemplars and carry research-use terms; the form does not need a model at all |

**No form is invalidated by any of these verdicts.** All four remain well-formed and producible
by hand or by fixture, which is exactly what Lane A's `deferred` state was for.

---

## `extent.soft_field`

### The question the controls were built to settle

Three quantities keep being confused, and only the first is what this form holds:

| | what it is | is it soft occupancy? |
|---|---|---|
| **alpha** | the fraction of the pixel the thing covers | **yes — this is the form** |
| **sigmoid(logit)** | how far a decoder's decision surface sits from its threshold | no |
| **IoU prediction** | how good the model thinks the whole mask is | no, and it is not even per-pixel |

`hair-veil` separates the first from the third better than anything else here. The model is *not
unsure* where the hair is; the pixel is genuinely 30% hair. A producer reporting that as
`uncertain` has mislabelled a measurement as a doubt.

### SAM 2 raw logits — REJECT for this form

| control | true soft fraction | observed | transition width | reading |
|---|---|---|---|---|
| `hard-edge` | 0.000 | 0.009 | 3.1 px | passes: it does **not** invent a wide fringe |
| `soft-fog` | 0.631 | **0.034** | 11.1 px | **fails**: 1/19th of the true softness |
| `hair-veil` | 0.370 | 0.686 | 50.1 px | fails: nearly 2× too much, and no alpha to compare |

Look at `previews/sam2_logits.soft-fog.png`. A haze filling the frame comes back as a small bright
core. The logit field is a **sharpened mask**: it has a transition width set by the decoder's own
resolution rather than by the picture, and it cannot represent a gradient that has no edge at all.

The IoU predictions confirm the published account — 0.992 on `hard-edge`, 0.31 on `soft-fog`.
That scalar is a mask-level quality estimate ("Mask-level Confidence Confusion"), and it says
nothing about which pixels near the boundary are reliable.

**Rejected for `extent.soft_field`, not for its own job.** SAM's masks remain the right producer
for `extent.hard_mask`, and its logits remain a legitimate *proposal* — for a fringe hint or a
trimap seed — as long as nothing writes them into a field and calls them coverage.

### ViTMatte small — ADOPT AS EXPERIMENTAL

`hustvl/vitmatte-small-composition-1k` · Apache-2.0 · 25.8M params, ~103 MB ·
1.18 GB MPS allocation · cold 1.4–1.6 s, warm **0.12–0.17 s** at 256².

| control | band | true alpha mean | observed | error | true soft frac | observed |
|---|---|---|---|---|---|---|
| `hard-edge` | 10 px | 0.2500 | **0.2502** | **0.0002** | 0.000 | 0.006 |
| `soft-fog` | 10 px | 0.2712 | 0.3419 | 0.0708 | 0.631 | 0.164 |
| `soft-fog` | 70 px | 0.2712 | **0.2876** | **0.0164** | 0.631 | **0.696** |
| `hair-veil` | 10 px | 0.1358 | **0.1258** | **0.0100** | 0.370 | 0.436 |
| `hair-veil` | 70 px | 0.1358 | 0.1626 | 0.0268 | 0.370 | 0.581 |

Three things this establishes:

1. **It does not invent softness.** On the negative control the recovered alpha mean is within
   0.0002 of exact and the fringe is 0.6% of the frame — the anti-aliasing of the trimap band,
   not a gradient.
2. **It recovers sub-pixel coverage.** 7% relative error on filaments thinner than a pixel, with
   each strand individually resolved (`previews/vitmatte.hair-veil.png`).
3. **The trimap band must match the scale of the graded region.** This is the finding with the
   most consequence for Lane G. A 10 px band around a threshold is right for hair and wrong for
   fog — widening it to 70 px cuts the fog error by **4.3×** (0.071 → 0.016) and simultaneously
   makes hair *worse* (0.010 → 0.027). There is no single correct band.

**Why EXPERIMENTAL and not ADOPT.** Three things are unmeasured, and each is a real gate:

- **Calibration is untested.** Every trial records `calibration.state: uncalibrated`, honestly.
  Alpha being close to true alpha on three synthetic controls is not a calibration; that needs a
  held-out set with measured reliability, and nothing here provides one.
- **Only synthetic controls.** These are flat-coloured composites. Fog in a de Chirico is not fog
  in a gradient, and the Lane F corpus is the actual test.
- **It is trimap-based, so it inherits its input's error.** ViTMatte decides nothing outside the
  unknown band. A soft field produced this way is a *derivation of a hard mask*, and Lane A
  already has the vocabulary for that.

---

## `extent.fused_hypothesis`

### DINOv2 patch affinity — ADOPT AS EXPERIMENTAL, as one ground among several

`facebook/dinov2-small` · Apache-2.0 · resident · 107 MB MPS · warm **0.017–0.022 s**.

| control | truth | mean cosine | min | expected |
|---|---|---|---|---|
| `fence-tree` (4 fragments of one blob) | **one entity** | 0.942 | 0.884 | high |
| `false-twins` (two identical blobs) | **not one entity** | **0.947** | 0.947 | should be lower |
| `lit-floor` (one surface, half in shadow) | **one entity** | **0.925** | 0.925 | should be higher |

**The ordering is exactly wrong.** The thing that is not one object scores highest; the thing that
is one object scores lowest. That is not a defect in DINOv2 — it is what a patch cosine *is*. It
answers "do these look alike", and the two controls that break it are precisely the two cases
Extent cares about: things that look alike and are not one, and one thing that does not look alike
across itself.

*Caveat, stated because it bounds the claim:* these controls are flat-coloured, which gives a
texture-sensitive backbone little to work with. A photograph would likely separate `false-twins`
better. It would not fix `lit-floor`, which is the harder case and the one the tree-behind-a-fence
scene actually depends on.

**So it is adopted as a `Ground`, never as a decider.** Lane A's `extent.fused_hypothesis` already
requires `grounds` to be a non-empty list of typed records with per-ground `strength`, precisely so
that one signal cannot carry a claim. This is one of them, of kind `appearance_continuity`, with
the cosine as its strength. Anything that let it *decide* fusion would ship the `false-twins` error
as a fact.

### Depth Anything V2 small — ADOPT AS EXPERIMENTAL, as one ground among several

`depth-anything/Depth-Anything-V2-Small-hf` @ `5426e4f0` · Apache-2.0 · resident · 1.23 GB MPS ·
warm **0.08–0.25 s**. Deterministic across repeats.

It supplies the one thing a fusion claim genuinely needs and appearance cannot give: **the fence is
in front of the tree**. That is a `Ground` of kind `occlusion_hypothesis` or `depth_continuity`.

**It is never an Extent measurement**, and the trial records `is_an_extent: false` and
`units: "relative inverse depth, no zero and no scale"` so no reader can mistake it. Reading it as
occupancy would make a far wall "0.2 occupied" rather than "0.2 near". In Lane A's terms depth
belongs to the Depth organ; Extent may cite it and may not produce it.

**Newer option, not adopted here:** Depth Anything 3 ships `DA3-SMALL` (0.08B) and `DA3-BASE`
(0.12B) under Apache-2.0 — `DA3-LARGE` and above are CC-BY-NC and are not usable. DA3-SMALL is a
lawful, in-budget upgrade. Not swapped in this lane because depth is supporting evidence and V2 is
already resident and already pinned; worth a single A/B before Lane G commits.

---

## `extent.visible_inferred_partition` — DEFER, twice, for two different reasons

**pix2gestalt — DEFERRED on resources, not failed on merit.** The published demo needs roughly
22–28 GB of VRAM against a 10 GB budget. **Not downloaded, not run, not integrated**, per the
resource rule. Its Stable-Diffusion-1.5 lineage also carries CreativeML OpenRAIL-M, which needs a
licence decision separate from the hardware one.

**Amodal SAM — DEFERRED on availability.** Published April 2026 (arXiv 2604.20748) as a
lightweight spatial-completion adapter on SAM, which would sit comfortably inside the budget if
released. No public checkpoint was found on 2026-08-22. Re-check before Lane G rather than
adopting on the strength of a paper.

**What holds regardless of which model eventually arrives.** Amodal completion is a **hypothesis**,
permanently. Lane A's `ExtentPartitionPayload` already enforces it: the `inferred` part may be
`interpretive` or `uncertain` and the schema refuses `visible` or `measured` — and the
`inferred_completion` partition caps the whole artifact at `uncertain` on any basis, at any
confidence. **No model changes that.** The right integration for whichever model lands is to fill
the `inferred` region and nothing else, leaving `visible` to the hard mask that measured it, and
`unknown` to the part neither saw nor inferred.

`occluder-table` is ready for that day: it records `hidden_fraction` and the exact band, so a
hallucinated-structure rate can be computed the moment there is something to compute it on.

---

## `extent.density_field` — REJECT the model, keep the form

Low-shot counters (DAVE, CVPR 2024; GeCo, NeurIPS 2024; GeCo2, AAAI 2026) are the strongest
current family, and none of them should produce this form:

1. **They need exemplars or a text prompt.** That makes a counter an *operation a person invokes*,
   not a producer of a standing field. Lane A separates those registries for exactly this reason.
2. **Their published terms are research-use.** A verdict that needs a licence review before it can
   ship is not an adoption.
3. **The form does not need a model.** `ExtentDensityFieldPayload` separates `members_counted`,
   `samples_taken` and `smoothing` on purpose. The counts come from an extent set the lab
   *already measured*; only the smoothing kernel needs deciding, and that is arithmetic.

`crowd-plaza` (60 marks, 45 east / 15 west), `windows-facade` (20 regular openings) and
`sparse-objects` (3) are committed for the day someone wants to A/B a counter against
measured-and-smoothed. The measured route should be the baseline a model has to beat.

**No weights were fetched for this candidate.**

---

## Model residency and cost

| candidate | licence | size | MPS allocation | cold | warm | resident already |
|---|---|---|---|---|---|---|
| DINOv2 ViT-S/14 | Apache-2.0 | 85 MB | 107 MB | 0.7–2.8 s | 0.017–0.022 s | yes |
| Depth Anything V2 small | Apache-2.0 | 95 MB | 1.23 GB | 0.8 s | 0.08–0.25 s | yes |
| SAM 2.1 hiera-tiny | Apache-2.0 | 149 MB | 1.21 GB | 0.2–0.3 s | 0.27–0.40 s | yes |
| ViTMatte small | Apache-2.0 | 103 MB | 1.18 GB | 1.4–1.6 s | 0.12–0.17 s | **fetched here** |

All four together are ~3.7 GB against a 10 GB budget, and only ViTMatte is new. Every trial was
deterministic across repeated runs on identical input.

---

## Exact integration instructions for Lane G

### 1. `extent.soft_field` — a ViTMatte adapter, and the four things it must record

Add `backend/services/vitmatte_service.py` on the house pattern: `CHECKPOINT`, a **pinned**
`REVISION` (this lane deliberately did not pin one — resolve the commit at integration and record
it), `MODEL_TAG`, `is_available()`, lazy load, and a module-level `unload()` so
`model_residency.imported_releasables()` discovers it without a list edit. Add the entry to
`weights.manifest.json` with `license: Apache-2.0` and `size_human: ~103 MB`.

**The trimap is 0–255, not 0–1.** `VitMatteImageProcessor` has `do_rescale=True` with factor
1/255 and applies it to the trimap as well as the image. A trimap handed over in [0, 1] arrives as
uniform "definite background" and the model returns an all-zero alpha — which looks exactly like a
model that cannot do the job. The first run of this harness fell into it. Assert the range at the
adapter boundary.

**Record the band radius in the payload's `basis_detail`.** It is the single biggest determinant
of the result (4.3× on fog) and it is a *decision*, not a constant. A field whose record does not
say which band produced it cannot be compared with another field.

**Declare `derivation: direct_probability` and `calibration.state: uncalibrated`.** Not
`blur_of_binary_mask` — this is a real matte, and Lane A's schema would refuse the pair
`blur_of_binary_mask` + `calibrated` anyway. `nominal` becomes available only once someone measures
a correspondence; `calibrated` needs a method *and* a reference, and the schema enforces both.

**Set the epistemic frame:** `epistemic_basis: mask` (the trimap came from one),
`partition: exact_derivation` (a derivation of a hard mask, adding no new evidence), and therefore
`input_refs` must name the hard mask — the schema refuses a derivation that cites nothing. The
status is then capped by the weakest of the basis ceiling, the partition ceiling and the input's
own status; call `definitions.derived_ceiling(...)` and record what it returns.

**Enabling the form is two edits and no more:** declare an operation producing `extent_soft_field`,
and move the form's `state` to `enabled`. The parity test that asserts
`state == enabled ⟺ produced_by_operations` will fail if you do half of it.

### 2. `extent.fused_hypothesis` — two grounds, never a decider

Both DINOv2 affinity and Depth V2 fill `Ground` records inside the hypothesis payload. Neither may
be the sole ground, and **nothing may compute fusion from a threshold on either**. `false-twins`
is the committed proof of what that would ship.

Suggested shape: `GroundKind.APPEARANCE_CONTINUITY` with the pooled patch cosine as `strength`,
`GroundKind.OCCLUSION_HYPOTHESIS` with the depth ordering, and a third ground from geometry
(severed-edge continuation) that this lane did not evaluate. The hypothesis stays
`interpretive_grouping` when it only groups what is visible and `inferred_completion` the moment it
asserts hidden extent — the schema already refuses `asserts_hidden_extent` under the former.

Before adopting, re-run `dinov2_affinity` on the Lane F corpus. If the ordering is still wrong on
real paintings, downgrade the ground's default `strength` rather than dropping it.

### 3. `extent.visible_inferred_partition` — do not integrate a model yet

Re-check Amodal SAM for a released checkpoint; adopt only after running `occluder-table` and
measuring the hallucinated-structure rate against the recorded `hidden_fraction`. pix2gestalt stays
deferred until the hardware or a distilled variant changes, and needs an OpenRAIL-M decision
independently.

Manual and fixture production of this form works today and should be the route until then.

### 4. `extent.density_field` — build the measured route first

Counts from an existing `extent_set`, a declared smoothing kernel, `counts_are_exact: true`, and
`derivation: kernel_density`. Lane A's schema already refuses a smoothed field that names a
derivation doing no smoothing. Only benchmark a counter after that baseline exists.

### 5. What must not happen, in any lane

- No `sigmoid(logit)` written into `extent.soft_field`. `sam2_logits.soft-fog` is the committed
  counter-example.
- No depth written into any Extent form.
- No `calibrated` calibration state without a measured method and reference.
- No amodal output at `visible` or `measured`, at any confidence.
- No VLM or LLM painting geometry. Naming and proposing are theirs; occupancy is not.

---

## Sources

- ViTMatte — [hustvl/vitmatte-small-composition-1k](https://huggingface.co/hustvl/vitmatte-small-composition-1k) (Apache-2.0, 25.8M params), [transformers docs](https://huggingface.co/docs/transformers/en/model_doc/vitmatte)
- MatAnyone / MatAnyone 2 — [pq-yang/MatAnyone](https://github.com/pq-yang/MatAnyone), [pq-yang/MatAnyone2](https://github.com/pq-yang/MatAnyone2) — CVPR 2025 / CVPR 2026 Highlight, **NTU S-Lab License 1.0** (non-commercial) and video-oriented; not evaluated for that reason
- SAM 2 — [facebookresearch/sam2](https://github.com/facebookresearch/sam2), [SAM 2 paper](https://arxiv.org/pdf/2408.00714)
- Mask-level Confidence Confusion — [Segment Anything with Robust Uncertainty-Accuracy Correlation](https://arxiv.org/html/2605.10603v1)
- DINOv2 — [facebook/dinov2-small](https://huggingface.co/facebook/dinov2-small) (Apache-2.0)
- DINOv3 — [facebookresearch/dinov3](https://github.com/facebookresearch/dinov3), [paper](https://arxiv.org/html/2508.10104v1). ViT-S/16 is 21M and would fit; weights are behind a Meta access request under the DINOv3 License, so it is an upgrade path with a licence step, not a drop-in
- Depth Anything V2 — [depth-anything/Depth-Anything-V2-Small-hf](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf) (Apache-2.0)
- Depth Anything 3 — [ByteDance-Seed/Depth-Anything-3](https://github.com/ByteDance-Seed/Depth-Anything-3), [DA3-BASE](https://huggingface.co/depth-anything/DA3-BASE). SMALL/BASE Apache-2.0; LARGE and above CC-BY-NC
- pix2gestalt — [cvlab-columbia/pix2gestalt](https://github.com/cvlab-columbia/pix2gestalt) (CVPR 2024)
- Amodal SAM — [arXiv 2604.20748](https://arxiv.org/abs/2604.20748)
- DAVE — [arXiv 2404.16622](https://arxiv.org/abs/2404.16622), [jerpelhan/DAVE](https://github.com/jerpelhan/DAVE); GeCo — [arXiv 2409.18686](https://arxiv.org/abs/2409.18686), [jerpelhan/GeCo](https://github.com/jerpelhan/GeCo); GeCo2 — [jerpelhan/GECO2](https://github.com/jerpelhan/GECO2/) (AAAI 2026)
- CLIP-Count — [arXiv 2305.07304](https://arxiv.org/abs/2305.07304)
