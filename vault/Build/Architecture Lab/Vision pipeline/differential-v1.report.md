# Differential v1 — implementation report

**Built against** `architecture-lab/differential-v1.build.md` (the repo-grounded spec).
**Branch** `feat/frontend`. **Tracker** issue #46. **Commits** `5de29ab` (spec) →
`563d240` (A) → `49d71cd` (B) → `6c3dbe6` (C) → `4cc85cc` (D) → this (E).

Differential is the dedicated percept-construction workspace. v1 closes the full
circulation — **image → Ground → Percept → Mention → recall on the image** — and ships
first versions of all seven perceptual operations. Verified end to end in-browser at
every increment (screenshots below), not by reading source.

---

## Changed files

**New (`frontend/src/differential/`)**
- `useStageGeometry.js` — the extracted coordinate contract (contentBox + the only
  sanctioned pointer↔normalized converters). RegionSurface now consumes it too.
- `grounds.js` — Ground records for all seven types, the Region adapter, `resolveGround`
  (graceful detachment), `groundBBox`/`groundCenter`, `hydrateGrounds`. (+ `grounds.test.js`)
- `fieldCanvas.js` — Soft Field painter (alpha-buffer radial-gradient stamps, tinted with
  the one accent, wash ≤0.32; bloom = radius/alpha ramp).
- `freehandTaper.js` — tiny vendored taper (ribbon, centerline, chevron, length). (+ test)
- `recall.js` — `buildRecallScript` (recede → primary → supporting-stagger → expression,
  composition expansion) + `useRecallPlayer` (reduced-motion aware). (+ test)
- `GroundLayers.jsx` — the shared renderer: canvas field + SVG (Path·Boundary·Frame·
  Region·Constellation·Relation). Consumed by both surfaces; recall-only in Chiasm.
- `DifferentialWorkspace.jsx` / `.css` — the workspace shell, tools, inspector, composer.

**Extended (surgical)**
- `state/perceptMentions.js` — expression Percepts (`pctx_`, new kind; the locked
  attention-percept shapes untouched). (+ tests)
- `state/regionStore.js` — grounds state + CRUD, expression percepts, recall state, and a
  **separate debounced `PATCH {grounds, percepts}` write path**.
- `components/RegionSurface.jsx` / `.css` — consumes the shared geometry; mounts
  GroundLayers in recall-only mode + caption.
- `components/RegionOverlay.jsx` — optional `litIds` set (multi-select) + `onSelect` passes
  the event (⇧).
- `components/RefPicker.jsx` — `kind:'percept'`.
- `components/blocknote/{Manuscript,regionRefInline}.jsx` — `/percept` slash item;
  `emit()` carries `perceptId` so focus routes to recall.
- `components/PostDetailPage.jsx` / `.css` — `workspaceMode`; percept-Mention focus/click →
  `playRecall`; the quiet ◈ Differential entry.
- `backend/schemas/post.py`, `backend/routers/posts.py` — `grounds`/`percepts` on
  `Post`/`PostUpdate` + `post_helper` (~9 lines, no migration).

24 files, +2801 / −68.

---

## Decisions taken vs the spec

Followed the spec's locked decisions exactly. Where it left a choice, what I chose:

- **Persistence** — grounds/percepts in NEW post fields via `PATCH` (never inside
  `region_annotations`), exactly as the spec's "important decision" prescribes. Only
  **expression** percepts persist; attention percepts (`pct_`) stay reconstructed on
  hydrate, so nothing about the old model changed on disk.
- **Region multi-select light** — added an optional `litIds` Set to RegionOverlay rather
  than overloading the single `focusId`; back-compat preserved (both code paths kept).
- **Collect/Connect membership** — members are chosen from the grounds list (toggle) and
  by clicking regions (adapted to region-Grounds on the spot, deduped by `region_id`);
  Constellation also takes raw image points. I did **not** hit-test thin path/boundary
  geometry on the image — list + region clicks are more reliable and honest.
- **Recall of compositions** — `buildRecallScript` expands a Constellation/Relation into
  itself then its members, reusing the existing stagger, so the whole scene performs
  ("pulse sequential" / "A, then B, then unite") with no new timeline machinery.
- **Focus treatment** — per the spec, no fragile cross-layer SVG masking: the image
  recedes (CSS filter/opacity), evidence renders above.

---

## Compatibility approach

- **Region is preserved, not absorbed.** Region ids, `Region.block_id`, `data-region-ids`
  chips, detection, persona rollup, embeddings all keep working. A Ground references a
  Region via `{ground_type:'region', region_id}`; a re-dissect that replaces the Region id
  degrades the Ground to "detached evidence" (renders nothing, listed) — covered by a test.
