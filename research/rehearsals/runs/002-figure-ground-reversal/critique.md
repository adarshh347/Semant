# 002 — Critique (meta-observation)

Adversarial pass over this rehearsal's own conduct. Where A1 is weak, it is said here.

---

## Where the rehearsal is weak

**1. The seed gesture leaked its own answer.** Probe 2 offered `NO_GROUND` as an explicit reply
option. The model taking it is therefore *much* weaker evidence than it looks — a compliant model
picks an offered escape hatch. The load-bearing evidence for the stall is the **pixel measurement**
(59.5 % literal black) and Probe 1's *unprompted* "no objects, textures, or gradients". Probe 2
corroborates; it does not establish. Future grounding probes should not name the refusal token.

**2. n = 1.** One image, one interval, one model. The "figure/ground reversal is unavailable to the
machine" claim rests on a single VLM's single answer plus a reading of the detection code. A second
model, or a detector actually run over the strip, would test it properly. Not done — the batch plan
caps A1 at 2 calls, and that cap was honoured over the temptation to keep probing.

**3. The strongest finding was not what A1 set out to test.** A1 was designed to test *non-object
Grounds*. What it actually found is the **artifact/depiction distinction** (spark-01) — reached
because the subject happened to be a composite plate. That is a genuine finding but partly an
accident of fixture choice, and it should be treated with the suspicion due to any result the
experiment was not designed to produce. spark-01's "next test" exists precisely to attack it.

**4. I got the ontology wrong on the first pass** and had to correct it mid-rehearsal. My initial
reading was that non-object grounds were unrepresentable. Checking `grounds.js` and
`DifferentialWorkspace.jsx` showed `field`/`boundary`/`frame` are fully constructible from freehand
geometry. Recorded because the corrected finding (*proposal* gap, not *representation* gap) is
sharper than the wrong one, and because the wrong version would have licensed a schema change the
evidence does not support.

**5. Interval bounds come from region boxes, not from the seam.** x ∈ [0.43, 0.46] is derived from
where the annotated *face* boxes end — not from where the composited *cutouts* end. The true
background gap is wider than the annotated gap. The measurement is valid for the strip as defined,
but "the space between the faces" and "the space between the photographs" are not the same
interval, and A1 measured the first.

## Where it held

- It did not fabricate a result. The predicted stall arrived and was reported as the outcome
  rather than being written around.
- It withheld the seductive sentence (`sparks.md` → Withheld) instead of quietly not thinking it.
- It stayed inside the 2-call budget and the 20 s throttle. No retries, no exploratory extra calls.
- It read production and wrote nothing to it.
- Three independent routes (measurement, open probe, grounding probe) were required to converge
  before the stall was called.

## Substrate findings (surfaced, not silently fixed)

- **The `virtual-rehearsal-score` protocol does not cover instrumented runs.** Its schema pins
  `"mode": { "const": "imaginative" }`, and `additionalProperties: false` leaves no room. A
  conforming `virtual-score.json` for A1 would have to **misdeclare its own mode**, so none was
  written. The user's schema was deliberately left untouched. This needs a decision before A2:
  either widen `mode`, or state that instrumented runs are indexed differently. Flagged, not
  resolved — it is the user's protocol.
- **Groq sits behind Cloudflare and bans urllib's default agent.** A missing `User-Agent` yields
  `HTTP 403 / "error code: 1010"` *before* the key is validated — a failure that reads exactly
  like a bad key or a dead model. Cost a diagnostic cycle; now documented at the call site.
- **The R1 runner hardcoded `local_file_digest`** in its capture loop, so the allowlist was not
  actually general. Generalised via an additive `probes` parameter; `capture_targets` untouched
  and all 25 pre-existing R1 tests still pass.
- **`capture_observation` hardcoded `latency_ms: None`** with the comment "not measured for a pure
  local digest". Left as-is it would have silently discarded the real latency of every model call.
  Now records telemetry only when the adapter actually measured it — still never inventing it.
