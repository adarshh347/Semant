# CIRCUIT-001 P1E — How a model operation attaches to a percept

**DECISION DOC — no implementation. No code changed, no route, no schema, no field added, no
production data touched, no model call.** Decides the *shape* of the relation a future dispatch would
record. Extends `Decisions/CIRCUIT-001-P1E-percept-packet-dispatch-decision.md`, which deferred
dispatch itself.

| | |
|---|---|
| **id** | CIRCUIT-001 P1E · run relation design |
| **date** | 2026-07-22 |
| **status** | **Decided.** Implementation deferred; see §8 for the recommended next gate. |
| **decision, in one line** | **No product entity carries a run reference. The run records what it observed, in the `input_refs` seam that already exists, and the thread reads runs by query — a derived index, never a stored back-reference.** |
| **rests on** | code read this cycle (§1), `CIRCUIT-001-P0-open-decisions.md` §1, `CIRCUIT-001-P0-product-circuit-map.md` §§3, 5 |

---

## 1. What the code already has — and it changes the answer

Read this cycle, and it is the most consequential finding of the gate:

**The reference seam already exists and is already in use.** `VisionStageEvent` carries
`input_refs` and `output_refs` (`vision_run_contracts.py:219-220, 257-258`), and three of the four
instrumented operations populate them:

| site | what it stores, **in the corpus today** |
|---|---|
| `posts.py:1230` refine | `input_refs: [{"region_id": …, "geometry_rev": 0}]` |
| `posts.py:1260` refine | `output_refs: [{"region_id": "refine_a02726c3c5", "geometry_rev": 1}]` |
| `posts.py:1417` semantic_read | `output_refs: [candidate_id, …]` |
| `posts.py:1535-6` find_similar | `input_refs: [{"region_id": "seg_0", "space": "visual_identity"}]` |

**`geometry_rev` is already travelling in a ref.** The generation marker a trustworthy run relation
needs is not a new idea here — it is existing practice on the refine path.

Two more facts that constrain the design:

- **`vision_runs` knows nothing about percepts.** `grep percept` over `vision_run_contracts.py`
  returns nothing. The percept is a product-layer object the run machinery has never seen — so
  attaching runs to percepts is a *new relation*, not an extension of an existing one.
- **The codebase already refuses causal ordering.** `project_run`'s docstring:
  *"`events` keep their stored (observation) order; **that order is not a causal claim**."*
  The discipline P1D applied to the thread is already the house rule for runs. **We are extending an
  existing commitment, not importing one.**

Corpus: 9 runs — 4 dissect, 3 find_similar, 2 refine. **No dissect run populates either ref field**,
which is P0 §5's finding, now precisely bounded: the seam is not missing, `dissect` simply does not
use it.

---

## 2. Q1 — Which entity carries the run reference?

**Decision: none of them. The run carries the reference to the percept, and the thread finds runs by
query.**

| candidate | verdict |
|---|---|
| **Percept** (`percept.run_ids: []`) | **Rejected.** A stored back-reference is a second copy of a fact the run already holds, and this codebase has an exact precedent for how that ends: the durable `detached: true` flags — **written by the F-series recovery, read by nothing, accurate today, and stale on the first id collision** (`HW-C6` finding). A `run_ids` array on a percept is that failure with a longer half-life: it would keep asserting a reading after the run was superseded, deleted, or found to have observed different evidence. |
| **Percept Packet record** | **Rejected as a stored entity**, and this is the sharper call. The packet is *built at the moment of asking* and its whole value is that it is derived — persisting it creates a third truth that can disagree with both the percept and the run. **A snapshot of the packet belongs INSIDE the run** (§6), not beside it. |
| **Mention** | **Rejected.** Mentions are reconstructed from markup on every load (`CIRCUIT-001-P0` §1) and the durability fork is still open. Hanging model provenance off the least durable object in the circuit inverts the risk. |
| **Ground** | **Rejected.** A ground is evidence, not a question. Grounds are already the thing we refuse to write interpretation onto — that is the whole argument of P1C's Ground Roles. |
| **Separate read/result attachment** (a new collection) | **Rejected for now.** It is `vision_runs` with a different name. If runs prove structurally unable to carry this, revisit — but not before. |
| **The run's own `input_refs`, plus a derived index** | **CHOSEN.** |

### The chosen shape

A dispatched operation records, on its receive stage, what it was asked *about*:

```
input_refs: [{ "percept_id": "pctx_…",
               "grounds": [{ "ground_id": "gnd_…", "region_id": "…",
                             "geometry_rev": 2, "mask_hash": "…", "detached": false }],
               "packet_digest": "sha256:…" }]
```

The thread then answers *"has anything read this percept?"* by **querying runs for the post and
filtering on `input_refs[].percept_id`** — exactly how it already answers *"is this cited in the
writing?"* by filtering mentions.

