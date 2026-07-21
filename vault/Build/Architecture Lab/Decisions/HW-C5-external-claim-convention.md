# HW-C5 — Should R2 adopt a convention for recording external claims verbatim?

**DECISION DOC — no implementation authorized, rehearsal-artifact convention only, no production
entity.**
Nothing in this document authorizes a source file, schema file, route, migration, Mongo collection,
Ground type, Percept field, Atlas object or agent skill. No model calls were made. No production
document was read or written. Nothing was staged, committed or pushed. Vault documents and the two
rehearsal schemas were **read only**.

| | |
|---|---|
| **id** | HW-C5 · arises from **spark-08** (`R2/CANDIDATE-REGISTER.md` §spark-08) |
| **date** | 2026-07-21 |
| **status** | **Proposed** — awaiting the orchestrator's acceptance. Until accepted, A6 and the `695be843` A/B are not blocked by it and may proceed without it. |
| **decision, in one line** | **Adopt now, in reduced form: a markdown-only `## External claims` ledger in `score.md`, recording frame-settleability and never truth. No schema change to either score schema.** |
| **scope** | rehearsal trace/report practice only — how a run's own markdown records what a model said |
| **supersedes** | nothing |
| **rests on** | **one run** (A5 / `runs/006-narrative-overreach/`). Said plainly, and §6 says what would overturn it. |

---

## 1. The question, stated precisely

In A5 (`runs/006-narrative-overreach/`), asked only *"what is happening in this photograph?"*, the
model unprompted supplied a title (*"The Angel of Gethsemane"*), a sculptor (*Paul Manship*), a date
(*1921*), an institution (*Gethsemane Chapel, National Cathedral, Washington D.C.*) — and quoted a
scriptural inscription (*"THE LORD IS MY LIGHT AND MY SALVATION"*), writing that it *"confirm[s]"*
the religious context and location.

**The inscription is not in the photograph.** Verified from the pixels at 6× upscale
(`fixtures/006-narrative-overreach/_medallion-x6.png`): the medallion is a coloured figural mosaic
tondo with a fragmentary **non-English** band. The model manufactured documentary evidence and cited
it as confirmation of a location claim it had also supplied.

The question this doc answers is narrow:

> **Should R2 adopt, now, a standing convention for recording — verbatim, in a rehearsal's own
> artifacts — claims a model makes that the frame does not settle?**

It is **not** the question "should Semant have an external-citation entity." That question is
`spark-08`'s, it is at n=1, and this document does not touch it (§7).

### Why now rather than later

Four reasons, and one reason against which is answered in §2.

