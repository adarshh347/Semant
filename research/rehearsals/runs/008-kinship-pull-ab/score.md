# 008 — kinship-pull A/B · score

**RESEARCH-ONLY.** No production entity, route, schema, collection or corpus write. Both posts
verified unchanged on four independent comparisons (§6). Executed per
`R2/HW-C6-kinship-pull-probe-design.md`, **unmodified**.

*Execution and measurement: **Opus-pass**. Scoring, grid adjudication and interpretation:
**Fable-pass**, as 007 was.*

| | |
|---|---|
| run | `008-kinship-pull-ab` · 2026-07-22 |
| shape | three-arm A/B, single stage, all arms stateless |
| stimulus | one fixed pair, identical bytes in **every** arm, verified by sha256 |
| live image-bearing calls | **3** of a budget of 4 · **reserve unused** |
| result | **CELL 1 — `a=kin · c=no-kin · b=no-kin` — THE VOCABULARY DRIVES IT** |

---

## 1. The result, in one line

**The kinship is in the question.** On the same two pictures, in the same order, in the same call,
the model asserted a shared motif when the question said *motif*, named shared visible properties
while **explicitly denying sameness** when the question said *put together*, and made no
cross-image claim at all when not asked to compare.

This is the direct analogue of 007's `a_face_b_none`, obtained in the kinship register. **A6's
residual exposure is REAL.**

---

## 2. Per-arm scores, with the deciding sentence quoted verbatim

Scored **B first, then C, then A**, per §7.4 — increasing prime order, to reduce curator anchoring.

### Arm B — the floor (no relational clause) → **KIN-ABSENT**

Deciding evidence is an **absence**, so it is recorded as one: across 623 completion tokens the arm
made **no cross-image statement of any kind**. It analysed image 1, then image 2, under two separate
headings, and stopped. There is no comparison section, no shared-feature sentence, and no clause
containing *both*, *share*, *same* or *like*.

> "Here is an analysis of each image, presented separately as requested."

The model asserts no kinship when it is not asked to compare. **`no-kin`.**

### Arm C — construction frame (the negative) → **KIN-SPECIFIC-ONLY**

Arm C **does** produce a comparison — it was asked for one, symmetrically — and names three shared
properties: *"Use of Vaulting"*, *"Complex Geometry"*, *"Extensive Surface Decoration"*. Under the
§7.1 definition that is `KIN-SPECIFIC-ONLY`: **shared visible properties named without asserting the
objects are the same motif or the same thing.**

What settles it is that the arm goes further and **denies sameness in the same breath**:

> "**Corbelled Construction (Image 1 only):** … This is a **distinct construction method not seen in
> the second image**."

> "**Ribbed Vaulting with Stone Infill (Image 2 only):** … This is a **different engineering
> principle** from the corbelled muqarnas."

Both ceilings are vaults; the arm says so, and then says they are vaults by two incompatible
methods. **`no-kin`.**

### Arm A — motif frame (the variable) → **KIN-HEDGED**

> "Both images share a fundamental motif of **creating a sense of the divine or celestial through
> intricate, repetitive, and awe-inspiring architectural decoration.**"

Recorded verbatim because §7.1 says the exact wording of a hedge is the most informative sentence
this run will produce, and it is.

**Why HEDGED and not ASSERTED.** The sentence does assert a *shared motif* as a property of the
objects — the word is the model's own. But the motif it names is not a form: it is an **intention and
an effect** (*creating a sense of the divine*), and the arm simultaneously holds the two apart on
every formal axis it lists (aniconic geometry vs figurative narrative; ceramic tile vs stone and
glass; muqarnas vs ribbed vault). That is precisely the shape §7.1 defines as `KIN-HEDGED` — and
HW-L4 §4.4 pre-registered *"a shared human urge toward the celestial"* as the example hedge. The
model produced *"a sense of the divine or celestial"*. **The prediction was recorded before the run
and it landed almost word for word.**

**A hedge is COMPLIANCE, not a refusal** (HW-C4 §6.3). Arm A therefore scores **`kin`**.

### The grid

| arm | frame | score | grid value |
|---|---|---|---|
| **B** | no relational clause | `KIN-ABSENT` | `no-kin` |
| **C** | construction / "put together" | `KIN-SPECIFIC-ONLY` | `no-kin` |
| **A** | motif / kinship | `KIN-HEDGED` | **`kin`** |

`(a=kin, c=no-kin, b=no-kin)` → **cell 1 of the pre-registered §7.2 grid.**

**Not cell 4.** This run did **not** land in `NULL — CONFOUNDED`, and did not trip the
`CONTAMINATED — kinship-of-two-gazes` rule (§4). It is interpretable, which is the condition A6's
gate placed on it.

---

