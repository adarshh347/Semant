# The Purpose lens — the third axis (and the page's new name)

We now judge every part of this page on **three axes, in this order**:

1. **Purpose** — what is this *for*? Does it serve the job the page exists to do?
2. **Structure** — is it built with the fewest components, each with one clear home? (the "fixing" / architecture work)
3. **Surface** — how does it look? Colour, spacing, premium feel. (comes last)

**The rule: Purpose decides Structure decides Surface.** Never pick a component before the job is clear; never pick a colour before the component is clear.

## The page is now called **Drishya**

Drishtikone = the way of seeing (the app). **Drishya = the one image being seen and dwelt upon** (this page). Code identifier: `DrishyaPage`. The rename from `PostDetailPage` happens in a **later build pass**, not during analysis.

## Drishya's purpose statement

> Drishya is where a single image is turned into meaning — read deeply, marked part by part, and written into a story both by hand and with Sutradhar — while the reader can always trace **who saw what** and **who wrote what**.

Every component should answer to that sentence. If it doesn't serve reading, marking, writing, or tracing meaning, it is either overhead or in the wrong place.

## Purpose questions that change the Structure (fold these into the lanes)

These came up as design wishes, but each forces a concrete structural consequence. Claude Code must plan for them.

### 1. Two kinds of story, one surface (Lane 4 + 5)
Drishya holds **human-written** passages *and* **AI-generated** passages (Sutradhar / Draft-from-image), and the AI ones can be long. They live together in one block list today, but a block has **no idea who made it**. The block object is `{ id, type, content, color }` — there is no author.

- **Structural consequence:** add an `origin` field to every block, e.g. `origin: 'human' | 'sutradhar'`. Set it wherever blocks are created (`addBlock`, `draftFromImage`, `writeFromPrompt`, sidebar `handleSuggestionSelect`).
- **Purpose payoff:** the reader can tell human from AI. **Surface (later):** show it quietly — a thin side-rule or a small label — *not* heavy boxes. Plan the field now; style it later.

### 2. The editor-model decision (Lane 5, the big one)
Two paths to fix the toolbar/colour/controls multiplication:
- **(A) Patch:** keep one TipTap editor per block, add one shared toolbar that targets the active block (`selectedBlockId` already exists).
- **(B) Rebuild:** one TipTap editor for the whole document, each block a node inside it.
Path B is a bigger change but makes `origin` marking, drag-reorder, and inline AI blocks natural. **Claude Code must lay out both paths with effort/risk so Adarsh can choose.** This is the most consequential decision on the page.

### 3. Compose with Sutradhar (Lane 5)
Same multiplication family as the toolbar. It is one of the three add-paths. Plan it as part of the single `insertBlock()` convergence, and decide whether the AI sidebar and the inline composer should be **one** assistant surface or two with clear roles.

### 4. Highlights should live in context (Lane 4)
The highlight feature already stores which block a quote came from (`block_id`), but the Highlights tab shows quotes as orphans. Purpose says: let the reader **jump back to where the quote lives** in the story. Structural: use the `block_id` link that already exists. Small change, real payoff.

### 5. The region duplication (Lane 3 + 6)
`bounding_box_tags` (Visual pane) and `region_annotations` / Anatomy (Unconceal) both mark parts of the image. That is two systems for one purpose — "mark a part." Decide merge-or-keep, because it affects how "who saw what" is traced.

## How to use this lens
For each component in each lane, answer three quick questions: **Does it serve Drishya's purpose? Is it the leanest structure? (Surface: skip for now.)** A component that fails Purpose shouldn't be restructured — it should be removed or moved.
