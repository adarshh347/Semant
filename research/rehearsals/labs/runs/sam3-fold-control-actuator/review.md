# Review — `sam3-fold-control-actuator`

*Fold control — through the production actuator · mode `actuator_direct` · locked to `concept_segment` · expected `positive`*

> The same image and the same phrase as `sam3-fold-control-organ`, executed through the real Director runner instead of straight into the organ. Nothing else differs, which is what makes the pair an instrument: any gap between the two runs is the `concept_segment` WRAPPER — image plumbing, region conversion, the two-status descriptors, the epistemic guard, the provenance stamp — and cannot be anything else.
This is the arm that would have caught the `architectural_axis` class of bug, where a producer ships, the mark never renders, and nothing fails loudly in between.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `drapery fold` |
| phrase actually used | `drapery fold` |
| phrase source | control |
| planner | — (not_applicable) |
| image | `research/rehearsals/fixtures/002F-pieta-single-object/pieta-in-situ.jpg` |

## What the harness measured

| | |
|---|---|
| availability | available |
| device / model | mps / facebook/sam3 |
| invocations | 1 of budget 1 |
| lock held | yes |
| cold / warm | cold |
| latency | 1.37e+04 ms (load 2.3 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| conversion | 0 instance(s) → 0 measured + 0 interpretive descriptor(s), 0 naming withheld, 0 dropped |
| two-status preserved | — |
| invariants held | yes |

## Attribution

**empty_ambiguous_pending_review** — the organ measured no instance of 'drapery fold'. Whether that is true absence or a missed detection is a review question, not a measured one

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] Did every instance the organ measured survive into a proposed region?
      > 
- [ ] Is each extent `measured` and each naming `interpretive`, as two separate descriptors?
      > 
- [ ] Was any naming withheld below the 0.50 floor — and did its extent still come through?
      > 

```text
concept_binding :          # correct | partial | misbound | ambiguous | absent
coverage        :          # all_instances | some_instances | none | not_applicable
boundary_quality:          # clean | loose | wrong
false_positives :
false_negatives :
empty_means     :          # true_absence | missed_detection | undetermined
reviewer        :
reviewed_at     :
notes           :
```

When filled in, copy these into `score.json` under `review`, set `review.status` to `complete`, and set `verdict.semantic_correctness` to `established_by_review` or `refuted_by_review`. The harness will never write those fields itself.