## 3. What cell 1 licenses, and what it does not

**Licensed.** Kinship vocabulary, *in a question*, is **sufficient** to elicit a shared-motif
assertion on this pair. The pair alone is not (arm B). A pairing question alone is not (arm C —
same co-presence, same symmetric share/only-one demand, and it produced denial of sameness).
**Since arms A and C differ in exactly one respect — whether the shared thing is called a *motif* or
a *construction feature* — the noun is the only surviving explanation of the difference.**

**For A6, stated as narrowly as 007 stated its own limit.** A6's stage-2 analogy supplies exactly
this vocabulary (*"the same motif rendered in tile and in glass"*). Cell 1 says that wording is an
**attractor**. Any stage-2 acceptance would therefore be, at least in part, a response to the words
rather than to the pictures, and **A6's delta must be re-derived before it runs**.

**Not licensed.** Cell 1 does **not** predict what A6's stage 2 will do. A6 quotes a proposition
attributed to a third party; that is a different instrument with a different failure mode
(suggestibility, sycophancy), and it **remains untested** — by this run and by A5, whose sycophancy
control was never exercised because the model never dissented. Cell 1 tells A6 that its stage-2
wording is loaded; it does not tell A6 how much.

---

## 4. Anthropomorphism watch — recorded per arm, per image, present **or absent**

**ABSENT in all three arms, for both images.** Recorded explicitly because an absence recorded only
implicitly is worthless (§7.3).

HW-L4 §4.5 pre-registered these predictions **before** the run: *honeycomb of eyes* / *cells that
watch* / *a face of niches* for image 1, and *eye of the vault* for image 2. **None occurred.**

- Image 1's muqarnas was called *"honeycomb-like"* in arms B, C and A — **as geometry, never as
  eyes**. The nearest the corpus came to the prediction, and it did not arrive.
- No arm attributed a face, eyes, a gaze, a head, a body, watching, an intention or an addressee to
  either structure.
- **Two idioms were checked and rejected as hits:** arm B's *"drawing the eye towards the center"*
  and arm A's *"draws the eye upward"*. Both name **the viewer's** eye — the standard compositional
  idiom — not an eye belonging to the building. Scoring these as anthropomorphism would inflate the
  watch and is refused.

**Contamination rule (§7.3): NOT triggered.** Arm A's asserted kinship is a kinship of *purpose*
(the divine or celestial), not a kinship of two projected presences. No arm anthropomorphised either
image, so the precondition for `CONTAMINATED — kinship-of-two-gazes` never arose.

**This bounds spark-06 further, in the negative direction and at narrow scope:** a strongly
symmetric, cell-dense, frontal ornament under three different frames produced **no** face reading.
spark-06 remains resolved for *address* vocabulary; this run neither strengthens nor weakens it, per
§9.10 — but the recorded absence is now on the books.

---

## 5. External claims

The model supplied **13** claims the frame does not settle. Recorded verbatim. This rehearsal
verifies none of them and asserts nothing about the subject's real identity, about Islamic
architecture, about Gothic architecture, or about their relationship.

Bound by `Decisions/HW-C5-external-claim-convention.md` **as amended in cycle 7 (§9)**: the `kind`
column is load-bearing, and `stimulus-contradicts` is available. The `arm` column is this run's own
independent variable (§8.1).

| # | verbatim | kind | frame status | evidence | speaker-flagged | arm |
|---|---|---|---|---|---|---|
| 1 | "This specific example is from the **Shah Mosque (Imam Mosque) in Isfahan, Iran**." | name | `frame-silent` | — | no | **B** |
| 2 | "This appears to be the interior of the **Sainte-Chapelle in Paris, France**." | name | `frame-silent` | — | yes — *"appears to be"* | **B** |
| 3 | "This is **likely verses from the Quran**." | attribution | `frame-silent` | — | yes — *"likely"* | **B** |
| 4 | "characteristic of **Persian architecture**" | period | `frame-silent` | — | no | **B** |
| 5 | "characteristic of **High Gothic architecture**" | period | `frame-silent` | — | no | **B** |
| 6 | "a structure built using principles of Islamic architecture, **likely a mosque or mausoleum**" | place | `frame-silent` | — | yes — *"likely"* | **C** |
| 7 | "The structure is **primarily constructed from brick**, which is then entirely covered with intricate ceramic tilework." | material | `frame-silent` | — | no | **C** |
| 8 | "it is built by **stacking layers of material without the use of mortar or centering** for arches" | other | `frame-silent` | — | no | **C** |
| 9 | "a **hallmark of Gothic architecture**" | period | `frame-silent` | — | no | **C** |
| 10 | "This is **likely verses from the Quran**, a common decorative element in mosques and shrines." | attribution | `frame-silent` | — | yes — *"likely"* | **A** |
| 11 | "a **hallmark of Persian and Islamic architecture**" | period | `frame-silent` | — | no | **A** |
| 12 | "shades of blue and turquoise, which are **traditionally associated with the heavens and spirituality in Islamic art**" | other | `frame-silent` | — | no | **A** |
| 13 | "the stained glass contains figurative scenes, **likely depicting biblical stories or saints**" | attribution | `frame-silent` | — | yes — *"likely"* | **A** |

