# HW-C4 — The detached-evidence repair fork: tombstone / notify / neither / hybrid

**DECISION DOC — no implementation authorized, no production data touched.**
No source file, schema, route, migration or record was created or modified by this lane. Mongo was
not queried. No model calls. Nothing was staged, committed or pushed. Code and vault documents were
**read only**, to check that the claims below are still true.

| | |
|---|---|
| **id** | HW-C4 · resolves **D-1** in `Plans/HW-L5-prototype-rotation-backlog.md` §13 |
| **date** | 2026-07-21 |
| **status** | **Proposed** — awaiting the orchestrator's acceptance. Nothing may be built from it until then, and even then see §5. |
| **decision, in one line** | **Notify. Do not tombstone.** Detachment is reported as speech about the record; it is never repaired by making a dead reference resolve. |
| **supersedes** | nothing |
| **blocks released** | B-02, B-03b, B-06, B-07, B-08, B-14 may stop being neutral on this fork — *as to wording only* (§5) |

---

## 1. The question, stated precisely

A **Ground** is how a percept's visual evidence occupies the image. Seven types
(`grounds.js :: GROUND_TYPES`). Six carry their own geometry. One — the **region adapter** — does
not: `groundFromRegion` stores **only** `region_id`, and the file says why in its own header:
*"The Region adapter — reference, not duplication. Geometry stays on the Region."*

**Detached** has a precise, already-shipped meaning. From `resolveGround`:

- **`region` ground** — `detached: !region`, where `region = regions.find(r => r.id === ground.region_id)`.
  Detached ⟺ the cited `region_id` is not among the post's *current* `region_annotations`.
- **composite** (`constellation` / `relation`) — detached ⟺ it has `member_ids`, **no** member
  resolves, **and** it carries no raw `points`.
- **`field` / `path` / `boundary` / `frame`** — **never** detached. They carry geometry.

Note what `detached` does *not* mean. It is not "the region was deleted", not "the curator was
wrong", not "the evidence is gone". It is exactly one thing: **this identifier does not currently
match anything in this post's region array.** Everything downstream that reads more into it is
reading more in.

**The fork.** When `resolveGround` returns `detached`, what — if anything — should the system do?

1. **Tombstone** — retain the vanished Region in some non-active form so the Ground resolves to *something*.
2. **Notify** — leave resolution as it is; announce the fact of non-resolution.
3. **Neither** — keep today's silent graceful degradation plus A2R's caption note, and stop there.
4. **Hybrid** — some combination, or a staged commitment.

This document chooses. It authorizes no build.

---

## 2. The evidence, with n stated honestly

**What is known** (`R2/A2S-detached-ground-sweep.md`, `R2/evidence/A2S-detached-ground-sweep.json`,
`runs/003-sensory-disagreement/score.md`, `R2/A2R-recall-evidence-honesty.md`):

| | |
|---|---|
| posts scanned | 127 |
| posts with any grounds or percepts | **11** |
| posts with ≥1 detached ground | **2** (`695be786`, `695be794`) |
| grounds total | 26 |
| — reference-based (`region`) | 11, of which **4 detached** |
| — geometry-bearing | 15, of which **0 detached** |
| — composite | 0 |
| percepts | 7 · **1** with detached evidence · **1** fully unevidenced (`pctx_mrqp950d_0`, *"the upper head"*) |
| detached grounds cited by no percept | 2 |
| `vision_runs` documents corpus-wide | **1**, for an unrelated post |

**Four data points.** That is the whole empirical base for this decision, and the decision is
written to survive being wrong about all four (§6, §7).

What the sweep established and what it did not:

- **Established:** the mechanism is real and reproducible — the same signature appears on two
  independent posts. It is not an A2 accident.
- **Not established:** any *rate*. `4/11` is 36.4 % and **that number must never be quoted as a
  corpus property**, in this document or any interface (backlog K-9). With n = 11 the interval is
  useless. Two posts produce the entire finding.
- **Not established:** *when* detachment happened, or by which operation. One `vision_runs` document
  exists corpus-wide and zero for the affected posts. The re-dissect is **inferred from region
  naming (`fine_*` → `arch_*`), never observed.** A2's critique refused that inference and this
  document does not un-refuse it.
- **Currently low harm — incidentally.** `695be794`'s two stranded grounds happen not to be cited by
  any percept. Nothing in the system arranged that. It is luck.

