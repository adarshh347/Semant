# CIRCUIT-002 · A3 — the answer that resumes the loop

**Branch:** `agentic/a3-resume` (worktree, off `main`)
**Files:** `backend/services/director/loop_controller.py`, `memory.py`, `questions.py`, `backend/tests/test_resume_a3.py`
**Depends on:** A1 (loop), A1-FIX (closed doors), A2 (questions)

## What A2 left

A2 earned the right to ask: at a stop point the loop emits one grounded question and stops at
`awaiting_answer`. Then nothing. The curator could read the question and had nowhere to put the
answer. A3 is the return path — and it is deliberately the *smallest* one that could work, because
the reopen machinery already existed: `_door_still_closed()` re-runs `resolve()` on a blocked step,
and `plan._missing_param` checks the packet as well as the step params, so **a missing-param door
opens the moment the param exists on memory**. A3 injects the param and lets A1-FIX's own code
notice.

```
run_loop → awaiting_answer + Question + ResumeState
                      ↓  curator says "her folded hands"
resume_loop → validate → inject as a PARAM on the packet → run_loop(resume=…)
                      ↓
        the door re-opens, the step runs, the arc is ONE receipt
```

## The guards, and where each one lives

| # | guard | where it is enforced |
| --- | --- | --- |
| 1 | an answer supplies a **param**, never evidence | `WorkingMemory.with_phrase` touches two fields and both are words — structurally incapable of adding a region/mark/ground/percept. Mirrors `plan.availability_for` one layer down. |
| 2 | it routes to the **exact** question it answers | `ANSWERABLE_PARAMS` + `question.missing_param`; the blocked step is recovered from the closed-door entry (`_blocked_step`), so the check runs against what was actually refused. |
| 3 | **resume, not restart** | `ResumeState` carries memory, `executed_sigs`, closed doors and the prior rounds; round numbering continues, so continuation chain ids cannot collide with the first half's. |
| 4 | an answer that doesn't unblock is **refused, never fabricated** | empty/whitespace refused before injection; then `missing_param_of(step, injected)` — `resolve()`'s own check, not a re-derivation. |
| 5 | **no re-ask ping-pong** | terminal `ANSWER_DID_NOT_UNBLOCK` instead of the same question again. The structural half is free: `question_for` returns None once the packet can answer, so an answered param cannot re-earn its question. |
| 6 | suggestions-only | unchanged from A1 — the loop never accepts a mark or writes a post. Pinned in the real run by hashing the post dict. |
| 7 | attribution | `memory.phrase_source = "curator_answer"`, on `summary()` so it reaches every receipt. A phrase that came on the packet keeps `None`: both are the curator's words, but they are not the same event. |

**A rejected answer leaves the loop exactly where it was** — still `awaiting_answer`, still holding
the same question and the same `ResumeState`. Nothing was supplied, so nothing changed, and
consuming the curator's turn for a blank would be the loop pretending it had heard something.

## Design forks (surfaced, as directed)

**1. Round budget on resume — FRESH `max_rounds`.** A human just intervened; spending their answer
on the remainder of a budget the first half burned looking for a way to proceed without them would
waste the intervention. Safe because of guard 5: an answered param cannot produce the same question
again, so a fresh budget cannot become an ask/answer treadmill.

**2. Where the param lives — `memory.phrase`.** The curator's words belong to the packet, and it
makes the reopen machinery work with *zero* special-casing: no step-params bookkeeping, no second
notion of "supplied". **The limit, stated rather than solved:** one global phrase is too coarse if
two steps each need a *different* phrase — the second question would overwrite the first answer.
That is the multi-param case; it needs per-step param injection and a question that carries which
step it belongs to (`Question.step_id` already does). Not this gate.

**3. Cross-request persistence — in-memory now, serializable by construction.** `ResumeState`
round-trips through plain JSON (`to_dict`/`from_dict`, pinned by a test that resumes a loop from a
state that has been through `json.dumps`). No live handles: no actuators, no director, no client.
Persisting a paused loop is a store and a load. One honest limit: a corpus packet
(`corpus.CorpusMemory`) comes back as the plain `WorkingMemory` it extends, so cross-request resume
of a corpus loop needs its own packing.

