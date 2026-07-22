# HW-C6 — Evidence identity: what a region id is allowed to mean

**DECISION DOC — no implementation authorized, no production data touched; supersedes HW-C4 in part.**
No source file, schema, route, migration, test or record was created or modified by this lane. Mongo
was not queried (the corpus facts below are carried from HW-C5, which read it with `find` /
`count_documents` only). No model/LLM calls. Nothing staged, committed or pushed. Code was read only,
and every claim marked *verified* below was re-checked at source in this lane.

| | |
|---|---|
| **id** | HW-C6 · re-opens and re-answers **D-1** |
| **date** | 2026-07-21 |
| **branch** | `feat/rehearsal-research-r1` |
| **status** | **Proposed** — awaiting the orchestrator's acceptance. Nothing may be built from it until then, and even then see §8. |
| **decision, in one line** | **Detect substitution where it is created — at the dissect merge boundary — and keep notify. Do not change id generation now. Do not fingerprint the Ground.** |
| **supersedes** | `Decisions/HW-C4-detached-evidence-repair-fork.md`, **in part** — see §1.3 for exactly which parts |
| **key input** | `Findings/HW-C5-positional-id-reattachment-probe.md` |

---

## 1. What changed since HW-C4

### 1.1 The probe's evidence

HW-C4 named ordinal id reuse in its §2(b) and listed a read-only probe as an open trigger in its §7.
HW-C5 ran that probe. Its findings, re-verified at source in this lane:

**Verified — four of five id-generation sites emit per-run positional ordinals.**

| site | expression | id is |
|---|---|---|
| `backend/services/vision_service.py:645` | `"id": f"fine_{i}"` from `enumerate(...)` over the VLM parts list | rank in one response |
| `backend/services/vision_orchestrator/adapters.py:68` | `"id": f"{id_prefix}_{i}"` over the YOLO mask array | rank in one response |
| `backend/services/architecture_segmentation_service.py:137` | `"id": f"arch_{len(regions)}"` | append counter |
| `backend/services/fashion_segmentation_service.py:216` | `"id": f"fseg_{len(regions)}"` | append counter |
| `backend/services/vision_orchestrator/adapters.py:191` | `"id": base_id or f"refine_{uuid.uuid4().hex[:10]}"` | random, or deliberate identity continuity |

None of the four ordinal sites incorporate the mask, box, label, image, run or timestamp. **The id
encodes rank within one detector response and nothing else.** `refine_*` is safe from this hazard by
non-collision (uuid4), **not** by content-addressing — so no part of a "content-derived ids" fix is
already half-built anywhere in the repo. HW-C4's §2(b) said ids were positional; HW-C5 establishes
that this is true at four independent sites and false at exactly one, and that the one exception is
accidental.

**Verified — the persistence path matches on that string alone.** `backend/routers/posts.py:808-813`
carries `prioritised`, `weight`, `user_note` **and the `actor == "creator"` promotion** from `prev`
to the new candidate whenever `existing.get(r["id"])` hits, where `existing` is keyed purely by id.
`posts.py:847` then persists with one wholesale `{"$set": {"region_annotations": regions}}`. There is
no history collection, no `superseded` flag, no archive.

**Verified — `resolveGround` compares nothing but the string.** `frontend/src/differential/grounds.js:71`:
`regions.find((r) => r.id === ground.region_id)`, `detached: !region`. No geometry, no `mask_rle`, no
`geometry_rev`, no label, no detector, no creation-time record enters the comparison. The file's own
header is honest about the design — *"If a re-dissect replaces that Region, the Ground degrades
gracefully"* — but "replaces" silently assumes the replacement does not reuse the identifier.