**A2R's sharpening.** The pre-fix system did not merely fail to announce loss: `recall.js` passed a
raw `groundById` lookup into a parameter *named* `resolveGround`, so a detached ground received a
full timed highlight step that drew nothing, and the caption *"the upper head"* played over an empty
image — **100 %** of that percept's performance was empty. A2R fixed it (`lookup` + `{ isResolved }`
from the real `resolveGround`, `unresolvedGroundIds` / `resolvedCount` / `citedCount`,
`evidenceNote` rendered *with* the caption; 96 frontend tests, render-verified). **This is the single
most important input to the decision below**, and §4 explains why.

### Two mechanism facts this lane checked in code, which the prior documents do not state

Both are read-only findings from source. They change the analysis materially.

**(a) The replaced geometry is not recoverable. There is nothing to tombstone retroactively.**
`detect-regions` persists with one wholesale `$set` (`posts.py:847`:
`{"$set": {"region_annotations": regions}}`, where `regions = creator_regions + kept_auto`). There is
no history collection, no archive, no `superseded` flag anywhere in `backend/` (grepped). Dropped
auto regions are overwritten in place. **`fine_0` and `fine_3`'s masks no longer exist in the
database.** A tombstone policy adopted today could therefore do nothing whatsoever for the four
grounds that motivated the question — it would be purely prospective. That is not a detail; it means
tombstoning does not repair the motivating case, and the case would still need §4's answer anyway.

**(b) Region ids are positional counters, so a re-dissect can silently *re*-attach a detached ground
to a different shape.**
`vision_service.py:645` emits `"id": f"fine_{i}"` from `enumerate(...)` over a VLM's parts list;
`architecture_segmentation_service.py:137` emits `f"arch_{len(regions)}"`;
`fashion_segmentation_service.py:216` emits `f"fseg_{len(regions)}"`. Ids are **per-run ordinals
within a detector family**, not stable identities. So if the sukshma/fine pass is ever re-run on
post `695be786`, it will very likely emit a `fine_3` again — and `resolveGround` will resolve
`gnd_mrqp8tls_0` to it. Not the curator's "hair". Whatever is third in the new response.

This is **automatic fabricated provenance requiring zero code** — precisely the outcome K-4 bans,
arriving by data rather than by design. It is already half-live: the merge at `posts.py:808-813`
carries `prioritised` / `weight` / `user_note` across generations **by id**, so a curator's note can
already migrate onto a different shape the same way. This lane did not measure whether that has
happened. It should not be assumed to have, and it should not be assumed not to have.

The consequence for this fork is direct: **"resolves" is already a weaker guarantee than it looks.**
Any option whose value depends on `detached` staying true — or on resolution meaning identity — is
standing on softer ground than the corpus numbers suggest.

---

## 3. The four options

Applies to all four — **invariants no option may break:**

- **`mask_rle` is authoritative identity.** `Region.box`, `polygons` and legacy `polygon` are
  *derived* from it by `mask_geometry.canonicalize_geometry`, with `geometry_rev` bumping on every
  mask-identity re-derivation and `geometry_provenance` carrying lineage (`schemas/post.py:46-52`).
  No option may produce a Region-shaped record whose `box`/`polygons` are not derived from its own
  `mask_rle`, or which carries a `mask_rle` it did not get from a real derivation. A fabricated or
  hand-edited mask is a corrupt canonical record, not a memorial.
- **Geometry is never duplicated onto a Ground.** The region adapter stores `region_id` and nothing
  else, deliberately. No option may "rescue" a ground by copying the region's mask onto it — that
  creates a second canonical geometry with no `geometry_rev`, no provenance, and no way to be
  re-derived.
- **`region_annotations` is the single source of truth and is iterated by everything.**
  `anatomy_catalog_service` (aggregates *across all posts* by category/label),
  `evidence_embedding_service`, `find_similar_service`, `indexing_service`, `taste_signal_service`,
  `anuranana_service`, `evidence_packet`, `geometry_recovery`, `semantic_pass`, plus the persona
  rollup in `save_region_annotations`. Any record placed in that array is seen by all of them.
- **Creator geometry already survives re-dissection.** `posts.py:795-797` preserves every
  `actor == "creator"` region intact through a re-dissect. Whatever is decided must not weaken that,
  and must not be justified by pretending it does not exist.
- **A2R's honesty property must not regress.** Script and render must continue to agree: a ground
  that draws nothing must not receive a highlight step, and a percept whose evidence does not
  resolve must not be performed as though it does.
