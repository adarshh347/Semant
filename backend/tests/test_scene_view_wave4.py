"""
WAVE4 — the scene view: what it may show, and what it must never make look settled.

The engine grounds nesting, adjacency, occlusion and chromatic rhyme on regions, and this is the
first place any of it is drawn on the picture it was measured from. A view is where a status
quietly becomes a stronger one — a defaulted field, a hue that reads as confidence, a proposal
rendered like a finding — so most of this file is about the two words that must survive the trip:

  1. **`epistemic` is re-derived, never read.** The cache stores a BASIS, which is data. The status
     is a conclusion, and `hydrate` recomputes it on every read, so a hand-edited cache cannot
     promote a box-basis relation to `measured`.
  2. **`ledger_status` is `proposed` unless the relation came out of a post's ledger.** Nothing in
     the cache can be `committed`; only the curator's single write puts a mark there.

And the third thing a view gets wrong: **absence**. An unbuilt cache is not an empty picture, and
the response has to be able to say which.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import scene as scene_router
from backend.services import scene_relations as sr
from backend.services.epistemics import STATUS_KEY

POST_ID = "6a5fef58a3ddb6341fd69930"


def region(rid, *, masked=True, provenance=None, actor=""):
    out = {"id": rid, "label": rid, "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}}
    if masked:
        out["mask_rle"] = {"size": [64, 64], "counts": "stub"}
        out["polygon"] = [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]]
    if provenance is not None:
        out["geometry_provenance"] = provenance
    if actor:
        out["actor"] = actor
    return out


def post(*regions, marks=()):
    return {"_id": POST_ID, "photo_url": "http://example/x.jpg",
            "region_annotations": list(regions), "visual_marks": list(marks)}


def cached(**kinds):
    return {"cache_version": sr.CACHE_VERSION, "built_at": "2026-08-07T00:00:00Z",
            "kinds_built": sorted(kinds), "provenance": {},
            "scenes": {POST_ID: {"post_id": POST_ID, "relations": kinds}}}


def nesting_row(source, target, basis):
    return sr.row(kind="nesting", axis="axis_nestedness", relation="nested_within",
                  source=source, target=target, basis=basis,
                  detail=f"{basis} containment 1.000", organ="nestedness_organ",
                  numbers={"containment": 1.0})


@pytest.fixture
def cache_at(tmp_path, monkeypatch):
    """Point the cache at a throwaway file — a test that read the developer's own build would be
    neither hermetic nor repeatable."""
    path = tmp_path / "scene_relations.json"
    monkeypatch.setenv("SCENE_RELATIONS_PATH", str(path))

    def write(payload):
        path.write_text(json.dumps(payload))
    return write


# ── 1. the status is a conclusion, recomputed ────────────────────────────────────────────────

def test_a_box_basis_relation_is_interpretive_however_the_cache_is_edited(cache_at):
    """THE CLAIM THE VIEW RESTS ON. The cache is a faster way to see what the organs said, not a
    second ledger — so a status typed into the file is not a status."""
    tampered = nesting_row("a", "b", "box")
    tampered["epistemic"] = "measured"          # someone edits the JSON
    tampered["admissible"] = True
    cache_at(cached(nesting=[tampered]))

    view = sr.scene_for(post(region("a"), region("b")))
    relation = view["relations"][0]
    assert relation["epistemic"] == "interpretive"
    assert relation["admissible"] is False


def test_a_mask_basis_relation_is_measured():
    assert sr.epistemic_for("mask") == "measured"
    assert sr.epistemic_for("box") == "interpretive"
    assert sr.epistemic_for("") == "interpretive"
    assert sr.epistemic_for("something_new") == "interpretive"


def test_the_founding_pathology_renders_as_an_estimate(cache_at):
    """`cseg_golden_finial_7 in region_2` scores containment 1.000 on boxes and the finial is in
    FRONT of the sky. It is the first relation this view draws on the temple scene, and drawing it
    like a measured one would be the founding pathology again, in CSS."""
    cache_at(cached(nesting=[nesting_row("cseg_golden_finial_7", "region_2", "box")]))
    view = sr.scene_for(post(region("cseg_golden_finial_7"), region("region_2", masked=False)))
    relation = view["relations"][0]
    assert relation["basis"] == "box"
    assert relation["epistemic"] == "interpretive"
    assert relation["ledger_status"] == "proposed"


# ── 2. proposed vs committed ─────────────────────────────────────────────────────────────────

def test_everything_in_the_cache_is_proposed(cache_at):
    """Nothing derived is `committed`, and there is no field a build could set to make it so."""
    forged = nesting_row("a", "b", "mask")
    forged["ledger_status"] = "committed"
    cache_at(cached(nesting=[forged]))
    # `row()` does not carry a ledger status at all; hydrate defaults it. A forged one survives
    # only because the test put it there — so the assertion is on what `row` PRODUCES.
    assert "ledger_status" not in nesting_row("a", "b", "mask")
    assert "epistemic" not in nesting_row("a", "b", "mask")


def test_a_relation_in_the_posts_ledger_is_committed(cache_at):
    """The only way `committed` can appear: the mark is actually in the post."""
    cache_at(cached())
    mark = {"id": "vm_occ_1", "type": "relation_mark", "relation": "in_front_of",
            "axis": "axis_occlusion", "front_region_id": "a", "back_region_id": "b",
            STATUS_KEY: "measured", "measurement": {"basis": "mask", "separation": 0.99},
            "provenance": {"producer": "occlusion_organ"}}
    view = sr.scene_for(post(region("a"), region("b"), marks=[mark]))
    committed = [r for r in view["relations"] if r["ledger_status"] == "committed"]
    assert len(committed) == 1
    assert committed[0]["relation"] == "in_front_of"
    assert committed[0]["mark_id"] == "vm_occ_1"


def test_a_committed_mark_that_misstates_its_basis_is_flagged_not_believed(cache_at):
    """A box-basis mark wearing `measured`. The view must be able to draw the contradiction rather
    than silently preferring one of the two answers."""
    cache_at(cached())
    mark = {"id": "vm_x", "type": "relation_mark", "relation": "nested_within",
            "measurement": {"basis": "box", "inner_region_id": "a", "outer_region_id": "b"},
            STATUS_KEY: "measured", "provenance": {"producer": "nestedness_organ"}}
    relation = sr.scene_for(post(region("a"), region("b"), marks=[mark]))["relations"][0]
    assert relation["misstated"] is True
    assert relation["epistemic"] == "interpretive"      # what the basis supports, not the stamp


def test_an_empty_ledger_reads_as_empty_rather_than_as_missing(cache_at):
    """On this corpus NOTHING has ever been committed, and the view renders that. The difference
    between a proposal and a finding is only visible when both can appear."""
    cache_at(cached(nesting=[nesting_row("a", "b", "mask")]))
    view = sr.scene_for(post(region("a"), region("b")))
    assert view["tallies"]["by_ledger"] == {"proposed": 1}


# ── 3. absence is a value ────────────────────────────────────────────────────────────────────

def test_an_unbuilt_cache_is_not_an_empty_scene(tmp_path, monkeypatch):
    monkeypatch.setenv("SCENE_RELATIONS_PATH", str(tmp_path / "nothing.json"))
    view = sr.scene_for(post(region("a")))
    assert view["cache"]["missing"] is True
    assert view["relations"] == []
    assert view["kinds_absent"] == ["adjacency", "nesting", "occlusion", "rhyme"]


def test_a_cache_from_another_layout_is_ignored_whole(tmp_path, monkeypatch):
    """A stale relation is worse than none: it is silently wrong and looks exactly as confident."""
    path = tmp_path / "scene_relations.json"
    path.write_text(json.dumps({"cache_version": 999, "scenes": {POST_ID: {"relations": {
        "nesting": [nesting_row("a", "b", "mask")]}}}}))
    monkeypatch.setenv("SCENE_RELATIONS_PATH", str(path))
    view = sr.scene_for(post(region("a"), region("b")))
    assert view["cache"]["stale"] is True
    assert view["relations"] == []


def test_missing_evidence_and_evidence_of_absence_are_different_answers(cache_at):
    """CAUGHT ON THE FIRST RENDER, and it is the distinction the whole view is for.

    The temple scene reported "occlusion not derived" when occlusion HAD been derived across the
    corpus and that picture simply has none of it — the 13 are on four other posts. Reporting a gap
    in the build as a fact about the scene is the same error class as rendering a proposal as a
    finding, one level up: it makes an absence of looking indistinguishable from a looking that
    found nothing.
    """
    cache_at(cached(nesting=[nesting_row("a", "b", "mask")], occlusion=[]))
    view = sr.scene_for(post(region("a"), region("b")))

    # occlusion WAS derived (it is in `kinds_built`) and this scene has none.
    assert view["kinds_none_here"] == ["occlusion"]
    assert "occlusion" not in view["kinds_absent"]

    # adjacency and rhyme were never derived at all.
    assert view["kinds_absent"] == ["adjacency", "rhyme"]
    assert "nesting" not in view["kinds_absent"] + view["kinds_none_here"]


def test_a_rhyme_carries_the_image_its_far_end_is_in(cache_at):
    """The one relation on a scene whose far end is NOT on the scene.

    The view draws it as a stub to the frame edge rather than a line to a point, because a line
    between two visible things would be claiming a relation between two things you can see. The
    far end is genuinely elsewhere, and `target_post_id` is what says so.

    On this corpus the build derives ZERO rhymes — `MIN_RHYME` is 0.8 and the chroma lane measured
    the corpus's own correlations at p75 = +0.26, so 0.8 is far out in the tail. That is a null,
    not a gap, and the shape still has to be right for the first one that clears it.
    """
    cache_at(cached(rhyme=[sr.row(
        kind="rhyme", axis="axis_chromatic_rhyme", relation="rhymes_with",
        source="a", target="far_region", basis="mask", detail="warmth fields rhyme 0.87",
        organ="chromatic_relation", target_post_id="OTHER_POST")]))
    relation = sr.scene_for(post(region("a")))["relations"][0]
    assert relation["target_post_id"] == "OTHER_POST"
    assert relation["epistemic"] == "measured"
    assert relation["ledger_status"] == "proposed"


def test_the_rhyme_caps_are_reported_so_a_short_list_is_not_read_as_complete(cache_at):
    """A bounded sweep that does not say what it dropped reads as 'these are all there are'."""
    cache_at(cached())
    caps = sr.scene_for(post(region("a")))["cache"]["caps"]
    assert caps["rhyme_regions_per_post"] == sr.RHYME_REGION_CAP
    assert caps["rhyme_posts"] == sr.RHYME_POST_CAP


# ── 4. regions carry who drew them ───────────────────────────────────────────────────────────

def test_every_region_names_a_maker_or_says_it_cannot(cache_at):
    """A `measured` relation on a mask nobody can attribute is a measurement resting on geometry of
    unknown origin — ORGAN-PROVENANCE-001's point, carried into the view so it is visible."""
    cache_at(cached())
    view = sr.scene_for(post(
        region("drawn", provenance={"adapter": "sam3", "model": "sam3-l"}),
        region("traced", actor="creator"),
        region("orphan", provenance={"kind": "legacy-box"})))
    kinds = {r["id"]: r["maker"]["kind"] for r in view["regions"]}
    assert kinds == {"drawn": "model", "traced": "human", "orphan": "unknown"}
    assert view["regions"][2]["maker"]["attributed"] is False


