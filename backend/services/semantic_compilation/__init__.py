"""
HARNESS-002A — the scene theorist and the semantic compiler.

    verbatim prompt + InquiryFrame + selected images
      -> provisional VLM scene reading        (pixels, interpretive at strongest)
      -> atomic typed claims and relations
      -> observable requirements and alternatives
      -> decision candidates, semantic remainder, refusals

Nothing here executes, dispatches, persists, or measures. The output is a `SemanticInquiryGraph`:
a statement of what was said, what a reader of the pictures thought, what those two decompose into,
and what would have to be produced for any of it to gain support.

The modules:

    contracts.py   loads `contracts/semantic-inquiry-graph.v1.json` and scans for geometry keys
    ids.py         content-derived ids, so a replay is a comparison rather than an act of faith
"""
from __future__ import annotations

from backend.schemas.semantic_compilation import SCHEMA_VERSION, SemanticInquiryGraph

from . import contracts, ids

__all__ = ["SCHEMA_VERSION", "SemanticInquiryGraph", "contracts", "ids"]
