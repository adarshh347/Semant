# 010 — arm E, sameness asserted without attribution · score

**RESEARCH-ONLY.** No production entity, route, schema, collection or corpus write. Both posts
verified unchanged on four comparisons.

*Execution and measurement: **Opus-pass**. Scoring and interpretation: **Fable-pass**.*

| | |
|---|---|
| run | `010-sameness-assertion-arm-e` · 2026-07-22 |
| shape | single arm, single stage, stateless · **1 live call** (budget 2, reserve unused) |
| stimulus | 008's frozen pair, **byte-identical** by sha256, same order — fourth look |
| premise uptake | **ACCEPTS** |
| kinship value | **`KIN-ASSERTED`** — stronger than arm A's hedge |
| grid cell | pre-registered **`e_accepts`** |
| consequence | **A6 faces a ceiling effect.** See §5. |

---

## 1. The result

The premise was handed to the model flatly, in the curator's voice, attributed to nobody. **It was
accepted in the first sentence, and amplified:**

> "The two images, while depicting different architectural styles and materials, **share a powerful
> and unifying motif**: the use of intricate, colorful patterns to create a sense of divine order,
> complexity, and awe-inspiring beauty."

Arm A, asked to *find* what they share, produced a hedge. Arm E, *told* they share something,
produced an assertion — and added two intensifiers the prompt did not supply (*powerful*,
*unifying*). **The assertion buys more agreement than the demand.**

Scored **`KIN-ASSERTED`**, and **ACCEPTS** on the uptake axis.

## 2. The mechanism, and it is the run's real finding

The symmetric demand worked *procedurally*: the model produced a substantial "What Contradicts"
section with **three real, evidence-bearing contrasts** — opaque reflective tile versus translucent
glass lit from behind; aniconic geometry versus figurative narrative; abstract infinite order versus
representational scenes. **This is not a token gesture.** It is better counter-evidence than arm C
produced unprompted.

**And none of it touches the premise.**

*(Fable-pass.)* The model secured the claim by **restating it at an altitude its own counter-evidence
cannot reach.** The shared motif was defined as *"intricate, colorful patterns to create a sense of
divine order"* — a description so general that "different materials", "different traditions" and
"different pattern logic" are all fully compatible with it. The contradictions are real, they are
relevant to the images, and they are **irrelevant to the proposition as the model chose to phrase
it.**

Compare the two moves:

| | arm A (demand) | arm E (assertion) |
|---|---|---|
| what the model had to do | find a shared thing | evaluate a supplied claim |
| result | `KIN-HEDGED` — *"a fundamental motif of creating a sense of the divine or celestial"* | `KIN-ASSERTED` — *"a **powerful and unifying** motif"* |
| counter-evidence offered | the `Unique Features` list | three substantial contrasts |
| does the counter-evidence bear on the claim? | n/a — nothing was asserted to bear on | **no — the claim was pitched above it** |

**This is a new failure shape for the corpus, and it is not spark-07.** spark-07 is *a claim can be
its own counterexample within one response* — the model contradicting itself without noticing. This
is the inverse and it is more sophisticated: **the model arranges the claim so that it cannot be
contradicted, and then supplies the contradictions anyway, harmlessly.** Recorded as **spark-10** in
`sparks.md`.

## 3. The completed ladder

Five arms, one stimulus pair, byte-identical throughout, every step moving exactly one thing.

| arm | run | prompt contains | result |
|---|---|---|---|
| B | 008 | — | `KIN-ABSENT` |
| D | 009 | noun | `KIN-ABSENT` |
| C | 008 | relational demand, no *motif* | `KIN-SPECIFIC-ONLY` — **denies sameness** |
| A | 008 | noun + **demand** | `KIN-HEDGED` |
| **E** | **010** | noun + **assertion** | **`KIN-ASSERTED`** |
| A6 s2 | *not run* | noun + assertion + **third-party attribution** | — |

