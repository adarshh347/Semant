"""WAVE3 — the first non-geometric sense: the claims, and where a new sense would lie.

A sense is a good place to smuggle something in, because "the organ measured it" is a sentence
nobody checks twice about a modality nobody else in the system can read. So these tests are the
guard on five claims, each of which would still look right from the outside if it failed:

  1. IT MEASURES SOMETHING REAL — the field tracks the pixels, and the gradient tracks where the
     warm pixels are. A warmth organ that returned a plausible constant would be indistinguishable
     from this one in every transcript the run script prints. §1.
  2. THE SUBSTRATE CONTRACT (TWO-STATUS-001) — first organ built on it rather than retrofitted:
     `measured` on masks, `interpretive` on boxes, and a measured-on-box claim refused by the
     guard. §2.
  3. THE NAMING IS A SECOND PRODUCER — "warm" is a word with an uncalibrated threshold behind it,
     and it is emitted separately so a curator can keep the number and throw away the word. §3.
  4. A DIFFERENT WORLD AT THE SAME PLACE — a geometry agent and a chroma agent on one region
     produce percept fields with nothing in common. This is the lane's payoff and it is a number,
     not an assertion. §4.
  5. COMMENSURABILITY IS REFUSED, NOT SOLVED — there is no scale on which a warmth mean and a
     nesting index compare, and the absence is reachable rather than merely undocumented. §5.

§6 covers purity and the substrate-declaration scan, and §7 pins the percept-expression defect this
lane found in the two organs that came before it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services import chroma_organ as chroma
from backend.services import epistemics, nestedness_organ as nest
from backend.services.agents import organs
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

STAMP = "2026-08-06T00:00:00+00:00"


# ── fixtures: a synthetic raster, and NO image library ──────────────────────

class Raster:
    """A hand-painted image, satisfying exactly the three methods `sample_rgb` uses.

    No PIL. That is the point of the duck-typed protocol: an organ whose tests need an image
    library installed is an organ whose behaviour is partly that library's, and the numbers below
    would then be checking a resampler as much as a measurement.
    """

    def __init__(self, pixels, size):
        self.pixels, self.size = pixels, size

    @classmethod
    def split(cls, left, right, size=64):
        """Left half one colour, right half another — a raster with a known warmth gradient.

        Returned as a DECLARED FRAME (`chroma_organ.image_frame`), not a bare image, because
        ORGAN-PROVENANCE-001 made that the organ's contract: the mask's coordinates are the frame's
        coordinates, and an image that is not that frame produces a confident number about a
        different subject. The fixtures declare it the same way a real caller has to.
        """
        px = [left if x < size // 2 else right for _ in range(size) for x in range(size)]
        return chroma.image_frame(cls(px, size), source="fixture:split")

    @classmethod
    def flat(cls, rgb, size=64):
        return chroma.image_frame(cls([rgb] * (size * size), size), source="fixture:flat")

    @classmethod
    def raw(cls, rgb, size=64):
        """The undeclared image, for the tests that check the refusal."""
        return cls([rgb] * (size * size), size)

    def convert(self, _mode):
        return self

    def resize(self, wh):
        w = int(wh[0])
        if w == self.size:
            return self
        out = [self.pixels[(y * self.size // w) * self.size + (x * self.size // w)]
               for y in range(w) for x in range(w)]
        return Raster(out, w)

    def getdata(self):
        return list(self.pixels)


WARM = (220, 120, 40)     # strongly red-over-blue
COOL = (40, 110, 220)     # strongly blue-over-red
GREY = (128, 128, 128)    # neither


def _rle(x0, x1, y0, y1, w=16, h=16):
    from backend.services import mask_geometry as mg

    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: The left half of the frame, masked. On a `Raster.split(WARM, COOL)` this region contains only
#: warm pixels while its BOUNDING BOX (the same rectangle) contains only warm pixels too — so a
#: second fixture is needed to make the two bases disagree. See `L_SHAPE`.
LEFT = {"id": "r_left", "label": "left", "mask_rle": _rle(0, 8, 0, 16)}

#: An L: the warm left column plus a strip reaching into the cool right half. Its MASK is mostly
#: warm; its BOUNDING BOX spans the whole frame and is therefore half cool. This is the fixture
#: that makes "a box is a different subject" a number rather than a sentence.
L_SHAPE = {"id": "r_L", "label": "ell", "mask_rle": _rle(0, 4, 0, 16),
           "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}

#: Mask-free: only a box, so the organ must take the box path.
BOXED = {"id": "r_box", "label": "boxed", "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}

#: Too small to read — a refusal, never a neutral field.
SLIVER = {"id": "r_sliver", "label": "sliver", "mask_rle": _rle(0, 1, 0, 1)}


# ── 1. it measures something real ───────────────────────────────────────────

def test_warmth_tracks_the_pixels_in_both_directions():
    """The number moves with the light, and it is signed. A constant would pass a test that only
    checked the warm case."""
    warm = chroma.measure(LEFT, Raster.flat(WARM))
    cool = chroma.measure(LEFT, Raster.flat(COOL))
    grey = chroma.measure(LEFT, Raster.flat(GREY))

    assert warm["warmth_mean"] > 0.5
    assert cool["warmth_mean"] < -0.5
    assert abs(grey["warmth_mean"]) < 1e-6
    assert warm["chroma_mean"] > 0.5 and grey["chroma_mean"] == 0.0


def test_a_neutral_region_is_measured_not_refused():
    """Zero warmth means "measured, and this is neither warm nor cool". A refusal means "not
    measured". Collapsing them would report an unread region as neutral grey."""
    grey = chroma.measure(LEFT, Raster.flat(GREY))
    assert grey["warmth_mean"] == 0.0
    assert grey["sampled_pixels"] > 0
    with pytest.raises(chroma.ChromaRefusal, match="below"):
        chroma.measure(SLIVER, Raster.flat(GREY))


