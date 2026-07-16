# How we work

Two assistants + one human:
- **Claude (desktop)** — studies, explains in plain language, writes prompts + notes, verifies shipped code.
- **Claude Code (CLI, in-repo)** — does the deep reading and the building.
- **Adarsh** — decides, and does on-screen checks until the browser extension is connected.

## Loops
- **Lanes**: research prompt → `architecture-lab/responses/*.findings.md` → decisions locked in `architecture-lab/decisions-log.md` → narrow build prompt → verify.
- **Documentation**: GitHub issues (label `architecture`) + `architecture-lab/workflow-log.md`, kept in sync. Issue format: Expected → Claude Code promised → Delivered (verified) → Gaps/new demands → Decisions.
- **Git**: Claude Code owns commits/issues/PRs (`architecture-lab/workflow-protocol.md`). Conventional commits referencing issue numbers; one open PR per phase; human doesn't manage git plumbing.

## Rules that keep us honest
- Verify UI by screenshot, not by reading code. See [[Constraints we must not break]].
- One lane / one battlefield at a time. Research can run in parallel sessions; building stays serial.
- Distil durable lessons here in the vault; keep ephemeral working files in `architecture-lab/`.







**data-contract problem**.