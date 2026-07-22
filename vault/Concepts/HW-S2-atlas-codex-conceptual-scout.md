# HW-S2 — Atlas / Codex conceptual scout

**READ-ONLY CONCEPTUAL SCOUT. Research-only. This document proposes no implementation, no schema,
no field list, no route, and no collection. It designs nothing. It reads what the vault's prose
aspires to, what the code actually has, and what the rehearsal evidence actually supports, and
reports where those three disagree.** Nothing here is a candidate or a decision. No source file was
edited, no database was touched, nothing was committed.

---

## 0. Where each word currently stands

A blunt inventory before any interpretation. "Code" means: it exists as something the running
system stores or executes.

| Term | Prose says | Code has | Evidence status |
|---|---|---|---|
| **Percept** | the object that crosses the image boundary | two *different* things: `pctx_…` **expression** percepts persisted in `post.percepts` (7 corpus-wide), and `pct_…` **attention** percepts that are a frontend composition, "NOT a DB table" | 1 of 7 is **fully unevidenced** (A2S) |
| **Ground** | how visual evidence occupies the image | real: `frontend/src/differential/grounds.js`, persisted as `post.grounds`, 7 types | the load-bearing split is **reference-based vs geometry-bearing** (A2S) |
| **Mention** | the join between a percept and a textual location | **no durable form** — `data-percept-id` / `data-region-ids` attributes inside `text_blocks` HTML, rebuilt by `mentionsFromBlocks()` | rendered-verified once (R2.0), unsaved; 0 saved mentions existed before that probe |
| **trace** | two unrelated senses: the *interaction verb* (brush/trace a boundary) and the *rehearsal trace* (append-only event record) | rehearsal `trace.json` files under `rehearsals/runs/`; separately `vision_runs` + embedded stage events in production | Passage-001's trace is **100 % reconstructed** with null telemetry throughout |
| **Passage** | a unit of grounded writing; also the name of the research program's run #0 | only the English word in LLM prompt strings (`editor_llm_service.py`, `PostDetailPage.jsx`) | R0: "no inquiry/history object exists at all — so a Passage/Inquiry has nothing to extend" |
| **Atlas** | a Warburg-style cross-image arrangement canvas | **nothing.** All three code hits are false friends: *MongoDB* Atlas (`database.py`), "Atlas Vector Search" (`region_embedding_service.py`), and "P0.5 Contract Atlas" as a doc name (`vision_run_contracts.py`) | untested by any rehearsal |
| **Codex** | the long-form multi-page work | **zero code hits anywhere** (R0's own finding, re-verified) | untested by any rehearsal |

Cited: `vault/Build/Architecture Lab/Vision pipeline/rehearsals/R0/R0-reality-map.md`,
`frontend/src/differential/grounds.js`, `backend/database.py`.

R0 already classified these honestly — Atlas **theoretical**, Codex **absent** — and that
classification has not changed since. Two whole programs have completed and neither of them touched
Atlas or Codex. That is itself the most important datum in this report: the two most elaborated
concepts in the vault are the two with the least evidence behind them.

---

## 1. What ATLAS seems to want to be now

### What the prose aspires to

The prose is consistent and old. `vault/Concepts/ChatGPT goldmine/Atlas and Codex idea.md` calls
Atlas "where the story is arranged before it is written" — a canvas of beat / character / motif /
tension / percept nodes with typed edges, whose central claim is that **"the arrangement is the
prompt."** `Findings/responses/narrative-atlas-vision.findings.md` supplies the lineage (Warburg's
*Bilderatlas Mnemosyne*) and the node/edge vocabulary. `Plans/differential-atlas-codex-bridge.md`
supplies the sharpest single sentence in the whole Atlas corpus:

> "The image boundary is the cut, and the Percept is the only object that crosses it."

That bridge doc is genuinely good work: it establishes that Grounds are indexical and stay local,
that Constellation/Relation are Grounds and must **not** be promoted, and that a Motif is a new
object born on the far side of the cut. It also names the trigger for hardening: "the first time a
Percept is cited outside its own image … it hardens."

### What the recent evidence does to that

The evidence does not refute Atlas. It attacks its **precondition** from two directions.

**(a) The only object that crosses is the one whose evidence rots silently.** A2S
(`rehearsals/R2/A2S-detached-ground-sweep.md`) found that 4 of 11 reference-based grounds in the
corpus are detached, 0 of 15 geometry-bearing ones are, and one percept — `pctx_mrqp950d_0`, "the
upper head" — is **fully unevidenced**, 2/2 grounds detached, with the curator never told. This is
precisely the object the bridge doc designates as the sole traveller.

