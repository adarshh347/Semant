# 003 — Sparks

**Epistemic status: SPARK only.** Nothing here is a candidate, a decision, or a schema proposal.
Graduation needs ≥3 fixtures plus transfer and negative tests (R3) — not attempted. No durable
candidate object was created.

---

## spark-03 — evidence loss should be announced, not merely survived

**Origin:** the detached-ground finding.

**Observation.** Percept `pctx_mrqp950d_0` ("the upper head") has 2/2 grounds detached because a
re-dissect replaced the `fine_*` regions those grounds referenced. The curator was never told. The
percept still renders as a percept; only its evidence is gone.

**Enablement claim.** Detachment is currently a *rendering* state (`resolveGround` marks it, the
inspector lists "detached evidence") but not an *event*. Nothing surfaces it at the moment it
happens, and nothing accumulates it. A curator can lose the grounding of an arbitrary number of
percepts without a single notification.

**Nearest existing construct:** `Ground` — detachment is already modelled; what is missing is
notification, not representation.

**Why this is the strong version of the A2 finding.** It needs no new entity, no new schema, and
no ontology change. The information already exists in the documents — a re-dissect could compare
the outgoing region ids against grounds that reference them and report a count. The gap is that
nobody is told.

**Next test.** Sweep the corpus read-only: how many percepts across all posts currently cite
detached region grounds? If `pctx_mrqp950d_0` is alone, this is one post's accident. If it is
common, it is a standing property of re-dissection. Cheap, read-only, no model calls.

---

## spark-04 — distinguish channel disagreement from out-of-domain collapse

**Origin:** all 7 regions on a sculpture close-up labelled `wall` or `floor`.

**Observation.** The semantic channel here is not *disagreeing* with the material channel; it is
answering a question it has no vocabulary for. An ADE20K-style scene segmenter has no sculpture
class, so it returns its nearest architectural labels with no signal that it is out of domain.

**Enablement claim.** Treating this as "sensory disagreement" would be a category error with a
design consequence: an uncertainty UI that offers the curator a choice between a competent reading
and a confident non-answer teaches them to distrust the wrong channel. Before disagreement can be
surfaced honestly, out-of-domain output has to be detectable.

**Cheap available evidence, on this fixture:**
- **Label collapse** — 7 regions → 2 classes, both from a domain absent from the image.
- **Boundary/material mismatch** — chromaticity across label boundaries (0.0061–0.0067) is *lower*
  than within a single label (0.0124). Real object boundaries in one material need not show a
  colour break, so this is suggestive, not decisive, on its own — but combined with label collapse
  it is a strong signal.

**Nearest existing construct:** `VisionRun` / `VisionStageEvent` — a run already records
`capability` and `actual_source`, so an out-of-domain flag would have somewhere honest to live.

**Deliberately NOT concluded:** that Semant should add domain detection, confidence thresholds, or
an uncertainty UI. One fixture. This names the distinction; it does not license machinery.

**Next test.** Run the same two probes on a fixture the architecture segmenter *is* in-domain for
(a real building interior). If labels stay diverse and boundaries track material there, the
collapse signature is specific to out-of-domain input and usable.

---

## Withheld

- **"The stone remembers being one block; the labels cut it up."** The image and the measurement
  both invite this. It is a sentence about the sculpture's making, and nothing here is evidence
  about carving practice. Withheld.
- **Any claim about which detector produced `arch_*`, or when.** There are 0 `vision_runs` for this
  post; the history is not recoverable. Naming a model would be invention.
- **Any claim that the curator's "upper head" percept was *correct*.** It is unevidenced *now*;
  whether `fine_0`/`fine_3` were good regions cannot be checked, because they no longer exist.

## Unresolved questions

1. How many percepts corpus-wide currently cite detached grounds? (spark-03's next test.)
2. Is the `field` ground's durability an argument for preferring it, or does reference-based
   grounding remain right with better notification?
3. Should a re-dissect be allowed to replace a region set that grounds depend on at all, or should
   the old regions persist as tombstones so the evidence resolves to something?
