# CIRCUIT-001 · P2C-MS — Implementation & Design Report

**Gate:** Manuscript as Multimodal Field + Orchestration Session
**Branch:** `feat/rehearsal-research-r1` (HEAD was `3a78785` — P2B)
**Date:** 2026-07-23
**Design docs:** `CIRCUIT-001-P2C-MS-manuscript-multimodal-field.md` · `CIRCUIT-001-P2C-OS-orchestration-session.md`
**Screenshots:** `CIRCUIT-001-P2C-MS-screenshots/`

---

## 1. What the Manuscript is becoming

It stops being a text box beside the image and becomes **a surface of the circuit**, on equal footing with the Field.

P2 closed with the finding that the crossing is one-directional: a percept can be carried into the writing, and the writing cannot answer back. That is the structural violation this gate names — the Chiasmatic Network's governing rule is that *nothing may leave the circuit without being able to return*, and until now the writing could return nothing.

Two capacities define the target:

- **Accountable** — a sentence can be asked what it rests on, and answers honestly, *including "nothing" and including "not assessed."*
- **Generative** — a sentence can act back on the image: become a percept, arm a mark, request a counter-reading.

The asymmetry held throughout: **prose is the curator's; perception is cited.** The Manuscript never writes the curator's sentence for them unasked, and never claims a sentence is supported when it is not.

### 1.1 The design's sharpest refusal

The obvious design — a green tick on supported sentences, a red flag on unsupported ones — is **explicitly forbidden** (§2.1 of the spec), for three reasons:

1. It inverts degradation-only display. Nine badges per paragraph is how honesty stops being read.
2. **"Unsupported" is not a fact the system possesses.** It knows *"cites nothing"*. It does not know *"rests on nothing."* Rendering the second is the fake causality P1 forbids.
3. It would make citation performative. A curator scored on citations cites to clear the score, and the mention graph stops recording where attention actually went.

The shipped code encodes this in its vocabulary: `citation_state: 'cites_nothing'` is a **record**; the question *"What is unsupported?"* answers `not assessed — cites nothing is not rests on nothing` and is marked `answerable: false`.

### 1.2 The live hazard this gate names but does not fix

`aiSlashItems` already seeds blocks with `origin: 'sutradhar'`, the meta side-channel already preserves it through serialisation — and **`[data-origin]` has no styling**. A model-written passage currently reads as the curator's own sentence. Recorded as unbuilt item #2; it needs inline-level provenance, which the block-keyed `metaRef` side-channel cannot provide.

## 2. Orchestration Session

**Name adopted: Orchestration Session.** It inherits from *Perceptive Orchestration* (P0.5) — *"a packing rule, not an agent, not a pipeline, and not a place to put intelligence"* — widened from one percept to the whole current circuit.

Alternates were rejected on specific grounds: *Session Mind* / *Working Mind* / *Studio Mind* impute an interior a context object does not have (and "mind" is how a context object becomes an agent by drift); *Perceptual Session* claims it perceived something, when it carries records of what the **curator** perceived; *Chiasmatic Session* was the strongest runner-up but "chiasm" already names the writing-side shell in code.

It is **not** an agent, not persistent memory, not a mutation path, and not a prompt. Constraints travel **as data**, so the discipline cannot be quietly edited by whoever writes the next prompt template.

**Five fields do the real work**, each guarding an honesty invariant:

| Field | Guards |
|---|---|
| `unreadable[]` | everything asked for and not obtained — so silence is never readable as absence |
| `resolution_assessed` | when `false`, every `detached` flag carries **no information** |
| `citation_state: 'cites_nothing'` | a record; the vocabulary makes it impossible to collapse into `unsupported` |
| `external_claims: null` | `null` = not assessed; `[]` would mean *assessed, found none*. There is no assessor |
| `dispatch_state` | stated **inside** the object so it cannot be mistaken for a dispatch record |

