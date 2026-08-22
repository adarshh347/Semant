"""
INTELLIGENCE-002A — four scenes for the observation spine, committed rather than generated.

IN THE REPO, NOT THE VAULT. `CLAUDE.md`: anything the test suite reads lives in the repo.

## Why frozen replies and not a live provider

Every test in this lane is about what the code does with an answer, not about whether a model
gives a good one. A live call would make the suite slow, non-deterministic, and — worst — it would
make the adversarial scene impossible: the whole point of that one is a reply that lies in seven
specific ways at once, and no provider can be asked for that reliably.

The clients built here wear `ExecutionIdentity.FIXTURE`, not REPLAY. These readings were never a
call. Calling them a replay would put a hand-authored lie in a run record wearing the badge of
something that once happened.

## Three clean scenes, and what makes them clean is hard-won

SCULPTURE, ARCHITECTURE and PLANT each carry a prompt with hypotheses and questions in it, and
blind readings that describe the same pictures WITHOUT reaching for the person's vocabulary. That
is not decoration. The sculpture prompt says "drapery", "folds", "weight", "heavier"; the blind
reading says "channels", "close-set", "converging". A reading that had said "folds" would trip the
audit, and it is worth knowing that a well-behaved observer has to work at this.

PLANT is the deliberate near-miss. The person asks about leaves; the observer says "leaves",
because that is what they are. The audit reports a SUSPICION and not a violation, and the whole
severity split exists for exactly this sentence.

## One adversarial scene, lying in every way a reply is able to

ADVERSARIAL is one reply carrying: the person's hypothesis vocabulary handed back as a blind
reading; history and intent in the field that is read as what the picture shows; a claimed
measurement with agreement named as the instrument; the same noticing filed twice; and an
observation attributed to an image nobody supplied. Its alignment reply cites an observation that
does not exist, a hypothesis nobody made, a relation that is not one of the five, and a `supports`
resting on nothing at all.

TWO OF THE AUDIT'S CODES ARE DELIBERATELY ABSENT HERE. `missing_image_ref` and
`missing_source_ref` are unreachable through `observe_images`, which stamps both from the request
— no reply can produce them. The audit still checks for them, because observations can arrive from
somewhere that is not this observer, and the tests reach that path by building records by hand
rather than by pretending a model could return one.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from backend.services.inquiry_intelligence.observer import ImageRef, fixture_client

# ── sculpture ────────────────────────────────────────────────────────────────

SCULPTURE_PROMPT = (
    "I think the drapery is what carries the weight of this figure. "
    "How many separate folds are visible on the left side? "
    "Why does the lower half feel heavier than the upper?"
)

SCULPTURE_IMAGES: Tuple[ImageRef, ...] = (
    ImageRef("sculpture_1", "posts/sculpture_1.jpg", "image/jpeg", "sha256:aa01"),
)

SCULPTURE_REPLIES: Mapping[str, Mapping[str, Any]] = {
    "sculpture_1": {"observations": [
        {"observation_id": "sculpt_obs_1",
         "feature": "a run of parallel channels",
         "locus": "across the middle of the standing form",
         "visible_organization": "the channels are close-set and roughly equal in width, and they "
                                 "converge toward the base",
         "appearance_effect": "the surface reads as continuous rather than broken",
         "interpretive_possibility": "the density could be doing structural work",
         "uncertainty": "the far edge is in shadow and I cannot count what is there"},
        {"observation_id": "sculpt_obs_2",
         "feature": "a rectangular block",
         "locus": "beneath the standing form",
         "visible_organization": "wider than the mass above it, with a plain unbroken face",
         "appearance_effect": "it reads as a support rather than as part of the body",
         "interpretive_possibility": "it may be a later addition",
         "uncertainty": "nothing joins the two in view"},
    ]},
}

# ── architecture ─────────────────────────────────────────────────────────────

ARCHITECTURE_PROMPT = (
    "Compare the two facades. "
    "I suspect the left one is later than the right. "
    "Are the window openings the same width in both?"
)

ARCHITECTURE_IMAGES: Tuple[ImageRef, ...] = (
    ImageRef("facade_a", "posts/facade_a.jpg", "image/jpeg", "sha256:bb01"),
    ImageRef("facade_b", "posts/facade_b.jpg", "image/jpeg", "sha256:bb02"),
)

ARCHITECTURE_REPLIES: Mapping[str, Mapping[str, Any]] = {
    "facade_a": {"observations": [
        {"observation_id": "facade_a_obs_1",
         "feature": "a row of tall rectangular voids",
         "locus": "the upper band of the elevation",
         "visible_organization": "eight of them at even intervals, each about twice as tall as it "
                                 "is broad",
         "appearance_effect": "the band reads as regular and unhurried",
         "interpretive_possibility": "the regularity could indicate a single build campaign",
         "uncertainty": "the end bay runs out of frame"},
    ]},
    "facade_b": {"observations": [
        {"observation_id": "facade_b_obs_1",
         "feature": "a row of tall rectangular voids",
         "locus": "the upper band of the elevation",
         "visible_organization": "six of them, and the two toward one end sit closer together "
                                 "than the rest",
         "appearance_effect": "the band reads as interrupted near one end",
         "interpretive_possibility": "the interruption could mark a joint between two phases",
         "uncertainty": "surface staining obscures the join"},
    ]},
}

#: All five relations, so a test over this scene exercises the whole vocabulary rather than the
#: two that are easy to produce.
ARCHITECTURE_ALIGNMENT: Mapping[str, Any] = {"alignments": [
    {"hypothesis_id": "hyp_1", "relation": "complicates",
     "observation_ids": ["facade_a_obs_1", "facade_b_obs_1"],
     "reasoning": "one elevation is even and the other is interrupted; that bears on sequence "
                  "without settling which came first",
     "uncertainty": "neither reading carries a date"},
    {"hypothesis_id": "hyp_1", "relation": "cannot_determine", "observation_ids": [],
     "reasoning": "nothing in either reading speaks to relative age"},
]}

# ── plant ────────────────────────────────────────────────────────────────────

PLANT_PROMPT = (
    "How many leaves are attached at each node? "
    "I think the plant is a climber."
)

PLANT_IMAGES: Tuple[ImageRef, ...] = (
    ImageRef("plant_1", "posts/plant_1.jpg", "image/jpeg", "sha256:cc01"),
)

#: Says "leaves" — because that is what they are. The audit calls this a SUSPICION, and the fact
#: that it is NOT a violation is the thing this scene exists to pin down.
PLANT_REPLIES: Mapping[str, Mapping[str, Any]] = {
    "plant_1": {"observations": [
        {"observation_id": "plant_obs_1",
         "feature": "leaves",
         "locus": "along the upper stem",
         "visible_organization": "they emerge in twos at each swelling of the stem",
         "appearance_effect": "the spacing gives the stem a jointed look",
         "interpretive_possibility": "the pairing may hold along its whole length",
         "uncertainty": "the lowest joints are cut off by the frame"},
    ]},
}

# ── adversarial ──────────────────────────────────────────────────────────────

ADVERSARIAL_PROMPT = (
    "I think the drapery is what carries the weight of this figure. "
    "How many separate folds are visible on the left side?"
)

ADVERSARIAL_IMAGES: Tuple[ImageRef, ...] = (
    ImageRef("adv_1", "posts/adv_1.jpg", "image/jpeg", "sha256:dd01"),
)

ADVERSARIAL_REPLIES: Mapping[str, Mapping[str, Any]] = {
    "adv_1": {"observations": [
        # 1. the person's hypothesis vocabulary, handed back as a blind reading.
        {"observation_id": "adv_obs_1",
         "feature": "drapery",
         "locus": "the left side",
         "visible_organization": "the drapery carries the weight of the figure",
         "appearance_effect": "heavier below than above",
         "interpretive_possibility": "",
         "uncertainty": ""},
        # 2. history and intent in the field read as what the picture shows.
        {"observation_id": "adv_obs_2",
         "feature": "a base block",
         "locus": "beneath",
         "visible_organization": "originally cut in the 17th century; the sculptor intended a "
                                 "plain support",
         "appearance_effect": "was commissioned to read as heavy",
         "interpretive_possibility": "a plain support",
         "uncertainty": ""},
        # 3. a claimed measurement with agreement named as the instrument.
        {"observation_id": "adv_obs_3",
         "feature": "a run of channels",
         "locus": "the middle",
         "visible_organization": "there are exactly eleven of them",
         "appearance_effect": "regular",
         "interpretive_possibility": "",
         "uncertainty": "",
         "epistemic_status": "measured",
         "measurement": {"capability": "model_agreement", "quantity": "count", "value": 11,
                         "units": "channels", "artifact_ref": "three readings concurred"}},
        # 4. the same noticing as adv_obs_3, filed again under a new id.
        {"observation_id": "adv_obs_4",
         "feature": "a run of channels",
         "locus": "the middle",
         "visible_organization": "there are exactly eleven of them",
         "appearance_effect": "regular",
         "interpretive_possibility": "",
         "uncertainty": ""},
        # 5. attributed to an image nobody supplied.
        {"observation_id": "adv_obs_5",
         "feature": "a second figure",
         "locus": "the right of the group",
         "visible_organization": "turned away",
         "appearance_effect": "recessive",
         "interpretive_possibility": "",
         "uncertainty": "",
         "image_ref": "adv_2"},
    ]},
}

#: Cites an observation nobody produced, and a hypothesis nobody made.
ADVERSARIAL_ALIGNMENT: Mapping[str, Any] = {"alignments": [
    {"hypothesis_id": "hyp_1", "relation": "supports", "observation_ids": ["adv_obs_99"],
     "reasoning": "the eleventh channel settles it"},
    {"hypothesis_id": "hyp_7", "relation": "supports", "observation_ids": ["adv_obs_1"],
     "reasoning": "answers a claim that was never made"},
    {"hypothesis_id": "hyp_1", "relation": "supports", "observation_ids": [],
     "reasoning": "supported, on nothing"},
    {"hypothesis_id": "hyp_1", "relation": "proves", "observation_ids": ["adv_obs_1"],
     "reasoning": "a sixth relation, invented"},
]}


# ── the scenes, as clients ───────────────────────────────────────────────────

def sculpture_client():
    return fixture_client(SCULPTURE_REPLIES, provider="committed", model="sculpture-scene")


def architecture_client():
    return fixture_client(ARCHITECTURE_REPLIES, {"*": ARCHITECTURE_ALIGNMENT},
                          provider="committed", model="architecture-scene")


def plant_client():
    return fixture_client(PLANT_REPLIES, provider="committed", model="plant-scene")


def adversarial_client():
    return fixture_client(ADVERSARIAL_REPLIES, {"*": ADVERSARIAL_ALIGNMENT},
                          provider="committed", model="adversarial-scene")


#: (name, prompt, images, client factory) for the three scenes a well-behaved observer produces.
CLEAN_SCENES: Tuple[Tuple[str, str, Tuple[ImageRef, ...], Any], ...] = (
    ("sculpture", SCULPTURE_PROMPT, SCULPTURE_IMAGES, sculpture_client),
    ("architecture", ARCHITECTURE_PROMPT, ARCHITECTURE_IMAGES, architecture_client),
    ("plant", PLANT_PROMPT, PLANT_IMAGES, plant_client),
)
