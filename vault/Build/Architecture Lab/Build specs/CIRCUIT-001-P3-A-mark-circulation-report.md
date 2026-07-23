# CIRCUIT-001 P3-A — Mark Circulation: Manuscript citation, recall performance, visible provenance

**Lane A3 (the soul lane), main tree. Branch `feat/circuit-p3-circulation` off `origin/main`
@ `f679141` (PR #64 P2E-B mechanics confirmed MERGED). Additive only: no backend change, no
migration, no new dependency, no Konva. Nothing in Lane B3's files touched.**

**The one sentence this gate finishes:** the curator marks; the mark persists (P2E-A); the
Manuscript now CITES a committed mark as a chip; the citation RETURNS and PERFORMS it on the
image; and at every step you can see who made what — a suggestion can never be cited, and a
mark is honestly labelled *saved* or *session* wherever it appears.

---

## Gate 0 — precondition

`git fetch` → **PR #64 is MERGED** (`mergeCommit f679141`, now the tip of `origin/main`; the
P2E-B mechanics — handles, hit-paths, perfect-freehand, semantic brush — are in the base). Branched
`feat/circuit-p3-circulation` off it. The only dirty file carried in my ownership area was
`recall.test.js` (+95 lines of valid P1A ledger coverage matching already-merged `recall.js`) —
preserved, not authored by me, left as uncommitted WIP.

> Note: my `node_modules` predated PR #64, so `perfect-freehand` (a dep #64 added to
> `package.json`) was missing and `freehandStroke.test.js` failed to *load*. `npm install` synced
> it — no dep added by me; `package.json` untouched.

## 2a — Mark citation (a committed mark becomes referenceable)

**Chip grammar — additive.** `regionRefInline.jsx` gains a `markId` prop, a `data-mark-id="vm_…"`
attribute (emitted only when present), and reads it back in `parse`. `data-percept-id` /
`data-region-ids` / `data-mention-id` are untouched; every legacy chip is byte-identical, and
back-compat is absolute (a chip with no `markId` serialises exactly as before). `blockConvert`
round-trips it automatically (it delegates to the schema-aware engine); the gated test's mirror
spec was extended to carry `markId` and a new assertion proves `data-mark-id="vm_abc_0"` survives
import→export alongside the ground ids and mention id.

**Mention model.** `perceptMentions` accepts a `markId` edge. `mentionId`'s grammar is
**unchanged** (`men_<subject>_<block>_<slot>`); a mark chip simply names the mark as its subject
when it cites neither percept nor region. `mentionsFromBlocks` reconstructs a mark edge from stored
markup (one edge per chip, keyed on the mark — never split into region edges); `mentionsForMark`
is the query. A stored `data-mention-id` still wins over a re-derived one (no second name for the
same edge).

**The citation filter — one place.** `RefPicker` gains a `kind: 'mark'` branch that offers
`marks.filter(canCiteMark)` and nothing else. `canCiteMark` (committed + `user`/`user_confirmed` +
geometry not `unresolved`) is THE filter and it lives only in `suggestionQuarantine.js`. A
suggestion, a draft, or an ungeometried mark is never even listed. A `/mark` slash item
(`Manuscript.jsx`) opens the picker; `insertRegionChip` carries `markId` through.

**Enforced at the seam — fails closed.** `PostDetailPage.insertRef`'s `kind === 'mark'` branch
opens with `if (!canCiteMark(raw)) return;` — no chip, no Mention. Even a caller that reached the
seam another way cannot cite a suggestion: a chip on the page IS a claim of evidence, and the claim
must be earned. (Covered by the RefPicker test's "never offers a suggestion / draft" cases + the
`canCiteMark` guard.)

## 2b — Mark recall (clicking a mark chip performs the mark)

**`recall.js` — the mark analog of `buildRecallScript`, in the same module:**

- `resolveMark(mark, { regions, marks })` is to a mark what `resolveGround` is to a ground: it
  returns `{ detached, reason }`. A geometry-bearing family (brush/trace/frame) resolves iff it has
  real geometry; a `region_mask` resolves iff the region it points at still exists (the mask lives
  on the Region — contract v2 §7.2-C); a relation/collection resolves iff it still names ≥1 ref.
- `MARK_PERFORMANCE` names each family's signature — `brush_field → bloom`, `trace_mark → draw_on`,
  `relation_mark → perform_then_unite`, `region_mask → illuminate`, `frame_mark → frame`,
  `collection_mark → gather`.
