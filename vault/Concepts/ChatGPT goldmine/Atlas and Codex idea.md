The idea is building **a narrative system in which images do not merely inspire prose—they remain structurally present inside the story.**

Today, Chiasm is essentially:

```text
One image
   ↓
Regions
   ↓
Percepts
   ↓
Mentions inside writing
   ↓
A grounded reading/manuscript
```

Atlas and Codex take that same logic and stretch it across an entire essay, novel, research work, or image-led collection:

```text
Many images
   ↓
Many percepts
   ↓
Narrative arrangement
   ↓
Many connected pages
   ↓
Long-form work
```

The project stops being only an image-reading tool. It becomes a **percept-grounded narrative studio**.

# The two surfaces

## Codex: where the actual long-form work lives

Codex is the book.

It contains the prose the user will eventually read, revise, export, or publish:

```text
Codex: “The Architecture of Restraint”
├── Chapter 1 — The disciplined shoulder
├── Chapter 2 — Concealment
├── Chapter 3 — Fabric and authority
├── Chapter 4 — The body beneath structure
└── Chapter 5 — Release
```

Each chapter or page is its own editor document.

So instead of one enormous BlockNote document, you have:

```text
Work
├── Page A → BlockNote document
├── Page B → BlockNote document
├── Page C → BlockNote document
└── Page D → BlockNote document
```

The Codex supplies the larger structure around those documents:

- chapter ordering
    
- page outline
    
- links between chapters
    
- recurring motifs
    
- characters or entities
    
- backlinks
    
- cross-page percept references
    

It is closer to a combination of:

```text
Scrivener
+ Obsidian
+ Semant’s percept architecture
```

But the crucial difference is that Codex can cite actual visual attention.

A passage does not merely say:

> The shoulder feels restrained.

It can carry a real Mention pointing to:

```text
image-12
   ↓
region-4
   ↓
percept: “restrained shoulder drape”
```

That percept might appear in chapter 2, chapter 5 and chapter 9.

The prose remains connected to the seen object that generated it.

---

## Atlas: where the story is arranged before it is written

Atlas is not primarily a prose editor.

It is a map.

You place narrative objects on a canvas:

```text
[Arrival]
    │ precedes
    ▼
[The red dress]
    │ intensifies
    ▼
[Social discomfort]
    │ releases_into
    ▼
[Private tenderness]
```

Some nodes are conventional narrative objects:

- scene
    
- beat
    
- character
    
- event
    
- motif
    
- tension
    

Some are specifically Semant objects:

- percept
    
- image region
    
- Aletheia reading
    
- taste pattern
    

The user is therefore not writing sentences first. They are arranging meaning.

For example:

```text
[Percept: rigid neckline]
          │ contrasts_with
          ▼
[Percept: loose lower drape]
          │ creates
          ▼
[Tension: discipline vs surrender]
          │ appears_in
          ▼
[Scene: protagonist enters the reception]
```

That graph already says something.

Even before prose exists, the arrangement contains a narrative proposition:

> The scene should embody the tension between control above and release below.

The Atlas then lets the agent turn that structure into prose.

# “The arrangement is the prompt”

This is the most important line in the proposal.

Ordinary AI writing usually begins with a textual instruction:

```text
Write a scene where a woman enters a reception wearing a red dress.
Make it atmospheric.
```

That prompt is vague. The model fills the emptiness with generic narrative habits.

Atlas instead gives the model a structured subgraph:

```text
Scene:
- protagonist enters a formal reception

Grounding percepts:
- rigid neckline
- gathered shoulder
- loosening lower drape

Narrative tension:
- public control contrasts with private vulnerability

Motif:
- restraint producing the conditions for release

Relation:
- neckline intensifies public authority
- lower drape foreshadows later emotional release

Voice context:
- the author repeatedly prefers tactile description
- avoid explicit psychological explanation
```

The agent is no longer asked to hallucinate the story’s inner logic.

The human has already designed that logic spatially.

The model’s job is to **carve prose from the arrangement**.

That is much more interesting than autocomplete.

# What the story agent actually does

The agent should not be one prompt saying “look at this graph and write.”

It needs a staged pipeline.

