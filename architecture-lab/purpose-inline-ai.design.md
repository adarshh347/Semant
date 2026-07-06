# Purpose sub-lane — "AI as part of the pen" (inline generation + slash commands)

**To:** Claude Code. **Mode:** RESEARCH + design proposal first (no big build yet). Write findings to `responses/purpose-inline-ai.findings.md`. A build prompt follows once Adarsh approves the plan.

## The principle (locked)
AI generation must feel like an **extension of writing**, not a separate chatbot you visit. The wall between "I write" and "I ask AI to write" should dissolve. Two mechanisms, locked as the direction:

1. **Inline generation** — AI text streams into the **same block the caret is in**, then the writer keeps typing over it. No side panel for quick generation.
2. **Slash commands** — typing `/` in an empty block (or at the caret) opens a small command menu; commands are verbs inside writing. **This is the primary surface — develop it deeply.**

The existing `origin: 'human' | 'sutradhar'` field is what keeps "who wrote what" traceable even as the wall comes down.

## What this replaces
- The insert menu's "Compose with Sutradhar" (input + Write) — folds into `/` commands.
- "Draft from image" — becomes `/draft`.
- The deep AI **sidebar stays** only for genuine back-and-forth conversation, not quick generation.

## Research questions (answer in findings, with file/version evidence)
1. **TipTap feasibility.** What is the installed TipTap version? Is `@tiptap/suggestion` (or the Mention/slash pattern) available, and does the per-block editor model (Path A: one editor per `RichTextBlock`) support a `/` suggestion menu anchored to the caret? If per-block editors make a global slash menu awkward, say so — this may be the first strong reason to move toward Path B (single-document editor). Give a clear recommendation.
2. **Streaming.** Does the backend (`epicService.autoRecommendText` / `promptEnhancedText`, and the `/posts/brainstorm` route) support token streaming, or only whole-response? Inline generation feels best when it streams. Report what exists and what a streaming path would need (backend + frontend).
3. **Origin marking at sub-block level.** If AI text streams into a block the human also edited, `origin` on the whole block is too coarse. Investigate a TipTap **mark** (like bold) that tags a *range* of text as `sutradhar`, so a block can hold mixed authorship the reader can still trace. Is this feasible with StarterKit + a custom mark? Recommend block-level vs range-level origin.
4. **Empty-block affordance.** Design the empty-block placeholder ("Write, or press / for Sutradhar…") and how `/` triggers the menu without fighting normal typing.

## Command set to design (starter — propose the final list)
Group into **block-type** commands (local, instant) and **AI** commands (call Sutradhar):
- Block-type: `/paragraph`, `/heading`, `/quote` (replaces the manual insert buttons).
- AI, image-aware: `/draft` (draft a passage from the image), `/describe`.
- AI, text-aware: `/continue` (keep writing from here), `/expand`, `/shorten`, `/rewrite` (tone or clarity).
- Deep: `/ask` (hands off to the sidebar for real conversation).
Propose which are v1 vs later, and the exact insertion behaviour of each (into current block? new block after? replace selection?).

## New ideas to explore (go further if you see more)
- **Ghost text / inline suggestion**: AI proposes a continuation as faint text; Tab accepts, Esc dismisses (Copilot-style) — no menu at all for `/continue`.
- **Selection actions**: select existing text → the bubble toolbar gains an AI verb (rewrite/shorten) so AI also acts on what's already written, not just empty blocks.
- **A quiet "Sutradhar is writing…" state** in the block itself, not a spinner in a panel.
- **Undo semantics**: an AI generation should be a single undo step, and its `origin` marking should survive undo/redo.

## Output contract → `responses/purpose-inline-ai.findings.md`
- **Feasibility verdict** — TipTap version, slash support, per-block vs single-document recommendation (Path A vs Path B), streaming status, origin-marking approach. With evidence.
- **Interaction spec** — empty-block placeholder, `/` menu behaviour, per-command insertion behaviour, streaming + busy state, accept/dismiss for ghost text.
- **Final command set** — v1 vs later.
- **Build plan** — phased: (1) `/` menu for block types (no AI), (2) AI commands non-streaming, (3) streaming + range-level origin + ghost text. So we can ship the shell before the hard parts.
- **Questions for Adarsh.**

## Constraints
- Research + plan only in this round; do not rip out the current composer yet.
- Keep every existing generation capability working until its `/` replacement is built.
