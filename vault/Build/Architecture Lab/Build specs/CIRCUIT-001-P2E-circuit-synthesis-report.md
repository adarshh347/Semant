# CIRCUIT-001 · P2E — Circuit Synthesis Report

**Gate kind:** synthesis (reconcile lanes + real product integration)
**Status:** shipped
**Branch:** `feat/rehearsal-research-r1` (HEAD was `c14f82a` — P2C-MS2)
**Screenshots:** `CIRCUIT-001-P2E-screenshots/`

---

## 0. Headline

The lanes are now one circuit. A Manuscript sentence returns to Differential and **prefills First Attention**; First Attention **suggests structured acts** from it; arming a mark-making act shows the **draft `visual_mark`** it will produce — role, provenance, citability — before any geometry exists; and the Manuscript can **inspect the marks behind a percept's evidence**, honestly labelled session-only. Verified end-to-end in the browser, no model call, no mutation.

## 1. A live lane was working the same files — what I did about it

Gate 0 surfaced a **parallel durable-marks lane actively editing `state/regionStore.js` and `differential/visualMarks.js`** (building `visual_marks` persistence: `persistableMarks`, `PERSISTED_STATUSES`, hydration from `post.visual_marks`, PATCH persistence, and a full store API). My first store edit collided (a duplicate `visualMarks` declaration).

Per the Gate 0 rule ("if dirty files overlap, stop"), I:

- **Reverted my collision immediately** and did **not touch `regionStore.js` or `visualMarks.js` again.**
- Discovered the lane had **already exposed the exact store API I needed** — `visualMarks`, `addVisualMark`, `updateVisualMark`, `removeVisualMark`, `visualMarksForGround`, `visualMarkById` — so my synthesis **consumes `store.visualMarks` read-only** rather than adding its own plumbing.
- Kept all my work on **files the lane was not editing** (AttunementPanel, DifferentialWorkspace, PassageInspector, PostDetailPage, manuscript modules) plus one **new** module.
- At commit, staged **only my files**; the lane's staged `regionStore.js`/`visualMarks.js`/`visualMarks.test.js`/`visualMarksPersistence.dom.test.jsx` were left in the index, untouched.

This is the synthesis working as designed: my session-only-marks plan was **superseded by the lane's durable version**, and I adopted theirs instead of forcing mine.

## 2. What was reconciled (Gate 6 — vocabulary)

The action / mark / layer vocabularies were checked for drift. The finding: **they are already reconciled at the code level and should stay separate modules**, because each owns a *different lifecycle* while *sharing* the role vocabulary by import (not by copy):

- `perceptualActions.js` owns **action** `source`/`status`; `visualMarks.js` imports P2B's `FIELD_ROLES`/`TRACE_ROLES`/`RELATION_ROLES` directly and asserts `MARK_SOURCES ⊇ SOURCES` in a test, so the two cannot drift. A mark's `status` (`draft…superseded`) is deliberately its **own** vocabulary — a mark's life is not an action's life.
- `markStaging.js` (new, this gate) is the **only** place that composes the two: action → draft mark → display. It invents no vocabulary.

The four open drift items from P2D-A §7, settled here as recommendations for the durable-marks lane (which owns the storage decision):

| Item | Resolution |
|---|---|
| `region_mask` vs `raster_mask` + `material_field` | **Keep `brush_field` + `raster_mask` + `role: material_field`.** A SAM mask is a material extent; a new `region_mark` family would fork the vocabulary for one geometry kind. Revisit only if regions need mark-level roles a field cannot express. |
| `boundary` as `frame_mark` vs a boundary family | **Keep `frame_mark`** (`frame_role: boundary`). A boundary is a seam framing evidence; it needs no family of its own. |
| session-only vs durable marks | **Superseded by the parallel lane** — it is building durable persistence (`persistableMarks`, only `committed`/`superseded` reach storage; suggestions stay session truth). My surfaces already say "session — not saved," which stays correct for anything unpersisted. |
| `instrument_role`/`origin_action_id`/`mark_source` (additive dict fields on grounds) vs the mark | **The mark is the record of record.** The additive ground fields are a denormalised echo for a surface that has the ground but not the mark; they must never be read where the mark is available. |
| `detached_from_ref`, erase-as-data | **Not defined in any lane.** Not invented here. Erase remains canvas `destination-out`; a data-model erase is a future gate, not a P2E term. |

## 3. What was integrated (real product wiring)

### Gate 2 — Manuscript → First Attention prefill *(the MS2 deferred caveat, now wired)*

