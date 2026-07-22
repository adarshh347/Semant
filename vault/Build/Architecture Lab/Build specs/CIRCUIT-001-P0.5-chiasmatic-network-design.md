# CIRCUIT-001 P0.5 — The Chiasmatic Network: product architecture

**DESIGN DOC — no implementation authorized, no code changed, no production data touched, no model
calls.** Names and defines the living architecture. The buildable slice is
`CIRCUIT-001-P1-differential-manuscript-circuit-spec.md`; its verification scenes are
`CIRCUIT-001-P1-test-scenes.md`. Rests on `CIRCUIT-001-P0-product-circuit-map.md` (file:line
evidence, not re-derived here).

> **The framing that governs this phase, in the user's words:** *"We should not build Atlas/Codex as
> giant nouns. That's how systems become theatrical. We should build the Chiasmatic Circuit: the real
> relations between image evidence, percepts, writing, runs, and future comparative/temporal
> surfaces."*

**And the correction that shaped this document:** evidence honesty is **the immune system, not the
organism.** A product that only tells you what is broken is a diagnostic tool. The organism is the
**circulation** — and the finding that reorganised this design is that *the circulation is severed at
its most important join, and severed by absence rather than by bug.*

---

## 0. The discovery that reorganises everything

`DifferentialWorkspace.jsx:19-23` — Differential is **a full-workspace MODE inside `PostDetailPage`,
not a route**; the Chiasm shell *stays mounted* so unsaved Manuscript state survives. It is rendered
at `PostDetailPage.jsx:890`. **Both surfaces share one `regionStore`.**

And yet: grepping Differential for any handoff to the Manuscript returns exactly one hit —
`DifferentialWorkspace.jsx:450`, a **"Back to Chiasm"** button.

**A percept composed in Differential has no way to reach the writing.** The curator forms it
(`:347-350`), it is persisted (`regionStore.js:177`), and then they must leave, remember it existed,
type `/percept`, and find it again in a picker whose empty state says *"No percepts yet — compose one
in Differential"* (`RefPicker.jsx:113`).

*(Fable-pass.)* **The two halves of the product are in the same component tree, sharing the same
store, and there is no artery between them.** That is not a missing feature; it is the missing
circulation. Everything in this document proceeds from it.

---

## 1. The Chiasmatic Network

**Definition.** The Chiasmatic Network is the full circuit a noticing travels, and the rule that it
must be able to **return**.

```
        ┌──────────────────────────── return ────────────────────────────┐
        │                                                                │
     image ──▶ ground ──▶ percept ──▶ mention ──▶ recall ──▶ operation ──┴─▶ trace
       │         │          │           │          │           │            │
    evidence   citation  noticing    writing   performance   asking      memory
```

Read as a sentence: **something is seen; part of it is cited as evidence; a noticing is composed from
those citations; the noticing is carried into writing; the writing can perform the noticing back onto
the image; the noticing can be put to a model; and the asking leaves a trace that rejoins the
circuit.**

*Chiasmatic* is load-bearing rather than decorative: the circuit **crosses**. Image and text are not
two panes side by side; each is the other's evidence. The manuscript cites the image, and the image —
through recall — performs the manuscript. **The crossing is the product.**

### 1.1 The seven hops, and the state of each today

| hop | exists? | state |
|---|---|---|
| image → ground | ✅ | solid. `makeGround`, `groundFromRegion`, seven ground types |
| ground → percept | ✅ | solid. Composer at `DifferentialWorkspace.jsx:288-350`; `pctx_` percepts are **the only durable object in the relationship model** |
| **percept → mention** | ❌ | **SEVERED. No affordance exists.** §0 |
| mention → recall | ⚠️ | the machinery is correct and **is not rendered on the writing surface** (`RegionSurface.jsx:330-332` drops `evidenceNote`) |
| recall → operation | ❌ | a percept cannot be put to a model. No path |
| operation → trace | ⚠️ | 4 of 13 operations instrumented; **no produced entity carries a `run_id`** |
| trace → return | ❌ | nothing re-enters the circuit. `vision_runs` is written and never read by a curator surface |

**Three of seven hops do not exist; two are half-built.** The circuit is a chain of arcs, not a loop.
**P1 closes the one that matters most.**

### 1.2 The design rule the network imposes

> **Nothing may enter the circuit without being able to say where it came from, and nothing may
> leave it without being able to return.**

This is one rule, not two, and it is why provenance and recall belong to the same design. A percept
that cannot be recalled is a dead end; a mention that cannot say what it cites is a rumour.

---

## 2. Perceptive Orchestration

**Definition.** The layer at which **a percept becomes an operation packet** — the thing you can put
to a model without laundering its origins.

