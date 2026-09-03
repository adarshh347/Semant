#!/usr/bin/env python3
"""
PERCEPTUAL-FORMS-001F — the scoring functions, one family per form.

WHAT A BENCHMARK IS FOR, AND THE WAY THIS ONE REFUSES TO LIE.

A number is easy. `iou = 0.71` will print for any two masks, including two masks that were never
comparable — different rasters, a producer that returned nothing, an annotator who declared two
legitimate readings where the scorer wanted one. The whole discipline of this module is that those
cases DO NOT PRODUCE A NUMBER. `Score.value` is `None` and `Score.refused` carries a sentence, and
`aggregate()` counts refusals separately rather than averaging them in as zeros.

    A zero means the producer answered and was wrong.
    A refusal means nobody has been measured yet.

Those are different findings and a mean over both is a third thing that is true of neither.

THE FIVE RULES THIS FILE ENFORCES STRUCTURALLY, each because a benchmark somewhere has broken it:

  1. NO FORCED COLLAPSE. Where the annotation declares several legitimate extents or several
     legitimate readings, `hypothesis_coverage` and `extent_ontology_agreement` score against the
     SET and refuse to name one correct answer. A benchmark that picks the annotator's first
     option and calls the rest wrong is measuring its own tie-break.
  2. VISIBLE AND INFERRED ARE NEVER POOLED. `partition_accuracy` returns them separately and
     provides no mean. An amodal producer that guesses generously scores well on inferred and
     badly on visible, and one number hides exactly that trade.
  3. A SCALAR FIELD IS NOT A MASK. `field_calibration` scores the field as a field — reliability
     over bins — and `contour_agreement` needs a declared threshold before it will compare a
     level set to anything.
  4. DIRECTION IS PART OF AN EDGE. `graph_score` scores directed edges as directed: getting
     `a contains b` when the truth is `b contains a` is a wrong edge, not a right one drawn
     backwards.
  5. THE METRIC NAMES COME FROM THE CONTRACT. Every `Score.metric` is either one of
     `closed_sets.comparison_methods` or is listed in `EXTENSIONS` with a reason. A benchmark that
     invents its own vocabulary cannot be compared with the forms it is scoring.

STDLIB ONLY, AND THAT IS DELIBERATE. `numpy` and `pillow` live in `requirements-ml.txt` — the
heavy stack CI does not install. A benchmark that only runs on a workstation with torch is a
benchmark nobody runs on a pull request, so everything here is pure Python over the same COCO RLE
the contract already speaks.

WHAT IT DOES NOT DO. No models, no images, no I/O, no clock. It scores records against records.
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.mask_geometry import rle_decode  # noqa: E402
from backend.services.perception_lab.extent_forms.raster import (  # noqa: E402
    BACKGROUND_CONNECTIVITY,
    FOREGROUND_CONNECTIVITY,
)

CONTRACT_PATH = REPO_ROOT / "contracts" / "perception-lab.v1.json"

with CONTRACT_PATH.open(encoding="utf-8") as handle:
    _CONTRACT = json.load(handle)

#: The contract's own vocabulary. Read, never re-typed — a metric named here is a metric a form
#: can declare in `comparison_methods`, and one that is not is a metric no form can ask for.
COMPARISON_METHODS: Tuple[str, ...] = tuple(_CONTRACT["closed_sets"]["comparison_methods"])

#: Metrics this benchmark needs that the contract's closed set does not carry, each with the
#: reason it could not be expressed as one of the ten. These are candidates for a Lane A ticket,
#: not private vocabulary: `report()` lists them so the gap stays visible.
EXTENSIONS: Dict[str, str] = {
    "hole_count_error": "a count, not an overlap. `set_overlap` over voids would score a producer "
                        "that found the right number of wrong holes as perfectly correct.",
    "ring_reconstruction": "compares a traced ring against a recorded one at the LATTICE, which "
                           "is neither `boundary_f1` (a tolerance band) nor `chamfer` (a distance) "
                           "— an exact ring either reproduces the crack path or it does not.",
    "calibration_error": "reliability over bins. `field_l1` compares values; this compares whether "
                         "a stated confidence means what it says, which is a different claim.",
    "count_error": "how many, not where. Density's first question.",
    "localisation_error": "where, given how many. Density's second question, and separable from "
                          "the first — a producer can get the count right and the place wrong.",
    "direction_accuracy": "the fraction of directed edges whose direction is right, scored only "
                          "over edges that exist in both. `graph_edit` folds direction into an "
                          "edit distance where it stops being separately readable.",
    "transition_sensitivity": "whether a change of one pixel was detected at all. A hit rate over "
                              "known perturbations, not a comparison of two structures.",
    "hypothesis_coverage": "how much of a SET of legitimate readings was reached, with no single "
                           "correct answer to compare against.",
    "evidence_completeness": "whether a hypothesis enumerated grounds, and of what kinds. About "
                             "the record's own honesty rather than about its geometry.",
    "verdict_agreement": "agreement with a human verdict, which is a person and not a measurement.",
}

ALL_METRICS: Tuple[str, ...] = COMPARISON_METHODS + tuple(sorted(EXTENSIONS))


# ── the score ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Score:
    """One measurement, or one stated reason there is none.

    `value is None` and `refused is not None` always travel together: a score with neither is a
    score nobody can act on, and `__post_init__` refuses to build one.
    """
    metric: str
    value: Optional[float]
    n: int = 0
    unit: str = "fraction"
    refused: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metric not in ALL_METRICS:
            raise ValueError(
                f"{self.metric!r} is not a metric this benchmark declares. The contract's "
                f"comparison methods are {', '.join(COMPARISON_METHODS)}, and this lane's "
                f"extensions are {', '.join(sorted(EXTENSIONS))}. A benchmark that invents its "
                "own vocabulary cannot be compared with the forms it is scoring."
            )
        if (self.value is None) == (self.refused is None):
            raise ValueError(
                f"{self.metric}: a score carries a value OR a refusal and never both or neither. "
                "A refusal with a number in it gets averaged; a value with no number and no "
                "reason is a hole in the report."
            )

    @property
    def scored(self) -> bool:
        return self.value is not None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric, "value": self.value, "n": self.n, "unit": self.unit,
            "refused": self.refused, "detail": self.detail,
        }


def refuse(metric: str, why: str, **detail: Any) -> Score:
    """The only way to produce an unscored result. There is no default number."""
    return Score(metric=metric, value=None, refused=why, detail=dict(detail))


# ── raster helpers, over the contract's own RLE ──────────────────────────────

def _pixels(rle: Mapping[str, Any]) -> Tuple[Set[int], int, int]:
    bits, h, w = rle_decode(dict(rle))
    return {i for i, b in enumerate(bits) if b}, h, w


def _same_raster(a: Mapping[str, Any], b: Mapping[str, Any]) -> Optional[str]:
    """The one precondition every pixel comparison shares, and the sentence when it fails."""
    ash, bsh = tuple(a.get("size") or ()), tuple(b.get("size") or ())
    if not ash or not bsh:
        return "one of the masks declares no raster size"
    if ash != bsh:
        return (f"the masks are on different rasters ({ash[0]}×{ash[1]} and {bsh[0]}×{bsh[1]}). "
                "Resampling one to compare them would score the resampler")
    return None


def _neighbours(p: int, h: int, w: int, connectivity: int) -> Iterable[int]:
    r, c = divmod(p, w)
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1))
    if connectivity == 8:
        steps = steps + ((-1, -1), (-1, 1), (1, -1), (1, 1))
    for dr, dc in steps:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w:
            yield rr * w + cc


def _boundary(pixels: Set[int], h: int, w: int) -> Set[int]:
    """Pixels of the set with at least one 4-neighbour outside it, or on the frame edge.

    The 4-pairing matches `extent_forms.raster.FOREGROUND_CONNECTIVITY`, so a boundary counted
    here and a boundary traced by the producer are counted under one definition of adjacency.
    Under the other pairing a diagonal staircase has a different boundary, and the two numbers
    would differ for a reason that is about digital topology rather than about the answer.
    """
    out = set()
    for p in pixels:
        r, c = divmod(p, w)
        if r in (0, h - 1) or c in (0, w - 1):
            out.add(p)
            continue
        for q in _neighbours(p, h, w, 4):
            if q not in pixels:
                out.add(p)
                break
    return out


def _dilate(pixels: Set[int], h: int, w: int, radius: int) -> Set[int]:
    grown = set(pixels)
    for _ in range(max(0, radius)):
        ring = set()
        for p in grown:
            ring.update(_neighbours(p, h, w, 8))
        grown |= ring
    return grown


def _components(pixels: Set[int], h: int, w: int, connectivity: int) -> List[Set[int]]:
    """Flood fill in scan order, so component order is a fact about the mask rather than a race."""
    unseen = set(pixels)
    out: List[Set[int]] = []
    for seed in sorted(pixels):
        if seed not in unseen:
            continue
        stack, comp = [seed], set()
        unseen.discard(seed)
        while stack:
            p = stack.pop()
            comp.add(p)
            for q in _neighbours(p, h, w, connectivity):
                if q in unseen:
                    unseen.discard(q)
                    stack.append(q)
        out.append(comp)
    return out


# ── 1. mask: IoU and boundary F ──────────────────────────────────────────────

def mask_iou(truth: Mapping[str, Any], predicted: Optional[Mapping[str, Any]]) -> Score:
    """Intersection over union, over the same raster or not at all.

    An EMPTY TRUTH AND AN EMPTY PREDICTION score 1.0 and say so in the detail, because "looked and
    found nothing, correctly" is a real result the contract has a whole law about. An empty truth
    against a non-empty prediction scores 0.0 — the producer answered, and was wrong.
    """
    if predicted is None:
        return refuse("iou", "the producer returned no mask. That is not a score of zero: nothing "
                             "was measured, and averaging it as zero would credit the benchmark "
                             "with a comparison it never made")
    why = _same_raster(truth, predicted)
    if why:
        return refuse("iou", why)
    t, h, w = _pixels(truth)
    p, _, _ = _pixels(predicted)
    inter, union = len(t & p), len(t | p)
    if union == 0:
        return Score("iou", 1.0, n=0, detail={"both_empty": True,
                     "note": "truth and prediction are both empty. The form looked and found "
                             "nothing, and so did the producer"})
    return Score("iou", inter / union, n=len(t),
                 detail={"intersection_px": inter, "union_px": union,
                         "truth_px": len(t), "predicted_px": len(p)})


def boundary_f1(truth: Mapping[str, Any], predicted: Optional[Mapping[str, Any]],
                *, tolerance_px: int = 2) -> Score:
    """F-score over boundary pixels within a stated tolerance.

    THE TOLERANCE IS PART OF THE MEASUREMENT and travels in `detail`. A boundary F reported without
    it is uninterpretable: at tolerance 0 a one-pixel offset scores 0, at tolerance 5 a badly wrong
    edge scores well, and the number alone cannot tell those apart.
    """
    if predicted is None:
        return refuse("boundary_f1", "the producer returned no mask, so it has no boundary")
    why = _same_raster(truth, predicted)
    if why:
        return refuse("boundary_f1", why)
    t, h, w = _pixels(truth)
    p, _, _ = _pixels(predicted)
    tb, pb = _boundary(t, h, w), _boundary(p, h, w)
    if not tb and not pb:
        return Score("boundary_f1", 1.0, n=0, detail={"both_empty": True,
                     "tolerance_px": tolerance_px})
    if not tb or not pb:
        return Score("boundary_f1", 0.0, n=len(tb),
                     detail={"tolerance_px": tolerance_px, "truth_boundary_px": len(tb),
                             "predicted_boundary_px": len(pb),
                             "note": "one side has a boundary and the other has none"})
    t_near = _dilate(tb, h, w, tolerance_px)
    p_near = _dilate(pb, h, w, tolerance_px)
    precision = len([q for q in pb if q in t_near]) / len(pb)
    recall = len([q for q in tb if q in p_near]) / len(tb)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return Score("boundary_f1", f1, n=len(tb),
                 detail={"precision": precision, "recall": recall, "tolerance_px": tolerance_px,
                         "truth_boundary_px": len(tb), "predicted_boundary_px": len(pb)})


# ── 2. rings and holes ───────────────────────────────────────────────────────

def ring_reconstruction(truth_rings: Sequence[Sequence[Sequence[float]]],
                        predicted_rings: Optional[Sequence[Sequence[Sequence[float]]]]) -> Score:
    """Do the recorded rings reproduce the traced ones, vertex for vertex?

    EXACT, NOT APPROXIMATE, and that is the point of the form. `extent.boundary_rings` exists so
    the boundary stops being something a browser traces and becomes something a producer recorded;
    a ring that is close is a ring that was smoothed, and smoothing is exactly what the form was
    introduced to make visible. Rings are matched by their vertex SET so that a different starting
    vertex or winding direction is not counted as an error — those are representations of one ring.
    """
    if predicted_rings is None:
        return refuse("ring_reconstruction", "the producer recorded no rings")
    def key(ring: Sequence[Sequence[float]]) -> Tuple[Tuple[float, float], ...]:
        return tuple(sorted((round(float(x), 9), round(float(y), 9)) for x, y in ring))
    t = [key(r) for r in truth_rings]
    p = [key(r) for r in predicted_rings]
    if not t and not p:
        return Score("ring_reconstruction", 1.0, n=0, detail={"both_empty": True})
    remaining = list(p)
    exact = 0
    for ring in t:
        if ring in remaining:
            remaining.remove(ring)
            exact += 1
    denom = max(len(t), len(p))
    return Score("ring_reconstruction", exact / denom, n=len(t),
                 detail={"truth_rings": len(t), "predicted_rings": len(p),
                         "exactly_reproduced": exact,
                         "unmatched_predicted": len(remaining),
                         "note": "matched by vertex set, so winding direction and start vertex "
                                 "are not counted as errors — they are two spellings of one ring"})


def hole_count_error(truth_holes: int, predicted_holes: Optional[int],
                     *, truth_enclosed: Optional[Sequence[bool]] = None,
                     predicted_enclosed: Optional[Sequence[bool]] = None) -> Score:
    """|predicted − truth|, and separately whether enclosure was judged the same way.

    THE COUNT IS NOT AN OVERLAP. A producer that reports two holes in a two-holed shape, in the
    wrong places, is right about the count and wrong about the form — so this returns the count
    error and carries the enclosure judgements beside it rather than blending them into one score.
    `enclosed` matters because a bay in the boundary and a void are different topology, and the
    background connectivity that decides it is declared in `extent_forms.raster`.
    """
    if predicted_holes is None:
        return refuse("hole_count_error", "the producer reported no hole set")
    detail: Dict[str, Any] = {
        "truth_holes": truth_holes, "predicted_holes": predicted_holes,
        "background_connectivity": BACKGROUND_CONNECTIVITY,
        "note": "counted under the pairing extent_forms.raster declares: foreground "
                f"{FOREGROUND_CONNECTIVITY}-connected, background {BACKGROUND_CONNECTIVITY}-"
                "connected. Reverse the pairing and a corner pinch invents a hole",
    }
    if truth_enclosed is not None and predicted_enclosed is not None:
        n = min(len(truth_enclosed), len(predicted_enclosed))
        detail["enclosure_agreement"] = (
            sum(1 for i in range(n) if bool(truth_enclosed[i]) == bool(predicted_enclosed[i])) / n
            if n else None)
    return Score("hole_count_error", float(abs(predicted_holes - truth_holes)),
                 n=truth_holes, unit="holes", detail=detail)


# ── 3. scalar fields ─────────────────────────────────────────────────────────

def field_l1(truth_values: Sequence[float], predicted_values: Optional[Sequence[float]]) -> Score:
    """Mean absolute error over a field, cell for cell. Refuses across different shapes."""
    if predicted_values is None:
        return refuse("field_l1", "the producer returned no field. Its statistics are not a field")
    if len(truth_values) != len(predicted_values):
        return refuse("field_l1",
                      f"the fields have different cell counts ({len(truth_values)} and "
                      f"{len(predicted_values)}). Resampling one would score the resampler")
    if not truth_values:
        return refuse("field_l1", "the field is empty")
    total = sum(abs(float(a) - float(b)) for a, b in zip(truth_values, predicted_values))
    return Score("field_l1", total / len(truth_values), n=len(truth_values), unit="value")


def field_calibration(truth_values: Sequence[float], predicted_values: Optional[Sequence[float]],
                      *, bins: int = 10) -> Score:
    """Expected calibration error: does a stated 0.7 actually cover 70% of its cell?

    WHY THIS IS NOT `field_l1`. L1 asks whether the numbers are close. Calibration asks whether the
    numbers MEAN what they say — a producer whose output is a monotone but badly scaled function of
    coverage has low correlation error and high calibration error, and only the second one tells
    you the field cannot be thresholded at a meaningful value. The contract's own
    `calibration_states` (`calibrated` / `nominal` / `uncalibrated`) is a claim; this is the check.
    """
    if predicted_values is None:
        return refuse("calibration_error", "the producer returned no field to calibrate")
    if len(truth_values) != len(predicted_values):
        return refuse("calibration_error", "the fields have different cell counts")
    if not truth_values:
        return refuse("calibration_error", "the field is empty")
    buckets: List[List[Tuple[float, float]]] = [[] for _ in range(bins)]
    for t, p in zip(truth_values, predicted_values):
        p = min(max(float(p), 0.0), 1.0)
        idx = min(bins - 1, int(p * bins))
        buckets[idx].append((float(t), p))
    n = len(truth_values)
    ece = 0.0
    reliability = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            reliability.append({"bin": i, "n": 0, "stated": None, "actual": None})
            continue
        stated = sum(p for _, p in bucket) / len(bucket)
        actual = sum(t for t, _ in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(stated - actual)
        reliability.append({"bin": i, "n": len(bucket), "stated": stated, "actual": actual})
    return Score("calibration_error", ece, n=n, unit="probability",
                 detail={"bins": bins, "reliability": reliability,
                         "note": "expected calibration error. A field may match closely and be "
                                 "badly calibrated, and a badly calibrated field cannot be "
                                 "thresholded at a number that means anything"})


def contour_agreement(truth_values: Sequence[float], predicted_values: Optional[Sequence[float]],
                      *, level: Optional[float] = None) -> Score:
    """Agreement of the level sets at a DECLARED threshold, as a Jaccard over cells.

    REFUSES WITHOUT A LEVEL, and that refusal is the point. Comparing contours means comparing two
    binarisations, and a binarisation with no stated threshold is a mask nobody measured — the same
    rule the renderer lane enforces at the layer. Choosing a level here to make a number appear
    would be this function deciding what the field said.
    """
    if predicted_values is None:
        return refuse("field_correlation", "the producer returned no field to contour")
    if level is None:
        return refuse("field_correlation",
                      "no threshold was declared. A contour is a level set and a level set with "
                      "no level is not a claim; picking one here would be this benchmark deciding "
                      "what the field said")
    if len(truth_values) != len(predicted_values):
        return refuse("field_correlation", "the fields have different cell counts")
    t = {i for i, v in enumerate(truth_values) if float(v) >= level}
    p = {i for i, v in enumerate(predicted_values) if float(v) >= level}
    if not t and not p:
        return Score("field_correlation", 1.0, n=0,
                     detail={"level": level, "both_empty": True})
    return Score("field_correlation", len(t & p) / len(t | p), n=len(t),
                 detail={"level": level, "truth_cells": len(t), "predicted_cells": len(p)})


# ── 4. fragments ─────────────────────────────────────────────────────────────

def fragment_precision_recall(truth_fragments: Sequence[Mapping[str, Any]],
                              predicted_fragments: Optional[Sequence[Mapping[str, Any]]],
                              *, iou_threshold: float = 0.5) -> Score:
    """Precision and recall over fragments, matched greedily by IoU at a stated threshold.

    ONE SCORE, TWO NUMBERS, AND F1 AS THE SUMMARY — but precision and recall both travel in the
    detail because they fail differently and the difference is the finding. A producer that splits
    one fragment into six has perfect recall and poor precision; one that merges six into one has
    the reverse; and an F1 in the middle describes neither.
    """
    if predicted_fragments is None:
        return refuse("set_overlap", "the producer returned no fragment set")
    truth = [dict(f) for f in truth_fragments]
    pred = [dict(f) for f in predicted_fragments]
    if not truth and not pred:
        return Score("set_overlap", 1.0, n=0, detail={"both_empty": True,
                     "note": "the image was examined for separable pieces and none was found, "
                             "by both the annotation and the producer"})
    if not truth or not pred:
        return Score("set_overlap", 0.0, n=len(truth),
                     detail={"truth_fragments": len(truth), "predicted_fragments": len(pred),
                             "precision": 0.0 if pred else None,
                             "recall": 0.0 if truth else None})
    used: Set[int] = set()
    matched = 0
    pairs = []
    for ti, t in enumerate(truth):
        best, best_iou = None, 0.0
        for pi, p in enumerate(pred):
            if pi in used:
                continue
            score = mask_iou(t["mask_rle"], p.get("mask_rle"))
            if score.scored and score.value > best_iou:
                best, best_iou = pi, score.value
        if best is not None and best_iou >= iou_threshold:
            used.add(best)
            matched += 1
            pairs.append({"truth": ti, "predicted": best, "iou": best_iou})
    precision = matched / len(pred)
    recall = matched / len(truth)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return Score("set_overlap", f1, n=len(truth),
                 detail={"precision": precision, "recall": recall, "matched": matched,
                         "truth_fragments": len(truth), "predicted_fragments": len(pred),
                         "iou_threshold": iou_threshold, "pairs": pairs})


def fragment_membership_agreement(truth_groups: Sequence[Sequence[str]],
                                  predicted_groups: Optional[Sequence[Sequence[str]]]) -> Score:
    """Do two partitions of the same fragments agree about which pieces go together?

    Scored pairwise, over every pair of fragments: the fraction of pairs on which the two
    partitions agree about together-or-apart. That is the right unit because GROUPING IS THE CLAIM
    — a producer that gets every fragment right and every grouping wrong is answering a different
    question from the one `extent.fused_hypothesis` asks, and a per-fragment score would not show
    it. It is also invariant to what the groups are called, which they should be.
    """
    if predicted_groups is None:
        return refuse("set_overlap", "the producer proposed no grouping")
    def index(groups: Sequence[Sequence[str]]) -> Dict[str, int]:
        return {m: gi for gi, group in enumerate(groups) for m in group}
    t_index, p_index = index(truth_groups), index(predicted_groups)
    members = sorted(set(t_index) & set(p_index))
    missing = sorted(set(t_index) ^ set(p_index))
    if len(members) < 2:
        return refuse("set_overlap",
                      "fewer than two fragments are named by both the annotation and the "
                      "producer, so there is no pair to agree or disagree about",
                      shared_members=members, unshared=missing)
    agree = total = 0
    for i in range(len(members)):
        for j in range(i + 1, len(members)):
            a, b = members[i], members[j]
            total += 1
            if (t_index[a] == t_index[b]) == (p_index[a] == p_index[b]):
                agree += 1
    return Score("set_overlap", agree / total, n=total, unit="pairs",
                 detail={"members_compared": len(members), "unshared_members": missing,
                         "note": "pairwise together-or-apart agreement, so the score does not "
                                 "depend on what the groups were named"})


# ── 5. fusion hypotheses ─────────────────────────────────────────────────────

GROUND_KINDS: Tuple[str, ...] = tuple(_CONTRACT["closed_sets"]["ground_kinds"])


def evidence_completeness(hypothesis: Mapping[str, Any]) -> Score:
    """Did the hypothesis say what it rests on, and were the grounds of declared kinds?

    NOT A JUDGEMENT OF THE HYPOTHESIS. A well-grounded wrong reading scores well here and badly on
    `verdict_agreement`, and keeping the two apart is the whole reason both exist: the contract
    permits a hypothesis with no grounds, and a reader should be able to see that it took the
    permission. `asserts_hidden_extent` is reported because a hypothesis that claims pixels behind
    an occluder is making a strictly larger claim than one that only groups what is visible.
    """
    grounds = list(hypothesis.get("grounds") or [])
    kinds = [g.get("kind") for g in grounds]
    unknown = [k for k in kinds if k not in GROUND_KINDS]
    weighed = [g for g in grounds if g.get("strength") is not None]
    citing = [g for g in grounds if g.get("cites")]
    if not grounds:
        return Score("evidence_completeness", 0.0, n=0,
                     detail={"grounds": 0,
                             "asserts_hidden_extent": bool(hypothesis.get("asserts_hidden_extent")),
                             "note": "this hypothesis enumerates nothing that supports it. The "
                                     "contract permits that; a reader should weigh it knowing so"})
    score = (
        0.5
        + 0.25 * (len(weighed) / len(grounds))
        + 0.25 * (len(citing) / len(grounds))
    )
    if unknown:
        score = 0.0
    return Score("evidence_completeness", score, n=len(grounds),
                 detail={"grounds": len(grounds), "kinds": kinds, "unknown_kinds": unknown,
                         "weighed": len(weighed), "citing_records": len(citing),
                         "distinct_kinds": len(set(kinds)),
                         "asserts_hidden_extent": bool(hypothesis.get("asserts_hidden_extent")),
                         "note": "0.5 for enumerating any ground at all, then strength and "
                                 "citations. A ground of an unregistered kind zeroes the score: "
                                 "an unrecognised reason is not a weaker reason, it is one "
                                 "nothing can check"})


def verdict_agreement(human_verdicts: Sequence[str],
                      predicted_verdict: Optional[str]) -> Score:
    """Agreement with the humans, over the SET of verdicts they gave.

    THERE IS NO MAJORITY VOTE HERE. Where annotators disagree, the disagreement is a fact about the
    picture and not noise to be averaged away — so the score is the fraction of annotators who said
    what the producer said, and `unanimous` travels beside it. A hypothesis two of three people
    called `wrong` and one called `unclear` is not two-thirds wrong; it is a contested reading, and
    a benchmark that resolves the contest silently has made the annotators' disagreement invisible.
    """
    verdicts = [str(v) for v in human_verdicts]
    if not verdicts:
        return refuse("verdict_agreement", "no human verdict was recorded for this item")
    if predicted_verdict is None:
        return refuse("verdict_agreement", "the producer offered no verdict to compare")
    matches = sum(1 for v in verdicts if v == predicted_verdict)
    return Score("verdict_agreement", matches / len(verdicts), n=len(verdicts), unit="annotators",
                 detail={"human_verdicts": verdicts, "predicted": predicted_verdict,
                         "unanimous": len(set(verdicts)) == 1,
                         "distinct_verdicts": sorted(set(verdicts)),
                         "note": "the fraction of annotators who agree, not a majority vote. "
                                 "Where they disagree, that disagreement is a fact about the "
                                 "picture"})


# ── 6. visible / inferred, never pooled ──────────────────────────────────────

PARTITION_PARTS: Tuple[str, ...] = tuple(_CONTRACT["closed_sets"]["partition_parts"])


@dataclass(frozen=True)
class PartitionScores:
    """Per-part scores, and NO MEAN — the absence is the design.

    An amodal producer that guesses generously scores well on `inferred` and badly on `visible`.
    One number hides exactly that trade, which is the one thing anybody evaluating a completion
    model needs to see. `as_dict` emits the parts and a note saying why there is no summary.
    """
    parts: Dict[str, Score]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "parts": {k: v.as_dict() for k, v in self.parts.items()},
            "no_summary_because": "visible and inferred accuracy are not poolable. A producer that "
                                  "asserts hidden extent generously scores well on one and badly "
                                  "on the other, and a mean is true of neither",
        }

    @property
    def scored_parts(self) -> List[str]:
        return sorted(k for k, v in self.parts.items() if v.scored)


def partition_accuracy(truth: Mapping[str, Mapping[str, Any]],
                       predicted: Optional[Mapping[str, Mapping[str, Any]]]) -> PartitionScores:
    """IoU per partition part, kept apart.

    `truth` and `predicted` are `{part: {"mask_rle": …}}`. A part present in the truth and absent
    from the prediction refuses rather than scoring zero — the producer may simply not implement
    `unknown`, and that is a different finding from getting `unknown` wrong.
    """
    out: Dict[str, Score] = {}
    for part in PARTITION_PARTS:
        t = truth.get(part)
        if t is None:
            continue
        if predicted is None:
            out[part] = refuse("iou", "the producer returned no partition at all")
            continue
        p = predicted.get(part)
        if p is None:
            out[part] = refuse("iou", f"the producer's partition has no {part!r} part. It may not "
                                      f"implement one, which is not the same as getting it wrong")
            continue
        out[part] = mask_iou(t["mask_rle"], p.get("mask_rle"))
    return PartitionScores(parts=out)


# ── 7. hierarchy ─────────────────────────────────────────────────────────────

def hierarchy_consistency(truth_nodes: Sequence[Mapping[str, Any]],
                          predicted_nodes: Optional[Sequence[Mapping[str, Any]]]) -> Score:
    """Do the two trees agree about who is inside whom?

    Scored over ANCESTRY PAIRS rather than over parent links, and that choice matters. A producer
    that inserts one correct intermediate node — a courtyard between a palace and a fountain —
    changes every parent link below it while getting the containment entirely right. Ancestry is
    invariant to that and is what the form actually claims: `occupancy_of_parent` is a measurement
    ABOUT a nesting, and the nesting is the transitive relation.
    """
    if predicted_nodes is None:
        return refuse("tree_edit", "the producer returned no hierarchy")

    def ancestry(nodes: Sequence[Mapping[str, Any]]) -> Tuple[Set[Tuple[str, str]], List[str]]:
        parent = {str(n["node_id"]): (str(n["parent_node_id"])
                                      if n.get("parent_node_id") else None) for n in nodes}
        pairs: Set[Tuple[str, str]] = set()
        cyclic: List[str] = []
        for node in parent:
            seen, cur = set(), parent[node]
            while cur is not None:
                if cur in seen or cur not in parent:
                    if cur in seen:
                        cyclic.append(node)
                    break
                seen.add(cur)
                pairs.add((cur, node))
                cur = parent[cur]
        return pairs, sorted(set(cyclic))

    t_pairs, t_cycles = ancestry(truth_nodes)
    p_pairs, p_cycles = ancestry(predicted_nodes)
    detail: Dict[str, Any] = {
        "truth_pairs": len(t_pairs), "predicted_pairs": len(p_pairs),
        "truth_cyclic_nodes": t_cycles, "predicted_cyclic_nodes": p_cycles,
        "note": "scored over ancestry pairs, so inserting a correct intermediate node is not "
                "counted as breaking every link beneath it",
    }
    if p_cycles:
        return refuse("tree_edit",
                      f"the producer's hierarchy contains a cycle through {', '.join(p_cycles)}. "
                      "A containment cycle is not a badly scoring tree, it is not a tree",
                      **detail)
    if not t_pairs and not p_pairs:
        return Score("tree_edit", 1.0, n=0, detail={**detail, "both_empty": True})
    return Score("tree_edit", len(t_pairs & p_pairs) / max(len(t_pairs | p_pairs), 1),
                 n=len(t_pairs), unit="ancestry pairs", detail=detail)


# ── 8. density ───────────────────────────────────────────────────────────────

def density_count_error(true_count: int, predicted_count: Optional[int]) -> Score:
    """How many. The first of density's two questions, and separable from the second."""
    if predicted_count is None:
        return refuse("count_error", "the producer reported no count")
    return Score("count_error", float(abs(predicted_count - true_count)), n=true_count,
                 unit="members",
                 detail={"true_count": true_count, "predicted_count": predicted_count,
                         "relative": (abs(predicted_count - true_count) / true_count)
                                     if true_count else None})