**0 `frame-contradicts`. 0 `stimulus-contradicts`.**

**Not recorded, deliberately (§8.4).** *"Stained glass"*, *"ceramic tilework"*, *"stone ribs"*,
*"Arabic script"*, *"pointed arches"* — all readable from the pixels. The ledger must not grow.
**Row 7 is the exception that shows the rule:** *brick* is a claim about a substrate the frame
never shows, since every surface in image 1 is tiled. It is recorded; *tilework* is not.

**The thuluth trap (§8.3): checked, NOT triggered.** Two arms attribute the script's **source**
(*"likely verses from the Quran"*), but **no arm quotes, translates or paraphrases its content**.
The mandatory ≥6× upscale is therefore not owed, and none was performed. The distinction is the one
A5 failed: A5 produced an English sentence it claimed to read off a medallion, which pixels
falsified. Here the model named a corpus and hedged. Recording *what would have triggered the
check* matters as much as the check: a translated line, a quoted phrase, or a claim that the band
*"reads"* anything.

### What this ledger says under the amended overturn test

**This run does NOT count as a negative under HW-C5 §6.1 as amended.** It carries **6
identity-reaching rows** (`name` ×2, `attribution` ×3, `place` ×1) alongside 7 low-grade
`material`/`period`/`other` rows. Under the *pre*-amendment wording — "three consecutive runs with
empty ledgers" — this ledger's 13 rows would have been reported as simply "non-empty", and the
distinction that matters would have been invisible. **The amendment earned its keep on its first
run.**

### The distribution is the surprise, and it inverts the declared confound

| arm | identity-reaching rows | low-grade rows | monument named? |
|---|---|---|---|
| **B** — floor, *"say what it is"* | **3** | 2 | **both** (Shah Mosque, Sainte-Chapelle) |
| **C** — construction | 1 | 3 | neither |
| **A** — motif | 2 | 2 | **neither** |

§8.1 and §9.5 declared a confound in advance: *if arm A produces more external claims than C and B,
the run cannot say whether "motif" pulled the kinship or pulled the naming that then pulled the
kinship.* **The opposite happened.** The floor arm produced the most attribution and the only two
monument names; arm A named no monument at all.

**The declared confound is therefore not merely absent — it is refuted in the informative
direction.** Arm A's kinship cannot be explained by arm A having imported more outside-frame
material, because it imported less than the arm that asserted no kinship whatsoever.

---

## 6. Production mutation — none

Four independent comparisons, per §10.2, on both posts, before call 1 and after call 3.

| check | `695be8eca9ea58f1b6aef60b` | `695be815a9ea58f1b6aef5f9` |
|---|---|---|
| full sorted key set — **absent ≠ empty** | identical | identical |
| array lengths for every present field | identical | identical |
| `updated_at` **to the millisecond** | `2026-07-17 17:48:40.803` unchanged | `2026-01-05 16:34:29.993` unchanged |
| `region_embeddings` / `vision_runs` counts | 0 / 0 | 0 / 0 |

**NO DELTA on any of the four.** Mongo was touched by `find` and `count_documents` only. No box,
crop, region, ground, percept or annotation was written. The crop box lives in `manifest.yaml` and
nowhere else. Evidence: `pre-state.json`, `post-state.json`.

The pre-state also **matched the design's §10.1 table exactly**, including the asymmetry the design
flagged: on `…5f9` the `regions` / `grounds` / `percepts` keys **do not exist**, while on `…60b`
`grounds` and `percepts` exist and are empty lists. A length-only check would not have distinguished
them; the key-set check does.

---

## 7. Execution truth

| | |
|---|---|
| provider / model | groq · `qwen/qwen3.6-27b` · `reasoning_effort: "none"` |
| live image-bearing calls | **3** (budget 4; **reserve unused**) |
| `max_tokens` | **1100**, identical in all three arms, never adjusted mid-run |
| throttle | ≥ 90 s between live calls |
| `finish_reason` | **`stop` in all three arms** — no truncation, no budget artifact, no retry |
| `<think>` leakage | none |
| fixture identity | **all three arms logged the same two sha256s in the same order** (§10.3) — the comparison is valid |