Today a model call carries an image and a prompt. Nothing that reaches a VLM knows it is *about a
percept*, and nothing that comes back knows what it was asked about. This is why
`semantic_pass.py:104`'s global reading **has no id** and `enforce_candidate_ids` cannot reach it —
the asking had no anchor to begin with.

**An operation packet is a derived, in-memory value.** It is not a collection, not a schema, not a
stored document. It is assembled at the moment of asking, from state already present:

| field | source (existing) | why it must be in the packet |
|---|---|---|
| **intent** | the operation the curator chose | so the trace records *what was asked*, not just *that something was asked* |
| **grounds** | `percept.ground_ids` → `post.grounds` | the evidence the question rests on |
| **evidence state** | `resolveGround` per ground (`grounds.js:68`) | **so a question over dead evidence can be refused or flagged before it is asked** |
| **manuscript context** | the block the mention sits in (`text_blocks`) | so the model answers *this* passage, not the image in general |
| **external-claim rules** | `HW-C5` as amended | so the ask carries its own constraints (`no_iconographic_identification` already exists in rehearsal manifests) |
| **model run history** | `vision_runs` for this post | so a repeat asking is legible as a repeat |
| **allowed operations** | the profile's `scheduled_passes` + capabilities | so the UI cannot offer what cannot run |

**What Perceptive Orchestration is NOT, and this is the whole discipline:** it is not an agent, not a
pipeline, not a queue, and **not a place to put intelligence**. It is a *packing rule*. Its value is
that the packet is **inspectable before it is sent and recorded after** — which is precisely what the
rehearsal program spent eleven runs learning to do, and what production does not do at all.

*(Fable-pass.)* The rehearsals already built this and called it a **manifest**. A rehearsal manifest
freezes intent, stimulus, constraints and grid *before* the call, and the runner **refuses an invalid
manifest before spending budget** — that ordering caught two errors at zero cost. **Perceptive
Orchestration is the manifest discipline moved into the product**, minus the research apparatus.

---

## 3. Liquid Constructs

**Definition.** Research-born interpretive identities that are **real enough to name and not yet real
enough to be schema**: *address*, *motif*, *kinship*, *surface-becoming-structure*, *scope*,
*external claim*, *abstraction-as-immunisation*.

**Why they need a name at all.** The rehearsal program produced ten sparks and a hard rule that
**nothing graduates** without ≥3 fixtures, a transfer test and a negative. That rule is right and has
already paid: spark-08 was *weakened* by run 011 after three runs had lined up behind it, and spark-09
was rewritten twice. **A construct that had become a database column in cycle 8 would have been wrong
by cycle 10.**

But the opposite failure is equally real: a construct with no vessel stays in a markdown file and
never touches the product, and the vault becomes what `HW-S2` warned of — *"the most developed prose
and the least evidenced structures."*

**A Liquid Construct is the vessel between those failures.** Its rules:

1. **It travels as a candidate, always labelled.** A UI that shows one shows it as *a way of reading*,
   never as a property of the image.
2. **It is never the primary key of anything.** No `construct_id` on a Region, Ground or Percept.
3. **It may shape a question but never a stored answer.** *Address* may be a lens you can ask through;
   it may not be a field asserting an image *has* address.
4. **It carries its own evidence and its own scope**, in the register the rehearsals established:
   spark-06 is resolved **for address vocabulary, on one image**, and any surface citing it must be
   able to say so.
5. **It can be retired.** A6's two-stage device was retired in cycle 10; a construct must be as
   retirable as an instrument.

**The one that matters most for product safety** is `abstraction-as-immunisation` (spark-10): a claim
restated at an altitude its own counter-evidence cannot reach — supplying real contradictions that
bear on nothing. **Semant's entire method asks a reader to say what supports what they say.** Arm E
showed that demand can be satisfied *formally* and emptied. **Any Semant surface that solicits
justification inherits this failure mode**, and Perceptive Orchestration is where that is checkable —
because the packet knows the grain of the question it asked.

---

## 4. Circulation Thread

**Definition.** A visible chain showing **what happened to a noticing** — without inventing why.

The distinction is doing real work. `DifferentialWorkspace.jsx:815` currently reads *"its part was
replaced by a re-dissect"*, and `resolveGround` (`grounds.js:71-72`) **only knows the `region_id` is
missing**. The product asserts a cause it cannot know — while the project's own causal-language guard
(`visionActivity.js:164-171`) exists and covers only the Rail. **The Circulation Thread must extend
that guard to the whole circuit.**

### 4.1 The nine relations

Grouped by what kind of thing each is, because conflating them is how a thread becomes a lie.

