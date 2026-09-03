#!/usr/bin/env python3
"""
PERCEPTUAL-FORMS-001F — the form benchmark: corpus, controls, annotation protocol, matrix.

WHAT THIS LANE IS FOR. Lane A registered nineteen perceptual forms and froze their payloads.
Lane B and Lane C built exact producers for some of them. Lane C's model laboratory says, in its
own manifest, that "the Lane F corpus of real works is the actual test and does not exist yet".
This is that corpus, plus the thing a corpus is useless without: a way of scoring answers that
does not quietly decide what the question was.

THREE PARTS, AND THEY ARE DELIBERATELY SEPARATE.

  THE ATLAS  `research/perception_lab/form_atlas/atlas.json` — real works, resolved to an
             institution and an accession number, with their rights status recorded rather than
             assumed. NO IMAGE BYTES ARE COMMITTED. Two of the six works the build names are in
             copyright until the 2040s; two more are public-domain paintings whose only available
             reproductions are not freely licensed. A manifest that pointed at those and said
             nothing would be the most expensive kind of quiet.

  THE CONTROLS  `research/perception_lab/benchmarks/controls/` — twelve synthetic scenes drawn
             here, whose ground truth is known BY CONSTRUCTION rather than by annotation. A donut
             has one hole because a hole was punched in it. These are what a producer meets before
             it is allowed near a painting, and they are the only place in this benchmark where
             the answer is not a matter of opinion.

  THE MATRIX  `research/perception_lab/benchmarks/matrix.json` — one row per form, naming its
             real image, its control, the question a person is actually asking, the action they
             take, the metric, the failures worth photographing, and the screenshot required.

WHY THE GROUND TRUTH IS CONSTRUCTED AND THEN CHECKED. Each control is drawn by placing pixels
deliberately, so the fragment count and the hole count are facts about the drawing. The suite then
asserts that Lane B's `extent_forms` substrate agrees with the construction. That is not circular:
if it ever disagrees, one of the two is wrong and the disagreement is the finding. Deriving the
truth FROM the substrate would have made the check vacuous.

THE CONNECTIVITY PAIRING IS BORROWED, NOT CHOSEN. `extent_forms.raster` declares foreground
4-connected and background 8-connected, and every count here is under that pairing. Two islands
touching at a corner are two fragments; the void between them is one void and encloses nothing.
Choose the other pairing and half the numbers in this file change — so it is imported rather than
re-typed, and a control exists specifically to catch a producer that assumed the other one.

STDLIB ONLY. `numpy` and `pillow` are in `requirements-ml.txt`, which CI does not install; a
benchmark that only runs where torch is installed is a benchmark nobody runs on a pull request.
Previews are ASCII for the same reason and for a better one: a text preview shows up in a diff,
and a PNG does not.

USAGE

    python scripts/perception_lab_form_benchmark.py controls          # write the controls
    python scripts/perception_lab_form_benchmark.py controls --check  # verify no drift
    python scripts/perception_lab_form_benchmark.py matrix            # write the matrix
    python scripts/perception_lab_form_benchmark.py matrix --check
    python scripts/perception_lab_form_benchmark.py atlas             # validate the corpus
    python scripts/perception_lab_form_benchmark.py annotations       # validate the annotations
    python scripts/perception_lab_form_benchmark.py report            # coverage and gaps
    python scripts/perception_lab_form_benchmark.py verify            # every check, one exit code

WIRES NOTHING. No route, no operation, no registry entry, no model. It writes under
`research/perception_lab/` and reads the contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.services.mask_geometry import rle_encode  # noqa: E402
from backend.services.perception_lab.extent_forms.raster import (  # noqa: E402
    BACKGROUND_CONNECTIVITY,
    FOREGROUND_CONNECTIVITY,
)
from perception_lab_form_scoring import (  # noqa: E402
    ALL_METRICS,
    COMPARISON_METHODS,
    EXTENSIONS,
)

CONTRACT_PATH = REPO_ROOT / "contracts" / "perception-lab.v1.json"
RESEARCH = REPO_ROOT / "research" / "perception_lab"
ATLAS_DIR = RESEARCH / "form_atlas"
BENCH_DIR = RESEARCH / "benchmarks"
CONTROLS_DIR = BENCH_DIR / "controls"
ANNOTATIONS_DIR = BENCH_DIR / "annotations"
SCHEMAS_DIR = BENCH_DIR / "schemas"
MATRIX_PATH = BENCH_DIR / "matrix.json"
ATLAS_PATH = ATLAS_DIR / "atlas.json"

#: Lane C's model-trial controls. Referenced, never redrawn — where a scene already exists for the
#: model laboratory, this benchmark points at it by digest rather than making a second one that can
#: drift from it.
MODEL_TRIAL_CONTROLS = RESEARCH / "model_trials" / "controls" / "manifest.json"

with CONTRACT_PATH.open(encoding="utf-8") as handle:
    CONTRACT = json.load(handle)

FORMS: Dict[str, Dict[str, Any]] = {f["key"]: f for f in CONTRACT["perceptual_forms"]}
FORM_KEYS: Tuple[str, ...] = tuple(CONTRACT["closed_sets"]["perceptual_forms"])

#: The raster every control is drawn on. Big enough for real structure — nested voids, a
#: four-piece chain, a one-pixel bridge — and small enough that an exact flood fill in pure Python
#: is instant and the committed RLE stays readable in a diff.
SIZE = 64


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── drawing, in pure Python ──────────────────────────────────────────────────

def blank() -> bytearray:
    return bytearray(SIZE * SIZE)


def rect(bits: bytearray, r0: int, c0: int, r1: int, c1: int, value: int = 1) -> bytearray:
    """Inclusive-exclusive box, clipped to the frame."""
    for r in range(max(0, r0), min(SIZE, r1)):
        for c in range(max(0, c0), min(SIZE, c1)):
            bits[r * SIZE + c] = value
    return bits


def disc(bits: bytearray, cr: int, cc: int, radius: int, value: int = 1) -> bytearray:
    for r in range(max(0, cr - radius), min(SIZE, cr + radius + 1)):
        for c in range(max(0, cc - radius), min(SIZE, cc + radius + 1)):
            if (r - cr) ** 2 + (c - cc) ** 2 <= radius * radius:
                bits[r * SIZE + c] = value
    return bits


def encode(bits: Sequence[int]) -> Dict[str, Any]:
    return rle_encode(bytearray(bits), SIZE, SIZE)


def area_fraction(bits: Sequence[int]) -> float:
    return round(sum(1 for b in bits if b) / (SIZE * SIZE), 6)


def box_of(bits: Sequence[int]) -> Optional[Dict[str, float]]:
    rows = [i // SIZE for i, b in enumerate(bits) if b]
    cols = [i % SIZE for i, b in enumerate(bits) if b]
    if not rows:
        return None
    return {"x": round(min(cols) / SIZE, 6), "y": round(min(rows) / SIZE, 6),
            "w": round((max(cols) - min(cols) + 1) / SIZE, 6),
            "h": round((max(rows) - min(rows) + 1) / SIZE, 6)}


#: What `holes` means everywhere in this manifest, said once.
#:
#: `extent_forms.holes.voids_of` returns EVERY component of a piece's complement and flags each
#: `enclosed` — so a plain rectangle has one void (the unbounded exterior, not enclosed) and a
#: donut has two. This benchmark's `holes` counts the ENCLOSED ones only, because that is what
#: `extent.hole_set` asks about and what `enclosed` exists to distinguish. Both numbers travel, so
#: a producer can be checked against either without anybody guessing which convention was meant.
#: A hole count reported without this sentence is not comparable with anything.
HOLES_COUNTED_AS = ("enclosed voids only. The unbounded exterior is a complement component and is "
                    "not a hole; `complement_components` carries the other count beside it")


def preview(bits: Sequence[int], step: int = 2) -> List[str]:
    """An ASCII preview, sampled.

    Committed because it lands in a DIFF. A control that changes shape shows the change as moved
    characters in a review; a PNG shows a binary blob and a new digest, and a reviewer has to take
    the digest on trust.
    """
    out = []
    for r in range(0, SIZE, step):
        out.append("".join("#" if bits[r * SIZE + c] else "." for c in range(0, SIZE, step)))
    return out


# ── the twelve controls ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Control:
    name: str
    forms: Tuple[str, ...]
    what: str
    the_trap: str
    build: Callable[[], Dict[str, Any]]
    also_see: Optional[str] = None


def c_solid_mask() -> Dict[str, Any]:
    """The negative control for every void and fragment claim."""
    bits = rect(blank(), 16, 16, 48, 48)
    return {
        "instances": {"inst_solid": encode(bits)},
        "truth": {
            "fragments": 1,
            "holes": 0,
            "holes_counted_as": HOLES_COUNTED_AS,
            "complement_components": [1],
            "rings": {"outer": 1, "inner": 0},
            "area_fraction": area_fraction(bits),
            "box": box_of(bits),
            "note": "a producer that reports a void here has found its own smoothing. A producer "
                    "that reports two fragments has split a rectangle",
        },
        "preview": preview(bits),
    }


def c_donut() -> Dict[str, Any]:
    """One piece, one enclosed void. The simplest thing `extent.hole_set` exists to say."""
    bits = rect(blank(), 12, 12, 52, 52)
    rect(bits, 24, 24, 40, 40, 0)
    return {
        "instances": {"inst_donut": encode(bits)},
        "truth": {
            "fragments": 1,
            "holes": 1,
            "holes_counted_as": HOLES_COUNTED_AS,
            "complement_components": [2],
            "holes_enclosed": [True],
            "rings": {"outer": 1, "inner": 1},
            "hole_area_fraction": round((16 * 16) / (SIZE * SIZE), 6),
            "area_fraction": area_fraction(bits),
            "note": "the inner ring bounds a void. Drawn identically to the outer ring it reads "
                    "as a second object rather than as a hole in the first",
        },
        "preview": preview(bits),
    }


def c_nested_holes() -> Dict[str, Any]:
    """A void containing an island containing a void — two foreground pieces, one hole each.

    THE TRAP IS THE COUNT. Naively "this shape has two holes" is wrong: the island is a separate
    foreground component under any pairing, and the hole inside IT belongs to the island. A
    producer that reports one piece with two voids has flattened the nesting the form exists to
    record.
    """
    bits = rect(blank(), 6, 6, 58, 58)
    rect(bits, 14, 14, 50, 50, 0)          # the outer void
    rect(bits, 22, 22, 42, 42, 1)          # the island inside it
    rect(bits, 28, 28, 36, 36, 0)          # the void inside the island
    return {
        "instances": {"inst_nested": encode(bits)},
        "truth": {
            "fragments": 2,
            "fragment_holes": [1, 1],
            "holes": 2,
            "holes_counted_as": HOLES_COUNTED_AS,
            "complement_components": [2, 2],
            "holes_enclosed": [True, True],
            "depth": 2,
            "note": "two foreground pieces, one void each. A producer reporting one piece with "
                    "two voids has flattened the nesting; a producer reporting one void has "
                    "missed the inner one entirely",
        },
        "preview": preview(bits),
    }


def c_disconnected_fragments() -> Dict[str, Any]:
    """Four blobs, two of which touch ONLY at a corner.

    THE PAIRING CONTROL. Under `FOREGROUND_CONNECTIVITY = 4` the corner-touching pair is two
    pieces, and the single background void that runs between them encloses nothing. Under the
    other pairing both answers flip. A producer that reports four fragments here has assumed
    8-connected foreground and will disagree with every count in this benchmark for a reason that
    is about digital topology rather than about the picture.
    """
    bits = blank()
    rect(bits, 8, 8, 20, 20)                # A
    rect(bits, 20, 20, 32, 32)              # B — shares exactly one corner with A at (20,20)
    rect(bits, 8, 44, 20, 56)               # C
    rect(bits, 44, 8, 56, 20)               # D
    rect(bits, 44, 44, 56, 56)              # E
    return {
        "instances": {"inst_scatter": encode(bits)},
        "truth": {
            "fragments": 5,
            "foreground_connectivity": FOREGROUND_CONNECTIVITY,
            "background_connectivity": BACKGROUND_CONNECTIVITY,
            "corner_touching_pair": ["A", "B"],
            "holes": 0,
            "holes_counted_as": HOLES_COUNTED_AS,
            "complement_components": [1, 1, 1, 1, 1],
            "note": "A and B share one corner and are TWO pieces under the declared pairing. A "
                    "producer that reports four has assumed 8-connected foreground",
        },
        "preview": preview(bits),
    }


def c_false_similarity() -> Dict[str, Any]:
    """Three identical blobs; two of them belong together and the third does not.

    Appearance is useless here on purpose: all three are the same shape and the same size. The
    grouping the annotation calls legitimate rests on POSITION — two sit on a common baseline and
    the third does not — so a producer that groups by similarity gets the wrong pair, confidently.
    """
    a, b, c = blank(), blank(), blank()
    disc(a, 40, 14, 7)
    disc(b, 40, 30, 7)          # same baseline as A
    disc(c, 14, 50, 7)          # same blob, different place
    return {
        "instances": {"frag_a": encode(a), "frag_b": encode(b), "frag_c": encode(c)},
        "truth": {
            "fragments": 3,
            "legitimate_groupings": [
                {"grouping_id": "baseline", "groups": [["frag_a", "frag_b"], ["frag_c"]],
                 "why": "A and B rest on one baseline; C is elsewhere in the frame"},
            ],
            "similarity_would_give": [["frag_a", "frag_b", "frag_c"]],
            "note": "all three are the same disc. A producer grouping on appearance gets one "
                    "group of three, confidently and wrongly",
        },
        "preview": preview([x | y | z for x, y, z in zip(a, b, c)]),
    }


def c_soft_fringe() -> Dict[str, Any]:
    """A field with exact, hand-computed values: a core, a linear ramp, and a zero ground.

    THE VALUES ARE THE MEASUREMENT. `true_values` is fractional COVERAGE — what portion of each
    cell the thing occupies — and it is not confidence, not a class probability, and not model
    doubt. A producer that returns its own uncertainty here will look calibrated on the core and
    wrong everywhere the ramp is, which is exactly the confusion the form was registered to end.
    """
    shape = (16, 16)
    values: List[float] = []
    for r in range(shape[0]):
        for c in range(shape[1]):
            d = max(abs(r - 7.5), abs(c - 7.5))
            if d <= 3.5:
                v = 1.0
            elif d >= 7.5:
                v = 0.0
            else:
                v = round((7.5 - d) / 4.0, 6)
            values.append(v)
    soft = [v for v in values if 0.0 < v < 1.0]
    return {
        "field": {
            "field_shape": list(shape),
            "coordinate_system": "mask_rle_hw",
            "value_range": [0.0, 1.0],
            "derivation": "direct_probability",
            "inline_values": values,
        },
        "truth": {
            "cells": len(values),
            "true_values": values,
            "mean": round(sum(values) / len(values), 6),
            "soft_cells": len(soft),
            "binary_cells": len(values) - len(soft),
            "threshold_at_half_gives_cells": sum(1 for v in values if v >= 0.5),
            "note": "fractional coverage, not confidence. A producer returning its own doubt "
                    "will match on the core and miss the whole ramp",
        },
        "preview": ["".join(" .:-=+*#%@"[min(9, int(values[r * 16 + c] * 9.5))]
                            for c in range(16)) for r in range(16)],
    }


def c_partition() -> Dict[str, Any]:
    """A figure behind a bar, and a third region nobody can settle.

    Three parts, and the third is the one benchmarks usually leave out. `visible` is what survives
    the occluder. `inferred` is known EXACTLY because the whole figure was drawn before the bar
    covered it. `unknown` is where the figure runs off the bottom of the frame: it may continue
    and it may not, nothing in the picture says, and a producer that assigns those pixels to
    either of the other two parts has asserted something the image does not contain.
    """
    whole = rect(blank(), 10, 24, 60, 40)          # runs off the bottom edge
    bar = rect(blank(), 28, 0, 38, SIZE)
    visible = bytearray(1 if (w and not b and r < 52) else 0
                        for r, (w, b) in ((i // SIZE, (whole[i], bar[i])) for i in range(SIZE * SIZE)))
    inferred = bytearray(1 if (w and b) else 0 for w, b in zip(whole, bar))
    unknown = bytearray(1 if (w and i // SIZE >= 52) else 0 for i, w in enumerate(whole))
    return {
        "instances": {"inst_visible": encode(visible), "inst_inferred": encode(inferred),
                      "inst_unknown": encode(unknown), "inst_occluder": encode(bar)},
        "truth": {
            "parts": {
                "visible": {"area_fraction": area_fraction(visible), "epistemic_status": "measured"},
                "inferred": {"area_fraction": area_fraction(inferred),
                             "epistemic_status": "uncertain"},
                "unknown": {"area_fraction": area_fraction(unknown),
                            "epistemic_status": "uncertain"},
            },
            "coverage_sums_to": round(area_fraction(visible) + area_fraction(inferred)
                                      + area_fraction(unknown), 6),
            "note": "the inferred part is exact because the figure was drawn before the bar "
                    "covered it. The unknown part runs off the frame and is settled by nothing",
        },
        "preview": preview([2 if u else (1 if (v or f) else 0)
                            for v, f, u in zip(visible, inferred, unknown)]),
    }


def c_density_peaks() -> Dict[str, Any]:
    """Twenty-four marks in two clusters of known size, and one stray.

    COUNT AND PLACE ARE SEPARATE QUESTIONS and this control lets them fail separately: a producer
    can return 25 marks smeared evenly (right count, wrong place) or three tight clusters of nine
    (wrong count, right place), and `count_error` and `localisation_error` come apart accordingly.
    """
    bits = blank()
    points: List[List[float]] = []
    for i in range(12):                                   # the dense cluster, east
        r, c = 14 + (i // 4) * 5, 40 + (i % 4) * 5
        disc(bits, r, c, 1)
        points.append([round(c / SIZE, 6), round(r / SIZE, 6)])
    for i in range(12):                                   # the sparse cluster, west
        r, c = 34 + (i // 4) * 8, 6 + (i % 4) * 8
        disc(bits, r, c, 1)
        points.append([round(c / SIZE, 6), round(r / SIZE, 6)])
    disc(bits, 4, 4, 1)                                   # the stray
    points.append([round(4 / SIZE, 6), round(4 / SIZE, 6)])
    east = sum(1 for x, _ in points if x >= 0.5)
    return {
        "instances": {"inst_marks": encode(bits)},
        "truth": {
            "true_count": len(points),
            "points": points,
            "east_count": east,
            "west_count": len(points) - east,
            "clusters": 2,
            "strays": 1,
            "note": "the stray is deliberate. A producer that reports two clusters and drops it "
                    "has a count error of one and a localisation error of nearly zero",
        },
        "preview": preview(bits),
    }


def c_containment_tree() -> Dict[str, Any]:
    """Nested boxes: A ⊃ B ⊃ C, A ⊃ D, and E outside everything.

    Scored over ANCESTRY, so a producer that inserts a correct intermediate node is not punished
    for changing every parent link beneath it. The disjoint E is here because a tree with nothing
    outside it cannot show whether a producer knows the difference between "not contained" and
    "not examined".
    """
    a, b, c, d, e = blank(), blank(), blank(), blank(), blank()
    rect(a, 4, 4, 52, 52)
    rect(b, 10, 10, 34, 34)
    rect(c, 16, 16, 26, 26)
    rect(d, 38, 10, 48, 30)
    rect(e, 54, 54, 62, 62)
    return {
        "instances": {"node_a": encode(a), "node_b": encode(b), "node_c": encode(c),
                      "node_d": encode(d), "node_e": encode(e)},
        "truth": {
            "nodes": [
                {"node_id": "node_a", "parent_node_id": None},
                {"node_id": "node_b", "parent_node_id": "node_a"},
                {"node_id": "node_c", "parent_node_id": "node_b"},
                {"node_id": "node_d", "parent_node_id": "node_a"},
                {"node_id": "node_e", "parent_node_id": None},
            ],
            "root_node_ids": ["node_a", "node_e"],
            "ancestry_pairs": [["node_a", "node_b"], ["node_a", "node_c"], ["node_a", "node_d"],
                               ["node_b", "node_c"]],
            "occupancy_of_parent": {"node_b": round((24 * 24) / (48 * 48), 6),
                                    "node_c": round((10 * 10) / (24 * 24), 6),
                                    "node_d": round((10 * 20) / (48 * 48), 6)},
            "pairs_examined": 10,
            "note": "E is contained by nothing and that is a measurement. A forest, not a tree — "
                    "a producer that forces a single root has invented a container",
        },
        "preview": preview([1 if (x or y or z or w or v) else 0
                            for x, y, z, w, v in zip(a, b, c, d, e)]),
    }


def c_adjacency_graph() -> Dict[str, Any]:
    """A chain of four pieces that meet, plus one that overlaps — six pairs, three kinds.

    Every pair is examined and the record says so, which is what makes this a control for the
    thing a node-link drawing cannot show: the difference between a pair that was examined and
    found unrelated and a pair nobody looked at.
    """
    p1, p2, p3, p4 = blank(), blank(), blank(), blank()
    rect(p1, 20, 4, 34, 18)
    rect(p2, 20, 18, 34, 32)      # shares the edge at column 18 with p1 → meets
    rect(p3, 20, 32, 34, 46)      # meets p2
    rect(p4, 20, 40, 34, 54)      # OVERLAPS p3, columns 40..46
    overlap = bytearray(1 if (x and y) else 0 for x, y in zip(p3, p4))
    return {
        "instances": {"pier_1": encode(p1), "pier_2": encode(p2),
                      "pier_3": encode(p3), "pier_4": encode(p4)},
        "truth": {
            "nodes": ["pier_1", "pier_2", "pier_3", "pier_4"],
            "edges": [
                {"source": "pier_1", "target": "pier_2", "kind": "meets", "directed": False},
                {"source": "pier_2", "target": "pier_3", "kind": "meets", "directed": False},
                {"source": "pier_3", "target": "pier_4", "kind": "overlaps", "directed": False},
            ],
            "disjoint_pairs": [["pier_1", "pier_3"], ["pier_1", "pier_4"], ["pier_2", "pier_4"]],
            "pairs_examined": 6,
            "intersection": {"pair": ["pier_3", "pier_4"],
                             "area_fraction": area_fraction(overlap),
                             "fraction_of_source": round(sum(overlap) / sum(p3), 6),
                             "fraction_of_target": round(sum(overlap) / sum(p4), 6)},
            "note": "six pairs examined, three edges recorded, three examined and unrelated. The "
                    "two intersection fractions differ and neither is 'the' overlap",
        },
        "preview": preview([1 if (a or b or c or d) else 0 for a, b, c, d in zip(p1, p2, p3, p4)]),
    }


def c_one_pixel_transition() -> Dict[str, Any]:
    """Two pieces one pixel apart, and three perturbations — two real, one null.

    THE NULL IS THE HALF THAT MATTERS. A producer that calls every pair `changed` has perfect
    sensitivity, so `perturbations` carries a change that alters no relation at all, and a
    detection on it is a false alarm with a name.
    """
    left = rect(blank(), 28, 20, 36, 30)
    right = rect(blank(), 28, 32, 36, 42)       # a one-column gap at column 31 → disjoint
    bridged = bytearray(left)
    rect(bridged, 31, 31, 32, 32)               # ONE pixel, and now they meet
    grown = bytearray(left)
    rect(grown, 28, 18, 36, 20)                 # two columns added away from the gap: no change
    overlapped = bytearray(left)
    rect(overlapped, 28, 30, 36, 34)            # now it overlaps the right piece
    return {
        "instances": {"left": encode(left), "right": encode(right),
                      "left_bridged": encode(bridged), "left_grown": encode(grown),
                      "left_overlapped": encode(overlapped)},
        "truth": {
            "base_relation": {"source": "left", "target": "right", "kind": "disjoint",
                              "separation_px": 1},
            "perturbations": [
                {"id": "bridge", "revision": "left_bridged", "pixels_changed": 1,
                 "changes": True, "becomes": "meets",
                 "why": "one pixel closes the gap. A producer with any tolerance at all misses it"},
                {"id": "overlap", "revision": "left_overlapped", "pixels_changed": 32,
                 "changes": True, "becomes": "overlaps",
                 "why": "a change of kind, not of degree"},
                {"id": "grow-away", "revision": "left_grown", "pixels_changed": 16,
                 "changes": False, "becomes": "disjoint",
                 "why": "sixteen pixels added, none of them near the gap. NOTHING about the "
                        "relation changed, and a detection here is a false alarm"},
            ],
            "note": "one real one-pixel change, one real change of kind, one null with more "
                    "pixels moved than the real one",
        },
        "preview": preview([1 if (a or b) else 0 for a, b in zip(left, right)]),
    }


def c_competing_extents() -> Dict[str, Any]:
    """A figure and its cast shadow: two legitimate extents, and no correct one.

    THE CONTROL FOR THE RULE THIS WHOLE BENCHMARK IS BUILT AROUND. Asked to segment "the figure",
    a person may lawfully return the body alone or the body with the shadow it casts — those are
    two ontologies, both defensible, and neither is an error. Any scorer that picks one and marks
    the other wrong is measuring its own tie-break, which is why `hypothesis_coverage` and
    `extent_ontology_agreement` exist and why this control has no `truth.mask`.
    """
    body = blank()
    disc(body, 22, 30, 9)
    rect(body, 30, 26, 46, 34)
    shadow = rect(blank(), 46, 26, 50, 54)
    both = bytearray(1 if (a or b) else 0 for a, b in zip(body, shadow))
    return {
        "instances": {"body": encode(body), "shadow": encode(shadow), "body_and_shadow": encode(both)},
        "truth": {
            "legitimate_readings": [
                {"reading_id": "body_only", "instance": "body", "label": "the figure itself",
                 "why": "a shadow is cast BY the figure and is not part of its extent"},
                {"reading_id": "body_and_shadow", "instance": "body_and_shadow",
                 "label": "the figure and what it casts",
                 "why": "in a scene read as light and dark, the shadow belongs to the figure that "
                        "throws it"},
            ],
            "iou_between_readings": round(sum(body) / sum(both), 6),
            "has_single_correct_answer": False,
            "note": "there is no truth mask here on purpose. A benchmark that picked one of these "
                    "would be scoring its own tie-break, and the two readings are far enough "
                    "apart that the choice dominates any IoU reported against a single answer",
        },
        "preview": preview([2 if s else (1 if b else 0) for b, s in zip(body, shadow)]),
    }


CONTROLS: Tuple[Control, ...] = (
    Control("solid-mask", ("extent.hard_mask", "extent.boundary_rings", "extent.hole_set"),
            "a filled rectangle with no voids and no pieces",
            "reporting a void, or a second fragment, where a rectangle was drawn",
            c_solid_mask),
    Control("donut", ("extent.hole_set", "extent.boundary_rings"),
            "one piece with one enclosed void",
            "drawing the inner ring like the outer one, so a hole reads as a second object",
            c_donut),
    Control("nested-holes", ("extent.hole_set", "extent.hierarchy", "extent.boundary_rings"),
            "a void holding an island holding a void",
            "flattening the nesting into one piece with two voids",
            c_nested_holes),
    Control("disconnected-fragments", ("extent.fragment_set", "extent.hard_mask"),
            "five pieces, two of them touching only at a corner",
            "assuming 8-connected foreground and reporting four",
            c_disconnected_fragments,
            also_see="model_trials/controls/fence-tree.png tests the same form against an image"),
    Control("false-similarity", ("extent.fragment_set", "extent.fused_hypothesis"),
            "three identical discs, two of which belong together",
            "grouping on appearance, which gives one group of three",
            c_false_similarity,
            also_see="model_trials/controls/false-twins.png is the image-space version"),
    Control("soft-fringe", ("extent.soft_field", "extent.density_field",
                            "topology.negative_space_field"),
            "a scalar field with exact per-cell coverage",
            "returning model confidence in place of fractional coverage",
            c_soft_fringe,
            also_see="model_trials/controls/soft-fog.png and hair-veil.png test the same "
                     "distinction against images"),
    Control("partition", ("extent.visible_inferred_partition", "extent.fused_hypothesis"),
            "a figure behind a bar, running off the frame",
            "assigning the off-frame pixels to visible or to inferred rather than to unknown",
            c_partition,
            also_see="model_trials/controls/occluder-table.png is the image-space version"),
    Control("density-peaks", ("extent.density_field",),
            "two clusters and a stray, with exact positions",
            "smoothing the stray away and calling the count right",
            c_density_peaks,
            also_see="model_trials/controls/crowd-plaza.png is the image-space version"),
    Control("containment-tree", ("extent.hierarchy", "topology.containment_tree"),
            "A ⊃ B ⊃ C, A ⊃ D, and E outside everything",
            "forcing a single root, which invents a container for E",
            c_containment_tree),
    Control("adjacency-graph", ("topology.adjacency_graph", "topology.pair_relation",
                                "topology.contact_locus", "topology.intersection_area",
                                "topology.clearance_path"),
            "a chain of four pieces, three related and three not",
            "rendering the three unrelated pairs as blank space, indistinguishable from unexamined",
            c_adjacency_graph),
    Control("one-pixel-transition", ("topology.transition", "topology.pair_relation"),
            "a one-pixel gap, two real changes and one null",
            "detecting the null, which more pixels moved than the real change",
            c_one_pixel_transition),
    Control("competing-extents", ("extent.hypothesis_set", "extent.fused_hypothesis",
                                  "topology.uncertain_relation_set"),
            "a figure and its cast shadow — two legitimate extents",
            "collapsing to one answer, which scores the benchmark's tie-break",
            c_competing_extents),
)


def build_controls() -> Dict[str, Any]:
    entries: Dict[str, Any] = {}
    for control in CONTROLS:
        built = control.build()
        body = json.dumps(built, sort_keys=True, separators=(",", ":"))
        entries[control.name] = {
            "forms": list(control.forms),
            "what": control.what,
            "the_trap": control.the_trap,
            "raster": [SIZE, SIZE],
            "digest": sha256_text(body),
            **built,
        }
        if control.also_see:
            entries[control.name]["also_see"] = control.also_see
    return {
        "what_this_is": [
            "PERCEPTUAL-FORMS-001F. Twelve synthetic controls whose ground truth is known BY",
            "CONSTRUCTION: a donut has one hole because a hole was punched in it. Drawn by",
            "`scripts/perception_lab_form_benchmark.py controls` and pinned by `--check`.",
            "THE COUNTS ARE UNDER ONE DECLARED PAIRING. `extent_forms.raster` pairs foreground",
            f"{FOREGROUND_CONNECTIVITY}-connected with background {BACKGROUND_CONNECTIVITY}-",
            "connected; `disconnected-fragments` exists to catch a producer that assumed the",
            "other one. Reverse the pairing and half the numbers here change.",
            "A HOLE COUNT NEEDS A CONVENTION. `holes` here is enclosed voids only; the",
            "unbounded exterior is a complement component and is not a hole. Both numbers are",
            "recorded per control so a producer can be checked against either.",
            "SEPARATE FROM LANE C. `model_trials/controls/` holds IMAGE controls with alpha",
            "truth, for asking whether a model can see. These hold PAYLOAD truth, for asking",
            "whether a producer's record means what the form it fills says it means. Where a",
            "scene exists in both, `also_see` points at it rather than redrawing it.",
        ],
        "raster": [SIZE, SIZE],
        "foreground_connectivity": FOREGROUND_CONNECTIVITY,
        "background_connectivity": BACKGROUND_CONNECTIVITY,
        "controls": entries,
    }


# ── the benchmark matrix ─────────────────────────────────────────────────────

#: One row per form. `image` names an atlas slot; `control` names a synthetic control; `question`
#: is what a person is actually asking when they open the form; `action` is what they do about it;
#: `metric` is the scoring family; `failures` are the ways it goes wrong that are worth a picture;
#: `screenshot` is the capture the review needs.
MATRIX_ROWS: Tuple[Dict[str, Any], ...] = (
    {"form": "extent.hard_mask", "image": "van-steenwyck-courtyard", "control": "solid-mask",
     "question": "Which pixels are that thing?",
     "action": "draw or refine an extent, then read the mask against the box",
     "metrics": ["iou", "boundary_f1"],
     "failures": ["a box returned where a mask was asked for",
                  "a mask whose declared box does not contain it",
                  "an instance with no mask silently drawn as its box"],
     "screenshot": "extent.hard_mask · fill · the box-only instance refusing to be drawn"},
    {"form": "extent.boundary_rings", "image": "van-delen-gallery", "control": "donut",
     "question": "Where exactly does its edge run?",
     "action": "trace the boundary, then compare the recorded ring with the traced one",
     "metrics": ["ring_reconstruction", "boundary_f1", "chamfer"],
     "failures": ["a smoothed ring presented as a measured one",
                  "an inner ring drawn like an outer one",
                  "a ring whose winding is not declared"],
     "screenshot": "extent.boundary_rings · winding · outer and inner told apart"},
    {"form": "extent.hole_set", "image": "wells-nave", "control": "nested-holes",
     "question": "What voids are inside it, and are they enclosed?",
     "action": "mark a void, then check enclosure against the background connectivity",
     "metrics": ["hole_count_error", "iou", "set_overlap"],
     "failures": ["a bay in the boundary reported as an enclosed void",
                  "nested voids flattened onto one piece",
                  "a hole count that changes with the connectivity pairing"],
     "screenshot": "extent.hole_set · parent_context · the void inside its piece"},
    {"form": "extent.soft_field", "image": "adversarial-fog", "control": "soft-fringe",
     "question": "How much of it is here, where the edge is not a line?",
     "action": "sweep the threshold and watch which cells survive",
     "metrics": ["field_l1", "calibration_error", "field_correlation"],
     "failures": ["model confidence returned as fractional coverage",
                  "a blurred hard mask presented as a soft field",
                  "a field thresholded into a mask with no threshold shown"],
     "screenshot": "extent.soft_field · threshold · the number on screen and the field beneath it"},
    {"form": "extent.fragment_set", "image": "adversarial-fence-tree", "control":
     "disconnected-fragments",
     "question": "What separate pieces are visible, without saying yet whether they are one thing?",
     "action": "number the islands, then propose a membership correction",
     "metrics": ["set_overlap"],
     "failures": ["fragments merged because they look alike",
                  "corner-touching pieces counted as one",
                  "`unity_asserted` set true by a form that only found pieces"],
     "screenshot": "extent.fragment_set · islands · numbered, with unity not asserted"},
    {"form": "extent.fused_hypothesis", "image": "adversarial-fence-tree",
     "control": "false-similarity",
     "question": "Are these pieces one thing, and on what evidence?",
     "action": "accept or reject the grouping, and read the grounds it rests on",
     "metrics": ["set_overlap", "evidence_completeness", "verdict_agreement"],
     "failures": ["a grouping with no enumerated grounds",
                  "a fusion drawn as solidly as the pieces it joins",
                  "`asserts_hidden_extent` unset on a hypothesis that claims hidden pixels"],
     "screenshot": "extent.fused_hypothesis · fusion · members solid, connection dotted"},
    {"form": "extent.visible_inferred_partition", "image": "adversarial-person-behind-table",
     "control": "partition",
     "question": "Which of this did we see, which did we infer, and which do we not know?",
     "action": "paint a part, then read visible and inferred accuracy separately",
     "metrics": ["iou", "field_l1"],
     "failures": ["inferred pixels drawn like visible ones",
                  "the unknown part absorbed into inferred",
                  "one pooled accuracy hiding a generous completion"],
     "screenshot": "extent.visible_inferred_partition · tricolor · three treatments at once"},
    {"form": "extent.hierarchy", "image": "van-steenwyck-courtyard", "control":
     "containment-tree",
     "question": "What contains what, and how much of the parent does the child occupy?",
     "action": "link a child to a parent and inspect the occupancy",
     "metrics": ["tree_edit", "set_overlap"],
     "failures": ["a forest forced into a single root",
                  "a containment cycle presented as a tree",
                  "occupancy reported without saying which basis measured it"],
     "screenshot": "extent.hierarchy · tree · a forest with two roots"},
    {"form": "extent.density_field", "image": "adversarial-crowd-plaza", "control":
     "density-peaks",
     "question": "Where is the collection, when there is no single object to outline?",
     "action": "read the count against the field, and the field against the smoothing",
     "metrics": ["count_error", "localisation_error", "field_l1", "rank_agreement"],
     "failures": ["a smoothed field read as a count",
                  "strays smoothed away with the count still reported exact",
                  "a density peak where no member was counted"],
     "screenshot": "extent.density_field · samples · counts exact, field smoothed"},
    {"form": "extent.hypothesis_set", "image": "gris-cubist-interior",
     "control": "competing-extents",
     "question": "What are the competing readings of where this thing is?",
     "action": "hold the alternatives apart, then accept one without resolving it",
     "metrics": ["hypothesis_coverage", "iou", "rank_agreement"],
     "failures": ["alternatives merged into one overlay by default",
                  "weights read as probabilities when the record says they are not",
                  "a single reading returned where several are legitimate"],
     "screenshot": "extent.hypothesis_set · split · three readings, three panes"},
    {"form": "topology.pair_relation", "image": "de-chirico-piazza", "control":
     "adjacency-graph",
     "question": "How do these two stand to each other?",
     "action": "pick a pair, read the relation, and compare the drawn band with the number",
     "metrics": ["set_overlap", "graph_edit", "direction_accuracy"],
     "failures": ["an arrowhead on an undirected relation",
                  "a browser-drawn band presented as the measurement",
                  "a stale relation drawn against changed geometry"],
     "screenshot": "topology.pair_relation · contact · derived band beside the recorded number"},
    {"form": "topology.contact_locus", "image": "van-delen-gallery", "control":
     "adjacency-graph",
     "question": "Where exactly do they touch?",
     "action": "read the locus against the contact pixel count",
     "metrics": ["iou", "chamfer", "boundary_f1"],
     "failures": ["a contact count measured at a resolution the mask cannot carry",
                  "a dilation tolerance not declared with the band",
                  "a locus drawn for a pair that does not touch"],
     "screenshot": "topology.contact_locus · band · the recorded locus, not a traced one"},
    {"form": "topology.intersection_area", "image": "adversarial-fence-tree",
     "control": "adjacency-graph",
     "question": "What region do they share, and how much of each is it?",
     "action": "read both fractions and refuse to average them",
     "metrics": ["iou", "set_overlap"],
     "failures": ["one fraction reported as 'the' overlap",
                  "an intersection drawn across two different rasters",
                  "an empty intersection reported for an `overlaps` relation"],
     "screenshot": "topology.intersection_area · area · both fractions side by side"},
    {"form": "topology.clearance_path", "image": "de-chirico-piazza", "control":
     "adjacency-graph",
     "question": "How far apart are they, and along which line?",
     "action": "read the separation against the two closest points",
     "metrics": ["chamfer", "hausdorff"],
     "failures": ["a centroid-to-centroid line presented as a clearance",
                  "a separation with fewer than two path points",
                  "a clearance reported for a touching pair"],
     "screenshot": "topology.clearance_path · path · endpoints at the measured points"},
    {"form": "topology.containment_tree", "image": "van-steenwyck-courtyard",
     "control": "containment-tree",
     "question": "What is inside what, across the whole scene?",
     "action": "read the tree, then check every edge's direction",
     "metrics": ["tree_edit", "graph_edit", "direction_accuracy"],
     "failures": ["an undirected line where containment was measured",
                  "a dangling parent silently re-rooted",
                  "a cycle rendered as a tree"],
     "screenshot": "topology.containment_tree · tree · directed edges and unresolved endpoints"},
    {"form": "topology.adjacency_graph", "image": "wells-nave", "control": "adjacency-graph",
     "question": "What touches what, across the whole scene?",
     "action": "read the matrix, not only the node-link drawing",
     "metrics": ["graph_edit", "set_overlap", "direction_accuracy"],
     "failures": ["examined-and-unrelated rendered as empty space",
                  "`pairs_examined` disagreeing with the number of possible pairs",
                  "an isolated node dropped rather than named"],
     "screenshot": "topology.adjacency_graph · matrix · blank cells that mean 'examined'"},
    {"form": "topology.negative_space_field", "image": "van-schooten-still-life",
     "control": "soft-fringe",
     "question": "What is NOT the figure, and how far from it?",
     "action": "read the statistics, and the browser-computed field beside them",
     "metrics": ["field_l1", "field_correlation", "calibration_error"],
     "failures": ["a wash invented from the statistics when the field is behind a ref",
                  "a distance transform truncated at a different bound than the record declares",
                  "the derived field presented as the measured one"],
     "screenshot": "topology.negative_space_field · wash · measured absent, derived beside it"},
    {"form": "topology.transition", "image": "van-schooten-still-life",
     "control": "one-pixel-transition",
     "question": "What changed between these two revisions?",
     "action": "compare before and after in separate panes",
     "metrics": ["transition_sensitivity", "graph_edit"],
     "failures": ["a one-pixel change smoothed away by a tolerance",
                  "a null perturbation reported as a change",
                  "a transition citing only one revision"],
     "screenshot": "topology.transition · before_after · two panes, revisions named"},
    {"form": "topology.uncertain_relation_set", "image": "gris-cubist-interior",
     "control": "competing-extents",
     "question": "Which relations hold, and under which reading?",
     "action": "switch readings and watch which relations survive",
     "metrics": ["hypothesis_coverage", "graph_edit", "rank_agreement"],
     "failures": ["a conditional relation read without its condition",
                  "readings merged into one graph by default",
                  "a condition naming a hypothesis the record does not list"],
     "screenshot": "topology.uncertain_relation_set · by_hypothesis · the condition on the claim"},
)


def build_matrix() -> Dict[str, Any]:
    rows = []
    for row in MATRIX_ROWS:
        form = FORMS[row["form"]]
        rows.append({
            **row,
            "organ": form["organ"],
            "state": form["state"],
            "carries_hypothesis": form["carries_hypothesis"],
            "declared_comparison_methods": list(form["comparison_methods"]),
            "epistemic_ceiling": form["epistemic_ceiling"],
        })
    return {
        "what_this_is": [
            "PERCEPTUAL-FORMS-001F. One row per registered form: the real image it is tested on,",
            "the synthetic control that comes first, the question a person is actually asking,",
            "the action they take, the metrics, the failures worth a picture, and the screenshot",
            "the review needs. Generated by `scripts/perception_lab_form_benchmark.py matrix`.",
            "THE METRICS ARE CHECKED AGAINST THE FORM. Where a row names a metric the form does",
            "not declare in `comparison_methods`, `report` lists it — either the row is reaching",
            "for something the contract has not registered, or the form's declaration is short.",
            "Both are findings and neither is silently correct.",
        ],
        "generated_by": "scripts/perception_lab_form_benchmark.py",
        "forms": len(rows),
        "rows": rows,
    }


# ── validation ───────────────────────────────────────────────────────────────

def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_matrix(matrix: Mapping[str, Any]) -> List[str]:
    problems: List[str] = []
    rows = matrix.get("rows", [])
    seen = [r["form"] for r in rows]
    missing = [k for k in FORM_KEYS if k not in seen]
    if missing:
        problems.append(f"the matrix has no row for {', '.join(missing)}")
    extra = [k for k in seen if k not in FORM_KEYS]
    if extra:
        problems.append(f"the matrix has rows for unregistered forms: {', '.join(extra)}")
    if len(seen) != len(set(seen)):
        problems.append("a form has more than one row")
    control_names = {c.name for c in CONTROLS}
    atlas_slots = set()
    if ATLAS_PATH.exists():
        atlas_slots = {e["slot"] for e in _read_json(ATLAS_PATH).get("entries", [])}
    for row in rows:
        where = row["form"]
        if row["control"] not in control_names:
            problems.append(f"{where}: names control {row['control']!r}, which is not drawn")
        if atlas_slots and row["image"] not in atlas_slots:
            problems.append(f"{where}: names image slot {row['image']!r}, not in the atlas")
        for metric in row["metrics"]:
            if metric not in ALL_METRICS:
                problems.append(f"{where}: metric {metric!r} is not one this benchmark implements")
        for key in ("question", "action", "screenshot"):
            if not row.get(key):
                problems.append(f"{where}: has no {key}")
        if not row.get("failures"):
            problems.append(f"{where}: names no failure worth photographing")
    return problems


def metric_gaps(matrix: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Rows whose metrics the form does not declare — a gap in one direction or the other."""
    gaps = []
    for row in matrix.get("rows", []):
        declared = set(FORMS[row["form"]]["comparison_methods"])
        undeclared = [m for m in row["metrics"] if m in COMPARISON_METHODS and m not in declared]
        extensions = [m for m in row["metrics"] if m in EXTENSIONS]
        unused = sorted(declared - set(row["metrics"]))
        if undeclared or extensions or unused:
            gaps.append({"form": row["form"], "reaches_for_undeclared": undeclared,
                         "uses_extensions": extensions, "declares_but_unused": unused})
    return gaps


