"""
CIRCUIT-001 ORCH-001 — the actuator capability map.

Layer 3's ground truth: what each actuator NEEDS before it can fire, and what it LEAVES
BEHIND once it has. Everything else in this package is a consequence of this table —
the dependency graph reads `requires`, the planner reads `produces` to decide ordering,
the executor reads `capability` to know what a stub is standing in for.

WHY A SECOND CAPABILITY TABLE. `vision_capabilities.py` maps *recovery actions* to the
models they need (is SAM up?). This maps *actuators* to the EVIDENCE they need (is there
a region to work on?). Those are different failure modes and they refuse for different
reasons: a model being down is transient and retryable, a missing region means the plan
was built wrong. Collapsing them would make "SAM is offline" and "you have not selected
anything" the same message, which helps nobody.

VOCABULARY DISCIPLINE. Actuator names here are the SAME strings the runtime uses —
`_FIELD_PRODUCERS` keys in `routers/posts.py` and `ACTION_TYPES` in the frontend's
`perceptualActions.js`. This table does not invent a parallel naming scheme; a name that
drifts from the runtime is a bug this module cannot detect, so the names must be copied,
not paraphrased. `test_director.py` pins the field-producer half against the live registry.

This module is PURE: no torch, no fetch, no database, no model import. It is a table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Resource(str, Enum):
    """A kind of evidence an actuator can consume or leave behind.

    Deliberately coarse. This is not the mark contract — it is the smallest vocabulary
    that lets the planner answer "can this step run yet?" without understanding geometry.
    """
    IMAGE = "image"          # the picture itself — the only resource always present
    REGION = "region"        # a committed extent (a part) on the image
    PHRASE = "phrase"        # a curator's words — an open-vocabulary query
    MARK = "mark"            # committed evidence: a field, a trace, a naming
    GROUND = "ground"        # a mark promoted into a named ground
    PERCEPT = "percept"      # a composed reading resting on grounds
    READING = "reading"      # a sentence ABOUT the image (P8-D) — never evidence IN it
    # CIRCUIT-003 M6 — a quotation from OUTSIDE the image, carrying a citation.
    #
    # It sits beside READING rather than beside MARK, and for the same reason: neither is
    # evidence IN the picture. But they are not the same kind either — a reading is what a
    # model made of the pixels, a source is what a document says about the subject, and the
    # second cannot be checked by looking harder.
    #
    # Nothing in this table REQUIRES a source, which is deliberate for M6. Because
    # `WorkingMemory.evolve()` never files SOURCE into an evidence bucket (exactly as it never
    # files READING), a research step cannot make a mark-hungry step satisfiable. That is the
    # epistemic wall expressed in the planner: no chain can reach a mark by way of a citation.
    SOURCE = "source"


@dataclass(frozen=True)
class Requirement:
    """One input condition. `min_count` is the whole reason this is not just a set.

    `connect_marks` needs TWO marks, not one — a relation between a thing and itself is
    not a relation. A plain "needs marks" requirement would happily fire it on a single
    mark and produce a degenerate edge, so the count is part of the requirement.
    """
    kind: Resource
    min_count: int = 1

    def satisfied_by(self, available: Dict[Resource, int]) -> bool:
        return available.get(self.kind, 0) >= self.min_count

    def describe(self) -> str:
        if self.min_count > 1:
            return f"{self.min_count}× {self.kind.value}"
        return self.kind.value


@dataclass(frozen=True)
class Actuator:
    """One thing the Director can ask for.

    `produces` is what the step ADDS to working memory when it succeeds. It is what makes
    reordering possible: a step needing a region can follow a step that produces regions,
    even though the region does not exist when the plan is first written down.

    `capability` names the runtime dependency (a model family, or None for pure-python).
    ORCH-001 never checks it — the executor is handed stubs — but the field is here so the
    real-actuator gate has somewhere to put the availability probe without a migration.

    `authors_geometry` marks the actuators that put NEW extent on the image. It is not used
    for scheduling; it is here because the review path treats those differently and a
    planner that forgets which steps are consequential is a planner that will eventually
    chain five of them together unattended.
    """
    name: str
    summary: str
    requires: Tuple[Requirement, ...] = ()
    produces: Tuple[Resource, ...] = ()
    capability: Optional[str] = None
    authors_geometry: bool = False
    # Params the actuator reads off the step. Used to explain a refusal precisely
    # ("needs a phrase") rather than generically ("bad inputs").
    param_keys: Tuple[str, ...] = ()

    # WIRE-002 — this actuator yields an UNKNOWN number of each thing it produces, not exactly one.
    # A finder returns however many parts are there; a field producer returns one field.
    #
    # It matters only for PLAN-TIME PROJECTION. Projecting one mark from `find_parts` made
    # "find the parts, then relate two of them" unresolvable — the planner refused a step the
    # runner would happily have fed, which is a worse failure than the one the refusal prevents.
    #
    # Projecting two is SAFE because it is not a claim. `execute()` re-checks every requirement
    # against REAL memory immediately before dispatch, so if the finder actually returned one
    # part, `connect_marks` is skipped there with an honest reason naming the step that came up
    # short. The projection decides ORDER; reality still decides what runs.
    plural: bool = False

    # CIRCUIT-003 M1 — how many DISTINCT images this actuator's inputs must come from.
    #
    # 1 (the default, and every actuator that existed before M1) means "one picture at a time" —
    # unchanged behaviour, because a single-image packet reports IMAGE: 1 and every such actuator
    # asks for at most one.
    #
    # 2 means the actuator is COMPARATIVE: it does not merely tolerate a second image, it is
    # meaningless without one. It is declared here AND as an ordinary `_req(Resource.IMAGE, 2)`,
    # which is what lets the EXISTING resolver refuse it with no corpus-specific code path — a
    # single-image packet can never report two images, so "compare the façade with the rotunda"
    # asked of one photograph is refused for the same reason, by the same gate, as a relation
    # asked of one mark. This field is the DECLARATION (what a planner and the corpus tiering
    # read); the requirement is the ENFORCEMENT.
    spans_images: int = 1

    def projected_produces(self) -> Tuple["Resource", ...]:
        """What the PLANNER should assume this leaves behind. Two for a plural producer — the
        smallest count that distinguishes 'one' from 'several', and exactly what a relation needs."""
        if not self.plural:
            return self.produces
        return tuple(r for r in self.produces for _ in range(2))


def _req(kind: Resource, n: int = 1) -> Requirement:
    return Requirement(kind=kind, min_count=n)


# ── the map ──────────────────────────────────────────────────────────────────
# Grouped by archetype, matching how the producers were actually built (P6/P8).

_ACTUATOR_LIST: List[Actuator] = [
    # -- finders: they create the regions everything else stands on ------------
    Actuator(
        name="find_parts",
        summary="Propose parts of the image as regions.",
        requires=(_req(Resource.IMAGE),),
        # WIRE-002: it produces BOTH. Each proposed region is also minted as a `region_mask`
        # suggestion (that is what the runner does and always did), so a found part is a mark you
        # can relate or compose from. Declaring only REGION made every chain that finds parts and
        # then reasons about them unresolvable — the plan refused steps the runner would have fed.
        produces=(Resource.REGION, Resource.MARK),
        capability="segmenter",
        authors_geometry=True,
        plural=True,          # yields however many are there, not exactly one
    ),
    Actuator(
        name="grounded_sam_find_parts",
        summary="Find the named thing and cut it exactly.",
        # The phrase is not optional here — an open-vocabulary finder with nothing to
        # look for is the exact shape of the P8-B fabrication.
        requires=(_req(Resource.IMAGE), _req(Resource.PHRASE)),
        produces=(Resource.REGION,),
        capability="grounding_detector",
        authors_geometry=True,
        param_keys=("phrase",),
        plural=True,          # yields however many are there, not exactly one
    ),
    # CONCEPT-SEG-001 (SF-004) — the fine-parts finder that MEASURES instead of estimating.
    #
    # Its sibling `find_parts` runs the SŪKṢMA stage through a VLM, which returns boxes it
    # guessed and no mask at all. This takes a CONCEPT and returns every instance of it as real
    # pixel geometry. Same shape as `grounded_sam_find_parts` — image + phrase, refuse without
    # the phrase — for the same reason: an open-vocabulary finder with nothing to look for is
    # the P8-B fabrication shape, and this model will happily mask SOMETHING for any phrase you
    # give it (a painting returned a confident background mask for "shoulder fabric").
    Actuator(
        name="concept_segment",
        summary="Measure every instance of a named concept, as real pixel masks.",
        requires=(_req(Resource.IMAGE), _req(Resource.PHRASE)),
        produces=(Resource.REGION, Resource.MARK),
        capability="concept_segmenter",
        authors_geometry=True,
        param_keys=("phrase",),
        plural=True,          # the headline claim is that it finds them ALL, not one
    ),
    # -- fields: brushed evidence over the image or a region -------------------
    Actuator(
        name="negative_space",
        summary="The space the subject leaves behind.",
        requires=(_req(Resource.IMAGE), _req(Resource.REGION)),
        produces=(Resource.MARK,),
        capability=None,                       # pure geometry — mask complement
        authors_geometry=True,
    ),
    Actuator(
        name="material_field",
        summary="Where the same material recurs.",
        requires=(_req(Resource.IMAGE), _req(Resource.REGION)),
        produces=(Resource.MARK,),
        capability="dinov2",
        authors_geometry=True,
    ),
    Actuator(
        name="rhythm",
        summary="Repetition and interval across the surface.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability=None,                       # cpu_perceptual
        authors_geometry=True,
    ),
    Actuator(
        name="pressure_zone",
        summary="Where the composition concentrates.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability=None,
        authors_geometry=True,
    ),
    Actuator(
        name="background_recession",
        summary="How far back the picture goes.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability="depth",
        authors_geometry=True,
    ),
    Actuator(
        name="atmosphere_field",
        summary="The haze that softens distance.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability="depth",
        authors_geometry=True,
    ),
    Actuator(
        name="light_field",
        summary="Where the light lives.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability="intrinsic",
        authors_geometry=True,
    ),
    Actuator(
        name="shadow_field",
        summary="Where the light is withheld.",
        requires=(_req(Resource.IMAGE),),
        produces=(Resource.MARK,),
        capability="intrinsic",
        authors_geometry=True,
    ),
    # -- readings: they answer ABOUT the image and mint nothing ----------------
    # P8-D's distinction, carried into Layer 3: these produce READING, never MARK, so a
    # plan can never satisfy a mark-hungry step with a sentence.
    Actuator(
        name="presence_check",
        summary="Is the named thing actually there?",
        requires=(_req(Resource.IMAGE), _req(Resource.PHRASE)),
        produces=(Resource.READING,),
        capability="grounding_detector",
        param_keys=("phrase",),
    ),
    Actuator(
        name="enumerate",
        summary="How many of the named thing are verified.",
        requires=(_req(Resource.IMAGE), _req(Resource.PHRASE)),
        produces=(Resource.READING,),
        capability="grounding_detector",
        param_keys=("phrase",),
    ),
    Actuator(
        name="semantic_read",
        summary="Ask a reading of what has been gathered.",
        # A semantic pass with no regions is a caption, which is not what this is for.
        requires=(_req(Resource.IMAGE), _req(Resource.REGION)),
        produces=(Resource.READING,),
        capability="semantic_provider",
        param_keys=("question",),
    ),
    # -- circulation: they work on evidence, not pixels ------------------------
    Actuator(
        name="find_similar",
        summary="Find this again in other images.",
        requires=(_req(Resource.MARK),),       # the seed — you must have something to match
        produces=(Resource.MARK,),
        capability="dinov2",
        param_keys=("seed_mark_id",),
        plural=True,          # yields however many are there, not exactly one
    ),
    Actuator(
        name="connect_marks",
        summary="Name the relation between two marks.",
        requires=(_req(Resource.MARK, 2),),    # the count that makes this a relation
        produces=(Resource.GROUND,),
        capability=None,
        param_keys=("relation_role",),
    ),
    # -- research: it reads the library, not the picture ------------------------
    # CIRCUIT-003 M6. The only actuator that does not take IMAGE, and the omission is the
    # design: it has no access to the picture, so it cannot accidentally describe it. What it
    # needs is a TOPIC — the curator's words — and it refuses without one through the same
    # `_missing_param` path that stops `grounded_sam_find_parts` from grounding an empty
    # phrase. No topic → no lookup → no claim, which is the research twin of "no ground → no
    # mark" enforced before anything runs.
    Actuator(
        name="historical_source",
        summary="Retrieve what is documented about a named topic, with citations.",
        requires=(_req(Resource.PHRASE),),
        produces=(Resource.SOURCE,),
        capability="external_source",
        authors_geometry=False,        # it authors no extent, and could not: it never sees the image
        param_keys=("phrase",),        # the topic, in the curator's own words
        plural=True,                   # a lookup yields however many statements the sources carry
    ),
    Actuator(
        name="compose_percept",
        summary="Compose a reading that rests on what was gathered.",
        requires=(_req(Resource.MARK),),
        produces=(Resource.PERCEPT,),
        capability=None,
        param_keys=("draft_text",),
    ),
    # -- comparison: they work ACROSS images (CIRCUIT-003 M1) -------------------
    # `connect_marks` relates two marks on ONE picture and is left exactly as it was — the
    # single-image relation is the common case and half the suite pins its behaviour. These two
    # are its cross-image siblings rather than a widening of it, because the two say different
    # things: relating two marks in one frame is a claim about that frame's internal structure;
    # relating a mark on the façade to a mark on the rotunda is a claim about a SEQUENCE, and it
    # has to carry which picture each side came from or the claim cannot be checked.
    Actuator(
        name="compare_views",
        summary="Name the relation between marks on two different images.",
        # Two images AND two marks. The IMAGE count is the whole difference from connect_marks:
        # it is unsatisfiable on a single-post packet, which is what makes this refuse rather
        # than quietly degrade into a same-image relation.
        requires=(_req(Resource.IMAGE, 2), _req(Resource.MARK, 2)),
        produces=(Resource.GROUND,),
        capability=None,
        param_keys=("relation_role", "left_ref", "right_ref"),
        spans_images=2,
    ),
    Actuator(
        name="compose_comparative_percept",
        summary="Compose a reading that rests on a relation across two images.",
        # Rests on a GROUND, not on loose marks: a comparative reading that did not rest on a
        # NAMED comparison would be a sentence about two pictures that happen to be adjacent,
        # which is the fabrication this pairing exists to prevent. `compare_views` produces the
        # ground, so the resolver orders this after it or refuses it.
        requires=(_req(Resource.IMAGE, 2), _req(Resource.GROUND)),
        produces=(Resource.PERCEPT,),
        capability=None,
        param_keys=("draft_text",),
        spans_images=2,
    ),
]

ACTUATORS: Dict[str, Actuator] = {a.name: a for a in _ACTUATOR_LIST}

# The subset that reaches `POST /{post_id}/produce-field`. Pinned by test against the live
# `_FIELD_PRODUCERS` registry so this table cannot silently fall behind the runtime.
FIELD_PRODUCER_ACTUATORS: Tuple[str, ...] = (
    "negative_space", "material_field", "rhythm", "pressure_zone",
    "background_recession", "atmosphere_field", "light_field", "shadow_field",
    "grounded_sam_find_parts", "presence_check", "enumerate",
)


def get(name: str) -> Optional[Actuator]:
    """Look up an actuator, or None. None is a REFUSAL upstream, never a default.

    This matters most for the planner seam: when a language model eventually proposes the
    steps, it will sooner or later invent an actuator that sounds plausible. Returning None
    (rather than a permissive stub) is what makes that hallucination a refusal.
    """
    return ACTUATORS.get(name)


def known() -> Tuple[str, ...]:
    return tuple(ACTUATORS.keys())


def producers_of(kind: Resource) -> Tuple[str, ...]:
    """Every actuator that leaves `kind` behind — how the planner repairs an ordering."""
    return tuple(a.name for a in _ACTUATOR_LIST if kind in a.produces)


def comparative() -> Tuple[str, ...]:
    """Every actuator that relates ACROSS images (CIRCUIT-003 M1).

    Derived from `spans_images`, never listed by hand, so a comparative actuator added later
    is picked up by the corpus tiering without an edit here."""
    return tuple(a.name for a in _ACTUATOR_LIST if a.spans_images >= 2)


def is_comparative(name: str) -> bool:
    actuator = ACTUATORS.get(name)
    return bool(actuator and actuator.spans_images >= 2)
