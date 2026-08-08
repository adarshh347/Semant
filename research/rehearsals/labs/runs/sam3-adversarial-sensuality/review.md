# Review — `sam3-adversarial-sensuality`

*An abstract noun, handed to a segmenter · mode `organ_direct` · locked to `concept_segment` · expected `adversarial`*

> `sensuality` is a word from the wave's prompt and it names nothing a segmentation model can find. This run exists to see WHAT HAPPENS ANYWAY, because the failure mode that matters is not refusal — it is a confident, well-formed mask of something, which is exactly what the SF-004-R2 spike watched happen on a painting for `shoulder fabric`.
Whatever it returns, this run establishes NOTHING about the image. It is not a positive control with a hard phrase; it is a probe of the organ's willingness to answer an unanswerable question, and it is marked `adversarial` so no reader can mistake a returned mask for a finding about sensuality.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `sensuality` |
| phrase actually used | `sensuality` |
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
| latency | 1.403e+04 ms (load 2.5 ms) |
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

- [ ] Did it refuse (empty), or did it mask something?
      > 
- [ ] If it masked something, WHAT — and at what naming confidence?
      > 
- [ ] Would that mask have survived the 0.50 naming floor and reached a curator as a reading?
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
