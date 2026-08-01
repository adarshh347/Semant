# AGENT-DEMO — the run surface (Lane B)

**Branch** `feat/agent-demo` · **Route** `/agent` · **Status** built against the fixture; awaiting Lane A's live routes.

A dedicated surface where someone picks images, types a question, and watches the orchestrator work — live progress, the produced output, and the full manifest of what each actuator did.

---

## Its own route and shell, on purpose

Not folded into `/differential`, and nothing there is imported or altered. The Differential is the **manual** instrument — a curator marking one image by hand. This is the opposite entry: raw images and a sentence, with the machine doing the looking. They have diverged deliberately, and sharing a shell would force one to pretend to be the other.

`/agent` code-splits into its own JS + CSS chunk, so the main bundle is unchanged for everyone who never opens it.

## Annotation-independence, made visible

The governing principle is a UI claim here, not only a backend one:

- `canStartRun` is the **only** gate the entry form consults, and it asks for a corpus and an intention — nothing else. A future "must be annotated" check cannot be added without failing `runContract.test.js`.
- The corpus picker offers an unannotated post exactly like an annotated one — no filter, no sort, no disabled state.
- It **says** `no marks yet` beside such an image rather than hiding the count. That is the demo's argument made in passing.

## What was built

| File | What it is |
|---|---|
| `runContract.js` | The contract as runnable code — vocabulary, normalisers, `canStartRun`, `isHonestlyEmpty`. No React, no fetch. |
| `runViewFixture.js` | Lane B's copy of the fixture (see ownership note below). |
| `runClient.js` | The only module that knows a network exists. `createRunClient` (live) and `createMockRunClient` (tests) are interchangeable. |
| `RunEntry.jsx` | Images + tags + prompt + mode. |
| `RunProgress.jsx` | The loop, round by round. |
| `ProductionPanel.jsx` | Per-step manifest: consumed, produced, model, adapter, latency, refusal. |
| `QuestionFlow.jsx` | A2/A3 — the ask, the answer, the run continuing. |
| `RunOutput.jsx` | `ArticleView` for `argue`; produced evidence for `explore`. |
| `AgentDemoPage.jsx` | The shell. State is a single `RunView`; every panel is a pure function of it. |

## Three decisions worth recording

**Normalisers exist because the contract is under construction.** Lane A is building these routes in parallel, and the first real payload will differ somewhere — a null where a list was assumed, a field not filled yet. Reading through normalisers means that shows up as a missing row rather than a white screen, and the demo survives the meeting of the two lanes. An unrecognised `status` becomes `pending`, not `complete`, so an older client keeps polling a run that is still going instead of declaring it finished.

**No progress bar, anywhere.** The loop does not know how many rounds it will take, so a bar would be inventing a denominator — a run that re-plans twice is not "60% done". What is shown is what has *happened*, plus a live pulse that says the thing is moving without claiming to know how far. Pinned by a test asserting no `<progress>` and no `role="progressbar"`.

**A refusal is a result and is rendered as one** — marked, not greyed out, with its reason and detail. A producer that declined to trace a projective frame across a flat wall has told you something true about the picture. So has a step that ran and produced nothing, which is shown saying `Produced nothing` rather than omitted; omitting empty rows would quietly make a run look tidier than it was.

Unknowns are em dashes, never zeros. `0 ms` is a measurement never taken presented as an instant one; `0` confidence reads as certainty about being wrong.

## The one seam in the reuse rule

The brief says render `explore` output "through the same renderers" as the article, **and** that nothing in `/differential` may be imported here. Both hold: `article/PerceptFigure` is already the component that wraps `RegionOverlay`, `FlowFieldLayer` and `paintFields` for exactly this purpose. So this surface imports from `article/` only, and the differential renderers arrive transitively through the component whose job is already to host them. A field looks the same here as in the workspace because it is literally the same painter — no renderer was copied.

A structural test walks every module under `agentDemo/` and fails on any import path containing `differential/`.

## Fixture ownership — a real coordination point

`run-contract.md` assigns `runViewFixture` to **Lane A**, which also owns the routes that produce it. `run-contract.md` is not in the repo yet, and neither is the fixture. `agentDemo/runViewFixture.js` is written from the spec so Lane B could be built and tested before those exist.

**When Lane A's fixture lands, delete this one and swap the import** — do not merge them, do not keep both. Two fixtures claiming to be the same contract is precisely the drift the shared-fixture rule exists to prevent.

The fixture deliberately carries the failures, because they are the interesting part: a refused step, a step that produced nothing, an unknown model, an unknown latency, a percept with no confidence, and an `awaiting_answer` variant with a real grounded question. Its article is `articleFixture()` verbatim — the same payload `/lab/article` renders — so this surface and the article harness cannot disagree about what an `ArticleDraft` looks like.

## Verification

- **34 new tests**, all passing: 21 contract + 13 DOM.
- Full frontend suite: **944 passing, 59 files**.
- `vite build` clean (3.05s); `/agent` emits its own chunk.

Guards from the brief, each pinned:
1. the full fixture renders — article, production records, question — with no backend;
2. the answer box round-trips `awaiting_answer` → resumed, same `run_id`;
3. nothing under `agentDemo/` imports from `differential/` (structural test);
4. Editorial tokens only — no hard-coded colour, so light and dark follow the app.

Two bugs were found by the tests and fixed rather than worked around: the mock's `watch` looped forever on a non-terminal final script entry (starving the microtask queue and killing the vitest worker), and after `answer()` it replayed the `awaiting_answer` view so the question reappeared under the user. The second was a mock-fidelity gap masking a real behaviour, so the mock was made faithful rather than the assertion loosened.

## Not done

- **Not wired to a live backend.** `createRunClient` is written to the contract but has never spoken to a real route — Lane A's endpoints do not exist yet. The swap point is `AgentDemoPage`'s `client` prop; no component changes.
- **Upload is not implemented.** The entry offers *select by post* and *select by tag*. Dropping new images needs the upload path, which is a separate concern from the run contract.
- SSE is written with a poll fallback but only the poll path has been exercised, since there is no stream to open yet.
