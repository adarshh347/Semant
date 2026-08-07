"""ORGAN-PROVENANCE-001 — the whole sensorium, audited in one place.

Four organs now, added one lane at a time, each with its own test file written against its own
worries. This file is the cross-cutting pass the depth lane's findings asked for, and it exists
because both gaps it closes were *inherited* rather than invented: the stand-in descriptor habit
spread from the first organ's tests to the second, and the missing-artifact-provenance hole was
closed for depth while chroma — written earlier, with the same exposure — kept it.

So the guard here is a TABLE, not a set of hand-written cases. A fifth organ added without wiring
it in fails `test_the_audit_covers_every_organ_there_is`, which is the only way a per-organ property
stays true of an organ nobody has written yet.

  1. EVERY ORGAN'S REAL MARK PASSES ITS OWN GUARD — the mark the organ actually produces, through
     `producer_of` → `permitted_statuses` → the substrate check. Two of the four were testing a
     flat descriptor rebuilt from the mark, which is a shape nothing in production has. §1.
  2. RETAINED ADMISSION — every honest mark each organ produces on either substrate is still
     admitted after this lane. Hardening that quietly refused something real would be worse than
     the gap it closed. §2.
  3. A SAME-SHAPE-BUT-INVALID MARK IS REFUSED — per organ, at the level each one needs. §3.
  4. THE ASYMMETRY, STATED — the geometry organs read the post's own `region_annotations`; the
     sensory organs read an artifact handed in from outside. Only an external artifact can silently
     be a different picture, which is why only two of the four carry artifact provenance. §4.
"""
from __future__ import annotations

import pytest

from backend.services import adjacency_organ as adj
from backend.services import chroma_organ as chroma
from backend.services import depth_organ as depth
from backend.services import epistemics
from backend.services import mask_geometry as mg
from backend.services import nestedness_organ as nest
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

GRID = 16


def _rle(x0, x1, y0, y1, w=GRID, h=GRID):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


