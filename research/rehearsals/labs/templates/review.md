# Review — `<run_id>`

*Generated per run by `scripts/single_actuator_lab.py capture`. This file is the template it
follows; the real ones live in `runs/<run_id>/review.md`.*

The judgement slots below are **empty on purpose**. Pre-filling them from the automated signals
and inviting a reviewer to correct what already looks decided is how a confidence score becomes
a correctness claim by social pressure rather than by anyone deciding it should.

---

## What was asked

| | |
|---|---|
| prompt | |
| control phrase | |
| phrase actually used | |
| phrase source | control / planner / deterministic_framer |
| planner | model (status) |
| image | |

### Refused, and recorded rather than filtered

*Every actuator the planner reached for and did not get. An empty section here on an
orchestrated run is itself a result: the mind stayed inside its hands.*

### Parameters dropped

*Where a planner trying to author geometry, a region id or a confidence would show up. It shows
up nowhere else.*

## What the harness measured

| | |
|---|---|
| availability | available / weights_absent / runtime_absent |
| device / model | |
| invocations | n of budget 1 |
| lock held | |
| cold / warm | |
| latency | ms (load ms) |
| organ status | **ok / empty / unavailable / error** |
| instances | |
| mask areas (px) | |
| max pairwise IoU | |
| all masks well-formed | |
| conversion | n instance(s) → n measured + n interpretive descriptor(s), n naming withheld, n dropped |
| two-status preserved | |
| invariants held | |

## Attribution

**\<attribution\>** — which layer produced this outcome.

Harness: **clean / violated**. Semantic correctness: **not_established** until filled in below.

> Nothing above establishes that a mask is of the thing the words named. A confidence, a
> plausible area and a well-formed RLE are all compatible with a mask of the background —
> SF-004-R2 measured exactly that. That question is settled below, by a person, or not at all.

![overlay](overlay.png)
![contact sheet](contact-sheet.png)

## Manual review — TO BE FILLED IN

- protocol: **human_visual / gold_mask / none_required** · gold mask present: **no** · status: **pending**

- [ ] Did the mask land on the thing the phrase named?
      >
- [ ] Were ALL visible instances found, or only some?
      >
- [ ] Is the boundary clean, loose, or simply wrong?
      >
- [ ] If the result was empty: is the concept truly absent, or was it missed?
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

When filled in, copy these into `score.json` under `review`, set `review.status` to `complete`,
and set `verdict.semantic_correctness` to `established_by_review` or `refuted_by_review`. The
harness will never write those fields itself.