**HW-C5's synthetic trace** (scratchpad only, importing the real unmodified `grounds.js`) walks a
ground on `fine_3` = "hair" through the three generations the corpus actually exhibits:
`detached=false` (hair) → `detached=true` (after the `arch_*` re-dissect — today's corpus state) →
`detached=false` (after a `fine` re-run, now "gravel", geometry moved). The final state is
indistinguishable, by every signal the system computes, from the original.

**The named latent instance.** Both detached posts cite `fine_*` ids. Two other posts currently hold
live `fine_0 … fine_8` arrays from the same loop, so the fine pass routinely emits ordinals 0–8 on
this corpus. If the fine pass is re-run on `695be786` or `695be794` and returns four or more parts,
`fine_3` exists again and `gnd_mrqp8tls_0` resolves to whatever the VLM listed fourth. `fine_0` needs
only a non-empty response. **Three of the four grounds this fork exists for are one ordinary
re-dissect away from silently resolving to an unrelated shape.** This is inference from a single
snapshot, labelled as such by HW-C5 and not upgraded here.

### 1.2 The two facts HW-C4 did not have

1. **The dissect path never looks at `grounds`.** `grep -n 'grounds' backend/routers/posts.py` returns
   one hit, an unrelated response projection. The route cannot notice that it is about to strand or
   re-attach a ground.
2. **The detection logic already exists and is wired to no router** — `geometry_recovery.py:153`. §5
   treats this at length.

### 1.3 What of HW-C4 is superseded, and what still stands

**Superseded (three specific things, no more):**

- **HW-C4 §4's completeness.** Its decision line — *"Notify. Do not tombstone."* — presents as a
  complete answer to the detached-evidence question. It is a complete answer to **half** of it.
  Superseded: the implicit claim that choosing notify closes D-1.
- **HW-C4 §7's trigger row** *"§2(b) id-reuse probe — never run — revisit immediately on any result,
  either way."* Discharged. The probe ran. This document is the revisit.
- **HW-C4 §5.3's blanket refusal**, insofar as it forbids *any* change to `detect-regions`' merge.
  §7 below concludes that the merge's unconditional carry-by-id is itself a defect and must become
  proposable. It remains unbuilt and ungated by this doc, but it may no longer be refused by
  reference to HW-C4.

**Still standing, unweakened, and re-affirmed here:**

- **Notify, not tombstone**, for loss-by-absence. HW-C4's load-bearing argument — that a tombstone is
  a *change to state* where a notification is *speech about state*, and that flipping `detached` to
  false silently re-arms the exact rendered behaviour A2R disarmed, with no code change and no
  failing test — is correct, and HW-C5 strengthens it rather than undermining it.
- **Every invariant in HW-C4 §3** (`mask_rle` canonicity; geometry never duplicated onto a Ground;
  `region_annotations` as single source of truth; creator regions survive re-dissect; A2R's honesty
  property; no blame; K-4 no fabricated repair targets; no implicit preference for geometry-bearing
  grounds).
- **HW-C4 §5's entire refusal list**, except as narrowed in §5.3 above. In particular §5.2 (no repair
  affordance), §5.5 (no rate — 36.4 % must never appear), §5.9 (the four detached grounds are the
  fixture and are not to be touched).
- **HW-C4 §4b's rejection** of a durable detachment note on the Ground. §4 below shows the
  ground-side fingerprint is that rejected shape in better clothes, and rejects it again on the same
  grounds plus one new one.
- **HW-C4 §4c** ("pin the cited") remains named, unchosen, and reserved for its own decision.

---

## 2. Why notify-only is insufficient

Every notification HW-C4 contemplates fires on the same predicate. At the moment of loss (§Option 2:
*"at the moment an operation drops Regions that Grounds cite"*), at rest (the quiet derived marks
B-02 / B-03b / B-06, all reading `resolveGround`'s boolean), and in recall (A2R's `evidenceNote` and
`unresolvedGroundIds`, both derived from `isResolved`) — **all of them fire on `detached === true`.**
Under re-attachment `detached` is `false`: the ground is not stranded, it is *occupied*. The
unresolved count is zero, the evidence note is empty, and a moment-of-loss check written exactly as
HW-C4 describes would compute *"cited ids still present: `fine_3` ✓"* and correctly stay silent. The
notification is not merely absent — **it is affirmatively wrong, and it is wrong by working exactly as
designed.** Worse, if the latent re-dissect happens, the chosen policy reports the corpus as
*healthier* — four detached grounds becoming one or zero — at the precise moment the citations stop
being dead and start being false. Notify covers loud-by-absence and has no mechanism whatsoever for
silent-by-substitution; the two failures are complements, not a whole and a part, so a policy
addressed to one is orthogonal to the other rather than a partial answer to it. And below the Ground
layer the same substitution already runs unattended on curator-authored fields
(`posts.py:808-813`), reachable with no frontend involvement at all, covered by no notification
anyone has proposed.

