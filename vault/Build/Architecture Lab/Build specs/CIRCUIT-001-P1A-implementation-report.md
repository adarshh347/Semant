# CIRCUIT-001 P1A — Implementation report

**First product code of the CIRCUIT programme.** Implements the artery between Differential and
Manuscript, plus the seed Circulation Thread. Specs:
`CIRCUIT-001-P0.5-chiasmatic-network-design.md`,
`CIRCUIT-001-P1-differential-manuscript-circuit-spec.md`.

**Production data: NOT mutated.** No backend file, route, schema, collection or migration was
touched. Browser verification was **read-only** — an existing post was loaded and inspected; nothing
was created, saved or deleted.

---

## 1. Gate 0 — the dirty state, classified before anything was edited

Six frontend files were dirty on arrival. **All six are directly part of P1A Part C** (recall truth)
and were kept and built on, per the gate's instruction:

| file | what it already contained |
|---|---|
| `recall.js` | two ledgers (`unresolvedCitedIds` / `unresolvedMemberIds`) fixing the *"2 of 1 cited grounds"* arithmetic; a cited ground whose **record** is gone now counts as unresolved instead of being silently skipped; a `Partial evidence — N grounds inside this composition…` phrasing |
| `grounds.js` | **recursive** composite detachment — a constellation whose members' regions were all replaced is now detached, with a cycle guard. Previously member *records* surviving counted as attachment while `GroundLayers` drew nothing: the A2R failure one ground type deeper |
| `RegionSurface.{jsx,css}` | `evidenceNote` rendered on the **writing** surface, in a bounded scrollable `.rs-recall-say` wrapper so a paragraph-length percept cannot cover the image |
| `grounds.test.js`, `recall.test.js` | +11 tests pinning the above |

Three untracked files — `backend/tests/test_foundry_harness.py`, `scripts/foundry_run.py`,
`scripts/_run_backend.py` — are **unrelated user work** and were neither staged nor touched.

**Consequence: Gate 4 (Part C) arrived already satisfied.** This report claims no credit for it; it is
recorded here because the commit carries those files.

---

## 2. What changed in this gate

### Gate 2 — the DOM test harness (was: none at all)

P0 found no jsdom, no testing-library, vitest defaulting to `node`, and **zero component tests**, so
every UI finding shipped green. There was also **no test config of any kind**.

Added `vite.config.js` test block with **node as the default** and DOM opt-in **by filename**:

```js
environment: 'node',
environmentMatchGlobs: [['**/*.dom.test.jsx', 'jsdom']],
```

**One new devDependency: `jsdom`.** `@testing-library/{react,jest-dom}` were installed, found
unnecessary (these tests assert with plain `expect`), and **uninstalled** — the harness is the
environment, not a matcher library. The 107 pre-existing tests run exactly as before, in node, at the
same speed.

### Gate 3 — Part B: lossless mention reconstruction (`perceptMentions.js`)

**The bug:** `mentionsFromBlocks` regexed **one attribute** (`data-region-ids`) out of markup that
faithfully round-trips five. On every load a percept citation came back as an anonymous region edge,
its percept id, mention id, ref kind and label discarded — and the mention id it re-derived could
never match the one in the markup.

**The fix:** match the whole chip element and read what is there.
- `data-percept-id`, `data-mention-id`, `data-inline-type`/`data-ref-kind`, `data-label` recovered.
- **An id carried by the markup wins over a derived one** — deriving is right when a chip is *being
  made*, wrong when one is *being read back*.
- **One edge per percept chip**, not one per id: a `/percept` chip's `data-region-ids` are **ground**
  ids, so splitting them minted region edges pointing at `gnd_…`.
- **Back-compat preserved**: a chip with no percept id still yields one region edge per id, verbatim.
- Added `blockIdsForPercept()` — answers *"is this noticing carried by the writing?"*

### Gate 5 — Part A: the artery

`insertRef(raw, kindOverride)` in `PostDetailPage.jsx` now accepts an explicit kind, so a caller that
did not come through the RefPicker can use **the same insertion path** as the slash command. A new
`onSendToManuscript` prop on `DifferentialWorkspace` exits to Chiasm and inserts the percept chip.

**Deliberately the same path, not a parallel one** — the chip is identical whichever route produced
it, so the two cannot drift. The Chiasm shell stays mounted while Differential is open, so the editor
handle is already live and no remount is involved.

**UX:** a quiet second verb — **"Write from this"** — beside each percept. The percept is *not*
consumed; a noticing can be carried many times.

### Gate 6 — the seed Circulation Thread

New pure module `differential/circulationThread.js`, mirroring `visionActivity.js`'s contract:

- Relations: `formed · cites · mentioned · recalled · recorded · unavailable`.
- **Reports sequence, never causation.** A test asserts no link text matches
  `/because|caused|re-dissect|replaced|deleted|due to/i`.
- **Absent ≠ none.** A missing link says *"not recorded"* — a claim about the record, not the world.
- **`no model reading recorded`, always**, because no entity carries a `run_id` (P0 §5). *That blank
  row is the argument for `run_id`, and it makes it better than a document can.*
- Rendered as one line per percept, `threadSummary()` degradation-first.

### Gate 7 — polish taken because it was already in hand

