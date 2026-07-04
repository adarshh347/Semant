# AGENTS.md — Frontend house rules (Semant / Drishtikone)

You are doing **frontend/UI** work on a React 19 + Vite app. Read this before editing.
Full reasoning lives in `../FRONTEND_PLAYBOOK.md`. This file is the enforceable contract.

## Design system — the single source of truth
- Tokens: `src/index.css` and `design-system/tokens.css`.
- Aesthetic: editorial — Fraunces (`--font-display`) for headings, Inter (`--font-sans`)
  for UI, warm paper/ink neutrals, terracotta accent, calm and spacious.
- Dark mode is driven by `[data-theme='dark']`. Everything must work in both themes.

## Hard rules (do not violate)
1. **No raw values. Use tokens.** Never hardcode hex colors, and never invent spacing.
   Colors → `--ink`, `--ink-muted`, `--surface`, `--surface-2`, `--line`, `--accent`,
   `--accent-soft`, etc. Spacing → the 4px scale `--space-1..24`. Radius → `--radius-*`.
   Type → `--fs-*`. Shadow → `--shadow-*`. Motion easing → `--ease`.
2. **No inline `style={{...}}` for styling.** Write a scoped CSS class in the matching
   `.css` file. Inline styles are only acceptable for truly dynamic values (e.g. a
   computed transform/position). `StoryFlow.jsx` is the anti-pattern — do not copy it.
3. **Every data view needs an empty state.** If data can be missing, render an
   intentional empty state: icon + serif title + one guiding line + a clear next action.
   Never render nothing (that reads as a bug). See `.story-empty` for the pattern.
4. **Every interactive element needs states:** default, `:hover`, `:focus-visible`,
   `:active`, and `:disabled`. Reuse existing button language (pill shape, accent
   primary, subtle `translateY(-1px)` hover lift).
5. **Reuse before creating.** Search for an existing class/component before adding one.
   Match existing patterns (`.btn`, `.chip`, `.composer-btn`, `.panel-tab`).
6. **Consistency > cleverness.** Same job → same pattern across the app.

## Review your own work against this lens (score 1–5, fix the lows)
Layout & spacing rhythm · visual hierarchy · color/surface/elevation ·
interaction & affordance · usability & ergonomics · motion · consistency.

## Workflow
- **Small, focused diffs.** One section/problem per change. Explain what and why.
- **Do not touch** `backend/`, `chrome-extension/`, or API/service logic. UI only.
- **Verify before finishing:** run `npx vite build` from `frontend/` — it must pass.
- Check both light and dark mode, and both empty and populated states.
- When unsure about intent, state your assumption in the diff rather than guessing silently.
