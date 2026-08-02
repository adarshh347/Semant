# 007 — Critique (meta-observation)

Adversarial pass over this replication's own conduct.

---

## Where it is weak

**1. "Address" may be a leading question rather than a frame.** The word arguably *names* a
viewer-relation, so arm A may not be testing "framing" so much as "asking a question that
presupposes a facing thing". That makes the result useful operationally — it tells A6 which words
to avoid — but it is a narrower finding than "prompt framing causes anthropomorphism", and
`score.md` and `sparks.md` both say so rather than claiming the broader version.

**2. Order was not counterbalanced.** Arm A ran first, every time — n=1 of one order. Both calls are
stateless and independent, so there is no mechanism for carry-over; but "no mechanism I can think
of" is weaker than "counterbalanced and measured", and the program has already been burned once by
inferring absence of a bug from code shape (the hydration race).

**3. The stimulus differs from A3's in resolution and call shape.** 768 px single-image here vs
256 px three-image there. Declared in the manifest **before** running, and it does not touch the
core finding — which rests on the contrast *between arms*, where resolution is held constant — but
the two runs are not strictly identical conditions and the score says so.

**4. n = 1 image.** The resolution of spark-06 rests on a single stimulus. It happens to be the
right one (the only image known to have produced the behaviour), which is why one is defensible
here — but a second stimulus would make it robust rather than merely decisive.

**5. I designed both the hypothesis and the test.** The interpretation grid was pre-registered in
the manifest, which is the correct guard, but a genuinely independent arm-B prompt would have been
better written by someone who did not already believe the frame hypothesis.

## Where it held

- **Pre-registration.** All four cells of the interpretation grid, including the confounded
  `a_none_b_none` case, were written into the manifest **before** any call — with an explicit rule
  that a null result must NOT be scored as resolving spark-06. The result could not be retrofitted.
- **The variable was genuinely isolated.** Identical stimulus by sha256, identical model,
  `reasoning_effort`, `max_tokens` and call shape; both arms stateless.
- **Neither prompt primed.** No *face*, *eye*, *gaze*, *body*, *head*, *watching* in either.
- **The finding was reported at its actual scope**, not its most impressive one: address vocabulary
  resolved, kinship vocabulary explicitly *not* — which is the question A6 actually asks.
- **The A6 consequence was stated as a limit as well as a clearance.** It would have been easy to
  write "A6 is now protected" and stop.
- Production read, never written. Nothing graduated.

## A note on what this run cost to get right

The manifest failed schema validation on first run (`seed_constellation` requires `texts` and
`existing_percepts`). That cost one cycle and **zero model calls** — the runner refuses an invalid
manifest before any adapter is invoked. Worth recording as evidence that the validate-then-capture
ordering is doing real work: an invalid run cannot spend budget.
