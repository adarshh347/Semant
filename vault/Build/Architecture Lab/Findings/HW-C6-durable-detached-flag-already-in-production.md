# HW-C6 — The durable `detached` flag is already in production

**READ-ONLY finding. No production data was written, and nothing was cleaned up.** Discovered while
verifying the one open check Lane 1 flagged; not covered by any other cycle-6 lane.

---

## What was found

Lane 1's revised evidence-identity decision noted that `geometry_recovery.py:187` writes a durable
`g["detached"] = True`, that `scripts/vision_f3_recover_one.py` persists, and that HW-C4 §4b had
**rejected** that shape — concluding it was "one manual invocation from production."

**It is not one invocation away. It has already happened.**

| post | ground | `region_id` | stored `detached` | `detached_reason` |
|---|---|---|---|---|
| `695be786a9ea58f1b6aef5ed` | `gnd_mrqp8tls_0` | `fine_3` | `true` | "region evidence absent after recovery" |
| `695be786a9ea58f1b6aef5ed` | `gnd_mrqp8tlt_1` | `fine_0` | `true` | "region evidence absent after recovery" |
| `695be794a9ea58f1b6aef5f1` | `gnd_mrphxkl1_0` | `fine_3` | `true` | "region evidence absent after recovery" |
| `695be794a9ea58f1b6aef5f1` | `gnd_mrpi0b4o_2` | `fine_8` | `true` | "region evidence absent after recovery" |

**4 of 26 grounds corpus-wide** carry it — exactly the four known detached grounds. No ground
carries `superseded`, `stale`, `recovered`, or `geometry_recovered`. The `detached_reason` string
identifies the writer: the F-series geometry recovery work, not a curator.

## It is read by nothing

`resolveGround` (`grounds.js:72`) computes detachment **fresh** from region presence —
`detached: !region`. It never consults the stored field. Every consumer goes through it:
`recall.js:117`, `grounds.js:125`, `DifferentialWorkspace.jsx:438`.

So the stored flag is **inert**: present in the data, absent from behaviour.

`vision_recovery.py:82-84` already treats it as machine annotation, stripping `detached` and
`detached_reason` before comparison so that "marking a Ground detached does not read as a curator
data change." The codebase understood the distinction; the flag simply outlived the work that wrote
it.

## Why this matters

**1. HW-C4 §4b rejected a shape that was already in the data.** The decision was taken against a
fact nobody had checked. That does not make the reasoning wrong — a *behavioural* stored flag is
still the thing to avoid — but the decision should not be read as having kept the data clean. It
did not.

**2. The reattachment hazard has a second victim.** Today stored and computed **agree** on all four.
They diverge the moment a re-dissect regenerates a colliding positional ordinal:

| | computed by `resolveGround` | stored field |
|---|---|---|
| after ordinal collision | `false` — looks healthy | `true` — stale, now **wrong** |
| read by | everything | nothing |

So the collision would produce **two** failures, not one: the computed state silently wrong (Cycle
5's finding), *and* a durable marker silently stale. Neither surfaces anywhere.

**3. It slightly strengthens Lane 1's Option D.** Detecting substitution at the dissect merge
boundary is the only proposed option that would notice either failure, because it compares masks
rather than trusting an id or a flag.

## What was deliberately NOT done

- **Nothing was cleaned up.** The four flags remain exactly as found. Removing them would be a
  production write, and they are currently harmless and accurate.
- No claim that writing them was wrong. They were written by a recovery pass that had reason to.
- No recommendation to start reading the stored field — that would convert an inert annotation into
  behaviour, which is precisely what HW-C4 §4b argued against and HW-C6 upholds.

## Open question for a later cycle

If the merge-boundary detector is ever built, does it **clear** a stale `detached` flag when it
observes substitution, or leave it? Clearing it is a production write on curator-adjacent data;
leaving it means the corpus accumulates annotations that were true once. Not decided here.