**Observed / recorded — things that happened, with a record:**
| relation | means | provenance |
|---|---|---|
| **observed** | a detector or a curator marked this part | region `actor` + `detector` |
| **cited** | a ground names this evidence | `ground.region_id` |
| **referenced** | a manuscript passage carries this percept | the chip in `text_block.content` |
| **recalled** | recall was played from that passage | client event |
| **inferred** | a model produced this | a run + adapter |

**Judgements — things the system concludes, and must mark as its own:**
| relation | means | discipline |
|---|---|---|
| **external** | a claim the frame does not settle | `HW-C5`/`HW-C8` — records *frame-settleability*, **never truth** |
| **missing** | the referent does not resolve | states absence; **never a cause** |
| **suspect** | it resolves, but something changed underneath | *the most important one, and it does not exist today* |
| **challenged** | a human disagreed | the only relation a model may never author |

### 4.2 Why **suspect** is the load-bearing invention

P0's sharpest inference: **the dangerous case is not the dead reference — it is the live one.** A
re-dissect producing the same number of regions gives every `/part` chip a resolving id, a stale
label, and a confident highlight of the wrong part, **with no signal anywhere**.

Today the vocabulary has two values: *resolves* and *does not*. **`suspect` is the third**, and it is
what turns a defensive check into a product: it is how the circuit says *"this still points somewhere,
and I am no longer sure it is the same somewhere."*

**It requires nothing new to be stored.** `geometry_rev` and `mask_hash` already exist on regions and
embeddings; a reference that captured either at insert time could compare. **P1 does not build it** —
P1 makes the seam where it would live.

### 4.3 What the Thread must never do

- **Never assert a cause.** *"No longer resolves"*, not *"replaced by a re-dissect"*.
- **Never render nine badges.** Degradation-only display is the established discipline; a thread that
  announces every nominal state is noise, and noise is how honesty stops being read.
- **Never present a judgement in the same register as a record.** The four judgements need a visibly
  different voice from the five records.
- **Never let a model author `challenged`.**

---

## 5. Atlas and Codex as future surfaces

Both are **surfaces over the circuit**, never stores of truth, and **neither reduces to evidence
health.**

**Atlas — the comparative surface.** *"What has happened across everything?"* Percepts and their
evidence, across images: what recurs, what a curator keeps noticing, where two noticings rhyme.
`HW-S1`'s dividing line holds — existing surfaces answer *"is what I'm looking at real?"*; anything
failing that test belongs in `RegionSurface`, `RefPicker` or the recall path.
**Materialized view, not store** — three independent sources agree, and `HW-S2` §1 argues the
evidence pushes harder than the prose: *an arrangement over objects whose evidence can silently vanish
should not be where truth is stored.* **Evidence health is one column in an Atlas, not its purpose.**

**Codex — the temporal and accountability surface.** *"What did I think, when, and on what?"*
Its centre has moved from long-form container to **the layer at which change over time is
answerable** — the multi-page editor is the least interesting part.
**Its two preconditions do not exist:** a citation durable outside the prose it sits in, and **a
record that evidence was destroyed rather than merely absent**. Today detachment cannot be
distinguished from a never-existed id or a typo.

**The honest caveat that travels with both:** *no rehearsal in R0–R2 tested a cross-image surface at
all.* The evidence says what these surfaces would have to **survive**; it says nothing about whether
they are needed. **Naming them is not a decision to build them.**

---

## 6. How the five concepts compose

```
   LIQUID CONSTRUCTS ......... ways of reading, always labelled candidate
            │ shape questions, never stored answers
            ▼
   PERCEPTIVE ORCHESTRATION .. packs a percept into an inspectable operation
            │ records what was asked, on what evidence, under what rules
            ▼
   CHIASMATIC NETWORK ........ the circuit the noticing travels and returns through
            │ every hop provenanced, every reference recallable
            ▼
   CIRCULATION THREAD ........ shows what happened, never why
            │
            ▼
   ATLAS (across images) · CODEX (across time) ... surfaces, not stores
```

**One sentence:** *Liquid Constructs shape the asking, Perceptive Orchestration makes the asking
inspectable, the Chiasmatic Network carries the answer home, the Circulation Thread shows the journey
without inventing it, and Atlas and Codex are the views you get once the circuit is real.*

---

## 7. What this document does NOT authorize

- **No entity, collection, route, schema, migration or field.** Not `Construct`, not `Packet`, not
  `Thread`, not `Mention` as a stored document.
- **No Atlas and no Codex.** Naming a surface is not scheduling it.
- **No repair of production data**, no id migration, no backfill.
- **No graduation of any spark.** The R3 bar stands: ≥3 fixtures, a transfer test, a negative.
- **No claim that this architecture is validated.** It is a design read off one audit and eleven
  rehearsals; its first real test is P1.
- **`suspect` is designed, not built.** P1 makes the seam; a later gate decides the mechanism.