**Why this is the right shape, in one sentence:** *the run is the thing that happened, so the run
should be the thing that remembers; the percept should stay a noticing, not become a ledger.*

**Cost, stated honestly:** a query per render rather than a field read. On this corpus (9 runs) that
is nothing; if it ever matters, the fix is a materialized index — which is a *cache* of a derived
truth and can be rebuilt, not a second source of it.

---

## 3. Q2 — What is the relation called?

**Decision: `observed_run`.**

| candidate | verdict |
|---|---|
| `produced_by` | **Rejected — causal, and false in both directions.** The run did not produce the percept (a curator did), and the percept did not produce the run. |
| `reading_run` | Rejected: presumes the operation was a *reading*. `challenge` is not. |
| `run_ref` / `operation_ref` | Accurate and empty. They name a pointer, not a relation, and the thread would have to invent the verb anyway. |
| `referenced_run` | Ambiguous about direction — who referenced whom. |
| **`observed_run`** | **Chosen.** From the percept's side the run is something that *looked at* it. True, directionally clear, and non-causal: observing something does not make it, confirm it, or validate it. It also matches the vocabulary the codebase already uses for runs — `observed_at`, "observation order". |

**Binding:** `observed_run` names the *relation*. It never appears as a claim about truth, and no
surface may render it as `validated`, `confirmed`, `proved`, or `generated`.

---

## 4. Q3 — What does supersession mean?

**Decision: supersession requires the same operation, the same percept, AND the same evidence
fingerprint. Otherwise it is not a newer answer — it is a different question.**

This is the load-bearing rule of the whole design.

| situation | relation |
|---|---|
| `challenge` on percept P, evidence fingerprint F, then `challenge` on P with the **same** F | the newer **supersedes** the older |
| `challenge` on P with F, then `challenge` on P with **F′** (a ground was refined, replaced, or detached) | **neither supersedes.** They answer questions about *different evidence*, and collapsing them would let a newer answer silently overwrite one that was true of what was actually there |
| `challenge` then `read` on P | **independent.** Different operations are not versions of each other |

**Nothing is deleted.** Older runs are retained — a superseded answer is still a record of what was
said, and Codex's whole subject is *the standing of a noticing changing over time*.

**Rendering:** the thread shows the latest as `last challenge recorded`, and older ones only when
expanded, as `older challenge`. A run whose fingerprint no longer matches the percept's current
evidence is rendered **`challenge recorded · evidence has changed since`** — which states the fact
and refuses the inference. It is not marked wrong; it is marked *asked of something else*.

**Precedent, and it is already in the code:** `project_run` computes `stale` / `staleness_seconds`
from real timestamps and refuses to claim a run is live forever. Supersession is the same honesty
applied to relevance rather than liveness.

---

## 5. Q4 — Minimal first operation

**`challenge`.** Reaffirmed from the dispatch decision; the reasoning is unchanged and is not
restated here beyond its core: *its output is supposed to disagree, so a curator reads it sceptically
by construction, whereas an agreeable `read` beside a percept is taken as endorsement.*

One addition this gate makes: **`challenge` is also the operation whose supersession rule is least
dangerous to get wrong.** A stale challenge that is still visible is a stale objection — a curator
can weigh it. A stale *reading* that is still visible looks like standing description of the image.

---

## 6. Q5 — Interaction with stable evidence identity

**This is where the design is weakest, and the weakness is not fixable by the run relation.**

`CIRCUIT-001-P0-open-decisions.md` §1 remains open: region ids are per-run positional ordinals, and
**the dangerous case is the live-but-wrong reference** — a re-dissect producing the same number of
regions gives every reference a resolving id pointing at different geometry.

**The existing refs already inherit this.** In the corpus today, `find_similar` stores
`input_refs: [{"region_id": "seg_0", …}]` — `seg_0` being precisely the collision-capable ordinal
`HW-C8` enumerated. **A run relation built naively on ids would industrialise the problem: it would
let a model's answer be re-pointed at evidence it never saw, with provenance that still looks
clean.**

**Therefore: the run relation cannot make a run's answer trustworthy. It can only record enough to
DETECT later that it should not be trusted.** Four things must be captured **at dispatch**, and all
four already exist somewhere in the system:

1. **Ground identity AND generation** — `ground_id`, `region_id`, **`geometry_rev`**, and
   `mask_hash` where available. `geometry_rev` is already stored in refine's refs; `mask_hash` is
   already computed by the embedding service. **Nothing new is invented; it is collected.**
2. **Evidence state at dispatch** — the packet's `evidence.state` (`intact` / `partial` / `detached`
   / `ungrounded` / `unknown`). A question asked over already-detached evidence must be legible as
   such forever after.