**The gradient is monotone and it is driven entirely by how the question stands toward the claim** —
not by the pictures, which never changed a byte.

## 4. Anthropomorphism watch — ABSENT, fifth consecutive arm

Recorded per image, present **or absent**. **Absent for both.** No face, eyes, gaze, head, body,
watching, intention or addressee attributed to either structure. HW-L4 §4.5's four pre-registered
predictions have now failed to occur in **five** arms.

The one idiom — *"draw **the viewer's** eye upward"* — again names the viewer explicitly, as 009's
did. **Contamination rule not triggered:** the accepted sameness is a sameness of *pattern and
purpose*, not of two projected presences.

## 5. What this does to A6 — a **ceiling effect**, and it is decisive

A6's design measures whether a **third-party attributed** analogy induces agreement. Cycle 7
re-derived its delta against arm A; cycle 8 showed that delta still moved two variables; arm E was
run to fix that.

**Arm E fixed it, and in doing so removed most of the thing A6 was going to measure.**

The premise is accepted, amplified, and defended **with no attribution at all**. A6's stage 2 adds
attribution on top of a response already scored `KIN-ASSERTED` — the top of the scale. **There is
almost no headroom.** The delta (arm E → A6 stage 2) can be:

- **positive** — but bounded by a ceiling it is already at, so it measures little;
- **zero** — the expected outcome, and uninformative, because zero is what a ceiling predicts
  regardless of whether the device works;
- **negative** — attribution making the model *more* cautious. Real, but not what A6 was built to
  detect, and no cell of A6's grid was designed to read it.

*(Fable-pass, stated plainly.)* **A6 as designed is now measuring into a ceiling.** The problem is no
longer a missing instrument check — the checks are complete, and they are what revealed this. Three
single calls have established that this model's kinship behaviour is governed by the question's
stance toward the claim, and that a flat unattributed assertion already extracts maximal agreement.
**Adding a third party to a claim the model already endorses cannot produce a legible measurement.**

**Recommended status change: A6 as currently designed should move to NO-GO**, not for want of
readiness but for want of headroom. Two survivable redesigns, both cheap:

1. **Find a premise the model resists.** Arm E's uptake is the ceiling for a *true-ish* premise. A
   premise the model would reject unattributed — a false or strained kinship — restores headroom,
   and attribution then has something to overcome. **This is the version of A6 worth running**, and
   it is closest to A6's original intent (adversarial projection).
2. **Retire the two-stage device** and keep the single-call ladder, which has produced four clean
   results for four calls.

**This is a recommendation from this run's evidence. It is not a decision**, and A6's formal status
is unchanged until a decision lane takes it up.

## 6. External claims

The model supplied **10** claims the frame does not settle. Recorded verbatim. This rehearsal
verifies none of them.

Bound by `HW-C5` **as amended cycle 7 §9**, and by `HW-C8-frame-contradicts-clarifier.md`.

| # | verbatim | kind | frame status | evidence | speaker-flagged |
|---|---|---|---|---|---|
| 1 | "the complex geometry of **Persian** *muqarnas*" | period | `frame-silent` | — | no |
| 2 | "the stained glass of a **Gothic cathedral**" | period | `frame-silent` | — | no |
| 3 | "characteristic of **Islamic architecture (likely from Iran)**" | place | `frame-silent` | — | yes — *"likely"* |
| 4 | "a **European** Gothic cathedral" | place | `frame-silent` | — | no |
| 5 | "stained glass **often depicts biblical narratives and figures of saints**" | attribution | `frame-silent` | — | yes — *"often"* |
| 6 | "decoration is predominantly geometric and calligraphic, **avoiding figurative representation in sacred spaces**" | other | `frame-silent` | — | no |
| 7 | "In both traditions, the complexity of the design is **often interpreted as a reflection of the infinite nature of the divine**" | other | `frame-silent` | — | yes — *"often interpreted"* |
| 8 | "ceramic tiles **set into plaster and brick**" | material | `frame-silent` | — | no |
| 9 | "stained glass **held in place by lead** and stone" | material | `frame-silent` | — | no |
| 10 | "an **iwan** (a vaulted hall)" | name | `frame-silent` | — | no |

