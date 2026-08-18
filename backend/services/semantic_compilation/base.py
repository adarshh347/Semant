"""
HARNESS-002A — the two seams, and what travels across them.

Two protocols, each with a REPLAY implementation and a LIVE implementation behind it. The shape is
`director`'s planner seam and HARNESS-001A's framer seam again, for the same argument: swapping a
frozen fixture for a model changes the SOURCE of the proposals and nothing else. Both paths run the
same parser, hit the same closed sets, and produce the same typed refusals.

    SceneTheorist.read(...)  -> ReadingResult   pixels in, an interpretive reading out
    SemanticCompiler.compile(...) -> SemanticInquiryGraph

WHY A RESULT WRAPPER FOR THE READING. `SceneReading` has no `refusals` field and deliberately will
not get one: a reading is the theorist's product, and a refusal is a fact about the CALL. Putting
them in one object would make "the model tried to output a bounding box" look like part of what it
read. They travel together and stay distinguishable.

WHY THE CALLER OWNS THE CLOCK. Every timestamp in a receipt is handed in. This package has no
`datetime.now()` anywhere, which is what makes a replay a byte comparison rather than a comparison
with an exclusion list long enough to hide a real drift in.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

from backend.schemas.semantic_compilation import (CompilerRefusal, CompilerRefusalKind, ImageRef,
                                                  ModelReceipt, SceneReading,
                                                  SemanticInquiryGraph)

from . import ids


def sha256_of(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def refusal(inquiry_id: str, kind: CompilerRefusalKind, what: str, why: str,
            detail: Sequence[str] = ()) -> CompilerRefusal:
    """A refusal with a content-derived id, so replaying one produces the same refusal."""
    return CompilerRefusal(refusal_id=ids.refusal_id(inquiry_id, kind, what), kind=kind,
                           what=what, why=why, detail=[str(d) for d in detail])


def to_image_refs(raw: Optional[Sequence[Any]]) -> List[ImageRef]:
    """Accept a loose sequence of post ids or mappings and keep only what a ref may hold.

    Lenient in the same place and for the same reason `inquiry.base.to_corpus_context` is: the
    caller is a route or a script that legitimately holds more about a post than an image ref
    carries. What is kept is an id, a title, a transport ref and a note.
    """
    out: List[ImageRef] = []
    for entry in raw or ():
        if isinstance(entry, ImageRef):
            out.append(entry)
            continue
        if isinstance(entry, str):
            if entry.strip():
                out.append(ImageRef(post_id=entry.strip()))
            continue
        if isinstance(entry, Mapping):
            post_id = str(entry.get("post_id") or entry.get("id") or entry.get("_id") or "").strip()
            if not post_id:
                continue
            out.append(ImageRef(
                post_id=post_id,
                title=str(entry.get("title") or "").strip(),
                image_ref=str(entry.get("image_ref") or entry.get("photo_url")
                              or entry.get("url") or "").strip(),
                note=str(entry.get("note") or "").strip()))
    return out


@dataclass(frozen=True)
class ReadingResult:
    """A reading, plus what did not become part of it."""
    reading: SceneReading
    refusals: Tuple[CompilerRefusal, ...] = ()
    notes: Tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        """Did anything actually read the pictures? An unavailable theorist is not an empty one."""
        return self.reading.provenance.parsed


@dataclass(frozen=True)
class CompilationRequest:
    """Everything a compilation is allowed to see, in one object.

    The frame and the reading are SEPARATE FIELDS rather than a merged context, and that is the
    lane's first rule made structural: "the user said this" and "a VLM thought it saw this" are
    different warrants, and only the first is something the person can be held to.
    """
    prompt: str
    inquiry_id: str
    inquiry_frame: Dict[str, Any] = field(default_factory=dict)
    reading: Optional[SceneReading] = None
    images: Tuple[ImageRef, ...] = ()
    corpus: Dict[str, Any] = field(default_factory=dict)
    #: HARNESS-003F. `full` — the default and the existing behaviour — or `vertical_slice`.
    #:
    #: A STRING rather than the enum, deliberately, because this dataclass is the seam a route, a
    #: script and a test all construct: it already takes a loose sequence of post ids and a mapping
    #: for the frame, and the one place the value is turned into a decision (`scope.parse`) is the
    #: one place that should be able to refuse it.
    execution_scope: str = "full"
    #: Handed in. This package owns no clock — see the module docstring.
    now: Optional[str] = None
    #: Refusals produced upstream (by the theorist) that belong on the finished graph.
    inherited_refusals: Tuple[CompilerRefusal, ...] = ()
    inherited_notes: Tuple[str, ...] = ()


@runtime_checkable
class SceneTheorist(Protocol):
    """Reads the prompt and the images. Proposes an abundant reading. Authors no geometry."""

    name: str

    def read(self, prompt: str, images: Sequence[ImageRef], *, inquiry_id: str,
             corpus: Optional[Mapping[str, Any]] = None,
             now: Optional[str] = None) -> ReadingResult:
        ...


@runtime_checkable
class SemanticCompiler(Protocol):
    """Reads words — the prompt, the frame, the reading. Emits a graph. Executes nothing."""

    name: str

    def compile(self, request: CompilationRequest) -> SemanticInquiryGraph:
        ...


def unavailable_receipt(role: str, why: str, *, model: Optional[str] = None,
                        provider: Optional[str] = None, prompt_sha256: str = "",
                        images: Sequence[ImageRef] = (),
                        now: Optional[str] = None) -> ModelReceipt:
    """The receipt an unavailable or unparseable call leaves behind.

    It exists so that "no model answered" and "a model answered and said nothing" are different
    objects rather than two empty readings. `parsed=False` is the field every consumer branches on.
    """
    from backend.schemas.semantic_compilation import CallTopology
    return ModelReceipt(role=role, model=model, provider=provider, prompt_sha256=prompt_sha256,
                        image_refs=[i.post_id for i in images], requested_at=now,
                        parsed=False, refusal=why, call_count=0,
                        call_topology=CallTopology.UNAVAILABLE)


__all__ = ["sha256_of", "refusal", "to_image_refs", "ReadingResult", "CompilationRequest",
           "SceneTheorist", "SemanticCompiler", "unavailable_receipt"]