---

## 3. The options

**Invariants no option may break** (carried from HW-C4 §3, re-verified this lane against
`schemas/post.py:46-52`):

- `mask_rle` is authoritative identity on the **Region**; `box` / `polygons` are derived from it by
  `canonicalize_geometry`, `geometry_rev` bumps on re-derivation, `geometry_provenance` carries
  lineage. Nothing may carry a `mask_rle` it did not get from a real derivation.
- **Geometry is never duplicated onto a Ground.** The region adapter stores `region_id` and nothing
  else, deliberately. No option may copy a mask, a polygon or a box onto a ground.
- `region_annotations` is the single source of truth, iterated by ~10 backend consumers. Anything
  placed in that array is seen by all of them.
- Creator regions survive re-dissect intact (`posts.py:795-797`). No option may weaken this.
- **A2R's honesty property:** a ground that draws nothing must not receive a highlight step, and a
  percept whose evidence does not resolve must not be performed as though it does.
- **No blame**, and **no fabricated repair targets** (K-4, permanent): no IoU re-match, no *"did you
  mean `arch_2`?"*, no automatic re-pointing.
- **No implicit preference for geometry-bearing grounds.** Reference semantics are deliberate.

### Option A — id stability (content-derived or otherwise non-positional ids)

**Concretely.** Replace the four ordinal expressions with something a different shape cannot
reproduce: `fine_<hash(mask_rle)>`, or a uuid4 per region as `refine_*` already does.

**Cost.** Touches four generation sites in three services. **Every existing id in the corpus becomes
legacy** — `fine_0…8`, `arch_0…5`, `fseg_0…6`, `seg_0` are all live and cited, so this needs dual-read
or a migration, and a migration is a write to the four-ground fixture that HW-C4 §5.9 forbids. Ids
stop being human-readable, which debug workflows, fixtures and every doc in this vault (including
this one) rely on to name specific regions.

**What it claims epistemically.** *An identifier denotes a shape, not a position.* That is the
correct claim — it is what everything downstream already assumes. It is also the strongest claim on
offer, which is precisely why it should not be made casually.

**How it could go wrong.** Content-derived is not a synonym for stable: a hash of `mask_rle` churns
under harmless preprocessing drift, so a genuinely unchanged region can get a new id and *manufacture*
detachment where none occurred — converting a silent-false-positive problem into a loud-false-negative
one. Conversely, a stable shape re-deriving the same id makes re-attachment *legitimate* in exactly
the case where it is legitimate — which is arguably right, and **nobody has decided it**. A random
uuid avoids both but destroys the diagnostic legibility of the id and still requires the migration.

**Invariants at risk.** None structurally, but the migration path collides with §5.9 (do not touch the
fixture) and with `region_embeddings`, which key on `region_id` and would be orphaned wholesale.

### Option B — generation / run stamping

**Concretely.** Each region carries which run produced it: either a `run_id` / `generation` **field**
alongside the unchanged id, or the stamp folded into the id string (`fine_3@run7`).

**Cost.** Needs a real `VisionRun` per dissect. **DATA-1-blocked: one `vision_runs` document exists
corpus-wide**, for post `6a5b9275bf74ef485d0039b8`, a dissect that produced nothing
(`{anchor_count: 0, fine_count: 0, region_count: 0}`), on a post unrelated to any detached ground.
Field-form is a small additive schema change; string-form is Option A's migration under another name.

**What it claims epistemically.** *This region came from this operation.* True, checkable, and it is
the history the corpus provably lacks (§6). It is the honest home HW-C4 §4b already identified for
detachment events.

**How it could go wrong.** In field-form it **detects nothing on its own**: `resolveGround`'s string
match is unchanged and the hazard survives untouched. The failure mode is a fix that is built, is
green, is correct, and changes no behaviour — the most expensive kind of nothing. In string-form it
inherits every migration problem of Option A.

**Invariants at risk.** None. This is the most inert option, in both senses.

### Option C — ground-side fingerprint

**Concretely.** The Ground records something about what it pointed at — e.g. `region_mask_hash` at
creation time. `resolveGround` compares, and distinguishes *resolved-and-same* from
*resolved-but-changed*.

