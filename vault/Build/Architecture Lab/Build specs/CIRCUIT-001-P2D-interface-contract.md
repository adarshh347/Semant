# CIRCUIT-001 P2D — Shared interface contract (Lane A ↔ Lane B)

Both lanes obey this file. Lane A **implements** it; Lane B **emits against** it. Neither lane
may change it unilaterally — proposed amendments go in the lane's report for the P2E synthesis.

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
