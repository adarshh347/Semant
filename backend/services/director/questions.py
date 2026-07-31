"""
CIRCUIT-002 A2 — a question as a first-class, honest output of the planner.

A1-FIX gave the loop two ways to meet a closed door, and both are correct:

    MISSING INPUT  something the models can still produce. The loop produces it, the door
                   re-opens, work continues. No one needs to be asked anything.
    MISSING PARAM  a phrase the curator did not give. No amount of looking at the picture
                   supplies it, so the door never re-opens and the loop dead-ends.

That second case is where a loop stops being useful and starts being merely correct. The
system knows exactly what it needs, knows no amount of further looking will produce it, and
knows a human could supply it in four words — and says nothing. A2 gives it the fourth mode:
ASK.

WHY THIS IS AN HONESTY FEATURE AND NOT A CONVENIENCE. The alternative to asking is guessing.
A planner that needs a phrase and has none can always invent a plausible one — "the drapery",
"the figure" — and every downstream receipt would be immaculate: real model, real mask, real
confidence, attached to a question nobody asked. Asking is how the system declines to invent
the one thing it cannot know. So the guard that matters most is not that questions are
well-formed; it is that an UNANSWERED question yields a refusal, never a fabricated param.

WHEN IT MAY ASK — all three, or it stays quiet:

  1. UNRESOLVABLE FROM MEMORY. If the packet already supplies the phrase, the step is not
     refused at all and there is nothing to ask about. A question about something already
     known is noise that teaches the curator to ignore questions.
  2. A HUMAN COULD ACTUALLY UNBLOCK IT. Only a missing PARAM qualifies. A missing-input door
     is the loop's own work to do, and asking "please produce some marks for me" would push
     labour back onto the curator that the machine is standing right next to.
  3. GROUNDED IN WHAT EXISTS. The question names real options — the parts actually found, the
     thing the curator already said caught them. "Which window — the leftmost, or the lit one
     you marked?" is answerable. "What would you like me to look for?" is fishing: it moves
     the entire burden back to the human while appearing helpful, and it is the shape a
     question takes when the system has not bothered to look first.

A2 EMITS AND RETURNS. Carrying an answer back into a resumed loop is A3; this gate stops at
`awaiting_answer` with the question on the receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .capabilities import get as get_actuator
from .memory import WorkingMemory
from .plan import REFUSED_MISSING_PARAM, Step

# The most a question may offer before it stops being a choice and becomes a list.
MAX_OPTIONS = 5


@dataclass(frozen=True)
class Question:
    """A grounded clarification the loop needs answered to continue.

    `missing_param` is the machine-readable half — A3 will use it to route an answer back into
    the step that was blocked. `text` is the human half. `options` are REAL: every one refers to
    something that exists in the packet, so an empty `options` is meaningful (nothing has been
    found yet to point at) rather than an omission.
    """
    step_id: str
    actuator: str
    missing_param: str
    text: str
    options: Tuple[str, ...] = ()
    grounded_in: Dict[str, Any] = field(default_factory=dict)
    round_index: int = 0

    @property
    def is_grounded(self) -> bool:
        """A question is grounded when it names the act it is blocking. Options strengthen it but
        are not required — an image with nothing found yet still supports "what should I look
        for, in this picture you said is about X" without inventing options to offer."""
        return bool(self.actuator and self.missing_param and self.text)

    def to_dict(self) -> Dict[str, Any]:
        return {"step_id": self.step_id, "actuator": self.actuator,
                "missing_param": self.missing_param, "text": self.text,
                "options": list(self.options), "grounded_in": dict(self.grounded_in),
                "round": self.round_index}


@dataclass(frozen=True)
class Proposal:
    """What a planner returns. `steps` alone is the ordinary case; `question` lets a planner that
    already knows it is stuck say so instead of proposing something it cannot run.

    Kept a separate type rather than a tuple so `propose()` can keep returning a bare list — the
    loop normalises both, and no existing planner has to change to keep working.
    """
    steps: List[Step] = field(default_factory=list)
    question: Optional[Question] = None

    @classmethod
    def of(cls, value: Any) -> "Proposal":
        """Normalise whatever a planner returned. A bare list is the pre-A2 contract."""
        if isinstance(value, Proposal):
            return value
        return cls(steps=list(value or []))


