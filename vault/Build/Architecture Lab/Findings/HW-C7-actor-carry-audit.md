# HW-C7 — The `actor == "creator"` carry: dead code today, live for eleven days in July

**READ-ONLY audit. No production data was written. No source file was edited. No repair was
performed.** Horizon Weave cycle 7, Lane 3. Mongo access was `find` / `count_documents` only.

Cycle 6's decision doc (`HW-C6-evidence-identity-decision.md`) named the carry at
`backend/routers/posts.py:814-815` "the real corruption" — a fresh auto region inheriting
permanent re-dissect immunity on a string-id match. This lane was asked to verify or reject that
claim **by measurement**.

**Verdict: the claim is REJECTED for the code as it stands today, and 0 promotions are observed in
the corpus.** But the rejection comes with a date attached — the branch was genuinely live and
reachable between 2026-07-08 and 2026-07-19, and it is only unreachable now because a *different*
commit incidentally shadowed it.

---

## 1. Possible in code?

### 1a. The block as it stands (`backend/routers/posts.py:792-830`)

```
existing      = {r.get("id"): r for r in existing_list}          # 794 — last-wins
creator_ids   = {r.get("id") for r in existing_list if actor == "creator"}   # 797-798
for r in candidates:
    if r.get("id") in creator_ids: continue                      # 804-805  ← guard
    ...
    prev = existing.get(r["id"])                                 # 809
    if prev and prev.get("actor") == "creator": r["actor"] = "creator"   # 814-815 ← carry
```

**Reachability verdict: UNREACHABLE. Provably dead code, under every input.**

The proof is that both the guard and the carry key off the *same* list by the *same* equality:

| step | derived from | equality used |
|---|---|---|
| `creator_ids` (798) | `existing_list` — no filtering other than `actor == "creator"` | set membership (`__hash__`/`__eq__`) |
| `existing` (794) | the **same** `existing_list` | dict key lookup (`__hash__`/`__eq__`) |

If the carry fires, then `prev` is an `existing_list` entry with `actor == "creator"`, so
`prev.get("id") ∈ creator_ids`. `prev` was retrieved *as the value at key* `r["id"]`, so
`prev`'s key equals `r["id"]` under exactly the equality that the set uses. Therefore
`r.get("id") ∈ creator_ids`, therefore `continue` already fired at line 805. Contradiction.

The interesting edge cases all fail to break it, and were tested rather than argued:

| edge case | outcome | why |
|---|---|---|
| duplicate ids, one creator one auto (`existing` last-wins vs `creator_ids` set-over-all) | still `continue` | `creator_ids` is a **superset** of the ids `existing` can resolve to a creator, in both orderings |
| `ObjectId` vs `str` id | consistent miss | dict lookup and set membership use the same `__eq__`; both miss together |
| `id: None` on an existing creator entry, candidate with `id: None` | `continue` | `None` is hashable and lands in `creator_ids` |
| candidate with **no** `"id"` key at all | **`KeyError` at line 809** — a 500, not a promotion | `r.get("id")` → `None`, misses the set, then `r["id"]` raises |
| `float("nan")` id | consistent miss | CPython's identity-then-equality check applies to both the set and the dict |
| unhashable id (list/dict) | `TypeError` at 804 | crashes before reaching the carry |

**OBSERVED (a run, not an argument).** A brute-force simulation of the control flow above
(`scratchpad/reach.py`, not added to the repo) enumerated every `existing_list` of length 0–2 over
an id domain containing `"a"`, `"b"`, `None`, the `1 / 1.0 / True` equality clique, an
`ObjectId`-like wrapper that hashes as a `str` but never equals one, `nan`, and a missing-`id` key,
crossed with `actor ∈ {creator, auto, None}`:

```
cases run: 6813
carry-branch firings (prev.actor == 'creator' reached): 0
exceptions raised (crash, not promotion): {'KeyError': 651}
```

Zero firings. The 651 `KeyError`s are the latent id-less-candidate 500 noted in the table; no
current detector emits an id-less region (`seg_{i}`, `arch_{i}`, `fseg_{i}`, `region_{i}`,
`fine_{i}`, `refine_{hex}` all stamp one), so it is unreachable in practice too, and it is not a
promotion under any reading.

### 1b. It was NOT always dead — the eleven-day window

**OBSERVED (git).** The carry and its guard were introduced by different commits, eleven days apart:

