# Single-actuator labs

**Research only.** Nothing here defines a production entity, route or Mongo collection, and the
running app imports none of it. The lab reads the live production seams and measures them from
the outside without changing them.

## Why one actuator

A full orchestration run blends prompt interpretation, action choice, parameter extraction,
model availability, organ quality, wrapper conversion, downstream display and stopping logic.
When such a run "produced nothing", that sentence names no layer, and the next thing anyone does
is guess.

A lab run locks execution to **exactly one actuator**, spends **exactly one call**, and records
every boundary it crosses. That is enough to say which layer produced the outcome:

```text
organ succeeded, prompt phrase failed
organ failed on a good control phrase
organ succeeded but actuator conversion dropped data
negative control correctly returned empty
empty remains ambiguous pending review
```

SAM 3 / Director `concept_segment` is the first instrument. Later organs enter by **new
manifests and thin adapters**, not by custom, incomparable harnesses of their own — that is the
point of the pattern being here rather than in a one-off script.

## The three arms, and the two differences between them

| Arm | Mode | Input | Answers |
|---|---|---|---|
| A | `organ_direct` | image + explicit phrase | Given this image and this phrase, what did SAM 3 return? |
| B | `actuator_direct` | image + frozen `Step` | Does the `concept_segment` tool preserve and expose what the organ returned? |
| C | `prompt_orchestrated` | image + full prompt | Can the prompt-facing reasoning choose a useful concrete phrase for the one tool it has? |
| D | `replay` | frozen observations | Rebuild trace and score with zero model / GPU / network / actuator calls. |

Run against the same image, **A and B differ only by the wrapper**, and **C and A differ only by
who chose the words**. Three arms, two differences, and every failure lands on one of them. This
is why the manifests come in pairs (`pair_with`) — a single run in isolation attributes nothing.

## The capability firewall

Built before the SAM adapter, and every arm goes through it (`scripts/single_actuator_lab_support/firewall.py`).

- `actuator_lock` is a single string, not a list — a list is a thing someone widens.
- The call budget is **one**, and it is spent by *attempting*, not by succeeding. A budget that
  refunded failures would let a lab retry until something came back, which is searching for a
  result rather than measuring for one.
- A planner naming another actuator is **refused and recorded**, never filtered out of the
  proposal into apparent success. How often the mind reaches past its hands is the observable.
- Param keys are intersected with the **production** actuator's declared `param_keys`, so a
  manifest cannot widen the actuator and the actuator cannot widen an old manifest.
- Database write methods are **instrumented, not banned by import discipline**. Arm B runs the
  production runner, which imports route modules transitively — "the lab does not import a
  collection" would be a false guarantee, so every write method is wrapped and any call is a
  recorded violation.
- Replay mode makes every invocation *raise*. Zero live calls is a property of the harness, not
  a promise in a docstring.

`lock_held` is computed from what actually reached an instrument, never from what was configured.

## What the score may and may not say

`score.json` is split in two, structurally.

- **`measured`** — availability, planner validity, actuator leakage, invocation count, cold/warm
  latency, instance count and truncation, mask area / bounds / overlap / well-formedness,
  conversion survival, repeat stability, invariant violations.
- **`review`** — concept binding, coverage, boundary quality, false positives and negatives, IoU
  against a gold mask, and whether an empty result means true absence or a missed detection.

Everything in `review` starts **null**, and null renders as *unknown*, never as *pass*.
`verdict.semantic_correctness` stays `not_established` until a human or a gold mask moves it; the
harness will never write that field itself.

The reason is specific. SF-004-R2 §4.3 measured it: on a painting, `shoulder fabric` at
confidence 0.27–0.43 returned a clean, well-formed mask **of the background**. Valid RLE,
plausible area, sane bounds, a confidence — every automated signal said yes. The extent was
measured correctly and the words were simply wrong. **A mask is not correct because it is large,
confident, or cleanly encoded.**

## Layout

```text
labs/
  README.md
  schemas/     single-actuator-{manifest,trace,score}.schema.json
  manifests/   one YAML per capture; the manifest IS the lock
  runs/        one directory per run — trace.json, score.json, review.md,
               overlay.png, contact-sheet.png, observations/
  templates/   review.md skeleton
```

Run directories are **frozen**: `capture` refuses to overwrite one that already holds a trace.
Evidence that can be silently replaced under the same name is not evidence — use a new `run_id`.

