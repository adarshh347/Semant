# Frontend Playbook — Semant / Drishtikone

A living record of *how we think about frontend*, not just what we changed.
The goal is to build an **eye** and a **method** you can reuse on any project, so you
can direct AI precisely and judge what it gives back. This file grows as we work.

---

## 0. The mindset shift (why you feel "blank")

The 2022 skill was *knowing CSS* — memorising flexbox, grid, media queries.
That knowledge is now cheap: AI writes the CSS. The scarce, valuable skill is the
layer above it:

1. **Diagnosis** — looking at a screen and naming *why* it feels weak.
2. **Judgment** — deciding which problems actually matter.
3. **Direction** — describing the target precisely enough to execute (yourself or via AI).
4. **Evaluation** — knowing whether the result is good.

You already have the hard part covered on this project: a real **design system**
(`frontend/src/index.css` + `design-system/tokens.css`) — Fraunces + Inter, paper/ink
neutrals, terracotta accent, a fluid type scale, spacing tokens, dark mode. Your gap
is not the system; it's *applying it consistently and solving interaction problems*.

---

## 1. The Lens — 7 dimensions to score any screen

Run this on every section. Give each a 1–5 and a one-line note. The low scores are
your work list.

1. **Layout & spacing rhythm** — Is spacing on a consistent scale (using `--space-*`)?
   Do related things sit close and unrelated things sit apart? Any lonely elements
   floating in a void, or cramped elements with no breathing room?
2. **Visual hierarchy** — Where does the eye land first? Is that the *most important*
   thing? Is type scale/weight/color doing the ranking, or is everything the same?
3. **Color, surface & elevation** — Are tokens used (never raw hex)? Do surfaces and
   shadows communicate depth/grouping, or is it flat and ambiguous?
4. **Interaction & affordance** — Do clickable things *look* clickable? Are there
   hover/active/focus/disabled states? Is feedback immediate?
5. **Usability & ergonomics** — Can the user do the core task comfortably? (Mouse
   travel, target sizes, number of steps, cognitive load.) Critical for the
   annotation/anatomy tools.
6. **Motion** — Do transitions guide attention and feel intentional, or absent/janky?
7. **Consistency** — Same patterns for same jobs across the app? Reusing components
   and tokens, or one-off inline styles everywhere?

---

## 2. The Method — per-section loop

For each section we:

1. **Screenshot** the current state (light + dark, empty + populated).
2. **Name the job** — in one sentence, what is this screen *for*?
3. **Score the 7 dimensions**, note the low ones.
4. **Prioritise** by *impact × (1/effort)*. Fix the cheap, high-impact things first.
5. **Design the target** — describe it in words before touching code.
6. **Implement the smallest change** that moves the needle.
7. **Review together** against the job and the lens.

Rule of thumb: *empty states, spacing rhythm, and hierarchy* give the biggest visible
wins for the least effort. Do them before anything fancy.

---

## 3. Recurring failure patterns found in this codebase

Things to watch for and fix on sight (these are the "tells" of hand-grown UI):

- **Inline styles instead of tokens.** e.g. `StoryFlow.jsx` uses `marginTop:'15px'`,
  `fontSize:'13px'`, raw `#fff`/`#ef4444`, and mixes px with rem. This breaks the
  spacing scale, can't theme for dark mode, and is unmaintainable. → Move to CSS
  classes that use `--space-*`, `--fs-*`, and color tokens.
- **Magic numbers.** `15px`, `12px`, `8px` scattered around instead of the 4px-based
  scale (`--space-1..24`). Pick from the scale; the rhythm becomes automatic.
- **No empty states.** When data is missing, sections render *nothing*, leaving a
  broken-looking void (see the Story tab). Every data-driven view needs a designed
  empty state: icon + title + one line + a clear next action.

---

## 4. Section audits & decisions log

### Editor › Story tab (PostDetailPage) — in progress

**Job:** Show (and let you write) the written story attached to an image.

**Diagnosis:** The "totally broken" look happens when a post has **no story blocks**.
View mode rendered *nothing* between the persona pill (top) and the tags (bottom), so
the tall scroll column pinned two lonely pills to opposite ends — an empty void that
reads as a bug. (Dimensions failing: #1 spacing/void, #2 hierarchy, #5 usability — no
guidance on what to do next.)

**Fix #1 (this pass):** Added a designed **empty state** — soft accent icon, serif
title "No story yet", one guiding line, and two clear actions ("Write the story" /
"Draft from image"). It fills the void intentionally and tells the user what to do.
Uses scoped `.story-empty*` classes on the token system (no inline styles).

**Next:** review a *populated* story view + the Edit-mode spacing/congestion.
