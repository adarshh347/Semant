# R0 — Recommendation

## Headline finding

The circulation the program cares about is **partly already built and completely unexercised**, and
everything past a single image is **absent**. Specifically:

- **Percept → Writer chip → click → recall-on-image is real code on `/posts/:postId`** — but **0
  real percept mentions exist** in the corpus. Its truth is unverified, not missing.
- **Contextual role, epistemic distance, return-with-question, Atlas, Codex, and any inquiry/history
  are genuinely absent.** These are where the program's `Embodiment` / `Passage` questions actually
  live — and none may be answered by design; only by instrumented rehearsal.

This is why **PASSAGE-CIRCULATION-001 should not be run as a straight G0–G8 build**: three of its
gates sit on unexercised machinery and two on absence. Establish the research loop first.

## Smallest safe R1

**R1 = the research substrate only, in imaginative/instrumented mode, writing nothing to production.**

Build exactly:
1. `architecture-lab/rehearsals/` skeleton (README + the eight sub-folders).
2. Two **research** JSON schemas under `schemas/`: `rehearsal-trace.schema.json` (the event grammar)
   and `candidate-card.schema.json` (the CEC yaml shape from `02-…`). These are *research artifacts*,
   not Pydantic/Mongo models.
3. A **deterministic runner** (`scripts/rehearsal_run.py`) that: loads a fixture packet, replays an
   event grammar, calls **existing read-only adapters** (`R0-existing-adapters.md`), and writes a
   frozen `trace.json` + `score.md` to `runs/<id>/`. No route, no collection, no product entity.
4. **Import Passage 001 as run #0** per `R0-passage-001-import-plan.md`, with `missing-telemetry.md`.
5. One **rendered-verification probe** (not a rehearsal): drive the *existing* percept→chip→recall
   loop once, live, on `/posts/:postId` with a real `pctx_` percept, and capture a screenshot — to
   convert "capability exists" into "capability verified" or "capability broken." (Uses B1's
   programmatic server launcher.) This is the one place R1 touches the running app, read-only.

Then **stop and run the six-rehearsal breadth batch (R2)** before any entity or UX is designed.

## What R1 must NOT build

- **No** `Passage`, `Inquiry`, `Discovery`, `Embodiment`, `Candidate`, `Field`, role, or
  context-memory **production entity** — not in Mongo, not on `Post`, not as a React route.
- **No** user-facing "Rehearsal" product surface; no Differential/Writer redesign.
- **No** Atlas, Codex, or cross-image structure.
- **No** agent-skill persistence (skills come only after multi-run support, R6).
- **No** new ML model, no provider repoint, **no 118-post expansion**, no corpus mutation.
- **No** write to `posts`/`region_embeddings`/any production collection — research writes only to
  `runs/` on disk.
- **No** promotion of any Passage-001 construct beyond SPARK; nothing graduates in R1.

## Sequence from here (informational, each gated)

`R1 substrate + Passage-001 import + one rendered probe` → **stop** → `R2 six-rehearsal breadth` →
`R3 transfer/negative/sequence/counter-reading trials` → `R4 ≤2 reversible prototypes` → `R5 one
evidence-backed circulation slice (adapt the strongest of PASSAGE-CIRCULATION here)` → `R6 skills` →
`R7 expansion decision`. A contradiction at any gate is a result, not a failure to smooth over.

## One-line recommendation

Approve **R1 = research substrate + Passage-001 import + a single live rendered probe of the existing
percept→text→recall loop**, building **no production entity and no new surface**, then pause for the
breadth batch — so the rehearsals can genuinely surprise the architecture instead of confirming a
design already chosen.