def density_localisation_error(true_points: Sequence[Sequence[float]],
                               predicted_points: Optional[Sequence[Sequence[float]]]) -> Score:
    """Where, given how many — mean nearest-neighbour distance, both directions.

    SYMMETRIC ON PURPOSE. One-directional nearest-neighbour distance is trivially gamed by
    predicting one point in the middle of every cluster, or by predicting a thousand points
    everywhere. Averaging truth→predicted with predicted→truth penalises both.
    """
    if predicted_points is None:
        return refuse("localisation_error", "the producer reported no positions")
    t = [(float(x), float(y)) for x, y in true_points]
    p = [(float(x), float(y)) for x, y in predicted_points]
    if not t and not p:
        return Score("localisation_error", 0.0, n=0, unit="normalized distance",
                     detail={"both_empty": True})
    if not t or not p:
        return refuse("localisation_error",
                      "one side has points and the other has none, so there is no distance to "
                      "measure. The count error is the finding here",
                      true_points=len(t), predicted_points=len(p))

    def nearest_mean(a: Sequence[Tuple[float, float]],
                     b: Sequence[Tuple[float, float]]) -> float:
        return sum(min(math.dist(x, y) for y in b) for x in a) / len(a)

    forward, backward = nearest_mean(t, p), nearest_mean(p, t)
    return Score("localisation_error", (forward + backward) / 2, n=len(t),
                 unit="normalized distance",
                 detail={"truth_to_predicted": forward, "predicted_to_truth": backward,
                         "note": "symmetric: a single point in the middle of a cluster scores "
                                 "well one way and badly the other"})