REQUIRED_ATLAS_FIELDS = ("slot", "role", "identity", "rights", "access", "why_this_work")
REQUIRED_RIGHTS_FIELDS = ("artwork_status", "reproduction_status", "may_commit_bytes",
                          "attribution", "retrieved", "resolved")


def validate_atlas(atlas: Mapping[str, Any]) -> List[str]:
    problems: List[str] = []
    entries = atlas.get("entries", [])
    if not entries:
        return ["the atlas has no entries"]
    slots = [e.get("slot") for e in entries]
    if len(slots) != len(set(slots)):
        problems.append("two atlas entries share a slot")
    for entry in entries:
        slot = entry.get("slot", "<unnamed>")
        for key in REQUIRED_ATLAS_FIELDS:
            if key not in entry:
                problems.append(f"{slot}: has no {key}")
        rights = entry.get("rights", {})
        for key in REQUIRED_RIGHTS_FIELDS:
            if key not in rights:
                problems.append(f"{slot}: rights block has no {key}")
        # THE CHECK THIS BLOCK EXISTS FOR. A committable byte source must say what makes it
        # committable; anything else must carry the reason it does not.
        if rights.get("may_commit_bytes") is True and not rights.get("licence"):
            problems.append(f"{slot}: claims bytes may be committed and names no licence")
        if rights.get("may_commit_bytes") is False and not rights.get("why_not"):
            problems.append(f"{slot}: says bytes may not be committed and does not say why")
        if entry.get("bytes_committed"):
            problems.append(
                f"{slot}: declares committed bytes. This lane commits none — the manifest points "
                "at a lawful source and records a digest, and a checkout carries no image")
        problems += _check_in_repo_reference(slot, entry.get("access", {}))
    return problems


