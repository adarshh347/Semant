"""
HARNESS-001B — one inquiry goal engine, connecting the Director and the situated simulation.

The Director plans and prepares GLOBALLY: a corpus, a prompt, an actuator chain, quarantined
suggestions. A situated agent perceives LOCALLY: one locus, one body, organs bound to where it
stands. They are two scales of one inquiry and, before this package, neither could commission the
other. This is the missing hierarchy and the two adapters — **not** a merge.

    goals.py       InquiryGoal → EvidenceGoal → PreparationTask / AgentMission → SituatedGoal
    frame.py       `inquiry-frame.v1` intake, parallel-safe; owns representation adjustment
    capability.py  need or public act → one of six outcomes, read against the LIVE tables
    adapters.py    DirectorAdapter, SimulatorAdapter, and the wall between them
    evaluator.py   declared criteria against returned evidence, and nothing else
    events.py      the append-only causal history and the serialisable `InquiryRun`
    engine.py      the bounded, deterministic loop
    fixtures.py    the committed frames and worlds the rehearsals run in

Nothing here is moved, renamed or deleted from `backend/services/director/` or
`backend/services/agents/`. Every decision that already belongs to one of them is delegated to it.

═══════════════════════════════════════════════════════════════════════════════
## RUN-STORE RECONCILIATION — read before adding persistence

The directive requires this lane to reconcile the existing run mechanisms BEFORE creating anything,
and to open **no new Mongo collection**. It opens none. `InquiryRun` is a pure value; `to_dict()` is
what a persistence lane would store, once the following is reviewed.

There are three run stores today, and they are three different KINDS of thing:

| store | collection | what it persists | authoritative? |
|---|---|---|---|
| `research_agent_service` | `agent_runs` | a background job queue: status, steps, article id | yes — it IS the queue |
| `vision_run_service` | `vision_runs` | write-behind telemetry for one Dissect route, events embedded | no — a failed write must never change the route |
| `run_store` | `runs` | one corpus run: the `RunView` served by the API, plus A3's `ResumeState` and the resolver's `image_of` | yes — an `awaiting_answer` run is RESUMED from it |

**What each persists.** `agent_runs` is a work queue with a step ledger. `vision_runs` is
observability: one document per operation with its stage events embedded, explicitly never holding
authoritative geometry. `runs` is continuity: a run outlives the request that started it, and the
document is what a curator's later answer resumes from.

**Which could carry an inquiry-level event history.** Only `runs`. `vision_runs` is scoped to one
post and one vision operation and is write-behind by contract — an inquiry whose causal history
could be silently lost on a failed write would be a history nobody can rely on, which is the one
property this lane's log must have. `agent_runs` is a queue whose steps are job phases, not
epistemic transitions, and its consumer is a single asyncio worker; widening it would put two
unrelated lifecycles in one document.

**Which fields overlap.** `runs` and `InquiryRun` already agree closely: `run_id` / `_id`, a
`status` / `outcome` pair drawn from a closed lifecycle, a per-step trace (`view.rounds` +
`view.production_records` vs `events`), a quarantine of uncommitted items (`view.suggestions` vs
`evidence`), and a stated stop reason (`view.stop_reason` vs `stop_reason`). Both are non-
authoritative about geometry and both hold only proposals. `vision_runs` overlaps only on `_id`,
`status` and an embedded event array; `agent_runs` only on `_id`, `status` and `steps`.

**Would extending one corrupt its meaning?**

- `vision_runs` — YES. Its load-bearing rule is that telemetry never becomes load-bearing. An
  inquiry history stored there would be load-bearing telemetry, which is a contradiction, and the
  first failed write would prove it.
- `agent_runs` — YES, in a quieter way. Its `steps` are job phases ("gathering images"); an
  inquiry's events are epistemic transitions ("a capability gap was named"). Sharing the array
  would mean sharing a code path, and the two obey different rules about what may be dropped.
- `runs` — NO. `run_store` already stores a whole envelope under one key, already validates against
  a closed status list, already refuses to be write-behind, and already carries a companion
  structure (`resume`) beside the view. An `inquiry` key beside `view`/`resume`, or an
  `InquiryRun` stored as the `view` of a run whose `spec.mode` says so, fits the document's existing
  meaning rather than stretching it.

**Recommendation, for review rather than for action in this lane: `runs`, via `run_store`.** It is
the only store whose contract already is "this document IS the run's continuity", which is what an
inquiry history has to be. A fourth collection would reproduce exactly the drift this wave exists to
remove. What that lane must add is a `contract_version`-aware read (this run carries its own) and a
decision about whether an inquiry run and a corpus run share `_id` space — they should not, and a
prefixed id (`inq_…` vs `run_…`) already keeps them apart.

`run_store.acyclic` is worth noting as a reason the fit is good rather than merely acceptable: it
exists because argue mode shipped a self-referential article. `InquiryRun` is acyclic by
construction — every field is a tuple of frozen values — so it would pass that guard with
`encoding_repairs: []`, and a future non-empty list there would be a real signal rather than noise.
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

from backend.services.inquiry_engine.adapters import (DirectorAdapter, FakeDirectorAdapter,
                                                      FakeSimulatorAdapter, MissionResult,
                                                      PreparationResult, ProposalNotAPerception,
                                                      SimulatorAdapter, assert_organ_authored)
from backend.services.inquiry_engine.capability import (AGENT_MISSION, CAPABILITY_GAP, COMPOSITE,
                                                        DIRECTOR_PREPARATION, HUMAN_ACTION, NEEDS,
                                                        REFUSED, Need, Resolution, need_for_action,
                                                        need_for_term, resolve_action, resolve_need)
from backend.services.inquiry_engine.engine import derive, run_inquiry
from backend.services.inquiry_engine.evaluator import GoalVerdict, evaluate
from backend.services.inquiry_engine.events import (CapabilityGap, Event, Evidence, InquiryRun,
                                                    OUTCOME_ANSWERABLE, OUTCOME_AWAITING_HUMAN,
                                                    OUTCOME_EXHAUSTED,
                                                    OUTCOME_PARTIALLY_ANSWERABLE, new_run)
from backend.services.inquiry_engine.frame import AcceptedFrame, FrameRefused, accept
from backend.services.inquiry_engine.goals import (AgentMission, Criterion, EvidenceGoal, Goal,
                                                   InquiryGoal, PreparationTask, SituatedGoal)

#: Which existing run store should eventually persist an `InquiryRun`. Stated as a constant rather
#: than only in prose so a persistence lane cannot miss it, and so a test can pin that this lane
#: made a recommendation at all.
RECOMMENDED_RUN_STORE = "runs"
RECOMMENDED_RUN_STORE_MODULE = "backend.services.run_store"

__all__ = [
    "RECOMMENDED_RUN_STORE", "RECOMMENDED_RUN_STORE_MODULE",
    "accept", "AcceptedFrame", "FrameRefused",
    "Goal", "InquiryGoal", "EvidenceGoal", "PreparationTask", "AgentMission", "SituatedGoal",
    "Criterion",
    "NEEDS", "Need", "Resolution", "resolve_need", "resolve_action", "need_for_term",
    "need_for_action",
    "DIRECTOR_PREPARATION", "AGENT_MISSION", "HUMAN_ACTION", "COMPOSITE", "CAPABILITY_GAP",
    "REFUSED",
    "DirectorAdapter", "SimulatorAdapter", "FakeDirectorAdapter", "FakeSimulatorAdapter",
    "PreparationResult", "MissionResult", "ProposalNotAPerception", "assert_organ_authored",
    "evaluate", "GoalVerdict",
    "Event", "Evidence", "CapabilityGap", "InquiryRun", "new_run",
    "OUTCOME_ANSWERABLE", "OUTCOME_PARTIALLY_ANSWERABLE", "OUTCOME_AWAITING_HUMAN",
    "OUTCOME_EXHAUSTED",
    "derive", "run_inquiry",
]
