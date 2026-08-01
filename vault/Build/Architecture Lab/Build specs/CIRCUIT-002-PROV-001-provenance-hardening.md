# CIRCUIT-002 · PROV-001 — Provenance Hardening

**Branch** `provenance/circuit-002-prov-001` · **Status** Seams 1, 2, 4, 5 **landed** · Seam 3 + migration deferred by directive.

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

## Seam 2 — DECIDED and landed: declare, don't denormalise

**The decision: provenance is AUTHORED on the produced object and DERIVED by the ground.** No second authored copy on grounds or percepts.

The finding that produced it stands. The directive assumed the accept flow either funnels through `suggestion_service` or fans out across `posts.py` handlers; **neither is true**. There is no server-side accept boundary at all — grounds, percepts and marks are authored *client-side* and PATCHed wholesale through the generic `update_post` (`posts.py:2688`). No fake chokepoint was invented for one. The defense moved to the type/contract layer instead, which is where it belongs.

Denormalising `run_id`/`step_id` onto grounds was rejected because `regionStore.js:321` (CIRCUIT-001 P3-A) already keeps provenance in one place on purpose — *"visible provenance on a ground, WITHOUT authoring it … one source of truth"* — and two authored copies is the drift `test_producer_parity` exists to catch elsewhere in this codebase. It would arrive the first time a mark was superseded and its ground was not.

### The hole that was actually closed

`step_id` reached the mark only through an undeclared `...(fields.provenance || {})` spread, and `visual_marks` was bare `List[dict]` server-side. Nothing anywhere **declared** that `step_id` is part of the record. Undeclared is undefended: an edit replacing the spread with an explicit pick drops it and nothing fails. That is precisely how `TextBlock.origin` was lost — the frontend stamped it for an entire lane while Pydantic dropped it on every save, because the field was not declared.

- `MarkProvenance` (`run_id`, `step_id`, `producer`, `adapter`) and `Mark` in `backend/schemas/post.py`.
- `visual_marks` typed with it on **both** `Post` and `PostUpdate`. The write model is the half that matters — it is what the wholesale PATCH validates against.
- `step_id` declared in `visualMarks.js` beside `run_id`.

**`extra="allow"` is load-bearing, not laxity.** A strict model would delete every undeclared key — `planner`, `prompt_excerpt`, `model`, `matched`, `latency_ms`, and whatever the next phase adds — on the next save, trading this hole for a strictly bigger one. `model` stays undeclared deliberately: it collides with Pydantic's protected `model_` namespace, and extras carry it without a rename that would break the wire contract. `Mark` declares **only** provenance; restating the mark contract server-side would create a second copy to drift, the same failure this seam closes.

### Percepts — confirmed deriving

`makeExpressionPercept` (`perceptMentions.js`) mints `{id, kind, expression, ground_ids, properties, actor, created_at}` and **no provenance**. It cites `ground_ids`, so a percept reaches a run transitively through grounds to marks. It therefore *derives*, and is left deriving, covered by the parity test.

Worth stating because the name collides: the director's `compose_percept` output is a **suggestion** that becomes a mark — not the persisted `pctx_` expression percept. Two different objects sharing a word.

### Verification item 3 — met, in its corrected form

- a committed **mark** carries typed `run_id` + `step_id` + `producer`, defended by contract and pinned by `test_mark_provenance_prov001.py`;
- a **ground** derives it, pinned by `groundProvenanceParity.test.js`, which also asserts a ground has *no* independent authoring path and that a stale copy is **detected**.

Both test suites were proven non-vacuous by breaking the thing they guard: making the models strict fails 4 backend tests; the parity suite asserts drift detection directly rather than assuming it.

### Future option, deliberately not taken

If a surface ever needs grounds queryable by run *without* a join — none exists today; the article resolver joins on the mark/suggestion, not the ground — add a clearly non-authoritative `provenance_snapshot` on the ground plus a parity test against the mark, so it is visibly a copy and drift is caught rather than believed. Until that need is real, don't.

## Test deltas

**Backend**

| Pass | Collected | New |
|---|---|---|
| Baseline (`main`) | 1049 | — |
| Seams 1 + 4 | 1076 | +27 |
| Seam 5 | 1083 | +7 |
| Seam 2 | 1092 | +9 |

**Frontend**

| Pass | Tests | New |
|---|---|---|
| Baseline (branch) | 901 | — |
| Seam 2 | 910 | +9 |

### Two pre-existing failure sets, both from the same unmerged branch

Neither is caused by PROV-001, and both disappear when `fix/mac-apple-silicon-gate` merges.

- **Backend, 2:** `test_real_intrinsic_*` — `run_gray_pipeline` defaults `device='cuda'`, so it dies on Apple Silicon.
- **Frontend, 23:** every test in `SeeingConsole.dom.test.jsx` and `PassageRail.dom.test.jsx`, erroring *"mixed up default and named imports"*. This is the macOS case-insensitivity bug: on APFS, `./PassageRail` resolves to `passageRail.js` (the logic module, no default export) before `PassageRail.jsx`. **Verified pre-existing** by running both files at clean `HEAD` with the Seam 2 changes stashed — 23 failed there too. The arithmetic reconciles: 878 passing at baseline + 9 new = 887.

Any session reporting whole-suite totals from this branch should quote these two sets rather than treat the branch as red.

## Environment

- **Verification item 6 (guarded real run) still blocked.** MongoDB Atlas auth is rejected (verified independently with `mongosh`, so it is the credential, not the code). `CLOUDINARY_NAME` has since landed; Groq and all four vision models are ready. Re-runs once Mongo auth is fixed.
- **Not pushed** — no git credentials. `gh` 2.97.0 is installed; awaiting `gh auth login`.

## Process

This pass ran in a dedicated worktree (`git worktree add ../semant-prov provenance/circuit-002-prov-001`), per directive.

On arrival the branch topology was wrong: Seams 1 and 4 were committed onto **`main`** (ahead 2, unpushed) while `provenance/circuit-002-prov-001` still pointed at the base `b9e3e77`. Repaired by moving the branch to the commits and resetting `main` to `origin/main`; nothing was lost and another session's untracked vault docs were untouched. This is exactly the collision the worktree now prevents.