# ── 9. graphs and trees, with direction ──────────────────────────────────────

def graph_score(truth_edges: Sequence[Mapping[str, Any]],
                predicted_edges: Optional[Sequence[Mapping[str, Any]]]) -> Score:
    """Edge precision and recall, where a directed edge's direction is part of its identity.

    THE UNDIRECTED EDGES ARE NORMALISED and the directed ones are not. `a meets b` and `b meets a`
    are one measurement written two ways; `a contains b` and `b contains a` are two different and
    incompatible claims. Folding them together — as an undirected graph-edit distance does —
    makes a producer that reverses every containment look perfect.
    """
    if predicted_edges is None:
        return refuse("graph_edit", "the producer returned no graph")

    def key(edge: Mapping[str, Any]) -> Tuple[str, str, str, bool]:
        s, t = str(edge["source"]), str(edge["target"])
        directed = bool(edge.get("directed"))
        kind = str(edge.get("kind", ""))
        if not directed and t < s:
            s, t = t, s
        return (s, t, kind, directed)

    t_keys = {key(e) for e in truth_edges}
    p_keys = {key(e) for e in predicted_edges}
    if not t_keys and not p_keys:
        return Score("graph_edit", 1.0, n=0, detail={"both_empty": True})
    if not p_keys:
        return Score("graph_edit", 0.0, n=len(t_keys),
                     detail={"precision": None, "recall": 0.0,
                             "note": "the producer recorded no edge at all"})
    matched = len(t_keys & p_keys)
    precision = matched / len(p_keys)
    recall = matched / len(t_keys) if t_keys else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return Score("graph_edit", f1, n=len(t_keys), unit="edges",
                 detail={"precision": precision, "recall": recall, "matched": matched,
                         "truth_edges": len(t_keys), "predicted_edges": len(p_keys),
                         "note": "undirected edges normalised by endpoint order; directed edges "
                                 "not — reversing a containment is a wrong edge"})


