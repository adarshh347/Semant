"""WAVE3 — chromatic rhyme: the claims, and the three ways a rhyme statistic lies.

The occlusion lane made the statistic question compulsory: it built difference-of-means first and
that failed on the one case it existed for. So these tests are arranged around what a WRONG rhyme
statistic would do, each of which produces a confident, plausible reading:

  1. IT WOULD SCORE COINCIDENCE — two regions sharing an average and nothing else. Centring makes
     that arithmetically impossible rather than merely unlikely, and §1 shows it on fields whose
     means are identical by construction.
  2. IT WOULD CREDIT ABSENCE — two flat fields "agreeing" that nothing happens. The `present`
     aggregation lesson. §2.
  3. IT WOULD SCORE NOISE — a correlation over a handful of cells is about the sample size. §3.

§4 is the substrate contract, §5 the mark and its provenance, §6 the scope this lane held.
"""
from __future__ import annotations

import math
import statistics

import pytest

from backend.services import chroma_organ as chroma
from backend.services import chromatic_relation as rel
from backend.services import epistemics, mask_geometry as mg
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

N = 32                       # mask raster
SAMPLE = chroma.SAMPLE


class Frame:
    """A synthetic image whose warmth is a declared function of position. No image library.

    `f(u, v) -> warmth in [-1, 1]` with u, v in [0, 1) over the whole frame. Warmth is realised as
    an (r, g, b) with the right red-minus-blue ratio, so the organ's own arithmetic recovers it.
    """

    def __init__(self, f, size=SAMPLE):
        self.f, self.size = f, size

    def convert(self, _mode):
        return self

    def resize(self, wh):
        return Frame(self.f, int(wh[0]))

    def getdata(self):
        out = []
        for y in range(self.size):
            for x in range(self.size):
                w = max(-1.0, min(1.0, self.f(x / self.size, y / self.size)))
                # w = (r - b) / (r + b) with r + b = 200
                r = int(round(100 * (1 + w)))
                out.append((r, 120, 200 - r))
        return out


def _frame(f, source="fixture"):
    return chroma.image_frame(Frame(f), source=source)


def _rect(x0, x1, y0, y1, w=N, h=N):
    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: Two regions in DIFFERENT places and DIFFERENT sizes, so a rhyme between them cannot be an
#: artifact of sharing coordinates — the canonical grid is over each region's own bounding box.
LEFT_BIG = {"id": "left_big", "mask_rle": _rect(1, 15, 1, 29)}
RIGHT_SMALL = {"id": "right_small", "mask_rle": _rect(18, 30, 6, 26)}

#: A SQUARE, so a left→right ramp and a top→bottom ramp have the same mean over it BY SYMMETRY
#: rather than by a fudge factor. The coincidence test needs the means to match exactly, and
#: arranging that with an offset would be arranging the answer.
SQUARE = {"id": "square", "mask_rle": _rect(8, 24, 8, 24)}

#: A DIAGONAL BAND. Its bounding box is large but it occupies only a handful of canonical cells,
#: which is the shape the shared-cell floor exists for — and the shape the real corpus is full of.
#: Two solid rectangles always co-occupy all 64 cells, so a rectangle could never exercise it.
def _diagonal(width=3, n=N):
    bits = [0] * (n * n)
    for i in range(n):
        for d in range(width):
            x = min(n - 1, i + d)
            bits[i * n + x] = 1
    return {"id": "diagonal", "mask_rle": mg.rle_encode(bits, n, n)}


DIAGONAL = _diagonal()


def _ramp(lo=-0.5, hi=0.5, offset=0.0):
    """Warmth ramping left→right across the whole frame, plus a constant offset."""
    return lambda u, v: lo + (hi - lo) * u + offset


def _flat(level=0.2):
    return lambda u, v: level


# ── 1. rhyme, not coincidence ──────────────────────────────────────────────

