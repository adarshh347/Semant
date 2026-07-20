Here’s the whole Darshan track map in one clean frame.

**Important distinction:** most of this is **architecture locked / planned**, not app code shipped yet. Track A and E are now settled as docs/decisions; B/C/D/F are the next build/research directions.

## The big architecture

Darshan is becoming:

```txt
image / reel
→ regions / parts
→ felt reading
→ taste graph
→ grounded writing
→ creator + audience + brand intelligence
```

The new core object is:

```txt
Region
= one meaningful visual part or signal
```

Everything will hang from that: detection, comments, Aletheia readings, embeddings, story links, creator notes, audience taps.

---

## Track E — Purpose / niche / positioning

**Job:** decide what this product is actually for.

**Locked direction:** fashion first, architecture second, photography as fallback. The wedge is not “AI image tagging”; it is **part-by-part felt close-reading that becomes taste-language and grounded writing**.

**New thing it creates:** the product spine:

```txt
Articulate → Accumulate → Generate
```

Meaning:

```txt
Articulate why an image works
Accumulate that into taste memory
Generate writing from that taste
```

**Demo target:** one fashion image → garment parts → Aletheia reading → taste signal → Sutradhar lookbook paragraph.

---

## Strategy v2 — Two-sided taste-and-story layer

**Job:** expand the project from only creator-tool to creator + audience + brand platform.

**Locked direction:** creator-first, audience-ready, brand-monetized. Darshan becomes “a level up from social media”: a taste-and-story layer over fashion/entertainment culture.

**New architecture implied:**

```txt
Audience signals
Creator annotations
Brand queries
        ↓
Taste-and-story graph
```

So later the system can know not just:

```txt
user liked image
```

but:

```txt
user keeps responding to soft drape, severe tailoring, warm light, ritual poses
```

---

## Track A — Data model / Region spine

**Job:** define the shared data contract.

**Locked decision:** everything becomes one `Region`. Old `bounding_box_tags` gets retired; `region_annotations` becomes the single region model.

**Final Region architecture:**

```txt
Region
- id
- actor: auto | creator | audience
- detector: yolo | fashionpedia | sam2 | vision
- category
- part
- label
- attributes[]
- box / polygon
- material
- user_note
- prioritised
- weight
- embedding_id
- block_id
```

**New things this enables:**

```txt
manual marks + auto detections use one schema
creator annotations and audience taps can share one shape
regions can link to story blocks
regions can point to FashionCLIP embeddings
future vector search can be added without changing posts
```

This is the foundation. B/C/D/F are now unblocked because they all know what a “visual part” is.

---

## Track B — Segmentation intelligence

**Job:** give Darshan better eyes.

Today:

```txt
YOLO = coarse COCO objects
LLM = guesses finer meaning
```

Future:

```txt
YOLO11n-seg       → cheap coarse anchors
Fashionpedia      → garment parts + attributes
DeepFashion2      → possible alternative fashion segmenter
SAM2              → arbitrary masks: drape, texture, light zones, later video
FashionCLIP       → labels + embeddings
Vision-LLM        → reading, not geometry
```

**New architecture to implement:**

```txt
image
→ YOLO coarse pass
→ Fashionpedia/DeepFashion2 fashion parts
→ SAM2 arbitrary aesthetic zones
→ FashionCLIP vectors
→ Region objects
```

Track B’s key responsibility is to stop the LLM from guessing boxes. CV models locate parts; the LLM interprets them.

---

## Track C — Aletheia / native context intelligence

**Job:** make Aletheia the brain, not just a generic “interpretation panel.”

Current problem:

```txt
fixed generic lenses:
phenomenological / semiotic / atmospheric
```

Future:

```txt
image-specific lenses selected from:
domain + detected parts + mood + user history
```

For fashion, lenses might become:

```txt
silhouette
drape
material tension
styling logic
era/reference
mood/story
body posture
```

**New architecture to implement:**

```txt
Region data
+ user notes
+ Aletheia readings
+ FashionCLIP embeddings
+ past taste history
        ↓
context/RAG layer
        ↓
inline Sutradhar writing
```

So `/draft`, `/continue`, `/rewrite`, `/part`, `/lens` should not write from a blank prompt. They should write from this image’s regions and the user’s taste graph.

Track C is the load-bearing differentiator.

---

## Track D — Unified Visual annotation UX

**Job:** make the Visual pane the premium interaction surface.

Current problem:

```txt
BoundingBoxEditor = manual boxes
Unconceal / RegionDetectorModal = auto anatomy regions
```

Future:

```txt
one Visual pane
one region layer
manual + auto regions together
pick → comment → remember
```

**New UX architecture:**

```txt
Visual pane
├── image
├── region overlays
├── parts list
├── category filters
├── selected region detail
├── comment box
└── Aletheia hints/readings
```

**Main interaction loop:**

```txt
pick a part
→ comment how it affects you
→ save it
→ region becomes part of taste memory
```

This is the creator-side deep interaction. Later, Track F can strip this down into a consumer version: tap → choose reason → taste signal.

---

## Track F — Consumer / audience layer

**Job:** design the B2C side.

Not heavy annotation. Lightweight taste capture.

Future consumer signals:

```txt
pause
tap region
zoom
replay
save with reason
choose one-tap fork
read deeper
```

**New architecture implied:**

```txt
audience action
→ actor: audience Region/signal
→ taste graph
→ better readings/recommendations/creator-brand intelligence
```

Track F owns the endpoint and UX problems:

```txt
auth
rate limits
abuse
privacy
consumer interaction design
video/reel signals
```

Video/reel is later, not MVP.

---

## Model integration stack

The new concrete model architecture is:

```txt
Geometry:
YOLO + Fashionpedia/DeepFashion2 + SAM2

Vectors:
FashionCLIP

Meaning:
Vision-LLM / Aletheia

Writing:
Sutradhar slash AI

Memory:
Region model + region_embeddings sidecar + taste graph
```

Clean division:

```txt
CV sees where things are.
FashionCLIP makes them searchable.
Aletheia explains why they matter.
Sutradhar writes from that context.
```

---

## What will actually be implemented architecturally

The new implementation work will likely be:

```txt
1. Region schema implementation
   Retire bounding_box_tags, normalize all regions, add actor/part/attributes/embedding_id/block_id.

2. Embedding sidecar
   Create region_embeddings collection keyed by embedding_id.

3. FashionCLIP endpoint
   Generate vectors and semantic labels for regions.

4. Segmentation service upgrade
   Keep YOLO, add Fashionpedia/DeepFashion2 evaluation, add SAM2 later.

5. Aletheia context engine
   Replace fixed generic lenses with domain-triggered lenses and structured evidence.

6. RAG/context injection into Sutradhar
   Inline writing AI uses regions, notes, readings, and taste history.

7. Unified Visual pane
   One surface for manual/auto regions, filters, focus, comments, remembered state.

8. Consumer Track F later
   Audience taps/saves/replays become taste graph signals.
```

## Shortest summary

```txt
Track E tells why.
Track A defines the shared Region spine.
Track B gives better eyes.
Track C gives interpretation and memory.
Track D gives the creator interaction surface.
Track F gives the audience/taste-signal surface.
```

The whole new architecture is:

**a region-based taste graph where image parts, human reactions, AI readings, embeddings, and generated writing all connect.**