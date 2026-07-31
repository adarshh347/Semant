# CIRCUIT-001 P5-A — The Crossing: circulation between images

**Lane A5 (the soul lane), main tree. Branch `feat/circuit-p5-crossing` off `origin/main` @
`62d80e8`** (P4F wiring merged: PR #72 producers + PR #73 review). Additive backend only, no
migration, no new frontend dep, no model called in tests, dirty vault files preserved. Lane B5's
Passage Rail runs in parallel in its own worktree; its files untouched.

**The rule this gate serves:** the original CS-001 dream was *Differential → Manuscript → … →
another Differential*. P0 found the crossing absent; every phase since built inside one image. This
gate builds the border itself — **truthfully, which means: a crossing is a reference with receipts —
never a copy, never an assertion, never silent about its own staleness.**

---

## Gate 0 — precondition + base

`git fetch`. The P4F wiring PR is **merged** (PR #72 real producers + contract v3; PR #73 review UX —
both on `origin/main`). Branched `feat/circuit-p5-crossing` off `origin/main` @ `62d80e8`. Main
health carried by the automated suites (725 frontend + clean build; 433 backend) — a dev-server
click-through remains blocked by the machine's `inotify` watcher limit (`vite` `ENOSPC`), so the
comprehensive suites + build are the "main is not broken" signal.

## 2d/9.1 — the reference shape (a reference, never a copy)

A cross-post mark is a `region_ref` whose `region_ref` carries the **border coordinates**:

```
geometry { kind:'region_ref', region_ref: { region_id, post_id, geometry_rev } }
```

- `post_id` present → the reference names a region on ANOTHER post. Absent → a same-post ref
  (unchanged from v3 §8.2). `crossPostReference(mark)` reads `{post_id, region_id, geometry_rev}` or
  `null`; `isCrossPostMark` is the predicate. (`visualMarks.js`.)
- `geometry_rev` is the source region's rev **AT CITATION** — the whole basis of staleness (2d).
- **No pixels, no `mask_ref`.** The border rule is enforced in `validateMark`: a `region_ref` that
  carries a `mask_ref` (or `pixels`/`rle`/…) is refused — a naming reference authors nothing, so a
  crossing physically cannot copy geometry across the border. A test asserts reference-only both at
  intake and after acceptance.

## 2c/9.2 — find-similar as a producer (Invariant 4 finally has a product seam)

`PRODUCERS` gains **`find_similar`**. `suggestion_service.suggestions_from_similar(result, run_id)`
projects each neighbour (which lives on ANOTHER post) → a `model_suggested` cross-post `region_ref`
descriptor on the CURRENT post:

```python
{ 'producer':'find_similar', 'type':'region_mask', 'role':None, 'label':'lapel',
  'source_ref':'post_B:reg_9',
  'geometry':{'kind':'region_ref','region_ref':{'region_id':'reg_9','post_id':'post_B','geometry_rev':3}},
  'linked_ground_ids':[],
  'provenance':{'model':'dinov2_vits14','adapter':'find_similar','run_id':'run_fs','producer':'find_similar'} }
```

- The find-similar route gains an **additive `suggestions`** field, computed from the same research
  packet the route already returns — **no post state written** (a suggestion is a proposal). A
  degraded/empty search carries none. The suggestion's `run_id` is the route's real
  `VisionRunRecorder` run (no second run concept — the P1E model, same as P4-A).
- The neighbour's own `mask_rle`/geometry is present in the research packet and **deliberately not
  copied** — only `{post_id, region_id, geometry_rev}` crosses.
- The frontend intake side (`useFindSimilar`) exposes the `suggestions` array; feeding it through
  `store.ingestSuggestions` (built in P4-A) drops each into **B4's review rhythm unchanged**.
  Accepting one mints a `user_confirmed` cross-post reference (2a's kind) — the same border geometry
  rides forward through `acceptSuggestion`; nothing is copied.

## 2a/9.3 — cross-post citation identity (chip + Mention carry the border)

- The `regionRef` inline chip gains additive **`data-post-id`** (`regionRefInline.jsx` +
  `Manuscript.jsx` `insertRegionChip`). It round-trips through `blockConvert` (the gated Phase-3
  test now asserts a cross-post chip survives import→export — else the crossing would silently
  flatten to a same-post citation on the next edit).
- The **Mention model** gains a `postId` edge (`makeMention`, `mentionsFromBlocks` reads
  `data-post-id`, new `mentionsForPost`). `postId` does **not** enter the mention id — the slot
  (`inlineContentId`) already makes a chip unique in its block — so **no existing edge is
  invalidated** (byte-identical for same-post chips).
- **Citability across the border is fail-closed.** A chip is a claim of evidence, so only a
  committed, curator-owned/confirmed mark is insertable (`canCiteMark`, enforced at the insertion
  seam in `PostDetailPage`). A find-similar suggestion is `model_suggested` → **not citable until
  accepted**; the RefPicker never even offers it. The crossing therefore rides the P4-A quarantine:
  research → suggestion → (human accepts) → `user_confirmed` cross-post reference → citable chip.

## 2b/9.4 — cross-post recall: **navigate**, not overlay (the decision)

Clicking a foreign chip **resolves the source post (fetch, never assume loaded)** then **navigates**
to it with recall armed; the existing recall performs natively there.

**Navigate vs overlay — why navigate.** An in-place overlay would need a second render surface
holding a *copy* of the foreign image + regions inside the current page — precisely the "copy across
the border" this gate exists to forbid, and a copy that goes stale the moment the source changes.
Navigating carries only the reference (`{post_id, region_id}`) in router state; the destination
`PostDetailPage` re-fetches the live source and performs the recall it already knows how to perform
(`focusRegions` today; `playMarkRecall` when a foreign mark is cited). Cheapest, and the only option
with no duplicate/stale render. Recorded here as the settled decision.

Mechanically: `crossPost.resolveCrossPost(ref, {fetchPost})` returns a verdict; the click seam acts:
- `ok` / `stale` → `navigate('/posts/<source>', { state:{ crossRecall:{ regionId, stale } } })`;
  the destination's one-shot effect performs it once loaded, then clears the router state so a
  refresh does not replay it.
- `post_gone` / `region_gone` → **state the loss** ("evidence unavailable — …") in a small honest
  notice; never a crash, never a silent no-op — a foreign chip degrades exactly as a detached ground
  does (P1B).

**Staleness (2d).** `resolveCrossPost` compares the citation's `geometry_rev` against the source
region's current rev: a mismatch is `stale` — the crossing **still performs** (the region exists),
but the drift is **stated** ("source has changed since cited"), never hidden. When either rev is
unknown, no drift is claimed (silence about an unknowable is honest; a false "stale" is not).

## Tests + build (no model called; no production data mutated)

| | |
|---|---|
| backend | **6 new** (`test_crossing_producers.py`: pure find-similar → cross-post descriptors ×4 + route additive-`suggestions`, reference-only, degraded ×2) · full backend suite **433 green** |
| frontend | **+39** across touched suites → **725 green (43 files)**: `visualMarks` cross-post block (reference shape, no-copy, broken-ref rejection, `find_similar` receipt) · `crossPost.test.js` (resolution + degradation: post/region gone, throwing fetch, rev-drift stale, no-false-stale) · `suggestionQuarantine` crossing block (quarantined intake, idempotent by border target, accepted-crossing lineage reference-only) · `perceptMentions` postId edge · `blockConvert` gated cross-post chip round-trip |
| build | ✅ clean |
| border truth | tests assert **no geometry crosses**: the neighbour's `mask_rle` is present in the research packet yet never appears in the descriptor; acceptance preserves the reference, copies nothing; a `region_ref` carrying a `mask_ref` is refused by the validator |

## `// P5F:` markers (Differential/rail affordances for B5 / next-B)

- **`PostDetailPage.jsx`** — the cross-post degradation notice is a minimal inline breath (a fixed
  status line). Marked `P5F:` — **B5's Passage Rail may render this in its own idiom** (a
  border-inspection surface showing the reference, its source, and its staleness). The DATA is here
  (`crossPostNote`, the `stale` verdict); the styled surface belongs to the rail.
- **Foreign-mark recall** — the recall armed on navigation currently performs `focusRegions` for a
  find-similar crossing (a region reference). When a future gate lets a chip cite a foreign *mark*
  directly, the destination should `playMarkRecall` on it — the seam reads `crossRecall.markId`
  already; only the arming producer needs to set it. (Differential affordance, not built here.)

## Files changed

**Backend (additive):** `services/suggestion_service.py` (`PRODUCER_FIND_SIMILAR` +
`suggestions_from_similar`) · `routers/posts.py` (find-similar route gains additive `suggestions`) ·
`tests/test_crossing_producers.py` (new).

**Frontend:** `differential/visualMarks.js` (cross-post `region_ref` validation + `crossPostReference`/
`isCrossPostMark` + `regionRefMark` postId/geometryRev + `find_similar` producer) · `differential/
crossPost.js` (new — resolution/degradation/staleness) · `differential/useFindSimilar.js` (expose
`suggestions`) · `components/blocknote/regionRefInline.jsx` + `Manuscript.jsx` (`data-post-id` chip) ·
`state/perceptMentions.js` (`postId` edge + `mentionsForPost`) · `components/PostDetailPage.jsx`
(cross-post click → resolve+navigate/degrade; armed-recall consumer; cross-post citation) · tests
(`visualMarks`, `crossPost`, `suggestionQuarantine`, `perceptMentions`, `blockConvert`).

**Docs:** contract §9 (the crossing layer) · this report.

**Not touched (Lane B5 / others):** `DifferentialWorkspace.jsx`, `AttunementPanel.*`,
`GroundLayers.jsx`, `InstrumentHandles.jsx`, `SuggestionReview.*`, and no vision-run endpoints.

## What Lane B5 / the merge gate must know

1. **A crossing is a reference, never a copy.** A cross-post mark is a `region_ref` carrying
   `{post_id, region_id, geometry_rev}` and NO geometry. Read it with `crossPostReference`.
2. **find-similar now emits `suggestions`** — feed the array through `store.ingestSuggestions` and it
   enters the existing review rhythm; accepting mints a `user_confirmed` cross-post reference.
3. **Recall crosses by NAVIGATION** — the destination performs it. The border degradation
   (`crossPostNote` + `stale`) is the rail's to render richly (`P5F:`); the data is supplied.
4. **Citability is fail-closed** — only committed, curator-owned marks cross; a suggestion cannot be
   laundered into a cross-post citation.