1. **The recording is lossy if deferred.** A5's four fabrications survive only because prose in
   `score.md` happened to narrate them. A6, the `695be843` A/B, and every later R2 run will produce
   the same behaviour or fail to — and if there is no place to put it, the *absence* of external
   claims in a later run will not be recorded at all. **A convention adopted after three more runs
   cannot retroactively record the three runs' negatives**, and negatives are exactly what spark-08's
   next test needs ("re-run stage 1 on two further monuments … if attribution appears each time,
   this is a standing behaviour").
2. **spark-08's own stated next move is this convention.** `sparks.md` and the register both say the
   honest first move is "a rehearsal convention that records, verbatim, whenever a model supplies a
   name, date, place or quotation that the frame does not contain." This doc is that move, made
   explicit and bounded, not an escalation of it.
3. **The failure was severe.** Not over-reading, but *importing* — the model presented outside-frame
   material as read off the image and reasoned from it. Every prior R2 run tested the milder failure.
4. **It is cheap.** A markdown table. No schema, no code, no lookup, no cost to a run that has
   nothing to record.

---

## 2. The decision

**Adopt now, in reduced form.**

- **Adopt**: a `## External claims` section in `score.md`, standing for all R2 instrumented runs from
  the next run onward.
- **Reduced**: markdown only. **No field is added to `instrumented-score.schema.json` and none to
  `virtual-rehearsal-score.schema.json`.** Cross-run comparability, where wanted, goes in the
  already-free `notes` string (§3.4).
- **Reduced**: the ledger records **whether the frame settles a claim**, never whether the claim is
  true (§4).

### Reasoning, including the argument against

The program's repeated and correct lesson is that **conventions adopted on n=1 tend to be wrong** —
A1's spark-01 was narrowed by A1F, A4's spark-06 narrowing was reverted by the A6 gate, the hydration
race was inferred by two independent scouts from code shape and dissolved by one measurement.
`HB-004` §4 states the moral: *inference from reading is not evidence*. That lesson is real and it
applies here. A5 is one image, one model, two calls, on a subject `critique.md` itself flags as
"close to the most projection-friendly subject available."

**The lesson does not reach this decision, and the reason is a distinction worth stating once
clearly:**

> The n=1 lesson bites on conventions that **model** the phenomenon — that assert a taxonomy, a
> mechanism, or a shape the world must have. It does not bite on conventions that merely **record**
> it. A wrong model propagates: everything downstream inherits its categories. A wrong recording
> convention produces, at worst, a table nobody uses — and it is discovered by the same runs that
> would have discovered the right one, because the raw text is frozen either way.

The four categories in the horizon brief are a **model**, and this doc deliberately declines to adopt
three of them as recorded values (§3.2, §4.1). What it adopts is the thinner thing that survives
being wrong: *the model said X; the frame does not settle X; here is X verbatim.*

Two further considerations decide it:

- **Asymmetric cost of the two errors.** Adopting and being wrong costs a heading and a sentence per
  run. Deferring and being right costs nothing; deferring and being wrong costs the negative results
  of every run between now and adoption — irrecoverable, because the *absence* of a behaviour is only
  evidence if you were looking for it.
- **The verbatim requirement is the point.** A5's finding survives paraphrase poorly. *"The model
  attributed the work"* is a summary; *"created by Paul Manship in 1921"* next to *"we cannot
  determine the sculptor or year from the image alone"*, both quoted, is the finding. Verbatim
  capture is what a recording convention is for, and it is the thing that decays fastest if left to
  each run's prose.

**Deferring is rejected.** Adopting the full four-category taxonomy is rejected (§4.1). Adopting a
schema field is rejected (§3.4).

---

## 3. The record shape

### 3.1 Where it lives

A section in `score.md`, at the end, before `## Provenance`:

```markdown
## External claims

The model supplied N claim(s) the frame does not settle. Recorded verbatim. This rehearsal
verifies none of them and asserts nothing about the subject's real identity.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
```

If a run produces none, the section still appears, as one line: **`## External claims — none. The
model made no claim the frame does not settle.`** The empty case is the whole point (§2).

### 3.2 The columns

| column | values | rule |
|---|---|---|
| **verbatim** | quoted model text, unedited | Never paraphrased. Elide with `…` only; never rewrite. |
| **kind** | `name` · `attribution` · `date` · `place` · `quotation` · `other` | Descriptive only; a bucket for scanning, carrying no claim. |
| **frame status** | `frame-silent` · `frame-contradicts` | Two values, not four. See below. |
| **evidence** | a file/crop ref, or `—` | **Required** when status is `frame-contradicts`. An unevidenced "the frame refutes this" is an assertion, not a check — the same rule `instrumented-score.schema.json` already applies to `production_mutation.evidence_ref`. |
| **speaker-flagged** | `yes` / `no` / `contradicted` | Did the model itself mark this as something the image cannot settle? `contradicted` = it flagged the limit *and* asserted the claim anyway (spark-07). |

**`frame status` has two values, deliberately.** The brief's categories 2 (*external-documentary,
true and sourced*) and 3 (*invented/unverified*) **cannot be told apart by a rehearsal** — separating
them requires the external lookup A5 correctly refused, and §4.3 forbids making that lookup a
precondition. Collapsing them into `frame-silent` is not a simplification; it is the honest record.
The rehearsal knows one thing about both: *the picture does not settle it.*

Category 4 is not a status but the **speaker-flagged** column, because A5 showed it is orthogonal —
the model flagged the limit *and* asserted the claim in the same response. A taxonomy that makes them
exclusive would have made A5's central contradiction unrecordable.

A **third** thing A5 produced does not fit the brief's four categories at all, and this is why
`frame-contradicts` exists: the inscription is **not an outside-frame claim**. It is a claim *about
what the frame contains*, which the frame **falsifies**. That is a strictly worse failure than an
unverifiable attribution, and it is the only cell in the ledger a rehearsal can settle on its own
authority — from pixels.

### 3.3 Worked example — A5's four fabrications

```markdown
## External claims

The model supplied 4 claims the frame does not settle. Recorded verbatim. This rehearsal verifies
none of them and asserts nothing about what the monument actually is.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "the famous marble sculpture *\"The Angel of Gethsemane\"*" | name | `frame-silent` | — | no |
| 2 | "created by **Paul Manship**" | attribution | `frame-silent` | — | **contradicted** — same response: *"No signature or plaque is visible in the frame, so we cannot determine the sculptor or year from the image alone."* |
| 3 | "in **1921**" | date | `frame-silent` | — | **contradicted** — same sentence as #2 |
| 4 | "**Inscription visible in background** … part of an inscription reads *\"…THE LORD IS MY LIGHT AND MY SALVATION…\"* — confirming the religious context and location" | quotation | **`frame-contradicts`** | `fixtures/006-narrative-overreach/_medallion-x6.png` — 6× LANCZOS upscale, `x ∈ [0.32,0.72]`, `y ∈ [0,0.13]`; resolves as a coloured figural mosaic tondo with a fragmentary **non-English** band. The quoted English phrase does not appear in the frame. | no |

*(The institution — "Gethsemane Chapel at the National Cathedral in Washington, D.C." — is recorded
under #1 as part of the same attribution cluster rather than split, since the model supplied it as
one identification. Splitting or clustering is the run's call; the verbatim text must be complete
either way.)*

**Not recorded here:** what the monument actually is. The rehearsal performed no external lookup and
makes no claim. Whether #1–#3 are confabulated or real-but-misapplied is `sparks.md`
unresolved-question 1.
```