## CLI

```bash
python scripts/single_actuator_lab.py capture  --manifest research/rehearsals/labs/manifests/sam3-fold-control.yaml
python scripts/single_actuator_lab.py replay   --run     research/rehearsals/labs/runs/sam3-fold-control-organ
python scripts/single_actuator_lab.py compare  --runs    research/rehearsals/labs/runs/sam3-fold-control-organ \
                                                         research/rehearsals/labs/runs/sam3-fold-orchestrated
python scripts/single_actuator_lab.py validate --manifest <yaml>
python scripts/single_actuator_lab.py validate --run <run-dir>
```

A live capture needs `SAM3_WEIGHTS` pointing at the checkpoint (~3.2 GiB, fetched out of band)
and the ML stack from `requirements-ml.txt`. Without either, a capture still runs and records
`availability: weights_absent` or `runtime_absent` — it reports the gap rather than skipping.

`--deterministic-framer` replaces Arm C's live planner with a frozen prompt→phrase mapping and
**says so in the trace**. It is never a silent stand-in for an unavailable model: that
substitution would turn an orchestration failure into an orchestration success in the record.

## Suites: the pre-registered matrix (HARNESS-001C2)

A single capture answers "what did this phrase do on this picture". A **suite** answers "what
does this *family* of phrasings do across a *set* of pictures" — and it answers that honestly
only if the phrases were written down first.

```bash
python scripts/single_actuator_lab.py matrix --suite sam3-fold-phrase-matrix --plan
python scripts/single_actuator_lab.py matrix --suite sam3-fold-phrase-matrix --live
python scripts/single_actuator_lab.py matrix --suite sam3-fold-phrase-matrix --replay
python scripts/single_actuator_lab.py matrix --suite sam3-fold-phrase-matrix --report
```

`--plan --freeze` writes the content digests into the suite's `lock` block. Legal only **before**
collection begins; afterwards the harness refuses.

**Why the freeze.** An open-vocabulary organ can be made to look capable by trying phrases until
one lands and reporting the survivor. That number reads as a hit-rate and is the outcome of a
search — and nothing in a trace tells the two apart afterwards, because a phrase tried third and
a phrase tried thirtieth leave identical records. So `lock.phrases_sha256` is declared in the
suite, frozen into `runs/<suite>/collection.json` at the first live capture, and re-checked at
every later `--live` and `--report`. Editing a phrase mid-collection moves the digest and the run
stops. The digest covers **roles** as well as strings: moving `bicycle` out of `negative_control`
would leave the phrase set identical while inverting what a hit means. Fixture ids are locked to
their content hashes for the same reason.

**The availability gate.** Each suite declares an `availability_control` family. If it returns
nothing on a fixture, every other empty on that fixture is *uninterpretable* — nothing separates
a phrase the organ cannot bind from an organ that was never working on that picture. Gated
fixtures drop out of the curve and their empties attribute to `not_established`, never to the
phrase. Without it, a fixture the instrument simply fails on contributes a column of zeroes that
reads exactly like a robustness finding.

**Bounded attribution.** `instrument_unavailable`, `planner_reach_refused`,
`phrase_conditioned_empty`, `wrapper_loss`, `semantic_mismatch`, `instrument_class_gap`,
`not_established`. The last two are **review-only** and scoring code can never write them.
`instrument_class_gap` is the conclusion such a lane most wants and exactly the one it may not
reach on machine scores: a pile of phrase-conditioned empties is evidence of absence only once a
human has confirmed the target was there to be found.

**No retries.** An empty is a result and is recorded as one. Re-issuing on empty would turn the
most important observation a matrix can make — that a frozen phrase returns nothing — into a
sampling artifact, invisibly. Frozen cells are skipped on a resumed run rather than re-spent.

**Planner samples spend no attempts.** `planning_only: true` is declared in advance and honoured
structurally: the sampler calls `firewall.authorize` and never `firewall.invoke`, so
`sam_invocations: 0` is measured rather than promised, and a planning-only receipt carries
`kind: planning_only` with no organ observation so nothing can mistake it for an organ empty.

## Adding an instrument

1. A manifest naming the new `actuator_lock` (it must exist in the production capability table).
2. If the organ is not `sam3_concept_service`, a thin arm that calls it and returns the same
   normalised observation shape.

Not a new harness. Two organs evaluated by two harnesses cannot be compared, and the comparison
is the reason to have any of this.