def direction_accuracy(truth_edges: Sequence[Mapping[str, Any]],
                       predicted_edges: Optional[Sequence[Mapping[str, Any]]]) -> Score:
    """Of the directed edges BOTH sides found, how many point the same way?

    Scored only over edges present in both, which is what makes it readable: mixing "found the edge
    and reversed it" with "never found the edge" gives one number that cannot distinguish a
    producer with a systematic direction bug from one that finds nothing.
    """
    if predicted_edges is None:
        return refuse("direction_accuracy", "the producer returned no graph")
    t_directed = {(str(e["source"]), str(e["target"])): e for e in truth_edges
                  if e.get("directed")}
    p_directed = {(str(e["source"]), str(e["target"])): e for e in predicted_edges
                  if e.get("directed")}
    if not t_directed:
        return refuse("direction_accuracy",
                      "no edge in the truth is directed, so direction cannot be right or wrong "
                      "here. That is a property of this scene, not a gap in the producer")
    right = wrong = 0
    reversed_pairs = []
    for (s, t) in t_directed:
        if (s, t) in p_directed:
            right += 1
        elif (t, s) in p_directed:
            wrong += 1
            reversed_pairs.append({"truth": f"{s}→{t}", "predicted": f"{t}→{s}"})
    found = right + wrong
    if not found:
        return refuse("direction_accuracy",
                      "the producer found none of the directed edges, so none of its directions "
                      "can be scored. The edge recall is the finding here",
                      truth_directed=len(t_directed))
    return Score("direction_accuracy", right / found, n=found, unit="directed edges",
                 detail={"correct": right, "reversed": wrong, "reversed_pairs": reversed_pairs,
                         "truth_directed": len(t_directed),
                         "note": "scored only over edges both sides found, so a direction bug is "
                                 "readable separately from a recall failure"})


