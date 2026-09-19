"""A preserved unit of inquiry, never a Differential Ground or evidence object.

The optional session extension has its own version. Old sessions are read without a write;
absence means not recorded. Revisions are append-only and references always name a revision.
"""
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Authorship(Strict):
    kind: Literal["human", "model"] = "human"
    actor: str = Field(min_length=1, max_length=200)
    source_ref: str = ""

    @model_validator(mode="after")
    def named(self):
        if not self.actor.strip():
            raise ValueError("authorship requires a named actor")
        return self


class AnchorInput(Strict):
    origin: Literal["user_prompt", "model_reading"]
    source_id: str = Field(min_length=1)
    span: Tuple[int, int]
    exact_text: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def bounded(self):
        start, end = self.span
        if start < 0 or end <= start or end - start != len(self.exact_text):
            raise ValueError("source span must bound the exact text (Unicode code points)")
        return self


class SourceAnchor(AnchorInput):
    source_sha256: str
    author: Literal["user", "scene_theorist"]
    image_refs: List[str] = Field(default_factory=list)


class AlternativeInput(Strict):
    alternative_id: str = ""
    text: str = Field(min_length=1, max_length=2000)
    authorship: Authorship


class ThoughtInput(Strict):
    organising_question: str = Field(min_length=1, max_length=2000)
    anchors: List[AnchorInput] = Field(min_length=1, max_length=4)
    central_tension: str = Field(default="", max_length=2000)
    alternatives: List[AlternativeInput] = Field(default_factory=list, max_length=8)
    perceptual_questions: List[str] = Field(default_factory=list, max_length=8)
    perceptual_relevance: str = Field(default="", max_length=2000)
    authorship: Authorship
    confirmed_by: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def meaningful(self):
        if not self.organising_question.strip() or not self.authorship.actor.strip():
            raise ValueError("question and author must contain words")
        if sum(len(a.exact_text) for a in self.anchors) > 4000:
            raise ValueError("select at most 4000 source characters per thought")
        if self.confirmed_by is not None and not self.confirmed_by.strip():
            raise ValueError("confirmation requires a named human")
        return self


class GraphPin(Strict):
    graph_id: str
    graph_hash: str
    schema_version: str
    inquiry_id: str
    session_revision: int
    checkpoint: int


class Candidate(Strict):
    claim_ref: str
    reason: Literal["source_atom_lineage", "immediate_graph_neighbour"]
    source_unit_refs: List[str] = Field(default_factory=list)
    atom_refs: List[str] = Field(default_factory=list)
    inference_refs: List[str] = Field(default_factory=list)
    via_edge_refs: List[str] = Field(default_factory=list)
    image_refs: List[str] = Field(default_factory=list)


class Inspection(Strict):
    graph: GraphPin
    producer: Literal["semantic_constellation/lineage-v1"] = "semantic_constellation/lineage-v1"
    source_unit_refs: List[str] = Field(default_factory=list)
    candidates: List[Candidate] = Field(default_factory=list)
    candidate_edge_refs: List[str] = Field(default_factory=list)
    candidate_count: int = 0
    pilot_limit: Literal[8] = 8
    narrowing_required: bool = False
    missing_links: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def complete_candidates(self):
        if self.candidate_count != len(self.candidates) or len(
                {c.claim_ref for c in self.candidates}) != self.candidate_count:
            raise ValueError("candidate count must include every distinct candidate")
        if self.narrowing_required != (self.candidate_count > self.pilot_limit):
            raise ValueError("oversized candidates require explicit narrowing")
        return self


class JudgmentInput(Strict):
    value: Literal["not_assessed", "preserved", "partly_preserved", "lost", "unclear"] = "not_assessed"
    note: str = Field(default="", max_length=4000)
    recovered_thought: str = Field(default="", max_length=4000)
    next_investigation: str = Field(default="", max_length=4000)


class PreservationJudgment(JudgmentInput):
    assessed_by: Optional[str] = None
    at: Optional[str] = None

    @model_validator(mode="after")
    def assessment_is_attributed(self):
        if self.value != "not_assessed" and not (self.assessed_by and self.at and self.note.strip()):
            raise ValueError("a preservation judgment requires a human, time and explanatory note")
        return self


