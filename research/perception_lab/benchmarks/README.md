# PERCEPTUAL-FORMS-001F — the form benchmark

The evaluation corpus and scoring system for the nineteen registered perceptual forms. Lane C's
model laboratory says in its own manifest that *"the Lane F corpus of real works is the actual test
and does not exist yet"* — this is that corpus, plus the thing a corpus is useless without: a way of
scoring answers that does not quietly decide what the question was.

**Implements no models and no production UI.** Nothing here is wired to a route, an operation, a
registry entry or a database; the tests assert that by reading the scripts' import graph.

```
python scripts/perception_lab_form_benchmark.py verify      # every check, one exit code
python scripts/perception_lab_form_benchmark.py report      # coverage and contract gaps
python -m pytest backend/tests/test_perception_lab_form_benchmark.py
```

## What is here

| path | what it is |
| --- | --- |
| `../form_atlas/atlas.json` | six real works and four adversarial controls, resolved to accession numbers, with rights recorded rather than assumed |
| `../form_atlas/RIGHTS.md` | the licensing findings and the four unresolved questions |
| `controls/manifest.json` | twelve synthetic controls whose truth is known **by construction** |
| `schemas/form-annotation.schema.json` | what a person records when they annotate |
| `annotations/*.json` | four worked annotations, including two annotators who disagree |
| `matrix.json` | one row per form: image, control, question, action, metric, failures, screenshot |
| `../../../scripts/perception_lab_form_scoring.py` | the metric families |
| `../../../scripts/perception_lab_form_benchmark.py` | controls, matrix, validation, CLI |

## The five rules the scorer enforces structurally

1. **A refusal is not a zero.** `Score` carries a value *or* a stated reason and never both or
   neither, and `aggregate()` reports `coverage` beside `mean`. A zero means the producer answered
   and was wrong; a refusal means nobody has been measured. Averaging them gives a third number
   true of neither.
2. **No forced collapse.** Where an annotation declares several legitimate readings,
   `hypothesis_coverage` scores against the set and names what was missed. Matching is
   **best-first**, so the order the annotator listed them in cannot change the score.
3. **Visible and inferred are never pooled.** `partition_accuracy` returns a per-part result with
   *no mean*, and says why in the payload. A generous amodal producer scores well on one and badly
   on the other, and one number hides exactly that trade.
4. **A field is not a mask.** `contour_agreement` refuses without a declared threshold;
   `field_calibration` scores reliability over bins, which is a different claim from `field_l1`.
5. **Direction is part of an edge.** Undirected edges are normalised by endpoint order and directed
   ones are not, so reversing a containment is a wrong edge rather than a right one drawn backwards.

## The controls

Twelve scenes, drawn by placing pixels, so a donut has one hole because a hole was punched in it.
The suite then asserts that Lane B's `extent_forms` substrate **independently agrees** with the
construction — deriving the truth *from* the substrate would have made that check vacuous.

Previews are ASCII on purpose: a text preview shows a shape change as moved characters in a diff,
and a PNG shows a binary blob and a new digest.

| control | forms | the trap it catches |
| --- | --- | --- |
| `solid-mask` | hard_mask, boundary_rings, hole_set | reporting a void where a rectangle was drawn |
| `donut` | hole_set, boundary_rings | drawing the inner ring like the outer one |
| `nested-holes` | hole_set, hierarchy | flattening a void-in-island-in-void into two holes on one piece |
| `disconnected-fragments` | fragment_set | assuming 8-connected foreground and reporting four pieces where there are five |
| `false-similarity` | fragment_set, fused_hypothesis | grouping on appearance, which gives one group of three |
| `soft-fringe` | soft_field, density_field, negative_space | returning model confidence in place of fractional coverage |
| `partition` | visible_inferred_partition | putting off-frame pixels in `inferred` because there is no `unknown` bin |
| `density-peaks` | density_field | smoothing the stray away and calling the count right |
| `containment-tree` | hierarchy, containment_tree | forcing a single root, which invents a container |
| `adjacency-graph` | adjacency_graph, pair_relation, contact_locus, intersection_area, clearance_path | rendering examined-and-unrelated as blank space |
| `one-pixel-transition` | transition | detecting the null perturbation, which moved more pixels than the real change |
| `competing-extents` | hypothesis_set, fused_hypothesis, uncertain_relation_set | collapsing to one answer, which scores the benchmark's tie-break |

**The connectivity pairing is borrowed, not chosen.** `extent_forms.raster` pairs foreground
4-connected with background 8-connected; every count here is under that pairing, and
`disconnected-fragments` exists specifically to catch a producer that assumed the other one.

**A hole count needs a convention beside it.** `holes` here means *enclosed voids only*; the
substrate counts the unbounded exterior as a complement component. Both numbers are recorded per
control, so neither reading is a guess.

## The annotation schema

**There is no `ground_truth` field and no `correct_mask` field, and the absence is the design.**
Asked to outline "the figure", a person may lawfully return the body alone or the body with the
shadow it casts. A schema with one correct-answer slot forces the annotator to choose and forces
the scorer to mark the rest wrong — which measures the tie-break.

So the shape is `legitimate_readings`: a list, each with **a required reason**, and a
`single_correct_answer` flag the validator refuses to leave `true` when there is more than one
reading. Ambiguity is recorded as itself (`edge_not_in_picture`, `runs_off_frame`,
`shadow_or_reflection`, …) rather than as noise, annotator `expertise` is recorded because it
predicts systematic disagreement, and `disagrees_with` makes a contradiction evidence instead of
variance.

The four worked annotations include a **pair on one picture** — a trained annotator who excludes a
cast shadow and a naive one who includes it, each recording the other's reading as legitimate. The
suite asserts the scorer never reads `preferred_by_annotator` as truth.

## Contract gaps this lane found

`report` prints these. **Ten metrics the benchmark needs are not in the contract's
`comparison_methods` closed set**, each declared in `EXTENSIONS` with the reason it could not be
expressed as one of the ten — for example `hole_count_error` (a count, not an overlap:
`set_overlap` would score a producer that found the right number of wrong holes as perfect), and
`hypothesis_coverage` (coverage over a set with no correct answer to compare against). Each is a
candidate Lane A ticket rather than private vocabulary.

The report also names, per form, where the matrix reaches for a metric the form does not declare
and where a form declares one the matrix does not use. Both directions are findings.
