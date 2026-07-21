# HW-C9 — Should the announcement-only merge fix at `posts.py:804` be authorized?

**DECISION DOC — NO IMPLEMENTATION. No source file was edited; `backend/routers/posts.py`
remains exactly as found. No production data was read or written by this lane. Nothing was
staged, committed or pushed. No id migration, no backfill, no repair was performed or
authorized here.** Horizon Weave cycle 9, Lane 3.

| | |
|---|---|
| **id** | HW-C9 · rules on the fix proposed but not authorized at `HW-C8-auto-ordinal-curator-region-probe.md` §6 |
| **date** | 2026-07-22 |
| **status** | **Decided.** |
| **decision, in one line** | **AUTHORIZE WITH CONDITIONS — a counter-only announcement of merge-stage drops, narrowed to box-IoU classification with no mask decode, authorized for a later build gate but NOT scheduled: it may only be built as a ride-along on work that already opens the merge block, or on a measured trigger.** |
| **rests on** | `backend/routers/posts.py:788-839` and `:574-597` read in full this cycle; `backend/services/vision_orchestrator/adapters.py:59-84`; `backend/services/vision_service.py:505-520,640-652`; `backend/services/mask_geometry.py:88-125`; `backend/services/vision_orchestrator/vision_run_contracts.py:110-192,206-260`; `backend/services/vision_run_service.py:250-260`; HW-C8's whole-corpus measurement (2 exposed regions), HW-C6 §Option D, HW-C7 §4 |

*Fable-pass: the judgement, the re-framing in §2, the counter-argument in §6. Opus-pass: the
code grounding in §1 and §3.*

---

## 1. What the code actually does — OBSERVED, read this cycle

`backend/routers/posts.py:792-835`, the merge block, in execution order:

- `:793-798` — `existing_list` = the post's stored `region_annotations`; `existing` = the same
  keyed by id; `creator_regions` = every stored region with `actor == "creator"`, held as the
  **original dicts**; `creator_ids` = their id strings.
- `:803-805` — for each candidate: `if r.get("id") in creator_ids: continue`. A bare string-id
  match. No geometry is consulted.