`DifferentialWorkspace.jsx:832` said *"its part was replaced by a re-dissect."* `resolveGround` knows
only that the `region_id` does not resolve — a re-dissect is one cause among several. Now: **"its part
is no longer in the image."** This is the exact rule the new thread module's own guard enforces; it
would have been incoherent to ship the guard and leave the violation beside it.

**`Dissect` → `Find parts` was NOT taken.** It is fully specified and independent, and mixing a
12-string rename into the first product artery would have made this diff harder to review and revert
for no gain. Left for its own gate.

---

## 3. How a percept now travels

```
Differential                          Manuscript
  compose  ─┐
            │  "Write from this"      insertRef(percept,'percept')
            └──────────────────────▶  chip with data-percept-id
                                          │
                                          │ reload
                                          ▼
                                      mentionsFromBlocks → percept identity INTACT
                                          │
                                          │ click
                                          ▼
                                      playRecall → image performs the noticing
                                          │
                                          └─ evidence gone? evidenceNote says so, once
```

**Before this gate, hop 3 did not exist and hops 4–5 lost the percept's identity on the first
reload.**

---

## 4. Verification

| | |
|---|---|
| **frontend tests** | **126 passed, 9 files** (was 96 at branch state, 107 with the inherited Part C work). **+19 this gate**: 7 Part B, 9 thread, 3 DOM |
| **DOM test** | `mentionMarkup.dom.test.jsx` — builds the chip as a **real element**, lets the DOM serialise it, and parses *that*. Testing the regex only against hand-written strings would have proved it works on the one shape I happened to type |
| **production build** | `vite build` ✓ (pre-existing chunk-size warning unchanged) |
| **backend tests** | not run — **no backend file was touched** |
| **browser** | read-only, on `695be786a9ea58f1b6aef5ed` (2 percepts, 2 detached grounds) |

**Observed in the browser, on real data:**
- *"the upper head"* → **"cites 2 grounds · 2 no longer resolve"** — degraded, counted correctly, no
  cause invented.
- *"braided aspect which is commonly found in indian rock cut architecture"* → **"cites 1 ground"** —
  healthy, **no badge, no warning**. Degradation-only is working.
- Detached evidence rows read **"hair — its part is no longer in the image"**. The causal fix is live.
- `VISION ACTIVITY — nothing recorded yet`, consistent with the thread's *"no model reading
  recorded"*.

**Not visually confirmed:** the hover-reveal of "Write from this" (it is `opacity: 0` until
`:hover`/`:focus-visible`). The element renders and its handler is wired; the *reveal* was not
captured. See §6.

---

## 5. Production mutation status

**None.** Frontend-only diff. Mongo was never written; the browser session only read one post. No
percept, ground, region, text block or vision run was created, modified or deleted. `package.json`
gained one devDependency (`jsdom`) and `vite.config.js` gained a test block — neither ships to
production behaviour.

---

## 6. What remains missing — honestly

1. **The artery is hover-only.** For *the primary connective action of the product*, `opacity: 0`
   until hover is a real discoverability risk, and I could not confirm the reveal in-browser. **This
   is the first thing P1B should look at**, and the answer may simply be: always visible, quiet.
2. **No end-to-end run.** Forming a percept and writing from it would create data on a live post, and
   the gate forbids uncontrolled mutation. **The artery has passing unit-level wiring and no observed
   round trip.** Scenes 1, 3 and 4 of `CIRCUIT-001-P1-test-scenes.md` remain unexecuted.
3. **The three other silent recall failures are untouched** — a dead `/part` id still dims the whole
   image with no message; a percept absent from the store still lights its chip over a no-op; a
   `/lens` with replaced regions still shows nothing. Specced in P1 Part C, not built here.
4. **`RefPicker` badges still overstate** (cited counts, not resolving) — Part D, not taken.
5. **`suspect` does not exist.** A reference that still resolves to *different* geometry is
   indistinguishable from a healthy one. P0's sharpest finding remains unaddressed by design.
6. **Mentions are still reconstructed, not durable.** Part B made the reconstruction lossless — open
   decision §4 branch (b) — and deliberately did **not** persist them.
7. **`relationType` / `actor` are still defaulted** to `cites`/`human` on reconstruction. The gate's
   required list did not include them and the markup does not carry them; recovering them needs the
   chip to emit them first.

---

## 7. What P1B should build

**In this order, and the first is not the biggest:**

1. **Make the artery discoverable**, and run the three unexecuted scenes on a controlled post.
2. **Finish Part C's remaining three failures** — they are the rest of the click path this gate only
   half-repaired, and each is a small independent diff.
3. **Ground roles** (the addendum §2): *what each ground does for this percept* — anchor, counterforce
   — a per-percept property that cannot live on the Ground record. This is what makes a percept a
   *reading* rather than a list.
4. **Percept Packet builder** (Perceptive Orchestration): assemble intent + grounds + evidence state +
   manuscript context, inspectable before sending. Nothing sends yet; build the packet first.
5. **Fuller Circulation Thread** — expandable rows, records and judgements in visibly different
   voices.
6. **DOM visual verification** for the surfaces this gate changed, now that the harness exists.
7. **Atlas prep is NOT next.** It needs the durable-citation decision, and P1A deliberately did not
   take it.

**Do not, in P1B:** persist Mentions, implement `suspect`, add `run_id`, or start Atlas/Codex —
each is a decision in `CIRCUIT-001-P0-open-decisions.md`, not a task.
