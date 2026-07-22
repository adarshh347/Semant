# CIRCUIT-001 P2C — Which renderer should Semant's perceptual instruments be built on?

**DECISION DOC — NO IMPLEMENTATION. No source file was edited; no dependency was installed;
no production data was read or written. Nothing in `frontend/` or `backend/` changed in this
gate.** Rests on `CIRCUIT-001-P2C-OH-open-harvest-perceptual-instruments.md`, which carries the
evidence and is not re-derived here.

| | |
|---|---|
| **id** | CIRCUIT-001-P2C · rules on the question opened by P2B §9 ("deeper instrument bodies") |
| **date** | 2026-07-23 |
| **status** | **Decided.** |
| **decision, in one line** | **OPTION D — build Semant's own instrument data model now, renderer-independent; keep the existing SVG+canvas hybrid in production; name `react-konva` as the sole renderer candidate and test it in a one-day throwaway spike AFTER the model lands. Fabric.js is ruled out. No dependency is authorized by this document.** |
| **rests on** | `GroundLayers.jsx`, `fieldCanvas.js`, `useStageGeometry.js`, `RegionOverlay.jsx`, `useMaskRefine.js`, `grounds.js`, `regionStore.js` read in full this gate · a live corpus measurement (31 grounds / 16 posts) · primary-source research on konva 10.3.0, react-konva 19.2.5, fabric 7.4.0, CVAT, Label Studio |

---

## 1. The decision

**Adopt no renderer now. Build the ontology first.**

1. **Production stays on the existing hybrid** — canvas for soft fields, SVG for everything
   else, HTML for chrome, all slaved to `useStageGeometry`. It works, and it is already the
   hybrid the question was asking about.
2. **P2C builds `visual_mark` / `brush_field` / `trace_mark` / `relation_mark` /
   `visual_layer` / `tool_proposal_result`** as pure, fail-closed, node-tested modules — the
   part no library can supply.
3. **`react-konva` is the named candidate** for a later instrument layer, and the only one.
4. **A one-day throwaway spike** (report §6.4) decides it, on a branch, without touching
   `frontend/package.json` on the mainline.
5. **Fabric.js is ruled out** for Semant.

## 2. Why — the four findings that decided it

**2.1 Three of the four gaps are ontology, not rendering.** The matrix isolates four
weaknesses: layers-as-data, visibility/opacity/lock, semantic roles on marks, and editable
handles. **Only the last is a renderer capability.** Adopting a renderer would close one gap
and leave the three that matter — and those three must be built in Semant either way.

**2.2 The measured scale removes the usual reason to switch.** Across the live corpus:
**31 grounds over 16 posts, maximum 6 on any single post.** A scene graph earns its ~95 kB at
hundreds of interactive objects. Semant's actual load is a *handful of objects carrying dense
polylines* — a 1194-point stroke — which is rasterisation, and `fieldCanvas.js` already does it.

**2.3 Konva's own documentation prescribes this order.** It calls `Konva.Node.create()` *"an
anti-pattern"* with React and instructs users to *"save and load the data that defines our
shapes, then let the framework components handle rendering."* Building the Semant model first
is not deferral — **it is the prerequisite the candidate library itself names.**

**2.4 The migration cost is real and would be paid against the best-working hop.** 29 CSS
rules, 25 `vectorEffect` uses, and — decisively — **the entire recall choreography is SVG
`pathLength` + `strokeDashoffset`**. P0.5 §1.1 records recall as *the one hop the product
already does well*. **We do not put that at risk to gain resize handles.**

## 3. Why Fabric.js is ruled out

Three independent grounds, any one sufficient:

1. **No official React binding**; the documented pattern is imperative `useEffect` + `dispose()`
   with known StrictMode lifecycle bugs. The third-party `fabricjs-react` peer-declares
   `fabric ^5 || ^6` — **it does not declare v7**, which is current.
2. **The eraser is not in core** — it lives in third-party `@erase2d/fabric`, which
   peer-declares `>=6.0.0` with v7 unasserted. Semant's eraser already works
   (`destination-out`); adopting Fabric would move a working feature onto an out-of-core
   single-maintainer package.
3. **Fabric wants to own application state.** Its docs push `loadFromJSON` as *the* persistence
   model. That collides head-on with the rule that no renderer object is ever truth.

Fabric's one uncontested advantage is bidirectional SVG import/export. **Semant has no such
requirement**, and if one appears this decision should be re-opened.

## 4. What this decision does NOT authorize

- **No dependency.** Not konva, not react-konva, not fabric. Installing react-konva to evaluate
  react-konva pre-empts the decision it is meant to test.
- **No renderer swap**, no rewrite of `GroundLayers`, `RegionOverlay` or `fieldCanvas`.
- **No change to `useStageGeometry`, `freehandTaper`, `maskGeometry`, or normalized storage.**
  These are renderer-independent and correct.
- **No `run_id`, no packet dispatch, no Atlas/Codex, no persisted Mentions, no suspect
  detection, no LangChain.**
- **No reading of the tldraw source.** Its licence is proprietary — *"Not to use the Software in
  Production Environments"* without a paid key. Reading it and then writing similar code
  creates a derivation narrative that is expensive to rebut, and permissive alternatives (CVAT
  MIT, Label Studio Apache-2.0, Annotorious BSD-3) demonstrate the same architectures. **This
  gate did not read it and no later gate should.**

## 5. The binding constraint any later spike inherits

**`visual_layer` maps to a Konva `Group`, never to a Konva `Layer`.** Konva's own performance
documentation states: *"Do not create too many layers. Usually 3-5 is max"* — each `Layer` is a
real `<canvas>`. A naive one-layer-per-`visual_layer` mapping would be a silent architectural
mistake, and it is recorded here so a later gate cannot make it.

## 6. The counter-argument, stated fairly

**The strongest case against this decision:** deferring the renderer risks building a data model
in the abstract that then fights the renderer chosen later — the classic premature-abstraction
failure. `Transformer` mutating `scaleX`/`scaleY` rather than `width`/`height` is exactly the
kind of impedance mismatch that only shows up on contact.

**Why it does not overturn the decision:** the model is not being invented from nothing. Its
geometry kinds are *what Semant already stores* (`freehand_path` is today's field strokes,
`polyline` is today's path ground), and its provenance vocabulary is *what P2B already ships and
tests*. The abstraction risk is therefore low, and the specific mismatch named above is spike
test #3 — **the decision routes the counter-argument into an experiment rather than dismissing
it.**

## 7. What would re-open this

| signal | reconsider |
|---|---|
| P2C needs direct manipulation immediately (drag a trace endpoint, reshape a committed field) | bring the spike forward; Option B |
| grounds per post reach ~100+ in real use | Option B |
| SVG hit testing on grounds proves unworkable once `pointerEvents:none` is lifted | Option B |
| a hard SVG import/export requirement appears | re-open Fabric specifically |
| the spike shows recall choreography ports cleanly **and** `Transformer` respects normalized geometry | Option B — and this decision was too cautious |

## 8. The rule this decision serves

> **Open-source libraries provide mechanics. Semant provides meaning.**

The corollary this gate establishes, and which should outlive the renderer question:

> **When a gap can be closed by a library, that is an implementation choice. When it cannot,
> it is ontology, and it is ours. Build the ontology first — it is the part that cannot be
> bought, and it is the part every renderer will have to serve.**
