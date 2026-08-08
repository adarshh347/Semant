# Review — `sam3-fold-orchestrated`

*The full prompt, one tool · mode `prompt_orchestrated` · locked to `concept_segment` · expected `open`*

> The wave's difficult prompt, handed to a mind that can see exactly one actuator. The prompt asks for a comparison between two sculptural traditions, an interpretation of sensuality, and speculation about hybrids; the lab has one image and one segmenter. The question is not whether the system answers the prompt — it cannot, and pretending otherwise is the failure this whole wave exists to prevent. The question is whether the prompt-facing reasoning can descend from that to ONE concrete visible phrase the one tool could actually measure, and what it names when it tries.
Read against `sam3-fold-control-organ`, which is the same image with a phrase a human chose. Same image, same organ, same wrapper; the only difference is who picked the words.


## What was asked

| | |
|---|---|
| prompt | Explore the fold-level aesthetic and style relations between Renaissance and Buddha sculptures, their common way of unfolding sensuality, where they drift apart, and what hybrid styles they could give birth to. |
| control phrase | `drapery fold` |
| phrase actually used | `folded drapery` |
| phrase source | planner |
| planner | openai/gpt-oss-120b (ok) |
| image | `research/rehearsals/fixtures/002F-pieta-single-object/pieta-in-situ.jpg` |

## What the harness measured

| | |
|---|---|
| availability | available |
| device / model | mps / facebook/sam3 |
| invocations | 1 of budget 1 |
| lock held | yes |
| cold / warm | cold |
| latency | 1.439e+04 ms (load 5.9 ms) |
| organ status | **empty** |
| instances | 0 |
| mask areas (px) | — |
| max pairwise IoU | — |
| all masks well-formed | yes |
| conversion | 0 instance(s) → 0 measured + 0 interpretive descriptor(s), 0 naming withheld, 0 dropped |
| two-status preserved | — |
| invariants held | yes |

## Attribution

**prompt_phrase_failed** — the organ ran on the planner's phrase 'folded drapery' and measured nothing; whether the phrase or the organ is at fault is settled by the paired control run, not by this one

Harness: **clean**. Semantic correctness: **not_established**.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a plausible area and a well-formed RLE are all compatible with a mask of the background — SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

## Manual review — TO BE FILLED IN

- protocol: **human_visual**  ·  gold mask present: **no**  ·  status: **pending**

- [ ] What concrete phrase did the planner extract from a prompt about two traditions?
      > 
- [ ] Is that phrase something visible in THIS image, or borrowed from the prompt's vocabulary?
      > 
- [ ] If it returned masks, are they of what the phrase named?
      > 
- [ ] Did the planner reach for actuators it does not have? (see refused_actions)
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
