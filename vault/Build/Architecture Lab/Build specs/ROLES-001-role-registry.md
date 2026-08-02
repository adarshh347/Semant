**Mode:** build. Production code, tests, PR.
**Branch:** `feat/roles-and-sam3` (worktree `../semant-roles`), off `main` at `85ce742`.
**Status:** **Part 1 BUILT and green.** Part 2 (`CONCEPT-SEG-001`) specced separately.
**Test delta:** backend **1113 → 1159** passed, 9 skipped, **0 failed** — baseline re-measured on this branch before any edit, and it was clean. (The directive expected "two known-unrelated failures"; they do not reproduce here. See §6.)
**House rule:** K-9 — every count above is a measured pytest total, not an estimate.

---

# ROLES-001 — the role registry: organs and thinkers, model-agnostic

## 0. What this is, in one paragraph

A **role** is a job the system needs done, named independently of whoever does it. `dissector` is a role; `qwen/qwen3.6-27b` is what is currently bound to it. Organs — everything that looks at pixels — already worked this way. Thinkers did not: their model ids were literals at the point of use, eight of them across seven files. This makes thinkers roles too, behind one registry, so rebinding a job to a stronger model is a config change rather than a grep.

## 1. Seam confirmation (the directive's references, checked against the tree)

The directive said its references *"are where I believe things live — CONFIRM each against the tree before editing"*. Every one was checked. **Six confirmed, three corrections.**

| Directive said | Tree says | Verdict |
|---|---|---|
| `vision_orchestrator` has `Adapter` protocol (`spec`/`is_available`/`load`/`unload`/`infer`) | `registry.py:19-27` — exact | ✅ |
| `AdapterSpec(name, Capability, ResourceKind, model_id, revision, available, deferred)` | `contracts.py:122-138` — exact, plus `checkpoint`, `preprocessing_version`, `license`, `shares_feature` | ✅ |
| `default_roster()` declares YOLO/SAM2/SegFormer/DINOv2/Depth/Florence/GroundingDINO/cloud_vlm | `registry.py:31-88` — **14 specs**, all present | ✅ |
| `ModelManager` / `model_residency` handle GPU/MPS residency | `manager.py`, `model_residency.py` — confirmed | ✅ |
| `Actuator.capability` "names the runtime dependency (a model family, or None for pure-python)" | `director/capabilities.py:99` — the docstring is quoted verbatim and correct | ✅ |
| `groq_planner.DEFAULT_MODEL = "openai/gpt-oss-120b"`; `argument_planner` imports it | `groq_planner.py:52`, `argument_planner.py:52` | ✅ |
| `llm_service.model`, `editor_llm_service.literary_model`/`vision_model`, `vision_service.vision_model = "qwen/qwen3.6-27b"`, `semantic_provider.FALLBACK_MODELS` | all confirmed at the stated names | ✅ |
| — *(not mentioned)* | **`story_block_service.py:26` — an eighth literal, `llama-3.3-70b-versatile`** | ⚠️ **CORRECTION: the list was incomplete.** It is now the `story_segmenter` role. |
| "M5's guard stops duplicating a per-producer table" | The table is `epistemics._DEFAULTS` (`epistemics.py:224`), 20 entries keyed on producer | ✅ located, but see next row |
| Implied: the ceiling can simply replace `_DEFAULTS` | **It cannot — three producers contradict their role's ceiling, on purpose** | ⚠️ **CORRECTION.** See §3.2. |
| `Actuator.capability` is the binding point for organs | It is *a* binding point, but there are **three** parallel capability vocabularies, not one | ⚠️ **CORRECTION.** See §1.1. |

### 1.1 The three capability vocabularies (found, not fixed)

The tree carries three unrelated string vocabularies all called "capability", and the directive's plan implicitly assumed one:

1. **`Capability` enum** (`contracts.py:18`) — `segment`, `mask_refine`, `grounding`, … the orchestrator's row-families.
2. **`Actuator.capability`** (`capabilities.py`) — `"segmenter"`, `"dinov2"`, `"depth"`, `"intrinsic"`, `"grounding_detector"`, `"semantic_provider"`, `"external_source"`. Probed by `real_actuators._capability_available` against a hand-written dict at `real_actuators.py:60-72`.
3. **`vision_capabilities.ACTION_CAPABILITIES`** (`vision_capabilities.py:15`) — `"yolo"`, `"sam"`, `"segformer"`, `"fashion_segmenter"`, `"fashionclip"`, `"geometry"`.

`capabilities.py`'s own docstring defends (1) vs (2) explicitly and correctly — they answer different questions and fail differently. Nobody has ever defended (2) vs (3), and they overlap: `"segmenter"` and `"yolo"`/`"sam"` name the same models for different consumers.

**Not unified here, deliberately.** Collapsing them touches the Director's refusal path and the recovery planner's skip path — two places where a wrong merge silently converts "the model is down" into "you selected nothing", which is the exact failure `capabilities.py` was written to prevent. It is logged as follow-up F-1 (§7), not smuggled into a registry change that is supposed to be behaviour-neutral.

