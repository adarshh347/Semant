# Foundry Critique — FS-004-communication-quality

**Sandbox:** FS-004-communication-quality · **Axis:** communication-quality · **RESEARCH-ONLY**

> The critique argues against the run's own score. A cycle with no correction is either genuinely
> clean or insufficiently adversarial — and this document must say which.

---

## 1. The strongest case against the result

**A and B are not comparable, and the run's headline depends on comparing them.**

R1 ("the denominator is the mechanism") rests on treating two sentences as instances of one class —
"reporting that something is missing". They are not the same job:

- **A** reports a *specific failure* about a *specific object the user is looking at right now*: this
  percept's grounds are gone. It has a natural denominator because a percept cites a countable number
  of grounds.
- **B** is a *collapsed-drawer summary of a log*. Its job is to indicate whether opening the drawer is
  worthwhile. "N recorded" has no obvious denominator — recorded **out of what**? Runs that were never
  attempted are not a denominator; they are not a number at all.

If B has no available denominator, then R1 is not a finding about communication. It is an artifact of
picking one sentence that had a countable base and one that did not. **The score never checks whether
B *could* carry a denominator**, and that gap is its main defect.

There is a partial defence, and the score should have made it: B *does* have a countable base for the
distinction it discards — `partial` / `timed_out` / `stale` **out of** `recordedCount`. That is "2 of
5 incomplete", and it is exactly what HW-S1's E5 proposes. So the criticism lands on the *denominator*
framing while the underlying observation (B throws away a distinction it holds) survives.

## 2. Deflationary reading

**The run restated HW-S1 with a rubric attached.**

Strip it down: (a) the rail's summary hides non-nominal states — **HW-S1 §1.2 and E5 already say this,
in more detail, with line numbers**; (b) A2R's note is good — **A2R already says this, and verified it
in a browser**; (c) the model overclaims — **spark-10 and HB-010 §7 already established this**.

FS-004 contributed the *table*. A deflationary reader would say the table is presentation, not
discovery, and that a five-column rubric applied to four sentences is a rubric performing rigour on a
sample too small to constrain it.

**This reading is strong and I do not think the run defeats it.** The genuinely new content is R2
(honest internals / mute surface) and R5 (everything closes) — two reframes across sources that had
not been read together. Reframes are worth something. They are not measurements.

## 3. Confounds

- **Sample selection is the whole result.** I chose four utterances, and I chose them knowing the
  argument I expected. A different four — error toasts, empty states, loading copy, the `pc-reason`
  sentence that does not yet exist — could easily produce the opposite picture.
- **Two of four are not user-facing.** C is an internal audit rule; D is model output. The run's
  claims about "how Semant speaks" therefore rest on **two** sentences, and the table's four rows
  create an impression of a larger base than exists.
- **`invites_return` is inferred from text with no reader.** It is the dimension carrying R5, the
  run's most interesting claim, and it is the least observed. The score marks this; the marking does
  not make the inference safer.
- **Non-blind, single analyst, self-designed rubric.** Third consecutive lane with this confound.
- **Cross-lane contamination.** R5's link to FS-001 arrived because I wrote FS-001 first. Same
  sequence-confounding the FS-002 critique flagged. **Three lanes, one analyst, one order — the batch
  cannot rule this out and should stop claiming cross-lane insights are independent.**

## 4. Method corrections

**Correction 1 — R1 is downgraded.** "The denominator is the mechanism" overreaches. The defensible
claim is narrower: **B discards a distinction it already computes.** Whether the fix is a denominator,
a status word, or something else is a design question this run cannot settle, and framing it as "the
mechanism" pre-decides it. §1 supplies the reasoning.

**Correction 2 — the run should not have scored D on the same table as A and B.** The score's own §5
names this as `analogy_overreach` and then does it anyway. A generated sentence and a designed
sentence are different objects; putting them in one table invites reading D's `inverted` as
commensurable with A's `tracks`. **D belongs in a separate register**, and its only legitimate role
here is as the failure the product does not guard against (R4) — which does not require scoring it.

**Correction 3 — "exactly one render-verified honest sentence" (R3) is unverified as a count.** I did
not enumerate the product's copy. I enumerated the copy *the research record discusses*. There may be
honest sentences in the app that no rehearsal has ever mentioned. The claim should read: **exactly one
in the research record.**

**Does an earlier conclusion fall?** No. A2R, HW-S1 and spark-10 are all restated, none contradicted.
This run adds no evidence that would move any of them.

## 5. What would kill this finding

- **An enumeration of the product's actual user-facing copy.** If it turns out there are a dozen
  well-formed honest sentences the research record never discussed, R3 collapses and R2 weakens
  sharply. This is a bounded, read-only inspection — and **it is outside this sandbox's declared
  inputs**, so FS-004 cannot perform it. Same structural limit FS-001 hit.
- **Showing B *cannot* carry the partial/timed_out/stale distinction** without opening the drawer —
  e.g. because the states are not known until the payload is fetched. That would make B's silence a
  consequence rather than a choice, and R2's "honest internals, mute surface" would lose its edge.
- **One user observation.** Any evidence that A reads as an error message rather than a qualification
  would kill R5's optimistic half and, incidentally, kill spark-FS001-03.

## 6. Declared weaknesses

- **n = 4 utterances; 2 user-facing.** The smallest sample of the three lanes.
- **0 observed renderings** — everything inherited or described.
- **The load-bearing dimension (`invites_return`) is inferred, not measured.**
- **All three findings restate existing documents**; the contribution is arrangement.
- **The run cannot enumerate its own subject matter** (§5) inside its declared boundary.

## 7. Recorded discomfort

R2 — "honest internals, mute surface" — is the sentence I am most pleased with and most suspicious
of. It is elegant, it unifies two sources, and it is exactly the shape spark-10 describes: a claim
pitched at an altitude where the available counter-evidence cannot reach it. What would falsify
"honesty is implemented one level below where it is spoken"? I cannot state a clean test, and **a
claim I cannot falsify is one I should hold more loosely than its phrasing suggests.**

Second discomfort: withholding the rewritten rail summary (score §8) was correct by the manifest, but
I noticed I wanted to write it *badly*, and that the wanting was about craft satisfaction rather than
research value. Recording that, because the next session will feel it too.
