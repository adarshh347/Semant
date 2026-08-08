# Review — `sam3-fold-synonym-architecture`

*Fold synonym — folding architecture · mode `organ_direct` · locked to `concept_segment` · expected `open`*

> The third fold phrase, and the one that should behave differently. `folding architecture` uses the same root word but names a different KIND of thing, and this image contains real architecture — the apse, the cross, the plinth — behind the cloth. If the organ binds on the word `folding` and masks the drapery anyway, that is a measurable case of the phrase's head noun being ignored; if it masks the apse, that is the phrase working and the concept being absent. Both are findings, and they are not the same finding.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `folding architecture` |
| phrase actually used | `folding architecture` |
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
| latency | 1.401e+04 ms (load 2.2 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**empty_ambiguous_pending_review** — the organ measured no instance of 'folding architecture'. Whether that is true absence or a missed detection is a review question, not a measured one

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] Did it mask cloth (binding on `folding`) or built structure (binding on `architecture`)?
      > 
- [ ] If it returned nothing, is that the honest answer for this picture?
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
