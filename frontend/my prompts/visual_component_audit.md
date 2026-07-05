Do not edit the code yet.

First perform a visual UI audit of this page as a design system.

Break the interface into visual categories and identify weaknesses in each category.

Analyze these categories:

1. Layout skeleton
- page shell
- two-column image/content layout
- top navbar
- persona/action strip
- content card
- visual card
- internal scroll areas
- bottom save/cancel bar

2. Density and spacing
- sections that take too much height
- controls that are oversized
- areas where vertical rhythm feels awkward
- places where padding is too large or too inconsistent
- places where content feels trapped inside containers

3. Component hierarchy
- primary actions
- secondary actions
- tabs
- metadata
- empty states
- editor tools
- persona links
- image annotation tools

4. Repeated container problem
Find every place where the UI uses a rounded rectangle, border, shadow, pill, or card.
Decide which containers are truly necessary and which should become borderless, transparent, inline, ghost-like, or hover-only.

5. Typography
- heading scale
- section labels
- nav text
- metadata text
- empty state copy
- button text
- tab text
- persona identity text

6. Color and material
- current dark palette
- accent color usage
- dull/boring areas
- overuse of terracotta
- lack of premium contrast
- places where subtle blur, translucency, gradient, or warmer surface treatment could improve the feeling
- places where effects would be unnecessary decoration

7. Editing mode
- what should fade away
- what should stay visible
- what should collapse
- what should become icon-only
- what should remain reachable but quiet

8. Empty state design
- “No story yet”
- “Unconceal this image”
- Story Blocks with 0 words
- Add Block section
- Compose with Sutradhar
Judge whether these feel elegant, premium, and calm.

9. Micro-interaction potential
- hover reveal
- focus reveal
- sticky compact headers
- opacity changes
- transitions
- active tab behavior
- inactive tab behavior

10. Implementation risk
For each issue, label it:
- safe CSS-only change
- small component layout change
- state/interaction change
- risky logic change

Output:
A structured audit table with:
- category
- problem
- exact visual symptom
- likely cause in styling/layout
- recommended fix
- implementation risk
- priority: P0/P1/P2

Do not write code yet.
Do not make vague suggestions like “improve spacing.”
Be specific and visual.