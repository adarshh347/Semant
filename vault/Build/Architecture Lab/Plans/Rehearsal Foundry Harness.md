# Rehearsal Foundry Harness

**RESEARCH-ONLY.** This document describes tooling that authorizes no production change. It creates
no backend route, Mongo collection, product entity, or UI surface, and mutates no production data.

---

## 1. Why this exists: protocol vs harness

The rehearsal program has, until now, been carried almost entirely by **protocol** — documents
describing how a run should behave, plus a Claude Code session that had read them. That works while
the session lives. It fails in three specific ways:

1. **Session death.** A context window ends. The next session reads a subset of the docs, or reads
   them differently, and the invariants drift. HB-010 §9 records a real instance of drift in the
   opposite direction — a published constant (`~1794 tokens/image`) that was an artefact of holding
   one pair fixed, and which nothing mechanical would have caught.
2. **Parallelism.** Several sessions running different axes cannot each hold the whole protocol, and
   nothing arbitrates when two of them reach for the same file.
3. **Enforcement asymmetry.** A protocol says "do not mutate production". A harness *refuses to run*
   a manifest that names a production path. Only the second survives an eager session at 2 a.m.

A **protocol** is a document you must remember. A **harness** is code that remembers for you.

This is the harness. It deliberately implements the *smallest* mechanical part of the Foundry idea —
declaration, validation, scaffolding, freezing, replay, and stub generation — and leaves every
judgement (what the finding means, whether it is real, whether it should be built) exactly where it
belongs: with the orchestrator, in prose.

## 2. What was built, and why it extends rather than replaces

**Decision: thin wrapper, not a parallel universe.** `scripts/foundry_run.py` imports
`scripts/rehearsal_run.py` and reuses:

- its vendored minimal Draft-2020-12 validator (`jsonschema` is not installed in this venv, and the
  Foundry must not add a dependency to research tooling);
- its YAML/JSON manifest loaders;
- `rehearsal_adapters.ALLOWLIST` — the Foundry has **no separate allowlist**, so a sandbox can never
  reach a model the rehearsal substrate has not already sanctioned;
- the existing `frozen-observation` and `rehearsal-trace` schemas, so a foundry run's artifacts stay
  inspectable by R1/R2 tooling and a real R2 observation replays through the foundry path unchanged
  (there is a test for exactly that).

**One genuinely new schema was required.** The rehearsal manifest's `mode` enum is
`imaginative|instrumented|prototype|product`. A Foundry Sandbox is not a run's input packet; it is a
*standing declaration* of an axis, a budget, a stop condition and a graduation rule. It therefore
gets `foundry/schemas/foundry-sandbox.schema.json` with `mode: foundry` and `research_only: true`.

**Schema validation is necessary but not sufficient**, and the code says so. The vendored validator
subset has no `contains` keyword and cannot express cross-field rules, so `validate_sandbox()` adds
semantic guards: baseline forbidden-action superset, adapter allowlist membership, production-path
denial, and approval-gating of live calls. Both passes always run, so a caller sees every problem at
once rather than one per invocation.

## 3. How this survives Claude Code session death

The durable state is on disk, in the repository, and machine-checkable:

| what would have been in a prompt | where it now lives |
|---|---|
| "don't touch production" | `PRODUCTION_DENY_MARKERS` + `REQUIRED_FORBIDDEN` in `foundry_run.py`; a manifest naming `backend/routers` or `mongodb://` **fails validation** |
| "don't make live calls without asking" | `model_budget.approved`; `max_live_calls > 0` with `approved: false` is a validation error, and raising it is a reviewable diff |
| "only use sanctioned models" | `adapters` must be members of `rehearsal_adapters.ALLOWLIST` |
| "replay must not re-query" | `replay()` never resolves an adapter; a test booby-traps every allowlist entry and replays successfully |
| "a run may only emit sparks" | `graduation_rule.emits` is `const: "SPARK"` |
| "record what you withheld" | the generated `sparks.md` and `score.md` stubs carry a **Withheld** section; tests assert the sections exist |
| "say what should NOT be built" | `horizon-brief.md` §6 is mandatory and tested |

A future session that has read *nothing* can run `foundry_run.py validate` and be told, concretely,
what is wrong. That is the whole point.

## 4. How a future Claude session should use it

1. **Read** `foundry/README.md` and the target sandbox's manifest. Do not start from a prompt alone.
2. **Validate** the manifest. If it fails, fix the manifest — never weaken the guard.
3. **`init`** the run, **`freeze`** the seeds (use `--strict` as a pre-execution gate; a missing seed
   should stop a run that claims to study those seeds).
4. **Do the research.** This is prose work, not tooling work. Write into the generated `score.md`,
   then argue against yourself in `critique.md` before harvesting `sparks.md`.
