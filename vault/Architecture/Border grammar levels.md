# Border grammar levels

Every UI element has a level; the level decides whether it may draw a border.

- **L0 page background** — no border.
- **L1 global shell / chrome** — navbar, Sutradhar strip. Thin, quiet.
- **L2 major split panes** — Visual pane, Content pane. Real structural border.
- **L3 pane headers** — CONTENT + tabs. Hairline divider only.
- **L4 active editor surface** — the focused block. Calm focus, not a glowing cage.
- **L5 inline tools / chips** — source row, add-block, tags, gutter controls. No box — whitespace.

Diagnostic sentence for the CLI: *"This is L5, why does it behave like L2?"* See [[Constraints we must not break]].
