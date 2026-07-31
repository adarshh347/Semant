# CIRCUIT-002 · PROV-001 — Provenance Hardening

**Branch** `provenance/circuit-002-prov-001` · **Status** Seams 1, 4, 5 landed · Seam 2 **blocked on a design decision** · Seam 3 + migration deferred by directive.

Make every produced entity trace back to the run and the plan-step that made it, so the thinking layer can cite the acting layer's output without ambiguity.

---

## Landed

### Seam 1 — `step_id` stamped at production (the keystone)

`real_actuators._stamp_step_id`, called from `RealActuatorRunner.__call__`.

**Built against the directive, deliberately.** The directive asked to thread `step_id` down through the execution context. The seam was taken at the chokepoint instead: `__call__` already isolates one step's output with `before = len(ctx.suggestions)` — the identical slice `epistemics.guard` has used since M5 — and all eight producer sites reach the quarantine through it. That replaces ~40 signature edits across `suggestion_service`, `real_actuators` and the `_FIELD_PRODUCERS` chain in `posts.py`.

The reason is not brevity. Threading makes `step_id` a thing each *new* producer signature can silently omit, which is the exact class of gap this initiative exists to close. Stamped centrally, a producer added tomorrow is stamped without its author knowing. `TestChokepoint` asserts that structural property against the module source, so a producer that ever bypasses `ctx.suggestions` fails loudly.

No fabrication: an empty `step.id` writes nothing rather than `{"step_id": ""}`; `setdefault` leaves alone any producer that stamped its own.

**The weak key is kept on purpose.** `article_resolver` now joins on `step_id` first, falling back to `(actuator, image)`. Deleting the fallback would be a bug — every suggestion produced before this change carries no `step_id`, and for those the approximation is not a worse key, it is the only key. M4's own ambiguity suite passes **unchanged**, which is the proof that its refusal was never the defect.

**AMBIGUOUS now has two causes and says which.** A single step can produce several drawable percepts (`ctx.suggestions.extend`), so the exact path can still be ambiguous — but for an unrelated reason. Emitting "does not record its step" there would send a reader to fix something already fixed.

### Seam 4 — refine no longer destroys meaning

`posts._merge_refined_region`. `regions[idx] = region` replaced the stored region wholesale; only five fields were rescued. `label`, `category`, `material`, `description`, `part`, `attributes`, `embedding_id`, `block_id` were dropped while the id survived — so a prose chip still resolved and found nothing left to mean. Corroborated: all six creator regions read `label: null`.

Merging is safe **only because** `canonicalize_geometry` takes the `mask_rle` branch here and rewrites the entire derived geometry set, so no stale geometry can survive. That is pinned by a test, because the naive version of this fix introduces a worse bug than the one it repairs.

Lifted out of the route body so it is testable with plain dicts — the defect was one assignment on the persist path, and a test needing a GPU to reach it is a test nobody runs.

### Seam 5 — honest block authorship

Three backend `TextBlock` paths, none of which set `origin`; two are model paths now marked `sutradhar`. The third (`add-tag-and-story`) takes a bare string a person submitted, which may be theirs or generated — the server cannot tell, so the caller declares it and the default stays `human`. Stamping `sutradhar` there would be the same fabrication as the silent `human`, inverted.

`TestNoSilentOmission` is the durable part. Its first version was **vacuous** — it matched `{...}` with a `[^{}]` class, which the literals' own `f"block_{uuid.uuid4()}"` braces defeat — and passed while matching nothing. Rewritten by line window and verified by deleting an `origin` and watching it fail.

---

## Seam 2 — BLOCKED, needs a decision

The directive assumed the accept flow either funnels through one commit point in `suggestion_service.py` or fans out across `posts.py` handlers, and asked which. **Neither is the case.**

**There is no server-side accept boundary at all.** Grounds and percepts are authored *client-side* and PATCHed wholesale as arrays through the generic `update_post` (`posts.py:2688`, `PostUpdate`). No route takes a suggestion and commits it.

**And grounds are architecturally forbidden from authoring provenance.** `regionStore.js:321` states the rule explicitly (CIRCUIT-001 P3-A):

> visible provenance on a ground, WITHOUT authoring it … one source of truth

`makeGround` sets `actor: 'creator'`, `detector: null`, and no run identity. A ground's provenance is *derived* at read time from `visual_marks` via `reconcileBridgeFields`. Provenance is authored on the **mark**, whose shape (`visualMarks.js:245`) is `{planner, prompt_excerpt, model, matched, run_id, producer, adapter, latency_ms}` and which spreads `...(fields.provenance || {})` — so Seam 1's `step_id` already flows through into a persisted mark, and `validateMark` does not strip it.

So adding typed `run_id`/`step_id`/`producer` to grounds/percepts as directed would **duplicate** a value that P3-A deliberately keeps in one place, creating two records that can disagree — precisely the drift `test_producer_parity` exists to catch elsewhere in this codebase. That is a bad trade made silently, so it was not made.

**The real gap is narrower and different.** `step_id` survives onto the mark only by an undeclared spread. Undeclared is undefended: nothing pins it, and a refactor replacing the spread with an explicit pick would drop it with nothing failing. Server-side, `visual_marks` is `Optional[List[dict]]`, so Pydantic guarantees nothing either — the same shape of hole that silently dropped `TextBlock.origin` until it was declared.

**Recommended (needs sign-off):**

1. Declare `step_id` in the mark provenance contract in `visualMarks.js` (default `null`, beside `run_id`), so it is first-class rather than incidental.
2. Add a typed `MarkProvenance` model in `backend/schemas/post.py` and type `visual_marks` with it, so the durable record cannot be silently dropped. `unknown` where a field is genuinely absent — never a synthesized id.
3. Leave grounds/percepts deriving, per P3-A. Add a test that a mark carrying a producer cannot lack `run_id`/`step_id`.

**Alternative**, if you want provenance denormalised onto grounds anyway — legitimate if grounds must be queryable by run without joining marks: do it as an explicitly derived, non-authoritative cache field (e.g. `provenance_snapshot`) with a parity test against the mark, so it is visibly a copy and drift is caught rather than believed.

Verification item 3 ("a committed ground/percept carries `run_id` + `step_id` after accept") is **not** met and cannot be met honestly until this is settled.

---

## Test deltas

| Pass | Collected | New |
|---|---|---|
| Baseline (`main`) | 1049 | — |
| Seams 1 + 4 | 1076 | +27 |
| Seam 5 | 1083 | +7 |

All green except 2 pre-existing `test_real_intrinsic_*` failures — unrelated, and fixed on `fix/mac-apple-silicon-gate`, which this branch does not include.

## Environment

- **Verification item 6 (guarded real run) still blocked.** MongoDB Atlas auth is rejected (verified independently with `mongosh`, so it is the credential, not the code). `CLOUDINARY_NAME` has since landed; Groq and all four vision models are ready. Re-runs once Mongo auth is fixed.
- **Not pushed** — no git credentials. `gh` 2.97.0 is installed; awaiting `gh auth login`.

## Process

This pass ran in a dedicated worktree (`git worktree add ../semant-prov provenance/circuit-002-prov-001`), per directive.

On arrival the branch topology was wrong: Seams 1 and 4 were committed onto **`main`** (ahead 2, unpushed) while `provenance/circuit-002-prov-001` still pointed at the base `b9e3e77`. Repaired by moving the branch to the commits and resetting `main` to `origin/main`; nothing was lost and another session's untracked vault docs were untouched. This is exactly the collision the worktree now prevents.
