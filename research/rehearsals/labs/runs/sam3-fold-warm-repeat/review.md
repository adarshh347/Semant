# Review — `sam3-fold-warm-repeat`

*Warm, repeated — is the organ deterministic? · mode `organ_direct` · locked to `concept_segment` · expected `positive`*

> The same frozen call issued three times against a resident model. Two things come out of it and they are separate: a WARM latency to set beside the cold receipt in `sam3-fold-control-organ`, and an answer to whether identical input yields identical masks.
The second matters more than it looks. Every comparison in this lab — control against orchestrated, organ against actuator — assumes that a difference between two runs means something. If the organ is not deterministic on repeated identical input, that assumption is false and every attribution in the matrix needs an error bar it does not currently have.
A repeat is not a retry. The call is byte-identical, no planner runs, and each repeat gets its own budget-of-one firewall, so nothing here can search for a better result.


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
| latency | 1.407e+04 ms (load 2.2 ms) |
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

- [ ] Were the mask hashes identical across all three runs?
      > 
- [ ] If not, how far apart were the instance counts — and does any comparison in this lab survive that?
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
