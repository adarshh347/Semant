"""
CIRCUIT-003 M6 — epistemic status: HOW a produced item is known.

Every producer in this system already records WHAT made an item (`provenance`: model,
adapter, run). None of them records what KIND OF KNOWING it is. That distinction has been
implicit in the architecture from the beginning — `semantic_read` produces a READING and
never a MARK precisely because a sentence about the image is a different kind of claim than
an extent in it — but it lived in the actuator table, where nothing downstream could read it.

M6 makes it a FIELD, because M6 introduces the first producer whose output does not come
from the image at all. A historical claim about Schinkel's intent is not weak evidence; it is
a different species of evidence, and the only safe way to carry it is to say so on the item
itself.

THE FIVE STATUSES, and the boundary that matters:

    visible       the extent is present in the picture — you can point at it
    measured      computed from the image signal — a number, not an opinion
    interpretive  a reading ABOUT the image, resting on what was gathered
    sourced       from OUTSIDE the image, carrying a citation            ← the walled one
    uncertain     produced, but the producer will not vouch for which of the above

The first three are all IMAGE statuses: whatever their confidence, they were obtained by
looking at the picture. `sourced` was not. That is the wall.

WHY A WALL AND NOT A CONVENTION. The failure this prevents is laundering: a sourced claim
("Schinkel intended a civic temple") re-tagged as `visible` and thereby becoming citable as
something the picture shows. It would not look like a lie at any point — each step is a
plausible edit — and the resulting mark would be indistinguishable from one a segmenter
authored. So the transition is not discouraged, it is IMPOSSIBLE through the supported API
(`retag` refuses it) and DETECTED when someone bypasses the API and edits the dict directly
(`guard` refuses it). Both paths are tested.

The wall is deliberately one-directional and narrow: `sourced` may not become an image
status. Everything else may be sharpened or softened freely — `uncertain` → `measured` is a
producer becoming more confident about its own reading, which is nobody's business but its own.

SCOPE. M6 seeds the field and the wall. The epistemic LAYER — surfacing status in review, the
UI, filtering a composition by what kind of knowing it rests on — is M5, which generalizes
`guard()` from "the research actuator's output" to "everything entering the quarantine".

PURE MODULE. No database, no network, no model. It is a vocabulary and two guards.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class EpistemicStatus(str, Enum):
    """How an item is known. A `str` enum so a descriptor stays plain JSON."""
    VISIBLE = "visible"            # an extent present in the picture
    MEASURED = "measured"          # computed from the image signal
    INTERPRETIVE = "interpretive"  # a reading about the image
    SOURCED = "sourced"            # from outside the image, with a citation
    UNCERTAIN = "uncertain"        # the producer will not vouch for a kind


#: The statuses obtainable BY LOOKING AT THE IMAGE. `sourced` is the one that is not, and
#: this set is the whole definition of the wall: nothing may cross from `sourced` into here.
IMAGE_STATUSES = frozenset({
    EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED,
    EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN,
})

#: The status that may never be overwritten. A set of one, named rather than hardcoded,
#: because M5 will likely add a second (a curator's own testimony is not image-derived either).
WALLED_STATUSES = frozenset({EpistemicStatus.SOURCED})

#: The descriptor `type` a sourced statement travels as. It is NOT a mark type — the mark
#: types are region_mask / brush_field / trace_mark / relation_mark, and a sourced statement
#: is deliberately none of them so that `_quarantined_marks()` in the Director's runner cannot
#: pick one up and feed it to `connect_marks` as if it were evidence on the image.
SOURCED_STATEMENT_TYPE = "sourced_statement"

#: The descriptor key. One string, defined once, so a rename cannot half-happen.
STATUS_KEY = "epistemic_status"


class EpistemicViolation(Exception):
    """An attempt to move a claim across the wall, or to publish one that already crossed.

    An exception rather than a returned error because there is no sensible way to continue.
    A caller that gets this has a bug that would otherwise ship a laundered claim, and the
    only correct handling is to stop.
    """


# ── the wall ─────────────────────────────────────────────────────────────────

def _coerce(status: Any) -> Optional[EpistemicStatus]:
    """A status value in any accepted form → the enum member, or None if unrecognised."""
    if isinstance(status, EpistemicStatus):
        return status
    try:
        return EpistemicStatus(str(status))
    except (ValueError, TypeError):
        return None


def retag(descriptor: Dict[str, Any], status: EpistemicStatus) -> Dict[str, Any]:
    """Change an item's epistemic status. The ONLY supported way to do so.

    Refuses to move a walled status (`sourced`) to anything else. Returns a NEW descriptor —
    the original is left alone, so a caller holding the pre-edit item still holds the truth
    about what the producer actually claimed.
    """
    target = _coerce(status)
    if target is None:
        raise EpistemicViolation(f"'{status}' is not an epistemic status")
    current = _coerce(descriptor.get(STATUS_KEY))
    if current in WALLED_STATUSES and target is not current:
        raise EpistemicViolation(
            f"cannot retag a '{current.value}' claim as '{target.value}': a claim from outside "
            f"the image can never become one the image shows")
    return {**descriptor, STATUS_KEY: target.value}


def guard(descriptors: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Verify a batch of descriptors before it enters the quarantine. Returns them unchanged.

    Catches the bypass `retag` cannot: a plain dict whose status key was edited in place. Three
    ways a descriptor fails, all of them the same underlying error — a claim presenting itself
    as better-founded than it is:

      1. a `sourced_statement` carrying any status other than `sourced`
      2. a `sourced_statement` with no citation (see `external_source_service`: no source, no
         claim — the research twin of "no ground → no mark")
      3. any descriptor carrying an unrecognised status string

    Raising rather than filtering is deliberate. A silently dropped laundered claim is a bug
    nobody investigates; a raised one is a bug someone fixes.
    """
    out: List[Dict[str, Any]] = []
    for d in descriptors:
        status = _coerce(d.get(STATUS_KEY))
        if d.get(STATUS_KEY) is not None and status is None:
            raise EpistemicViolation(f"unknown epistemic status {d.get(STATUS_KEY)!r}")
        if d.get("type") == SOURCED_STATEMENT_TYPE:
            if status is not EpistemicStatus.SOURCED:
                raise EpistemicViolation(
                    f"a sourced statement is tagged '{d.get(STATUS_KEY)}' — it may only be "
                    f"'{EpistemicStatus.SOURCED.value}'")
            if not (d.get("citation") or {}).get("url"):
                raise EpistemicViolation("a sourced statement with no citation is not sourced")
        out.append(d)
    return out


