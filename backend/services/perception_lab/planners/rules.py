"""
PERCEPTUAL-ORGANS-002 Lane D — the deterministic planner: a closed phrase table and no model.

This is the arm that makes the laboratory testable offline, and it is also the arm the model
planner falls back to. Both jobs want the same property: the same sentence produces the same plan
every time, on any machine, with no key and no network.

HOW IT DECIDES, in three rules that are the whole algorithm:

  1. EVERY CUE IN THE TABLE IS MATCHED, not the first one. A sentence that matches four cues has
     matched four cues, and knowing that is worth more than the speed of an early return.

  2. THE LONGEST MATCHED CUE WINS. "do not touch" beats "touch"; "in front of" beats "inside";
     "what surrounds" beats "surrounds". Specificity is length here because the longer phrase is
     the one that carried the extra word the person chose to say.

  3. EVERY OTHER MATCH BECOMES A NOTE. `"is the finial inside the sky, or merely in front of it?"`
     plans occlusion and SAYS that containment also matched. The person asked a question with two
     readings; a planner that silently took one of them would be hiding the ambiguity that was
     the point of the sentence.

THE PLANNER IS ORGAN-BLIND, AND THAT IS DELIBERATE. Asked "do those two touch?" in an
extent-locked session it proposes `topology.adjacency` anyway, and the resolver refuses it
`organ_locked`. It must work this way: `LabPlan` requires that a proposed step leaving the locked
organ carry an `organ_locked` refusal, precisely so that a crossing is REFUSED rather than quietly
not proposed. A planner that knew about the lock would produce an empty plan, and the person would
never learn that what they asked for exists one switch away.

TWO OPERATIONS THIS PLANNER WILL NOT PROPOSE, however the sentence is phrased:

  · `extent.draw` — its parameters are a mask or a polygon. A prompt cannot say where a mask is,
    and a planner that emitted one would be inventing the measurement rather than requesting it.
    The Direct arm reaches it because there the parameters are a person's hand.

  · `extent.reuse` — it consumes canonical region refs, and `InputRef` requires a `geometry_rev`
    with every region id. `LabSession.active_region_ids` carries ids without revisions, so there
    is no revision here to cite and inventing one would be inventing the identity the revision
    exists to pin. Recorded as a contradiction for Lane F; the Direct arm supplies both halves.

PURE. No database, no network, no model, no clock. `ids` is injected.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from backend.schemas.perception_lab import PlannerIdentity, SessionMode
from backend.services.perception_lab.clock import IdFactory, SequentialIds
from backend.services.perception_lab.definitions import operation
from backend.services.perception_lab.planners.base import (StepBuilder, bind_many, bind_pair,
                                                           bind_single, input_limit)
from backend.services.perception_lab.resolver import Proposal
from backend.services.perception_lab.session import SessionView

#: `(operation, cue)`. Order in this tuple is irrelevant — rule 2 sorts by cue length — so it is
#: grouped by operation for reading. A cue is a substring test on a normalized prompt, not a
#: regex, because a regex in a table is a rule nobody can scan.
CUES: Tuple[Tuple[str, str], ...] = (
    # -- topology --
    ("topology.occlusion", "in front of"),
    ("topology.occlusion", "behind"),
    ("topology.occlusion", "occlud"),
    ("topology.occlusion", "nearer the viewer"),
    ("topology.occlusion", "closer to the viewer"),

    ("topology.containment", "inside"),
    ("topology.containment", "within"),
    ("topology.containment", "contained in"),
    ("topology.containment", "contains"),
    ("topology.containment", "nested in"),
    ("topology.containment", "enclosed by"),

    ("topology.adjacency", "touch"),
    ("topology.adjacency", "meet"),
    ("topology.adjacency", "adjacent"),
    ("topology.adjacency", "next to"),
    ("topology.adjacency", "up against"),
    ("topology.adjacency", "share a border"),
    ("topology.adjacency", "share an edge"),

    ("topology.overlap", "overlap"),
    ("topology.overlap", "intersect"),
    ("topology.overlap", "cross over"),

    ("topology.disjoint", "disjoint"),
    # Longer than the `touch` and `meet` cues they negate, which is how rule 2 makes a negation
    # win without a second pass that would have to know what negation is.
    ("topology.disjoint", "not touch"),
    ("topology.disjoint", "n't touch"),
    ("topology.disjoint", "never touch"),
    ("topology.disjoint", "not meet"),
    ("topology.disjoint", "n't meet"),
    ("topology.disjoint", "separate from"),
    ("topology.disjoint", "apart from"),
    ("topology.disjoint", "away from"),
    ("topology.disjoint", "clear of"),

    ("topology.negative_space", "negative space"),
    ("topology.negative_space", "what surrounds"),
    ("topology.negative_space", "surrounds"),
    ("topology.negative_space", "surrounding"),
    ("topology.negative_space", "space around"),

    ("topology.all_pairs", "all pairs"),
    ("topology.all_pairs", "which of these"),
    ("topology.all_pairs", "which selected"),
    ("topology.all_pairs", "how are these related"),
    ("topology.all_pairs", "relations between"),
    ("topology.all_pairs", "relate to each other"),
    ("topology.all_pairs", "every relation"),

    # -- extent --
    ("extent.compare", "compare"),
    ("extent.compare", "the other adapter"),
    ("extent.compare", "repeat that"),
    ("extent.compare", "run it again"),
    ("extent.compare", "same again"),

    ("extent.refine", "refine"),
    ("extent.refine", "tighten"),
    ("extent.refine", "clean up"),
    ("extent.refine", "extend the mask"),
    ("extent.refine", "grow the mask"),
    ("extent.refine", "shrink the mask"),

    ("extent.find_all", "how many"),
    ("extent.find_all", "what is in this"),
    ("extent.find_all", "what's in this"),
)

#: The verbs that mean "produce an extent of the thing I am about to name". Matched only when no
#: table cue won, so "compare the two masks" stays a comparison rather than a search for "the two
#: masks".
_SEARCH = re.compile(
    r"\b(mask|find|segment|outline|detect|isolate|highlight)\b\s+"
    r"(?:me\s+)?(?:(?:every|each|all(?:\s+of)?)\s+)?(?:the\s+)?(.*)",
    re.IGNORECASE)

#: A concept that means "whatever is there" is a search for everything, not a search for a thing
#: called "everything".
UNIVERSALS = frozenset({
    "", "it", "it all", "them", "them all", "everything", "anything", "instance", "instances",
    "object", "objects", "thing", "things", "region", "regions", "shape", "shapes", "part",
    "parts", "of it", "of them",
})

#: Where a noun phrase stops. Cutting here is what keeps `concept` inside its declared 120
#: characters without a truncation that could slice a word in half.
_CLAUSE = re.compile(r"\s*(?:[,.;:?!]|\band\s+then\b|\bthen\b|\bso\s+that\b|\bbecause\b)")

#: A noun phrase is short. Eight words is generous, and the cut is REPORTED as a note rather than
#: made silently, because a concept the person did not say is a concept that will be searched for.
MAX_CONCEPT_WORDS = 8

#: The words that point at something already on the screen. They are never RESOLVED here — the
#: session's declared ids do that — but noticing them is what turns "no extents were supplied"
#: into "you said 'those two' and this session has nothing selected", which is a sentence a person
#: can act on.
DEMONSTRATIVES: Tuple[str, ...] = (
    "that mask", "that one", "that region", "that extent", "those two", "those masks", "these two",
    "these masks", "them", "those", "these", "it", "the other one", "the same",
)

#: Trailing locatives that name the image rather than the thing being looked for.
_TAIL = re.compile(
    r"\s+\b(?:in|on|of)\s+(?:this|the)\s+"
    r"(?:image|picture|photo|photograph|frame|shot|painting|drawing)\b.*$",
    re.IGNORECASE)


class RulesPlanner:
    """A closed table over the words, and nothing that could look at a picture."""

    name = "rules"
    identity = PlannerIdentity.RULES

    def __init__(self, ids: Optional[IdFactory] = None):
        self._ids = ids if ids is not None else SequentialIds()

    def plan(self, request: str, session: SessionView) -> Proposal:
        prompt = " ".join(str(request or "").split()).lower()
        builder = StepBuilder(session.selected_organ, self._ids)
        if not prompt:
            builder.note("an empty prompt proposes nothing. There is no default operation.")
            return _proposal(builder)

        matched = _matches(prompt)
        chosen, alternatives = _choose(matched)

        if chosen is None:
            chosen = _search_operation(prompt)
            if chosen is None:
                builder.note(
                    "no cue in the deterministic table matched this prompt, and no plan was "
                    "proposed. An empty proposal is the honest answer; a keyword guess dressed as "
                    "a plan is not.")
                return _proposal(builder)

        for other in alternatives:
            builder.note(f"{other} also matched this prompt and was not proposed. The longer cue "
                         f"won, and the reading you did not get is recorded rather than lost.")

        prerequisite = _prepare_chain(chosen, session, builder)
        _propose(chosen, prompt, session, builder, matched)
        return _proposal(builder, prerequisite)


# -- matching -----------------------------------------------------------------


def _matches(prompt: str) -> Dict[str, str]:
    """`{operation: the longest cue of that operation this prompt contains}`."""
    found: Dict[str, str] = {}
    for op_key, cue in CUES:
        if cue in prompt and len(cue) > len(found.get(op_key, "")):
            found[op_key] = cue
    return found


def _choose(matched: Dict[str, str]) -> Tuple[Optional[str], List[str]]:
    """Rule 2 and rule 3: the longest cue wins, and the rest are named.

    Ties break on the operation key so the answer does not depend on dictionary order. A tie means
    two cues of identical length matched, which is rare enough that any stable rule will do and
    important enough that there must BE one.
    """
    if not matched:
        return None, []
    ranked = sorted(matched.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return ranked[0][0], [op for op, _ in ranked[1:]]


def _search_operation(prompt: str) -> Optional[str]:
    """`mask every face` -> find_named; `mask every instance` -> find_all; `hello` -> nothing."""
    hit = _SEARCH.search(prompt)
    if hit is None:
        return None
    return "extent.find_all" if _concept(hit.group(2)) in UNIVERSALS else "extent.find_named"


def _concept(raw: str) -> str:
    """The noun phrase the person named, cut at the first clause boundary."""
    text = _CLAUSE.split(raw.strip(), maxsplit=1)[0]
    text = _TAIL.sub("", text).strip()
    return " ".join(text.split()[:MAX_CONCEPT_WORDS])


# -- proposing ----------------------------------------------------------------


def _unbound(prompt: str, refs: Tuple, session: SessionView, builder: StepBuilder) -> None:
    """Say when the sentence pointed at something and the session had nothing to point at.

    This adds NO resolution power whatsoever — the step still goes to the resolver with no inputs
    and is still refused. What it adds is a reason the refusal makes sense: `missing_extent_inputs`
    on its own reads as a complaint about the operation, and the person's actual mistake was that
    "those two" refers to a selection they have not made.
    """
    if refs:
        return
    said = [d for d in DEMONSTRATIVES if d in prompt]
    if not said:
        return
    builder.note(
        f"the prompt said '{max(said, key=len)}' and this session has "
        f"{len(session.artifact_ids)} declared artifact references. A demonstrative resolves "
        f"through selected and active ids and through nothing else, so nothing was cited.")


def _propose(op_key: str, prompt: str, session: SessionView, builder: StepBuilder,
             matched: Dict[str, str]) -> None:
    cue = matched.get(op_key, "a search verb")
    why = f"the deterministic table matched '{cue}'"

    if op_key == "extent.find_all":
        builder.propose(op_key, rationale=why)

    elif op_key == "extent.find_named":
        hit = _SEARCH.search(prompt)
        concept = _concept(hit.group(2)) if hit else ""
        if not concept:
            builder.note("a search verb matched but named nothing to search for.")
            return
        if hit and len(hit.group(2).split()) > MAX_CONCEPT_WORDS:
            builder.note(f"the concept was cut to the first {MAX_CONCEPT_WORDS} words: "
                         f"'{concept}'. What is searched for is what is shown here.")
        builder.propose(op_key, parameters={"concept": concept}, rationale=why)

    elif op_key == "extent.refine":
        refs = bind_single(session, "base")
        _unbound(prompt, refs, session, builder)
        builder.propose(op_key, parameters={"mode": _refine_mode(prompt)}, input_refs=refs,
                        rationale=why)

    elif op_key == "extent.compare":
        refs = bind_pair(session, ("left", "right"))
        _unbound(prompt, refs, session, builder)
        builder.propose(op_key, input_refs=refs, rationale=why)

    elif op_key == "topology.negative_space":
        refs = bind_single(session, "figure")
        _unbound(prompt, refs, session, builder)
        builder.propose(op_key, input_refs=refs, rationale=why)

    elif op_key == "topology.all_pairs":
        params: Dict[str, object] = {}
        kinds = _relation_kinds(op_key, matched)
        if kinds:
            params["relations"] = kinds
            builder.note(f"the prompt named {', '.join(kinds)}, so the all-pairs sweep is bounded "
                         f"to those relations rather than every declared kind.")
        refs = bind_many(session, "members", input_limit(op_key, "members"))
        _unbound(prompt, refs, session, builder)
        builder.propose(op_key, parameters=params, input_refs=refs, rationale=why)

    else:                                    # every remaining topology operation is a pair
        refs = bind_pair(session, ("source", "target"))
        _unbound(prompt, refs, session, builder)
        builder.propose(op_key, input_refs=refs, rationale=why)


def _refine_mode(prompt: str) -> str:
    """`add`, `subtract` or `replace`, and `replace` is not a default.

    `extent.refine` declares `mode` required with no default, so something must choose. A prompt
    that says neither "add" nor "remove" is asking for a new proposal for the same subject, which
    is what `replace` means -- it is a reading of the sentence, not a fallback value, and it is
    recorded on the plan where a person can disagree with it.
    """
    if any(w in prompt for w in ("add", "include", "grow", "extend", "more of")):
        return "add"
    if any(w in prompt for w in ("remove", "subtract", "exclude", "shrink", "erase", "less of")):
        return "subtract"
    return "replace"


def _relation_kinds(op_key: str, matched: Dict[str, str]) -> List[str]:
    """The relation kinds the sentence also named, clamped to what all-pairs declares.

    `"which selected shapes touch?"` matched both `which selected` and `touch`. The first chose
    the operation; the second says which relation to look for, and dropping it would run a full
    sweep the person did not ask for.
    """
    declared = set(operation(op_key).relation_kinds)
    by_cue = {"topology.adjacency": "meets", "topology.overlap": "overlaps",
              "topology.containment": "nested_within", "topology.disjoint": "disjoint"}
    return [by_cue[op] for op in sorted(matched) if op in by_cue and by_cue[op] in declared]


def _prepare_chain(op_key: str, session: SessionView, builder: StepBuilder) -> Tuple[str, ...]:
    """In chain mode, offer the extents a topology question has nothing to measure.

    ONLY in chain mode. In isolation the same shortfall is a refusal, because isolation is the
    mode in which a judgement about one organ means something and a silent extent call inside it
    would be exactly the hidden crossing the master plan's non-goals forbid.

    The preparation is proposed BEFORE the measurement and does not feed it. The resolver writes
    the prerequisite that says the person stands between them.
    """
    if session.mode is not SessionMode.CHAIN or not op_key.startswith("topology."):
        return ()
    if len(session.artifact_ids) >= 2:
        return ()
    builder.propose("extent.find_all",
                    rationale="the chain prepares extents; the person inspects them and selects "
                              "which to measure before the relation is planned again")
    return ("this chain begins in the extent organ and ends in topology. Both stages are visible, "
            "and confirming it is a decision about crossing the boundary, not about running.",)


def _proposal(builder: StepBuilder, prerequisites: Tuple[str, ...] = ()) -> Proposal:
    return Proposal(planner=PlannerIdentity.RULES, steps=tuple(builder.steps),
                    refusals=tuple(builder.refusals), prerequisites=prerequisites,
                    notes=tuple(builder.notes))


__all__ = ["RulesPlanner", "CUES", "UNIVERSALS"]
