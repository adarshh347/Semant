# R1 — Implementation report

**Branch:** `feat/rehearsal-research-r1` (from R0 `16650e8`, kept intact). **Roles:** Fable
orchestrated + wrote reports + ran the probe; Opus built the substrate + tests. **No production
ontology, surface, Atlas, Codex, Passage/Inquiry/Discovery/Embodiment, field, context-memory, or
agent-skill entity was created.**

## What R1 delivered

The **research substrate** — schemas, a deterministic capture/replay runner, Passage 001 imported
as reconstructed run #0, and tests — plus an honest (blocked) rendered probe.

### Files (all inside the declared boundary)

```text
architecture-lab/rehearsals/
  schemas/rehearsal-manifest.schema.json
  schemas/rehearsal-trace.schema.json        # append-only events[]; $defs/event; if/then null-reason rule
  schemas/candidate-card.schema.json         # epistemic_status SPARK…RETIRED; research_only:const true; percept_kind enum
  schemas/frozen-observation.schema.json
  protocols/event-grammar.md
  runs/000-passage-001/{manifest.yaml, source.md, trace.json, missing-telemetry.md, sparks.md}
  R1/*.md                                    # these eight reports
scripts/rehearsal_run.py                     # vendored validator + CAPTURE/REPLAY + CLI + classify_percept_id
scripts/rehearsal_adapters.py               # ALLOWLIST = {local_file_digest}; AdapterNotAllowed
backend/tests/test_rehearsal_r1.py          # 25 tests
```

### Runner shape

`rehearsal_run.py` is import-safe (no side effects), exposes importable functions + an argparse CLI,
and enforces the capture/replay contract (`R1-capture-replay-contract.md`): CAPTURE freezes a
`frozen-observation` from an allowlisted adapter; REPLAY uses only frozen observations and makes
**zero** adapter calls. `classify_percept_id` disambiguates `pct_` (attention) vs `pctx_`
(expression) and rejects bare ids. No `backend.database` / pymongo / motor import — a test asserts
this by source scan + `sys.modules` delta.

### Adapter scope (R1)

Only `local_file_digest` (pure, local sha256+size) is allowlisted — **no** SAM / YOLO / SegFormer /
DINOv2 / FashionCLIP / semantic / LLM call. Live sensory adapters are an R2 concern under explicit
approval.

## Verification (independently re-run by Fable)

- `pytest backend/tests/test_rehearsal_r1.py` → **25 passed**.
- **Capture/replay proof:** REPLAY of run #0 → `adapter_calls: 0`, reproduced the 14-event trace,
  status `completed`. CAPTURE of `local_file_digest` on the vault passage → froze one observation,
  `content_hash` sha256 `43225ff6…` matching `source.md` (and Fable's independent hash). The CAPTURE
  demo ran into a **scratch** runs-root so run #0 stays purely reconstructed (empty `observations/`).
- **Rendered probe: BLOCKED** — see `R1-existing-circulation-probe.md`. Not fabricated.

## Orchestrator fix applied

`.gitignore` line 15 (`runs/`, meant for Ultralytics artifacts) silently ignored the rehearsals
`runs/` tree. Added a scoped negation (`!architecture-lab/rehearsals/runs/` + `/**`) so research runs
are committed as inspectable memory. Minimal and additive; no other ignore rule changed.

## Boundary honoured

No git commit by Opus (Fable commits); no Mongo/production write; no new model; no Groq repoint; no
route/schema/entity; `new-planning/`, `vault/`, and the `R0/` reports untouched.