3. **A packet digest** — a hash of the built packet, so the exact request is identifiable without
   storing a fourth copy of its contents.
4. **Input refs, per ground, not per percept.** A percept-level ref cannot tell you *which* ground
   changed.

**What must be true before a run's answer is trusted:** its recorded fingerprints still match the
percept's current grounds. When they do not, the honest render is *"evidence has changed since"* —
**not** a silent refresh, and **not** a claim the answer is wrong.

**Stated plainly: `suspect` detection is a precondition for trusting run answers, not a follow-on
from them.** That drives §8.

---

## 7. Q6 — Thread language, and Q7 — the cost of being wrong

### Language

**Permitted:** `challenge recorded` · `reading recorded` · `last challenge · <when>` ·
`older challenge` · `challenge recorded · evidence has changed since` · `no model reading recorded` ·
`packet prepared, not sent`.

**Forbidden:** `proved` · `validated` · `confirmed` · `caused` · `generated this percept` ·
`supports` · `agrees with` · anything implying the run *tested* the percept.

**Voice:** a run is a **RECORD** (something observed, pointable), never a judgement — the system did
not conclude it, a model produced it. This matches P1D's existing filing of
`no model reading recorded`.

**And one rule inherited from spark-10:** a `challenge` that returns contradictions must not be
rendered as having tested anything. Arm E supplied three real, image-grounded contradictions and
moved not at all.

### If this is wrong

| failure | what it looks like |
|---|---|
| **False authority** | a model's sentence rendered beside a curator's own words, in the same register, reads as a second opinion of equal standing. Mitigated by the record/judgement split and by `challenge` first. |
| **Stale readings** | an answer to a question about evidence that has since changed, presented as current. This is what §4's fingerprint rule exists for, and it is the most likely failure to actually ship. |
| **Endorsement mistaken for truth** | the reason `read` is not first. |
| **Wrong evidence via suspect reattachment** | **the worst case, and the only one that produces a confidently wrong answer with clean-looking provenance.** No part of this design fixes it; §6 only makes it detectable. |
| **Atlas/Codex inheriting fake lineage** | the compounding one. Both surfaces are *about* accumulated relations. A run relation that quietly re-points would let a cross-image surface assemble a history that never happened — and unlike a single wrong row, an assembled history is read as a pattern. |

**The asymmetry worth naming:** every failure above except the last is visible to the curator who
made the percept. Atlas and Codex would show these relations to a reader who was not there.

---

## 8. Recommended next gate

**Chosen: B — `P1F — Stable evidence identity precondition`.** Not the dispatch prototype.

**Why not A (challenge dispatch prototype).** §6 is decisive: a run's answer cannot be trusted while
a reference can silently re-point, and dispatch would attach model output to exactly that. Building A
first means the first model reading in the product ships on the one hazard the whole programme has
been tracking — and it is the failure that looks clean.

**Why not C (durable Mention prep).** Genuinely valuable and correctly ordered *after* B. Its own
blocker is unchanged: the corpus has **0 text blocks**, so there is still no evidence of how curators
actually cite. Making citation durable before knowing its shape is the premature-crystallisation risk
`HW-S2` §5 names.

**Why B.**

1. It is the **precondition** §6 identifies, not a detour from it.
2. It is **already authorized with conditions and unscheduled** —
   `Decisions/HW-C9-announcement-only-merge-fix.md`: `suppressed_by_id` + `suppressed_by_geometry`
   counters in the existing `STAGE_MERGE_CURATOR` detail, classified by the **existing
   `_region_box_iou`**, with a byte-identical-`region_annotations` acceptance test. **Three integers
   and arithmetic that cannot raise.**
3. It unblocks **three** things at once: run-answer trust, `suspect` in the Circulation Thread (which
   currently renders `substitution not assessed`), and Atlas's precondition.
4. It is the smallest change with the largest release of blocked work — and its worst case is *"the
   number is always zero"*, which is a result.

**One correction B should carry:** HW-C9 scoped the counters to the id guard at `posts.py:804`,
covering the 2 exposed curator regions. The **auto→auto** branch at `:809-819` re-points an ordinal
onto a new mask and counts it in `kept_auto` as an ordinary survivor — covering the **51-region** auto
population. **The larger exposure is the uninstrumented one**, and P1F should instrument both.

---

## 9. What this decision does NOT authorize

- **No dispatch, no model call, no `run_id` field, no route, no schema, no collection, no migration.**
- No change to `input_refs` / `output_refs` today — the shape in §2 is a *design*, not a change.
- No persisted Percept Packet, no persisted Mention, no `suspect` implementation, no Atlas, no Codex.
- **No claim that this design makes run answers trustworthy.** §6 says the opposite: it makes them
  *auditable*, which is a different and lesser thing.
