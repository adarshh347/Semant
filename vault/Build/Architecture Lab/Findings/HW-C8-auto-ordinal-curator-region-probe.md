# HW-C8 — Curator regions wearing auto ordinals: the exposure is exactly two, and one of them is cited

**READ-ONLY probe. No production data was written — `find` / `count_documents` only. No source
file was edited. Nothing was staged, committed or pushed. No repair or clean-up was performed.**
Horizon Weave cycle 8, Lane 3.

Cycle 7 (`HW-C7-actor-carry-audit.md`) rejected the `actor == "creator"` promotion claim and, in
its §4, flagged a different live hazard: the merge guard at `backend/routers/posts.py:804` drops an
incoming candidate on a **bare string-id match** against a curator-owned id. Two curator regions
hold the auto positional ordinal `seg_0`. This lane was asked whether that is confined to those two
or is a broader surface.

**Verdict: the scope is exactly the two already-known cases — CONFIRMED NARROW, whole-corpus, not
sampled. No third instance exists.** But the measurement adds one fact cycle 7 did not have: one of
the two exposed regions is **cited by a curator `region` ground and two percepts**, which moves the
hazard from "geometry substitution" to "silent re-pointing of a curator's interpretation", squarely
inside spark-03. No collision has occurred; the one case where the data could have shown one is
clean.

---

## 1. Where each id form is minted, and which are collision-capable

**OBSERVED (code read, not inferred).** Every region-id mint site in `backend/` and `scripts/`,
plus the one frontend site:

| id form | file:line | expression | index source | collision-capable? |
|---|---|---|---|---|
| `seg_{i}` | `backend/services/vision_orchestrator/adapters.py:68` | `f"{id_prefix}_{i}"` | `for i, m in enumerate(masks)` — YOLO instance order | **YES — positional ordinal** |
| `region_{i}` | `backend/services/vision_service.py:513` | `f"region_{i}"` | `enumerate` over VLM anchor list | **YES — positional ordinal** |
| `fine_{i}` | `backend/services/vision_service.py:645` | `f"fine_{i}"` | `enumerate` over VLM fine-part list | **YES — positional ordinal** |
| `arch_{n}` | `backend/services/architecture_segmentation_service.py:137` | `f"arch_{len(regions)}"` | running count of *accepted* ADE blobs | **YES — accumulator ordinal** |
| `fseg_{n}` | `backend/services/fashion_segmentation_service.py:216` | `f"fseg_{len(regions)}"` | running count of *accepted* ATR instances | **YES — accumulator ordinal** |
| `refine_{hex10}` | `backend/services/vision_orchestrator/adapters.py:191` | `base_id or f"refine_{uuid.uuid4().hex[:10]}"` | 40 bits of uuid4 | **NO — random, safe by non-collision** |
| `reg_creator_{ms}` | `frontend/src/components/RegionSurface.jsx:215` | `` `reg_creator_${Date.now()}` `` | wall-clock ms | **NO — monotonic, not run-relative** |

Two corrections to the cycle-5 shorthand, both material:

1. Cycle 5 wrote the YOLO form as `seg_{prefix}_{i}`. It is `f"{id_prefix}_{i}"` with
   `id_prefix` **defaulting to `"seg"`**, and grep shows **no caller anywhere passes a non-default
   `id_prefix`** (`adapters.py:39` is the only definition; `segmentation_service.py:64` is the only
   production call site and passes it not at all). So the family is exactly `seg_{i}`, never
   parameterised in practice.
2. Cycle 5 wrote `arch_{len}` / `fseg_{len}` as if length-based were a distinct safety class. It is
   not: `len(regions)` is the count of regions accepted *so far in this run*, i.e. a dense
   0..N-1 ordinal identical in behaviour to `enumerate`. It is fully collision-capable. The only
   difference from `enumerate` is that skipped/filtered blobs do not consume an index.

**The `refine_*` exemption is narrower than it looks.** `adapters.py:191` reads
`base_id or f"refine_{...}"`. A refine that is given a `base_id` **keeps the base id** and mints
nothing. So refining an auto region named `seg_0` produces a *curator-owned region still called
`seg_0`* — that is the exact mechanism that creates the exposure measured in §2. `refine_*` is
only reached when a refine has no base (hand-started refine or a save-region-annotations round-trip).

