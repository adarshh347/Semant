# CIRCUIT-001 P2D-B — Renderer spike disposition

**DECISION DOC.** Rests on the executed evidence in
`Build specs/CIRCUIT-001-P2D-B-advanced-instrument-spike-report.md` (three spikes,
39 + 369 tests green, five screenshots, production build clean). It does not
re-derive that evidence.

| | |
|---|---|
| **id** | CIRCUIT-001 P2D-B · resolves the renderer question the P2C decision (Option D) deferred to a spike |
| **date** | 2026-07-23 |
| **rests on** | react-konva 19.0.10 + konva 10.3.0 + perfect-freehand 1.2.3 installed and run in `../semant-p2d-spike`; handles dragged live on both renderers; bundle + taper + pressure measured |

---

## The verdict

> ## EXTEND THE CURRENT HYBRID — SVG handles + perfect-freehand. Do NOT adopt Konva now.

Two dependency changes are authorized *for a later build gate, not by this
document*: add nothing for handles (they are `handleEditing.js`, pure app code);
adopt `perfect-freehand` (MIT, ~5 kB gzip) for brush taper. **Konva is rejected
for the instrument layer at Semant's current and near-term scale.** `Transformer`
is rejected outright, on either renderer.

---

## Why — argued against Spike 2's cost line, not in a vacuum

The P2C decision named editable handles as **the one gap that is a renderer
capability** (its other three gaps were ontology, now built). react-konva was the
sole candidate to close it. **Spike 2 closed it without react-konva.**

- **The gap Konva was named to close is closed by ~70 lines of pointer routing
  plus the 202-line `handleEditing.js` — and that module is renderer-independent,
  imported unchanged by the Konva spike too.** Dragging an endpoint, inserting a
  vertex, deleting one, reshaping a polyline: all confirmed live on the plain SVG
  overlay, writing normalized geometry, serializing clean. (Report §3.)
- **The cost line is decisive.** Konva adds **≈ 94 kB gzip** to the instrument
  route (measured: 97.6 kB vs 3.3 kB lazy chunks). The SVG-handles path adds
  **≈ 3 kB** — a transparent hit-path per trace and a handle layer — plus
  perfect-freehand's ~5 kB. So the choice is *~3–8 kB to close the gap vs ~94 kB
  to close the same gap and inherit a migration.*
- **Konva would put the one thing that already works at risk.** P0.5 recorded
  recall (SVG `pathLength`/`strokeDashoffset`) as the hop the product does best.
  Spike 1 test #8 shows recall can sit as an SVG overlay above a Konva stage —
  but that means adopting Konva buys you *nothing for recall* while still forcing
  29 CSS rules and 25 `vectorEffect` uses into JS. You pay the migration and keep
  the SVG recall anyway.
- **`Transformer` — the specific impedance mismatch P2C flagged — turned out to be
  a non-tool.** It resizes a bounding box via `scaleX/scaleY`; it cannot move one
  vertex of a trace, which is the actual gesture. And a scale-factor is the wrong
  representation for a mark that will be serialized. The counter-argument P2C
  fairly stated ("`Transformer` mutating `scaleX/scaleY` is exactly the kind of
  mismatch that only shows on contact") resolved on contact as: don't use it;
  rewrite points instead. Three lines (`scalePoints`), on either renderer.

**perfect-freehand is adopted (later gate) because Spike 3 earned it on quality,**
not on Konva's coattails: ~18–20× more pressure-responsive and visibly smoother
taper on the heaviest real stroke, at no storage cost (input points stored,
polygon regenerated) and sub-frame generation. It is a pure points-in/polygon-out
swap for `taperedRibbon` with zero ontology risk. Keep both behind a toggle
initially; measure per-frame raster cost during recall on a real device before
making it the recall default.

---

## What this disposition does NOT authorize

- **No dependency lands on the mainline by this doc.** The worktree and its three
  installed deps are thrown away. A later build gate adds `perfect-freehand` only.
- **No renderer swap.** `GroundLayers`, `RegionOverlay`, `fieldCanvas`,
  `useStageGeometry`, recall choreography — all stay.
- **No Konva, no react-konva, no Fabric** in `frontend/package.json`.
- **No `Transformer`** pattern anywhere, on any renderer.

---

## Updated P2C §7 re-open table — with what we now know

| signal | prior ruling | **now** |
|---|---|---|
| P2C needs direct manipulation immediately (drag endpoint / reshape) | bring spike forward; Option B (adopt Konva) | **Resolved WITHOUT Konva.** Direct manipulation works on SVG via `handleEditing.js` + a hit-path. Not a Konva trigger. |
| grounds per post reach ~100+ in real use | Option B | **Still the live Konva trigger.** Measured load is 6 max / 31 total (OH §1.10). At ~100+ *interactive* objects, SVG hit-graph + per-node React reconciliation may degrade and a retained-mode scene graph earns its bundle. **This is the one condition that re-opens Konva.** |
| SVG hit testing proves unworkable once `pointerEvents:none` is lifted | Option B | **Partially tested: it works, with a caveat.** Thin marks need an explicit transparent hit-path (Konva's `hitStrokeWidth` for free). Cheap and systematic; not disqualifying. Re-opens only if hit-graph cost (not clickability) becomes the bottleneck — i.e. it collapses into the ~100+ row above. |
| a hard SVG import/export requirement appears | re-open Fabric | unchanged — still the only Fabric trigger, still absent. |
| recall choreography ports cleanly to canvas AND `Transformer` respects normalized geometry | Option B — "decision was too cautious" | **Both premises fell.** Recall does not need porting (overlay above the stage). `Transformer` does not respect normalized geometry and should not be used. The condition that would have said "P2C was too cautious" **evaluates the other way: P2C was correctly cautious.** |

**Net:** exactly one condition re-opens Konva — **~100+ interactive marks per
post in real use.** Until the corpus shows that (it shows 6), extend the hybrid.

---

## What P2E should build first

1. **`handleEditing.js` into production** (or a thin `useHandleLayer`) over the
   existing `GroundLayers` SVG overlay — with the transparent hit-path per
   editable mark. This is the highest-value, lowest-risk piece and it is already
   written and tested in the spike; cherry-pick the module, not the components.
2. **Reconcile the contract stub with Lane A's real modules** — `visualMarks.js`,
   `visualLayers.js`, `suggestionQuarantine.js` (landed in P2D-A `3aa4b3e`, which
   this spike predates) — using the five friction notes (report §7), especially
   anchor detachment and `op`-as-data.
3. **Adopt `perfect-freehand`** behind a toggle; wire it into `freehandTaper`'s
   call sites; keep `taperedRibbon` as fallback until recall raster cost is
   measured on device.
4. **Make provenance visible in the real UI** (the anti-CVAT requirement) — the
   suggestion layer + citable count from the spike are the pattern to lift.

**Not first, and gated on the 100-mark signal:** any renderer adoption.

> The renderer edits; Semant interprets; the user confirms. Only then does a mark
> enter the circuit. The spike showed the editing can stay on the surface Semant
> already owns — so it should.
