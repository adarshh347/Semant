# Foundry Score — FS-002-textual-dynamism

**Sandbox:** FS-002-textual-dynamism · **Axis:** textual-dynamism · **Mode:** foundry · **RESEARCH-ONLY**

**Research question.** Can text act as a live force, not just prompt context?

> Zero live model calls. No book was opened, ingested, or quoted at length. Sources appear here only
> as **theme names and locators**, per the protocol's "source pressure, never source authority".

---

## 1. What was actually done

A zero-call pass over every rehearsal manifest, the two imaginative runs' recorded source pressures,
and the R2 register's two vocabulary findings. The bounded task: determine, from the frozen record,
**when a textual slice changed what was visible** and **when it merely ventriloquized the model**.

The task completed, but inverted: the record cannot separate those two cases, for a structural
reason given in E1.

## 2. Evidence

**E1 — Every instrumented run declares a source condition it does not have.** Tallying
`source_condition` and `seed_constellation.texts` across all 13 run manifests:

| run | mode | source_condition | texts supplied |
|---|---|---|---:|
| 000-passage-001 | imaginative | `present` | **1** |
| 001-eyes-of-stone | imaginative | `present` | **1** |
| 002, 002F, 003, 004, 005, 006 | instrumented | `present` | **0** |
| 007, 008, 009, 010, 011 | instrumented | `present` | **0** |

**11 of 13 runs declare `source_condition: "present"` while supplying zero texts.** Run 002's own
`source-notes.md` states it plainly under a heading: *"No text source"* — while its manifest says
`present`. The two are in direct contradiction, and the manifest is the machine-readable one.

**E2 — The enum has four values and only one has ever been used.** `source_condition` accepts
`present | absent | replaced | misleading` (`rehearsal-manifest.schema.json`). `absent`, `replaced`
and `misleading` have **never been set in any run**. Those three are precisely the doctrine's
prescribed remedy for source ventriloquism: *"run without the source, with a counter-source, and on
material that resists it"* (`01-doctrine.md`; `12-failure-and-safety.md`).

**E2b — The field's meaning is defined, and it is the literal one.** `R1/R1-schema-decisions.md`:
*"`source_condition` (present|absent|replaced|misleading) — so a run records **whether the source was
there, removed, swapped, or misleading**"*. This was checked because the critique raised the
alternative reading (that `present` might mean "no adversarial manipulation applied"); **that reading
is refuted.** E1's contradiction is real.

**E2c — The absence was, in part, deliberate.** `R2-batch-operating-plan.md` records A3's lens as
*"choreography — **not** Merleau-Ponty; avoid source ventriloquism"*. At least one run removed a
philosophical source **on purpose**, to avoid the failure mode. The absence of texts is therefore not
simple neglect.

**E2d — The only run ever designed with a manipulated source was retired.** The same plan assigns
**`source_condition: misleading` to A6 alone** — the single adversarial source run in the program.
A6 was **RETIRED** (HB-010 §3) because the agreement ceiling made its *attribution* measurement
impossible. The retirement was correct on its own terms and is not reopened here; but it removed the
program's only designed source-manipulation run **as collateral**, and no document records that
loss under this heading.

**E3 — Text demonstrably changed what the model saw — but the text was the question, not a source.**
Two findings, both strong, both about single words in a prompt:

- **spark-06 (RESOLVED).** Byte-identical 768 px stimulus, same model, same call shape, both arms
  stateless. Address-framed → *"glowing eyes"*, *"face-like frontality"*. Structure-framed →
  *"light fixtures"*, *"mirrored placement"*. **The same lamps.** *"The face is not in the
  photograph; it is in the question."*
- **spark-09.** A 2×2 with exactly one filled corner on held-constant stimulus. The noun *motif*
  moves the model into purpose-and-atmosphere talk **per image**; the relational demand licenses the
  **joint** predication. Neither ingredient is sufficient alone.

**E4 — The only recorded source pressures are imaginative and correctly disciplined.**
`runs/001-eyes-of-stone/virtual-score.json` carries four `source_pressures`, each with a
`source_ref`, a `locator` (e.g. *Touching the World*, *The Significance of the Shadow*, *Materiality
and Time*) and a **`paraphrase`** — no quotation, no page-length ingestion. Run 001 is
`mode: imaginative`, and its images have no post, Region, Ground or Percept ids.

**E5 — Present in the vault; absent from the instrument.** Merleau-Ponty, Pallasmaa and Bachelard
appear across `Concepts/`, `Writing/Passage rehearsals/`, and the R0 planning documents. Casey,
Warburg and Didi-Huberman appear **nowhere** in the rehearsal record.

## 3. Reading

**R1 — The program has evidence that prompts are a live force and none that sources are, and has
been calling both "source pressure".** E3 is as clean as this program gets: one word changed what
the model reported seeing, on identical bytes, pre-registered. E1 shows no instrumented run has ever
had a source text at all. So the question *"can text act as a live force?"* has a split answer:
**prompt text, yes, decisively; source text, unknown — never tested.**

**R2 — The safeguard is unfalsified because it is untested.** The protocol's rule *"source pressure,
never source authority"* has never been under load: there has never been a source in an instrumented
run to acquire authority. The rule reads as a hard-won discipline; it is at present an untested
intention.

**R3 — `source_condition: "present"` is the program's most misleading field.** It is set truthfully
in the two imaginative runs and falsely in eleven instrumented ones. Anyone querying the corpus for
"runs with a source" gets 13 and should get 2. This is a **metadata integrity finding**, and it is
the kind spark-08 warned about from the other direction: the record asserts something the frame does
not contain.

