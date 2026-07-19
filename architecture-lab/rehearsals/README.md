# Semant Rehearsal Research Program — repository home

Research memory for the two-loop program defined in `new-planning/` (doctrine `01`, candidates `02`,
harness `03`, repertoire `04`, foundry `06`, protocol `08`, plan `09`). **This folder is research
only** — Markdown + JSON/YAML (+ a deterministic runner from R1). It defines **no** production
entity, route, or Mongo collection. Nothing here is imported by the running app.

```text
rehearsals/
  R0/           reality reconciliation reports (this gate — read-only, no code)
  protocols/    (R1+) rehearsal input packets + event grammar
  fixtures/     (R1+) deterministic seed constellations, provenance-marked
  runs/         (R1+) one dir per run — frozen trace.json + Passage Score
  candidates/   (R1+) Candidate Embodied Construct cards (epistemic_status)
  evaluations/  (R1+) transfer / negative / sequence-inversion / critique results
  skills/       (R6+) versioned agent skills (only after multi-run support)
  decisions/    ADRs — graduate / retain / revise / demote / retire
  schemas/      (R1+) research trace + candidate-card JSON schemas (not product schemas)
```

**Start here:** `R0/R0-recommendation.md`. Invariants: `mask_rle` authoritative; semantics/narrative
never mutate geometry; curator identity sticky; similarity is research, never truth; no corpus
mutation; no PR merge without review.