**Cost.** Smallest surface of any option: one optional field; `hydrateGrounds` already preserves
unknown fields verbatim; `mask_hash` already exists (`region_embedding_service.py:84`) and the
comparison is already written and tested (`geometry_recovery.py:153`).

**What it claims epistemically.** *When this citation was made, it pointed at this shape.* True at
creation. But the stored value's **meaning decays**: it is a durable snapshot of a transient
condition, and a legitimate refine (`refined_mask_to_region` deliberately reuses `base_id` when
upgrading the same shape — verified at `adapters.py:191`) changes the mask without changing the
identity. The fingerprint would then report substitution where there was continuity. It claims more
than it can keep.

**How it could go wrong.** Three ways, and the third is decisive. (i) It is **HW-C4 §4b's rejected
shape in better clothes** — durable state about a transient condition, written onto the Ground — and
§4b was rejected *for this very hazard*. (ii) It cannot be backfilled: the four existing grounds'
original masks are gone (§6), so it is prospective-only, exactly as tombstoning was. (iii) **A stored
fingerprint is one short step from IoU re-matching** — once a ground knows what it used to point at,
*"find the region that best matches this hash-adjacent shape"* is the obvious next ticket, and K-4
bans it permanently. An option whose natural next move is a banned move is a bad option even when its
first move is fine.

**Invariants at risk.** The geometry-never-duplicated-onto-a-Ground invariant is not broken by a hash
— but a hash is the thin end of it, and the next reviewer will not have read this paragraph.

### Option D — notify + detect

**Concretely.** Keep resolution semantics and keep notify, and add a detection step for
substitution — at the one place in the system where both generations exist simultaneously.
**That place is verified and specific:** at `posts.py:790-847`, `existing` (the old
`region_annotations`, keyed by id) and `candidates` (the new regions, each already carrying its
authoritative `mask_rle` from the segmenter) are **both in memory in the same function**, before the
wholesale `$set`. Same-id/different-mask is computable there from data already present — no new
collection, no ground-side field, no id change, no backfill.

**Cost.** A comparison and a count at one site, plus a telemetry `detail` on the existing recorder
(`rec.event(...)` already writes bounded counts at that exact point). Server-side, so **not gated on
B-01** (the hydration race is a client-side concern and cannot produce a false positive here).

**What it claims epistemically.** *At this operation, N ids kept their name and changed their
shape.* That is the narrowest true statement available about the hazard, it is checkable from the two
arrays in front of the function, and it is a fact about an **operation** — the same category HW-C4
§4b said detachment events belong in.

**How it could go wrong.** (i) Detection with no consequence is a log nobody reads; it must be
recorded somewhere a later lane will actually look. (ii) A refine-then-re-dissect sequence will show
same-id/different-mask legitimately, so a raw count over-reports unless intentional identity
continuity is excluded — this is a real design problem, not a rounding error. (iii) Detecting at the
merge and doing nothing about `posts.py:808-813` leaves the actual data corruption running while the
telemetry watches it happen.

**Invariants at risk.** None, if it stays observational. All of them, if "detect" quietly acquires a
"and then fix it" clause.

### Option E — hybrid

Any staged combination. Evaluated in §4 rather than here, because the whole question is *which*
combination and *in what order* — and the ordering carries more weight than the ingredients.

---

## 4. The decision

> **Detect substitution where it is created — at the dissect merge boundary — and keep notify.**
> Region ids remain positional for now. The Ground remains a pure reference and gains no fingerprint.
> `resolveGround`'s semantics are not touched. Nothing is repaired, re-matched or re-pointed.
> Held open with triggers (§9): id stability (A), run stamping (B), and pinning (HW-C4 §4c).
>
> **This is Option D, backed by Option B held in reserve. A and C are declined for now; C is declined
> in principle.**

### Why this, and not the others

**Because the merge boundary is the only place the truth exists, and it exists there for free.** Every
other option pays to *reconstruct* knowledge that `detect_regions` already holds in local variables
for the duration of one function call. The Ground cannot know what changed — it holds a string. The
client cannot know — it sees one generation. The database cannot know — HW-C5 proved there is no
history anywhere. The merge site knows, briefly, completely, and then throws it away in a `$set`.
Detecting there is not the cheapest of several ways to learn this; it is the only way that does not
require inventing a new durable record first.

