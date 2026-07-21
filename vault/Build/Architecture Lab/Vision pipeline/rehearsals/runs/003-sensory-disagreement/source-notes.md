# 003 — Source notes

## The subject

Post `695be786a9ea58f1b6aef5ed`, read **read-only** from the live `visualDictionaryDB`. Its image
was downloaded once from `photo_url` and frozen locally so the rehearsal does not depend on a
remote URL.

- `fixtures/003-sensory-disagreement/carved-figure-close.jpg`
- 452 × 679 JPEG, 52 470 bytes
- `sha256: 12eaa7e7a44d17cf7ee6514181a6bcf319ccd7f1b6117d27947fb0ec583c89f4`

**reproduction_vs_depiction: `depiction`.** A single photograph of one carved stone object — not a
composite plate, scan, or collage. This is recorded per the amendment carried from run `002F`,
where reproduction-vs-depiction completely determined the outcome.

**What it is:** a close-up of a carved stone figure — elaborate headdress, face in profile,
shoulder, breast, torso, and a raised arm, with further relief carving behind and to the left. The
stone is a warm dark brown; probe 2 read it as "basalt or granite", which is plausible but
**unverified** and load-bearing on nothing here.

**Metadata status:** `title` is null, `description` is empty. No catalogue number, collection,
date, region, or material is recorded. No iconographic identification was attempted — the figure is
not named, dated, or attributed anywhere in this rehearsal.

## Pre-existing annotation layer — this is the subject, not just context

Unlike other runs, the persisted layer *is* what A2 examines:

**7 regions, every one architectural:**

| id | label | bbox (x, y, w, h) |
|---|---|---|
| `refine_c6485b9a94` | — | 0.0, 0.0, 1.0, 1.0 |
| `arch_0` | **wall** | 0.0, 0.0, 0.403, 0.530 |
| `arch_1` | **wall** | 0.367, 0.0, 0.350, 0.140 |
| `arch_2` | **wall** | 0.124, 0.543, 0.179, 0.134 |
| `arch_3` | **wall** | 0.836, 0.747, 0.164, 0.227 |
| `arch_4` | **floor** | 0.0, 0.823, 0.535, 0.177 |
| `arch_5` | **floor** | 0.783, 0.909, 0.217, 0.091 |

**5 grounds, 2 percepts** — see `score.md` for the detachment table. The two percepts are the
curator's own words: `pctx_mrqp950d_0` = "the upper head"; `pctx_mrqpamw0_1` = "braided aspect
which is commonly found in indian rock cut architecture".

The referenced regions `fine_0` ("face") and `fine_3` ("hair") **are not present** in the current
region set. That absence is the finding.

## Discrepancy with the governing document

R0's breadth portfolio describes this fixture as *"architecture `695be786` (wall/floor, single
image)"*. That description matches the **region labels**, not the image. Reported in `score.md`
rather than silently corrected, because the portfolio's error and the detector's error have the
same root: taking `arch_* = wall` at face value.

## No text source

No theoretical text is loaded. R5 tests a counterforce between channels; the evidence needed is
material and semantic, not textual. `source_pressures` is empty by choice.

## Model

`qwen/qwen3.6-27b` on Groq, `reasoning_effort: "none"`. Two calls, 25 s apart, no retries, no
provider failures. Both `finish_reason: "stop"`, no `<think>` leakage. Raw text frozen verbatim —
**no JSON parsing was attempted on either response**, so the greedy-regex parse risk noted in the
batch plan did not arise.

Neither prompt named a refusal token (amendment 1 from `002F`).

## Reproducing the measurements

Chromaticity figures in `score.md` are model-free: convert to float RGB, drop pixels with
channel-sum ≤ 30 (near-black carries no reliable hue), normalise each pixel by its own sum, then
average. Patches: the detector's own bboxes for `arch_0`/`arch_2`/`arch_4`, and hand-sampled figure
patches at torso (0.42, 0.42, 0.16, 0.14), shoulder (0.55, 0.55, 0.14, 0.14), headdress
(0.28, 0.10, 0.14, 0.12).

## Honesty notes

- The `fine_*` → `arch_*` replacement is **inferred** from dangling references, not observed. There
  are 0 `vision_runs` for this post and 1 in the whole database.
- The head bbox overlap figure (70.1 %) is the fraction of the *model's* box inside `arch_0`, not
  an IoU.
- No production document was written at any point.