- **No blame.** No wording, mark, count or affordance may imply the curator broke something. The
  register A2R chose — *"Detached evidence — none of the 2 cited grounds still resolves"*, a fact
  about the record — is the ceiling, not a floor to escalate from.
- **No fabricated repair targets.** No IoU re-match, no "did you mean `arch_2`?", no automatic
  re-pointing. (K-4, permanent.)
- **No implicit preference for geometry-bearing grounds.** `0/15` vs `4/11` is a striking contrast
  and it is **not** a recommendation. Reference semantics are deliberate; durability is one axis.
  Nothing may nudge curators to draw a `field` instead of citing a Region — that pushes them to
  duplicate geometry, which is the invariant above, inverted.

---

### Option 1 — Tombstone

**Concretely.** At the moment a re-dissect would drop a Region that at least one Ground cites,
retain that Region — flagged (`superseded: true`, or moved to a sidecar collection) — so
`resolveGround` finds it and returns `detached: false`.

**Cost.**
- Every one of the ~10 backend consumers listed above must learn to exclude tombstones, or the
  cross-post anatomy catalog, the taste graph, `find_similar` and the evidence packet all start
  counting retired regions as live evidence. A missed call site is a silent data-quality bug in a
  place nobody is looking.
- The frontend round-trips the whole array: `save_region_annotations` (`posts.py:1009-1015`) sets
  `region_annotations` to exactly what the client sent. **Any client that does not know about
  tombstones deletes them by saving normally.** Tombstones are therefore not an additive flag; they
  are a whole-stack invariant with an obligation on every writer.
- A sidecar avoids the consumer problem but then `resolveGround` — a pure client-side function over
  `regions` — must be fed a merged array, which re-imports the problem into the client.
- **And it repairs nothing that exists.** Per §2(a), the four detached grounds' masks are gone.
  Prospective only.

**What it would claim, epistemically.** More than the humility argument grants it, but also less
than its critics assume. Honestly stated: a tombstoned `mask_rle` would be a *true* record. The
image is immutable; a normalized mask marks the same pixels forever; the curator really did point
there. Preserving it is **not** fabrication and it is **not** IoU guessing. That is the strongest
thing that can be said for this option and it should not be waved away.

What is wrong is the second-order claim. Making the ground resolve says *"this citation is fine"* to
every consumer of `resolveGround` — and those consumers do things. `GroundLayers` would draw the old
mask. `groundBBox` would return it. `recall.js`'s `isResolved` would pass, so the highlight step
comes back and *"the upper head"* plays over the retired shape again. **A tombstone would undo A2R's
honesty fix by data rather than by code** — the same rendered behaviour A2R was written to stop,
reachable without touching `recall.js` and without any test failing. And it would re-endorse a
retired detector's reading of the image: on this very post the labels being memorialised are
`wall` / `floor` on a sculpture (spark-04, out-of-domain collapse). The system would be asserting
that a reading it has since replaced is still current evidence.

**How it could go wrong.**
- The A2R regression above, silently, with green tests.
- Unbounded growth: nothing says when a tombstone stops mattering, so region arrays accrete forever
  and every re-dissect adds another stratum.
- Tombstone + §2(b) id reuse: a re-run `fine_3` and a tombstoned `fine_3` in one array is an id
  collision inside the source of truth. `regions.find(r => r.id === ...)` takes the first. Which
  one is first is an ordering accident.
- It quietly answers a question nobody asked — *"is a Region a durable object or a current
  reading?"* — in favour of durable, for a system whose entire dissect design says current.

**Invariants at risk.** The `region_annotations`-is-truth invariant (directly). The A2R honesty
property (indirectly, and worst, because it fails silently). `mask_rle` canonicity, if anyone is
ever tempted to synthesise a tombstone mask for the four grounds whose masks no longer exist —
which, given §2(a), is exactly what a well-meaning implementer would be tempted to do.

---

### Option 2 — Notify

**Concretely.** Resolution is untouched. `detached` stays `detached`. The system *says so*: at
minimum, at the moment an operation drops Regions that Grounds cite — the count is derivable at the
dissect site, which already holds both the outgoing region ids and `post.grounds`, and already
records a `region_ids` list into telemetry (`posts.py:1394`) — and, in the resting state, the quiet
derived marks already queued as B-02 / B-03b / B-06. Frontend notification infrastructure already
exists (`components/ui/Toast.jsx`).