- `AttunementPanel` accepts a `prefill` prop: it **seeds the prompt** (guarded by a ref so a curator who edits is never re-seeded), shows *"Brought from the Manuscript — suggest acts when ready."*, and **never auto-submits** — the planner keys only on words the curator approves.
- `DifferentialWorkspace` threads a `firstAttentionPrefill` prop through (2-line change, far from the marks code).
- `PostDetailPage` holds the prefill: `sendSelectionToDifferential(text)` seeds it with the **selection text**; `reviseInDifferential` seeds it with the **percept's expression**; both cleared on exit so a later manual open starts blank.

### Gate 3 — action cards create/stage visual marks

- New pure module **`markStaging.js`**: `draftMarkFromAction(action)` (wraps Lane A's `actionToDraftMark`, quarantines a model-authored action at the bridge, fails closed to `null`), `markDisplay(mark)` (one honest descriptor — role, provenance via `summarizeProvenance`, `citable` via `canCiteMark`, `derived_from`, `needs_geometry`, `session:true`), `marksForPercept`, `marksSummary`.
- `AttunementPanel`'s `ActionCard` shows the **draft mark the moment an image-act is armed** — *"Draft mark · Light field · System · Ready for your mark"* — carrying role, provenance and `action_id`, geometry still the curator's hand.
- **Commit-time marks were already done by Lane A** (`commitDraft` emits a committed `visual_mark` with `linked_action_ids`; a selected ground shows `summarizeProvenance`). This gate adds the **intent-time** half.

### Gate 4 — Manuscript inspects visual mark references

- `PassageInspector` reads `store.visualMarks` (read-only) and, for a focused percept, shows the marks behind its evidence via `marksForPercept` → `markDisplay`: **type · role · provenance · citable/not · `derived_from`**, under a **"Visual marks · Session — not saved"** heading. A model suggestion renders visibly quarantined (dashed, "not citable"); a user/confirmed mark reads differently.
- The link path is real and needs no new field: a committed mark rides a ground (`linked_ground_ids`), the percept cites the ground (`ground_ids`), so the writing reaches the instrument behind what it writes about.

## 4. What remains lane-specific (not touched)

- **Durable `visual_marks` persistence** — the parallel lane's active work in `regionStore.js`/`visualMarks.js` (hydration, PATCH, `persistableMarks`). I consume its read API only.
- **`GroundLayers`/`fieldCanvas`/renderer** — untouched (see Gate 5).

## 5. Mechanics from Lane B (Gate 5) — deliberately none

The renderer verdict (`Decisions/CIRCUIT-001-P2C-instrument-renderer-decision.md`, **Decided: Option D**) governs here, and it is explicit:

- **Keep the existing SVG+canvas hybrid. Adopt no renderer. Do not install Konva/Fabric.**
- **`perfect-freehand` is NOT installed and NOT adopted** — `freehandTaper.js` is the vendored substitute already in the tree.
- Native SVG hit-testing is **already free** today; **editable handles are the one real renderer gap and are explicitly deferred** to the future throwaway `react-konva` spike.
- There is **no `handleEditing.js`** anywhere — it was never built.

So there is no low-risk mechanic to "bring in": the three candidates the gate listed (editable handle helper, transparent hit-path, perfect-freehand toggle) are each either the deferred renderer gap or an unadopted dependency. Doing any of them would violate the constraints ("do not adopt a new renderer", "do not install Konva/Fabric"). **Correct action: integrate nothing renderer-level; the production plan is the deferred spike.** Recorded honestly rather than shipping a mechanic the decision forbids.

## 6. Tests & build (Gate 7)

| | Before (P2C-MS2) | After |
|---|---|---|
| Test files | 26 | **32** |
| Tests | 501 | **563 — all green** |
| New this gate | — | `markStaging.test.js` (20), `AttunementPanel.p2e.dom.test.jsx` (8), `PassageInspector.p2e.dom.test.jsx` (7) |
| Production build | clean | **clean** |

The +35 also includes the parallel lane's suites (`markProvenance`, `visualMarksPersistence`), which now pass. New coverage proves: an armed brush/trace/connect becomes the right draft mark with `action_id`/role/provenance preserved; a model-suggested action is quarantined and not citable; `ask_model_reading` and no-mark families fail closed to null; the inspector shows a session mark as "not saved", a suggestion as uncitable, a user mark differently, and never a fake "supported"; First Attention seeds from a prefill and **does not auto-submit**.

## 7. Browser verification (Gate 8)

Live, post `6a5ffc05a3ddb6341fd699f9`. Screenshots in `CIRCUIT-001-P2E-screenshots/`.

| # | Check | Result |
|---|---|---|
| 1 | Manuscript: select prose → Send to Differential → prompt prefilled | ✅ First Attention seeded with the exact sentence; *"Brought from the Manuscript"* notice; **0 acts — no auto-submit** |
| 2 | Differential: Suggest acts → arm brush → staged mark appears | ✅ 4 acts from the prefilled prompt; arming Brush light field shows **"DRAFT MARK · Light field · System · Ready for your mark"**, `citable=false` |
| 3 | Inspector still collapses/expands; Recall; Revise | ✅ collapses to `Percept · 1 ground · 1 passage`; re-expands; Recall + Revise present and working |
| 4 | Console errors | ✅ none |
| 5 | Cancel edit / production mutation | ✅ Cancel restores; `updated_at` unchanged |

*(The inspector's Visual-marks section shows only when a **committed** mark links to the percept; this quick session armed but did not draw geometry, so none was committed — the section is unit-verified with committed marks in `PassageInspector.p2e.dom.test.jsx`.)*

## 8. Production mutation status

**NONE.** `updated_at` identical across the whole session (`2026-07-22T01:53:14.959000`); `text_blocks: 0`, `grounds: 1`, `percepts: 1`, `visual_marks: 0`. A sentence was carried across, First Attention seeded, acts suggested, a brush armed — all cancelled, none reached the API.

## 9. Visual mark / action bridge status

**Complete for the non-persistent path.** `action → draftMarkFromAction → markDisplay` is live at intent-time (AttunementPanel) and consumed read-only by the Manuscript (PassageInspector); commit-time marks are Lane A's. The bridge preserves `action_id`, role, source, status, provenance, and quarantines model authorship. Durable persistence is the parallel lane's, in flight.

## 10. Manuscript return path status

**Complete.** Prose → First Attention (prefill + suggest, no auto-submit); percept → First Attention (expression) + grounds focus + recall; both are real, visible, mutation-free returns. The circuit is now bidirectional at the First-Attention seam.

## 11. Files changed (mine only)

- `frontend/src/differential/markStaging.js` + `markStaging.test.js` *(new)*
- `frontend/src/differential/AttunementPanel.jsx` + `.css` + `AttunementPanel.p2e.dom.test.jsx` *(new)*
- `frontend/src/differential/DifferentialWorkspace.jsx` *(prefill prop, +2 lines)*
- `frontend/src/manuscript/PassageInspector.jsx` + `.css` + `PassageInspector.p2e.dom.test.jsx` *(new)*
- `frontend/src/components/PostDetailPage.jsx` *(prefill state + wiring)*
- `vault/…/CIRCUIT-001-P2E-circuit-synthesis-report.md` + screenshots

**Not touched / not staged:** `regionStore.js`, `visualMarks.js`, `visualMarks.test.js`, `visualMarksPersistence.dom.test.jsx` — the parallel durable-marks lane's.

## 12. Caveats

1. **A parallel durable-marks lane is mid-flight** in `regionStore.js`/`visualMarks.js`. My work consumes its read API and does not stage its files; when it lands, the inspector's Visual-marks section will show **persisted** marks across reloads, and its "session — not saved" copy should be revisited per-mark using `PERSISTED_STATUSES`.
2. **First Attention prefill for a percept** rides on "Revise in Differential" (seeds the expression). If a distinct "send percept expression without focusing grounds" act is wanted, it is a small addition.
3. **No renderer mechanics** were integrated (§5) — correct under Option D, but it means editable handles remain the outstanding renderer gap.

## 13. Next gate recommendation

**P2F — durable-marks landing + Manuscript citation.** Once the parallel lane commits `visual_marks` persistence: (a) let a Manuscript sentence **cite a committed mark** (turning MS2's preview-only `map_sentence` into a real staged citation via `canCiteMark`); (b) make the inspector's "session/saved" wording derive per-mark from `PERSISTED_STATUSES`; (c) the deferred **`react-konva` throwaway spike** for editable handles, on a branch, without touching `package.json`.

Still not recommended: any model dispatch. `no model reading recorded` stays a true record until the circuit can record events — the packet must not be sent before the ledger can hold the reply.

---

*The model may suggest; Semant shapes; the curator confirms. The lanes now meet at First Attention, and a mark can be proposed, seen for what it is, and refused — before it is ever evidence.*
