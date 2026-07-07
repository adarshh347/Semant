# Step 1 — The evaluation rubric

**Purpose.** Turn the four-layer lens into something you can *run against any UI* — yours or a competitor's — without writing code. For each dimension: **observable signals** a non-expert can actually spot on screen or with basic DevTools, and the **orchestrator question** to ask the coding agent. Scored 0–3 (0 absent · 1 partial · 2 solid · 3 exemplary).

**How to use it.** Score **bottom-up** (Foundation first). A high Craft score sitting on a low Foundation score is lipstick — flag it. The rubric's job is to tell you *which layer is doing the work* (or failing), so you direct the fix at the right layer instead of asking for "make it look nicer."

**Golden rule for the whole chain:** every "this feels great" must name the **architectural choice** behind it — a token system, a state model, a data contract, virtualization, a transition tied to state — never a colour.

---

## Layer 1 — Foundation (the constraint system)
*If this layer is weak, nothing above it can be fixed by polish. Score this hardest.*

### 1.1 Design tokens
Tokens are named design decisions stored once, so a change propagates everywhere instead of being find-and-replaced. A single source of truth for spacing, type scale, colour, radius, shadow, motion.
- **Signals:** spacing/sizes fall on a visible scale (4/8-style rhythm), not random px; the same grey/blue appears identically in many places; dark mode flips cleanly (evidence values are centralized); no "almost the same" near-duplicate values; **no undefined-token gaps** (our `--space-5` bug is the canonical failure).
- **Orchestrator Q:** *"What is our token system, and does every value come from it — or are there hardcoded one-offs?"*

### 1.2 Component primitives
Buttons, inputs, menus, dialogs, toasts built **once** and reused.
- **Signals:** the same control looks and behaves identically everywhere; one focus-ring style; consistent disabled/loading treatment across buttons; menus/dialogs share behaviour (Esc closes, outside-click closes) app-wide; you can't find two buttons that disagree.
- **Orchestrator Q:** *"Is this a reusable primitive, or a one-off we'll have to maintain in five places?"*

### 1.3 State ownership & data flow
Where state lives; client vs server state; derived vs stored; what re-renders when it changes.
- **Signals:** related features change together without breaking; no "god component" holding everything; **derived values are computed, not duplicated** (a count, not a hand-maintained number); selection/active state lives at the level that needs it, not trapped in a leaf; changing one thing doesn't visibly re-render the whole screen.
- **Orchestrator Q:** *"Who owns this state, and what exactly changes when it changes?"*

