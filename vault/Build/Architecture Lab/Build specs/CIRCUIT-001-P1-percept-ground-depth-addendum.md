# CIRCUIT-001 P1 — Percept and Ground as travelling expressive units

**ARCHITECTURAL ADDENDUM — no implementation authorized by this document.** No entity, field, schema,
collection, route or migration is proposed. Extends
`CIRCUIT-001-P0.5-chiasmatic-network-design.md`; the code evidence it rests on is in
`CIRCUIT-001-P0-product-circuit-map.md` and is cited, not re-derived.

**Why this document exists.** P1A is a small, safe slice, and small safe slices have a way of
becoming the whole ambition. **This addendum is the guard against P1A being read, later, as "the
evidence-health patch" — as though the circuit were a validation problem.** It is not. Evidence
honesty is the immune system. The organism is a **perceptual act circulating**, and a Percept and a
Ground are the units that travel.

The test of every proposal below: *does this help a noticing move, or does it only help the system
check itself?* Both are needed. Only one is the product.

---

## 1. Percept as a travelling object

**Today** a percept is `{id, expression, ground_ids, properties}` — persisted at
`regionStore.js:177`, composed at `DifferentialWorkspace.jsx:288-350`. It is durable, untyped, and
**static**: it records *what was said* and nothing about *what kind of saying it was*, *how far it
claims*, or *what happened to it afterwards*.

A travelling percept needs twelve things. **None of them is proposed as a stored field**; each is
marked by where it would live.

| # | facet | what it is | where it lives |
|---|---|---|---|
| 1 | **expression** | the curator's words | **exists** — `percept.expression` |
| 2 | **act type** | *what kind of noticing this is* — see §3 | **derived at composition**, from which affordance made it |
| 3 | **scope** | how far the claim reaches: *this part* / *this image* / *this kind of image* / *unbounded* | **curator-declared, later.** The rehearsals' hardest-won discipline: spark-06 is resolved *for address vocabulary, on one image*, and every citation of it must say so |
| 4 | **register** | descriptive / interpretive / comparative / speculative / quoted | **derived**, and it is what lets a surface show a guess differently from a description |
| 5 | **ground bundle** | the evidence cited | **exists** — `ground_ids` |
| 6 | **ground roles** | *what each ground does* for this percept — see §2 | **per-percept**, not per-ground. The same region is an anchor in one percept and a counterforce in another |
| 7 | **provenance** | who composed it, from what, when | **partly exists** (`actor`); no `run_id` anywhere (P0 §5) |
| 8 | **manuscript mentions** | where it has been written about | **reconstructed and lossy today** (`perceptMentions.js:154-170`) |
| 9 | **recall behaviour** | how it re-performs | **exists** — `buildRecallScript`. Currently one choreography for all percepts |
| 10 | **challenge / revision** | that a human disagreed, or that the curator changed their mind | **does not exist.** A percept can only be deleted, and deletion is not revision |
| 11 | **transfer potential** | whether this noticing is *about this image* or *about a way images work* | **does not exist**, and it is the hinge Atlas turns on |
| 12 | **Liquid Construct relation** | that this percept is *an instance of address*, *of motif* | **does not exist.** Must be a **candidate** relation, never a classification |

### 1.1 The three that matter most, and why

**Scope (3)** is the difference between a note and a claim. A percept saying *"the upper head"* claims
nothing; one saying *"this façade addresses the viewer"* claims a great deal. Without scope, Atlas
cannot compare two percepts without silently equating their reach — **and that is exactly the
`abstraction-as-immunisation` failure at the product level**: a claim pitched at a level where nothing
can contradict it. Run 011's model did this by *"or, more broadly"*. A product that never asks a
curator how far they mean does it by default.

**Ground roles (6)** are what make a percept a *reading* rather than a *list*. *"The arch and the
shadow"* is two grounds; *"the arch, held against the shadow"* is a percept. The role is not a
property of the ground — it is a property of **this percept's use of it**, which is why it cannot live
on the Ground record.

**Challenge/revision (10)** is what makes the circuit temporal rather than accumulative. It is
**Codex's real subject**, and it is the reason Codex is *not* a long-form editor: what changes over
time is not the prose but **the standing of a noticing**.

### 1.2 Percept biography — the object Codex would read

Composed → cited → written about → recalled → put to a model → contradicted → narrowed → recalled
again. **Every one of those is already an event the system could observe today and does not record.**

**The design constraint:** a biography must be *derivable*, not *maintained*. The moment percept
biography becomes a stored log, it acquires a truth of its own that can disagree with the circuit —
the exact failure of the durable `detached: true` flags, which are correct today and would go stale
on collision, **written by nothing and read by nothing**.

---

## 2. Ground as expressive architecture

