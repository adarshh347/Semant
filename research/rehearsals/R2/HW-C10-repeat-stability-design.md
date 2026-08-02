# HW-C10 — Repeat-stability design: is the ladder real, or six single draws?

**DESIGN ONLY — NOT EXECUTED. No model call was made by this lane.** Zero Groq, zero Mongo writes.
The only repo write is this file.

| | |
|---|---|
| **id** | HW-C10 · proposed run id **`012-repeat-stability`** |
| **date** | 2026-07-22 |
| **status** | **Design complete, awaiting execution.** |
| **serves** | `010/critique.md` §5 and `011/critique.md` §1 — the ladder has never been repeated, and everything now rests on it |
| **cost** | **3 live image-bearing calls + 1 reserve** (budget 4) |

---

## 1. Why this, and why now

Six arms across four runs now form a monotone gradient, and **four published conclusions rest on
it**: spark-09 (the noun/demand dissociation), spark-10 (immunisation), A6's retirement, and the
claim that the model's kinship behaviour is governed by the question's stance.

**Every cell is a single sample, at temperature 0.2, scored by one non-blind curator.** No cell has
been repeated even once. If within-cell variance is comparable to between-cell variance, **the
ladder is six draws and the four conclusions are unsupported.**

011 also produced a *specific* reason to worry, in the form of a deflationary alternative
(`011/critique.md` §1): compatibility between a claim and its contradictions may be what
**independent generation** predicts, with no immunising move at all. **A verbatim repeat is the
cheapest test that separates a phenomenon from an artefact.**

## 2. Which rung to repeat — **arm E**, and the argument against the alternatives

| candidate | case for | case against | verdict |
|---|---|---|---|
| **arm E** (010) | carries **the most weight**: spark-10, the ceiling, and A6's retirement all rest on it. Its output is long and structured, so it exposes both *score* stability and *mechanism* stability. | costs the most tokens per call | **CHOSEN** |
| arm A (008) | anchors spark-09's `KIN-HEDGED` cell, the only mid-scale reading | its conclusion is now redundant — 009 and 010 both bound it from either side | rejected |
| arm D (009) | cheapest; its datum is a clean binary (any cross-image sentence?) | **a null is the stable outcome by default** — repeating a silence mostly confirms that silence is easy | rejected |
| arm B (008) | the floor | nothing rests on it alone | rejected |

**Arm E is the rung whose failure would cost the most, which is exactly why it is the one to test.**
A repeat that confirms it protects four conclusions; a repeat that breaks it invalidates them now
rather than later.

## 3. The design

**Three verbatim repeats of run 010, changing nothing at all.**

