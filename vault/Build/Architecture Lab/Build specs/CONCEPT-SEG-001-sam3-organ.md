**Mode:** build. Production code, tests, PR.
**Branch:** `feat/roles-and-sam3` (worktree `../semant-roles`), on top of `ROLES-001`.
**Status:** **BUILT.** Wired, tested, and exercised against the real weights on this Mac. **Off by default** — see §1.
**Test delta:** backend **1159 → 1188** passed (+29), 9 skipped, 0 failed. Frontend **944 passed, unchanged**.
**Gate:** `SF-004-R2` returned **QUALIFIED GO** — GO on quality, and the latency clause explicitly missed. §1 is how that verdict is honoured rather than rounded up.
**House rule:** K-9 — every figure below is measured. The SAM 3 numbers come from `SF-004-R2` or from the guarded run in §5.

---

# CONCEPT-SEG-001 — SAM 3 as the first new organ-role

## 0. What it is

A new organ role, `concept_segmentation`, that takes an image and a **concept** and returns **real pixel masks for every instance of it** — in place of the SŪKṢMA fine-parts stage, which currently asks a VLM to dissect the picture and returns boxes the model estimated, with no `mask_rle` at all.

The measured difference, from `SF-004-R2` §4.2: **27 of 35 concepts really masked, against 0 masks on 72/72 baseline parts.**

## 1. The gate, honoured rather than rounded up

The directive gates this on *"the `SF-004-R2` spike returning GO (SAM 3 runs at usable latency on the Mac)"*, and instructs: *"Build the role plumbing now; wire the live model on GO."*

**The spike returned QUALIFIED GO, and the qualification is precisely the latency clause in that parenthetical.** Measured: 5,292 ms per concept warm on an Apple M4; 63–67 s per image across ~12 concepts, against 3.3–39.6 s for the single VLM call it would sit behind. That is a GO on quality and a miss on cost.

So the whole thing is built — adapter, capability, role, actuator, runner, two-status emission, fallback — and **the SŪKṢMA switch ships OFF**, behind `SEMANT_SUKSHMA_CONCEPT_SEGMENT`. Nothing is stubbed and nothing is pretend; the organ runs on demand today through the `concept_segment` actuator. What is withheld is making it the default path for every dissect, which on the measured numbers is a large wall-clock regression.

Two further gates are structural rather than a judgement call:

- **`is_available` turns on the weights being on disk**, not on the library importing. ~3.2 GiB, fetched out of band. A deploy without them (Render) reports the capability DOWN and the stage falls back to the VLM, saying so. Nothing downloads inside a live route — that is not a fallback, it is an outage.
- **Domain evidence is recorded, not yet enforced.** Photograph 11/12, engraving 11/12, **painting 5/11** on an art-heavy corpus. Three fixtures is not a domain policy, so the numbers sit in `CONCEPT_SEGMENT_DOMAIN_NOTE` beside the code that would use them rather than becoming a gate on evidence that thin.

## 2. The honest core: one object, two statuses

`SF-004-R` §5.3 recorded that SAM 3 gives one object two statuses at once and **nothing emitted it**. This is the emission.

| | producer | status | carries |
|---|---|---|---|
| the extent | `concept_segment` | **`measured`** | the real `mask_rle` — computed off the image signal |
| the naming | `concept_naming` | **`interpretive`** | the label — which came from the prompt |

**SAM 3 never named anything.** It was handed a name and measured where that name lands. So the words are not its claim to make; they belong to whoever wrote the prompt.

Why this is not pedantry, in one measured case (`SF-004-R2` §4.3): on a painting, `shoulder fabric` at confidence 0.27–0.43 returned a clean, well-formed mask — **of the background**. The geometry was right and the words were wrong. Under a single status a reviewer must accept both or bin both, and it is neither.

Mechanically, the two descriptors are the shape the VLM's own namings already use:

- the extent is a `region_mask` with `geometry.kind == "raster_mask"` and an **empty label**;
- the naming is a `region_mask` in `region_ref` mode with the label and **no geometry at all** — the existing law that a reading never mints an extent;
- the naming's `source_ref` points at the extent, so review can accept one and reject the other and still know which mask was meant.

Both pass `epistemics.guard()`. A naming that leaked out tagged `measured` is refused there rather than in review.

### 2.1 Where the ceilings live, and the one that deliberately does not

- `sam3` is an **organ role with ceiling `measured`** — not `visible`. A segmenter's extent is `visible`: you can point at the thing it found. This organ was handed the words and computed where they land, so what it earned is the computation.
- `concept_naming` has **no role at all**, and its absence from `role_registry._ADAPTER_PRODUCERS` *is* the two-status wall expressed in the table. The concept may come from the `dissector` thinker, a fixed `domain_profiles` vocabulary, or the curator's own phrase — no single role owns it, so it keeps its own `epistemics._DEFAULTS` entry. It is exactly the residue criterion ROLES-001 §3.2 established.

`concept_source` (`domain_profile` | `vlm` | `curator`) rides on the provenance. It does not change the status — none of the three is the image, so all three are `interpretive` — it records **who is answerable**, which a reviewer cannot weigh a naming without.

