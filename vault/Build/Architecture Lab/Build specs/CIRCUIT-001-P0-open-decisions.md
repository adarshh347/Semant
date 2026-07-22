# CIRCUIT-001 P0 — Open decisions

**DECISION REGISTER — nothing here is decided by this document.** Each item states the fork, the
evidence, what each branch costs, and what would settle it. No implementation is authorized. No
source file was edited.

Rests on `CIRCUIT-001-P0-product-circuit-map.md` and `CIRCUIT-001-P0-build-sequence.md` (same cycle).

**Ranked by how much else is blocked on them.**

---

## 1. Stable evidence identity — **the root decision**

**The fork.** Region ids are per-run positional ordinals (`vision_service.py:513` `region_{i}`, and
the `seg_`/`fine_`/`arch_`/`fseg_` families). Every downstream fragility traces here. Three branches:

- **(a) Leave ordinals, detect substitution at the boundary.** HW-C6's Option D, plus HW-C9's
  authorized-but-unscheduled announcement. Cheapest; does not fix references, only reports.
- **(b) Content-address new ids** (mask hash or uuid, as `refine_*` already does at
  `adapters.py:191`). Fixes the future, leaves the corpus mixed, and **`adapters.py:191`'s
  `base_id or …` means a refine *keeps* the base's ordinal — so this branch must change that line or
  it does nothing.**
- **(c) Version references rather than ids** — a prose chip carries `geometry_rev` or a checksum and
  can say *"my region changed"* instead of resolving blindly.

**What the audit adds.** *The dangerous case is not the dead reference — it is the live one.* A
re-dissect producing the same number of regions gives every `/part` chip a resolving id, a stale
label, and a confident highlight of the wrong part, **with no signal anywhere**. Branch (a) does not
touch this. **Only (c) does.**

**Also new:** refine-in-place **destroys meaning while preserving identity**
(`posts.py:1233-1243`, `adapters.py:190-204`; all 6 creator regions have `label: null`). Identity
stability alone would not have prevented it.

**Cost of deciding wrong:** (b) and (c) are migrations; (a) is two integers.
**What would settle it:** measure how often region *count* is stable across re-dissects on the same
post. If counts are usually stable, the live-but-wrong case is common and (c) is mandatory. **Nobody
has measured this and it is cheap to measure.**

**Recommendation: do not decide yet.** P1 is deliberately branch-agnostic — it *reports* health under
any of the three. Decide after P1 exists and after the count-stability measurement.

---

## 2. The announcement-only merge-boundary fix

**Status: AUTHORIZE WITH CONDITIONS, not scheduled** (`HW-C9-announcement-only-merge-fix.md`).
Authorized: `suppressed_by_id` + `suppressed_by_geometry` counters in the existing
`STAGE_MERGE_CURATOR` detail, classified by the **existing `_region_box_iou`** (box IoU only —
the probe's proposed *mask* comparison was **not** announcement-only: `rle_decode` is a per-pixel loop
that can raise inside a live route, and 32 of 51 auto regions have no mask at all).

**What is still open** is only *when*. HW-C9 said ride-along or on a re-dissect of an exposed post.

**What the audit adds, and it strengthens the case slightly:** HW-C9 scoped this to the id guard at
`:804`, which covers **2** curator regions. The **auto→auto branch at `:809-819, 832` re-points an
ordinal onto a new mask and counts it in `kept_auto` as an ordinary survivor** — covering the
**51-region** auto population. **The larger exposure is the uninstrumented one.**

**Decision needed:** whether the authorized counters should extend to the auto→auto branch. That is
still arithmetic and still cannot raise, so it does not change the safety verdict — but it does
change what the number means. **Recommend: yes, and say so before it is built, not after.**

---

## 3. External claims beyond the markdown ledger

**Status.** The ledger is adopted, amended twice (`HW-C5` §9 cycle 7; `HW-C8` cycle 8) and is
**markdown-only, in rehearsal artifacts**. `HW-C5` §4.4 explicitly forbids citing its shape as a
design proposal, and §3.4 rejects a schema field because `additionalProperties: false` makes an
optional field indistinguishable from absent.