## Receipt additions

`LoopResult` gains `resume_state` (set exactly when there is a question to answer), `answer` (what
the curator said and what became of it — **including when it was refused**), and `resumed_at_round`
(where the human came in). `to_dict()` carries `answer`, `resumed_at_round` and `resumable`; the
state itself is not inlined because it would duplicate the rounds and the packet already there.

## Verification

**`backend/tests/test_resume_a3.py` — 16 new tests. Backend: 1049 → 1065 collected**, all green
apart from the two pre-existing `test_suggestion_producers.py` intrinsic failures that fail
identically on `main`. `test_loop_controller.py`'s 30 A1/A1-FIX/A2 tests are untouched and green —
the non-resume call is the loop A1 shipped.

Covered: the answer unblocks and the loop carries on · the arc is one receipt (contiguous rounds,
prior rounds verbatim, `resumed_at_round`) · the intention is unchanged across the resume · only
PHRASE availability changes and no evidence is added · the injection itself cannot carry evidence ·
a blank phrase is never stored · the answered door re-opens through the existing `reopened` path ·
executed signatures carry forward so finished work is not redone · still-shut doors are suppressed,
not re-refused · empty answer refused with nothing fabricated · a loop that asked nothing cannot be
answered · an unroutable param terminates with `answer_did_not_unblock` rather than re-asking · the
question cannot be re-earned once the param is on the packet · the phrase is marked curator-supplied
· `ResumeState` round-trips through JSON and still resumes.

### Guarded real run (real Groq, real models, real image, no DB, no accept)

Scratch post in memory, `real_registry(ctx)`, public-domain painting fetched exactly as production
fetches a post image, post dict hashed before and after.

```
intention 'check whether it is present', no phrase on the packet
  [ask]     stop=awaiting_answer  rounds=1  planner_calls=1  resumable=True
            "To answer “Is the named thing actually there?” I need to know what to
             look for. Nothing has been found on this image yet, so there is nothing
             to point at."
            round 0: only_refusals_or_empties   presence_check → missing_param

  curator answers: 'her folded hands'
  [resume]  stop=no_new_evidence  rounds=2  planner_calls=2   (17.2s)
            answer accepted=True  source=curator  param=phrase  actuator=presence_check
            memory: phrase='her folded hands'  phrase_source='curator_answer'
            round 1: presence_check {phrase:'her folded hands'} → ok  conf=0.9897
                     · 1 suggestion, presence_reading, model=grounding_dino_tiny
  post identical: True · regions 0 · marks 0 (nothing accepted)

  [empty answer, same live loop] stop=awaiting_answer  accepted=False
            why='an empty answer supplies nothing'  phrase=None
```

Two things worth recording rather than smoothing over:

- **The model carried the answer into the step params.** Groq planned the continuation as
  `presence_check {phrase: "her folded hands"}` — a *new* step signature, so it ran directly rather
  than through the `reopened` path. The rule-based shape (`presence_check {}`, phrase on the packet)
  is where the door literally re-opens; the unit tests pin that path. Both reach the same place, and
  neither invents the phrase.
- **The same intention planned by Groq returns `[]`** — `nothing_planned`, no question. That is A2's
  documented case C, closed on the `agentic/a2-ext-empty-plan` branch (A2-EXT) and *not* here; A3
  branches off `main` as directed. The two are independent, but both touch the ask-block and
  `LoopResult`, so **expect a textual merge conflict** in `loop_controller.py` when they land — the
  resolution is mechanical (A2-EXT adds question sources; A3 adds the resume/answer fields).

## Not in this gate

Persisting a paused loop across HTTP requests (fork 3 — a store and a load on top of `ResumeState`);
the multi-param case (fork 2); and any surfacing of the question in the UI.
