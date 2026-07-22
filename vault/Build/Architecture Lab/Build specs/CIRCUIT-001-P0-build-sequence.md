# CIRCUIT-001 P0 — Build sequence

**PLAN ONLY — NOTHING HERE IS AUTHORIZED TO BE BUILT.** No source file was edited. Each phase below
is a *proposed* gate; opening one requires an explicit instruction. Rests on
`CIRCUIT-001-P0-product-circuit-map.md` (same cycle) and on the cited HW findings.

**The ordering principle**, and it follows from the audit rather than from taste:

> The circuit's model of evidence is already correct. What is missing is that the system **computes
> the truth about its own evidence and does not show it**. So the sequence goes: make the truth
> *legible to code* (P1) → make it *visible to the reader* (P2) → make the surfaces *stop lying in
> smaller ways* (P3) → and only then consider new surfaces (P4, P5).

**A constraint that binds every phase from P2 onward:** there is **no DOM test environment** — no
jsdom, no testing-library, vitest defaults to `node`, zero component tests. **Every UI finding in the
map ships green today.** Standing up that environment is a precondition of P2, not a nice-to-have,
and is costed there rather than hidden.

---

## P1 — Evidence health projection

**Goal.** Give the codebase **one function that answers "is this citation still good?"** for every
kind of reference, and one derived object a surface can ask for cheaply. Today `resolveGround`
(`grounds.js:68`) answers it for grounds only, needs the full `regions` + `grounds` arrays, and has
**no analogue for a lens or a bare region reference** — which is precisely why the recall click fails
silently in three of four cases.

**This is a projection, not a store.** It derives from state already hydrated. **No schema change, no
collection, no migration, no persisted field.**

| | |
|---|---|
| **files likely touched** | `frontend/src/differential/grounds.js` (extend, do not rewrite); a new pure module beside it, e.g. `evidenceHealth.js`; `frontend/src/differential/recall.js` (consume); `regionStore.js:112-118` (expose) |
| **backend scope** | **none.** P1 is deliberately frontend-only and derivation-only |
| **frontend scope** | pure functions + one derived selector. **No component may be edited in P1** — that is P2 |
| **tests required** | pure-module vitest, which already works. Resolution for: a region ref that resolves; one that does not; a lens with 0/some/all resolving; a percept whose grounds are partly and wholly detached; a percept absent from the store; a composite ground **all of whose members are detached** (today `grounds.js:81` reports `detached: false` and a step is emitted that draws nothing); and the `citedCount` arithmetic that can currently print *"2 of 1 cited grounds"* |
| **risks** | (1) **Scope creep into repair.** P1 must only *report*. (2) **The hydration flicker HW-S1 E1 named** — if resolution transiently reports detached during load, any consumer will flicker; P1 must expose a `loading` state rather than a false `detached`. (3) Extending `resolveGround` risks breaking the 4 tests that pin it — extend by addition, never by edit |
| **non-scope** | no UI, no backend, no `run_id`, no id migration, no repair of the 2 exposed `seg_0` regions, no announcement-only merge fix (that is authorized-but-unscheduled per `HW-C9`) |
| **stop condition** | the module answers all six test cases above, the existing suite is green at ≥60 backend / ≥96 frontend, and **nothing renders differently**. If a rendered pixel changes, P1 has overrun |

---

## P2 — Chiasm / Differential evidence-health UI

**Goal.** Render what P1 computes. The headline item is the smallest and most valuable change in the
whole sequence: **`RegionSurface.jsx:330-332` renders `recallPlayer.caption` and drops
`evidenceNote`**, which is computed on that very code path and has exactly one render site in the
frontend (`DifferentialWorkspace.jsx:547-549`). *The fix is a conditional render of a value already
in hand.*

Then, in order of value: the four silent recall-click failures; `RefPicker`'s overstating badges
(HW-S1 **E2**); the detached ground still offered for "Compose a percept"
(`DifferentialWorkspace.jsx:747`); the invented cause at `:815`.

