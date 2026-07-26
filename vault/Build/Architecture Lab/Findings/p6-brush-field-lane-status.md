# P6 — the brush_field lane: what is live, what is deferred, what is owed

**Status as of P6-H** · branch `circuit/p6-actuator-breadth` · 9 commits ahead of `main`

The frontier survey that opened this lane found the honest gap: `brush_field` had **12 roles and
zero producers**, while every shipped producer served find/gather/connect/compose. P6 closed that
gap. Eight producers now reach the curator through **one** invocation surface.

---

## The four archetypes

The lane is worth reading by *how a field is derived*, not by role name — that is what makes the
next producer cheap or expensive:

| Archetype | Derives the field from | Producers | Model cost |
|---|---|---|---|
| **Mask-derived** | geometry already in the packet | `negative_space` | none |
| **Signal** | the image's own statistics | `rhythm`, `pressure_zone` | none (CPU) |
| **Model-embedding** | a learned representation | `material_field`, `recession`/`atmosphere` | GPU, ~100–235 MiB |
| **Intrinsic** | a physical decomposition of the image | `light_field`, `shadow_field` | GPU — **deferred** |

---

## LIVE — reachable and proven

| Producer | Role(s) | Adapter | Receipt | Proof |
|---|---|---|---|---|
| `negative_space` | `negative_space` | none (pure geometry) | run + producer, **no model** | live browser: accept minted a field |
| `material_field` | `material_field` | `dinov2_vits14` (GPU) | **full** — model/checkpoint/latency/vram | live browser + real inference, 99.1 MiB |
| `rhythm` | `rhythm` | `cpu_perceptual` (CPU_LIGHT) | adapter + latency, **no model** | live browser: field + refusal |
| `pressure_zone` | `pressure_zone` | `cpu_perceptual` (CPU_LIGHT) | adapter + latency, **no model** | component-level only |
| `recession` | `background_recession`, `atmosphere_field` | `depth_anything_v2_small` (GPU) | **full** | real GPU inference: warm 120 ms, 233.9 MiB |

All five are registered in the route registry, selectable in the Field tool, and flow through the
**unchanged** `suggestionQuarantine → SuggestionReview` path. No producer has its own route or its
own review UI — that was the point of P6-C.

## DEFERRED — wired, weights absent

| Producer | Role(s) | Why deferred |
|---|---|---|
| `shading` | `light_field`, `shadow_field` | Intrinsic is a **GitHub-only install**, not PyPI/HF |

**The exact activation cost** (nothing here is feature work):

1. `pip install git+https://github.com/compphoto/Intrinsic`
   ⚠️ **`pip install intrinsic` is a trap** — PyPI carries only an unrelated `0.0.1` stub under
   that name. `is_available()` deliberately probes `intrinsic.pipeline` + `chrislib`, which the
   stub would not satisfy.
2. Two further GitHub-only dependencies: `chrislib`, `altered_midas`.
3. Checkpoints are **not on the HF hub** — `load_models('paper_weights')` fetches from the
   project's own hosting.
4. **Confirm one thing:** the pipeline result's shading key. The package cannot be imported here,
   so `_extract_shading` tolerates `inv_shading` / `shading` / `gry_shd` / `ord_shading`. Pin it.

A route test (`test_produce_field_shading_runs_end_to_end_once_the_package_is_present`) flips
`is_available()` and proves light and shadow flow end-to-end with a full receipt through code that
does not change on activation. Until then the endpoint answers `unavailable` honestly — never an
error, never a fabricated light field.

---

## Remaining `brush_field` roles

Four of twelve are still unbuilt:

| Role | Needs | Shape of the work |
|---|---|---|
| `gaze_field` | DeepGaze IIE | new adapter; VRAM-tight on 4 GB — measure before committing |
| `threshold`, `fold` | CLIPSeg | new adapter; phrase → heatmap, so it also opens *prompted* fields |
| `fall_of_light` | **nothing new** | the converter (`shading_gradient`) already ships — but it is a **`trace_mark`**, not a field |
| `external_limit` | PerspectiveFields | belongs with the trace lane, not here |

`fall_of_light` is the interesting one: the measurement exists and is tested, but a *direction* is
a different mark family. It is the natural bridge into the **`trace_direction` lane** (8 roles,
still at zero producers) — the same position `brush_field` was in when P6 opened.

---

## Honest ledger — proofs still owed

Not everything claimed here was proven the same way. Ranked by how much it matters:

1. **`pressure_zone`, `recession`, `atmosphere`, `light`, `shadow` have no live-browser proof.**
   They are verified at component level (real modules, ingest → accept → dismiss) and, for
   recession, by real GPU inference — but nobody has watched them land in the review panel.
   P6-E/F/G were specified unattended, so this is by instruction, not oversight.
2. **`rhythm`'s refusal threshold is uncalibrated.** Real photographs never fall below ~0.44
   relief (measured across a whole image), so the 0.05 threshold effectively only rejects
   genuinely blank surfaces. Honest, but rarely binding. Calibrating against a corpus sample —
   rather than the two synthetic extremes it was tuned on — is outstanding.
3. **Intrinsic's result key is unconfirmed** (see above).
4. **No producer has been run against a *fashion* or *architectural* image.** Every proof used one
   sculpture photograph. Domain routing exists; whether these fields read sensibly across domains
   is untested.

## Data safety

Every live proof after P6-C ran on **scratch posts**, deleted afterwards. P6-C's proof did not:
accepting a suggestion there wrote a mark *and a ground* to a real post. Both were reverted and
that post is byte-identical to its original (`updated_at 2026-01-05 16:31:58.699000`, `grounds: 0`,
`visual_marks: 0`). The lesson is recorded because it is a property of the product, not of the
test: **Accept persists**, so any live proof belongs on a scratch post.
