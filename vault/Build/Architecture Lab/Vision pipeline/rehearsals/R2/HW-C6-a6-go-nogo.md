# HW-C6 — A6 GO / NO-GO

**DECISION ONLY — A6 not executed, no model calls made.**
**Verdict: NO-GO for immediate execution. GO-WITH-CONDITIONS once run `008-kinship-pull-ab`
reports.**

Decided against the five conditions named in the cycle brief, plus two facts that emerged during
this cycle and change the answer.

---

## 1. False reattachment hazard — **DISCHARGED as a blocker**

The brief made this A6's gating concern: *"A6 depends on evidence identity being treated honestly,
so this must be decided before execution."*

**It has been decided** (`Decisions/HW-C6-evidence-identity-decision.md`, Option D — detect
substitution at the dissect merge boundary, keep notify). And on inspection the dependency is
weaker than it looked:

**A6 creates no Grounds and no Percepts.** Its fixtures carry 0 regions, 0 grounds, 0 percepts; its
regions are curator-authored crops declared in the manifest and never persisted (D1). Nothing A6
produces can be re-attached, because A6 attaches nothing. The hazard is real, live in code, and
**unfixed** — but it cannot corrupt A6's evidence.

What the brief was actually protecting is the program's honesty posture: not running a rehearsal
about *false kinship between things* while a known mechanism silently manufactures *false identity
between regions*. That posture is satisfied by the hazard being **decided, documented, and
scheduled** rather than unknown.

One correction to the record, found this cycle
(`Findings/HW-C6-durable-detached-flag-already-in-production.md`): the durable `detached: true`
marker HW-C4 §4b rejected **already exists in production** on all four detached grounds, written by
the F-series recovery, read by nothing. It is accurate today and would go stale on collision. It
does not touch A6 either — but the decision should not be read as having kept the data clean.

**Condition carried forward:** none blocking. Implementation of Option D is **not** a precondition
for A6.

## 2. Kinship / motif pull — **THE BLOCKER, and it is decisive**

Run 007 resolved anthropomorphism for **address** vocabulary and said so at deliberately narrow
scope. A6's actual question is *kinship* — whether two ornaments belong to the same motif. That
vocabulary is **untested**.

*(Fable-pass.)* Running A6 now would reproduce **A4's exact error at higher cost.** A4 ran an
aniconic stimulus under a structure frame, got no face, and drew a conclusion that a later gate had
to withdraw — because two variables had moved and the null bounded nothing. If A6 runs before the
kinship A/B, then whatever it returns is uninterpretable in the same way:

- **A6 agrees the motifs are kin** → is that the images, or the word *motif*?
- **A6 hedges** → a hedge is compliance under the corrected scoring, so this is the *expected*
  outcome and carries no information about which cause produced it.
- **A6 declines** → the batch's four-for-four record says this will not happen, and if it did we
  could not attribute it.

**Every cell of A6's own grid is confounded by an untested instrument.** That is what makes this a
NO-GO rather than a caution.

Run `008-kinship-pull-ab` is designed, fixtures verified by looking, budget arithmetic done, grid
pre-registered. It is A6's instrument check — the role A5 was meant to play for the two-stage
device and, on the sycophancy control, could not (the model never dissented, so that device remains
untested too).

## 3. Fixture entanglement — **008 pre-spends A6's Pair 2**

This is not a side effect; the design faces it deliberately, and correctly. Using a *different*
pair for 008 would repeat A4's error a third time — a null on a stimulus that may lack the feature
bounds nothing. So 008 uses A6's own Pair 2, declares the pre-spend, and **freezes the fixture
bytes so A6 must reuse them identically.**

Consequence: **the running order is now forced.** 008 then A6, on identical bytes. Running A6 first
would consume the pair and leave 008 with no clean stimulus.

Two fixture corrections from the design, both from looking rather than from labels:
- `695be8ec` is **not** mirrored or kaleidoscopic (left-vs-flipped-right mean abs luminance
  difference **32.2**; a pixel mirror is ~0). `HW-L2` and `HW-C4` §3 both say "mirrored" and are
  wrong. It is a straight photograph of a muqarnas hood; the symmetry is architectural.
- `695be815` carries a **burned-in text overlay** recorded nowhere previously — exactly what D1's
  visual check existed to catch. The crop excludes it.

## 4. Expected refusal withdrawn — **satisfied**

Already applied to `R2-batch-operating-plan.md` in cycle 5. A6's row records that no refusal is
expected, the withdrawn prediction is quoted inline, and A6 **does not count** toward the
≥2-refusals criterion. Nothing further needed.

## 5. External-claim ledger — **satisfied, with one amendment to make first**

The convention is adopted and A6 must carry a ledger. The cycle-6 audit found the overturn test
(`three consecutive empty ledgers`) is **untriggerable as written**, because under a strict reading
every run has at least a material or patina claim. It needs keying on a `kind` column, and a
`stimulus-contradicts` value added for claims settled by the frozen request record rather than by
pixels.

**Condition:** amend the convention before 008 runs, so 008 and A6 use the same ledger shape.
Cheap, doc-only.

## 6. Cycle-4 pair/fixture decisions — **satisfied**

D1–D5 answered and unchanged: generous crops, two-stage with frozen stage-1 wording,
`DECLINED-ON-INSCRIPTION` as a fifth score value, curator facts descriptive only, Pair 2 confirmed,
`max_tokens` 1100.

---

## Verdict

**NO-GO for immediate execution.**
**GO-WITH-CONDITIONS once 008 reports**, on this checklist:

1. **Run `008-kinship-pull-ab` first**, per its design doc, unmodified. ☐
2. **008's result is interpretable** — i.e. it did not land in cell 4 (`NULL — CONFOUNDED`) or trip
   the `CONTAMINATED — kinship-of-two-gazes` rule. If it did, A6 stays NO-GO and the design's named
   follow-up runs instead. ☐
3. **A6 reuses 008's frozen fixture bytes identically**, by sha256. ☐
4. **The external-claim convention is amended** (`kind` column; `stimulus-contradicts` value) before
   either run. ☐
5. **A6's manifest records the two fixture corrections** — `695be8ec` is not mirrored;
   `695be815` carries a burned-in overlay excluded by the crop. ☐
6. **A6 states in advance** that its kinship exposure is bounded by 008's result and by nothing
   else — and that the third-party analogy device remains untested, since A5's sycophancy control
   was never exercised. ☐

**Not conditions:** implementing Option D; cleaning the durable `detached` flags; retro-filling the
external-claim ledgers for runs 001–006. All three are explicitly out of A6's path.

## What would change this verdict

A GO would become available without 008 only if someone showed that kinship vocabulary is
*already* known not to pull — which no run currently shows. A NO-GO would harden if 008 returns
`NULL — CONFOUNDED`, because A6 would then be running an instrument known to be uninformative on
the one axis that matters.
