# Semant Writer — W7 BUILD DIRECTIVE (the alignment reading — the honest editor)
**A deep, buildable-now layer, independent of W6 (build in either order). Companion to the W1–W5 directives and `GROUNDING.md`. Executable: build W7 only, until its gate (§8) passes. Read §2 before any code — it is the load-bearing philosophical decision, the way `GROUNDING.md` was for the render side.**

> Precondition: W1–W5 + the library surface merged. W7 adds a new actuator and its surface. It touches provenance (as *input*) and adds diagnostics, but it **never** produces or edits prose. If at any point it writes to the manuscript, the build is wrong.

---

## 0. Mission (one paragraph)
Rendering answers "produce prose from my declared operators and orchestration." W7 answers its mirror: **"where does this prose diverge from what I declared?"** The alignment reading takes a passage that carries provenance (the operators + `//` intents that made it) and reports, span by span, where the prose fails to honor that declared intent — citing the specific declared element each flag rests on. It is an editor that refuses to have taste: it measures the author's prose against the author's own standard, and it may say nothing else. It never rewrites; it diagnoses, and the author acts.

## 1. Why this is the honest counterpart, not a generic AI editor
Every "AI writing assistant" critiques against a generic notion of good prose — that is priors deciding what your writing should be, the exact fabrication this project refuses. W7 inverts it: the **only** yardstick is the author's declared intent. A passage's provenance already records the operators and `//` orchestration that produced it (I4). Those are the author's declarations, and they are the evidence base (`GROUNDING.md`). The alignment reading measures the prose against *that* — `//avoid melodrama`, the operator `restraint`'s definition, an operator's `negative_examples` — and against nothing else. It is the render loop's honesty run backwards: rendering may only compose in the author's language; the reading may only critique in the author's language.

## 2. The taste wall (the load-bearing decision — state it in code and defend it)
The hard question, named so it isn't discovered at demo: to judge "this reads melodramatic despite `//avoid melodrama`," the model uses its own notion of melodrama — which is priors. So is a taste-free critique even possible? Yes, on one precise line:

> **The model may use its linguistic competence to *measure conformance to a term the author declared*. It may not introduce a term of its own.** Recognizing melodrama is the detector; *deciding melodrama is unwanted* is the author's `//avoid`. The competence detects; the author sets the standard.

This is exactly the vision side's split: a detector recognizes a cat using its trained competence, but the decision that cats matter here is the author's marking. So the taste wall is enforceable and concrete:

- **Every flag must (a) name a declared element** — an operator (by id/version) or a `//` intent from the passage's provenance — **and (b) assert only that the prose conforms to or diverges from THAT element's declared meaning.**
- **A flag that introduces any evaluative dimension the author did not declare is forbidden** ("vary your sentence length," "stronger verb here" — none of these name a declared element, so none may appear).
- Enforced **structurally**: a diagnostic that does not reference a provenance element by id is dropped before it reaches the author — not requested politely in the prompt, guarded at the boundary (the same lesson as the style-by-reference wall in `GROUNDING.md`).

## 3. What the reading measures against
For a passage, the declared standard is exactly its provenance:
- **`//avoid` intents** — flag spans that violate them.
- **operator `rendering_intent`** — flag where the prose fails to realize what the operator was meant to do.
- **operator `negative_examples`** — the operator's own authored "not this"; flag matches.
- **`//goal` / `//voice` / other `//` intents** — flag divergence from them.

Each flag cites the specific element (operator id+version, or the `//` intent text) it rests on — the writer's "which detector evidence this mark stands on."

## 4. Honesty guards (each needs a test)
- **Never authors canon (I1).** The reading emits diagnostics only; it cannot rewrite or commit prose; it is read-only w.r.t. the manuscript. *Test:* run a full reading; assert manuscript export byte-identical, no prose produced.
- **Taste wall (§2).** Every flag references a provenance element id; no undeclared dimension appears. *Test:* feed prose with an obvious "quality issue" the author never declared (e.g. repetitive openings, absent from every operator/intent); assert the reading does **not** raise it. Feed a real `//avoid` violation; assert it **is** flagged, citing that intent.
- **Refusal as silence (I2).** If a critique cannot be grounded in a declared element, the reading says **"aligned / nothing to flag,"** never a manufactured nitpick. On a passage with thin/empty declared intent, it reports **"little declared intent to check against,"** not invented advice. *Test:* run on a near-empty-orchestration passage; assert no invented suggestions.
- **Scoped to a passage's own provenance.** A passage is measured **only against the operators/intents that made it.** An author-typed span with no provenance is **not** critiqued against operators it wasn't made from. *Test:* run on a hand-typed (no-provenance) span; assert it is not critiqued against unrelated operators.
- **Diagnostics are propose-not-commit.** Flags are quarantined suggestions the author dismisses or acts on; nothing auto-changes, and acting routes back through the author-driven render loop (re-render under adjusted orchestration), never a silent patch. *Test:* dismiss a flag; assert canon and ontology unchanged.
- **The reading is itself audited.** Each reading records what it measured against (the element ids) and the model that produced it. *Test:* assert the reading's own provenance is present and resolves.