**What the audit adds — and it changes the question.** Until now this was a *rehearsal recording*
question. The map shows the phenomenon **in production**:

- the global semantic reading **has no id**, so `enforce_candidate_ids` cannot reach it
  (`semantic_pass.py:104`); live instance `6a5b91fb…9a4` stores a full confident image-level reading
  with `dropped_ids: ["1","2","1","2"]` and **0 assertions**;
- **4 of 6 text-block write paths omit `origin`**, so model prose reads back as human;
- `data-origin` is stamped and **has zero CSS rules**, so AI prose is visually identical to the
  curator's.

**The fork.** (a) keep it rehearsal-only; (b) make *provenance* durable in production without
adopting the ledger's taxonomy; (c) build the ledger as an entity.

**(c) is the trap `HW-C5` §4.4 warns against** — its columns were chosen to be *recordable*, not
*modellable*, and `frame-silent` deliberately merges two things a product would need to distinguish.

**Recommendation: (b), and it is nearly free.** Rendering `data-origin` is **one CSS rule**, and
supplying `origin` on the 4 paths that omit it is a defaulting fix. **Neither adopts the ledger's
taxonomy.** Do not conflate "the reader can see the model wrote this" with "Semant has an
external-claim entity."

---

## 4. The durable Mention — **the pivot for everything after P3**

**The finding, definitive** (map §1): a Mention is **reconstructed**, by regex over block HTML, on
every load (`regionStore.js:112` → `perceptMentions.js:154-170`). There is no mentions field, model,
route or collection in the backend. The reconstruction drops the percept id, the mention id, the form
and the relation type; `data-mention-id` is **write-only** (producers only, zero consumers); and the
insert-time id can **never** match a store Mention after the first reload.

Consequently `relationType: 'interprets'` / `actor: 'sutradhar'` become `'cites'` / `'human'` on every
page load — **the provenance chain `perceptMentions.js:18-19` promises is broken at the Mention
link**, and the only surviving AI signal is `TextBlock.origin`, which is not rendered.

**`HW-S2` §7 already named this as the single object Atlas and Codex both depend on.**

**The fork.**
- **(a) Leave it reconstructed.** Honest about what it is; today nothing would behave differently if
  the mention array were deleted on load, *except* `blockIdsForRegion` — which is already shadowed by
  an independent regex at `PostDetailPage.jsx:744-756`. **The cheapest branch, and it permanently
  forecloses "where else is this percept cited?"** without parsing every block of every post.
- **(b) Make the markup lossless** — reconstruct *all* fields rather than one attribute. No schema
  change, no backend. Fixes provenance; does **not** make citation queryable across posts.
- **(c) Persist Mentions.** Makes cross-post citation answerable; a real entity, a real migration, and
  the thing `HW-S2` §5 lists as dangerous to crystallise early.

**A fact that should temper (c):** the corpus has **0 text blocks**. There is no citation data to
migrate, and no evidence of how curators actually cite, because nobody has yet.

**Recommendation: (b) now, defer (c).** (b) is bounded, reversible, fixes a broken promise the code
already makes, and **buys the information (c) would need** — once blocks exist, their markup will
show what people actually cite.

---

## 5. Atlas — materialized view or store

**Recommend: materialized view. This one is close to settled and should be written down as such.**