**Cost.** Small and almost entirely reversible. No schema, no migration, no stored data, no new
endpoint; a derived count and a string. This is the backlog's own reversibility criterion (S1 §5).
The real costs are not technical: **attention budget** (every notification spends some), **register**
(D-2 — three quiet marks in three places may add up to something louder than any one was approved to
be), and the **dead-end problem** — a notice with no next action is a notice about something the
curator cannot act on, and giving it a next action chooses the repair fork by the back door.

**What it would claim, epistemically.** Exactly and only: *this reference does not currently
resolve.* That is verifiable from the two arrays in front of you, and it is the whole content of
`resolveGround`'s boolean. It claims nothing about whether the evidence was good, whether the
curator was right, whether anything was destroyed, or when. It is speech about the record.

**How it could go wrong.**
- **False notifications from the hydration race.** `regionStore.js:94-119` loads regions and grounds
  in one effect; if grounds land first, *every* region-ground reports detached for a frame. A toast
  fired on that frame is a false alarm about the curator's own work — the most damaging failure
  available here. **B-01 exists precisely to measure this and has not been run.** This is a hard
  precondition for anything that fires at a moment rather than rendering at rest.
- **Blame drift.** "2 of your citations are broken" is one careless rewrite away from the register
  A2R established, and notifications are written by whoever is closest to the deadline.
- **Fatigue, then a repair verb.** The predictable arc: notice → "there's nothing I can do" →
  someone adds a button. That button is Option 1 or K-4 wearing a different hat.
- **It only ever helps forward.** It says nothing about the four grounds already detached, whose
  loss predates all telemetry.

**Invariants at risk.** None structurally — which is most of the argument. The exposures are wording
(no-blame) and timing (the hydration race).

---

### Option 3 — Neither

**Concretely.** Ship nothing further. Detachment stays modelled (`resolveGround`), rendered
("detached evidence" in the Differential inspector), and honest in recall (A2R). Loss is survived,
never announced.

**Cost.** Zero. It is today's state.

**What it would claim.** Nothing — and that is both its virtue and its problem. It is the only option
that adds no assertion whatsoever. But silence is not neutral when the system is the only party that
knows: the curator has no way to learn that a percept they wrote is now unevidenced except by opening
that percept and pressing play.

**How it could go wrong.** A2S's own projection: as percept density grows against a corpus that keeps
being re-dissected, harmed percepts should rise, *because nothing links the two events*. The current
low harm is luck (two of the four detached grounds are uncited by accident). And §2(b) makes the
tail worse than silence — a re-run detector family can re-attach a stale citation to an unrelated
shape, and the "neither" system would render that with full confidence and no mark at all.

**Invariants at risk.** None. It breaks nothing. It just declines to know out loud.

**This is the serious rival.** At n = 4, "do nothing yet, gather data" is a genuinely defensible
answer and any decision doc that does not say so is posturing. §4 says why it loses anyway.

---

### Option 4 — Hybrid

Two distinct things travel under this word; they deserve separate verdicts.

**4a — "notify now, tombstone later if evidence demands."** This is not a hybrid, it is a sequencing
of Option 2 with an option held open. It costs exactly Option 2 plus the discipline to write down
what would trigger the second step. Epistemically it claims what Option 2 claims. It is the honest
shape of a decision made on four data points. **Adopted as part of the decision below** (§6, §7).

**4b — "notify *and* durably record the detachment on the Ground."** Append a note to the ground dict
(`grounds` is `List[dict]`; `hydrateGrounds` preserves unknown fields verbatim, so it would survive
round-trips) saying the reference did not resolve at time T. Attractive: it costs almost nothing,
it gives Codex the one thing it lacks — a record where today there is *"no record exists for this
period"* — and it resurrects no geometry.

**Rejected, for a specific reason.** Given §2(b), a stored `detached_at` becomes *wrong* the moment a
re-run emits the same ordinal id — and it becomes wrong in the most dangerous direction, because the
ground would then both resolve *and* carry a durable note saying it once did not, on evidence that
is a different shape. It writes a snapshot of a transient condition into durable data (the same
argument B-06 makes against storing a dim in serialised prose, one layer down). If detachment events
are ever to be recorded, the honest home is **`VisionRun`** — a record of what an *operation* did,
where it belongs — and that is DATA-1-blocked with 1 document corpus-wide. Not now.