**Is `actor` the only curator-ownership marker?** Checked, and for the merge guard: **yes**.
`posts.py:797` builds `creator_regions` from `r.get("actor") == "creator"` alone — no other field
participates. Other curator-signal fields exist (`user_note`, `prioritised`, `weight`,
`refined_from`, `detector == "sam2"`, `detector is None`) and are read elsewhere
(`vision_recovery.py:54,75`), but none of them confers re-dissect immunity. Corpus check for
divergence between markers: **0 non-`creator` regions in the whole corpus carry any of
`user_note` / `prioritised` / non-zero `weight` / `refined_from` / `detector: "sam2"`.** The marker
sets do not disagree anywhere, so `actor` is a sufficient probe here.

---

## 2. Whole-corpus measurement

`visualDictionaryDB.posts`, every document, read-only.

| measure | count |
|---|---|
| posts total | **421** |
| posts with a `region_annotations` field | 14 |
| … non-empty | **11** |
| … `[]` | 3 |
| … field absent / `null` | 407 |
| **regions total** | **57** |

(Cycle 7 measured 127 posts / 43 regions on 2026-07-21. The corpus has grown since; the creator-region
population has not — still 6.)

| `actor` | regions |
|---|---|
| `auto` | 51 |
| `creator` | **6** |
| missing / other | 0 |

Id-form class cross-tabulated against actor — this is the table the lane was asked for:

| actor | ORDINAL (collision-capable) | non-ordinal |
|---|---|---|
| `auto` | `fine_` ×26, `arch_` ×8, `fseg_` ×7, `region_` ×6, `seg_` ×4 — **51** | 0 |
| `creator` | **`seg_` ×2 — EXPOSED** | `refine_` ×4 — **SAFE** |

**Exposure totals: 2 regions, on 2 posts, out of 6 curator regions (33%) and 57 regions (3.5%).
4 curator regions are safe by uuid id. 0 curator regions use `reg_creator_*`.**

### 2a. The full exposed list (item 1 of the brief)

| post id (24-hex) | region id | pattern class | `refined_from` | `geometry_rev` | detector | provenance |
|---|---|---|---|---|---|---|
| `695be8b0a9ea58f1b6aef606` | `seg_0` | ORDINAL / `seg` (`adapters.py:68`) | `seg_0` | 3 | `sam2` | `sam2-refine`, `sam21_hiera_tiny`, prompt `box`, size 451×680 |
| `6a5b91ecbf74ef485d00399f` | `seg_0` | ORDINAL / `seg` (`adapters.py:68`) | `seg_0` | 2 | `sam2` | `sam2-refine`, `sam21_hiera_tiny`, prompt `box`, size 853×640 |

Both are genuine refine-in-place upgrades, confirming cycle 7. Both have `proposed: false`,
`user_note: ""`, `prioritised: false`, `weight: 0`, `depth: 0`, `label: null`, a live `mask_rle`.

### 2b. The safe curator regions, for contrast (item 3)

| post id | region id | class | `refined_from` | `geometry_rev` |
|---|---|---|---|---|
| `695be786a9ea58f1b6aef5ed` | `refine_c6485b9a94` | UUID — safe | `refine_c6485b9a94` | 2 |
| `6a5b923ebf74ef485d0039af` | `refine_3e81b38e50` | UUID — safe | — | 2 |
| `6a5b9273bf74ef485d0039b7` | `refine_5117cd9d1d` | UUID — safe | — | 1 |
| `6a5b9273bf74ef485d0039b7` | `refine_747d7bc5cd` | UUID — safe | `refine_747d7bc5cd` | 4 |

**EXPOSED 2 / SAFE 4.** The split is entirely explained by whether the curator refined an
existing auto region (keeps the ordinal) or started one without a base (gets a uuid).

---

## 3. Namespace crowding on the exposed posts (item 2)

How many candidates would a re-dissect have to emit before it collides?

| post | regions held today | `seg_*` occupancy | first colliding ordinal | collisions if a re-dissect emits `seg_0..seg_N` |
|---|---|---|---|---|
| `695be8b0a9ea58f1b6aef606` | **1** (only the curator `seg_0`) | `seg_0` = creator | `seg_0` | **1 — the very first candidate, guaranteed** |
| `6a5b91ecbf74ef485d00399f` | **1** (only the curator `seg_0`) | `seg_0` = creator | `seg_0` | **1 — the very first candidate, guaranteed** |

This is the worst possible crowding shape, not the best. Both posts hold the *zeroth* ordinal and
nothing else, so **any** YOLO re-dissect that finds at least one instance mask collides on its
first and highest-confidence detection. There is no depth of namespace to absorb it.

Whole-corpus `seg_*` occupancy, for context on how the family is used:

