# Frontend beyond visuals — the orchestrator's lens

The realization: **quality is downstream of architecture.** A site feels smooth/premium because of the layers *beneath* the pixels. As an orchestrator you don't need to code these, but you must be able to SEE them, name them, and direct them in the right order. Related: [[Purpose Structure Surface]], [[Constraints we must not break]].

## The four layers (direct them in this order)
Polish applied before the layer below it is right = lipstick. This is why "make it premium" fails until the foundation exists.

### Layer 1 — Foundation (the constraint system everything rests on)
- **Design tokens** — one source of truth for spacing, type scale, colour, radius, shadow, motion. *Look for:* is spacing on a consistent scale? Do all values come from tokens? *(Our `--space-5` bug — an undefined token — is exactly a foundation failure.)* Orchestrator question: **"What is our token system, and does every value come from it?"**
- **Component primitives** — buttons, inputs, menus, dialogs, toasts built ONCE and reused. *Look for:* the same control looking/behaving identically everywhere. Q: **"Is this a reusable primitive or a one-off?"**
- **State ownership & data flow** — where state lives, client vs server state, derived state, what re-renders. *Look for:* features that interrelate without breaking; no "god component." Q: **"Who owns this state, and what changes when it changes?"**
- **Frontend↔backend contract** — the API/data shape decides what UI is even possible. *Look for:* how the data model enables or blocks the experience. Q: **"Does the data model actually support the experience we want?"** *(This is the constraint you just felt — the annotation data model bounds the annotation UX.)*

### Layer 2 — Structure (how the screen is organized)
- **Layout system & shell** — grid, panes, the app frame; responsive/adaptive; density modes. (Our border-grammar / split-pane work.)
- **Information hierarchy & progressive disclosure** — how complex tools reveal power without overwhelming (the Notion/Linear/Figma skill). Q: **"How much shows now, and what's revealed on demand?"**
- **Navigation model** — how you move and stay oriented (command palettes, breadcrumbs, tabs).

### Layer 3 — Behaviour (what makes it feel alive and smooth)
- **Interaction & feedback** — affordances, hover/focus/active states, optimistic updates, and *system status* (saving / dirty / synced). Q: **"Does the UI always tell the user what just happened and what's happening?"**
- **Motion & transitions** — purposeful, tied to state changes; never decorative. Smoothness lives here, not in static screenshots.
- **Performance & perceived speed** — code-splitting, lazy loading, list virtualization, skeletons, no layout thrash. "Feels fast" is engineered.
- **State coverage: loading / empty / error / edge** — handling all four is the maturity marker amateurs skip.

### Layer 4 — Craft (the finish, and only convincing if 1–3 are right)
- **Typography & reading rhythm**, **accessibility & semantics** (keyboard, ARIA, focus order), **pattern consistency** (a predictable language), then **surface polish** (colour, depth, spacing). This is where "beautiful" finally belongs.

## How to actually study a great site
For each exemplar, go **dimension by dimension** and ask *"what architectural choice produces this feel?"* — never just "what colour is that." Examples of the transferable lesson each teaches:
- **Linear** — speed, keyboard-first, state/sync architecture, high data density kept calm.
- **Notion** — block model, composition, progressive disclosure, one editing primitive everywhere.
- **Figma** — canvas performance, multiplayer state, precise direct-manipulation.
- **Stripe** — clarity, forms, docs, information hierarchy under heavy content.
- **Raycast / Superhuman** — command palette, keyboard, motion, "instant" feel.
- **Vercel / Arc** — motion language, novel navigation, restraint.

## The one orchestrator habit
When something looks great, resist "let's copy that look." Instead ask: *which layer is doing the work?* Usually it's tokens + state + interaction, not colour. Direct the build **foundation → structure → behaviour → craft**, and name the layer when you talk to the coding agent. See [[Editor model - Path A vs Path B]] for how a Layer-1 choice (state/editor model) gates everything above it.
