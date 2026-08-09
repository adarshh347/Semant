"""
HARNESS-002B §2 — when a person is asked, and when the machine may decide alone.

THE RULE THIS MODULE IS ARRANGED AROUND. *It does not ask questions merely because uncertainty
exists.* A system that consults on everything is not more careful than one that consults on
nothing; it has moved the entire burden back onto the person while appearing deferential, and it
teaches them to click through. The Director's question gate settled this one layer down — "a
question about something already known is noise that teaches the curator to ignore questions" — and
this is the same rule at the scale of an interpretation rather than a missing phrase.

THE CLASSIFICATION LIVES IN THE CONTRACT. `contracts/inquiry-interaction.v1.json` says which kinds
always pause, which are material and which are deferrable. This module READS it. The alternative —
a dict here and a copy in the frontend — is two policies that agree until somebody edits one, and
the divergence would show up as a person not being asked something, which is the failure mode with
no symptom.

THE TIE IS THE POINT. When two options are equally recommended, or none is, auto mode does NOT pick
the first. Picking by list order is a preference nobody stated, nobody can review and nobody can
even see, and it would be indistinguishable in the record from a considered choice. Auto mode
yields an UNRESOLVED decision instead, carrying the reason — a recorded "nobody chose" rather than
an unrecorded one.

AND `reversible` MUST BE DECLARED. An option that never said whether it can be undone is not
thereby reversible. The direction of that default is where this module's honesty actually lives:
`True` would auto-choose every under-specified candidate the compiler ever emits.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Mapping, Tuple

from backend.schemas.inquiry_interaction import DecisionKind, InteractionMode
from backend.services.inquiry.contracts import load as load_contract
from backend.services.inquiry_interaction.candidates import DecisionCandidate

INTERACTION_FILE = "inquiry-interaction.v1.json"
INTERACTION_SCHEMA_VERSION = "inquiry-interaction.v1"

# ── pause classes ────────────────────────────────────────────────────────────
CLASS_ALWAYS_PAUSE = "always_pause"
CLASS_MATERIAL = "material"
CLASS_DEFERRABLE = "deferrable"

PAUSE_CLASSES: Tuple[str, ...] = (CLASS_ALWAYS_PAUSE, CLASS_MATERIAL, CLASS_DEFERRABLE)

# ── verdict outcomes ─────────────────────────────────────────────────────────
#: Three, and `unresolved` is not a quieter `pause`. A pause opens a user wait; an unresolved
#: decision closes the fork without settling it and lets the run continue. Auto mode produces the
#: second and never the first, except at a gate.
OUTCOME_AUTO = "auto"
OUTCOME_PAUSE = "pause"
OUTCOME_UNRESOLVED = "unresolved"


class PolicyContractError(RuntimeError):
    """The interaction contract is missing, or classifies a kind this code does not know."""


@lru_cache(maxsize=1)
def contract() -> Dict:
    return load_contract(INTERACTION_FILE, INTERACTION_SCHEMA_VERSION)


@lru_cache(maxsize=1)
def pause_class_of() -> Mapping[DecisionKind, str]:
    """kind → pause class, from the contract, checked for total coverage.

    A kind that the contract does not classify is a hard failure at first use rather than a silent
    default, because the plausible default (`material`, "ask about it") is wrong in exactly the
    direction that matters: an unclassified `accept_to_ledger` treated as material would be paused
    in consult and PASSED in auto.
    """
    declared = contract().get("pause_classes") or {}
    table: Dict[DecisionKind, str] = {}
    for name in PAUSE_CLASSES:
        entry = declared.get(name) or {}
        for raw in entry.get("kinds") or ():
            try:
                kind = DecisionKind(str(raw))
            except ValueError as exc:
                raise PolicyContractError(
                    f"the interaction contract classifies {raw!r} as {name!r}, which is not a "
                    f"declared decision kind") from exc
            if kind in table:
                raise PolicyContractError(
                    f"{kind.value!r} is classified both {table[kind]!r} and {name!r}; two classes "
                    f"for one kind means the policy is decided by dict iteration order")
            table[kind] = name
    missing = [k.value for k in DecisionKind if k not in table]
    if missing:
        raise PolicyContractError(
            f"the interaction contract classifies no pause class for {missing}. Every kind is "
            f"classified or none of them is trustworthy — an unclassified gate defaults to "
            f"passable, which is the one direction a default must not go.")
    return table


def pause_class(kind: DecisionKind) -> str:
    return pause_class_of()[kind]


def is_gate(kind: DecisionKind) -> bool:
    """Author-exclusive or ledger-accepting. No mode passes one, including auto."""
    return pause_class(kind) == CLASS_ALWAYS_PAUSE


@dataclass(frozen=True)
class PolicyVerdict:
    """What the policy decided about one candidate, and why in a sentence a reviewer can check."""
    outcome: str
    reason: str
    pause_class: str
    option_id: str = ""
    alternatives: Tuple[str, ...] = ()

    @property
    def chose(self) -> bool:
        return self.outcome == OUTCOME_AUTO


def _eligibility(candidate: DecisionCandidate) -> Tuple[str, str]:
    """(option_id, reason). An empty option_id means no option may be taken without the person.

    One function, used by both auto mode and consult's deferrable pass, so the two cannot drift
    into different ideas of what "safe to take alone" means.
    """
    if not candidate.options:
        return "", ("the candidate declares no options, so there is nothing to choose — a fork "
                    "with one road is not a fork")
    recommended = candidate.recommended
    if not recommended:
        return "", (f"none of the {len(candidate.options)} declared options is recommended; "
                    f"choosing among them would be a preference this system does not hold")
    if len(recommended) > 1:
        names = ", ".join(sorted(o.option_id for o in recommended))
        return "", (f"{len(recommended)} options are equally recommended ({names}). A tie broken "
                    f"by list order is a preference nobody stated and nobody can review")
    only = recommended[0]
    if only.reversible is None:
        return "", (f"option {only.option_id!r} does not declare whether it can be undone. An "
                    f"undeclared reversibility is not a yes")
    if only.reversible is False:
        return "", f"option {only.option_id!r} declares itself irreversible"
    if only.authorial:
        return "", (f"option {only.option_id!r} is author-exclusive under the action grammar; only "
                    f"a person may author it")
    if only.accepts_to_ledger:
        return "", (f"option {only.option_id!r} would accept something into the shared ledger, "
                    f"which is a curator's act and nothing else's")
    return only.option_id, (f"option {only.option_id!r} is the single recommended option, declares "
                            f"itself reversible, is not author-exclusive and accepts nothing into "
                            f"the ledger")


@dataclass(frozen=True)
class DeliberationPolicy:
    """Deterministic. Same mode, same candidate, same verdict — every time, with no state."""
    mode: InteractionMode

    def verdict(self, candidate: DecisionCandidate) -> PolicyVerdict:
        cls = pause_class(candidate.kind)
        others = tuple(o.option_id for o in candidate.options)

        if cls == CLASS_ALWAYS_PAUSE:
            return PolicyVerdict(
                outcome=OUTCOME_PAUSE, pause_class=cls, alternatives=others,
                reason=(f"{candidate.kind.value} is an author/ledger gate: it pauses in every "
                        f"mode, including auto. Authoring a public act and accepting into the "
                        f"shared ledger are the person's alone."))

        if self.mode is InteractionMode.STEP:
            return PolicyVerdict(
                outcome=OUTCOME_PAUSE, pause_class=cls, alternatives=others,
                reason=("step mode stops at every declared fork, so that a person debugging the "
                        "chain can see the ones a policy would have taken silently"))

        option_id, why = _eligibility(candidate)

        if self.mode is InteractionMode.AUTO:
            if option_id:
                return PolicyVerdict(
                    outcome=OUTCOME_AUTO, pause_class=cls, option_id=option_id,
                    alternatives=tuple(o for o in others if o != option_id),
                    reason=f"auto mode took it without asking: {why}")
            return PolicyVerdict(
                outcome=OUTCOME_UNRESOLVED, pause_class=cls, alternatives=others,
                reason=(f"auto mode left this unresolved rather than choosing: {why}"))

        # consult
        if cls == CLASS_MATERIAL:
            return PolicyVerdict(
                outcome=OUTCOME_PAUSE, pause_class=cls, alternatives=others,
                reason=(f"consult mode pauses at a material fork: two readings of "
                        f"{candidate.kind.value} would produce substantially different "
                        f"investigations, and the person's answer changes which one happens"))
        if option_id:
            return PolicyVerdict(
                outcome=OUTCOME_AUTO, pause_class=cls, option_id=option_id,
                alternatives=tuple(o for o in others if o != option_id),
                reason=(f"consult mode passed a {cls} fork with a record rather than interrupting: "
                        f"{why}"))
        return PolicyVerdict(
            outcome=OUTCOME_PAUSE, pause_class=cls, alternatives=others,
            reason=(f"consult mode would have passed this {cls} fork, but no option qualified to "
                    f"be taken alone: {why}"))


__all__ = ["DeliberationPolicy", "PolicyVerdict", "PolicyContractError",
           "OUTCOME_AUTO", "OUTCOME_PAUSE", "OUTCOME_UNRESOLVED",
           "CLASS_ALWAYS_PAUSE", "CLASS_MATERIAL", "CLASS_DEFERRABLE", "PAUSE_CLASSES",
           "contract", "pause_class", "pause_class_of", "is_gate",
           "INTERACTION_FILE", "INTERACTION_SCHEMA_VERSION"]
