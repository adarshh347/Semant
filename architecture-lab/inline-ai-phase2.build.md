# Inline AI Phase 2 — context-aware slash + replace Compose with Sutradhar (#15)

**To:** Claude Code. **Mode:** build. Reuse existing endpoints (non-streaming). Verify by **screenshot**. Commit per `workflow-protocol.md` (#15). Preserve every capability.

Two things, done strictly:

## 1. The slash menu must be CONTEXT-AWARE (core fix)
Right now `/` always shows the block-type trio, even mid-sentence. That's wrong. The trigger can stay (start of block or after whitespace), but the **items depend on where the caret is**:

- **Block is empty / caret at block start (no real text yet)** → **structure/creator set:** `Paragraph`, `Heading`, `Quote`, and `Version` (generate a starting draft from the image). This is the only place the trio appears.
- **Caret is mid-text (block already has content)** → **AI-verb set:** `Draft from image`, `Write…`, `Continue`, `Rewrite`, `Expand`, `Shorten`. **Never show the trio here.**

Implementation hint: in the Suggestion `items({ query, editor })`, inspect the current textblock — if it has no non-whitespace text besides the `/query`, use the structure set; otherwise the AI set. Then filter by query. (You already anchor context via `editor.view.dom`.)

## 2. Replace "Compose with Sutradhar" entirely with slash
The compose button + popover (Draft-from-image / Write) must be **removed** — its two functions become slash commands, so no capability is lost:
- `/draft` → `epicService.autoRecommendText(post.photo_url, existingTextForAI())`; insert a new block **after** the current one, `origin: 'sutradhar'` (via `insertBlock`/`makeBlock`).
- `/write` → needs a short instruction. Trigger the existing prompt flow (`promptEnhancedText`) from a **minimal inline prompt at the caret** (not the old card); on submit, insert a `sutradhar` block. Keep it compact.
- `/continue`, `/rewrite`, `/expand`, `/shorten` → `promptEnhancedText` with the appropriate instruction over the current block's text (`existingTextForAI()` / current node text). All non-streaming, land as one insert/replace with `origin: 'sutradhar'`.
- Show the existing `aiBusy` state while a command runs.

Once `/draft` and `/write` work in slash, **delete the Compose button + popover**. Keep the recognisable **"+ Add block"** button (discoverable entry that inserts an empty paragraph → then type `/`).

## Notes
- `Version` at the empty-block context = "generate an alternate starting draft from the image." If Adarsh meant an alternate of *existing* text, that's a mid-text transform — flag it, don't guess into a different behaviour.
- This is non-streaming (Phase 2). Streaming + ghost-text + range-origin stay Phase 3.

## Verify on screen
- Mid-text `/` shows AI verbs, NOT the trio. Empty-block `/` shows trio + Version.
- Compose button/popover gone; `/draft` and `/write` reachable and working.
- `origin: 'sutradhar'` on AI blocks intact. Commit each as `feat(drishya): … (#15)`, update #15, push PR, one-paragraph handoff.
