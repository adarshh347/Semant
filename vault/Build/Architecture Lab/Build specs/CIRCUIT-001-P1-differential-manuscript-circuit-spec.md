# CIRCUIT-001 P1 — Differential ↔ Manuscript circuit: build spec

**SPEC ONLY — NOT IMPLEMENTED. No code changed, no production data touched, no model calls.**
Opening this gate requires an explicit instruction. Rests on
`CIRCUIT-001-P0.5-chiasmatic-network-design.md` and `CIRCUIT-001-P0-product-circuit-map.md`
(file:line evidence not re-derived here). Verification scenes: `CIRCUIT-001-P1-test-scenes.md`.

**Goal.** Make Differential and Manuscript feel like **one living circuit** rather than two panes that
happen to share a post.

**The slice's spine, and why it is this:** P0 found the circuit **severed at percept → mention** —
and severed by *absence*, not by bug. `DifferentialWorkspace.jsx:19-23` shows Differential is a
**mode inside `PostDetailPage`** (mounted at `:890`), the Chiasm shell stays mounted, and **both share
one `regionStore`**. Grepping Differential for a handoff returns one hit: a *"Back to Chiasm"* button
(`:450`). **The two halves are in the same component tree, sharing the same store, with no artery
between them.** This slice builds the artery and makes the round trip legible.

**Frontend-only, derivation-first.** No new collection, no new route, no migration, no schema change.
The one persisted change considered (§4) is additive and optional, and is explicitly deferrable.

---

## Part A — Carry the percept across (the artery)

### A.1 Current code path

| step | file:line | today |
|---|---|---|
| compose | `DifferentialWorkspace.jsx:288` `openComposer` → `:347-350` `savePercept` | builds `{expression, ground_ids, properties}` |
| persist | `regionStore.js:177` (`persistMeta` sends `{grounds, percepts}`) | `pctx_` percepts are the **only durable object** in the relationship model |
| leave | `DifferentialWorkspace.jsx:450` | *"Back to Chiasm — the Manuscript is exactly as you left it"* |
| re-find | `RefPicker.jsx:113` | *"No percepts yet — compose one in Differential."* |

**The curator must leave, remember, type `/percept`, and search for the thing they just made.**

### A.2 Proposed UX

After `savePercept` succeeds, the composer's confirmation offers a **second, equal action** beside
"Keep this percept":

> **Keep this percept** · **Keep and write from it →**

"Keep and write from it" exits Differential to the Manuscript **with the percept armed**: the caret
lands in the manuscript and a chip for that percept is inserted at the cursor (or, if the manuscript
is empty, a new paragraph is opened with the chip leading it).

A quieter second affordance: each row in the existing percept list
(`DifferentialWorkspace.jsx:795-804`) gains a **"write from this"** action, so an older percept can be
carried across without recomposing.

**What this is not:** not a new panel, not a modal, not a route. It reuses the exit that already
exists and the insertion path that already exists.

### A.3 Data needed

**None that is not already in hand.** The percept id (`pctx_…`), its `ground_ids`, and its
`expression` are all in the store at the moment of the click. The insertion path
(`PostDetailPage.jsx:683-697`, the `/percept` route) already builds a chip from exactly these.

### A.4 Files likely touched

`differential/DifferentialWorkspace.jsx` (two buttons, one callback prop) ·
`components/PostDetailPage.jsx` (accept an "arm this percept" intent on mode exit; reuse the existing
`/percept` insertion at `:683-697`) · CSS for the second button.

### A.5 Tests

Pure-module where possible; **component tests require the DOM environment stood up first** (§7).
- the armed-percept intent is cleared after insertion (no double-insert on a second mode switch)
- inserting an armed percept produces the **same** chip props as the `/percept` slash route — assert
  prop equality against the existing path, so the two can never drift