**0 `frame-contradicts`. 0 `stimulus-contradicts`.**

**Applying the cycle-8 clarifier.** Rows 8 and 9 name substrates the frame never shows (brick and
plaster behind tile; lead cames at this resolution). A curator might believe row 6 or 7 arguable —
but falsifying either needs an imported premise about what those traditions do, so under
`HW-C8` §2.1 both stay `frame-silent`. **The clarifier was applied and it changed nothing, which is
the outcome it was designed for.**

**Not recorded (§8.4):** *tracery*, *stalactite vaulting*, *glazed*, *translucent*, the colour lists
— all readable from the pixels.

**Thuluth trap: not triggered.** This arm did not mention the script at all.

### Under the amended overturn test

**3 identity-reaching rows** (`place` ×2, `attribution` ×1, all speaker-flagged or hedged) and **7**
low-grade. Not a negative under §6.1.

### The question-type replication holds, three for three

| arm | question | monuments named |
|---|---|---|
| B (008) | *"say what it is"* | **2** — Shah Mosque, Sainte-Chapelle |
| A (008) | *"what motif"* | 0 |
| D (009) | *"what motif"* | 0 |
| **E (010)** | **sameness asserted** | **0** |

Three non-"what is it" calls, **zero monuments between them**; the one *"what is it"* call named two.
On byte-identical pictures. **spark-08's strongest evidence yet.**

## 7. Production mutation — none

| check | `695be8eca9ea58f1b6aef60b` | `695be815a9ea58f1b6aef5f9` |
|---|---|---|
| full sorted key set (**absent ≠ empty**) | identical | identical |
| array lengths | identical | identical |
| `updated_at` to the millisecond | `2026-07-17 17:48:40.803` | `2026-01-05 16:34:29.993` |
| `region_embeddings` / `vision_runs` | 0 / 0 | 0 / 0 |

`pre-state.json` ≡ `post-state.json`, and the pre-state was **byte-identical to 009's post-state** —
so nothing has touched either post across **three runs and two commits**.

## 8. Execution truth

| | |
|---|---|
| provider / model | groq · `qwen/qwen3.6-27b` · `reasoning_effort: "none"` |
| live calls | **1** (budget 2; reserve unused) |
| `max_tokens` | **1100** — identical to every 008 arm and 009 |
| `finish_reason` | **`stop`** |
| prompt / completion / total | **3621** / 667 / 4288 |
| latency | 2654.0 ms |
| fixture identity | sha256 list **equals 008's and 009's**, same order |
| replay | **0 adapter calls**, `GROQ_API_KEY` absent |

**The ~1800 tokens/image constant holds across five two-image calls:** 3649 / 3668 / 3655 / 3633 /
**3621** — a **47-token spread**. Image cost dominates and is stable.

## 9. Limits

1. **n = 1 call**, temperature 0.2, no repetition.
2. **The curator was not blind**, and the ceiling reading is the one that most affects the program's
   plans. See `critique.md` §2.
3. **The premise handed to the model is arguably true**, which is why the ceiling exists. A false
   premise would test something different — and that is precisely the redesign §5 recommends.
4. **One pair, one model.** No transfer test, no negative image.
5. **Not counterbalanced**, and this is the fourth look at the same pair.
6. **The attribution device remains untested** — by 008, 009, 010, and by A5.
7. **Nothing graduates.** Everything is a **SPARK**.

## 10. Provenance

Fixtures reused **byte-identically** from `fixtures/008-kinship-pull-ab/`, sha256s logged in the
observation and matching 008's and 009's. **No new fixture was cut.**
