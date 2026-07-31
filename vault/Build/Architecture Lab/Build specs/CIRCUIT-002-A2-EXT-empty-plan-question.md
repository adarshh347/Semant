# CIRCUIT-002 · A2-EXT — the question that survives an empty plan

**Branch:** `agentic/a2-ext-empty-plan` · **Files:** `backend/services/director/loop_controller.py`, `backend/tests/test_loop_controller.py`
**Depends on:** A1 (loop controller), A1-FIX (closed doors + auditable receipt), A2 (questions as an honest planner output)

## The one dead end A2 left

A2 gave the loop its fourth mode — ASK — and hung it on the **closed doors**: at a stop point,
`_askable_door()` scans the refused-step dict for something refused `REFUSED_MISSING_PARAM` and
builds a grounded question from it. That hook fires only if something was *refused*.

A planner that proposes **nothing** refuses nothing. `propose()` returns `[]` → `plan.steps` is
empty and `plan.refused` is empty → the loop stops `nothing_planned` with `closed == {}` → no door
→ no question. The dead end A2 existed to remove, reached by a different road. A2's own commit
named it as case C and left it: *"Widening the trigger beyond the specified hook is a design
decision, not a patch, so it is left for the next gate."* This is that gate.

It is **model-specific and real**, not hypothetical:

| planner | on `check whether it is present`, packet with no phrase | A2 |
| --- | --- | --- |
| `RuleBasedPlanner` | emits `presence_check {}`; `resolve()` refuses it `missing_param` | asks ✓ |
| `GroqPlanner` | returns `[]` rather than inventing a phrase (`groq_planner.py`, the `if not steps` branch) | silent ✗ |

The better-behaved planner got the worse outcome. Its honesty — declining to invent — is exactly
what erased the signal.

## The root conflation

An empty proposal collapses two different facts into one silence:

```
NO ACTUATOR SERVES THIS INTENTION      an honest refusal. Nothing to ask; asking anyway is fishing.
ONE SERVES IT, I LACK THE PHRASE       a door shut on four words from a human — A2's whole subject.
```

Recovering the distinction is the entire change.

## What was built

### 1. `_diagnostic_probe()` — a deterministic diagnostic, not a second prompt

On the `nothing_planned` stop **where nothing was refused**, the loop asks the `RuleBasedPlanner`
what it *would* propose for this intention and runs that through the same `resolve()`. Four
outcomes, a closed set, all recorded:

| outcome | meaning | question |
| --- | --- | --- |
| `no_rule_based_shape` | the intent table matches nothing — no actuator serves this | none |
| `resolves_cleanly` | the shape runs on this memory; the empty proposal was not about a gap | none |
| `no_askable_door` | refused, but for a missing **INPUT** — the loop's own work to do | none |
| `question_recovered` | refused for a missing **PARAM** | ask, via `question_for()` |

**Why this stays inside every boundary.** It is not re-prompting around a refusal: there was no
refusal to route around (the model returned nothing), the intention is untouched, and no model is
consulted a second time. `RuleBasedPlanner.propose()` is a fixed function of intention + memory —
no network, no generation, nothing that could invent a phrase. And nothing the probe proposes is
ever *run*: its only output is a question or silence.

It reuses A2's `is_question_able` / `missing_param_of` / `question_for` rather than re-deriving
them, so "missing param" cannot drift from what `resolve()` refuses for, and the grounding guards
(no invented options; say plainly when there is nothing to point at) come along unchanged.

### 2. Legibility — the probe is its own receipt field

A1-FIX's contract is that *"the planner was not called a second time about the same door"* stays
readable from the receipt. So the diagnostic is recorded as `diagnostic_probe` on `LoopResult`,
distinct from `planner_calls`, which **does not move for it**:

```json
"planner_calls": 1,
"diagnostic_probe": {"planner": "rule_based", "counts_as_planner_call": false,
                     "proposed": ["presence_check"],
                     "refused": [{"actuator": "presence_check", "reason": "missing_param", …}],
                     "outcome": "question_recovered", "question_from": "presence_check"}
```

`null` means it never ran — there was no dead end to diagnose.