**4c — a third thing this lane considered and is naming so it is not silently reinvented:
"pin the cited."** Grant a cited auto-Region the durability that creator Regions already have
(`posts.py:795-797`), so citation itself protects geometry from the next re-dissect. It prevents the
harm instead of reporting it, needs no tombstone flag, and duplicates no geometry.

**Not chosen, and it is the strongest future rival to this decision.** It makes a re-dissect no
longer a full replacement, so the system's current perception becomes constrained by the curator's
past attention. A2 framed the finding exactly as *"the curator's past attention vs. the system's
current perception — and the system won"*; 4c does not balance that, it flips it so the curator
always wins. That is a real theory of what a Region is, and it deserves its own decision with its
own evidence — not to be smuggled in as the mild-sounding half of a hybrid.

---

## 4. The decision, and why

> **Notify. Do not tombstone. Do not do nothing.**
> Detachment is announced as a **fact about the record**, at the moment it becomes true and quietly
> at rest. Resolution semantics are **not** touched: a dead reference stays dead until a human
> re-points it. Nothing is repaired, resurrected, re-matched or re-pointed automatically.
> Held explicitly open, with triggers (§7): tombstoning, `VisionRun`-side recording (4b), and
> pinning (4c).

### Engaging the orchestrator's argument directly

The stated position: *"notify, not tombstone. Tombstone sounds like the system knows the evidence is
dead; notify says the current reference no longer resolves and preserves humility."*

**The conclusion is right. The stated reason is the weaker half of the case, and I think it is
largely a wording problem.**

"Tombstone" and "notify" are engineering words, not user-facing ones. A tombstone can be worded with
perfect humility — *"the part this cites was replaced when the image was re-read; here is where it
used to be"* — which asserts less about deadness than the word "tombstone" does. A notification can
be worded arrogantly — *"2 broken citations"* — and that phrasing is *more* accusatory than any
tombstone. Register is orthogonal to the fork. Both options can be humble; both can be arrogant; and
whichever we choose, the no-blame constraint has to be enforced in the copy regardless. So if
humility were the whole argument, the fork would still be open.

**The load-bearing difference is not what the option says. It is what it makes true.**

A notification is **speech about state**. A tombstone is a **change to state** — and in this codebase
`resolveGround`'s boolean is *load-bearing behaviour*, not a display value. Flip it and
`GroundLayers` draws, `groundBBox` returns a box, `RefPicker`'s badge fills, and `recall.js`'s
`isResolved` passes so the caption *"the upper head"* is performed over evidence again. **A tombstone
would silently re-arm the exact behaviour A2R was written to disarm** — same rendered outcome, no
code change, no failing test, and the regression would arrive as data. That is the argument I would
put first. It is stronger than the humility one because it does not depend on wording at all.

Second, weight §2(a): the four grounds this whole fork exists to answer for **cannot be tombstoned**.
Their masks were overwritten by a wholesale `$set` and no history exists. Tombstoning is prospective
only, so the motivating case still needs a non-tombstone answer — which means tombstone was never a
complete answer, only an additional one.

Third, and this is the part the humility framing actually gets exactly right, just for a different
reason than stated: **the system genuinely does not know the evidence is dead, and it does not know
it is alive either.** Given §2(b) it does not even reliably know that "resolves" means "is the same
shape". The only proposition the system can defend is the literal content of the boolean: *this
identifier does not match anything here right now.* Notify is the option whose claim is exactly
coextensive with what is checkable. That is not humility as a tone. It is humility as **scope of
assertion** — and that distinction is worth keeping, because tone is negotiable in review and scope
is not.

### Why not "neither", at n = 4

Because the harm is already demonstrably worse than silence, and that is established *independently*
of the corpus size. A2R did not infer a risk; it **confirmed a bug and render-verified the fix** — a
percept was being performed with 100 % empty evidence. One post proves a mechanism the way one
reproducible crash does. And the current low harm is explicitly luck (two stranded grounds uncited by
accident), while §2(b) supplies a *second*, unmeasured mechanism — ordinal id reuse — that "neither"
would render at full confidence with no mark.

"Neither" would also be a strange verdict to reach immediately after A2R: the codebase has *already
half-chosen notify*. `evidenceNote` exists, it is rendered, it is tested, and A2R's own document asks
for the remaining three surfaces by name. Declining to decide would leave one surface honest and
three not, which is worse than either coherent answer.

### What n = 4 does buy the sceptic