- arming a percept whose `ground_ids` are all detached still inserts (the percept is real; its
  evidence state is Part C's job, not a gate on writing)

### A.6 Must remain non-causal / non-authoritative

- **The handoff asserts nothing about the percept's quality.** It carries; it does not endorse.
- **It must not auto-write prose.** The chip is inserted; the sentence is the curator's.
- **It must not mark the mention as "interprets"** or any relation the curator did not perform.

### A.7 Rollback

Delete the two buttons and the intent field. **No persisted data is created by Part A**, so revert is
stateless and leaves the corpus indistinguishable.

---

## Part B — Make the chip carry percept identity honestly

### B.1 Current code path

`PostDetailPage.jsx:694` — a `/percept` chip's `data-region-ids` are **the percept's GROUND ids**, so
`mentionsFromBlocks` (`perceptMentions.js:154-170`) manufactures Mentions with `regionId: 'gnd_…'`.
`data-mention-id` is **write-only** — producers only, zero consumers — and its insert-time value can
**never** match a reconstructed Mention after one reload (`perceptMentions.js:94-96`). The
reconstruction reads **only** `data-region-ids`, dropping `data-percept-id`, form and relation type;
so `relationType:'interprets'` / `actor:'sutradhar'` written at `PostDetailPage.jsx:593` become
`'cites'`/`'human'` **on every page load**.

**The provenance chain `perceptMentions.js:18-19` promises is broken at the Mention link.**

### B.2 Proposed UX

**Invisible in the happy path — this is a correctness change with one visible consequence.**
The visible consequence: a passage written by the model stops reading as the curator's own sentence
(`data-origin` is stamped at `PostDetailPage.jsx:1194-1206` and has **zero CSS rules**).

### B.3 Data needed

Nothing new persisted. **Make the reconstruction lossless** — read the attributes already in the
markup (`data-percept-id`, `data-mention-id`, `data-inline-type`) instead of `data-region-ids` alone.
This is open-decision §4 branch **(b)**, chosen because it is bounded, reversible, fixes a promise the
code already makes, and **buys the information a durable Mention would need** — the corpus has **0
text blocks**, so there is no citation data and no evidence yet of how curators actually cite.

### B.4 Files likely touched

`state/perceptMentions.js:154-170` (the parser) · `components/blocknote/regionRefInline.jsx` (ensure
every producer emits what the parser now reads) · one CSS rule for `[data-origin="sutradhar"]`.

### B.5 Tests

`perceptMentions.test.js` extends cleanly (pure module, environment already works):
- a `pctx_` chip round-trips its **percept id**, not just its region ids
- `form` and `relationType` survive a store round-trip — **today they do not, and the loss is untested
  rather than accepted**
- `mentionId` is **stable** across insert → serialise → reconstruct
- a `/percept` chip does **not** manufacture a Mention whose `regionId` is a `gnd_` id

### B.6 Must remain non-causal / non-authoritative

- **Do not persist Mentions in this slice.** That is open-decision §4(c) and is deliberately deferred.
- **Do not infer `relationType`.** If the markup does not carry it, it is `cites` — and the test
  should assert that default explicitly rather than let it be a silent fallback.
- `data-origin` styling must be **quiet** — a mark of authorship, not a warning badge.

### B.7 Rollback

Revert the parser and the CSS rule. **Markup already in the corpus is unaffected either way**, since
the change is read-side.

---

## Part C — Recall that tells the truth, on both surfaces

### C.1 Current code path — the single highest-value fix in the slice

`recall.js:164-168` computes
`"Detached evidence — none of the N cited grounds still resolves."`
`RegionSurface.jsx:330-332` renders `recallPlayer.caption` **and not `evidenceNote`**. The **only**
render site for `evidenceNote` in the entire frontend is `DifferentialWorkspace.jsx:547-549`.

**The honesty machinery exists, is computed on this very code path, and was wired into one surface of
two.** The fix is *a conditional render of a value already in hand.*

Three further silent failures on the click path:
- **dead `/part` id** — `focusRegions` sets `selectedId` with no existence check
  (`regionStore.js:272-277`); `RegionOverlay.jsx:32-33` then dims **every** region and lights none,
  while the panel expands and the pane scrolls. **Full choreography pointing at nothing, no message.**
- **percept absent from the store** — script is null, nothing plays, but `regionRefInline.jsx:65-67`
  lights the chip because `store.recall.perceptId` matches. **The chip asserts "I am being replayed"
  over a no-op.**
- **lens regions replaced** — `AletheiaHook.jsx:105-106` filters to `[]`; the explanatory hint at
  `:160-165` is guarded by `regions.length > 0`, so it **never appears**.

Plus an arithmetic bug: `unresolved` collects expanded members while `citedCount` counts only
`ground_ids`, so the note can print **"2 of 1 cited grounds"**; and a composite ground whose members
are *all* detached is `detached: false` (`grounds.js:81`), so it gets a timed step that draws nothing
— **pre-A2R behaviour, one ground type deeper.**

### C.2 Proposed UX

**Degradation-only, and quiet.** Nothing changes when evidence is healthy — no green ticks, no
"verified" badges. When it is not:

- recall in the **Manuscript** shows the same one-line note Differential already shows;
- a dead `/part` chip click shows a brief inline line — *"this part is no longer in the image"* —
  **and does not dim the image**;
- a chip that cannot play **does not light**;
- the lens hint stops being guarded by a condition that makes it unreachable exactly when needed.

**No badge on healthy chips. No panel. One line, at the moment of failure, where the failure happens.**

### C.3 Data needed

Nothing new. All of it is `resolveGround` (`grounds.js:68`) and the existing player. The composite and
arithmetic fixes are pure-module.

### C.4 Files likely touched

`components/RegionSurface.jsx:330-332` (the headline) · `differential/recall.js` (arithmetic;
composite resolution) · `differential/grounds.js:81` (composite detachment — **extend by addition;
four tests pin the current behaviour**) · `state/regionStore.js:272-277` (existence check) ·
`components/blocknote/regionRefInline.jsx:65-67` (do not light a chip that cannot play) ·
`components/AletheiaHook.jsx:160-165` (unguard the hint).

### C.5 Tests

Pure-module (works today): composite-all-detached resolution; the `citedCount` arithmetic; a percept
absent from the store yields an inactive player.
DOM (needs §7): `evidenceNote` renders in the writing surface; a dead `/part` chip does not dim the
image.

### C.6 Must remain non-causal / non-authoritative

- **Never state a cause.** `DifferentialWorkspace.jsx:815`'s *"its part was replaced by a re-dissect"*
  must go — `resolveGround` knows only that the id is missing. The project's own causal-language guard
  (`visionActivity.js:164-171`) already exists for the Rail; **this extends its discipline, it does
  not invent it.**
- **Never mark a percept invalid.** Evidence can be gone and the noticing still true; that is the
  premise `grounds.js:5-7` was built on.
- **Do not add `suspect` here.** It is designed in P0.5 §4.2 and deliberately **not built** in P1 —
  it needs a captured `geometry_rev`, which is a persisted change.

### C.7 Rollback

Every item is render-side or pure-derivation. Revert the diff; **no stored byte differs.**

---

## Part D — The Circulation Thread panel

### D.1 Current code path

Nothing exists. The nearest relatives: `VisionActivityRail` (which renders a *run's* stages and whose
derived `stages[].adapter` is **never rendered**, `visionActivity.js:247` vs
`VisionActivityRail.jsx:79-87`) and the percept list at `DifferentialWorkspace.jsx:795-804`.

### D.2 Proposed UX

**A single collapsed line under a selected percept**, expanding to the thread. Not a new surface — it
lives in the space the percept row already occupies.

```
◈ "the upper head"                                    formed · 2 cited · in writing · recalled
   ├─ formed          in Differential                              [record]
   ├─ cited           2 grounds — 1 no longer resolves             [record + judgement]
   ├─ referenced      1 passage                                    [record]
   ├─ recalled        played from the manuscript                   [record]
   └─ inferred        —                                            [absent]
```

**The four judgement relations render in a visibly different voice from the five records** (P0.5 §4.3).
`inferred` shows `—` until Perceptive Orchestration exists — **an honest empty rung is better than a
hidden one**, and it is how the product says what it cannot yet do.

**Degradation-only still applies to the collapsed line:** it summarises, and only mentions a
non-nominal state when there is one.

### D.3 Data needed

Four of the five rungs are **derivable now**: `formed` (the percept exists), `cited`
(`ground_ids` + `resolveGround`), `referenced` (`blockIdsForRegion` /
`PostDetailPage.jsx:744-756`), `recalled` (a client-session flag).

**`recalled` is session-only and must be labelled as such** — nothing persists it, so the thread must
say *"this session"*, not imply history. `inferred` needs the `run_id` that no entity carries (P0 §5);
it renders as absent.

### D.4 Files likely touched

A new pure module `differential/circulationThread.js` (derivation) · a small component beside the
percept list · `DifferentialWorkspace.jsx:795-804` (mount point).

### D.5 Tests

Pure-module, fully testable today: each rung derives correctly from a fixture store; a percept with no
mention shows `referenced: absent` and **not** a zero-count that reads as a claim; a detached ground
produces `cited` with a judgement, **never a cause**.

### D.6 Must remain non-causal / non-authoritative

- **This is the document's most dangerous component.** A thread implies a story, and a story implies
  causes. It must render **what is recorded and what is derived**, and nothing else.
- **`challenged` is not in P1.** It is the one relation a model may never author, and there is no
  human affordance for it yet — shipping it empty would invite it to be filled by inference.
- **No timestamps that imply order beyond what is known.** Nothing carries a `run_id`; the thread must
  not imply a sequence it cannot evidence.

### D.7 Rollback

Delete the module and the mount. **Pure derivation, nothing stored.**

---

## Part E — Humane labels over stable operations

### E.1 Current code path

`HW-C9-find-parts-rename-spec.md`: **12 display strings verified with zero line drift, 37 frozen
identifiers**, four places the label does not slot in grammatically. `HW-C10-ui-proposal-sequencing.md`
decided **B ships first, alone; increment C's step 6 is struck permanently.**

### E.2 Proposed UX

UI says **`Find parts`**. Backend stays `dissect` — `OPERATION_DISSECT`, all `STAGE_*`, routes,
payload keys, DB fields, telemetry ids **frozen**.

**The rule this establishes for the whole product, and it generalises past this rename:**
> **operation names are wire identity; labels are curator-facing and may be rewritten freely.**

Docs must carry that separation explicitly, so the next label change does not re-litigate it.

### E.3 Files, tests, risk

4 frontend files, values only. **Key-integrity test, not a copy test** — assert
`Object.keys(OPERATION_LABEL/EPISTEMIC/AFFECTS)` each equal `OPERATIONS` and all fourteen `dissect.*`
`STAGE_LABEL` keys are present. **Do not assert on display copy**: it would freeze the copy this
change is unfreezing.

**Risk:** over-application into a wire identity — the 14 keys must match the backend exactly or every
stage degrades to the `humanStage` fallback. **No existing test catches a wrong label** (one grep hit,
and it is a comment).

### E.4 Rollback

Single `git revert`; stateless. Completeness check is an empty `git diff` — counts can coincide, an
empty diff cannot.

---

## Part F — External-claim awareness, lightly

### F.1 Current code path

`semantic_pass.py:104` — the **global reading has no id**, so `enforce_candidate_ids` cannot reach it.
Live instance: post `6a5b91fb…9a4` stores a full confident image-level reading with
`dropped_ids: ["1","2","1","2"]` and **0 assertions**. **4 of 6 text-block write paths omit `origin`.**

### F.2 Proposed UX — deliberately minimal

**One CSS rule and one defaulting fix.** `data-origin` is already stamped, schema-rescued
(`post.py:80-83`) and test-pinned (`blockConvert.test.js:111`) — and rendered as an invisible
attribute. Style it quietly; supply `origin` on the paths that omit it.

**No ledger, no taxonomy, no entity.** `HW-C5` §4.4 explicitly forbids citing the ledger's shape as a
design proposal — its columns were chosen to be *recordable*, not *modellable*, and `frame-silent`
deliberately merges two things a product would need to distinguish. **Making authorship visible is not
adopting the ledger.**

### F.3 Must remain non-causal / non-authoritative

- **Never label a model's sentence false.** The distinction is *who wrote this*, not *is this true*.
- **Do not surface `dropped_ids` to curators** in P1. It is a real signal and it is a research signal;
  productising it needs its own gate.

### F.4 Rollback

One CSS rule and one default. Trivial.

---

## 7. Preconditions, sequencing, and honest cost

**Precondition for Parts A, C(DOM), D(mount):** a **DOM test environment**. There is none today — no
jsdom, no testing-library, vitest defaults to `node`, **zero component tests**. Every UI finding in P0
ships green. **This is costed here, not hidden**, and it is the single largest line item in the slice.

**Suggested internal order** (each independently revertible):

| # | part | why here | needs DOM env? |
|---|---|---|---|
| 1 | **C** (pure-module half) + **B** | highest value per risk; both are pure modules with working tests. **`evidenceNote` alone justifies the gate** | no |
| 2 | **E** | independent of everything; hours not days | no (key-integrity test) |
| 3 | *stand up DOM env* | precondition | — |
| 4 | **C** (render half) + **A** | the artery, once its failure modes can be tested | yes |
| 5 | **D** | derives from everything above | yes for the mount |
| 6 | **F** | trivial, any time | no |

**What is explicitly NOT in this slice:** `suspect` (needs persistence) · durable Mentions (§4(c)) ·
Perceptive Orchestration (no operation path exists) · Atlas · Codex · any `run_id` plumbing · the
announcement-only merge fix (**authorized but not scheduled**, `HW-C9`) · any repair of production
data, id migration or backfill.

---

## 8. Global rollback

**No persisted data is created by any part of this slice.** Every change is render-side, pure
derivation, a read-side parser, or a display string. A full revert leaves the corpus **byte-identical**
to a world where P1 never ran — which is the property that makes it safe to try.
