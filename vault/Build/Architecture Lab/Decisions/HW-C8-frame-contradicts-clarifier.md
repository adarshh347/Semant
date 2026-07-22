# HW-C8 — Resolving the OPEN §C3 clarifier: when may a rehearsal say the frame refutes a claim?

**DECISION DOC — no implementation authorized. Markdown convention only.** No schema change, no
source file, no route, no collection, no production entity. No model calls were made by this lane.
No production document was read or written.

| | |
|---|---|
| **id** | HW-C8 · closes the item left **OPEN** at `HW-C5-external-claim-convention.md` §9.3 |
| **date** | 2026-07-22 |
| **status** | **Decided.** Amends `HW-C5` §3.2 and §6.3. |
| **decision, in one line** | **`frame-contradicts` requires that the falsification be statable using only the picture and no external premise. `stimulus-contradicts` requires the frozen request record and nothing else. Anything needing an imported premise stays `frame-silent`.** |
| **rests on** | the cycle-6 audit of runs 001–006, plus the two runs since (008: 13 rows, 009: 8 rows), which is the first evidence gathered *under* the convention rather than reconstructed |

*Fable-pass: the adjudication and the boundary argument. Opus-pass: the corpus recount.*

---

## 1. What was left open, and why it could not stay open

Cycle 6's audit (§C3) found **two arguable `frame-contradicts` in six runs** and warned that
`HW-C5` §6.3 — *the status collapses to one value if "whether the frame refutes a claim is itself
arguable"* — was close to firing:

- **A3's** *"windows that function as eyes"* — recorded `frame-silent` for consistency with 007.
- **A4's** *"the central mihrab niche"* — recorded `frame-silent` because falsifying it needs an
  imported definition of what a mihrab is.

Against **two clean ones**: A5's fabricated inscription (settled by a 6× crop) and A3's *"obscuring
lace veil"* (settled by looking).

The audit proposed a rule and did not adopt it. Cycle 7 deliberately left it open, having been
authorised only two amendments. **It cannot stay open now**, because A6 — whichever form it takes —
will run against a corpus of curator-supplied attributions and is the most likely run yet to
generate a claim someone wants to mark as refuted.

## 2. The decision

**Adopt the audit's proposed rule, in three parts.**

### 2.1 `frame-contradicts` — the picture, and nothing else

> **A claim may be marked `frame-contradicts` only if its falsification can be stated using the
> picture alone, with no premise imported from outside it.**

Evidence remains **required** (a crop, an upscale, a coordinate box), unchanged from §3.2.

**Test to apply, in one question:** *could a reader who knows nothing about the subject — no
architecture, no art history, no vocabulary — verify the refutation by looking at the crop you
supplied?*

- A5's inscription: **yes.** The model quoted an English sentence; the band resolves to a
  fragmentary non-English text. No knowledge required beyond seeing that the letters are not those
  letters. ✅ `frame-contradicts`.
- A3's *"lace veil"*: **yes.** Either the thing is lace-like and obscuring, or it is not. ✅
- A4's *"the central mihrab niche"*: **no.** You must first know what a mihrab is, and then argue
  that this niche is not one. ❌ stays `frame-silent`.
- A3's *"windows that function as eyes"*: **no.** *"Function as eyes"* is a reading, not a
  measurement; refuting it requires a premise about what counts as an eye. ❌ stays `frame-silent`.

**Under this rule the corpus has 2 clean `frame-contradicts` and 0 arguable ones, and §6.3 is not
triggered.** That is the outcome the audit predicted, and it is the point of adopting the rule:
**the status survives because it was narrowed, not because the corpus got luckier.**

### 2.2 `stimulus-contradicts` — the frozen request record, and nothing else

> **A claim may be marked `stimulus-contradicts` only if the frozen record of what was sent
> falsifies it: the manifest, the trace, the `image_sha256` list, the prompt text, or the observed
> `usage`.** Cite the specific field.

This is the value added in cycle 7 for A5's *"multiple cropped views"* / *"the top crop"* when a
single image was sent. **It is the cheapest settlement the program has** — no crop, no upscale, no
looking — because the runner already freezes the record.

### 2.3 The two never overlap, and the boundary is worth stating

*(Fable-pass.)* The two statuses are not two flavours of "wrong". They impugn different things:

| | what the model got wrong | what settles it | what it says about the model |
|---|---|---|---|
| `frame-contradicts` | **the world in the picture** | the pixels | it misread what it was looking at |
| `stimulus-contradicts` | **the encounter itself** | the request record | it misreported the conditions of its own observation |

