# Frontend mastery — deep-research prompt chain (for a dedicated session)

Goal: turn Adarsh into a sharper **orchestrator** of frontend work by studying what makes established products feel smooth/premium *beneath the visuals*, and distilling it into a rubric + playbook + vocabulary he can use to direct Claude Code.

Read first: `vault/Frontend Analysis/Frontend beyond visuals - the orchestrator's lens.md` (the four-layer lens). Web search + web fetch are allowed and expected. **Research + synthesis only — no app code.** Run the steps in order; each writes its own file under `architecture-lab/responses/frontend-research/`. Commit findings as `docs(...)`.

---

## Step 1 — Build the evaluation rubric
Using the four-layer lens (Foundation → Structure → Behaviour → Craft), expand it into a concrete **scoring rubric**: for each dimension, list 3–5 observable signals a non-expert can actually spot, and the "orchestrator question" to ask. Add anything the lens misses.
→ write `responses/frontend-research/01-rubric.md`.

## Step 2 — Exemplar teardowns
Pick 5 exemplars across different problem-shapes: **Linear, Notion, Figma, Stripe, and Raycast (or Superhuman)**. For EACH, research its public engineering/design writing (blogs, talks, docs) plus direct observation, and write a teardown organized by the rubric's four layers. For every "it feels great" observation, name the **architectural choice that produces it** (token system, state model, data contract, motion, virtualization, etc.) — not the surface look. Note what's transferable to a content+canvas creative tool like Drishya.
→ write `responses/frontend-research/02-exemplars.md`.

## Step 3 — Principles & anti-patterns
Distil across the teardowns into: (a) 10–15 **transferable principles** (each: the principle, why it works, the architectural enabler), and (b) a list of **anti-patterns** that make apps feel amateur/messy (god components, styling-before-tokens, missing empty/error states, layout thrash, inconsistent primitives, etc.).
→ write `responses/frontend-research/03-principles.md`.

## Step 4 — Map to Semant/Drishya
Read the real stack (`frontend/package.json`, `frontend/src/` structure, `index.css` tokens, `PostDetailPage.jsx` as the flagship). Assess Drishya against the rubric honestly (where it's strong/weak per layer), then produce a **prioritised adoption plan**: which principles to adopt, in what order (foundation first), given the current constraints and the Darshan initiative. Ground every item in a real file.
→ write `responses/frontend-research/04-semant-map.md`.

## Step 5 — The orchestrator's toolkit (the payoff)
Produce three compact, reusable artifacts for Adarsh:
1. **Evaluation checklist** — a one-page list he can run against any UI (his or a competitor's) to judge it beyond looks.
2. **Direct-the-build playbook** — the order of operations for any new feature (foundation → structure → behaviour → craft), with the decision each step forces.
3. **Vocabulary** — 20–30 precise terms (design token, primitive, derived state, optimistic update, progressive disclosure, virtualization, layout thrash, focus trap, skeleton, …) each with a one-line plain-language meaning, so he can name the layer when directing the coding agent.
→ write `responses/frontend-research/05-toolkit.md`, and copy the durable parts into the vault (`Frontend Analysis/`).

---

## Rules
- Research + synthesis only; no app-code edits.
- Prefer primary sources (the companies' own engineering/design writing) over listicles.
- Every "feels good" claim must name its architectural cause.
- Keep the orchestrator (a non-coder director) as the audience throughout — plain language, actionable.