- `:809-819` — carry of `prioritised` / `weight` / `user_note` from `prev`. (`:814-815`'s
  `if prev.get("actor") == "creator"` is unreachable: any such `prev` already `continue`d at
  `:804`. This confirms HW-C7 §4's dead-carry finding, independently, from the same lines.)
- `:822-823` — `canonicalize_geometry` for candidates that lack a provenance stamp.
- `:827-829` — `_is_duplicate_geometry(r, creator_regions, 0.7, require_same_kind=False)` — a
  **measured** drop, using `_region_box_iou` (`:574-582`), pure arithmetic on normalized boxes.
- `:832` — `regions = creator_regions + kept_auto`. **The creator dicts are carried through
  unmodified**, geometry included.
- `:833-835` — `rec.event(vrc.STAGE_MERGE_CURATOR, SUCCEEDED, detail={"creator_preserved": n,
  "kept_auto": n, "candidates": n})`.

**The asymmetry HW-C8 identified is real and is confirmed:** the name-match drop at `:804`
fires *before* the geometry dedup at `:827`, so a candidate named `seg_0` is discarded with no
comparison of any kind, while a candidate named `seg_1` sitting on the same pixels is discarded
only after a measured IoU. The drop with the least evidence behind it runs first.

**The telemetry gap is real and is worse than one missing counter.** `candidates` counts every
incoming region; `kept_auto` counts survivors; the difference is an unlabelled residual that
mixes *two distinct drop reasons* — the id guard at `:804` and the geometry dedup at `:827`.
Neither is named. A reader of a `dissect.merge_curator_state` event today cannot tell whether
a shrunken `kept_auto` means "the detector re-found what the curator already has" (correct,
uninteresting) or "a new detection was thrown away because its name was taken" (the hazard).

## 2. Does it serve spark-03? Yes — but not for the reason the probe gives

spark-03 is *evidence loss should be announced, not merely survived*. Tested against the code,
the probe's argument survives in part and **fails in one material part**, and the correction
narrows what is worth authorizing.

**What survives.** A drop at `:804` is a genuine, unannounced evidence loss. Something the
detector found in the image this run does not become a region and leaves no trace that it ever
existed. That is exactly the announce-vs-survive shape, and it is the shape at its purest: the
loss is not even *measured*, so it cannot be argued to have been considered.

**What fails — the citation argument.** HW-C8 §5 frames the exposed `seg_0` on
`695be8b0a9ea58f1b6aef606` (cited by ground `gnd_mrtof0k1_0` and percepts `pctx_mrtof46o_0` /
`pctx_mrtofp6b_1`) as a case of *"silent re-pointing of a curator's interpretation"*, and calls
it a ground that "still RESOLVES — to different geometry". **On this code path that is not what
happens.** `:804` `continue`s the *candidate*; `:832` carries the creator dict through verbatim.
The stored geometry named `seg_0` after the merge is byte-identical to the geometry named
`seg_0` before it. The ground resolves to the same mask it always did. **The id guard is the
thing protecting that citation, not the thing endangering it.**

Re-pointing — same id, different shape, ground silently redirected — is possible in this block,
but on the *other* branch: an auto candidate whose id matches an existing **auto** region does
not `continue`; it falls through `:809-819`, keeps the old id, brings its own new mask, and
replaces the stored region in `regions` at `:832`. **That** is the substitution HW-C6 Option D
was written about, and it is a different line, a different population (51 auto regions, not 2
curator ones), and a different decision. This lane does not decide it.

**Consequence for the verdict.** Because nothing is re-pointed on the guarded path, the question
"is announcement enough, or is something stronger owed?" answers itself: **announcement is
proportionate, and nothing stronger is warranted from this path.** The loss is of a *candidate
that was never cited by anything*, because it did not exist a moment earlier. There is no
curator claim silently redirected, no ground to repair, no geometry to migrate. The stronger
remedies HW-C8's open question floats (keep both under distinct ids; surface the divergence to
the curator) are product decisions about what a re-dissect owes a curator, and they belong to
whatever cycle takes up Option D proper — **not to a telemetry counter**.

## 3. Is it genuinely announcement-only? Not as written — as narrowed, yes

The probe's sentence is *"compare the candidate's **mask** against the creator region"*. Taken
literally that is **not** announcement-only. Three concrete objections, all from code read this
cycle:

1. **The mask is frequently absent on the candidate side.** `region_*` anchors
   (`vision_service.py:512-519`) and `fine_*` parts (`:645-652`) are emitted **box-only** — no
   `mask_rle` key at all. Only YOLO `seg_*` (`adapters.py:67-76`) carries an authoritative mask.
   In HW-C8's own corpus tabulation that is 32 of 51 auto regions (`fine_` ×26 + `region_` ×6)
   with no mask to compare. A mask comparison would silently degrade to "no opinion" on the
   majority of candidates — an announcement that is blank most of the time.
2. **Decoding is not free and the sizes need not agree.** `mask_geometry.rle_decode`
   (`:88-103`) is a pure-Python nested loop that writes one byte per set pixel; on the 451×680
   region HW-C8 enumerated that is up to ~3·10⁵ interpreter-level iterations per decode, two
   decodes per suppressed candidate. Worse, `rle_encode_mask` stamps `size` from the source
   array, so a fresh YOLO mask and a stored curator mask **can carry different `size`**, and
   `mask_geometry` has **no resampler** — there is no defined pixel-wise comparison between
   them. A hand-rolled one at `:804` would be new geometry code in a live route, which is not
   an announcement.
