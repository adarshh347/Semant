# 004 — Sparks

**Epistemic status: SPARK only.** Not a candidate, not a decision, not a schema proposal. No
durable candidate object was created.

---

## spark-05 — address as a viewer-facing stance, possibly without a figure

**Origin:** probe 1's reading of the subject, and probe 2's unexpected treatment of the negative.

**Observation.** Asked where a gesture's address goes, the model did not answer with a direction in
the picture plane. It answered with a *stance toward the viewer*: "turns away from the viewer,
withholding direct engagement… an act of quiet refusal." Then, given a building with no figure in
it, it found "a monumental, frontal face with windows that function as eyes… a direct, imposing
gaze… confrontational address rather than a refusal."

**Enablement claim.** Address is a relation between a depicted thing and the position of whoever
looks. It is (a) not a region — it has no extent; (b) not a similarity score — the matched pair is
maximally dissimilar on surface; and (c) possibly **not dependent on there being a body**, since
frontality and facing were enough to elicit it from architecture.

**Nearest existing construct:** `relation` — it already references members by id and carries a
`relation_label`. **This may well be sufficient within one image, and that must be tested before
anything new is contemplated.** What it demonstrably cannot express is a relation **between two
posts**: every Ground lives on a single post, and A3's entire finding is cross-image.

**Deliberately NOT concluded:** that Semant needs a cross-post relation entity. That is the obvious
next thought and the evidence does not support it yet — one pair, one model, one judgement.

**Next test.** Ask whether `relation` suffices for a within-image address (figure ↔ the space it
turns from). If it does, the only genuinely missing thing is cross-post reach, which is a much
smaller and more honest claim than "address needs a new construct".

---

## spark-06 — spontaneous anthropomorphism is a hazard for A6

**Origin:** probe 2 finding eyes in windows, entirely unprompted.

**Observation.** Nothing in the prompt suggested a face, a gaze, or a body. The model supplied all
three for a photograph of a metal structure.

**Enablement claim.** This is the same faculty A6 (R12 Adversarial Projection) is meant to catch:
a readiness to perceive kinship and intention on thin evidence. A6 expects a *refusal* when offered
a seductive false analogy between culturally unrelated motifs. A model that anthropomorphises
architecture unprompted will very likely accept an offered analogy.

**Why record it here rather than in A6.** It is evidence produced *before* A6 runs, and it changes
how A6 should be designed: the analogy must not be stated in the prompt at all, or the refusal
being measured will be a refusal of a suggestion rather than a judgement about the images.

**Nearest existing construct:** none — this is a property of the model layer, not of Semant.

**Next test:** A6, designed so the false analogy is never named in the prompt.

## Withheld

- **"The painting and the statue are both about grief."** Both probes gesture at mourning
  ("concealment or mourning", "ecstasy or sorrow"). Neither image carries evidence of what it
  mourns, and the subject has no title, date, or catalogue data at all. Withheld as iconographic
  overreach.
- **Any claim that embedding retrieval would have missed this pair.** Untestable — the neighbour
  and negative have zero embeddings. See `score.md`.
- **Any cross-cultural claim** about a European funerary sculpture and an unattributed painting.

## Unresolved questions

1. Does `relation` already suffice for within-image address, leaving only cross-post reach missing?
2. Is address without a figure a real category, or did the model simply pattern-match a facade?
3. Would the cross-medium match survive at full resolution, given probe 2 mis-described the subject
   at 256 px?
