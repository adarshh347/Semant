"""
HARNESS-001A — the framing seam.

One protocol, two implementations behind it, exactly as `Director` has one planner seam with a
rule-based and a Groq implementation behind it. The shape is deliberately the same, because the
argument is the same: swapping the deterministic framer for a model changes the SOURCE of the
proposals and nothing else. Every frame still validates against the same grammar, still arrives
with every action `proposed`, still refuses the acts a machine may not author, and still says in
its provenance which mind produced it.

    frame(prompt, corpus_context) -> InquiryFrame

`corpus_context` is a mapping of ids, titles and counts. There is no image argument and there
will not be one: a framer that could be handed pixels is a framer somebody will eventually hand
pixels to, and then the frame starts describing pictures instead of questions.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.schemas.inquiry import CorpusContext, InquiryFrame, InquiryMode


@runtime_checkable
class InquiryFramer(Protocol):
    """Reads a prompt. Proposes acts. Executes nothing and claims nothing about any image."""

    name: str

    def frame(self, prompt: str, corpus_context: Optional[Mapping[str, Any]] = None, *,
              mode: InquiryMode = InquiryMode.EXPLORE) -> InquiryFrame:
        ...


def to_corpus_context(raw: Optional[Mapping[str, Any]]) -> CorpusContext:
    """Accept a loose mapping and keep only what a mind without eyes may hold.

    Unknown keys are DROPPED here rather than refused, and this is the one place in the lane that
    is deliberately lenient: `corpus_context` is supplied by a caller (a route, a script, Lane B)
    that may reasonably hold more about a post than the frame is allowed to carry. Refusing the
    whole call because the caller also knew a region count would push callers toward stripping
    fields by hand, which is where an image fact eventually slips through as a `title`.

    What is kept is ids, titles, tags, a count and a note. What is dropped is everything else,
    and the count is derived from the ids when they are given so the two cannot disagree.
    """
    if not raw:
        return CorpusContext()
    ids = [str(x) for x in (raw.get("post_ids") or raw.get("image_ids") or []) if str(x).strip()]
    titles = [str(x) for x in (raw.get("titles") or []) if str(x).strip()]
    tags = [str(x) for x in (raw.get("tags") or []) if str(x).strip()]
    count = raw.get("count")
    if ids:
        count = len(ids)
    elif not isinstance(count, int):
        count = 0
    note = raw.get("note")
    return CorpusContext(post_ids=ids, titles=titles, tags=tags, count=int(count),
                         note=str(note) if isinstance(note, str) and note.strip() else None)