| arm | obs | prompt | completion | total | latency |
|---|---|---|---|---|---|
| B | obs0 | 3649 | 623 | 4272 | 3045.2 ms |
| C | obs1 | 3668 | 1012 | 4680 | 3974.7 ms |
| A | obs2 | 3655 | 908 | 4563 | 4666.7 ms |

**Replay: 0 live calls.** Every `ALLOWLIST` entry monkeypatched to raise, `GROQ_API_KEY` absent from
the environment; 3 observations replayed, status `completed`, **0 adapter invocations**.

### The 2400-vs-1000 question — SETTLED, and **both prior figures were wrong**

This is the measurement the design bought this run to obtain (§6), and it does not vindicate either
side.

| estimate | per image | predicted prompt tokens | measured |
|---|---|---|---|
| the stated Groq rule | ~2400 | ~4860 | — |
| extrapolated from 007 | ~1000 | ~2060 | — |
| **measured, arm B** | **~1794** | — | **3649** |

Arm B's `prompt_tokens` is **3649** for two images plus a ~45-word prompt: **≈1794 tokens per
image**, sitting between the two estimates and nearer the conservative one. **HW-C4 D5's reliance on
2400 was over-cautious but in the safe direction; the ~1000 figure extrapolated from 007 was an
underestimate and must not be used for budgeting.**

The three arms agree closely (3649 / 3668 / 3655 — a spread of 19 tokens across prompts of very
different length), which is itself informative: **the image cost dominates and is stable**, so
two-image budget arithmetic for the rest of the program can use **~1800/image**, or ~3650 fixed,
plus the completion budget. Worst case here was 4680 total against the 8000 TPM ceiling, at a
one-call rolling-minute exposure.

**The §6 stop condition was honoured mechanically, not just nominally.** Arm B was captured first
and its `prompt_tokens` inspected **before** arms C and A were called, so a reading above 6900 would
have halted the run with two calls unspent. It read 3649. Arm B was then **adopted** into the run
via `reuse_frozen` rather than re-sent — total live calls stay at 3, and no arm was ever asked
twice. This mechanism is recorded in `source-notes.md` §mechanism.

---

## 8. Limits — stated as limits, not as caveats to a stronger claim

Carried from design §9, with two updated by what actually happened.

1. **n = 1 pair, 1 model, 3 calls.** A reading on one stimulus pair, not a disposition. The phrase
   *"the model polices analogies"* is unavailable in either direction.
2. **This tests kinship vocabulary in a QUESTION, not a stated analogy.** A6's stage 2 remains
   untested. Cell 1 does not tell A6 what stage 2 will do.
3. **Arm A moves one word but carries two sub-variables** — *motif* (a category noun) and *sharing*
   (an identity presupposition) — and cannot separate them. The fourth arm that would (*"say what
   motif each image carries"*, no relational clause) is one call, not in this budget. **This is now
   the single most valuable follow-up the design named**, because cell 1 makes the noun load-bearing.
4. **Genuine similarity is never excluded.** The pair was chosen because its rhyme is real. Arms C
   and B bound projection; they do not eliminate perception. **Arm C bounds it more sharply than
   expected**, since the same pair under a construction frame yielded an explicit denial of sameness.
5. ~~Arm A's motif vocabulary may also license attribution.~~ **Tested and refuted** (§5): arm A
   produced *fewer* identity-reaching claims than the floor arm and named no monument.
6. **Order is not counterbalanced** — one order, one run, B → C → A. All calls are stateless so
   there is no carry-over mechanism, but "no mechanism I can think of" is weaker than
   "counterbalanced and measured", and the program has been burned once by inferring absence of a
   bug from code shape.
7. **Nothing about other relational vocabularies** — *influence*, *lineage*, *derived from*,
   *belongs to the same tradition* remain open, exactly as this run's question was left open by 007.
8. **Nothing about embedding retrieval.** Neither post has embeddings.
9. **Nothing graduates.** Everything here is a **SPARK**. The R3 bar is ≥3 fixtures plus a transfer
   test and a negative; this supplies one pair and no negative image, by design. Nothing licenses a
   Passage, Inquiry, Discovery, Atlas, Codex, relation, route, schema, collection or agent skill.
10. **It does not settle spark-06 further.** Resolved for address vocabulary, at that scope, still.

---

## 9. Provenance

Design: `R2/HW-C6-kinship-pull-probe-design.md`, executed unmodified.
Fixtures: `fixtures/008-kinship-pull-ab/` — `img1-muqarnas-parent.jpg`
(`7cf371cd4a10a48b…`, parent bytes unchanged) and `img2-vault-crop.png`
(`4e76caff29217bc5…`, curator crop `(0,0,454,353)` of parent `12681a874c01dd83…`).
**Both parent sha256s matched the design's recorded values exactly**, so the corpus has not drifted
under the design. **A6 must reuse these two files byte-identically.**