Note what the worked example does **not** produce: any statement that the model was wrong about #1–#3.
Only #4 is settled, and only because someone looked at pixels.

### 3.4 Why not a schema field — stated plainly

`instrumented-score.schema.json` sets **`additionalProperties: false`**. Adding
`external_claims` — or even an `external_claim_count` integer — is therefore a **real schema change**,
and its costs are:

- Every existing instrumented score in the tree must remain valid, so the field must be optional —
  which means a `0` and an absent field are indistinguishable, destroying the exact negative-evidence
  property that motivated adopting now (§2).
- A schema is the program's most durable artifact. Putting a taxonomy there at n=1 is precisely the
  move the n=1 lesson forbids, and it is the shape most likely to be mistaken later for a
  product-side commitment — spark-08 explicitly declines to conclude that Semant needs an
  external-citation entity.
- Schemas index **cross-run bones** by their own descriptions ("prose stays in `score.md`"). A
  verbatim quotation is prose. It belongs in `score.md` by the existing division of labour.

**Where a count may go if wanted:** `notes`, which is already `["string", "null"]` and free-form —
e.g. `"external claims: 4 (1 frame-contradicts)"`. That is not a schema change and needs no
authorization. **Do not add it as a required practice**; it is permitted, not mandated.

Reconsider a schema field only after §6's threshold is met.

---

## 4. What the convention must NOT do

**4.1 It must not adjudicate truth.** A rehearsal cannot verify a catalogue fact and must not try.
`frame-silent` means *the picture does not settle this* — nothing more. It is not "false", not
"suspect", not "unsourced" as an accusation. This is why the brief's category 2 vs 3 split is
refused: adopting it would require every run to decide which, and every run would either guess or
look it up.

**4.2 It must not accuse the model of lying.** The word *confabulated* stays where `critique.md`
already put it — as a labelled **inference**, in prose, with the honest note that distinguishing
invention from misapplication needs a lookup that was not done. The ledger uses no intent language.
A5's `source-notes.md` §Honesty notes is the standard.

**4.3 It must not require external lookup as a precondition for running a rehearsal.** No run may be
blocked, delayed, or scored down for not verifying a claim. `frame-silent` with `evidence: —` is a
complete, correct, finished row. A run **may** optionally look something up and say so; it must never
be obliged to. Making lookup a precondition would import a research dependency into every rehearsal
and would, on its own, be a reason to reject this convention entirely.

**4.4 It must not become a production entity by the back door.** No Ground type, no Percept field, no
`external_ground`, no `citation` object, no route, no collection. If a later cycle proposes any of
those, it must argue from evidence, not from "the ledger already has this shape." **The ledger's
shape is not a design proposal and must not be cited as one.** Explicitly: the columns in §3.2 were
chosen to be *recordable*, not to be *modellable*, and they are wrong as a data model on purpose —
`frame-silent` merges two things a product would need to distinguish.

