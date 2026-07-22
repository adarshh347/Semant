# Purpose — inline AI & slash commands (research first)

Relates to #13. Labels: architecture, drishya, enhancement
Full spec: `architecture-lab/purpose-inline-ai.design.md`
Output: `architecture-lab/responses/purpose-inline-ai.findings.md`

## Principle (locked)
AI generation is an extension of writing, not a chatbot. Two mechanisms:
1. **Inline generation** — streams into the block the caret is in.
2. **Slash commands** (`/`) — the primary surface; develop deeply.
The `origin` field keeps "who wrote what" traceable. The deep AI sidebar stays for real conversation only.

## Research to settle (this round is research + plan, no rip-out)
- [ ] TipTap version + whether a `/` suggestion menu works under per-block editors (Path A) — or if this forces Path B (single-document editor). **Clear verdict required.**
- [ ] Backend streaming: does `epicService` / `/posts/brainstorm` stream tokens, or whole-response only? What would streaming need?
- [ ] Range-level `origin` (a TipTap mark) so a block can hold mixed human/AI authorship.
- [ ] Empty-block placeholder + `/` trigger design.

## Command set to design (v1 vs later)
Block-type: `/paragraph` `/heading` `/quote`. AI: `/draft` `/continue` `/expand` `/shorten` `/rewrite`. Deep: `/ask` (→ sidebar). Specify each command's insertion behaviour.

## Explore further
Ghost-text continuation (Tab to accept) · selection→AI verbs in the bubble toolbar · in-block "Sutradhar is writing…" state · AI generation as one undo step.

## Output contract
Feasibility verdict (Path A vs B, streaming, origin marking) · interaction spec · final command set · phased build plan (menu → non-streaming AI → streaming + range origin + ghost text) · questions for Adarsh.
