"""
HARNESS-001A — the prompt-to-decision mind.

A free prompt becomes a valid, inspectable inquiry WITHOUT pretending to see. That sentence is
the whole lane, and every module here is shaped by the second half of it.

    from backend.services.inquiry import frame_prompt
    frame = frame_prompt("segment every raised hand", {"post_ids": ["abc"]})

WHAT IT SEES: the user's words, and corpus metadata (ids, titles, counts).
WHAT IT DOES NOT SEE: pixels, masks, regions, depth, or anything an organ produced.
WHAT IT PRODUCES: an `InquiryFrame` — attentions attributed to the prompt, epistemic demands
each carrying its clause, grammar-valid acts every one of them `proposed`, terms nothing can
operationalise, and the meaning the available measurements will not exhaust.
WHAT IT NEVER DOES: dispatch, persist, author geometry, or claim any evidence exists.

The modules:

    contracts.py     loads the two shared JSON contracts and refuses to run without them
    grammar.py       the Perceptual Action Grammar, enforced in Python
    lexicon.py       the attunement lexicon, matched in Python
    base.py          the `InquiryFramer` protocol and the corpus-context intake
    deterministic.py the lexicon framer — the panel's intelligence, backend side
    model.py         the model-backed framer — one call, clamped, refusals kept

Lane B consumes the frame BY SHAPE. It does not import this package until Lane A merges.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from backend.schemas.inquiry import InquiryFrame, InquiryMode

from .base import InquiryFramer, to_corpus_context
from .deterministic import DeterministicFramer

__all__ = [
    "InquiryFrame", "InquiryFramer", "InquiryMode",
    "DeterministicFramer", "ModelInquiryFramer", "get_framer", "frame_prompt",
    "to_corpus_context",
]


def get_framer(kind: str = "deterministic", **kwargs: Any) -> InquiryFramer:
    """Select a framer by name. An unknown name gets the deterministic one, not an error.

    The same choice `director.groq_planner.get_planner` offers, and for the same reason: the
    selection changes what is PROPOSED and can never change what is allowed. Both framers hand
    their output to the same validator.
    """
    if (kind or "").strip().lower() in {"model", "groq", "inquiry_framer"}:
        from .model import ModelInquiryFramer
        return ModelInquiryFramer(**kwargs)
    return DeterministicFramer()


def frame_prompt(prompt: str, corpus_context: Optional[Mapping[str, Any]] = None, *,
                 framer: str = "deterministic",
                 mode: InquiryMode = InquiryMode.EXPLORE, **kwargs: Any) -> InquiryFrame:
    """Frame a prompt. Deterministic by default — no network unless `framer='model'`."""
    return get_framer(framer, **kwargs).frame(prompt, corpus_context, mode=mode)


def __getattr__(name: str) -> Any:
    # `ModelInquiryFramer` is importable from the package without the package importing the model
    # module — which pulls in the role registry and, through it, the vision roster. A deterministic
    # framing should not pay for a model client it will never build.
    if name == "ModelInquiryFramer":
        from .model import ModelInquiryFramer
        return ModelInquiryFramer
    raise AttributeError(name)