| post | `seg_*` present | total regions |
|---|---|---|
| `695be7faa9ea58f1b6aef5f7` | `seg_0` auto/yolo | 1 |
| `695be77ea9ea58f1b6aef5eb` | `seg_0` auto/yolo | 3 (+2 `arch_*`) |
| `695be794a9ea58f1b6aef5f1` | `seg_0` auto/yolo | 1 |
| `695be6c9a9ea58f1b6aef5e0` | `seg_0` auto/yolo | 10 (+9 `fine_*`) |
| `695be8b0a9ea58f1b6aef606` | `seg_0` **creator/sam2** | 1 |
| `6a5b91ecbf74ef485d00399f` | `seg_0` **creator/sam2** | 1 |

**OBSERVED:** every `seg_*` region in the corpus is `seg_0`; YOLO has never persisted more than one
instance mask on any post here. Two posts mix families (`seg_`+`arch_`, `seg_`+`fine_`), which is
direct evidence that ordinal namespaces from different detectors do coexist in one document — so an
`arch_`/`fine_` re-dissect on a post already holding those families would collide across the same
axis if a curator ever refined one of them. **INFERENCE:** that has not happened yet only because
all four refines-with-base so far landed on `seg_0`; there is nothing in the code that prevents the
same exposure appearing on `fine_*`, `arch_*`, `fseg_*` or `region_*` the next time a curator
refines one of those. The surface is 2 today and structurally open, not closed.

---

## 4. Has a collision already happened? (item 5)

**No evidence of one, and one of the two cases is affirmatively clean.**

| check | result |
|---|---|
| duplicate ids within a single post's `region_annotations` | **0 posts, corpus-wide** |
| curator region whose `detector`/`geometry_provenance` shows an auto fingerprint | **0** — all 6 are `sam2` + `sam2-refine`/`rle` (reconfirms C7 §2) |
| `refined_from` inconsistent with own id | **0** — the 3 present values each equal the region's own id, as refine-in-place produces |
| stored mask vs the mask the embedding layer indexed | see below |

The strongest available test is on `6a5b91ecbf74ef485d00399f`, the only exposed post with
`region_embeddings`. Those documents store `mask_hash` and `geometry_rev` captured at index time, so
a substitution between then and now would show as a hash divergence:

| artifact | `geometry_rev` | `mask_hash` |
|---|---|---|
| live region `seg_0` (recomputed from stored `mask_rle`) | 2 | `ee1e781b2dc27e3081e50254c406516655bf8a149e471660be0f4e5f3c2b0a39` |
| embedding `…_identity_6a5b91ecbf74ef485d00399f_seg_0` | 2 | same |
| embedding `…_context_…_seg_0` | 2 | same |

**Exact match, `stale_reason: ""`.** The geometry that `seg_0` names today is the same geometry that
was indexed on 2026-07-19. No substitution occurred on that post between those two moments.

`695be8b0a9ea58f1b6aef606` has **no** `region_embeddings`, so no independent witness of its earlier
geometry exists.

**Stated plainly, as the brief asks: for that post the data CANNOT distinguish "a collision happened
and the curator's mask was kept" from "a normal refine happened".** Both leave `refined_from: seg_0`,
`geometry_rev: 3`, `detector: sam2` and a sam2-refine provenance — the guard's whole point is that
the surviving record looks identical either way. That is not a null result; it is the finding: the
merge guard is **unfalsifiable from stored state**. The only reason we can clear
`6a5b91ecbf74ef485d00399f` at all is that a *different* subsystem (embedding staleness) happened to
keep a hash.

Also checked, and it does not help: `vision_runs` holds **2** documents (posts
`6a5b9275bf74ef485d0039b8` and `6a5fef58a3ddb6341fd69930`), neither of them an exposed post, both
recording `creator_preserved: 0`. Run telemetry began with Circulation Spine P1 (`85652ed`) and
therefore covers none of the history of these two regions. **No claim is made here that no
re-dissect ran on them.**

---

## 5. Judgement — is this a spark-03 surface, and how big?

**Yes, and the measurement makes it sharper than cycle 7 could.**

spark-03 says evidence loss must be *announced*, not merely survived. The guard at `posts.py:804-805`
does the opposite twice over:

**OBSERVED (code):** the id guard fires *before* the geometry dedup. Reading `posts.py:798-828` in
order — `continue` on `r.get("id") in creator_ids` at 804, and only at 826 does
`_is_duplicate_geometry(r, creator_regions, 0.7, ...)` run. So a candidate named `seg_0` is dropped
**without its mask ever being compared to anything**, while a candidate named `seg_1` that overlaps
the curator's region *is* compared and drops on a measured IoU. The name-based drop is the one with
no evidence behind it, and it is the one that runs first.

