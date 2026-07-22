# CIRCUIT-001 P2D-B — Advanced Instrument Mechanics: three spikes + open-source harvest

**Lane B (experimental/mechanical). Report of an EXECUTED spike.** Three candidate
mechanics were built and run head-to-head so the P2E synthesis chooses on evidence.

| | |
|---|---|
| **id** | CIRCUIT-001 P2D-B · answers P2C-OH §6.4 / the renderer question deferred by the P2C decision |
| **date** | 2026-07-23 |
| **worktree** | `../semant-p2d-spike` · branch `spike/circuit-p2d-instruments` · **DISPOSABLE** |
| **base commit** | `01d0300` (feat/rehearsal-research-r1) |
| **deps installed (worktree only)** | `konva@10.3.0` · `react-konva@19.0.10` · `perfect-freehand@1.2.3` — all MIT, zero peer warnings against React 19.1.1 |
| **status** | **Executed.** 39 spike tests + full 369-test suite green · production build clean · all three spikes exercised by hand with screenshots |
| **survives into P2E** | ONLY this report + the disposition doc. The `__spikes__/` tree, the dev route, and the three installed deps are thrown away with the worktree. |

> **Disposability, stated plainly:** nothing in `frontend/` on the mainline was
> touched. The spike lives entirely in `frontend/src/differential/__spikes__/`
> plus one lazy dev route (`/lab/p2d-spike`, not linked from any nav). It can be
> deleted with `git worktree remove`. Only the two vault docs are meant to
> outlast it; they can be cherry-picked or re-copied into P2E.

---

## 0. What was built

| file | non-blank LoC | role |
|---|--:|---|
| `visualMarkContract.js` | 432 | LOCAL STUB of the P2D interface contract (see §1) — schemas, validators, serialization whitelist, suggestion quarantine |
| `handleEditing.js` | 202 | renderer-independent anchor math — **imported by BOTH Spike 1 and Spike 2** |
| `spikeFixture.js` | 206 | shared workspace + 1194-point synthetic stroke + data-URI base image |
| `freehandCompare.js` | 146 | Spike 3 measurement harness |
| `KonvaInstrumentSpike.jsx` | 312 | Spike 1 |
| `SvgHandlesSpike.jsx` | 278 | Spike 2 (null hypothesis) |
| `spikeShared.jsx` + `Spike3Panel.jsx` + host page | ~250 | chrome, serialization panel, dev route |

Tests: `visualMarkContract.test.js` (21) · `handleEditing.test.js` (11) ·
`freehandCompare.test.js` (7) = **39 green**, plus the pre-existing **369-test
suite still green** (production untouched).

### 0.1 The binding contract did not exist on the base commit