- `buildMarkRecallScript(mark, …)` stages **recede → the mark performs → (relation/collection) its
  member grounds stagger in → the caption**. A detached mark yields a script that recedes and names
  the loss — never a timed highlight over nothing (the discipline the ground path learned in P1A).

**The player.** `useRecallPlayer` branches on `recall.markId`: it finds the mark in
`store.visualMarks`, builds the mark script, and exposes `progressForMark(markId)`,
`markPerformance`, `isMarkRecall`, `markMissing` (the mark analog of `perceptMissing`), and
`markDetached` + `markNote`. The percept path is byte-for-byte unchanged; `perceptMissing` now
excludes mark recall so it can't misfire.

**Store + dispatch.** `regionStore` gains `playMarkRecall(markId)` (sets `recall = { markId }`; the
two recall shapes never coexist). `PostDetailPage` routes `data-mark-id` **exactly as `pctx_`
does** — in BOTH seams: the DOM-path `chipClickRef` (read view + editor) checks `data-mark-id`
first and calls `playMarkRecall`; the emit-path `onFocus`/`onHover` checks `e.detail.markId`. A
mark chip lights itself while its mark is performed (same honesty guard as the percept chip: only
if the mark is actually in the store). Detached/degraded marks degrade exactly as grounds do.

## 2c — Visible provenance, everywhere

- **Manuscript mark inspection (`PassageInspector`).** The stale blanket **"Session — not saved"**
  is RETIRED. Durability is now per mark: a committed/superseded mark reads **"Saved"**
  (`data-persisted="true"`), a draft/suggestion reads **"Session — not saved"** — derived from
  status, never asserted. `summarizeProvenance` is shown on every row, so `model_refined` /
  `user_confirmed` are never displayed as a bare `user`.
- **The source of truth for both surfaces (`markStaging.markDisplay`).** `session: true` became
  `persisted: isPersistableMark(mark)` + `session: !persisted` + `superseded`. Both the Manuscript
  and the Differential armed-strip read this descriptor, so no surface can claim otherwise.
  `marksSummary` is honest too — `"2 marks · 1 saved · 1 not citable"`, not `"session marks"`.
- **Ground display (bridge reconciliation, via the store).** `regionStore.groundProvenance(ground)`
  runs `reconcileBridgeFields` against the live marks and returns `{ mark_id, mark_source, label }`
  — a ground can now SHOW who made it (`summarizeProvenance`) without ever authoring provenance
  itself. The mark stays the only authored home (decision E). See **P3F** below for the render.
- **RefPicker rows** show `type · summarizeProvenance(mark)` as the sub-line, so provenance is
  visible at the moment of citation.

## 2d — Truth maintenance

`marksForPercept` reads the store's marks, which now include the durable (committed/superseded)
ones after hydrate (P2E-A). A superseded mark is surfaced in inspection as **lineage** via
`markLineageNote(mark, marks)` → `"replaces vm_old"` / `"replaced by vm_new"` — recoverable, per
P1F/P1G. Silent re-pointing is the failure this exists to prevent; the note makes the supersession
loud. The row carries `is-superseded` styling (kept, recessed, not hidden).

## `// P3F:` markers — rendering that lands in Lane B3 / the merge gate

Per the ownership rule, where mark recall or provenance needs a change inside a B3-owned file I
extended the store/recall **data contract** and left a marker + spec here:

1. **`recall.js:123` — GroundLayers must consume the `kind: 'mark'` recall step.** The script
   already carries, per step: `{ markId, mark_type, role, performance, at, dur }`, and the player
   exposes `progressForMark(markId)` (0..1, same ramp as `progressFor(groundId)`) and
   `markPerformance`. B3 renders: `bloom` a brush_field (like a field ground), `draw_on` a trace
   (the SVG `pathLength` idiom recall already uses for paths), `perform_then_unite` a relation over
   its trailing `kind: 'ground'` member steps, `illuminate` a `region_mask`'s region. The DATA is
   done; only the visual bloom/draw is deferred.