## 2. What was built

`backend/services/role_registry.py` — a pure module. No torch, no client, no socket, no weights. Importable from `epistemics` and in a slim deploy.

### 2.1 The `Role`

```python
Role(name, kind, summary, epistemic_ceiling,
     default_model=None, producers=(), capability=None,
     adapter=None, provider=None, fallback_models=())
```

- **`kind`** — `ORGAN` (looks at the picture; may claim `visible`/`measured`) or `THINKER` (reads, plans, composes, writes; may claim at most `interpretive`).
- **`epistemic_ceiling`** — the strongest status this role's output may carry. A *ceiling*, not a stamp: `permitted_statuses` already lets any producer weaken to `uncertain`, and that asymmetry is what makes it a ceiling.
- **`producers`** — the `suggestion_service` producer strings this role stands behind. The join to the epistemic guard. **Explicit, not derived** — §3.2 is why.
- **`capability` / `adapter`** — organs only; they point back at the roster entry that executes the role, so the two tables cannot name different things.

### 2.2 Binding precedence

1. `bind(role, model)` — in-process override (tests; a future admin surface).
2. **`SEMANT_ROLE_<NAME>_MODEL`** — the environment. This is the no-code-edit path.
3. `Role.default_model` — what ships.

Resolution is **live**, re-read per call. This is load-bearing and is the one thing the naive implementation gets wrong: `self.model = "…"` in `__init__` would make the env var a setting that only takes effect on restart, and every one of these services is a module singleton constructed at import. So each call site exposes `model` as a **property**. `test_rebinding_a_role_in_config_moves_its_call_site` reads the *singletons* specifically, because they are the case an `__init__` capture would fail.

Fallbacks are rebindable too (`SEMANT_ROLE_<NAME>_FALLBACKS`, comma-separated) — a role moved to another provider has to take its alternates with it, or the first failure lands back on the old catalogue.

### 2.3 The eight thinkers

| Role | Was | Shipped default |
|---|---|---|
| `dissector` | `vision_service.vision_model` | `qwen/qwen3.6-27b` |
| `writer_vision` | `editor_llm_service.vision_model` | `qwen/qwen3.6-27b` |
| `writer_literary` | `editor_llm_service.literary_model` | `openai/gpt-oss-120b` |
| `archivist` | `llm_service.model` | `openai/gpt-oss-120b` |
| `story_segmenter` | `story_block_service.model` | `llama-3.3-70b-versatile` |
| `semantic_annotator` | `semantic_provider.MODEL` | `openai/gpt-4o-mini` |
| `step_planner` | `groq_planner.DEFAULT_MODEL` | `openai/gpt-oss-120b` |
| `argument_planner` | *imported `DEFAULT_MODEL`* | `openai/gpt-oss-120b` |

**Two splits were made on purpose.** `dissector` and `writer_vision` shared a string; `step_planner` and `argument_planner` shared an import. In both cases nothing recorded whether that was a decision or a coincidence — a literal cannot say. They are now separate roles with equal defaults, so behaviour is identical today and either can move alone tomorrow. `test_two_roles_sharing_a_default_move_independently` pins that.

### 2.4 The fourteen organs — generated, not retyped

Organ roles are built from `default_roster()` at import, with the ceiling derived from `Capability` via `_CAPABILITY_CEILINGS`. Re-listing the roster here would have created exactly the second table this module exists to abolish, and it would fall behind on the first adapter added. `test_every_roster_adapter_is_a_role_and_no_role_invents_one` asserts set equality both ways.

## 3. The epistemic ceiling now travels with the role

### 3.1 What moved

`epistemics.default_status_for()` asks the **role** first, then falls back to `_DEFAULTS`. Eleven producers moved onto their role's ceiling: `sam_refine`, `florence_find_parts`, `grounded_sam_find_parts`, `material_field`, `rhythm`, `pressure_zone`, `recession`, `shading`, `fall_of_light`, `semantic_read`, `planner`.

The ordering is the point. A producer wired to a new organ or thinker now inherits its ceiling with **no edit to `epistemics`** — which is precisely the failure mode `model_residency.py` already documents at length (a thing wired in one place and registered in another, with nothing connecting the two, going wrong four times running).

### 3.2 The correction: the tables partition, they do not collapse

The directive implies the role ceiling can simply replace the per-producer table. **It cannot, and the reason is interesting rather than incidental.** Three producers disagree with their role's ceiling *correctly*:

- **`find_similar`** runs on DINOv2, ceiling `measured` — but hands back a real extent on *another* image. It is `visible`: **stronger** than its organ's ceiling, because it is not reporting a measurement at all.
- **`presence_check`, `enumerate`** run on the grounding detector, ceiling `visible` — but answer a *question* instead of minting an extent. They are `interpretive`: **weaker**.