### 1.4 Frontend↔backend data contract
The data shape decides what UI is even *possible*.
- **Signals:** the experience you want maps cleanly onto the data (no heroics to render it); **one concept has one representation** (not two parallel schemas for the same thing — cf. Lane 2's `bounding_box_tags` vs `region_annotations`); ids are stable and linkable across features; the API returns what the screen needs in roughly the shape it needs.
- **Orchestrator Q:** *"Does the data model actually support the experience we want, or are we fighting it?"*

---

## Layer 2 — Structure (how the screen is organized)

### 2.1 Layout system & shell
The app frame: grid, panes, regions, density, responsive/adaptive behaviour.
- **Signals:** one consistent boundary grammar (you can predict where a divider/edge will be); regions have clear ownership; independent scroll regions with fixed chrome (headers stay put); it adapts to width without breaking; a coherent density (not some areas cramped, others airy at random).
- **Orchestrator Q:** *"What is the shell, and is every region's role and scroll behaviour deliberate?"*

### 2.2 Information hierarchy & progressive disclosure
How power is revealed without overwhelming — the Notion/Linear/Figma skill.
- **Signals:** the primary action is obvious; advanced controls appear on demand (hover, `/`, right-click, "more"), not all at once; empty screens teach the next step instead of dumping options; secondary metadata is present but de-weighted; you're never facing every control simultaneously.
- **Orchestrator Q:** *"How much shows now, and what's revealed only on demand?"*

### 2.3 Navigation model
How you move and stay oriented.
- **Signals:** you always know where you are and how to leave; consistent navigation primitives (tabs/breadcrumbs/command palette used predictably); back/exit is always reachable; deep-linkable URLs; keyboard can move between major regions.
- **Orchestrator Q:** *"How do I move through this, and do I ever get lost?"*

---

## Layer 3 — Behaviour (what makes it feel alive)
*This is where "smooth/premium" actually lives — invisible in a screenshot.*

### 3.1 Interaction & feedback (incl. system status)
Affordances; hover/focus/active; optimistic updates; and the UI telling you what's happening (saving / dirty / synced).
- **Signals:** every interactive thing has hover + **focus** + active states; actions feel instant because they're **optimistic** (UI updates first, reconciles with server, rolls back on error); there's an explicit saving/saved/dirty indicator; nothing leaves you wondering "did that work?"; destructive actions confirm.
- **Orchestrator Q:** *"Does the UI always tell the user what just happened and what's happening right now?"*

### 3.2 Motion & transitions
Purposeful motion tied to state changes — never decorative.
- **Signals:** things that appear/move **animate from where they came** (a panel slides from its edge, a menu grows from its trigger); durations are short and consistent (~150–250ms); motion explains a state change rather than ornamenting; it respects `prefers-reduced-motion`; nothing jitters or bounces without meaning.
- **Orchestrator Q:** *"Is this motion explaining a state change, or is it decoration?"*

### 3.3 Performance & perceived speed
"Feels fast" is engineered: code-splitting, lazy loading, virtualization, skeletons, no layout thrash.
- **Signals:** interactions respond immediately (the INP idea — clicks/keys paint a response fast); **content doesn't jump as it loads** (low layout shift / CLS — reserved space, no reflow); long lists stay smooth (virtualization, not 10k DOM nodes); skeletons/placeholders for waits under ~10s instead of a blank or a spinner; images have reserved dimensions.
- **Orchestrator Q:** *"Is 'fast' engineered here (virtualize, reserve space, split), or are we hoping the data is small?"*

### 3.4 State coverage: loading / empty / error / edge
Handling all four is the maturity marker amateurs skip.
- **Signals:** a real **loading** state (skeleton/placeholder); a **designed empty** state that guides the first action; a **graceful error** state with a way forward (not a raw stack or silent fail); **edge cases** handled (very long text, missing image, zero vs one vs many, stale/broken references degrade instead of crashing).
- **Orchestrator Q:** *"Show me loading, empty, error, and the ugly edge case — do all four exist?"*

---

## Layer 4 — Craft (the finish — only convincing if 1–3 are right)

### 4.1 Typography & reading rhythm
- **Signals:** a real type scale (few, deliberate sizes); comfortable measure (~60–75ch) and line-height; clear heading/body contrast; consistent vertical rhythm; numerals/labels aligned.
- **Orchestrator Q:** *"Is type on a scale, and is the reading measure controlled?"*

### 4.2 Accessibility & semantics
- **Signals:** full **keyboard** operation (tab order sane, `/`, Esc, arrows where expected); visible focus; correct roles/ARIA (a divider is a `separator`, a menu is a `menu`); focus is **trapped** in modals and **restored** on close; sufficient contrast; images have alt.
- **Orchestrator Q:** *"Can I do everything from the keyboard, and does a screen reader get the right roles?"*

### 4.3 Pattern consistency
- **Signals:** one predictable language — the same gesture does the same thing everywhere; icons mean one thing; identical spacing between like elements; no two components solving the same problem differently.
- **Orchestrator Q:** *"Is this the pattern we already use, or a new dialect?"*

### 4.4 Surface polish (colour, depth, spacing)
*Last, on purpose.*
- **Signals:** restrained palette from tokens; depth (shadow/elevation) used consistently to signal layering; generous, even spacing; alignment holds on a grid; nothing arbitrary.
- **Orchestrator Q:** *"Is every surface value coming from a token, applied consistently?"*

---

## What the lens misses (added dimensions)

- **A0 · Build/tooling hygiene (pre-Foundation).** Does it build clean — no console errors/warnings, no dead dependencies shipped (cf. the unused `allotment` dep), no undefined tokens at runtime? A noisy console is the cheapest tell that the foundation is leaky. *Q: "Does it run clean — zero console errors, no dead deps?"*
- **1.5 · Responsive & adaptive as a Foundation concern.** Not just "does it fit small screens" (Craft) but "is there a layout **strategy** — breakpoints/container queries/density modes — or is width handled ad hoc per component?" *Q: "Is responsiveness a system, or patched per component?"*
- **3.5 · Input & forms integrity.** Validation timing (on blur vs submit), inline error placement, preserved input on error, sane defaults, no lost work. Amateurs lose the user's typing on a failed submit. *Q: "If a submit fails, is the user's work preserved and the error shown where they can fix it?"*
- **4.5 · Internationalization & content elasticity.** Layout survives 2× longer strings, missing data, RTL; nothing assumes English-length labels. *Q: "Does the layout survive twice-as-long text and missing fields?"*
- **Cross-cutting · Trust & data safety.** Autosave/draft recovery, undo, confirm-on-destroy, no silent data loss. This spans Behaviour + contract and is often what separates "toy" from "tool." *Q: "What protects the user's work — undo, autosave, confirm?"*

---

## The one-line scorecard (carry this forward)

| Layer | Dimension | Score 0–3 |
|---|---|---|
| Foundation | tokens · primitives · state · data contract · (build hygiene · responsive strategy) | |
| Structure | shell · hierarchy/disclosure · navigation | |
| Behaviour | feedback/status · motion · perf/perceived speed · state coverage · forms | |
| Craft | typography · a11y · consistency · surface · i18n | |

Score foundation-first; if Craft > Foundation, write "lipstick" in the margin and direct the fix downward.

---

### Sources
- Atlassian Design System — Design tokens (single source of truth for design decisions): https://atlassian.design/foundations/tokens/design-tokens
- Adobe Spectrum — Design tokens: https://spectrum.adobe.com/page/design-tokens/
- web.dev — Cumulative Layout Shift (content-jump as an observable signal): https://web.dev/articles/cls
- web.dev — LCP and INP (responsiveness to clicks/keys as an observable signal): https://web.dev/blog/lcp-and-inp-are-now-baseline-newly-available
- Nielsen Norman Group — Skeleton Screens 101 (perceived performance): https://www.nngroup.com/articles/skeleton-screens/
- Nielsen Norman Group — Animation & motion in UX (motion tied to meaning): https://www.nngroup.com/articles/animation-purpose-ux/