PART = {"id": "part", "mask_rle": _rle(4, 16, 4, 12)}
WHOLE = {"id": "whole", "mask_rle": _rle(0, 16, 0, 16)}
PART_BOX = {"id": "part", "box": {"x": 0.25, "y": 0.25, "w": 0.7, "h": 0.5}}
WHOLE_BOX = {"id": "whole", "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}


class _Raster:
    """A warm/cool split raster. No image library — the chroma organ's protocol is three methods."""

    def __init__(self, size=64):
        self.size = size

    def convert(self, _mode):
        return self

    def resize(self, wh):
        return _Raster(int(wh[0]))

    def getdata(self):
        return [((220, 120, 40) if x < self.size // 2 else (40, 110, 220))
                for _ in range(self.size) for x in range(self.size)]


def _frame(**over):
    return {**chroma.image_frame(_Raster(), source="audit:fixture"), **over}


def _depth_field(**over):
    base = depth.depth_field(
        {"depth": [9.0 if i % GRID < GRID // 2 else 1.0 for i in range(GRID * GRID)], "grid": GRID},
        adapter=depth.SOURCE_ADAPTER, model="depth_anything_v2_small",
        revision="5426e4f0f36572d16453bbda7a8389317b1bef99",
        preprocessing_version="depth-anything-v2-s-v1")
    return {**base, **over}


#: THE SENSORIUM, as a table. Each entry says how to get a REAL mark out of that organ on each
#: substrate — no hand-built descriptors anywhere in this file, which is the gap being closed.
ORGANS = {
    nest.ORGAN: {
        "module": nest,
        "mask": lambda: nest.grounding_mark(nest.measure(PART, WHOLE), post_id="p"),
        "box": lambda: nest.grounding_mark(nest.measure(PART_BOX, WHOLE_BOX), post_id="p"),
        "external_artifact": False,
    },
    adj.ORGAN: {
        "module": adj,
        "mask": lambda: adj.grounding_mark(adj.measure(PART, WHOLE), post_id="p"),
        "box": lambda: adj.grounding_mark(adj.measure(PART_BOX, WHOLE_BOX), post_id="p"),
        "external_artifact": False,
    },
    chroma.ORGAN: {
        "module": chroma,
        "mask": lambda: chroma.grounding_mark(chroma.measure(PART, _frame()), post_id="p"),
        "box": lambda: chroma.grounding_mark(chroma.measure(PART_BOX, _frame()), post_id="p"),
        "external_artifact": True,
    },
    depth.ORGAN: {
        "module": depth,
        "mask": lambda: depth.grounding_mark(depth.measure(PART, _depth_field()), post_id="p"),
        "box": lambda: depth.grounding_mark(depth.measure(PART_BOX, _depth_field()), post_id="p"),
        "external_artifact": True,
    },
}


def test_the_audit_covers_every_organ_there_is():
    """THE NO-DRIFT GUARD. A fifth organ that is invocable but absent from `ORGANS` fails here,
    because every property below is only true of the organs this table names."""
    from backend.services.agents import organs

    missing = sorted(set(organs.PURE_PYTHON_ORGANS) - set(ORGANS))
    assert not missing, (
        f"{missing} can be invoked by an agent but is not in this audit. Every per-organ property "
        f"in this file — real-mark guarding, retained admission, same-shape refusal — has to be "
        f"asserted of it too, or the sensorium grows past its own honesty floor.")


# ── 1. every organ's REAL mark passes its own guard ─────────────────────────

@pytest.mark.parametrize("organ", sorted(ORGANS))
@pytest.mark.parametrize("basis", ["mask", "box"])
def test_the_mark_the_organ_actually_produces_passes_the_guard(organ, basis):
    """THE GAP THE DEPTH LANE NAMED: "the marks the organs actually produce were never the thing
    being guarded."

    Two of these four tested a flat descriptor rebuilt from the mark's fields, because when those
    tests were written a real mark read as producer `None` — `grounding_mark` names the producer in
    `provenance` and `guard` only looked at the top level. #158 fixed that; the tests kept their
    stand-ins, so what was being guarded was a shape nothing in production has.

    Nothing is rebuilt here. The mark goes in as the organ made it.
    """
    mark = ORGANS[organ][basis]()
    assert epistemics.producer_of(mark) == organ
    assert epistemics.substrate_of(mark) == basis
    assert epistemics.guard([mark]) == [mark]


@pytest.mark.parametrize("organ", sorted(ORGANS))
def test_the_substrate_decides_the_kind_on_a_real_mark(organ):
    """`measured` on masks, `interpretive` on boxes — read off the real marks rather than off the
    table that is supposed to produce them."""
    assert ORGANS[organ]["mask"]()[STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert ORGANS[organ]["box"]()[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    assert epistemics.declared_substrates(organ) == ("mask", "box")


@pytest.mark.parametrize("organ", sorted(ORGANS))
@pytest.mark.parametrize("basis", ["mask", "box"])
def test_a_real_mark_promoted_past_its_substrate_is_refused(organ, basis):
    """The retained refusal, on every organ and both substrates. A mask reading tagged
    `interpretive` is as wrong as a box reading tagged `measured`: the substrate does not cap the
    kind, it decides it."""
    mark = ORGANS[organ][basis]()
    wrong = (EpistemicStatus.INTERPRETIVE if basis == "mask" else EpistemicStatus.MEASURED)
    with pytest.raises(epistemics.EpistemicViolation, match="substrate"):
        epistemics.guard([{**mark, STATUS_KEY: wrong.value}])


# ── 2. retained admission: nothing honest became inadmissible ──────────────

@pytest.mark.parametrize("organ", sorted(ORGANS))
def test_every_honest_mark_this_organ_makes_is_still_admitted(organ):
    """THE HONESTY FLOOR OF THIS LANE. Hardening that quietly refused a real reading would be worse
    than the gap it closed — the failure would look like an organ that had gone quiet.

    Both substrates, the organ's own numbers, straight through the guard.
    """
    for basis in ("mask", "box"):
        mark = ORGANS[organ][basis]()
        assert epistemics.guard([mark]) == [mark], f"{organ}/{basis} stopped being admissible"
        assert mark["measurement"], "a mark with no measurement is not a real reading"
        assert mark["provenance"]["producer"] == organ


def test_the_organs_that_read_an_external_artifact_still_read_it():
    """The two organs this lane actually changed, exercised end to end rather than only refused."""
    warm = chroma.measure(PART, _frame())
    assert warm["basis"] == "mask" and warm["warmth_mean"] != 0.0
    near = depth.measure(PART, _depth_field())
    assert near["basis"] == "mask" and near["relief"] > 0.0


# ── 3. a same-shape-but-invalid reading is refused, per organ ──────────────

def test_chroma_refuses_an_image_that_is_not_the_frame():
    """THE FINDING THIS LANE WAS OPENED BY. Before the frame contract, the same region and the same
    call on a differently-framed image produced a `measured` mark of identical shape with the
    OPPOSITE SIGN, and nothing downstream could tell them apart. See `chroma_organ.image_frame`."""
    with pytest.raises(chroma.ChromaRefusal, match="bare image"):
        chroma.measure(PART, _Raster())
    with pytest.raises(chroma.ChromaRefusal, match="not the whole picture"):
        chroma.measure(PART, _frame(whole_frame=False))
    with pytest.raises(chroma.ChromaRefusal, match="names no source"):
        chroma.measure(PART, _frame(source=""))


def test_depth_refuses_a_field_that_is_not_the_frame_or_not_the_model():
    """The contract chroma's was modelled on, re-asserted here so the two stay symmetrical rather
    than symmetrical-today."""
    with pytest.raises(depth.DepthRefusal, match="whole frame"):
        depth.measure(PART, _depth_field(whole_frame=False))
    with pytest.raises(depth.DepthRefusal, match="another model"):
        depth.measure(PART, _depth_field(adapter="midas_small"))
    with pytest.raises(depth.DepthRefusal, match="provenance"):
        depth.measure(PART, _depth_field(model="", revision=""))


@pytest.mark.parametrize("organ,measure,refusal", [
    (nest.ORGAN, lambda r: nest.measure(r, WHOLE), nest.NestednessRefusal),
    (adj.ORGAN, lambda r: adj.measure(r, WHOLE), adj.AdjacencyRefusal),
])
def test_the_geometry_organs_refuse_an_empty_mask_rather_than_reading_it(organ, measure, refusal):
    """The geometry organs' version of the same-shape-but-empty case, and they already close it.

    An empty mask is a structurally valid RLE that decodes to no pixels — a region-shaped hole. Both
    refuse it, which is the behaviour this lane checked for rather than assumed: a zero containment
    or a zero contact fraction would mean "measured, and these do not relate", and an unmeasurable
    pair reported that way is a claim about the picture made from an absence of evidence.
    """
    with pytest.raises(refusal):
        measure({"id": "empty", "mask_rle": _rle(0, 0, 0, 0)})


def test_the_field_organs_refuse_a_region_too_small_to_read():
    """The sensory organs' floor: below it, the number is the sampler's rather than the region's."""
    sliver = {"id": "sliver", "mask_rle": _rle(0, 1, 0, 1)}
    with pytest.raises(chroma.ChromaRefusal):
        chroma.measure(sliver, _frame())
    with pytest.raises(depth.DepthRefusal):
        depth.measure(sliver, _depth_field())


# ── 4. the asymmetry, stated rather than left as an accident ──────────────

@pytest.mark.parametrize("organ", sorted(ORGANS))
def test_an_organ_that_reads_an_external_artifact_names_it_on_the_mark(organ):
    """WHY ONLY TWO OF THE FOUR CARRY ARTIFACT PROVENANCE, as a rule rather than a coincidence.

    The geometry organs read the POST'S OWN `region_annotations` — `measure(a, b)` takes both terms
    from one document, so there is no second artifact that could be the wrong one, and a provenance
    field naming "the geometry" would be naming the thing the mark already cites by region id.

    Chroma and depth read an artifact handed in from OUTSIDE: pixels, and a model's depth grid.
    Only an external artifact can silently be a different picture, and that is exactly the class of
    error both now refuse. So this is the discipline "at the level each organ needs" — not the same
    field on all four, which would be provenance theatre on two of them.
    """
    mark = ORGANS[organ]["mask"]()
    prov = mark["provenance"]
    external = ORGANS[organ]["external_artifact"]

    named = [k for k in ("image_source", "model", "revision") if prov.get(k)]
    if external:
        assert named, f"{organ} reads an external artifact and its mark names none of it: {prov}"
    else:
        assert not named, (
            f"{organ} reads only the post's own geometry, so {named} on its mark would be naming "
            f"an artifact it does not have")


def test_the_two_sensory_organs_name_different_kinds_of_artifact():
    """Chroma's artifact is the pixels; depth's is a MODEL'S OUTPUT, so its mark names a checkpoint
    and a revision as well. Same discipline, different amount of it — which is what "at the level
    each needs" means when the levels genuinely differ."""
    chroma_prov = ORGANS[chroma.ORGAN]["mask"]()["provenance"]
    depth_prov = ORGANS[depth.ORGAN]["mask"]()["provenance"]

    assert chroma_prov["image_source"] == "audit:fixture"
    assert depth_prov["model"] and depth_prov["revision"] and depth_prov["adapter"]
    assert "revision" not in chroma_prov, \
        "chroma reads pixels, not a checkpoint — a revision here would be borrowed authority"


def test_no_organ_invents_a_comparable_number():
    """Re-asserted across the whole sensorium rather than per lane: commensurability stays refused,
    and a hidden magnitude under another name would be the easiest way to lose it quietly."""
    readings = {
        nest.ORGAN: nest.measure(PART, WHOLE),
        adj.ORGAN: adj.measure(PART, WHOLE),
        chroma.ORGAN: chroma.measure(PART, _frame()),
        depth.ORGAN: depth.measure(PART, _depth_field()),
    }
    for organ, reading in readings.items():
        for forbidden in ("score", "salience", "combined", "comparable"):
            assert not [k for k in reading if forbidden in k], (organ, forbidden)

    for module in (chroma, depth):
        with pytest.raises(module.Incommensurable):
            module.compare_across_senses(readings[nest.ORGAN], readings[module.ORGAN])
