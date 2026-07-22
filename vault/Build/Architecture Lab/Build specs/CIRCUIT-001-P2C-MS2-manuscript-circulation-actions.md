# CIRCUIT-001 · P2C-MS2 — Manuscript Circulation Actions

**Gate kind:** implementation (Lane B — Manuscript)
**Status:** shipped
**Branch:** `feat/rehearsal-research-r1` (HEAD was `dfc45f2` — P2D interface contract)
**Builds on:** P2C-MS (`PassageInspector`, Orchestration Session), P1B (handoff), P1C (packet), P1D (thread), P2B (action grammar)
**Lane discipline:** P2D interface contract — Lane A owns `visualMarks.js` / `visualLayers.js` / `suggestionQuarantine.js` and the dirty `DifferentialWorkspace.jsx`. **This gate touched none of them.**

---

## 0. What changed, in one line

The Passage Inspector stopped being a read-only panel of preview-only cards and became a surface that **acts** — it collapses so it never dominates the writing, and its acts now do real, safe things: replay the noticing on the image, return to Differential, begin a passage, disclose the packet and thread — while everything that would touch the image or a model stays honestly staged.

The P2C-MS report named the return leg as *"the smallest useful piece of the circuit's governing rule."* This gate builds it. The Manuscript can now answer back.

---

## 1. Collapse / expand UX (Gate 2)

The visible complaint — *expanded, the inspector occupies too much writing space; the collapse affordance was not visible enough* — is fixed.

- The header is a real `<button class="pi-toggle">` with a chevron, `aria-expanded`, and `aria-controls="pi-body"`. Keyboard-accessible by construction; it traps no focus.
- **Collapsed, it does not disappear** — it shows a context-dependent compact line:
  - percept chip → `Percept · 1 ground · 1 passage` (verified live)
  - degraded percept → the same, plus the calm degraded note (e.g. `… · 1 of 2 cited grounds no longer resolves`) — **only** when truly degraded; `unknown` is not treated as degraded
  - plain prose → `Selection · cites nothing`
  - nothing selected → `Nothing selected · pick a sentence or a chip`
- Collapsing **preserves the selection** (the `selection` state is untouched by the toggle).
- It still cannot collide with the tag strip / footer: the P2C-MS anti-collision fix holds (`flex: 0 0 auto; max-height: 16rem; overflow-y: auto`), and collapsing drops `max-height` since the body is unmounted. Verified in the browser — collapsed, the inspector is a single line and TAGS sits comfortably below.

## 2. Which acts became real (Gate 3, 4)

Each act declares **how far it can go**, and the class is the honesty:

| Act | On | Kind | What it does now |
|---|---|---|---|
| **Recall on the image** | chip | `live` | calls `regionStore.playRecall(perceptId)` — the noticing replays; if grounds no longer resolve, P1B's honest degraded recall already refuses to point at nothing |
| **Revise in Differential** | chip | `live` | `setWorkspaceMode('differential')` + `focusRegions` on the percept's resolved grounds + `playRecall` — a **real** return to where it was formed, verified switching the whole workspace |
| **Start a passage** | chip | `live` | new `Manuscript` handle method `startPassage()` inserts an empty human paragraph after the chip's block and focuses it — local, unsaved, cancellable. Verified: block count 1 → 2, cursor in the new empty block |
| **Show packet** | chip | `disclose` | `buildPerceptPacket` rendered inline — states *"built for inspection; nothing is sent"* |
| **Show circulation** | chip | `disclose` | `buildCirculationThread` rendered with record/judgement voices — reports *"no model reading recorded"* as a record about the ledger |
| **Challenge support** | chip | `staged` | builds a valid `challenge_percept`, `source: 'user'` (P2B refuses a model-authored challenge), shown as *"Ready, not sent"* — **not dispatched** |
| **Create percept from selection** | prose | `staged` | valid `compose_percept`, seeded with the sentence **verbatim** |
| **Draft a description / critique / script** | prose | `staged` | valid `start_manuscript` (`insertion_mode: 'unsaved'`), carrying P2B's *"Nothing is saved until you save it."* warning |
| **Send to Differential** | prose | `live` | `setWorkspaceMode('differential')` — a real, visible return to the image side |

### 2.1 Which remain preview (structured, not loose text)

`Map sentence to image`, `Challenge sentence`, `Mark external claim`, `Compare` — their grammar types do not exist yet (`normalizeAction` returns `null` for an unknown type, the correct failure). They produce a **structured `previewProposal`** — `{ proposal_kind: 'structured_preview', grammar: false, payload: {…}, dispatch: { sent: false }, status: 'preview_only' }` — never a loose string, so a later gate can lift them into the grammar without reinterpreting prose. Verified live: `map_sentence` shows *"Structured preview · Needs your mark on the image"*.

## 3. Alive copy (Gate 5)

The dead line *"Preview only — execution path not wired yet"* is gone as the dominant tone (asserted by a test). Honesty is kept, but the panel reads as able to act: *"Play it back where its grounds live"*, *"Return to where it was formed"*, *"Ready, not sent"*, *"Challenge is staged — no model has read it"*, *"This sentence has not cited an image yet"*, *"The request as it would be asked — nothing sent"*.

## 4. Orchestration Session update (Gate 6)

`buildOrchestrationSession` now accepts a `manuscriptAction` and records it at `manuscript_context.requested_action` as `{ type, status, return_target }`:

- `status ∈ MANUSCRIPT_ACTION_STATUSES = ['preview_only', 'staged', 'applied']` — `applied` means a **local** effect ran (recall, a return, a passage begun), **never** a model dispatch.
- `return_target ∈ RETURN_TARGETS = ['image', 'differential', 'percept', 'ground']` — the circuit's governing rule made addressable.
- Unknown status → `preview_only`; unknown target → `null` (guessed defaults are refused).
- `validateSession` rejects an unrecognised status/target, and an `applied` action never lets the session claim a dispatch (`dispatch_state` stays `none`; the existing `sent`-without-`run_id` refusal is unchanged).

