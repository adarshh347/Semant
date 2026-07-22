# CIRCUIT-001 P1D — Implementation report

**The Circulation Thread, made rich.** Frontend only. **No production data changed** — verified by
API after the browser run (§6).

Follows `CIRCUIT-001-P1C-implementation-report.md` §8 item 1. The dispatch question it raised is
answered separately in `Decisions/CIRCUIT-001-P1E-percept-packet-dispatch-decision.md`.

---

## 1. What changed

| file | what |
|---|---|
| `differential/circulationThread.js` | rewritten: two voices, fuller row set, roles, packet row |
| `differential/circulationThread.test.js` | rewritten for the two-voice model (19 tests) |
| `differential/PerceptThread.jsx` **(new)** | the expandable thread; render only |
| `differential/DifferentialWorkspace.{jsx,css}` | the P1A one-line thread and the P1C packet disclosure are folded into `PerceptThread` |

The percept row previously carried *two* separate affordances — a summary line (P1A) and a packet
`<details>` (P1C). They are now one thing, which is what the row was always describing.

## 2. The thread model

`buildCirculationThread(percept, ctx)` → rows, **records first, then judgements**.

**Records — observed, and pointable:**

| relation | says |
|---|---|
| `formed` | `formed in Differential` |
| `cites` | `cites 2 grounds: anchor, counterforce` — the count, with roles when named |
| `mentioned` | `mentioned in 1 passage` · `mentioned in the writing` (crossing known, passage not) · `not yet in the writing` |
| `recalled` | `recalled 2× this session` — session-local, and the text says so |
| `packet` | `packet prepared, not sent · intent read` |
| `model-reading` | `no model reading recorded` |

**Judgements — concluded, and ours:**

| relation | says |
|---|---|
| `missing` | `none of the 2 cited grounds still resolves` |
| `degraded` | `1 of 2 cited grounds no longer resolves` |
| `external` | `external claims not assessed` |
| `suspect` | `substitution not assessed` |

`state` describes the **row**, not the percept's worth: `nominal` · `degraded` · `absent` ·
`unassessed`.

## 3. Record vs judgement — why the distinction is load-bearing

> A **record** is something the system observed and can point at.
> A **judgement** is something the system concluded, and owns as its own.

Rendering them identically teaches a reader to trust them equally. This programme has already made
that error once: `DifferentialWorkspace` told a reader a ground's *"part was replaced by a
re-dissect"* when `resolveGround` knew only that an id no longer resolved.

Two consequences fall out of the split, and both are the point:

**The count of grounds is a record; what is wrong with them is a judgement.** So a healthy citation
reads as a plain fact with no warning welded to it — `cites 2 grounds`, and nothing else. Degradation
gets its own row or none at all.

**`no model reading recorded` is a RECORD, not a judgement**, and this is deliberate. It is a fact
about *our ledger* — we looked and there is nothing there — not a conclusion about the percept.
Filing it as a judgement would imply the system had assessed something.

**And what we have NOT looked at says so.** `external claims not assessed` and `substitution not
assessed` exist so that silence is not mistaken for a clean bill. They are true, they are not
findings, and the CSS recedes them accordingly.

## 4. UI behaviour

**Resting: one quiet line**, because a curator is usually composing, not auditing.
`formed · cites 2 grounds · mentioned in 1 passage`. Degradation displaces the mention:
`formed · cites 2 grounds · none of the 2 cited grounds still resolves`.

**Expanded: the relation chain**, records above judgements, each labelled `RECORD` / `JUDGEMENT`.
Records read plain; judgements are italic and carry slightly more weight — the curator's own
register. `absent` and `unassessed` rows recede, so **only a real finding carries emphasis**.

**Only a real degradation tints the closed line.** `not assessed` is honest but is not news, and must
not make a healthy percept look sick.

The packet remains available inside the expanded thread as *"the packet, as it would be asked"* —
still collapsed, still the full JSON.

**Not a timeline.** Rows are ordered by the question a reader would ask, not by when anything
happened, and nothing is joined by an arrow.

## 5. Packet integration

The thread reports the packet's existence, its `intent`, and that `sent: false`. `PerceptThread`
builds the packet to do so. **Nothing dispatches.** The row reads
`packet prepared, not sent · intent read`.

## 6. Verification

| | |
|---|---|
| **tests** | **187 passing, 13 files** (P1C left 177). **+10 net**, thread suite rewritten 9 → 19 |
| **build** | `vite build` ✓ |
| **backend** | not run — **no backend file touched** |
| **console** | no errors |

**Browser, read-only, on `695be786a9ea58f1b6aef5ed`:**

- Resting lines correct: the degraded percept reads
  `formed · cites 2 grounds · none of the 2 cited grounds still resolves`; the healthy one
  `formed · cites 1 ground` and stays quiet.
- Expanded shows six `RECORD` rows and three `JUDGEMENT` rows, visually distinct, with
  `not yet in the writing`, `not recalled yet`, `no model reading recorded`, `external claims not
  assessed` and `substitution not assessed` all recessed, and only *"none of the 2 cited grounds
  still resolves"* carrying weight.

**Production mutation: NONE.** `percepts: 2`, `grounds: 5`, `text_blocks: 0`,
`updated_at: 2026-07-19T00:46:31.869` — days before this session.

## 7. What remains

**P1E — packet dispatch: DEFERRED, with a conditional GO.** See
`Decisions/CIRCUIT-001-P1E-percept-packet-dispatch-decision.md`. The short form: **dispatch turns an
inspectable request into a recorded event, and the circuit cannot yet record events.** The thread's
`no model reading recorded` is true today and becomes a lie the moment a packet is sent. First
operation, when approved, should be **`challenge`** — not `read` — and even then its output must
never be presented as having *tested* the percept. **P1E should instead design the `run_id`
relation**, which is an identity question, not plumbing.

**Ground Role refinement.** Roles do not travel into the manuscript chip's markup, so a chip cannot
show what its grounds do. The packet reads them from the percept, which is sufficient for
orchestration. Worth doing only if a surface needs it.

**Durable Mention.** Still branch (b) — reconstruction lossless, persistence deferred. The corpus
still has **0 text blocks**, so there is still no evidence of how curators actually cite.

**Suspect detection.** Still unimplemented, and now visible as a row that says so. It remains the
highest-consequence gap in the map: a reference that resolves to *different* geometry is
indistinguishable from a healthy one.

**Atlas/Codex prep.** Blocked on the durable Mention decision, unchanged.

**Still deliberately absent:** persisted Mentions, `suspect` detection, `run_id`, any backend change,
any model call.
