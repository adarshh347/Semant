ground

what matters in successful implementation of ground is (region, soft field, etc)
what it is best for(region can serve objects, soft fields can serve light,shadows,atmospheres, etc) 
then how the user will be able to create it-how handy it will be, this factor needs to be planned researched well
then
how it renders in field - because it should not create mess on original image, mix easily cleverly, will take separate platform or swtich or whatever to get rendered
and the second hand rendering will also matter
can we make it render as percept among the pages, between the lines and between the brainstorming sections of atlas

then how it recalls also matters

A Percept may use one Ground or combine several.

## Compact Ground set

| Ground            | Best for                                                           | How the user creates it                                   | How it renders in Field                                             | How it recalls                                                    |
| ----------------- | ------------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------- |
| **Region**        | Object, garment part, face, flower, book                           | Click detection, SAM selection, box, polygon, lasso       | Clean outline plus faint translucent fill                           | The form illuminates; surroundings gently recede                  |
| **Soft Field**    | Light, shadow, atmosphere, colour influence, visual intensity      | Paint with a feathered brush; add/subtract strength       | Elegant single-colour glow or wash—not a scientific rainbow heatmap | The quality gradually blooms across the affected area             |
| **Path**          | Gaze, movement, brush direction, visual flow, pressure             | Draw an arrow or curved line                              | Tapered path with minimal directional cue                           | Light travels along the path, recreating the eye’s movement       |
| **Boundary**      | Dissolving edge, sharp-to-soft transition, figure–ground ambiguity | Trace along the transition; adjust band width             | Thin two-sided shimmer or feathered edge band                       | The boundary oscillates, magnifies, or briefly increases contrast |
| **Constellation** | Repeated flowers, colours, motifs, shapes, visual rhythm           | Select several instances; optionally “find similar”       | Small related halos, marks, or subtle numbered points               | Members pulse together or appear sequentially as one family       |
| **Relation**      | Contrast, echo, balance, opposition, dominance                     | Select two or more Grounds and connect them               | Grounds illuminate together; connector remains faint or hidden      | Alternates A/B, then reveals both together with the relationship  |
| **Frame**         | Overall mood, composition, enclosure, openness, shallow depth      | Choose “whole image”; optionally mark supporting evidence | Delicate frame treatment; no fake full-image mask                   | The full image shifts while supporting areas emerge in sequence   |

## Rendering rules

The rendering is not decoration. It is the moment the Percept becomes alive again.

### 1. Preserve the image

Overlays must never suffocate the artwork. Use:

- low-opacity treatments;
- soft transitions;
- restrained colour;
- temporary emphasis;
- instant clear/reset;
- original-image toggle.

The user should feel that the painting is revealing something—not that analytics have been poured over it.

### 2. Use motion to explain structure

Motion should communicate the kind of Ground:

- Region: fade in;
- Field: bloom;
- Path: travel;
- Boundary: shimmer;
- Constellation: pulse;
- Relation: alternate, then unite;
- Frame: whole-image tonal transition.

Each Ground acquires a recognisable visual behavior.

### 3. Reveal in stages

A strong recall sequence could be:

1. unrelated image areas recede slightly;
2. primary Ground appears;
3. supporting Grounds appear;
4. relationship or direction animates;
5. the Percept’s words arrive.

That sequence recreates the original act of seeing.

### 4. Keep interaction simple

Field only needs six visible creation actions:

> **Select · Brush · Trace · Collect · Connect · Frame**

Boundary can live as a mode within Trace. Region refinement can live inside Select.

The philosophical categories remain backstage.

## How a Ground becomes a Percept

After creating any visual Ground, a small composer appears:

> **What do you notice here?**

The user writes:

> The pale dress creates an opening in the garden’s density.

That produces:

```
Percept
├── expression
├── ground_ids[]
├── image_id
├── creator
└── optional visual properties
```

Optional properties might include:

- light
- colour
- material
- movement
- composition
- attention
- atmosphere
- repetition
- contrast

These help retrieval, but the user should never be forced to classify before writing.

Multiple Grounds can produce one Percept:

```
dress Region
+ surrounding Soft Field
+ dissolving Boundary
= “The figure emerges from the garden without fully separating from it.”
```

Multiple Percepts can later produce a deeper Percept:

```
“Branch encloses the figure”
+ “Dress opens a field of light”
= “The woman is enclosed from above but released into light below.”
```

## Making Percepts usable inside words

Every Percept receives a stable identity. Its expression can then become a **Mention** anywhere language appears:

- manuscript paragraph;
- image caption;
- annotation;
- essay note;
- social post;
- campaign copy;
- discussion;
- Atlas node;
- AI-generated draft.

A Mention should look like ordinary text—not an ugly database token. Its connection can remain quiet until interaction.

For example:

> Her body appears to be **slowly absorbed by the garden**.

The linked phrase could have a very subtle underline or margin glyph.

### Hover

A small preview shows:

- image crop or thumbnail;
- Percept expression;
- Ground type;
- one-line provenance.

### Focus or click

The full Field opens and replays the Ground:

- dress highlights;
- vegetation blooms;
- shared boundary shimmers.

### Writing nearby

The writer can invoke the Percept through:

- `/percept`;
- `@percept`;
- search by phrase;
- image thumbnail;
- “show related percepts”;
- automatic suggestions based on the current sentence.

Selecting it inserts a Mention without flattening the Percept into copied text.

```
Words ──Mention──▶ Percept ──Grounds──▶ Image
```

The sentence can change while the underlying Percept remains stable.

## Why the set helps the whole system

### In Field

Grounds give the user several precise ways to point—not only at objects, but at light, movement, repetition, transitions, and composition.

### In Writer

Mentions allow prose to remain attached to the actual visual evidence from which it emerged.

### In Codex

The same Percept can recur across chapters without duplicating its image annotation. Every use remains connected to one perceptual identity.

### In Atlas

Percepts become structural nodes:

- this visual rhythm recurs across five works;
- this lighting Percept supports three interpretations;
- this Monet Percept contrasts with another painter’s treatment.

### In AI generation

The agent receives meaningful evidence:

> Use these four Percepts, preserve their visual specificity, and draft the paragraph.

It does not merely receive an image and hallucinate a fresh description every time.

### In retrieval

The system can retrieve through several routes:

- words: “dissolving boundary”;
- visual similarity;
- Ground typ