# ── 10. transitions ──────────────────────────────────────────────────────────

def transition_sensitivity(perturbations: Sequence[Mapping[str, Any]],
                           detected: Optional[Sequence[str]]) -> Score:
    """Of the known changes, how many were noticed — and how many were imagined?

    THE FALSE POSITIVES ARE THE HALF THAT MATTERS. A producer that reports every pair as
    `changed` has perfect sensitivity and is useless, so the null perturbations — the ones where
    nothing moved — are scored alongside, and a detection on one of those is counted and named.
    """
    if detected is None:
        return refuse("transition_sensitivity", "the producer reported no transitions")
    detected_set = {str(d) for d in detected}
    real = [p for p in perturbations if p.get("changes")]
    null = [p for p in perturbations if not p.get("changes")]
    if not real:
        return refuse("transition_sensitivity",
                      "no perturbation in this set actually changes a relation, so there is "
                      "nothing to be sensitive to")
    hits = [p["id"] for p in real if str(p["id"]) in detected_set]
    false = [p["id"] for p in null if str(p["id"]) in detected_set]
    return Score("transition_sensitivity", len(hits) / len(real), n=len(real),
                 unit="perturbations",
                 detail={"detected": len(hits), "real_changes": len(real),
                         "null_perturbations": len(null), "false_alarms": false,
                         "false_alarm_rate": (len(false) / len(null)) if null else None,
                         "note": "a producer that calls everything changed has perfect "
                                 "sensitivity; the false alarms beside it are what stop that "
                                 "from looking like success"})


