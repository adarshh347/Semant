# Review — `sam3-fold-phrase-matrix/angel_of_grief/organ_direct__folded-drapery`

*angel_of_grief · 'folded drapery' · organ_direct · mode `organ_direct` · locked to `concept_segment` · expected `open`*

> Matrix cell from the pre-registered suite 'sam3-fold-phrase-matrix': family 'fold_target' (role 'fold_target') against fixture 'angel_of_grief'. The phrase was frozen before any live call in this lane and may not be changed now.

## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `folded drapery` |
| phrase actually used | `folded drapery` |
| phrase source | control |
| planner | — (not_applicable) |
| image | `research/rehearsals/fixtures/006-narrative-overreach/angel-of-grief-rotunda.jpg` |

## What the harness measured

| | |
|---|---|
| availability | available |
| device / model | mps / facebook/sam3 |
| invocations | 1 of budget 1 |
| lock held | yes |
| cold / warm | warm |
| latency | 5925 ms (load 0 ms) |
| organ status | **ok** |
| instances | 1 |
| mask areas (px) | 26786 |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**organ_succeeded** — the organ measured 1 instance(s) of 'folded drapery'. Whether those instances ARE that concept is not established here

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

![overlay](overlay.png)

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
