# Foundry Score — FS-004-communication-quality

**Sandbox:** FS-004-communication-quality · **Axis:** communication-quality · **Mode:** foundry · **RESEARCH-ONLY**

**Research question.** When Semant has less than it wishes it had — absent evidence, an unreadable
run, a contradicted model, a claim it cannot check — does the way it speaks earn trust, or spend it?

> Zero live model calls. Every utterance below is quoted **verbatim** from a frozen artifact, as the
> recording rule requires: you cannot measure a sentence's wording through a paraphrase of it.

---

## 1. What was actually done

A zero-call pass over the utterances the program has already written down. Four were identified
across the declared inputs and scored in isolation on the five rubric dimensions. Two are
user-facing product surfaces, one is an internal rule, one is model output.

**Bounded task:** score every identified utterance, or mark it absent. Completed.

## 2. Evidence

### Utterance A — the detached-evidence note (shipped, render-verified)

> **"Detached evidence — none of the 2 cited grounds still resolves."**

Source: `A2R-recall-evidence-honesty.md`. Appears **with** the caption, never before it; render-
verified in a real browser against the real detached percept `pctx_mrqp950d_0`. Design choices
recorded there: the percept is **never suppressed** ("it is the curator's own words"); the note
"states a fact about the **record**, not a fault of the curator"; no repair, no re-pointing, no IoU
guessing. `resolvedCount` and `citedCount` are exposed together — explicitly "a denominator, so
'1 of 3 gone' reads differently from '3 of 3 gone'".

### Utterance B — the Vision Activity Rail's closed summary (shipped)

> **"N recorded"** / **"nothing recorded yet"**

Source: `HW-S1-frontend-opportunity-scout.md` §1.2, cited within this sandbox's declared inputs. The
rail's *internals* are unusually honest: absence vs unreadability **is** discriminated, causal
wording **is forbidden and tested**, raw errors are scrubbed behind a disclosure, polling is bounded
to active runs. But the rail **starts collapsed**, renders **below** the counts footer at the bottom
of the inspector, and its closed line is a pure count. A run that is `partial`, `timed_out` or
`stale` contributes to `recordedCount` and is **indistinguishable from a clean success until you open
it**. With one `vision_runs` document corpus-wide, in practice it says "nothing recorded yet" almost
everywhere — and that fact is itself invisible outside the drawer.

### Utterance C — the ledger's inapplicability rule (internal, not user-facing)

> **"run 000 must be marked `n/a`, never `none`."**

Source: `HW-C6-external-claim-audit-001-006.md`. The distinction between *having nothing to say* and
*having said nothing*. HW-C6's reasoning: recording an empty ledger where no model ever spoke "would
enter a negative into the evidence base for spark-08 that no model ever had the chance to produce."

### Utterance D — the model's own overclaim (measured failure)

> **"a powerful and unifying motif: the use of intricate, colorful patterns to create a sense of
> divine order"**

Source: `runs/011-strained-premise-probe/score.md` §1, on a pair two prior lanes recorded as a **poor
rhyme**. HB-010 §7 names the diagnostic precisely: the response **"amplifies force while diluting
content in one sentence"**. The opening also builds its escape hatch before any objection arrives —
*"the rose window or, **more broadly**, the concept of a circular, radiating… design"*.

## 3. Reading

**R1 — The denominator is the mechanism, and it is the whole difference between A and B.** Both A
and B report the same class of fact: *something that should be here is not*. A carries a denominator
("none of the **2** cited grounds") and reads as trustworthy. B carries a bare count ("N recorded")
and reads as fine. **The information is comparable; the trust outcome is opposite.** A2R arrived at
the denominator deliberately and said why. Nothing generalised that insight to the rail.

**R2 — Honest internals, mute surface.** This is the run's central finding. The rail *already knows*
what B fails to say: it discriminates absent from unreadable, and it has a **tested** prohibition on
causal wording. The knowledge exists in the module and **dies at the rendering boundary**. Semant's
communication problem, on this evidence, is not that it lacks honesty — it is that **honesty is
implemented one level below where it is spoken**.

**R3 — The program has exactly one render-verified honest sentence, and it exists because of a bug.**
A was written when A2R confirmed a scout's claim. There is no policy, convention or shared vocabulary
that would produce a second one. HW-C5's external-claim convention is still marked **Proposed**.
Honesty here is an incident, not a practice.

