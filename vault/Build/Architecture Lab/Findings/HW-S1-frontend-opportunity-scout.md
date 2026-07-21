# HW-S1 · Frontend opportunity scout

**READ-ONLY SCOUT REPORT. Research only. Nothing here is approved for build.**
No frontend or backend source was edited, no build was run, no data mutated. Every
"EXISTS" claim below is grounded in a file:line I actually read; every "PROPOSED" item is
speculative and unapproved. Where I could not find something, I say so rather than invent it.

---

## 0. What the frontend actually is right now

Routes (`frontend/src/main.jsx:31-91`): `/` Landing, `/home` bento, `/gallery`,
`/posts/:postId` (Chiasm + Differential), `/read/:postId` (Aletheia hook), `/feed`,
`/epics`, `/research`, `/personas`, `/unconceal`, `/anatomy`, plus three labs
(`/lab/region-surface`, `/lab/refine`, `/lab/blocknote`, `/lab/manuscript`) and two
`PlaceholderPage` stubs (`/atelier`, `/you`).

The circulation intelligence built in CIRCULATION-SPINE-001 touches **exactly one component**.

```
grep -rn "VisionActivityRail" frontend/src
→ differential/VisionActivityRail.jsx  (the component)
→ differential/DifferentialWorkspace.jsx:14, :821  (the only mount)
```

`grep -rn "run_id\|runId" frontend/src` returns **no production consumer at all** — only
`differential/visionActivity.test.js` and `services/researchService.js:21` (a *different*,
unrelated research-agent run API). No surface in the app displays a `run_id`.

`grep -rn "detached" frontend/src` returns the pure model (`differential/grounds.js:68-85`),
its tests, and **one** render site: `differential/DifferentialWorkspace.jsx:803-812`.

That is the shape of the whole opportunity: a rich, honest, well-tested epistemic substrate
exists, and it is visible in one collapsed drawer inside one workspace mode.

---

## 1. Which surfaces are static/dull relative to the new circulation intelligence

### 1.1 The Home bento calls detector output "percepts" — EXISTS, and it is the sharpest finding

`frontend/src/components/home/homeData.js:44-50`:

```js
export function percepts(post) {
  return Array.isArray(post?.region_annotations) ? post.region_annotations : [];
}
export function perceptCount(post) { return percepts(post).length; }
```

- `PerceptsTile.jsx:22` iterates `percepts(post)` and renders each region crop under the
  eyebrow **"Parts you recently noticed"** (`PerceptsTile.jsx:36`), labelled by
  `perceptLabel` = `region.label` (`homeData.js:52-55`).
- `WeekTile.jsx:23,28` sums the same array and prints it as **"percepts"** marked this week.
- `ContinueTile.jsx:78` → `progressLine` (`homeData.js:70-77`) prints `"N percepts · M words"`.

Two consequences, both grounded:

1. **The R2 label-collapse finding lands directly on the home page.** A sculpture whose 7
   regions are all labelled `wall`/`floor` and a painting with `dress`/`scarf`/`tie knot`
   become plum ◈ chips under "Parts you recently noticed". Home presents unreviewed detector
   guesses as the curator's own noticing, with no provenance mark of any kind.
2. **Real percepts are invisible on Home.** `homeData.js` never reads `post.percepts` or
   `post.grounds`. Expression percepts (`pctx_…`, `state/perceptMentions.js:59-78`) and
   Grounds — the things the curator actually composed in Differential — do not appear
   anywhere on `/home`. The tile named "Percepts" is the only one that *cannot* show a percept.

### 1.2 The Vision Activity Rail is real but structurally quiet — EXISTS

The rail is honest and unusually well-built: absence vs unreadability is discriminated
(`visionActivity.js:47-63`, `:215-240`), causal wording is forbidden and tested
(`:164-171`), raw errors are scrubbed and hidden behind a disclosure
(`:151-161`, `VisionActivityRail.jsx:91-96`), and polling is bounded to active runs only
(`useVisionActivity.js:11, :54-61`). But:

- it starts **collapsed** (`VisionActivityRail.jsx:102`);
- it renders at the **bottom of the Differential inspector**, below the counts footer
  (`DifferentialWorkspace.jsx:814-829`), i.e. below Grounds, Percepts and Detached lists;
- its closed-state summary is a pure count — `"N recorded"` / `"nothing recorded yet"`
  (`VisionActivityRail.jsx:124-133`). A run that is `partial`, `timed_out` or `stale`
  contributes to `recordedCount` and is indistinguishable from a clean success until you open it.