### 3. A volunteered question is CONFIRMED, never trusted

`Proposal(steps=[], question=…)` lets a capable planner short-circuit to the same honest outcome.
Taken on faith it is a hole in the guard A2 *is*: claiming *"I need a phrase for X"* is exactly as
easy for a model as inventing the phrase would have been. `_confirmed_volunteer()` runs the claimed
actuator through `resolve()` and surfaces the question only if it really is refused
`REFUSED_MISSING_PARAM` for the param claimed. A rejected claim is recorded on `volunteer_check`
(with why) and dropped — and the honest paths still get their turn, so rejecting a claim never
costs the curator a question they were owed.

The order of trust, each falling through to the next: **confirmed claim → closed door → diagnostic
probe.**

### 4. `STOP_MAX_ROUNDS` still excluded

Unchanged, and for A2's reason: at the backstop progress was still being made, so the closed door
is not the blocker and a question implying the curator is the bottleneck would be false.

## Verification

`backend/tests/test_loop_controller.py`: **30 → 43 (+13)**, all green; the rest of the backend
suite is unchanged and green apart from two pre-existing failures in `test_suggestion_producers.py`
(the real intrinsic/gray pipeline) that fail identically on `main`. A whole-suite count is not
quoted here: this ran in a working tree shared with the parallel PROV-001 session, so the totals
would attribute that session's tests to this gate.

- **D** `test_an_empty_proposal_still_asks_when_a_phrase_is_the_real_blocker` — a faked GroqPlanner
  returns `[]` for `is there a cross…`; loop stops `awaiting_answer` with a grounded question, the
  planner asked exactly once.
- **E** `test_an_intention_no_actuator_serves_asks_NOTHING` — `mumble` stays `nothing_planned`,
  probe `no_rule_based_shape`, no question. No fishing.
- **F** `test_the_probe_is_its_own_receipt_field_and_is_not_a_planner_call` — the probe is on the
  receipt in its own field; `planner_calls == len(planner.calls) == len(rounds) == 1`.
- Branch coverage: `resolves_cleanly` and `no_askable_door` (missing INPUT) both stay silent; the
  probe dispatches nothing and fabricates no param; it does not run when a closed door already
  answers, nor on the max-rounds backstop.
- Volunteer confirmation: confirmed claim surfaced unrewritten; claims rejected for
  already-answerable, missing-input, and wrong-param; a rejected claim still falls through to the
  diagnostic's honest question.

### G — guarded real run (real Groq, in-memory scratch post, no DB, no accept)

`real_registry(ctx)` on a scratch post dict, hashed before and after. **Case C reproduced and
closed:**

```
'check whether it is present'   groq proposed []  →  awaiting_answer
    probe: presence_check → missing_param → question_recovered
    "To answer “Is the named thing actually there?” I need to know what to look for.
     Nothing has been found on this image yet, so there is nothing to point at."
    planner_calls 1 · groq api calls 1 · suggestions 0 · post identical ✓

'how many are there?'           groq proposed []  →  awaiting_answer
    probe: enumerate → missing_param → question_recovered

'check whether it is present'   phrase='a cross' in the packet
    groq proposed presence_check{phrase:'a cross'} → ran → no question, probe null

'what do you think of my haircut'
    groq proposed [] → nothing_planned, probe no_rule_based_shape, NO question
    (a second run of the same intention proposed find_parts + semantic_read — model
     nondeterminism; both outcomes are honest and neither produces a question)

'is there a cross in this picture'   (A2's case B, unchanged)
    groq proposed presence_check{phrase:'cross'} — grounded in the curator's OWN words
    rather than invented, so it plans and runs instead of asking
```

Every run: `suggestions 0`, post hash byte-identical, one Groq call per round, nothing accepted.
Note the question fires **before anything executes** — the probe closes the door on a dead end
without spending a model call or touching an actuator.

## What this does not do

Carrying an answer back into a resumed loop is still **A3**. A2-EXT emits and returns
`awaiting_answer`, exactly as A2 does. The invariant holds unchanged: an unanswered question yields
a refusal, never a fabricated param.