# ── grounding ────────────────────────────────────────────────────────────────

def default_options(memory: WorkingMemory, *,
                    labels: Optional[Sequence[str]] = None) -> Tuple[str, ...]:
    """Real things the curator could point at, drawn from what actually exists.

    `labels` is how a live run supplies real region names (the executor's context has them;
    working memory carries only counts and ids). Without it this falls back to the packet's own
    contents — never to invented examples, because an invented option is a suggestion the system
    has no basis for and the curator has no way to tell apart from a found one.
    """
    out: List[str] = []
    for lab in (labels or ()):
        text = str(lab).strip()
        if text and text not in out:
            out.append(text)
    if not out:
        # No names available: offer the ids that DO exist rather than nothing, so the curator can
        # at least see how much has been found.
        out.extend(str(r) for r in memory.region_ids[:MAX_OPTIONS])
    return tuple(out[:MAX_OPTIONS])


def _phrase_question(actuator: str, options: Tuple[str, ...],
                     memory: WorkingMemory) -> str:
    """The sentence: name the act being blocked, then the real options, then stop.

    The act is quoted rather than folded into the grammar, because an actuator summary may
    itself be a question ("Is the named thing actually there?") and splicing that into an
    infinitive produces nonsense. Quoting is robust to both shapes and keeps the curator's own
    vocabulary intact.
    """
    act = get_actuator(actuator)
    doing = (act.summary if act else actuator).strip().rstrip(".")
    caught = (memory.first_attention or "").strip()
    lead = f"To answer “{doing}” I need to know what to look for."
    if options:
        listed = ", ".join(f"“{o}”" for o in options[:-1])
        tail = f"“{options[-1]}”"
        choice = f"{listed} or {tail}" if listed else tail
        return f"{lead} You have already found {choice} — which of those, or something else?"
    if caught:
        return f"{lead} You said what caught you was “{caught}” — is that what I should find?"
    # Nothing found and nothing said: state the gap plainly rather than dressing it as a choice.
    return f"{lead} Nothing has been found on this image yet, so there is nothing to point at."


def question_for(step: Step, memory: WorkingMemory, *, missing_param: str,
                 round_index: int = 0, labels: Optional[Sequence[str]] = None,
                 step_id: str = "") -> Optional[Question]:
    """Build the grounded question for a step blocked on a missing param, or None.

    Returns None when the param is NOT missing — the first honesty guard, enforced here rather
    than trusted to the caller, because a question asked about something already supplied is the
    cheapest way to make a curator stop reading questions.
    """
    if not missing_param:
        return None
    on_step = str((step.params or {}).get(missing_param) or "").strip()
    on_memory = str(getattr(memory, missing_param, "") or "").strip()
    if on_step or on_memory:
        return None                     # already answerable — do not ask

    options = default_options(memory, labels=labels)
    return Question(
        step_id=step_id or step.id or step.actuator,
        actuator=step.actuator,
        missing_param=missing_param,
        text=_phrase_question(step.actuator, options, memory),
        options=options,
        # What the question was built from, so a reader can check it was grounded in real
        # contents rather than in the model's imagination.
        grounded_in={"regions": len(memory.region_ids), "marks": len(memory.mark_ids),
                     "first_attention": memory.first_attention,
                     "options_from": "labels" if labels else "packet"},
        round_index=round_index,
    )


def missing_param_of(step: Step, memory: WorkingMemory) -> Optional[str]:
    """Which param this step is missing, or None if it is not missing one.

    Delegates to the resolver's own check rather than re-deriving it, so "missing param" means
    exactly what `resolve()` refuses for and the two cannot drift apart.
    """
    from .plan import _missing_param
    actuator = get_actuator(step.actuator)
    if actuator is None:
        return None
    return _missing_param(actuator, step, memory)


def is_question_able(reason: str) -> bool:
    """Only a missing PARAM is worth asking about.

    A missing-input door is the loop's own work — it has the models to produce marks, and
    turning that into a question would hand the curator a job the machine is standing next to.
    An unknown actuator is a planner bug, not a gap in what the curator told us.
    """
    return reason == REFUSED_MISSING_PARAM