# ── 11. hypotheses, without forced collapse ──────────────────────────────────

def hypothesis_coverage(legitimate: Sequence[Mapping[str, Any]],
                        offered: Optional[Sequence[Mapping[str, Any]]],
                        *, iou_threshold: float = 0.5) -> Score:
    """How much of a SET of legitimate readings did the producer reach?

    THERE IS NO CORRECT ANSWER HERE AND THIS FUNCTION WILL NOT INVENT ONE. Where the annotation
    declares that several extent ontologies are legitimate — the figure with or without its
    shadow, the table with or without what is on it — a benchmark that scores against the first
    one is measuring its own tie-break. So the score is coverage over the whole declared set, and
    three further facts travel beside it:

        `missed`         legitimate readings nothing reached
        `unmatched`      readings the producer offered that no annotator called legitimate
        `collapsed`      whether the producer returned ONE reading where several are legitimate,
                         which is not an error and is a thing to know

    A producer that returns one of three legitimate readings scores 1/3 and is not wrong; a
    producer that returns all three scores 1.0 and has offered a person a choice. The difference
    between those two is a design decision, not a defect, and the number does not hide it.
    """
    if offered is None:
        return refuse("hypothesis_coverage", "the producer offered no hypothesis set")
    if not legitimate:
        return refuse("hypothesis_coverage",
                      "the annotation declares no legitimate reading for this item, so coverage "
                      "is undefined. An item with no agreed reading is a finding about the item")
    # MATCHED BEST-FIRST, NOT FIRST-OVER-THRESHOLD, and the difference is not academic here.
    # Two legitimate readings of one thing are often similar — a figure with and without its
    # shadow scores 0.77 against each other — so a first-past-the-post walk assigns the producer's
    # answer to whichever reading the annotator happened to list first, and reports the other as
    # missed. That would make the ORDER OF THE ANNOTATION change the score, which is the same
    # forced collapse this function exists to avoid, arriving through the back door.
    candidates: List[Tuple[float, int, int]] = []
    for li, leg in enumerate(legitimate):
        for oi, off in enumerate(offered):
            score = mask_iou(leg["mask_rle"], off.get("mask_rle"))
            if score.scored and score.value >= iou_threshold:
                candidates.append((score.value, li, oi))
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    used: Set[int] = set()
    claimed: Set[int] = set()
    reached: List[Dict[str, Any]] = []
    for value, li, oi in candidates:
        if oi in used or li in claimed:
            continue
        used.add(oi)
        claimed.add(li)
        reached.append({"legitimate": legitimate[li].get("reading_id", li),
                        "offered": offered[oi].get("alternative_id", oi),
                        "iou": value})
    missed = [leg.get("reading_id", i) for i, leg in enumerate(legitimate)
              if not any(r["legitimate"] == leg.get("reading_id", i) for r in reached)]
    unmatched = [off.get("alternative_id", i) for i, off in enumerate(offered) if i not in used]
    return Score("hypothesis_coverage", len(reached) / len(legitimate), n=len(legitimate),
                 unit="readings",
                 detail={"reached": reached, "missed": missed, "unmatched_offered": unmatched,
                         "legitimate_readings": len(legitimate), "offered": len(offered),
                         "collapsed": len(offered) == 1 and len(legitimate) > 1,
                         "iou_threshold": iou_threshold,
                         "note": "coverage over the declared set, matched best-first so the "
                                 "order the annotator listed the readings in cannot change the "
                                 "score. Returning one of three legitimate readings is not an "
                                 "error; it is a different product decision from returning all "
                                 "three, and the number says which"})


