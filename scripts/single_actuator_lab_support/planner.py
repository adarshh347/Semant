"""Arm C's mind: a one-call planner that can see exactly one tool.

WHY NOT THE PRODUCTION `GroqPlanner` UNMODIFIED. It builds its catalogue from `known()` — all
twenty actuators. Handing a locked lab a planner that can see twenty tools and then filtering
its answer would measure the filter, not the planner: the interesting question is what a mind
proposes when `concept_segment` is the only thing it has, and that question requires the
catalogue itself to be one entry long.

WHAT IS REUSED, DELIBERATELY. `groq_planner.parse_steps` does the parsing, the param clamping
against the production declaration, the step-id minting and the note-keeping — including the
rule that an unknown actuator name is passed through VERBATIM rather than filtered, so it is
refused by name where a reader can see it. Rewriting that would have produced a second, softer
copy of the discipline, and the softer copy is always the one that drifts.

WHAT IS NOT REUSED. The catalogue, and the one-call ceiling: the lab's budget is 1, not 8. An
orchestration framework never broadens the lock.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

OK = "ok"
UNAVAILABLE = "unavailable"
DETERMINISTIC = "deterministic_framer"
ERROR = "error"
EMPTY = "empty"

#: The frozen prompt→phrase mapping behind `--deterministic-framer`. Explicit, tiny, and it
#: NEVER runs by default: an unavailable model must record `planner_unavailable`, because
#: quietly substituting a good phrase would make an orchestration failure look like an
#: orchestration success — the single most misleading thing this lab could do.
DETERMINISTIC_FRAMES = (
    (("fold", "drapery", "robe", "cloth"), "drapery fold"),
    (("hand", "gesture"), "raised hand"),
    (("face", "head"), "face"),
)
DETERMINISTIC_FALLBACK = None       # no keyword matched → no phrase, and it says so


SYSTEM_PROMPT = (
    "You are a planning component inside a visual close-reading laboratory. You translate a "
    "curator's intention into AT MOST ONE actuator call, chosen ONLY from the single-entry "
    "list you are given. You output JSON and nothing else.\n\n"
    "Hard rules:\n"
    "- You have exactly ONE tool. Use its name exactly, or return no steps at all.\n"
    "- You may set only the parameter keys listed for that actuator. Never output geometry, "
    "masks, coordinates, region ids, mark ids, or confidence values — you cannot see the "
    "image and do not possess that information.\n"
    "- You may return AT MOST ONE step. A second step cannot run.\n"
    "- If the intention cannot be served by this actuator, return an empty list. An empty "
    "plan is a valid and useful answer; a plausible-looking wrong plan is not.\n"
    "- A phrase must be something CONCRETE and VISIBLE that a segmentation model could find in "
    "one photograph. Abstract nouns, comparisons between images, and speculative styles are "
    "not things this tool can measure."
)


@dataclass
class Proposal:
    """What the planner came back with, before the firewall judges it."""
    status: str
    steps: List[Any] = field(default_factory=list)
    raw: Any = None
    model: Optional[str] = None
    role: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    detail: Optional[str] = None
    #: Params the PRODUCTION clamp removed, as structure rather than as prose.
    #:
    #: `parse_steps` records them in a human-readable note and hands back already-clean steps,
    #: so by the time the firewall sees a step there is nothing left to drop and its structured
    #: `dropped_params` would sit empty while the run's most interesting fact — the planner
    #: trying to author geometry — survived only inside a sentence. Recovered here from the raw
    #: payload, using the production clamp, so one rule produces both records.
    dropped: List[Dict[str, Any]] = field(default_factory=list)


def build_prompt(prompt: str, catalogue: List[Dict[str, Any]]) -> str:
    """The user-side prompt. The catalogue is passed in from the FIREWALL, never rebuilt here —
    the one place that decides what the planner may see is the one place that holds the lock."""
    return (
        f"CURATOR'S PROMPT (verbatim):\n{prompt}\n\n"
        f"THE ONLY ACTUATOR YOU HAVE:\n{json.dumps(catalogue, indent=2)}\n\n"
        f"Return JSON of exactly this shape:\n"
        f'{{"steps": [{{"actuator": "<the name above>", "params": {{"phrase": "<one concrete '
        f'visible thing>"}}, "note": "<why this phrase, one short clause>"}}]}}\n'
        f'Return {{"steps": []}} if this actuator cannot serve the prompt.'
    )


def _deterministic(prompt: str, lock: str) -> Proposal:
    from backend.services.director.plan import Step
    text = (prompt or "").lower()
    phrase = DETERMINISTIC_FALLBACK
    for keywords, candidate in DETERMINISTIC_FRAMES:
        if any(k in text for k in keywords):
            phrase = candidate
            break
    if not phrase:
        return Proposal(status=EMPTY, raw=None, notes=["deterministic framer matched no frame"],
                        detail="the frozen mapping has no frame for this prompt")
    step = Step(actuator=lock, params={"phrase": phrase}, id="lab:0:" + lock,
                note="deterministic framer")
    return Proposal(status=DETERMINISTIC, steps=[step],
                    raw={"steps": [{"actuator": lock, "params": {"phrase": phrase}}]},
                    notes=["phrase came from the frozen deterministic framer, not a model"],
                    detail="deterministic framer")


def propose(prompt: str, *, firewall: Any, client: Any = None, model: Optional[str] = None,
            deterministic: bool = False) -> Proposal:
    """One call. No loop. No fallback to the control phrase.

    The no-fallback rule is the whole reason Arm C can be believed. `GroqPlanner` falls back to
    the rule-based planner when the model is down, which is right for production — a curator
    wants their plan. It is wrong here: the measurement IS whether the model could name a
    useful phrase, and answering that question with a phrase from somewhere else would report
    a capability the system does not have.
    """
    from backend.services import role_registry
    from backend.services.director import groq_planner

    role = groq_planner.ROLE
    if deterministic:
        p = _deterministic(prompt, firewall.lock)
        p.role = role
        return p

    if client is None:
        try:
            from groq import Groq
            from backend.config import settings
            client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            client = None
    if client is None:
        return Proposal(status=UNAVAILABLE, role=role,
                        notes=["no planner client or API key"],
                        detail="planner_unavailable: no client or API key")

    resolved = model or role_registry.model_for(role)
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_prompt(prompt, firewall.catalogue())}],
            model=resolved,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        payload = json.loads(content)
    except Exception as e:
        return Proposal(status=ERROR, model=resolved, role=role,
                        notes=[f"planner call failed: {type(e).__name__}"],
                        detail=f"{type(e).__name__}: {e}")

    # Production parsing, production clamping, production one-call discipline.
    steps, notes = groq_planner.parse_steps(payload)
    dropped = _dropped_from(payload)
    if not steps:
        return Proposal(status=EMPTY, raw=payload, model=resolved, role=role, dropped=dropped,
                        notes=list(notes) + ["the planner proposed no steps"],
                        detail="the planner declined to act with this actuator")
    return Proposal(status=OK, steps=steps, raw=payload, model=resolved, role=role,
                    dropped=dropped, notes=list(notes))


def _dropped_from(payload: Any) -> List[Dict[str, Any]]:
    """Re-derive what the production clamp removed, from the raw payload.

    Calls `groq_planner._clamp_params` rather than re-deriving the rule from `param_keys`: a
    second implementation of "which params may a planner set" would be a second thing to keep
    in step with the capability table, and it is exactly the kind of copy that agrees on the
    day it is written and disagrees a year later.
    """
    from backend.services.director import groq_planner

    out: List[Dict[str, Any]] = []
    steps = (payload or {}).get("steps") if isinstance(payload, dict) else None
    if not isinstance(steps, list):
        return out
    for row in steps:
        if not isinstance(row, dict):
            continue
        name = row.get("actuator") or row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        _, dropped = groq_planner._clamp_params(name.strip(), row.get("params"))
        if dropped:
            out.append({"actuator": name.strip(), "keys": dropped,
                        "reason": f"not in {name.strip()}.param_keys — a planner cannot author "
                                  f"evidence it has no way to possess"})
    return out
