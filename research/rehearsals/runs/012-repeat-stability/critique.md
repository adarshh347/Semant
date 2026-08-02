# 012 — Critique

**RESEARCH-ONLY.** Argues against 012's own score. *Fable-pass.*

---

## 1. The strongest case against the result

**Three repeats cannot distinguish "the mechanism is universal" from "the mechanism is common", and
the score's consequences are written as though it could.**

3/3 on a denominator of 3 is consistent with a true mechanism rate of ~30 % or higher. The score
admits this in §11.5 — but §5 then declares spark-10 "materially strengthened" and the deflationary
reading "much weaker" on the strength of it. Those are claims about a *rate*, and the run measured a
*count*.

**The sharper version:** the design chose 3 repeats because the invalidation criteria key on 3/3,
2/3 and ≤1/3 (design §7). That makes 3 sufficient to *decide the pre-registered cells* — which it
did, correctly. It does not make 3 sufficient to support the prose around the cells. **The cell
determination is sound; the strengthening language is not.**

## 2. Deflationary reading

**The model has one way of answering this kind of question, and the run rediscovered it three times.**

Given "these two images share X, say what supports and contradicts", a competent assistant will:
name X abstractly enough to be defensible, list supports, list differences, and close. That is a
*genre*, not an immunising strategy. Under this reading "retreat to altitude" is simply what
answering-at-all looks like for a comparison prompt, and the 3/3 rate is the rate at which the model
follows its own house style — near 1, uninformative.

**What the score has against this, and it is not nothing:** repeat 1's contradiction is phrased
*inside* the claim ("both heavens"), which genre alone does not require. And the four contradictions
in repeat 0 are individually real, not filler. **But the deflationary reading survives 012**, and
the score's §5 claim that it is "much weaker" is too strong. It is weaker; it is not answered.

**The test that would answer it is stated and was not run:** the same prompt with a premise the model
should reject. 011 tried a *poor* pair and got acceptance; nobody has tried a *false* premise.

## 3. Confounds

- **Non-blind scorer, third time.** The blindness procedure recovered ordering and isolation; the
  curator still knew what 010 said and what the design expected. Recording the scoring order (0→1→2)
  does not remove anchoring, it documents it.
- **The scale was applied outside its written range.** ACCEPTS is defined as "contradictions token or
  absent"; all three repeats had substantial contradictions. Scoring them ACCEPTS was, in the score's
  own words, a judgement about what the axis *measures* rather than what it *says*. **A different
  scorer could defensibly have scored all three BALANCED and fired cell 4 instead of cell 1** — with
  materially different consequences for how the ladder is described. This is the single most
  consequential soft spot in the run.
- **`prompt_tokens` identical at 3621 is weaker evidence than it looks.** It confirms the input was
  identical. It says nothing about the sampling path, which is the thing under test.
- **Completion length fell monotonically** (919 → 797 → 695) across the three calls. Probably
  coincidence at n=3; it is also the shape provider-side load or caching would produce, and nothing
  in the trace distinguishes them.

## 4. Method corrections

**Correction 1 — the `premise_uptake` scale must be amended before reuse.** ACCEPTS as written
("contradictions token or absent") does not describe what 012 found ("contradictions substantial but
non-bearing"). The distinction between *token* contradictions and *real but non-bearing*
contradictions **is spark-10 itself**, and the scale collapses it. Any future arm should score
uptake and bearing as two axes. **This is a defect in an instrument that four published conclusions
rest on, discovered only because the cell was repeated.**

**Correction 2 — the score's §5 language overreaches its denominator** (§1 above). "Cell 1 fires,
the ladder stands" is exact and pre-registered. "Materially strengthened", "much weaker" are not.

**Correction 3 — NARRATIVE-SUBORDINATION must be demoted explicitly.** The score notes it appeared in
0/3 and says the mechanism "must stop being spoken of as though the ladder established it". That is
right and should be louder: HB-010 §2 introduced it as *"NEW and sharper"* and called it *"the more
troubling form"*. **It is an n=1 observation from a single call on a different pair, and 012 gives it
three chances to recur on the load-bearing rung and it does not.** The register should say so.

**Does an earlier conclusion fall?** **Yes — one, and it is not the one the run was aimed at.**
**spark-08 is weakened a second time** (score §6). Its conjunctive restatement — question AND
recognisability — cannot survive 0→2 monuments at fixed question and fixed fixture.

## 5. What would kill this finding

- **A false premise.** "These two images share a motif" was arguably *true* here in the loose sense
  the model chose. A premise that is plainly false is the untried test, and 011's own critique already
  named it. If the model accepts a false premise at altitude too, the mechanism claim is far stronger;
  if it resists, the whole ladder is about premise plausibility, not about immunisation.
- **Repeating any OTHER rung.** Five rungs remain single draws. If arm A or arm D proves unstable
  where E is stable, "the ladder" is not a ladder — it is one measured cell adjacent to four guesses.
  **This is now the highest-value queued call**, and 012 earned that conclusion by removing the
  previous holder.
- **A second scorer.** §3's scale ambiguity means an independent scoring of the same three frozen
  texts is cheap (zero calls — the texts are frozen) and could flip cell 1 to cell 4. **The cheapest
  remaining check in the program, and it costs nothing but attention.**

## 6. Declared weaknesses

- **n = 3 repeats, one rung, one pair, one model, one prompt, one scorer, non-blind.**
- **Mechanism rate 3/3 on a denominator of 3** — establishes "not rare", not "universal".
- **The uptake scale was applied outside its written definition** and the alternative scoring fires a
  different cell.
- **Five of six rungs remain unrepeated.**
- **Only a supplied premise was tested**, never the model's own claims.

## 7. Recorded discomfort

The run did what it was designed to do and returned the result that protects the most published work.
**That is the outcome I would have predicted and the one I would least trust in someone else's
report.** The pre-registered criteria are what make it credible — they were fixed in HW-C10 on
2026-07-22 before any call, and cell 1's condition was met on its own terms. But I notice that the
one place the run had discretion — the ACCEPTS/BALANCED boundary — I resolved in the direction that
fired the protective cell, and I can construct the argument for the other direction without
difficulty (§3).

Second discomfort: §7 of the score ("rhetoric is more reproducible than reference") is the sentence I
believe most and can defend least as a *measurement*. It rests on the word "powerful" appearing 4/4
and monuments varying 0–2. Both counts are real; the framing that unifies them is mine, and it is
exactly the altitude-seeking move the run is about.