| | |
|---|---|
| **files likely touched** | `RegionSurface.jsx:330-332`; `DifferentialWorkspace.jsx:731-747, 768-790, 815`; `RefPicker.jsx:43-62`; `partRefBlock.jsx:24-35`; `regionRefInline.jsx:65-85`; `AletheiaHook.jsx:160-165`; **plus `vitest.config` + a jsdom/testing-library dev dependency** |
| **backend scope** | **none** |
| **frontend scope** | render-only, consuming P1. No new fetches, no new state shape |
| **tests required** | **stand up the DOM test environment first.** Then component tests for: `evidenceNote` renders in the writing surface; a dead `/part` chip shows a message rather than dimming the image; a percept chip with a missing percept does **not** light; `RefPicker` badges show resolving counts. Per `HW-C10` §5, **do not assert on display copy** — assert on presence/behaviour and on key integrity |
| **risks** | (1) **The flicker** — the reason HW-S1 E1 said "killed by a race"; mitigated by P1's `loading` state, but this is the phase where it will actually bite. (2) **Over-announcing.** Five badges saying "degraded" turns honesty into noise; the map's §8 records that degradation-only display is the established discipline — announce **only** non-nominal states. (3) Standing up jsdom may surface pre-existing failures in modules that currently never render |
| **non-scope** | no naming changes (that is P3), no new panel, no history view, no backend telemetry, no repair |
| **stop condition** | every failure case in map §6 either shows an honest state or is explicitly deferred **in writing**; DOM tests exist and pass; no copy is frozen by a test |

---

## P3 — UI naming and action polish

**Goal.** Three already-specified, bounded items. **All three are fully specified and none is
authorized.**

**(a) `Dissect` → `Find parts`.** Spec complete at `HW-C9-find-parts-rename-spec.md`: 12 display
strings verified with zero line drift, 37 frozen identifiers, four places the label does not slot in
grammatically, and a rollback. Sequencing decided at `HW-C10-ui-proposal-sequencing.md`: **B ships
first, alone; increment C's step 6 is struck permanently.** Note `?operation=dissect` leaves the
browser as a query value (`visionActivity.js:36`) — "no route change" holds, "stays client-side" does
not.

**(b) Aletheia saver simplification.** `HW-C8` §A: the whole overlay is `chrome-extension/content.js`;
**content type is already in hand at the decision point** (`showTarget(el, type)` at `:465`, which
already calls `findCarousel` at `:480`), so single/carousel/video → Save / Save all / Split needs
**zero detection or plumbing**. Smallest gate: `content.js` + `content.css`, ~10 lines, **reparenting
the four existing button objects rather than merging them**.

**(c) Quieter profile vocabulary.** **Blocked, and correctly so.** `HW-C10` §3.2 records its single
unmet precondition — the `pc-reason` honesty sentence — as still unwritten. The map adds a *new*
reason: `ProfileControl.jsx:28-33, 68` **fails open to `ready`**, so the only unavailability signal
in the product is unreliable. **Fix the fail-open before renaming anything**, or the quieter
vocabulary will make an unreliable signal look calmer.

| | |
|---|---|
| **files likely touched** | (a) 4 frontend files, values only · (b) `chrome-extension/content.js` + `.css` · (c) `ProfileControl.jsx` |
| **backend scope** | **none.** `OPERATION_DISSECT`, all `STAGE_*`, routes, payload keys and DB fields stay frozen |
| **tests required** | (a) **key-integrity test, not a copy test** — `Object.keys(OPERATION_LABEL/EPISTEMIC/AFFECTS)` each equal `OPERATIONS`, and all fourteen `dissect.*` `STAGE_LABEL` keys present. Plus grep arithmetic and eyes-on. (b) manual, plus a screenshot. (c) a test that a capabilities failure does **not** render `ready` |
| **risks** | (a) over-application into a wire identity — the 14 `dissect.*` keys must match the backend exactly or every stage degrades to the `humanStage` fallback. **No existing test catches a wrong label** (one grep hit, and it is a comment). (b) dialog/permission surface in the extension. (c) **making the UI say something untrue** — not choosing a profile means those regions *don't exist*, not that they are hidden |
| **non-scope** | no backend rename, no route change, no redesign, no change to `Chiasm`/`Differential` naming, and **C does not ship** until its precondition is written |
| **stop condition** | (a) grep counts match the spec and both suites plus `npm run build` pass · (b) the two-slot bar works on all three content types, screenshot-verified · (c) **not started** unless explicitly authorized |