**R4 — Nothing in the product guards against the failure the program has actually measured.** D is
the documented behaviour: as content thins, force rises. Every Semant surface that will display model
prose — Aletheia `/read`, the stubbed "Draft from the image" and "Continue writing" actions —
inherits that behaviour, and none of the four utterances shows any mechanism that would notice it.
**A is the anti-pattern's exact inverse** (quiet, qualified, denominated) which is suggestive but is
one sentence, written for a different reason.

**R5 — Every user-facing utterance closes rather than invites.** A tells you evidence is gone and
offers nothing to do. B tells you a count and hides the rest. Neither offers a next act. **This is
where communication quality meets FS-001:** an honest announcement that terminates the encounter
cannot produce circulation. The surface most likely to prompt a return is currently the one that ends
the conversation.

## 4. Opening

**[SPEC] O1** — If a single transferable rule exists in this evidence, it is R1's: **absence claims
need denominators.** It is cheap, it is derivable from data already in the client, and it is the one
thing A does that B does not.

**[SPEC] O2** — R5 suggests trust and circulation may be the same axis seen twice. An utterance that
invites a return is both more trustworthy and the only kind that could produce a second turn.
Speculative, and it is exactly the kind of unifying claim spark-10 warns about — recorded here with
that suspicion attached.

## 5. Resistance

- **`insufficient_evidence`** — n = 4 utterances, of which only **2** are user-facing product
  surfaces. Any claim about "how Semant speaks" rests on two sentences.
- **`sensory_unavailable`** — **no utterance was observed in a browser by this run.** A's render
  verification is A2R's, inherited. B is described by a scout, not seen here. Nothing was experienced;
  everything was read.
- **`curator_refusal` (structural)** — the rubric's `invites_return` dimension asks about a reader's
  experience, and this run has no reader. Those scores are **inferences from text**, not observations
  of use, and are marked as such in §6.
- **`analogy_overreach`** — scoring model output (D) and UI copy (A, B) on one rubric treats a
  generated sentence and a designed sentence as the same kind of object. They are not. D is retained
  because it is the program's only measured communication *failure*, but its scores are not
  commensurable with A's and B's.

## 6. Scoring rubric

Scored verbatim and in isolation. **`invites_return` is inferred, not observed** (§5).

| utterance | states_the_limit | locates_the_fault | denominator | force_vs_content | invites_return |
|---|---|---|---|---|---|
| **A** — "Detached evidence — none of the 2 cited grounds still resolves." | **names-it** | **about-record** | **denominated** | **tracks** | informs |
| **B** — "N recorded" / "nothing recorded yet" | **silent** (partial/timed_out/stale all fold in) | neutral | **bare** | flat | **closes** |
| **C** — "`n/a`, never `none`" *(internal rule)* | **names-it** | **about-record** | n/a — it *is* a denominator rule | tracks | n/a |
| **D** — "a powerful and unifying motif…" *(model output)* | silent | n/a | bare | **inverted** | **closes** |

**No composite score.** Reading across rather than down: the two shipped surfaces (A, B) sit at
opposite ends of four of five dimensions, and **the axis they differ on is the denominator**.

**Absent utterances, recorded as absent rather than imagined:** there is **no** utterance anywhere in
the record for *model contradiction*, for *external-claim limits* at the surface (HW-C5's convention
is Proposed, adopted voluntarily by one run's score), or for *refusal* — the program has recorded
**eleven arms with zero refusals** and correspondingly has no sentence for one.

## 7. Stop condition

Declared stops:

- every identified utterance has been scored or marked absent
- scoring would require writing new UI copy
- a finding would require proposing a tone system or voice guide
- a result would require a live model call

**Fired: the first.** The second and third were live pressures throughout — the pull toward drafting
a better rail summary was strong and is recorded in §8 as withheld rather than acted on.

## 8. Withheld

- **A rewritten rail summary.** I can see what B should say. Writing it here would be writing UI copy,
  which the manifest forbids and the stop condition names. **Withheld deliberately, and it was the
  hardest withholding in this run.**
- **A tone system / voice guide.** The obvious synthesis of five dimensions and four utterances. Two
  user-facing samples cannot license a system, and `forbidden_actions` names it.
- **"Semant communicates untrustworthily."** Withheld — false. A is genuinely good, and the rail's
  internals are better than most of the product.
- **"Open the rail by default."** HW-S1 already considered and declined this ("I nearly listed this
  as experiment #1"). Repeating a rejected idea as a finding would be laundering it.
- **Any claim about how a user *feels*.** No user was present. The rubric measures text properties.
