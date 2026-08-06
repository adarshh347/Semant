"""
Schemas for Semant Writer (W1 · the executable document).

The Writer is the manuscript half of the Chiasmatic circulation, wrapping the SAME
orchestration kernel the vision app runs on. It stores no canon of its own — Accept
writes through `manuscript_service` into WS-0A's scenes — so nothing here describes a
manuscript, a chapter or a scene. What it does describe:

  - the OPERATOR: an actuator authored by the writer from dialogue, versioned, and the
    only evidence base a render is permitted to draw on;
  - the BLOCK RUN: a scripted block of `/` directives under `//` orchestration;
  - the DECISION: accept a quarantined passage into canon, or dismiss it.

`project_id` scopes operators. For W1 it is the manuscript id; W3's operator graph will
want the indirection, so the field is named for what it will be rather than what it
currently holds.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Operators (the author's ontology) ---

class OperatorRelation(BaseModel):
    """A typed edge to another operator (W3).

    `target` is an operator NAME, never free text — that is what makes an edge incapable
    of importing a style the ontology never declared (I5). `kind` is one of
    `relations.RELATION_KINDS`, and only `requires` feeds rendering in v1.
    """
    target: str
    kind: str = "requires"


class RelationsUpdate(BaseModel):
    """Replace an operator's whole edge set. Validated, then version-bumped."""
    relations: List[OperatorRelation] = Field(default_factory=list)


class OperatorPropose(BaseModel):
    """`#create <name>: <description>` — draft an operator. Returns it UNSAVED."""
    name: str
    description: str
    author: Optional[str] = ""


class OperatorCreate(BaseModel):
    """The author-confirmed write. `definition` is required: see `operators._validate`."""
    name: str
    definition: str
    rendering_intent: Optional[str] = ""
    examples: List[str] = Field(default_factory=list)
    negative_examples: List[str] = Field(default_factory=list)
    relations: List[OperatorRelation] = Field(default_factory=list)
    author: Optional[str] = ""


class OperatorUpdate(BaseModel):
    """Patch an operator. Bumps `version`; the prior body is kept in `history`."""
    definition: Optional[str] = None
    rendering_intent: Optional[str] = None
    examples: Optional[List[str]] = None
    negative_examples: Optional[List[str]] = None
    relations: Optional[List[OperatorRelation]] = None
    author: Optional[str] = None


# --- Assemblages (W4) ---

class AssemblageDismiss(BaseModel):
    """The author does not want this cluster named. Changes no ontology."""
    members: List[str] = Field(default_factory=list)
    support: int = 0


class AssemblageCreate(BaseModel):
    """Author an assemblage from a suggested cluster.

    `members` are operator NAMES, looked up in the ontology — never free text (I5).
    `rendering_intent` is REQUIRED and is the AUTHOR'S: the system may show that these
    operators recur, but what the recurrence means is the one thing it must not decide.
    """
    name: str
    members: List[str] = Field(default_factory=list)
    rendering_intent: str
    # REQUIRED, and distinct from `rendering_intent`. The two do different work — what this
    # thing IS, and what should happen on the page when it fires — and an assemblage that
    # says one of them twice renders thinly: W4's live gate had the intent handed straight
    # back as the passage. See `operators.create_assemblage`.
    definition: str
    author: Optional[str] = ""


# --- The portable ontology (W5) ---

class LibraryOp(BaseModel):
    """Promote / import / publish / pull, all of which name an author and an operator.

    `author` is required and is what the library is keyed by. W5 is SINGLE-AUTHOR: a
    library is one person's declared language, and importing across authors would put
    prose in your book in a voice you never declared.
    """
    author: str
    name: str


# --- The alignment reading (W7) ---

class AlignmentRead(BaseModel):
    """Read a passage against its OWN declared standard.

    `provenance` is what makes the reading possible and what bounds it: a passage is measured
    against the operators and `//` intents that made it, and against nothing else. Passing
    prose with no provenance is allowed and returns `no_provenance` — the honest answer, not
    a critique against operators it was never made from.
    """
    text: str
    provenance: Dict[str, Any] = Field(default_factory=dict)
    passage_id: Optional[str] = ""
    block_id: Optional[str] = ""
    scene_id: Optional[str] = ""
    manuscript_id: Optional[str] = ""


class FlagDecision(BaseModel):
    """The author's response to one flag. `acted` is a judgement, never an applied fix."""
    state: str          # dismissed | acted
    note: Optional[str] = ""


# --- Running a block ---

class BlockRun(BaseModel):
    """Execute a scripted block. Renders are QUARANTINED; nothing reaches the manuscript.

    `scene_id` is where accepted passages would land and where continuity is read from.
    It is optional: a block can be rendered against no scene at all, which produces
    passages that cannot be accepted until one is named.
    """
    text: str
    manuscript_id: Optional[str] = ""
    scene_id: Optional[str] = ""
    quarantine: bool = True
    # BLOCK SCOPE (W3 §1). Indices, in document order, of the `/` directives that are
    # still PENDING — the ones whose render has not been accepted. `None` means run the
    # whole block, which is the explicit "re-run everything" action. Omitting this is
    # therefore the safe default for any caller with no notion of what is satisfied.
    only_directives: Optional[List[int]] = None


class BlockParse(BaseModel):
    """Parse only — the `/` ÷ `//` split, with no model called and nothing stored."""
    text: str


# --- The author's decision on a quarantined passage ---

class PassageAccept(BaseModel):
    """Commit a passage into canon. `scene_id` overrides the one it was rendered against."""
    scene_id: Optional[str] = ""


class PassageDismiss(BaseModel):
    reason: Optional[str] = ""