def _check_in_repo_reference(slot: str, access: Mapping[str, Any]) -> List[str]:
    """An `in_repository` reference must name a file that exists and hash to what Lane C recorded.

    THE CROSS-LANE GATE. The four adversarial controls this benchmark requires already exist as
    synthetic images in `model_trials/controls/`, and are referenced rather than redrawn. A
    reference is only worth having if it cannot drift: if Lane C redraws a control, this fails
    here rather than silently pointing at a different picture with the same filename.
    """
    if access.get("how") != "in_repository":
        return []
    problems: List[str] = []
    source = str(access.get("source_url") or "")
    target = REPO_ROOT / source
    if not target.exists():
        return [f"{slot}: references {source}, which is not in the repository"]
    if not MODEL_TRIAL_CONTROLS.exists():
        return [f"{slot}: references a Lane C control and {MODEL_TRIAL_CONTROLS.name} is missing"]
    lane_c = _read_json(MODEL_TRIAL_CONTROLS).get("controls", {})
    name = Path(source).stem
    recorded = lane_c.get(name, {}).get("digest")
    if recorded is None:
        problems.append(f"{slot}: {name} is not a control Lane C's manifest declares")
    elif recorded != access.get("digest"):
        problems.append(
            f"{slot}: the digest recorded here does not match Lane C's manifest for {name}. "
            "One of the two lanes is pointing at a different picture than it thinks")
    for companion in ([access["companion"]] if access.get("companion") else []) \
            + list(access.get("companions") or []):
        if not (REPO_ROOT / companion).exists():
            problems.append(f"{slot}: names companion {companion}, which is not in the repository")
    return problems


