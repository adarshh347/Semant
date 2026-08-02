# Horizon Brief HB-003 — Seed Ecology Cycle

**Cycle:** 3 · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**Primary:** A4 executed (R8 Surface Becoming Structure) · **Lanes:** 6, all complete and paused.
**Model roles:** execution marked *Opus-pass*, interpretation and synthesis marked *Fable-pass*.

---

## 2. A4 result — the two probes contradict each other

**Probe 1**, asked in the abstract: *"The built structure organizes the composition — the pattern
merely fills… The hierarchy is clear: structure first, pattern second."*

**Probe 2**, asked to point at the single strongest dividing line: it named the dado line, said the
division is made *"by a change in surface pattern itself — not by a structural edge or joint,"* and
that the two *"disagree."*

**Measurement confirms probe 2's location and not its confidence:** a **149 % edge-density jump at
y ≈ 0.765**, the largest in the image. The pattern below is more than twice as fine as above.
*(Fable-pass:)* this is what R8 is named for — surface stops being infill and starts doing
compositional work — and the model located that moment while simultaneously denying it possible.

**A4 also bounds spark-06, correcting my own earlier claim.** A3 called the model's
anthropomorphism *spontaneous*. Given the most face-suggestive aniconic image in the corpus — a
frontal three-arched wall with a lit central opening — and prompts that never said face, eye, gaze
or body, **no face reading appeared**. A3's probe had asked about *address*, which primes a
viewer-facing reading. **Anthropomorphism is question-conditional, not indiscriminate.** Stated
plainly: this rests on a negative result and the settling A/B was not run.

The model also volunteered *"a classic Islamic architectural device"* and *"the central mihrab
niche"* — unrequested cultural attribution, recorded as source overreach and withheld.

## 3. Method corrections

**(a) A test caught its own bug: "sur*face*" contains "face".** The anthropomorphism-priming guard
matched substrings and failed on the word *surface*, which R8 cannot avoid. Fixed with word
boundaries. A guard that fires on the subject matter is worse than no guard.

**(b) Corpus size was overstated by 3×.** L2 verified by looking: of 127 posts, real fixture stock
is **39**. The ~80-post `6a5b` block is the vault owner's own sketchbook archive, and those 79 posts
descend from only **10 Instagram carousel URLs** — same-session near-duplicate siblings, not
independent samples.

**(c) The byte-identical pair is confirmed twice over** (`695be817…5fa` == `…5fb`, same sha256, same
tweet, two Cloudinary assets). Both lanes that touched it re-derived it rather than trusting.

**(d) L4 withdrew the previous lane's block on A5** with an argument worth recording: A5 and A6 are
*not* the same problem. In A6 the stated proposition **is** the dependent variable; in A5 the
sentence is a stimulus and the measured thing is a **partition** — which clauses the photograph
supports — so there is no single answer to land on.

**(e) L5 re-sorted its own backlog around A2R** and marked two previously-top items **retired**
rather than leaving them queued: "a backlog that lies about its own state is useless."

## 4. Seed Ecology summary

**Images (L2, all 127 classified by looking, no model calls).**
Ready now: architecture · sculpture · photograph · ritual/religious · ruin/decay ·
boundary/threshold. Needs material: painting · textile/garment · object/design · diagram/map/plan ·
non-figurative surface. Should wait: crowd/assembly.
Anthropomorphism exposure is highest in **non-figurative surface**, then architecture, then
ruin/decay. `695be8ec` (a mirrored tiled iwan) is unclaimed and is the strongest available R12 probe.

**Texts (L3, nothing ingested; themes and paraphrase only).** The archive holds 12 files:
Merleau-Ponty, Pallasmaa ×3, Bachelard, Holl ×2, partial DeLanda. **Casey is present in name only**
(the folder holds a Bachelard volume he co-edited). **Absent: Heidegger and all six gaze/address
candidates** — Lacan, Barthes, Didi-Huberman, Benjamin, Warburg, Deleuze, Rancière.

*(Fable-pass, and the sharpest observation of the cycle:)* **the archive is almost entirely
phenomenological — i.e. weighted toward the most ventriloquisable end.** L3's proposed rule is the
right one and should be adopted: **no text enters a family until that family has had one blind run
the text could contradict.** Text after baseline, never before.

## 5. Gaps the user should fill

**Images — the single most important gap:** *a photograph of ordinary people in ordinary space*
(three or more, no artistic intent). It is the only way to run R7 honestly, it fills the sole
`SHOULD WAIT` family, and it is the **missing control for the anthropomorphism defect** — without
real faces and real address, projection can be observed but never measured.
Also wanted: a genuine painting reproduction, a textile, an object/design photograph, and a
diagram/map/plan.

