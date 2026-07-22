# CIRCUIT-001 P1F — Implementation report

**The first backend change in the CIRCUIT programme, and it is announcement-only.**
No repair, no id migration, no backfill, no suspect detection, no `run_id`, no dispatch, no persisted
Mentions, no Atlas/Codex. **No production data mutated.**

Implements the fix authorized-with-conditions in `Decisions/HW-C9-announcement-only-merge-fix.md`,
with the scope correction required by `CIRCUIT-001-P1E-design-report.md` §5.

---

## 1. What changed

**One file, 54 insertions, 1 deletion** — and the single deleted line is the telemetry `detail`
literal being extended.

`backend/routers/posts.py`:
- **`_MERGE_SAME_PLACE_IOU = 0.5`** — a new observation constant.
- **Five counters** in the merge loop, and five new keys on the existing
  `STAGE_MERGE_CURATOR` event detail.

`backend/tests/test_circuit_p1f_merge_observation.py` **(new)** — 12 tests.

**Nothing else.** No route signature, no response model, no schema, no persistence, no merge
decision, no id.

## 2. The problem it closes

The merge event's arithmetic did not close. `detail` carried
`{creator_preserved, kept_auto, candidates}`, so **`candidates − kept_auto` was an unlabelled
residual mixing two distinct drop reasons.** A candidate that vanished at the merge boundary left no
trace of *why* — and the id-guard case in particular reported `creator_preserved` and looked like
success.

## 3. The counters

| key | means |
|---|---|
| `suppressed_by_id` | dropped because its id belongs to a creator region (`posts.py` id guard) |
| `suppressed_by_id_moved` | …and it was **not** where that creator region is |
| `suppressed_by_geometry` | dropped by the existing box-IoU dedup |
| `id_reused_auto` | an auto candidate **keeping** an id that already named something |
| `id_reused_auto_moved` | …and its box no longer overlaps the old one |

**The acceptance invariant, asserted in three tests:**

```
candidates == kept_auto + suppressed_by_id + suppressed_by_geometry
```

Every candidate is now either kept or accounted for by exactly one named reason. **The `_moved`
counts deliberately do NOT participate in that sum** — they describe suppressions already counted,
and adding them would double-count and make the invariant meaningless. One test pins that.

## 4. Both branches instrumented — the scope correction

`HW-C9` scoped the counters to the id guard, which covers the **2** exposed curator regions
`HW-C8` enumerated. P1E's §5 required the other branch too, and it is the larger one.

- **id guard** — a candidate is *dropped*. `suppressed_by_id(_moved)`.
- **auto→auto reuse** — a candidate **survives** while keeping an id that already named something
  else. It appears in `kept_auto` as an ordinary region, so a re-pointed reference was **invisible in
  the counts**. `id_reused_auto(_moved)`.

Corpus proportion: **51 auto regions to 6 curator ones.** The uninstrumented branch was the bigger
exposure, exactly as P1E argued.

## 5. Safety — how this cannot break a live route

**Every added operation is `.get()` or `_region_box_iou`.** That helper is pure arithmetic: `.get()`
with defaults on every field, and `return inter / union if union > 0 else 0.0` — a zero-guard on the
only division. Verified directly: `_region_box_iou({}, {}) == 0.0`, and the same for zero-area boxes.

**No mask decode.** `HW-C9` §2 established that the probe's originally proposed mask comparison was
*not* announcement-only — `rle_decode` is a per-pixel loop indexing `rle["size"]`/`rle["counts"]`
unguarded, inside the merge loop and outside any telemetry try/except, and **32 of 51 auto regions
have no mask at all**. Box IoU only, as decided.

**Nothing branches on a counter.** They are incremented and reported; no merge decision reads them.

## 6. Verification

| | |
|---|---|
| **new tests** | **12 passing** — `test_circuit_p1f_merge_observation.py` |
| **full backend suite** | **419 passing** |
| **frontend** | untouched; suite unchanged at 187 |
| **route import** | `from backend.routers import posts` OK; live server still `/health` 200 |
| **production data** | **not mutated** — no `detect_regions` call was made against a real post |

**The byte-identical guarantee is the load-bearing test.** `test_regions_are_byte_identical_to_the_
pre_P1F_behaviour` re-enacts the merge loop *as it behaved before this gate* and asserts the output
is identical in ids, order and content.

**That test earned its place on the first run: it failed.** The failure was in the harness — my
re-enactment had dropped the curator-field carry block — but the route was verified intact by
reading it. A test that only ever passes proves nothing about a change like this one; this one
demonstrated it could detect a divergence.

Also pinned: counters survive regions with **no box, an empty box, and a zero-area box**, and
`_MERGE_SAME_PLACE_IOU` is asserted **distinct from the 0.7 / 0.85 decision thresholds**, so relaxing
an observation can never loosen a merge rule by accident.

## 7. Known edges, recorded rather than hidden

**Zero-area boxes read as "moved".** `_region_box_iou` returns `0.0` when the union is zero, which is
below the threshold — so two box-less regions are counted as a relocation. That is *honest* (we
cannot say they are in the same place) but it means **a corpus of box-less regions would inflate the
signal.** Pinned by a test that documents it rather than asserting it is desirable.

**A pre-existing latent `KeyError` was NOT fixed.** The id guard uses `r.get("id")` while the very
next lines use `r["id"]`, so a candidate with no id raises. `HW-C7`'s brute force found no detector
emits one. **Out of scope, deliberately** — fixing it would change behaviour, and this gate changes
none.

**The counters are not yet read by anything.** They land in `STAGE_MERGE_CURATOR` detail and are
visible through the existing run projection. Nothing in the UI surfaces them, and the Circulation
Thread still renders `substitution not assessed` — correctly, because *observing* suppression is not
*detecting* substitution.

## 8. What this unblocks, and what it does not

**Unblocked:** the measurement HW-C9 said was impossible from stored state. `HW-C8` §4 established
that the guard is unfalsifiable after the fact; now a re-dissect **records** what it suppressed and
whether it had moved. The worst case remains *"the number is always zero"* — which is a result.

**Not unblocked, and this must not be overstated:**

- **`suspect` detection is not done.** These counters observe a *merge*. A reference that silently
  re-points between merges is still undetectable, and the thread's `substitution not assessed` row
  stays honest.
- **Run answers are not yet trustworthy** (`CIRCUIT-001-P1E-run-relation-design.md` §6).
- **No dispatch, no `run_id`.**

## 9. Recommended next

**Measure before building anything on it.** These counters have never fired — there is no corpus
evidence of a real suppression, because no re-dissect has run since they landed. The honest next step
is a **read-only sweep once a dissect has run on a post with existing regions**, reporting the five
counts and whether `_moved` ever fires.

If it never fires, that is the strongest possible evidence that the ordinal hazard is theoretical on
this corpus — and it would change the priority of the whole evidence-identity thread. **A gate that
can disconfirm its own premise is worth running before one that builds on it.**