def validate_annotations() -> List[str]:
    """Every committed annotation against the schema, and against the no-forced-collapse rule."""
    problems: List[str] = []
    schema_path = SCHEMAS_DIR / "form-annotation.schema.json"
    if not schema_path.exists():
        return [f"{schema_path.relative_to(REPO_ROOT)} is missing"]
    schema = _read_json(schema_path)
    required = schema.get("required", [])
    if not ANNOTATIONS_DIR.exists():
        return ["the annotations directory is missing"]
    files = sorted(ANNOTATIONS_DIR.glob("*.json"))
    if not files:
        problems.append("no annotation is committed, so the schema is unexercised")
    for path in files:
        rel = path.relative_to(REPO_ROOT)
        record = _read_json(path)
        for key in required:
            if key not in record:
                problems.append(f"{rel}: has no {key}")
        if record.get("form") not in FORM_KEYS:
            problems.append(f"{rel}: form {record.get('form')!r} is not registered")
        readings = record.get("legitimate_readings") or []
        if not readings:
            problems.append(f"{rel}: declares no legitimate reading. An annotation that names no "
                            "acceptable answer cannot score anything")
        if len(readings) > 1 and record.get("single_correct_answer") is not False:
            problems.append(
                f"{rel}: declares {len(readings)} legitimate readings and does not set "
                "`single_correct_answer` to false. A scorer reading this would pick the first one")
        for reading in readings:
            if not reading.get("why"):
                problems.append(f"{rel}: reading {reading.get('reading_id')!r} gives no reason. "
                                "An ontology nobody explained cannot be argued with")
        for verdict in record.get("utility_verdicts", []):
            if verdict.get("verdict") not in CONTRACT["closed_sets"]["review_verdicts"]:
                problems.append(f"{rel}: verdict {verdict.get('verdict')!r} is not in the "
                                "contract's closed set")
    return problems


