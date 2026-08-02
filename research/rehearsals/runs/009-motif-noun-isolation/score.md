# 009 — motif-noun isolation · score

**RESEARCH-ONLY.** No production entity, route, schema, collection or corpus write. Both posts
verified unchanged on four comparisons. The "fourth arm" named in 008's design §9.3 and in
`008/sparks.md` unresolved-question 1.

*Execution and measurement: **Opus-pass**. Scoring and interpretation: **Fable-pass**.*

| | |
|---|---|
| run | `009-motif-noun-isolation` · 2026-07-22 |
| shape | single arm, single stage, stateless · **1 live call** (budget 2, reserve unused) |
| stimulus | 008's frozen pair, **byte-identical** by sha256, same order |
| prompt | 008 arm A **with its final sentence deleted, and nothing else changed** |
| result | **THE PRESUPPOSITION CARRIES IT** — `KIN-ABSENT` |

---

## 1. The result

**Arm D made no cross-image statement of any kind.** Across 519 completion tokens it named a motif
for image 1, named a motif for image 2, and stopped. There is no comparison section, and no sentence
anywhere containing *both*, *share*, *shared*, *same*, *similar*, *common* or *like* applied across
the two images.

> "### Image 1 — **Motif:** The primary motif is **Islamic geometric and calligraphic art** …"
> "### Image 2 — **Motif:** The primary motif is **Gothic architecture** …"

**Score: `KIN-ABSENT`.** Pre-registered cell **`d_names_per_image_motifs_only`**.

**The noun *motif* alone is inert. 008 arm A's kinship came from being asked what the two SHARE.**

---

## 2. The three-arm comparison this run completes

All four observations are on **identical bytes, identical order, identical model, identical
`max_tokens`, all stateless**.

| arm | run | what the question contained | cross-image verdict | score |
|---|---|---|---|---|
| **B** | 008 | no relational clause, no *motif* — *"say what it is"* | none | `KIN-ABSENT` |
| **D** | **009** | ***motif*, no relational clause** | **none** | **`KIN-ABSENT`** |
| **C** | 008 | relational clause, *construction* not *motif* | **denies sameness** | `KIN-SPECIFIC-ONLY` |
| **A** | 008 | ***motif* + relational clause*** | asserts a shared motif | `KIN-HEDGED` |

**Read down the column: only arm A has both, and only arm A produced kinship.** D isolates the noun
and gets nothing. C isolates the relational demand and gets an explicit denial. **Neither ingredient
is sufficient alone. Arm A's kinship required the conjunction.**

### The most informative detail in the run

Arm D wrote, of **image 2 alone**:

> "…creates a luminous, ethereal environment, which was **intended to evoke a sense of the
> divine**."

008 arm A wrote, of **both images together**:

> "Both images share a fundamental motif of **creating a sense of the divine or celestial**…"

**The same phrase, in the same vocabulary, appears in both runs — but in arm D it is a property of
one picture, and in arm A it is the bridge between two.** The raw material was available to the
model either way. What the relational demand supplied was not the *content* of the kinship but the
**move of predicating it jointly**.

*(Fable-pass.)* That is a sharper finding than "the vocabulary drives it". The noun licenses the
**register** — spiritual, atmospheric, purpose-talk. The presupposition licenses the **identity
claim**. 008 could not separate them and said so; separated, they turn out to do different work.

---

## 3. What this does to A6 — cycle 7's re-derivation SURVIVES, with one new residual

**It survives.** Cycle 7 re-derived A6's delta as **(008 arm A → A6 stage 2)**, on the reasoning that
arm A already spends the vocabulary *without* a third party. 009 does not disturb that: arm A
contains *motif* **and** the sameness move, and A6's stage 2 contains both plus the attribution. The
anchor holds, and 009 strengthens the case for using arm A rather than a fresh stage 1 — because a
fresh stage 1 without a relational clause would now be predicted to return `KIN-ABSENT`, which is a
floor, not a baseline.