**Because it inverts the failure mode of every other option.** A, B and C all change something
durable in order to make a future comparison possible. D makes the comparison now and changes nothing
durable, which means it can be wrong without leaving residue. That is HW-C4 §6's own reversibility
criterion, applied to a problem HW-C4 did not solve.

**Because it makes the unknowable knowable prospectively, which is the actual bottleneck.** HW-C5's
corpus verdict is UNDETERMINABLE and will stay UNDETERMINABLE under A, B or C until enough runs
accumulate. D starts producing evidence on the next dissect. Every subsequent decision on this fork —
including whether to adopt A at all — needs that evidence and cannot be made honestly without it.

**Why not A (id stability), now.** It is probably the right long-run answer and it is explicitly not
declined on the merits. It is declined on **sequence**: adopting it today means migrating live cited
ids on a corpus of 11 annotated posts, on the strength of a hazard that has been shown *possible in
code* and *undetermined in data*, and the migration would have to touch the four-ground fixture that
three prior lanes deliberately preserved. Do the measurement that A's cost should be justified by,
first. Note also the unresolved semantic question A forces and nobody has answered: **if a re-run
produces a genuinely identical shape, should it be the same region?** A content-derived id answers
"yes" silently. That deserves a decision, not a hash function.

**Why not B alone.** In field-form it is inert — `resolveGround` still matches strings and the hazard
is untouched, so it ships a fix that fixes nothing. In string-form it is A with extra steps. It is
kept in reserve because it is the correct *home* for what D observes, and because it is DATA-1-blocked
today at n=1 anyway.

**Why not C, in principle.** It relocates a fact about an *operation* onto a *citation*, which is the
category error HW-C4 §4b already rejected; the stored value's meaning decays under legitimate refines;
it cannot be backfilled; and its natural successor ticket is the one thing K-4 bans permanently. C is
the option that most looks like a fix and least is one. **The apparent cheapness of C is entirely
because the comparison already exists in `geometry_recovery.py` — and §5 shows that comparison belongs
at the merge, not on the Ground.**

**Why notify still stands.** Nothing in HW-C5 weakens HW-C4 §4's argument that a tombstone is a change
to state where a notification is speech about state. HW-C5 *strengthens* it: HW-C4 rejected
tombstoning because it would silently re-arm A2R's disarmed behaviour by data rather than code, and
ordinal reuse produces the identical regression by the identical route **without anyone choosing
tombstoning**. That does not make the rejection wrong. It makes it insufficient as a stopping point —
which is what this document supplies.

### What should be implemented LATER, in this order

Nothing below is authorized (§8). This is the order a future lane must follow if the orchestrator ever
approves any of it.

**Step 1 — Observe at the merge (server-side, no behaviour change).**
At the dissect merge, compute the set of ids present in both `existing` and `candidates` whose
authoritative masks differ, excluding intentional identity continuity (a `refined_from` /
`base_id` upgrade is continuity, not substitution). Record the **count and the affected id list**
into the existing `VisionRun` recorder at that site. Nothing renders. Nothing warns. Nothing changes
for the curator.
*Trigger:* the next lane that touches the dissect route for any reason, or DATA-1 work on
`vision_runs`, whichever comes first. Independent of B-01.
*Why first:* it is the only step that produces evidence, and every later step is gated on it.

**Step 2 — Stop the silent carry (the actual corruption).**
`posts.py:808-813` migrates `prioritised`, `weight`, `user_note` and — worst — the
`actor == "creator"` promotion onto whatever new region occupies a matching ordinal. The
`actor` promotion grants a fresh auto region the permanent re-dissect immunity of
`posts.py:795-797` on the strength of a string match. Curator-authored fields must not cross a
substitution boundary. The condition is available for free once Step 1 computes it.
*Trigger:* Step 1 landing, **or** any measurement showing a nonzero substitution count — whichever is
sooner. If Step 1 measures nonzero, Step 2 stops being a queued item and becomes the priority item on
this fork, ahead of anything Ground-side.
*Why second and not first:* the condition Step 2 needs is exactly what Step 1 computes. Doing 2 first
means writing the comparison twice, in two places, with two chances to disagree.

**Step 3 — Extend notify to substitution (client-side).**
Only if Step 1 measures nonzero. Then, and only then, the Ground layer may say — in A2R's register, as
a fact about the record, with the denominator visible and no repair verb — that a cited region was
replaced. **Gated on B-01**, like every other moment-of-loss notification, and on its own review.

