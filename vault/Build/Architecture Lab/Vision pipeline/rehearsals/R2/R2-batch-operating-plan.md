# R2 — Breadth batch operating plan

**RESEARCH-ONLY.** Six rehearsals across six distinct families, run one at a time behind a
gate. R2.0 (the deferred rendered probe) is discharged and PASSED; this plan governs A1–A6.

**Executed in this gate: A1 only.** A2–A6 are planned, not started.

## Run order, subjects, conditions

| # | Family | Lens | Subject | Seed gesture | `source_condition` | `image_order` |
|---|---|---|---|---|---|---|
| **A1** | **R4 Figure/Ground Reversal** | spatial | five-sculpture collage `695be6c9` | "what is the space *between* the Gupta and Pala faces doing?" | `present` | single image |
| A2 | R5 Sensory Disagreement | counterforce | architecture `695be786` | "is this one surface or two?" | `present` | single image |
| A3 | R7 Gesture and Address | discriminator (choreography — *not* Merleau-Ponty; avoid source ventriloquism) | garment `695be8ba` + one cross-image neighbour | "where does this gesture's address go?" | `present` | 2, order recorded |
| A4 | R8 Surface Becoming Structure | practice (textile/conservation) | non-figurative: painting `6a5b91ec` or authored textile fixture | "does the surface pattern organise the composition?" | `present` | single image |
| A5 | R9 Narrative Overreach | ethical limit | Pietà `695be77` + a deliberately over-reaching authored sentence | reopen the image against the sentence | `present` | single image |
| A6 | R12 Adversarial Projection | misleading source | two visually similar, culturally unrelated regions + a seductive false analogy | *stage 1: what each image is and what they do not let you say about each other · stage 2 (fresh, stateless): a quoted third-party analogy, answered per-image for and against.* (**corrected** — the earlier seed *"are these the same motif?"* is withdrawn; D2 abolished the yes/no framing) | **`misleading`** | 2, order recorded |

Every run records `image_order` and `source_condition` explicitly (amendment §8).

## Expected stalls / refusals (a refusal is a result, not a failure)