| commit | date | what it did |
|---|---|---|
| `153d469` — *unified Region model + retire bounding_box_tags* | **2026-07-08** | introduced `if prev.get("actor") == "creator": r["actor"] = "creator"`, with the comment *"a creator who edited an auto region keeps their authorship"* |
| `00b71c5` — *C5 — mixed-domain scheduling + compact profile-control UX* | **2026-07-19** | introduced `creator_regions` / `creator_ids` and the `continue` guard, which incidentally shadowed the carry |

The pre-C5 block had **no guard at all** — the loop ran over every region and the carry was the
only thing that preserved authorship. In that window the promotion was fully reachable: any
re-dissect that regenerated a positional ordinal already held by a creator region would have
stamped `actor: "creator"` onto the fresh auto candidate.

**INFERENCE.** The carry is not a bug that was written; it is a mechanism that was *superseded*.
C5 replaced field-level carry with whole-region preservation and left the older line standing. It
is vestigial, not malicious. That reading matters for the fix in §5.

### 1c. Other carry sites — none

**OBSERVED.** Every `actor` assignment in the repo outside tests:

| site | writes | promotion risk |
|---|---|---|
| `posts.py:807` | `r.setdefault("actor", "auto")` | none — defaults down, never up |
| `posts.py:815` | the carry | dead (§1a) |
| `vision_orchestrator/adapters.py:192` | `"actor": "creator"` in `refined_mask_to_region` | **legitimate** — a refine is user-directed, by definition |
| `segmentation_service.py` / `architecture_segmentation_service.py:138` / `fashion_segmentation_service.py:217` / `vision_service.py:514,646` | `"actor": "auto"` | none |
| `taste_signal_service.py:176` | `"actor": "audience"` | different actor space |
| `geometry_recovery.py :: apply_mask_to_region` | preserves `actor` unchanged while replacing geometry | none — explicitly identity-preserving |
| `frontend RegionSurface.jsx:215` | hand-drawn `reg_creator_*`, `actor: 'creator'`, `detector: null` | legitimate |

`POST /{id}/region-annotations` (`posts.py:989`) persists whatever the client sends — a client
*could* post `actor: "creator"` on anything, but that is a curator save, not a silent promotion.
`refine-region/confirm` (`posts.py:1233-1244`) upgrades a base region in place and carries only
`prioritised`/`weight`/`user_note`/`depth`/`parent_id` — it never reads or copies `actor`.
No script under `scripts/` writes `actor`.

**No second carry exists anywhere the cycle-6 doc did not look.**

### 1d. What actually depends on `actor == "creator"`

This is what makes the carry consequential or not:

| consumer | consequence of `actor == "creator"` |
|---|---|
| `posts.py:797,804` | **the re-dissect immunity itself** — the region is copied into `creator_regions` verbatim and every colliding candidate is dropped |
| `services/evidence_packet.py:85` | `curator_label` becomes authoritative and `authoritative: true` is sent to the VLM, which is told not to overwrite it |
| `services/vision_recovery.py:59,76` | `actor` is part of the curator-signature comparison — a changed `actor` reads as a curator data change |
| `frontend RegionOverlay.jsx:21` | `.rs-shape--creator` styling |

So the immunity claim in the cycle-6 doc is **correct about the stakes** — `actor` really does gate
permanent survival and VLM-override protection. It is only wrong about the reachability.

---

## 2. Observed in corpus?

Whole-corpus sweep of `visualDictionaryDB.posts`, read-only.

| measure | count |
|---|---|
| posts total | 127 |
| posts with `region_annotations` field present | 13 |
| … non-empty (`region_annotations.0` exists) | **10** |
| … `[]` | 3 |
| … `null` | 114 |
| **regions total** | **43** |

| `actor` | regions |
|---|---|
| `auto` | 37 |
| `creator` | **6** |
| missing / other | **0** |

`detector` cross-tabulated against `actor` — this is the discriminating table:

| actor | detectors observed |
|---|---|
| `auto` | `vision` ×18, `segformer_ade` ×8, `segformer_clothes` ×7, `yolo` ×4 |
| `creator` | **`sam2` ×6 — and nothing else** |

| actor | id prefixes observed |
|---|---|
| `auto` | `fine_` ×18, `arch_` ×8, `fseg_` ×7, `seg_` ×4 |
| `creator` | `refine_` ×4, `seg_` ×2 |

### The fingerprints used, and how far they can be trusted

