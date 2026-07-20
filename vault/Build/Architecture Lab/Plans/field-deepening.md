# The Deep Field — a layered workbench for seeing (research + plan)

Source: `vault/prompts/f1- prompt.md` §3 + the current Field screenshot + code. **This is research/plan first, then a phased build.** Field = the visual pane of Chiasm (image + regions + reading), per the locked lexicon.

## The problem
Today the Field is a hand-rolled zoomable `<img>` + SVG polygons. Two failures: (1) **the whole image doesn't show** — it fills width and crops a tall image; (2) it's **"just an image with boxes"** — primitive. Adarsh wants a *Photoshop-level* workbench in **capability**, but with **Semant's intentions** — not pixel-editing, not aesthetics-for-its-own-sake, but the *possibilities to play with the image* in service of seeing/reading/taste.

## The reframe (the key idea)
Photoshop's power = **layers + tools + non-destructive play**. The Field keeps that *structure* but swaps the *intention*: its layers are **layers of seeing**, not layers of pixels. You never retouch the image — you **accrue interpretation over it, in composable layers.** That single distinction is the whole design: Photoshop changes the picture; the Field changes your *understanding* of it, reversibly, in stackable layers.

## Fix first: the image itself
Adopt **OpenSeadragon** as the viewer substrate (deep-zoom, pan, fullscreen, whole-image fit; overlays via SVG/Fabric that pan+zoom *with* the image and stay pixel-aligned at any zoom — which also fixes the polygon-alignment class of bugs). Default = **fit whole image** (letterbox), with **deep zoom to inspect craft** (every stitch, stone, stitch-line) + a `fit / 1:1 / fill` control. This alone answers "the whole image is not coming."

## The layer model (layers of seeing — a real layer panel)
Each is a toggleable, opacity-adjustable overlay on the deep-zoom image:
1. **Image** — the base, deep-zoomable.
2. **Regions / parts** — the segmentation polygons + the maps (quiet/outline/focus), filterable by category. (Today's RegionSurface becomes one layer.)
3. **Reading (Aletheia)** — lenses tied to regions; a lens highlights its part; felt-notes float by their region.
4. **Taste (Anuraṇana)** — resonant regions from *your* corpus surfaced at the margin: "this emerald cluster rhymes with X you saved." Resurfacing, made spatial — the "third thing" living inside the Field.
5. **Marks** — your freehand marks, stars, felt-relations.
6. **Composition / light (later)** — depth, light zones, colour fields; the non-object aspects (atmosphere is image-global, per Track B).
A **layer panel** (Photoshop-familiar, but the layers are ways of seeing) toggles/weights them. That is the "layer stack that emerges."

## The tools (possibilities to play — Semant-oriented)
- **Deep zoom + pan + loupe** — inspect texture and craft; a magnifier under the cursor.
- **Isolate a region** — pull one part out to dwell on it (same mechanic as the B2C "cropped-section taste").
- **Compare** — hold two parts side by side (this drape vs that; this stone vs that).
- **Overlay similar (taste)** — bring resonant regions from your corpus into the margin (resurfacing in the Field).
- **Pull to Manuscript** — drag a region/reading into the writer (extends the existing `/part` wire into a spatial gesture).
- **Re-read** — trigger Aletheia on a selected part.
- **Felt-relation** — draw a saved connection between two parts ("this colour answers that").
- **Freehand mark** — mark a spot no detector found.

## The non-destructive principle
Nothing edits pixels. Every tool produces an *interpretation layer* (a region, a reading, a mark, a relation) that is saved, reversible, and composable. That is what makes it Semant and not Photoshop — and it maps cleanly onto the existing `Region` model + `origin`/`actor` provenance.

## Phasing (build after the design round)
1. **Viewer swap + full-fit + deep zoom** (OpenSeadragon; port the existing polygon/maps overlay onto it). Kills "image not coming."
2. **Layer panel** (toggle/weight: regions / reading / marks).
3. **Play tools** (loupe, isolate, compare).
4. **Taste layer** (overlay similar from `region_embeddings` — coordinate with the vision thread) + pull-to-Manuscript gesture + felt-relations.

## Open questions for Adarsh
- OpenSeadragon (mature, deep-zoom, IIIF-ready) vs a canvas engine (Konva/Fabric alone)? OSD is the safer deep-zoom substrate; recommend it.
- Do we need real tiled/DZI images for deep zoom, or is single-image OSD enough at current resolutions? (Single-image is enough now; tiling later if images get huge.)
- How loud should the taste layer be by default — a quiet margin, or on-demand?

## Coordination
Field = the Chiasm visual pane. Touches the Field component (not the Manuscript, not the gallery). The taste-layer's "similar regions" needs the vision thread's embeddings/projection. Otherwise self-contained.

Refs: OpenSeadragon (deep-zoom + overlays), Annotorious (annotation on OSD).