## 5. The calibration payoff (why this is more than an editor)
Because a flag names the operator it diverged from, the instrumentation can now answer the §9 hard problem *measurably*: **an operator whose renders are repeatedly flagged as diverging from its own intent is miscalibrated** — too vague, or pulling against the prose. Log every flag with its cited operator and the author's response (dismiss = false alarm, act = real divergence). Over a corpus this becomes the first honest signal of *which operators are working and which aren't* — the exact thing the dogfooding period exists to learn, now instrumented. Ship this logging with W7; build no analysis on it yet (that reads thin until the corpus grows), but capture it from the first reading.

## 6. Editor surface (build it here — do not repeat the W5 backend-only miss)
- An **"read alignment"** affordance on a committed span (and on a quarantined render before accepting).
- Flags shown inline / in the margin, each **citing the declared element** it measures against, each **dismissable**.
- **No rewrite button.** The reading diagnoses; it never offers to fix. The only forward action is author-driven "re-render under adjusted orchestration," which goes back through the render loop.
- A visibly distinct empty state: "aligned — nothing diverges from what you declared," and "little declared intent to check against" for thin passages. Silence must read as an honest result, not a failure.

## 7. Out of scope (forbidden or deferred)
- **Rewriting / auto-fix / suggested replacements** — never; diagnosis only.
- **Generic writing-quality critique, style scores, numeric grades** — forbidden by the taste wall; a "quality score" reifies exactly the taste this refuses.
- **Critiquing author-typed prose against operators it wasn't made from** — out of scope; measure a passage only against its own provenance.
- **Auto-acting on flags, batch "fix all"** — the author acts, one at a time, through the render loop.
- **Corpus-level calibration analysis / operator auto-tuning** — log now, analyze later; auto-tuning is emergent/data-gated.

## 8. THE W7 GATE — the demo that proves it
Green, live, real Groq, no manual fixup:

1. Render a passage under `//avoid melodrama` + operator `restraint`; run the alignment reading → **aligned**. Then force a divergent passage; run again → a flag that **cites `//avoid melodrama` (or `restraint`) by reference**.
2. **Taste wall:** feed prose with an undeclared "quality issue" (e.g. repetitive sentence openings, named by no operator/intent); assert the reading does **not** raise it; assert every flag it does raise references a provenance element id.
3. **Refusal as silence:** run on a thin/near-empty-orchestration passage; assert "little declared intent to check against," no invented advice.
4. **Scope:** run on an author-typed span with no provenance; assert it is not critiqued against unrelated operators.
5. **Canon untouched (I1):** across a full session of readings, assert no prose produced and manuscript export byte-identical.
6. **Reading is audited:** assert each reading records the element ids it measured against + its model, and resolves.
7. **Calibration log:** assert each flag logs its cited operator and the author's dismiss/act response.
8. **Surface:** flags appear citing their declared element with no rewrite affordance; the aligned and thin empty-states render as honest results; dismiss leaves canon and ontology unchanged.

If step 2's taste-wall check or step 3's silence check fails, W7 is not done — those are the line between an honest editor and a generic one, and they are the entire point.

## 9. Definition of done
- A read-only alignment actuator that measures a passage against its own provenance (operators + `//` intents) and nothing else; the taste wall enforced structurally (every flag cites a declared element id).
- Refusal-as-silence for ungroundable critique; honest empty-states for aligned and thin passages; scoped to a passage's own provenance.
- Diagnostics propose-not-commit; the only forward action is author-driven re-render; no rewrite anywhere.
- The reading is itself audited; flags + author responses logged for the calibration signal (no analysis built on it yet).
- Editor surface ships with W7; every §8 assertion has a passing test; W1–W5 suites still green; export-leak CI still green.
- No rewriting, no generic-quality critique, no scores, no auto-acting, no corpus analysis.
- The W7 gate (§8) passes end to end.

When this holds, the author has both halves of the loop: a composer that writes only in their language, and a reader that critiques only against their standard — and neither ever imposes a voice or a taste the author didn't declare. Merge at the checkpoint.

---
### Appendix — the one line to hold
The alignment reading is safe exactly as long as every word it says points back at something the author declared. The temptation will be to let it be "helpful" — one small suggestion the author didn't ask for, one quality it noticed on its own. Refuse it in code and in review: the moment the reading introduces a standard the author didn't set, it stops being the author's editor and becomes the model's taste wearing the author's document, which is the same fabrication the render side spent seven gates refusing. It detects against the author's terms; it never brings its own.

---

## Build record — how the gate was met (added after the build)

**Where the pieces live.**