def test_the_gradient_says_which_way_the_warmth_runs():
    """THE FIELD, as opposed to the swatch. A uniformly warm region and a region lit warm on one
    side have the same mean and are not the same thing to stand in — an organ reporting only the
    average would erase that and never say it had."""
    whole = {"id": "r_all", "mask_rle": _rle(0, 16, 0, 16)}

    split = chroma.measure(whole, Raster.split(WARM, COOL))["gradient"]
    assert split["magnitude"] > 0.5
    assert split["dx"] < -0.2, "warm is on the LEFT, so the warm centroid sits left of the cool one"
    assert abs(split["dy"]) < 0.1, "the split is vertical: nothing should run up or down"

    flat = chroma.measure(whole, Raster.flat(WARM))["gradient"]
    assert flat["magnitude"] == 0.0 and flat["dx"] == 0.0 and flat["dy"] == 0.0
    assert "uniform" in flat["detail"]


def test_an_organ_with_no_pixels_refuses_rather_than_reading_grey():
    with pytest.raises(chroma.ChromaRefusal, match="no pixels"):
        chroma.measure(LEFT, None)


def test_a_bare_image_is_refused_because_it_declares_no_frame():
    """ORGAN-PROVENANCE-001. The organ used to take any image and index the region's mask against
    it, which is only meaningful if the image IS the frame the mask was drawn on."""
    with pytest.raises(chroma.ChromaRefusal, match="bare image"):
        chroma.measure(LEFT, Raster.raw(WARM))


def test_a_frame_that_admits_it_is_a_crop_is_refused():
    frame = chroma.image_frame(Raster.raw(WARM), source="fixture", whole_frame=False)
    with pytest.raises(chroma.ChromaRefusal, match="not the whole picture"):
        chroma.measure(LEFT, frame)


def test_a_frame_that_names_no_source_is_refused():
    frame = chroma.image_frame(Raster.raw(WARM), source="")
    with pytest.raises(chroma.ChromaRefusal, match="names no source"):
        chroma.measure(LEFT, frame)


