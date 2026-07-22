# CIRCUIT-001 P2E-B — Production Instrument Mechanics report

**Production-intent. Executed.** Handles, hit-paths, perfect-freehand, and the semantic
brush (with live suggestion quarantine) land on the real Differential surface, in an
isolated worktree, against Lane A's landed P2D-A modules.

| | |
|---|---|
| **id** | CIRCUIT-001 P2E-B · implements the P2D-B disposition (EXTEND THE HYBRID — SVG handles + perfect-freehand) |
| **date** | 2026-07-23 |
| **worktree** | `../semant-p2e-mechanics` · branch `feat/circuit-p2e-mechanics` · base `3aa4b3e` (Lane A P2D-A) |
| **dependency** | `perfect-freehand@1.2.3` (MIT) — the only add; no konva, no fabric, no tldraw |
| **tests** | **513 green** (was 505 at base; +8 new; the pure/handle modules add 21 across 2 files) · production build clean |
| **verified live** | offline fixture harness `/lab/differential` (backend blocked by server-exit-144) — brush role picker, PF toggle, editable handles + reshape, suggestion quarantine → Accept, all exercised by hand; **zero console errors** after the setState fix (§6) |

---

## 1. What was lifted vs rewritten

| piece | origin | disposition |
|---|---|---|
| `handleEditing.js` (214 L) | P2D-B spike `__spikes__/handleEditing.js` | **Lifted near-verbatim**, adapted so `editablePoints`/`withEditedPoints` read/write BOTH a Ground (path/boundary, points at top level) and a `visual_mark` (points under `geometry`). The stub `visualMarkContract.js` did **not** come along — Lane A's `visualMarks.js` is the truth. |
| `freehandStroke.js` (59 L) | new, wrapping the spike's Spike-3 measurement | perfect-freehand as a **drop-in** for `taperedRibbon(px, {maxWidth})` → SVG path `d`. Same signature, so the swap is a one-line ternary in `GroundLayers`. |
| `InstrumentHandles.jsx` (100 L) | new | the handle overlay — draggable vertices, midpoint-insert hints, right-click delete, a **live dashed preview** of the reshaped centerline, locked-layer inert state. A thin VIEW; all math is `handleEditing.js`. |
| hit-paths | new, in `GroundLayers.jsx` | the one SVG tax the spike named (§2). |
| PF toggle | new, in `GroundLayers.jsx` + workspace UI | (§3). |
| semantic brush + quarantine | new, in `DifferentialWorkspace.jsx` | (§4). |

Nothing Lane A owns was touched: `visualMarks.js`, `visualLayers.js`, `suggestionQuarantine.js`,
`regionStore.js`, and `backend/` are all called at their `3aa4b3e` signatures, never modified.

## 2. Hit-paths (2b) — the SVG tax, paid systematically

A 1-px SVG line is unclickable, and the parent `<svg>` is `pointerEvents:none`. Each editable
ground (`path`/`boundary`) now renders a **transparent companion path** with
`strokeWidth = 0.025 × naturalW` (~a fingertip) and `pointer-events: stroke`, which overrides
the parent's `none`. It fires `onPickGround(id)`, and it is suppressed for the ground currently
being edited (its own handles own the pointer then). Gated behind `interactive` (only on the
Select tool), so the recall/Chiasm consumers of `GroundLayers` are byte-unchanged.
**Verified:** clicking the seeded gaze path opens the reshape session (screenshot 01).

## 3. perfect-freehand toggle (2d)

`GroundLayers` chooses the ribbon generator at render:
`(usePerfectFreehand ? perfectFreehandRibbon : taperedRibbon)(px, { maxWidth })`, for path
grounds and the path draft. A UI toggle sits above the stage on the drawing tools.

**Measured on the heaviest real corpus stroke (1194 pts), reproduced this gate:**
`perfect-freehand → 12 651 vertices / 212 370 path chars`; `taperedRibbon → 630 vertices /
13 044 chars`. PF is smoother and (spike-measured) ~18–20× more pressure-responsive; its ~20×
larger polygon is a **render** cost, not a storage cost — **raw input points stay the stored
truth; the polygon is regenerated at render**, so the toggle is a pure view swap and
`taperedRibbon` remains the fallback (the documented rollback). Production bundle grew from
~1 969 kB → ~1 999 kB raw (≈ +30 kB / a few kB gzip) — the disposition's "~5 kB gzip" holds.

## 4. The semantic brush, end-to-end (2e)