class SemanticConstellation(Strict):
    schema_version: Literal["semantic-constellation.v1"] = "semantic-constellation.v1"
    constellation_id: str
    session_id: str
    inquiry_id: str = ""
    revision: int = Field(ge=1)
    previous_revision: Optional[int] = None
    created_at: str
    revised_at: str
    revision_actor: str
    revision_reason: Literal["capture", "edit", "inspection", "human_review"]
    captured_checkpoint: int
    timing: Literal["before_compilation", "retrospective"]
    organising_question: str
    anchors: List[SourceAnchor]
    central_tension: str = ""
    alternatives: List[AlternativeInput] = Field(default_factory=list)
    alternatives_exhaustive: Literal[False] = False
    alternatives_mutually_exclusive: Literal[False] = False
    perceptual_questions: List[str] = Field(default_factory=list)
    perceptual_relevance: str = ""
    perceptual_questions_executable: Literal[False] = False
    authorship: Authorship
    confirmed_by: Optional[str] = None
    status: Literal["proposed", "reviewed"]
    inspection: Optional[Inspection] = None
    confirmed_claim_refs: List[str] = Field(default_factory=list)
    rejected_claim_refs: List[str] = Field(default_factory=list)
    confirmed_edge_refs: List[str] = Field(default_factory=list)
    rejected_edge_refs: List[str] = Field(default_factory=list)
    membership_reviewed_by: Optional[str] = None
    judgment: PreservationJudgment = Field(default_factory=PreservationJudgment)
    limits: List[str] = Field(default_factory=lambda: [
        "Shared ancestry is a structural candidate, not demonstrated semantic coherence.",
        "Human membership and preservation judgments do not strengthen evidence status.",
        "Recognition and aesthetic bearing require separately attributed interpretation.",
        "Chromatic and flow claims are capability gaps in this Extent/Topology pilot.",
    ])

    @model_validator(mode="after")
    def attributed_membership(self):
        if (self.status == "reviewed") != bool(self.confirmed_by and self.confirmed_by.strip()):
            raise ValueError("reviewed intent requires a named confirmation")
        if not self.anchors or not self.organising_question.strip():
            raise ValueError("an intact source and organising question are required")
        for accepted, rejected, available in (
            (self.confirmed_claim_refs, self.rejected_claim_refs,
             {c.claim_ref for c in self.inspection.candidates} if self.inspection else set()),
            (self.confirmed_edge_refs, self.rejected_edge_refs,
             set(self.inspection.candidate_edge_refs) if self.inspection else set()),
        ):
            if set(accepted) & set(rejected) or not (set(accepted) | set(rejected)) <= available:
                raise ValueError("memberships must name disjoint pinned candidates")
            if (accepted or rejected) and not self.membership_reviewed_by:
                raise ValueError("memberships require a human attribution")
        if len(self.confirmed_claim_refs) > 8:
            raise ValueError("narrow confirmed membership to eight claims")
        return self


class SemanticConstellations(Strict):
    schema_version: Literal["semantic-constellations.v1"] = "semantic-constellations.v1"
    preparation: Literal["prompt", "reading", "compiler", "released", "not_requested"] = "not_requested"
    history: List[SemanticConstellation] = Field(default_factory=list)

    @model_validator(mode="after")
    def revisions_are_contiguous(self):
        seen = {}
        for row in self.history:
            previous = seen.get(row.constellation_id)
            if row.revision != (previous or 0) + 1 or row.previous_revision != previous:
                raise ValueError("constellation history must preserve contiguous revisions")
            seen[row.constellation_id] = row.revision
        return self


class ThoughtWrite(Strict):
    expected_checkpoint: int = Field(ge=0)
    expected_constellation_revision: int = Field(default=0, ge=0)
    thought: ThoughtInput


class ReviewWrite(Strict):
    expected_checkpoint: int = Field(ge=0)
    expected_constellation_revision: int = Field(ge=1)
    graph_hash: str
    actor: str = Field(min_length=1, max_length=200)
    confirmed_claim_refs: List[str] = Field(default_factory=list, max_length=8)
    rejected_claim_refs: List[str] = Field(default_factory=list)
    confirmed_edge_refs: List[str] = Field(default_factory=list)
    rejected_edge_refs: List[str] = Field(default_factory=list)
    judgment: JudgmentInput = Field(default_factory=JudgmentInput)

    @model_validator(mode="after")
    def named_reviewer(self):
        if not self.actor.strip():
            raise ValueError("review requires a named human")
        return self


class PreparationWrite(Strict):
    expected_checkpoint: int = Field(ge=0)