def test_the_reading_that_made_this_a_rule():
    """THE AUDIT FINDING, kept as a test so nobody has to take the docstring's word for it.

    The same region, the same call, two images that differ only in framing. Before the frame
    contract both produced a `measured` mark of identical shape, and the sign of the answer was
    opposite. Nothing downstream could have told them apart.
    """
    class Shifted(Raster):
        def __init__(self, size=64, off=0):
            super().__init__([], size)
            self.off = off

        def resize(self, wh):
            return Shifted(int(wh[0]), self.off)

        def getdata(self):
            return [(WARM if (x + self.off) < self.size // 2 else COOL)
                    for _ in range(self.size) for x in range(self.size)]

    on_frame = chroma.measure(LEFT, chroma.image_frame(Shifted(), source="frame"))
    shifted = chroma.measure(LEFT, chroma.image_frame(Shifted(off=32), source="other"))

    assert on_frame["warmth_mean"] > 0.5 and shifted["warmth_mean"] < -0.5, \
        "the fixture must actually flip the sign or this test proves nothing"
    # ...and now the two marks are distinguishable, which is the whole fix
    a = chroma.grounding_mark(on_frame, post_id="p")["provenance"]["image_source"]
    b = chroma.grounding_mark(shifted, post_id="p")["provenance"]["image_source"]
    assert a == "frame" and b == "other" and a != b


def test_it_reads_no_label_and_no_category():
    """What it says must be checkable against the numbers, so it may not be about what the region
    depicts. Same reading from the same pixels whatever the region is called."""
    a = chroma.measure({**LEFT, "label": "sky", "category": "background"}, Raster.flat(WARM))
    b = chroma.measure({**LEFT, "label": "fire", "category": "subject"}, Raster.flat(WARM))
    assert a["warmth_mean"] == b["warmth_mean"] and a["detail"] == b["detail"]


# ── 2. the substrate contract, on the first organ built for it ──────────────

def test_a_mask_reading_is_measured_and_a_box_reading_is_an_estimate():
    masked = chroma.measure(L_SHAPE, Raster.split(WARM, COOL))
    boxed = chroma.measure(BOXED, Raster.split(WARM, COOL))

    assert masked["basis"] == "mask"
    assert chroma.grounding_mark(masked, post_id="p")[STATUS_KEY] == \
        EpistemicStatus.MEASURED.value
    assert boxed["basis"] == "box"
    assert chroma.grounding_mark(boxed, post_id="p")[STATUS_KEY] == \
        EpistemicStatus.INTERPRETIVE.value
    assert chroma.is_admissible(masked) and not chroma.is_admissible(boxed)


def test_the_box_path_is_a_number_about_a_different_subject():
    """WHY the box path is `interpretive` here, as a measurement rather than an argument.

    `L_SHAPE`'s mask is the warm left column; its bounding box spans the whole frame and is
    therefore half cool. Same region, same pixels available, two bases — and the two answers do not
    merely differ in precision, they differ in SIGN. That is the WAVE2.5 case (a box around a spire
    contains the sky) arriving in a second modality.
    """
    image = Raster.split(WARM, COOL)
    by_mask = chroma.measure(L_SHAPE, image)
    by_box = chroma.measure(BOXED, image)

    assert by_mask["warmth_mean"] > 0.4
    assert by_box["warmth_mean"] < 0.1
    assert by_mask["warmth_mean"] - by_box["warmth_mean"] > 0.4


def test_the_guard_admits_both_kinds_and_refuses_a_measured_box():
    """THE CONTRACT, exercised end to end by the first organ built on it — and the refusal is the
    half that makes the widening safe."""
    image = Raster.split(WARM, COOL)
    for region in (L_SHAPE, BOXED):
        mark = chroma.grounding_mark(chroma.measure(region, image), post_id="p")
        assert epistemics.guard([mark]) == [mark]

    boxed = chroma.grounding_mark(chroma.measure(BOXED, image), post_id="p")
    with pytest.raises(epistemics.EpistemicViolation, match="substrate"):
        epistemics.guard([{**boxed, STATUS_KEY: EpistemicStatus.MEASURED.value}])


def test_the_mark_names_its_substrate_in_the_contracts_own_key():
    """Born after TWO-STATUS-001, so it writes `epistemic_basis` flat rather than leaving the guard
    to find it under `measurement.basis` — which is where the two organs that predate the contract
    keep it, and which `substrate_of` still reads for them."""
    mark = chroma.grounding_mark(chroma.measure(LEFT, Raster.flat(WARM)), post_id="p")
    assert mark[epistemics.SUBSTRATE_KEY] == "mask"
    assert epistemics.substrate_of(mark) == "mask"
    assert mark["provenance"]["image_source"] == "fixture:flat"


def test_the_organ_declares_its_substrates():
    assert epistemics.declared_substrates(chroma.ORGAN) == ("mask", "box")
    assert epistemics.default_status_for(chroma.ORGAN) is EpistemicStatus.MEASURED
    assert epistemics.permitted_statuses(chroma.ORGAN) == frozenset(
        {EpistemicStatus.MEASURED, EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN})
    epistemics.assert_substrate_tables_agree()


def test_the_three_organs_read_one_ruling():
    from backend.services import adjacency_organ as adj

    for basis in ("mask", "box"):
        assert chroma.epistemic_for(basis) == nest.epistemic_for(basis) == \
            adj.epistemic_for(basis) == epistemics.substrate_ceiling(basis).value


# ── 3. the naming is a second producer, not a second status ────────────────

def test_the_word_is_a_separate_producer_and_always_interpretive():
    """`DECISION-two-status-producer-declares-its-substrates` §8: if a curator could accept the
    field and reject the name, they are two descriptors. A curator plainly could — the field is
    computed from the pixels, the word is a convention about where warm begins."""
    named = chroma.name_of(chroma.measure(LEFT, Raster.flat(WARM)))
    assert named["producer"] == chroma.NAMING_PRODUCER != chroma.ORGAN
    assert named[STATUS_KEY] == EpistemicStatus.INTERPRETIVE.value
    assert epistemics.default_status_for(chroma.NAMING_PRODUCER) is EpistemicStatus.INTERPRETIVE
    assert epistemics.guard([named]) == [named]


def test_the_naming_declares_no_substrate_because_no_substrate_could_help_it():
    """Declaring one would suggest a mask could make "warm" a measurement. Nothing can: the
    threshold is a convention and nothing in the picture votes on it."""
    assert epistemics.declared_substrates(chroma.NAMING_PRODUCER) == ()
    assert "basis" not in chroma.name_of(chroma.measure(LEFT, Raster.flat(WARM)))
    with pytest.raises(epistemics.EpistemicViolation):
        epistemics.declare(chroma.NAMING_PRODUCER, EpistemicStatus.MEASURED)


@pytest.mark.parametrize("rgb,mood", [(WARM, "warm"), (COOL, "cool"), (GREY, "neutral")])
def test_the_word_follows_the_number_and_says_which_threshold_it_used(rgb, mood):
    named = chroma.name_of(chroma.measure(LEFT, Raster.flat(rgb)))
    assert named["mood"] == mood
    assert named["threshold"] == chroma.WARM_THRESHOLD
    assert "UNCALIBRATED" in named["detail"]


def test_rejecting_the_word_costs_nothing_that_was_measured():
    """The whole point of the split, made concrete: drop the naming descriptor and the field
    descriptor is untouched — same numbers, same mark, same status."""
    measurement = chroma.measure(LEFT, Raster.flat(WARM))
    mark = chroma.grounding_mark(measurement, post_id="p")
    chroma.name_of(measurement)                                  # produced, then discarded
    assert mark["measurement"]["warmth_mean"] == measurement["warmth_mean"]
    assert epistemics.producer_of(mark) == chroma.ORGAN
    assert epistemics.guard([mark]) == [mark]
    assert "mood" not in mark and "mood" not in mark["measurement"]


# ── 4. a different world at the same place ─────────────────────────────────

def _post(post_id="pc"):
    """One region that ALL THREE organs can read from — nested in `r_whole`, meeting its rim, and
    big enough to carry a warmth field. Needed so §7 can compare the three narrations of one
    locus rather than three different ones."""
    return {"_id": post_id, "region_annotations": [
        {"id": "r_part", "label": "part", "mask_rle": _rle(4, 8, 2, 14)},
        {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 8, 0, 16)},
    ]}


