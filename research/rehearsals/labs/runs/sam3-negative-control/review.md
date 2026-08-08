# Review — `sam3-negative-control`

*A concept that is not there · mode `organ_direct` · locked to `concept_segment` · expected `negative`*

> The control whose PASS is an empty result. SAM 3 will return a confident, well-formed mask for very nearly any phrase — the SF-004-R2 spike watched it mask the background of a painting for `shoulder fabric` at 0.27–0.43 — so the interesting question is not whether it finds things but whether it declines to. If this run comes back with instances, every positive run in the matrix is weakened, because the organ is answering the prompt rather than the picture.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `bicycle` |
| phrase actually used | `bicycle` |
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
| latency | 1.396e+04 ms (load 2.1 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| invariants held | yes |

## Attribution

**negative_control_empty_as_expected** — 'bicycle' is not in this picture and the organ returned nothing, which is the pass condition for a negative control

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] There is no bicycle in this photograph. Did the organ return nothing?
      > 
- [ ] If it returned something, what did it mask — and what does that say about every positive run?
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