3. **It can raise.** `rle_decode` indexes `rle["size"][0]` and iterates `rle["counts"]`
   unguarded — a malformed or absent RLE raises `KeyError`/`TypeError` *inside the merge loop*,
   which is outside any telemetry try/except, and `detect_regions`' handler at `:882-887`
   would turn a telemetry improvement into a **FAILED run and a 500 on a route that works
   today**. `rle_is_valid` (`:106-120`) exists, but requiring a validity gate, a size check and
   a fallback is the admission that this is not a one-line announcement.

**The narrowing that makes it true.** `_region_box_iou` (`:574-582`) is already in the file,
operates on the normalized `box`, uses `.get(...)` defaults throughout, **cannot raise**, and is
`O(1)` arithmetic. Both sides always have a usable box: YOLO candidates are canonicalized at
`adapters.py:79` before they ever reach the router, VLM candidates are box-native, and all six
curator regions carry geometry. **The authorized comparison is box IoU, not mask pixels.**

**The telemetry side is already safe.** `detail` is free-form (`vision_run_contracts.py:222`),
passes `assert_bounded_payload` (`:153-192`) which caps depth/items/strings and rejects
geometry keys — integer counters are trivially inside those bounds — and `Recorder.event`
(`vision_run_service.py:250-260`) wraps `make_event` **and** the append in `try/except`, setting
`telemetry_degraded` rather than propagating. **A telemetry mistake in the added detail cannot
break the route.** The risk is entirely in the comparison, which is why the comparison is
capped at arithmetic that cannot throw.

## 4. The decision

### 4.1 Verdict

> **AUTHORIZE WITH CONDITIONS.**
>
> A **counter-only** announcement of merge-stage drops is authorized for a later build gate:
> classify each drop by reason, count them, and emit the counts in the existing
> `STAGE_MERGE_CURATOR` `detail`. Comparison is **box IoU via the existing `_region_box_iou`
> only** — no mask decode, no new geometry code, no new helper that can raise.
>
> **The gate is authorized but NOT scheduled.** Nothing in the program is blocked on it and it
> must not be built as a standalone errand (§4.4).

### 4.2 What exactly is authorized

At `backend/routers/posts.py:803-830`, telemetry only:

- Count candidates dropped by the id guard at `:804` → `suppressed_by_id`.
- Count candidates dropped by the geometry dedup at `:827` → `suppressed_by_geometry`.
  **This is a condition, not scope creep:** announcing only the id drops leaves the residual
  still ambiguous. With both, the merge event's arithmetic closes —
  `candidates == kept_auto + suppressed_by_id + suppressed_by_geometry` — and *that closure* is
  the announcement. One counter alone does not make the ledger readable.
- For id-guard drops only, classify by `_region_box_iou(candidate, creator_region)` against a
  single stated threshold, and carry the split as two integers (e.g. a same-place count and a
  different-place count). **The different-place count is the interesting number**: it means the
  detector found something *elsewhere in the image* and it was discarded for its name.
- Optionally, the dropped ids as a short bounded list of strings. Ids are not geometry and pass
  the payload gate; the list must be capped well under `MAX_PAYLOAD_ITEMS = 64`.

### 4.3 What is emphatically NOT authorized

- **No id migration.** `seg_0` on either exposed post is not renamed, re-keyed, or made stable.
- **No backfill, no repair, no clean-up** of the two existing curator regions, their grounds,
  their percepts or their embeddings.
- **No change to what is persisted.** The `$set` at `:846-847` writes the same `regions` list
  it writes today. The route response at `:873-875` is unchanged. **A run before and after this
  change must produce byte-identical `region_annotations`.** That is the acceptance test.
- **No change to merge behaviour.** The `continue` at `:805` still fires. Nothing that is
  dropped today is kept tomorrow. No new region is created, none is renamed, none is retained
  under an alternate id.
- **No mask decode, no `rle_decode` call, no mask hashing, no new geometry helper** in the
  route.
- **No removal of the dead carry at `:814-815`.** Correct to remove, out of scope here; HW-C7
  flagged it and no lane has authorized touching it.
- **No curator-facing surface.** No API field, no UI, no notification. The counters live in
  `vision_runs` and are read by a later lane.
