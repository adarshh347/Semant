# Horizon Brief HB-002 — Horizon Weave cycle 2

**Cycle:** 2 · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** A2R (recall evidence honesty) — a **fix**, not a rehearsal.
**Scouts:** L2 Atlas/Codex prototype brief · L3 interface rotation map · L4 next-rehearsal directive.
**All four lanes complete and paused.** No rehearsal executed this cycle. Nothing pushed.

---

## 2. What changed

**The most serious finding of the whole program was confirmed and fixed in one lane.** S1's claim
was right: recall built its script from a raw existence lookup, so a percept whose evidence had been
destroyed still played a full performance and then asserted its caption over an empty image. For
`pctx_mrqp950d_0` ("the upper head") that was **100 %** of the performance. See
`A2R-recall-evidence-honesty.md`.

**One surface now tells the truth**, and only one. The Differential recall path reports detached
evidence beside the caption. Chiasm's chip path, `RefPicker`, and Aletheia were explicitly **not**
fixed and must not be assumed fixed.

**Atlas and Codex were re-framed away from their vault prose** — Atlas as a comparative
evidence-health view rather than a narrative canvas, Codex as answering one temporal question rather
than being a multi-page container. Both remain prose; neither exists in code.

**The next rehearsal is decided and de-risked:** A4 on an aniconic tile revetment, chosen partly
because it directly tests spark-06.

## 3. Method corrections

**(a) A parameter name lied, and the lie was load-bearing.** `buildRecallScript(percept,
resolveGround)` received `groundById`. The name asserted a resolution the value never performed, and
nobody caught it because the render *did* resolve — so the failure was invisible except as absence.
Renamed to `lookup`. **Where a name promises a guarantee, check the caller.**

**(b) Two counts of the same phenomenon disagreeing is a reporting bug, not a data fact** —
carried from A2S and applied again here: the script counted grounds the renderer refused to draw.

**(c) L4 overturned two of S4's conclusions on new evidence.** S4's A6 "Pair 1" rhyme is weaker
than claimed (the Nataraja shadow is an arch, not a radial circle; the Duomo frame's lower half is a
Madonna and five saints), and S4 missed a reuse conflict — `695be78f` is the *same sculpture* as
A3's committed neighbour `695be790`. **A scout's output is an input, not a verdict.**

**(d) A5's ambiguous id was resolved by bytes, not by guessing:** `…5fa` and `…5fb` are
byte-identical under different Cloudinary URLs.

## 4. Data integrity findings

No new corpus scan this cycle. The four detached grounds on two posts are **unchanged and
deliberately unrepaired**. What changed is that one surface no longer misrepresents them.

**The escalation matters for spark-03:** the problem was never merely "nothing announces it". The
system *performed* the missing evidence convincingly. That is a stronger argument for notification —
and a stronger argument against auto-repair, which would have hidden it.

## 5. Model / runtime constraints

Unchanged from HB-001, plus one correction carried from A3: **Groq charges ~2400 tokens per image
regardless of pixel dimensions.** A 3-image call needs ~7200 of the 8000 TPM ceiling, so
`max_tokens` must be trimmed and a multi-image call needs 65–75 s of clearance. **This is why A4 is
attractive: one image at native resolution with `max_tokens ≥ 1200`**, repairing A3's 256 px /
380-token confound.

## 6. Candidate sparks

No new sparks. **spark-03 strengthened and sharpened** (see §4). **spark-06 is now the deciding
variable for A6** — L4 chose A4 partly because an aniconic frontal arched wall is the sharpest
available test of whether the model invents faces. Either outcome is useful: n=2 forces A6's
redesign; a clean result bounds the spark and makes A6's refusal test credible.

## 7. UI / product opportunities

L3 mapped eight surfaces and returned only **two NOWs**, both narrow: the Differential replay guard
(now addressed by A2R) and a silent-at-zero evidence count in Chiasm's already-empty
`panel-actions` slot. Everything else is LATER or NEVER.

Three NEVERs argued rather than assumed — chief among them that the Vision Activity Rail's current
placement should be **defended, not promoted**: with one run corpus-wide, opening it by default
shows rows of "No recorded activity" and trains dismissal.

L3's own best finding is an argument against building: two of its three cheapest experiments render
*nothing*, because the corpus cannot feed a display. L2 reaches the same conclusion independently —
"Atlas today is a table of eleven rows, two of them interesting; that is not a surface, it is a
paragraph."

## 8. What the orchestrator should study deeply

**(1) The repair fork — still unchosen, now more urgent.** A2R proved the system can display absent
evidence convincingly. That raises the stakes on tombstoning-vs-notifying without answering it.
*Read:* `A2R-recall-evidence-honesty.md` §"What this does NOT fix", `A2S-detached-ground-sweep.md`.

**(2) Whether corpus density is now the binding constraint on everything.** Two independent scouts
concluded, separately, that the honest move is *not to build a surface yet*. 11 annotated posts,
7 percepts, 1 vision_run. *Read:* L2 §"too small", L3's emptiness section.

**(3) A6's five decisions.** L4 reduced them to clear questions with recommendations, and reversed
S4 on which pair to use. A6 cannot run until these are answered. *Read:*
`HW-L4-next-rehearsal-directive-draft.md`.

**(4) Whether the A2R fix should propagate.** Chiasm's chip path, `RefPicker`, and Aletheia have the
same shape of problem. Each is a separate, small, reversible change — but each is also a decision
about how loudly the app should admit its own gaps.

## 9. Next execution expectation

**Next primary action: execute A4** (R8 Surface Becoming Structure) on `695be784`, the turquoise
tile revetment, as run `005-surface-becoming-structure`. One image, native resolution,
`max_tokens ≥ 1200`, ≤2 live calls, no named refusal token, per-image `reproduction_vs_depiction`.

**Must not happen next:** A5 or A6 (A5 is fixture-ready but not design-ready; A6 is blocked on five
decisions); any repair of detached grounds; any Atlas/Codex implementation; any new production
entity, route, or collection; any push or merge.

## 10. Artifacts

`R2/A2R-recall-evidence-honesty.md` · `R2/evidence/A2R-detached-recall-honest.jpg` ·
`R2/HW-L4-next-rehearsal-directive-draft.md` · `Build specs/HW-L2-atlas-codex-prototype-brief.md` ·
`Findings/HW-L3-interface-rotation-map.md` · this brief.
Code: `frontend/src/differential/recall.js`, `DifferentialWorkspace.jsx`,
`DifferentialWorkspace.css`, `recall.test.js` (+5 tests, 96 pass).
