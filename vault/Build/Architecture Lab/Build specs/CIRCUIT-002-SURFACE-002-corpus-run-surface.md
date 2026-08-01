# CIRCUIT-002 · SURFACE-002 — the corpus run surface + production record

**Branch:** `feat/run-surface` (worktree, off `main` after #112/#113)
**Lane:** A (backend). Lane B renders from `runViewFixture` until these routes are live.
**Contract:** `run-contract.md` at the repo root — owned by this lane, with the implementation
addenda marked inline.

## What this is

SURFACE-001 exposed ONE image, ONE Director pass, ONE plan. SURFACE-002 is the keystone that makes
the whole engine drivable by a person: **a set of images and a sentence go in**, the multi-round
loop runs over the corpus, and what comes back is the produced evidence, the article (when the
prompt is an argument), and a full per-actuator **production record** of what actually happened —
persisted, resumable, streamable.

```
POST /api/v1/runs {image_ids|tags, prompt, mode}  →  {run_id}
   corpus of RAW images → hydrate → run_loop (A1/A2/A2-EXT/A3) over routed actuators
   → quarantined suggestions + ProductionRecords (+ ArticleDraft in argue mode)
GET  /api/v1/runs/{id}          the RunView (poll)
GET  /api/v1/runs/{id}/events   the same RunView, streamed
POST /api/v1/runs/{id}/answer   A3 — the curator answers; the SAME run continues
```

## It is not a second engine

Everything that decides anything already existed and is *called*, not reimplemented:

| decision | owner |
| --- | --- |
| what to do next | `loop_controller.run_loop` (A1 / A2 / A2-EXT / A3) |
| what may run at all | `corpus.resolve_corpus` → `plan.resolve` |
| where a step runs | `corpus_execution.routed_registry` |
| what a claim may say | `argument` / `composition` / `article_resolver` (M2–M6) |
| how an item is known | `epistemics` (M5/M6) |

What is genuinely new is the **assembly**: the `RunView` envelope, and the `ProductionRecord` that
widens PROV-001's typed provenance into a manifest a reader can audit step by step.

## The governing principle, and how it is held

**Annotation-independent.** Memory is hydrated from `photo_url`, never from `region_annotations`.
`corpus_from_posts` takes a post because it *has a picture*; `hydrate_corpus` folds in whatever
committed evidence exists as a head start. The test that matters — a post with zero annotations
produces a full run, with real production records and real suggestions — is
`test_a_post_with_ZERO_annotations_produces_a_full_run`. The failure it prevents is a demo that
only works on the three posts somebody prepared by hand.

## Three decisions worth naming

**1. Fan-out across the corpus (`FanOutPlanner`).** Left alone, `resolve_corpus` defaults an
untargeted step to the corpus's FOCUS image — right for a plan a curator wrote ("the one I'm
looking at"), wrong for a run whose whole premise is a *set* of images: five photographs in, and
only the first is ever looked at. So the run surface stamps each single-image step with each image
before the loop sees it. Comparative actuators are not fanned out; seeing across images is their
job.

Stamping *before* the loop also keeps A1-FIX honest across a corpus. A step's signature is its
actuator plus its params; a step that gained its image at resolve time would have one identity when
proposed and another once the gate had seen it, and closed-door suppression — which matches on that
signature — would never recognise a refused step coming back.

**2. Per-image reconciliation (`CorpusResolver`).** `resolve_corpus` judges each image against ITS
OWN packet, but the loop carries one merged packet forward and `execute()` advances it with
projected ids (`step#kind@n`) that name a step, not an image. Across rounds that would leave the
per-image packets frozen at hydration — round 2 refusing a step for want of the region round 1
actually produced. The resolver therefore attributes each projected id to the image whose step
minted it (recorded from the plans it returned itself) and rebuilds the merged view from the
advanced per-image packets. Nothing is invented: the totals are the loop's own, only their ORIGIN
is restored.

The same reconciliation carries the curator's **phrase** into every per-image packet. That is not
cosmetic — it is what makes A3 work over a corpus, and it was a real bug found by a test: the
answer reached the merged packet, `resolve_corpus` judged the step against the per-image one, and
the answered door stayed shut.

**3. Two upstream seams, both small.**
- `run_loop(resolve_fn=…)` — the gate the loop resolves through, defaulting to single-image
  `resolve()`. The loop does not learn what a corpus is; the corpus hands it its own gate. Used at
  every resolve site including the closed-door recheck, or a door could be judged shut by one gate
  and open by another.
- `run_loop(on_round=…)` and `StepRecord.latency_ms` — progress out of a synchronous loop, and a
  manifest that can say how long a model took. The observer is told what has already been decided
  and its exceptions are swallowed: an observer that breaks the run is not an observer.

## The production record

Per executed step: `step_id`, actuator, status, params, model, adapter, **image**, **round**,
`consumed`, `produced[]` (with M5 epistemic status per item), `refusal`, `latency_ms`, `confidence`,
`detail`, `inputs_used`. Refused steps are on it too — a manifest listing only what ran would make
a plan of five steps look like a plan of three.

Two honesty details, both in the contract as addenda:

- **`produced[].id` is `null` for a quarantined suggestion.** It has no stored id until someone
  accepts it; minting one would dress a proposal as a record. `ref` (`{run_id}:{step_id}#{n}`) is a
  run-local handle instead.
- **`consumed` ≠ `inputs_used`.** `consumed` is what the step *demonstrably read* (explicit id
  params, sources its own descriptors name); `inputs_used` is what it *could see*. Collapsing them
  would let every record overstate what the step consulted.

## Persistence and A3 across a request boundary

`run_store` holds three things per run: the `RunView` (stored whole, so a receipt does not change
when the renderer does), A3's serialized `ResumeState`, and the resolver's `image_of` map (without
it a resumed run re-attributes the first half's evidence to the focus image). Unlike `vision_runs`
this is **not** write-behind: the document *is* the run's continuity, so a failed write is reported
rather than swallowed. Writing `resume: None` on every non-waiting save is what stops a late answer
resuming a run that has already continued.

## Verification

**+36 tests, all green** (`test_run_surface.py` 25, `test_run_routes.py` 11). Full backend suite:
**1149 passed, 9 skipped, 0 failed** (1113 → 1149).

- annotation-independent: zero-annotation raw post → a full run; every corpus image is looked at;
  committed annotations are a head start, never a requirement
- suggestions-only: every post document byte-identical, at both the driver and the route
- provenance: every descriptor carries `run_id`+`step_id`; the record joins each step to what it
  minted, with model, latency and M5 status per item; refusals carry the closed-vocabulary reason;
  unknowns are `null`
- A3: a run that needs a phrase asks and waits; the answer arrives in a **separate request** and
  continues the same run (trace extends, contiguous rounds, the blocked step then runs); an empty
  answer leaves it waiting; a run not waiting refuses one (409); an answered run cannot be answered
  twice
- honest emptiness: an unservable prompt → `stopped` with `nothing_planned`, empty suggestions
- argue mode: composes nothing (with a note) when no argument could be planned; composes against a
  chain that **ran** when one could; a composition failure is a note, never a failed run
- fixture: `RunView` serialises to `runViewFixture`'s shape; the fixture is generated by the real
  assembler; the JSON and the python literal cannot disagree

**A CI hazard this work caught:** the offline fixture silenced the *step* planner only, so an
argue-mode test was quietly calling the real Groq API — passing, over the network. Both planners
and the composer are now forced offline. A suite that reaches the network is the failure a suite is
least likely to notice about itself.

**One shared test-double fix:** `FakeCollection._match` compared `$in` against an array field as a
scalar, so a tag query the real driver answers came back empty. It now matches element-wise, like
Mongo.

### Guarded real run (real Groq, real models, real images, no DB, no accept)

In-memory scratch posts, post documents hashed before and after:

```
'read the material of the surface'   status=complete stop=fixed_point rounds=2 (38.3s)
  · find_parts       ok           yolo11n_seg+sam2_auto     31270.1ms → region_mask/visible
  · material_field   ok           facebook/dinov2-small      2495.8ms → brush_field/measured
  · semantic_read    unavailable  openai/gpt-4o-mini         1238.3ms → —   (honest, not an error)
  2 suggestions quarantined · weakest_link 0.9661 · posts byte-identical ✓

'check whether it is present'        status=awaiting_answer rounds=1 (1.1s)
  "To answer “Is the named thing actually there?” I need to know what to look for.
   Nothing has been found on this image yet, so there is nothing to point at."
  curator answers 'her folded hands' → status=complete rounds=2 (12.5s)
  · presence_check   ok           grounding_dino_tiny                 → presence_reading/interpretive
  answer accepted=True source=curator · resume_state serialised ✓ · posts byte-identical ✓
```

Both halves of the arc, on real weights, with the manifest and the epistemic status of every item.

**Item 6 — the live guarded run against Atlas is NOT executed here and is not faked green.** It is
gated on Atlas auth (currently down). What is untested is exactly one thing: the store's real
collection. Everything above it ran for real against `FakeCollection`, and the run above ran for
real against real models.

## Not in this gate

Per-round SSE granularity beyond what `on_round` publishes in-process (a multi-worker deployment
would need the store to carry partials); a `stopped` run cannot be re-tried from where it stopped
(only `awaiting_answer` is resumable, which is A3's contract); and the multi-param answer case
(A3's fork 2) is still open — one global phrase per run.