def test_two_regions_whose_warmth_runs_the_same_way_rhyme():
    """Both regions sit on a left→right warmth ramp, in different places and at different sizes.
    Their warmth is ORGANISED the same way, which is what the word is supposed to mean."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    assert m["rhyme"] > 0.9 and m["rhymes"] is True
    assert m["relation"] == rel.RELATION_RHYMES_WITH
    assert m["shared_cells"] >= rel.MIN_SHARED_CELLS


def test_two_regions_sharing_an_average_and_nothing_else_do_not_rhyme():
    """THE COINCIDENCE TRAP, and the reason it is closed by construction rather than by threshold.

    Both fields are built to have the same mean warmth over the region — one ramps left→right, the
    other ramps top→bottom. A mean-matching statistic would call these identical. Centring removes
    the mean before the comparison, so the shared average contributes nothing and only the
    (orthogonal) structures are compared.
    """
    horizontal = rel.measure(SQUARE, _frame(_ramp(), "a"),
                             SQUARE, _frame(lambda u, v: -0.5 + 1.0 * v, "b"))
    assert abs(horizontal["mean_gap"]) < 0.02, "the fixture must actually share a mean"
    assert horizontal["rhyme"] < 0.3
    assert horizontal["rhymes"] is False
    assert horizontal["relation"] == rel.RELATION_UNRELATED


def test_a_large_shared_offset_changes_nothing_at_all():
    """The strongest form of the same claim: the SAME structure at two very different warmth
    levels still rhymes, and by exactly the same number. If the mean contributed, it could not."""
    same = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    shifted = rel.measure(LEFT_BIG, _frame(_ramp(), "a"),
                          RIGHT_SMALL, _frame(_ramp(offset=0.4), "b"))
    assert shifted["mean_gap"] > 0.3, "the fixture must actually shift the mean"
    assert shifted["rhyme"] == pytest.approx(same["rhyme"], abs=1e-6)


def test_opposed_structures_score_negative_and_do_not_rhyme():
    """A rhyme is a correspondence, not a relationship. Warmth running the opposite way is a real
    reading and it is not a rhyme — reported, and below the floor."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"),
                    RIGHT_SMALL, _frame(_ramp(lo=0.5, hi=-0.5), "b"))
    assert m["rhyme"] < -0.9 and m["rhymes"] is False


def test_the_mean_gap_is_reported_so_a_reader_can_see_it_was_ignored():
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(offset=0.3), "b"))
    assert m["mean_gap"] > 0.2
    assert "removed by centring, not scored" in m["detail"]


# ── 2. absence is not agreement ───────────────────────────────────────────

def test_two_flat_fields_are_refused_rather_than_scored_as_rhyming():
    """THE ABSENCE-CREDIT TRAP — the `present` aggregation lesson in a second modality. Two fields
    with no structure agree about nothing; a correlation against a constant is 0/0, and both
    conventional answers to that (1.0, 0.0) are wrong in the flattering direction."""
    with pytest.raises(rel.RhymeRefusal, match="flat field cannot rhyme"):
        rel.measure(LEFT_BIG, _frame(_flat(0.2), "a"), RIGHT_SMALL, _frame(_flat(0.2), "b"))


def test_one_flat_side_is_enough_to_refuse():
    with pytest.raises(rel.RhymeRefusal, match="has a level and no structure"):
        rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_flat(0.0), "b"))


def test_the_refusal_is_not_a_null_reading():
    """`chromatically_unrelated` is a MEASUREMENT — both fields were read and do not correspond.
    A refusal is not, and collapsing them would let an unreadable pair count as evidence."""
    unrelated = rel.measure(LEFT_BIG, _frame(_ramp(), "a"),
                            LEFT_BIG, _frame(lambda u, v: -0.5 + 1.0 * v, "b"))
    assert unrelated["relation"] == rel.RELATION_UNRELATED
    assert "rhyme" in unrelated and unrelated["rhymes"] is False
    with pytest.raises(rel.RhymeRefusal):
        rel.measure(LEFT_BIG, _frame(_flat(), "a"), RIGHT_SMALL, _frame(_flat(), "b"))


