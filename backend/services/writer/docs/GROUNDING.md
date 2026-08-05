# Semant Writer — the grounding decision

This is the load-bearing philosophical decision of the whole module. Every honesty guard in
`render.py` derives from it — most of all the `_STYLE_BY_REFERENCE` wall. If you are reading
`_STYLE_BY_REFERENCE` and wondering *why it refuses what it refuses*, the answer is here. Do not
weaken a guard without first arguing against this document.

---

## The one sentence

**A rendered passage rests on the author's own operator ontology. The author's declared language is
the evidence base. The model may render only in terms of operators the author defined and the `//`
orchestration the author set — it may never import unstated style from its priors.**

That is the whole thing. Everything below is why it holds and what it forces.

## Why this exists — honesty is authorial, not evidential

Semant's spine is *never fabricate; rest on real evidence.* On the vision side that is literal: a
mark rests on real detector output, and the VLM may only speak about marked regions. Fiction has no
detector — fiction is invention by definition — so the naive reading is that honesty cannot survive
the crossing into writing. It survives by **moving from evidential to authorial**.

The transposition: on the vision side the evidence is the detector's output; on the writing side the
evidence is **the author's declared ontology** — the operators they defined, the `//` orchestration
they set for this passage. "Cites nothing, never rests on nothing" becomes: *a passage carries which
operators produced it, and those operators are the author's, so nothing is smuggled in.* The model
proposes; the author commits; and critically, the model may only propose **in the author's own
declared language.** The canon is never authored by the AI, and never written in a voice the author
has not declared. That second clause is the one that takes work to enforce, and it is what the rest
of this document is about.

## The principle that settles the edge cases: grounded vs imported

Every hard call in this module reduces to a single distinction:

> **Grounded** — the meaning of the instruction is supplied by the author (an operator they defined;
> a `//` note in their own words). Render it.
>
> **Imported** — the meaning of the instruction lives in the model's training priors, and the author
> has merely *gestured at* it. Refuse it.

This is sharper and more correct than the surface distinction "describes-qualities vs
names-a-corpus." Naming a corpus is refused **not because it is a proper noun** but because its
meaning lives in the priors, not in the author's declarations. The reframing is what closes the
ambiguity in the honesty invariant (I5): *permitted `//` orchestration means orchestration whose
meaning the author supplies; a value that refers out to the priors is an import wearing the author's
syntax, and never was permitted.* An author typing "Tolstoy" with their own hand does not make the
meaning of Tolstoy theirs — the meaning is still the model's statistical memory of a corpus the
author never declared.

### Worked cases

- `//voice a spare, cold remove; the narrator knows less than the reader` → **grounded.** The author
  supplied the meaning. Render.
- `//avoid melodrama, adjectives in threes` → **grounded, and note: declining a style imports
  nothing.** A negative constraint is purely subtractive; it can never pull priors onto the page.
  `//avoid` is exempt from the wall by construction.
- `//voice like Tolstoy` / `//voice the ornate omniscience of a 19th-century Russian novel` /
  `//voice write it Woolf` → **imported.** The meaning lives entirely in the priors. Refuse —
  structurally, before the model is ever called.

## Why the wall had to be structural, not a prompt rule

This is the empirical finding that shaped the implementation, and it is worth preserving so no one
re-litigates it. Stating the prohibition plainly *in the prompt* does not hold: asked for "the ornate
omniscience of a 19th-century Russian novel" via `//voice`, with the prohibition written directly
into the system prompt, the model complied — invented a Russian name, addressed the reader.
Strengthening the prompt did not fix it; the pull of the priors beats the instruction.

So style-by-reference is a **structural pre-flight refusal** in `render.py`
(`_STYLE_BY_REFERENCE`), sitting beside undefined-operator and contradictory-orchestration as a
reason a render is refused *before Groq is called.* The prompt-level rule stays, but only as a
backstop to catch phrasings the marker list misses — it is not the guard, it is the net behind the
guard. This is exactly what invariant I5 meant by *"enforced at the prompt-construction boundary,
not merely requested in the prompt"*: the discovery that even the boundary prompt leaks on corpus
references is the invariant correctly hardening itself, not a defect.

## The detector is tuned to over-refuse — on purpose

The marker list (bare surnames, emulation formulas, named periods, movements, genres) is a
**documented heuristic, not a complete decision procedure.** It will miss some phrasings and it will
occasionally flag an innocent one. That asymmetry is deliberate and must stay:

- A **false positive** is a shrug: the refusal names the exact phrase it caught, the author rephrases
  in their own words or defines an operator, and moves on. Nothing is lost.
- A **false negative** is the cardinal sin: the model silently renders a voice from its priors into
  the sacred canon, and no one sees it happen.

So the detector **biases toward refusal**, and any under-refusal is a **priority bug, not a
papercut.** A false positive always surfaces as a loud refusal naming the phrase — never as a silent
change to the prose. When in doubt, refuse.

## The refusal is generative — it routes to `#create`

The wall is not a dead end; it is the on-ramp to the author's ontology growing. A style-by-reference
refusal does not merely block — it converts the gesture into the calibration loop:

```
// voice: like Tolstoy, but shorter  names something whose meaning lives in my
priors, not in your ontology. I cannot check it against your book.

Tell me what it means TO YOU instead — the remove, the sentence length, what the
narrator is allowed to know — and it becomes an operator you own:

    #create tolstoy_voice: <the qualities, in your words>

Then  / tolstoy_voice  renders it, versioned and auditable, and it is yours.
```

The author names the qualities they meant; the voice becomes declared, versioned, and grounded; and
they reach the destination they were reaching for — by the honest path. This is the "the language
becomes more the author's own with every chapter" promise made concrete. The prohibition is not the
feature; **this on-ramp is the feature.** (Implementation note: only surname markers yield a
suggested stem name; phrase markers fall back to `my_voice`, because stems like `th_century_voice`
are noise.)

## What this decision forces on everything downstream

- **Composition stays sequential (v1).** One operator, one span, in explicit author order — which
  keeps provenance one-operator-per-span and keeps this grounding auditable. The blended-field
  interpretation is Tier 3 precisely because fused provenance would blur the line this document
  draws.
- **The editor (W2) may not become a second door to the canon.** Accept still flows through the one
  owner (`manuscript_service`); the surface is a view, not a writer.
- **`//` never reaches the page (I6).** Orchestration is the author's private reasoning; if it leaked
  into the surface it would be un-authored text in the canon. Enforced at the schema level in W2, not
  merely styled.
- **Roles are declared, not shared by coincidence.** `manuscript_renderer` is its own rebindable role
  so that rebinding some other role (e.g. `archivist`) can never silently change how the author's
  book reads. Two roles sharing a default string must be a visible fact, never an accident.

## The test for any future change

Before adding a capability or relaxing a guard, ask: **does the meaning of what the model is about to
render come from the author, or from the priors?** If from the author — grounded — allow it. If from
the priors — imported — refuse it, and offer the `#create` path to ground it. That question is the
whole module in miniature. If a proposed feature can only work by answering "from the priors, and
that's fine," the feature is out of scope, no matter how good the prose it would produce.
