"""
VISION-D · D0 — the typed, versioned semantic response.

The VLM is an INTERPRETER of specialist-produced candidate masks, never a geometry
generator. This schema encodes that by construction: every model is `extra="forbid"`, so
any coordinate / box / polygon / rle / x,y,w,h field the model tries to emit is REJECTED
at parse time. Assertions reference candidate IDs only; a separate check
(`enforce_candidate_ids`) rejects unknown IDs. Nothing here can carry pixels.

Persistence (D2) wraps these with provenance + curator state and stores them SEPARATELY
from geometry — a semantic rerun changes assertions only, never a Region's mask/rev.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "sem-v1"

# field names that would smuggle geometry in — rejected explicitly in addition to
# extra="forbid", so the guard is legible and testable.
_GEOMETRY_KEYS = {"box", "bbox", "polygon", "polygons", "mask", "mask_rle", "rle",
                  "coordinates", "coords", "points", "x", "y", "w", "h", "geometry",
                  "parent_id", "geometry_rev"}


class RelationProposal(BaseModel):
    """A candidate→candidate relation the VLM proposes. It cites its endpoints (candidate
    IDs) and a type, carries confidence, and stays a PROPOSAL — it can never become
    geometry parenting or change mask ownership/containment."""
    model_config = ConfigDict(extra="forbid")
    from_id: str
    to_id: str
    relation: str                       # e.g. "beside", "echoes", "same-material-as"
    confidence: Optional[float] = None
    note: Optional[str] = None


class CandidateSemantics(BaseModel):
    """Semantics bound to ONE supplied candidate id. No geometry."""
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    label: Optional[str] = None
    ranked_alternatives: List[str] = Field(default_factory=list)
    part: Optional[str] = None
    material: Optional[str] = None
    attributes: List[str] = Field(default_factory=list)
    style: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty: Optional[str] = None


class GlobalReading(BaseModel):
    """Image-global observations that do NOT pretend to be object masks."""
    model_config = ConfigDict(extra="forbid")
    composition: Optional[str] = None
    atmosphere: Optional[str] = None
    colour: Optional[str] = None
    scene: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class SemanticResponse(BaseModel):
    """The whole VLM reply. `extra="forbid"` at every level makes free geometry unrepresentable."""
    model_config = ConfigDict(extra="forbid")
    candidates: List[CandidateSemantics] = Field(default_factory=list)
    relations: List[RelationProposal] = Field(default_factory=list)
    global_reading: Optional[GlobalReading] = None
    # candidate ids the VLM says need better evidence → the UX can launch Refine on them.
    needs_better_evidence: List[str] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION


class StoredAssertion(BaseModel):
    """A persisted semantic assertion (D2) — the interpretation PLUS provenance and the
    curator's state. Stored separately from geometry; never carries pixels."""
    model_config = ConfigDict(extra="forbid")
    candidate_id: str                   # == Region id it interprets
    label: Optional[str] = None
    ranked_alternatives: List[str] = Field(default_factory=list)
    part: Optional[str] = None
    material: Optional[str] = None
    attributes: List[str] = Field(default_factory=list)
    style: Optional[str] = None
    confidence: Optional[float] = None
    uncertainty: Optional[str] = None
    provider: str
    model: str
    prompt_schema_version: str = SCHEMA_VERSION
    created_at: Optional[datetime] = None
    status: str = "proposed"            # proposed | accepted | rejected | overridden
    curator_label: Optional[str] = None  # set when the curator edits/overrides


def enforce_candidate_ids(resp: SemanticResponse, allowed_ids) -> List[str]:
    """Return the list of offending ids that reference candidates NOT supplied. The caller
    drops or rejects them — the VLM may only speak about ids it was given (so a `person`
    label can never adopt a distant candidate it invented)."""
    allowed = set(allowed_ids)
    bad = []
    for c in resp.candidates:
        if c.candidate_id not in allowed:
            bad.append(c.candidate_id)
    for r in resp.relations:
        if r.from_id not in allowed:
            bad.append(r.from_id)
        if r.to_id not in allowed:
            bad.append(r.to_id)
    for cid in resp.needs_better_evidence:
        if cid not in allowed:
            bad.append(cid)
    return bad


def has_geometry_key(obj) -> bool:
    """True if a raw dict (pre-parse) carries any geometry-smuggling key at any depth."""
    if isinstance(obj, dict):
        if _GEOMETRY_KEYS & set(str(k).lower() for k in obj.keys()):
            return True
        return any(has_geometry_key(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_geometry_key(v) for v in obj)
    return False
