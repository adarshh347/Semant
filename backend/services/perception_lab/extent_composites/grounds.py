"""
PERCEPTUAL-FORMS-001G — the evidence a claim rests on, and who is allowed to vouch for it.

A GROUND IS AN ATTRIBUTION BEFORE IT IS A NUMBER. `Ground` carries a kind, a detail, citations and
an optional strength; what it does NOT carry is who measured it, and without that a cosine from a
resemblance model and a per-pixel adjacency count are two entries in one list that a reader cannot
tell apart. So this module takes `GroundEvidence` — a ground plus its attribution — checks the
attribution, and only then builds the contract record. The attribution does not survive into the
payload, and that is a real limit this lane reports rather than works around: see `attributed_to`
below.

THREE ATTRIBUTIONS, AND EACH IS ALLOWED A DIFFERENT SET OF KINDS:

    geometry        computed here, per pixel, from masks that were supplied. Shape continuity,
                    relative position, scale consistency — the three that follow from geometry
                    alone and need nothing to be believed
    human           a person said so. `human_assertion`, and nothing else, because a person
                    asserting `depth_continuity` is asserting a measurement they did not take
    model:<key>     a candidate Lane C admitted, for the kinds it was admitted for, in the ground
                    role. Everything else is refused by `admission.ground_admission`

NOTHING HERE CALLS A MODEL. A model-attributed ground arrives already measured, with the number
the adapter produced; this module checks that the adapter was allowed to produce it. The gate and
the call are two acts in two places on purpose — a gate that could also invoke is a gate that
eventually invokes to check whether it should have.

THE SOLE-GROUND RULE IS LANE C'S SENTENCE AND NOT A STRICTER ONE. "Neither may be the sole ground"
— so a hypothesis whose ONLY ground comes from a source marked `sole_ground_forbidden` is refused,
and one carrying that ground beside any other is not. This lane deliberately does not extend the
rule to "at least one non-model ground", which would have been defensible and would also have been
this lane inventing policy on top of the evidence. What it does instead is report which grounds
carry the mark, so a reviewer can apply a stricter rule with their eyes open.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.perception_lab import Ground, GroundKind, InputRef
from backend.services.perception_lab.extent_composites import admission as A
from backend.services.perception_lab.topology_forms.production import Omission

#: The two attributions that are not a model. Spelled rather than enumerated because a third one
#: would be a new kind of witness, and adding a witness should be a visible edit.
GEOMETRY = "geometry"
HUMAN = "human"
MODEL_PREFIX = "model:"

#: What geometry alone can establish, from masks that were supplied and nothing else.
GEOMETRIC_KINDS = frozenset({
    GroundKind.SHAPE_CONTINUITY,
    GroundKind.RELATIVE_POSITION,
    GroundKind.SCALE_CONSISTENCY,
})

#: What a person may assert on their own authority. Exactly one: a person saying
#: `depth_continuity` is reporting a measurement nobody took.
HUMAN_KINDS = frozenset({GroundKind.HUMAN_ASSERTION})


@dataclass(frozen=True)
class GroundEvidence:
    """One piece of evidence, with the thing that vouches for it.

    `attributed_to` IS THE FIELD `Ground` DOES NOT HAVE, and the mismatch is deliberate rather
    than hidden. The contract's record carries kind, detail, citations and strength; it has no
    place for the witness. So the witness is checked HERE, where the record is built, and the
    check's result travels on the production beside the payload. A later contract revision that
    adds `attributed_to` to `Ground` would make this carrier redundant, and until then a payload
    read alone cannot tell a cosine from a pixel count — which is in the lane report.
    """
    kind: GroundKind
    detail: str
    attributed_to: str = GEOMETRY
    strength: Optional[float] = None
    cites: Tuple[InputRef, ...] = ()

    @property
    def is_model(self) -> bool:
        return self.attributed_to.startswith(MODEL_PREFIX)

    @property
    def model_key(self) -> Optional[str]:
        return self.attributed_to[len(MODEL_PREFIX):] if self.is_model else None

    def record(self) -> Ground:
        """The contract record. Detail carries the witness in prose, since no field holds it."""
        return Ground(kind=self.kind, detail=f"[{self.attributed_to}] {self.detail}",
                      cites=list(self.cites),
                      strength=None if self.strength is None else float(self.strength))


@dataclass(frozen=True)
class Vetting:
    """The grounds that survived, the ones that did not, and which of them may not stand alone."""
    grounds: Tuple[Ground, ...]
    omitted: Tuple[Omission, ...]
    may_not_stand_alone: Tuple[str, ...]

    @property
    def only_forbidden(self) -> bool:
        """True when every surviving ground came from a source that may not be the sole ground.

        WITH ONE GROUND THIS IS LANE C'S RULE EXACTLY. With two it is a flag a reviewer reads, and
        this lane does not turn it into a refusal — see the module docstring.
        """
        return bool(self.grounds) and len(self.may_not_stand_alone) == len(self.grounds)

    @property
    def sole_forbidden_ground(self) -> bool:
        """Lane C's sentence, enforced: the ONLY ground is one that may never be the sole one."""
        return len(self.grounds) == 1 and len(self.may_not_stand_alone) == 1