It buys the **scope**, and the scope is where the sceptic's caution belongs. This decision authorizes
a *policy about resolution semantics*, not a feature. It does not license a dashboard, a rate, a
health score, a repair verb, or a durable record. Every one of those needs its own evidence, and §5
refuses them by name.

---

## 5. What this decision does NOT authorize

Firm. **No build follows from this document.** It settles which fork the backlog may assume; it does
not move a single item into "approved". Each item still needs its own gate, its own preconditions,
and its own review.

Specifically **not** authorized:

1. **Any code, anywhere.** Not a toast, not a pill, not a prop, not a string. B-02, B-02a, B-03b,
   B-06, B-13 remain queued exactly as `HW-L5` left them, behind their own dependencies —
   **B-01 (the hydration-race probe) still gates B-02, B-03b and B-06, and it has not been run.**
   A moment-of-loss notification is *additionally* gated on B-01, because a false alarm about the
   curator's own work is the worst failure available on this fork.
2. **Any repair affordance.** No click target, no "re-point this citation", no "fix", no repair verb
   on any mark. `HW-L5` §13 is explicit: *"the moment any mark acquires a click target, the fork has
   been silently chosen."* Choosing notify does **not** unlock the verb — it forbids it more clearly,
   because a repair verb is a resolution change wearing a notification's clothes. Curator-confirmed
   re-pointing with both shapes shown remains a **separate future decision**, never automatic
   (K-4 stands, permanently).
3. **Any change to `resolveGround`, to `region_annotations`, or to what a Region is.** No
   `superseded` flag, no sidecar, no history collection, no archive-on-replace, no change to
   `detect-regions`' merge, and no weakening of creator-region preservation.
4. **Any durable record of detachment** on a Ground, a Percept, or a Region (4b, rejected). If
   detachment events are ever recorded, the home is `VisionRun` and it is DATA-1-blocked.
5. **Any rate, percentage, ratio, progress bar or health score.** **36.4 % must never appear.**
   Absolute counts with the denominator always visible, or nothing (K-9, categorical).
6. **Any evidence-health surface, Atlas route, Codex panel, or corpus dashboard.** B-07 stays
   `never as a production surface`; B-08/B-14 stay a static mock gated on B-02 and B-03b. This
   decision does not advance them one place in the queue.
7. **Any audience-facing exposure.** Nothing about detachment reaches `/read/:postId` or any viewer
   surface, at any volume, ever. The audience gets the reading, not the workshop.
8. **Any nudge toward geometry-bearing grounds.** No copy, ordering, default or affordance may imply
   `field` is safer than `region`.
9. **Backfill, cleanup or "fixing" of the four existing detached grounds.** They stay exactly as they
   are. A2 and A2S and A2R each deliberately left them; they are the corpus's only real fixture and
   repairing them would destroy the test case. **Production data is not to be touched.**
10. **Any wording change to A2R's shipped note.** It is the reference register; if a lane wants to
    change it, that is a review, not a consequence of this doc.

---

## 6. Reversibility

**How this is undone if it is wrong.** Notify was chosen partly *because* it is the cheapest fork to
reverse, and that should be stated plainly rather than claimed as an incidental virtue.

- **Nothing durable is created.** No schema field, no migration, no collection, no stored value, no
  serialised output. Everything the decision permits is derived at render time from state already in
  the client. Reversal is `git revert` of the diffs that cited this doc, and the data is byte-identical
  before and after. There is no "un-migrate" step because there is no migrate step.
- **Resolution semantics are untouched**, so nothing downstream has adapted to a changed meaning of
  `detached`. This is the property that makes reversal cheap; it is also why 4b was rejected.
- **The decision is not a prerequisite for anything.** No queued item *requires* notify; every item
  in `HW-L5` was deliberately designed neutral on this fork. If this doc is retracted tomorrow they
  all still work, minus one paragraph of justification each.
- **Reversing to tombstone later costs no more than deciding it today** — indeed slightly less,
  because by then `VisionRun` density (DATA-1) may make it possible to know *when* detachment
  happens, which is information a tombstone policy would want and cannot currently have.
- **The one thing that would be expensive to undo is anything §5 forbids.** That asymmetry is the
  reason §5 is as long as it is. A repair verb, a stored flag, or a published rate would each create
  a dependency that survives the revert.

**Retraction protocol.** Set this doc's status to `Superseded by <id>`; do not edit its reasoning.
D-1 re-opens. Any lane that shipped under it re-reads §5 before shipping anything further.