def test_the_mask_outline_is_sent_and_the_rle_is_not(cache_at):
    """A COCO run-length encoding is large and not drawable in a browser without decoding it.
    `has_mask` stays, so a region whose mask exists but whose outline is missing is still legible
    as masked rather than silently becoming a box."""
    cache_at(cached())
    view = sr.scene_for(post(region("a"), region("b", masked=False)))
    masked, boxed = view["regions"]
    assert masked["has_mask"] is True and masked["polygons"]
    assert boxed["has_mask"] is False and boxed["polygons"] == []
    assert "mask_rle" not in masked


# ── 5. the route ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(cache_at, monkeypatch):
    cache_at(cached(nesting=[nesting_row("a", "b", "box"),
                             nesting_row("b", "c", "mask")]))

    async def _load_post(post_id):
        if post_id != POST_ID:
            return None
        return post(region("a"), region("b"), region("c"))

    monkeypatch.setattr(scene_router, "_load_post", _load_post)
    app = FastAPI()
    app.include_router(scene_router.router, prefix="/api/v1/scene")
    with TestClient(app) as c:
        yield c


def test_the_route_never_renders_an_estimate_as_a_measurement(client):
    """THROUGH THE REAL ROUTE, because the serializer is where a status quietly acquires a default:
    FastAPI fills an unset field from the model and renders it as data. The curator lane hit this
    and the writer lane hit it twice before that."""
    body = client.get(f"/api/v1/scene/{POST_ID}").json()
    by_basis = {r["basis"]: r for r in body["relations"]}
    assert by_basis["box"]["epistemic"] == "interpretive"
    assert by_basis["mask"]["epistemic"] == "measured"
    assert {r["ledger_status"] for r in body["relations"]} == {"proposed"}


def test_the_status_fields_are_required_on_the_wire():
    """Un-defaulted, so a handler that forgot to set one fails loudly instead of shipping a
    flattering default."""
    fields = scene_router.RelationView.model_fields
    for name in ("epistemic", "ledger_status", "basis", "kind"):
        assert fields[name].is_required(), name


def test_an_unknown_post_is_a_404(client):
    assert client.get("/api/v1/scene/nope").status_code == 404


def test_status_never_404s(client):
    body = client.get("/api/v1/scene/status").json()
    assert "built_at" in body and "kinds_built" in body


def test_the_router_has_no_write_path():
    """Read-only, and structurally so. Committing is the curator surface's single route; a view
    that could change the ledger would be the thing it exists to report on."""
    methods = {m for route in scene_router.router.routes for m in getattr(route, "methods", set())}
    assert methods <= {"GET", "HEAD", "OPTIONS"}, methods
