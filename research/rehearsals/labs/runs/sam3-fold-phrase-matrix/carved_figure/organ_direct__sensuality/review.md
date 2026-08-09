# Review — `sam3-fold-phrase-matrix/carved_figure/organ_direct__sensuality`

*carved_figure · 'sensuality' · organ_direct · mode `organ_direct` · locked to `concept_segment` · expected `adversarial`*

> Matrix cell from the pre-registered suite 'sam3-fold-phrase-matrix': family 'adversarial_abstraction' (role 'adversarial_abstraction') against fixture 'carved_figure'. The phrase was frozen before any live call in this lane and may not be changed now.

## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `sensuality` |
| phrase actually used | `sensuality` |
| phrase source | control |
| planner | — (not_applicable) |
| image | `research/rehearsals/fixtures/003-sensory-disagreement/carved-figure-close.jpg` |

## What the harness measured

| | |
|---|---|
| availability | available |
| device / model | mps / facebook/sam3 |
| invocations | 1 of budget 1 |
| lock held | yes |
| cold / warm | warm |
| latency | 5464 ms (load 0 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**empty_ambiguous_pending_review** — the organ measured no instance of 'sensuality'. Whether that is true absence or a missed detection is a review question, not a measured one

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] For each non-empty fold-target mask: is it LOCAL FOLD GEOMETRY, or the garment as a whole?
      > 
- [ ] Where the object_scope family succeeded and fold_target failed on the same fixture, does the overlay show folds that were there to be found?
      > 
- [ ] Does `face` land on faces on every fixture — i.e. is the availability gate honest?
      > 
- [ ] On the Angel of Grief versus the Pietà: does the untreated image behave differently from the texture-blended one for the SAME phrase?
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