**The new residual, and it is real.** Arm A **demands** sameness (*"say which features these two
share"*); A6's stage 2 **asserts** it (*"the same motif rendered in tile and in glass"*, attributed
to a third party). A demand invites the model to go find something; an assertion invites it to
agree. **So the delta (arm A → stage 2) still moves two things at once:** demand → assertion, and
no-attribution → attribution.

**The cheapest fix is one more single call — an arm E** that asserts sameness **without** attribution:

> *"These two images share a motif. Say what in the images supports that, and what contradicts it."*

Arm E would sit between arm A and A6's stage 2 and make the attribution device the **only** thing A6
changes. One call, on the same frozen bytes. **This is now the highest-value single call available,
displacing the fourth arm, which this run has spent.**

This is recorded as a recommendation, not a decision. **A6 is not run, and its GO-WITH-CONDITIONS
status is unchanged** — but its checklist should gain arm E, or state explicitly that it accepts a
two-variable delta.

---

## 4. Anthropomorphism watch — ABSENT, for the fourth consecutive arm

Recorded per image, present **or absent**, because an unrecorded absence is worthless.

**Absent for both images.** No face, eyes, gaze, head, body, watching, intention or addressee was
attributed to either structure. HW-L4 §4.5's pre-registered predictions — *honeycomb of eyes*,
*cells that watch*, *a face of niches*, *eye of the vault* — **did not occur**, for the fourth arm
running. Image 1's muqarnas was again called *"honeycomb-like"*, again as geometry.

**One idiom, and it settles itself.** Arm D wrote *"drawing the **viewer's** eye towards the apex"* —
the model named the viewer explicitly. 008 §4 judged the bare form (*"draws the eye upward"*) as not
a hit; here the model removes the ambiguity itself. **That retroactively supports 008's judgement**,
which was the one contestable adjudication in that run.

**Contamination rule: not triggered** (no anthropomorphism, and no asserted sameness at all).

---

## 5. External claims

The model supplied **8** claims the frame does not settle. Recorded verbatim. This rehearsal
verifies none of them and asserts nothing about the subjects' real identity.

Bound by `HW-C5-external-claim-convention.md` **as amended in cycle 7 (§9)**.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "Vertical bands of Arabic script, **likely verses from the Quran**" | attribution | `frame-silent` | — | yes — *"likely"* |
| 2 | "a **hallmark of Islamic architecture**" | period | `frame-silent` | — | no |
| 3 | "characteristic of **Persian and Islamic tilework**" | period | `frame-silent` | — | no |
| 4 | "a **defining feature of Gothic cathedrals**" | period | `frame-silent` | — | no |
| 5 | "The primary motif is **Islamic geometric and calligraphic art**" | period | `frame-silent` | — | no |
| 6 | "The primary motif is **Gothic architecture**" | period | `frame-silent` | — | no |
| 7 | "**intended to evoke a sense of the divine**" | other | `frame-silent` | — | no |
| 8 | "This vertical emphasis … **symbolizing a connection to heaven**" | other | `frame-silent` | — | no |

**0 `frame-contradicts`. 0 `stimulus-contradicts`.**

**Not recorded (§8.4):** *tracery*, *stone ribs*, *stained glass*, *cobalt blue*, *stars, polygons
and interlacing lines* — all readable from the pixels.

**Thuluth trap: checked, NOT triggered.** Row 1 attributes the script's **source** and hedges it; no
arm quotes, translates or paraphrases its content. Per the precedent 008 set explicitly, the ≥6×
upscale is not owed and none was performed.

### Under the amended overturn test

**1 identity-reaching row** (`attribution`, hedged) and **7 low-grade** `period`/`other` rows. The
run therefore does **not** count as a negative under §6.1 as amended — but only just, and the single
identity-reaching row is speaker-flagged.

### This directly replicates 008's question-type finding

