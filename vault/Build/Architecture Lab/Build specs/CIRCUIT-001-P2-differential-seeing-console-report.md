# CIRCUIT-001 P2 — Differential Seeing Console

**Frontend only. No backend file was touched. No production data was mutated.**
Verified live against the running stack; screenshots in `CIRCUIT-001-P2-screenshots/`.

**The one sentence:** the curator now asks the image to open itself, chooses how to attend
to it, sees which sources that schedules and what the asking actually did — in one
instrument, in the same vocabulary the rest of the product speaks.

---

## 1. What changed

### 1.1 The Seeing Console — new

`differential/SeeingConsole.jsx` + `.css`, all derivation in `differential/seeingConsole.js`
(node-testable; the JSX is thin, the discipline `visionActivity.js` already kept).

Four groups, in the order a curator meets them:

| group | was | is |
|---|---|---|
| **the operation** | a `Dissect` button between a select and an overflow icon | one generous primary action, **Find parts**, with the grain select and overflow beside it |
| **ways of looking** | `ProfileControl` — a `Profile` eyebrow, three capitalised specialist chips, an `Auto` button, a raw router reason, and a row of pass names | *Ways of looking* — modes of attention (`Ordinary looking`, `Fashion & body`, `Built space`, `Painting & surface`, `Let it choose`) |
| **sources** | pass names mixed into the profile block, at the same weight as the choices | a quiet read-only strip: source, the role the **server** reports for it, and its state |
| **operation memory** | `VisionActivityRail`, bolted beneath the inspector with `margin-top: auto` | inside the console: collapsed to the latest run, expanding to stage rows |

### 1.2 Where it mounts, and one thing that surprised me

**The `Dissect` button was never in `DifferentialWorkspace.jsx`.** It lives in
`components/RegionSurface.jsx` — the Field pane of Chiasm — together with `ProfileControl`,
the vocabulary select and the empty state the gate named. The Differential workspace had
**no way to find parts at all**: a curator who entered it with nothing there had to leave,
act on the Field, and come back.

So the console mounts in **both**, and Differential gains the operation it never had
(`differential/useFindParts.js` — same route, same payload keys, same store channel).

### 1.3 The percept workshop — new

`differential/PerceptWorkshop.jsx` + `.css` replaces the percept rows. Same percepts, same
P1C roles, same P1D thread, same P1A handoff; what changed is that a percept reads as a unit
of attention — the noticing in the display face, then what it rests on, then what it does.

### 1.4 The rename

`OPERATION_LABEL.dissect` is now `'Find parts'`. **Keys are frozen and nothing else moved:**
the route, the payload, all fourteen `dissect.*` stage ids, `vision_runs.operation`. This is
the rule P1 Part E set, applied: *operation names are wire identity; labels are curator-facing
and may be rewritten freely.*

## 2. Files changed

**New (8)**
```
frontend/src/differential/seeingConsole.js              derivation + all curator copy
frontend/src/differential/SeeingConsole.jsx             the console
frontend/src/differential/SeeingConsole.css
frontend/src/differential/useFindParts.js               find parts from inside Differential
frontend/src/differential/PerceptWorkshop.jsx           the percept as a unit of attention
frontend/src/differential/PerceptWorkshop.css
frontend/src/differential/seeingConsole.test.js         33 tests
frontend/src/differential/SeeingConsole.dom.test.jsx    16 tests
frontend/src/differential/PerceptWorkshop.dom.test.jsx  12 tests
```

**Modified (5)**
```
frontend/src/components/RegionSurface.jsx     console replaces ProfileControl + rs-verbs; copy
frontend/src/components/PostDetailPage.jsx    one line: onPostChange into Differential
frontend/src/differential/DifferentialWorkspace.jsx   console + workshop replace rail + rows
frontend/src/differential/visionActivity.js   one label value; keys untouched
frontend/src/test/setup.dom.js                IS_REACT_ACT_ENVIRONMENT (see §6)
```

**Orphaned but NOT deleted:** `components/ProfileControl.jsx` / `.css` and
`differential/VisionActivityRail.jsx` / `.css` now have no importers. Deleting a shipped
CIRCULATION-SPINE-001 artefact is a decision, not a side effect of this gate — recommended as
a follow-up, flagged rather than taken.

## 3. Gate 3 outcomes

| | |
|---|---|
| **A** no visible primary `Dissect` | ✅ Nothing on the console renders that word — asserted over the whole subtree, case-insensitively, in a mounted test. Wire id still `dissect`, asserted beside it. |
| **B** controls are one console | ✅ One `<section class="sc">`; the loose two-row cluster is gone. |
| **C** activity integrated | ✅ Inside the console, collapsed to the latest run. |
| **D** empty state | ✅ *"Nothing found here yet. / Find parts to begin composing grounds and percepts."* |
| **E** ways of looking | ✅ Attention modes; base pass is a non-clickable mark, not a disabled button. |
| **F** packet / thread coherent | ✅ Both in the card; the packet has its own plain-language disclosure. |
| **G** no fake capabilities | ✅ See §5. |

## 4. Tests and build

| | |
|---|---|
| new tests | **61** — 33 pure, 28 mounted |
| full frontend suite | **248 passing** (was 187) |
| production build | ✅ `vite build` clean |
| backend | untouched; not run |
| lint | new files clean; pre-existing warnings elsewhere unchanged |

**What the tests deliberately do NOT do.** They are not copy tests. Copy is what this gate
*unfreezes*; a suite asserting display strings would have to be rewritten by the next label
change and would freeze exactly what P1 Part E.3 says to leave free. What is pinned instead:
key integrity, the label→profile-value mapping **at the network boundary** (clicking
`Built space` must PATCH `architecture`, never `painting`), absent-vs-unreadable, and
degradation-only rendering.

