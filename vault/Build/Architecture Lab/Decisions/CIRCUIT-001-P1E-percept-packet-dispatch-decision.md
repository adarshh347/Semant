# CIRCUIT-001 P1E — Should Percept Packets be dispatched to model operations?

**DECISION NOTE — no implementation authorized. Nothing dispatches in P1D and nothing may dispatch
on the strength of this document.** No code changed by this note.

| | |
|---|---|
| **id** | CIRCUIT-001 P1E · arises from P1C (`278fb2d`) and P1D |
| **date** | 2026-07-22 |
| **status** | **DEFER — do not dispatch in P1E.** Conditional GO stated in §6. |
| **decision, in one line** | **Dispatch turns an inspectable request into a recorded event, and the circuit cannot yet record events. Build the relation first, then dispatch.** |
| **rests on** | `CIRCUIT-001-P0-product-circuit-map.md` §5; `HW-C10-abstraction-as-immunisation.md`; the P1C and P1D reports |

---

## 1. Why dispatch makes `run_id` unavoidable

Today the Circulation Thread says **"no model reading recorded"** and that sentence is *true* — a
fact about our ledger, not a hedge. **The moment a packet is sent, it stops being true and becomes a
lie**, because a reading will exist and the thread will still not be able to name it.

P0 §5 established the shape of the problem: **no Region, Ground, Percept, assertion or embedding
carries a `run_id` anywhere in the codebase.** `vision_runs` records the *attempt* — operation,
timing, per-stage status, bounded counts — and **never the ids it produced**; `STAGE_PERSIST` logs
`{region_count, matched_count}` only.

So a dispatched packet would produce a reading that:

- cannot be attached to the percept it was about,
- cannot be found again from the percept,
- cannot be distinguished from a reading of a different percept on the same image,
- and cannot be superseded, because there is no identity to supersede.

**Dispatch without `run_id` does not merely miss a feature. It manufactures exactly the failure this
programme was built to remove:** a claim in the product whose provenance cannot be recovered. The
rehearsals spent eleven runs establishing that an unprovenanced model claim is the thing to guard
against; shipping one from our own product would be the same error with our name on it.

**Corollary that constrains the design:** `run_id` is not a column to bolt on when convenient. The
question *"which entity carries it, and what happens when the run is superseded"* is the durable
identity question again, and it belongs with the open decisions in
`CIRCUIT-001-P0-open-decisions.md` §1 — not inside a dispatch ticket.

## 2. Why P1D stops at prepared/unsent

Three reasons, in order of weight.

**(a) The packet's value is realised before it is sent.** It makes visible *what would be asked, on
what evidence, under what constraints* — and lets a curator see that a question rests on grounds that
no longer resolve **before** paying for a confident answer about nothing. That is the whole
manifest discipline: the rehearsal runner's refusal of an invalid manifest cost **zero** model calls
twice, and both times the refusal was the valuable event.

**(b) An unsent packet cannot be wrong about provenance.** `dispatch: { sent: false, run_id: null }`
is a complete and honest record. There is no state it can drift into.

**(c) Stopping here is cheap; stopping later is not.** Once a surface has shown a curator a model
reading attached to their percept, removing it is a regression they will feel. **The right order is
relation first, then dispatch** — the reverse ordering is how a product acquires a feature it cannot
later make honest.

## 3. What must remain non-causal, whatever P1E does

The Circulation Thread's rule holds through dispatch and after it:

- A model reading row may say **`read recorded · <when>`**. It may **never** say the reading
  *explains*, *confirms*, *supports* or *was caused by* the percept — and never that the percept was
  caused by the reading.
- A reading is a **record**, in the record voice, exactly like `mentioned`. It is not a judgement,
  because the system did not conclude it — a model produced it.
- **A model may never author the `challenged` relation.** A model disagreeing is a model's output;
  a *challenge* is a curator's act. Collapsing the two would let the product treat a generated
  sentence as a human's dissent.
- The reading must be marked as **external claim territory by default** — `mark_external_claims` is
  already on in `DEFAULT_CONSTRAINTS`, and the thread's `external claims not assessed` row must
  become *assessed* only when something actually assessed them.

## 4. If dispatch is later approved, what goes first

**Recommended first operation: `challenge`.** Not `read`.

| candidate | case | verdict |
|---|---|---|
| **challenge** | Asks the model to argue **against** the percept from the image. Its output is *supposed* to disagree, so a curator reads it sceptically by construction — the safest possible first output to put beside a curator's own words. It also directly exercises `ask_for_contradictions`, the constraint spark-10 exists to test. | **first** |
| `read` | The most tempting and the most dangerous first: an agreeable interpretation sitting beside a percept is read as endorsement, and `semantic_read` already exists, so the marginal product value is low. | later |
| external-claim audit | High value and **not a percept operation** — it audits prose, not a noticing, so it does not need the packet at all. Worth doing; belongs elsewhere. | separate track |
| compare | Cross-image, so it is Atlas territory and blocked on the durable-citation decision. | not yet |

**And a caution that comes from our own evidence.** `challenge`'s output is exactly the shape
spark-10 described: real, image-grounded contradictions that can be arranged to bear on nothing. Arm
E supplied three and moved not at all. **A challenge feature must not be presented as having tested
the percept.** It produces material for the curator to weigh; it does not adjudicate.

## 5. Risks of dispatching before the prerequisites

| prerequisite | why dispatch before it is harmful |
|---|---|
| **`run_id` relation design** | §1. The reading cannot be found, attached, or superseded. |
| **durable Mention decision** (open-decisions §4) | A reading about a percept that is cited in prose is *more* consequential than one about a workspace percept — and today the citation itself is reconstructed from markup on every load. Dispatch would put model output on the strongest end of a chain whose weakest link is unresolved. |
| **suspect detection** | A packet can say a ground *resolves*. It cannot yet say it resolves **to different geometry** (P0's live-but-wrong reference). Dispatching a question about evidence that silently changed underneath is the worst case in the whole map: a confident answer about the wrong part, with provenance that looks clean. |
| **cost and rate limits** | The rehearsals hit `413` and `429` repeatedly and learned that a 413 is unservable rather than transient. A product-side dispatch path needs that knowledge encoded, and P1D has no throttle, no budget, no retry policy. |

**The third row is the one that would keep me up.** Everything else produces a missing feature;
`suspect` produces a *wrong answer that looks right*.

## 6. Verdict

**DEFER. Do not dispatch in P1E.**

**Conditional GO** — dispatch may be built when all of these hold:

1. A `run_id` relation is **designed and decided** (not implemented) — specifically, which entity
   carries it and what supersession means.
2. The **durable Mention** fork in `CIRCUIT-001-P0-open-decisions.md` §4 is taken.
3. The first operation is **`challenge`**, with a curator-initiated trigger — never automatic, never
   on selection.
4. The thread's model-reading row is a **record**, non-causal, and the reading is marked external-
   claim territory.
5. A throttle and a budget exist, with `413` treated as unservable rather than retryable.

**What P1E should do instead:** the `run_id` relation *design*, as a decision doc — the question is
identity, not plumbing, and it is the same question `suspect` and Atlas both wait on.

## 7. What this note does NOT authorize

- **No dispatch, no route, no model call, no queue, no `run_id` column.**
- No change to `DEFAULT_CONSTRAINTS`, which are not a prompt and must not become one here.
- No Atlas, no Codex, no persisted Mentions, no suspect detection.
- **No claim that `challenge` is safe** — only that it is the safest first, and that its output must
  never be presented as having tested anything.