# ── the CLI ──────────────────────────────────────────────────────────────────

def _write_or_check(path: Path, payload: Mapping[str, Any], check: bool, label: str) -> List[str]:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if check:
        if not path.exists():
            return [f"{label} is missing at {path.relative_to(REPO_ROOT)}"]
        if path.read_text(encoding="utf-8") != text:
            return [f"{label} has drifted from what the script generates — run "
                    f"`python {Path(__file__).relative_to(REPO_ROOT)} "
                    f"{label.split()[0]}` to regenerate"]
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return []


def cmd_controls(args: argparse.Namespace) -> int:
    problems = _write_or_check(CONTROLS_DIR / "manifest.json", build_controls(),
                               args.check, "controls manifest")
    for line in problems:
        print(f"  ✗ {line}")
    if not problems:
        print(f"  ✓ {len(CONTROLS)} controls "
              f"{'verified' if args.check else 'written'} at "
              f"{(CONTROLS_DIR / 'manifest.json').relative_to(REPO_ROOT)}")
    return 1 if problems else 0


def cmd_matrix(args: argparse.Namespace) -> int:
    matrix = build_matrix()
    problems = validate_matrix(matrix)
    problems += _write_or_check(MATRIX_PATH, matrix, args.check, "matrix")
    for line in problems:
        print(f"  ✗ {line}")
    if not problems:
        print(f"  ✓ {len(matrix['rows'])} form rows "
              f"{'verified' if args.check else 'written'} at "
              f"{MATRIX_PATH.relative_to(REPO_ROOT)}")
    return 1 if problems else 0