The carry copies **only** `actor`. It does **not** copy `detector`, `geometry_provenance`,
`confidence`, `refined_from`, or `geometry_rev` — line 808 sets `r.setdefault("detector", "vision")`
on the candidate *before* the carry, and the candidate arrives from a detector that already stamped
its own. **A promoted region therefore keeps its auto detector and auto geometry provenance while
wearing `actor: creator`.** That is the exact signature to look for:

| fingerprint | promoted auto region would show | genuine curator region shows |
|---|---|---|
| `detector` | `vision` / `yolo` / `segformer_ade` / `segformer_clothes` | `sam2` (refine) or `null` (hand-drawn) |
| `geometry_provenance.via` | `detect-regions` | absent |
| `geometry_provenance.method` | `segformer-ade`, `ultralytics-retina`, … | `sam2-refine` or `rle` |
| `geometry_provenance.adapter` | `segformer_b0_ade`, … | `sam21_hiera_tiny` |
| `refined_from` | absent | usually present |

**This fingerprint is high-reliability, not a guess.** There are exactly two code paths that can
author a creator region — `refined_mask_to_region` (always `detector: "sam2"`,
`adapter: sam21_hiera_tiny`, `method: sam2-refine`) and the frontend's hand-drawn
`reg_creator_${Date.now()}` (`detector: null`). Neither can produce `detector: "vision"` or a
`segformer_*` adapter. The two families are cleanly separable in this corpus; there is no ambiguous
middle.

**RESULT: 0 promoted regions observed. All 6 creator regions carry `detector: "sam2"` and
sam2-refine provenance. Not one wears an auto-authored fingerprint.** The negative is clean.

Additional negative: only **1** document exists in `vision_runs`, a single `dissect` on 2026-07-21.
Run telemetry only began with `85652ed` (Circulation Spine P1), so this **cannot** be used to argue
that no re-dissect ran during the 2026-07-08 → 2026-07-19 window. The corpus evidence stands on the
detector fingerprint alone, which is sufficient.

---

## 3. Which posts / regions

**Nothing suspicious. All six creator regions are genuine curator authorship.** Listed in full for
the record, by full 24-hex post id:

| post id | region id | detector | geometry_provenance | confidence | `refined_from` | `geometry_rev` |
|---|---|---|---|---|---|---|
| `695be8b0a9ea58f1b6aef606` | `seg_0` | `sam2` | adapter `sam21_hiera_tiny`, method `sam2-refine` | 0.848 | `seg_0` | 3 |
| `6a5b91ecbf74ef485d00399f` | `seg_0` | `sam2` | adapter `sam21_hiera_tiny`, method `sam2-refine` | 0.588 | `seg_0` | 2 |
| `695be786a9ea58f1b6aef5ed` | `refine_c6485b9a94` | `sam2` | adapter `sam21_hiera_tiny`, method `sam2-refine` | 0.844 | `refine_c6485b9a94` | 2 |
| `6a5b923ebf74ef485d0039af` | `refine_3e81b38e50` | `sam2` | `via: save-region-annotations`, method `rle` | 0.851 | — | 2 |
| `6a5b9273bf74ef485d0039b7` | `refine_5117cd9d1d` | `sam2` | adapter `sam21_hiera_tiny`, method `sam2-refine` | 0.906 | — | 1 |
| `6a5b9273bf74ef485d0039b7` | `refine_747d7bc5cd` | `sam2` | adapter `sam21_hiera_tiny`, method `sam2-refine` | 0.847 | `refine_747d7bc5cd` | 4 |

Every one has `user_note: ""`, `prioritised: false`, `weight: 0` — no curator *meaning* rides on any
of them yet; only curator *geometry*.

### The two `seg_0` rows deserve a second look — and survive it

`seg_0` is an **auto positional ordinal**: `adapters.py:67` mints `f"{id_prefix}_{i}"` with
`id_prefix="seg"` for every YOLO instance mask. A region whose id is an auto ordinal but whose
actor is `creator` is precisely the shape one would expect a promotion to leave behind.

It is not one. Both were produced by the legitimate refine-in-place path: `refine-region/confirm`
called with `base_id="seg_0"` returns a region that keeps the base identity (`adapters.py:189`,
`"id": base_id or f"refine_{...}"`) and stamps `actor: "creator"`, `detector: "sam2"`. The stored
`refined_from: "seg_0"` and `geometry_rev` of 2–3 confirm the upgrade chain. A curator selected an
auto YOLO region and refined it; the id simply never changed.