Given only one `vision_runs` document exists corpus-wide, in practice this rail says
"nothing recorded yet" almost everywhere — and that fact is itself invisible outside the drawer.

### 1.3 `run_id` is produced by the backend and thrown away by the client — EXISTS

`backend/routers/posts.py` (dissect route, ~:873) returns
`{"regions": …, "source": …, "run_id": rec.run_id}`. The client:

```js
// frontend/src/components/RegionSurface.jsx:180-181
const data = await res.json();
const next = data.regions || [];
```

`run_id` is discarded at `RegionSurface.jsx:181`. The user dissects an image, a run record is
minted, and the UI shows only `"Dissecting the image…"` (`RegionSurface.jsx:363-367`) then
polygons. There is no thread from the act to its record.

### 1.4 Region rows carry no provenance at all — EXISTS

`RegionSurface.jsx:469-497` renders each part as: star toggle, `regionName(r)`, an optional
lens reading, an optional note. Not rendered anywhere: `actor`, `detector`, `confidence`,
`geometry_rev`, `depth`, `parent_id`. The *only* provenance signal in the whole region UI is a
CSS class: `RegionOverlay.jsx:21` `if (r.actor === 'creator') cls.push('rs-shape--creator')`.

So a `wall` label hallucinated by an out-of-domain segmenter and a part the curator drew by
hand (`RegionSurface.jsx:214-223`) present identically in the list. Meanwhile the *neighbouring*
panels already do this well — `FindSimilar.jsx:49-52` shows space + model per result and
`:123-124` carries an explicit "not meanings" disclaimer; `SemanticReading.jsx:141-144` renders
a confidence bar per assertion. The region list is the outlier.

### 1.5 The Manuscript's AI slash items are dead stubs — EXISTS

`Manuscript.jsx:77-97` defines `AI_STUB` ("wires in Phase 4") whose `onItemClick` merely
inserts an empty `origin: 'sutradhar'` paragraph. Meanwhile `PostDetailPage.jsx:714-720`
constructs `onAiCommand` / `onRefCommand` callbacks — and the actual mount
(`PostDetailPage.jsx:1167-1173`) passes only `ref`, `initialBlocks`, `onChange`, `store`,
`onRefTrigger`. **`onAiCommand` and `onRefCommand` are dead code**; `runAiSlashCommand`
(`PostDetailPage.jsx:606-619`) is unreachable from the BlockNote editor.

### 1.6 Landing is a static mock — EXISTS

`LandingPage.jsx:50-54` hard-codes `HERO_REGIONS` as three CSS-percentage boxes with the
labels "the neckline" / "the drape" / "the patterned hem". Nothing on `/` touches live data.
That is a legitimate editorial choice for a marketing page; I note it only so it is not
mistaken for a surface with circulation potential.

### 1.7 The Aletheia / read-deeper surface has the *same* detachment bug, unannounced — EXISTS

`AletheiaHook.jsx:105-106`:

```js
const cited = new Set(lens?.region_ids || []);
const regions = (post.region_annotations || []).filter(r => cited.has(r.id));
```

If a re-dissect replaced the regions a lens cites — precisely the R2 mechanism that detached
`pctx_mrqp950d_0` — this filter yields `[]`. The `<svg>` at `:115-131` then renders zero
tappable shapes, and the hint at `:160-165` (`regions.length > 0 &&`) simply never appears.
The audience sees a confident reading paragraph (`:143`) over an image with nothing to tap,
and is told nothing. This is a **lens-level detachment** with no model support — `resolveGround`
has no analogue for lenses, and nothing computes it.

`RefPicker.jsx:53-64` has the mirror problem in the creator's UI: a lens row's badge is
`${l.region_ids.length} parts` — an unchecked count of possibly-dead ids.

---

## 2. Where run_id / stages / traces / candidates / DETACHED EVIDENCE / recall could become visible

All PROPOSED, all speculative.

### 2.1 Detached evidence — the highest-value, lowest-cost gap

**What exists.** Detachment is modelled (`grounds.js:68-85`), rendering degrades correctly
(`GroundLayers.jsx:164-166`: `if (!region) return null`), and one inspector list names it
(`DifferentialWorkspace.jsx:803-812`).

**Where it is silently swallowed today, with the exact call chain:**

