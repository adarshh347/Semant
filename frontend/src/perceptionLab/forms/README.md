# PERCEPTUAL-FORMS-001E — the form renderer laboratory

Fixture-first renderers for the nineteen canonical Extent and Topology forms. This is the visible
painting layer for manual inspection. **It makes and alters no canonical evidence**, and it cannot:
nothing under this directory imports a client, calls `fetch`, or touches storage, and
`toolRegistry.test.js` asserts that over the module graph as text.

## What Lane H has to do

```jsx
import FormRendererLab from '@/perceptionLab/forms';

<Route path="/lab/forms" element={<FormRendererLab />} />
```

There is no client prop. `FormRendererLab` accepts four optional props, all of them for a route
that wants to put its state in the URL or drive a screenshot:

| prop | default | what it is for |
| --- | --- | --- |
| `initialForm` | `extent.hard_mask` | one of the nineteen form keys |
| `initialView` | the form's default | a view key from `viewsFor(form)` |
| `initialScenario` | `contract` | one of `contract` · `resolvable` · `empty` · `dense` · `withheld` |
| `now` | `null` | the timestamp proposals carry. The clock is never read, so a screenshot taken twice is the same screenshot |
| `onProposal` | `null` | called with each frozen proposal, if the route wants to collect them |

`FormHarness` is the same laboratory at 1100 / 720 / 430 / 320 in one page, with no props needed.
Mount it behind a lab route if the responsive behaviour is worth having on hand.

Everything else the route might want — `renderView`, `viewsFor`, `COVERAGE`, `verifyRegistry`,
`layer`, `assertLayer` — is exported from `./index.js`, with a note there on why.

**`verifyRegistry()` runs at import and throws.** If Lane H's integration suite wants the failure
to name itself rather than surfacing at a random import, call it directly.

## The five ideas, in the order they matter

1. **A layer is a drawing plus its declaration**, and `assertLayer` throws. A renderer that does
   not say where a drawing came from cannot render at all. The declaration carries the source form
   and record, the evidence class, the coordinate system, the basis, the hypothesis, the partition
   part and the threshold.
2. **Four evidence classes, three redundant channels.** `measured` · `derived` · `inferred` ·
   `hypothetical` differ in stroke dash AND fill pattern AND printed word before colour is
   considered. Colour does one job here: telling sibling layers apart.
3. **No view decides its own evidence class.** `shared.evidenceFor` reads it off the record's
   partition, the projection's declared mode and the partition part. The same contact band comes
   out dashed under `topology.pair_relation` (all five of whose projections are `derived`) and
   solid under `topology.contact_locus` (which carries the mask).
4. **A diagram is not a stage.** `FormStage` refuses a `diagram` layer and `FormDiagram` refuses
   everything else. Both report the refusal on screen rather than skipping silently.
5. **Absence is a finding.** No renderer returns a bare `.map()`; `orEmpty` fetches the counter the
   form declares and the `empty_means` sentence the contract already wrote.

## Screenshots

Eleven captures — every plate below is a claim in this README made visible, both themes, plus the
four-width responsive proof:

**https://claude.ai/code/artifact/8551b80c-c2d8-4966-bd71-ac45bd08581a**

They are not committed. Nothing in the test suite reads them, and a binary that nothing reads does
not belong in the repo. To regenerate: mount `FormHarness` (or `FormRendererLab` with
`initialForm` / `initialView` / `initialScenario`) behind a temporary Vite entry, and drive the
cases in `harnessCases.js` — each one carries a `why` that is its caption.

## Rendered-form coverage

Nineteen of nineteen forms, forty-four views. Every projection each form declares is drawn by some
view, and no view draws a projection its form does not declare — both directions are asserted at
import by `verifyRegistry` and again in `rendererRegistry.test.js`.

| form | state | views | declared projections |
| --- | --- | --- | --- |
| `extent.hard_mask` | enabled | `fill` (stage), `outline` (stage), `focus` (stage), `box` (stage), `points` (stage), `contact_sheet` (sheet), `before_after` (compare), `ab_overlay` (stage), `difference` (panel) | mask_fill, mask_outline, box_outline, point_markers, contact_sheet, before_after, ab_overlay, difference_overlay |
| `extent.boundary_rings` | experimental | `rings` (stage), `winding` (stage), `edit` (stage), `as_outline` (stage) | ring_outline, mask_outline |
| `extent.hole_set` | experimental | `hatch` (stage), `void_focus` (stage), `parent_context` (stage) | hole_fill, mask_outline |
| `extent.soft_field` | deferred | `wash` (stage), `isolines` (stage), `threshold` (stage) | scalar_wash, density_contours |
| `extent.fragment_set` | experimental | `islands` (stage), `component_focus` (stage), `links` (stage) | fragment_cluster, mask_fill |
| `extent.fused_hypothesis` | deferred | `fusion` (stage), `grounds` (panel) | fragment_cluster, hypothesis_stack |
| `extent.visible_inferred_partition` | deferred | `tricolor` (stage), `part_focus` (stage), `coverage` (panel) | partition_tricolor, scalar_wash |
| `extent.hierarchy` | experimental | `tree` (diagram), `nested_focus` (stage) | hierarchy_tree, mask_fill |
| `extent.density_field` | deferred | `wash` (stage), `contours` (stage), `samples` (panel) | density_contours, scalar_wash |
| `extent.hypothesis_set` | deferred | `tabs` (stage), `split` (compare), `layered` (stage), `weights` (panel) | hypothesis_stack, ab_overlay |
| `topology.pair_relation` | enabled | `endpoints` (stage), `contact` (stage), `intersection` (stage), `outlines` (stage), `graph` (diagram), `list` (panel) | endpoint_pair, relation_graph, contact_band, intersection_area, mask_outline |
| `topology.contact_locus` | experimental | `band` (stage), `points` (stage) | contact_band, point_markers |
| `topology.intersection_area` | experimental | `area` (stage), `endpoints` (stage) | intersection_area, mask_fill |
| `topology.clearance_path` | experimental | `path` (stage), `endpoints` (stage) | path_overlay, point_markers |
| `topology.containment_tree` | experimental | `tree` (diagram), `graph` (diagram) | hierarchy_tree, relation_graph |
| `topology.adjacency_graph` | experimental | `graph` (diagram), `matrix` (diagram), `contact` (stage) | relation_graph, contact_band |
| `topology.negative_space_field` | enabled | `wash` (stage), `contours` (stage), `statistics` (panel) | scalar_wash, density_contours |
| `topology.transition` | deferred | `before_after` (compare), `diff` (panel) | transition_diff, before_after |
| `topology.uncertain_relation_set` | deferred | `by_hypothesis` (stage), `layered` (stage), `graph` (diagram), `hypotheses` (panel) | hypothesis_stack, relation_graph |

