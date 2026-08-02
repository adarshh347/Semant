"""
CIRCUIT-001 PLANNER-001 — the real Groq planner, behind the Director's seam.

ORCH-001 shipped the seam and proved the guardrails with a fake: a planner that emitted a
hallucinated actuator, an unsatisfiable real step, and no ids got exactly one step through,
with the other two refused by name and by missing input. This is the real implementation
plugged into that same socket.

WHAT THE MODEL IS AND IS NOT ALLOWED TO DO. It proposes a chain of actuator NAMES with
params. That is all. It does not dispatch, it does not author geometry, it does not assert
that evidence exists, and it does not get a second chance to produce a plan that passes.
Everything it returns goes through the unmodified `resolve()`, which is the same function
that judges the rule-based planner.

The three guards below are the ones that would silently rot if left implicit, so each is
enforced in code rather than in the prompt. A prompt is a request; these are the fence.

  1. HALLUCINATIONS ARE NOT FILTERED HERE. It would be easy to drop unknown actuator names
     while parsing and hand back a tidy list. That is exactly wrong: it would hide how often
     the model invents capabilities, and the refusal is the observable that tells you whether
     to trust the planner at all. Unknown names are passed through verbatim so `resolve()`
     refuses them BY NAME and the refusal shows up in the plan.

  2. PARAMS ARE CLAMPED TO THE DECLARED VOCABULARY. For a known actuator, every param key not
     in its `param_keys` is dropped. This is what stops the model from smuggling in
     `geometry`, `mask`, `region_ids`, or a `confidence` — evidence it has no way to possess
     and no right to assert. Dropped keys are recorded, not silently discarded.

  3. NO RE-PROMPT LOOP. Exactly one call per `propose()`. If `resolve()` refuses steps, that
     is reported and the plan stands as refused. Looping until something passes would search
     for a chain that runs rather than a chain that is true — the fabrication this whole
     layer exists to prevent, arriving at the top instead of the bottom.

FAILURE IS UNAVAILABLE, AND SAID OUT LOUD. No key, no client, API error, unparseable JSON —
all fall back to `RuleBasedPlanner` and record WHY in `last_notes`, which the Director copies
into `plan.notes`. A silent fallback would mean the model could be down for a week and every
plan would still look like it came from the model.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.services import role_registry

from .capabilities import ACTUATORS, get as get_actuator, known
from .memory import WorkingMemory
from .plan import Step
from .planner import RuleBasedPlanner

PLANNER_GROQ = "groq"

#: ROLES-001 — the role this planner fills. The "one model choice, one place to change it"
#: intention that `DEFAULT_MODEL` carried was right and is now actually true: the place is the
#: role registry, and it covers the other seven thinkers too.
ROLE = "step_planner"

#: Retained as a module name because the argument planner and the tests read it. It is the role's
#: SHIPPED default — the live binding is `role_registry.model_for(ROLE)`, which is what the
#: planner actually calls with.
DEFAULT_MODEL = role_registry.ROLES[ROLE].default_model

# A plan longer than this is not a plan, it is the model free-associating. The cap is applied
# after parsing and the overflow is REPORTED, never trimmed silently.
MAX_STEPS = 8

SYSTEM_PROMPT = (
    "You are a planning component inside a visual close-reading tool. You translate a "
    "curator's intention into an ordered chain of actuator calls, chosen ONLY from a fixed "
    "list you are given. You output JSON and nothing else.\n\n"
    "Hard rules:\n"
    "- Use ONLY actuator names from the provided list. Never invent one.\n"
    "- You may set only the parameter keys listed for that actuator. Never output geometry, "
    "masks, coordinates, region ids, mark ids, or confidence values — you cannot see the "
    "image and do not possess that information.\n"
    "- Order the steps so that each step's required evidence exists by the time it runs, "
    "using what already exists plus what earlier steps produce.\n"
    "- If the intention cannot be served by these actuators, return an empty list. An empty "
    "plan is a valid and useful answer; a plausible-looking wrong plan is not.\n"
    "- Prefer short chains. Do not pad a plan with steps that were not asked for."
)


def _actuator_catalog() -> List[Dict[str, Any]]:
    """The vocabulary, as data the model must choose from.

    Sent as a structured list rather than described in prose. An actuator name is a closed
    set and should be typed as one — prose invites paraphrase, and a paraphrased name is a
    hallucination that merely looks like a typo.
    """
    rows: List[Dict[str, Any]] = []
    for name in known():
        a = ACTUATORS[name]
        rows.append({
            "actuator": name,
            "does": a.summary,
            "requires": [r.describe() for r in a.requires],
            "produces": [p.value for p in a.produces],
            "params_you_may_set": list(a.param_keys),
        })
    return rows


def build_prompt(intention: str, memory: WorkingMemory) -> str:
    """The user-side prompt: what was asked, what exists, what may be used.

    `memory.summary()` carries the COUNTS — a planner that cannot see there are zero marks
    will keep proposing `connect_marks`, and every one of those is a wasted call and a
    refusal the curator has to read past.
    """
    summary = memory.summary()
    return (
        f"CURATOR'S INTENTION:\n{intention}\n\n"
        f"WHAT ALREADY EXISTS ON THIS IMAGE (counts):\n"
        f"{json.dumps(summary['counts'], indent=2)}\n\n"
        f"CURATOR'S PHRASE (may be null; open-vocabulary actuators need one):\n"
        f"{json.dumps(summary.get('phrase'))}\n\n"
        f"WHAT CAUGHT THEIR ATTENTION (may be null):\n"
        f"{json.dumps(summary.get('first_attention'))}\n\n"
        f"AVAILABLE ACTUATORS — choose only from these:\n"
        f"{json.dumps(_actuator_catalog(), indent=2)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"steps": [{{"actuator": "<name from the list>", '
        f'"params": {{}}, "note": "<why this step, one short clause>"}}]}}\n'
        f'Return {{"steps": []}} if none of these actuators serve the intention.'
    )


def _clamp_params(actuator_name: str, raw: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Keep only params the actuator declares. Returns (kept, dropped_keys).

    Guard 2. An unknown actuator keeps nothing — it is about to be refused by name anyway,
    and carrying its invented params forward would put model-authored data into a refusal
    record where a reader might mistake it for something the system considered real.
    """
    if not isinstance(raw, dict):
        return {}, []
    actuator = get_actuator(actuator_name)
    if actuator is None:
        return {}, sorted(str(k) for k in raw.keys())
    allowed = set(actuator.param_keys)
    kept = {k: v for k, v in raw.items() if k in allowed}
    dropped = sorted(str(k) for k in raw.keys() if k not in allowed)
    return kept, dropped