1. **Recall never checks.** `recall.js:27-66` `buildRecallScript` resolves ground ids via
   `store.groundById` (`regionStore.js:214-216`) — a raw array lookup that returns the Ground
   record, *not* `resolveGround`. A detached region-ground is therefore a full step in the
   script (`recall.js:48-59`). At playback, `GroundLayers.jsx:248-250` resolves it, gets
   `region: null`, and `RegionGround` returns `null` (`:166`).
   **Net effect:** the image recedes (`recall.js:46`, CSS `is-recalling`), nothing at all is
   drawn, and then the expression caption appears (`recall.js:117-123`). The curator watches
   an animation assert a noticing over *no visible evidence*, with no message.
2. **The Manuscript chip is the trigger.** `PostDetailPage.jsx:771-787` — a click on any
   `[data-percept-id^="pctx_"]` chip expands the Field pane and calls `playRecall`; the same
   path exists for keyboard/focus at `:117-129`. `RegionSurface.jsx:320-332` mounts
   `GroundLayers … recallOnly`, so at rest nothing shows and during a detached recall
   *still* nothing shows. `pctx_mrqp950d_0` ("the upper head") would replay as a caption over
   an empty image.
3. **The picker offers it without warning.** `RefPicker.jsx:39-51` builds percept rows whose
   badge is `${p.ground_ids.length} grounds` and whose sub-line lists ground *types*. It
   already receives the `grounds` array as a prop (`RefPicker.jsx:26`) — but it never receives
   `regions`, so it *cannot* currently resolve region-grounds. A fully detached percept is
   offered as "2 grounds" with no hint that neither resolves.
4. **The chip markup has no slot for it.** `regionRefInline.jsx:43-57` `chipAttrs` emits
   `data-region-ids`, `data-percept-id`, `data-mention-id`, `data-label`. Nothing encodes
   evidence state, so neither the live chip (`:62-88`) nor the read-view chips painted at
   `PostDetailPage.jsx:818-829` can style a detached citation.

**Proposed loci, in priority order:**

- `differential/recall.js` — `buildRecallScript` takes a resolver; give it the *resolving*
  one and let the script carry `{ resolvable: n, total: m }`; a zero-resolvable script should
  refuse to perform and say why. This is the single highest-truth change available.
- `components/RefPicker.jsx` — pass `regions` in (`PostDetailPage.jsx:938-950` already has
  them) and degrade the badge to "1 of 2 grounds resolve" / "unevidenced".
- `components/blocknote/regionRefInline.jsx` — a derived class (not a stored attr) on the
  editor chip when `store` shows the percept unevidenced.
- `differential/DifferentialWorkspace.jsx:788-801` — the Percepts list is where the ▶ replay
  button lives; that button should not offer to replay nothing.
- `components/AletheiaHook.jsx:105-106` — the audience analogue; needs a lens-resolution
  concept that does not yet exist.

### 2.2 `run_id` and the dissect trace

- `RegionSurface.jsx:180-190` already receives `run_id` and `source`. The natural home for a
  provenance stamp is the `rs-maps` strip (`:372-383`) which already carries "12/40 parts · 3★" —
  a quiet append of "· from run …7f2, 4 min ago" costs nothing and creates the first thread
  from an act to its record.
- The Rail already knows how to turn a run into human stages (`visionActivity.js:89-127`,
  `deriveEntry` at `:212-279`); the `dissect.*` vocabulary is fully mapped (`:90-103`).
  Nothing renders it outside Differential because nothing *mounts* it outside Differential.
- **Constraint that bounds every trace idea:** the only read endpoints are
  `GET /{post_id}/vision-runs/latest?operation=` (`backend/routers/posts.py:890`) and
  `GET /{post_id}/vision-runs/{run_id}` (`:902`). **There is no list/history endpoint.** Any
  "run timeline" is a backend change, not a frontend experiment.

### 2.3 Stages, candidates, rehearsals

- Stage rendering exists and is good (`VisionActivityRail.jsx:75-89`); it is one `<details>`
  deep inside a collapsed drawer.
- "Candidates" already have a curator surface: `SemanticReading.jsx` renders assertions with
  status (`:23-26`), confidence bars (`:141-144`) and accept/edit/reject/tentative, plus a
  "needs better evidence → Refine" handoff wired at `DifferentialWorkspace.jsx:113-116`.
  This is the model the rest of the app should imitate, not a gap.
