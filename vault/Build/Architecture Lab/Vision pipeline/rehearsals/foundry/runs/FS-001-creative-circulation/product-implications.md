# Product Implications — FS-001-creative-circulation

**Sandbox:** FS-001-creative-circulation · **Axis:** creative-circulation · **RESEARCH-ONLY**

> **This document authorizes nothing.** It records pressure, not proposals. Every item is
> **[SPEC]** until an explicit build gate says otherwise, and **no single sandbox can create a
> production entity**.

---

## 1. Pressure observed

The pressure is **not** "build recurrence". It is narrower and more awkward:

**The program cannot currently evaluate its own graduation criterion.** The Candidate Foundry
(`new-planning/06-candidate-foundry.md`) requires a **circulation test** — "does it matter after
leaving the image?" — before any candidate graduates. This run establishes that on the frozen record
there is nothing downstream to test against: 0 of 11 posts carry writing. Every spark in the R2
register is therefore blocked at the same gate, for a reason none of them names.

Pressure lands on **process**, not on code: the program is accumulating sparks it has no way to
promote.

## 2. Nearest existing construct

- **`Mention`** — already models "a percept cited in a passage" and is reconstructed from block
  markup (`perceptMentions.js`). It is complete, tested (17 tests), and **has never held a real
  Mention** because no passage has been saved.
- **`Ground` + `resolveGround`** — already models evidence that may stop resolving.
- **The recall script** — already models re-presentation over time.

**The default answer is correct here: an existing construct already covers the modelled part.** What
is missing is not a construct; it is *usage*, and one unblocked probe.

## 3. What could be expressed with NO new entity

The largest section, as it should be.

- **[SPEC] Nothing needs building to answer this axis' first question.** UQ1 is a read-only count of
  `text_blocks` across the corpus. It is not a feature; it is a query, and it would kill or confirm
  spark-FS001-02 outright.
- **[SPEC] The blocked R1 rendered probe is the real unblocking action.** It requires no code: insert
  a chip, click it, observe recall, discard without saving (level A). R1 recommended R2 carry it "as
  its first obligation"; R2 ran eleven model probes instead. Servers stayed alive this session.
- **[SPEC] The A2R shape generalises without a schema.** "Qualify a past reading with the present
  state of its evidence; never delete, never repair" is a behaviour over existing data. If
  recurrence is ever wanted, this is the form that costs nothing structurally — and FS-004 is already
  scoring whether that one shipped sentence actually reads as a qualification.

## 4. What would require a new entity — and why that is not yet justified

**The temptation, stated plainly:** a revision/version field on `Percept`, or a `PerceptRevision`
entity, or a cross-post relation so a percept can recur on a *different* image.

**Why premature, in order of force:**

1. **Zero positive instances.** Not a small n — an empty positive class. The rubric's own
   `discrimination` row scored `names-everything`, meaning the instrument that would detect
   circulation has never separated a single case.
2. **The finding may be about the corpus, not the architecture** (critique §1). Building a schema on
   a selection artifact is the worst available outcome.
3. **spark-07 already wanted scope; this run wants time.** Two absences found by two runs with no
   positive instances is a reason to look for a common cheaper explanation, not to add two fields.
4. **The repair fork from spark-03 is still unchosen.** Tombstoning vs notifying are different
   theories of what evidence is. Adding revision semantics before that fork is decided would
   pre-decide it silently.

## 5. Deliberately NOT concluded

- That Semant **cannot** support creative recurrence. The evidence supports **unattested**.
- That recall should write back to the percept.
- That Home should surface percepts (second-hand evidence in this run).
- That the imaginative mode is architecturally privileged for returns.
- That "0 of 11" describes the whole corpus — it describes the instrumented posts.

## 6. Cost and risk if built prematurely

- **Premature ontology** — the headline risk. One run, no positive class, and a schema would freeze
  a theory of recurrence before a single instance exists to check it against.
- **False precision** — a `revision_count` or `last_returned_at` would render as fact on every
  percept while measuring an interaction nobody has performed.
- **Hidden behavioural profiling** — recording returns is recording attention. `12-failure-and-safety`
  names sedimented salience silently manipulating future attention; a return-log is that, by default.
- **Interface taxonomic overload** — every construct becoming a chip and a sidebar section.

## 7. Reversibility

If any version were prototyped: it must be **derivation-only** — computed from data already stored,
removable by deleting the diff, stranding nothing. The moment recurrence requires persisted state it
acquires a migration and a deletion story the program has not written. A pressure with no rollback
story is not ready to be discussed as a build, and **this one currently has none**.

## 8. Graduation status

**Current: SPARK** — three of them, all weak, one (spark-FS001-02) explicitly **unfalsifiable inside
this sandbox's boundary**.

**Required to advance:** a repeated pattern across ≥ 2 independent runs, then a candidate card with
an enablement claim, then transfer/negative/sequence-inversion trials, then an explicit build gate.

**The single next step is not a build. It is UQ1 — a read-only count — and the R1 rendered probe.**
