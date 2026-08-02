# Horizon Brief HB-001 — R2.0 through A3P

**Cycle:** first Horizon Brief · **Date:** 2026-07-21 · **Branch:** `feat/rehearsal-research-r1`
**Covers:** R2.0, A1, A1F, A1R, A2, A2S, A3P · **Commits:** `f93c800` → `044ea24`
**Primary rehearsals executed:** 3 live (A1, A1F, A2) + 1 rendered probe (R2.0). **A3 prepared, not run.**

Written for the orchestrator. Read §3, §4, and §8 if you read nothing else.

---

## 2. What changed

**The rehearsal substrate became real.** R1 left one unmet criterion — a deferred rendered probe —
honestly marked *blocked*, not failed. R2.0 discharged it: in a real browser against real Mongo, a
percept became a chip in the Manuscript and drove recall on the image (recede → grounds highlight →
expression). Zero production mutation. The substrate now also makes bounded live model calls
(`groq_vlm_probe`), freezes them, and proves replay touches nothing.

**Three rehearsals ran and produced three different kinds of result** — which is the point of a
breadth batch: A1 an honest **stall**, A1F a **correction to A1**, A2 a **finding plus two sparks**.
None was a failure, and none was written around.

**The program found a live data-integrity problem it was not looking for.** A2's assigned question
was about sensory disagreement. What it actually surfaced was curator evidence silently destroyed by
re-dissection (§4). This is the most consequential thing the cycle produced.

**Mode-specific score indexing exists.** Instrumented runs are indexed by
`schemas/instrumented-score.schema.json`; the imaginative `virtual-rehearsal-score` protocol was
left untouched rather than widened. The honesty constraints are conditional, not blanket — most
importantly, `replay_live_call_count` is a plain integer so a *violation stays recordable*, and it
is a **verified** replay proof that requires it to be zero.

**The corpus is far thinner than it looks.** 127 posts, but only **11** carry any grounds or
percepts, and there are **7 percepts total**. Almost every rate this program computes has n ≈ 10.

## 3. Method corrections

**This is the section that matters most. Four instruments were wrong.**

**(a) The R0 breadth portfolio's fixture descriptions are unreliable — 3 for 3.** It described A1's
subject as a "five-sculpture collage" (actually a *composite comparative plate*: cut-out heads keyed
onto flat black with captions), A2's as "architecture (wall/floor)" (actually a *close-up of a
carved stone figure*), and A3's as a "garment" (actually an *oil painting*). In every case the
description was inherited from **detector region labels**, not from looking at the image. **Standing
rule now: verify every fixture by opening it.** A region label is not evidence of what an image is.

**(b) A1's grounding probe was a broken instrument, and A1F proved it.** A1's probe 2 offered
`NO_GROUND` as a named reply option. On A1F's control image the same probe returned `NO_GROUND` and
then *contradicted itself in the same breath* — "occupied by a large cross and an ornate marble
wall, **which are depicted content**." The offered token is an attractor. **Amendment: never name a
refusal token in a prompt.** Let refusals be unprompted.
→ **Does A1's stall fall?** No. A1's own critique had already recorded probe 2 as "corroborates; it
does not establish"; the load-bearing evidence was the pixel measurement (59.5 % literal black) plus
probe 1's *unprompted* answer. The result stands; the instrument does not.

**(c) A1's spark-02 was overstated and A1F corrected it.** A1 claimed detection is object-shaped end
to end. False: the Pietà post carries `arch_0 "wall"` and `arch_1 "floor"` — non-figure regions. The
accurate claim is narrower: **detection proposes *things* (figures and surfaces) but never
*intervals*.**

**(d) A2S's first sweep would have given the wrong answer.** It reported only percept-*cited*
detachments, which hid an entire affected post and would have concluded "isolated to A2". Caught
because the ground-level count (4) didn't match the percept-level count (2). **Lesson: when two
counts of the same phenomenon disagree, the reporting is wrong before the data is.**

## 4. Data integrity findings

**Detached curator evidence is real, recurring, and unannounced.**

Definition (ported from `grounds.js :: resolveGround`, not invented): a `region`-type Ground is
*detached* when its `region_id` no longer resolves. `field`/`path`/`boundary`/`frame` carry their own
geometry and are immune. Composites detach only if no member survives and they hold no raw points.

| | |
|---|---|
| posts scanned / annotated | 127 / **11** |
| posts with ≥1 detached ground | **2** |
| reference-based grounds | 11 · **4 detached (36.4 %)** |
| geometry-bearing grounds | 15 · **0 detached** |
| percepts fully unevidenced | **1** |

- `695be786` — percept `pctx_mrqp950d_0`, the curator's own words *"the upper head"*, is **fully
  unevidenced**: both its grounds cite `fine_0`/`fine_3`, replaced by an `arch_*` generation.
- `695be794` — 2 more detached grounds, **uncited**, so no statement was harmed. That is luck, not
  design.

**The clean contrast:** every `field`/`frame` in the corpus survived; over a third of region-adapter
grounds did not. **Nothing announced any of it.** Detachment is already modelled and rendered — the
missing thing is *notification*, not representation.

**Do not quote 36.4 % as a corpus rate.** n = 11. It means "this recurs", not "this happens 36 % of
the time".

