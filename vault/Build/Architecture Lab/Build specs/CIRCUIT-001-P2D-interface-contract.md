# CIRCUIT-001 P2D — Shared interface contract (Lane A ↔ Lane B)

Both lanes obey this file. Lane A **implements** it; Lane B **emits against** it. Neither lane
may change it unilaterally — proposed amendments go in the lane's report for the P2E synthesis.

> **Version: v2** (P2E-A). §§1–6 below are the frozen v1 baseline Lane B2 read against at
> `3aa4b3e`; **§7 is the v2 amendment layer and takes precedence where it overrides.** Five
> decisions are recorded in §7 — two settled upstream (anchors, erase), three decided by Lane A
> this gate (region_mask family, boundary, provenance home). Read §7 before §1–2.

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
