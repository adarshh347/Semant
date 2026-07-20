# Lane 4 — Content view build (one framed story column)

**To:** Claude Code. **Mode:** build, structure only (no colour/surface polish). Preserve every capability. Verify by **screenshot**. Commit per `workflow-protocol.md`. Source of truth: `responses/lane-4-content-view.findings.md` + the 5 locked answers in `decisions-log.md`.

**Run AFTER the Phase 2 slash work is committed** — both touch `PostDetailPage.jsx/.css`; do not parallelize.

## The shape we're building
One `.story-column` inside `.content-area`, framed identically in every state:
**meta-head** (identity) → **story** (empty / editing / reading) → **meta-foot** (TagStrip). No layout jump between states.

## 1. Meta-head — gate identity, demote epic
- Move `.source-account-section` and `.epic-badge-section` **inside** the `tab === 'content'` gate so they stop rendering on the Highlights/Unconceal tabs and in a way that bleeds across modes (currently above the gate → 3 redundant render sites).
- Keep the source/@handle as the provenance line (meta-head). **Persona identity lives here only** — Lane 1 must NOT also render it in the topbar (locked answer 1).
- **Demote Epic** to a small chip on the same meta-head row (`From @handle · Epic: Title`), not its own `<h5>` band (locked answer 2).

## 2. Meta-foot — one TagStrip, both modes
- Introduce a single `<TagStrip mode={isEditing ? 'edit' : 'view'} …>` as the **last child of the story column, inside `.content-area`**.
  - `view` → read-only chips (today's `.tags-section` markup minus the standalone `<h4>` band).
  - `edit` → chips-with-remove + popular row + add input (today's `.tags-edit-section` internals).
- **Delete** both old homes: the sibling `.tags-section` (outside `.content-area`) and `.tags-edit-section` (inside `.edit-layout`).
- **Edit mode: make the strip sticky/collapsible** so tags stay reachable while writing a long column (locked answer 4) — don't bury them at the bottom.
- Preserve: tag display, add, remove, popular tags.

## 3. One story column — three states, shared frame
- Wrap the edit-shell / story-empty / reading branches in a single `.story-column` framed by meta-head + meta-foot, so switching state doesn't reflow the frame.
- Treat **empty as the zero-block case of reading** (not a separate hero): left-aligned, its primary "Write the story" flips `isEditing` in place. `startEditing` already seeds a focused empty block (locked), so the transition is already behaviourally seamless — this makes it seamless in layout too.
- "Draft from image" on the empty state stays for now; it folds into `/draft` when Phase 2 slash lands.

## 4. Highlights in context — jump to source
- Make each `.highlight-card` a **jump-to-source** control: add `jumpToBlock(blockId)` = set `activeRightTab='content'`, then `document.querySelector('[data-block-id="…"]').scrollIntoView({behavior:'smooth', block:'center'})` + a brief flash on the target.
- Uses the existing link (`highlight.block_id` ↔ reading `data-block-id`) — no backend/data change.
- **Graceful degradation:** when `block_id` is null or the block no longer exists, render the quote with NO jump affordance — never a dead link. (Locked answer 3: cross-tab jump now; inline margin rail is a later enhancement.)

## 5. Remove the underline hint strip
- Delete the persistent `.underline-hint` band; rely on the existing selection tooltip (`showUnderlineTooltip` / `handleTextSelection`) which already teaches the gesture (locked answer 5).

## Verify on screen
- Source/epic no longer appear on Highlights/Unconceal tabs; epic is a chip; handle not duplicated in topbar.
- Tags render in ONE place (meta-foot) in both modes; reachable while editing; add/remove/popular all work.
- Empty→edit→read keep the same frame (no jump).
- A highlight card jumps to its block and flashes; a highlight with no/invalid block_id shows no jump and doesn't error.
- No permanent underline strip; selection tooltip still works.
Commit each as `feat(drishya)/refactor(drishya): … (#NN)`, update the Lane 4 issue, push the PR, one-paragraph handoff.