- **No claim of substitution.** The emitted counters describe *suppression* (§2). Wording that
  implies a curator's region was replaced would be false on this path.

### 4.4 The condition that matters most — authorized, not scheduled

**This must not be built as a standalone change.** It may be built when **either**:

- **(a) ride-along** — a lane is already authorized to open `posts.py`'s merge block for another
  reason (Option D proper, the `:814-815` dead-carry removal, or an id-stability step). Then the
  counters go in with it, since the review cost is already being paid; **or**
- **(b) trigger** — a re-dissect is about to be run, or has been run, on a post holding a
  curator-owned ordinal id (today: `695be8b0a9ea58f1b6aef606`, `6a5b91ecbf74ef485d00399f`).
  Then the counters go in **first**, because that run is the only occasion on which the
  measurement can exist at all.

Rationale in one line: the value of this change is entirely prospective, so its cost should be
paid at the moment something prospective is about to happen — not on a calendar.

## 5. Scope honesty — does a 2-region exposure justify touching a live route?

**The case against (the honest one).** HW-C8 measured the whole corpus, not a sample: **2**
exposed regions, on **2** posts, **0** observed collisions, and the one case with an independent
witness is **affirmatively clean** (matching `mask_hash` at equal `geometry_rev`). `vision_runs`
holds 2 documents, neither on an exposed post. The route in question is the one that persists
every region in the product. A 3.5%-of-corpus exposure with a zero incident rate is a weak
mandate for a diff in `detect_regions`, and "it is only telemetry" is exactly the sentence that
precedes a regression in a route nobody wanted to touch.

**The case for.** The counters are not *for* the two exposed regions. They are for the merge
event, which is emitted on **every** dissect on **every** post — 421 posts, not 2 — and which
today reports a number (`kept_auto`) whose shortfall has no explanation anywhere. The exposure
count is the *motivation*; the beneficiary is the run record's honesty in general. And the
exposure is structurally open, not closed: `adapters.py:191`'s `base_id or f"refine_{...}"`
means every future refine of an ordinal-id auto region mints another exposed case, which is the
observed explanation for HW-C8's 2-exposed/4-safe split.

**How the two are reconciled.** By separating *authorization* from *scheduling*. A 2-region
exposure does not justify opening the file today; it does justify having the counters ready to
go in the moment the file is open anyway, or the moment a re-dissect makes the measurement
possible. §4.4 is where this section lands.

## 6. The counter-argument that must be engaged — acting on an unobserved failure

**Stated at full strength.** This program has been burned twice, in consecutive cycles, by
acting on inference. The hydration race was rejected. Cycle 6's "real corruption" was rejected
by cycle 7 as unreachable code. **No collision has ever been observed**, and HW-C8 §4 concedes
that on `695be8b0a9ea58f1b6aef606` the stored state *cannot distinguish* a collision from a
normal refine. Authorizing a fix for a failure that has never been seen, on a route that works,
looks like the same mistake in a third costume.

**The resolution — and it is a distinction, not a dodge.** The two prior burns share a shape
this one does not: both **asserted that something was already wrong** and proposed to change
behaviour on the strength of that assertion. The hydration race asserted a client-side ordering
bug; cycle 6 asserted live corruption at `:808-813`. Both claims were falsifiable and both were
falsified — and in each case the proposed remedy would have *changed what the system does*.

This change asserts nothing. It **repairs nothing, prevents nothing, and alters no outcome.**
It adds arithmetic on data already in local variables and writes three integers into a record
that already exists. It cannot be *wrong about the corpus*, because it makes no claim about the
corpus — it reports what one run did. Its failure mode is not "we acted on a false belief"; it
is "we spent a small diff and learned that the number is always zero", **which is a result.**

