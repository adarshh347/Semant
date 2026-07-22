# CIRCUIT-001 P2D-A — Visual Instrument Model + Suggestion Quarantine

**Lane A (production foundation). Frontend only. No backend file touched. No production data
mutated. No dependency added. No model call.** Implements
`CIRCUIT-001-P2D-interface-contract.md` §1–4.

**The one sentence:** Semant now has a renderer-independent truth model for what an instrument
produces — marks, layers, provenance — and a model suggestion is now *visibly quarantined on
the existing SVG stack*, with acceptance minting a new mark that keeps the model's part in the
record rather than laundering it into "I drew this."

This is a vertical slice: the pure model AND its live integration shipped together.

---

## 1. What was built

### 1.1 Three pure modules (fail-closed, node-tested, dependency-free)

| module | exports | contract |
|---|---|---|
| `differential/visualMarks.js` | `makeVisualMark` · `normalizeMark` · `validateMark` · `markId` · `actionToDraftMark` · `markRoleFromAction` (+ vocabularies, `setMarkStatus`, `markSummary`) | §1–2 |
| `differential/visualLayers.js` | `createDefaultLayers` · `normalizeLayer` · `validateLayer` · `assignMarkToLayer` · `layerCanContainMark` (+ visibility/opacity/lock/reorder) | §3 |
| `differential/suggestionQuarantine.js` | `quarantineSuggestion` · `isSuggestion` · `canCiteMark` · `acceptSuggestion` · `dismissSuggestion` · `supersedeSuggestion` · `summarizeProvenance` (+ `deriveUserConfirmedMark`, `getSuggestionLineage`, `countEvidence`, `hasModelInvolvement`) | §4 |

Every export in contract §5 is present with the specified name. `normalizeMark` returns **null**,
never a partial object, exactly as `perceptualActions.normalizeAction` does — a caller that gets an
object back will render it, and a half-valid mark rendered as evidence is what this prevents.

### 1.2 Schemas as shipped

`visual_mark` carries all §1 fields: `id`(`vm_<base36>_<seq>`) · `type` · `role` · `label` ·
`source` · `status` · `geometry{kind}` · `style` · `linked_ground_ids/percept_ids/action_ids` ·
`derived_from` · `provenance{planner,prompt_excerpt,model,matched,run_id:null}` · `created_at` ·
`updated_at` · `warnings`.

**`citable` is derived and lives in exactly one place** — `canCiteMark(mark)`: committed AND
`source ∈ {user, user_confirmed}` AND `geometry.kind !== 'unresolved'`. Never stored.

Five families, five role vocabularies (§2 verbatim); `trace_role` includes the contract's
`rhythm` and `return_path` beyond P2B's eight. Ten geometry kinds including `unresolved`.

`visual_layer`: `createDefaultLayers()` ships exactly the four system layers — `scratch`,
`evidence`, `suggestion`, `recall` — in render order. `recall` is a locked system layer that
cannot be unlocked, reordered off the top, or saved.

## 2. Quarantine rules, as enforced

| contract rule | how it is enforced |
|---|---|
| §4.1 suggestions never citable/counted/committed | `canCiteMark` returns false for any suggestion; `countEvidence` excludes them; `validateMark` refuses a `model_suggested` mark that arrives `committed`; `layerCanContainMark` files a suggestion onto the `suggestion` layer and **nowhere else** |
| §4.2 acceptance mints, never overwrites | `acceptSuggestion` returns `{accepted, suggestion}` — `accepted` is a NEW mark with `derived_from` the suggestion id; `suggestion` is returned byte-identical (a test asserts `kept === input`) |
| §4.3 model-tightened is `model_refined` | a geometry edit at acceptance yields `model_refined`; `validateMark` requires `derived_from` for both `model_refined` and `user_confirmed` |
| §4.4 provenance surfaceable | `summarizeProvenance` → a short visible label, rendered on screen (§3 below) |
| §4.5 superseded stays recoverable | `supersedeSuggestion` marks the old one `superseded` and KEEPS it; the replacement links back |
| §6 no confidence, no run_id | `validateMark` refuses `provenance.confidence` and any non-null `run_id` |

## 3. What changed in existing files

**`differential/DifferentialWorkspace.jsx`** — three surgical edits, no renderer rewrite:

- **`commitDraft` (2b)** — an armed act now carries `instrument_role` and `origin_action_id`
  onto the ground (additive dict fields, never read by the ground store) **and emits a
  committed `visual_mark`** linked via `linked_ground_ids`. P2B dropped everything but `label`;
  this closes that gap. `normalizeMark` fails closed, so a role the vocabulary rejects produces
  no mark rather than a wrong one — the ground is unaffected either way.
- **`confirmRefine` (2c)** — the SAM proposal is first `quarantineSuggestion`'d, then confirm
  ACCEPTS it: a refine-of-existing region mints `model_refined` (the model tightened the
  curator's mask), a fresh mask mints `user_confirmed` (the model proposed, the curator
  accepted) — both with `derived_from` lineage. The region is stamped with additive
  `mark_source` / `refined_from` / `mark_id` so the store and the chip show the model's part
  this session. The refine buttons now read **Accept / Dismiss** rather than Confirm / Cancel.
- **the selected-ground inspector (2d)** — a provenance chip driven by `summarizeProvenance`,
  quiet ("Yours") for a curator brush, tinted for anything the model touched.