```text
Selected Atlas subgraph
        ↓
1. Plan
        ↓
2. Retrieve grounding
        ↓
3. Generate prose
        ↓
4. Place prose into Codex
        ↓
5. Record Mentions and provenance
```

## 1. Plan

The agent reads the selected nodes and edges.

It determines:

- what scene or passage is being requested
    
- which tension is central
    
- what must happen first
    
- what should remain implicit
    
- which percepts must appear
    
- what role each percept plays
    

It might construct an internal plan:

```text
Opening:
establish social rigidity through neckline imagery

Middle:
shift attention toward the drape loosening beneath the shoulder

Turn:
connect material release to the protagonist’s private hesitation

Ending:
do not resolve the tension; preserve it
```

## 2. Retrieve grounding

The agent retrieves:

- percept crops
    
- region notes
    
- Aletheia readings
    
- earlier chapters
    
- character history
    
- motif occurrences
    
- the author’s Anuraṇana taste patterns
    
- relevant research or quotations
    

This is where the prose becomes evidence-bound.

## 3. Generate

The model writes from the plan and retrieved material.

## 4. Place

The result is inserted into a particular Codex page, not merely returned in a chat window.

## 5. Write Mentions back

If the generated paragraph used:

```text
percept-12
percept-18
motif-4
```

the system records those connections.

That means the manuscript and Atlas remain linked after generation.

You can later ask:

```text
Where has this percept been used?

Which chapters embody restraint → release?

Which passages were generated from this tension node?

What images ground chapter 7?
```

The generation process enriches the graph rather than producing disposable text.

# Why Percept must become a real backend entity

Currently, a percept may exist as a composition assembled inside a particular product surface:

```text
Region
+ note
+ reading
+ local UI state
= percept-like object
```

That works while the percept belongs to one image and one post.

It breaks when the same percept must travel across multiple chapters.

For example:

```text
Percept: “restrained shoulder drape”

Mentioned in:
- Work A, Chapter 2
- Work A, Chapter 7
- Essay B, Page 1
- Study C
```

Now the percept needs its own identity:

```js
Percept {
  id: "percept-12",
  region_id: "region-44",
  title: "restrained shoulder drape",
  creator_note: "...",
  reading_ids: [...],
  embedding_id: "...",
  created_by: "...",
}
```

Then a Mention becomes the join between a percept and a textual location:

```js
Mention {
  id: "mention-88",
  percept_id: "percept-12",
  work_id: "work-4",
  page_id: "page-17",
  block_id: "block-42",
  role: "evidence"
}
```

The percept remains stable.

Its appearances multiply.

That is why the long-form system forces a backend promotion. Cross-document identity cannot safely live only in frontend composition.

# The shared spine

Atlas and Codex are not two unrelated products.

They are two views over the same narrative objects.

```text
                  ┌──────────────┐
                  │    Atlas     │
                  │ arrangement  │
                  └──────┬───────┘
                         │
                         │ nodes and relations
                         ▼
Percepts ────────► Narrative graph ◄────── Characters
                         │
                         │ generation / linking
                         ▼
                  ┌──────────────┐
                  │    Codex     │
                  │    prose     │
                  └──────┬───────┘
                         │
                         │ Mentions
                         ▼
                  Percepts / motifs /
                  entities / readings
```

Atlas emphasises:

- structure
    
- sequence
    
- relation
    
- tension
    
- possibility
    

Codex emphasises:

- sentences
    
- pages
    
- chapters
    
- voice
    
- revision
    
- continuity
    

One is the skeleton.

The other is the flesh.

# A concrete example

Imagine you want to build a long essay or fictional work around “authority and softness.”

## Step 1: collect percepts

From several images:

```text
Percept A
Rigid black neckline

Percept B
Loose orange drape

Percept C
Hand partially hidden by fabric

Percept D
Architectural column under warm light
```

## Step 2: arrange them in Atlas

```text
[Rigid neckline]
       │ establishes
       ▼
[Authority]
       │ contrasts_with
       ▼
[Loose orange drape]
       │ releases
       ▼
[Vulnerability]

[Hidden hand]
       │ echoes
       ▼
[Concealment]

[Architectural column]
       │ intensifies
       ▼
[Authority]
```

Then add narrative beats:

```text
[Public entrance]
[Private room]
[Moment of exposure]
```

