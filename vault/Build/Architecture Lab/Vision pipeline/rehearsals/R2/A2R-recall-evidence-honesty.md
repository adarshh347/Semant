# A2R — Recall evidence honesty: **bug CONFIRMED and fixed**

Verification of the HW-S1 scout's claim that detached grounds replay as confident captions over
empty evidence. **The claim was correct.** Smallest honesty fix applied, tested, and
render-verified against the real detached case.

Production data **unchanged**; the detached grounds were **deliberately not repaired**.

---

## The bug, confirmed at source

Three files had to agree and did not:

1. **`regionStore.js:214`** — `groundById` is a raw array lookup:
   `groundsRef.current.find(g => g.id === id) || null`. It answers *"does this Ground exist?"*
2. **`recall.js`** — `useRecallPlayer` passed `groundById` into `buildRecallScript`'s parameter,
   which was **named `resolveGround`**. The name asserted a resolution the value never performed.
   A detached ground exists, so it passed the `if (!g …) continue` check and received a full timed
   `ground` step.
3. **`GroundLayers.jsx:249`** — at render, the *real* `resolveGround` runs:
   `resolveGround(g, { regions, grounds })?.region` → `null` for a detached ground →
   `RegionGround` returns `null` (`:166`). **Nothing is drawn.**

Net rendered behaviour, before the fix, for percept `pctx_mrqp950d_0` ("the upper head") on post
`695be786`: the image recedes and desaturates → two highlight steps play over **nothing** → the
caption asserts *"the upper head"* over an empty image. Both of that percept's grounds are detached
(`fine_3` "hair", `fine_0` "face" — replaced by an `arch_*` re-dissect), so **100 %** of its
performance was empty.

**This is worse than the silence A2S described.** A2S found that nothing *announces* evidence loss.
A2R finds the system actively *performs* the missing evidence and then states the claim — a
confident display of absent evidence.

## The fix (smallest honest change)

**`recall.js`**
- Renamed the misleading parameter `resolveGround` → **`lookup`**, since that is what it does. The
  name was load-bearing in the wrong direction.
- Added an optional `{ isResolved }` option. Grounds that fail it get **no highlight step** and are
  collected into `script.unresolvedGroundIds`, with `resolvedCount` and `citedCount` alongside — a
  denominator, so "1 of 3 gone" reads differently from "3 of 3 gone".
- `useRecallPlayer` now supplies `isResolved` built from the **real `resolveGround`**, the same
  function `GroundLayers` uses to decide what to draw. Script and render can no longer disagree.
- Exposes `evidenceNote`, which appears **with** the caption, never before it.

**`DifferentialWorkspace.jsx`** — the caption and its note render together in one `diff-recall-say`
wrapper.

**`DifferentialWorkspace.css`** — the wrapper is bounded (`max-height: 45%`, `overflow-y: auto`,
`overflow-wrap: anywhere`), so a paragraph-length percept can no longer overflow or clobber the
image. The note is styled quieter than the caption it qualifies.

### Choices made deliberately

- **The percept is never suppressed.** It is the curator's own words. When every ground is
  detached the expression still plays — qualified, not deleted. A test pins this.
- **The note states a fact about the record, not a fault of the curator.** It matches the language
  the inspector already uses ("DETACHED EVIDENCE", "its part was replaced by a re-dissect"), which
  turned out to already exist in the Differential panel.
- **No repair, no re-pointing, no IoU guessing.** Manufacturing provenance would be worse than the
  bug.
- **Chiasm was not redesigned.** Only the recall path changed.

## Verification

**Tests — 96 frontend tests pass**, including 5 new ones in `recall.test.js`:
detached ground gets no highlight step but is reported; mixed resolved/unresolved counted
correctly; the expression still plays when everything is detached; **back-compatible when no
`isResolved` is supplied**; a geometry-bearing `field` is never counted unresolved (matching the
corpus fact that 0 of 15 survived-by-geometry grounds are detached).

**Render-verified** in a real browser against the real backend, on the real detached percept
(`evidence/A2R-detached-recall-honest.jpg`): the caption *"the upper head"* now appears above
**"Detached evidence — none of the 2 cited grounds still resolves."** No console errors.

**Production unchanged** — post `695be786`: 7 regions, 5 grounds, 2 percepts, 0 text_blocks;
`gnd_mrqp8tls_0` and `gnd_mrqp8tlt_1` still detached. Nothing was saved (level A).

## What this does NOT fix

- **Chiasm's Manuscript chip path.** A percept chip clicked in the editor drives recall through the
  same player, so it inherits the fix — but the caption/note element lives in
  `DifferentialWorkspace.jsx`. Whether Chiasm renders the note in its own pane was **not** verified
  here and should not be assumed.
- **`RefPicker`** still offers a detached percept as "2 grounds" without resolving any (S1's
  finding). Out of scope for this lane.
- **The Aletheia `/read` surface**, which S1 reports has the same shape of problem with no model
  support.
- **The underlying data.** Two posts still carry four detached grounds. The repair fork —
  tombstoning versus notifying — remains open and unchosen.

## Effect on spark-03

**Strengthened, and sharpened.** The claim was "evidence loss should be announced, not merely
survived." A2R shows the pre-fix system did something stronger than fail to announce: it
*performed* absent evidence convincingly. One surface now tells the truth. The corpus-level
question — whether curators should be notified at the moment of loss, and whether old regions
should persist — is untouched and still needs the orchestrator's judgement.
