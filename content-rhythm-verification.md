# Content Rhythm Refinement — Verification

Pass: Content rhythm refinement (spacing / alignment / vertical rhythm) on the
Post Detail edit mode. Source of truth: `border-layout-plan.md`.
Constraint honored: **no card containers reintroduced** — grouping is done with
whitespace, alignment, and single-edge hairline separators only.

Verification method: code-level against the final `PostDetailPage.css` (the
browser extension was not connected, so a live screenshot could not be taken).
`npx vite build` passes.

## Checklist

- [x] **Main writing column feels intentional, not raw.**
  - `.edit-shell-intro` (Writing-studio kicker + heading + meta pills) sits above
    the grid with a bottom hairline; `.edit-section-head` ("Story blocks") keeps
    its underline in the main column, so the column reads as labeled sections,
    not loose text.
  - `.edit-layout` is `align-items: start` and the rail's `padding-top: 0` makes
    "Story blocks" and the Compose label share the same top line.

- [x] **Add Block toolbar feels designed, not just unboxed.**
  - `.add-block-menu` wrapper stays box-less (`padding:0; background:transparent;
    border:none; border-radius:0`).
  - `.add-block-btn` now carries a **persistent** subtle border
    (`1px color-mix(--line 60%)`) instead of `1px solid transparent`, so the
    three controls read as a deliberate segmented toolbar rather than
    invisible-until-hover buttons. Hover/focus-visible states retained.

- [x] **Compose and Tags feel like one quiet support rail.**
  - Both live in `.edit-side-column` with a single `gap: var(--space-6)` rhythm.
  - `.sutradhar-composer` no longer carries a stray top hairline (it is the rail's
    first item); the **one** separator is `.tags-edit-section`'s `border-top`
    hairline with balanced `padding-top: var(--space-6)` — one clean divider
    between the two support sections.
  - `.edit-side-column .edit-section-head` drops its underline so the "Tags"
    label matches the Compose label style → consistent rail rhythm.

- [x] **Right rail does not feel cramped.**
  - Rail sections spaced at `--space-6`; internal groups at `--space-3`.
  - Rail column widened away from the divider via `padding-left: var(--space-5)`;
    grid gutter `--space-5`.

- [x] **Save footer does not collide with rail content.**
  - Structural fact: `.edit-actions` is a **sibling** of `.content-area` inside
    `.post-detail-right` (JSX: content-area closes L950, edit-actions L966), so
    the footer is a pane-level bottom row. The rail (Compose/Tags) lives inside
    the independently-scrolling `.content-area` above it — no overlap possible.
  - Footer is non-sticky, solid `--surface-primary`, `flex-shrink:0`.

- [x] **No card boxes came back.**
  - Verified each wrapper: `.sutradhar-composer`, `.tags-card`, `.add-block-menu`
    → all `background:transparent; border:none; border-radius:0`.
  - `.source-account-section` and `.tags-edit-section` carry only a **single-edge
    hairline separator** (border-bottom / border-top), not a four-sided box, no
    fill, no radius.
  - `.rich-text-block` is box-less (transparent, no border, `border-radius:0`);
    only a left rule on `:focus-within`.
  - No new `border-radius` on any wrapper; the only rounded things are individual
    L5 controls (buttons, chips, inputs), which are allowed.

- [x] **Content panel feels more like an editorial workspace.**
  - Rhythm hierarchy: intro (hairline) → main column labeled sections → rail with
    one consistent gap and one divider → pane footer aligned to the pane edge
    (`--space-4`, matching the panel header inset).
  - Only the active editor surface shows a creation boundary (accent left rule +
    faint inset); everything else is whitespace-grouped.

## Alignment / rhythm summary

**Writing column:** columns top-align (`align-items:start` + rail `padding-top:0`);
main column keeps underlined section heads; Add Block became a designed inline
toolbar via persistent button borders on a box-less wrapper. Writing area given
more weight (`1.7fr` vs `0.8fr`).

**Support rail:** one `--space-6` rhythm; the stray top hairline on Compose was
removed and replaced with a single balanced divider between Compose and Tags;
rail labels unified (no underline); rail sits `--space-5` off the vertical
divider.

**Footer:** horizontal padding aligned to the panel-header edge (`--space-4`);
remains a solid, non-floating pane footer; Save primary, Cancel quiet.

## Changed files
- `frontend/src/components/PostDetailPage.css` (only file; CSS-only — no JSX,
  no handlers, no state, no data flow changed).

## Build
- `npx vite build` → success (pre-existing chunk-size warning only).
