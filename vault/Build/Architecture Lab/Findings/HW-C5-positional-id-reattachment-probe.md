# HW-C5 — The positional-id re-attachment probe

**MEASUREMENT ONLY — no production data mutated, no code fixed.**
Mongo was read with `find` / `count_documents` only. No source file, schema, route, migration or
record was created or modified. No model/LLM calls. Nothing staged, committed or pushed. The only
repo write is this document; probe scripts live in the session scratchpad and are not in the repo.

| | |
|---|---|
| **id** | HW-C5 · discharges the "§2(b) id-reuse probe" trigger in `Decisions/HW-C4-detached-evidence-repair-fork.md` §7 |
| **date** | 2026-07-21 |
| **branch** | `feat/rehearsal-research-r1` |
| **verdict — in code** | **PARTIALLY POSSIBLE (pass-specific)** — real for `fine_*`, `arch_*`, `fseg_*`, `seg_*`; **not** for `refine_*` |
| **verdict — in corpus** | **UNDETERMINABLE** — no generation history exists anywhere in the database. A latent instance is present and named in §2.3, but it is a standing hazard, not an observed event. |
| **verdict — Q4 (the decision's coverage)** | **There is a gap. Notification-only does not cover re-attachment, and cannot.** |

---

## 1. Is the hazard possible in code?

Four id-generation sites exist in `backend/`. I found them by grep and read each.

| site | expression | id is | reusable across runs? |
|---|---|---|---|
| `backend/services/vision_service.py:645` | `"id": f"fine_{i}"` | **positional ordinal** — `i` from `enumerate((data.get("parts") or data.get("regions") or [])[:max_regions])` over a VLM's JSON parts list | **YES** |
| `backend/services/vision_orchestrator/adapters.py:68` | `"id": f"{id_prefix}_{i}"` (`id_prefix="seg"` default, `masks_to_regions`) | **positional ordinal** over the YOLO instance-mask array | **YES** |
| `backend/services/architecture_segmentation_service.py:137` | `"id": f"arch_{len(regions)}"` | **positional ordinal** (append-counter) | **YES** |
| `backend/services/fashion_segmentation_service.py:216` | `"id": f"fseg_{len(regions)}"` | **positional ordinal** (append-counter) | **YES** |
| `backend/services/vision_orchestrator/adapters.py:191` | `"id": base_id or f"refine_{uuid.uuid4().hex[:10]}"` | **random** (`uuid4`), or an explicit `base_id` when upgrading an existing identity | **NO** |

**The `refine_*` correction.** The hazard brief asked whether `refine_c6485b9a94` is content-derived
and therefore safe. It is **not content-derived** — it is `uuid.uuid4().hex[:10]`, i.e. random. But
it is safe *for this hazard* for a different reason: a random id is never re-emitted, so a re-run
cannot collide with a prior one. It is safe by non-collision, not by content-addressing. This matters
for §5: a "content-derived ids" fix is not already half-implemented anywhere; the one safe pass is
safe by accident of randomness. Note also that `refined_mask_to_region` *deliberately* reuses
`base_id` when upgrading a region — that is intentional identity continuity, not the hazard, because
the same shape is being refined.

None of the four ordinal sites incorporate the mask, the box, the label, the image, the run, or a
timestamp. **The id encodes rank within one detector response and nothing else.**

**Persistence — both prior-lane claims verified.**

- **Wholesale `$set` confirmed.** `backend/routers/posts.py:847`:
  `await post_collection.update_one({"_id": obj_id}, {"$set": {"region_annotations": regions}})`,
  where `regions = creator_regions + kept_auto`. The whole array is replaced. There is no history
  collection, no `superseded` flag, no archive (grepped `backend/`; corpus-confirmed in §2).
- **Carry-by-id merge confirmed.** `posts.py:808-813`:
  ```
  prev = existing.get(r["id"])
  if prev:
      r["prioritised"] = prev.get("prioritised", False)
      r["weight"]      = prev.get("weight", 0)
      r["user_note"]   = prev.get("user_note", "")
      if prev.get("actor") == "creator":
          r["actor"] = "creator"
  ```
  `existing` is keyed purely by `r.get("id")`. So a curator's `user_note`, their `prioritised` flag,
  their `weight`, **and the `actor == "creator"` promotion** all migrate onto whatever new region
  happens to occupy that ordinal. This is the same hazard one layer below Grounds, and it needs no
  frontend at all. The `actor` promotion is the worst of the four: it grants a fresh auto region the
  re-dissect immunity of `posts.py:795-797`, permanently, on the strength of an ordinal match.

**Two aggravating facts found in this lane, not previously recorded.**

1. **The dissect path never looks at `grounds`.** `grep -n 'grounds' backend/routers/posts.py`
   returns exactly one hit — line 98, an unrelated response projection. The detect-regions route
   does not load, inspect, or count grounds. It cannot notice that it is about to strand or
   re-attach one.
2. **A mask-hash staleness check already exists in this codebase — and is not wired to dissect.**
   `backend/services/geometry_recovery.py:153-177` implements `stale_semantic_assertions` /
   `mark_stale_semantic_assertions`: it compares each region's current `mask_hash` against a
   `prior_mask_hashes` map **keyed by candidate id** and flags `evidence_stale=True` when the same
   id now carries a different mask. That is precisely the detection the Ground path lacks. Its
   docstring even states the principle: *"the region's mask now differs … the caller flags stale but
   preserves status/curator_label."* `mark_detached_grounds` sits in the same file
   (`geometry_recovery.py:180`). Grepping the routers: **neither is called from any router.** The
   pattern exists, is tested, and is confined to the geometry-recovery flow.

**Verdict in code: PARTIALLY POSSIBLE (pass-specific).** Four of five id-generation sites emit
per-run ordinals within a detector family, and the merge + persist path matches purely on that
string. The hazard is real for `fine_*`, `seg_*`, `arch_*`, `fseg_*`. It is not reachable through
`refine_*`.

---

## 2. Is it observed in the current corpus?

Read-only. Collections and counts as read this lane:

```
personas 3 · posts 127 · region_embeddings 98 · taste_consent 0 · taste_signals 0 · vision_runs 1
```

### 2.1 The data cannot answer the question, and here is exactly why

Direct observation of id reuse requires knowing what an id pointed at *before*. Every candidate
source of that knowledge is empty:

- `region_history`, `prev_region_annotations`, `superseded`, `region_generation` — **0 documents
  each** (`count_documents({field: {$exists: true}})`).
- `vision_runs` — **1 document corpus-wide**, for post `6a5b9275bf74ef485d0039b8`, a `dissect` on
  2026-07-21 05:56 with `result_summary {anchor_count: 0, fine_count: 0, region_count: 0}` — a run
  that produced nothing, on a post unrelated to any detached ground. And the dissect recorder writes
  bounded counts only (`detail={"region_count": len(regions)}` at `posts.py`), never region ids or
  geometry, so even a fully-populated `vision_runs` would not, as currently written, let you compare
  generations.
- `region_embeddings` looked like the one real chance: its documents carry `region_id`, `mask_hash`,
  `geometry_rev`, `created_at`, `updated_at`, and a `stale_reason` field. I checked whether any
  `(post_id, region_id)` pair holds two different `mask_hash` values — that would be direct
  observation. **Four pairs matched, all four are artefacts, none is evidence.** In each case
  (`695be8ba` · `fseg_3`, `fseg_4`, `fseg_6`, `fine_6`) the second value is the empty string `""`
  from a `fashion-clip|fashion|vitb32|512` document that stores no mask hash, alongside a real hash
  from the `dinov2` identity/context spaces. Different embedding space, same generation. **Zero
  genuine same-id/different-mask pairs.**
- Embeddings whose `region_id` no longer exists on their post: **9, all of them `__whole__`** — the
  synthetic whole-image key, not a region. So no embedding survives from any superseded generation
  either; the embedding run (2026-07-19 17:01) postdates the detachments entirely.

**No fingerprint of any prior generation exists anywhere in this database.** That is a definite
finding, not a shrug: the corpus is structurally incapable of answering "did an id ever change what
it pointed at", and will remain so until something records per-run region identity.

### 2.2 What the snapshot does show

Region-id families across all 127 posts: `seg` 6 posts · `arch` 2 · `refine` 3 · `fseg` 1 · `fine` 2.
No post has duplicate ids within its own array. Four posts carry **more than one family at once**,
which is the merge surviving across generations:

```
695be77e  ['arch_0', 'seg_0', 'arch_1']
695be786  ['refine_c6485b9a94', 'arch_0'…'arch_5']
695be8ba  ['fseg_0'…'fseg_6', 'fine_0'…'fine_8']
695be6c9  ['seg_0', 'fine_0'…'fine_8']
```

Grounds and detachment, re-confirmed independently of HW-C4's sweep (11 posts carry grounds):

| post | live families | grounds | detached | detached cites |
|---|---|---|---|---|
| `695be786` | arch, refine | 5 | **2** | `gnd_mrqp8tls_0 → fine_3`, `gnd_mrqp8tlt_1 → fine_0` |
| `695be794` | seg | 5 | **2** | `gnd_mrphxkl1_0 → fine_3`, `gnd_mrpi0b4o_2 → fine_8` |
| 9 others | — | 1–6 | 0 | — |

### 2.3 The latent instance — stated as an inference, and labelled as one

This is **inference from a single snapshot**, not observation:

Both detached posts cite `fine_*` ids. Two *other* posts currently hold live, complete `fine_0 …
fine_8` arrays produced by the same `vision_service.py:645` loop. So the fine pass routinely emits
ordinals 0 through 8 on this corpus. **If the fine pass is re-run on `695be786` or `695be794` and
returns four or more parts, `fine_3` will exist again**, and `gnd_mrqp8tls_0` / `gnd_mrphxkl1_0` will
resolve to it — to whatever the VLM happened to list fourth. `fine_0` (post `695be786`) is even more
certain: any non-empty fine response produces `fine_0`. `fine_8` needs nine parts, which the corpus
shows does happen but is the least likely of the four.

Three of the four grounds this fork exists for are therefore **one ordinary re-dissect away from
silently resolving to an unrelated shape.** Nothing prevents that re-dissect; it is a normal user
action.

**Verdict in corpus: UNDETERMINABLE (with a named latent instance).** Reuse has not been observed
and — given the total absence of history — could not have been. It has equally not been ruled out.
The corpus contains four grounds primed for it.

---

## 3. Could it fool `resolveGround`?

`frontend/src/differential/grounds.js:68-73`:

```js
export function resolveGround(ground, { regions = [], grounds = [] } = {}) {
  if (!ground) return null;
  if (ground.ground_type === 'region') {
    const region = regions.find((r) => r.id === ground.region_id) || null;
    return { ground, region, members: [], detached: !region };
  }
```

`detached` is `!region`, and `region` is a **string equality match on `id` alone**. Nothing in the
comparison consults geometry, `mask_rle`, `geometry_rev`, `geometry_provenance`, label, detector, or
any creation-time record. The file's own header states the design honestly — *"A region-adapter
Ground stores ONLY `region_id`… If a re-dissect replaces that Region, the Ground degrades gracefully"*
— but "replaces" silently assumes the replacement does not reuse the identifier. It does.

**Synthetic probe** (scratchpad only, plain node ESM importing the real, unmodified `grounds.js`; no
repo file added, no existing test touched). A ground on `fine_3` = "hair", traced through the three
generations the corpus actually exhibits:

```
A original (fine pass)     detached=false  label=hair     box={"x":0.28,"y":0.08,"w":0.24,"h":0.14}
B after arch re-dissect    detached=true   label=—        box=—
C after fine RE-run        detached=false  label=gravel   box={"x":0.05,"y":0.88,"w":0.9,"h":0.1}

ASSERTIONS
 A resolves to hair           : true
 B DETACHED (visible loss)    : true
 C INTACT again (silent)      : true
 C is a DIFFERENT shape       : true ("hair" -> "gravel")
 geometry moved               : true
```

State **B** is today's corpus (`695be786`). State **C** is one re-dissect later. The ground travels
`resolved → detached → resolved`, and the final state is indistinguishable, by every signal the
system computes, from the original. No exception. No flag. No console warning. No failing test.

Downstream, `detached: false` is **load-bearing behaviour**, not a display value: `GroundLayers`
draws the new mask, `groundBBox` returns the new box, `RefPicker`'s badge fills, and `recall.js`'s
`isResolved` passes — so the highlight step is scheduled and the caption *"the upper head"* is
performed, confidently, over gravel. This is the exact rendered outcome A2R was written to stop,
re-armed by data. Worse than the pre-A2R bug: A2R's failure drew *nothing* over the image, which a
viewer could at least perceive as emptiness. Re-attachment draws *something wrong* with full
conviction.

---

## 4. Does notification-only still handle it? — **No. There is a gap.**

This is the lane's central answer, and it is not softened.

`HW-C4` chooses **notify, not tombstone**, and its case is sound *for the failure it models*.
But every notification it contemplates is triggered by the same predicate:

- at the moment of loss — *"at the moment an operation drops Regions that Grounds cite"* (§Option 2);
- at rest — the quiet derived marks B-02 / B-03b / B-06, all reading `resolveGround`'s boolean;
- in recall — A2R's `evidenceNote` / `unresolvedGroundIds`, all derived from `isResolved`.

**Every one of them fires on `detached === true`.** Under re-attachment `detached` is `false`. The
ground is not stranded — it is *occupied*. The count of unresolved grounds is zero. The evidence note
is empty. The moment-of-loss check, were it written today as §Option 2 describes (compare outgoing
region ids against cited `region_id`s), would compute *"cited ids still present: `fine_3` ✓"* and
correctly stay silent. **The notification is not merely absent; it is affirmatively wrong, and it is
wrong by working exactly as designed.**

Put plainly: **notification-only covers loud-by-absence and has no mechanism whatsoever for
silent-by-substitution.** The two failures are complements. A policy addressed to one is not a
partial answer to the other; it is orthogonal to it.

HW-C4 is not unaware of this. Its §2(b) names the mechanism, §Option 3 cites it against "neither",
§Option 4b is *rejected because of it* (a durable `detached_at` "becomes wrong the moment a re-run
emits the same ordinal id"), §7 lists the probe as an open trigger — *"if ordinal id reuse is
happening, it is a more urgent problem than detachment"* — and §8 closes by recording it as *"newly
surfaced, not resolved here."* So the doc is honest about the gap's existence. **What it does not do,
and what this lane must state directly, is note that its chosen option provides zero coverage of it.**
The decision reads as a complete answer to the detached-evidence question; it is a complete answer to
half of it. Three of the four grounds that motivated the entire fork are one ordinary re-dissect away
from the half it does not cover, and if that re-dissect happens, the chosen policy will report the
corpus as *healthier* than before — four detached grounds becoming one or zero — while the citations
have in fact become false rather than dead.

There is a second-order consequence worth stating. HW-C4's strongest argument against tombstoning is
that *"a tombstone would silently re-arm the exact behaviour A2R was written to disarm — same
rendered outcome, no code change, no failing test, and the regression would arrive as data."* That
argument is correct, and **ordinal id reuse produces the identical regression by the identical route,
without anyone choosing tombstoning.** The doc rejected an option for causing a harm the system will
inflict on itself anyway. That does not make the rejection wrong — it makes the rejection
insufficient as a stopping point.

The `posts.py:808-813` carry-by-id (§1) widens the gap further: it is the same substitution below the
Ground layer, on curator-authored fields, reachable with no frontend involvement at all, and covered
by no notification anyone has proposed.

**Answer to Q4: the chosen decision does not cover this case. It is a gap, not a wording problem, not
a scoping choice, and not something a better-worded toast can reach.**

---

## 5. Minimal future fix, if one is ever wanted

**Prose only. No code. Explicitly NOT approved, NOT authorized, and NOT a recommendation to build.**
Listed so the options are on record with their costs, per HW-C4 §5's refusal to license anything.

**Invariants any fix must not break** (from HW-C4 §3, re-verified against `schemas/post.py:46-52`
this lane):

- `mask_rle` is authoritative identity on the **Region**; `box` / `polygons` are derived from it by
  `canonicalize_geometry`, with `geometry_rev` bumping on re-derivation. Nothing may carry a
  `mask_rle` it did not get from a real derivation.
- **Geometry is never duplicated onto a Ground.** The region adapter stores `region_id` and nothing
  else, deliberately. No fix may copy a mask onto a ground — that creates a second canonical
  geometry with no `geometry_rev` and no provenance.
- `region_annotations` is the single source of truth, iterated by ~10 backend consumers; anything
  placed in that array is seen by all of them.
- Creator regions survive re-dissect intact (`posts.py:795-797`).
- A2R's honesty property: a ground that draws nothing must not receive a highlight step.
- **No fabricated repair targets** (K-4): no IoU re-match, no *"did you mean `arch_2`?"*, no
  automatic re-pointing.

| approach | what it does | cost | risk |
|---|---|---|---|
| **Content-derived ids** (`fine_<hash(mask_rle)>` or of the box+label) | reuse becomes impossible: a different shape gets a different id | touches all four generation sites; **breaks every existing id in the corpus** unless dual-read; ids stop being human-readable, which every debug workflow and several fixtures rely on | a *stable* shape re-derives the *same* id across runs — which is arguably correct, but it silently makes re-attachment legitimate in exactly the case where it is legitimate, and nobody has decided that; hash-of-mask also changes under harmless preprocessing drift, so ids churn |
| **Generation / run stamping** (`fine_3@run7`, or a `run_id` field on each region, id unchanged) | old and new ids never collide; detachment stays loud | needs a real `VisionRun` per dissect — **DATA-1-blocked, 1 document corpus-wide**; every id consumer must ignore or handle the stamp; if the stamp is in the string, it is the previous row's migration problem again | if the stamp is a *field* rather than part of the id, `resolveGround`'s string match is unchanged and the hazard survives untouched — a fix that looks applied and is not |
| **Region records its originating run** (a `run_id` / `generation` field on Region only) | makes reuse *detectable* after the fact and gives the corpus the history §2 proved it lacks | small schema addition; harmless to existing consumers; still DATA-1-dependent for the run record itself | **detects nothing on its own** — something must compare, and nothing does today; risks being built, being green, and changing no behaviour |
| **Ground stores a fingerprint of what it pointed at** (e.g. `region_mask_hash` at creation) | `resolveGround` could compare and distinguish *resolved-and-same* from *resolved-but-changed*; the exact analogue of the already-shipped `stale_semantic_assertions` (§1) | smallest surface: one optional field, `hydrateGrounds` already preserves unknown fields verbatim; the comparison logic is already written and tested in `geometry_recovery.py:153` | **it is HW-C4 §4b's rejected shape wearing better clothes** — a durable snapshot of a transient condition on the Ground — and §4b was rejected *for this very hazard*. It must not be read as an approved back door. It also cannot be backfilled: the four existing grounds' original masks are gone (§2), so it is prospective only, exactly as tombstoning was. And a fingerprint tempts an implementer toward IoU re-matching, which K-4 bans permanently |

**One structural observation, offered as measurement, not advice.** The `geometry_recovery.py`
same-id-different-mask check already exists, is tested, preserves curator decisions, and is wired to
nothing outside its own flow, while the dissect route does not so much as read `post.grounds`. Any
future work on this hazard would be reusing an in-repo pattern rather than inventing one. That lowers
the cost; it does not make the decision, which belongs to a fork of its own with its own evidence —
and per HW-C4 §7 this probe is itself the trigger to re-open D-1.

---

## 6. What this lane did not do

No fix, no branch, no schema, no test, no commit. No write of any kind to Mongo. No model calls. It
did not attempt to *cause* a re-dissect to observe reuse empirically — that would mutate production
data and destroy the four fixture grounds, which HW-C4 §8 explicitly preserves as the fixture. The
question "would a real re-run of the fine pass on `695be786` actually emit `fine_3`" is therefore
answered by code reading and by the ordinal distribution across other posts, not by execution, and
that limitation is why §2's verdict is UNDETERMINABLE rather than OBSERVED.

---

*Findings doc ends. Measurement only. No implementation authorized; nothing in §5 is approved.*