# ── defaults for the producers that already exist ────────────────────────────
# Deliberately keyed on the FROZEN producer vocabulary (the `PRODUCER_*` constants in
# `suggestion_service`), not on the descriptor `type`. Two producers can share a type and
# differ in kind: `negative_space` and `material_field` are both `brush_field`, but one
# inverts a mask that already exists and the other reads a learned embedding. Both happen to
# be `measured` today; keying on the producer is what leaves room for them not to be.

_DEFAULTS: Dict[str, EpistemicStatus] = {
    # -- extents: something is there and you can point at it --------------------
    "sam_refine": EpistemicStatus.VISIBLE,
    "florence_find_parts": EpistemicStatus.VISIBLE,
    "grounded_sam_find_parts": EpistemicStatus.VISIBLE,
    "find_similar": EpistemicStatus.VISIBLE,      # a real extent, on another image
    # -- measurements: computed off the signal, no opinion in them --------------
    "negative_space": EpistemicStatus.MEASURED,
    "material_field": EpistemicStatus.MEASURED,
    "rhythm": EpistemicStatus.MEASURED,
    "pressure_zone": EpistemicStatus.MEASURED,
    "recession": EpistemicStatus.MEASURED,
    "shading": EpistemicStatus.MEASURED,
    "fall_of_light": EpistemicStatus.MEASURED,
    "architectural_axis": EpistemicStatus.MEASURED,
    "external_limit": EpistemicStatus.MEASURED,
    # -- readings: a claim ABOUT the picture, resting on it ---------------------
    # `semantic_read` mints both label proposals and relations, and both are the VLM's reading
    # rather than the image's testimony — a naming is an interpretation even when the extent
    # it names is `visible`.
    "semantic_read": EpistemicStatus.INTERPRETIVE,
    "presence_check": EpistemicStatus.INTERPRETIVE,
    "enumerate": EpistemicStatus.INTERPRETIVE,
    "connect_marks": EpistemicStatus.INTERPRETIVE,
    "compose_percept": EpistemicStatus.INTERPRETIVE,
    "planner": EpistemicStatus.INTERPRETIVE,      # percept drafts
    # -- from outside the image -------------------------------------------------
    "historical_source": EpistemicStatus.SOURCED,
}


def default_status_for(producer: Optional[str]) -> EpistemicStatus:
    """The status a producer's output carries unless it says otherwise.

    An UNKNOWN producer gets `uncertain`, never a flattering guess. A producer wired after
    this table was written is exactly the case where a confident default would be wrong, and
    `uncertain` is both honest and loud enough to get the table updated.
    """
    return _DEFAULTS.get(str(producer or ""), EpistemicStatus.UNCERTAIN)


def stamp(descriptor: Dict[str, Any], *,
          status: Optional[EpistemicStatus] = None) -> Dict[str, Any]:
    """Set a descriptor's status in place and return it — for producers building a new item.

    Unlike `retag` this is a first write, so there is nothing to launder: it refuses to
    overwrite an existing status at all, walled or not. A producer that has already declared
    its epistemic kind is not second-guessed by the plumbing.
    """
    if descriptor.get(STATUS_KEY) is not None:
        return descriptor
    chosen = status or default_status_for(descriptor.get("producer"))
    descriptor[STATUS_KEY] = EpistemicStatus(chosen).value
    return descriptor
