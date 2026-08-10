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
from typing import Iterable, List, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (IdentityScope, InputRef, LabSession, LabSource,
                                            OrganFamily, PromptTurn, SessionMode)
from backend.services.perception_lab.clock import Clock, IdFactory


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


class SessionMachine:
    """The write side: every transition a sitting at the laboratory can make.

    ONE PLACE THAT CHANGES A SESSION, so that the reference law has one place to be broken. The
    conductor never assigns to `session.selected_artifact_ids`; it calls `select` and `deselect`,
    and the invariant those two maintain is the only reason a follow-up can be trusted.

    EVERY TRANSITION REPLACES THE RECORD RATHER THAN EDITING IT. `model_copy` costs nothing at
    this size and buys the thing that matters: a caller holding a `LabSession` it read a moment
    ago holds a value, not a window onto state that something else is changing underneath it.

    THE DESELECTION INVARIANT, which is the one worth stating out loud:

        deselecting an artifact that is ALSO the active one clears the active one.

    Without it, "select A and B, deselect A, now measure that mask" would resolve to A — an id
    the person removed, still reachable through the other field that happened to hold it. The
    person's action would have been recorded and disobeyed, which is worse than not offering it.
    """

    def __init__(self, session: LabSession, *, clock: Clock, ids: Optional[IdFactory] = None):
        self.session = session
        self._clock = clock
        self._ids = ids

    # -- opening --

    @classmethod
    def open(cls, *, source: LabSource, organ: OrganFamily, mode: SessionMode, clock: Clock,
             ids: IdFactory, session_id: Optional[str] = None) -> "SessionMachine":
        now = clock.now_iso()
        return cls(LabSession(session_id=session_id or ids.mint("labs"), source=source,
                              selected_organ=organ, mode=mode, created_at=now, updated_at=now),
                   clock=clock, ids=ids)

    def view(self) -> SessionView:
        return SessionView.of(self.session)

    def _touch(self, **update) -> LabSession:
        self.session = self.session.model_copy(
            update={**update, "updated_at": self._clock.now_iso()})
        return self.session

    # -- what is being asked, and of which organ --

    def select_organ(self, organ: OrganFamily) -> LabSession:
        """Switch organs. Selections SURVIVE, and that is not an oversight.

        The extents a person selected are exactly what a topology question consumes, so clearing
        them on the switch would make the supported path — find extents, switch, measure their
        relation — impossible to walk. What does not survive the switch is permission: the lock
        is re-applied by the resolver on the next plan, against the new organ.
        """
        return self._touch(selected_organ=organ)

    def set_mode(self, mode: SessionMode) -> LabSession:
        return self._touch(mode=mode)

    # -- what "that" and "those two" are allowed to mean --

    def select(self, *artifact_ids: str) -> LabSession:
        """Add to the selection, in order, without repeating what is already there."""
        current = list(self.session.selected_artifact_ids)
        for artifact_id in artifact_ids:
            # Appended one at a time and checked against the list AS IT GROWS. A comprehension
            # against the original list would let `select("art_a", "art_a")` through, and the pair
            # question would then measure an artifact against itself — a relation that computes
            # perfectly and answers nothing.
            if artifact_id and artifact_id not in current:
                current.append(artifact_id)
        return self._touch(selected_artifact_ids=current)

    def deselect(self, *artifact_ids: str) -> LabSession:
        """Remove from the selection, and from `active` if that is where it also was.

        See the class docstring. This is the invariant the follow-up law rests on.
        """
        removing = {a for a in artifact_ids if a}
        remaining = [a for a in self.session.selected_artifact_ids if a not in removing]
        active = self.session.active_artifact_id
        return self._touch(selected_artifact_ids=remaining,
                           active_artifact_id=None if active in removing else active)

    def clear_selection(self) -> LabSession:
        return self._touch(selected_artifact_ids=[], active_artifact_id=None)

    def activate(self, artifact_id: str) -> LabSession:
        """Make one artifact the one "that mask" means. Selecting it too, because an active
        artifact that was not in the selection would be a reference reachable from one field and
        invisible in the other."""
        current = list(self.session.selected_artifact_ids)
        if artifact_id not in current:
            current.append(artifact_id)
        return self._touch(active_artifact_id=artifact_id, selected_artifact_ids=current)

    def clear_active(self) -> LabSession:
        return self._touch(active_artifact_id=None)

    def activate_regions(self, region_ids: Sequence[str]) -> LabSession:
        """The canonical regions in play. Replaces rather than appends: a region set is a choice
        about what this sitting is about, not a history of everything ever pointed at."""
        return self._touch(active_region_ids=[r for r in region_ids if r])

    # -- the ledger of the sitting --

    def record_turn(self, text: str, *, plan_id: Optional[str] = None,
                    turn_id: Optional[str] = None) -> PromptTurn:
        """What the person said, and which plan it became. Never what the machine understood.

        `LabSession` has no field for a remembered intention, and this method adds none. A turn is
        the words plus a plan id, and a later turn resolves through ids rather than through this
        history — see the module docstring.
        """
        turn = PromptTurn(turn_id=turn_id or self._mint("turn"), text=text,
                          at=self._clock.now_iso(), plan_id=plan_id)
        self._touch(prompt_turns=list(self.session.prompt_turns) + [turn])
        return turn

    def attach_plan(self, turn_id: str, plan_id: str) -> LabSession:
        """Bind a turn to the plan it produced, once the plan has an id."""
        turns = [t.model_copy(update={"plan_id": plan_id}) if t.turn_id == turn_id else t
                 for t in self.session.prompt_turns]
        return self._touch(prompt_turns=turns)

    def record_run(self, run_id: str) -> LabSession:
        if run_id in self.session.run_ids:
            return self.session
        return self._touch(run_ids=list(self.session.run_ids) + [run_id])

    def record_review(self, review_id: str) -> LabSession:
        if review_id in self.session.review_ids:
            return self.session
        return self._touch(review_ids=list(self.session.review_ids) + [review_id])

    def _mint(self, prefix: str) -> str:
        if self._ids is None:
            raise RuntimeError("this session machine was built without an id factory and cannot "
                               "mint one. Nothing in this laboratory invents an identity.")
        return self._ids.mint(prefix)


def declared_ids(session: LabSession) -> Tuple[str, ...]:
    """Every reference this session has declared, for a refusal that wants to list them."""
    view = SessionView.of(session)
    return view.artifact_ids + view.region_ids


__all__ = ["SessionView", "SessionMachine", "declared_ids"]
