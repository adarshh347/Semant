# R1 — Test and safety evidence

`backend/tests/test_rehearsal_r1.py` — **25 tests, all passing** (re-run independently by Fable:
`25 passed in 0.12s`). Coverage maps 1:1 to the amendment §9 requirements.

## Test coverage → requirement

| Requirement (§9) | Evidence |
|------------------|----------|
| schema validation | 4 schemas load; Passage-001 manifest + trace validate; a synthetic candidate-card validates |
| invalid event/reference rejection | event missing a required field / bad `kind` / additional property fails validation; `test_vendored_validator_rejects_wrong_types` guards the validator itself |
| reconstructed null telemetry | every run-#0 event asserted `reconstructed:true` with null `observation_ref`/`timestamp` + a null-reason |
| frozen-run overwrite refusal | capturing into an existing frozen run id raises `FileExistsError` unless `force_new_id` |
| capture/replay separation | adapter spy: **capture = 2 calls, replay = 0 calls** |
| no production DB writes | source scan + `sys.modules` delta assert the runner never imports `backend.database`/pymongo/motor; and writes only under `runs_root` |
| SPARK not silently promoted | all sparks asserted at SPARK; importing Passage-001 emits **zero** candidate cards |
| ambiguous `pct_`/`pctx_` | `classify_percept_id`: `pct_`→attention, `pctx_`→expression, bare/ambiguous→unknown, `None`→TypeError |
| failure/refusal terminal | a run ending `refused`/`stalled` writes a terminal refusal event **without raising** |

## Safety invariants held (verified)

- **No production mutation.** No Mongo/posts/region_embeddings write anywhere in the runner
  (asserted); the rendered probe touched no server/browser/data at all.
- **No sensory model call.** Only `local_file_digest` (pure/local) is allowlisted; a non-allowlisted
  adapter name raises `AdapterNotAllowed`. No SAM/YOLO/SegFormer/DINOv2/FashionCLIP/semantic/LLM ran.
- **No invented telemetry.** The schema's `if/then` forces a null-reason; run #0 has empty
  `observations/`.
- **No premature ontology.** Zero candidate cards; every construct at SPARK; `research_only:const
  true` on the card schema.
- **Determinism honesty.** Live output is never called deterministic; only replay is
  (`R1-capture-replay-contract.md`).
- **Geometry / curator identity untouched.** R1 wrote no geometry and no post; A–F invariants stand.
- **User-owned files preserved.** `new-planning/`, `vault/`, and `R0/*` unchanged; only a scoped,
  additive `.gitignore` negation was added so research runs are trackable.

## The one gap, stated plainly

The **rendered** percept→chip→recall probe is **not** verified (infrastructure blocker — all
long-lived servers exit 144 this session). The interaction's *logic* passes 56 existing frontend
unit tests, but that is **not** a substitute for rendered proof and is not claimed as one. See
`R1-existing-circulation-probe.md`.