def vet(evidence: Sequence[GroundEvidence], *, form_key: str, subject: str) -> Vetting:
    """Check every witness, build the records that pass, and name the ones that do not.

    A REFUSED GROUND IS DROPPED FROM THE EVIDENCE AND KEPT IN THE RECORD. Leaving it in would let
    an unadmitted model's number carry a hypothesis; leaving it out silently would make a claim
    that rested on four grounds and now rests on three look like it always rested on three.
    """
    grounds: List[Ground] = []
    omitted: List[Omission] = []
    forbidden: List[str] = []
    for item in evidence:
        if item.is_model:
            try:
                entry = A.ground_admission(str(item.model_key), item.kind, str(form_key))
            except A.ModelNotAdmitted as refused:
                omitted.append(Omission(
                    what=f"{subject}:{item.attributed_to}:{item.kind.value}",
                    reason="ground_not_admitted", detail=refused.refusal.message))
                continue
            if entry.sole_ground_forbidden:
                forbidden.append(item.attributed_to)
        elif item.attributed_to == GEOMETRY and item.kind not in GEOMETRIC_KINDS:
            omitted.append(Omission(
                what=f"{subject}:{GEOMETRY}:{item.kind.value}", reason="ground_not_admitted",
                detail=(f"geometry establishes {sorted(k.value for k in GEOMETRIC_KINDS)}. "
                        f"{item.kind.value} needs something that measured it, and a ground "
                        f"attributed to nothing is the invented witness this gate exists for.")))
            continue
        elif item.attributed_to == HUMAN and item.kind not in HUMAN_KINDS:
            omitted.append(Omission(
                what=f"{subject}:{HUMAN}:{item.kind.value}", reason="ground_not_admitted",
                detail=(f"a person may assert {sorted(k.value for k in HUMAN_KINDS)}. "
                        f"{item.kind.value} is a measurement, and asserting one is not taking "
                        f"it.")))
            continue
        elif item.attributed_to not in (GEOMETRY, HUMAN):
            omitted.append(Omission(
                what=f"{subject}:{item.attributed_to}", reason="ground_not_admitted",
                detail=(f"{item.attributed_to!r} is not a witness this laboratory knows. The "
                        f"three are {GEOMETRY!r}, {HUMAN!r} and {MODEL_PREFIX}<key>.")))
            continue
        grounds.append(item.record())
    return Vetting(grounds=tuple(grounds), omitted=tuple(omitted),
                   may_not_stand_alone=tuple(forbidden))


__all__ = ["GEOMETRIC_KINDS", "GEOMETRY", "GroundEvidence", "HUMAN", "HUMAN_KINDS",
           "MODEL_PREFIX", "Vetting", "vet"]
