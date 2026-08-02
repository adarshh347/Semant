# 005 — Critique (meta-observation)

Adversarial pass over A4's own conduct.

---

## Where the rehearsal is weak

**1. The contradiction may be an artifact of asking two differently-shaped questions.** Probe 1 asked
for a global judgement; probe 2 asked for a single line. A model with no memory between calls is
not "contradicting itself" in the way a person would — it is answering two prompts independently.
The finding is real as an observation about *outputs*, but `sparks.md` deliberately frames it as a
property of **claims at different scopes**, not as evidence the model is confused. Overstating it
as self-contradiction would be the easy, wrong version.

**2. Probe 2's question contained a nudge.** "State whether that division is made by the built
structure… or by a change in the surface pattern itself" offers exactly two options and names the
pattern option second. A freer question ("what makes that line a line?") would have been better
evidence. The location it gave is independently confirmed by measurement; the *attribution* is
weaker than it looks.

**3. n = 1 image, 1 model, 2 calls.** Every claim here is bounded by that.

**4. The spark-06 correction rests on a negative result.** "No face appeared" is weaker evidence
than "a face appeared." A single image and two prompts cannot establish that anthropomorphism is
*only* address-conditional — only that it did not occur here, on the image most likely to provoke
it. The A/B test named in `sparks.md` is the honest way to settle it and was not run.

**5. My own pre-registration may have shaped the reading.** The manifest recorded the competing
organisers (the lit window, the dado change, the damage) *before* probing — which is good practice
and prevents retrofitting. But it also means I was primed to find the dado line significant, and
the measurement I chose (edge density per band) is one that would surface exactly that. A different
measure might have foregrounded the arches.

## Where it held

- **Native resolution.** A4 ran unscaled, deliberately repairing A3's 256 px confound. No
  description in either probe was degraded by downsampling.
- **Amendments honoured.** No refusal token named; `reproduction_vs_depiction` recorded per image;
  no anthropomorphic priming in either prompt — which is what made the spark-06 test valid.
- **The stall was a live possibility, pre-registered, and did not have to be avoided.** The
  manifest stated in advance that the question might be undecidable. It turned out decidable. That
  order — predict, then run — is what makes the result worth anything.
- **The model's cultural overreach was recorded rather than quietly used.** "A classic Islamic
  architectural device" would have been a tempting sentence to keep.
- **The measurement checked the model rather than illustrating it.** Probe 2's location was
  confirmed independently; its characterisation was not, and the score says so.
- Production read, never written. Nothing graduated.

## Substrate notes

- No substrate changes were needed this run — the first rehearsal in the batch for which that is
  true. `reuse_frozen`, multi-image probes, and provider-error surfacing all held from A3.
- One image at native resolution cost ~2000-2300 tokens per call, comfortably inside the 8000 TPM
  ceiling with `max_tokens: 1200`. **Single-image rehearsals are cheap; the constraint is entirely
  a multi-image problem.**
- The model emitted decorative scaffolding in probe 2 (markdown headers, a ✅ "Final Answer"
  block) that no prompt requested. Harmless here because raw text is frozen and never parsed — but
  it would break any future rehearsal that tried to parse structured output.
