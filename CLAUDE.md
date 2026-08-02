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

Do NOT recreate `architecture-lab/`.

## The vault is NOT versioned — do not commit it
`vault/` is gitignored. It lives on disk and in the author's own backups; this repo is public and
the vault is not for it. So:

- **Author docs in the vault exactly as above** — that has not changed. They simply do not get
  committed, and there is no `docs(vault): …` commit any more.
- **Never `git add -f vault/…`**, and never move a vault doc into the repo to "save" it.
- A change that needs to be *shared* — a contract, a schema, a fixture the tests read — does not
  belong in the vault in the first place. Put it in the repo proper and reference it from the vault.

Anything the test suite reads must live in the repo. That is why the Rehearsal Research Program's
schemas, sandboxes, fixtures and run records sit at **`research/rehearsals/`** (`REHEARSALS_ROOT` in
`scripts/rehearsal_run.py`) rather than inside the vault.

History note: the vault was untracked on 2026-08-02 going forward only. Commits made before that
still contain it — nothing was rewritten.