def test_a_geometry_agent_and_a_chroma_agent_enact_different_worlds():
    """THE PAYOFF OF THE LANE, as a number rather than a claim.

    Same post, same region, same instant. The dialogue lane already showed two GEOMETRIC bodies
    differing; this is the first pair whose fields have no term in common at all — different organ,
    different relation vocabulary, different measurement keys, and one of them relates the locus to
    a second region while the other relates it to nothing.
    """
    post, image = _post(), Raster.split(WARM, COOL)
    geo = sa.inhabit(agent_id="geo", post_id="pc", region_id="r_part",
                     organ_set=(nest.ORGAN,))
    chr_ = sa.inhabit(agent_id="chr", post_id="pc", region_id="r_part",
                      organ_set=(chroma.ORGAN,))
    sa.perceive(geo, post, now=STAMP)
    sa.perceive(chr_, post, now=STAMP, image=image)

    assert geo.percept_field and chr_.percept_field
    assert {p.organ for p in geo.percept_field} == {nest.ORGAN}
    assert {p.organ for p in chr_.percept_field} == {chroma.ORGAN}

    # no shared relation vocabulary
    assert not ({p.reading.relation for p in geo.percept_field} &
                {p.reading.relation for p in chr_.percept_field})
    # no shared measurement keys beyond the bookkeeping every organ carries
    geo_keys = set(geo.percept_field[0].reading.measurement)
    chr_keys = set(chr_.percept_field[0].reading.measurement)
    assert geo_keys & chr_keys == {"organ", "organ_version", "basis", "basis_detail",
                                   "detail", "thresholds"}, sorted(geo_keys & chr_keys)
    # and the geometry agent relates itself to a second region while chroma relates itself to none
    assert all(p.reading.other_region_id for p in geo.percept_field)
    assert all(p.reading.other_region_id == "" for p in chr_.percept_field)

    # both are `measured`, on masks, and neither is stronger than the other for being so
    for agent in (geo, chr_):
        assert {p.epistemic_status for p in agent.percept_field} == \
            {EpistemicStatus.MEASURED.value}