def parse_steps(payload: Any) -> Tuple[List[Step], List[str]]:
    """Model JSON → Steps, plus notes about anything that had to be corrected.

    Deliberately tolerant of SHAPE and strict about CONTENT: a missing "note", an integer
    where a string belongs, params as a list instead of an object — all survivable, because
    none of them can cause a wrong action. An actuator name that is not in the vocabulary is
    NOT corrected here (guard 1); it goes to `resolve()` to be refused by name.
    """
    notes: List[str] = []
    if not isinstance(payload, dict):
        return [], ["planner returned a non-object payload"]
    raw_steps = payload.get("steps")
    if raw_steps is None and isinstance(payload.get("plan"), list):
        raw_steps = payload["plan"]           # a common near-miss worth absorbing
    if not isinstance(raw_steps, list):
        return [], ["planner returned no 'steps' list"]

    steps: List[Step] = []
    for i, row in enumerate(raw_steps):
        if not isinstance(row, dict):
            notes.append(f"step {i} was not an object and was dropped")
            continue
        name = row.get("actuator") or row.get("name")
        if not isinstance(name, str) or not name.strip():
            notes.append(f"step {i} named no actuator and was dropped")
            continue
        name = name.strip()
        params, dropped = _clamp_params(name, row.get("params"))
        if dropped:
            # Recorded, never silent: this is how you find out the model is trying to author
            # geometry, which is the failure that matters most and shows up nowhere else.
            notes.append(f"step {i} ('{name}') proposed disallowed params, dropped: "
                         f"{', '.join(dropped)}")
        note = row.get("note")
        steps.append(Step(actuator=name, params=params,
                          id=f"{PLANNER_GROQ}:{i}:{name}",
                          note=str(note) if isinstance(note, str) else ""))

    if len(steps) > MAX_STEPS:
        notes.append(f"planner proposed {len(steps)} steps; kept the first {MAX_STEPS}")
        steps = steps[:MAX_STEPS]
    return steps, notes