008 found identity-reaching claims concentrated in the **floor** arm: *"say what it is"* named
**both monuments** (Shah Mosque, Sainte-Chapelle); the motif and construction arms named **none**.

**009 is a second motif-framed observation on identical bytes, and it named no monument either.**

| arm | question | monuments named | identity-reaching rows |
|---|---|---|---|
| B (008) | "say what it is" | **2** — Shah Mosque, Sainte-Chapelle | 3 |
| A (008) | "what motif" | 0 | 2 |
| **D (009)** | **"what motif"** | **0** | **1** |

Two independent motif-framed calls, on the same pictures, produced zero monument names between
them, while the one "what is it" call produced two. **spark-08 gains a controlled replication**, and
it is the cleanest evidence the program has that *what the model imports tracks what it is asked* —
because here the pictures are held byte-identical.

---

## 6. Production mutation — none

Four comparisons, per 008 §10.2, on both posts, before and after the call.

| check | `695be8eca9ea58f1b6aef60b` | `695be815a9ea58f1b6aef5f9` |
|---|---|---|
| full sorted key set (**absent ≠ empty**) | identical | identical |
| array lengths | identical | identical |
| `updated_at` to the millisecond | `2026-07-17 17:48:40.803` unchanged | `2026-01-05 16:34:29.993` unchanged |
| `region_embeddings` / `vision_runs` | 0 / 0 | 0 / 0 |

`pre-state.json` and `post-state.json` are **byte-identical**, and the pre-state was **byte-identical
to 008's post-state** — so nothing has touched either post across two runs and a commit.

---

## 7. Execution truth

| | |
|---|---|
| provider / model | groq · `qwen/qwen3.6-27b` · `reasoning_effort: "none"` |
| live calls | **1** (budget 2; reserve unused) |
| `max_tokens` | **1100** — identical to all three 008 arms |
| `finish_reason` | **`stop`** — no truncation, no retry |
| prompt / completion / total | **3633** / 519 / 4152 |
| latency | 2413.6 ms |
| fixture identity | sha256 list **equals 008's, in the same order** — comparison valid |
| replay | **0 adapter calls**, `GROQ_API_KEY` absent, 1 observation replayed |

**The ~1800 tokens/image constant holds.** Four two-image calls now measured: **3649 / 3668 / 3655 /
3633**, a spread of **35 tokens** across prompts ranging from ~30 to ~60 words. Image cost dominates
and is stable, exactly as 008 concluded. Budget two-image runs at **~3650 fixed + completion**.

---

## 8. Limits

1. **n = 1 call.** One sample, temperature 0.2, no repetition; within-arm variance unmeasured.
2. **The curator was not blind.** 008's arms were scored before this ran. All calls are stateless so
   the *model* is unaffected, but the reading is not blind and the result was the one I expected.
   Recorded because it is the honest exposure. See `critique.md` §2.
3. **The deletion also halved the noun's frequency.** 008 arm A contains *motif* **twice**; arm D
   contains it **once**, because the second occurrence lived inside the deleted sentence. The
   isolation is therefore not perfectly clean: arm D removes the presupposition *and* reduces the
   noun's salience. **A frequency-matched control would repeat the noun without the relational
   demand.** Not run; declared. See `critique.md` §3.
4. **Not counterbalanced.** One order, one run.
5. **One pair, one model.** No transfer test, no negative image.
6. **It does not test A6's actual device.** A third-party attributed proposition remains untested by
   008, by 009, and by A5 (whose sycophancy control never fired).
7. **Nothing graduates.** Everything is a **SPARK**.

---

## 9. Provenance

Fixtures reused **byte-identically** from `fixtures/008-kinship-pull-ab/`:
`img1-muqarnas-parent.jpg` = `7cf371cd4a10a48b…`, `img2-vault-crop.png` = `4e76caff29217bc5…`,
both logged in the observation and matching 008's recorded values. No new fixture was cut.