Surfaces: `stage` (one letterboxed image stage) · `compare` (labelled panes, never superimposed) ·
`sheet` (cropped thumbnails) · `diagram` (node-link or matrix, in diagram space) · `panel`
(measurements that have no shape — not a fallback).

## What the fixtures can and cannot resolve

The nineteen committed payloads carry geometry for **two** collections, and cite a dozen more.
`fixtures/endpointGeometry.js` declares those two once — `art_extent_1` (from `extent.hard_mask`)
and `art_fragments_1` (from `extent.fragment_set`) — and refuses everything else **by name**.

Aliasing `inst_piazza` onto whichever mask is handy would fill every view with shapes, and a
fiction drawn at the exact pixel boundary of a real raster is more convincing than an empty stage
will ever be. So the mix stands: contact locus resolves both ends and draws; intersection resolves
neither and refuses; clearance resolves one of two and says which. The limits are printed in the
record inspector rather than in this file, because a person judging a renderer needs to know
`inst_piazza` is missing *before* they conclude the containment tree is broken.

## Contract gaps found

Three, none of them blocking, all worth a Lane A ticket.

1. **`negative_space_field` has no inline-values escape hatch.** Every other field in the grammar
   is a `ScalarField` with `inline_values`; this variant holds its field behind `field_ref` and
   nowhere else. Its declared `scalar_wash` projection is therefore **undrawable by any runtime
   that cannot fetch that ref**, which includes this one and any browser. The lab renders the
   measured field as absent with that sentence and draws a distance transform it computes itself
   beside it, stamped `derived`. If the intent is that the form be inspectable client-side, the
   variant needs the same escape hatch the others have.

2. **There is no projection kind for "a field cut into an extent".** `extent.soft_field` carries
   `threshold_would_be` and declares only `scalar_wash` and `density_contours`. Drawing the
   thresholded result as `mask_fill` would be drawing a projection the form does not declare, and
   `validateArtifact` fails on exactly that. So the threshold sweep keeps the result as a cell grid
   at full intensity, which is honest — you can see it is still 4×4 — and is not what a producer
   would write. When a producer does implement the threshold, its output is a `hard_mask` artifact,
   which does declare `mask_fill`; the gap is only in the preview.

3. **`topology.adjacency_graph`'s committed payload reports `pairs_examined: 6` for three nodes**,
   which make three unordered pairs. Either the counter is ordered pairs (and the field name
   should say so) or the fixture is off by a factor of two. The lab prints both numbers side by
   side rather than picking one.

Two smaller notes, which are fixture properties rather than contract gaps and are surfaced on
screen: `extent.hard_mask`'s first instance declares a box spanning 0.2–0.8 and carries a mask
occupying 0.125–0.5 — they do not agree, which is why both views exist; and
`topology.contact_locus` records 812 contact pixels on an 8×8 raster that holds 64, so the count
and the mask were measured at different resolutions.

## Tests

487 in this directory, across eight files.

| file | what it holds |
| --- | --- |
| `layerModel.test.js` | the declaration gate, tested by trying to get past it |
| `formGeometry.test.js` | decode, fields, isolines, trees and graphs, against the committed payloads |
| `formFixtureDrift.test.js` | the bundled payloads are the committed payloads; regenerates with `UPDATE_FORM_FIXTURES=1` |
| `rendererRegistry.test.js` | registry ↔ contract agreement, plus every view of every form under every scenario |
| `toolRegistry.test.js` | the tools are the contract's; and no file here can reach a client |
| `formStage.dom.test.jsx` | the declaration reaches the markup — letterbox, dashes, patterns, arrowheads, refusals |
| `formLab.dom.test.jsx` | the laboratory driven the way a person drives it |
| `formResponsive.dom.test.jsx` | four widths, the stylesheet read as text, colour, keyboard |

```
npx vitest run src/perceptionLab/forms
npx eslint src/perceptionLab/forms
```
