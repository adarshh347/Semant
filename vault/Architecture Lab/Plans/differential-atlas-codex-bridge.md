# The bridge: Differential → Atlas / Codex (conceptual layer only)

**Mode:** concept. No architecture, no build plan. Updates `narrative-atlas-vision` + `atlas-codex-build-plan` for the post-Differential reality (Grounds, Constellations, Relations, recall now exist). The question: which Differential objects become durable narrative objects, what crosses, what stays local.

## The one principle

**The image boundary is the cut, and the Percept is the only object that crosses it.**

Grounds are indexical — a stroke set, a polygon, a band along a transition mean nothing away from the pixels they occupy. A Percept is the first object with propositional content: "the pale dress opens the garden's density" survives being carried into a chapter or a map, even diminished. So Atlas and Codex never hold Grounds; they hold Percept references, and everything visual they need arrives either *through* the reference (recall, on demand) or as a disposable projection (a crop, glyphs). This keeps one perceptual identity per noticing — the Codex "no duplicate annotation" property and the Atlas "same rhythm across five works" property both fall out of it.

## Three classes of information

**Crosses (the Percept's identity card):** percept id · expression · optional properties (light, colour, movement…) · ground-type signature (the glyph row — *that* it was a boundary-noticing matters structurally; *where* the boundary runs does not) · image identity · provenance (creator, date). This is small, stable, and citable.

**Stays local (the evidence body):** all geometry — strokes, points, polygons, band widths, member coordinates; recall timelines and animation mechanics; region taxonomy (category, material, anatomy, detector); Aletheia lens internals; every piece of pane state (selection, hover, active verb). None of this is narrative material; all of it is reachable in one hop when a citation is opened.

**Projected (regenerable cache, never authoritative):** the crop URL (Cloudinary bbox-union of the percept's grounds), a static "still" of the recall final state, the glyph row rendered. Atlas and Codex may cache these freely because they can always be regenerated from the source — they are pictures *of* the evidence, not the evidence.

## Constellation and Relation: the operators cross, the records don't

This is the subtle one. An intra-image Constellation ("these five red echoes in this painting") is a Ground — evidence, local, cited only through a Percept like any other Ground. Do **not** promote it into Atlas.

But Atlas's whole purpose is the same two gestures one level up: *collect* and *connect* — over **Percepts across images** instead of Grounds within one. So the bridge is a symmetry, not a transfer:

```
Differential:  Collect Grounds  → Constellation (a Ground)      · Connect Grounds  → Relation (a Ground)
Atlas:         Collect Percepts → Motif (an Atlas node)          · Connect Percepts → typed Atlas edge
```

A Motif ("this dissolving-figure rhythm, across five works") is a **new object owned by Atlas**, whose members are percept ids — it reuses the existing Atlas node vocabulary (it *is* the `motif` node, now given real membership). An Atlas edge between two percept nodes ("this Monet percept `contrasts_with` that Sargent treatment") is likewise Atlas-owned. Neither reaches back into geometry; both resolve to images only at recall time. The user-facing continuity is that Collect and Connect feel like the same acts in both places — same verbs, lifted one level.

Borderline case — a "deeper Percept" composed from other Percepts: if its sources live in **one image**, it stays a Percept (image-local, grounds resolvable). If its sources span **images**, it is an Atlas object — a Motif that carries its own expression. The image boundary decides, mechanically.

## Recall crosses as a capability, not as data

Atlas and Codex store nothing about how a Percept animates. A citation anywhere resolves: percept → its image → its grounds → the recall engine, live. The cached still is the fallback (reduced motion, image unavailable, dense map views). If recall behavior ever changes, every citation everywhere improves — because none of them froze it.

## Codex needs no new bridge object at all

A chapter citing a Percept is just a Mention with page scope (the `page_id` already planned). The Codex-level view — "this percept recurs in chapters 2, 5, 9" — is a **query over Mentions, not a stored object**. Resist the urge to materialize a recurrence record; the join already carries it.

## The stability contract (what "durable" costs)

The first time a Percept is cited outside its own image — Atlas node, Motif membership, or a Mention in another Work — it hardens: this is the trigger (already anticipated in the earlier studies) to promote Percept to a real backend entity. From then on: **expression edits propagate** to every citation (one identity is the feature — "the sentence can change while the Percept remains stable" cuts both ways); **deleting a cited Percept tombstones**, never cascades (the Mention/node degrades to a marked ghost, the map is not silently rewritten); **editing or deleting Grounds under a cited Percept** degrades recall to whatever evidence remains (the "detached evidence" state Differential already defines) without touching the Percept's identity or its citations.

## Boundary summary

| Object | Crosses? | As what |
|---|---|---|
| Percept | **yes — the only one** | reference (id + identity card) |
| Ground (all seven types) | no | reachable through its Percept |
| Constellation / Relation (intra-image) | no | Grounds like any other |
| Motif / Atlas edge (cross-image) | born on the far side | Atlas-owned, members = percept ids |
| Recall | as capability | resolved live at the image; still as fallback |
| Crop / glyphs / stills | as projection | regenerable cache, never authoritative |
| Codex recurrence | no object | query over Mentions |

## Deliberately not decided here (the next 80%)

Atlas layout/persistence, the agent verbs over percept nodes, Motif membership UX, Percept-entity schema and migration, versioning of expressions, cross-corpus similarity for suggested Motif members. All of it sits comfortably on the boundary above; none of it moves the boundary.
