# Rehearsal Foundry — sandbox home

**RESEARCH-ONLY.** Nothing in this folder defines a production entity, route, Mongo collection, or
UI surface. Nothing here is imported by the running app. Every artifact is Markdown or JSON/YAML.

The Foundry lets the program run **parallel discovery tracks on different axes** without each track
having to re-derive the safety rules from a prompt. The rules live in a schema and a runner; a
session that forgets them gets an error, not a bad run.

```text
foundry/
  README.md                this file
  schemas/                 foundry-sandbox.schema.json — the sandbox manifest contract
  templates/               sandbox-manifest.yaml + the five reporting stubs
  sandboxes/               FS-###-*.yaml — standing sandbox declarations (designed, not run)
  runs/                    one dir per run — created by `foundry_run.py init`
  decisions/               ADRs when two sandboxes conflict (decision docs, never code races)
```

## Relationship to what already exists

This is **not** a second research program. It sits on top of the R1/R2 substrate:

| existing thing | the Foundry's relation to it |
|---|---|
| `scripts/rehearsal_run.py` | `scripts/foundry_run.py` imports it — same vendored validator, same loaders |
| `rehearsal_adapters.ALLOWLIST` | the only adapters a sandbox may name; no separate allowlist |
| `schemas/frozen-observation.schema.json` | foundry observations validate against it unchanged |
| `new-planning/06-candidate-foundry.md` | **the promotion ladder.** Sandboxes feed it; they do not replace it |
| `R2/HORIZON-BRIEF-template.md` | the brief format. `templates/horizon-brief.md` adds four foundry sections |

A **rehearsal** asks what a particular encounter reveals. A **sandbox** is a standing declaration of
an axis, a budget, a stop condition, and a graduation rule — the thing a rehearsal runs *inside*.

## The eight axes

One sandbox declares exactly one axis. A sandbox that moves two axes cannot attribute its result.

`evidence-honesty` · `creative-circulation` · `textual-dynamism` · `model-orchestration` ·
`communication-quality` · `ui-emergence` · `seed-ecology` · `agent-skill-emergence`

R2 has so far produced almost exclusively **evidence-honesty** findings (detachment, false
reattachment, recall honesty, external-authority hallucination, prompt vocabulary creating
relations). The other seven axes are unexplored, which is the reason this folder exists.

## Using the harness

```bash
# validate a sandbox declaration (schema + semantic guards)
./venv/bin/python scripts/foundry_run.py validate "…/foundry/sandboxes/FS-001-creative-circulation.yaml"

# scaffold a run, hash its seeds, generate the reporting stubs
./venv/bin/python scripts/foundry_run.py init      "…/FS-001-creative-circulation.yaml"
./venv/bin/python scripts/foundry_run.py freeze    "…/FS-001-creative-circulation.yaml"
./venv/bin/python scripts/foundry_run.py summarize "…/FS-001-creative-circulation.yaml"

# reproduce from frozen artifacts — makes ZERO adapter calls, by construction
./venv/bin/python scripts/foundry_run.py replay    "…/foundry/runs/FS-001-creative-circulation"
```

There is **no `capture` command in v1.** Live model calls are a deliberate future extension and
require an approved budget in the manifest — see the plan.

## The rules the runner actually enforces

Not advice — validation failures:

- `research_only: true` and `mode: foundry`, or the manifest is rejected.
- `forbidden_actions` must be a **superset** of the six-item baseline (`mutate_production_db`,
  `create_backend_route`, `create_mongo_collection`, `create_product_entity`,
  `create_frontend_surface`, `modify_product_code`).
- No input or seed may contain a production marker (`mongodb://`, `backend/routers`,
  `frontend/src`, `region_embeddings`, `.env`, …).
- Every named adapter must already be in `rehearsal_adapters.ALLOWLIST`.
- `max_live_calls > 0` requires `approved: true` — raising a budget is a **visible, reviewable diff**.
- `replay_policy` must be frozen-only with `adapter_calls_permitted: 0`.
- A sandbox emits **SPARK** and nothing else. **No single sandbox can create a production entity.**

## Graduation

```text
SPARK  →  repeated pattern  →  candidate card  →  build spec  →  prototype  →  product implementation
  ↑         (>= 2 runs)         (enablement       (explicit      (reversible)   (ADR + contract)
  |                              claim)            build gate)
  └── a sandbox may only ever produce this leftmost box
```

This maps onto the Candidate Foundry's existing ladder (`new-planning/06-candidate-foundry.md`:
SPARK → CANDIDATE → TRIAL → SUPPORTED → PROTOTYPE → GRADUATED). The Foundry adds no new gate; it
supplies the SPARKs and the discipline that stops one exciting run from jumping the queue.

See `Plans/Rehearsal Foundry Harness.md` for the protocol-vs-harness argument, the parallel
operation model, and what this does not authorize.
