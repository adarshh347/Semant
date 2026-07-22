# CIRCUIT-001 P2C-OH — Open Harvest for Perceptual Instruments

**RESEARCH + ARCHITECTURE GATE. No production UX changed. No dependency installed. No
production data touched.** Rests on code read this gate (cited file:line) and on primary
library/product sources (cited URL).

> **The rule this gate serves:** open-source libraries provide mechanics; Semant provides
> meaning. Percepts, grounds, ground roles, packets, the Circulation Thread, recall, liquid
> constructs, provenance and the no-fake-causality rules are **not** outsourced, ever.

---

## 1. Semant's current instrument architecture — OBSERVED

### 1.1 The finding that reframes the question

**Semant is already a hybrid renderer, and has been since Differential v1.**

`GroundLayers.jsx:20` states it outright: *"Two layers slaved to the stage-geometry
contract"* — a `<canvas>` for Soft Field, an `<svg>` for everything else. Add the HTML layer
(labels, note dots, brush cursor) and there are **three renderers already coexisting** over
one image, correctly registered.

So the gate's question *"can current SVG/DOM overlays coexist with a canvas stage?"* has an
empirical answer: **they already do, in production, today.**

### 1.2 What renders where

| ground type | renderer | file |
|---|---|---|
| **field** (soft brush) | **canvas 2D** — radial-gradient stamps into an alpha buffer, `source-in` tint, rim shadow | `fieldCanvas.js:77` `paintFields` |
| path · boundary · frame · region · constellation · relation | **SVG** in natural-pixel `viewBox` | `GroundLayers.jsx:230-270` |
| region masks (the Field surface) | **SVG** `<path fill-rule=evenodd>` / `<polygon>` / `<rect>` | `RegionOverlay.jsx:69-83` |
| labels, note dots, brush cursor, recall captions | **HTML** absolutely positioned | `RegionSurface.jsx:403-421`, `DifferentialWorkspace.jsx:543` |

**The eraser already exists.** `fieldCanvas.js:37` — `globalCompositeOperation =
stroke.op === 'sub' ? 'destination-out' : 'source-over'`, driven by ⌥ at
`DifferentialWorkspace.jsx:210`. This is the same mechanism a canvas library would give us.

### 1.3 The coordinate contract — the most valuable asset here

`useStageGeometry.js` is the single sanctioned pointer↔image mapping, and it is
**renderer-independent**:

- `contentBox(sw, sh, nw, nh)` — where a `contain`-fitted image actually sits (`:23`)
- `pointerToNormalized(e, stageEl, content)` — the only sanctioned inbound converter (`:36`)
- `normalizedToStage(pt, content)` — outbound (`:46`)
- **All stored geometry is normalized `0..1` in natural-image space** (`:14`)

The file carries its own warning (`:17`): *"a surface that reimplements the letterbox math is
how 'the earrings land on a cheekbone' happens again."* That is a real historical bug
(`RegionOverlay.jsx:16` — `preserveAspectRatio="none"` drifted ~129px).

**Any renderer we adopt must consume this contract, not replace it.** A library that insists
on owning coordinates is disqualified on this basis alone.

### 1.4 Where marks are stored

Grounds live on the post document, written through a **separate** save path from regions:
`regionStore.js:185` `persistMeta` → `PATCH /posts/{id}` with `{grounds, percepts}`
(`:193`). Geometry is normalized; `hydrateGrounds` rehydrates on load (`:115`).

Ground shape (`grounds.js:37` `makeGround`):
```
{ id, ground_type, actor, detector, label, note, created_at, ...typeFields }
```
`makeGround` is documented as the single creation point *"so provenance is always stamped"*.

### 1.5 Is there a layer concept? — **No.**

Z-order is *implicit and structural*: the `<canvas>` element precedes the `<svg>` in the DOM
(`GroundLayers.jsx:221,230`), so fields always sit under everything else. Within the SVG,
order is array order.

**There is no per-mark visibility, opacity, lock, or reorder.** What exists instead is
*attention state* — `groundAlpha()` (`:27`) computes `{on, progress, dim, recalling, focused}`
from `focusGroundIds` / `recall` / `recallOnly`. That is a **narrowing** model, not a layer
model, and it is the right model for recall. **A layer model is a data-model gap, not a
renderer gap** — and this matters for the recommendation.

### 1.6 Hit testing — free today

SVG native. `RegionOverlay.jsx:63-65` puts `onClick` / `onMouseEnter` / `onMouseLeave`
directly on shape elements; `interactive={false}` sets `pointerEvents:'none'` (`:56`) so
refine gestures fall through to the stage. `GroundLayers` is `pointerEvents:'none'` entirely
(`:234`) — **ground marks are not currently clickable on the image at all**; they are selected
from the inspector list. That is a real gap.

### 1.7 SAM-assisted marking is ~70% built already

`useMaskRefine.js` is a complete propose→confirm loop, and it is the pattern CVAT is famous
for:

