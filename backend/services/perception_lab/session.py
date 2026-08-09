"""
PERCEPTUAL-ORGANS-002 Lane D — what a session lets a plan refer to.

`LabSession` (Lane A) is the RECORD. This is the read side of it: the narrow view the resolver is
given, and the one question it may ask — "is this id something this session declared?"

WHY THE RESOLVER GETS A VIEW AND NOT THE SESSION. `LabSession` carries prompt turns, run ids,
review ids and timestamps, and the resolver has no business reading any of them. Handing it the
whole record would make "the resolver decided from the conversation" a one-line change nobody
would notice in review. It gets four id collections and a mode, and there is nothing else in the
object to decide from.

THE REFERENCE LAW, which is the whole reason this type exists:

    A step may cite only ids the session has DECLARED active or selected.
    An id from anywhere else is `unknown_reference`, never a lookup.

"that mask" is not resolved by remembering what the person probably meant. It is resolved by
`active_artifact_id`, and if nothing is active there is no mask, and the honest answer is a
refusal. A conductor that searched the store for a plausible recent artifact would be right most
of the time, and the times it was wrong would be indistinguishable from the times it was right.

PURE. No database, no network, no model, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from backend.schemas.perception_lab import (IdentityScope, InputRef, LabSession, OrganFamily,
                                            SessionMode)


@dataclass(frozen=True)
class SessionView:
    """The four id collections a plan may draw on, and the two facts that lock it.

    Frozen, and built by `of()` rather than by the resolver reaching into a session, so a resolver
    that wanted to widen what it can see would have to change this file.
    """
    session_id: str
    selected_organ: OrganFamily
    mode: SessionMode
    active_artifact_id: Optional[str] = None
    active_region_ids: Tuple[str, ...] = ()
    selected_artifact_ids: Tuple[str, ...] = ()

    @classmethod
    def of(cls, session: LabSession) -> "SessionView":
        return cls(
            session_id=session.session_id,
            selected_organ=session.selected_organ,
            mode=session.mode,
            active_artifact_id=session.active_artifact_id,
            active_region_ids=tuple(session.active_region_ids),
            selected_artifact_ids=tuple(session.selected_artifact_ids))

    # ── the declared references ──

    @property
    def artifact_ids(self) -> Tuple[str, ...]:
        """Active first, then selected, without repeating the active one.

        Order matters: a follow-up that wants ONE artifact takes the active one, and a follow-up
        that wants two takes the first two selected. Both read this list, so "which one did it
        mean" has a single answer written down in one place.
        """
        out = [self.active_artifact_id] if self.active_artifact_id else []
        out += [a for a in self.selected_artifact_ids if a != self.active_artifact_id]
        return tuple(out)

    @property
    def region_ids(self) -> Tuple[str, ...]:
        return self.active_region_ids

    def knows_artifact(self, artifact_id: str) -> bool:
        return artifact_id in self.artifact_ids

    def knows_region(self, region_id: str) -> bool:
        return region_id in self.active_region_ids

    def knows(self, ref: InputRef) -> bool:
        """Whether this session declared the thing an input ref names.

        `InputRef` has already guaranteed exactly one of the two ids is set, so there is no third
        branch here and no `else: return True` for a shape that cannot occur.
        """
        if ref.artifact_id is not None:
            return self.knows_artifact(ref.artifact_id)
        return self.knows_region(str(ref.region_id))

    def unknown(self, ref: InputRef) -> str:
        """The id that did not resolve, for the refusal message."""
        return str(ref.artifact_id if ref.artifact_id is not None else ref.region_id)

    # ── building refs, which is the only way a planner may cite anything ──

    def artifact_ref(self, role: str, artifact_id: str) -> InputRef:
        return InputRef(role=role, scope=IdentityScope.SESSION, artifact_id=artifact_id)


__all__ = ["SessionView"]