- **Rehearsals have no frontend representation whatsoever.** I searched for it; there is no
  component, hook, route or data shape in `frontend/src` corresponding to the R1/R2 rehearsal
  program. Anything shown about rehearsals would be new invention, not exposure.

---

## 3. Existing surfaces vs. a future Atlas/Codex

**Belongs in existing surfaces** (it is local truth about *this* image, needed at the moment
of the act):

- detached-evidence honesty in recall, RefPicker, percept rows, chips (§2.1);
- per-region provenance (detector / actor / confidence / rev) in `RegionSurface.jsx:486-494`;
- the dissect run stamp in `RegionSurface.jsx:372-383`;
- promoting non-nominal run states into the Rail's closed summary
  (`VisionActivityRail.jsx:124-133`);
- fixing Home's vocabulary so `region_annotations` are called *parts* and `post.percepts` are
  called *percepts* (`homeData.js:44-55`, `PerceptsTile.jsx:36`, `WeekTile.jsx:28`).

**Belongs to a future Atlas/Codex** (cross-corpus, comparative, historical — none of it is
answerable from the current API without new endpoints):

- "4 of 11 reference-based grounds corpus-wide are detached" — a corpus health view;
- run history / operation timelines / adapter-fallback rates over time;
- a percept↔ground↔region↔post graph;
- label-quality review across the archive (the `wall`/`floor` collapse as a *pattern*, not an
  incident);
- taste-vs-evidence reconciliation (`TasteTile.jsx` leans vs. what is actually grounded).

The dividing line I would hold: **existing surfaces answer "is what I'm looking at real?";
Atlas answers "what has happened across everything?"** Every idea in the second bucket needs a
backend read model that does not exist today.

---

## 4. Tempting but PREMATURE — arguing against my own best ideas

1. **A run timeline / "circulation history" panel.** My instinct is a per-post vertical
   timeline of runs. Against it: there is no list endpoint (`posts.py:890,902` are the only
   reads), and **there is exactly one `vision_runs` document in the entire database**. I would
   be building a chart of one point, then advocating for the backend endpoint to feed it. The
   honest order is: get telemetry density first, then a timeline.

2. **Live streaming (SSE/WebSocket) of stage events.** `useVisionActivity.js:1-6` explicitly
   chose bounded polling and says so. Streaming solves a latency problem nobody has
   demonstrated; the poll only arms while a run is `running` (`:54-61`). Premature.

3. **Auto-repairing detached grounds by re-matching geometry (IoU against new regions).**
   Genuinely tempting and genuinely dangerous. `grounds.js:12-19` is explicit that a
   region-ground stores *only* `region_id` and degrades rather than guessing. Silently
   re-pointing a curator's evidence at a *different* polygon that happens to overlap
   manufactures provenance. If this is ever built it must be a curator-confirmed action with
   both shapes shown, never automatic — and that is a build, not an experiment.

4. **An Atlas graph view now.** The graph edges exist client-side only
   (`perceptMentions.js:91-133`, `regionStore.js:300-315`) and Mentions are reconstructed from
   block markup by regex at load (`perceptMentions.js:154-170`). A graph over a
   regex-reconstructed, unpersisted join layer would look authoritative while being derived.
   The join needs to be real before it is drawn.

5. **Putting circulation telemetry on `/home`.** Tempting because Home is dull. But Home's
   actual defect is a *vocabulary* error (§1.1), not a missing dashboard. Adding run
   statistics to a bento tile before fixing "percepts" ≠ `region_annotations` would layer
   accurate machinery on top of an inaccurate claim.

6. **Making the Vision Activity Rail open by default.** I nearly listed this as experiment #1.
   Against it: with one run in the corpus it would open to four rows of "No recorded activity"
   for every user, every time — training people to close it permanently. The summary-line
   change (§5.5) gets the signal without spending the disclosure.

7. **A "detached evidence" badge on every percept chip.** Over-marking healthy percepts turns
   the mark into noise. Any badge should be *degradation-only* — silent when everything resolves.

---

## 5. Top 5 REVERSIBLE frontend experiments (PROPOSED, unapproved)

Reversibility criterion used throughout: **no schema change, no new endpoint, no stored data,
no migration** — pure derivation from state already in the client, removable by deleting the
diff.

### E1 — Honest recall: refuse to perform an unevidenced percept
- **Where:** `differential/recall.js:27-66` (script build) + captions in
  `DifferentialWorkspace.jsx:544` and `RegionSurface.jsx:330-332`.
