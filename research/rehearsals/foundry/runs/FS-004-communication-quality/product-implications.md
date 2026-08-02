# Product Implications — FS-004-communication-quality

**Sandbox:** FS-004-communication-quality · **Axis:** communication-quality · **RESEARCH-ONLY**

> **This document authorizes nothing.** It records pressure, not proposals. Every item is **[SPEC]**
> until an explicit build gate says otherwise, and **no single sandbox can create a production
> entity**.

---

## 1. Pressure observed

This is the **only lane in Batch 1 whose pressure reaches a shipped surface**, and it is worth being
precise about where.

The pressure is *not* "Semant communicates badly". It is: **`differential/VisionActivityRail.jsx`'s
closed summary renders a count where the module beneath it holds a distinction.** `visionActivity.js`
discriminates absent from unreadable and forbids causal wording under test; the closed line reports
`"N recorded"`, and `partial` / `timed_out` / `stale` are indistinguishable from success until the
drawer is opened — which it is not, by default.

A second pressure, weaker and more diffuse: every surface that will render model prose inherits a
documented tendency to raise force as content thins (spark-10), and nothing anywhere notices.

**Both were already named by HW-S1** (§1.2, E5) and by HB-010 (§7). This run adds a reason, not a
discovery — see critique §2.

## 2. Nearest existing construct

- **`visionActivity.js`** — already computes the states, already owns the tone vocabulary, already
  has a unit-tested derivation surface (`visionActivity.test.js`). HW-S1 is explicit that a summary
  derivation "would belong in `visionActivity.js` to stay unit-tested, per that module's stated
  contract".
- **The A2R recall note** — already the model of a well-formed absence statement, already shipped and
  render-verified.

**The default answer holds emphatically: existing constructs cover this entirely.** Nothing here
wants a new entity, a new field, a new route, or new stored data. What is missing is a rendered
sentence — and this sandbox may not write one.

## 3. What could be expressed with NO new entity

This section should be the longest, and here it is genuinely the whole story.

- **[SPEC] Everything this run touches is derivation + copy.** No schema, no endpoint, no migration,
  no persisted state. HW-S1's own reversibility criterion — *"no schema change, no new endpoint, no
  stored data, no migration; removable by deleting the diff"* — is satisfiable for every item.
- **[SPEC] The existing experiment already exists and is scoped.** HW-S1 **E5** is precisely this
  change, with its location, its home module, its test file, and its own kill condition already
  written. **The correct product action is not to design something; it is to decide whether to run
  E5.** That decision belongs to the orchestrator.
- **[SPEC] A2R's shape is the available template.** State the limit · locate it in the record, not in
  the person · give a denominator · never delete the claim it qualifies · never repair. Four
  properties, all satisfied by one shipped sentence, all expressible in copy.

## 4. What would require a new entity — and why that is not yet justified

**The temptations, in ascending order of danger:**

1. **A tone system / voice guide.** Forbidden by the manifest, and rightly: two user-facing samples
   cannot license a system. It would also freeze copy the program is still learning to write.
2. **An overclaim detector** — something that flags model prose whose force outruns its evidence.
   Deeply attractive after spark-10. **Premature and possibly incoherent:** spark-10's deflationary
   reading is still live and `012-repeat-stability` may invalidate the whole line. Building a
   detector for a phenomenon that may not survive its first repeat is the clearest possible case of
   premature ontology.
3. **A stored "communication quality" score or confidence field.** False precision on a sample of
   two, and it would put a number where the program has deliberately refused composite scores.

**The general reason all three fail:** this run's entire evidence base is **four sentences, two of
them user-facing, none observed in a browser by this run**. That licenses arrangement and argument.
It does not license architecture.

## 5. Deliberately NOT concluded

- That the rail should open by default. **HW-S1 explicitly considered and declined this**; repeating
  it as a finding would launder a rejected idea.
- That A is the right sentence for every absence. It was written for one case and verified on one.
- That trust and circulation are the same axis (score O2). Suggestive, and flagged in the score
  itself as the shape spark-10 warns about.
- That Semant should say anything specific when it refuses — **no refusal has ever occurred.**
- That the product lacks honest copy generally. This run enumerated only the copy the research record
  discusses (critique §4, correction 3).

## 6. Cost and risk if built prematurely

- **Interface taxonomic overload** — the named risk here. Every state becoming a badge, a chip, a
  tooltip. HW-S1 warned about spending the disclosure by defaulting the drawer open; the same logic
  applies to any louder status.
- **False precision** — a confidence or quality number derived from two samples.
- **Freezing copy that is still being learned** — a tone guide written now would encode a
  four-sentence understanding as a standard. The HB-010 lane-3 lesson applies directly: *do not add a
  test asserting on display copy*; it freezes exactly what should stay unfrozen.
- **Building a detector for a phenomenon awaiting its first repeat** (§4.2).

## 7. Reversibility

Genuinely good here, and worth stating because it is rare in this batch: every item in §3 is
**derivation + copy**, removable by deleting a diff, stranding no data and requiring no migration.
There is no rollback problem because there is nothing to roll back to.

That is an argument for E5 being *cheap*, not an argument for it being *right*. Cheapness has
repeatedly been the wrong sequencing criterion in this program — HB-010 §6 records exactly that
lesson about increment C ("the safest mechanically and the riskiest semantically").

## 8. Graduation status

**Current: SPARK** ×3, all weak, all restating existing documents with a new arrangement.

**Required to advance:** a repeated pattern across ≥ 2 independent runs, a candidate card with an
enablement claim, transfer/negative/sequence-inversion trials, then an explicit build gate.

**The next step is a decision, not a build:** whether to run HW-S1's **E5**, which already exists as
a scoped, reversible, kill-conditioned experiment. If the answer is yes, it is an implement
instruction the orchestrator must give explicitly — HB-010's standing constraint that **no UI string
changes without an explicit implement instruction** remains in force, and nothing in this sandbox
relaxes it.