- **positive / negative point prompts** — `addPoint(x, y, label)`, `label` 1 or 0 (`:60`)
- **box prompt** — `setBoxPrompt` (`:61`)
- **debounced preview** — 110 ms (`:56`), with request sequencing so *"a newer prompt wins"* (`:45`)
- **preview never persists** (`:11`); `confirm` writes a new geometry revision (`:66`)
- **session release** frees SAM (`:80`)
- the proposal renders **through the same overlay**, dashed (`RegionOverlay.jsx:93`)
- backend marks `region["proposed"] = False` on confirm (`posts.py:1285`)

**The gap is not the loop. The gap is provenance and scope:**
1. it applies only to **region masks** — not to brush fields, traces or relations;
2. a confirmed refinement does **not** record that it was model-proposed and human-confirmed.
   `proposed` flips `true → false` and `actor` is untouched, so *"SAM proposed this and I
   accepted it"* is indistinguishable from *"I drew this"* the moment it is saved;
3. proposals render **inline** with committed marks (dashed), not on a quarantined layer.

### 1.8 The three provenance vocabularies — Semant's real inconsistency

| where | vocabulary | file |
|---|---|---|
| **Region** | `actor` (`creator`/`auto`) · `detector` · `proposed: bool` · `geometry_rev` | `posts.py`, `RegionOverlay.jsx:21` |
| **Ground** | `actor` · `detector` (no status at all) | `grounds.js:37` |
| **Perceptual Action** (P2B) | `source`: user / system / **model_suggested** / fixture / **user_confirmed** · `status`: proposed / previewed / applied / dismissed / blocked | `perceptualActions.js:56,62` |

**P2B's is the only one that can express "a model suggested this and a human accepted it."**
The other two cannot. Unifying on the P2B vocabulary — rather than inventing a fourth — is
the single most valuable thing this gate can specify.

### 1.9 What would break if a canvas engine were introduced

| breaks | scale | note |
|---|---|---|
| **CSS styling of marks** | **29 rules** across `DifferentialWorkspace.css` + `RegionSurface.css` | canvas has no CSS; every rule becomes a JS style object. **This is the real migration cost.** |
| **`vectorEffect="non-scaling-stroke"`** | **25 uses** across 5 components | hairlines that survive zoom; canvas needs manual `1/scale` stroke widths |
| **SVG filters** | `feGaussianBlur` for boundary veil (`GroundLayers.jsx:238`) | canvas needs `ctx.filter` (weaker support) or pre-blur |
| **`pathLength` + `strokeDasharray` recall animation** | path travel, boundary shimmer, relation unite | the whole recall choreography is SVG dash-offset. **Re-implementing this on canvas is the largest single risk in any migration.** |
| **DOM-queryable marks in tests** | current DOM tests query `.ap-card`, `.pw-card` etc. | canvas is one opaque node — component tests over marks become pixel or model assertions |
| **native hit testing** | `RegionOverlay.jsx:63` | replaced by library hit graph |
| **does NOT break** | `useStageGeometry`, normalized storage, `maskGeometry`, `freehandTaper`, `fieldCanvas`, grounds schema, all pure modules | renderer-independent by construction |

### 1.10 Actual scale — measured against the live corpus, this gate

```
posts with grounds: 16   |  total grounds: 31  |  max grounds on ONE post: 6
field strokes: 9         |  total points: 3175 |  longest single stroke: 1194 points
by type: frame 13 · region 14 · path 2 · field 2
```

**This is decisive and it points the opposite way from intuition.** The performance profile is
**not** "hundreds of objects needing a scene graph" — it is *a handful of objects carrying very
dense polylines*. Six objects per post is far below where a scene-graph library earns its
bundle; a 1194-point stroke is a rasterisation problem, and canvas already handles it
(`fieldCanvas.js` stamps along the polyline with spacing `0.3 × radius`).

**Zero drawing libraries are installed today** (28 runtime deps, none canvas-related).

---

## 2. The libraries — primary-source findings

### 2.1 Konva / react-konva

| | |
|---|---|
| versions | `konva@10.3.0` (2026-04-30) · `react-konva@19.2.5` (2026-06-09) |
| **React 19** | **First-class.** `react-konva@19.x` peer-declares `react ^19.2.0` / `react-dom ^19.2.0` — React 19 is *required*, not merely tolerated. The 19.x line tracks React's major. |
| health | konva 14.6k★ / **17 open issues**; **react-konva: 3 open issues total** |
| size | 54.0 kB + 40.6 kB gzip ≈ **94.6 kB** |
| downloads/wk | konva 2.08M · react-konva 1.64M |

**The React 19 worry is dead.** The teething bugs (`ReactCurrentOwner` undefined, refs crashing,
`reading 'S'`) are all Dec 2024–Oct 2025 and **closed**; `19.2.1` shipped React 19.2 fixes plus a
StrictMode stage-reordering fix. Caveats that remain: no React Native, SSR renders an empty div
(irrelevant — Vite SPA), and the GitHub licence classifier says `NOASSERTION` while npm says MIT
(**read `LICENSE` before adopting**).

