# Constraints we must not break

Hard-won rules. Violating these is how the UI regressed before.

- **Only three things earn a visible border:** the two major panes (Visual, Content), the panel-header hairline, and the one focused editing surface. Everything else is spacing, not boxes. See [[Border grammar levels]].
- **A child may not repeat its parent's boundary type.** A Level-5 chip must not look like a Level-2 pane.
- **Order is Purpose → Structure → Surface.** Never pick colour before the component; never pick the component before the job. See [[Purpose Structure Surface]].
- **The navbar and the page are siblings** in `App.jsx`, so page-level editing state cannot restyle the global navbar via CSS — it needs a route-aware change.
- **Keep capability until its replacement is proven.** Don't delete an AI path / control before the new one works.
- **Verify UI by screenshot, not by reading CSS.** An undefined token or stale cascade can be "correct in source, wrong on screen" (this bit us: `--space-5` was undefined; the 80px block height "looked fixed" in code but not on screen).
- **`origin` on every block** (`human | sutradhar`) is the trace of who wrote what — never drop it. See [[Slash command potentialities]].
- **Spacing tokens are a fixed scale** (`--space-1..4,6,8,12,16,24`). There is no `--space-5`/`-7`/`-14` unless explicitly defined. Use defined tokens.
