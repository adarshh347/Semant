"""WAVE3 — the body: which organs an agent may perceive through, and what they measure from here.

An agent has no access to "the image". It has organs bound to its locus, and its world is exactly
what those organs can measure from where it stands. This module is that binding — the one place
that turns an organ NAME into either a measurement or a refusal, and never into a narration.

## Where the lane card and the tree disagree, and how this resolves it

The card says an agent's `organ_set` is "a set of organ-role ids from the role registry". The
registry's organ half is **generated from `vision_orchestrator.default_roster()`** and is pinned
that way by `test_role_registry.test_every_roster_adapter_is_a_role_and_no_role_invents_one` — its
whole point is that organ roles are never hand-listed. So the registry enumerates the organs that
LOAD WEIGHTS, and it has no room for one that does not.

`nestedness_organ` does not. It is pure geometry — no model, no residency, no GPU — and it is the
only organ in this corpus that mints a `measured` mark today. Adding it to the registry would mean
hand-listing an organ role and editing another lane's invariant to permit it, from this lane. So
the resolution runs the other way: this module asks the registry FIRST, treats a roster organ as
real-but-not-invocable-here, and keeps its own small table of the organs that execute in-process.

Three outcomes, and the middle one is the one worth having:

    RESOLVED     a pure-python organ this lane can invoke              → a measurement
    RESIDENT     a real registry organ role, residency-managed         → refused, WITH ITS REASON
    UNKNOWN      neither                                              → refused

A `RESIDENT` refusal is not a failure to find something. It is the system saying "that is a real
organ, it is not mine to start, and an agent that shares organs sequentially will invoke it
through the manager when that lane exists." Collapsing it into `UNKNOWN` would make a correct
organ name look like a typo, which is the kind of quiet wrongness this project keeps closing.

## WAVE2.5 — what a reading is worth is the organ's to say, not this lane's

A box is an estimate of an extent; a mask is a measurement of one. `nestedness_organ` now derives
each mark's status from its basis, and this module passes that through without opinion. The
consequence for an agent is small and it is not a filter: an inadmissible reading is still
something it genuinely perceived from here, so it stays in the percept field carrying
`admissible=False`. A body that discarded its own estimates would report a smaller world than it
has; what an estimate may never do is pass itself off as a measurement.

## The one thing this module may never do

Ask a language model. There is nothing to import here that could, and
`test_situated_agent_wave3.py` asserts it structurally over the whole package rather than trusting
this sentence. A situated agent is the richest place for confabulation to hide precisely because
"I, standing here, experienced X" is such a persuasive sentence; the defence is that the module
which produces those sentences has no way to generate one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services import adjacency_organ as adjacency
from backend.services import nestedness_organ as nestedness
from backend.services import role_registry
from backend.services.epistemics import STATUS_KEY, EpistemicStatus
from backend.services.role_registry import RoleKind

#: The organs this lane can actually invoke, in-process, with no weights to load.
#:
#: Two now, and the second was not optional. The dialogue lane needs two agents at one locus to
#: enact two WORLDS; with one organ between them they enact the same world twice and their
#: "disagreement" is a difference in bookkeeping. Every registry organ loads weights and resolves
#: RESIDENT here, so `adjacency_organ` was built for it — boundary contact, which is independent of
#: containment in both directions (`test_agent_dialogue_wave3.py` pins the 2×2).
PURE_PYTHON_ORGANS: Tuple[str, ...] = (nestedness.ORGAN, adjacency.ORGAN)

#: How an organ name resolved. Named constants because the refusal reason is reported to a human
#: and read by a test, and a bare string in both places is two spellings waiting to happen.
RESOLVED = "resolved"
RESIDENT = "resident"
UNKNOWN = "unknown"


class OrganRefusal(Exception):
    """This organ cannot perceive from this locus. Raised, never returned as an empty field.

    An empty `percept_field` means "the organ looked from here and measured nothing", which is a
    real and interesting fact about a locus. This means "no organ looked", which is not a fact
    about the locus at all. An agent that could not tell those apart would report an unmeasured
    world as a measured emptiness.
    """


@dataclass(frozen=True)
class OrganBinding:
    """An organ name, resolved. Says what it is and whether this lane may invoke it."""
    name: str
    resolution: str
    invocable: bool
    detail: str
    #: The registry role behind it, when there is one. `None` for a pure-python organ, and that
    #: absence is a fact about the registry (see the module note), not a missing lookup.
    role: Optional[role_registry.Role] = None


@dataclass(frozen=True)
class OrganReading:
    """One reading an organ took from the agent's locus.

    `mark` is the organ's own grounding mark — RETURNED, never committed. Committing it to a post
    is a curator's act and this wave performs none.

    `epistemic_status` is read off that mark rather than restated here, and under the WAVE2.5
    ruling it is no longer always `measured`: the organ derives it from the BASIS, so a mask-basis
    reading is `measured` and a box-basis one is `interpretive`. That is why nothing in this lane
    names a status of its own — the organ is the only thing entitled to say what kind of knowing
    its output is, and a second copy here would be a second place for it to be wrong.
    """
    organ: str
    relation: str
    #: `within` — the locus is the part; `contains` — the locus is the whole. Both are measurements
    #: made FROM the locus: it is one of the two terms either way. See `_readings_from`.
    direction: str
    locus_region_id: str
    other_region_id: str
    measurement: Dict[str, Any]
    mark: Dict[str, Any]
    detail: str

    @property
    def epistemic_status(self) -> str:
        return str(self.mark.get(STATUS_KEY) or "")

    @property
    def basis(self) -> str:
        return str(self.measurement.get("basis") or "")

    @property
    def admissible(self) -> bool:
        """WAVE2.5 — may this reading ground a measured claim, or only propose one?

        Asked of the organ rather than answered here (`nestedness.is_admissible`). It is not a
        quality threshold: a box containment of 1.000 is inadmissible while a mask containment of
        0.96 is admitted, because the question is what kind of thing the number is.

        An agent keeps its inadmissible readings — they are genuinely what it perceived from here,
        and a body that discarded its own estimates would be reporting a smaller world than it has.
        What they may never do is pass themselves off as measurements, which is why this is a
        field on every reading rather than a filter on the field.
        """
        return nestedness.is_admissible(self.measurement)


def resolve(organ_name: str) -> OrganBinding:
    """An organ name → what it is. Never raises; the refusal is the return value.

    Resolution is a question an agent asks about its own body before it tries to use it, and the
    answer "that is a real organ I cannot start" has to be inspectable rather than thrown.
    """
    name = str(organ_name or "")
    role = role_registry.get(name)

    if name in PURE_PYTHON_ORGANS:
        return OrganBinding(
            name=name, resolution=RESOLVED, invocable=True, role=role,
            detail=f"{name} — pure geometry, computed in-process from the segmenter's own output")

    if role is not None and role.kind is RoleKind.ORGAN:
        return OrganBinding(
            name=name, resolution=RESIDENT, invocable=False, role=role,
            detail=(f"{name} is a real organ role ({role.capability}, ceiling "
                    f"{role.epistemic_ceiling.value}) but it loads weights and is residency-"
                    f"managed. This wave invokes no resident organ: agents share organs "
                    f"sequentially through the manager, and that is the movement lane's work."))

    if role is not None:
        return OrganBinding(
            name=name, resolution=UNKNOWN, invocable=False, role=role,
            detail=(f"{name} is a {role.kind.value}, not an organ. A thinker reads; it does not "
                    f"measure, and an agent perceiving through one would be narrating."))

    return OrganBinding(
        name=name, resolution=UNKNOWN, invocable=False,
        detail=f"no organ named {name!r} — neither a registry role nor a pure-python organ")


def assert_invocable(organ_name: str) -> OrganBinding:
    """Resolve, and refuse loudly if this lane cannot perceive through it."""
    binding = resolve(organ_name)
    if not binding.invocable:
        raise OrganRefusal(binding.detail)
    return binding


# ── invocation ───────────────────────────────────────────────────────────────

def _region(post: Mapping[str, Any], region_id: str) -> Optional[Dict[str, Any]]:
    for r in post.get("region_annotations") or []:
        if isinstance(r, Mapping) and str(r.get("id")) == str(region_id):
            return dict(r)
    return None


def _regions(post: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(r) for r in (post.get("region_annotations") or []) if isinstance(r, Mapping)]


def _adjacency_readings(locus_region: Mapping[str, Any], others: Sequence[Mapping[str, Any]], *,
                        post_id: str, step_id: str, now: str) -> List[OrganReading]:
    """Every meeting the adjacency organ can measure FROM THE LOCUS. A different world, same place.

    One direction only, and that is a fact about the measurement rather than a simplification:
    `contact_fraction` is normalized by the FIRST region's boundary, so `measure(locus, other)`
    answers "how much of MY edge lies against that one" — which is the only version of the question
    an agent standing here can ask. The reciprocal is a fact about the other region's boundary, and
    an agent that reported it would be speaking for somewhere it is not.
    """
    out: List[OrganReading] = []
    locus_id = str(locus_region.get("id") or "")

    for other in others:
        other_id = str(other.get("id") or "")
        if not other_id or other_id == locus_id:
            continue
        try:
            measurement = adjacency.measure(locus_region, other)
        except adjacency.AdjacencyRefusal:
            continue
        if not measurement["adjacent"]:
            continue
        out.append(OrganReading(
            organ=adjacency.ORGAN,
            relation=adjacency.RELATION_MEETS,
            direction="meets",
            locus_region_id=locus_id,
            other_region_id=other_id,
            measurement=measurement,
            mark=adjacency.grounding_mark(measurement, post_id=post_id,
                                          step_id=step_id, now=now),
            detail=measurement["detail"]))

    out.sort(key=lambda r: -r.measurement["contact_fraction"])
    return out


def _readings_from(locus_region: Mapping[str, Any], others: Sequence[Mapping[str, Any]], *,
                   post_id: str, step_id: str, now: str) -> List[OrganReading]:
    """Every nesting the organ can measure WITH THE LOCUS AS ONE OF ITS TERMS.

    THIS IS THE SITUATEDNESS, and it is a constraint rather than a description. `find_nested_pairs`
    sweeps a post n² and reports every nesting in the image — that is the god's-eye reading the
    movement kernel needs and an agent must never have. A pair between two regions the agent is not
    standing on is not knowledge it could have from here, and an agent that returned one would be
    reporting the image rather than its position in it.

    So both directions are measured and neither is invented: `within` (the locus is the part) and
    `contains` (the locus is the whole) are the two ways the locus can be a term. Both are
    computed by the same organ from the same geometry; only the argument order differs.

    `test_situated_agent_wave3.py` pins the constraint from the other side — it plants a nesting
    between two non-locus regions and asserts the agent cannot see it.
    """
    out: List[OrganReading] = []
    locus_id = str(locus_region.get("id") or "")

    for other in others:
        other_id = str(other.get("id") or "")
        if not other_id or other_id == locus_id:
            continue
        for direction, inner, outer in (("within", locus_region, other),
                                        ("contains", other, locus_region)):
            try:
                measurement = nestedness.measure(inner, outer)
            except nestedness.NestednessRefusal:
                # Skipped silently, and the caller can see it: the reading count against the region
                # count is the coverage claim. A refusal per unmeasurable pair would be noise, and
                # `nestedness_organ.find_nested_pairs` already documents the same choice.
                continue
            if not measurement["nested"]:
                continue
            # `grounding_mark`, and the name matters: under the WAVE2.5 ruling this is NOT always a
            # measured mark. The organ derives the status from the basis, so a box-basis reading
            # comes back `interpretive` — and this lane passes that through untouched rather than
            # deciding for itself what its own evidence is worth.
            mark = nestedness.grounding_mark(measurement, post_id=post_id, step_id=step_id, now=now)
            out.append(OrganReading(
                organ=nestedness.ORGAN,
                relation=nestedness.RELATION_NESTED_WITHIN,
                direction=direction,
                locus_region_id=locus_id,
                other_region_id=other_id,
                measurement=measurement,
                mark=mark,
                detail=measurement["detail"]))

    out.sort(key=lambda r: -r.measurement["nesting_index"])
    return out


def invoke(organ_name: str, *, post: Mapping[str, Any], region_id: str,
           step_id: str = "", now: str = "") -> List[OrganReading]:
    """Point one organ at one locus and return what it measured. The only way into a percept field.

    Raises `OrganRefusal` when the organ cannot be invoked here, and when the locus does not exist
    in the post. The second is not pedantry: an agent standing on a region that is not there has no
    position, and every reading it produced would be about somewhere else.
    """
    binding = assert_invocable(organ_name)
    post_id = str(post.get("_id") or post.get("id") or "")

    locus_region = _region(post, region_id)
    if locus_region is None:
        raise OrganRefusal(
            f"no region {region_id!r} in post {post_id} — an agent cannot stand where there is "
            f"nothing to stand on, and every reading from a phantom locus would be about "
            f"somewhere else")

    readers = {nestedness.ORGAN: _readings_from, adjacency.ORGAN: _adjacency_readings}
    reader = readers.get(binding.name)
    if reader is not None:
        return reader(locus_region, _regions(post), post_id=post_id, step_id=step_id, now=now)

    # Unreachable while every entry in `PURE_PYTHON_ORGANS` has a reader, and kept so that adding a
    # third organ without wiring its invocation fails here rather than returning a confident empty
    # field. `test_agent_dialogue_wave3.py` asserts the two tables cover each other.
    raise OrganRefusal(
        f"{binding.name} resolves as invocable but this module has no invocation for it — "
        f"a silent empty reading would be indistinguishable from 'measured nothing'")


def epistemic_ceiling(organ_name: str) -> EpistemicStatus:
    """The strongest thing an organ's output may claim, asked of the registry where it knows.

    A pure-python organ falls through to `epistemics.default_status_for`, which is where its
    producer classification lives (see the note this lane added to `_DEFAULTS`). Both paths end at
    the same table, which is the point: nothing here holds a private opinion about what an organ
    is entitled to say.
    """
    from backend.services.epistemics import default_status_for
    role = role_registry.get(str(organ_name or ""))
    if role is not None and role.kind is RoleKind.ORGAN:
        return role.epistemic_ceiling
    return default_status_for(str(organ_name or ""))