def test_correlation_against_a_constant_returns_none_rather_than_a_number():
    assert rel._correlation([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None
    assert rel._correlation([5.0, 5.0], [5.0, 5.0]) is None
    assert rel._correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == pytest.approx(1.0)


# ── 3. a correlation over too few cells is about the sample size ─────────

def test_two_regions_that_barely_overlap_the_grid_are_refused():
    """CORPUS-DERIVED. Below 16 shared cells the permutation null itself clears |r| > 0.7 on 1.1%
    of pairs, and at 8-15 the same region turned up at both ends of the ranking."""
    with pytest.raises(rel.RhymeRefusal, match="canonical cells, below"):
        rel.measure(LEFT_BIG, _frame(_ramp(), "a"), DIAGONAL, _frame(_ramp(), "b"))


def test_two_solid_rectangles_always_co_occupy_the_whole_grid():
    """Worth pinning, because it says what the shared-cell floor is FOR. A solid convex region
    fills every canonical cell of its own bounding box, so two rectangles always share all 64 and
    the floor never bites. It exists for irregular masks — which is what a segmenter produces, and
    where the corpus showed 12 to 64 shared cells."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    assert m["shared_cells"] == rel.RHYME_GRID ** 2

    cells, _ = rel.warmth_shape(DIAGONAL, _frame(_ramp(), "a"))
    assert len(cells) < rel.MIN_SHARED_CELLS, "the diagonal must be sparse on the canonical grid"


def test_a_region_thinner_than_the_grid_is_refused_rather_than_upsampled():
    """Resampling a 3-pixel-wide region onto an 8×8 grid would invent the structure being
    compared — the same reasoning `adjacency_organ` gives for refusing to resample masks."""
    thin = {"id": "thin", "mask_rle": _rect(0, 3, 0, 30)}
    with pytest.raises(rel.RhymeRefusal, match="thinner than"):
        rel.measure(LEFT_BIG, _frame(_ramp(), "a"), thin, _frame(_ramp(), "b"))


def test_nothing_rhymes_with_itself():
    frame = _frame(_ramp(), "a")
    with pytest.raises(rel.RhymeRefusal, match="against itself"):
        rel.measure(LEFT_BIG, frame, LEFT_BIG, frame)


def test_the_same_region_in_two_different_frames_is_a_legitimate_pair():
    """Not self-comparison: one region's geometry read against two different pictures is exactly
    the cross-image question, and the ids matching is incidental."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), LEFT_BIG, _frame(_ramp(), "b"))
    assert m["rhyme"] > 0.9


# ── 4. the substrate contract ────────────────────────────────────────────

def test_a_mask_pair_is_measured_and_a_box_pair_is_an_estimate():
    boxed = {"id": "boxed", "box": {"x": 0.55, "y": 0.2, "w": 0.4, "h": 0.6}}
    masked = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    mixed = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), boxed, _frame(_ramp(), "b"))

    assert masked["basis"] == "mask" and mixed["basis"] == "box"
    assert rel.grounding_mark(masked)[STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert rel.grounding_mark(mixed)[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    assert rel.is_admissible(masked) and not rel.is_admissible(mixed)


def test_the_weaker_basis_governs():
    """One box on either side makes the whole pair an estimate. A rhyme between a mask and a box is
    a rhyme with something that includes whatever is behind it."""
    boxed = {"id": "boxed", "box": {"x": 0.55, "y": 0.2, "w": 0.4, "h": 0.6}}
    for pair in ((LEFT_BIG, boxed), (boxed, LEFT_BIG)):
        m = rel.measure(pair[0], _frame(_ramp(), "a"), pair[1], _frame(_ramp(), "b"))
        assert m["basis"] == "box"


def test_a_measured_claim_about_a_box_pair_is_refused_by_the_guard():
    boxed = {"id": "boxed", "box": {"x": 0.55, "y": 0.2, "w": 0.4, "h": 0.6}}
    mark = rel.grounding_mark(rel.measure(LEFT_BIG, _frame(_ramp(), "a"),
                                          boxed, _frame(_ramp(), "b")))
    assert epistemics.guard([mark]) == [mark]
    with pytest.raises(epistemics.EpistemicViolation, match="substrate"):
        epistemics.guard([{**mark, STATUS_KEY: EpistemicStatus.MEASURED.value}])


def test_a_crop_frame_is_refused_by_the_provenance_contract():
    """Inherited from the audit: the mask's coordinates are the frame's coordinates."""
    crop = chroma.image_frame(Frame(_ramp()), source="x", whole_frame=False)
    with pytest.raises(chroma.ChromaRefusal, match="not the whole picture"):
        rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, crop)
    with pytest.raises(chroma.ChromaRefusal, match="names no source"):
        rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL,
                    chroma.image_frame(Frame(_ramp()), source=""))


