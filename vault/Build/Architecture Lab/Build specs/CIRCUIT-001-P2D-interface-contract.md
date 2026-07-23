# CIRCUIT-001 P2D — Shared interface contract (Lane A ↔ Lane B)

Both lanes obey this file. Lane A **implements** it; Lane B **emits against** it. Neither lane
may change it unilaterally — proposed amendments go in the lane's report for the P2E synthesis.

> **Version: v3** (P4-A). §§1–6 are the frozen v1 baseline; **§7 is the v2 amendment layer and
> §8 is the v3 amendment layer — §8 takes precedence where it overrides.** v3 promotes P3-B's
> geometry-carried instrument fields to first-class validated schema and adds the
> suggestion-provenance shape now that real producers mint `model_suggested` marks. Read §8
> before §7 before §1–2.

## 1. The emission shape — `visual_mark`

Every tool, spike, or suggestion path produces marks of this shape (normalized 0..1,
natural-image coords, top-left origin — same contract as `useStageGeometry`):

```
visual_mark {
  id                 vm_<base36ts>_<seq>        // minted like groundId(); monotonic tail
  type               brush_field | trace_mark | relation_mark | frame_mark | collection_mark
  role               family role key (see §2)
  label              curator-facing, editable, may be ''
  source             user | system | model_suggested | model_refined | user_confirmed | imported | fixture
  status             draft | staged | suggested | previewed | committed | dismissed | superseded | blocked
  geometry           { kind, ...normalized coords }   // kind may be 'unresolved' (role proposed, no geometry yet)
  style              { color, opacity, softness?, stroke_width? }   // suggestion, not authority
  linked_ground_ids  []      linked_percept_ids []      linked_action_ids []
  derived_from       mark_id | null      // lineage: acceptance/refinement points BACK, never overwrites
  provenance         { planner?, prompt_excerpt?, model?, matched?[], run_id: null }
  created_at / updated_at
  warnings           []
}
```

`citable` is **derived, never stored**: a mark is citable iff
`status === 'committed'` AND `source ∈ {user, user_confirmed}` AND `geometry.kind !== 'unresolved'`.
Function of record: `canCiteMark(mark)` (Lane A, `suggestionQuarantine.js`).

## 2. Role vocabularies (P2B's, verbatim — do not invent a fourth dialect)

- `brush_field.field_role`: light_field, shadow_field, atmosphere_field, material_field,
  pressure_zone, gaze_field, negative_space, threshold, fold, rhythm, background_recession,
  external_limit.
- `trace_mark.trace_role`: gaze_address, gesture, fall_of_light, architectural_axis, movement,
  implied_address, comparison_path, force_direction, rhythm, return_path.
- `relation_mark.relation_role`: similarity, contrast, kinship, motif_echo, support, tension,
  contradiction, temporal_suggestion, address_relation.
- `frame_mark.frame_role`: aperture, boundary, crop, threshold, field_boundary, external_limit.
- `collection_mark.collection_role`: percept_constellation, evidence_set, comparison_set,
  motif_set, contradiction_set, field_cluster, manuscript_citation_set.

Geometry kinds: `freehand_path` (strokes[] of `[[x,y,pressure?]…]` + radius/strength/op),
`polygon`, `soft_mask` (today's field ground, unchanged), `raster_mask` (mask_ref only — never
inline pixels), `bounding_box`, `vector` ({from,to}), `curve` ({points,tension}), `polyline`,
`derived` (relation/collection — computed from refs at render, never stored), `unresolved`.

## 3. `visual_layer`

```
visual_layer { id, name, layer_type: evidence|suggestion|recall|scratch,
               visibility, opacity, locked, order, mark_ids[], provenance }
```
`createDefaultLayers()` ships exactly these four. `layer_type` is extensible later; no general
layer-manager UI in P2D. `recall` is a system layer: not lockable, not reorderable, not saved.
Renderer mapping rule (binding on Lane B): a `visual_layer` maps to a Konva **Group**, never a
Konva **Layer**.

## 4. Quarantine rules (the load-bearing ones)

1. `model_suggested` / `suggested` / `previewed` marks are **never citable, never counted,
   never committed** — they live on the `suggestion` layer, visibly distinct.
2. `acceptSuggestion(mark, edits?)` mints a **new** mark: `source: user_confirmed`,
   `derived_from: <suggestion id>`; the suggestion's provenance is preserved untouched
   (Label Studio `parent_prediction` pattern). Never flip a flag in place.
3. A human draw that a model tightened is `model_refined` — distinct from both `user` and
   `user_confirmed`.
