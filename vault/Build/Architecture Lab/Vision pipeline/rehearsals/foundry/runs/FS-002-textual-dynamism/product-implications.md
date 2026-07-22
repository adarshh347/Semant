# Product Implications — FS-002-textual-dynamism

**Sandbox:** FS-002-textual-dynamism · **Axis:** textual-dynamism · **RESEARCH-ONLY**

> **This document authorizes nothing.** It records pressure, not proposals. Every item is **[SPEC]**
> until an explicit build gate says otherwise, and **no single sandbox can create a production
> entity**.

---

## 1. Pressure observed

**The pressure lands on the research instrument, not on the product.** That is the honest headline
and it should not be dressed up.

Everything this run found — a mis-set control variable, a retired source arm, an unstressed
pressure-recording form — is about `rehearsal-manifest.schema.json` and the R2 batch plan, which are
**research artifacts that define no production entity**. Semant's data model is untouched by all four
sparks.

There is exactly one thread that reaches the product, and it reaches it indirectly: **spark-06 and
spark-09 mean that prompt wording is a load-bearing part of any surface that asks a model a
question.** Aletheia's `/read`, the "Draft from the image" and "Continue writing" actions stubbed in
`Manuscript.jsx`, and any future write-about-part path all embed a fixed question. On the program's
own evidence, that question **is** the instrument. Changing its wording is not copy-editing.

## 2. Nearest existing construct

- **`rehearsal-manifest.schema.json`** — research schema; carries `source_condition`. Not a product
  schema, has no route, no collection, no UI.
- **`virtual-rehearsal-score.schema.json`** — carries `source_pressures` with `paraphrase`/`locator`.
  Also research-only.
- **Product side: nothing.** No Semant entity models "a text exerting pressure on a reading". The
  correct answer to "what construct covers this?" is **none, and none is needed** — because nothing
  in this run establishes that Semant should model source pressure at all.

## 3. What could be expressed with NO new entity

- **[SPEC] Nothing needs building.** All four sparks are answerable by writing things down.
- **[SPEC] The strongest available move is a validation rule for *future* manifests** — refuse
  `source_condition: present` when `seed_constellation.texts` is empty. Note the shape: **the Foundry
  Harness already does exactly this class of check** for sandbox manifests (`validate_sandbox`
  cross-field guards). The rehearsal runner does not. This is a research-tooling improvement, costs
  no schema, and is **not proposed here** — it belongs to whoever owns the rehearsal substrate.
- **[SPEC] Record prompt wording as an experimental variable with the seriousness `image_order`
  already gets.** `image_order` is documented as "an experimental variable" in R1's schema
  decisions; on this run's evidence the **question's nouns** are at least as load-bearing, and they
  live in prose rather than in a field. Observation only.

## 4. What would require a new entity — and why that is not yet justified

**The temptation:** a `SourceSlice` / `Pressure` entity so a passage can record which text was acting
on it — the natural companion to FS-001's recurrence temptation.

**Why premature, in order of force:**

1. **Zero instrumented instances.** Same structural defect as FS-001: an empty positive class. The
   program has never once run a rehearsal with a source present.
2. **The one designed test was retired** (spark-FS002-03). Building an entity to model a force whose
   only measurement was cancelled is building on an intention.
3. **The existing research form is unstressed** (spark-FS002-04). If `paraphrase` + `locator` cannot
   survive one instrumented run, no product entity built on the same idea would either.
4. **Seed ecology argues the other way.** HW-C5 is unambiguous that **images, not texts, are the
   bottleneck** — 39 real unclaimed fixtures, and *"Texts are useful but never blocking."* Investing
   in textual infrastructure inverts the program's measured scarcity.

## 5. Deliberately NOT concluded

- That source texts do **not** act on readings. The run establishes **untested**, not **inert**.
- That the program was ventriloquizing philosophy — **refuted**, not merely withheld.
- That the eleven manifests should be corrected. Runs are frozen evidence (HW-C6).
- That A6 should be revived. The ceiling argument that retired it stands.
- That Warburg/Casey/Didi-Huberman should be acquired. Named as gaps only.
- That prompt wording should be centrally managed, templated, or versioned in the product. One
  observation about experimental method does not license a copy-governance system.

## 6. Cost and risk if built prematurely

- **Premature ontology** — a source/pressure entity with no positive instance anywhere.
- **Source ventriloquism, industrialised** — the deepest risk. Making sources easy to attach makes
  the doctrine's top creative failure mode cheap to commit at scale, while the guard against it
  remains untested (R4).
- **Cultural flattening** — E4's own pressures applied one European phenomenology across European,
  Pala, Chola and Cambodian sculpture. A product feature that attaches a slice to any image
  industrialises exactly that, and the protocol's warning would be structurally overridden.
- **Context flooding** — `12-failure-and-safety` names all prior passages entering every prompt.
  Source slices are additional context by construction.

## 7. Reversibility

The research-tooling move (§3, a manifest validation rule) is trivially reversible: delete the check.
It stores nothing and changes no past run.

Anything product-shaped has **no rollback story written**, and would strand attached slices on
readings that were composed under their influence — which is precisely the provenance the program
refuses to manufacture elsewhere. **Not ready to be discussed as a build.**

## 8. Graduation status

**Current: SPARK** ×4. One (spark-FS002-02) is machine-checkable and survived its strongest
objection; one (spark-FS002-03) was produced *by the critique rather than the score*, which is the
process working as designed.

**Required to advance:** a repeated pattern across ≥ 2 independent runs, a candidate card with an
enablement claim, transfer/negative/sequence-inversion trials, then an explicit build gate.

**The next step is not a build and not an ingestion. It is a decision the orchestrator owns:**
whether the program wants an `absent`/`misleading` source arm at all now that A6 is gone (UQ2). If
the answer is no, textual dynamism should be *closed as an axis* rather than left implicitly open.
