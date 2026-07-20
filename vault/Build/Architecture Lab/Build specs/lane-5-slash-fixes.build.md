# Lane 5 — slash menu fixes + retire the Add-block card (#15)

**To:** Claude Code. **Mode:** build. Verify by **screenshot**. Commit per `workflow-protocol.md` (#15). Preserve AI capability (don't delete generation).

Phase 1 slash works, but on-screen verification found issues.

## 1. Slash menu detaches on scroll (positioning bug)
In `slashCommand.jsx`, the floating menu uses the default **absolute** strategy (`el.style.position = 'absolute'`, `computePosition(... )`). The caret lives inside the **inner** scroll container (`.content-area`), so on scroll the block moves but the menu stays put / lands far from the caret (see screenshot).
**Fix:** use floating-ui **fixed** strategy — `el.style.position = 'fixed'` and `computePosition(virtual, el, { strategy: 'fixed', placement: 'bottom-start', middleware: [offset(6), flip({padding:8}), shift({padding:8})] })`. `autoUpdate` already tracks ancestor scroll; confirm the menu now stays pinned to the caret while scrolling. Screenshot proof.

## 2. Retire the big Add-block card; keep a recognisable trigger
Slash now covers block types, so the big expandable insert card is redundant.
- **Remove** the card's block-type section (Paragraph / Heading / Quote) — `/` replaces it.
- **Do NOT delete AI capability.** The "Compose with Sutradhar" (Draft from image / Write) is slated to become slash commands in Phase 2 (`/draft`, `/write`, `/rewrite` — see `slash-command-taxonomy` / vault). Until Phase 2 lands, keep AI compose reachable but **compact** (a small labelled affordance), not a big card.
- **The "+ Add block" trigger stays but must be RECOGNISABLE.** It was flattened to near-white/invisible. Give it a visible resting style (border + label + icon) so it reads as a button. Clicking it inserts a new empty paragraph (where the user can then type `/`).

## 3. Result to verify on screen
- Slash menu stays glued to the caret through scroll.
- No big insert card; a clean, visible "+ Add block" button; AI compose still reachable (compact) pending Phase 2.
- Then: this closes Phase 1 (#15). Phase 2 (AI slash commands) is the next inline-AI task.

## Order
0. Any queued git first (protocol). 1 → 2 → 3. Commit each as `fix(drishya): … (#15)` / `refactor(drishya): retire add-block card (#15)`. Update #15, push PR, one-paragraph handoff.