**R4 — Ventriloquism has not been observed because it was designed out, not because it was
defeated.** The doctrine lists source ventriloquism as a top creative failure mode; the record shows
zero instances. E2c shows why: at least one run deliberately swapped the philosophical lens for a
craft one *to avoid it*. That is real methodological discipline and should be credited. But the
consequence is unchanged and worth stating plainly: **the guard has never been under load.** A
failure mode avoided by never creating its conditions is untested, not defeated.

**R4b — The program retired its only source-manipulation run without noticing that cost.** E2d: A6
was the sole run designed with `misleading`. Its retirement (HB-010 §3) rests on an argument about
agreement ceilings that is independent of sources and remains sound. But A6 was carrying two
capabilities, and only one was accounted for at retirement. HB-010 records the loss of the
**suggestibility** test explicitly and with regret; the loss of the **source-condition** test is
recorded nowhere. **This is the run's most consequential observation** — and it is an observation
about the program's bookkeeping, not about text.

**R5 — The flame-stimulator form already exists and works.** E4's `source_pressures` shape —
`source_ref` + `locator` + `paraphrase`, never a quotation — is exactly "record the slice as a
stimulator, not an authority". It is implemented, schema-backed, and used in **imaginative mode
only**. The question is not whether to invent it. It is whether it survives contact with an
instrumented run.

## 4. Opening

**[SPEC] O1** — If a source slice were supplied to an instrumented run, the cheapest honest design
is the A/B the program has already run twice (spark-06, spark-09): identical bytes, identical
question, source present in one arm and `absent` in the other. The instrument exists; only the
`source_condition` value would change.

**[SPEC] O2** — **Warburg is the gap that touches another sandbox.** *Nachleben* (survival /
afterlife of a form) and the Mnemosyne panel arrangement are about a form recurring across time and
material — which is FS-001's exact vocabulary shortfall. A single Warburg-shaped slice is the only
one of the three named gaps that would pressure two axes at once.

**[SPEC] O3** — Casey (place as distinct from site) would pressure `frame` and the artifact-level
gap in spark-01. Didi-Huberman (the image that resists and looks back) would pressure the refusal
vocabulary FS-004 is scoring.

**All speculative. No slice is proposed for ingestion here.**

## 5. Resistance

- **`source_conflict`** — the manifests and the source-notes disagree about whether sources are
  present (E1). The run resolves this in favour of the manifests **and records that it did**, since
  the prose notes are not machine-checkable.
- **`insufficient_evidence`** — the run's own headline question (does a *source* act?) has an n of 0
  in instrumented mode. Nothing here can answer it; the run reports that rather than substituting
  the prompt findings as if they answered it.
- **`cultural_context_missing`** — Pallasmaa's pressures in 001 were applied across European, Pala,
  Chola and Cambodian sculpture. Formal analogy across those traditions on one Finnish architect's
  phenomenology is exactly the flattening the protocol warns of. Recorded, not resolved.
- **`other` (deferral)** — **Lacan remains deferred, and this run declines to justify him.** The
  program's documented failure is over-reading that immunises itself (spark-10). Vocabulary whose
  power is interpretive depth would amplify the known failure mode. Deferral stands on evidence.

## 6. Scoring rubric

| dimension | asks | scale | result |
|---|---|---|---|
| pressure_traceability | Can the thing that forced the revision be identified from artifacts alone? | identified / inferable / untraceable | **identified** for prompt-driven change (spark-06/09: one word, pre-registered); **untraceable** for source-driven — no instance |
| movement_vs_rewrite | Did the claim CHANGE, or only the wording? | claim-moved / scope-narrowed / wording-only | **claim-moved** (E3: *lamps* → *eyes* is a different claim, not a rephrasing) |
| retraction_honesty | When a claim weakened, does the text say so? | states-retraction / hedges / silently-overwrites | **states-retraction** — HB-010 §4 states spark-08's weakening explicitly and names it "the program's first disconfirmation" |
| discrimination | Does the measure separate revised-under-pressure from ordinary editing? | separates / partially / names-everything | **partially** — it separates prompt-pressure from human editing, but **cannot separate source-pressure from anything**, having no positive case |

**No composite score.** The `discrimination` row again carries the weight: the rubric works on one
half of its subject and is untested on the other.

## 7. Stop condition

Declared stops:

- every identified revision pair has been scored or marked unscoreable
- a result would require editing the user's prose
- a result would require a live model call
- scoring would require guessing the author's intent

**Fired: the first**, with the fourth nearly firing — attributing *why* a manifest says `present`
when no text exists would require guessing intent. The score records the contradiction as a fact and
declines the explanation.

## 8. Withheld

- **"The program has been ventriloquizing philosophy."** Withheld and in fact **refuted** — it
  cannot have been, since no instrumented run had a source (R4).
- **"Add Warburg / Casey / Didi-Huberman to the corpus."** Withheld as an action. Named as a gap in
  §4 with reasons; ingestion is a curatorial decision with a cultural-safety dimension, not a
  research output.
- **"Fix `source_condition` on the eleven runs."** Withheld emphatically. **Runs are frozen
  evidence.** HW-C6 settled the general form of this question — *"Do not retro-fill the runs"* — and
  the same answer applies. Record the contradiction; never edit the record.
- **Any long quotation from Pallasmaa or any other source.** None appears in this document by
  design; locators and paraphrase only.
