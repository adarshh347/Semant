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
    base.py        the two seams — `SceneTheorist` and `SemanticCompiler` — and what crosses them
    theorist.py    the VLM that reads the pictures, replayed or live, authoring no geometry
    compiler.py    prose to a typed graph — inventions refused, violations corrected downward
"""
from __future__ import annotations

from backend.schemas.semantic_compilation import SCHEMA_VERSION, SemanticInquiryGraph

from . import contracts, ids
from .base import (CompilationRequest, ReadingResult, SceneTheorist, SemanticCompiler,
                   to_image_refs)
from .compiler import FrozenSemanticCompiler, ModelSemanticCompiler, compile_graph
from .theorist import FrozenSceneTheorist, ModelSceneTheorist

__all__ = ["SCHEMA_VERSION", "SemanticInquiryGraph", "contracts", "ids",
           "CompilationRequest", "ReadingResult", "SceneTheorist", "SemanticCompiler",
           "to_image_refs", "FrozenSceneTheorist", "ModelSceneTheorist",
           "FrozenSemanticCompiler", "ModelSemanticCompiler", "compile_graph"]