- **The locked shapes are untouched.** `perceptMentions.test.js` still passes; expression
  percepts are a *new* kind beside the attention percepts, not a mutation of them.
- **Chip round-trip.** The `/percept` chip is the same `regionRef` inline content with
  `refKind:'percept'`; a new converter test asserts `data-percept-id` (the recall trigger)
  and the ground ids survive import→export, alongside the existing `/part` and `/lens` gates.
- **detect-regions can never wipe grounds** — the whole reason grounds live outside
  `region_annotations`.

---

## Working · v1-quality · known limitations

**Working (verified in-browser, both surfaces):** every operation composes a Ground, every
Ground composes a Percept, every Percept persists, survives reload, inserts as a `/percept`
Mention, and replays from that Mention on the Chiasm pane. Both rhythms — immediate
composer and accumulative tray — work. All six ground types + expression percepts
round-tripped through the live DB.

**v1-quality (works, will deepen):** the freehand taper is a small vendored approximation
(not perfect-freehand); Boundary is a blurred stroke at the 0.2 veil ceiling (legible but
deliberately faint); recall timings are fixed constants; the narrow-viewport inspector
stacks (no dedicated sheet gestures yet).

**Known limitations:** no deep zoom (OpenSeadragon is explicitly out of v1 — the geometry
contract is ready for it, "later deep-zoom swaps the container"); no find-similar /
overlay-similar (embeddings wiring deferred, manual Collect stands alone as specified);
Frame evidence is gathered from the current selection/tray, not by spatial containment.
Pre-existing, out of scope: with the Manuscript in edit mode but unfocused, plain typing
triggers the Chiasm g-nav hotkeys (flagged at increment A; not a Differential change).

---

## Exact test output (`npm test`, vitest)

```
✓ src/differential/freehandTaper.test.js (7 tests)
✓ src/state/perceptMentions.test.js (17 tests)
✓ src/differential/grounds.test.js (15 tests)
✓ src/differential/recall.test.js (6 tests)
✓ src/components/blocknote/blockConvert.test.js (18 tests)
Test Files  5 passed (5)
     Tests  63 passed (63)
```

Clean production build (`npm run build`), eslint clean across the module.

---

## Screenshots (scratchpad)

`diff-a-*` Chiasm resting · Differential resting · region selected · untouched hold-O ·
Manuscript-state-survives-enter/leave. `diff-b-*` brush draft · composer · in-Differential
recall · Chiasm recall from a read-view `/percept` chip. `diff-c-*` path/boundary/frame
drafts + recalls · region multi-select · Chiasm path recall. `diff-d-*` constellation/
relation drafts + recalls · tray · Chiasm relation recall. `diff-e-1-narrow` stacked
inspector.

---

## LEGACY-NAMES

Per locked decision #1, internal legacy filenames were left where renaming was risky. No
new legacy names introduced by this build. Existing ones deliberately kept:

- `RegionSurface.jsx` / `RegionOverlay.jsx` / `regionStore.js` — the Chiasm image pane and
  its store keep their names; Differential extends the store rather than forking it.
- `region_annotations` (backend) — the Region array keeps its name; grounds/percepts are
  additive sibling fields.
- Comments in older code still say "Field" for the Chiasm pane; user-facing text and all new
  code say **Differential**.

---

## Next expansion point per Ground type

- **Region (Select)** → SAM2 click-to-segment: the `detector` provenance slot and the
  region adapter are already in place; a SAM ground is just a new detector on a region.
- **Field (Brush)** → pressure-true tablet input + eraser refinement; the stroke model
  already carries per-point pressure and `op:'sub'`.
- **Path (Trace)** → curve smoothing / editable control points; `freehandTaper` is the
  seam to swap for perfect-freehand if a runtime dep becomes acceptable.
- **Boundary (Trace)** → edge-assist snapping to image gradients; band + centerline are
  independent already.
- **Constellation (Collect)** → similarity-suggested members (overlay-similar) once the
  region-embeddings backfill lands — the projection endpoint is the seam (see
  `feature-field-projection.md`).
- **Relation (Connect)** → a small typed vocabulary over the free-text label (answers /
  echoes / opposes …) without losing untyped freedom.
- **Frame** → spatial-containment evidence (auto-gather grounds whose bbox falls inside a
  sub-frame) + the Atlas/Codex export point the spec reserves.
- **Recall** → per-type performance signatures are stubbed to a shared ramp; each can grow
  its own choreography (the script already tags `ground_type` per step).

**Phase boundary:** v1 is complete (all seven operations, the full loop, both rhythms,
recall on both surfaces). The deferred surface is deep-zoom (OpenSeadragon) and
similarity — both have their seams prepared here.