def test_a_field_reading_rests_on_one_ground_not_two():
    """A relation rests on both its terms; a field rests only on the region it was read over. A
    second ground carrying an empty `region_id` would be a reference to nothing, sitting in the
    list a reader trusts to say what the claim stands on."""
    post = _post()
    agent = sa.inhabit(agent_id="c", post_id="pc", region_id="r_part", organ_set=(chroma.ORGAN,))
    sa.perceive(agent, post, now=STAMP, image=Raster.flat(WARM))

    perception = agent.percept_field[0]
    assert len(perception.grounds) == 1
    assert perception.grounds[0].region_id == "r_part"
    assert perception.grounds[0].detector == chroma.ORGAN
    assert perception.percept.ground_ids == [perception.grounds[0].id]


def test_the_agent_reports_a_field_as_proposed_like_any_other_reading():
    """Perceive-only does not mean a second reporting path. The chroma reading goes out through
    the same `report` the geometry organs use, carries no status of its own, and reads `proposed`
    until a curator commits the mark."""
    from backend.services.agents import observation as obs_mod

    post = _post()
    agent = sa.inhabit(agent_id="c", post_id="pc", region_id="r_part", organ_set=(chroma.ORGAN,))
    sa.perceive(agent, post, now=STAMP, image=Raster.flat(WARM))
    rows = sa.report(agent, now=STAMP)

    assert rows and all(STATUS_KEY not in row for row in rows)
    hydrated = obs_mod.hydrate_observation(rows[0], {"pc": post})
    assert hydrated["ledger_status"] == obs_mod.LEDGER_PROPOSED