A claim cannot be both, because a claim is either about **what is depicted** or about **what was
supplied**. If a run cannot tell which a claim is about, that is the signal the claim is a *reading*
and belongs in `frame-silent` — which is the same escape hatch §2.1 provides, arrived at from the
other side.

**Why `stimulus-contradicts` is the graver finding of the two.** A model that misreads a picture is
doing the thing the rehearsals exist to study. A model that invents *how many images it was shown*
has lost the thread between its evidence and its claim, and every downstream statement it makes is
unanchored. **A5's stage 2 is the only instance in the corpus and it was nearly lost to prose.**

## 3. What this costs, and the objection to it

**The rule makes `frame-contradicts` harder to earn, and that is deliberate.** It will systematically
under-count the model's errors: A4's mihrab attribution may well be wrong, and the ledger will not
say so.

**That is the correct trade, for the reason §4.1 already gives.** The ledger records
*frame-settleability*, never truth. A status that fires whenever a curator is *confident* the model
is wrong is a truth verdict wearing an evidence label — and it would import exactly the external
lookup §4.3 forbids as a precondition. **An under-counting ledger is recoverable** (the raw text is
frozen; a later run can revisit). **A ledger that has quietly become a scoreboard of the curator's
own art-historical opinions is not.**

**The honest cost, stated plainly:** a reader scanning ledgers will see fewer contradictions than the
model actually committed, and must not read a low `frame-contradicts` count as the model behaving
well. **Runs should say so when it applies.**

## 4. Evidence from the two runs that have used the convention

This is the first evidence gathered *under* the convention rather than reconstructed after the fact.

| run | rows | identity-reaching | `frame-contradicts` | `stimulus-contradicts` | arguable cases |
|---|---|---|---|---|---|
| 008 | 13 | 6 | 0 | 0 | **0** |
| 009 | 8 | 1 | 0 | 0 | **0** |

**Neither run produced a single arguable case**, and both hit the boundary in the same place and
resolved it the same way without the rule being written: *"likely verses from the Quran"* attributes
the script's **source** while hedging, and both runs recorded it `frame-silent` with the mandatory
upscale **not** triggered, reasoning that naming a corpus is not quoting its content.

**That convergence is the strongest argument for §2.1**: two runs independently applied the rule
before it existed. It is codification, not invention.

**One caution.** Both runs are motif/construction-framed and neither was asked *"what is this?"* —
the question shape that 008 and 009 jointly show produces identity-reaching claims. **The corpus has
not yet tested the rule against a run designed to elicit attributions.** A6, or any future
open-question run, will be the real test.

## 5. Consequential rule for the ledger's preamble

A run whose ledger has **0 `frame-contradicts` and 0 `stimulus-contradicts`** must not describe
itself as having found the model accurate. The required form is the convention's own:

> *"N claims the frame does not settle. This rehearsal verifies none of them."*

**Not** *"no false claims"*, **not** *"the model made no errors"*. The ledger never licensed either,
and the narrowed rule makes the distinction sharper rather than softer.

## 6. What this does NOT do

- **No schema change.** `instrumented-score.schema.json` still has `additionalProperties: false` and
  is untouched. Markdown only.
- **No backfill.** Runs 001–006 keep their `score.md` files as written. The audit's reconstructed
  ledgers stay in the audit doc. Under this rule A3's and A4's arguable rows would be `frame-silent`
  — **which is what the audit already recorded them as**, so nothing would change even if backfill
  were authorized. It is not.
- **No new column and no fourth status.** §4.5's *"it must not grow"* binds. Three statuses, six
  columns.
- **No truth adjudication**, no intent language, no external lookup made a precondition. §§4.1–4.4
  stand unchanged.
- **No design proposal.** §4.4 still forbids citing the ledger's shape as a data model.
- **It does not settle whether `frame-silent` is doing too much work.** It now absorbs both
  "unverifiable attribution" and "claim the curator believes is wrong but cannot show from pixels".
  **That merge is deliberate and is the price of §3.** If a later cycle finds the merge is hiding
  something, the evidence will be a run where the distinction changed a decision — and no such run
  exists yet.

## 7. What would overturn this

1. **A run where a claim is plainly refuted by the picture but fails the no-external-premise test**,
   and where recording it `frame-silent` visibly loses the finding. That would mean the rule is too
   strict and should be relaxed to "no *contested* external premise".
2. **Any run where applying the test is itself arguable** — the same §6.3 condition, moved up one
   level. Response: collapse to a single `frame-silent` value and put falsification in prose.
3. **`stimulus-contradicts` never firing again**, across ≥5 further runs, which would make it a
   one-off dressed as a category. Response: retire it and return A5's case to prose.
