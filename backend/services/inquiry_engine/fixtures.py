"""
HARNESS-001B — the committed `InquiryFrame` fixtures, and the worlds the rehearsals run in.

IN THE REPO, NOT IN THE VAULT. `CLAUDE.md`: *"Anything the test suite reads must live in the repo."*
These are read by `backend/tests/test_inquiry_engine_*.py` and by `scripts/inquiry_goal_run.py`, so
they are code, not prose.

## Why fixtures at all

Lane A and Lane B are being built in the same wave, in parallel. B must not import A until A merges
(the board says so), so B builds against a committed frame of the pinned minimum shape. When A
merges, one test passes A's real `InquiryFrame.model_dump()` through `frame.accept` unchanged, and
if the shapes differ the fix is a normaliser in `frame.py` and nothing else moves.

## Two frames, and they are not two examples of one thing

`control_frame()` is the BOUNDED STRUCTURAL question. Everything it asks is answerable today by a
pure-python organ on mask geometry, so the control rehearsal proves the chain end to end: intake,
resolution, a Director preparation, a real situated mission, evidence back to the parent goal, one
criterion satisfied and the rest honestly not.

`fold_frame()` is the wave's own acceptance prompt, verbatim. It is the DIFFICULT one, and it is
difficult in four different ways at once — a measurable extent, an interpretive reading, a
speculative synthesis, and one measurement nothing here can make. A run over it must come back
partially answerable with the fold-curvature gap impossible to miss.

The world builders below make posts with REAL mask geometry (`mask_geometry.rle_encode`), because a
box-basis rehearsal would prove the wrong thing: under WAVE2.5 a box nesting reads `interpretive`,
and a control rehearsal that never produced a `measured` mark could not tell a working chain from a
broken one.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from backend.services import mask_geometry as mg
from backend.services import movement_graph as mgraph
from backend.services import nestedness_organ as nest
from backend.services.inquiry_engine.frame import SCHEMA_VERSION

#: The stamp every fixture run uses. Handed in rather than read, so two runs of the same fixture are
#: comparable byte for byte — which is what makes the round-trip and goal-invariance proofs proofs.
STAMP = "2026-08-08T00:00:00+00:00"

_N = 16


def _rle(x0: int, x1: int, y0: int, y1: int) -> Dict[str, Any]:
    bits = [0] * (_N * _N)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * _N + x] = 1
    return mg.rle_encode(bits, _N, _N)


# ── the frames ───────────────────────────────────────────────────────────────

def control_frame() -> Dict[str, Any]:
    """A bounded structural question, in the minimum `inquiry-frame.v1` shape.

    `connect_marks` is the proposed act, and it is `user`-sourced rather than `model_suggested` for
    a reason worth stating: this rehearsal is about the CHAIN working, and a model-sourced act would
    add a caveat to every resolution and make the assertion about the caveat rather than the chain.
    The model-sourced path has its own test.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "inquiry_id": "inq_control_structural",
        "prompt": ("Standing on the finial: is it inside the sky region, or is the sky behind it? "
                   "Show me what the geometry actually supports."),
        "mode": "explore",
        "attentions": ["nestedness", "adjacency"],
        "epistemic_demands": [
            "measured: containment at this locus rests on mask geometry, not on a box",
        ],
        "proposed_actions": [
            {"type": "connect_marks", "role": "similarity", "source": "user",
             "target": "ground"},
        ],
        "unresolved_terms": [],
        "semantic_remainder": [],
        "provenance": {"lane": "fixture", "note": "committed in-repo; not a model output"},
    }