def test_the_relation_declares_its_substrates():
    assert epistemics.declared_substrates(rel.ORGAN) == ("mask", "box")
    assert epistemics.default_status_for(rel.ORGAN) is EpistemicStatus.MEASURED
    epistemics.assert_substrate_tables_agree()


# ── 5. the mark, and both artifacts named ───────────────────────────────

def test_the_mark_names_both_images_it_read():
    """ORGAN-PROVENANCE-001: chroma reads an external artifact, and a cross-image relation reads
    two of them. A mark naming one would leave half the reading anonymous."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "picture-a"), RIGHT_SMALL, _frame(_ramp(), "picture-b"))
    mark = rel.grounding_mark(m, post_id="p")
    prov = mark["provenance"]

    assert prov["producer"] == rel.ORGAN
    assert prov["a_image"] == "picture-a" and prov["b_image"] == "picture-b"
    assert mark[epistemics.SUBSTRATE_KEY] == "mask"
    assert epistemics.producer_of(mark) == rel.ORGAN
    assert epistemics.guard([mark]) == [mark]


def test_the_statistic_is_on_every_reading_so_a_caller_can_rethreshold():
    """`occlusion_organ` established this for `dominance`: a floor that is a free parameter must
    not force a re-measurement to disagree with."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    for key in ("rhyme", "shared_cells", "a_spread", "b_spread", "mean_gap", "thresholds"):
        assert key in m
    assert m["thresholds"]["min_rhyme"] == rel.MIN_RHYME
    assert rel.grounding_mark(m)["measurement"]["rhyme"] == m["rhyme"]


def test_amplitude_is_reported_and_never_folded_in():
    """Correlation is scale-free, and the docstring says so rather than hiding it: a rhyme claims
    the warmth is ORGANISED the same way, not that the two are equally chromatic. Both spreads ride
    on the reading so a caller who wants amplitude agreement can add it."""
    strong = _frame(_ramp(-0.6, 0.6), "a")
    faint = _frame(_ramp(-0.06, 0.06), "b")
    m = rel.measure(LEFT_BIG, strong, RIGHT_SMALL, faint)
    assert m["rhyme"] > 0.9, "the shapes correspond"
    assert m["a_spread"] > 5 * m["b_spread"], "and the amplitudes do not"


# ── 6. scope, and no second definition of warmth ────────────────────────

def test_this_modules_warmth_agrees_with_the_organs():
    """The relation recomputes warmth rather than reaching into `chroma_organ`'s private helper.
    That is a copy, and a copy can drift into a second definition — so it is pinned against the
    organ's own `warmth_mean` over the same region and frame."""
    frame = _frame(_ramp(), "a")
    cells, basis = rel.warmth_shape(LEFT_BIG, frame)
    assert basis == "mask"
    mine = statistics.fmean(cells.values())
    theirs = chroma.measure(LEFT_BIG, frame)["warmth_mean"]
    assert mine == pytest.approx(theirs, abs=0.05), (mine, theirs)


def test_the_lane_did_not_touch_the_systematicity_gate():
    """The higher-order lane settled `structure_map` as a null and this lane CONSUMES it. A
    relation lane that quietly re-opened the gate would be re-litigating a settled decision from
    the one place nobody would look for it."""
    import subprocess
    changed = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        capture_output=True, text=True,
        cwd=str(__import__("pathlib").Path(rel.__file__).resolve().parents[3])).stdout
    assert "structure_map.py" not in changed, changed
    assert "chroma_organ.py" not in changed, f"the organ was changed: {changed}"


def test_the_relation_invents_no_cross_modal_number():
    """The commensurability guard still holds. A chromatic rhyme and a geometric containment remain
    incomparable; this lane makes chroma relational, not commensurable."""
    m = rel.measure(LEFT_BIG, _frame(_ramp(), "a"), RIGHT_SMALL, _frame(_ramp(), "b"))
    for forbidden in ("score", "salience", "combined", "comparable", "strength"):
        assert not [k for k in m if forbidden in k], forbidden
    with pytest.raises(chroma.Incommensurable):
        chroma.compare_across_senses({"nesting_index": 0.8}, m)
