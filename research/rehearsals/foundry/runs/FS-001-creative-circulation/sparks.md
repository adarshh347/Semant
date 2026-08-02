# Foundry Sparks — FS-001-creative-circulation

**Sandbox:** FS-001-creative-circulation · **Axis:** creative-circulation · **RESEARCH-ONLY**

> **A sandbox may emit only SPARKs.** Not a candidate, a decision, an approved design, or a durable
> object. **Nothing graduates in its originating run.** No entry here may be built from without an
> explicit build gate.

---

## Spark register

### spark-FS001-01 — playback is not recurrence, and Semant has only playback

- **Origin thread:** score §3 R2, from evidence E3.
- **Enablement claim:** the program has been using one word for two capabilities. **Playback**
  re-presents a stored reading; **recurrence** lets a later encounter revise an earlier reading and
  records that it did. Semant implements the first and has no position in its data model for the
  second. Naming the distinction is what becomes possible — not building it.
- **Evidence:** `R1-existing-circulation-probe.md` (staged timeline: recede → primary ground →
  supporting → expression); `A2R-recall-evidence-honesty.md` (every added field is a read).
- **Nearest existing Semant construct:** `Percept` + `Ground`, and **none for the second turn**. No
  new entity is proposed.
- **Strength:** SPARK, n = 3 percepts, 0 positive instances, 1 analyst, 0 calls. **Weak.** The
  critique (§7) records that this may be a definition dressed as a discovery.
- **What would strengthen it:** any mechanism found elsewhere in the app by which a re-encounter
  alters stored state — its absence is currently argued from two documents not written to answer it.
- **What would kill it:** finding such a mechanism. Retire immediately if so; do not defend.
- **[SPEC] possible location:** **deliberately not proposed.**

### spark-FS001-02 — the corpus has percepts and no passages; the second leg is unexercised

- **Origin thread:** score §2 E1/E2.
- **Enablement claim:** across all 11 posts the program holds frozen state for, **0 carry writing**,
  including the 2 that carry percepts. Every circulation question the Candidate Foundry requires for
  graduation is therefore currently unanswerable — not answered negatively, **unanswerable**.
- **Evidence:** 9 posts parsed from `runs/*/pre-state.json`,`post-state.json`; `695be6c9` (R1 probe);
  `695be786` (A2R).
- **Nearest existing Semant construct:** `Mention` — which `perceptMentions.js` reconstructs from
  block markup, i.e. its only durable form is inside a saved passage. **No passage has ever been
  saved.** So the Mention machinery is complete and has never held a Mention.
- **Strength:** SPARK, n = 11 posts. **The count is solid; its scope is contested** — see critique
  §1. Restated honestly: *the posts the rehearsal program has instrumented carry no writing.*
- **What would strengthen it:** a read-only count of `text_blocks` across the whole corpus.
- **What would kill it:** **one** post anywhere carrying a passage that cites a percept. This
  sandbox cannot perform that check (critique §5) — which is why this spark must not be promoted on
  its current evidence.
- **[SPEC] possible location:** none. This is a fact about corpus state, not about ontology.

### spark-FS001-03 — the qualified replay is the program's only recurrence-shaped behaviour

- **Origin thread:** score §3 R4.
- **Enablement claim:** A2R made the *present* state of evidence change how a *past* reading is
  presented, without editing the past reading. That shape — **qualify, never delete, never repair** —
  is the only place the program has let time act on a stored claim, and it was built as a bug fix.
- **Evidence:** `A2R`: the percept still plays when all grounds are detached; the note states a fact
  about the record, not a fault of the curator; no IoU re-pointing.
- **Nearest existing Semant construct:** `resolveGround` + the recall script. **No new entity.**
- **Strength:** SPARK, n = 1 behaviour, 1 surface. Critique §7 warns this reading may be flattering.
- **What would strengthen it:** a second, independent place where present evidence qualifies a past
  claim without mutating it.
- **What would kill it:** showing the A2R note is experienced as an error message rather than as a
  qualification — i.e. that it closes the encounter instead of continuing it. **FS-004 scores exactly
  this sentence and is the natural test.**
- **[SPEC] possible location:** deliberately not proposed. See product-implications §3.

---

## Withheld

- **"Recall should write back to the percept."** The obvious move, and precisely the premature
  ontology the doctrine warns about. Zero positive instances licence zero schema thinking.
- **"Add a revision/version field to Percept."** Same reason. spark-07 already showed percepts lack
  *scope*; adding *time* to fix a gap found by a run with no positive class would be building on
  absence.
- **"Home should show percepts."** Attractive and second-hand here (score §5). Not recorded as a
  spark because this run did not read the evidence itself.
- **"The imaginative mode is where circulation lives."** E4 is suggestive and n = 1 run; promoting it
  would convert a single virtual-score array into an architectural claim.

## Unresolved questions

- **UQ1** — Does any post in the wider corpus carry a passage citing a percept? One read-only query
  settles it and would kill or confirm spark-FS001-02. **This sandbox cannot ask it.**
- **UQ2** — Is the blocked rendered probe (R1, exit-144) still blocked? Servers ran fine this
  session. If it is now runnable, it is the cheapest unblocking action available on this axis and it
  has been waiting since R1.
- **UQ3** — Does Chiasm render A2R's evidence note in its own pane? A2R explicitly declines to assume
  it. If Chiasm shows the caption without the note, the one honest surface is honest in one place
  only.
- **UQ4** — Is `Mention` durable anywhere other than block markup? If not, an unsaved passage means
  the Mention never existed, and "0 mentions" is a statement about saving, not about noticing.
