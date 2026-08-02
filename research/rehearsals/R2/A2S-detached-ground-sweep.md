# A2S — Detached-ground corpus sweep

**Read-only.** No post was modified, and the detached grounds found here were deliberately **not
repaired**. Follow-up to run `003-sensory-disagreement` (A2), testing whether its detached-evidence
finding is a one-post accident or a corpus-level property.

Script: `scripts/detached_ground_sweep.py` · Evidence: `evidence/A2S-detached-ground-sweep.json`
No model calls.

---

## Definition used (ported from the authority, not invented)

`frontend/src/differential/grounds.js :: resolveGround` is the authority. It has **three** cases,
and A2 only exercised the first:

1. **`region` ground** — detached ⟺ its `region_id` no longer resolves against the post's regions.
2. **composite** (`constellation` / `relation`) — detached ⟺ it has `member_ids`, **no** member
   survives, **and** it carries no raw `points`.
3. **`field` / `path` / `boundary` / `frame`** — **never** detached; they carry their own geometry.

Case 3 is the load-bearing one. Treating those as detachable would have inflated every count.

## Results

| | count |
|---|---|
| posts scanned | 127 |
| posts with any grounds or percepts | **11** |
| posts with ≥1 detached ground | **2** |
| posts with a *harmed percept* | **1** |
| grounds total | 26 |
| — reference-based (`region`) | 11 · **4 detached (36.4 %)** |
| — composite | 0 · 0 detached |
| — geometry-bearing | 15 · **0 detached** |
| percepts total | 7 |
| percepts citing ≥1 ground | 7 |
| percepts with detached evidence | **1** |
| percepts **fully unevidenced** | **1** |
| detached grounds not cited by any percept | **2** |

### The two affected posts

**`695be786a9ea58f1b6aef5ed`** — A2's post. Current regions are `refine_c6485b9a94` + `arch_0…5`.

- `gnd_mrqp8tls_0` → missing `fine_3` — **cited**
- `gnd_mrqp8tlt_1` → missing `fine_0` — **cited**
- Percept `pctx_mrqp950d_0` ("the upper head") is **fully unevidenced**, 2/2 detached.
- Surviving on the same post: `frame`, `frame`, `field`.

**`695be794a9ea58f1b6aef5f1`** — **new, independent, and the reason this sweep mattered.** Current
regions: `['seg_0']` only.

- `gnd_mrphxkl1_0` → missing `fine_3` — not cited
- `gnd_mrpi0b4o_2` → missing `fine_8` — not cited
- `gnd_mrpi0b4n_1` → `seg_0` — resolves.
- Surviving: `frame`, `frame`.

## Interpretation: **a recurring data-integrity issue**, with the sample caveat stated

spark-03 is **not isolated to A2**. The same signature — reference grounds pointing at a vanished
`fine_*` region set, on a post whose regions are now a different generation — appears on a second,
independent post. Two of the six posts that have any reference-based grounds are affected.

The distinction that matters:

- **The mechanism is reproducible.** It has now been observed twice, on unrelated posts.
- **The harm is currently rare.** Only one percept has actually lost its evidence, and only because
  `695be794`'s stranded grounds happen not to be cited by any percept. That is luck, not design —
  nothing prevented those grounds from being cited.

**The clean contrast holds corpus-wide:** 4 of 11 reference-based grounds are detached; **0 of 15
geometry-bearing grounds are**. Every `field` and `frame` in the corpus survived; over a third of
the region-adapter grounds did not.

### Why this is not yet "corpus-level" in the strong sense

The corpus is small where it counts: **11 annotated posts, 7 percepts, 11 reference grounds**. A
36.4 % detachment rate over 11 items has a wide confidence interval, and 116 of 127 posts carry no
annotation at all. So:

- **Not** inconclusive — the mechanism is confirmed on an independent post, which is what the sweep
  was asked to determine.
- **Not** established as a *rate* — with n = 11 the percentage should not be quoted as a corpus
  property. It says "this happens repeatedly", not "this happens 36 % of the time".

The honest verdict: **recurring, confirmed, and currently low-harm — and the low harm is
incidental.** As percept density grows against a corpus that gets re-dissected, the number of
harmed percepts should be expected to rise, because nothing links the two events.

## Repair is NOT designed here

Per the gate, no repair is proposed. Recording only what a future candidate would have to settle:

- Detachment is already *modelled* (`resolveGround` returns `detached`) and already *rendered*
  ("detached evidence" in inspectors). The gap is that nothing **announces** it at the moment it
  happens, and nothing accumulates it.
- Whether old regions should persist as tombstones so grounds resolve to *something*, versus
  notifying and letting the curator re-point, is an open design question with real trade-offs.
- Whether `field`-style geometry-bearing grounds should be preferred over the region adapter is a
  separate question this sweep does **not** answer — the region adapter's reference semantics
  ("geometry stays on the Region") are deliberate, and durability is only one axis.

None of this is a candidate. It stays SPARK.

## Method notes

- The sweep initially reported only percept-cited detachments, which **hid post `695be794`
  entirely**. Corrected to report uncited detached grounds too, since they evidence the mechanism
  even where no curator statement has been harmed yet. Without that fix this report would have
  concluded "isolated to A2" — the wrong answer.
- `resolve_ground` is a port of JS logic, so it is unit-tested (4 tests) rather than trusted:
  region detachment, geometry-bearing immunity, the composite three-part condition, and purity.
