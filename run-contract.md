# Semant — the Run Contract

**Purpose:** the interface between the backend run surface (Lane A) and the demo frontend (Lane B),
pinned so both build in parallel and meet without a rewrite. Both lanes pin this with ONE shared
fixture (`backend/tests/fixtures/run_view_fixture.py`, and its `.json` twin) — the backend asserts a
real run serialises to this shape, the frontend renders from it.

**Status:** Lane A implemented (`SURFACE-002`). Sections marked **[addendum]** were decided during
implementation and are the changes Lane B needs to know about; everything else is as specified.

## The governing principle — ANNOTATION-INDEPENDENT
A run requires only **a set of images + a prompt.** No pre-filled regions, grounds, marks, or text
blocks are required — the actuators *produce* all evidence from raw pixels, and the prompt carries
the intent. Filled annotations, if present, are used as extra memory; their absence must never
block a run. This is a test, not a hope: a run on a post with zero annotations produces a full run
(`test_a_post_with_ZERO_annotations_produces_a_full_run`).

## Endpoints
- `POST /api/v1/runs` → start a run. Body: `{ image_ids?: [str], tags?: [str], prompt: str, mode?: "explore" | "argue", max_rounds?: int }`. At least one of `image_ids`/`tags`. Returns `{ run_id, status }`.
- `GET  /api/v1/runs/{run_id}` → the current `RunView` (poll).
- `GET  /api/v1/runs/{run_id}/events` → SSE stream of `RunView` frames (`event: run`). Poll is the fallback; both return the same shape.
- `POST /api/v1/runs/{run_id}/answer` → `{ answer: str }`. Resumes an `awaiting_answer` run (A3). Returns the updated `RunView`.
- `GET  /api/v1/runs` **[addendum]** → `{ runs: [{run_id, status, prompt, mode, created_at, updated_at}] }`, newest first. Added because the demo needs to find the run it just started.

All routes sit behind the curator API key, like every other authoring surface.

**Status codes.** 422 — no prompt, or neither `image_ids` nor `tags`. 404 — no posts matched, or no
such run. 409 — answering a run that is not waiting for one (including a run already answered: the
resume state is cleared when the run moves on, so a late answer cannot resume a run that has
already continued without it).

## Lifecycle
`pending → running → (awaiting_answer ⇄ running) → complete | stopped`

`awaiting_answer` carries a `question`; POSTing an answer resumes (A3). `stopped` carries the honest
stop reason from the loop. **[addendum]** `complete` means the loop converged (`fixed_point`) or ran
out of new evidence; every other ending — `nothing_planned`, `only_refusals_or_empties`,
`only_closed_doors`, `max_rounds`, `answer_did_not_unblock` — is `stopped` with its reason on the
receipt. Nothing is promoted: an empty run never reports as a complete one.

## RunView (the envelope — the contract's core)
```
RunView {
  run_id: str
  status: "pending"|"running"|"awaiting_answer"|"complete"|"stopped"
  intention: str                       // the prompt, verbatim; fixed for the run
  mode: "explore"|"argue"
  corpus: [{ post_id, image_url, title }]   // raw images; may have zero annotations
  rounds: [RoundRecord]                 // the LoopResult trace, as it already serialises
  question: Question | null             // present iff status == awaiting_answer (A2/A3)
  stop_reason: str | null
  weakest_link: float | null
  suggestions: [Descriptor]             // quarantined, never committed
  production_records: [ProductionRecord]// see below — the transparency data
  article: ArticleDraft | null          // present iff mode == "argue" (M4 shape)
  answer: Answer | null                 // [addendum] A3: what the curator said, and what became of it
  notes: [str]                          // [addendum] run-level notes (e.g. why argue composed nothing)
  created_at: str | null
  updated_at: str | null
}
```

**[addendum] `answer`** — `{text, missing_param, step_id, actuator, accepted, why, source, at_round}`.
On the receipt whether it was taken or REFUSED: an empty answer leaves the run `awaiting_answer`
with `accepted: false` and the same question, so the UI should re-offer the input rather than treat
the response as a new state.

**[addendum] while a run is still `pending`/`running`**, `GET` returns the same envelope with empty
collections plus a `progress` key (`{round, verdict, new_evidence, suggestions_so_far, …}`) carrying
the latest round the worker published. Terminal views never carry `progress`.

