Follow AGENTS.md. UI-only, small diff, run `npx vite build` to verify.

Target: the Story tab EDIT mode in src/components/PostDetailPage.jsx +
PostDetailPage.css (the isEditing branch: "Story Blocks" head, editor-meta,
advanced-editor, add-block-menu, sutradhar-composer, Tags section, footer).

Problem: it feels cramped and congested — weak vertical rhythm, groups run
into each other, no clear separation between "write blocks", "add block",
"compose with AI", and "tags".

Do:
- Establish a consistent vertical rhythm between the major groups using the
  spacing scale (--space-*). Group related controls tighter, separate unrelated
  groups more.
- Give each sub-section (blocks / add-block / composer / tags) clear visual
  grouping and enough breathing room; the composer and tags should read as
  distinct cards/zones, not a wall.
- Keep the token system; no inline styles, no magic px.
- Do NOT change any logic, handlers, or state — layout/spacing/CSS only.

Then show me the diff and confirm the build passed.


I want you to deeply improve the frontend UI/UX of this page, not by changing the product logic, but by redesigning the layout, spacing, sizing, hierarchy, and visual rhythm.

Current problem:
The interface feels congested, heavy, and slightly awkward. Too many components are visually shouting at the same time. The page has a lot of functional pieces — navigation, persona header, tabs, story blocks, AI compose panel, tags, save/cancel actions — but they do not fade into a calm hierarchy. The result feels cramped and unfinished.

Goal:
Make the UI feel refined, calm, spacious, editorial, and lightweight. The components should feel smaller, more breathable, and better layered. The page should have a “soft writing studio / literary workspace” feeling rather than a dashboard stuffed with controls.

Key improvements needed:

1. Reduce visual congestion
- Decrease button sizes where possible.
- Reduce excessive padding inside cards and controls.
- Make secondary controls visually quieter.
- Do not let every border, shadow, tab, button, and card compete equally.
- Use more negative space, but without making the layout feel empty.

2. Improve hierarchy
- The main content editor should clearly be the focus.
- Persona info, tabs, block buttons, and AI compose tools should feel supportive, not dominant.
- “Story”, “Highlights”, and “Unconceal” tabs should be smaller and more elegant.
- “Save” and “Cancel” should stay accessible but not feel like they are floating awkwardly.

3. Make components smaller and more subtle
- Navigation items should feel slimmer.
- Header buttons should be compact.
- The AI Assistant / Delete / Upload buttons are currently too visually loud.
- Inputs and panels should have softer borders, lighter backgrounds, and less height.
- Use small-radius pill buttons only where they help. Avoid everything becoming a pill.

4. Fix spacing and alignment
- Align the content panel, header area, and controls more precisely.
- The large white editor area should not feel like a random blank box.
- The bottom save bar should feel integrated with the page, not pasted over it.
- Vertical spacing between sections should be consistent.
- Left/right padding inside the main content area should be visually balanced.

5. Improve the “Compose with Sutradhar” panel
- Make it lighter, smaller, and less boxy.
- The panel should feel like a subtle assistant tray, not a giant card.
- “Draft from image” and the prompt input should align beautifully.
- The Write button should be less bulky.
- Helper text should be smaller and quieter.

6. Improve the block controls
- Paragraph / Heading / Quote buttons should be compact and elegant.
- They should look like small writing tools, not large dashboard buttons.
- Use subtle hover states.
- Consider grouping them in a lightweight toolbar.

7. Improve typography
- Keep the literary/editorial identity, but improve size hierarchy.
- Section titles like CONTENT, STORY BLOCKS, TAGS should be smaller, letter-spaced, and quieter.
- Persona title “Sutradhar” can stay strong, but the subtitle should be refined.
- Body text and labels should use consistent font sizes.

8. Improve visual depth
- Use fewer heavy shadows.
- Use very subtle borders and soft background differences.
- Components can “fade off” by using low-contrast borders, muted text, and gentle surfaces.
- The UI should feel layered, but not boxed everywhere.

9. Responsive behavior
- Make sure the layout works on desktop first.
- The main editor panel should scale gracefully.
- Avoid fixed heights that cause awkward scroll behavior.
- If the page scrolls, the important action areas should remain natural and usable.

10. Do not break functionality
- Keep all existing buttons, tabs, inputs, and actions.
- Do not remove features.
- Only change layout, styling, spacing, component sizing, and visual structure.
- Preserve existing state logic and event handlers.

Design direction:
Think: quiet literary software, Notion-like calmness, refined manuscript editor, soft ivory backgrounds, restrained terracotta accents, delicate separators, small precise controls, airy layout, editorial typography, and subtle interaction states.

Please inspect the current components and CSS, then refactor the frontend styles/component layout to achieve this. After changes, explain:
- which files you changed
- what visual problems you fixed
- what design system decisions you applied


Be opinionated. Do not only make tiny CSS tweaks. Rebalance the whole visual composition. The page should immediately feel less crowded, more mature, and more pleasurable to write in.
Also improve editing-mode spatial behavior.

Problem:
The top navigation/header area and persona action strip consume too much vertical space while editing. When the user is focused on editing content, these areas should become quieter or temporarily fade away so the editor gets more breathing room.

Required behavior:
- Create a focused editing mode or compact editing layout.
- When the user is editing content, the large top nav/header should reduce visual dominance.
- The top app navbar can become smaller, sticky-but-compact, translucent, or fade into the background.
- The persona/action strip with Sutradhar, AI Assistant, Delete, and utility buttons should not remain visually heavy during editing.
- Consider collapsing secondary header controls into a compact row, icon-only state, or soft floating toolbar.
- The content/editor area should gain more vertical space.
- Avoid removing actions completely; they should remain discoverable but not visually loud.
- The user should feel like they have entered a writing surface, not that they are trapped under two thick headers.

Possible implementation ideas:
- Add an `.editing-mode` or `isEditing` UI state if the app already tracks editor focus.
- On editor focus, apply compact styles to header/nav/action rows.
- Use opacity, transform, reduced padding, and smaller controls.
- Keep primary save/cancel actions accessible.
- Use smooth transitions so the page feels alive, not jumpy.
- If state logic is too risky, implement a CSS-first compact mode using focus-within around the editor container.

Design feeling:
When editing begins, the interface should gently step backward. The writing surface should come forward.