**Undated.** There is **1** `vision_runs` document in the entire database, 0 for the affected post.
The telemetry built to make exactly this visible did not exist when it happened.

## 5. Model / runtime constraints

- **`qwen/qwen3.6-27b` on Groq, `reasoning_effort: "none"` is mandatory.** Unset, it emits an
  unclosed `<think>` block that eats the whole `max_tokens` budget (`finish_reason: length`).
  `response_format: json_object` is rejected (400).
- **8000 TPM.** Image calls cost ~900–2100 tokens each here. **Sleep ≥ 20–25 s between image calls.**
  Back-to-back calls have already 429'd.
- **Groq sits behind Cloudflare and bans urllib's default agent** — `HTTP 403 / "error code: 1010"`
  *before* the key is checked. Reads exactly like a bad key or dead model. A `User-Agent` header
  fixes it.
- Budgets held: 2 calls per rehearsal, 6 live calls across the whole cycle, no retries, no provider
  failures. Latency 712–3928 ms.
- **`frontend/.env` pins `VITE_API_URL=http://localhost:8000`** — run the backend on 8000, don't
  edit the user's `.env`.

## 6. Candidate sparks

All **SPARK**. Full detail in the candidate register.

| id | claim | would be killed by |
|---|---|---|
| spark-01 | claims about the *artifact* (plate, crop, compositing, caption) have nowhere to live; every Ground points into the depiction | showing artifact-level claims are rare or expressible today |
| spark-02 *(corrected)* | detection proposes things, never intervals | any detector returning a non-object interval proposal |
| spark-03 | **evidence loss should be announced, not merely survived** | showing detachment is rare in a denser corpus, or that curators notice unaided |
| spark-04 | out-of-domain label collapse ≠ genuine channel disagreement | in-domain fixture showing the same collapse signature |

**spark-03 is the strongest.** It needs no new entity, no schema, no ontology change — the
information already exists in the documents.

## 7. UI / product opportunities *(speculative, none approved)*

Motivated directly by this cycle's evidence:
- **Evidence health is invisible.** A percept can be fully unevidenced and still render normally.
- **The Vision Activity Rail exists but has almost nothing to show** — 1 run in the whole DB.
- **`field` vs `region` grounding has a durability difference no surface communicates.**

Detailed scouting is delegated to the parallel Horizon Weave scouts (frontend, Atlas/Codex);
their findings supersede this section.

## 8. What the orchestrator should study deeply

**(1) Whether detachment gets repaired, and by whom.** *Read:* `R2/A2S-detached-ground-sweep.md`,
`003-sensory-disagreement/score.md`, `grounds.js :: resolveGround`. This is a genuine judgement
call, not a technical one: tombstoning old regions so grounds resolve to *something* versus
notifying and letting the curator re-point are different theories of what evidence *is*. The
program has deliberately not chosen. **It is the one place where a wrong call does lasting damage
to curator trust.**

**(2) Whether the artifact/depiction distinction is real or an artefact of fixture choice.**
*Read:* A1 `score.md` + `sparks.md`, A1F `score.md`. A1F already narrowed it from "general" to
"reproductions". Museum plates, scans, and crops are a large share of any art-historical corpus, so
if it is real it is not niche — but it currently rests on **one** plate.

**(3) The corpus-density problem, which quietly limits everything.** 11 annotated posts, 7 percepts,
98 region embeddings. F6 already flagged same-image bias as *corpus density, not geometry*. Several
questions this program keeps hitting — retrieval quality, detachment rate, whether gesture
neighbours exist — are **not answerable at this size**. Deciding whether to grow the corpus is
upstream of much of the research.

**(4) That R5 was not actually tested.** A2 delivered something better than planned, but the family
assumed two *competent* channels and got one out-of-domain. If R5 matters as a family it needs a
fixture with a genuinely ambiguous boundary. *Read:* A2 `critique.md`.

## 9. Next execution expectation

**Next primary action: execute A3 (R7 Gesture and Address), one rehearsal only.**
Preconditions are met and recorded in `R2/A3-execution-note.md`: subject `695be8ba` treated as a
**painting**; neighbour `695be790` chosen by *gesture*, not similarity; negative `695be843`;
per-image `reproduction_vs_depiction`; ≤2 live calls; no named refusal token.

**A3 must not claim** that an embedding would have chosen differently — the neighbour and negative
have **0 region embeddings**, so that counterfactual is untestable. Reason from F6's documented
material/colour dominance and label it untested.

**Must not happen next:** A4–A6; any repair of detached grounds; any production entity, route,
collection, or frontend surface; any candidate graduation; any push or merge.

## 10. Artifacts

`runs/002-figure-ground-reversal/`, `runs/002F-single-object-followup/`,
`runs/003-sensory-disagreement/` (each: manifest, trace, frozen observations, score, critique,
sparks, source-notes, instrumented-score) · `schemas/instrumented-score.schema.json` ·
`R2/R2.0-*`, `R2/R2-batch-operating-plan.md`, `R2/A2S-detached-ground-sweep.md`,
`R2/A3-execution-note.md`, `R2/evidence/` · `scripts/detached_ground_sweep.py` ·
`scripts/rehearsal_run.py`, `scripts/rehearsal_adapters.py` · 47 tests in
`backend/tests/test_rehearsal_r1.py`.
