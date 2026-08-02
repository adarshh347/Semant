# 003 — Critique (meta-observation)

Adversarial pass over A2's own conduct.

---

## Where the rehearsal is weak

**1. The strongest finding was not produced by the rehearsal instrument.** The detached-ground
discovery came from *reading the post's grounds*, not from the seed gesture or either VLM probe. A
plain read-only query found it; the 2 model calls corroborated the surface reading ("one stone",
"a sculpture not a wall") but contributed nothing to the finding that matters. Honest accounting:
A2's value came from inspection, and the model budget was largely ceremonial here.

**2. Chromaticity is weaker evidence than it looks.** Two genuinely different objects made of the
same stone *should* have similar chromaticity — so "cross-label distance < same-label distance"
does not by itself prove the labels are wrong. It proves the labels don't track *material*. What
actually establishes the labels are wrong is that the image contains no wall and no floor, which
is a judgement from looking, corroborated by probe 2. `sparks.md` spark-04 states this limitation
rather than leaning on the number.

**3. The probes were easy.** "Is this one surface or two?" on a single carved figure has an
obvious answer, and the model gave it. Neither probe was designed to fail, so neither one tested
much. A sharper A2 would have probed the *boundary* the detector drew — e.g. asking what changes
along x≈0.40 — where a wrong answer would have been informative.

**4. Sample of one, again.** Every claim about out-of-domain collapse rests on this single post.
spark-04's next test exists to attack it, and was deliberately not run inside A2's budget.

**5. The re-dissect story is inferred, not observed.** That a dissect *replaced* `fine_*` with
`arch_*` is the most plausible reading of `fine_0`/`fine_3` being referenced but absent. With 0
`vision_runs` for this post, it is not directly evidenced. Stated as inference in `score.md`, and
no model or date is named.

## Where it held

- **Amendment 1 was honoured.** Neither prompt named `NO_GROUND` or any refusal token. Probe 2
  returned a positive identification rather than reaching for an escape hatch — consistent with
  002F's diagnosis that the token, not the image, drove A1's probe-2 behaviour.
- **Amendment 2 was honoured.** `reproduction_vs_depiction: depiction` is recorded in the manifest
  with a note on why.
- The portfolio's factual error about the fixture was surfaced and reported rather than quietly
  worked around or silently "corrected" by swapping fixtures.
- The budget held at 2 calls with a 25 s throttle. No retries; no provider failures.
- Production was read, never written. Nothing was graduated; both findings sit at SPARK.
- The temptation to fix the detachment — or to start circulation work to date it — was declined as
  out of scope.

## A note on what A2 says about R5 as a family

R5 is framed as *sensory disagreement*, which presumes two channels with standing. This fixture
delivered something else: one channel out of its domain. That is arguably a **better** result than
the planned one, but it means A2 did not really test what R5 was designed to test. If the R5
family matters, it needs a fixture where both channels are competent and still disagree — a
genuinely ambiguous boundary, not a segmenter guessing. Recommended in the final report as an
adjustment to A3's planning inputs rather than a re-run of A2.