def cmd_atlas(_: argparse.Namespace) -> int:
    if not ATLAS_PATH.exists():
        print(f"  ✗ {ATLAS_PATH.relative_to(REPO_ROOT)} is missing")
        return 1
    atlas = _read_json(ATLAS_PATH)
    problems = validate_atlas(atlas)
    for line in problems:
        print(f"  ✗ {line}")
    if problems:
        return 1
    entries = atlas["entries"]
    primary = [e for e in entries if e["role"] == "primary"]
    free = [e for e in entries if e["rights"]["may_commit_bytes"]]
    encumbered = [e for e in entries if not e["rights"]["may_commit_bytes"]]
    # IDENTITY AND RIGHTS ARE COUNTED SEPARATELY because they fail separately: a work can be
    # pinned to an accession number and be unusable, and a work can be freely licensed and be the
    # wrong picture. Reporting one number for both would hide whichever was fine.
    unresolved_identity = [e for e in entries if not e["identity"]["resolved"]]
    unresolved_rights = [e for e in entries if not e["rights"]["resolved"]]
    print(f"  ✓ {len(entries)} atlas entries validate "
          f"({len(primary)} primary, {len(entries) - len(primary)} adversarial)")
    print(f"    {len(free)} carry a licence that would permit committed bytes; this lane commits "
          "none regardless")
    print(f"    {len(encumbered)} are reference-only: "
          + ", ".join(e["slot"] for e in encumbered))
    print(f"    {len(unresolved_identity)} have an unresolved IDENTITY question: "
          + (", ".join(e["slot"] for e in unresolved_identity) or "none"))
    print(f"    {len(unresolved_rights)} have an unresolved RIGHTS question: "
          + (", ".join(e["slot"] for e in unresolved_rights) or "none"))
    print(f"    see {(ATLAS_DIR / 'RIGHTS.md').relative_to(REPO_ROOT)}")
    return 0