def extent_ontology_agreement(legitimate: Sequence[Mapping[str, Any]],
                              predicted: Optional[Mapping[str, Any]]) -> Score:
    """Score one predicted extent against ALL legitimate extents, and report the best.

    The single-answer companion to `hypothesis_coverage`, for the forms that return one mask. It
    still refuses to name a correct answer: it reports which legitimate reading the producer
    landed nearest to and the IoU against every one of them, so a producer that consistently
    chooses "the figure without its shadow" is visible as a consistent ontology rather than as a
    scatter of middling scores.
    """
    if predicted is None:
        return refuse("iou", "the producer returned no extent")
    if not legitimate:
        return refuse("iou", "the annotation declares no legitimate extent for this item")
    scores = []
    for i, leg in enumerate(legitimate):
        s = mask_iou(leg["mask_rle"], predicted)
        scores.append({"reading_id": leg.get("reading_id", i),
                       "label": leg.get("label"),
                       "iou": s.value, "refused": s.refused})
    scored = [s for s in scores if s["iou"] is not None]
    if not scored:
        return refuse("iou", "no legitimate reading could be compared with the prediction; "
                             + (scores[0]["refused"] or "reason unrecorded"),
                      per_reading=scores)
    best = max(scored, key=lambda s: s["iou"])
    return Score("iou", best["iou"], n=len(legitimate),
                 detail={"matched_reading": best["reading_id"], "label": best.get("label"),
                         "per_reading": scores, "readings": len(legitimate),
                         "note": "the best of several legitimate readings, with every one of "
                                 "them reported. A producer that always lands on the same "
                                 "reading has an ontology, not a scatter"})