- **the refine inspector (2d)** — a dashed suggestion line while a mask is proposed: *"Model
  suggestion — not accepted — accepting keeps it as 'Model proposed · you accepted'."*

**`differential/DifferentialWorkspace.css`** — provenance chip + honest dashed suggestion
treatment (warm, not an alarm; no `error`/`warn` class).

**No other file changed.** No `regionStore`, no `grounds.js`, no `PerceptWorkshop`, no backend,
no other lane's files.

## 4. The SAM provenance result — patched, with one honest residue

**Patched (this session, no backend change):** the accepted region carries its provenance and
lineage in the store immediately; the mark record carries `source: model_refined|user_confirmed`
+ `derived_from`; the chip renders it. Acceptance goes through `acceptSuggestion`, so the
suggestion→confirmed transition is a real mint-with-lineage, not a flag flip.

**Residue (documented, deferred by scope):** *cross-reload persistence* of the region's
additive provenance fields. The `refine-region/confirm` endpoint persists geometry but does not
echo `mark_source`/`refined_from`, and P2D-A is forbidden backend changes. The provenance is
therefore correct and visible for the session and would need a one-line endpoint echo to survive
a reload. **This is the "patch the safe part, document the exact residue" path the prompt
allows — the client patch was attempted in full and works; only the backend echo is out of
scope.** Flagged for P2E.

There is also **no marks persistence layer** — marks live in component state this session, by
design (no marks backend exists and P2D-A adds none). The ground remains the persisted surface;
the mark is the session's canonical record, linked to it.

## 5. Tests + build

| | |
|---|---|
| new tests | **68** — 62 node (`visualMarks` 26, `visualLayers` 16, `suggestionQuarantine` 20) + 6 DOM (`markProvenance`) |
| full frontend suite | **484 passing** (was 330 at P2B; delta includes other lanes' committed suites) |
| production build | ✅ clean |
| lint | new + changed files clean |
| backend | untouched; not run |

Coverage against contract §1–4: valid/invalid marks; every family; unknown role/source/status/
geometry rejected; `model_suggested`/`suggested`/`previewed`/unresolved never citable; acceptance
lineage + suggestion preserved untouched; dismissal; supersession recoverable; every layer
helper; the quarantine placement rule; `actionToDraftMark` family mappings; **action_id survival**;
**`ask_model_reading` can never mint a mark** (the third refusal, at the bridge); no confidence /
no run_id; `summarizeProvenance` leaks no number.

## 6. Production-mutation status

**None.** No `detect_regions`, no `refine-region/confirm`, no model call was made against any
real post. The integration was exercised only by tests. The `confirmRefine` path mutates
production *only when a curator actually confirms a SAM mask* — the same already-authorized
mutation that existed before this gate, now additively enriched.

## 7. Deviations from the interface contract — for P2E

1. **`brush_field.geometry` for a SAM mask uses `raster_mask` with `role: 'material_field'`.**
   The contract's roles are perceptual (light/shadow/fold…); a SAM region mask is a *material
   extent* with no perceptual role yet, so `material_field` is the least-wrong coarse choice.
   **P2E should decide whether a region-mask mark wants its own family** (`region_mark`?) rather
   than borrowing `brush_field`.
2. **A drawn `boundary` maps to `frame_mark`/`polyline`.** The contract has no `boundary` family;
   `frame_mark` (a seam/edge) is the closest. Fine, but worth confirming at synthesis.
3. **Marks are session-only.** No deviation from §1–4 (which are silent on persistence), but P2E
   must decide the marks store: additive on the post document, or a new collection. The residue
   in §4 rides on this decision.
4. **`instrument_role`/`origin_action_id`/`mark_source` on grounds and regions are additive dict
   fields.** Safe, but they are a second home for provenance beside the mark. P2E should decide
   whether the mark is the sole record and the ground merely points to it.

None of these change a §1–4 rule; all are placement/family questions for synthesis.

## 8. What Lane B should know

- **The mint-not-mutate contract is real and tested.** If the spike accepts a Konva-drawn
  suggestion, route it through `acceptSuggestion` — do not set `source` in place. The suggestion
  object you pass in comes back untouched; use the returned `accepted`.
- **`visual_layer` → Konva `Group` is enforceable at the data layer:** `createDefaultLayers`
  gives four layers, and `recall` is locked. The spike maps these to Groups; the cap of 3–5 real
  Konva `Layer`s is unaffected because layers here are data, not canvases.
- **`canCiteMark` is the single citability gate.** The spike must never render a suggestion as
  citable; call `canCiteMark`, do not re-derive the rule.
- **Coordinate parity is still the first spike test.** These modules store normalized `0..1`
  geometry (contract §1) exactly as `useStageGeometry` produces — the spike's #1 pass condition
  (marks land within 1px of the SVG rendering) is unchanged and now has a real mark shape to
  round-trip.
- **`actionToDraftMark` already exists** — if the spike arms an act, it can get a draft mark from
  a P2B action directly, `geometry.kind: 'unresolved'` until the pointer supplies it.

## 9. Recommended next

**P2E synthesis** — reconcile Lane A's model with Lane B's spike result: settle the four §7
deviations (region-mask family, boundary family, marks persistence, ground-vs-mark provenance
home), and decide whether the renderer decision flips based on the spike's coordinate-parity and
recall-choreography findings.

**Then P2D-B-persist** (small) — the one-line confirm-endpoint echo that closes the §4 residue,
so SAM provenance survives a reload. Backend-touching, so it is its own gate.