5. **`replay`** to confirm the run reproduces from frozen artifacts.
6. **Write the brief** (`horizon-brief.md`) and `product-implications.md`. §6 of the brief — what
   should not be built yet — is not optional.
7. **Pause.** Every sandbox declares `pause_after_bounded_task: true`. Report and stop; do not chain
   into the next sandbox because momentum is pleasant.

### Parallel operation

- **One sandbox per branch or per clearly isolated run folder.** Run dirs are keyed by `sandbox_id`,
  so two sandboxes never contend for a path.
- **No product code edits from any lane** — enforced by `forbidden_actions` and by the fact that the
  harness writes only under `foundry/runs/`.
- **All outputs are Markdown/JSON.** No lane emits code.
- **All lanes pause after their bounded task**, so the orchestrator always resumes from a quiet tree.
- **Cross-sandbox synthesis happens in a Horizon Brief**, not in any single run's score.
- **Conflicts are resolved in `foundry/decisions/`** — a decision doc, never a code race. When two
  sandboxes want the same file or reach opposite conclusions, the resolution is written down and
  cited; the losing lane records why it stopped.

## 5. What this does NOT authorize

Explicitly, because the failure mode is enthusiasm rather than malice:

- **No production entity, route, Mongo collection, schema change, or UI surface** — from any number
  of sandboxes, at any strength of finding. A finding that can only be expressed by creating one is
  a finding that must wait for a build gate.
- **No live model calls.** There is no `capture` command in v1. The three shipped sandboxes are all
  committed with `max_live_calls: 0`, including the model-orchestration one that will eventually
  need calls — its budget is zero *and* blocked on a stated precondition.
- **No production DB reads**, let alone writes. Circulation is studied on frozen artifacts.
- **No corpus mutation, no id migration, no backfill, no repair.**
- **No merging or pushing.** The harness has no git path at all.
- **No graduation.** A sandbox emits SPARK. Nothing else.

## 6. How findings graduate

```text
SPARK              a sandbox names it once, with evidence and a next test
  ↓                requires: a second independent run seeing the same thing
repeated pattern   named across >= 2 runs; the repeat must state what was held constant
  ↓                requires: an enablement claim and a nearest-existing-construct answer
candidate card     the Candidate Foundry's CANDIDATE — a card, not a feature
  ↓                requires: transfer, negative case, sequence inversion, curator counter-reading
build spec         an explicit build gate decided by the orchestrator; ADR names the rejected alternatives
  ↓                requires: the smallest reversible prototype
prototype          reversible, behind a switch, usable without its theoretical essay
  ↓                requires: a circulation test — does it matter after leaving the image?
product implementation
```

**The strict rule: no single rehearsal or sandbox can create a production entity.** This is not a
guideline about tidiness; it is the remedy for the failure mode `12-failure-and-safety.md` names as
*premature ontology* — "one rehearsal creates five permanent entities."

The ladder above is a restatement of, not a replacement for, the Candidate Foundry's existing
promotion ladder (`new-planning/06-candidate-foundry.md`: SPARK → CANDIDATE → TRIAL → SUPPORTED →
PROTOTYPE → GRADUATED → RETAIN/REVISE/DEMOTE/RETIRE) and its eight required tests. Where the two
disagree, **06 wins** — it is the older contract and the one the R2 register already cites.

## 7. Files

**Code** · `scripts/foundry_run.py` (new; imports `rehearsal_run`, `rehearsal_adapters`) ·
`backend/tests/test_foundry_harness.py` (new; 65 tests).

**Vault** · `foundry/README.md` · `foundry/schemas/foundry-sandbox.schema.json` ·
`foundry/templates/{sandbox-manifest.yaml,score.md,critique.md,sparks.md,horizon-brief.md,product-implications.md}` ·
`foundry/sandboxes/{FS-001-creative-circulation,FS-002-textual-dynamism,FS-003-model-orchestration}.yaml` ·
`foundry/runs/` and `foundry/decisions/` (empty, awaiting first run) · this plan.

**Not modified:** any backend, frontend, schema, route, collection, or production data.

## 8. What is still manual

The harness scaffolds and validates; it does not think. Still entirely human/agent judgement:

- choosing which sandbox to run and when;
- the actual research — every word of `score.md`, `critique.md`, `sparks.md`;
- deciding a pattern has repeated, and that a spark has become a candidate;
- approving a live-call budget (a manifest edit, deliberately);
- writing the decision doc when two sandboxes conflict;
- all git operations.

There is also **no `capture` path**, so any sandbox needing a live reading currently has to borrow
`rehearsal_run.py`'s probe mechanism under the existing R2 approval discipline. That is the obvious
v2 extension and was left out on purpose: building a live-call path before any sandbox has earned
one would be the harness committing the exact error it exists to prevent.