# ── aggregation ──────────────────────────────────────────────────────────────

def aggregate(scores: Sequence[Score]) -> Dict[str, Any]:
    """A summary that counts refusals rather than absorbing them.

    `mean` is over the SCORED items only, and `coverage` says what fraction of the attempted items
    that is. Reporting a mean without the coverage beside it is the specific way a benchmark
    flatters a producer that declines the hard cases: it answers ten of a hundred, gets them
    right, and prints 1.0.
    """
    by_metric: Dict[str, List[Score]] = {}
    for s in scores:
        by_metric.setdefault(s.metric, []).append(s)
    out: Dict[str, Any] = {"metrics": {}, "total": len(scores),
                           "scored": sum(1 for s in scores if s.scored),
                           "refused": sum(1 for s in scores if not s.scored)}
    for metric, group in sorted(by_metric.items()):
        scored = [s for s in group if s.scored]
        refusals = [s.refused for s in group if not s.scored]
        out["metrics"][metric] = {
            "n": len(group),
            "scored": len(scored),
            "refused": len(refusals),
            "coverage": len(scored) / len(group) if group else None,
            "mean": (sum(s.value for s in scored) / len(scored)) if scored else None,
            "unit": group[0].unit,
            "refusals": sorted(set(refusals)),
            "is_contract_method": metric in COMPARISON_METHODS,
        }
    out["note"] = ("`mean` is over the scored items only. Read it with `coverage`: a producer that "
                   "answers ten of a hundred and gets them right prints 1.0 here.")
    return out


__all__ = [
    "ALL_METRICS", "COMPARISON_METHODS", "EXTENSIONS", "GROUND_KINDS", "PARTITION_PARTS",
    "PartitionScores", "Score",
    "aggregate", "boundary_f1", "contour_agreement", "density_count_error",
    "density_localisation_error", "direction_accuracy", "evidence_completeness",
    "extent_ontology_agreement", "field_calibration", "field_l1",
    "fragment_membership_agreement", "fragment_precision_recall", "graph_score",
    "hierarchy_consistency", "hole_count_error", "hypothesis_coverage", "mask_iou",
    "partition_accuracy", "refuse", "ring_reconstruction", "transition_sensitivity",
    "verdict_agreement",
]
