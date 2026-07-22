# CIRCUIT-001 P1G — Controlled suppression measurement

**A measurement gate.** One controlled, reversible `detect_regions` on one post, snapshot → run →
restore. **The post was mutated deliberately and restored byte-identically; verification below.**

**Headline: the counters fired on the first run, and `suppressed_by_id_moved` fired with them. The
ordinal collision is real on this corpus, not theoretical.**

Evidence: `CIRCUIT-001-P1G-controlled-measurement/` — `pre-state.json`, `detect-response.json`,
`vision-run.json`.

---

## 1. Target post, and why

**`695be8b0a9ea58f1b6aef606`** — chosen over `6a5b91ecbf74ef485d00399f`.

| | 695be8b0 (chosen) | 6a5b91ec |
|---|---|---|
| regions | 1 · `seg_0` · creator · sam2 | 1 · `seg_0` · creator · sam2 |
| domain profile | **`["general"]`** — YOLO + SAM only | `["general","painting"]` — also runs the painting specialist |
| grounds / percepts | **6 / 2** | 0 / 0 |
| **a ground citing `seg_0`** | **yes — `gnd_mrtof0k1_0`** | no |
| embeddings / runs | 0 / 0 | 3 / 0 |

**Reasons:** the gate's own selection rule prefers *"lower risk of expensive domain models"*, and this
post schedules the fewest. And it is **the named hazard case**: `HW-C8` identified it as the post
where a collision would leave *"a ground that still resolves — to different geometry."* The
measurement should happen where the citation actually exists.

**Why its curator work was not at risk:** `detect_regions` performs **exactly one write** —
`update_one({"_id": …}, {"$set": {"region_annotations": regions}})`. Verified by enumerating every
write in the route body. Grounds, percepts, semantics and text blocks are **not in the write path at
all**. Everything was snapshotted regardless.

## 2. What ran

One `POST /api/v1/posts/695be8b0a9ea58f1b6aef606/detect-regions`, HTTP **200**, **11.2 s**, no retry.
The backend was restarted first (PID `251669` → `286861`, same worktree, exact PID only) because the
running process predated P1F and would not have carried the counters.