**Three findings that directly shape Semant's design:**

1. **"Do not create too many layers. Usually 3-5 is max."** — official
   [Layer Management](https://konvajs.org/docs/performance/Layer_Management.html). Each Konva
   `Layer` is a real `<canvas>`. **So `visual_layer` must map to `Group`, never to Konva `Layer`.**
   This would have been a silent architectural mistake.
2. **Konva's own docs call `Konva.Node.create()` "an anti-pattern" with React**, and say to
   *"save and load the data that defines our shapes, then let the framework components handle
   rendering."* — [Simple Load](https://konvajs.org/docs/data_and_serialization/Simple_Load.html).
   **The library itself endorses §4 rule zero.**
3. **The eraser is `globalCompositeOperation: 'destination-out'`** —
   [Free Drawing](https://konvajs.org/docs/sandbox/Free_Drawing.html) — i.e. *exactly what
   `fieldCanvas.js:37` already does.* Konva would not give Semant an eraser it lacks.

Other mechanics: `Konva.Arrow` (`pointerLength`/`pointerWidth`) and `Line{tension}` splines are
first-class; `Transformer` gives resize/rotate handles but **mutates `scaleX`/`scaleY`, not
`width`/`height`** (a real gotcha for a normalized-geometry model); hit testing uses a hidden
per-layer colour-keyed canvas with documented escape hatches (`listening(false)`,
`perfectDrawEnabled(false)`, `cache()`); `getRelativePointerPosition()` inverts ancestor
transforms.

### 2.2 Fabric.js

| | |
|---|---|
| version | **7.4.0** (2026-05-18) — *the gate asked about v6; Fabric is on v7* |
| health | 31.3k★ but **467 open issues**; MIT |
| size | **91.9 kB** gzip |
| downloads/wk | 873k |

v7 requires Node ≥20 and **changed `originX`/`originY` defaults to `"center"`** — a live
migration hazard. Two recent CVEs, both in SVG handling (**CVE-2026-27013** stored XSS in SVG
export, **CVE-2026-44311**).

**Three disqualifiers for Semant specifically:**

1. **No official React binding.** The documented pattern is imperative `useRef` + `useEffect` +
   `dispose()`, with known StrictMode lifecycle bugs
   ([#8899](https://github.com/fabricjs/fabric.js/issues/8899)). The third-party
   `fabricjs-react` peer-declares `fabric ^5 || ^6` — **it does not declare v7.**
2. **The eraser is not in core.** It lives in third-party `@erase2d/fabric` (MIT, single
   maintainer), which peer-declares `>=6.0.0` — **v7 compatibility unasserted.** Semant's eraser
   already works; adopting Fabric would make it depend on an out-of-core package.
3. **Fabric wants to own state.** Its docs push `loadFromJSON` as *the* persistence model, and
   objects carry selection/lock/cache state. That is a direct collision with §4 rule zero.

**Fabric's one uncontested advantage is bidirectional SVG** (`loadSVGFromString` → Promise,
`toSVG()`). Semant has no SVG import/export requirement today.

### 2.3 The thing neither library provides

**Pressure and taper.** Neither documents pressure support. Semant already has
`freehandTaper.js` — `taperedRibbon`, `centerlinePath`, `endChevron`, a width profile easing from
a tail width through a head — **with its own test suite**. Adopting either library means keeping
that math and feeding it through a custom `sceneFunc`/`BaseBrush`. It is an asset, not a gap.

---

## 3. Comparison matrix

Legend: ● strong · ◐ workable · ○ weak/absent · ✱ *Semant already has this*

| capability | current DOM/SVG+canvas | Konva | Fabric | hybrid (both engines) | CVAT/LS (study only) |
|---|---|---|---|---|---|
| freehand brush | ✱ ● `fieldCanvas` stamping | ● `Line`+points | ● `PencilBrush` | ○ redundant | brush size/shape UX |
| **semantic brush fields** | ✱ ◐ geometry yes, **role no** | ○ *no such concept* | ○ *no such concept* | ○ | ○ — **Semant-native** |
| eraser | ✱ ● `destination-out` | ● same mechanism | ○ out-of-core pkg | ○ | eraser as peer *mode* |
| polygon / lasso | ◐ mask polys render; no draw tool | ● | ● | ◐ | polygon→mask commit |
| trace arrows | ◐ hand-rolled chevron | ● `Arrow` | ○ build from Path | ◐ | — |
| curved paths | ✱ ● taper ribbon | ● `Line{tension}` | ● | ◐ | — |
| relation lines | ✱ ● derived from centres | ◐ you derive | ◐ | ◐ | — |
| **layers (data)** | ○ **absent** | ◐ `Group` (**not** `Layer` — 3–5 cap) | ◐ per-object | ◐ | LS: predictions/annotations as sibling collections |
| visibility / opacity / lock | ○ absent | ● | ● | ● | LS auto-accept toggle |
| hit testing | ● SVG native, free | ● colour-keyed hit canvas | ● | ◐ two systems | hover-to-delete point |
| **coordinate mapping** | ✱ ● `useStageGeometry`, one contract | ◐ must bridge `getRelativePointerPosition` | ◐ must bridge | ○ **two mappings = the 129px bug again** | — |
| serialization | ✱ ● normalized, renderer-free | ◐ `toJSON` — *docs call it an anti-pattern in React* | ◐ `loadFromJSON` wants ownership | ○ | LS `parent_prediction` lineage |
| React state compat | ● full | ● declarative reconciler | ○ imperative, StrictMode bugs | ○ | — |
| performance risk | **● none at measured scale** (max 6 grounds/post) | ● headroom | ◐ single canvas redraw | ◐ | — |
| migration cost | — | **◐ 29 CSS rules + 25 `vectorEffect` + recall dash choreography** | ○ high — invert control | ○ highest | free |
| accessibility / testing | ● DOM-queryable | ○ one opaque node | ○ one opaque node | ◐ | — |
| **editable handles** | ○ **absent — the real gap** | ● `Transformer` (scale gotcha) | ● controls | ● | CVAT movable toolbar |
| future SAM integration | ✱ ● `useMaskRefine` propose→confirm | ◐ neutral | ◐ neutral | ◐ | **CVAT interactor + ±point prompts** |
| future Atlas/Codex fit | ● normalized, portable | ◐ if model stays ours | ○ if Fabric owns state | ○ | LS region-level lineage |

**Reading the matrix:** the ○s in the "current" column are **`layers`, `visibility/opacity/lock`,
and `editable handles`** — plus the half-mark on `semantic brush fields` (geometry exists, role
does not). Of those four, **only `editable handles` is a renderer capability.** The other three
are data-model gaps that a library cannot fill and that must be built in Semant regardless.

---

## 3.5 What CVAT and Label Studio actually teach

**Licences — all safe to learn from, one to avoid entirely.**

| | licence | risk |
|---|---|---|
| CVAT | **MIT** (core; `/serverless` model *weights* carry own, some non-commercial) | low — patterns and code both borrowable |
| Label Studio | **Apache 2.0**, no Commons Clause, explicit patent grant | low |
| Annotorious | BSD-3-Clause | low |
| **tldraw** | **PROPRIETARY** — *"Not to use the Software in Production Environments"* without a paid key | **HIGH — do not read the source** |

**On tldraw:** proprietary is in one way *worse* than copyleft here. GPL would at least permit
reading. Reading a proprietary codebase closely and then writing similar code creates a
derivation narrative that is expensive to rebut, and there is no licence permitting the result.
CVAT, Label Studio and Annotorious demonstrate comparable tool/layer architectures under
licences that affirmatively permit borrowing. **There is no reason to accept tldraw's risk, and
this gate did not read it.**

### 3.5.1 Label Studio — the single best idea in either tool

**Predictions and annotations are separate, sibling, differently-typed collections, and
predictions are immutable:** *"Predictions cannot be modified and are always read-only."* A
human correction **creates a new annotation pointing back at its source** via
`parent_prediction` (*"Points to the prediction from which this annotation was created"*); the
prediction survives untouched.

**Why this matters more than a flag:** it makes `user_confirmed` a **derived fact** — an
annotation whose `parent_prediction` is non-null — rather than a boolean somebody has to
remember to set. Semant's §1.7 gap is exactly a flag nobody remembered to set.

Two further ideas worth taking:
- **Model metadata lives on the proposal, not the object.** `model_version` and `score` are
  prediction fields. A confirmed record therefore does not inherit a confidence number that has
  stopped meaning anything. This independently confirms §4.7's refusal to put confidence on a mark.
- **Stable region ids survive the prediction→annotation copy**, giving *region-level* lineage on
  top of object-level lineage — so "what exactly did the human change?" is answerable.

### 3.5.2 CVAT — a negative lesson that is Semant's own risk

CVAT **has** a correct provenance enum — `SourceType: AUTO | SEMI_AUTO | MANUAL | FILE |
CONSENSUS` on every annotation. And it is **almost invisible**: `source` is *not* in the
documented filter properties, and issue
[#6261](https://github.com/cvat-ai/cvat/issues/6261) reports semi-auto "is not handled anywhere
in the CVAT UI", displaying as manual.

> **A provenance field nobody can see or filter on is, in practice, no provenance at all.**

That is precisely the failure Semant's evidence-honesty discipline exists to prevent, and
Semant is one gate away from repeating it: §1.8 found *three* provenance vocabularies, and the
richest one (P2B's) currently governs only action cards, not marks.

**Also do not copy:** CVAT's automatic annotation has **no proposal gate at all** — detector
output writes straight into the job behind a pre-hoc threshold. And its bulk shape conversion
is documented as *"cannot be undone"*.

**Worth harvesting from CVAT (interaction, not code):**
1. **Contextual, movable tool chrome** — the brush toolbar appears with the mode, shows
   brush-size only in brush/eraser mode, and can be dragged off the region being worked.
2. **Decouple gesture from inference** — hold `Ctrl` to place several point prompts and run
   inference *once* on release. Directly applicable to `useMaskRefine`'s 110 ms debounce.
3. **Left click = positive, right click = negative**, one gesture vocabulary, no mode switch.
4. **Explicit commit, plus "save and continue"** — in-progress is a real state distinct from
   committed.
5. **Hover-to-delete a placed prompt point.**

### 3.5.3 Annotorious — one structural idea

Its data model attaches **`bodies[]`** — a plural, open-ended array — to one target geometry,
each body carrying `purpose`, `creator`, `created`, `updatedBy`. *Multiple independently
attributed interpretations over one region.* That is closer to "many percepts over one ground"
than Label Studio's flat `result` array, and it separates geometry from semantics explicitly:
*"Annotorious does not process or display body information directly."*

## 4. The Semant-native instrument model

**Rule zero: no renderer object is ever truth.** A Konva `Line` or a Fabric `Path` is a
*view* of a `visual_mark`. Serialising a library's scene graph into the post would make the
library's version an upgrade hazard and its schema our ontology — the exact inversion this
gate exists to prevent.

**Rule one: reuse the P2B vocabulary, do not invent a fourth.** §1.8 found three partial
provenance vocabularies. `source` and `status` below are **the same values**
`perceptualActions.js` already defines and tests.

### 4.1 `visual_mark` — the common shape

```
visual_mark {
  id                 vm_<base36>            // minted like groundId(), monotonic tail
  type               brush_field | trace_mark | relation_mark | region_ref | frame_ref
  role               the family's role key  (field_role | trace_role | relation_role)
  label              curator-facing, editable, may be empty
  source             user | system | model_suggested | user_confirmed | model_refined | fixture
  status             draft | staged | committed | dismissed | superseded
  geometry           { kind, ...normalized 0..1 natural-image coords }
  style              { color, opacity, softness, width }   // suggestion, not authority
  linked_ground_ids  []     // a committed mark BECOMES/answers to a ground
  linked_percept_ids []
  linked_action_ids  []     // the P2B action that proposed or armed it
  provenance         { planner, prompt_excerpt, matched[], model, run_id: null }
  created_at / updated_at
}
```

**Why `status` has five values and not two.** `draft` is being drawn right now; `staged` is
drawn but uncommitted (the P2B *armed* state made durable); `committed` is real evidence;
`dismissed` is refused; **`superseded` is the one that earns its place** — when a mark is
replaced by a refinement, the old one must be recoverable, because P1F/P1G established that
silent replacement is precisely how a citation re-points without anyone noticing.

**`source` distinguishes three things the current code cannot:**
- `model_suggested` — proposed, not accepted. **Must never render as committed evidence.**
- `user_confirmed` — a model proposed it, a human accepted it. *Different from `user`.*
- `model_refined` — a human drew it, a model tightened it, a human kept the result.

**`run_id: null` is deliberate.** P1E left run identity under-specified and P1G found the
stored `run_id` field is literally `None`. The slot exists; it stays null until that is
settled. **No causal link is claimed.**

### 4.2 `brush_field`

```
brush_field extends visual_mark {
  type: 'brush_field'
  field_role   light_field | shadow_field | atmosphere_field | material_field |
               pressure_zone | gaze_field | negative_space | threshold | fold |
               rhythm | background_recession | external_limit
  geometry     kind: freehand_path | polygon | soft_mask | raster_mask | unresolved
               freehand_path → strokes[] { points[[x,y,pressure]], radius, strength, op }
               soft_mask     → the existing field ground, unchanged
               raster_mask   → mask_ref only; never inline pixels
  style        { softness 0..1, opacity ≤ 0.32 (the wash ceiling), color }
  suggested_by action_id | null
  confirmed_by 'user' | null
  mask_ref     { region_id, geometry_rev } | null     // SAM-assisted, later
}
```

`freehand_path` **is what `fieldCanvas.js` already stores** — the twelve `field_role` values
are P2B's, and the geometry is today's. This is a relabelling of existing data plus a role,
not a new store.

**`unresolved` is required**, not a placeholder: a planner proposes a light field before any
geometry exists. A model that cannot express *"this role, no geometry yet"* forces either a
fake shape or a dropped proposal.

### 4.3 `trace_mark`

```
trace_mark extends visual_mark {
  type: 'trace_mark'
  trace_role   gaze_address | gesture | fall_of_light | architectural_axis |
               movement | implied_address | comparison_path | force_direction
  geometry     kind: vector | curve | polyline
               vector   → { from:[x,y], to:[x,y] }
               curve    → { points[], tension }
               polyline → { points[] }              // today's `path` ground
  anchors      { from: anchor|null, to: anchor|null }
               anchor = { kind: 'point'|'ground'|'region'|'percept', ref, at:[x,y] }
  arrow        { head: none|chevron|open, at: end|both }
  ambiguous    bool     // the curator could not say exactly where it lands
}
```

**`ambiguous` is the honesty field.** A gaze often has no determinate terminus. Without it the
UI forces a false precision — an arrow with a sharp end asserting a target the curator never
claimed. It is the mark-level equivalent of the Circulation Thread's *absent ≠ none*.

**Anchors carry a `ref`,** so a trace from one ground to another survives the ground moving —
and, when the ref stops resolving, degrades exactly as `resolveGround` already degrades.

### 4.4 `relation_mark`

```
relation_mark extends visual_mark {
  type: 'relation_mark'
  relation_role similarity | contrast | kinship | motif_echo | support |
                tension | contradiction | temporal_suggestion | address_relation
  source_refs   [{ kind, ref }]
  target_refs   [{ kind, ref }]
  label / reason
  geometry      kind: 'derived'   // drawn from its refs' centres; never stored
}
```

**Its geometry is derived, never stored.** `GroundLayers.jsx:108` `compositionNodes` already
computes relation geometry from member centres at render time. Storing a connector line would
create a second truth that goes stale the moment a member moves — the same failure as a
durable `detached` flag.

`contradiction` and `tension` are the load-bearing entries, for the reason the P1 addendum
gives about `counterforce`: **a reading whose contradictions are structurally attached to it
cannot be immunised by restating the claim at a higher altitude** (spark-10).

### 4.5 `visual_layer`

```
visual_layer {
  id, name
  layer_type   evidence | suggestion | recall | scratch
  visibility   bool
  opacity      0..1
  locked       bool
  order        int
  mark_ids     []
  provenance   { created_by: 'system'|'user', action_id? }
}
```

**Four layer types, and `suggestion` is the point.** Model proposals land on a `suggestion`
layer that is *visibly distinct and never committed*. That is Gate 5G, and it is the single
most important structural borrowing from CVAT/Label Studio.

**`recall` is a system layer, not a user one** — it is transient performance, and it must not
be lockable, reorderable or savable.

Today's implicit z-order (canvas under SVG) becomes `order`; today's `groundAlpha` narrowing
stays **separate** from `opacity`. *Attention narrowing and layer opacity are different
things and must not collapse into one number* — the first is transient and derived, the second
is a stored curator decision.

### 4.6 `tool_proposal_result`

Bridges the planner to the instruments; a direct extension of P2B's `actionCanApplyNow`.

```
tool_proposal_result {
  action_id
  proposed_marks  [ partial visual_mark ]   // role + label + style, geometry usually unresolved
  previewable     bool
  applicable      bool
  blocked_reason  string | null   // REQUIRED when !applicable — the "preview only" copy
  confirmation    { required: bool, state: pending|confirmed|refused }
}
```

`blocked_reason` is required rather than optional **because P2B's rule is that a UI must never
silently no-op**. Making the field mandatory means a blocked proposal cannot be rendered
without saying why.

### 4.7 What is deliberately NOT in this model

- **No `run_id` causal link.** The slot is null.
- **No stored biography.** Derivable or not at all (P1 addendum §1.2).
- **No liquid-construct classification.** A mark is never *tagged* `address`; a `gaze_address`
  trace_role is an instrument, not a claim that the image *has* address.
- **No renderer objects.** No Konva/Fabric JSON anywhere.
- **No confidence score on a mark.** Semant has no calibrated source for one, and an
  uncalibrated number rendered next to evidence is worse than none.

---

## 5. Instrument workflows

### A. Manual semantic brushing
Brush (B) → *(new)* a role picker appears in the working area, defaulting to the last used →
paint → `status: draft` while the pointer is down → release makes it `staged` with a
`brush_field` mark, `source: 'user'`, geometry `freehand_path` → the curator names it or
accepts the role's default label → **Keep** commits it to a ground and opens the composer.
**Today** steps 1, 3 and the commit exist; the role picker and the staged-mark identity do not.

### B. Prompt-led brush *(P2B, shipped)*
*"left-side illumination"* → card `brush_field:light_field`, colour swatch, `where: left` →
**Arm this** → Brush arms, `stagedMark` holds role+label → curator draws → `commitDraft`
carries the label onto the ground.
**Gap:** `stagedMark` is component state, not a `visual_mark`; the `field_role` and the
originating `action_id` are dropped at commit. Only `label` survives.

### C. SAM-assisted brush / refine
Rough brush, box, or click → `useMaskRefine` preview (debounced, non-persisting) → proposal
lands on the **suggestion layer** as `source: 'model_suggested'`, `status: 'staged'` → curator
**accepts / edits / rejects** → accepted becomes `source: 'user_confirmed'` (edited →
`model_refined`), moves to the evidence layer, `status: 'committed'`.
**Today** the loop exists for region masks only, and acceptance erases the model's part in it
(§1.7). **The fix is provenance, not plumbing.**

### D. Trace as address
Planner or curator proposes `gaze_address` → Trace arms → curator anchors start, then end →
if they decline the end anchor, the mark is kept with `ambiguous: true` and an open head
rather than a chevron → committed, linkable to a percept.
**Today** trace draws a polyline with no anchors, no roles, and no ambiguity.

### E. Connect as relation
Select two or more marks/grounds/percepts → choose a `relation_role` → a derived connector
appears → the relation is available to `compose_percept` as a cited ground.
**Today** Connect exists over grounds with a free-text `relation_label`; the nine roles and
percept-as-endpoint do not.

### F. Manuscript recall over instruments
A percept chip recalls **every kind** of linked mark — fields bloom, traces travel, relations
unite — not only segmentation regions.
**Today** `GroundLayers` already does per-type recall choreography for all seven ground types,
and `RegionSurface` mounts it `recallOnly`. **This workflow is essentially built**; it inherits
new mark types for free provided they become grounds.

### G. Model suggestion quarantine *(the load-bearing one)*
Every model output lands on the `suggestion` layer: visibly distinct (dashed / reduced
opacity), **never counted in evidence totals, never citable by a percept, never
recallable**, and dismissible without trace. Only acceptance moves a mark to `evidence` with
`source: 'user_confirmed'`.
**Today** a refine proposal renders dashed inline — the visual half exists, the structural half
does not. A proposal is not a separate layer, and nothing prevents it being counted.

---

## 6. Architecture recommendation

### **Option D — Semant data abstraction now; renderer spike next, with react-konva as the named candidate.**

**Not A** (stay and do nothing) — the layer/provenance gaps are real and blocking.
**Not B yet** (adopt react-konva now) — see §6.2.
**Not C** (Fabric) — ruled out on three independent grounds (§2.2).
**Not E** (defer) — deferring the *data model* would be the expensive mistake.

### 6.1 Why

**1. The gaps are not renderer gaps.** §3 isolates four weaknesses. Three of them — layers as
data, visibility/opacity/lock, and semantic roles on marks — **no library supplies**, because
they are ontology. Only *editable handles* is a renderer capability. **Adopting a renderer would
close one of four gaps and leave the three that matter.**

**2. The measured scale removes the usual reason to switch.** Max **6 grounds on any post**;
31 grounds across the whole corpus. A scene graph earns ~95 kB gzip at hundreds of interactive
objects. Semant's real load is *dense polylines* (a 1194-point stroke), which is a
rasterisation problem canvas already solves in `fieldCanvas.js`.

**3. Semant's coordinate contract and taper math are assets neither library replaces.**
`useStageGeometry` is the single sanctioned mapping and carries the scar of a real 129 px
alignment bug; `freehandTaper` does pressure/taper that **neither Konva nor Fabric documents**.
Both survive any renderer — and both would have to be *bridged*, not adopted, either way.

**4. Konva's own documentation endorses the abstraction-first order.** It calls
`Konva.Node.create()` an anti-pattern in React and says to keep the shape-defining data in app
state. Doing §4 first is not deferral — **it is the prerequisite the library itself names.**

**5. The renderer decision is cheap to keep open, and getting cheaper.** react-konva is
React-19-first with 3 open issues. There is no deprecation clock forcing a decision now.

**6. The migration cost is real and currently unfunded.** 29 CSS rules, 25 `vectorEffect`
uses, and — the big one — **the entire recall choreography is SVG `pathLength` +
`strokeDashoffset`**: path travel, boundary shimmer, relation unite. Re-implementing that on
canvas is the largest single risk in any migration, and recall is the one hop P0.5 says the
product already does well. **Do not put the best-working part of the circuit at risk to gain
resize handles.**

### 6.2 What this means concretely

**Build now (P2C, renderer-independent):**
- `visual_mark` / `brush_field` / `trace_mark` / `relation_mark` / `visual_layer` /
  `tool_proposal_result` as pure modules with validators, in the style of
  `perceptualActions.js` — fail closed, node-tested.
- **Unify provenance on the P2B vocabulary** (§1.8) and adopt Label Studio's lineage idea:
  `derived_from: { mark_id | proposal_id }` so `user_confirmed` is **derived, not flagged**.
- **The `suggestion` layer** — quarantine, per §5G. Model output never counts as evidence.
- Carry `field_role` / `trace_role` and the originating `action_id` through `commitDraft`,
  closing the P2B gap where only `label` survives.

**Spike next (P2C-S, throwaway):** react-konva, behind an adapter, testing the one thing SVG
lacks.

**Do not touch:** `useStageGeometry`, `freehandTaper`, `fieldCanvas`, `maskGeometry`, normalized
storage. These are renderer-independent and correct.

### 6.3 What would prove this wrong

| signal | what it would mean |
|---|---|
| P2C's instruments need **direct manipulation immediately** — drag a trace endpoint, reshape a committed field, transform a mark | the "editable handles" gap is urgent, not deferrable → bring the spike forward |
| ground count per post reaches **~100+** in real use | scene-graph + hit-graph escape hatches start earning their bundle |
| SVG **hit testing on grounds** proves unworkable once `pointerEvents:none` is lifted (§1.6) | Konva's colour-keyed hit canvas becomes the cheaper path |
| a hard requirement for **SVG import/export** appears | re-open Fabric, which is uncontested on that axis |
| re-implementing recall on canvas turns out **trivial** in the spike | the largest migration risk evaporates and B becomes attractive |

**The honest disconfirmer:** if the spike shows the SVG dash-offset recall choreography ports
to Konva cleanly *and* `Transformer` handles normalized geometry without fighting
`scaleX`/`scaleY`, then Option B is right and this recommendation was too cautious.

### 6.4 The smallest spike that tests it

**Do NOT install react-konva into `frontend/package.json` on this branch.** Installing the
dependency is itself the decision this gate defers.

Run it on a **throwaway branch**, on a route not linked from the product:

| # | test | pass condition |
|---|---|---|
| 1 | **coordinate parity** — render 3 known grounds via Konva, fed by `useStageGeometry`'s `content` box | marks land within 1px of the SVG rendering at 3 stage sizes and 2 aspect ratios |
| 2 | **one brush field** — a `freehand_path` through `freehandTaper` via a custom `sceneFunc` | taper matches `taperedRibbon` visually; no pressure data lost |
| 3 | **one trace arrow with a draggable endpoint** — `Arrow` + `Transformer`/drag anchor | dragging updates **normalized** geometry, not `scaleX` — *this is the gate's real question* |
| 4 | **recall animation** — path travel via dash offset equivalent | reproduces the SVG choreography, or names precisely what is lost |
| 5 | **layer visibility toggle** — `visual_layer` → Konva **`Group`** (never `Layer`) | 4 layers toggle without a second canvas |
| 6 | **serialize back to `visual_mark`** | round-trips with **no Konva object stored** |

**Time-box: one day.** If #3 or #4 fails, Option A stands and the answer is "SVG + a hand-rolled
handle layer".

---

## 7. Spike status — **PLANNED, NOT EXECUTED**

**No spike code was written and no dependency was installed in this gate.** The reasoning is
stated rather than hidden: installing react-konva to evaluate react-konva pre-empts the decision,
and this gate's remit is docs/specs with production UX untouched. §6.4 is the executable plan.

---

## 8. Risks

| risk | severity | mitigation |
|---|---|---|
| **Semant repeats CVAT's mistake** — a provenance model that exists in data and is invisible in the UI | **high** | make `source` *renderable and filterable* in P2C, not just storable; §3.5.2 |
| the data model is built and the renderer never follows, leaving editable handles unbuilt | medium | §6.3's first row is the trigger; revisit at P2C exit |
| `visual_layer` naively mapped to Konva `Layer` in a later spike | medium | §2.1 finding: map to **`Group`**; Konva caps real layers at 3–5 |
| `Transformer`'s `scaleX/scaleY` semantics corrupt normalized geometry | medium | spike test #3 is exactly this |
| recall choreography degrades in any canvas migration | **high** | spike test #4; do not migrate recall before it passes |
| Konva licence ambiguity (`NOASSERTION` on GitHub vs MIT on npm) | low | read `LICENSE` before any adoption |
| adding `status`/`source` to grounds breaks stored data | medium | additive only, with a hydration default — `hydrateGrounds` already exists as the seam |
| the model grows into a stored biography | medium | §4.7 forbids it; derivable or not at all |

---

## 9. Next build gate

**CIRCUIT-001 P2C — Instrument model + suggestion quarantine (renderer-independent).**

1. `differential/visualMarks.js` — the §4 schemas, validators, fail-closed, node-tested, in
   `perceptualActions.js` style.
2. **Provenance unification** — one vocabulary across region / ground / action / mark, with
   `derived_from` lineage so `user_confirmed` is derived (§3.5.1).
3. **The `suggestion` layer** — model output quarantined, uncountable, uncitable, unrecallable
   until accepted (§5G).
4. **Carry role + `action_id` through `commitDraft`** — closes the P2B gap.
5. **Make provenance visible** — the anti-CVAT requirement.

**Then P2C-S:** the §6.4 spike, on a throwaway branch, time-boxed to a day.

**Explicitly not in P2C:** no renderer swap · no dependency · no packet dispatch · no `run_id` ·
no Atlas/Codex · no persisted Mentions · no suspect detection · no LangChain.