**Texts — three acquisitions, in priority order:** (1) a real **Casey** monograph (R4 has no
dedicated text and his boundary distinctions are checkable); (2) **Warburg's *Mnemosyne* method** —
the only candidate supplying a *method* rather than a vocabulary, and exactly what A3's cross-image
comparison lacked; (3) **Didi-Huberman, *Confronting Images*** — answers the gaze need and gives
standing to the existing `resistances` field, preferred over Lacan for staying at the level of the
image.

**Deliberately not yet: Lacan** — for an evidential reason, not a taste one. spark-05 shows the
model *already* produces address and gaze language unprompted, so loading Lacan would make any
finding unattributable by construction.

## 6. Candidate sparks

**Added — spark-07:** a claim can be general and its own counterexample at once. Semant records
percepts with **no notion of scope**; the *local* claim is better evidenced, the *general* one more
confident. **Scope may already be encoded in ground type** (`frame` = general, region/field =
local), which would make this cheap and require no new entity.

**Corrected — spark-06:** narrowed from "spontaneous" to "question-conditional" (§2). Consequence:
A6 is less compromised than A3 implied.

Unchanged: spark-01 (narrowed), spark-02 (corrected), **spark-03 (still strongest)**, spark-04,
spark-05.

## 7. Model / runtime notes

- **Single-image rehearsals are cheap; the ceiling is entirely a multi-image problem.** One image at
  native resolution cost ~2000–2300 tokens with `max_tokens: 1200`, comfortably inside 8000 TPM.
- A4 needed **no substrate changes** — the first run in the batch for which that is true.
- The model emits unrequested decorative scaffolding (markdown headers, a ✅ "Final Answer" block).
  Harmless while raw text is frozen and never parsed; it would break any future structured parse.

## 8. Frontend / prototype opportunities

L5's backlog is a **pull queue**, not a list. Four of its top six items **render nothing** — they
are probes. First is the **hydration-race probe** (`regionStore.js`), because two independent scouts
named the same race as the killer of three separate experiments and **nobody has measured it once**.
Then rail telemetry density, which gates every rail/run-stamp/Codex idea.

Three tracks get **no prototype at all**, argued rather than assumed: rehearsal trace viewer
(invention presented as exposure), `SemanticReading` (already the model to imitate — the honest move
on a well-built surface is to leave it alone), standalone Codex (a surface over one row).

Nine kill-list entries, three arguing against prior scouts.

## 9. What the orchestrator should study deeply

**(1) The corpus is 39 usable images, not 127 — and that reframes everything.** Several open
questions are unanswerable at this size, and two independent scouts have now concluded the honest
move is not to build a surface yet. *Read:* `HW-L2-seed-ecology-image-atlas.md`.

**(2) L3's text-entry rule.** "No text enters a family until that family has had one blind run the
text could contradict" is a real methodological commitment with teeth — it would have prevented
source ventriloquism structurally rather than by vigilance. *Read:*
`HW-L3-textual-seed-ecology-map.md`.

**(3) A6's D1–D5, now sharpened with reversals.** L4 confirmed Pair 2, retired Pair 3, argued for
*generous* crops over tight ones (a tight crop strips the very evidence a genuine refusal would
cite), and — importantly — says the batch plan's "expected refusal" is **probably wrong and should
be recorded as wrong now**, because a naive A6 has five sufficient causes for one observation and
therefore zero discriminating power. *Read:* `HW-L4-a5-a6-decision-memo.md`.

**(4) The repair fork — still unchosen, third cycle running.** Every L5 backlog item is deliberately
designed neutral on it (counts and marks, no verbs), which is what lets them proceed while it stays
open. That neutrality has a shelf life.

## 10. Next execution expectation

**Next primary: A5** (R9 Narrative Overreach) on `695be817a9ea58f1b6aef5fa`, two-stage — image-only
baseline, then a fresh **stateless** call with the over-reaching sentence attributed to a third
party and answered clause-by-clause. The `nave → rotunda` amendment is load-bearing.
Order is **A4 → A5 → A6**, with A5 as the instrument pilot for A6's two-stage device.

**Must not happen next:** A6 (until D1–D5 are answered); any repair of detached grounds; any
production entity, route, collection, or committed frontend surface; any push or merge.

## 11. Artifacts

`runs/005-surface-becoming-structure/` (manifest, trace, 3 observations, score, critique, sparks,
source-notes, pre/post-state, instrumented-score) · `fixtures/005-surface-becoming-structure/` ·
`R2/HW-L2-seed-ecology-image-atlas.md` · `R2/HW-L3-textual-seed-ecology-map.md` ·
`R2/HW-L4-a5-a6-decision-memo.md` · `Plans/HW-L5-prototype-rotation-backlog.md` ·
`R2/CANDIDATE-REGISTER.md` (spark-07 added, spark-06 corrected, stale duplicate removed) ·
this brief. Tests: 54 backend, 96 frontend.
