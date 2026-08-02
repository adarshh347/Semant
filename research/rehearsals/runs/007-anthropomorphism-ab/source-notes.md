# 007 — Source notes

## The stimulus

Post **`695be843a9ea58f1b6aef5ff`**, read **read-only**. Chosen because it is **the one image known
to have produced the behaviour under test** — run 004 (A3) described it as having "windows that
function as eyes… a direct, imposing gaze."

- original: `fixtures/007-anthropomorphism-ab/dark-structure.jpg`, 1366×2048, 489 602 B,
  `sha256: c1f69be0be7aba25240a3d5ed23fed709b9d1384f15c8397a56f8c8ce303c86d`
- **probe variant used in BOTH arms**: `probe-768.jpg`, 512×768, 98 595 B,
  `sha256: d366b2e1ae779807a1ad70568bf1c1ee3c84bd13bc9d8acabe45ca8c9336c086`

**`reproduction_vs_depiction: depiction`.** A photograph of a dark metal structure. **No figure, no
face, no body is present** — which is the entire point: any face in the reading is supplied by the
reader.

**Metadata status:** no title, no description, no catalogue data. Neither arm volunteered an
attribution, and none is asserted here.

**Annotation state:** 0 regions, 0 grounds, 0 percepts, 0 text_blocks — before and after.

## The design

One variable: **the question frame**.

| held constant | value |
|---|---|
| stimulus | identical file, verified by sha256, in both arms |
| model | `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| `max_tokens` | 1000 in both arms |
| call shape | single-image, stateless, independent |

**Arm A (address-framed)** mirrors run 004's framing: *"Where does the address of what is shown here
go — that is, where does it direct itself, and what does it turn away from or withhold?"*

**Arm B (structure-framed)** mirrors run 005's framing: *"What organises this composition — how are
its parts arranged, and what decides that arrangement?"*

**Neither prompt contains** *face*, *eye*, *gaze*, *body*, *head*, or *watching*. The word
**address** appears in arm A only — that is the variable under test.

## Pre-registration

The manifest recorded, **before any call**, all four cells of the interpretation grid —
`a_face_b_none`, `a_face_b_face`, `a_none_b_none`, `a_none_b_face` — with the explicit rule that a
**null result in both arms is CONFOUNDED, not negative**, and must not be scored as resolving
spark-06. The observed cell was `a_face_b_none`.

## Declared confound

A3 sent this image at **256 px inside a three-image comparison**; this run sends it alone at
**768 px**. Resolution and call shape therefore differ from A3 in **both** arms.

This does not weaken the finding, because the finding rests on the **contrast between arms**, where
resolution is held constant. It does mean the two runs are not strictly identical conditions — and
it makes arm A's reproduction of the face a **secondary result in its own right**: A3's reading was
not an artifact of downscale degradation or of comparison context.

## Model

Groq, `qwen/qwen3.6-27b`, `reasoning_effort: "none"`. **2 live calls** (budget 2), 33 s apart, no
retries, no provider failures. Both `finish_reason: "stop"`, no `<think>` leakage. Raw text frozen
verbatim; no JSON parsing attempted.

## Honesty notes

- Order was **not counterbalanced** — arm A ran first. Both calls are stateless, so there is no
  mechanism for carry-over, but this is weaker than a counterbalanced design.
- The word "address" arguably *names* a viewer-relation, so arm A may be a leading question rather
  than a neutral frame. The finding is reported at that narrower scope.
- This run is the **first voluntary adopter** of the external-claims ledger proposed in
  `Decisions/HW-C5-external-claim-convention.md`; see `score.md`.
- No production document was written at any point.