### 2.2 The confidence floor gates the naming, never the geometry

`NAMING_CONFIDENCE_FLOOR = 0.50`. Below it the **naming is withheld and the extent is still emitted**, with the drop recorded on the extent (`naming_withheld`) rather than happening silently. A measurement does not become false because the word attached to it is doubtful.

And never the reverse: **there is no fallback to an estimated box when a mask is missing.** No mask, no claim. `SF-004-R2`'s build recommendation was a confidence floor with no fallback to fake boxes, and that is what this is.

The floor is **not calibrated**. `SF-004-R2` §4.3 observed that confidence tracked correctness — `snake hood` right eleven times at 0.92, `shoulder fabric` wrong at 0.27–0.43 — across three fixtures and thirty-five concepts. That is an observation, not a curve, and the code says so.

## 3. What was built

| Layer | Change |
|---|---|
| `contracts.py` | `Capability.CONCEPT_SEGMENT` — distinct from `GROUNDING`, which resolves a phrase to *the* referent. This asks for *all* of them, which the grounding row cannot express. |
| `registry.py` | `AdapterSpec("sam3", CONCEPT_SEGMENT, GPU, "facebook/sam3")`, deferred until weights exist. |
| `sam3_concept_service.py` | The organ. Lazy singleton, module-level `unload()`, `MODEL_TAG` — the existing GPU-service shape, so `model_residency` **discovers** it with no registration step. |
| `adapters.py` | `Sam3ConceptAdapter` — the full `Adapter` protocol, cancel-checked *between concepts* because each is a multi-second call. |
| `role_registry.py` | Organ role generated from the roster; ceiling `measured`; `producers=("concept_segment",)`. |
| `epistemics.py` | `concept_naming` → `interpretive`, with the reasoning. |
| `suggestion_service.py` | `suggestions_from_concept_segments` — the two-status emission. |
| `capabilities.py` | The `concept_segment` actuator: IMAGE + **PHRASE**, produces REGION + MARK, `authors_geometry=True`, `plural=True`. |
| `real_actuators.py` | `_run_concept_segment` + the `concept_segmenter` availability probe. |
| `posts.py` | The SŪKṢMA measuring pass, opt-in, plus `fine_source` on the response. |
| `visualMarks.js` | Both producers added to the frontend `PRODUCERS` vocabulary. |

### 3.1 The measuring pass runs BEHIND the VLM, not instead of it

The VLM stays the **concept source**; SAM 3 measures the parts it named. That ordering is the spike's own finding, not a preference: `SF-004-R2` §3.4 records a first Gate-2 run that inverted it — a fixed generic vocabulary — and scored **6/18**, because it asked a painterly neck close-up for `collar`/`cuff`/`hem`/`placket`, parts not in that image. Feeding SAM 3 the VLM's own per-image labels gave **27/35**. The concepts have to come from something that has looked at *this* picture.

A part SAM 3 cannot measure **keeps its estimated box and is not dropped**. 27/35, not 35/35 — the eight it missed still reach the curator as what they are.

### 3.2 The fallback names which producer ran

`fine_source` on the dissect response: `vlm` | `sam3` | `sam3_fallback_vlm`. The two producers are not interchangeable — one returns measured pixel geometry, the other returns a guess — so a caller that could not tell them apart would read an estimate as a measurement. A run-contract event is emitted either way (`SUCCEEDED` with `adapter: sam3`, or `UNAVAILABLE` with `fallbacks: [decompose_regions]`).

An organ that raises **degrades the pass, never fails the route.**

### 3.3 Three refusals

1. **No concept, no run** — at the actuator, the runner, and the adapter. An open-vocabulary finder with nothing to look for is the P8-B fabrication shape, and this model will mask *something* for very nearly any phrase.
2. **No mask, no claim** — an instance with no `mask_rle` yields no descriptor. Never coerced to a box.
3. **Empty is an answer** — zero instances returns `EMPTY` / `SUCCEEDED`-with-nothing, not a failure. "That concept is not in this picture" must be distinguishable from "the organ broke", or a caller invents a box to cover the gap. This makes the silent-empty-return hazard `SF-004-R2` §7 left open **visible** rather than resolved.

### 3.4 The positional-identity hazard (HW-C6)

SAM 3's instance ids are positional. `source_ref` is therefore `concept|index`, scoped so two concepts on one image cannot collide, and identity across re-runs comes from `run_id`/`step_id` (PROV-001) — never from the index. The hazard is contained, not solved; `SF-004-R2` §7 keeps it open, and the VLM's own non-determinism at `temperature=0.25` compounds it.

## 4. Propose-never-commit

Every descriptor is a quarantined suggestion. No post is written, no Accept path runs, no auto-commit exists. Asserted directly (`test_nothing_here_writes_a_post`), and the guarded run in §5 touched no database.

## 5. The guarded real run — and the defect it caught

Run 2026-08-02, Apple M4 (MPS), against the real 3.2 GiB checkpoint and a **local fixture file**. No post read or written, no DB.

`snake hood` on the line engraving (`f_product_695be7fa.jpg`):