Result: **1 region → 13**. `seg_0` (the curator's, preserved) plus `fine_0 … fine_11`.

## 3. The counters — `dissect.merge_curator_state`

```json
{
  "candidates": 13,
  "creator_preserved": 1,
  "kept_auto": 12,
  "suppressed_by_id": 1,
  "suppressed_by_id_moved": 1,
  "suppressed_by_geometry": 0,
  "id_reused_auto": 0,
  "id_reused_auto_moved": 0
}
```

**The invariant holds: `13 == 12 + 1 + 0`.** ✓ Every candidate is accounted for by exactly one named
reason. Before P1F this event said `{creator_preserved: 1, kept_auto: 12, candidates: 13}` and the
missing candidate was an unlabelled residual.

**`suppressed_by_id_moved: 1` — the hazard's precondition, observed.**

Concretely: the detector emitted a candidate with id **`seg_0`** — the same positional ordinal the
curator's refined region already holds — and that candidate's box was **not in the same place**
(IoU below `_MERGE_SAME_PLACE_IOU = 0.5`). The id guard discarded it in favour of the curator's mask.

**Before this gate, that event reported `creator_preserved: 1` and looked like success.**

## 4. What this proves — and what it does not

**Proved.** *Ordinal ids collide across runs, immediately, on the first re-dissect of a real post* —
and a colliding candidate can describe **a completely different part of the image**. The premise the
whole evidence-identity thread rests on is **not theoretical on this corpus.** It took one run to
demonstrate.

**Not proved, and this must not be overstated.** **No citation was re-pointed in this run.** The
cited region is `actor: creator`, so the id guard fired and *protected* it — the ground
`gnd_mrtof0k1_0` still resolves to the curator's own mask, correctly. `id_reused_auto: 0`, because
this post has exactly one region and it is creator-owned.

**The dangerous branch was therefore not exercised.** It is the auto→auto path: a ground citing an
**auto** region whose id is regenerated onto different geometry. There the guard does not fire and
nothing intervenes. P1E flagged this as the larger population — **51 auto regions to 6 curator ones**
— and this run leaves it untested.

*Stated plainly: this run shows the collision is real and shows the guard working. It does not show
the failure the guard cannot catch.*

## 5. Restore proof

| check | before | after run | after restore |
|---|---|---|---|
| `region_annotations` | 1 region, `seg_0` | 13 regions | **1 region, `seg_0` — byte-identical** |
| `grounds` / `percepts` / `semantics` / `text_blocks` | 6 / 2 / — / 0 | unchanged (not in write path) | **byte-identical** |
| `updated_at` | `2026-07-20 20:28:16.355` | unchanged — the `$set` touched only `region_annotations` | **unchanged** |
| full key set | — | — | **identical** |
| `region_embeddings` | 0 | 0 | **0** |
| `vision_runs` (this post) | 0 | 1 | **0** |
| `vision_runs` (corpus total) | 9 | 10 | **9** |

Verified by a comparator over the canonical JSON of every snapshotted field:
**`fields byte-identical to pre-state: True`**, `key set identical: True`.

**Two deliberate write actions, both reported rather than buried:**

1. **`region_annotations` restored** by `$set` of the snapshotted value. Only the one field that
   differed was written.
2. **The `vision_runs` document I created was deleted** (`_id 6a6047a67651dd52e8260e85`), to restore
   the sidecar count the gate required. **Its full content — all 10 stage events — is preserved in
   `CIRCUIT-001-P1G-controlled-measurement/vision-run.json`, so no evidence was lost.** The delete
   was guarded by an assertion on `post_id` **and** `operation` so it could not remove anything else.

**Net production state: identical to before this gate.**

## 6. An incidental observation

**The stored run's `run_id` field is `None`.** The route returns the document `_id`
(`6a6047a67651dd52e8260e85`) as `run_id` in its response, but the field of that name on the document
is unset — which is why an initial lookup by `run_id` found nothing.

Not a bug this gate fixes, and not in scope. It is a small, concrete instance of what
`CIRCUIT-001-P1E-run-relation-design.md` argued: **run identity is under-specified today**, and a
relation built on it needs that settled first.

## 7. Verdict on the identity thread

**Status: OBSERVED — live, not theoretical.** The priority should **not** drop.

The honest refinement is that what was observed is the **precondition** (ids collide, and collide
onto different geometry), while the **consequence** (a citation silently re-pointing) was prevented
here by the guard, because the cited region happened to be curator-owned.

That refinement makes the next measurement obvious rather than optional.

## 8. What this implies for P1H

**Recommend: one more measurement, then return to product UX.** Not more identity *design*.

The specific gap is narrow and cheap: **a post whose cited region is `actor: auto`.** On such a post
a re-dissect would exercise `id_reused_auto`, and either:

- **it fires with `_moved`** → a citation has been silently re-pointed, the consequence is
  demonstrated, and `suspect` detection stops being speculative; or
- **it does not fire** → the collision is real but consistently absorbed, and the identity thread can
  be de-prioritised on evidence rather than on argument.

**Either outcome is decisive, and the corpus has 51 auto regions to choose from.** After that,
whichever way it lands, the honest move is back to product: P1D's thread, P1C's roles and the
Manuscript circuit are the parts a curator actually touches, and three gates in a row have now gone
to identity.

**Not recommended:** building `suspect` detection now. This run shows the guard *working*; detection
should be designed against an observed failure, not an observed near-miss.

## 9. What this gate did NOT do

- **No suspect detection, no dispatch, no `run_id` propagation, no persisted Mentions, no
  Atlas/Codex.**
- **No code changed.** P1F's counters were read, not modified.
- **No permanent repair.** The post is exactly as it was.
- **No second run.** One call, no retries, no improvisation — a failure would have been recorded as a
  failure.