A derived table would have got all three wrong, in both directions. So `_DEFAULTS` survives, holding exactly the producers no single role executes — `find_similar`, `presence_check`, `enumerate`, `negative_space` (measured, but pure-python: its actuator declares `capability=None`), `architectural_axis`, `external_limit`, `connect_marks`, `compose_percept`, `historical_source`. That residue is the *interesting* half, and it is now visibly the interesting half rather than buried among eleven mechanical entries.

`test_the_two_tables_partition_rather_than_shadow_each_other` asserts the intersection is empty. A producer in both would mean the split is half-done and whichever table lost would go stale invisibly.

### 3.3 One existing test was changed, and why

`test_epistemic_layer.py::test_every_frozen_producer_has_a_classification` asserted membership in `epistemics._DEFAULTS` directly. Its *intent* — no producer silently unclassified — is untouched; its *implementation* pinned the surface that moved.

Rather than teach the test about two tables (which goes stale the moment there is a third), `epistemics.classified_producers()` was added as the one place to ask, and the test asks it. The test deliberately does **not** use `default_status_for(p) is not UNCERTAIN`: that would pass for a producer that had fallen through unclassified *and* fail for `external_limit`, which is classified `uncertain` on purpose. That distinction is the whole value of the guard.

## 4. Verification

`backend/tests/test_role_registry.py` — **46 tests**, five sections.

**§2 is the build gate.** Parametrized across six call sites: set `SEMANT_ROLE_<NAME>_MODEL`, read the model off the live service, assert it followed. No code edited, no module reloaded, singletons included.

**§3 is the regression guard, and it is the one worth keeping.** A source-level scan of all of `backend/` for hosted-model-id literals outside the registry. Every behavioural test in this file passes for a *new* service that hardcodes `openai/gpt-oss-120b`; only reading the source catches it.

That scan found one real thing, and it forced a distinction worth writing down: `clip_presence_service.py:35` holds `CHECKPOINT = "openai/clip-vit-base-patch32"`. It is **not** a thinker binding and must not become one. It sits next to `REVISION = "3d74acf…"` and is governed by WEIGHTS-001 — it names a file *and the exact commit it came from*, passed to every `from_pretrained` so the pin is enforced at load. Making that "rebindable by env var" would break reproducibility, which is the opposite of what it is for. A thinker's `openai/gpt-oss-120b` is a catalogue entry with no commit and no local file; swapping it is the entire point. The scan skips weight-pin constants and says so.

**§1** pins all eight shipped defaults as the literals they replaced, read from the services rather than the registry (a registry agreeing with itself proves nothing), and pins that a keyless `vision_service`/`story_block_service` still reports `None` rather than naming a model it cannot call.

**§4** pins `epistemics._DEFAULTS` *verbatim as it stood before this change* and asserts every one of the 20 producers classifies identically. A transcribed copy rather than a derivation, so it is independent evidence.

**§5** pins the organ generation against the roster.

## 5. Honesty

- **No behaviour change from the indirection.** Proven by the suite staying green (§6) plus §1 and §4 above.
- **Ceiling travels with the role** — §3.
- **Provenance untouched.** `Provenance.model` is populated from the resolved binding at every existing site; `SemanticResult` now resolves live rather than capturing `MODEL` as a default argument, because a receipt reporting the *old* model after a rebind is the one failure this layer cannot tolerate.
- **Nothing was fabricated.** Every number in this document is a pytest total.

## 6. Test delta

| | Baseline (`main`, this branch, pre-edit) | After |
|---|---|---|
| backend | **1113 passed, 9 skipped, 0 failed** | **1159 passed, 9 skipped, 0 failed** |

The directive asked to *"keep the two known-unrelated failures noted"*. **They do not reproduce.** The baseline was measured on this worktree before any edit and was clean. One environmental note: the worktree initially failed collection on 22 files with `pydantic_core.ValidationError` because `backend/config.py` requires `MONGO_DETAILS` and a fresh worktree has no `.env`; symlinking the repo `.env` resolved it. That is a worktree setup step, not a test failure, and it would be the same for anyone else checking this branch out.

Frontend (910) was not run — no frontend file is touched by Part 1.

## 7. Follow-ups (logged, not done)

- **F-1 — the three capability vocabularies (§1.1).** Unifying them touches the Director's refusal path and the recovery skip path. Wants its own change with its own gate.
- **F-2 — `semantic_pass.py:19` imports `MODEL` and never uses it.** Harmless, still works. Left alone: deleting an unused import is not this change's business.
- **F-3 — organ *bindings* are still roster-level, not env-rebindable.** Deliberate (§4): organ weights are WEIGHTS-001 commit pins, and rebinding by env would break reproducibility. If organs should ever be swappable at runtime, that needs a revision-aware mechanism, not this one.
- **F-4 — `role_registry.describe()` is not surfaced anywhere.** It exists and is tested; no route reads it. Wiring it into the ops surface is Lane A's business, not this one.

---

*Production code. Existing suites green. No post read or written by this change; no model was called during it.*