```
available: True | device: mps
instances=11  latency_ms=14276.2  truncated=False
confidences: [0.9212, 0.9023, 0.8689, 0.8265, 0.7165, 0.4893,
              0.3674, 0.3242, 0.263, 0.2592, 0.255]
first mask rle size: [680, 445]
suggestions emitted: 16          # 11 measured extents + 5 namings above the 0.50 floor
epistemics.guard: PASSED
status pairs per instance: {'snake hood|0': ['interpretive', 'measured'], …}
```

The same eleven serpent heads `SF-004-R2` found, now as canonical RLE with both statuses attached. 14.3 s is the **cold start** the spike also measured (the encoder builds on first inference).

Then the case the design exists for, on the painting:

```
[painting] shoulder fabric -> instances=4  confs=[0.4274, 0.3396, 0.3023, 0.2656]
  emitted: 4 × ('concept_segment', 'measured')      # every measurement survives
  withheld: 4 × {'concept': 'shoulder fabric', 'confidence': …, 'floor': 0.5}
```

**Every naming withheld, every measurement kept.** The wrong label does not reach review; the geometry still does.

### 5.1 The defect

The first real run failed:

```
TypeError: Unsupported image type
```

Every production caller holds **bytes** — `_fetch_post_image_cached` returns the fetched image and no file is ever written — and Ultralytics accepts `str`/`Path`/PIL/ndarray but not `bytes` or a `BytesIO`. **The spike could not have caught this**: it fed file paths off disk, because it had them.

Fixed with `_to_source`, which decodes to **PIL** rather than a numpy array on purpose — Ultralytics reads a bare ndarray as BGR and a PIL image as RGB, and getting that backwards is a silent channel swap that degrades results without raising. The guarded run is now a skipif-guarded test, so the regression has a tripwire.

This is the argument for the guarded run existing at all. Twenty-nine tests against fakes were green while the integration could not accept the one input shape it would ever be given.

## 6. Verification

`backend/tests/test_concept_segmentation.py` — **30 tests**, six sections: the two statuses; the floor; availability and fallback; propose-never-commit and provenance; the wiring (roster, role, actuator, runner, residency discovery, adapter protocol); and the guarded real run.

Against the directive's bar:

| Required | Where |
|---|---|
| real masks, mask `measured` + label `interpretive`, **distinct** | §1 tests + the guarded run |
| fallback fires when unavailable and records `source` | `test_the_fallback_leaves_the_vlm_parts_intact_and_names_what_ran` |
| provenance / `step_id` present | `test_provenance_carries_the_run_and_the_step` |
| propose-never-commit, post byte-identical | `test_nothing_here_writes_a_post` |
| guarded real run on a local image | §5 |

Three existing wiring guards caught real omissions while building, which is them working: every declared actuator must have an in-process runner (`test_wire_002`, `test_wire_actuators`, `test_corpus_m1`), and every backend mark producer must exist in the frontend `PRODUCERS` vocabulary (`test_producer_parity` — the `architectural_axis` bug, where a producer shipped and its vocabulary entry did not, and nothing failed loudly in between).

## 7. Test delta

| | Baseline | After ROLES-001 | After CONCEPT-SEG-001 |
|---|---|---|---|
| backend | 1113 / 9 skipped / **0 failed** | 1159 | **1188 passed, 9 skipped, 0 failed** |
| frontend | **944 passed** | 944 | **944 passed, unchanged** |

**Two corrections to the directive's stated baselines.** The frontend baseline is **944, not 910** — measured on `main` in the primary checkout, unmodified. And the *"two known-unrelated failures"* **do not reproduce**: the backend baseline was clean before any edit here.

With `SAM3_WEIGHTS` set, the guarded run is +1 (30 in this file, 1189 total); without it that test skips.

## 8. What is NOT done

- **The latency work.** fp16, encode-once-prompt-many, `torch.compile`, and the MLX arm (`SF-004-R2` criterion 6, never run) are all untouched. This is what the default-off switch is waiting on. `encode-once-prompt-many` is the obvious win and is *deliberately* not attempted here: the Ultralytics semantic predictor exposes no such seam, and reaching into its internals inside a production route is not a thing to do on a measurement this thin.
- **Domain gating** — evidence recorded (§1), not enforced.
- **Rubric scoring** against `vision-eval-001/rubric.md`, and boundary fidelity: still no ground-truth masks, so nothing here measures how *good* a correct mask is.
- **`SF-002` / `SF-003` schemas** — untouched, per the standing hold. What Gate 5 asked for was that the two-status emission exist and be flagged to `SF-002`; it now exists in the suggestion layer. Where those statuses land in the durable soft-field schema is still `SF-002`'s call.
- **A CUDA path.** This ran on MPS. `requirements-ml.txt` is CUDA-pinned; SAM 3 is not in it, and the Ultralytics AutoUpdate that self-installs `clip`/`ftfy`/`regex`/`wcwidth` (building `clip` from source, 21.9 s here) still needs pinning before any deploy.

---

*Production code. Backend and frontend suites green. No post read or written; the only model call was against a local fixture file.*
