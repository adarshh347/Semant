# CIRCUIT-001 P4-A — Real Suggestion Producers + Contract v3

**Lane A4 (the soul lane), main tree. Branch `feat/circuit-p4-producers` off `origin/main` @
`bf42bef` (PR #68 P3-A + PR #69 P3-B merged).** Additive backend only, no migration, no new
frontend dep, no model called in tests. Lane B4's UI files untouched.

**The rule this gate serves:** the model may finally speak in the circuit — but only in its own
name, on its own layer, with its receipts attached. Today no producer minted a `model_suggested`
mark; after this gate, SAM refine and semantic read both do, each carrying a real
`vision_run_service` `run_id`. **The deliberate `run_id: null` of P2D ends here.**

---

## Gate 0 — base + reconcile

`git fetch`; branched off `bf42bef`. Main health: **662 frontend tests + clean build** on a fresh
checkout (the circuit's draw→commit→cite→recall paths are covered end-to-end by that suite). A
manual dev-server click-through was constrained by the machine's `inotify` watcher limit (vite
crashes on `ENOSPC` without polling); the comprehensive automated coverage + clean build is the
"main is not broken" signal I built on. No STOP condition.

## Contract v3 (Commit 1 — `217bc29`)

Committed FIRST so Lane B4 can code against it. Promotes P3-B's geometry-carried fields to
validated schema and adds the suggestion-provenance shape. **Back-compat gate held: every new
field is optional, so no persisted P3-B mark is invalidated** (regressioned below).

- **First-class instrument fields** (`visualMarks.js`): `ANCHOR_KINDS`, `STROKE_OPS`, `PRODUCERS`.
  `validateMark` now checks `geometry.anchors.{from,to}` via `anchorError` (a `point` anchor is
  self-anchored; a ref kind requires a `ref`; `detached_from_ref` is a boolean), `geometry.ambiguous`
  / `geometry.arrowhead` as booleans, and `strokes[].op ∈ {add, sub}`.
- **`region_ref` geometry mode**: `region_mask` may now reference an existing region EITHER as a
  segmented extent (`raster_mask` + `mask_ref`) OR as a naming reference only (`region_ref` +
  `region_ref{region_id}`, no mask authored — the VLM's law). `regionRefMark()` constructor.
- **Suggestion-provenance shape**: `provenance` gains `producer`, `adapter`, `latency_ms`; the P2D
  `run_id: null` rule is **retired** — `run_id` may be a real run id, and a named `producer` (not
  `fixture`) MUST carry one. `confidence` stays forbidden. Contract doc §8.

## Producer 1 — SAM refine as suggester (2a)

**Flow.** New additive route `POST /{post_id}/refine-region/suggest` (backend, my side of the
`useMaskRefine` plumbing): computes the same SAM2 preview as `/preview`, but mints a **real refine
run** and returns a quarantined suggestion — **persisting nothing** (the mask is a proposal until
the curator accepts it through the existing `/confirm` path). `suggestion_service.suggestion_from_refine_region(region, run_id, latency_ms, base_id)`
maps the previewed region → a `region_mask` (`raster_mask`) descriptor.

**Provenance sample (real dict, redacted nothing):**
```python
{'producer': 'sam_refine', 'type': 'region_mask', 'role': None, 'label': 'collar',
 'source_ref': 'reg_7',
 'geometry': {'kind': 'raster_mask', 'mask_ref': {'region_id': 'reg_7', 'geometry_rev': 3}},
 'linked_ground_ids': [], 'base_id': 'reg_7',
 'provenance': {'model': 'sam2.1', 'adapter': 'sam2', 'latency_ms': 42.0,
                'run_id': 'run_abc', 'producer': 'sam_refine'}}
```

**Accept path unchanged**: `acceptSuggestion` mints `user_confirmed` + `derived_from`; the
region-level bridge fields stay derived server-side (`/confirm`, v2 §7.2-E).

## Producer 2 — semantic read as suggester (2b)

**Flow.** `semantic-read`'s response gains an additive `suggestions` field (the persisted
`post.semantics` is untouched — geometry is never written). `suggestion_service.suggestions_from_semantics(semantics, run_id)`
projects:
- each **assertion** → a `model_suggested` `region_mask` in **`region_ref` mode** (a label
  reference to an existing region — no geometry authored). A curator-**rejected** assertion is not
  re-suggested; an **overridden** label rides through as the curator's text.
- each **relation** → a `model_suggested` `relation_mark` with `derived` geometry, `linked_ground_ids`
  = `[from_id, to_id]`. The VLM's free-text relation ("echoes", "beside", "same-material-as") is
  keyword-mapped to the frozen `relation_role` vocabulary (`relation_role_for`, default
  `address_relation` — a valid role, so a relation is never silently dropped by the validator).

**Provenance sample (real dicts):**
```python
# label → region_ref (no pixels)
{'producer': 'semantic_read', 'type': 'region_mask', 'role': None, 'label': 'lapel',
 'source_ref': 'reg_3', 'geometry': {'kind': 'region_ref', 'region_ref': {'region_id': 'reg_3'}},
 'linked_ground_ids': [],
 'provenance': {'model': 'vlm-default', 'adapter': 'semantic_pass', 'latency_ms': None,
                'run_id': 'run_sem', 'producer': 'semantic_read'}}
# relation → derived
{'producer': 'semantic_read', 'type': 'relation_mark', 'role': 'motif_echo', 'label': 'echoes',
 'source_ref': 'reg_1|reg_3|echoes', 'geometry': {'kind': 'derived'},
 'linked_ground_ids': ['reg_1', 'reg_3'],
 'provenance': {'model': 'vlm-default', 'adapter': 'semantic_pass', 'run_id': 'run_sem',
                'producer': 'semantic_read'}}
```

## Run identity honest (2c)

Both producers ride a **real** `vision_run_service` run (P1E's relation model, not a second run
concept):
- refine-suggest mints `operation=refine` via `VisionRunRecorder` (stages `refine.receive`,
  `refine.propose`), finalizes `terminal_reason="suggested"` — **no persist stage**, because
  nothing is written. `rec.run_id` becomes the suggestion's `provenance.run_id`.
- semantic-read already minted `operation=semantic_read`; the suggestions reuse that `rec.run_id`.
No schema fork; the recorder's `requested_profile` carried the correlation refs already.

## Store intake semantics (2d)

`suggestionQuarantine.js` (pure) + `regionStore.ingestSuggestions` (the store seam):
- **fail-closed**: `suggestionFromDescriptor` returns `null` on any invalid descriptor (bad role,
  missing receipt, junk); `suggestionsFromDescriptors` drops nulls — never a partial mark.
- **idempotent**: the mark id is DETERMINISTIC — `suggestionId(d) = vm_sug_<producer:type:source_ref>` —
  so a re-run REPLACES its suggestion by id rather than adding a duplicate (`addVisualMark` replaces
  by id). Proven: ingesting the same 2 descriptors twice → 2 marks, not 4.
- **never persisted**: a `suggested` status is excluded from `persistableMarks`; intake calls
  `addVisualMark(m, {save:false})`, so nothing is even scheduled. PATCH body carries 0 marks; a
  fresh store from the persisted post has 0 suggestions.
- **survives reload by RE-DERIVATION** (re-run the producer), not storage.

## The store API surface Lane B4 consumes (exact signatures)

On the object `useRegionState` returns:
```
ingestSuggestions(descriptors: Descriptor[]) → mark[]
    // maps descriptors → quarantined model_suggested marks, adds each with {save:false},
    // returns the marks actually ingested (invalid dropped). Idempotent by deterministic id.
```
Pure helpers (from `differential/suggestionQuarantine.js`), if B4 needs them directly:
```
suggestionFromDescriptor(descriptor, {now?}) → mark | null
suggestionsFromDescriptors(descriptors[], {now?}) → mark[]
suggestionKey(descriptor) → 'producer:type:source_ref'
suggestionId(descriptor) → 'vm_sug_…'   // deterministic
```
**Descriptor shape** (backend emits, contract v3 §8.4):
```
{ producer, type, role|null, label, source_ref, geometry, linked_ground_ids, provenance }
```
The Differential/refine UX (B4) wires the two backend routes to `ingestSuggestions`:
`POST …/refine-region/suggest` → `{suggestions}` and `POST …/semantic-read` → `{suggestions}`.

## `// P4F:` markers

**None emitted.** The store capability B4 needs (`ingestSuggestions`) is built and exposed now, per
the ownership rule ("if the UI needs a store capability that's missing, that's yours to add NOW").
If B4's review UX finds a missing seam, it will mark it `// P4F:` and this lane reconciles.

## Tests + build

| | |
|---|---|
| backend | **8 new** producer tests (pure service × 6 + route-level × 2, no model/network) + 77 green across `test_circulation_spine_p1/p2_1`, `test_vision_b3_refiner`, `test_semantic_pass`, `test_suggestion_producers` |
| frontend | **686 green (40 files)** — new: `suggestionIntake.dom` (4), intake block in `suggestionQuarantine.test` (7), contract-v3 block in `visualMarks.test` (13) |
| build | ✅ clean |
| regression (contract v3 vs P3-B) | `p3Instruments.test.js` (21) builds marks with the EXACT shapes P3-B persists (anchors `{point, ground}`, ambiguous, arrowhead) and passes under v3; my v3 tests add detached_from_ref, strokes `op`, region_ref |
| quarantine-under-volume | 100 produced suggestions → **0 citable, 0 persistable** |

**No production data mutated.** Every producer path was exercised through fixture dicts and the
fake-collection route harness — no real SAM2, no real VLM, no live post written.

## Files changed

**Backend (additive):** `services/suggestion_service.py` (new — the two producers, pure) ·
`routers/posts.py` (`import suggestion_service`; new `refine-region/suggest` route; `semantic-read`
gains additive `suggestions`) · `tests/test_suggestion_producers.py` (new).

**Frontend:** `differential/visualMarks.js` + `.test.js` (contract v3 — Commit 1) ·
`differential/suggestionQuarantine.js` (intake) + `.test.js` · `state/regionStore.js`
(`ingestSuggestions`) · `state/suggestionIntake.dom.test.jsx` (new). Contract doc §8 (Commit 1).

**Not touched (Lane B4 / others):** `DifferentialWorkspace.jsx`, `AttunementPanel.*`,
`GroundLayers.jsx`, `InstrumentHandles.jsx`, `useMaskRefine.js`, `markStaging.js`.

## What Lane B4 / the merge gate must know

1. **Two routes emit suggestions**: `POST …/refine-region/suggest` and `POST …/semantic-read`
   (additive `suggestions` field). Feed both into `store.ingestSuggestions`.
2. **A suggestion is never durable** — render it on the suggestion layer, quarantined. Accepting it
   goes through the existing `acceptSuggestion` → `user_confirmed` + `derived_from` path (and, for
   SAM, `/refine-region/confirm` to persist the mask).
3. **Idempotency is free** — re-running a producer and re-ingesting will not duplicate; you can call
   `ingestSuggestions` on every producer response without dedup logic of your own.
4. **`region_ref` marks carry NO geometry** — a label suggestion references a region by id; don't
   try to draw it. A relation suggestion is `derived` (shape comes from its refs at render).