**Draw → mark.** The Brush tool now shows a **12-role picker** (`FIELD_ROLE_KEYS`, from Lane A —
never a fourth dialect). Painting a field and pressing *Keep* mints a contract-shaped
`brush_field` via `normalizeMark` — `source: user`, `status: committed`, the chosen `role`,
`linked_ground_ids` to the ground, `linked_action_ids` when an act armed it. `normalizeMark`
fails closed, so a bad role yields no mark rather than a wrong one. Provenance is visible on the
ground (Lane A's `summarizeProvenance` chip). **Verified:** screenshot 03 (picker + toggle),
04-area (kept field reads "Yours").

**The quarantine, live.** A `model_suggested` brush renders as a **distinct teal dashed ghost**
over the stage (`SuggestionGhosts`) — uncitable, never counted, unmistakable for evidence (the
CVAT lesson). The **Model suggestions** inspector panel shows `summarizeProvenance` + role +
**Accept**/**Dismiss**. *Accept* calls Lane A's `acceptSuggestion` (mints `user_confirmed` with
`derived_from`, suggestion preserved), then promotes the geometry to a committed field ground so
it becomes citable evidence; the suggestion leaves the queue the moment a descendant exists.
*Dismiss* calls `dismissSuggestion`. **Verified:** screenshots 04 (ghost + panel) → 05 (accepted,
ghost gone). Lineage/uncitability is pinned rigorously by the DOM test.

**Editable anchors (2c)** work on committed path/boundary grounds (via the store's existing
`updateGround(id, {points})` — id-preserving, persists through the established save path, keeps
linked marks/percepts intact) and on the in-progress draft. Drag a vertex, click the line to
insert one, right-click to remove, **Esc reverts**, *Keep changes* commits. Ref-anchored
endpoints honor `detached_from_ref` (contract v2 #1) via `syncAnchors`. **Verified:** screenshots
01 (handles + panel) → 06 (live preview) → 02 (kept reshape persists).

## 5. Tests

- `handleEditing.test.js` (15) — hit-testing, edit ops, the Transformer-as-point-rewrite answer,
  the Ground/mark adapter, and `detached_from_ref` flagging.
- `freehandStroke.test.js` (6) — PF is a drop-in, output is plain data, honours real pressure,
  and the render-cost (vertex-count) finding holds.
- `instrumentHandles.dom.test.jsx` (8) — the overlay grabs/moves/inserts/removes, a locked layer
  is inert, and the full suggestion flow (pending → Accept mints `user_confirmed`+`derived_from`,
  citable; Dismiss; the pending-filter drops accepted suggestions) on Lane A's real modules.
- Full suite **513 green**; production build clean.

## 6. One production bug found and fixed

Live verification surfaced a React warning — *"Cannot update a component while rendering a
different component"* — from `keepEdit` calling `updateGround`/`setMarks` **inside a `setEditing`
updater** (React runs the updater during render). Refactored to read the edit draft from closure
and commit outside the updater. **This would have fired in `PostDetailPage` too**, not just the
harness — a real fix, not a harness artefact. Console is clean afterward.

## 7. The `// P2F:` swap list (exact)

| file:line | marker | what P2F does |
|---|---|---|
| `DifferentialWorkspace.jsx` (`emitMark`) | `// P2F: … swap this to regionStore.addVisualMark(mark)` | marks live in session state (inherited P2D-A design — no marks backend). When Lane A2's store API lands, persist marks alongside grounds. **Ground reshapes already persist** via `updateGround`; only mark emission is session-local. |
| `DifferentialWorkspace.jsx` (`__diffSeedSuggestion` effect) | `// P2F: the planner emits suggestions once orchestration lands` | a **DEV-only** (`import.meta.env.DEV`) seam that seeds one quarantined brush suggestion so the Accept/Dismiss flow is exercisable without a planner. Remove when a real `model_suggested` action arrives from orchestration. |
| `pages/DifferentialLab.jsx` + its route in `main.jsx` | dev-only harness | offline fixture mount of the workspace. Not linked from nav. Remove (or keep as a lab) at P2F. |

**No contract divergence.** The two v2 decisions are honored: `detached_from_ref` is set by
`syncAnchors` and covered by test; erase stays geometry (`strokes[].op:'add'|'sub'` — the draft
already carries it; rendering composites it). Serialized marks remain contract-shaped (Lane A's
`normalizeMark` is the only door); no renderer node is ever stored.

## 8. What P2F must reconcile / swap when Lane A2's store APIs land

1. **`emitMark` → `regionStore.addVisualMark`** (marks persist; the one real swap).
2. **Remove the two dev seams** (`__diffSeedSuggestion`, `DifferentialLab` route) once a real
   planner emits `model_suggested` actions — then the quarantine panel drives itself.
3. **Confirm the layer model wiring.** This gate uses Lane A's `visualLayers` vocabulary
   implicitly (suggestion vs evidence via source/status); if P2F introduces an explicit layer
   manager UI, route marks through `assignMarkToLayer` so the suggestion→evidence promotion is a
   layer move, not just a source change.
4. **perfect-freehand as the field default** is deferred by design: PF currently governs
   path/trace ribbons and the brush draft preview; soft fields keep their radial wash. Whether
   committed fields render as PF tapered strokes (a new brush aesthetic) is a P2F design call —
   the module is in place behind the toggle, measured, and reversible.

## 9. Disposability

The worktree and the `perfect-freehand` dependency are **production-intent** and reach mainline
at P2F (unlike the P2D-B spike worktree, which was disposable). The two dev seams (§7) and the
`DifferentialLab` harness are the only throwaway parts. The two spike vault docs travel in this
branch so they reach mainline at P2F.