Three independent sources agree: the Infrastructure Lexicon (*"could be a materialized view rather
than the authoritative source"*), the bridge doc (Codex recurrence as *"a query over Mentions, not a
stored object"*), and `HW-S2` §1, which argues the evidence pushes **harder** than the prose: *an
arrangement over objects whose evidence can silently vanish should not be the place where truth is
stored.*

**The honest caveat that must travel with it:** `HW-S2` records that **no rehearsal in R0–R2 tested a
cross-image surface at all.** The evidence tells us what an Atlas would have to *survive*; it says
**nothing about whether one is needed.** Deciding "view, not store" is not a decision to build one.

**What would overturn it:** a demonstrated query that a view cannot answer at acceptable cost.
None exists, because there is nothing to query.

---

## 6. Codex — temporal accountability or writing container

**Recommend: temporal accountability, and defer the whole thing.**

`HW-S2` §2: Codex's animating idea has moved from long-form container to *the layer at which change
over time is answerable*; the multi-page editor is *"the least interesting part and the most easily
imitated."*

**The blocking fact is now doubled.** `HW-S2` said Codex's only load-bearing dependency — a citation
that survives — is the thing demonstrated to be fragile. The map makes it literal: **the citation
record is a `<span>` inside `text_block.content`.** And a second gap the audit names: there is **no
record that evidence was destroyed**, only that an id no longer resolves — which cannot distinguish a
re-dissect from a never-existed id from a typo.

**A temporal-accountability Codex needs both.** Neither exists. **Do not open.**

---

## 7. Should `Find parts` ship before evidence-health UI?

**Recommend: no — but it is not blocked, and the reason matters.**

`HW-C9`'s spec is complete and `HW-C10` sequenced it: **B ships first, alone; C's step 6 struck.** It
touches no evidence path, has 12 verified strings, 37 frozen identifiers, and a clean rollback. **On
its own merits it is ready today.**

The argument for P2 first is **not** risk — it is that both changes touch the same surfaces, and
`HW-C10` already found one collision between two UI proposals. Doing the truthfulness work first
means the naming work lands on surfaces that have stopped lying, rather than renaming a control whose
neighbouring caption asserts evidence that does not exist.

**The counter-argument, which is real:** P2 needs a DOM test environment stood up first, so it is
weeks not days; `Find parts` is hours. **If the user wants a visible win early, (a) is the correct
one to take** — and this document should not pretend otherwise.

**Either order is defensible. What is not defensible is shipping C** (profile vocabulary) before its
honesty precondition is written — see §8.

---

## 8. Does the Aletheia saver simplification belong in P3?

**Recommend: yes, and it is the strongest item in P3 on value-per-risk.**

`HW-C8` §A resolved the crux: **content type is already in hand at the decision point.**
`showTarget(el, type)` receives `type` (`content.js:465`) and already calls `findCarousel` (`:480`),
so single/carousel/video → Save / Save all / Split needs **zero detection and zero plumbing**. The
smallest gate touches `content.js` + `content.css` only, ~10 lines, **reparenting the four existing
button objects rather than merging them** — no handler and none of the eleven `textContent` state
writers.

**Two caveats to carry:** the extension is inconsistently branded *"Alexia"* vs *"Aletheia"*, and the
comments at `:25`/`:130` promise a summon shortcut **that does not exist**. Neither blocks the change;
both should be fixed or explicitly deferred in the same gate rather than left to accumulate.

**One reason it might *not* belong in P3:** it is the only item in the sequence that touches the
**Chrome extension**, which has its own permission surface, its own release path, and **no test
environment whatsoever**. If P3 is meant to be a single coherent gate, this is a different codebase
wearing the same phase number. **Splitting it into its own gate is defensible and probably cleaner.**

---

## 9. Two decisions the gate did not ask for, surfaced by the audit

**9.1 Should Home stop calling detector output "percepts"?** `homeData.js:43-45` returns
`region_annotations` verbatim under *"Parts you recently noticed"*, *"N percepts · M words"*. The
store's stricter rule lives twelve files away (`regionStore.js:113-117`). **Two definitions of the
product's central noun are live in one frontend**, and the tile named "Percepts" is the only surface
that cannot display one. `WeekTile.jsx:23` compounds it: one re-dissect on an old post can add forty
*"percepts marked"* to the week. **This is a truthfulness bug, not a naming preference, and it is
arguably P2 scope rather than P3.**

**9.2 Should the only unavailability signal in the product stop failing open?**
`ProfileControl.jsx:28-33` swallows a capabilities failure with `.catch(() => {})`, then `:68`
defaults `passState` to `'ready'`. `HW-C8` §C2 identified these pills as *the only place in the UI
where an unavailable model is surfaced at all*. **It fails open.** Small, self-contained, and it is a
**precondition for P3(c)** — a quieter vocabulary over an unreliable signal makes the unreliability
harder to see, not easier.