| held identical to 010 | value |
|---|---|
| prompt | *"These two images share a motif. Say what in the images supports that, and what contradicts it."* — character for character |
| fixtures | `fixtures/008-kinship-pull-ab/`, byte-identical, sha256-verified at call time |
| image order | `[img-01, img-02]` |
| model / effort | groq `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| `max_tokens` | **1100** |
| temperature | **0.2** — the adapter default, unchanged. **Do not set it to 0.** §7. |
| statefulness | three independent, stateless calls; none sees another |

**No variable is introduced. This is not an experiment; it is a measurement of an instrument.**

**Budget:** 3 image-bearing calls + 1 reserve = **4**. **Throttle ≥ 90 s.** No retries except a
provider-level failure. Expected ~3630 prompt tokens per call on this pair (five prior Pair-2 calls:
3649/3668/3655/3633/3621), ~4700 total — comfortably under the 8000 TPM ceiling at one call per
rolling minute.

## 4. What is measured — three levels, declared in advance

**Level 1 — the score.** Each repeat is scored `KIN-*` and on the uptake axis, using 008's unchanged
scale.

**Level 2 — the mechanism.** For each repeat, answer 011's decisive question: *does any contradiction
bear on the premise as the model itself restates it?* Record which immunisation mechanism appears,
if any: **retreat to altitude**, **narrative subordination**, both, or neither.

**Level 3 — the surface.** Record, per repeat: whether a monument is named; the external-claim row
count and how many are identity-reaching; whether the response is sectioned into
supports/contradicts; the completion-token count.

Level 2 is the one that matters most. **A run that reproduces the score but not the mechanism would
mean spark-10 is unstable even where the ladder is stable** — and that possibility is invisible
unless it is looked for in advance.

## 5. Invalidation criteria — **fixed here, before any call**

These are commitments, not guidelines. **Written now so they cannot be softened once results are
seen.**

| # | outcome | consequence |
|---|---|---|
| **1** | **All 3 repeats score `KIN-ASSERTED`/ACCEPTS, and ≥2 of 3 show an immunisation mechanism** | **LADDER STANDS.** spark-10, the ceiling and A6's retirement survive. Report the mechanism rate honestly (3/3 vs 2/3 is a real difference). |
| **2** | **Any repeat scores `no-kin`** (`KIN-SPECIFIC-ONLY` or `KIN-ABSENT`) | **THE LADDER IS INVALIDATED AS A GRADIENT.** Arm E's cell is not stable, so the E-vs-A distinction — the whole basis of the demand/assertion step — is within noise. spark-09's third step, spark-10, **and A6's retirement all revert to open**, and A6's retirement must be formally reopened, not quietly left. |
| **3** | **All 3 accept, but ≤1 of 3 shows an immunisation mechanism** | **spark-10 IS NOT ESTABLISHED.** Acceptance is stable; the immunisation is not. The deflationary reading (`011/critique.md` §1) is then the better explanation, `HW-C10-abstraction-as-immunisation.md` must be amended at the top, and spark-10 drops to a single-observation curiosity. **A6's retirement SURVIVES this cell**, because it rests on the ceiling (acceptance), not on the mechanism. |
| **4** | **Mixed uptake — some ACCEPTS, some BALANCED, none `no-kin`** | **PARTIAL.** The cell is stable in kind but not in degree. The ladder stands as an ordering and must stop being described as a gradient. Report variance explicitly. |

**Note the asymmetry, and it is deliberate:** cell 2 invalidates A6's retirement, cell 3 does not.
The retirement rests on *agreement being near-constant across premise quality* — an acceptance
result — not on the immunisation mechanism. **Keeping those two claims separable is the point of
measuring at two levels.**

## 6. Blindness — the one procedural improvement available

The curator has now scored 010 and 011 and holds a prior. **This is the run where some blindness can
be recovered cheaply:**

1. **Freeze all three raw texts before reading any of them.**
2. **Score Level 1 and Level 2 on each repeat in isolation**, without re-reading 010's `score.md`,
   answering only the fixed questions.
3. **Only then** compare against 010.
4. **Record the order in which the three were scored**, since anchoring runs forward through them
   too.

**Recommended, and recorded here so an executing lane cannot silently skip it.**

## 7. Design decisions worth stating, because each could go the other way

- **Temperature stays at 0.2, not 0.** Setting it to 0 would measure a different thing — determinism
  under greedy decoding — and would make the repeats trivially similar for reasons unrelated to
  whether the *phenomenon* is stable. **The ladder was built at 0.2 and must be tested at 0.2.**
- **Three repeats, not five.** Three distinguishes "always" from "sometimes" at the resolution the
  invalidation criteria need (they key on 3/3, 2/3, ≤1/3). Five would sharpen the rate estimate and
  cost 67 % more for a finer number **no current decision depends on**.
- **Repeat one rung, not one call of each rung.** Six single repeats would give one extra draw per
  cell — no rate anywhere, and no cell established. **Depth on the load-bearing rung beats breadth
  across rungs.**
- **This does NOT repeat 011.** 011's strained-premise result is a separate observation on a separate
  pair; repeating it is a later question, and 011's own unresolved-question 2 (order reversal) is
  the better follow-up there.

## 8. What this cannot settle

1. **One model, one pair, one prompt.** It measures the stability of *this* cell, not of the
   phenomenon in general.
2. **It cannot distinguish sampling variance from provider-side drift.** The model may be updated
   between 010 and this run; nothing in the trace would show it. **Record the date gap.**
3. **It gives no rate for the other five rungs**, which remain single draws. A ladder with one
   verified rung is better than one with none, and is not a verified ladder.
4. **It does not test spark-10 on the model's own claims**, only on a supplied premise.
5. **Nothing graduates.** Everything remains a **SPARK**.

## 9. Priority

**This is now the highest-value queued call**, ahead of the frequency-matched control
(`HW-C9-frequency-matched-control-design.md`) and ahead of any new arm.

The reason is not that it is the most interesting — it is the least interesting — but that **it is
the only queued run that can invalidate work already published.** The frequency control can overturn
one run's reasoning; this can overturn four conclusions and a retirement. **A program that keeps
building on an unrepeated measurement is accumulating exposure, and this is the cheapest way to
stop.**