**Step 4 — Revisit id identity (A and B) as a decision, not a task.**
Once Steps 1–2 have produced real run data, re-open the question of what a region id should denote,
with a decision doc of its own. It must answer the semantic question A forces (is a re-derived
identical shape the same region?) before choosing a hash.

---

## 5. The `geometry_recovery.py` finding

**Verified in this lane.** `geometry_recovery.py:153-177` implements `stale_semantic_assertions` /
`mark_stale_semantic_assertions`: it builds `cur = {region_id: mask_hash(mask_rle)}` and compares it
against a `prior_mask_hashes` map **keyed by candidate id**, flagging `evidence_stale=True` where the
same id now carries a different mask. Its docstring states the principle exactly:
*"the region's mask now differs … the caller flags stale but preserves status/curator_label."*
`mark_detached_grounds` sits at `:180` and writes `g["detached"] = True` plus
`g["detached_reason"] = "region evidence absent after recovery"` onto the ground dict.

**Verified — its call sites, in full.** `grep -rn "geometry_recovery\|stale_semantic_assertions\|mark_detached_grounds"`
across the repo returns exactly: `scripts/vision_f3_recover_one.py`, `scripts/vision_f4_refresh.py`,
`backend/tests/test_vision_f3.py:89`, `backend/tests/test_vision_f4.py`, and the module itself
(`:149`, where `recover_post` calls `mark_detached_grounds`). **`grep -rn "geometry_recovery" backend/routers/`
returns nothing.** No router, no service, no request path reaches any of it. It is operator-script
surface with test coverage.

**One thing HW-C5 did not say, found here.** `scripts/vision_f3_recover_one.py:88` **persists** —
`update_one({"_id": ObjectId(PID)}, ...)` after validation. So `mark_detached_grounds`' durable
`detached: true` write onto a Ground is not hypothetical dead code: it is a live, operator-runnable
mutation. **HW-C4 §4b's rejected shape — a durable detachment note on the Ground — already exists in
this codebase and is one manual script invocation from production.** HW-C4 rejected building it. It
is already built, in a corner. (Whether any of the four detached grounds currently carries that flag
was not checked this lane; it is a read-only query and is named in §9 as an open check.)

**Is it a gift, a trap, or a sign the problem was already understood and abandoned?**

**All three, and separably — which is why the answer is: take the predicate, refuse the marker.**