4. Provenance must be **surfaceable**: `summarizeProvenance(mark)` returns a short visible label
   (CVAT's negative lesson: invisible provenance is no provenance).
5. `superseded` marks stay recoverable (silent replacement is how citations re-point unnoticed —
   P1F/P1G).

## 5. What Lane A exports (Lane B codes against these names)

From `frontend/src/differential/visualMarks.js`: `makeVisualMark`, `normalizeMark`,
`validateMark`, `markId`. From `visualLayers.js`: `createDefaultLayers`, `normalizeLayer`,
`validateLayer`, `assignMarkToLayer`, `layerCanContainMark`. From `suggestionQuarantine.js`:
`quarantineSuggestion`, `isSuggestion`, `canCiteMark`, `acceptSuggestion`, `dismissSuggestion`,
`supersedeSuggestion`, `summarizeProvenance`. From `visualMarks.js` (action bridge):
`actionToDraftMark`, `markRoleFromAction`.

If Lane B starts before Lane A lands, Lane B stubs these signatures locally in the spike and
notes any signature it wished were different — that note is P2E input, not a licence to diverge
from §1–§4.

## 6. Hard prohibitions (both lanes)

No renderer object is ever truth — no Konva/Fabric node, no raw SVG element, in any serialized
output. No `run_id` causal claims (slot stays null). No confidence scores on marks. No stored
mark biography. No tldraw (never read, never install). Licences: MIT/BSD/Apache only.

---

## 7. v2 amendments (P2E-A) — precedence over §§1–6 where they conflict

### 7.1 Settled upstream — record, do not reopen

**A. Ref-anchored endpoints — `detached_from_ref: bool`.** A `trace_mark`/`relation_mark`
anchor may point at a ground/region/percept (`anchor.ref`). Dragging a ref-anchored endpoint
**keeps the ref, freezes the dragged position, and sets `detached_from_ref: true`** — the mark
still records what it was anchored to *and* that the curator moved it off. (Spike report §7.)
Anchor shape:
```
anchor { kind: 'point'|'ground'|'region'|'percept', ref: id|null, at: [x,y], detached_from_ref: bool }
```

**B. Erase is geometry, not style.** In a `freehand_path`, each stroke carries
`op: 'add' | 'sub'`. That `op` is **canonical mark data** — it is *what the curator drew*.
Compositing (`destination-out` etc.) is a renderer detail that reads `op`; it is never the
source of truth. A serialized mark that dropped `op` would have lost a subtraction the curator
made.

### 7.2 Decided by Lane A this gate

**C. `region_mask` is a sixth family.** DECISION: **add it.** A SAM-segmented extent is not a
perceptual field — mapping it to `brush_field + material_field` (P2D-A's stopgap) asserted a
perceptual reading no one made. `region_mask` names *what was segmented*, honestly, and defers
the perceptual reading to a later, explicit act.
```
region_mask extends visual_mark {
  type:     'region_mask'
  role:     null (default) | segment | part | material_extent | anchor_extent   // OPTIONAL — a
            //   segmented extent has no perceptual role until a curator gives it one
  geometry: { kind: 'raster_mask', mask_ref: { region_id, geometry_rev } }       // ONLY raster_mask;
            //   mask_ref is the sole pointer; NEVER inline pixels
}
```
- **Citability:** a `region_mask` follows the same base rule (committed + `source ∈ {user,
  user_confirmed}` + geometry not `unresolved`) — an accepted region IS citable evidence, as
  regions always have been. Its optional `role` does **not** gate citability.
- **Conversion path (later gate, not built here):** `region_mask → brush_field` is an explicit
  curator act that mints a NEW perceptual mark `derived_from` the region_mask. Reading a
  segmented extent *as* a light field is a perceptual claim and must be made, never inferred.
- **Reason it is a family and not a role:** its geometry is constrained to `raster_mask` and its
  role is optional — both differ structurally from `brush_field`, so overloading would have made
  `brush_field`'s own invariants weaker.

**D. Boundary stays `frame_mark` with role `boundary`.** DECISION: **no new family.** A drawn
boundary is a `frame_mark`, `frame_role: 'boundary'` (already in the §2 vocabulary), geometry
`polyline`. No evidence yet justifies a `boundary_mark` family; multiplying families without a
distinct invariant is how a vocabulary rots. Revisit only if boundaries acquire behaviour a
frame does not have.

**E. `visual_mark.provenance` is the ONLY authored provenance.** DECISION: single source of
truth. The additive `mark_source` / `instrument_role` / `refined_from` fields on grounds and
regions are **DERIVED BRIDGE FIELDS** — written only by helpers that read from the canonical
mark, never authored independently, and never read as truth. A bridge field that disagrees with
its mark is a bug, and a drift test pins that it cannot. Rationale: P2D-A left provenance in two
places (mark + region stamp); two homes for one fact is exactly the CVAT failure of a provenance
nobody can trust. The mark is the home; the bridge fields are a convenience view for surfaces
that hold a ground/region but not its mark.

### 7.3 Persistence (new in v2)

`post.visual_marks: [visual_mark]` — additive on the post document, PATCH-persisted beside
`grounds`/`percepts`, hydrated in `regionStore`. **Persistence policy:** only `committed` and
`superseded` marks persist. `superseded` persists because recoverability is the whole point of
the status (P1F/P1G); `draft`/`staged`/`suggested`/`previewed`/`dismissed` are **session-only** —
**the quarantine is session truth and a suggestion never touches the database.**

## 8. v3 amendments (P4-A) — precedence over §§1–7 where they conflict

P3-B (PR #69) added trace anchors, terminus honesty, region_mask and erase — and, to avoid
touching this contract mid-flight, carried the new fields **inside `geometry` verbatim**,
validated only by `geometry.kind`. v3 promotes them to first-class, checked schema. **The gate:
what P3-B persisted must still validate** — the rules below accept exactly the shapes
`handleEditing.syncAnchors` and the trace tool write.

### 8.1 First-class instrument fields (now validated)

- **Trace anchors.** `geometry.anchors = { from, to }`, each an anchor or `null`. An **anchor** is
  `{ kind, at:[nx,ny], ref?, detached_from_ref? }` where `kind ∈ {point, ground, region, percept,
  mark}` (`ANCHOR_KINDS`). A `point` anchor is self-anchored (`at` IS the endpoint, no `ref`); a
  ref kind requires a non-empty `ref` and treats `at` as a cached copy. `detached_from_ref: true`
  (a boolean) records a drag that froze the cached position — contract v2 decision #1, now
  enforced, not merely honored. Validator: `anchorError(anchor)`.
- **Terminus honesty.** `geometry.ambiguous` and `geometry.arrowhead` are booleans (a trace wears
  a sharp arrowhead only when it asserts a target; `ambiguous` fades it). Non-boolean → reject.
- **Erase as data.** `geometry.strokes[].op ∈ {add, sub}` (`STROKE_OPS`) — erase is stroke DATA,
  not a compositing detail (v2 decision B), so it validates here. `region_mask` still forbids
  inline `strokes` entirely.
- **Back-compat:** every one of these fields is optional. A mark that omits them validates exactly
  as before — no persisted P3-B mark is invalidated (regression-tested against seeded shapes).

### 8.2 `region_ref` — a naming reference (the VLM's law)

`region_mask` may now carry EITHER geometry mode:
- `raster_mask` + `mask_ref{region_id[, geometry_rev]}` — a **segmented extent** (SAM/Dissect drew
  the mask). Unchanged from v2 §7.2-C.
- `region_ref` + `region_ref{region_id}` — a **naming reference only, no mask authored.** This is
  what a semantic-read label proposal becomes: the VLM may say WHAT a region is, never draw one.
  Bans inline pixels exactly as `raster_mask` does. Constructor: `regionRefMark(...)`.

### 8.3 Suggestion-provenance shape (producers finally speak)

`run_id: null` was deliberate in P2D (P1E/P1G: run identity was under-specified). **The
CIRCULATION-SPINE run substrate (`vision_runs` + `vision_run_service`) has landed, so that rule is
retired.** `provenance` now carries, additively:

```
provenance {
  planner, prompt_excerpt, model, matched,   // unchanged
  run_id,        // null (a curator's mark) OR a non-empty vision-run id (a producer's)
  producer,      // one of PRODUCERS = {sam_refine, semantic_read, planner, fixture}, or null
  adapter,       // concrete transport, e.g. 'sam2' / 'semantic_pass' (optional)
  latency_ms,    // producer wall time when known (optional)
}
```

Rules (in `validateMark`):
- `run_id` must be `null` or a **non-empty** run id (whitespace-only is a broken receipt → reject).
- A named `producer` must be in `PRODUCERS`; and a real producer (anything but `fixture`) **must
  carry a `run_id`** — a suggestion that claims the model without a run has lost its receipt.
- `confidence` remains forbidden (v1 §6). Producers attach receipts, not scores.

### 8.4 Producer → suggestion mapping (P4-A)

- **`sam_refine`** (SAM2 mask preview) → a `model_suggested` **`region_mask`** (`raster_mask`),
  quarantined, `provenance {model:'sam2.1', adapter:'sam2', latency_ms, run_id, producer:'sam_refine'}`.
  Accept mints `user_confirmed` + `derived_from` (existing quarantine path); region-level bridge
  fields stay derived (v2 §7.2-E).
- **`semantic_read`** (VLM) → label proposals become `model_suggested` `region_ref` marks
  referencing existing regions (no geometry authored); relation proposals become `model_suggested`
  `relation_mark`s with `derived` geometry. `provenance {model, adapter:'semantic_pass', run_id,
  producer:'semantic_read'}`.
- **Intake** (`store.ingestSuggestions`): idempotent (a re-run does not duplicate — keyed on
  `producer + type + source_ref`, a deterministic id), fail-closed (invalid → dropped, never a
  partial), and NEVER persisted (suggestion status → excluded from `persistableMarks`, v2 §7.3).
  Survives reload by RE-DERIVATION (re-running the producer), not by storage.
