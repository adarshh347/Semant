# Semant Writer — the instrument-and-wait period: dogfooding & evaluation
**Not a build directive.** This is what to do now that Tier 2 is complete (W1–W4), the
portable-ontology mechanism is in (W5), and Tier 3 is deliberately unbuilt. Its job is to
make the waiting *productive*: to answer the one question the whole project rides on, and to
grow a corpus worth analyzing when the time comes.

---

## 0. The one question this period exists to answer
From the plan's §9: *everything in Tiers 2–3 rides on Tier 1's render loop feeling like the
author's voice coming back to them. Get it right and you have a language that becomes more
the author's own with every chapter. Get it wrong and operators are just fancy prompts.*

That is not a thing tests can tell you. It is a thing only real writing can tell you. So the
purpose of this period is to find out, honestly, **which one it is** — and the answer
determines everything downstream. If the loop feels like a second mind, Tier 3 is worth its
eventual cost. If it feels like fancy prompting, no amount of Tier-3 machinery will rescue
it, and the right move is to fix the calibration loop, not build upward. This period is the
experiment that settles that.

## 1. The small fix that had to come first — DONE
The W4 render echoed its `rendering_intent` back almost verbatim as the passage, because an
assemblage's `definition` defaulted to its `rendering_intent` when the author didn't supply
both, leaving the operator thin. That is the calibration problem (plan §9) showing up in
miniature — a thin operator renders thinly.

**Shipped:** an assemblage now REFUSES without a distinct `definition`, and any operator whose
`definition` and `rendering_intent` are identical draws a warning in the render diagnostics.
The confound is gone: dogfooding now tests the author's calibration rather than an artifact
of a defaulted field.

## 2. How to dogfood (so the corpus is real)
- **Write real material, not test scenes.** The corpus is only worth analyzing later if it's
  genuine writing you cared about — a real chapter, a real story. Synthetic exercises produce
  synthetic patterns.
- **Author operators as you go, via `#create`, in your own words.** Resist the urge to
  pre-build a tidy ontology. The whole thesis is that the language grows with the writing; let
  it. When you reach for a quality you don't have an operator for, make one.
- **Edit operators when they misfire** rather than working around them. An operator that
  renders wrong is data: too vague (renders generically) or too specific (fits only one scene)
  is the exact §9 calibration axis. Sharpen it and note what you changed. That edit history is
  signal.
- **Let refusals happen and watch how they feel.** When a `//voice like X` refuses and offers
  `#create`, notice whether the on-ramp felt like a helpful collaborator or an obstacle.
  That's I2/I5 being judged in the only court that matters.
- **Say yes and no to assemblage suggestions honestly.** When the system proposes a cluster,
  does it feel like it noticed something real about your writing, or like noise? Both answers
  are useful; dismissals are logged and are themselves data.

## 3. What to notice — a light rubric (keep it qualitative, keyed to `run_id`)
You don't need a spreadsheet. Keep a running note, and when a render is memorable in either
direction, jot the `run_id` and one line. Watch for:

- **Voice.** Did the accepted passage read like *you* — or like a competent generic model?
  This is the whole ballgame. Track the ratio over time; it should climb as your operators
  sharpen.
- **Calibration misses.** Which operators keep misfiring, and in which direction (too vague /
  too specific)? Which ones stabilized after a few edits and now "just work"? The ones that
  stabilize are the proof the loop works; the ones that never do are where the loop is weak.
- **Provenance usefulness.** When you looked at *why a paragraph reads the way it does*, did
  the provenance actually let you understand and re-render it — or was it inert metadata? I4
  is only real if you use it.
- **Refusal quality.** Did refusals protect you from a smuggled generic voice, or just annoy
  you? A refusal you were grateful for is I5 earning its place; a refusal that felt pedantic is
  a tuning signal.
- **Assemblage truth.** When you accepted a suggested assemblage, did naming it change how you
  write afterward — did the language actually compress and evolve? That's the Tier-2 promise
  being kept or not.

## 4. Keep the instrumentation analyzable
The logs capture usage, co-occurrence, pulled operators, suggestions, dismissals, authorings,
`run_id` per block run, and (since W5) the library lineage of any operator used in a render.
Two light things keep them useful:
- **Don't reset or prune the log.** It has been accruing since W1; its value is cumulative and
  its early sparseness is part of the record.
- **Pair it with your qualitative note by `run_id`.** The logs will tell you *what* recurred;
  your note tells you *whether it felt right*. The Tier-3 analysis needs both — structure
  without the felt-sense reading is how you'd build narrative "physics" that measures something
  real but useless.

## 5. When to come back — and for what
Come back for the **analysis**, not a directive, and only when both conditions hold: (a) a
Tier-3 metaphor has a candidate *measurable* over the log, and (b) there's enough real usage
that the measurable shows a stable signal — not a coincidence of a few sessions. As a rough
gate, that means weeks of genuine writing, operators that have matured through several
versions, and at least a few assemblages you actually authored and kept using. Thin corpus, no
analysis — reading noise as structure is exactly the fabrication the project refuses.

When it's rich, the first artifact is a grounded read of the log: *what real, recurring
structure does the author's usage actually show?* That read — not a guess about narrative
fields or a semantic genome — is what tells you which Tier-3 idea, if any, has become
engineering. Some may never operationalize, and "this metaphor stays a metaphor" is a
legitimate, honest finding.

## 6. What NOT to do in this period
- **Do not build Tier 3 speculatively.** Not narrative physics, not fields, not operator
  evolution, not the semantic genome, not cross-author libraries, not live shared references,
  not blended-field composition. All of it is data-gated; building ahead of the data is
  guessing dressed as engineering.
- **Do not add features to "help" the loop feel better** before you've honestly assessed
  whether it does. If the voice isn't landing, the fix is calibration (sharper operators,
  better `#create` drafting, the distinct-definition rule) — the existing loop — not new
  machinery on top.
- **Do not let the corpus go synthetic** by writing exercises to "generate data." Real writing
  or nothing.

---
### The shape of what was built
Five gates, each proving one thing and resting on the one before: the document is executable
and the author commits (W1); the loop has a body that feels like writing, with the invariants
in the schema (W2); the ontology is visible and one edge can ground a span without blending
(W3); the language compresses from real evidence while the author keeps naming (W4); and that
language is portable between books without an edit in one silently redefining another (W5).
The honesty spine held across all five — the canon is never authored by the AI, and never
written in a voice that isn't yours. What's left isn't more building. It's writing enough,
honestly enough, to find out whether the thing you built is a second mind or a clever prompt —
and then letting the corpus, not a directive, tell you what comes after.
