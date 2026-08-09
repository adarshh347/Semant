"""
HARNESS-001B §4 — capability resolution, and the three vocabularies it refuses to flatten.

The board states the distinction this module exists to preserve:

    Perceptual Action Grammar   what kind of act may be PROPOSED to a curator?
    Director actuators          what globally scoped operation has an EXECUTOR?
    Agent organs / world acts   what can THIS BODY perceive or do FROM THIS LOCUS?

They are related and they are not the same, and the tempting move — one enum, one `capabilities`
list — would make `brush_field(fold)` and `concept_segment("fold")` the same row. They are not:
the first is a mark a CURATOR authors by hand, the second is a model measuring pixels and a human
naming the result. Collapsing them would let a run execute the manual act silently, which is the
single most consequential fabrication available at this seam.

## Six outcomes, and why none of them is a default

    director_preparation   a global executable actuator chain may prepare evidence
    agent_mission          an existing body/organ/world action can investigate locally
    human_action           grammar-valid, but requires the curator's hand or confirmation
    composite              preparation followed by one or more missions
    capability_gap         the requested measurement has no current instrument
    refused                violates an epistemic/product law

`capability_gap` is DATA, never an error, and it always names the unmet requirement. That is the
difference between "we looked and found nothing" and "nothing here can look", and the fold rehearsal
turns on it: the sensorium can measure segmentation, depth, adjacency and nestedness, and has no
dedicated fold-curvature or surface-normal instrument. Reporting that as an empty result would be a
lie about the corpus rather than about the system.

## Availability is not a gap

An actuator whose model is down is UNAVAILABLE — transient, retryable, and the instrument exists.
A missing instrument is a gap — no retry will help. `execution.py` already keeps `unavailable`,
`empty` and `skipped` apart for exactly this reason, and this module keeps the same line one level
up: resolution answers *is there an instrument*, execution answers *is it up*. A resolver that folded
availability into `capability_gap` would tell a curator to stop asking a question that a restarted
model would answer.

## What this module reads LIVE

`director.capabilities.ACTUATORS` and `agents.organs.resolve` — the real tables, not a copy. A need
naming an actuator that has since been deleted resolves as a gap because the lookup returns `None`,
and an organ that is real-but-residency-managed resolves as available-with-a-caveat because
`organs.resolve` says so in its own words. Nothing here holds a private opinion about what exists.

PURE. No database, no network, no model, no clock it was not handed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.services.agents import organs as agent_organs
from backend.services.director import capabilities as director_caps
from backend.services.inquiry_engine.goals import (CLAUSE_IMAGINED, CLAUSE_INTERPRETIVE,
                                                   CLAUSE_MEASURED, CLAUSE_SOURCED)

# ── the six outcomes ─────────────────────────────────────────────────────────
DIRECTOR_PREPARATION = "director_preparation"
AGENT_MISSION = "agent_mission"
HUMAN_ACTION = "human_action"
COMPOSITE = "composite"
CAPABILITY_GAP = "capability_gap"
REFUSED = "refused"

RESOLUTIONS: Tuple[str, ...] = (DIRECTOR_PREPARATION, AGENT_MISSION, HUMAN_ACTION,
                                COMPOSITE, CAPABILITY_GAP, REFUSED)

# ── refusal reasons, a closed set a caller may branch on ─────────────────────
LAW_MODEL_MAY_NOT_AUTHOR = "model_may_not_author_this_act"
LAW_SYNTHESIS_BEFORE_EVIDENCE = "synthesis_before_evidence"
LAW_UNGROUNDED_HORIZON = "ungrounded_horizon"
LAW_UNKNOWN_INSTRUMENT = "unknown_instrument"
LAW_SPECULATION_IS_NOT_EVIDENCE = "speculation_is_not_evidence"


@dataclass(frozen=True)
class Need:
    """One answerable need, and the instruments that could serve it.

    A table rather than a function, for the reason `agents.goal.GOALS` and `director.INTENTS` are
    tables: a need a run acted on has to be a thing a reader can look up afterwards. A need that
    matched nothing is refused by name, never approximated into a neighbouring one.
    """
    key: str
    summary: str
    demands: str = CLAUSE_MEASURED
    #: Director actuators that could prepare this globally. Looked up live in `director_caps`.
    actuators: Tuple[str, ...] = ()
    #: Agent organs that could investigate it from a locus. Looked up live in `agent_organs`.
    organs: Tuple[str, ...] = ()
    #: An organ here needs a field a MODEL produces first — so the honest resolution is `composite`,
    #: not `agent_mission`. `depth_organ` is the only current member and `organs.invoke` refuses
    #: without the field, so pretending otherwise would surface as a refusal mid-mission.
    prepares_first: Tuple[str, ...] = ()
    requires_phrase: bool = False
    requires_locus: bool = False
    #: Non-empty → this need can never be met by any instrument this system has. The string names
    #: what is MISSING, in the words a later lane would have to build.
    missing_instrument: str = ""
    #: Non-empty → an epistemic or product law forbids serving this need as evidence.
    law: str = ""
    #: Words that route a curator's unresolved term here. Matched as phrases, longest-first, exactly
    #: like `director.planner._score` — deliberately dumb, because a clever matcher that guessed
    #: wrong would produce a confident gap against the wrong instrument.
    terms: Tuple[str, ...] = ()
    relation: str = ""
    basis: str = ""


#: The needs this lane states. Every entry is either servable by a named instrument, or explicitly
#: not servable and says why — there is no third row, and no default.
NEEDS: Dict[str, Need] = {
    "extent_of_a_named_thing": Need(
        key="extent_of_a_named_thing",
        summary="the real pixel extent of a concept the curator named",
        actuators=("concept_segment", "grounded_sam_find_parts"),
        requires_phrase=True,
        # `folding` is listed EXPLICITLY now that matching is boundary-aware. It used to be
        # caught by `fold` as a substring — along with `unfolding`, which is the word Lane A uses
        # for the manner it says nothing can measure. One of those two was a lucky hit and the
        # other was the bug; listing the intended one and dropping the accident separates them.
        terms=("segment", "outline", "extent", "mask", "cut out", "every instance", "drapery",
               "fold", "folds", "folding", "fold-level"),
    ),
    "parts_of_the_image": Need(
        key="parts_of_the_image",
        summary="what parts this picture has at all",
        actuators=("find_parts",),
        terms=("parts", "regions", "what is in it"),
    ),
    "comparison_across_images": Need(
        key="comparison_across_images",
        summary="a named relation between marks on two different images",
        actuators=("compare_views",),
        terms=("compare", "comparison", "between", "across", "drift apart", "differ"),
    ),
    "documented_context": Need(
        key="documented_context",
        summary="what the sources say about a named topic, with citations",
        demands=CLAUSE_SOURCED,
        actuators=("historical_source",),
        requires_phrase=True,
        terms=("history", "documented", "sources", "renaissance", "buddha", "provenance of the term"),
    ),
    "nestedness_here": Need(
        key="nestedness_here",
        summary="is the region this agent stands on inside another, or around one",
        organs=("nestedness_organ",),
        requires_locus=True,
        relation="nested_within",
        basis="mask",
        terms=("nested", "nestedness", "inside", "contains", "containment"),
    ),
    "adjacency_here": Need(
        key="adjacency_here",
        summary="what the region this agent stands on touches",
        organs=("adjacency_organ",),
        requires_locus=True,
        relation="meets",
        basis="mask",
        terms=("adjacent", "adjacency", "touches", "meets", "against"),
    ),
    "chroma_here": Need(
        key="chroma_here",
        summary="how warm or cool the region this agent stands on reads",
        organs=("chroma_organ",),
        requires_locus=True,
        relation="warmth",
        terms=("warm", "cool", "chroma", "colour temperature", "color temperature"),
    ),
    "depth_here": Need(
        key="depth_here",
        summary="how far back the region this agent stands on sits",
        organs=("depth_organ",),
        prepares_first=("background_recession",),
        requires_locus=True,
        relation="depth",
        terms=("depth", "recession", "how far back", "in front of", "behind"),
    ),
    "fold_morphology": Need(
        key="fold_morphology",
        summary="the curvature and surface normals of a fold — how the drapery actually turns",
        missing_instrument=(
            "a dedicated fold-curvature / surface-normal instrument. The sensorium can measure a "
            "fold's EXTENT (concept_segment), how far back it sits (depth_organ), what it touches "
            "(adjacency_organ) and what it is inside (nestedness_organ) — and none of those is a "
            "measurement of how a surface TURNS. A monocular depth field orders regions front to "
            "back; it does not yield the local normal a fold's morphology is a claim about, and "
            "reading one off it would be a derivative nobody measured."),
        # `unfolding` was here and is deliberately gone. It is a MANNER word, and this need is
        # specifically curvature and surface normals; matching it meant Lane A's "way of unfolding"
        # — which the framer refused for being a manner at all — came back as a confident gap
        # against an instrument that is not what it was talking about. Every remaining term names
        # the measurement, not the manner.
        terms=("fold curvature", "surface normal", "surface normals", "curvature",
               "how the fold turns", "fold morphology"),
    ),
    "interpretive_judgement": Need(
        key="interpretive_judgement",
        summary="a reading no organ measures — whether something reads as sensual, tender, austere",
        demands=CLAUSE_INTERPRETIVE,
        terms=("sensuality", "sensual", "beauty", "beautiful", "expressive", "aesthetic",
               "feels", "reads as", "style"),
    ),
    "speculation": Need(
        key="speculation",
        summary="what could exist but does not — a hybrid, a descendant, a possible form",
        demands=CLAUSE_IMAGINED,
        law=LAW_SPECULATION_IS_NOT_EVIDENCE,
        terms=("hybrid", "could give birth", "what if", "imagine", "speculate", "future",
               "give birth to"),
    ),
}


@dataclass(frozen=True)
class Resolution:
    """One capability question, answered. Data in every branch, including the refusals.

    `availability` is kept SEPARATE from `kind` on purpose. An actuator that exists but whose model
    is down still resolves as `director_preparation` — the instrument is real, the run will record
    `unavailable` when it dispatches, and a curator reading this can tell "ask again later" from
    "this question has no instrument".
    """
    kind: str
    need: str
    why: str
    actuators: Tuple[str, ...] = ()
    organs: Tuple[str, ...] = ()
    #: What is not met. For a gap this is the missing instrument; for a refusal, the law; for a
    #: composite, the preparation the mission is waiting on.
    unmet: Tuple[str, ...] = ()
    caveats: Tuple[str, ...] = ()
    law: str = ""
    #: The resolver proposed a MODEL MEASUREMENT plus an INTERPRETIVE NAMING where the curator's act
    #: would have been a hand-authored mark. True is not an error; it is the thing that must never
    #: be silent.
    interpretive_naming: bool = False
    availability: Dict[str, Any] = field(default_factory=dict)
    demands: str = CLAUSE_MEASURED
    requires_phrase: bool = False
    requires_locus: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "need": self.need, "why": self.why,
                "actuators": list(self.actuators), "organs": list(self.organs),
                "unmet": list(self.unmet), "caveats": list(self.caveats), "law": self.law,
                "interpretive_naming": self.interpretive_naming,
                "availability": dict(self.availability), "demands": self.demands,
                "requires_phrase": self.requires_phrase, "requires_locus": self.requires_locus}


# ── live lookups ─────────────────────────────────────────────────────────────

def actuator_availability(names: Sequence[str],
                          up: Optional[frozenset] = None) -> Dict[str, Any]:
    """Which of these actuators EXIST, and — when the caller says what is running — which are up.

    `up=None` means the caller does not know, which is the honest default for a pure resolver: it
    reports existence and declares availability `unknown` rather than assuming a model is running.
    """
    known: List[str] = []
    absent: List[str] = []
    needs_runtime: Dict[str, str] = {}
    for name in names:
        actuator = director_caps.get(name)
        if actuator is None:
            absent.append(name)
            continue
        known.append(name)
        if actuator.capability:
            needs_runtime[name] = actuator.capability
    out: Dict[str, Any] = {"exists": known, "absent": absent, "needs_runtime": needs_runtime}
    if up is None:
        out["state"] = "unknown"
        return out
    out["state"] = "checked"
    out["down"] = sorted({n for n, cap in needs_runtime.items() if cap not in up})
    return out


def organ_availability(names: Sequence[str]) -> Dict[str, Any]:
    """How each organ name resolves against the LIVE binding table.

    Three outcomes, and the middle one is the one worth keeping: a residency-managed organ is REAL
    and not invocable from a pure engine, which is a caveat on a legitimate mission — not a gap and
    not a typo.
    """
    invocable: List[str] = []
    resident: List[str] = []
    unknown: List[str] = []
    detail: Dict[str, str] = {}
    for name in names:
        binding = agent_organs.resolve(name)
        detail[name] = binding.detail
        if binding.invocable:
            invocable.append(name)
        elif binding.resolution == agent_organs.RESIDENT:
            resident.append(name)
        else:
            unknown.append(name)
    return {"invocable": invocable, "resident": resident, "unknown": unknown, "detail": detail}


# ── resolving a need ─────────────────────────────────────────────────────────

def resolve_need(need_key: str, *, phrase: str = "", locus: bool = False,
                 evidence_returned: int = 0, horizon_grounded: bool = False,
                 capabilities_up: Optional[frozenset] = None) -> Resolution:
    """One evidence need → one of the six outcomes. The whole resolver, in one function.

    `locus` and `horizon_grounded` are facts the CALLER establishes (does a post/region exist, did
    the kernel ground a crossing) — the resolver does not go looking, because a resolver that read
    the graph would be a second movement layer.
    """
    need = NEEDS.get(str(need_key or ""))
    if need is None:
        return Resolution(
            kind=REFUSED, need=str(need_key or ""), law=LAW_UNKNOWN_INSTRUMENT,
            unmet=(str(need_key or ""),),
            why=(f"no need named {str(need_key)!r}. The ones this lane states are {sorted(NEEDS)}. "
                 f"An unmatched need is refused by name rather than routed to the nearest-looking "
                 f"instrument — a confident answer to a question nobody asked is worse than none."))

    # 1. A law forbids serving this as evidence at all.
    if need.law:
        return Resolution(
            kind=REFUSED, need=need.key, law=need.law, demands=need.demands,
            unmet=(need.law,),
            why=(f"{need.summary} — {need.law}. This is not a gap: no instrument is missing, "
                 f"because this was never a measurement question. It is carried as an "
                 f"{need.demands!r} clause so the inquiry can state it and never satisfy it."))

    # 2. There is no instrument, and there never was one to be unavailable.
    if need.missing_instrument:
        return Resolution(
            kind=CAPABILITY_GAP, need=need.key, demands=need.demands,
            unmet=(need.missing_instrument,),
            why=(f"{need.summary}: no current instrument measures it. "
                 f"{need.missing_instrument}"))

    # 3. An interpretive clause has no instrument BY KIND, which is different again: it is not that
    #    nobody built the organ, it is that the question is not one an organ answers.
    if need.demands == CLAUSE_INTERPRETIVE:
        return Resolution(
            kind=HUMAN_ACTION, need=need.key, demands=need.demands,
            unmet=("a curator's reading",),
            why=(f"{need.summary} — an interpretive clause is the curator's to make. No organ "
                 f"measures it and no missing organ would; asking a model for the sentence would "
                 f"produce a reading indistinguishable from a measured one, which is the "
                 f"fabrication this whole system is arranged against."))

    # 4. A phrase the instrument needs and does not have.
    if need.requires_phrase and not str(phrase or "").strip():
        return Resolution(
            kind=HUMAN_ACTION, need=need.key, demands=need.demands,
            actuators=need.actuators, requires_phrase=True,
            unmet=("phrase",),
            why=(f"{need.summary} needs the curator's words and none were given. An "
                 f"open-vocabulary finder with nothing to look for will mask SOMETHING for any "
                 f"phrase — the P8-B fabrication shape — so this waits for a hand rather than "
                 f"guessing a query."))

    organs_state = organ_availability(need.organs) if need.organs else None
    actuators_state = (actuator_availability(need.actuators, capabilities_up)
                       if need.actuators else None)

    # 5. A locus the mission needs and does not have.
    if need.requires_locus and not locus:
        return Resolution(
            kind=HUMAN_ACTION, need=need.key, demands=need.demands, organs=need.organs,
            requires_locus=True, unmet=("a locus",),
            availability={"organs": organs_state} if organs_state else {},
            why=(f"{need.summary} is knowledge FROM SOMEWHERE, and no locus was given. An agent "
                 f"standing on a region that is not there has no position, and every reading it "
                 f"produced would be about somewhere else."))

    # 6. Composite: a model must produce a field before a body can read it.
    if need.prepares_first:
        prep_state = actuator_availability(need.prepares_first, capabilities_up)
        return Resolution(
            kind=COMPOSITE, need=need.key, demands=need.demands,
            actuators=tuple(need.prepares_first), organs=need.organs,
            unmet=tuple(need.prepares_first),
            availability={"preparation": prep_state, "organs": organs_state or {}},
            caveats=(f"{', '.join(need.organs)} reads a field a model produces; the field is handed "
                     f"in and never fetched, so the preparation is not optional and a mission "
                     f"dispatched without it is refused by the organ rather than degraded.",),
            why=(f"{need.summary}: global preparation ({', '.join(need.prepares_first)}) followed "
                 f"by a situated mission ({', '.join(need.organs)}). Two scales of one need, and "
                 f"the order is forced by the organ's own refusal."))

    # 7. A situated mission.
    if need.organs:
        assert organs_state is not None
        if organs_state["unknown"]:
            return Resolution(
                kind=REFUSED, need=need.key, law=LAW_UNKNOWN_INSTRUMENT,
                organs=need.organs, unmet=tuple(organs_state["unknown"]),
                availability={"organs": organs_state}, demands=need.demands,
                why=(f"{', '.join(organs_state['unknown'])} is not an organ this system has: "
                     f"{organs_state['detail'].get(organs_state['unknown'][0], '')}"))
        caveats = tuple(organs_state["detail"][n] for n in organs_state["resident"])
        return Resolution(
            kind=AGENT_MISSION, need=need.key, demands=need.demands,
            organs=tuple(organs_state["invocable"]) or need.organs,
            availability={"organs": organs_state}, caveats=caveats,
            requires_locus=need.requires_locus,
            why=(f"{need.summary}: a body standing at the locus can measure it through "
                 f"{', '.join(organs_state['invocable']) or 'no invocable organ'}."))

    # 8. Director preparation.
    if need.actuators:
        assert actuators_state is not None
        if not actuators_state["exists"]:
            return Resolution(
                kind=CAPABILITY_GAP, need=need.key, demands=need.demands,
                unmet=tuple(actuators_state["absent"]),
                availability={"actuators": actuators_state},
                why=(f"{need.summary}: the actuator(s) this need names "
                     f"({', '.join(actuators_state['absent'])}) are not in the live catalogue. "
                     f"A need pointing at an instrument that no longer exists is a gap, not a "
                     f"planning error."))
        caveats: Tuple[str, ...] = ()
        if actuators_state.get("down"):
            caveats = (f"{', '.join(actuators_state['down'])} needs a runtime that is not "
                       f"currently available. That is UNAVAILABLE, not absent — the instrument "
                       f"exists and a restarted model answers this; the run records the "
                       f"difference when it dispatches.",)
        return Resolution(
            kind=DIRECTOR_PREPARATION, need=need.key, demands=need.demands,
            actuators=tuple(actuators_state["exists"]), caveats=caveats,
            availability={"actuators": actuators_state},
            requires_phrase=need.requires_phrase,
            why=f"{need.summary}: a global actuator chain can prepare it.")

    # 9. Declared, servable by nothing, and not marked as either a gap or a law. Unreachable while
    #    every row above is complete, and kept so that adding a need without wiring an instrument
    #    fails HERE rather than resolving to a confident nothing.
    return Resolution(
        kind=CAPABILITY_GAP, need=need.key, demands=need.demands,
        unmet=("no instrument declared for this need",),
        why=(f"{need.summary} is declared in NEEDS and names neither an actuator nor an organ nor "
             f"a missing instrument. That is a table error, reported as a gap rather than as a "
             f"silent empty resolution."))


# ── resolving a proposed public action ───────────────────────────────────────

#: How a grammar-valid public act maps onto a need. NOT an equivalence table — see
#: `resolve_action`, where three of these rows are deliberately not a plain lookup.
_ACTION_NEEDS: Dict[str, str] = {
    "find_parts": "parts_of_the_image",
    "connect_marks": "nestedness_here",
}


def need_for_action(action_type: str) -> Optional[str]:
    """Which declared need a public act's PLAIN cases map onto, or None.

    Only the plain cases. `brush_field`, `challenge_percept` and `compose_percept` are absent from
    `_ACTION_NEEDS` on purpose — each has a rule in `resolve_action` that a lookup would erase, and
    a caller reaching for this to shortcut that is the mistake this docstring exists to catch.
    """
    return _ACTION_NEEDS.get(str(action_type or ""))


def resolve_action(action: Any, *, evidence_returned: int = 0, phrase: str = "",
                   locus: bool = False, horizon_grounded: bool = False,
                   capabilities_up: Optional[frozenset] = None) -> Resolution:
    """A proposed public act → one of the six outcomes.

    Three rows are NOT a lookup, and each is a rule the directive states outright:

      `brush_field(fold)`   is a CURATOR-AUTHORED mark. The resolver may propose
                            `concept_segment("fold")` as a distinct preparation when the phrase is
                            explicit — and it must carry that this is model measurement PLUS an
                            interpretive naming, never a silent execution of the manual act.
      `challenge_percept`   becomes an evidence/challenge goal. It may not be model-authored
                            (`perceptualActions.js` refuses it at the grammar level), so it
                            resolves to the curator's hand.
      `compose_percept`     is synthesis AFTER evidence. Proposed before any evidence has returned,
                            it is refused — a composition resting on nothing is the fabrication the
                            whole composition layer exists to prevent.
    """
    kind = str(getattr(action, "type", "") or (action.get("type") if isinstance(action, Mapping)
                                               else "") or "")
    role = str(getattr(action, "role", "") or (action.get("role") if isinstance(action, Mapping)
                                               else "") or "")
    words = str(getattr(action, "phrase", "") or (action.get("phrase") if isinstance(action, Mapping)
                                                  else "") or "") or phrase
    source = str(getattr(action, "source", "") or (action.get("source")
                                                   if isinstance(action, Mapping) else "") or "")

    if not kind:
        return Resolution(
            kind=REFUSED, need="", law=LAW_UNKNOWN_INSTRUMENT, unmet=("action type",),
            why=("a proposed action carried no readable type. It is refused by name rather than "
                 "dropped, because a dropped proposal is invisible in the run and an unnamed one "
                 "is a fact about the frame."))

    if kind == "challenge_percept":
        return Resolution(
            kind=HUMAN_ACTION, need="", law=LAW_MODEL_MAY_NOT_AUTHOR,
            unmet=("a curator's challenge",),
            why=("a challenge becomes an evidence/challenge goal, never a model-authored mutation. "
                 "The public grammar refuses `challenge_percept` from a model outright, and a run "
                 "that produced one here would be routing around a rule the frontend enforces."))

    if kind == "compose_percept":
        if evidence_returned <= 0:
            return Resolution(
                kind=REFUSED, need="", law=LAW_SYNTHESIS_BEFORE_EVIDENCE,
                unmet=("returned evidence",),
                why=("composition is synthesis AFTER evidence, and none has returned. A percept "
                     "composed before anything was gathered would rest on nothing while looking "
                     "exactly like one that rests on five marks."))
        state = actuator_availability(("compose_percept",), capabilities_up)
        return Resolution(
            kind=DIRECTOR_PREPARATION, need="", actuators=("compose_percept",),
            availability={"actuators": state},
            why=(f"composition, after {evidence_returned} piece(s) of evidence returned — the "
                 f"order the rule requires."))

    if kind == "brush_field":
        if not str(words).strip():
            return Resolution(
                kind=HUMAN_ACTION, need="extent_of_a_named_thing", requires_phrase=True,
                unmet=("phrase",),
                why=("a brushed field is a curator-authored mark and no phrase was given, so there "
                     "is not even a concept to propose measuring instead."))
        state = actuator_availability(("concept_segment",), capabilities_up)
        if not state["exists"]:
            return Resolution(
                kind=CAPABILITY_GAP, need="extent_of_a_named_thing",
                unmet=("concept_segment",), availability={"actuators": state},
                why=("the only instrument that could stand near a brushed field is "
                     "`concept_segment`, and it is not in the live catalogue."))
        return Resolution(
            kind=DIRECTOR_PREPARATION, need="extent_of_a_named_thing",
            actuators=("concept_segment",), interpretive_naming=True,
            availability={"actuators": state}, requires_phrase=True,
            caveats=(
                f"`brush_field({role or words!r})` is a CURATOR-AUTHORED mark. This resolution does "
                f"not execute it. It proposes `concept_segment({words!r})` as a DISTINCT "
                f"preparation: a model measuring pixel extent, plus an interpretive naming of what "
                f"was measured. The measurement is the model's; the name "
                f"{role or words!r} is a reading, and nothing in the run may treat the pair as the "
                f"hand-drawn field the curator would have made.",),
            why=(f"an explicit phrase ({words!r}) makes a measured stand-in proposable — as a "
                 f"different act, said so."))

    if kind == "ask_model_reading":
        # A READING, and `director.capabilities` is emphatic about what that is: `semantic_read`
        # produces `Resource.READING`, `WorkingMemory.available()` never carries one forward, and no
        # actuator requires one. A sentence ABOUT the image is never evidence IN it — so this
        # resolves as a preparation whose product is interpretive by kind, and no measured clause
        # can ever be settled by it.
        state = actuator_availability(("semantic_read",), capabilities_up)
        if not state["exists"]:
            return Resolution(
                kind=CAPABILITY_GAP, need="", unmet=("semantic_read",),
                availability={"actuators": state},
                why="`semantic_read` is not in the live catalogue.")
        return Resolution(
            kind=DIRECTOR_PREPARATION, need="", actuators=("semantic_read",),
            demands=CLAUSE_INTERPRETIVE, availability={"actuators": state},
            caveats=("a semantic reading produces a READING, not a mark. It is a sentence about "
                     "the picture and can never satisfy a measured clause — the resource type "
                     "enforces it, not this caveat.",),
            why="a reading of what has been gathered can be asked for, as an interpretive product.")

    if kind in ("trace_direction", "assign_ground_role", "start_manuscript"):
        return Resolution(
            kind=HUMAN_ACTION, need="", unmet=("the curator's hand",),
            why=(f"{kind!r} is grammar-valid and is the curator's act: it authors direction, a "
                 f"role, or a manuscript, none of which an organ measures. It is carried as a "
                 f"proposal, never performed."))

    need_key = _ACTION_NEEDS.get(kind)
    if need_key is None:
        return Resolution(
            kind=REFUSED, need="", law=LAW_UNKNOWN_INSTRUMENT, unmet=(kind,),
            why=(f"{kind!r} is not an act this resolver knows how to serve. Refused visibly rather "
                 f"than approximated — a plausible-sounding act routed to the nearest instrument "
                 f"is how a hallucinated action becomes a dispatched one."))

    resolution = resolve_need(need_key, phrase=words, locus=locus,
                              evidence_returned=evidence_returned,
                              horizon_grounded=horizon_grounded,
                              capabilities_up=capabilities_up)
    if source == "model_suggested":
        # A relation PROPOSED by a model is still only a proposal. The resolution stands — the model
        # is entitled to suggest the ACT — and the note travels with it so nothing downstream reads
        # the provenance off the instrument that served it.
        return replace(resolution, caveats=(
            *resolution.caveats,
            "proposed by a model: the act may be resolved; what it names is a proposal, and only "
            "an organ may stamp what it measures"))
    return resolution


# ── routing a curator's unresolved term ──────────────────────────────────────

def need_for_term(term: str) -> Optional[str]:
    """Which declared need a curator's word belongs to, or None.

    Deliberately dumb, and the same shape as `director.planner._score`: phrase matching, longest
    match wins, no stemming and no embeddings. None means REFUSE — the caller reports a gap naming
    the term rather than routing it to the nearest-looking instrument. A cleverer matcher would
    produce confident gaps against the wrong organ, which reads as a considered finding.

    ON WORD BOUNDARIES, which is not a tidy-up. Bare substring containment found `fold` inside
    `unfolding`, so Lane A's "way of unfolding" — a term it explicitly marks unresolvable, "no organ
    in the sensorium is scoped to a manner" — routed to the fold-extent instrument and became a
    clause this engine could report having measured. A boundary match keeps `fold-level` (a hyphen
    IS a boundary) and drops `unfolding`, which is exactly the distinction the framer was making.
    """
    text = str(term or "").strip().lower()
    if not text:
        return None
    best: Optional[str] = None
    best_score = 0
    for key, need in NEEDS.items():
        for word in need.terms:
            if len(word) > best_score and re.search(rf"\b{re.escape(word)}\b", text):
                best, best_score = key, len(word)
    return best


__all__ = [
    "DIRECTOR_PREPARATION", "AGENT_MISSION", "HUMAN_ACTION", "COMPOSITE", "CAPABILITY_GAP",
    "REFUSED", "RESOLUTIONS", "Need", "NEEDS", "Resolution",
    "LAW_MODEL_MAY_NOT_AUTHOR", "LAW_SYNTHESIS_BEFORE_EVIDENCE", "LAW_UNGROUNDED_HORIZON",
    "LAW_UNKNOWN_INSTRUMENT", "LAW_SPECULATION_IS_NOT_EVIDENCE",
    "actuator_availability", "organ_availability", "resolve_need", "resolve_action",
    "need_for_term", "need_for_action",
]