---

## 7. What would overturn it, and when to revisit

**Evidence that would overturn "notify" in favour of tombstone:**

- Curators, notified, consistently want the old shape *back* and cannot proceed without it — i.e.
  the notice is repeatedly a dead end in practice, not just in theory. This is the strongest possible
  overturn and it requires observation, not argument.
- Evidence that the retired mask is doing work no current region can do (e.g. a percept whose meaning
  depends on a boundary the new generation does not draw anywhere).
- Detachment turning out to be routine and self-inflicted by ordinary workflow — several re-dissects
  per post as normal practice — which would make "the reference is gone" a background condition
  rather than an event, and events are what notifications are for.

**Evidence that would overturn it in favour of "neither":**

- **B-01 finding a real hydration race**, making moment-of-loss notification unreliable — the notice
  narrows to the resting state, or waits.
- Curators reliably noticing unaided (spark-03's own stated kill condition).
- Detachment ceasing once dissection stabilises — the other stated kill condition. If the next 20
  annotated posts produce **zero** new detachments, the mechanism is a historical artifact of an
  unstable detector era and the notification is machinery for a solved problem.

**Evidence that would promote 4c ("pin the cited") over this decision:**

- A measured re-detachment rate after re-pointing — i.e. curators repair, and the next dissect breaks
  it again. At that point reporting a recurring harm is worse than preventing it, and 4c gets its
  own decision doc.

**Evidence that would change the analysis regardless of the fork:**

- **A measurement of §2(b).** Nobody has checked whether any ground currently resolves to a region
  from a *different generation* than the one it was created against, or whether the
  `prioritised`/`weight`/`user_note` carry-by-id has already migrated a curator note onto a different
  shape. A read-only probe would settle it. **If ordinal id reuse is happening, it is a more urgent
  problem than detachment** — detachment is loud-by-absence, whereas false re-attachment is silent
  and confident, and it needs no re-dissect to be dangerous.

**When to revisit — concrete triggers, any one sufficient:**

| trigger | current | revisit at |
|---|---|---|
| annotated posts | 11 of 127 | **≥ 30**, with ≥ 5 independent posts contributing detachments *or* a confirmed zero |
| reference-based grounds | 11 | **≥ 30**, so the reference-vs-geometry contrast has both arms in double digits from multiple posts (DATA-2) |
| independent detachment fixtures | 2 | **≥ 3 + a negative case** (a re-dissect that detaches nothing) + a transfer test — the R3 graduation bar for spark-03 (DATA-3) |
| `vision_runs` documents | **1** | enough that *when* detachment happened is recoverable for a majority of dissects across ~20 posts (DATA-1) |
| §2(b) id-reuse probe | never run | **immediately on any result**, either way |
| B-01 hydration race | never run | before any moment-of-loss notification is written |

**Scheduled revisit regardless:** at the end of the next full cycle, or the first time any lane
proposes an affordance that §5 forbids — whichever comes first. A request to break §5 is the signal
that the decision is under real pressure, and it should be answered by re-opening D-1, not by
carving an exception.

---

## 8. Consequences

**For `HW-L5`.** D-1 is answered. Items may stop being neutral on the fork **as to wording only** —
they may now say the thing plainly ("evidence not found", with a denominator) rather than hedging
around an unchosen fork. Their **priorities, dependencies and gates do not change**, and no item is
promoted. §5.1 and §5.2 bind all of them. B-02 remains queue position 4 behind B-01 and B-02a.

**For spark-03.** Unchanged in strength; it stays a **SPARK** and does not graduate. This decision
resolves the *design fork* that the register named as one of three reasons the spark is not
production-ready. The other two — tiny corpus, and notification being a behaviour that could be
built badly as a new schema — stand, and §5.3/§5.4 are written to hold the second one shut.

**For A2R.** Its register is now the standing one for this fork. Its three named unfixed surfaces
(Chiasm's chip path, `RefPicker`, Aletheia) keep their existing gates.

**For the corpus.** Nothing. Two posts still carry four detached grounds. `pctx_mrqp950d_0` is still
fully unevidenced, and it stays that way — it is the fixture.

**Newly surfaced, not resolved here:** §2(b), ordinal region-id reuse. It is out of scope for this
fork and needs its own read-only probe. Recorded here so it is not lost.

---

*Decision doc ends. Status: proposed. No implementation authorized. No production data was touched,
read or written by this lane.*
