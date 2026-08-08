# Review — `sam3-fold-synonym-robe`

*Fold synonym — robe folds · mode `organ_direct` · locked to `concept_segment` · expected `positive`*

> One of three phrases for the same visible thing (`drapery fold`, `robe folds`, `folding architecture`). An open-vocabulary organ is only useful if near-synonyms land near each other; if the three produce wildly different masks of the same cloth, then the phrase is doing far more work than the picture and every fold result in the wave is a result about wording.
Read against `sam3-fold-control-organ` and `sam3-fold-synonym-architecture`.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `robe folds` |
| phrase actually used | `robe folds` |
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
| latency | 1.394e+04 ms (load 2.1 ms) |
| organ status | **ok** |
| instances | 1 |
| mask areas (px) | 8989 |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**organ_succeeded** — the organ measured 1 instance(s) of 'robe folds'. Whether those instances ARE that concept is not established here

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

![overlay](overlay.png)

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] Does this land on the same cloth as `drapery fold`, or somewhere else entirely?
      > 
- [ ] Is the extent the whole robe, or the folds within it? Those are different claims.
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