Connect them:

```text
Public entrance
    → authority
    → rigid neckline

Private room
    → vulnerability
    → loose drape

Moment of exposure
    → concealment breaks
    → hidden hand
```

## Step 3: invoke an Atlas verb

You select:

```text
Public entrance
Authority
Rigid neckline
Loose drape
```

and choose:

> Carve this scene as an escalation.

The agent plans and generates a scene into Codex.

## Step 4: Codex receives the result

The generated chapter contains actual Mentions:

```text
Paragraph 1 → percept A
Paragraph 3 → percept B
Chapter motif → authority/release
```

Later you edit the prose manually.

The links remain.

## Step 5: Atlas reflects what became real

The scene node can now show:

```text
Generated into:
Chapter 2, blocks 14–22

Grounded by:
percept A, percept B

Status:
drafted
```

The map is no longer just planning residue. It remains a living structural interface over the manuscript.

# Why this is not simply React Flow plus ChatGPT

A generic implementation would be:

```text
draw boxes
connect them
serialize graph
ask LLM to write
```

That would be easy to imitate and likely produce generic prose.

The differentiating layer is the shared grounded ontology:

```text
Region
→ Percept
→ Reading
→ Mention
→ Narrative node
→ Codex passage
```

Each step preserves identity and provenance.

The output can answer:

- Which visual evidence grounded this paragraph?
    
- Which interpretation was used?
    
- Was the passage written by the author or generated?
    
- Which motif does it participate in?
    
- Where else does this percept occur?
    
- How has this percept’s meaning changed across the work?
    

That traceability is the moat.

# The Perceptual Library or “Field as drawer”

Inside one-image Chiasm, the Field is the visible image.

Inside Codex, there may be no single dominant image.

The Field therefore becomes a drawer or dock:

```text
Perceptual Library
├── recent images
├── pinned regions
├── named percepts
├── Aletheia readings
├── recurring motifs
└── related studies
```

While writing chapter 6, the user can summon:

```text
“Show every percept related to concealment.”
```

or:

```text
“Bring back the orange shoulder from the reception study.”
```

Then drag or cite it inside the manuscript.

This generalises the earlier Perceptual Margin idea.

Originally the margin meant:

> Keep the current image’s percepts near the writing.

Now it means:

> Keep the relevant perceptual corpus near the long-form work.

That is a much larger and more durable idea.

# Page connections and narrative backlinks

Pages should not only exist in a linear list.

A novel or long essay contains several simultaneous structures:

```text
chronological order
character arc
motif recurrence
conceptual argument
visual evidence
draft variants
```

So page connections may include:

```text
Chapter 2 precedes Chapter 3

Chapter 7 echoes Chapter 2

Chapter 4 resolves tension introduced in Chapter 1

Chapter 9 reuses motif “concealed hand”

Chapter 6 cites percept “orange drape”
```

Codex can therefore offer multiple views:

```text
Outline view
Timeline view
Motif view
Character view
Percept backlink view
Atlas graph view
```

The manuscript remains readable linearly, but its deeper structure becomes inspectable.

# How this connects to your streaming idea

The text-and-media stream could become the live substrate beneath Atlas and Codex.

As the user writes or explores media, the stream detects:

```text
new idea
new tension
repeated motif
new percept connection
possible scene
contradiction
```

Those do not all need to become prose.

Some can become suggested Atlas nodes.

For example:

```text
User repeatedly writes about:
discipline giving way to softness

Stream detects:
recurring narrative tension

Suggested Atlas node:
“Tension: restraint produces release”
```

The user can accept it into the map.

Similarly, selecting a region and writing several sentences might produce:

```text
Suggested percept node:
“Ceremonial restraint at the shoulder”
```

So the architecture could eventually become:

```text
Percept / media interaction
        ↓
Semantic stream
        ↓
Atlas suggestions
        ↓
Human arrangement
        ↓
Story agent
        ↓
Codex prose
```

The stream observes formation.

Atlas stabilises structure.

Codex stabilises prose.

# The backend shape

A lean initial model could be:

