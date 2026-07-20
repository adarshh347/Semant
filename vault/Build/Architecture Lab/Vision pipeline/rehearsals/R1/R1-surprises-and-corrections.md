# R1 — Surprises and corrections

A contradiction is a result. These are recorded, not smoothed.

## S1 — `.gitignore` silently swallows research memory (corrected)

`.gitignore:15` is a bare `runs/` under the *Ultralytics artifacts* section — it matches the
rehearsals `runs/` tree too, so `runs/000-passage-001/` was invisible to git (`check-ignore`
confirmed). R0's research-layout assumed `runs/` would be committed memory; this global pattern broke
that. **Correction:** Fable (orchestrator) added a scoped negation
(`!architecture-lab/rehearsals/runs/` + `/**`); run #0 is now trackable. Opus correctly did **not**
touch `.gitignore` (outside its packet). Lesson for R2: the runner should warn if its output path is
git-ignored.

## S2 — Rendered probe blocked by a *worsening* infrastructure state (reported, not fixed)

At R0, the programmatic `uvicorn.run` launcher (`scripts/_run_backend.py`) **worked** and served
`:8000`. At R1, **every** long-lived server — that same launcher included, and even the process that
had been serving — is killed with **exit 144**. Short-lived processes (pytest, vitest, scripts) are
unaffected. This is an environment change this session, not an app regression (startup is clean,
in-process ASGI works). Consequence: the R0 recommendation's "one live rendered probe" could not be
executed; it is honestly reported as blocked and carried into R2. **Do not** treat R0's earlier
server success as still true.

## S3 — "Percept" ambiguity is real but cleanly separable (confirmed)

R0 flagged two `Percept` objects. Confirmed at the id level: `pctx_` never matches a `pct_` prefix
test (the 4th char differs), so `classify_percept_id` is unambiguous, verified against the real
corpus id `pctx_mrpi3rjk_0`. The research schemas encode `percept_kind` so no card or trace can blur
them. This lowers the risk that a future "Embodiment" trial silently attaches to the wrong object.

## S4 — `jsonschema` absent → vendored validator (minor, corrected)

No `jsonschema` in `venv`. Rather than add a production dependency for research scaffolding, a
minimal Draft-2020-12 validator was vendored and self-tested. If R2+ needs broader schema features,
revisit (either extend the vendored validator or add `jsonschema` to a dev-only extra).

## S5 — The circulation gap is *adoption*, not (only) *construction* — reinforced

R0 corrected PASSAGE-CIRCULATION's assumption that percept→text→recall must be built; R1's unit-level
pass (56 tests) reinforces that the machinery's logic is sound. The unknown is purely **rendered
behaviour + real use** (0 mentions in the corpus). This sharpens R2's first task: verify the existing
loop renders before designing anything new — resist building an `Embodiment` to solve a problem that
may already be solved in code and merely unexercised.

## Net effect on the plan

None of these invalidates R1's deliverable (substrate is built + green). Two carry into R2 as
obligations: (a) **run the rendered probe** the moment a server can stay alive; (b) treat R0's
server-health note as stale. No construct graduated; no ontology created.
