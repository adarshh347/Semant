"""WAVE3 — the depth organ: the claims, and the one this lane must not overstate.

Depth is the sense that could finally answer the question WAVE2.5 could only route around — is the
finial INSIDE the sky or IN FRONT OF it. That makes it the easiest organ so far to oversell, so the
tests are arranged around what it does and does not establish:

  1. IT MEASURES SOMETHING REAL — the field tracks the depth grid, and the frame rank tracks where
     the region sits against everything else. A depth organ returning a plausible constant would be
     indistinguishable in every transcript. §1.
  2. THE BOX ARGUMENT, NO LONGER AN ANALOGY — a box around a near part contains what the part is in
     front of, so a box-basis reading is the arithmetic mean of a thing and the thing behind it.
     That is the `cseg_golden_finial_7` failure itself, and §2 reproduces it as a number.
  3. PROVENANCE IS REQUIRED — a synthetic depth grid and a real one are the same list of floats,
     and this organ mints `measured`. §3.
  4. THE MODEL AND THE SENSE ARE DIFFERENT THINGS — the roster role is residency-managed and this
     lane still may not start it; the sense is pure and invocable. §4.
  5. NO RELATION, AND NO HIDDEN COMPARABLE NUMBER — `in_front_of` is not in this lane, and cross-
     sense comparison raises. §5.

§6 is purity and the substrate-declaration scan.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services import chroma_organ
from backend.services import depth_organ as depth
from backend.services import epistemics, nestedness_organ as nest
from backend.services.agents import organs
from backend.services.agents import situated_agent as sa
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

STAMP = "2026-08-06T00:00:00+00:00"
GRID = 16

#: The real pinned checkpoint, so a fixture cannot pass while naming a model nobody uses.
MODEL = "depth_anything_v2_small"
REVISION = "5426e4f0f36572d16453bbda7a8389317b1bef99"


def _field(depth_values, grid=GRID, **over):
    base = depth.depth_field(
        {"depth": depth_values, "grid": grid},
        adapter=depth.SOURCE_ADAPTER, model=MODEL, revision=REVISION,
        preprocessing_version="depth-anything-v2-s-v1")
    return {**base, **over}


def _flat(value, grid=GRID, **over):
    return _field([float(value)] * (grid * grid), grid, **over)


def _near_left(grid=GRID, near=9.0, far=1.0, **over):
    """Left half NEAR (large inverse depth), right half FAR. A frame with a known ordering."""
    vals = [near if x < grid // 2 else far for _ in range(grid) for x in range(grid)]
    return _field(vals, grid, **over)


def _rle(x0, x1, y0, y1, w=16, h=16):
    from backend.services import mask_geometry as mg

    bits = [0] * (w * h)
    for y in range(y0, y1):
        for x in range(x0, x1):
            bits[y * w + x] = 1
    return mg.rle_encode(bits, w, h)


#: A masked part STRADDLING the near/far split of `_near_left`, and reaching the frame edge.
#:
#: Straddling on purpose: a region wholly inside one half has no relief and no gradient, and a
#: fixture like that would let a broken organ pass by measuring a constant. Reaching the edge on
#: purpose too — `test_every_invocable_organ_still_has_an_invocation` stands all four organs on this
#: one locus, and adjacency has nothing to say about a region that touches nothing.
NEAR_PART = {"id": "r_near", "label": "part", "mask_rle": _rle(4, 16, 4, 12)}

#: The same extent as a BOX ONLY — no mask, so the organ must take the box path.
NEAR_BOX = {"id": "r_near_box", "label": "part",
            "box": {"x": 4 / 16, "y": 4 / 16, "w": 12 / 16, "h": 8 / 16}}

#: Too small: covers fewer than MIN_CELLS on the grid.
SLIVER = {"id": "r_sliver", "mask_rle": _rle(0, 1, 0, 1)}


# ── 1. it measures something real ───────────────────────────────────────────

def test_depth_tracks_the_field_and_larger_is_nearer():
    near = depth.measure(NEAR_PART, _flat(9.0))
    far = depth.measure(NEAR_PART, _flat(1.0))
    assert near["depth_mean"] > far["depth_mean"]
    assert near["depth_mean"] == pytest.approx(9.0)
    assert far["depth_mean"] == pytest.approx(1.0)


def test_relief_separates_a_flat_region_from_a_receding_one():
    """A facade square-on and a wall running away from the camera have the same MEAN and are not
    the same thing to stand in front of — the average alone would erase that."""
    flat = depth.measure(NEAR_PART, _flat(5.0))
    receding = depth.measure(NEAR_PART, _near_left())
    assert flat["relief"] == 0.0
    assert receding["relief"] == pytest.approx(8.0), "near 9.0 against far 1.0 across the region"


def test_the_gradient_says_which_way_depth_runs_and_stays_silent_when_it_does_not():
    """Gated on the spread, because the chroma lane shipped a direction made of float noise between
    equal cell means before the same gate existed there."""
    receding = depth.measure(NEAR_PART, _near_left())["gradient"]
    assert receding["magnitude"] == pytest.approx(8.0)
    assert receding["dx"] < -0.1, "near is on the LEFT, so the near centroid sits left of the far"
    assert abs(receding["dy"]) < 0.1, "the split is vertical: nothing runs up or down"

    flat = depth.measure(NEAR_PART, _flat(5.0))["gradient"]
    assert flat == {**flat, "dx": 0.0, "dy": 0.0, "magnitude": 0.0}
    assert "flat to the camera" in flat["detail"]


def test_frame_rank_says_how_much_of_the_picture_is_behind_this_region():
    """The number a future occlusion relation would stand on — and a property of ONE region read
    against its frame, not a relation to any other region."""
    on_the_near_half = depth.measure(NEAR_PART, _near_left())
    assert on_the_near_half["frame_rank"] == pytest.approx(0.5, abs=0.02)

    # everything at one depth: nothing is behind anything
    assert depth.measure(NEAR_PART, _flat(5.0))["frame_rank"] == 0.0


def test_a_region_too_small_for_the_grid_is_refused_not_averaged():
    """One cell's block mean is the depth of that CELL. Reporting it as the region's depth would be
    measuring the grid, and it would look like a measurement."""
    with pytest.raises(depth.DepthRefusal, match="below"):
        depth.measure(SLIVER, _flat(5.0))


def test_it_reads_no_label_and_no_category():
    a = depth.measure({**NEAR_PART, "label": "sky", "category": "background"}, _near_left())
    b = depth.measure({**NEAR_PART, "label": "finial", "category": "subject"}, _near_left())
    assert a["depth_mean"] == b["depth_mean"] and a["detail"] == b["detail"]


# ── 2. the box argument, in the modality that makes it literal ─────────────

def test_a_mask_reading_is_measured_and_a_box_reading_is_an_estimate():
    masked = depth.measure(NEAR_PART, _near_left())
    boxed = depth.measure(NEAR_BOX, _near_left())
    assert masked["basis"] == "mask" and boxed["basis"] == "box"
    assert depth.grounding_mark(masked, post_id="p")[STATUS_KEY] == EpistemicStatus.MEASURED.value
    assert depth.grounding_mark(boxed, post_id="p")[STATUS_KEY] == \
        EpistemicStatus.INTERPRETIVE.value
    assert depth.is_admissible(masked) and not depth.is_admissible(boxed)


def test_a_box_averages_a_thing_with_the_thing_it_is_in_front_of():
    """THE `cseg_golden_finial_7` FAILURE, reproduced as arithmetic.

    A thin NEAR upright — the finial — against a FAR ground, the sky. Its mask covers only the
    upright and reads the upright's depth. Its bounding box spans the same rows across the frame and
    therefore contains the sky it is in front of, so the box reading lands BETWEEN the two.

    That is not a noisier estimate of the finial's depth. It is the mean of a thing and the thing
    behind it, and it is exactly why a box could never tell `inside` from `in front of`. The mask
    ruling refused the box basis without being able to say this; this organ can say it.
    """
    from backend.services import mask_geometry as mg

    grid = 16
    # A THIN DIAGONAL near spire against a far sky. Diagonal because that is what makes the case
    # real: a bounding box only differs from its mask when the shape is not a rectangle, and every
    # object in this corpus that a box lies about is one that does not fill its own box.
    bits = [0] * (grid * grid)
    vals = [1.0] * (grid * grid)                       # sky: far
    for i in range(grid):
        for x in (grid - 1 - i, max(0, grid - 2 - i)):
            bits[i * grid + x] = 1
            vals[i * grid + x] = 9.0                   # spire: near
    field = _field(vals, grid)

    finial = {"id": "finial", "mask_rle": mg.rle_encode(bits, grid, grid)}
    finial_box = {"id": "finial_box", "box": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}}
    # The sky is the frame MINUS the spire. Masking the whole frame would include the spire in
    # "the sky", which is the very conflation this test exists to take apart.
    sky_bits = [0 if b else 1 for b in bits]
    sky = {"id": "sky", "mask_rle": mg.rle_encode(sky_bits, grid, grid)}

    by_mask = depth.measure(finial, field)["depth_mean"]
    by_box = depth.measure(finial_box, field)["depth_mean"]
    sky_depth = depth.measure(sky, field)["depth_mean"]

    assert by_mask == pytest.approx(9.0), "the mask reads the upright and only the upright"
    assert by_box < by_mask, "the box has been pulled toward the sky behind it"
    assert sky_depth < by_box < by_mask, "the box reading sits BETWEEN the thing and its ground"

    # and the organ says so rather than leaving a reader to notice
    assert "IN FRONT OF" in depth.measure(finial_box, field)["basis_detail"]


def test_the_guard_admits_both_kinds_and_refuses_a_measured_box():
    """The contract on REAL marks — which only works because #158 taught `guard` to find a producer
    named in `provenance`. Before that these marks read as producer None and were refused."""
    field = _near_left()
    for region in (NEAR_PART, NEAR_BOX):
        mark = depth.grounding_mark(depth.measure(region, field), post_id="p")
        assert epistemics.producer_of(mark) == depth.ORGAN
        assert epistemics.guard([mark]) == [mark]

    boxed = depth.grounding_mark(depth.measure(NEAR_BOX, field), post_id="p")
    with pytest.raises(epistemics.EpistemicViolation, match="substrate"):
        epistemics.guard([{**boxed, STATUS_KEY: EpistemicStatus.MEASURED.value}])


def test_the_organ_declares_its_substrates_and_agrees_with_the_model_behind_it():
    """A sense may not claim more than the model it reads. `Capability.DEPTH` carries ceiling
    `measured` in `role_registry`, and this organ's ceiling is checked against it rather than
    against a memory of what it said."""
    from backend.services import role_registry as rr
    from backend.services.vision_orchestrator.contracts import Capability

    assert epistemics.declared_substrates(depth.ORGAN) == ("mask", "box")
    assert epistemics.default_status_for(depth.ORGAN) is EpistemicStatus.MEASURED
    assert rr._CAPABILITY_CEILINGS[Capability.DEPTH] is EpistemicStatus.MEASURED
    model_role = rr.get(depth.SOURCE_ADAPTER)
    assert model_role is not None and model_role.epistemic_ceiling is EpistemicStatus.MEASURED
    epistemics.assert_substrate_tables_agree()


def test_the_four_organs_read_one_ruling():
    from backend.services import adjacency_organ as adj, chroma_organ as chroma

    for basis in ("mask", "box"):
        assert depth.epistemic_for(basis) == nest.epistemic_for(basis) == \
            adj.epistemic_for(basis) == chroma.epistemic_for(basis) == \
            epistemics.substrate_ceiling(basis).value


# ── 3. provenance is required, because a fixture is a list of floats ──────

def test_a_field_that_names_no_model_is_refused():
    with pytest.raises(depth.DepthRefusal, match="provenance"):
        depth.measure(NEAR_PART, _flat(5.0, model="", revision=""))


def test_a_field_from_another_model_is_refused():
    with pytest.raises(depth.DepthRefusal, match="another model"):
        depth.measure(NEAR_PART, _flat(5.0, adapter="midas_small"))


def test_a_cropped_field_is_refused_because_it_looks_exactly_like_a_frame_field():
    """Monocular depth is a GLOBAL inference: on a crop it gives depth relative to the crop, which
    says nothing about occlusion order — and it is the same shape and the same dtype."""
    with pytest.raises(depth.DepthRefusal, match="whole frame"):
        depth.measure(NEAR_PART, _flat(5.0, whole_frame=False))


def test_a_malformed_field_is_refused_rather_than_indexed():
    with pytest.raises(depth.DepthRefusal, match="malformed"):
        depth.measure(NEAR_PART, _field([1.0, 2.0, 3.0], GRID))
    with pytest.raises(depth.DepthRefusal, match="no depth field"):
        depth.measure(NEAR_PART, None)


def test_the_mark_names_both_producers_behind_the_number():
    """Two things stand behind this measurement — the model that inferred the depth and the organ
    that read a region out of it. A mark naming only one would leave the weighted half anonymous."""
    mark = depth.grounding_mark(depth.measure(NEAR_PART, _near_left()), post_id="p")
    prov = mark["provenance"]
    assert prov["producer"] == depth.ORGAN
    assert prov["adapter"] == depth.SOURCE_ADAPTER
    assert prov["model"] == MODEL and prov["revision"] == REVISION
    assert mark[epistemics.SUBSTRATE_KEY] == "mask"


# ── 4. the model and the sense are different things ───────────────────────

def test_the_sense_is_invocable_and_the_model_is_still_resident():
    """THE CARD SAID this organ should go through the roster path instead of `PURE_PYTHON_ORGANS`.
    The roster entry already existed — `depth_anything_v2_small` has been an `AdapterSpec` with
    `Capability.DEPTH` since VISION-MODEL-MATRIX-001, with a generated organ role and a working
    `DepthAdapter`. What did not exist is a SENSE an agent can perceive through.

    They are different objects and this test is the difference: the model resolves RESIDENT, which
    is correct and unchanged — this lane still may not start it — while the sense resolves RESOLVED
    because there is nothing to start.
    """
    model = organs.resolve(depth.SOURCE_ADAPTER)
    assert model.resolution == organs.RESIDENT and not model.invocable
    assert model.role is not None and model.role.capability == "depth"

    sense = organs.resolve(depth.ORGAN)
    assert sense.resolution == organs.RESOLVED and sense.invocable
    assert depth.ORGAN in organs.PURE_PYTHON_ORGANS
    assert depth.ORGAN in organs._NEEDS_DEPTH


def test_an_agent_bound_to_depth_with_no_field_perceives_nothing_and_says_so():
    post = _post()
    agent = sa.inhabit(agent_id="d", post_id="pd", region_id="r_near", organ_set=(depth.ORGAN,))
    with pytest.raises(organs.OrganRefusal, match="none was handed"):
        sa.perceive(agent, post, now=STAMP)
    assert agent.percept_field == []


def _post(post_id="pd"):
    return {"_id": post_id, "region_annotations": [
        dict(NEAR_PART, id="r_near"),
        {"id": "r_whole", "label": "whole", "mask_rle": _rle(0, 16, 0, 16)},
    ]}


def test_an_agent_perceives_a_depth_field_and_narrates_it_in_its_own_words():
    """The `_percept_for` fix from the chroma lane: the organ writes its own sentence. A depth
    reading composed from a relation vocabulary would be false by construction."""
    post = _post()
    agent = sa.inhabit(agent_id="d", post_id="pd", region_id="r_near", organ_set=(depth.ORGAN,))
    sa.perceive(agent, post, now=STAMP, depth_field=_near_left())

    assert len(agent.percept_field) == 1
    perception = agent.percept_field[0]
    assert perception.reading.direction == "field"
    assert perception.reading.other_region_id == ""
    assert len(perception.grounds) == 1
    said = perception.percept.model_dump(mode="json")["expression"]
    assert re.match(r"^r_near sits at depth [\d.]+ with \d+% of the frame behind it$", said), said


def test_a_depth_agent_and_a_geometry_agent_enact_different_worlds():
    post = _post()
    geo = sa.inhabit(agent_id="geo", post_id="pd", region_id="r_near", organ_set=(nest.ORGAN,))
    dep = sa.inhabit(agent_id="dep", post_id="pd", region_id="r_near", organ_set=(depth.ORGAN,))
    sa.perceive(geo, post, now=STAMP)
    sa.perceive(dep, post, now=STAMP, depth_field=_near_left())

    assert geo.percept_field and dep.percept_field
    assert not ({p.reading.relation for p in geo.percept_field} &
                {p.reading.relation for p in dep.percept_field})
    geo_keys = set(geo.percept_field[0].reading.measurement)
    dep_keys = set(dep.percept_field[0].reading.measurement)
    assert geo_keys & dep_keys == {"organ", "organ_version", "basis", "basis_detail",
                                   "detail", "thresholds"}, sorted(geo_keys & dep_keys)
    assert all(p.reading.other_region_id for p in geo.percept_field)
    assert all(p.reading.other_region_id == "" for p in dep.percept_field)


def test_the_agent_reports_a_depth_field_as_proposed():
    from backend.services.agents import observation as obs_mod

    post = _post()
    agent = sa.inhabit(agent_id="d", post_id="pd", region_id="r_near", organ_set=(depth.ORGAN,))
    sa.perceive(agent, post, now=STAMP, depth_field=_near_left())
    rows = sa.report(agent, now=STAMP)
    assert rows and all(STATUS_KEY not in row for row in rows)
    assert obs_mod.hydrate_observation(rows[0], {"pd": post})["ledger_status"] == \
        obs_mod.LEDGER_PROPOSED


def test_the_private_memory_carries_the_organs_own_headline_number():
    post = _post()
    agent = sa.inhabit(agent_id="d", post_id="pd", region_id="r_near", organ_set=(depth.ORGAN,))
    sa.perceive(agent, post, now=STAMP, depth_field=_near_left())
    entry = sa.remember(agent, now=STAMP)[0]
    assert "depth_mean" in entry and "nesting_index" not in entry
    assert entry[STATUS_KEY] == EpistemicStatus.MEASURED.value


# ── 5. no relation, and no hidden comparable number ───────────────────────

def test_this_lane_mints_no_relation():
    """`in_front_of` is what this measurement exists to ground and it is deliberately absent: it
    needs the systematicity gate the floor lane is reworking, and a relation minted here would
    arrive before the gate that judges it."""
    mark = depth.grounding_mark(depth.measure(NEAR_PART, _near_left()), post_id="p")
    assert mark["type"] == "field_mark" and mark["role"] == depth.FIELD_DEPTH

    # Read off the module's API rather than its text: the docstring NAMES `in_front_of` in order
    # to say it is absent, and a scan that punished the explanation would push the next lane into
    # deleting the sentence instead of the code.
    exported = [n for n in dir(depth) if not n.startswith("_")]
    assert not [n for n in exported if n.startswith("RELATION")], exported
    assert not [n for n in exported if "front" in n.lower() or "occlu" in n.lower()], exported
    assert "relation_mark" not in repr(mark)


def test_comparing_two_senses_on_one_scale_is_refused():
    post = _post()
    geometry = nest.measure(post["region_annotations"][0], post["region_annotations"][1])
    with pytest.raises(depth.Incommensurable, match="no common scale"):
        depth.compare_across_senses(geometry, depth.measure(NEAR_PART, _near_left()))


def test_the_organ_invents_no_shared_magnitude():
    measurement = depth.measure(NEAR_PART, _near_left())
    for forbidden in ("score", "strength", "salience", "weight", "combined", "confidence"):
        assert not [k for k in measurement if forbidden in k], (forbidden, sorted(measurement))


def test_depth_is_not_reported_in_metres():
    """Depth-Anything gives RELATIVE inverse depth. A field called `distance_m` would be units
    arriving from nowhere, and they would be believed."""
    measurement = depth.measure(NEAR_PART, _near_left())
    assert not [k for k in measurement if "metre" in k or "meter" in k or k.endswith("_m")]
    assert "inverse" in measurement["detail"]


# ── 6. purity and the substrate-declaration scan ─────────────────────────

#: torch and transformers are the point: the MODEL is residency-managed elsewhere, and an organ that
#: imported it would make every agent's perception a GPU load.
_IMPURE = re.compile(
    r"\b(database|requests|httpx|aiohttp|torch|transformers|motor|PIL|cv2|numpy|"
    r"depth_service|llm_service|groq|openai|anthropic|vision_service)\b")


def test_the_depth_organ_is_pure():
    source = Path(depth.__file__).read_text()
    for lineno, line in enumerate(source.splitlines(), 1):
        if not (line.startswith("import ") or line.startswith("from ")):
            continue
        hit = _IMPURE.search(line)
        assert hit is None, f"depth_organ.py:{lineno} imports {hit.group(0)!r} — not pure"


def test_this_test_file_loads_no_model():
    source = Path(__file__).read_text()
    assert not re.search(r"^\s*(import|from)\s+(torch|transformers|PIL)\b", source, re.M)


def test_the_organ_appears_in_the_substrate_declaration_scan():
    services = Path(depth.__file__).resolve().parent
    adopters = set()
    for path in sorted(services.glob("*.py")):
        text = path.read_text()
        if "substrate_ceiling" not in text and "def epistemic_for" not in text:
            continue
        found = re.search(r'^ORGAN\s*=\s*"([^"]+)"', text, re.M)
        if found:
            adopters.add(found.group(1))
    assert depth.ORGAN in adopters
    assert not adopters - set(epistemics._SUBSTRATES)


def test_every_invocable_organ_still_has_an_invocation():
    """The two tables in `organs.py` must keep covering each other as the sensorium grows."""
    post = _post()
    from backend.tests.test_agent_dialogue_wave3 import _FlatImage

    for name in organs.PURE_PYTHON_ORGANS:
        kwargs = {}
        if name in organs._NEEDS_PIXELS:
            kwargs["image"] = chroma_organ.image_frame(_FlatImage(), source="fixture:flat")
        if name in organs._NEEDS_DEPTH:
            kwargs["depth_field"] = _near_left()
        readings = organs.invoke(name, post=post, region_id="r_near", now=STAMP, **kwargs)
        assert readings, f"{name} is invocable but measured nothing at a locus that affords all"