**OBSERVED (telemetry):** the merge stage emits `{"creator_preserved": n, "kept_auto": n,
"candidates": n}` (`posts.py:833-835`). A candidate dropped by the id guard is invisible in that
triple — it is neither preserved nor kept, and `candidates` counts it as if it had been considered.
There is no field anywhere that says "a new detection was discarded because its name was taken".
`kept_auto` silently shrinks. That is exactly the announce-vs-survive failure.

**The new fact this lane adds — the citation:** post `695be8b0a9ea58f1b6aef606` holds a `region`
ground `gnd_mrtof0k1_0` with `region_id: "seg_0"`, cited by two curator percepts,
`pctx_mrtof46o_0` (expression `arrow`) and `pctx_mrtofp6b_1` (expression `fold`), both
`actor: creator`, authored 2026-07-20. So the exposed `seg_0` is not inert geometry: it is the
referent of a curator's interpretation.

That inverts the detached-ground failure mode this program already knows. A re-dissect that *lost*
a region leaves a **detached** ground — visibly broken, and `scripts/detached_ground_sweep.py` can
find it. A re-dissect that collides on `seg_0` leaves a ground that **still resolves**, to geometry
that may be a different object, and nothing anywhere reports a change. Commit `f4d7b48` ("recall
must not perform evidence that no longer resolves") addressed the loud case. This is the quiet one.

**Size, honestly stated:** 2 regions / 2 posts / 1 of them cited / 0 observed corruptions. It is a
**small, fully enumerated, currently-uncorrupted surface with no detector on it.** The risk is not
that data is wrong today — measured, it is not — but that if it goes wrong there is no record and
no alarm, and that the guard's design makes new instances of the exposure appear every time a
curator refines an auto region with an ordinal id.

**INFERENCE, flagged:** the exposure count will grow monotonically with curator refine activity,
because the refine path preserves the base id by design (`adapters.py:191`) and nothing renames it.
It is not inferred from code shape alone — the 2/4 split in §2b is the observed consequence of that
line, on the same corpus.

---

## 6. Minimal future fix — NOT implemented

**One sentence: at `posts.py:804`, do not `continue` silently — compare the incoming candidate's
mask against the creator region that is about to suppress it, and when they are not the same
geometry, record the drop (a `suppressed_by_id` count in the `STAGE_MERGE_CURATOR` detail at
minimum) instead of discarding it unannounced.** That is HW-C6 Lane 1's Option D applied to the
name-collision path specifically, and it is an announcement, not a repair — it changes no stored
geometry and needs no id migration.

The deeper fix (stable non-positional region ids) is a schema and migration question that touches
curator geometry, and is explicitly out of scope for this lane.

---

## What was deliberately NOT done

- **No source file was edited.** `backend/routers/posts.py:804-815` remains exactly as found,
  including the dead carry cycle 7 identified.
- **No production data was written.** Only `find` and `count_documents`. The two exposed `seg_0`
  regions, their post documents, their grounds, their percepts and their embeddings are untouched.
- **Neither exposed region was renamed or re-keyed.** Rewriting `seg_0` to a stable id is the real
  remedy and is a mutation on curator geometry with a cited ground hanging off it; it is not
  designed and was not attempted.
- **No repair of anything.** Nothing was found needing repair, and nothing would have been repaired
  if it had been.
- **No re-dissect, no refine, no vision call.** Nothing was executed against either exposed post to
  "see what happens" — that would have been the collision.
- **No claim that no collision ever occurred on `695be8b0a9ea58f1b6aef606`.** Its stored state is
  compatible with both a collision and a normal refine, and it has no embedding witness. §4 says so
  rather than picking the comfortable reading.
- **No claim from `vision_runs`.** Two documents, neither on an exposed post, all postdating the
  regions in question.
- **No fix implementation, no test added, no other lane started.**
- **No `.env` value printed.** `MONGO_DETAILS` is present; that is the whole report on it.

## Open question for a later cycle

If the merge-boundary comparison in §6 is built, `695be8b0a9ea58f1b6aef606` is its first and best
subject — a cited, curator-owned, zeroth-ordinal region on a single-region post. When it observes
that this run's `seg_0` is a different object, what does it owe the curator whose percept
(`pctx_mrtof46o_0`, "arrow") is pointing at the old one: drop the candidate silently as today, keep
both under distinct ids, or surface the divergence? Cycle 7 left this open; this lane leaves it open
with a name attached to the percept that will be affected.