## ProductionRecord (per executed step — "the actuator tells, in full detail, what it produced")
```
ProductionRecord {
  step_id: str                          // from PROV-001
  actuator: str
  status: "ok"|"empty"|"unavailable"|"skipped"|"error"|"refused"
  params: { ... }                       // what it was called with
  model: str | null                     // e.g. gpt-oss-120b, yolo11n-seg, dinov2_vits14
  adapter: str | null
  image: str | null                     // [addendum] which corpus image this step ran on
  round: int                            // [addendum] which loop round
  consumed: [str]                       // ids of evidence this step read
  produced: [{ id, ref, kind, producer, epistemic_status, confidence }]
  refusal: { reason, detail } | null    // if the step was refused (closed set)
  latency_ms: float | null
  confidence: float | null              // [addendum] the step's own reported confidence
  detail: str                           // [addendum] the runner's own words
  inputs_used: { kind: count }          // [addendum] what the step could SEE — see below
}
```
This extends PROV-001's typed provenance (`run_id`/`step_id`/`producer`/`adapter`) into a full
manifest. Where a value is genuinely unknown, it is `null` — never fabricated. A refused step has no
model, no adapter and no latency, because it never reached a dispatch.

**[addendum] `produced[].id` is `null` for a quarantined suggestion**, and that is not an omission:
a suggestion is a proposal and has no stored id until a curator accepts it. Minting one here would
dress a proposal as a record. `ref` (`{run_id}:{step_id}#{n}`) is a run-local handle for pointing at
the item — safe as a React key, meaningless as a database id.

**[addendum] `consumed` vs `inputs_used`.** `consumed` lists ids the step *demonstrably read* —
ids it was explicitly called with, plus sources its own descriptors name. It is often empty, and an
empty list means "nothing was nameable", not "it read nothing". `inputs_used` carries the resource
COUNTS the step was handed. Two different facts, kept apart: collapsing them would let a manifest
overstate what a step actually consulted.

**[addendum] Refused steps appear in the manifest** with `status: "refused"` and the `refusal`
object. A manifest listing only what ran would make a plan of five steps look like a plan of three.

## Invariants (hold in every lane)
- **Suggestions-only.** A run never commits a mark, writes a post, or accepts anything. Post bytes
  are identical before/after — asserted at both the driver and the route.
- **Provenance everywhere.** Every produced descriptor and every ProductionRecord carries
  `run_id`+`step_id` (PROV-001).
- **Annotation-independent** (above).
- **Honest emptiness.** A corpus/prompt that yields nothing returns a `RunView` that says so
  (`status: "stopped"`, a real `stop_reason`, empty `suggestions`), not an empty success.
- **[addendum] Every image is looked at.** The run surface fans an untargeted step out across the
  whole corpus. `resolve_corpus` alone would default such a step to the FOCUS image — right for a
  plan a curator wrote, wrong for a run whose premise is a *set* of images.

## Lane B swap notes — three concrete deltas [addendum]

Lane B (#114) shipped `frontend/src/agentDemo/` against this contract before the routes existed,
with its own `runViewFixture.js` written from the spec and a docstring saying it should be deleted
when Lane A's lands. Comparing the two, three things need a change on the Lane B side when the
mock is swapped for the live endpoint. None of them is a disagreement about the shape — Lane B's
normalisers drop unknown fields, so the real payload renders today — but each would show something
subtly wrong.

1. **`produced[].id` is `null`; use `ref` as the key and the handle.** `ProductionPanel` does
   `key={p.id}` and renders `{p.id}`. Against the real payload every key is `null` (React duplicate
   keys) and the id column is blank. `id` stays null on purpose — a quarantined suggestion has no
   stored id until a curator accepts it, and emitting one would dress a proposal as a record. `ref`
   (`{run_id}:{step_id}#{n}`) is the run-local handle provided for exactly this.
2. **Adopt `status` on a production record.** `normalizeProductionRecord` drops it, so "produced
   nothing" is inferred from an empty `produced[]`. That conflates three different outcomes the
   backend distinguishes: `empty` (ran, honestly found nothing), `unavailable` (the model was
   down), `skipped` (an input never arrived). The panel already argues that a refusal is a result
   rather than an absence; the same argument applies here.
3. **`answer` explains a REFUSED answer.** POST `/answer` returns the updated view directly. An
   empty or unroutable answer comes back still `awaiting_answer`, with the same question and
   `answer.accepted: false` plus `answer.why`. Without reading it the page re-shows the question
   with no indication that the last attempt was declined, which reads as a lost click.

## Ownership
- **Lane A** implements the routes + assembles `RunView`/`ProductionRecord` and owns
  `runViewFixture` (`backend/tests/fixtures/run_view_fixture.{py,json}` — the `.py` generates it
  from a real run; the `.json` is the committed copy, and a test pins them together).
- **Lane B** renders from `runViewFixture` (mock) until Lane A's routes are live, then swaps the
  mock for the real endpoint.
- Changes to this contract are a shared decision, noted in both PRs.
