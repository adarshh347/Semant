"""
INTELLIGENCE-001A — four subjects with nothing in common, one set of contracts.

Each fixture is a whole small inquiry: the map of what was asked, the observations, how they stand
to the person's hypotheses, what was chosen for comparison, what was inferred, what the critic did
with it, and what the run amounted to. They are committed JSON rather than Python because the
contracts have to survive an encode/decode — a fixture built in memory proves nothing about what a
stored document does.

WHY FOUR AND WHY THESE. Three unrelated domains, so a test that passes for one subject and fails
for another has somewhere to fail; and one ADVERSARIAL case where the pictures contradict the
person, because a system that can only agree with its user has no way to be useful to them. The
domains share no vocabulary — `topic_nouns()` is the union of their subject words, and no
production source may contain any of them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from backend.schemas.inquiry_intelligence import (CandidateRelation, ContrastPlan,
                                                  HypothesisAlignment, InquiryMap,
                                                  IntelligenceOutcomeRecord, RelationCritique,
                                                  VisualObservation)

FIXTURE_ROOT = Path(__file__).resolve().parent / "inquiry_intelligence"

#: The four, by name. Order is the order they were authored in; nothing depends on it.
FIXTURES: Tuple[str, ...] = ("drapery-folds", "rose-window-organization", "plant-branching",
                             "contradicted-hypothesis")

#: The subject words of each fixture, plus the four topics the directive names outright. A
#: production source containing any of them has learned what its inputs are about.
TOPIC_NOUNS: Dict[str, Tuple[str, ...]] = {
    "drapery-folds": ("drapery", "fold", "veil", "undercut", "cloth"),
    "rose-window-organization": ("rose", "nave", "tracery", "arcade", "vault"),
    "plant-branching": ("fern", "frond", "maple", "twig", "branching"),
    "contradicted-hypothesis": ("vessel", "rim"),
    "_named_by_the_directive": ("sculpture", "cathedral", "architecture", "plant"),
}


@dataclass(frozen=True)
class Loaded:
    """One fixture, typed. Every list is already validated — a fixture that no longer parses is a
    contract change nobody declared, and it fails at load rather than deep inside a test."""
    name: str
    inquiry_map: InquiryMap
    observations: List[VisualObservation]
    alignments: List[HypothesisAlignment]
    contrasts: List[ContrastPlan]
    relations: List[CandidateRelation]
    critiques: List[RelationCritique]
    outcome: IntelligenceOutcomeRecord

    def relation(self, relation_id: str) -> CandidateRelation:
        for relation in self.relations:
            if relation.relation_id == relation_id:
                return relation
        raise KeyError(relation_id)

    def accepted_critiques(self) -> List[RelationCritique]:
        return [c for c in self.critiques if c.accepted()]


def raw(name: str) -> Dict:
    """The file as it sits on disk, undecoded into anything."""
    return json.loads((FIXTURE_ROOT / f"{name}.json").read_text(encoding="utf-8"))


def load(name: str) -> Loaded:
    body = raw(name)
    return Loaded(
        name=body["name"],
        inquiry_map=InquiryMap.model_validate(body["inquiry_map"]),
        observations=[VisualObservation.model_validate(o) for o in body["observations"]],
        alignments=[HypothesisAlignment.model_validate(a) for a in body["alignments"]],
        contrasts=[ContrastPlan.model_validate(c) for c in body["contrasts"]],
        relations=[CandidateRelation.model_validate(r) for r in body["relations"]],
        critiques=[RelationCritique.model_validate(c) for c in body["critiques"]],
        outcome=IntelligenceOutcomeRecord.model_validate(body["outcome"]),
    )


def topic_nouns() -> Tuple[str, ...]:
    seen: List[str] = []
    for nouns in TOPIC_NOUNS.values():
        for noun in nouns:
            if noun not in seen:
                seen.append(noun)
    return tuple(seen)
