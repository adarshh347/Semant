# PR draft — CIRCUIT-001 P6: the brush_field lane

> Draft only. Not opened. Target: `circuit/p6-actuator-breadth` → `main`.
> 9 commits · 28 files · +3149 / −6 (backend 12, frontend 7, docs/screenshots 9).

---

## Title

```
CIRCUIT-001 P6 — brush_field producers: eight fields on one invocation surface
```

## Body

### Why

A frontier survey of the actuator matrix found the gap plainly: **`brush_field` had 12 roles and
zero producers.** Every producer shipped to date (`sam_refine`, `semantic_read`, `find_similar`)
served find / gather / connect / compose. Nothing could propose a *field* — the felt, uneven,
non-object reading that most of Semant's vocabulary is actually about.

This branch closes that gap and, more importantly, builds the surface so the *next* producer is
cheap: one generic endpoint, one review path, four worked archetypes.

### What shipped

**The surface (P6-C)** — one generic endpoint, `POST /{post_id}/produce-field`, taking
`(producer, region_ref, seed/params)` and dispatching through a registry. A new producer plugs in
with **one row**, never a new route. GPU producers go through `ModelManager` / `ResourceKind.GPU`;
CPU producers run inline. Everything returns quarantined `model_suggested` descriptors into the
**unchanged** `suggestionQuarantine → SuggestionReview` path. A `Field` tool in the Differential
workspace selects the producer; the review UI was not touched.

**Eight producers across four archetypes:**

| Archetype | Producer | Role(s) | Adapter | Receipt |
|---|---|---|---|---|
| Mask-derived | `negative_space` | `negative_space` | — | run + producer, no model |
| Model-embedding | `material_field` | `material_field` | `dinov2_vits14` | full |
| Signal | `rhythm` | `rhythm` | `cpu_perceptual` | adapter + latency, no model |
| Signal | `pressure_zone` | `pressure_zone` | `cpu_perceptual` | adapter + latency, no model |
| Model-embedding | `recession` | `background_recession`, `atmosphere_field` | `depth_anything_v2_small` | full |
| Intrinsic | `shading` | `light_field`, `shadow_field` | `intrinsic_ordinal_shading` | full — **deferred** |

**Two adapters that were spec-only became real:** `cpu_perceptual` (OpenCV + numpy; the
`cheap_signals` job in `planner.py` had referenced it since VISION-ORCHESTRATOR-001 and it
resolves now) and `depth_anything_v2_small`. One is new and deferred: `intrinsic_ordinal_shading`,
plus a `Capability.SHADING` row-family.

### The invariants this branch is really about

- **A producer may propose; only a human commits.** Every descriptor arrives `model_suggested` /
  `suggested`, uncitable until accepted; acceptance mints a *derived* mark.
- **A receipt cannot be faked or padded.** Deterministic producers name an adapter and **no
  model**, because nothing was inferred. Inferring producers carry the full receipt
  (model/checkpoint/preprocessing/latency/peak VRAM). `confidence` never enters `provenance` —
  a mark may not carry a confidence score (contract §6) — so it rides the descriptor instead, and
  a descriptor that tries to launder it into provenance **fails closed**.
- **A tool that cannot say "nothing here" is not finished.** Every producer has a tested refusal:
  no mask, no seed, a flat surface, an isotropic surface, a scene with no depth relief, an
  evenly-lit wash. Refusals return `status: "empty"` / `"unavailable"` at HTTP 200 — never an
  error, never a fabricated field.
- **One GPU model resident at a time.** Verified with real weights: loading Depth evicts DINOv2
  and vice versa (VRAM swaps 84.1 ↔ 94.6 MiB, never sums); explicit unload releases to 0.0 MiB.

### Verification

- **Backend 433 → 504** (+71). **Frontend 751 → 771** (+20). Production build clean throughout.
  (Baselines measured by running each suite at `origin/main` in a detached worktree. Backend
  reports `430 passed, 3 skipped` there: the 3 skip on a schema fixture that is untracked, so they
  run in a normal working tree — 433. Nothing on this branch changes them.)
- **Real inference measured:** DINOv2 material 99.1 MiB peak; Depth-Anything warm 120 ms / 233.9
  MiB peak, both released cleanly.
- **Live browser proof** for `negative_space`, `material_field`, `rhythm`: select → produce →
  quarantined suggestion → **Accept mints a rendered field mark**; **Dismiss discards**; a flat
  surface shows *"Nothing here — no field to propose."* Screenshots committed under
  `vault/Build/Architecture Lab/Vision pipeline/`.

### Deferred, and exactly why

`shading` (light/shadow) ships **wired but weightless**. Intrinsic is a GitHub-only install
(`compphoto/Intrinsic` + `chrislib` + `altered_midas`) whose checkpoints are not on the HF hub —
and `pip install intrinsic` resolves to an **unrelated 0.0.1 stub**, so `is_available()`
deliberately probes `intrinsic.pipeline` rather than the bare name. The adapter registers
`deferred`, `ModelManager` refuses to execute it, and the endpoint answers `unavailable` honestly.
A route test flips `is_available()` and proves the full path works unchanged once installed —
activation is an install plus one call-shape confirmation, not feature work.

### Non-scope

No new grammar. No canvas paint outside the existing accept → mint flow. No changes to the
working `refine` / `find-similar` / `semantic-read` routes. No changes to the review UI. No
`trace_direction` producers — though `shading_gradient` (the fall of light) ships tested and is
the natural bridge into that lane.

### Data safety

Live proofs after P6-C ran on **scratch posts**, deleted afterwards. P6-C's own proof did not: it
wrote a mark **and a ground** to a real post. Both were reverted; that post is byte-identical to
its original (`updated_at 2026-01-05 16:31:58.699000`, `grounds: 0`, `visual_marks: 0`), and the
corpus is back to 451 posts. The lesson is a property of the product, not the test — **Accept
persists** — so any live proof belongs on a scratch post.

### Known gaps (deliberately not hidden)

1. `pressure_zone` / `recession` / `light` / `shadow` have **no live-browser proof** — component
   level only. Their gates were specified unattended.
2. `rhythm`'s refusal threshold is **uncalibrated**: real photographs never fall below ~0.44
   relief, so 0.05 rejects only genuinely blank surfaces. Honest, rarely binding.
3. Intrinsic's result key is unconfirmed (tolerant extraction, flagged in-code).
4. Every proof used **one sculpture photograph** — no fashion or architectural image tested.

Full ledger: `vault/Build/Architecture Lab/Findings/p6-brush-field-lane-status.md`.

### Review suggestions

Read in gate order — each commit is one working, revertable capability:
`P6-A` (the cheapest door) → `P6-C` (the surface, the load-bearing commit) → `P6-D` (the third
archetype; note the relief-refusal fix, which a live cv2 run forced) → `P6-G` (three commits:
scaffold / logic / wiring).

The two places most worth a careful eye: the **receipt discipline** in `suggestion_service`
(what may and may not appear in `provenance`) and the **refusal thresholds**, which are the honest
weak point of the branch.
