# Semant — working conventions

## The vault has three working spaces
Everything lives in the Obsidian vault, grouped by *how you work with it*:

- **`vault/Writing/`** — theoretical & personal prose (stories, motives, the orchestrator's writing, rehearsals, history).
- **`vault/Concepts/`** — conceptual discussion of Semant (percepts/atlas/codex ideas, lexicon, design language, positioning, architecture theory).
- **`vault/Build/`** — the dense Claude-Code-oriented docs (the Architecture Lab, execution prompts, workflow, engineering rehearsals).

## Docs live in the vault (architecture-lab is retired)
`architecture-lab/` has moved into **`vault/Build/Architecture Lab/`**. Author ALL planning docs there, by kind:

- Findings / research / analysis  → `vault/Build/Architecture Lab/Findings/`
- Build specs / execution prompts  → `vault/Build/Architecture Lab/Build specs/`
- Decisions / workflow / protocol  → `vault/Build/Architecture Lab/Decisions/`
- Vision pipeline / agent reports   → `vault/Build/Architecture Lab/Vision pipeline/`
- Loose plans                       → `vault/Build/Architecture Lab/Plans/`
- Conceptual / design / theory      → `vault/Concepts/` (design language → `vault/Concepts/Frontend Analysis/`)
- Personal / narrative writing      → `vault/Writing/`

Do NOT recreate `architecture-lab/`. Commit docs as `docs(vault): …`.