def cmd_annotations(_: argparse.Namespace) -> int:
    problems = validate_annotations()
    for line in problems:
        print(f"  ✗ {line}")
    if not problems:
        n = len(list(ANNOTATIONS_DIR.glob("*.json")))
        print(f"  ✓ {n} annotations validate against the schema")
    return 1 if problems else 0


def cmd_report(_: argparse.Namespace) -> int:
    matrix = build_matrix() if not MATRIX_PATH.exists() else _read_json(MATRIX_PATH)
    print("FORM COVERAGE")
    print(f"  forms registered : {len(FORM_KEYS)}")
    print(f"  matrix rows      : {len(matrix['rows'])}")
    print(f"  controls         : {len(CONTROLS)}")
    covered = {f for c in CONTROLS for f in c.forms}
    print(f"  forms with a control: {len(covered)} of {len(FORM_KEYS)}")
    uncovered = [k for k in FORM_KEYS if k not in covered]
    if uncovered:
        print(f"    without one: {', '.join(uncovered)}")
    print()
    print("METRIC VOCABULARY")
    print(f"  contract comparison methods : {len(COMPARISON_METHODS)}")
    print(f"  this lane's extensions      : {len(EXTENSIONS)}")
    for name, why in sorted(EXTENSIONS.items()):
        print(f"    {name}: {why}")
    print()
    print("WHERE THE MATRIX AND THE FORM REGISTRY DISAGREE")
    gaps = metric_gaps(matrix)
    if not gaps:
        print("  none")
    for gap in gaps:
        bits = []
        if gap["reaches_for_undeclared"]:
            bits.append(f"reaches for undeclared {', '.join(gap['reaches_for_undeclared'])}")
        if gap["uses_extensions"]:
            bits.append(f"uses extensions {', '.join(gap['uses_extensions'])}")
        if gap["declares_but_unused"]:
            bits.append(f"declares but unused {', '.join(gap['declares_but_unused'])}")
        print(f"  {gap['form']}: {'; '.join(bits)}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    args.check = True
    status = 0
    for name, fn in (("controls", cmd_controls), ("matrix", cmd_matrix),
                     ("atlas", cmd_atlas), ("annotations", cmd_annotations)):
        print(f"{name}:")
        status |= fn(args)
    return status


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn, has_check in (("controls", cmd_controls, True), ("matrix", cmd_matrix, True),
                                ("atlas", cmd_atlas, False), ("annotations", cmd_annotations, False),
                                ("report", cmd_report, False), ("verify", cmd_verify, False)):
        p = sub.add_parser(name)
        if has_check:
            p.add_argument("--check", action="store_true",
                           help="verify the committed file rather than rewriting it")
        p.set_defaults(func=fn, check=False)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
