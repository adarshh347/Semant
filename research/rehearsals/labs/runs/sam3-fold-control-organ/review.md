# Review — `sam3-fold-control-organ`

*Fold control — the organ alone · mode `organ_direct` · locked to `concept_segment` · expected `positive`*

> The paired control for the orchestrated run. One image, one explicit phrase a human chose, the organ called directly with no Director step and no suggestion conversion in the way. Whatever comes back is SAM 3's answer and nothing else's — which is the only thing that lets a later failure be attributed to the phrase or to the wrapper rather than to the model.


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
| latency | 1.436e+04 ms (load 3.3 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**empty_ambiguous_pending_review** — the organ measured no instance of 'drapery fold'. Whether that is true absence or a missed detection is a review question, not a measured one

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] Do the returned masks sit on actual drapery folds of the Pietà, or on the marble as a whole?
      > 
- [ ] Did it find the deep folds over the knees, or only the most contrasted edge?
      > 
- [ ] Is anything masked that is not cloth at all — the apse, the cross, the plinth?
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