---

## P4 — Atlas Evidence Ledger prototype

**Goal.** The *narrowest honest* cross-image surface: **"what has happened across everything?"** —
per `HW-S1`'s dividing line, which the map endorses: existing surfaces answer *"is what I'm looking at
real?"*; Atlas answers the cross-corpus question. Anything failing that test belongs in
`RegionSurface`, `RefPicker` or the recall path — i.e. in P2, not here.

**Atlas as a materialized view, not a store** — the vault's own Infrastructure Lexicon already says
so, and `HW-S2` §1 argues the evidence pushes harder than the prose: *an arrangement over objects
whose evidence can silently vanish should not be where truth is stored.*

**Precondition, and it is hard:** `HW-S2` §7 states that the single object Atlas and Codex both depend
on — **the Mention — has no durable form at all**, and the writing lane confirmed it definitively
(map §1). **P4 cannot begin before the durable-Mention decision in
`CIRCUIT-001-P0-open-decisions.md` §4 is taken.**

| | |
|---|---|
| **files likely touched** | unknown until the Mention decision; **a read-model/query path, not a collection**, if it proceeds |
| **backend scope** | possibly one read-only aggregation route. **No new collection. No write path. No migration** |
| **frontend scope** | one throwaway surface, per `HW-L2-atlas-codex-prototype-brief.md` |
| **tests required** | the aggregation's honesty: a node whose evidence is gone must be able to say so |
| **risks** | **the theatrical failure the user named.** An Atlas built now would industrialise the exact failure the rehearsals found — a citation outliving its grounding — across images instead of within one. `HW-S2`'s honest caveat also binds: **no rehearsal in R0–R2 tested a cross-image surface at all**; the evidence says what an Atlas would have to *survive*, not that one is needed |
| **non-scope** | no graph, no arrangement-as-prompt, no generative framing, no `Atlas` entity |
| **stop condition** | **do not open** until (1) the Mention decision is taken and (2) P1+P2 have shipped, so the surface has a health signal to display |

---

## P5 — Codex temporal accountability prototype

**Goal.** Codex's centre of gravity has moved from *long-form container* to **the layer at which
change over time is answerable** (`HW-S2` §2). The multi-page editor is the least interesting part and
the most easily imitated.

**The blocking fact, stated by `HW-S2` and confirmed by this audit:** Codex's *only* load-bearing
dependency — a citation that survives — is currently the thing demonstrated to be fragile. **A Codex
built on today's Mention would be a book whose footnotes are stored in the typography of its own
pages.** The map makes this literal: the citation record *is* a `<span>` inside
`text_block.content`.

| | |
|---|---|
| **precondition** | everything in P4's, **plus** a record that evidence was *destroyed*, not merely absent — today a re-dissect replaces the array and the previous ids leave no trace, so detachment cannot be distinguished from a never-existed id or a typo |
| **backend scope** | unknown; likely requires the temporal record P1–P4 deliberately avoid creating |
| **risks** | the largest premature-crystallisation risk in the vault (`HW-S2` §5) |
| **non-scope** | everything, for now |
| **stop condition** | **do not open.** Revisit only after P4 has run and the durable-citation question has an answer with evidence behind it |

---

## Sequencing notes

- **P1 → P2 is a hard order.** P2 without P1 means each surface reimplements resolution, which is how
  Home came to have its own wrong definition of "percept" (`homeData.js:43-45` vs
  `regionStore.js:113-117`). **Two definitions in one frontend is the failure mode to avoid
  repeating.**
- **P3(a) is independent and could ship at any time** — it touches no evidence path. It is placed
  after P2 only because P2 is worth more per unit risk, not because it is blocked.
- **P3(c) is blocked on writing one sentence**, and that sentence is a product-honesty decision, not
  a code task.
- **P4 and P5 are blocked on a decision, not on effort.**
- **The announcement-only merge fix (`HW-C9`) is authorized but NOT scheduled** and appears in no
  phase deliberately. It may ride along on work that already opens the merge block; it must not pull
  a phase open by itself.
- **What is deliberately absent from every phase:** any repair of production data, any id migration,
  any backfill, and any change to what is persisted about the 2 exposed `seg_0` regions.
