"""
CIRCUIT-001 ORCH-001 — working memory: the packet every step is handed.

The rule this exists to enforce: **no actuator fires blind.** A step that does not know
what has already been found will re-find it, contradict it, or ask the curator something
they already answered. The packet is how a plan carries its own context forward.

RELATION TO THE FRONTEND SESSION. `frontend/src/orchestration/orchestrationSession.js`
(P2C-OS) assembles the same idea on the client: image, selection, writing, evidence,
constraints, frozen before dispatch. This is its backend counterpart and it deliberately
borrows that module's vocabulary and its honesty invariants rather than inventing new ones.
It does NOT import from it, and ORCH-001 does not modify it — surfacing is a later gate.

The invariants worth restating here, because they are the ones a refactor destroys first:

  - `unreadable[]` names everything asked for and NOT obtained. Silence must never be
    readable as absence. A step that could not read the marks records that here; it does
    not quietly proceed with zero.
  - Counts come from what was actually loaded, never from a cached total. `available()`
    is derived, so it cannot drift from the contents.
  - The packet is a SNAPSHOT plus a projection. `evolve()` returns a NEW packet rather than
    mutating — an executed plan must be able to show what memory looked like at step 3,
    which is impossible if step 5 has already overwritten it.

PURE MODULE. No database, no fetch, no clock it is not handed. It is assembled by a caller
that has already done the reading.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .capabilities import Resource

PACKET_VERSION = 1

# A3 — the value `phrase_source` carries when the phrase came back as the answer to a question the
# loop asked, rather than on the packet the run started from.
PHRASE_FROM_ANSWER = "curator_answer"


@dataclass(frozen=True)
class WorkingMemory:
    """What the Director knows, at one moment, about one image.

    Frozen on purpose. Every step in an executed plan holds a reference to the memory it
    was run against, and those references have to stay truthful after the run finishes.
    """
    image_ref: str
    post_id: Optional[str] = None

    # -- what has been committed -------------------------------------------------
    region_ids: Tuple[str, ...] = ()
    mark_ids: Tuple[str, ...] = ()
    ground_ids: Tuple[str, ...] = ()
    percept_ids: Tuple[str, ...] = ()

    # -- what the curator brought ------------------------------------------------
    phrase: Optional[str] = None            # their words, when they gave any
    first_attention: Optional[str] = None   # what caught them, verbatim
    # A3 — HOW the phrase arrived. None means the packet carried it: the curator typed it into
    # the workspace before anything ran. `PHRASE_FROM_ANSWER` means it arrived mid-loop, as the
    # answer to a question the loop asked. Both are the curator's words and neither is invented,
    # but they are not the same event, and anything produced from the phrase should be able to
    # say which one it was rather than have a reader assume the first.
    phrase_source: Optional[str] = None

    # -- discipline, as data -----------------------------------------------------
    # Carried as DATA and not prose, so it cannot be quietly edited by whoever writes
    # the eventual planner prompt. Same reasoning as SESSION_CONSTRAINTS.
    constraints: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_CONSTRAINTS))

    # -- honesty -----------------------------------------------------------------
    # Everything asked for and not obtained. NEVER inferred from an empty list above:
    # "no marks" and "could not read the marks" are different facts.
    unreadable: Tuple[str, ...] = ()

    version: int = PACKET_VERSION

    # ── derived view ─────────────────────────────────────────────────────────
    def available(self) -> Dict[Resource, int]:
        """Resource counts the dependency graph checks against.

        IMAGE is 1 because a packet is always about an image. PHRASE is 1 only when the
        curator actually supplied non-empty words — a blank phrase must not satisfy an
        open-vocabulary actuator's requirement, or P8-B's fabrication returns by the back
        door with an empty query.
        """
        counts: Dict[Resource, int] = {
            Resource.IMAGE: 1,
            Resource.REGION: len(self.region_ids),
            Resource.MARK: len(self.mark_ids),
            Resource.GROUND: len(self.ground_ids),
            Resource.PERCEPT: len(self.percept_ids),
            Resource.READING: 0,     # readings are never carried in as prior evidence
            # M6: nor are sources. A citation retrieved during one plan does not become part of
            # what the image is known to contain, so it is never carried IN and — because
            # `evolve()` has no bucket for it — never accumulates either.
            Resource.SOURCE: 0,
        }
        counts[Resource.PHRASE] = 1 if (self.phrase or "").strip() else 0
        return counts

    def evolve(self, produced: Sequence[Resource], *, step_id: str) -> "WorkingMemory":
        """Project the memory forward as if `produced` now exists.

        Used two ways, and the difference matters:
          - by the PLANNER, to reason about ordering before anything has run. The ids here
            are projections (`step_id#kind@n`), not real records, and they exist only so
            counts advance. They are marked with '#' precisely so nothing downstream can
            mistake one for a database id.
          - by the EXECUTOR, after a step actually succeeded.

        Returns a new packet; never mutates.
        """
        regions, marks, grounds, percepts = (list(self.region_ids), list(self.mark_ids),
                                             list(self.ground_ids), list(self.percept_ids))
        bucket = {Resource.REGION: regions, Resource.MARK: marks,
                  Resource.GROUND: grounds, Resource.PERCEPT: percepts}
        for kind in produced:
            target = bucket.get(kind)
            if target is None:
                continue            # READING, SOURCE and IMAGE add nothing to the evidence layer
            target.append(f"{step_id}#{kind.value}@{len(target)}")
        return replace(self, region_ids=tuple(regions), mark_ids=tuple(marks),
                       ground_ids=tuple(grounds), percept_ids=tuple(percepts))

    def with_unreadable(self, *what: str) -> "WorkingMemory":
        return replace(self, unreadable=tuple([*self.unreadable, *what]))

    def with_phrase(self, phrase: str, *, source: Optional[str] = None) -> "WorkingMemory":
        """The curator's words, arriving on the packet. A3's injection point.

        Structurally incapable of adding EVIDENCE, and that is the point rather than an accident
        of implementation: it touches two fields, both of them words. A phrase is the one thing a
        param may supply (`plan.availability_for`) precisely because it is the one thing that is
        the curator's to say; a region, mark, ground or percept arriving this way would be the
        fabrication the whole layer exists to prevent.

        A blank phrase is not stored. `available()` would not count it anyway, so storing it would
        put a claim on the packet that satisfies nothing — the emptiness has to stay visible.
        """
        text = (phrase or "").strip()
        if not text:
            return self
        return replace(self, phrase=text, phrase_source=source)

    def summary(self) -> Dict[str, Any]:
        """A compact, loggable view. What a step is handed as context."""
        return {
            "version": self.version,
            "image_ref": self.image_ref,
            "post_id": self.post_id,
            "counts": {k.value: v for k, v in self.available().items()},
            "phrase": self.phrase,
            "phrase_source": self.phrase_source,
            "first_attention": self.first_attention,
            "constraints": dict(self.constraints),
            "unreadable": list(self.unreadable),
        }


DEFAULT_CONSTRAINTS: Dict[str, Any] = {
    # The four carried verbatim from the frontend packet, so a session and a plan cannot
    # drift apart on what the discipline actually is.
    "image_only": True,
    "mark_external_claims": True,
    "ask_for_contradictions": True,
    "no_identity_claims": True,
    "no_fake_causality": True,
    # ORCH-001's own: a plan may never invent evidence to keep itself running.
    "no_fabrication_on_refusal": True,
}


def build_memory(*, image_ref: str, post_id: Optional[str] = None,
                 region_ids: Sequence[str] = (), mark_ids: Sequence[str] = (),
                 ground_ids: Sequence[str] = (), percept_ids: Sequence[str] = (),
                 phrase: Optional[str] = None, first_attention: Optional[str] = None,
                 phrase_source: Optional[str] = None,
                 unreadable: Sequence[str] = (),
                 constraints: Optional[Dict[str, Any]] = None) -> WorkingMemory:
    """Assemble a packet. The only supported constructor — keeps tuple coercion in one place."""
    return WorkingMemory(
        image_ref=image_ref, post_id=post_id,
        region_ids=tuple(region_ids), mark_ids=tuple(mark_ids),
        ground_ids=tuple(ground_ids), percept_ids=tuple(percept_ids),
        phrase=phrase, first_attention=first_attention, phrase_source=phrase_source,
        unreadable=tuple(unreadable),
        constraints={**DEFAULT_CONSTRAINTS, **(constraints or {})},
    )