**On LangChain/LangGraph:** none present, none scaffolded, no dependency added. The constraint recorded for any future adoption is one-directional: *LangGraph may orchestrate the calls; it must consume Semant's action grammar; it must never define it.* `perceptualActions.js` defines the grammar and everyone else intersects with it — `allowedFrom()` is derived, and cannot name a type outside `ACTION_TYPES`.

## 3. Was code implemented?

**Yes — one bounded slice plus one pure module.** Both were judged safe because neither persists, dispatches, nor alters the editor.

### Files changed

| File | Δ | What |
|---|---|---|
| `vault/…/CIRCUIT-001-P2C-MS-manuscript-multimodal-field.md` | **new** | Gate 2 — the product architecture |
| `vault/…/CIRCUIT-001-P2C-OS-orchestration-session.md` | **new** | Gate 3 — the session design |
| `vault/…/CIRCUIT-001-P2C-MS-report.md` | **new** | this report |
| `vault/…/CIRCUIT-001-P2C-MS-screenshots/` (4 files) | **new** | browser verification |
| `frontend/src/manuscript/manuscriptField.js` | **new** | pure — object catalogue, `describeSelection`, `selectionQuestions`, `buildChipInspection`, `actionsForSelection`, `inspectorSummary` |
| `frontend/src/manuscript/manuscriptField.test.js` | **new** | 29 tests |
| `frontend/src/manuscript/PassageInspector.jsx` | **new** | the read-only inspector |
| `frontend/src/manuscript/PassageInspector.css` | **new** | record/judgement voices; internally scrolled |
| `frontend/src/manuscript/PassageInspector.dom.test.jsx` | **new** | 18 tests |
| `frontend/src/orchestration/orchestrationSession.js` | **new** | pure — Gate 5 assembler |
| `frontend/src/orchestration/orchestrationSession.test.js` | **new** | 39 tests |
| `frontend/src/components/PostDetailPage.jsx` | **+7 / −0** | one import, one mount below `<Manuscript>` |

`PostDetailPage.jsx` is the **only existing file touched**, and only additively. No editor schema change, no change to `insertRef`, the `/percept` slash flow, or the P1B handoff.

### How the slice couples: it listens, it does not wire

The inspector reads the `semant:region-focus` CustomEvent that `regionRefInline` **already emits**, plus the live DOM selection scoped to `.manuscript`. **Nothing in the editor had to change to make the writing answerable** — which is also why the blast radius is one import and one element.

## 4. Tests and build

| | Before | After |
|---|---|---|
| Test files | 19 | **22** |
| Tests | 330 | **416** (+86) |
| Result | green | **green** |
| Production build | — | **clean** (pre-existing chunk-size warning only) |

Tests pin the discipline, not the copy:

- evidence is `unknown` — never `intact` — without a resolver
- **no evidence section renders when evidence is healthy**
- a degradation is stated without a cause (asserts absence of `/replaced|because/`)
- `not_assessed` ≠ `cites_nothing`
- `unsupported` never appears anywhere in a serialised session
- `allowed_actions ⊆ ACTION_TYPES`; `challenge_percept` and `ask_model_reading` refused even when claimed as capabilities
- `dispatch_state: 'sent'` without a `run_id` is **refused, not corrected**
- every rendered act carries `data-wired="false"`; **zero buttons and zero links** inside the inspector
- clicking an act leaves the store byte-identical (`JSON.stringify` before/after)
- the session holds no functions and round-trips through JSON unchanged

## 5. Browser verification

Live against the running backend, post `6a5ffc05a3ddb6341fd699f9` (1 ground, 1 percept, 0 text blocks).

| # | Check | Result |
|---|---|---|
| 1 | Percept chip in Manuscript → inspector shows expression, cited grounds, in-the-writing | ✅ **no evidence row**, because the ground resolves — degradation-only confirmed live |
| 2 | Plain prose selection → `Selection · cites nothing`, 8 questions, preview-only acts | ✅ records at opacity 1; the two judgement rows recessed to 0.58 and reading *not assessed* |
| 3 | Differential → "Write from this" → opens Manuscript, inserts chip, recall plays; Cancel | ✅ all four; Cancel returned the pane to "No story yet" |
| 4 | Console errors | ✅ **none** (only a Vite HMR notice) |

