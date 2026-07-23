# CIRCUIT-001 P3-B — Instrument Completion report

**Production-intent. Executed.** The three `// P2F:` debts are paid, and the instrument set is
complete: every mark family now has a hand that makes it — brush (field), trace (line), relation
(tie), refine (region_mask) — with erase-as-data, minimal layer controls, and perfect-freehand as
the measured default. Built in an isolated worktree against Lane A3's landed modules; nothing Lane
A3 owns was modified.

| | |
|---|---|
| **id** | CIRCUIT-001 P3-B · pays the P2E-B debts + completes the instrument set |
| **worktree** | `../semant-p3-instruments` · branch `feat/circuit-p3-instruments` · base `f679141` (origin/main, with P2E-B #64 merged) |
| **dependency** | **none added** — `perfect-freehand@1.2.3` was already on main; no konva, no fabric, no tldraw |
| **tests** | **625 green** (was 592 at base; +33 new across 3 files) · production build clean · lint clean |
| **verified live** | offline fixture harness `/lab/differential` (backend blocked by server-exit-144) — trace/relation/brush role pickers, terminus toggles, erase, PF default, layer controls + lock refusal, and the suggestion Accept flow all exercised by hand; **zero console errors** |
| **precondition** | PR #64 (P2E-B) confirmed **MERGED** into origin/main (`f679141`) before branching |

---

## 1. The three debts, paid

### Debt 1 — marks route through the store (`regionStore.addVisualMark/updateVisualMark`)

**Before:** marks lived in component state (`const [marks, setMarks] = useState([])`); `emitMark`
pushed to that array with a `// P2F:` marker; reshape re-synced linked marks via `setMarks`.

**After:** `emitMark = addVisualMark`; `marks = visualMarks` (the store's live array); reshape
re-syncs linked marks through `updateVisualMark(m.id, { geometry, anchors })`; Accept adds through
`addVisualMark`; Dismiss patches via `updateVisualMark(id, { status:'dismissed' })`. The commit is
the write, and **a draft never thrashes the network** — the store's `persistMeta` filters to
`persistableMarks` (committed/superseded only), so drafts and suggestions stay session-local while
committed marks persist alongside grounds. No `setMarks` remains (grep-proof in test).

### Debt 2 — the real suggestion source (no DEV fork)

**Before:** a `window.__diffSeedSuggestion` seam gated on `import.meta.env.DEV` minted a demo
suggestion.

**After:** deleted. A `model_suggested` (or, for tests, `fixture`-source) action arriving through
the attunement/action path flows through Lane A3's real bridge — `markStaging.draftMarkFromAction`
→ (quarantine) → the suggestion layer → Accept/Dismiss. `applyPerceptualAction` branches on
`action.source`: a model/fixture proposal does **not** arm the curator's hand — it lands in the
quarantine via `receiveModelSuggestion`, which is the honest quarantine door (the bridge already
quarantines `model_suggested`; a `fixture` proposal is quarantined there too, so a suggestion is a
suggestion no matter who proposed it). No `import.meta.env` fork remains in the workspace
(grep-proof in test). The offline harness seeds one suggestion the honest way — as a fixture
*producer* injecting an already-quarantined mark into the store, never a workspace DEV branch.

### Debt 3 — region_mask honesty

**Before:** `confirmRefine` minted a `brush_field` mark with `role:'material_field'` for a SAM mask
(and its `raster_mask` geometry carried **no** `mask_ref`).

**After:** `confirmRefine` mints a **`region_mask`** via `regionMaskMark({ regionId, geometryRev,
source, derivedFrom, model:'sam2' })` — geometry `raster_mask` with `mask_ref:{ region_id,
geometry_rev }`, role `null` (a segmented extent has no perceptual reading until given one), and
**no inline pixels** (contract v2 §7.2-C, enforced by `validateMark`). A fresh mask →
`user_confirmed` via `acceptSuggestion` (lineage back to the quarantined proposal); a
refine-of-existing → `model_refined` with `derived_from` (fails closed without lineage).

## 2. The instrument set, completed

### 2a — Trace tool, end-to-end
A **trace-role picker** (Lane A3's `TRACE_ROLE_KEYS` — 10 roles, gaze/address … return_path),
mirroring the brush's. A hand-drawn path now **always** mints a contract-shaped `trace_mark`
(the P2E-B gap where a hand-drawn trace with no armed act minted no mark is closed:
`markRole = staged?.role || pickerRole`). Editable anchors via `handleEditing`/`InstrumentHandles`
(endpoint drag, midpoint insert/remove — unchanged from P2E-B, now applied to traces). **Ref
anchoring:** at commit, each endpoint is resolved onto the nearest ground/region within tolerance
via the new pure `anchorForEndpoint` → `anchor {kind, ref, at}`; an endpoint far from everything
anchors to *itself* (`kind:'point'`), an honest explicit anchor, never a wrong ref. Dragging a
ref-anchored endpoint sets `detached_from_ref` (via the existing `syncAnchors`, contract v2 #1) and
renders a **distinct hollow ring**. **Ambiguity:** an `ambiguous` toggle replaces the sharp
arrowhead with a **soft fading terminus** — the line never asserts a target the curator did not
name. **Arrowhead** is its own toggle. All of anchors/ambiguous/arrowhead ride in the mark's
`geometry` (and on the ground the renderer performs) — carried through Lane A3's existing geometry
spread, so **no contract module was touched**.

### 2b — Relation tool
A **relation-role picker** (`RELATION_ROLE_KEYS` — 9 roles). Connecting two+ grounds mints a
`relation_mark` whose geometry is **`kind:'derived'`** with `member_ids` — computed from the member
refs at render (the `compositionNodes` idiom in `GroundLayers`), **never stored**. It performs its
refs' honesty: a member that stops resolving is dropped from the connector, and with < 2 resolvable
nodes the connector simply does not draw — it **degrades, never crashes** (proven by the DOM test
mounting a relation with dangling member ids).

### 2c — Erase as data
The brush's **Erase** toggle writes `strokes[].op:'sub'` (⌥ still erases for one stroke). The
canvas composites `'sub'` as `destination-out` (already in `fieldCanvas`, unchanged). The **data**
is identical either way — the op round-trips through the ground and through a `brush_field` mark's
geometry, proven by test.

### 2d — Minimal layer controls
The four system layers (`createDefaultLayers` — scratch/evidence/suggestion/recall) get
**visibility · opacity · lock** controls in a compact strip at the foot of the tool column (no
panel framework). **Recall is system-only — no controls.** A **locked evidence layer refuses**
hit-path picks (`interactive` gated on `!evidenceLocked`), `beginEditGround`, and `commitDraft`
(two guard sites, grep-verified). The suggestion layer's distinct dashed styling stays; its
visibility control hides the ghosts. All mutators are Lane A3's immutable `visualLayers` functions
— never reimplemented. **Live-verified:** Select + unlocked → 2 hit-paths; Select + locked → 0
hit-paths (screenshots 05).

### 2e — perfect-freehand as the default
Measured (test `p3Instruments` records it live): the heaviest reproduced corpus stroke generates in
**~35 ms**, well within a frame budget, and the render cost — not a storage cost, since raw input
points stay the stored truth and the polygon is regenerated at render — is bounded (the corpus tops
out at 6 marks/post). **The toggle default is flipped to perfect-freehand**; `taperedRibbon` remains
the toggle's documented rollback. (The full ~20× vertex-count measurement from P2E-B still stands in
`freehandStroke.test.js`.)

## 3. Tests (+33, total 625)

- **`p3Instruments.test.js`** (new) — the three debts (store-persistability round-trip; grep-proof
  no DEV fork + the `draftMarkFromAction` fixture path; `region_mask` shape + accept lineage +
  fail-closed `model_refined`), plus trace geometry conformance, relation derived geometry, erase op
  round-trip, layer lock (mechanism + the two guard sites), and the PF measurement + default flip.
- **`handleEditing.test.js`** (+4) — `anchorForEndpoint`: nearest-within-tolerance, closer-of-two,
  point-anchor-when-far, and promote-then-detach.
- **`groundLayers.p3.dom.test.jsx`** (new, 8) — renders: plain path shows a chevron; ambiguous shows
  a soft terminus and no chevron; `arrowhead:false` suppresses it; a detached endpoint shows the
  hollow ring; a relation with a dangling member does not crash; evidence visibility/opacity wrap the
  committed group.
- One defensive fix I own: `fieldCanvas.paintFields` now guards a null 2D context (jsdom) — never
  throws where there is no canvas to paint.

Full suite **625 green**; production build clean; lint clean.

## 4. Live verification (offline harness)

`/lab/differential` over an offline fixture (data-URI image, seeded path + boundary grounds, two
regions, one seeded quarantined suggestion). Exercised by hand, **zero console errors**:

| # | screenshot | shows |
|---|---|---|
| 01 | `01-overview-quarantine-layers.jpg` | the PF-default trace, the teal dashed **suggestion ghost**, the **Model suggestions** panel (Accept/Dismiss), and the **layer controls** |
| 02 | `02-trace-roles-terminus.jpg` | the trace **role picker** + **arrowhead** / **ambiguous target** toggles + PF checked |
| 03 | `03-relation-roles.jpg` | the **relation-role picker** (similarity … address relation) |
| 04 | `04-brush-roles-erase.jpg` | the field-role picker + the **erase** toggle + PF checked |
| 05 | `05-layers-evidence-locked.png` | the layer strip with **Evidence locked** (Recall = system, no controls) |
| 06 | `06-suggestion-accepted.jpg` | after **Accept** — ghost gone, panel gone, the model's field promoted to a committed ground ("a field the model proposes") |

Live measurements (JS-verified, same session): lock refusal — Select+unlocked **2** hit-paths,
Select+locked **0**; Accept — pending 1→0, ghosts 1→0, grounds 2→3.

## 5. `// P3F:` markers

**None emitted.** Every API P3-B needed existed on origin/main at the signatures Lane A3 shipped
(`addVisualMark`/`updateVisualMark`, `draftMarkFromAction`, `regionMaskMark`, the role
vocabularies, `visualLayers` mutators). Nothing was stubbed or reimplemented; no missing-API debt
was created.

## 6. Ownership & parallel safety

Modified only owned files: `DifferentialWorkspace.jsx`, `GroundLayers.jsx`, `handleEditing.js`,
`fieldCanvas.js`, `DifferentialWorkspace.css`, `pages/DifferentialLab.jsx` (dev harness), and tests.
**Not touched:** `visualMarks.js`, `visualLayers.js`, `suggestionQuarantine.js`, `markStaging.js`,
`regionStore.js`, `recall.js`, blocknote/*, RefPicker, PostDetailPage, backend/ — all called at
their origin/main signatures. Lane A3's parallel PR **#68 (P3-A — marks circulate)** is open; if the
two collide on the Differential surface, a small **P3F reconcile** in the main tree resolves it (the
same shape as the P2E-B → P2E-A merge gate).

## 7. Residue

- The `DifferentialLab` harness (`/lab/differential`) + its route remain the only dev-only parts —
  a lab, not shipping UI. Keep or remove at a later gate.
- Whether a *committed* field should render as a PF tapered stroke (a new brush aesthetic) rather
  than the radial wash stays a design call, deferred; PF currently governs path/trace ribbons and
  the brush draft.
</content>
