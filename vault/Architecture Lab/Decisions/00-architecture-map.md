# The Post Detail page, explained simply

This is the map of how the page is actually built today, and where the *architecture* (not the looks) is heavier than it needs to be. Read this first. The six prompt files then send Claude Code to dig into each area deeply.

## What the page is made of, top to bottom

There are **two full-width bars stacked on top of each other** before you even reach the work:

1. **The global navbar** (`NavBar.jsx`) — the "Drishtikone" logo plus nine links (Gallery, Highlights, Feed, Epics, Research, Personas, Unconceal, Anatomy, Motive), a theme toggle, and an Upload button. This bar is the same on every page.
2. **The post topbar** (`.post-detail-topbar` inside `PostDetailPage.jsx`) — a "back to Gallery" link, the "Sutradhar" brand name in the middle, and on the right the three buttons: **AI Assistant, Edit, Delete** (plus an "Unsaved" pill and *a second* theme toggle).

Under those two bars is the **split workspace** (`.post-detail-split`):

- **Left pane — "Visual"**, with tabs *Image / Annotations*. Inside it lives `BoundingBoxEditor`: a stats strip on top (annotation count, coverage %), the image in the middle where you draw boxes, and a list of annotation tags at the bottom.
- **A draggable divider** in the middle.
- **Right pane — "Content"**, with tabs *Story / Highlights / Unconceal*. This pane changes a lot depending on whether you are reading or editing.

## The one architectural idea behind everything

Almost every problem on your list is the same shape: **a thing that is really just a small piece of information or a small control has been given its own full-width section, its own heading, and its own box.** The page is built as *sections stacked on sections*, when a lot of those things should be small items sitting inside a shared surface.

You already felt this as "cards within cards." Architecturally the fix is not new boxes — it's *fewer* boxes and giving each thing one clear home.

## Where that shows up (the six lanes)

**Lane 1 — the top is doubled.** Two bars do the job of one. The theme toggle literally appears twice. On a focused editing page, the nine global links are probably not needed — they compete with the Sutradhar strip for the same job. Also, the three buttons (AI / Edit / Delete) sit permanently across the top; Delete is rare and dangerous, and Edit could be a small affordance on the Content pane instead of a top-level button. There is a real technical catch here: the navbar and the page are **siblings** in the code, so the page cannot shrink the navbar with styling alone — it needs a small logic change at the app level. Claude Code already discovered this in `border-layout-plan.md`.

**Lane 2 — the two panes don't actually talk.** They sit side by side, but nothing connects them. Clicking an annotation on the left does nothing to the right. The question is whether "Visual" and "Content" are truly two halves of one tool, or just two separate tools sharing a screen. Also each pane repeats a header with a title *and* tabs — some of that ("Visual", "Content" as words) may be noise.

**Lane 3 — the Visual pane squeezes the image.** The image has a stats strip above it and a tag list below it, so the actual picture is boxed in from both sides. This part also uses emojis as icons and a "glassmorphism" style that appears nowhere else in the app — a little style island. Each drawn box carries a label, two corner buttons, a tooltip, and eight resize handles, which is a lot of furniture per box.

**Lane 4 — the Content view mode scatters small things into big sections.** The "From @handle · Open persona" line is a full-width band just to show one handle. The tags show up in a block at the very *bottom* of the pane in view mode — but in a totally different place (the side column) when editing. So tags have no single home, which is exactly why they feel "out of place." The empty "No story yet" state is a big centred hero floating in an otherwise empty pane.

**Lane 5 — the writing area is the heaviest.** This is the big one. Every single text block carries its *own* formatting toolbar, its *own* row of six colour swatches, and its *own* move/delete buttons. Ten blocks means ten toolbars stacked down the page. On top of that there are *three* different ways blocks get added (a separate "Add block" section, the Sutradhar composer that appends blocks, and the AI sidebar). And the edit view splits into two columns inside an already-narrow pane. This is where "optimal components instead of congestion" will pay off the most — for example, one shared toolbar that appears only when you select text, instead of one per block.

**Lane 6 — Unconceal is three tools in a trench coat.** It stacks Anatomy, then Aletheia's reading, then your commentary, each with its own little header, in one long scroll. And "Anatomy" (naming parts of the image) overlaps with the "Annotations" over in the Visual pane — the app has two different places for what is basically the same idea: marking parts of a picture. That duplication is worth deciding on before any redesign.

## The limits of this work (so we don't drift)

- We touch **only** the Post Detail page and the components it uses. Not the gallery, feed, personas pages, etc.
- We change **structure**: what components exist, how they nest, where each thing lives. We do **not** pick colours or fonts or do spacing polish yet.
- The aim is **the smallest set of components that still does everything the page does today** — nothing removed in function, just fewer containers and one clear home per thing.
- Every lane ends by asking Claude Code for *questions back to you*, so you stay in control instead of it guessing.