### 5.1 A real layout defect, found only in the browser

The first render put the inspector's action list **underneath the tag strip**: as an unbounded flex child of `.edit-section`, it grew the section past the story column's height and collided with the strip below. Every one of the 18 component tests passed while it was broken — *component tests assert structure; they do not assert that a box fits*, which is precisely the lesson P2 recorded and this gate re-earned.

Fixed with `flex: 0 0 auto; max-height: 15rem; overflow-y: auto` — the inspector now never takes space from the editor and scrolls internally. Screenshots `02-…-overflow-bug.jpg` (before) and `03-…-fixed.jpg` / `04-…-fixed.jpg` (after).

### 5.2 Incidental confirmation of P1B

Re-running "Write from this" for the same percept in the same session did **not** re-insert the chip — `wasDelivered` / `doneIds` at-most-once delivery, working as designed. A reload resets the session and it inserts again.

## 6. Production mutation status

**NONE.**

| | Before | After |
|---|---|---|
| `grounds` | 1 | 1 |
| `percepts` | 1 | 1 |
| `text_blocks` | 0 | 0 |
| `updated_at` | `2026-07-22T01:53:14.959000` | `2026-07-22T01:53:14.959000` |

A chip was inserted and prose typed in two separate editing sessions; both were cancelled and neither reached the API. No new module persists anything, and a full revert of this gate leaves the corpus byte-identical.

## 7. What remains unbuilt

Ordered by what unblocks the most.

1. **Inline provenance** — precondition for everything about model drafts and external claims. `metaRef` is keyed by block id and cannot address below a block.
2. **Model draft styling + accept/revise/dismiss** — the live hazard of §1.2. Accept should record lineage (`derived_from`), so `user_confirmed` is a **derived fact**, not a flag someone must remember to set.
3. **The return leg** — "Revise in Differential" from a chip. The smallest useful piece of the circuit's governing rule, and currently preview-only.
4. **Seven new action types** with specs and validators (`map_sentence_to_image`, `create_percept_from_sentence`, `challenge_sentence`, `extract_claims`, `mark_external_claim`, `revise_with_percepts`, `send_sentence_to_differential`, `compare_passage`). Until each has a spec, `normalizeAction` returns `null` for it — the correct failure — so none may render an Apply.
5. **Ground / field / trace / relation references** — blocked on P2C-OH's `visual_mark` module.
6. **`extract_claims`** — until it exists, the two judgement questions must keep answering *not assessed*, and must not be softened.
7. **Durable Mentions** — still correctly deferred: the corpus has 0 text blocks, so there is no evidence of how curators actually cite.

## 8. Recommended next gate

**P2C-VM — `visualMarks.js` + provenance unification** (P2C-OH's own recommendation), *not* the Manuscript's next layer.

Reasoning: items 1 and 5 above both need one thing first — a single provenance vocabulary. Three incompatible ones exist today (Region: `actor`/`detector`/`proposed`/`geometry_rev`; Ground: `actor`/`detector`; P2B action: `source`/`status`), and only P2B's can express *"a model suggested this and a human accepted it."* Inline manuscript provenance (item 1) and visual-mark references (item 5) would otherwise each invent a fourth and fifth.

**Second choice, if a Manuscript gate is preferred:** the return leg (item 3) alone — narrow, high-value, and the one thing that would make the circuit bidirectional for the first time.

**Explicitly not recommended yet:** wiring any model call. P1D's conditional GO still stands — `no model reading recorded` is a true record today and *becomes a lie the moment a packet is sent*. The recording must land **before** the first dispatch, not after.

---

*The model mind is not an autonomous ghost. It is a session-shaped witness to the current image-writing circuit. It may suggest. Semant shapes. The user confirms. Only then does an action enter the circuit.*
