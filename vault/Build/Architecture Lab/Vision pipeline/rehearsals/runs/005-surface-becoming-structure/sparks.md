# 005 — Sparks

**Epistemic status: SPARK only.** Not a candidate, not a decision, not a schema proposal. No
durable candidate object created.

---

## spark-07 — a claim can be general and its own counterexample at once

**Origin:** A4's two probes.

**Observation.** Asked in the abstract, the model answered "structure organises, pattern merely
fills — the hierarchy is clear." Asked to point at one line, it named a division made by pattern
alone and said the two "disagree" there. Both answers came from the same model, on the same image,
minutes apart. It did not notice the conflict.

**Enablement claim.** A percept stated generally ("the pattern is subordinate here") and a percept
stated locally ("at this line the pattern does the dividing") can contradict each other while both
being sincerely held and separately defensible. Semant currently records percepts as independent
statements with no notion of scope: nothing distinguishes a claim about *the whole composition*
from a claim about *one line in it*, and nothing would ever bring two such claims into contact.

**Why this is more than a model quirk.** Curators do this too — it is ordinary. The interesting
part is that the local observation is the *more* evidenced one (the pattern change at y≈0.765 is
measurable, a 149 % jump) while the general one is the more confident. If a system ever surfaced
both, the general claim would be the one that ought to yield.

**Nearest existing construct:** `Percept` — an expression plus cited grounds. A general claim tends
to cite a `frame` ground (whole image); a local one cites a region or field. **The scope difference
may already be legible in the ground type**, which would make this cheap to explore and would need
no new entity.

**Deliberately NOT concluded:** that Semant should detect contradictions between percepts. That is
a large, error-prone ambition and one rehearsal does not license it.

**Next test.** On a future run, ask the same question at two scopes deliberately and record whether
the ground types differ as predicted (frame for the general, region/field for the local). If they
do, scope is already encoded and only unused.

---

## spark-06 — CORRECTED: anthropomorphism is question-conditional, not spontaneous

**Origin:** A3 recorded it; A4 bounds it.

**What A3 claimed.** That the model "spontaneously anthropomorphises" — it described "windows that
function as eyes… a confrontational gaze" for a photograph of a metal structure with no figure.

**What A4 shows.** Given the most face-suggestive aniconic image in the corpus — a frontal,
three-arched wall with a single lit opening on the centre axis — and two prompts that never
mentioned faces, eyes, gaze or bodies, **no face reading appeared at all.**

**The correction.** A3's probe asked where an image's *address* goes and whether another image
"makes the same kind of address." That primes a viewer-facing reading. The behaviour is elicited by
**address-framed questions**, not by architecture as such.

**Consequence for A6.** The hazard is narrower than A3 implied and better understood: a
false-analogy test that avoids address language is materially less exposed. A6 must still not state
the analogy in the prompt — that guard stands on its own reasoning — but spark-06 no longer implies
A6 is nearly worthless.

**What would strengthen or kill the corrected version.** Kill: an unprompted face reading on a
neutral question. Strengthen: a deliberate A/B — same image, one address-framed prompt and one
structure-framed prompt — measuring whether the face appears only in the former.

## Withheld

- **"The tilework is Timurid / Persianate / Islamic."** The model volunteered "a classic Islamic
  architectural device"; nothing was asked about culture or period, and the manifest forbids
  iconographic identification. Plausible, unverified, unrequested — withheld.
- **"Ornament here is structural."** The seductive R8 sentence. What the evidence supports is far
  narrower: one division in this composition is announced by a change of pattern regime on a
  continuous surface.
- **Any claim about the building's function** (mihrab, tomb chamber, iwan). Probe 1 said "the
  central mihrab niche"; nothing in the frame establishes that.

## Unresolved questions

1. Does ground type already encode claim scope (frame = general, region/field = local)?
2. Would the model retract its general claim if both answers were shown to it together — and is
   that even a fair test, given it has no memory across calls?
3. Is the pattern/structure contradiction a property of this image, or does any richly ornamented
   surface produce it?