**And the asymmetry is the point.** The reason no collision has been observed is not that the
data is clean — HW-C8 §4 establishes that the merge guard is **unfalsifiable from stored state**,
because the surviving record is identical either way. The only reason one case could be cleared
at all is that a *different* subsystem happened to keep a hash. "Unobserved" here does not mean
"has not happened"; it means **there has never been an instrument.** Declining to install an
instrument because the instrument has never reported anything is not the lesson of the hydration
race — it is the condition that made HW-C5's corpus verdict UNDETERMINABLE and kept it there.

**What the counter-argument does correctly win.** It wins the *urgency* argument, completely.
It is why the verdict is not "authorize and schedule", why the scope is three integers and not
a mask comparison, and why §4.4 refuses to let this be a standalone errand. **If this were a
repair, or if it changed a single stored byte, the correct verdict would be DO NOT AUTHORIZE.**
It is authorized precisely to the extent that it is not a fix.

## 7. Relation to HW-C6's Option D

**It is a strict subset in mechanism and a different thing in subject.**

- **Same mechanism, same site.** Option D is "detect substitution at the dissect merge boundary,
  keep notify", justified because `existing` and `candidates` coexist in memory at
  `posts.py:790-847` and nowhere else. That is exactly this site and exactly this data.
- **Different subject.** Option D's target is *same id, different shape, stored geometry
  replaced* — which, per §2, happens on the **auto-id-reuse** fall-through at `:809-830`, not on
  the guarded `continue` at `:804`. This change measures **suppression**, Option D measures
  **substitution**. They are adjacent branches of the same `for` loop and are not the same
  finding.
- **It also dissolves one of Option D's stated design problems, for its own branch.** Option D
  §"how it could go wrong" (ii) warned that a refine-then-re-dissect shows same-id/different-mask
  *legitimately*, so a raw count over-reports. On the guarded branch that ambiguity does not
  arise: the creator region is preserved either way, so the count is unambiguously "a candidate
  was discarded", never "a curator legitimately changed their mind".

**Does authorizing this change Option D's status? No.** Cycle 6 decided Option D; cycles 7 and
8 both recorded that implementing it is **not a condition on anything**. That stands, unchanged.
This authorization does not implement Option D, does not partially implement it, does not
schedule it, and does not create pressure to complete it. If Option D is later built, these
counters are a natural companion and §4.4(a) says so — but Option D remains unscheduled and
unblocked-on, exactly as cycles 7 and 8 left it.

## 8. Rollback and safety notes (required by the gate)

**What the revert is.** `git revert` of a single commit touching one file. There is no schema
change, no migration, no index, no collection, no new module, and nothing written to
`region_annotations` — so the revert is a pure code revert with **no data step**. Reverting at
any time, including mid-flight, leaves the corpus in a state indistinguishable from one where
the change never landed.

**Why it is safe.**

1. **Nothing persisted changes.** Same `$set`, same payload, same route response. The acceptance
   test is byte-identical `region_annotations` before and after.
2. **The added computation cannot raise.** `_region_box_iou` (`:574-582`) reads only `.get(...)`
   with numeric defaults and divides only under `if union > 0`. No decode, no allocation
   proportional to image size, no external call.
3. **The telemetry write is already fail-open.** `Recorder.event` (`vision_run_service.py:250-260`)
   catches everything from `make_event` and `append_event` and sets `telemetry_degraded`. Even a
   payload-gate rejection degrades the record instead of failing the run.
4. **Readers already tolerate absent keys.** The counters are additive `detail` keys; the run
   projection carries `detail` through as a free-form dict, so consumers that predate them see
   the same events they see today. Reverting simply stops emitting them.

**What could go wrong.**

- **The comparison is placed wrong.** The natural place is at `:804`, *before* `continue` — but
  the candidate has not yet passed `canonicalize_geometry` (`:822`) at that point. YOLO
  candidates are already canonicalized upstream (`adapters.py:79`) and VLM candidates are
  box-native, so the box is present in practice; a candidate family added later might not be.
  **Mitigation: treat a missing/degenerate box as its own counter bucket, never as a match, and
  never move `canonicalize_geometry` above the guard** — moving it would change what is stamped
  onto dropped candidates and is a behaviour change, not an announcement.