def test_the_private_memory_carries_the_organs_own_headline_number():
    """And not a `nesting_index` of None. That was the shape before this lane: a hardcoded geometry
    key, which for a non-geometric reading writes a null a reader takes for "measured no nesting"
    rather than "measures no such thing"."""
    post = _post()
    agent = sa.inhabit(agent_id="c", post_id="pc", region_id="r_part", organ_set=(chroma.ORGAN,))
    sa.perceive(agent, post, now=STAMP, image=Raster.flat(WARM))
    entry = sa.remember(agent, now=STAMP)[0]

    assert "warmth_mean" in entry and "nesting_index" not in entry
    assert entry[STATUS_KEY] == EpistemicStatus.MEASURED.value


def test_an_agent_bound_to_chroma_with_no_image_perceives_nothing_and_says_so():
    post = _post()
    agent = sa.inhabit(agent_id="c", post_id="pc", region_id="r_part", organ_set=(chroma.ORGAN,))
    with pytest.raises(organs.OrganRefusal, match="no image was handed"):
        sa.perceive(agent, post, now=STAMP)
    assert agent.percept_field == []


# ── 5. commensurability: named, reachable, and refused ─────────────────────

def test_comparing_two_senses_on_one_scale_is_refused():
    """THE OPEN PROBLEM, made reachable instead of merely undocumented.

    A warmth mean and a nesting index are both small floats, which is a fact about floating point.
    A missing function would be indistinguishable from one nobody has needed; this one says, at the
    point somebody wants the number, that nobody has earned it — which is the single easiest place
    for this system to become confident about something it has never measured.
    """
    post, image = _post(), Raster.flat(WARM)
    geometry = nest.measure(post["region_annotations"][0], post["region_annotations"][1])
    warmth = chroma.measure(post["region_annotations"][0], image)

    with pytest.raises(chroma.Incommensurable, match="no common scale"):
        chroma.compare_across_senses(geometry, warmth)


def test_the_organ_invents_no_shared_magnitude():
    """The refusal above is worth nothing if a comparable number is sitting in the measurement
    under another name. Nothing here is normalized against geometry, and no combined score
    exists."""
    measurement = chroma.measure(LEFT, Raster.flat(WARM))
    for forbidden in ("score", "strength", "salience", "weight", "combined", "index"):
        assert not [k for k in measurement if forbidden in k], (forbidden, sorted(measurement))


# ── 6. purity, and the substrate-declaration scan ──────────────────────────

#: A pure organ reaches nothing outside itself. PIL is on the list too, and that is the stricter
#: half: the duck-typed protocol in `sample_rgb` is what makes this organ testable with a synthetic
#: raster, and an import would quietly make its numbers partly a resampler's.
_IMPURE = re.compile(
    r"\b(database|requests|httpx|aiohttp|torch|transformers|motor|PIL|cv2|numpy|"
    r"llm_service|groq|openai|anthropic|vision_service)\b")


def test_the_chroma_organ_is_pure():
    source = Path(chroma.__file__).read_text()
    for lineno, line in enumerate(source.splitlines(), 1):
        if not (line.startswith("import ") or line.startswith("from ")):
            continue
        hit = _IMPURE.search(line)
        assert hit is None, f"chroma_organ.py:{lineno} imports {hit.group(0)!r} — not pure"


def test_this_test_file_needs_no_image_library():
    """The claim above, from the other side: if the fixtures needed PIL the organ's protocol would
    not really be duck-typed, it would be PIL-shaped with a docstring."""
    source = Path(__file__).read_text()
    assert not re.search(r"^\s*(import|from)\s+(PIL|cv2|numpy)\b", source, re.M)