Two copy assertions earn exceptions, and only because the old string is the defect: the empty
state may not contain `anatomy`, and no console string may contain `dissect`.

## 5. Honesty notes

- **No packet dispatch.** The packet is built, shown, and unsent. `dispatch.sent` is `false`
  and a test reads it out of the rendered JSON.
- **No causal run relation.** No `run_id` is propagated and nothing claims one operation
  produced another. `latestEntry` orders by each run's own reported time, and the test that
  covers it says so: *being latest says nothing about having produced anything.*
- **No Atlas, no Codex.** Not started.
- **No suspect detection, no persisted Mentions, no Scheduler, no Passage entity.**
- **The operation trace is a projection, not live stages.** There is no socket, no SSE and no
  per-stage push. It is `…/vision-runs/latest` per operation, re-read on a bounded timer only
  while a run is running. The panel **states this on screen** — *"Latest recorded run per
  operation, re-read while one is running."* — beside its scope line. Both are asserted.
- **The source strip reports `not reported`, never `ready`, for a pass with no capability
  record.** `ProfileControl` defaulted to `ready`, asserting availability on the strength of
  a missing record. A strip that invents readiness is worse than one that admits it does not
  know.
- **Ways of looking are attention labels over model profiles, and that is a real abstraction
  gap.** `Built space` schedules `segformer_b0_ade`. If the mapping ever drifts, the label
  will keep sounding right while selecting the wrong pass — which is why the mapping is
  pinned at the network boundary rather than in the module alone.
- **The router reason is cleaned before display.** The live corpus stores
  `" · user override · user override · user override"`; the console renders `user override`,
  or nothing. This *presents* the value better; it does not fix the backend that builds it.

## 6. Two defects found while verifying

**A layout bug the screenshots caught, not the tests** — `00-bug-…-BEFORE-fix.jpg`.
The P1D thread carries `flex: 1 0 100%`, correct for the flex **row** it used to sit in. In
the card it is a **column** child, where basis `100%` means *height* and `flex-shrink: 0`
means it cannot give any back — so the card overflowed and the packet disclosure landed on
top of the inspector's footer counts. Fixed by resetting it under `.pw-card` rather than
editing the shared rule, so the thread still works wherever it is mounted in a row.
**Every test passed while this was on screen.** Component tests assert structure; they do not
assert that a box fits.

**The DOM harness was not an act environment.** Without `IS_REACT_ACT_ENVIRONMENT`, React
warns *and is entitled to stop flushing effects synchronously* — so the component tests could
have been asserting against a half-rendered tree while passing. One line in `setup.dom.js`.

## 7. Verification performed

Against the running stack (backend `127.0.0.1:8000`, vite `5173`), three real posts:

1. **`695be8be…` — no parts.** Console, `Find parts` primary, new empty state, no `Dissect`.
2. **`695be786…` — 7 parts / 5 grounds / 2 percepts, profile `[general, architecture]`.**
   `Built space` correctly pressed; sources show the third scheduled pass (`SegFormer ·
   Structure reading`); the stuttering router reason renders clean. Workshop shows the
   degraded percept with an amber edge and *"2 no longer resolve"* — and no cause.
3. **`6a5ac8ca…` — has recorded runs.** Collapsed memory reads *"Find similar · Complete ·
   23 h ago"* (genuinely the latest of four runs); expanded shows `Find parts · Complete`,
   `yolo · 2325 ms`, ten stage rows with per-stage latency.
4. **Narrow pane** (splitter dragged to ~460 px): the console goes full width, the image is
   not crushed, all targets stay generous. The container query fires at 21 rem.
5. **`Write from this`, controlled and unsaved:** Manuscript opened, chip `◈ the upper head`
   inserted, recall played (the Field receded), then **Cancel**.

**Production mutation: none.** After the handoff run, post `695be786…` reads
`text_blocks: 0`, `regions: 7`, `grounds: 5`, `percepts: 2`, `updated_at: 2026-07-19` — four
days before this gate. No `detect_regions` call was made against any real post.

## 8. What remains incomplete

- **`useFindParts` has never been fired against a real post.** The button is wired and the
  handler is tested, but no live find-parts run was performed from Differential — deliberately,
  because that mutates `region_annotations`. **This is the largest untested path in the gate.**
- **`compact` on `SeeingConsole` is accepted and barely used.** It sets one class; the
  Differential and Field renderings are near-identical. Either earn it or drop it.
- **The collapsed latest-run line truncates in a narrow pane.** Ellipsis, not overflow — but
  it reads as clipped.
- **Orphaned components** (§2).
- **`Coarse only` → `Large parts only` and `Mark a part` → `Mark a part yourself`** moved into
  the console's overflow. Neither is covered by a mounted test.
- **The empty state still lives in `RegionSurface`, not the console.** It reads the console's
  copy constants, so it cannot drift — but the two are not one component.

## 9. Recommended next gate

**P2B — Manuscript as perceptual writing surface.**

The console is good enough. The reason is not that it is finished but that **the crossing is
now visibly one-directional**: a percept can be carried into the writing, and the writing
still cannot answer back in the same register. `data-origin` remains unstyled (P1 Part F),
so a passage the model wrote reads as the curator's own sentence; and the Manuscript has no
equivalent of the workshop's "what does this rest on".

**Not P2C.** The trace panel's remaining gap is *live stages*, and that is a backend
capability (a stream, or per-stage push) — not polish. Building more UI over a projection
would make the shallowness harder to see, not easier.

**Not P2D.** P0.5 §5 is explicit that naming Atlas/Codex is not scheduling them, and their
preconditions — a citation durable outside its prose, a record that evidence was *destroyed*
rather than merely absent — still do not exist.
