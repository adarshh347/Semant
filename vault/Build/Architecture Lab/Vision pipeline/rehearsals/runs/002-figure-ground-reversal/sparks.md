# 002 — Sparks

**Epistemic status: SPARK only.** Nothing here is a candidate, a decision, or a schema proposal.
Graduation requires ≥3 fixtures plus a transfer test and a negative case (R3) — not attempted.

---

## spark-01 — the artifact layer: claims about the plate, not the picture

**Origin:** the whole of A1.

**Observation.** "What is the space between the faces doing?" has a true, evidence-backed answer —
*separating specimens for typological comparison* — and there is nowhere to put it. Every Ground
type points into the depicted image plane. This claim is about the **plate as a made object**: a
composite of five separately-photographed heads, keyed onto flat black, captioned, and scaled to a
common baseline for comparison.

**Enablement claim.** Some noticings are about the *artifact* (how it was made, framed, cropped,
composited, captioned, sequenced) rather than about *what it depicts*. Semant currently has no way
to distinguish those two registers, so an artifact-level claim must either be forced into a
picture-level Ground (making it false) or dropped (losing it).

**Nearest existing construct:** `Ground` — specifically `frame` (`whole: true`), which addresses
the image as a whole but still as a *depiction*.

**Why this matters beyond one plate.** Museum/textbook plates, catalogue scans, cropped details,
and collages are a large share of any art-historical corpus. On every one of them, the difference
between "this is in the artwork" and "this is in the reproduction" is exactly the difference
between a true and a false percept. A1 found a case where the system can only say the false one.

**Next test.** Take a *single-object* photograph (not a composite) and ask the same interval
question. If the stall disappears, the finding is specific to composite plates and the spark is
narrow. If a version of it survives, the artifact/depiction split is general. Run before A2.

---

## spark-02 — reversal is available to the hand but not to the machine

**Origin:** the "why it stalls" analysis.

**Observation.** A curator can draw a `field` over the interval right now. But nothing will ever
*offer* it: detection proposes objects, `groundFromRegion` needs a `region_id`, and the VLM
answered `NO_GROUND` when asked to point at the gap.

**Enablement claim.** The asymmetry is structural, not incidental — proposal machinery is
object-shaped end to end. Any figure/ground reversal therefore costs a deliberate human act, which
means it will happen rarely regardless of whether the ontology permits it.

**Nearest existing construct:** `Ground` (`field` / `boundary`).

**Deliberately NOT concluded:** that Semant should add interval/negative-space detection. A1 is
one image. The evidence supports naming the asymmetry, not fixing it.

**Next test.** A5/A6, or a dedicated probe: does *any* available detector ever return a
non-object proposal? If none can, the asymmetry is a property of the model layer, not of Semant.

---

## Withheld

- **"Negative space as breath / silence / the interval as caesura."** The image invites this
  sentence strongly. The evidence is 59.5 % pure black on a composited background. Withheld as
  unsupported — recorded here so the temptation is visible rather than quietly resisted.
- **Any claim about what the interval means across Gupta→Pala transmission.** The existing percept
  makes a transmission claim about facial geometry; extending it to the gap would be analogy
  overreach with zero supporting evidence.

---

## Followup correction (added after run `002F-single-object-followup`)

The A1 result above stands unchanged — the stall was real and is not rewritten. But the followup
control on a single, non-composite photograph (Michelangelo's Pietà in situ) narrowed two of the
claims on this page. Recorded here so this file is not read in isolation:

- **spark-01 narrows to reproductions.** The artifact/depiction split arose *because* A1's subject
  was a made comparative plate. On a real photograph the space beside the figure is in the depicted
  world; there is no category gap. Still a real corpus problem for plates, scans, and collages —
  but not the general claim it appeared to be.
- **spark-02 was overstated and is corrected.** Detection is **not** purely object-shaped: the
  Pietà post's pre-existing regions include `arch_0 "wall"` and `arch_1 "floor"`. The accurate,
  narrower claim is that detection proposes **things** (figures *and* surfaces) but never
  **intervals** — no region in either run points at a space-between.
- **The measurement contrast is stark:** 59.5 % literally `(0,0,0)` in A1's interval vs **0.0 %**
  everywhere tested in the photograph.

See `../002F-single-object-followup/score.md`.

## Unresolved questions

1. Is the artifact/depiction distinction a Ground *type*, a Ground *attribute*, or something that
   belongs on the image record rather than on Grounds at all? A1 cannot tell.
2. Does the answer change when the source is a single photograph rather than a composite plate?
3. Should a percept whose evidence is "the absence of evidence here" be expressible at all, or is
   refusing it the correct behaviour?
