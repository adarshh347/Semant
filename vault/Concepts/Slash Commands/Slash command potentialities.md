# Slash command potentialities

`/` is the primary creation surface in [[Drishya and Semant]]. The mental model: **slash creates at the caret; the bubble toolbar transforms a selection.** Everything AI does should feel like an extension of writing, not a chatbot.

## Command families
- **Structure** (instant, no AI) — `/paragraph` `/heading` `/quote`. *(shipped, Phase 1)*
- **Generation** (AI writes new text at caret; marks `origin: sutradhar`)
  - `/draft` — draft a passage from the image
  - `/write <prompt>` — write from a short instruction
  - `/continue` — continue from what's written
  - `/describe` — plainer visual description
- **Transformation** (act on current/selected text; prefer bubble-toolbar too)
  - `/rewrite` (tone/clarity) · `/expand` · `/shorten`
  - `/version` — offer an *alternate*, non-destructive version to compare/swap (a "candidates" idea; pairs with ghost-text)
- **Reference inserts** (later, creative — wires Visual↔Content complementarity, Lane 2)
  - `/part` — insert a reference to an annotated image region (`bounding_box_tags`)
  - `/lens` — insert an Aletheia reading/lens
- **Meta** — `/ask` — hand off to the deep AI sidebar for real conversation.

## Phasing
1. Structure (done). 2. Generation + transforms, non-streaming (reuse endpoints). 3. Streaming + range-level origin marking + ghost-text continuations (Tab to accept) + selection→AI verbs in the bubble toolbar.

## Durable ideas to revisit
- **Ghost text**: faint AI continuation, Tab accepts, Esc dismisses.
- **Versions**: keep multiple AI candidates per block, cycle and pick — non-destructive.
- **Trace view**: since every block/range carries `origin`, a future reader mode could show who wrote what.
- **Region-aware writing**: `/part` and `/lens` let the story literally cite the image — the deepest expression of Drishya's purpose.

Constraints that bound all of this: [[Constraints we must not break]], [[Editor model - Path A vs Path B]].