- **Shows:** whether the silent empty replay is actually experienced as a failure. Today
  `pctx_mrqp950d_0` recedes the image, draws nothing, and asserts a caption.
- **Reversible:** derivation only, via existing `resolveGround`; no persistence.
- **Cost:** small (~½ day incl. tests; `recall.test.js` already exists).
- **Killed by:** a race — regions hydrate async (`regionStore.js:94-119`) while grounds
  hydrate in the same effect; if resolution transiently reports detached during load the
  refusal will flicker and be worse than the silence. If that flicker cannot be eliminated
  without ordering guarantees, kill it.

### E2 — Degradation-only evidence badge in RefPicker
- **Where:** `components/RefPicker.jsx:26,39-51`; pass `regions` from
  `PostDetailPage.jsx:938-950`.
- **Shows:** whether curators avoid citing broken percepts when told at the point of citation.
  Currently the badge counts grounds without checking any of them resolve.
- **Reversible:** one prop + one derived string.
- **Cost:** very small (a few hours).
- **Killed by:** if in practice curators never re-cite old percepts after a re-dissect, the
  badge never fires and buys nothing — measure whether the percept picker is used at all first.

### E3 — Provenance line on region rows, degradation-first
- **Where:** `components/RegionSurface.jsx:486-494` (row body), styling hook already at
  `RegionOverlay.jsx:21`.
- **Shows:** whether making `detector` / `actor` / `confidence` visible changes how curators
  treat out-of-domain labels (the `wall`/`floor` sculpture, the `tie knot` painting).
- **Reversible:** render-only; reads fields already on the region objects.
- **Cost:** small, **but** — I could not verify from the frontend that stored regions actually
  carry `confidence` or `detector`. Only `actor` is read today (`RegionOverlay.jsx:21`), and
  `RegionSurface.jsx:214-223` writes `detector: null` for creator marks. **A data check must
  precede this experiment.**
- **Killed by:** the fields being absent/null on the majority of stored regions — in which
  case the row gains clutter and no information.

### E4 — Dissect run stamp: thread the act to its record
- **Where:** capture `data.run_id` at `RegionSurface.jsx:180-181`; render in the existing
  counts strip `RegionSurface.jsx:372-383`.
- **Shows:** whether a visible run identity makes the Rail get opened at all — i.e. whether
  telemetry becomes *used* rather than merely *recorded*. This directly addresses "only 1
  `vision_runs` document exists".
- **Reversible:** one `useState`, one span.
- **Cost:** very small.
- **Killed by:** if dissect runs are not in fact being recorded for most posts, the stamp will
  be empty almost always. That emptiness is itself the finding — but if so, the fix is
  backend instrumentation, not this UI.

### E5 — Rail summary tells the truth about non-nominal states
- **Where:** `differential/VisionActivityRail.jsx:124-133` (and its derivation would belong in
  `visionActivity.js` to stay unit-tested, per that module's stated contract at `:1-7`).
- **Shows:** whether surfacing "1 interrupted" / "1 partial" / "some unreadable" in the
  *closed* line gets the drawer opened, without spending the disclosure by defaulting it open.
  Today `partial`, `timed_out` and `stale` all fold into `"N recorded"`.
- **Reversible:** copy + derivation; the tone vocabulary already exists
  (`visionActivity.js:68-86`).
- **Cost:** very small; `visionActivity.test.js` already covers the derivation surface.
- **Killed by:** with corpus telemetry as sparse as it is, the summary will read
  "nothing recorded yet" essentially always — making the experiment unmeasurable until E4 or
  backend instrumentation lands. **E5 should be sequenced after E4.**

---

## 6. Things I looked for and did not find

Stated plainly rather than invented:

- No frontend concept of **rehearsals** anywhere in `frontend/src`.
- No **list/history** endpoint for vision runs — only `latest` and `by id`
  (`backend/routers/posts.py:890,902`).
- No **lens-level detachment** model (the `resolveGround` analogue for
  `aletheia.lenses[].region_ids`) — `AletheiaHook.jsx:106` and `RefPicker.jsx:53-64` both
  filter/count dead ids without any resolution concept.
- No surface anywhere displays a `run_id`.
- No consumer of `post.percepts` / `post.grounds` outside `regionStore.js:94-119`,
  `DifferentialWorkspace.jsx` and `RefPicker.jsx` — in particular, none on `/home` or `/gallery`.
