# CIRCUIT-001 P2B — Perceptual Action Grammar

**Frontend only. No backend file touched. No production data mutated.**
Verified live; screenshots in `CIRCUIT-001-P2B-screenshots/`.

**The one sentence:** a curator can now begin from what caught them — *"the gaze she points
toward, the shoulder-level folding architecture, the extreme lighting…"* — and Semant turns
it into structured, previewable, refusable perceptual acts, four of which carry straight
through into the existing tools.

**The ordering that governs this gate:** the grammar and the deterministic execution
pathways exist *first*. There is no model in the loop, and that is deliberate — swapping the
planner for a model later changes the **source** of proposals and nothing else. Every
proposal will still pass the same validators, still arrive as `model_suggested`, still be
refusable, and still require the curator's hand for anything that touches the image.

---

## 1. The Perceptual Action Grammar

`differential/perceptualActions.js` — pure, no React, no fetch, no clock it does not accept.

**Nine families.** `find_parts` · `brush_field` · `trace_direction` · `connect_marks` ·
`compose_percept` · `assign_ground_role` · `start_manuscript` · `challenge_percept` ·
`ask_model_reading`.

**Common shape** on every action: `id · type · label · intent · source · status ·
requiresConfirmation · target · createdAt · payload · warnings · provenance`.

**Vocabularies** (candidates, not taxonomies — P1 addendum §6): 12 field roles, 8 trace
roles, 9 relation roles, 7 manuscript modes, 5 challenge types. They overlap the Ground Role
vocabulary on purpose: a brushed light field *is* an atmosphere ground once it exists, so the
act names what will be made in the language the made thing will use.

**Validators:** `normalizeAction` · `validateAction` · `validateActionList` ·
`summarizeActions` · `groupActionsByTarget` · `actionNeedsGeometry` · `actionCanApplyNow` ·
`actionToHumanLabel` · `actionToShortReason` · `setActionStatus`.

### 1.1 Fail closed, and what that means here

`normalizeAction` returns **null**, never a partial object. A caller that receives an object
will render it, and a half-valid action rendered as a card is precisely the failure the
grammar exists to prevent. An unknown role is an **error**, not a coercion — a vocabulary is
only worth having if a word outside it fails.

**Three rules that are about the product, not the schema, and are enforced by the validator:**

| rule | why |
|---|---|
| **A model may never author `challenge_percept`** | P1 addendum §3.1 — the human's veto over the circuit. `source: 'model_suggested'` on a challenge is refused outright. |
| **`ask_model_reading` with `dispatch.sent === true` is refused** | Not quietly corrected. Silently resetting the flag is *how a dispatch happens*. |
| **`requiresConfirmation` is set by the spec, never by the caller** | A proposal must not be able to declare itself confirmation-free and skip the user. |

## 2. The planner

`differential/attunementPlanner.js` — deterministic, lexicon-driven. **No LLM, no LangChain.**

13 lexicon entries over the vocabulary of looking (gaze, light, shadow, fold, architecture,
recession, material, rhythm, gesture, threshold, comparison, tension, negative space) plus 7
writing-intent cues read separately, because those name an *output* rather than something in
the image.

Every emitted action carries `provenance.matched` — the actual words keyed on — so a card
says **you said "lighting"**, never *Semant detected light*. The planner has no access to the
image at all.

**Behaviour worth stating:**
- an empty prompt, or one with no vocabulary it knows, proposes **nothing**. Silence is the
  honest output; inventing acts for words it does not understand is how a proposer starts
  pretending to see.
- `find_parts` is suppressed when the post already has regions.
- the percept draft is seeded with **the curator's own sentence**, verbatim.
- side hints (*left / lower*) are hints only — no geometry is derived from them, ever.

### 2.1 The fixture, and the bug it caught

The sculpture prompt is stored beside the planner as `SCULPTURE_FIXTURE` and produces **10
acts**: trace gaze/address, brush gaze field, brush light field *(left / lower)*, brush
shadow field *(left / right / lower)*, brush fold *(you said "shoulder")*, trace
architectural axis, connect—contrast, compose percept, ask for counter-reading, find parts.

**Two lexicon defects the fixture exposed, both fixed:**
- `aesthetic` was a cue for `philosophical_note`. The fixture opens *"The **aesthetic** is in
  the gaze…"* — which describes the image and asks for nothing. A cue firing on a common
  descriptive noun makes the panel offer an essay every time somebody says what they see.
- `against the` was a cue for `threshold`, producing a threshold nobody had mentioned.

## 3. UI and layout

**`differential/AttunementPanel.jsx` + `.css`** — First Attention (prompt, helper copy,
*Suggest acts*, five quick chips) and Suggested acts (cards grouped by target).

**The orchestration column was widened** from `clamp(200px, 24cqi, 300px)` to
`clamp(320px, 30cqi, 440px)` and sectioned. Order, by when a curator needs each part:

```
FIRST ATTENTION  →  SEEING (Find parts · ways · sources · operation memory)
                 →  working area  →  GROUNDS  →  PERCEPTS  →  DETACHED  →  counts
```

Find parts remains one keystroke away and is **no longer the door**.

### 3.1 What a card shows

Label · a colour swatch for field acts · *you said "…"* · the payload facts that matter
(role, where, as, act, relation, saving, dispatch) · the draft text for a percept · warnings
· state · **Apply / Arm this · Preview · ✕**.

## 4. What actually applies, and what is preview only

**Carried through (5)** — `ACTION_CAPABILITIES` in `DifferentialWorkspace.jsx`, read together
with the executor switch so a capability cannot be claimed without an executor behind it:

| act | what happens | returns |
|---|---|---|
| `find_parts` | calls the existing `useFindParts` with the current grain | `applied` |
| `brush_field` | switches to Brush, stages role + label | `armed` |
| `trace_direction` | switches to Trace/Path, stages role + label | `armed` |
| `connect_marks` | switches to Connect, stages the relation | `armed` |
| `compose_percept` | opens the composer with the curator's sentence and any gathered evidence | `armed` |

**Preview only (4)** — `assign_ground_role` · `start_manuscript` · `challenge_percept` ·
`ask_model_reading`. Each renders **"Preview only — execution path not wired yet"** and has
**no Apply button**. An Apply that quietly does nothing teaches the curator that the whole
panel is theatre; the admission is cheaper than the lesson.

### 4.1 Arming is not drawing

The whole shape of applying an image act: the tool switches, the intended role/label is held
in `stagedMark`, and **the geometry is the curator's hand**. When the draft is committed the
staged label rides onto the ground. Leaving the tool abandons the arming — the alternative is
a stale label riding onto an unrelated mark later. Nothing is written by arming, and the
stage says so: *"lighting (left / lower) — armed. Make the mark; nothing is created until you
do."*

## 5. Files

**New (6)**
```
frontend/src/differential/perceptualActions.js          the grammar
frontend/src/differential/attunementPlanner.js          the deterministic planner
frontend/src/differential/AttunementPanel.jsx           First Attention + Suggested acts
frontend/src/differential/AttunementPanel.css
frontend/src/differential/perceptualActions.test.js     28 tests
frontend/src/differential/attunementPlanner.test.js     33 tests
frontend/src/differential/AttunementPanel.dom.test.jsx  21 tests
```

**Modified (2)** — `differential/DifferentialWorkspace.jsx` (panel mount, executor,
`stagedMark`, composer prefill, armed hint, section restructure) ·
`differential/DifferentialWorkspace.css` (column width, sections, armed line).

## 6. Tests and build

| | |
|---|---|
| new tests | **82** — 61 pure, 21 mounted |
| full frontend suite | **330 passing** (was 248) |
| production build | ✅ clean |
| backend | untouched; not run |
| lint | new and changed files clean |

**A defect the tests caught:** `defaultLabel` threw on a payload with no role, so a malformed
proposal **crashed instead of being refused**. A crash is not failing closed. Fixed by making
label derivation total, so the action reaches `validateAction` and is refused there.

## 7. Browser verification

Post `695be8be…` (0 regions) and `695be786…` (7 regions / 5 grounds / 2 percepts).

1. **Differential, empty post** — First Attention at the top of the column, prompt visible,
   five quick chips, Find parts present but not the only entry. ✅
2. **Sculpture prompt → Suggest acts** — *"10 suggested acts · 7 need a mark from you"*,
   grouped Image marks / Evidence relations / Percepts / Operations & model questions. Gaze,
   light, shadow, fold, axis, contrast, percept draft, counter-reading, find parts all
   present with colour swatches and *you said "…"* reasons. ✅
3. **Armed `brush_field`** — Brush tool activated, card became *"Ready — make the mark on the
   image."*, stage read the armed line. **No mark made, nothing written.** ✅
4. **Counter-reading card** — *"Preview only — execution path not wired yet"*, no Apply. ✅
5. **Existing percepts** — Percept Workshop, roles, degradation line, Circulation Thread and
   the unsent packet all intact in the wider column. ✅
6. **Console** — no errors or exceptions. ✅

**Production mutation: none.** After verification: `695be8be…` 0 regions / 1 ground / 0
percepts, `updated_at 2026-07-17`; `695be786…` 7 / 5 / 2, `updated_at 2026-07-19`;
`vision_runs` still **11**. No `find_parts` was run against a real post.

## 8. Caveats — stated, not buried

- **No model planner.** The planner is a lexicon. It does not see the image.
- **No LangChain / LangGraph.** None added, none scaffolded.
- **No packet dispatch.** `ask_model_reading` cannot be applied at all — `actionCanApplyNow`
  returns false for it regardless of what the mounted surface claims it can do.
- **No causal `run_id`, no Atlas/Codex, no persisted Mentions, no suspect detection.**
- **The narrow layout was NOT verified in the browser.** The extension captures at a fixed
  viewport regardless of window size, so the `@container diff (max-width: 720px)` stacked
  case could not be exercised. The stacking rule itself is unchanged by this gate, but the
  column is now taller — First Attention sits above everything inside a `max-height: 42vh`
  box when stacked, which likely needs more room. **Unverified and probably tight.**
- **`find_parts` still has never been fired against a real post** — from the console or from
  an action card. Carried over from P2 and still the largest untested path.
- **`assign_ground_role` has no planner path.** It is specified and validated but nothing
  emits one yet.
- **The side hint can be noisy** — *"shadow field · where left / right / lower"* on the
  fixture, because the window around the cue catches every side word near it. It is a hint,
  and it is labelled as one, but it is not precise.
- **`connect_marks` arms the Connect tool but does not preselect the marks** to connect;
  `source_refs`/`target_refs` are always empty from the planner.

## 9. Recommended next gate

**P2C — confirmed action execution**, as scoped, with one addition.

Turn the four preview-only families into staged, user-confirmed pathways: `start_manuscript`
into the existing P1B handoff (which already opens the editor unsaved and is cancellable),
`assign_ground_role` into the composer's role row, `challenge_percept` into a real percept
affordance. `ask_model_reading` stays unsent — it is the one that needs the packet dispatch
decision, not a UI.

**The addition: fix the narrow layout first.** It is the one thing in this gate that shipped
unverified, and a column that has become the primary surface should not be the one nobody has
seen at a small width.