**4.5 It must not grow.** No scores, no severity, no per-claim rating, no aggregate rate across runs
("4 of 11" style rates are what spark-03's register entry warns against on a corpus this size). Six
columns, two statuses. Any addition is a new decision.

---

## 5. Interaction with existing fields — is this already covered?

**Partly, and the uncovered part is the reason to adopt.**

| existing | what it covers | does it cover this? |
|---|---|---|
| **`source_pressures`** (`virtual` schema, `$defs/source_pressure`, `use: "pressure_not_authority"`) | Texts the *curator/rehearsal* brought in, with `source_ref`, `locator`, `paraphrase`, optional `brief_quote` — recorded as pressure, never as authority. | **No — and it is the closest miss.** It is the right *ethic* pointed the wrong way. `source_pressure` records what **we** imported, knowingly, with a locator. The A5 case is what the **model** imported, unbidden, with no locator and no source. It is also `virtual`-only; A5 was instrumented. **Do not extend `source_pressures` to cover it** — collapsing a deliberate curatorial citation and an unbidden model assertion into one field would lose the distinction that matters. |
| **`resistances`** (`$defs/resistance`, kinds incl. `insufficient_evidence`, `analogy_overreach`, `source_conflict`) | Where the rehearsal **refused** to go, and the consequence. | **No.** A resistance is *our* refusal. A5's problem is a claim that was **not** refused — asserted freely and then treated as evidence. `virtual`-only again. |
| **`harvest.withheld`** | Claims the rehearsal declines to make. A5 used it correctly: *"Any claim about what this monument actually is."* | **Partly, and it is the mirror.** `withheld` records our silence about the truth; the ledger records the model's speech. They are complementary and both should stand — the ledger's preamble ("verifies none of them") is exactly a `withheld` entry restated at the point of use. |
| **`harvest.unresolved_questions`** | Open questions, e.g. A5's *"Is the attribution confabulated or retrieved-and-misapplied?"* | **No, but it is where the un-adjudicable half goes.** The ledger records the claim; `unresolved_questions` records what we cannot settle about it. Unchanged. |
| **`instrumented-score.json`** | Execution truth: calls, latency, replay proof, mutation. | **No.** It has no field for model content at all, by design. |
| **the frozen raw observations** | The verbatim text *is* already on disk. | **This is the strongest "already covered" objection, and it is half right.** Nothing is lost — the text exists. What does not exist is any *index* of it: no way to ask "in which runs did the model import outside-frame material, and in which did it not," short of re-reading every observation. A ledger is an index over material we already keep, which is also why it is cheap and why being wrong about it is recoverable. |

**Net:** nothing existing covers it, one thing (`source_pressures`) covers its inverse and should not
be stretched, and one thing (frozen observations) makes the ledger an index rather than a new record.

---

## 6. Reversibility, and what would overturn this

**Reversibility: total.** The convention is a markdown heading. Reverting it means deleting a section
from N `score.md` files and this doc's status line. No schema validates it, no code reads it, no
production artifact depends on it, no earlier run must be backfilled (**and none should be** —
retrofitting A5's ledger into `006/score.md` is *not* authorized by this doc; §3.3's worked example
lives here, in this decision, precisely so that the run's own artifacts stay as they were written).

**What would overturn it:**

1. **Three consecutive runs with empty ledgers** on subjects of recognisable type. That would make
   A5 an accident of one famous pose — `critique.md` §3 already flags this as live — and the
   convention becomes ceremony. Response: drop it, and record in the register that spark-08 did not
   replicate. *(Note: the three empty ledgers would themselves be the evidence that killed it. This
   is the self-correcting property claimed in §2.)*
2. **Any run where filling the ledger required an external lookup to proceed.** That would mean §4.3
   is unenforceable in practice, and the convention should be withdrawn rather than patched.
3. **Ambiguity in `frame-contradicts` in practice** — i.e. a run where whether the frame refutes a
   claim is itself arguable. A5's case was settled by a 6× crop and was not arguable. If it becomes
   arguable, the status collapses to a single `frame-silent` value and the falsification goes in
   prose.
4. **The ledger being cited as a design proposal** (a violation of §4.4) would be grounds to withdraw
   it even if it were otherwise working.

**What would strengthen it toward a schema field:** ≥3 runs with non-empty ledgers **plus** at least
one non-empty ledger on an ordinary photograph (not a recognisable monument type) **plus** a
demonstrated cross-run question that the prose ledgers cannot answer. All three. Until then, §3.4
stands.

---

## 7. What this does NOT authorize

- **No production entity.** No `ExternalGround`, no citation object, no `Percept.source`, no route,
  no Mongo collection, no migration, no frontend surface, no agent skill.
- **No schema change.** Neither `instrumented-score.schema.json` nor
  `virtual-rehearsal-score.schema.json` is modified. `source_pressures` is not extended.
- **No graduation.** spark-08 remains a **SPARK at n=1**. This convention is not evidence for it; it
  is the instrument that might produce evidence for it. Graduation still requires ≥3 fixtures plus
  transfer and negative tests, per the register.
- **No claim about the A5 monument.** Sculptor, date, cemetery, city and inscription remain
  unasserted. This doc quotes the model's claims; it endorses none.
- **No backfill.** Runs 001–006 are not amended.
- **No change to prompts.** The ledger records what a model volunteers; it must not be used to
  justify *asking* a model to identify, attribute or date a work. A5 ran with
  `no_iconographic_identification: true` and that stays.
- **No blocking of A6 or the `695be843` A/B.** `HB-004` §10 sets the next execution order and this
  doc does not change it. If accepted before the next run, the next run applies it; if not, it does
  not.
- **No commit.** This lane wrote one file and nothing else.

---

## 8. Honest summary

This decision rests on **one run, one image, one model, two calls**, on a subject chosen to be
maximally projection-friendly. It would be indefensible as a data model. It is defensible as a
recording convention because a recording convention that turns out to be unnecessary costs one
heading per run, while the evidence that would show it unnecessary can only be gathered by having
adopted it.