`Build specs/CIRCUIT-001-P2D-interface-contract.md` — the spec the brief names as
binding — **was not present at `01d0300`, and no `visualMarks.js` existed in
`frontend/src/differential/`.** Lane A is authoring both in parallel. Per the
brief ("otherwise stub the signatures locally and note any signature you wished
were different"), `visualMarkContract.js` reimplements the contract from its
published ancestor, **P2C-OH §4.1–§4.6**, plus the `derived_from` acceptance edge
that OH §3.5.1 (Label Studio `parent_prediction`) prescribes. Divergences are
Lane A's to win; friction notes are in §7.

**UPDATE (observed at commit time):** while this spike ran, **Lane A's P2D-A
landed on `feat/rehearsal-research-r1` (`3aa4b3e`)** with the real modules —
`frontend/src/differential/visualMarks.js` (329 L), `visualLayers.js` (158 L),
`suggestionQuarantine.js` (203 L), and their tests. This spike is based on the
pre-P2D-A commit `01d0300` and does **not** contain them, so the stub was correct
to build. **The first P2E task is to reconcile `visualMarkContract.js` against
those three real modules** using §7 — the stub is a throwaway test double, they
are the ontology.

---

## 1. Coordinate contract on both renderers (Spike-1 test #1 / Spike-2 baseline)

**Result: PASS on both, and the finding is that the renderer does not remove the
need for the existing contract — it consumes it unchanged.**

`useStageGeometry.js` was NOT reimplemented. Both spikes import
`pointerToNormalized` / `contentBox` verbatim and store only normalized
`0..1` natural-image coordinates. The letterbox math (`preserveAspectRatio`
equivalent) is never re-derived — the historical "earrings on a cheekbone" bug
(OH §1.3) cannot recur because the sanctioned converter is the only path in.

**The one real Konva coordinate finding** — recorded because it is a trap a later
gate would otherwise hit: the *tempting* Konva idiom is one
`<Group scaleX={content.w} scaleY={content.h}>` so children draw in `0..1`. This
is **rejected**: `content.w ≠ content.h` on any non-square image, so a group
scale turns every anchor circle into an ellipse and every uniform stroke into an
anisotropic one. `strokeScaleEnabled={false}` fixes stroke width but not the
circle distortion. So Spike 1 converts normalized→content-box-pixels in JS —
**exactly what `GroundLayers.jsx:41 toPx` already does for SVG.** The conversion
is renderer-independent; Konva inherits it, it does not replace it.

Coordinate parity was confirmed by eye against a fixture image with landmarks at
known normalized positions (0.25/0.5/0.75 grid), across the pane's resize range
(the same `ResizeObserver` the contract already uses).

---

## 2. Spike 1 — react-konva

Screenshot: `CIRCUIT-001-P2D-B-screenshots/01-konva-handle-drag.jpg` (handle drag
mid-reshape) and `05-konva-accept-and-lock.jpg` (accept + layer lock).

Answered in the brief's priority order.

### #3 (the decision) — editable handles. Does `Transformer` fight normalized geometry?

**RESULT: `Transformer` was not used at all, and should not be. Custom draggable
anchor shapes write normalized points directly. Confirmed live** (dragged an axis
trace endpoint; the polyline reshaped; the serialized `points` updated; no
`scale*` field appeared anywhere in the record).

The reasoning, which is the load-bearing part:

- **`Transformer` resizes a bounding box.** It multiplies a node's
  `scaleX`/`scaleY`. It has no concept of "the third vertex of this polyline" —
  it cannot move one anchor of a trace, which is the actual editing gesture
  Semant needs. So `Transformer` is not even the right tool for the job the gate
  asked about; it answers a question (resize-the-whole-shape) Semant is not
  asking.
- **Even where a scale IS wanted** (grow a whole mark), `scaleX/scaleY` is the
  wrong representation: the next thing Semant does with a mark is *serialize* it,
  and a polyline whose truth lives in an unserialized scale factor renders
  correctly and **stores incorrectly**. `handleEditing.scalePoints` therefore
  bakes a scale into the points immediately (a point rewrite), so there is never
  a transform to forget to flatten. This is a three-line function and it is the
  whole `Transformer` answer.
- Native draggable `<Circle>` nodes (`draggable`, `onDragMove` → invert through
  the content box → `moveAnchor`) do exactly what is needed, idiomatically, and
  are undistorted because the geometry group is not scaled. Right-click deletes a
  vertex (`onContextMenu`). **`Transformer` is unnecessary; prefer custom anchors
  — recorded per the brief's instruction.**

### #1 base image + normalized mapping — PASS (see §1).

### #2 semantic brush styled by role, eraser — PASS.
Freehand strokes render via `<Path>` with a `d` from either `freehandTaper` or
`perfect-freehand` (a live toggle). Role drives colour (`light_field` amber,
`shadow_field` violet, `fold`, `gaze_field`, …). **Eraser: Konva supports
`globalCompositeOperation: 'destination-out'` natively** on a shape, and it
works — but the mark still stores `op:'sub'` as data, so the erase is *modeled*,
not only *composited*. That matters because the SVG surface (Spike 2) has no
`destination-out`, and a mechanic that only exists as a composite would not port.
**Verdict: keep erase as subtractive-stroke DATA; let each renderer composite it
however it can.**

### #4 relation lines, derived geometry — PASS.
`relation_mark` connectors are computed from member centres via
`relationNodes(mark, centerOf)` at render time and are **never stored**
(`geometry:{kind:'derived'}`; the validator refuses a relation that stores
coordinates). Moving a referenced brush moves the connector with zero writes to
the relation mark — verified by unit test.

### #5 layers → Konva **Group**, ≤3 real Layers — PASS, PROVEN.
The on-screen readout **"Konva `<Layer>` count: 1"** counts the actual mounted
`<canvas>` elements (react-konva renders one `<canvas>` per `<Layer>`). All four
`visual_layer`s are Konva **`<Group>`**s inside a single `<Layer>`; visibility →
`visible`, opacity → `opacity`, lock → `listening={!locked}`. The OH §5
"3–5 Layer max" constraint is honoured with room to spare.

### #6 suggestion mode + accept — PASS, confirmed live.
The `model_suggested` brush renders on a visibly-distinct `suggestion` layer and
is **uncitable** (`isCitable` returns false). Clicking *Accept* mints a new
`user_confirmed` mark with `derived_from` pointing at the suggestion; the
suggestion survives untouched (Label Studio's read-only-prediction rule). Live:
**citable count went 6/7 → 7/8**; the serialized record shows a
`"source":"user_confirmed"` mark with `"derived_from":"vm_…"`.

### #7 serialization panel — PASS.
Live JSON of contract-shaped marks/layers only, with a green **"no renderer
object"** badge. The guarantee is mechanical (§4), not visual.

### #8 recall coexistence — REASONED (no port attempted, per brief).
The SVG `pathLength`/`strokeDashoffset` recall choreography **can plausibly run as
an SVG overlay ABOVE the Konva stage, sharing the same content box** — Spike 1
already layers an absolute-positioned surface over the `<Stage>` and they align.
The recall animation does not need to know whether the marks beneath it are Konva
or SVG; it only needs the same `content` geometry, which is renderer-independent.
**So recall does NOT need porting to canvas** — this directly addresses the
"largest single risk" in OH §1.9. Caveat: if a mark's recall needs to read the
*Konva node's* animated path (rather than re-deriving from stored points), that
would couple them; keeping recall driven by stored `visual_mark` geometry avoids
it.

### Konva cost, measured
Lazy-loaded production chunk: **`KonvaInstrumentSpike` = 314 kB raw / 97.6 kB
gzip** (konva + react-konva + the spike). The equivalent **`SvgHandlesSpike` =
7.5 kB raw / 3.3 kB gzip**. Konva's delta over the existing hybrid is
**≈ +94 kB gzip.** Code-splitting keeps it off the main bundle, but a production
instrument layer that every curator loads pays it.

---

## 3. Spike 2 — the null hypothesis (SVG handles, zero new deps)

Screenshots: `02-svg-handles.jpg` (4 handles + midpoint hints on a selected gaze
trace) · `03-svg-handle-drag-reshape.jpg` (endpoint dragged; line reshaped).

**RESULT: the handles gap closes on the existing SVG overlay with no new
dependency. Confirmed live** — selected the gaze trace, dragged its endpoint from
`[0.40, 0.36]` to `[0.35, 0.51]`, watched the serialized `points` update and the
whole line reshape. Insert-midpoint (click the line) and delete-vertex
(right-click a handle) also work.

### LoC and where it got painful

- **The editing math is `handleEditing.js` = 202 non-blank lines, and Spike 1
  imports the identical module.** That reuse is the headline finding: **a scene
  graph does not save you from writing this file.** Konva supplies drag events;
  it does not supply "insert a vertex into segment 2 at parameter t, interpolating
  pressure" — that is Semant's, on either renderer.
- The SVG-specific new code over what production `GroundLayers` already draws is
  the pointer router + handle layer, ~70 lines. The rest of `SvgHandlesSpike.jsx`
  (mark drawing) **is the existing production approach.**
- **The one genuine ergonomic tax:** SVG hit-testing is on the visible stroke
  only (~2 px), which is unclickably thin. Konva ships `hitStrokeWidth` for
  exactly this. On SVG you add a fat **transparent companion path** per trace
  (one extra `<path stroke="transparent" strokeWidth="…">`). It is trivial, it is
  in the spike, and it is the whole of what Konva gives you "for free" here.
- **`destination-out` is unavailable** on the shared SVG surface, so erase is
  rendered as a hatched "removed" region driven by the `op:'sub'` data. This is
  arguably *more* honest (the removed area stays visible as an intention) but it
  is a real rendering difference to decide on deliberately, not a bug.

**Conclusion of the control experiment:** a few hundred lines — most of them the
renderer-independent `handleEditing.js` that Konva would need anyway — close the
handles gap. **Konva's remaining case cannot rest on "SVG can't do handles." It
must rest on something else** (see disposition §for what that "something else"
would have to be).

---

## 4. The no-renderer-object guarantee (contract §6) — mechanical, not aspirational

`serializeMark` is a **whitelist**: only keys named in the schema are copied, and
every copied value is walked by `assertPlainData`, which throws on any value whose
prototype is not `Object.prototype`/`null` (i.e. any class instance — a
`Konva.Line`, a `Fabric.Path`, an `SVGPathElement`, an `HTMLCanvasElement`), and
on any function/symbol/bigint/non-finite number.

Why a whitelist and not a blacklist: a Konva node survives naive
`JSON.parse(JSON.stringify(x))` as `{}` — silently emptied, not caught — so
structural cloning is not a sufficient guard. The tests attach a fake
`Konva`-shaped object to a mark under several field names and confirm none of its
fields (`attrs`, `_id`) can reach output. The serialization panel shows a green
"no renderer object" badge across all live interaction.

---

## 5. Spike 3 — perfect-freehand vs freehandTaper

Screenshot: `04-freehand-compare.jpg` (side-by-side ribbons + numbers table).
Pure points-in / polygon-out; **zero ontology risk** — mechanics, not truth.

Both fed points in **natural-pixel space** (the same `toPx` conversion
`GroundLayers` already does), because `perfect-freehand`'s `streamline`/`smoothing`
are distance-based and comparing in different unit systems would be meaningless.
`simulatePressure: false` is set deliberately — the corpus HAS pressure and a
generator that fabricates it would score well dishonestly.

**Measurements (two independent runs, consistent in direction):**

| metric (heavy = 1194-pt stroke) | freehandTaper | perfect-freehand | ratio |
|---|--:|--:|--:|
| output vertices (900×600) | 458 | 13 314 | **29× more (PF)** |
| output vertices (3024×4032) | 630 | 12 651 | 20× more (PF) |
| path string chars (900×600) | 8 703 | 199 711 | **23× bigger (PF)** |
| generation ms, median (900×600) | 0.30 | 2.00 | PF ~7× slower, both ≪ 16 ms |
| generation ms, median (3024×4032) | 0.54 | 0.60 | ~parity |
| pressure sensitivity px (900×600) | 0.8 | 14.3 | **PF ~18× more responsive** |
| pressure sensitivity px (3024×4032) | 2.6 | 52.3 | PF ~20× more responsive |

For a **short (6-pt) stroke** the picture inverts on size: PF = 26 vtx / 391
chars / ~0 ms; FT = 152 vtx / 2889 chars / 0.1 ms — PF is smaller and faster
there (FT's fixed resample step over-samples short strokes).

**Visual quality:** PF's heavy ribbon is visibly smoother and more organically
tapered, and it is *dramatically* more pressure-expressive (the numbers confirm
the eye). FT is flatter and barely modulates on pressure.

**Storage is UNAFFECTED either way** — both store input points and regenerate the
polygon at render, so PF's larger vertex count is a render/raster cost, not a
stored-record cost. See disposition for the verdict.

---

## 6. Pattern harvest (concrete, mapped to the contract; no source embedded)

- **Label Studio `parent_prediction` → `derived_from`.** Already in the contract;
  **the spike honours it** — `acceptSuggestion` mints a new `user_confirmed` mark
  whose `derived_from` is the suggestion's id, and the suggestion stays read-only.
  `user_confirmed` is thus a *derived fact* (has a parent), not a boolean — and the
  validator refuses a `user_confirmed` mark with no `derived_from` (no laundering).
- **CVAT → provenance must be VISIBLE.** The suggestion-mode rendering is the
  proof: the `suggestion` layer is a distinct, dashed, uncitable surface, and the
  "citable N/M" readout makes the quarantine countable. This is the explicit
  anti-CVAT requirement (a provenance field nobody can see is no provenance).
  *(Not built, noted for P2E: CVAT's foreground/background point prompts and its
  mask-preview→correct→commit loop are the right SAM UX shape — they map to
  `tool_proposal_result.previewable` + `confirmation.state`.)*
- **Annotorious (BSD-3) `bodies[]` / W3C target+selector** vs the contract's
  `anchor {kind, ref, at}`. Convergence worth borrowing: the anchor's `ref` is a
  *selector by identity* and `at` is a *cached resolved position* — the same
  target/selector split. **`syncAnchors` already makes the divergence visible**:
  dragging a `ground`-anchored endpoint sets `detached_from_ref:true` (ref kept,
  position updated) rather than silently moving the referent or keeping a stale
  `at`. P2E should consider adopting W3C selector vocabulary for `anchor.kind`.
- **Excalidraw (MIT) `version`/`versionNonce` + `isDeleted` tombstones** vs the
  contract's `superseded` status. The spike's `supersedeMark` keeps the old mark
  recoverable (`status:'superseded'`, new mark `derived_from` it) — this is the
  tombstone idea without a delete. **P2E should consider** a monotonic
  `version`/`updated_at` per mark for last-writer-wins conflict detection if marks
  ever sync across sessions; the slot is not in the OH §4 shape yet.

---

## 7. Contract friction notes for Lane A (P2E input, not a licence to diverge)

Signatures I wished were different while building against the OH §4 stub:

1. **`anchor` needs a first-class detachment field.** OH §4.3 gives
   `anchor {kind, ref, at}`. The moment you drag a ground-anchored endpoint you
   need to record "this `at` no longer agrees with `ref`". I added
   `detached_from_ref:bool`. Lane A should bless a name for it (or make `ref`
   nullable-on-detach) rather than leave each surface to invent one.
2. **`brush_field` erase belongs in geometry, not style.** I stored `op:'add'|'sub'`
   per stroke inside `geometry.freehand_path.strokes[]` (matching today's
   `fieldCanvas` stroke shape). The OH §4.2 shape lists `strokes[] {points, radius,
   strength, op}` — good — but the prose frames erase as a compositing detail;
   please keep `op` as **data** so it survives on renderers without
   `destination-out`.
3. **`visual_layer` wants an explicit `z`/`order` contract for the recall overlay.**
   Recall (an SVG overlay above the stage) is `order`-above everything but is a
   *system* layer. The current `order:int` + `layer_type:'recall'` works, but Lane
   A should state that the recall layer's `order` is derived (always top), not a
   stored curator decision, so it can't be dragged.
4. **`relationNodes` needs an injected resolver, like `groundRoleList(…, resolve)`.**
   I passed `centerOf(ref)`. Please keep resolution *injected* so the mark module
   stays free of store concerns (the OH §4.4 "derived, never stored" rule is only
   safe if the module can't reach the store directly).
5. Minor: `serializeMark` rounds coordinates to 4 dp at the serialization boundary
   (not on input), so a live drag stays smooth and the stored record stays small
   and diffable. If Lane A rounds on input instead, tapered strokes quantize.

None of these are divergences from the model — they are places the *signature*
needs one more field or one explicit sentence.

---

## 8. Risks & what production integration would require

| option | to put in production |
|---|---|
| **Konva** | +94 kB gzip on the instrument route; port 29 CSS rules → JS style objects; re-express 25 `vectorEffect` uses as `strokeScaleEnabled={false}`; keep recall as an SVG overlay (do NOT port to canvas); one `<Layer>`, groups for `visual_layer`; custom anchors (no `Transformer`). The `handleEditing.js` module ports **unchanged**. |
| **Extend current hybrid (SVG handles + perfect-freehand)** | add `handleEditing.js` (202 lines) + a fat transparent hit-path per trace + a handle layer to `GroundLayers`/a new overlay; adopt `perfect-freehand` for brush taper (swap `taperedRibbon`, or keep both behind the toggle). No renderer swap, no bundle hit beyond perfect-freehand (~5 kB gzip), recall untouched. |

Risks: (a) SVG hit-test ergonomics need the transparent-hit-path everywhere a thin
mark is editable — cheap but must be systematic; (b) perfect-freehand's larger
polygons raise per-frame raster cost during recall on the heaviest strokes —
measure on a real device before adopting for animated recall; (c) the `__spikes__`
contract stub will drift from Lane A's real `visualMarks.js` — reconcile at P2E
start (§7).

---

## 9. Disposition

See `Decisions/CIRCUIT-001-P2D-B-renderer-spike-disposition.md` for the single
verdict, argued against Spike 2's cost line and with the P2C §7 re-open table
updated.

**One-line preview:** EXTEND THE CURRENT HYBRID (SVG handles + perfect-freehand);
do not adopt Konva now — because Spike 2 closed the only gap Konva was named to
close, at ~3 kB instead of ~94 kB, without risking recall.