*It is a gift as a predicate.* `mask_hash(mask_rle)` compared across a same-id map is precisely the
Step 1 comparison, already written, already tested, already the right shape, and already committed to
the correct principle (flag, never drop the curator's decision). Step 1 should reuse this pattern
rather than invent one. That lowers Step 1's cost and, more importantly, means the codebase would be
applying *one* definition of "the evidence under this assertion changed" instead of two.

*It is a trap as a mechanism.* `mark_detached_grounds` mutates the Ground. Wiring `geometry_recovery`
into the dissect route wholesale would import that mutation along with the comparison, and would land
HW-C4 §4b through the back door with no decision ever taken. The two functions live in one file and
look like one feature; they are not. **Step 1 reuses `stale_semantic_assertions`' comparison
pattern. Step 1 must not call `mark_detached_grounds`, and must not write anything onto any ground.**

*It is a sign the problem was understood in a neighbouring context and never generalized.* VISION-F
faced exactly this question for **semantic assertions** during geometry recovery — *"if the mask under
an assertion changed, is the assertion still about the same thing?"* — answered it correctly, scoped
it to the recovery flow, and never asked whether the same question applies to Grounds during a
re-dissect. That is not abandonment and it is not negligence; it is a correct local answer that nobody
generalized. It does, though, mean the conceptual work is done: **the codebase already contains the
judgement that same-id-different-mask invalidates a downstream reading.** This decision is, in large
part, applying an existing in-repo judgement to the one place it was not applied.

**Verdict: it is the basis of the fix at the level of the comparison, and explicitly not at the level
of the marking.** Reuse the predicate. Do not reuse, extend, or route to the mutation.

---

## 6. What is now known to be UNKNOWABLE

Stated plainly, because it constrains everything above:

- **There is no region history.** `region_history`, `prev_region_annotations`, `superseded`,
  `region_generation` — **0 documents each**. `posts.py:847` overwrites `region_annotations` with a
  wholesale `$set`. Dropped auto regions are gone.
- **`vision_runs` holds 1 document corpus-wide**, for an unrelated post, recording a dissect that
  produced nothing. And the recorder writes **bounded counts** (`detail={"region_count": len(regions)}`),
  never region ids or geometry — so even a fully populated `vision_runs`, as currently written, would
  not let anyone compare generations.
- **`region_embeddings` cannot substitute.** HW-C5 checked whether any `(post_id, region_id)` pair
  holds two different `mask_hash` values. Four pairs matched; **all four are artefacts** — the second
  value is the empty string from a `fashion-clip` document that stores no mask hash, alongside a real
  hash from the `dinov2` spaces. Same generation, different embedding space. **Zero genuine
  same-id/different-mask pairs.** The 9 embeddings whose `region_id` no longer exists are all
  `__whole__`, the synthetic key. The embedding run postdates the detachments entirely.

Therefore:

**Whether ordinal id reuse has already occurred in this corpus is not merely unmeasured — it is
unmeasurable. It cannot be established now and it cannot be established later, because the evidence
that would settle it was never written and cannot be reconstructed.** HW-C5's UNDETERMINABLE verdict
is permanent for the existing corpus, not a gap awaiting a better query.

**Every option in §3 is prospective-only. The four detached grounds cannot be recovered by any of
them.** `fine_0` and `fine_3`'s masks no longer exist in the database. There is nothing to fingerprint,
nothing to stamp, nothing to re-derive, and — per K-4 and HW-C4 §5.9 — nothing to guess. A fingerprint
cannot be backfilled. A run stamp cannot be backdated. A content-derived id cannot be computed for a
mask that is gone. The four grounds stay exactly as they are: **they are the fixture, and the only
thing this fork can still do for them is not lie about them.**

**Honest n, unchanged:** 4 detached grounds · 11 annotated posts (of 127 scanned) · 7 percepts · 26
grounds · 2 affected posts · 1 harmed percept. Two posts produce the entire finding. **The 36.4 %
figure must never be quoted as a corpus property** (K-9, categorical). The current low harm — two of
the four stranded grounds happen to be cited by no percept — is luck, not design.

---

## 7. Consequences

**For the fork.** D-1 is answered more completely than HW-C4 answered it, and in a way that does not
retract HW-C4's answer. Detachment is announced (HW-C4). Substitution is measured before it is
announced (HW-C6). Neither is repaired.

**For `detect-regions`.** The merge at `posts.py:808-813` is now on the record as a **defect, not a
feature**: it carries curator-authored fields, including a permanent immunity promotion, across a
substitution boundary it cannot see. HW-C4 §5.3 forbade changing the merge; that refusal is narrowed
here to the extent needed for Step 2 to be proposable. It is not thereby approved.

**For `geometry_recovery.py`.** It stays exactly where it is, wired to exactly what it is wired to.
This document does not route it, extend it, or move it. It cites it as a pattern.

**For `resolveGround` and A2R.** Untouched. A2R's register remains the standing one. The honesty
property is unchanged and remains binding on every step.

**For the backlog.** No item is promoted, no queue position changes. B-01 still gates every
client-side moment-of-loss notification, including Step 3, and has still never been run.

**For the corpus.** Nothing. Four detached grounds, two posts, one fully unevidenced percept
(`pctx_mrqp950d_0`, *"the upper head"*). They stay.

---

## 8. What this does NOT authorize

**No build follows from this document.** Every item in HW-C4 §5 remains refused except as narrowed in
§1.3. In addition, specifically **not** authorized:

1. **Any code, anywhere.** Steps 1–4 in §4 are an *order*, not a queue entry. None of them may be
   started without the orchestrator's approval of this doc and a gate of their own.
2. **Any change to region id generation.** The four ordinal sites stay as they are. No hashing, no
   uuid, no prefix change, no migration, no dual-read.
3. **Any field on a Ground.** No `region_mask_hash`, no `detached_at`, no `detected_generation`, no
   fingerprint of any kind. Option C is declined in principle, and its cheapness is not an argument.
4. **Any routing of `geometry_recovery`.** Not into `detect-regions`, not into any router, not into
   any request path. Its `mark_detached_grounds` mutation is not to be extended, generalized, or
   invoked from anything new.
5. **Any repair, re-match or re-pointing.** K-4 stands permanently. A detected substitution is not a
   licence to find "the right" region. There is no right region.
6. **Any backfill or repair of the four detached grounds.** They are the fixture. Production data is
   not to be touched.
7. **Any curator-facing surface for substitution.** Step 3 is conditional on Step 1's measurement,
   gated on B-01, and needs its own review. No toast, pill, badge, count or copy before then.
8. **Any rate, percentage, health score or dashboard.** 36.4 % must never appear. Absolute counts with
   the denominator visible, or nothing.
9. **Any audience-facing exposure.** Nothing about detachment or substitution reaches `/read/:postId`
   or any viewer surface, at any volume, ever.
10. **Any nudge toward geometry-bearing grounds.** `0/15` versus `4/11` is a contrast, not a
    recommendation. Reference semantics stay first-class.
11. **Any claim that reuse has occurred.** It has not been observed and, per §6, cannot be. Nothing
    written under this decision may state or imply otherwise.

---

## 9. Reversibility, overturning evidence, and revisit

**Reversibility.** The decision itself creates nothing: no schema, no field, no migration, no stored
value, no id change, no semantic change to `detached`. Retracting it costs a status line. Step 1, if
ever built, adds a computed count to an existing telemetry `detail` — revertible by `git revert` with
the data byte-identical before and after, since it writes only into `vision_runs`, which nothing
currently consumes. Step 2 is the first step with a behavioural footprint (curator fields stop
migrating), and it is a *restriction* on a carry that should never have been unconditional, so
reversal restores a defect rather than losing a capability. Steps 3–4 are separately gated and their
reversibility is their own review's problem. **The asymmetry is deliberate: everything cheap to
reverse is early, everything expensive is deferred behind evidence.**

**Retraction protocol.** Set this doc's status to `Superseded by <id>`; do not edit its reasoning.
D-1 re-opens, and HW-C4's still-standing parts (§1.3) survive independently unless separately
retracted.

**Evidence that would overturn this decision:**

- **Step 1 measuring zero across ≥ 20 dissects on ≥ 10 posts.** Then substitution is a code-level
  hazard that the actual workflow does not produce, Step 3 never happens, and Option A's cost is
  unjustifiable. This is the most likely outcome and the decision is built to accept it gracefully.
- **Step 1 measuring nonzero on the first or second dissect.** Then the hazard is routine, Step 2
  becomes urgent rather than queued, and **Option A stops being deferred** — a measured recurring
  substitution is exactly the evidence that justifies migrating ids, and this decision's "not now"
  expires on it.
- **A dissect being shown to reuse an id for a shape a curator had cited** — the concrete case, not
  the mechanism. That would promote HW-C4 §4c ("pin the cited") from reserved to live, because at that
  point preventing the harm dominates measuring it.
- **A demonstration that the merge boundary is not the only site of substitution** — e.g. another
  write path that replaces `region_annotations`. The whole decision rests on the merge being the
  unique place both generations coexist. If that is false, Option D's central advantage is false.
- **`geometry_recovery`'s `mark_detached_grounds` turning out to have already run on production
  grounds.** That would mean durable `detached` flags exist in the corpus, HW-C4 §4b is already
  breached in fact, and the fixture is not what four lanes have assumed. **This is a read-only query
  and it should be the first thing the next lane checks.**

**When to revisit — any one sufficient:**

| trigger | current | revisit at |
|---|---|---|
| Step 1 substitution measurement | never run | **immediately on any result, either way** |
| `vision_runs` documents | **1** | enough to compare generations across ~20 posts (DATA-1) |
| annotated posts | 11 of 127 | ≥ 30, with ≥ 5 independent posts contributing |
| B-01 hydration race | never run | before Step 3 is written |
| `detached` flags present on production grounds | **unchecked** | on the answer, either way |
| a lane proposing anything in §8 | — | on the proposal — re-open, do not carve an exception |

**Scheduled revisit regardless:** at the end of the next full cycle, or the first time any lane
proposes an affordance §8 forbids — whichever comes first.

---

*Decision doc ends. Status: proposed. Supersedes HW-C4 in part (§1.3). No implementation authorized.
No production data was read or written by this lane.*