## 5. Tests & build (Gate 7)

| | Before | After |
|---|---|---|
| Test files | 22 (mine) | **26** (incl. Lane A's 3 untracked suites, left running) |
| Tests | 416 | **501** — all green |
| `manuscriptField` | 29 | 41 |
| `orchestrationSession` | 39 | 44 |
| `PassageInspector.dom` | 18 | 18 (rewritten) |
| Production build | clean | **clean** (pre-existing chunk-size warning only) |

New/updated test coverage proves: collapse/expand + `aria-expanded`; collapsed summary for percept (`Percept · N ground · M passage`) and selection; a degraded note appears without a cause and `unknown` is not degraded; Recall/Revise/Start-passage/Send call their callbacks; a live act leaves the store byte-identical; staged acts build **valid** grammar actions authored by the user; challenge is never model-authored; a preview proposal is structure with `dispatch.sent === false`; no fake `supported`/`verified`; the session can carry a manuscript action and never claims a dispatch.

## 6. Browser verification (Gate 8)

Live against the running backend, post `6a5ffc05a3ddb6341fd699f9`. Screenshots in `CIRCUIT-001-P2C-MS2-screenshots/`.

| # | Check | Result |
|---|---|---|
| 1 | Click percept chip → inspector opens, collapse button visible | ✅ header toggle with chevron; 7 chip acts with alive copy |
| 2 | Collapse → compact summary; expand again | ✅ `Percept · 1 ground · 1 passage`, no TAGS collision; re-expands preserving selection |
| 3 | Recall on image | ✅ callback fires; the noticing replays on the image (dots + caption) |
| 4 | Revise in Differential | ✅ **switched to the full Differential workspace**, grounds lit |
| 5 | Show packet / Show circulation | ✅ packet: *"nothing is sent in P1C"*; thread: *"no model reading recorded"* |
| 6 | Challenge support (staged) | ✅ *"Ready, not sent"* proposal, `grammar: true`, nothing dispatched |
| 7 | Plain prose selection | ✅ verbatim quote, *"This sentence has not cited an image yet"*, 8 structured acts |
| 8 | Start a passage | ✅ empty block inserted (1 → 2 blocks), cursor placed, still "Unsaved" |
| 9 | Cancel edit | ✅ returns to "No story yet" |
| 10 | Console errors | ✅ none |

## 7. Production mutation status

**NONE.** `updated_at` identical before, mid, and after (`2026-07-22T01:53:14.959000`); `text_blocks` still `0`; `grounds`/`percepts` unchanged. A chip was inserted, prose typed, a passage begun, and a proposal staged across multiple sessions — all cancelled, none reached the API.

## 8. Files changed

Lane B only:

- `frontend/src/manuscript/manuscriptField.js` — action model (`CHIP_ACTIONS`/`SELECTION_ACTIONS`, `ACTION_KINDS`), grammar-action builders, `collapsedSummary`, enriched `buildChipInspection` counts
- `frontend/src/manuscript/PassageInspector.jsx` — collapse/expand, live/disclose/staged/preview wiring
- `frontend/src/manuscript/PassageInspector.css` — collapse header, action tones, disclosures, proposals
- `frontend/src/manuscript/manuscriptField.test.js`, `PassageInspector.dom.test.jsx` — updated/extended
- `frontend/src/orchestration/orchestrationSession.js` + `.test.js` — `requested_action`, statuses/targets
- `frontend/src/components/blocknote/Manuscript.jsx` — additive `startPassage()` handle method
- `frontend/src/components/PostDetailPage.jsx` — four circulation handlers + inspector props
- `vault/…/CIRCUIT-001-P2C-MS2-manuscript-circulation-actions.md` (this) + screenshots

## 9. Caveats

1. **"Send to Differential as First Attention" does not prefill the First Attention prompt.** That prompt lives in `DifferentialWorkspace` / `AttunementPanel` — Lane A's surface under the P2D contract, dirty in the working tree — so wiring the consumer would clobber Lane A. The act performs a **real workspace switch** (never a no-op) and the prefill is deferred to P2E synthesis. Recorded as a P2E amendment request.
2. **Staged proposals are held in local component state**, not persisted and not queued — clicking again clears them. This is deliberate: there is no dispatch, so there is nothing to persist.
3. **The seven new action types are still not in the grammar.** They remain structured previews until a gate adds their specs to `perceptualActions.js` (out of scope here — the P2D contract steered this gate away from grammar expansion during a parallel lane).
4. **Recall counts** are not shown (store exposes no session recall counter); the section simply does not render, which is honest.

## 10. Next recommended gate

**P2E — Lane synthesis.** Both lanes (A: `visualMarks`; B: this) now sit on the shared P2D contract. P2E should: (a) wire "Send to Differential as First Attention" to prefill the prompt now that both surfaces are known; (b) let the Manuscript cite a committed `visual_mark` (P2D §1 `citable`), turning the preview-only `map_sentence` into a real staged mark once Lane A lands; (c) decide the seven new action-type specs together, so the Manuscript and the marks agree on one vocabulary.

Still explicitly **not** recommended: any model dispatch. P1D's conditional GO stands — `no model reading recorded` is a true record today and *becomes a lie the moment a packet is sent*; the recording must land before the first dispatch.

---

*The Manuscript can act. It replays, it returns, it begins a passage, it stages a proposal. It never claims to have done what it has only made ready — and nothing it does enters the circuit without the curator's hand.*