def fold_frame() -> Dict[str, Any]:
    """The wave's acceptance prompt, verbatim, in the minimum shape.

    The prompt is the board's own difficult one and is NOT paraphrased here. Four kinds of clause
    live in it and the run has to keep them apart:

        fold / drapery extent          measurable, by `concept_segment` — a preparation
        fold curvature / normals       NOT measurable: no instrument. The gap this rehearsal is for
        sensuality                     interpretive: the curator's reading, never a model's
        hybrid styles                  imagined: speculation, and never evidence
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "inquiry_id": "inq_fold_renaissance_buddha",
        "prompt": ("Explore the fold-level aesthetic and style relations between Renaissance and "
                   "Buddha sculptures, their common way of unfolding sensuality, where they drift "
                   "apart, and what hybrid styles they could give birth to."),
        "mode": "explore",
        "attentions": ["fold", "drapery"],
        "epistemic_demands": [
            "measured: the extent of the folds in each sculpture",
            "interpretive: whether the drapery reads as sensual",
            "imagined: what hybrid styles they could give birth to",
        ],
        "proposed_actions": [
            {"type": "brush_field", "role": "fold", "phrase": "fold",
             "source": "model_suggested", "target": "image"},
            {"type": "compose_percept", "source": "model_suggested", "target": "percept"},
        ],
        "unresolved_terms": ["fold curvature", "surface normal", "compare", "sensuality",
                             "hybrid"],
        "semantic_remainder": ["“unfolding” is doing two jobs at once — the drapery's and "
                               "the argument's"],
        "provenance": {"lane": "fixture", "note": "the wave acceptance prompt, verbatim"},
    }


# ── the worlds ───────────────────────────────────────────────────────────────

def control_world() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]]]:
    """Two posts of MASK-BACKED regions, a movement graph, and the organ marks that ground it.

    A part genuinely inside a whole, so `nestedness_organ` returns `nested=True` on the `mask` basis
    and stamps `measured`. That is the fact the control rehearsal's one satisfiable criterion rests
    on, and it is produced by the real organ here rather than written down.
    """
    def _post(pid: str) -> Dict[str, Any]:
        return {"_id": pid, "photo_url": f"https://example.invalid/{pid}.jpg",
                "region_annotations": [
                    {"id": "finial", "label": "finial", "mask_rle": _rle(4, 12, 4, 10)},
                    {"id": "sky", "label": "sky", "mask_rle": _rle(0, 16, 0, 16)},
                ]}

    posts = {"post_renaissance": _post("post_renaissance"),
             "post_buddha": _post("post_buddha")}
    marks = [nest.grounding_mark(m, post_id=pid, now=STAMP)
             for pid, post in posts.items()
             for m in nest.find_nested_pairs(post["region_annotations"])]
    first = next((m["id"] for m in marks if m["post_id"] == "post_renaissance"), "")
    graph = {"_id": "atlas_inquiry_control", "edges": [
        mgraph.movement_edge_entry(
            mark_id=first, source_node="vm_post_renaissance:finial",
            target_node="vm_post_buddha:finial",
            spans=["post_renaissance", "post_buddha"], axis_ref="axis_nestedness",
            systematicity=0.72, weight=1.0, edge_id="e_control_1")]}
    return posts, graph, marks


def fold_world() -> Dict[str, Dict[str, Any]]:
    """Two sculptures, each with a masked drapery region inside a masked figure.

    Enough real geometry for the measurable half of the fold inquiry to actually measure something,
    which is what makes the gap legible: the run returns a measured nesting AND says it cannot
    measure how the fold turns. A world with no geometry at all would produce a run whose emptiness
    could be blamed on the fixture.
    """
    def _post(pid: str, label: str) -> Dict[str, Any]:
        return {"_id": pid, "photo_url": f"https://example.invalid/{pid}.jpg",
                "title": label,
                "region_annotations": [
                    {"id": "drapery", "label": "drapery", "mask_rle": _rle(5, 11, 6, 14)},
                    {"id": "figure", "label": "figure", "mask_rle": _rle(2, 14, 2, 16)},
                ]}

    return {"post_renaissance": _post("post_renaissance", "Renaissance marble"),
            "post_buddha": _post("post_buddha", "Gandhara Buddha")}


FRAMES = {"control": control_frame, "fold": fold_frame}


__all__ = ["STAMP", "control_frame", "fold_frame", "control_world", "fold_world", "FRAMES"]