**INFERENCE, flagged as such:** this is the designed behaviour, and it is also the collision
surface — see §4.

---

## 4. Is curator identity semantics at risk?

**Not by the carry. Yes by the id, and the two are the same hazard wearing different clothes.**

The carry is dead (§1a) and leaves no trace in the corpus (§2). Cycle 6's "the real corruption"
framing does not survive measurement. **REJECTED.**

But the guard that killed it inherited the danger. `continue` at line 805 fires on a bare **string
id match**, and Cycle 5 established that `fine_{i}`, `seg_{i}`, `arch_{i}`, `fseg_{i}`, `region_{i}`
are **per-run positional ordinals** — a re-dissect regenerates them from scratch against whatever
the detector finds this time. The two interact directly:

| | old carry (dead) | current guard (live) |
|---|---|---|
| trigger | `prev.actor == "creator"` on an id match | `r.id ∈ creator_ids` on an id match |
| effect | an auto region is **promoted** to creator | a **new auto detection is silently dropped** and the stale creator region is kept |
| damage | a machine region gains permanent immunity | the curator's region survives, but now points at whatever the *old* run's `seg_0` was, while the image's actual `seg_0` this run may be an entirely different object |

Both are the same root cause: **identity by positional ordinal, trusted across runs.** The carry
would have corrupted authorship; the guard corrupts *reference* — which is exactly Cycle 5's
substitution hazard, and exactly the second failure mode HW-C6's detached-flag finding described.

The corpus has this loaded and ready: `695be8b0a9ea58f1b6aef606` and `6a5b91ecbf74ef485d00399f`
each hold a creator-owned `seg_0`. Re-dissect either post with YOLO in the source position and the
guard will drop the newly-detected `seg_0` — a different mask of possibly a different object — in
favour of the curator's older one, and report `creator_preserved: 1` as if that were a success.
Nothing surfaces the substitution.

So: curator identity semantics are **safe today** and were **at risk for eleven days in July**,
with no residue. What is at risk *going forward* is not who authored a region but **what a curator's
region is a region of**.

---

## 5. Minimal future fix

**For the carry itself: delete lines 814-815.** That is the whole fix. It is dead code that has
already been superseded by whole-region preservation at 797/832; removing it changes no behaviour
and removes the trap that would reopen the moment anyone loosens the `continue` guard. It is a
two-line deletion in a comment-heavy block, and it should carry a comment saying C5's
`creator_regions` replaced it. **Not implemented here — this lane is read-only.**

Optional and strictly secondary: line 809's `r["id"]` should be `r.get("id")` to match line 804 and
turn a latent 500 into a skip. No current detector can trigger it. Bundle it or leave it.

**What the carry fix does NOT address, and should not be mistaken for:** the ordinal-collision
substitution in §4. That needs the merge-boundary geometry check (HW-C6 Lane 1's Option D) — compare
the incoming candidate's mask against the creator region it is about to be suppressed by, and
record a divergence when they are not the same thing. Deleting the carry must not be reported as
having closed the identity hazard. It closes a vestigial line and nothing more.

---

## What was deliberately NOT done

- **No source file was edited.** The two dead lines remain in `backend/routers/posts.py` exactly as
  found. Deleting them is a code change and belongs to a build lane, not an audit.
- **No production data was written.** Only `find` and `count_documents`. The six creator regions,
  including the two `seg_0`s, are untouched.
- **The two ordinal-id creator regions were not renamed or re-keyed.** Rewriting `seg_0` to a stable
  id would be the real fix for §4's hazard and is a production mutation on curator geometry; it is
  not designed and was not attempted.
- **No test file was added to the repo.** The reachability brute-force lives only in the session
  scratchpad.
- **No claim that no re-dissect ran during the July window.** `vision_runs` holds one document and
  postdates the window; the negative in §2 rests on detector fingerprints, not on run history.
- **No `.env` value was printed.** `MONGO_DETAILS` is present; that is all that is reported.

## Open question for a later cycle

The two creator-owned `seg_0` regions are the cleanest available test case for the merge-boundary
detector. If it is built, does it run against them first — and if it observes that this run's
`seg_0` is geometrically unrelated to the curator's, does it drop the candidate (today's silent
behaviour), keep both under distinct ids, or surface the divergence to the curator? Not decided
here.
