# Editor model - Path A vs Path B

The Content editor (edit mode) uses TipTap. Two possible models:

**Path A (current, LOCKED first):** one TipTap editor *per block* (`RichTextBlock`). A shared bubble toolbar + slash menu target the focused block via `activeBlockId`. Cheap, already shipped. Reorder is custom drag; origin is block-level.

**Path B (later, bigger):** *one* TipTap editor for the whole document, each block a node inside it. Unlocks cross-block text selection, one unified undo stack, and native drag. It is a real rewrite.

**Verdict (from the slash research):** the `/` menu does NOT require Path B — `@tiptap/suggestion` attaches per block just fine. So build slash + AI on Path A. Path B stays a separate, later pass justified only by cross-block selection + unified undo — not by slash.

Key facts: TipTap 3.7.x, React 19. Added deps: `@tiptap/suggestion`, `@tiptap/extension-placeholder`, `@floating-ui/dom`. No token streaming exists yet (Groq `stream=False`); streaming is Phase 3. See [[Slash command potentialities]].
