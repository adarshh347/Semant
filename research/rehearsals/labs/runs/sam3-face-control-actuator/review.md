# Review — `sam3-face-control-actuator`

*Face, through the production actuator — the two statuses on real data · mode `actuator_direct` · locked to `concept_segment` · expected `positive`*

> `sam3-fold-control-actuator` was meant to exercise the wrapper, and it cannot: the organ returns nothing for `drapery fold` on this image, so there is no conversion to observe. An empty result tests the empty path and nothing else, and a matrix whose only actuator run is empty would let a wrapper bug sit undetected behind an honest zero.
`face` returns three instances at naming confidences 0.81, 0.47 and 0.35 — which is the single most useful thing in this matrix, because it straddles the 0.50 naming floor. It should produce three MEASURED extents and one INTERPRETIVE naming, with two namings withheld and their extents still standing. That is SF-004-R §5.3 executed on real pixels rather than asserted on fakes: the measurement does not become false because the word attached to it is doubtful.
Paired with `sam3-face-control`, which is the same image and phrase straight into the organ. Any difference between the two is the wrapper.


## What was asked

| | |
|---|---|
| prompt | — |
| control phrase | `face` |
| phrase actually used | `face` |
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
| latency | 1.356e+04 ms (load 2 ms) |
| organ status | **ok** |
| instances | 3 |
| mask areas (px) | 338, 172, 302 |
| max pairwise IoU | 0.539 |
| all masks well-formed | yes |
| conversion | 3 instance(s) → 3 measured + 1 interpretive descriptor(s), 2 naming withheld, 0 dropped |
| two-status preserved | yes |
| invariants held | yes |

## Attribution

**organ_succeeded** — the organ measured 3 instance(s) of 'face'. Whether those instances ARE that concept is not established here

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

![overlay](overlay.png)

![contact sheet](contact-sheet.png)

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] Did all three extents survive into proposed regions, with the same masks the organ measured?
      > 
- [ ] Did exactly one naming clear the 0.50 floor, and did the other two extents still come through?
      > 
- [ ] Is each extent `measured` and each surviving naming `interpretive` — two separate claims?
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