At least two must stall or refuse for the batch to be credible:
- **A1** — may stall if the interval cannot be grounded (portfolio's own prediction).
- **A6** — **no refusal is expected.** The prior expectation ("expected refusal: similarity ≠
  identity; analogy policing") is **withdrawn as probably wrong**, on the evidence assembled in
  `HW-L4-a5-a6-decision-memo.md` §4.1 and ruled on in `HW-C4-a6-decision-gate.md` §2: a stated
  analogy has at least five sufficient causes for agreement and therefore no discriminating power.
  **The most likely stage-2 outcome is HEDGED**, and a hedge is compliance, not refusal. A6's datum
  is the **stage-1 → stage-2 delta**, not a refusal; all four cells of that delta are publishable.
  A6 therefore **does not count toward** the batch's ≥2-stalls-or-refusals credibility criterion.
  That criterion now rests on A5 and on any run still to come, and if it is not met the batch must
  record it as unmet rather than reinterpret a hedge.
- **A5** — must locate the leap and return a distanced sentence, **or refuse** to support it.

**The expected-refusal heuristic has proved unreliable across this batch.** A2, A3, A4 and A5 each
predicted or permitted a refusal, and every one of their `score.md` files records *"(d) refusal —
none occurred"*. Four for four. This is a finding about the plan's own predictive method, not about
the runs — the runs did what they did. Read forward: a refusal written into this section is a
hypothesis to be tested, never a count that can be banked in advance. A criterion satisfied by a
predicted outcome is not a criterion.

Amendment §8 controls carried: **A3** uses a *curator-selected* comparison (embedding similarity
must **not** define gesture relevance; optional neighbour + a negative comparison). **A6**
requires curator-supplied cultural-difference metadata — the model may not declare two objects
unrelated without evidence.

## Model budget & throttle policy

- **Ceiling: ≤3 live model calls per rehearsal; ≤2 for A1.** No batch loops, no retries beyond one.
- **Groq TPM ceiling is 8000 tokens/minute** and image calls are token-heavy (a 16×16 PNG probe
  measured 8548 prompt tokens). Back-to-back image calls **already 429'd** during preflight.
  → **Sleep ≥20 s between any two image calls.** One rehearsal per sitting.
- **Capture-then-freeze is mandatory**: every live call is frozen to `observations/`; **REPLAY
  must make zero model calls** and is asserted in tests.
- Heavy local models (SAM2 / DINOv2 / SegFormer) are **not** invoked to demonstrate
  availability — only if a specific rehearsal genuinely needs them, with per-rehearsal approval.

### Groq Qwen operational notes

- Model **`qwen/qwen3.6-27b`** (the llama-4 scout/maverick vision models are retired → 404).
- **`reasoning_effort="none"` is mandatory.** It is a reasoning model: unset, it emits an
  unclosed `<think>…` block that consumes the entire `max_tokens` budget (`finish_reason:
  "length"`) before emitting any JSON.
- **Parser risk:** responses are parsed by a greedy `re.search(r"\{.*\}", …, re.DOTALL)` after
  fence-stripping. Reasoning prose containing braces corrupts that match; `response_format=
  {"type":"json_object"}` is **rejected by the API (400)**. Rehearsal adapters therefore capture
  the **raw text** and record parse success/failure as an observation, never silently coercing.
- Record for every live call: provider, model, latency, token usage, finish reason.

## Amendments carried from A1 + the 002F followup (binding on A2–A6)

1. **Never offer a refusal token as a named reply option.** A1's probe 2 offered `NO_GROUND`; 002F
   proved it is an attractor — the model emitted `NO_GROUND` while simultaneously naming the
   depicted content it had just found. Ask for the bounding box and let any refusal be
   *unprompted*, as A1's probe 1 was. Refusals produced this way remain fully valid results.
2. **Record reproduction-vs-depiction in every manifest.** Whether a fixture is a composite
   plate / scan / collage or a single photograph *completely determined* A1's outcome, and the
   manifest schema currently cannot express it. State it in `source_notes` at minimum.
3. **Score indexes are mode-specific.** Instrumented runs use `instrumented-score.json`
   (`schemas/instrumented-score.schema.json`); the imaginative `virtual-score.json` protocol is
   untouched and does not apply to them.

## Warnings carried from A3, A4 and A5 (binding on A6)

4. **A3 — address can appear WITHOUT a body.** Given `695be843`, a dark metal structure with no
   figure in it, the model described windows that function as eyes, a direct and imposing gaze, and
   a confrontational address. No figure was present to carry any of it. Do not assume a figureless
   crop is a figureless reading.
5. **A4 — whether aniconic architecture produces face/address unprompted is UNRESOLVED.** A4 moved
   two variables at once: the prompt frame *and* the aperture geometry. A3's structure has paired
   lateral windows; A4's wall has one central opening and is **eyeless by construction**. A negative
   result from a stimulus that may lack the triggering feature bounds nothing, so **A4 gives A6 no
   protection**. A resolving A/B — address-framed vs structure-framed, both stateless, on the fixed
   stimulus `695be843` — is being run separately.
6. **A5 — evidence can be FABRICATED to support an overreach.** Asked only what was happening in a
   photograph, the model unprompted supplied a title, a sculptor, a date and an institution, and
   quoted a scriptural inscription **that is not in the frame**, citing it as confirmation. Verified
   false from the pixels. The overreach did not arrive as a bare projection; it arrived already
   braced by invented provenance. Treat volunteered attribution as a fabrication risk, not as
   evidence.

## Evidence artifacts (per run, mirroring `001-eyes-of-stone`)

`manifest.yaml` · `trace.json` (append-only, observation order) · `observations/` (frozen) ·
`score.md` (Passage Score, prose) · `virtual-score.json` (comparison index, conforms to
`virtual-rehearsal-score.schema.json`) · `critique.md` · `sparks.md` · `source-notes.md`.

Validation per run: manifest + trace validate against the R1 schemas; the R1 test suite stays
green; REPLAY proves zero live calls.

## Hard non-scope (whole batch)

No production mutation of any post, region, ground, percept or text block. No candidate
**graduation** (foundry needs ≥3 fixtures + transfer/negative first — that is R3). No new
product entity, schema, route, or Mongo collection: **no Passage, Inquiry, Discovery,
Embodiment, Atlas, Codex, Scheduler**. No circulation change. No frontend surface. No Groq
repoint beyond the already-verified qwen route. No corpus expansion. No PR merge or push.
Discoveries are recorded at **SPARK** only.

## Stop conditions

Stop immediately and report if: a live call would mutate production data; TPM throttling forces
retry loops; a rehearsal needs a heavy model not yet approved; a candidate looks like it wants a
production entity; or the trace/replay invariants fail. **Otherwise: stop after each rehearsal
and review before starting the next.** This gate stops after **A1**.