| Concern | File |
| --- | --- |
| The actuator, the standard, the prompt, the structural guard | `backend/services/writer/alignment.py` |
| Readings + flag decisions (propose-not-commit, the calibration log) | `backend/services/writer/readings.py` |
| Persistence | `writer_readings` (`backend/database.py`) |
| Routes | `POST /{project}/alignment/read`, `GET /{project}/alignment/readings`, `POST /alignment/readings/{id}/flags/{flag_id}` |
| Role | `alignment_reader` (ROLES-001), deliberately separate from `manuscript_renderer` |
| Surface | `frontend/src/writer/alignment/AlignmentReading.jsx`, offered from `QuarantineCard` |
| Suite | `backend/tests/test_writer_w7.py` (27), `AlignmentReading.dom.test.jsx` (15) |
| Live gate | `scripts/writer_w7_proof.py` |

**Three decisions the directive left open, and how they were settled.**

*An operator's `definition` is NOT part of the standard.* §3 lists "the operator `restraint`'s definition" among what the reading measures against. It was excluded. A definition says what the thing **is**, which is the basis for *rendering* it; it is not something prose can be said to diverge from. Measuring prose against a definition collapses into "does this read like the idea?", which is taste wearing a citation — the exact failure §2 exists to prevent. The standard is therefore `//` intents, operator `rendering_intent`, and operator `negative_examples`: what the author said the prose should **do** and should **not be**. Test: `test_an_operator_definition_is_not_a_standard`.

*`no_provenance` is its own status, distinct from `thin`.* §4 folds "author-typed span" into scope and §8.3 into silence, but they are different answers and the surface says so differently. `thin` means *I looked and you declared almost nothing*; `no_provenance` means *you wrote this yourself, so there is no standard of yours to read it against.* Collapsing them would let "not ours to critique" read as "you should declare more."

*The guard drops rather than repairs, and drops loudly into diagnostics.* An ungrounded flag cannot be fixed by rewording — it is the model bringing a standard of its own, so it is removed before the author sees it. But the drop is recorded in `diagnostics`, so how often the model tries to step outside the standard is *observable* rather than merely asserted. A second structural check drops any flag quoting a span that is not in the passage: a flag about text that does not exist is a flag about nothing.

**What the live gate actually showed (real Groq, `openai/gpt-oss-120b`).**

All eight steps pass. Two results are worth recording rather than just claiming:

- **The wall held, and the guard was not what held it.** The §8.2 bait — three sentences opening "She waited", a genuine craft problem no element names — was run 8 additional times beyond the gate. Silent 8/8; the model raised nothing, so the structural guard never fired on it. That is the *better* outcome but it is the *weaker* evidence: on this bait the wall is currently being held by the prompt, and the prompt is the net, never the guard. The guard is exercised by the suite, and it did fire live on the divergent passage — dropping a flag that quoted "a tidal wave of grief…" as if it were in prose where it was not. Both mechanisms are live; only one is load-bearing, and it is the one that cannot be talked out of.
- **A grounded flag is specific in the author's own words.** On forced melodrama the reading returned three flags, citing `intent:avoid`, `operator:restraint:intent` and `operator:restraint:not:0` — the third matching the author's own negative example back to the prose. None suggested a replacement.

**Four guards added in review, three of them the same mistake in different clothes.**

The gate is about what the reading may *say*. Review surfaced that three separate paths could make it say something it had not earned:

- **An unreadable reply must not report as `aligned`.** Malformed JSON produced zero flags, and zero flags meant `aligned`. That is the same error as reporting an unreachable model as clean — which the suite already forbade — one layer in. `_parse` now distinguishes *could not read* (`None`) from *found nothing* (`[]`), and the former is an error the author can re-run. Fail closed: a false `aligned` is a lie the author has no way to catch.
- **A flag with no span is dropped.** Without a quoted span the author cannot locate the claim, so it functions as a verdict on the passage as a whole — the shape a quality score takes, arriving through the one door the taste wall left open.
- **Malformed provenance is skipped, not raised on.** A read-only diagnostic must not 500 on a request that changes nothing; well-formed stamps are still measured.

The fourth is about the calibration signal rather than the reading: **a flag decision is now a compare-and-set**, matching `state: open` in the query and updating one array element by position. "A decision is made once" was asserted by a test but enforced by a check-then-write, so two concurrent decisions could both land and both instrument — recording a dismissal *and* an action for one judgement, which is precisely the signal §5 exists to keep honest. Replacing the whole array had the quieter version of the same bug: a decision on one flag could revert a concurrent decision on another.

Also fixed: a failed decision surfaced to the author instead of escaping as an unhandled rejection (the flag would have gone on reading as open with nothing said), and the live proof's `try` moved above its first write so the fixture cannot survive a setup raise or the marker guard's early return.

**What was deliberately not built.** No rewrite path anywhere — not in the actuator, not in the router, not in the panel; the only forward action is the author re-rendering under adjusted orchestration. No score, grade or overall impression. No corpus analysis on the calibration log: §5 says capture now and analyze later, and an analysis over a handful of readings would read as a finding when it is noise.