**Today** a ground is `{id, ground_type, region_id | points | strokes | member_ids, actor, label}`,
with seven types (`grounds.js` `GROUND_TYPES`). The type says **what shape the evidence has**. It says
nothing about **what the evidence does**.

### 2.1 Substrate — *what kind of evidence this is* (exists)

`region · field · path · boundary · frame · constellation · relation`, plus two the product uses
without naming: **interval** (a stretch of something — A1F found detection proposes *things*, never
intervals) and **crop** (a curator-authored view, which A6's fixtures used and never persisted).

**Substrate is durable and already right.** Nothing in this addendum changes it.

### 2.2 Role — *what this evidence does for this percept* (does not exist)

A vocabulary, offered as candidates rather than a taxonomy:

| role | the ground… |
|---|---|
| **anchor** | is what the percept is chiefly about |
| **threshold** | is where something changes — an edge, a transition |
| **pressure** | pushes on the reading without being its subject |
| **rhythm** | is one of several repeating things, and the repetition is the point |
| **atmosphere** | is a condition, not an object — light, haze, tone |
| **aperture** | is an opening through which something else is seen |
| **support** | corroborates the anchor |
| **counterforce** | works *against* the reading, and is cited anyway |
| **trace** | is the residue of something absent |
| **external limit** | is where the frame stops settling the question |

**`counterforce` is the most important entry and the reason this vocabulary is worth having.** Run 011
showed a model supplying three real contradictions that bore on nothing, because it had pitched the
claim above them. **A percept that can cite its own counterforce is a percept whose contradictions
are structurally attached to it** — they cannot be floated free by restating the claim.

`external limit` is where `HW-C5`'s convention meets the product: a ground can mark *the frame does not
settle this* **as evidence**, rather than as a caveat in prose.

### 2.3 Behaviour — *how it acts in time*

`orient · hold · pull · resist · open · return · migrate · decay · transform · contradict · remain
silent`

**Two of these are already real and unnamed.** *Decay* is what `resolveGround` detects. *Remain
silent* is a field or frame that survives a re-dissect because it carries its own geometry — the
corpus sweep found **0 of 15** geometry-bearing grounds detached against **4 of 11** reference-based.
**Substrate already determines behaviour under change, and the product does not say so.**

### 2.4 The travel path

```
Differential mark → Percept role → Manuscript phrase → Recall object
        → Orchestration packet → Atlas comparison → Codex memory
```

| hop | state today |
|---|---|
| mark → role | **role does not exist**; a ground enters a percept unqualified |
| role → phrase | **the artery is missing** (P0.5 §0) |
| phrase → recall object | **works, and is the one hop the product does well** |
| recall → packet | **no operation path exists** |
| packet → Atlas | blocked on the durable-citation decision |
| Atlas → Codex | blocked on a record that evidence was *destroyed*, not merely absent |

**Three of six hops are missing. P1A hardens the one that works; P1B builds the second.**

---

## 3. The Perceptual Act

**Definition.** The unit Perceptive Orchestration packs. Not a UI verb and not a model call — **the
kind of noticing being performed**, which determines what evidence is required, what a model may be
asked, and what would count as being wrong.

| act | the curator is… | grounds required | what would falsify it |
|---|---|---|---|
| **isolate** | saying *this part, not that* | ≥1 anchor | the part is not distinguishable |
| **relate** | saying two things bear on each other | ≥2, one non-anchor | the relation holds for any pair |
| **compare** | saying two things are alike or unlike | ≥2, across frames | the likeness is at an altitude nothing can contradict — **spark-10** |
| **challenge** | disagreeing with a reading | the reading + ≥1 counterforce | — |
| **return** | re-performing a noticing on its evidence | the original bundle | the evidence no longer resolves |
| **transfer** | claiming this holds beyond this image | ≥2 images | it holds only here — the R3 bar in product form |
| **externalize** | admitting the frame does not settle it | ≥1 external limit | the frame *does* settle it |
| **split** | one noticing was two | the original | — |
| **revise** | narrowing or widening a standing noticing | the original + what changed | — |
| **rehearse** | trying a reading without committing | any | — |

### 3.1 Three observations that make this more than a list

**`compare` and `transfer` are where the product can be wrong in the way the rehearsals discovered.**
Both are altitude-sensitive. A `compare` act should therefore be the one place the product **asks for
the grain** — *at what level are these alike?* — because that is exactly the question run 011's model
answered for itself with *"or, more broadly"*.

**`rehearse` is the act that keeps the product humane.** Without a non-committal act, every noticing is
a claim, and a surface where every mark is a commitment is a surface people stop marking in. The
rehearsal program's own `mode: imaginative` versus `instrumented` split is the same distinction, and
it worked.

**`challenge` is the only act a model may never perform.** It is the human's veto over the circuit.
This is not caution — it is what keeps the circuit a **reading** rather than an inference pipeline.

---

## 4. Percept Packet and Ground Packet

**A derived, in-memory value assembled at the moment of asking. Not a document, not a collection, not
a stored artifact.** The rule it enforces: **nothing reaches a model without carrying the conditions
of its own asking, and nothing returns without being attachable to what was asked.**

```
PerceptPacket {
  act              isolate | relate | compare | challenge | return | transfer | ...
  expression       the curator's words
  scope            this part | this image | this kind | unbounded
  register         descriptive | interpretive | comparative | speculative
  grounds          [ GroundPacket ]
  manuscript       the passage this is being asked from
  constraints      external-claim rules, no_iconographic_identification, grain
  recall_state     did the evidence resolve at ask time?
  trace            prior runs on this post, this percept
  operation        the one allowed operation
}

GroundPacket {
  substrate        region | field | path | boundary | frame | composite | crop | interval
  role             anchor | threshold | pressure | counterforce | external limit | ...
  geometry         the evidence itself
  resolution       resolves | does not | suspect
  provenance       actor, detector, geometry_rev
}
```

### 4.1 The four rules that make a packet worth having

1. **It is inspectable before it is sent.** The rehearsal runner **refused an invalid manifest before
   spending budget**, twice, at zero cost. That ordering is the packet's whole value.
2. **It refuses to ask over dead evidence** — or asks *and marks the answer as resting on nothing*.
   A `return` act over a fully detached bundle is not a question; it is a category error.
3. **It carries the grain.** `compare` without a declared grain is the immunisation failure with a
   product's authority behind it.
4. **It is recorded with what came back.** The global semantic reading **has no id**
   (`semantic_pass.py:104`), which is why `enforce_candidate_ids` cannot reach it and why a live post
   holds a confident reading with `dropped_ids: ["1","2","1","2"]` and **0 assertions**. *A packet is
   the id that reading never had.*

**What a packet is not:** an agent, a queue, a plan, a place to put intelligence. It is a **packing
rule**, and its discipline is entirely in what it refuses.

---

## 5. UX implications

### 5.1 Differential as **Percept Workshop**

Not a viewer with drawing tools — **the place a noticing is made**. The shift: from *marking regions*
to *composing a reading*. Roles chosen as grounds enter the tray. Act type implied by the affordance
used. Scope asked **once**, at composition, in the curator's language (*"about this part" / "about
this image" / "about images like this"*) — never a dropdown of jargon.

**And the exit that does not exist: "write from this."**

### 5.2 Manuscript as **perceptual commitment surface**

Where a rehearsed noticing becomes a said one. **Writing about a percept is an act**, and the chip is
the trace of it. Two consequences: the chip should be able to say *what role* the percept plays in
*this* sentence (cited / interpreted / challenged); and **a percept written about is more committed
than one merely composed** — which is the distinction Codex would later read.

### 5.3 Atlas as **comparative percept field**

Percepts across images, arranged by what they claim rather than by which post they sit on. **Scope and
act type are what make the arrangement honest** — comparing an `isolate` with a `transfer` as though
they were the same kind of statement is how a comparative surface starts lying. **Evidence health is
one column, not the point.**

### 5.4 Codex as **percept biography**

Not a long-form editor. *What did I think, when, on what evidence, and what happened to it?* Its
subject is **the standing of a noticing over time** — composed, cited, challenged, narrowed, recalled
again. Its two preconditions do not exist: a citation durable outside its prose, and a record that
evidence was **destroyed** rather than merely absent.

### 5.5 Circulation Thread as **the visible relation chain**

The one piece of this addendum reachable soon. Nine relations, five records and four judgements, in
two visibly different voices. Degradation-only. **Never a cause.** An honest empty rung — `inferred —`
— is better than a hidden one, because it is how the product says what it cannot yet do.

---

## 6. What this addendum forbids

- **No field, schema, entity, collection, route or migration** is authorized by anything above.
- **Roles, acts, scope and register are candidate vocabularies**, not taxonomies. They must be
  usable before they are enumerable, and **retirable** — A6's device was retired after five cycles of
  gating; a vocabulary must be as retirable as an instrument.
- **No Liquid Construct becomes a classification.** A percept is never *tagged* `address`; it may be
  *read through* address, labelled candidate, with its scope attached.
- **No percept biography is stored.** Derivable, or not at all.
- **A model may never author `challenge`.**
- **None of this is a precondition for P1A.** P1A hardens the recall hop. This document exists so
  that hardening is understood as **strengthening one artery of a circulatory system**, not as
  finishing a validation feature.