class GroqPlanner:
    """Groq proposes the chain. The Director still refuses what cannot run.

    `client` is injectable so the whole class is testable with no network — the CI tests
    below pass a fake and never touch the API.
    """
    name = PLANNER_GROQ

    def __init__(self, client: Any = None, *, model: Optional[str] = None,
                 fallback: Optional[Any] = None):
        self._client = client
        self._client_resolved = client is not None
        # `= DEFAULT_MODEL` as a default argument bound at DEF time, which made the env rebind
        # invisible to any planner constructed after import — i.e. all of them. None means
        # "ask the role", per access.
        self._model = model
        self.fallback = fallback if fallback is not None else RuleBasedPlanner()
        # Read by Director and copied into plan.notes, so a fallback is never silent.
        self.last_notes: Tuple[str, ...] = ()
        self.calls: int = 0            # guard 3 is observable: tests assert this is 1

    @property
    def model(self) -> Optional[str]:
        return self._model if self._model is not None else role_registry.model_for(ROLE)

    # ── client ──
    def _get_client(self) -> Any:
        """Lazy real client. Absent key is UNAVAILABLE, not a crash."""
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq
            from backend.config import settings
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    # ── the seam ──
    def propose(self, intention: str, memory: WorkingMemory) -> List[Step]:
        """One call. No loop. Falls back to rules on any failure, and says so."""
        self.last_notes = ()
        client = self._get_client()
        if client is None:
            return self._fall_back(intention, memory,
                                   "groq planner unavailable (no client or API key)")
        try:
            self.calls += 1
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": build_prompt(intention, memory)}],
                model=self.model,
                response_format={"type": "json_object"},
            )
            content = completion.choices[0].message.content
            payload = json.loads(content)
        except Exception as e:
            return self._fall_back(intention, memory, f"groq planner failed: {type(e).__name__}")

        steps, notes = parse_steps(payload)
        if not steps:
            # An empty proposal is a legitimate answer ("nothing here serves that"). It is NOT
            # a failure, so it does NOT fall back to rules — falling back would overrule the
            # model's honest refusal with a keyword guess.
            self.last_notes = tuple([f"planner: {self.name}", "the planner proposed no steps",
                                     *notes])
            return []
        self.last_notes = tuple([f"planner: {self.name}", *notes])
        return steps

    def _fall_back(self, intention: str, memory: WorkingMemory, why: str) -> List[Step]:
        steps = self.fallback.propose(intention, memory)
        self.last_notes = (
            why,
            f"fell back to {getattr(self.fallback, 'name', 'rule_based')}"
            + ("" if steps else " — which also matched nothing"),
        )
        return steps


def get_planner(name: str = "rule_based", **kwargs: Any) -> Any:
    """Select a planner by name. Unknown names get the rules, not an error.

    The Director forces whichever one through the same `resolve()`, so this choice changes
    what is PROPOSED and can never change what is allowed to run.
    """
    if (name or "").strip().lower() == PLANNER_GROQ:
        return GroqPlanner(**kwargs)
    return RuleBasedPlanner()
