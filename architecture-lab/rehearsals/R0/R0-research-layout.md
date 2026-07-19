# R0 — Research-only repository layout

**Status:** proposal (nothing created yet beyond this `R0/` folder of reports). Read-only gate.

## Principle

The Rehearsal Research Program must live **entirely separate from production ontology**. Nothing
under this layout is a Mongo collection, a Pydantic model on `Post`, a React route, or an entity.
It is Markdown + JSON/YAML + (later, R1) a deterministic runner. No `Passage`, `Discovery`,
`Embodiment`, `Candidate`, `Field`, or context-memory *production* type is created by this program;
those names may appear only as **research artifacts** (cards, traces) that resolve back to real
evidence but never persist as product schemas until the Candidate Foundry graduates them.

## Proposed layout (matches `03-harness-architecture.md §minimal repository layout`)

```text
architecture-lab/rehearsals/
  README.md                     # what this is / is not; links to new-planning/ doctrine
  R0/                           # THIS gate — reality reports (no code)
    R0-reality-map.md
    R0-contract-and-route-trace.md
    R0-conflict-table.md
    R0-research-layout.md        (this file)
    R0-passage-001-import-plan.md
    R0-breadth-portfolio.md
    R0-existing-adapters.md
    R0-file-boundaries-and-conflicts.md
    R0-risks-and-blockers.md
    R0-recommendation.md
  protocols/                    # R1+: versioned rehearsal input packets + event grammar
  fixtures/                     # R1+: deterministic seed constellations (images+text+ids), provenance-marked
  runs/                         # R1+: one dir per run — raw append-only trace (frozen) + Passage Score
  candidates/                   # R1+: Candidate Embodied Construct (CEC) cards (yaml, epistemic_status)
  evaluations/                  # R1+: transfer/negative/sequence-inversion/critique results per candidate
  skills/                       # R6+: versioned agent-skill definitions (only after multi-run support)
  decisions/                    # ADRs: graduate/retain/revise/demote/retire, with rejected alternatives
  schemas/                      # R1+: trace + candidate-card JSON schemas (research schemas, NOT product)
```

## Why `architecture-lab/` and not `backend/` or `frontend/`

`architecture-lab/` already holds every increment's reports, build plans and decisions (A–F, the
atlas/codex bridge concept, lane plans). It is the established home for non-shipping design memory
and is never imported by the running app. Placing rehearsals here guarantees the research layer
cannot accidentally become a production dependency.

## Separation rules (enforced by convention in R0, by a runner boundary in R1)

- **Read production, never write it.** Adapters (see `R0-existing-adapters.md`) call existing
  read paths (image fetch, retrieval, VLM read, projection) in *imaginative*/*instrumented* mode.
  Any write in R1 goes to `runs/` on disk, never to Mongo `posts`/`region_embeddings`.
- **Four execution modes stay unblurred** (doctrine §execution modes): imaginative (no product
  writes) · instrumented (real read paths + on-disk trace) · prototype (lab/dev flag only) ·
  product (graduated only). R0 is pure inspection; R1 is imaginative + instrumented.
- **Candidate cards are research memory, not schemas.** A card names a hypothesis (`address field`,
  `context breathing`) with `epistemic_status: opening|trial|supported|graduated|demoted|retired`.
  It never implies a Mongo document exists.
- **Traces resolve to real ids** (post/region/ground/percept) but copy no geometry — they store
  references, exactly like a Mention resolves evidence on demand.

## What the runner will and won't be (R1 scope preview, not authorized here)

Will: a deterministic Python module under `architecture-lab/rehearsals/` (or `scripts/`) that loads
a fixture packet, replays an event grammar, calls read-only adapters, and writes a frozen trace +
Passage Score to `runs/`. Won't: a user-facing `/rehearsal` route, a `rehearsals` Mongo collection,
or any production entity. This is deferred to R1 and is explicitly **not** built in R0.