The bridge doc anticipated degradation and got the shape of it wrong:

> "editing or deleting Grounds under a cited Percept degrades recall to whatever evidence remains …
> without touching the Percept's identity or its citations."

A2S shows *whatever remains* can be **nothing**, and that the percept still renders as a percept.
The prose imagines graceful diminishment; the evidence shows unannounced total loss. There is no
floor in the contract, and nothing announces the fall. An Atlas built on today's Percept would
therefore be a surface whose nodes can each become empty citations without a single event
occurring anywhere in the system.

**(b) Warburg's Atlas was made of plates — and plates are the exact category A1 broke.**
A1 (`runs/002-figure-ground-reversal/sparks.md`, spark-01) found a determinate, evidence-backed
claim — the interval between five cut-out heads is *separating specimens for typological
comparison* — with nowhere to live, because "every Ground type points into the depicted image
plane." A1F (`runs/002F-single-object-followup/score.md`) narrowed this correctly: on a real
photograph the finding vanishes (0.0 % pure black everywhere tested, vs 59.5 % in A1's interval),
so the split is **reproduction-specific**, not general.

But the narrowing does not soften the point for Atlas — it sharpens it. An Atlas is a surface for
arranging *plates*: comparative composites, catalogue scans, cropped details. That is the one
source class where the system currently cannot distinguish a claim about the artwork from a claim
about the reproduction, and where forcing an artifact-level claim into a picture-level Ground makes
it **false** rather than merely imprecise.

### So what does Atlas want to be now?

Read against the evidence, Atlas's centre of gravity has shifted from **narrative arrangement** to
**comparative honesty across images**. Three sub-shifts:

1. **From authoritative structure to derived view.** The Infrastructure Lexicon already contains the
   right word: "An Atlas constellation or Percept-usage summary could be a **materialized view**
   rather than the authoritative source" (`vault/Concepts/ChatGPT goldmine/rehearsal phase/The
   Semant Infrastructure Lexicon.md` §3). The bridge doc independently reaches the same place for
   Codex recurrence ("a query over Mentions, not a stored object"). The evidence supports pushing
   this further than the prose does: an arrangement over objects whose evidence can silently vanish
   should not be the place where truth is stored.
2. **From "the arrangement is the prompt" to "the arrangement is a claim that must answer for its
   evidence."** The generative framing is untested by any rehearsal. What *has* been tested is that
   a percept's citation can outlive its grounding. An Atlas whose nodes cannot say "my evidence is
   intact / degraded / gone" would industrialise that failure across images.
3. **From graph-of-story to surface-that-knows-what-kind-of-picture-it-is-holding.** A1/A1F make
   this specific to reproductions, and only at n=1 + one control. It is not a licence to build
   anything — it is a reason the Atlas cannot be specified yet.

**Honest caveat:** none of the above is evidence *for* Atlas. No rehearsal in R0–R2 tested a
cross-image surface at all. The evidence tells us what an Atlas would have to survive; it says
nothing about whether one is needed.

---

## 2. What CODEX seems to want to be now

### What the prose aspires to

Codex is "the book" — a Work of ordered/linked Pages, each a BlockNote document, with cross-page
percept citation, backlinks, motif and character views ("closer to Scrivener + Obsidian + Semant's
percept architecture"). `Findings/responses/atlas-codex-build-plan.findings.md` even sequences it:
Phase 0 Codex-lite, "the one backend step: promote `Percept`."

The deeper aspiration is elsewhere, and is better. In
`vault/Concepts/ChatGPT goldmine/rehearsal phase/semant-rehearsal-aspiration.md`:

> "Much later, Codex may notice that something introduced as a visual detail has become an
> architectonic principle of the writing."

That is not Scrivener. That is **duration** — the layer at which a percept's meaning is observed to
change across a long work while remaining answerable to what was seen.

### What the recent evidence does to that

**(a) Codex's substrate was only just proven to exist, once, unsaved.** R0 recorded the whole
percept → chip → recall loop as "production-real but UNEXERCISED — 0 percept mentions in any post."
R2.0 (`rehearsals/R2/R2.0-rendered-probe-report.md`) closed that: the slash menu, RefPicker, chip,
the `data-percept-id` / `data-region-ids` / `data-mention-id` attributes, and the recall animation
over the correct two heads were all observed in a real browser against real Mongo — at Level A,
**discarded without saving**. That is a genuine pass and it is the strongest positive evidence
Codex has. It is also n=1, one percept, one post, unsaved.

**(b) The Mention is not durable.** R0: "no backend table; only `data-*` attrs in `text_blocks`
HTML, rebuilt by `mentionsFromBlocks()`." Every Codex claim in the prose — cross-chapter citation,
backlink views, "which chapters embody restraint → release" — is a **query over Mentions**, per the
bridge doc's own reasoning. Those queries have no substrate. The prose treats this as a small
gap ("the Mention join already does many-to-many; it just gains a `page_id`"). It is not small: the
join currently lives in serialized editor markup.

**(c) Duration is exactly what the corpus cannot currently narrate.** A2's critique records that the
re-dissect which stranded `fine_0`/`fine_3` is *inferred, not observed* — "there are 0 `vision_runs`
for this post; the history is not recoverable." The circulation spine now records `vision_runs` for
four operations going forward, but the past is gone. Codex's most interesting claim — that it could
notice a detail becoming a principle — presumes a recoverable history that, for the existing
corpus, does not exist.

### So what does Codex want to be now?

Codex's animating idea has moved from **long-form container** to **the layer at which change over
time is answerable**. The multi-page editor is the least interesting part of it and the most easily
imitated (`Atlas and Codex idea.md` says as much about generic implementations: "draw boxes,
connect them, serialize graph, ask LLM to write" would be "easy to imitate").

What the evidence supports saying about Codex is narrow and negative: **its only load-bearing
dependency — a citation that survives — is currently the thing demonstrated to be fragile.** A
Codex built on today's Mention would be a book whose footnotes are stored in the typography of its
own pages, pointing at percepts that can quietly lose their evidence.

---

## 3. What should remain ONLY prose / research for now

Everything in this list, and the reason in each case is a *specific* evidential deficit, not
caution in general.

- **Atlas, entire.** Zero rehearsals tested a cross-image surface. `R1-R2-recommendation.md` states
  the prohibition in the program's own words: "**No** Atlas, Codex, or cross-image structure."
  Nothing since has changed that.
- **Codex, entire.** Same prohibition; plus its substrate (durable Mention) has one unsaved
  rendered observation behind it.
- **The artifact/depiction distinction.** A1's own critique lists it as finding #3 — "the strongest
  finding was not what A1 set out to test … partly an accident of fixture choice." A1F then narrowed
  it to reproductions. A1's spark-01 leaves the locus explicitly open: "Is the artifact/depiction
  distinction a Ground *type*, a Ground *attribute*, or something that belongs on the image record
  rather than on Grounds at all? A1 cannot tell." A distinction whose *location* is unknown cannot
  be built.
- **Out-of-domain detection.** spark-04 states its own limit: "One fixture. This names the
  distinction; it does not license machinery." Its next test — the same probes on a fixture the
  architecture segmenter is in-domain for — has not been run.
- **Any repair for detached grounds.** A2S refuses to design one and records why: "Whether old
  regions should persist as tombstones so grounds resolve to *something*, versus notifying and
  letting the curator re-point, is an open design question with real trade-offs."
- **Interval / negative-space proposal.** spark-02 was overstated and was corrected by A1F:
  detection proposes *things* (figures **and** surfaces — `arch_0 "wall"`, `arch_1 "floor"`), just
  never *intervals*. The corrected claim is narrower than the one that would have justified work.
- **Passage / Inquiry as an entity.** R0: "no inquiry/history object exists at all … it would be
  genuinely new. Its necessity is unproven and must come from rehearsal failure." Passage-001's own
  `missing-telemetry.md` concludes it "can validate the schemas and anchor the trace grammar, but it
  can **support no construct beyond SPARK**."
- **Contextual role / embodiment on the Mention.** R0 poses it as the open question — whether Mention
  can absorb role, active-Grounds set, recall pose and epistemic distance, versus a new object —
  and explicitly assigns the answer to R2/R3, not to R0.
- **Agent skills.** Reserved to R6 by the program's own sequencing.

The general principle is already written down in the Lexicon and should be quoted at anyone in a
hurry: *"A schema is not the same as a concept. A beautiful idea does not deserve a schema until
persistence is necessary."*

---

## 4. What the rehearsal evidence is HINTING at — plain language only

No schemas, no fields, no routes, no collections. These are described as *jobs somebody might one
day need done*, not as things to build. Several may turn out to be behaviours of existing parts
rather than new parts at all — which is the point of not naming them yet.

1. **Something that notices when evidence stops being evidence, and says so.** A2S's clearest
   statement: "Detachment is already *modelled* … and already *rendered* … The gap is that nothing
   **announces** it at the moment it happens, and nothing accumulates it." spark-03 stresses this
   "needs no new entity, no new schema, and no ontology change" — the information already exists at
   the moment a re-dissect runs. The hint is toward a *noticing*, not a *thing*.

2. **Something that remembers a piece of evidence used to exist.** The Lexicon already has the
   vocabulary — tombstone, referential integrity ("If a Region is removed, a Ground must not
   silently point nowhere") — and A2S has the observation. But A2S deliberately leaves open whether
   the answer is remembering or notifying. Recorded as a hint with the fork intact.

3. **Something that knows what kind of picture it is holding.** From A1/A1F: a made comparative
   plate and a photograph of a sculpture in its chapel afford different claims. Note that A2's
   manifest already records `reproduction_vs_depiction: depiction` **as a rehearsal manifest field,
   in the research layer only** — which is exactly where a distinction with n=1 evidence belongs.

4. **Something that can tell "this channel is out of its depth" from "these two channels disagree."**
   spark-04. Its nearest existing home is already named by the spark itself: a VisionRun already
   records `capability` and `actual_source`, "so an out-of-domain flag would have somewhere honest
   to live." Notably this hint points at an *existing* structure, not a new one.

5. **Something that makes a citation durable outside the prose it sits in.** R0's finding that the
   Mention exists only as HTML attributes. This is the one hint that both Atlas and Codex depend on,
   and the one with the least rehearsal evidence behind it — R2.0 verified the loop *works*, not
   that the join *survives*.

6. **Something that can say why a re-dissect was allowed to destroy what other things depended on.**
   A2's critique: "the re-dissect story is inferred, not observed." Circulation spine now records
   the four instrumented operations, so this hint is partly already being answered going forward —
   but only for `dissect`, `refine`, `semantic_read`, `find_similar`, and only from now on.

---

## 5. What would be DANGEROUS to prematurely crystallize

Nine specific commitments the current evidence does **not** support, and the damage each would do.

**1. Promoting Percept to a durable backend entity now.**
`atlas-codex-build-plan.findings.md` proposes exactly this as Phase 0's "one backend step," and the
bridge doc names the trigger ("the first time a Percept is cited outside its own image … it
hardens"). This directly contradicts `R1-R2-recommendation.md` ("**No** production entity/schema
(Passage, Inquiry, Discovery, Embodiment, Candidate, Field, context-memory)"). The evidence sides
with the prohibition: there are **7 percepts corpus-wide, 1 of them fully unevidenced**. Hardening
an object at n=7 — when the known failure mode is that its evidence disappears without notice —
would make silent unevidencedness *portable and citable across works*. The damage is not a bad
schema; it is that the false thing gets a stable identity and starts propagating. Worse, the
promotion would inherit an unresolved identity collision the Lexicon already flags: `pct_…`
attention percepts and `pctx_…` expression percepts are "a conceptual collision even if prefixes
distinguish them technically." Promoting before resolving it hardens the collision.

**2. Committing to the Atlas node/edge vocabulary.**
`precedes`, `causes`, `contrasts_with`, `echoes`, `tension_with`, `intensifies`, `releases`,
`part_of` — plus beat / character / motif / tension node types. Every one of these was invented in
prose and none has been tested against a fixture. Damage: a typed-edge vocabulary is a claim about
what relations exist in the world, and once prose is written into it the vocabulary becomes
self-confirming — you can only arrange what the edges permit, so the arrangement never falsifies the
edge set. The rehearsal program exists precisely to invert this ("Architecture no longer possesses
the exclusive right to decide in advance what perception can become",
`semant-rehearsal-aspiration.md`). Freezing the edge set is the reversal running backwards.

**3. Making Atlas the authoritative store of arrangement.**
Damage: the bridge doc's own discipline collapses. It correctly resists materialising Codex
recurrence ("Resist the urge to materialize a recurrence record; the join already carries it") —
the same resistance is owed to the Atlas graph. An authoritative arrangement over percepts that can
silently lose their grounds becomes a map that is confidently wrong and has no way to learn it.

**4. Adding an artifact/depiction marker to Ground (or to anything in production).**
A1 cannot tell whether it belongs on a Ground type, a Ground attribute, or the image record; A1F
narrowed the claim to reproductions. Damage is twofold: (i) putting it on the wrong object is
expensive to undo once real annotations depend on it; (ii) any per-image marker becomes a question
every ingestion must answer, and for most images nobody can answer it honestly — producing a field
full of confident defaults, which is worse than the current honest silence.

**5. Auto-repairing or auto-tombstoning detached grounds.**
Damage from tombstones: a percept keeps resolving to geometry the curator's own re-dissect
*replaced* — the system would launder superseded evidence as live, which is a deeper dishonesty
than the current visible detachment. Damage from auto-repair (re-pointing to the nearest new
region): it fabricates curator intent, silently. A2S is explicit that this fork is unresolved, and
the current behaviour — degrade honestly, render as "detached evidence" — is at least not lying.

**6. Preferring geometry-bearing Grounds over the region adapter because they survived.**
The numbers are seductive: 0/15 geometry-bearing detached vs 4/11 reference-based. A2S refuses the
inference in advance: "the region adapter's reference semantics ('geometry stays on the Region') are
deliberate, and **durability is only one axis**." Damage: duplicating geometry into Grounds to make
them survive would break the canonical-representation invariant the whole evidence plane rests on
(`mask_rle = canonical`, everything else a projection), trading a visible failure for an invisible
divergence between two copies of the same boundary.

**7. Quoting 36.4 % as a corpus property.**
A2S pre-empts this too: "with n = 11 the percentage should not be quoted as a corpus property. It
says 'this happens repeatedly', not 'this happens 36 % of the time'." Damage: a fabricated
baseline. Any later "we reduced detachment from 36 % to 8 %" would be measuring noise, and would be
used to justify whichever repair was built.

**8. Building an uncertainty / disagreement UI on the A2 finding.**
spark-04 states the damage itself, and it is the sharpest sentence in the R2 corpus: "an uncertainty
UI that offers the curator a choice between a competent reading and a confident non-answer teaches
them to distrust the wrong channel." A2's own critique adds that A2 "did not really test what R5 was
designed to test" — one channel was out of domain, not two channels disagreeing. Building
disagreement machinery on a fixture that contained no disagreement would encode the category error
into the interface.

**9. Generalising the circulation spine into a causal history of everything.**
The P2.2 contract deliberately forbids exactly this: "Each operation is a standalone block — never a
step in one invented chain, never a causal arrow … Shared region ids read as 'Referenced …', never
'caused by'/'followed from'", with an explicit scope statement that only four operations are
recorded. Damage: the rail's honesty is its whole value; a rail that implies a causal chain it never
observed becomes a machine for manufacturing plausible provenance — the precise failure the
Lexicon's *auditability* and *provenance* entries exist to prevent. Note also that R2.0's rendered
verification and the spine's telemetry cover **future** operations only; the existing corpus's
history remains unrecoverable, and no surface should pretend otherwise.

---

## 6. Where the prose and the evidence disagree — summary

| The prose says | The evidence says |
|---|---|
| Bridge: a Percept "survives being carried into a chapter … even diminished" | A2S: it survives while its evidence is **entirely gone**, and nothing announces it |
| Bridge: grounds degrade "to whatever evidence remains" | A2S: "whatever remains" can be **zero**, and the percept still renders |
| Build plan: promote Percept as Codex-lite's one backend step | R1→R2: no production entity, no Atlas, no Codex |
| A1 spark-02: proposal machinery is "object-shaped end to end" | A1F: detection proposes **things incl. surfaces** (`wall`, `floor`); it never proposes **intervals** |
| A1 spark-01: the artifact/depiction split is general | A1F: **reproduction-specific**; no category gap on a real photograph |
| R5 family framing: "sensory disagreement" | A2: one channel **out of domain**, which is not disagreement |
| Atlas idea doc: Mention is already a join that "just gains a `page_id`" | R0: the Mention has **no durable form** at all |

---

## 7. One line

Atlas and Codex remain the vault's most developed prose and its least evidenced structures; what the
two completed programs actually established is that **the single object both of them depend on — a
Percept whose citation outlives its image — can currently lose all its evidence without anyone being
told**, and that is the finding that should govern what happens next, not the arrangement canvas.