2. **`regionStore.js:306` — the Differential inspector should read `groundProvenance(groundId)`.**
   `DifferentialWorkspace.jsx` (B3) already calls `summarizeProvenance` for a ground's own mark
   (`gm`); the P3F ask is to route its ground row through the store's `groundProvenance` (bridge
   reconciliation) instead of re-deriving, so there is one source of truth for "who made this
   ground". Non-blocking — DW already surfaces provenance; this makes it single-sourced.

## What Lane B3 / the merge gate must know

1. **Persist at commit, not at arm.** Unchanged from P2E-A: `addVisualMark(draft, {save:false})`
   while staging; `updateVisualMark(id, {status:'committed'})` at merge is the write. Only a
   committed/superseded mark reaches `canCiteMark`, so only then can it be cited in the Manuscript.
2. **The confirm-path mark should still migrate to `region_mask`** (P2E-A §10.1) — orthogonal to
   this gate, still a one-liner in B3's `confirmRefine`.
3. **`playMarkRecall` vs `playRecall`.** They set different `recall` shapes; never set both. The
   player and the chip both read `recall.markId` xor `recall.perceptId`.
4. **A mark chip's `data-region-ids` are the mark's linked GROUND ids** (hover context), NOT region
   ids — the click routes on `data-mark-id`, exactly as a percept chip routes on `data-percept-id`.

## Gate 3 — tests + build

| | |
|---|---|
| new/changed suites | `recall.test.js` (+resolveMark/buildMarkRecallScript per family), `recall.mark.dom.test.jsx` (NEW — player performs a mark, markMissing, region_mask detach), `RefPicker.mark.dom.test.jsx` (NEW — citation filter fails closed, suggestion/draft never offered), `blockConvert.test.js` (+/mark chip round-trip), `perceptMentions.test.js` (+mark edge, mentionsForMark, reconstruct-from-markup), `markStaging.test.js` (+persisted/session derived, provenance × 4 sources, lineage), `PassageInspector.p2e.dom.test.jsx` (Saved vs session per mark) |
| full frontend suite | **629 passing, 37 files** (was 623 pre-`npm install`; +6 = the freehand suite that couldn't load) |
| production build | ✅ clean (pre-existing chunk-size warning only) |
| lint | **zero new errors** — 18 errors identical to the `origin/main` baseline on the same files (legacy PostDetailPage `no-unused-vars` + one `react-refresh` on regionRefInline); the one warning I introduced was removed |
| backend | **untouched** — marks persist via P2E-A's `post.visual_marks`; the mark chip lives in `text_blocks` HTML, which already round-trips. No schema change was needed. |

Round-trip coverage: a `/mark` chip survives `blockConvert` (attrs asserted like the pctx test); a
non-citable mark is never offered AND the insert seam fails closed; a recall script is built per
family (bloom / draw_on / perform_then_unite / illuminate); the player routes `recall.markId` to a
mark performance; provenance labels render for all four sources; a superseded mark shows its
lineage; a committed mark reads "Saved" while a suggestion reads "Session — not saved".

## Production-mutation status

**None.** No PATCH, no refine-confirm, no detect-regions against a real post. Every persistence
path was exercised through pure builders and stubbed stores.

## Files changed

**Frontend (mine):** `differential/recall.js` (mark recall) · `differential/markStaging.js`
(durability derived, lineage) · `state/regionStore.js` (`playMarkRecall`, `groundProvenance`) ·
`state/perceptMentions.js` (mark edge) · `components/blocknote/regionRefInline.jsx` (`markId`
grammar) · `components/blocknote/Manuscript.jsx` (`/mark` item + chip prop) · `components/RefPicker.jsx`
(mark kind, `canCiteMark` filter) · `components/PostDetailPage.jsx` (insert branch fail-closed +
dispatch routing + picker prop) · `manuscript/PassageInspector.jsx` + `.css` (visible provenance,
retired stale label, lineage).

**New tests:** `differential/recall.mark.dom.test.jsx` · `components/RefPicker.mark.dom.test.jsx`.
**Extended tests:** `recall.test.js`, `blockConvert.test.js`, `perceptMentions.test.js`,
`markStaging.test.js`, `PassageInspector.p2e.dom.test.jsx`.

**Not touched (Lane B3 / other lanes):** `DifferentialWorkspace.jsx`, `GroundLayers.jsx`,
`InstrumentHandles.jsx`, `handleEditing.js`, `fieldCanvas.js`, `useMaskRefine.js`, `AttunementPanel.*`
— per the binding ownership split. `package.json` untouched.