```text
Work
- id
- title
- description
- status

Page
- id
- work_id
- title
- order
- text_blocks / BlockNote document reference

Percept
- id
- region_id
- title
- note
- embedding_id

Mention
- id
- percept_id
- page_id
- block_id
- role

AtlasGraph
- id
- work_id

AtlasNode
- id
- graph_id
- type
- label
- payload/reference_id
- position

AtlasEdge
- id
- graph_id
- source_node_id
- target_node_id
- relation_type

GenerationRun
- id
- graph_id
- selected_node_ids
- target_page_id
- plan
- output_block_ids
- model/provenance
```

Keep the Atlas graph thin.

Do not immediately build a universal knowledge graph engine.

The node can carry:

```js
{
  type: "percept",
  reference_id: "percept-12"
}
```

The canonical percept data remains in the Percept table.

The graph stores arrangement, not duplicated truth.

# What the MVP is truly trying to prove

The MVP is not trying to prove that you can build:

- a multi-page editor
    
- a node canvas
    
- an LLM button
    

All of those are already known to be possible.

It needs to prove one specific loop:

```text
Real visual percepts
        ↓
Human arranges a narrative relation
        ↓
Agent understands that arrangement
        ↓
Grounded prose is generated
        ↓
Prose retains links to its perceptual sources
```

If that loop feels powerful, the entire initiative has life.

If it produces ordinary prose with decorative graph links, then the architecture is not yet doing enough.

# Codex-first versus Atlas-first

The document leans Atlas-first because Atlas proves the bolder claim.

Conceptually, I agree—but technically there is an important dependency.

Atlas needs somewhere legitimate to put its prose.

And currently the real BlockNote migration is not complete: only the Phase 0 harness exists. The converter and production editor swap remain unfinished.

So the practical order should probably be:

```text
Foundation:
finish BlockNote migration

Small Codex substrate:
Work + Page + one reusable editor mount

Then Atlas proof:
3 node types
typed edges
one generation verb
output into one Page
Mentions written back
```

This is not the same as building the complete MVP-Codex first.

It means building only the minimum Codex receiving surface required for Atlas.

The boldest first product demonstration can still be Atlas:

> Arrange two percepts and one tension, then carve a grounded paragraph into a page.

But the page substrate must exist beneath it.

# The best first verb

Do not begin with:

```text
Generate my whole novel.
```

Begin with something narrow and falsifiable:

> **Write the tension between these two percept nodes.**

Input:

```text
Percept A
Rigid shoulder structure

Percept B
Loose lower drape

Edge
contrasts_with

Tension node
public control / private release
```

Output:

- one paragraph
    
- inserted into a selected page
    
- linked back to both percepts
    
- marked as AI-originated
    
- editable by the human
    

That single operation tests:

- graph selection
    
- typed relation semantics
    
- percept retrieval
    
- multimodal grounding
    
- generation
    
- Codex insertion
    
- Mention creation
    
- provenance
    

It is a tiny surface with enormous architectural coverage.

# Co-writer versus co-architect

These should eventually be separate modes.

## Co-writer

Turns an existing structure into prose:

```text
Expand this beat.
Write this tension.
Carve this scene.
Rewrite from this percept.
```

The human determines the structure.

## Co-architect

Questions or proposes structure:

```text
The emotional reversal is unearned.

Motif X disappears for four chapters.

There is no beat connecting suspicion to betrayal.

This tension resolves before it intensifies.

Percept A might echo more strongly in the final scene.
```

The co-architect is more novel because it works over relations rather than sentences.

But it is also more dangerous. Narrative critique can easily become generic writing-advice sludge.

It should therefore come after the graph has enough explicit semantics to support grounded critique.

First:

```text
human structures
agent writes
```

Later:

```text
agent analyses structure
human accepts or rejects proposals
```

# The essence

Chiasm says:

> This sentence came from this part of this image.

Atlas adds:

> These percepts stand in this narrative relationship.

Codex adds:

> That relationship becomes a sustained long-form work across chapters.

Anuraṇana adds:

> The work is shaped by what this author repeatedly notices and values.

Together:

```text
Seen evidence
      ↓
named attention
      ↓
arranged relation
      ↓
generated or human prose
      ↓
long-form narrative
      ↓
traceable back to perception
```

That is the real idea.

Not a visual outline attached to a word processor.

A narrative architecture where **perception remains inside structure, structure remains inside prose, and prose can always answer for where it came from.**