def test_the_organ_appears_in_the_substrate_declaration_scan():
    """TWO-STATUS-001 left a scan that fails for any module adopting the ruling without declaring.
    This lane is the first new organ since, so it is the first real test of that guard."""
    services = Path(chroma.__file__).resolve().parent
    adopters = set()
    for path in sorted(services.glob("*.py")):
        text = path.read_text()
        if "substrate_ceiling" not in text and "def epistemic_for" not in text:
            continue
        found = re.search(r'^ORGAN\s*=\s*"([^"]+)"', text, re.M)
        if found:
            adopters.add(found.group(1))
    assert chroma.ORGAN in adopters
    assert not adopters - set(epistemics._SUBSTRATES)


def test_resolve_reports_the_organ_and_says_it_needs_pixels():
    """The card asked for the roles registry. The registry's organ half is GENERATED from
    `default_roster()` and `test_role_registry` pins that organ roles are never hand-listed, so a
    weightless organ has no roster entry to generate from — the contradiction WAVE3 already
    recorded. `PURE_PYTHON_ORGANS` is the route the tree allows, and `resolve()` reporting it is
    the outcome the card wanted."""
    binding = organs.resolve(chroma.ORGAN)
    assert binding.resolution == organs.RESOLVED and binding.invocable
    assert "pixels are handed in" in binding.detail
    assert chroma.ORGAN in organs.PURE_PYTHON_ORGANS and chroma.ORGAN in organs._NEEDS_PIXELS


# ── 7. the percept-expression defect this lane found ───────────────────────

def test_a_reading_is_narrated_by_the_organ_that_took_it():
    """THE DEFECT THIS LANE FOUND IN THE TWO ORGANS BEFORE IT, pinned so it cannot come back.

    `situated_agent._percept_for` composed the percept's `expression` from a hardcoded "nested
    within". That was true while nestedness was the only organ and became false the moment
    adjacency arrived: a `meets` reading with contact 0.600 minted a percept reading
    "whole nested within rim" — the wrong relation AND the inverted direction, in the one field a
    reader takes for the agent's own account of what it perceived. Nothing caught it because the
    dialogue lane asserted on `relation` and on the mark and never on the percept.

    A field organ made it structural: chroma relates nothing, so any sentence composed from a
    relation vocabulary is false by construction.
    """
    from backend.services import adjacency_organ as adj

    post = _post()
    expected = {
        nest.ORGAN: re.compile(r"^r_part nested within r_whole$"),
        adj.ORGAN: re.compile(r"^r_part meets r_whole$"),
        chroma.ORGAN: re.compile(r"^r_part reads [+-]\d\.\d{3} on the warm/cool axis$"),
    }
    for organ_name, pattern in expected.items():
        agent = sa.inhabit(agent_id="a", post_id="pc", region_id="r_part",
                           organ_set=(organ_name,))
        image = Raster.split(WARM, COOL) if organ_name in organs._NEEDS_PIXELS else None
        sa.perceive(agent, post, now=STAMP, image=image)
        assert agent.percept_field, f"{organ_name} measured nothing at this locus"
        for perception in agent.percept_field:
            said = perception.percept.model_dump(mode="json")["expression"]
            assert pattern.match(said), f"{organ_name} narrated {said!r}"


def test_an_organ_that_writes_no_sentence_is_refused():
    """A blank expression would become an empty `expression` on a typed percept — an agent that
    noticed nothing, holding a measurement that says otherwise."""
    reading = organs.OrganReading(
        organ="mute_organ", relation="x", direction="field", locus_region_id="r_part",
        other_region_id="", measurement={"basis": "mask"}, mark={}, detail="d", expression="")
    with pytest.raises(sa.MarkMisstated, match="no expression"):
        sa._percept_for(reading, ())