- **Scope drift during the build.** The strongest failure mode is a builder deciding that since
  the comparison is there, the candidate should be *kept* under a suffixed id. **That is a
  different decision and is forbidden by §4.3.**
- **Cost.** One `_region_box_iou` per creator region per suppressed candidate. With 6 curator
  regions corpus-wide and ≤12 candidates, this is bounded by tens of float operations per run,
  against a route that already spends seconds in YOLO and a VLM. Not measurable.

**What telemetry would show if it went wrong.**

- **A route regression** would show as `dissect.complete` FAILED / `terminal_reason:
  "route_exception"` with the raised error on the run record — the same path that already
  reports any merge-block failure (`:882-887`).
- **A telemetry-only regression** would show as `telemetry_degraded: true` on the run, with the
  run still SUCCEEDED and the regions still persisted — the write-behind design's intended
  outcome, and the signal that the counters, not the route, are at fault.
- **A silent logic error in the counters** would show as the closure failing:
  `candidates != kept_auto + suppressed_by_id + suppressed_by_geometry`. **This is why the
  arithmetic must close** — the invariant is self-checking from the event alone, with no
  reference to the corpus, and any later reader can apply it. It should be asserted in a unit
  test over the merge block, extending `backend/tests/test_circulation_spine_p1.py`, which
  already exercises `creator_preserved` on a synthetic post.

## 9. Preconditions — what must be true before the build gate opens

1. **One of §4.4's two openers has fired** — a ride-along, or an imminent/completed re-dissect
   on a post holding a curator-owned ordinal id.
2. **A written statement of the box-IoU threshold used to classify id-guard drops**, and an
   explicit note that it is a *reporting* threshold with no effect on behaviour (unlike the
   0.7/0.85 at `:827-828`, which decide).
3. **The acceptance test named in §4.3 is written first**: a merge over a fixture with a curator
   region and a colliding candidate produces identical `region_annotations` to today, and a
   merge event whose arithmetic closes.
4. **The dead carry at `:814-815` is left alone** in the same diff, or removed under its own
   authorization with its own note. Not silently.
5. **No Mongo write outside `vision_runs`** in the diff.

## 10. What would change the verdict

**To DO NOT AUTHORIZE:**

1. **The comparison cannot be done without a mask decode.** If the box turns out to be absent or
   untrustworthy on a real candidate family at `:804`, the cheap version dies and the expensive
   version is not announcement-only (§3). Withdraw rather than escalate.
2. **The diff cannot be written without touching merge behaviour.** If the counters cannot be
   added without moving `canonicalize_geometry`, restructuring the loop, or altering the
   `continue`, the premise of the authorization is false.
3. **The two exposed regions are re-keyed to stable ids** by some other authorized work, and no
   ordinal-id curator region remains. The exposure closes and the counters lose their motivation
   (though the closed-arithmetic argument in §4.2 would survive on its own, more weakly).

**To AUTHORIZE AND SCHEDULE:**

4. **An observed collision** — any dissect that drops a candidate at `:804` whose box does not
   overlap the suppressing creator region. That is the failure becoming observed, and §6's
   entire resolution flips from "install an instrument" to "we have a measured problem".
5. **A curator reports a missing region after a re-dissect** on either exposed post. Same
   effect, from the other end.
6. **Option D proper is scheduled.** Then §4.4(a) fires by construction.

**To escalate beyond announcement** (a different decision, not this one):

7. **Evidence of substitution on the auto-id-reuse branch at `:809-830`** — a ground resolving
   to geometry it did not previously name. §2 argues that is where re-pointing can actually
   occur. It would be a decision about repair and about id stability, and it must be taken as
   its own fork, not as an amendment to a telemetry counter.

---

*Decision doc ends. Status: decided, authorized-not-scheduled. No implementation performed.
No production data read or written. No commit, no stage, no push.*
