"""
WAVE3 relational retrieval — ordering candidates by relation rather than by resemblance.

The measured claim this lane makes is a corpus fact and lives in
`scripts/relational_retrieval_proof.py`: at the kernel's default k=12, across five masked seeds,
`grounded` went 13 → 32 and `surface_only` 25 → 11 with nothing changed but the question the
retina was asked. What belongs in the suite is not that number but everything that decides it, and
above all the LIMITS — because the failure mode of a re-ranker is not being wrong, it is being
right for reasons that quietly turn it into the thing it is supposed to be feeding.

  1. **the skeleton** — box-basis containment, the tightest parent, and the counts the prior ranks
     on. The arithmetic that decides whether a candidate looks relationally plausible at all.
  2. **the prior is an estimate** — box basis, `kind: "prior"`, no epistemic status, no verdict.
     It may disagree with the organ, and a test constructs a case where it does: two boxes that
     overlap while the masks inside them do not touch. That is the finial-in-front-of-the-sky
     pathology, and the whole point is that the proposer is allowed to fall for it and the kernel
     is not.
  3. **re-rank reorders, never filters** — every candidate handed in comes back out. Narrowing is
     the caller's `k`, and what `k` cut is reported rather than silently absent.
  4. **the proposer changed, the decider did not** — `propose` picks a ranking; nothing downstream
     of it reads one. A test asserts the kernel grounds and refuses identically whichever ranking
     supplied the same candidates.
"""
import ast
import asyncio
import copy
import pathlib

import numpy as np
import pytest

from backend.services import mask_geometry as mg
from backend.services import movement_kernel as mk
from backend.services import nestedness_organ as organ
from backend.services.retina import geometry as geo
from backend.services.retina import relational as rel

RASTER = 100


def _box(x, y, w, h):
    return {"x": x, "y": y, "w": w, "h": h}


def _rle(x, y, w, h):
    bits = np.zeros((RASTER, RASTER), np.uint8)
    bits[int(round(y * RASTER)):int(round((y + h) * RASTER)),
         int(round(x * RASTER)):int(round((x + w) * RASTER))] = 1
    return mg.rle_encode_mask(bits)


def _masked(rid, box, label=""):
    return {"id": rid, "box": _box(*box), "label": label or rid, "mask_rle": _rle(*box)}


def _boxed(rid, box, label=""):
    """A VLM estimate: real data, a legitimate candidate, inadmissible as a grounding."""
    return {"id": rid, "box": _box(*box), "label": label or rid}


def _post(pid, regions):
    return {"_id": pid, "region_annotations": list(regions), "visual_marks": []}


#: A frame holding a whole holding a part, with one sibling — the corpus's commonest shape.
POST_A = _post("post_a", [
    _masked("a_frame", (0.05, 0.05, 0.90, 0.90)),
    _masked("a_whole", (0.20, 0.20, 0.50, 0.50)),
    _masked("a_part", (0.30, 0.30, 0.10, 0.10)),
    _masked("a_sibling", (0.50, 0.50, 0.10, 0.10)),
])

#: The same shape in another image, entirely unalike in appearance — what should be proposed.
POST_B = _post("post_b", [
    _masked("b_frame", (0.02, 0.02, 0.96, 0.96)),
    _masked("b_whole", (0.10, 0.10, 0.60, 0.60)),
    _masked("b_part", (0.20, 0.20, 0.12, 0.12)),
    _masked("b_sibling", (0.40, 0.40, 0.12, 0.12)),
])

#: Nothing inside anything: two regions side by side. The `surface_only` refusal, as geometry.
POST_FLAT = _post("post_flat", [
    _masked("f_left", (0.05, 0.40, 0.20, 0.20)),
    _masked("f_right", (0.70, 0.40, 0.20, 0.20)),
])

POSTS = {p["_id"]: p for p in (POST_A, POST_B, POST_FLAT)}


def geometry_of(*posts):
    return {p["_id"]: geo.post_geometry(p) for p in posts}


def _cand(post_id, region_id, score):
    return {"post_id": post_id, "region_id": region_id, "score": score, "kind": "candidate"}


# ── 1. the skeleton ──────────────────────────────────────────────────────────────────────────

def test_the_skeleton_finds_the_tightest_container_not_the_frame():
    """The immediate parent is the smallest thing that holds it. Ranking on the frame would make
    every region in the image look identically nested."""
    skel = rel.skeletons(geo.post_geometry(POST_A))["a_part"]
    assert skel["parent_id"] == "a_whole"
    assert skel["depth"] == 2                      # a_whole and a_frame both contain it
    assert skel["sibling_count"] == 1              # a_sibling shares a_whole
    assert skel["descendant_count"] == 0


def test_a_region_inside_nothing_has_no_relation():
    skel = rel.skeletons(geo.post_geometry(POST_FLAT))["f_left"]
    assert skel["has_relation"] is False
    assert skel["parent_id"] == "" and skel["depth"] == 0


def test_a_region_too_large_for_its_container_is_not_nested_in_it():
    """`MAX_SCALE_RATIO` — a part filling its container is not a part of it, it IS it. Without
    this the frame's only child would be a near-copy of the frame."""
    post = _post("p", [_masked("outer", (0.1, 0.1, 0.8, 0.8)),
                       _masked("inner", (0.1, 0.1, 0.79, 0.79))])
    assert rel.skeletons(geo.post_geometry(post))["inner"]["has_relation"] is False


def test_a_partially_overlapping_region_is_not_contained():
    post = _post("p", [_masked("outer", (0.1, 0.1, 0.4, 0.4)),
                       _masked("inner", (0.4, 0.4, 0.2, 0.2))])
    assert rel.skeletons(geo.post_geometry(post))["inner"]["has_relation"] is False


def test_the_extent_of_a_masked_region_is_its_masks_bbox_not_its_stored_box():
    """`canonicalize_geometry` treats the mask as authoritative and the box as a convenience. A
    prior read off a stale box would rank on geometry the kernel will not measure."""
    region = {"id": "r", "box": _box(0.0, 0.0, 1.0, 1.0), "mask_rle": _rle(0.25, 0.25, 0.5, 0.5)}
    extent = geo.region_extent(region)
    assert extent["w"] == pytest.approx(0.5, abs=0.02)
    assert extent["x"] == pytest.approx(0.25, abs=0.02)


def test_a_region_with_no_usable_geometry_is_absent_rather_than_full_frame():
    """Defaulting an unlocatable region to a full-frame box would make it appear to contain
    everything in the image — an absence turned into the strongest possible claim."""
    assert geo.region_extent({"id": "r"}) is None
    assert "r" not in geo.post_geometry(_post("p", [{"id": "r"}]))


# ── 2. the prior is an estimate, and says so ─────────────────────────────────────────────────

def test_every_prior_is_stamped_as_a_box_basis_guess():
    skels = rel.skeletons(geo.post_geometry(POST_A))
    prior = rel.relational_prior(skels["a_part"], skels["a_sibling"], identity_score=0.5)
    assert prior["kind"] == rel.PRIOR_KIND == "prior"
    assert prior["basis"] == rel.PRIOR_BASIS == "box"
    assert "epistemic_status" not in prior
    assert "measured" not in prior["note"].lower() or "only a mask" in prior["note"]


def test_the_prior_carries_no_verdict_and_no_relation():
    """THE CLAIM THAT KEEPS THIS A PROPOSER. A prior has a score and its terms. It has no
    `nested`, no `status`, no `mark` — nothing a caller could mistake for a finding."""
    skels = rel.skeletons(geo.post_geometry(POST_A))
    prior = rel.relational_prior(skels["a_part"], skels["a_whole"])
    for forbidden in ("nested", "status", "mark", "relation", "epistemic", "grounded"):
        assert forbidden not in prior


def test_the_box_prior_can_be_wrong_where_the_organ_is_right():
    """The pathology the WAVE2.5 ruling exists for, reproduced as a unit.

    Two masks that do not touch, inside two boxes that nest perfectly. The box prior says "stands
    in a relation" and the organ, reading the masks, says the containment is 0. The proposer is
    ALLOWED to fall for this — that is what makes it cheap — and the kernel is not, which is what
    makes it the decider. If this test ever fails because the prior got smarter, the disagreement
    rate the proof script reports has stopped meaning anything.
    """
    outer = {"id": "outer", "box": _box(0.1, 0.1, 0.8, 0.8), "mask_rle": _rle(0.1, 0.1, 0.3, 0.3)}
    inner = {"id": "inner", "box": _box(0.5, 0.5, 0.2, 0.2), "mask_rle": _rle(0.5, 0.5, 0.2, 0.2)}

    # The prior reads BOXES — from the stored box, since these masks sit elsewhere in the frame.
    boxes = {"outer": {"box": _box(0.1, 0.1, 0.8, 0.8), "has_mask": True},
             "inner": {"box": _box(0.5, 0.5, 0.2, 0.2), "has_mask": True}}
    assert rel.skeletons(boxes)["inner"]["parent_id"] == "outer"

    # The organ reads MASKS, on a shared raster, and finds no containment at all.
    measurement = organ.measure(inner, outer)
    assert measurement["basis"] == "mask"
    assert measurement["nested"] is False


def test_shape_affinity_sees_no_vector_no_label_and_no_score():
    """Stated as a signature, the same guarantee `systematicity` makes: two skeletons in, a number
    out. There is nothing here for appearance to leak through."""
    skels_a, skels_b = rel.skeletons(geo.post_geometry(POST_A)), rel.skeletons(
        geo.post_geometry(POST_B))
    assert rel.shape_affinity(skels_a["a_part"], skels_b["b_part"])["score"] == 1.0
    with pytest.raises(TypeError):
        rel.shape_affinity(skels_a["a_part"], skels_b["b_part"], 0.9)


def test_a_candidate_with_no_cached_geometry_scores_on_identity_and_says_so():
    """The retina not knowing where something sits is a fact about the retina. Dropping it would
    turn a gap in the cache into evidence about the region."""
    skels = rel.skeletons(geo.post_geometry(POST_A))
    prior = rel.relational_prior(skels["a_part"], None, identity_score=0.8)
    assert prior["geometry_known"] is False
    assert prior["terms"]["stands_in_relation"] == 0.0
    assert prior["terms"]["identity"] == 0.8


def test_stands_in_relation_outweighs_every_other_term_combined():
    """The guard the ablation shows is currently unexercised — `− stands_in_relation` costs
    nothing on the corpus. It is kept because `_alignment` scores 0-vs-0 as perfect agreement, so
    a seed with no descendants hands every relation-less candidate a free third of the affinity
    term. At 0.50 the guard holds regardless of which seed shape turns up."""
    w = rel.DEFAULT_WEIGHTS
    assert w["stands_in_relation"] >= sum(v for k, v in w.items() if k != "stands_in_relation")


# ── 3. re-rank reorders, never filters ───────────────────────────────────────────────────────

def _rerank(cands):
    skels = rel.skeletons(geo.post_geometry(POST_A))
    return rel.rerank(cands, seed_skeleton=skels["a_part"],
                      geometry=geometry_of(POST_A, POST_B, POST_FLAT))


def test_rerank_returns_every_candidate_it_was_given():
    """Narrowing is the caller's `k`. A retina that dropped candidates would be deciding, and the
    thing it would be deciding is exactly what the kernel exists to decide."""
    cands = [_cand("post_flat", "f_left", 0.99), _cand("post_b", "b_part", 0.10)]
    out = _rerank(cands)
    assert len(out) == 2
    assert {(c["post_id"], c["region_id"]) for c in out} == {("post_flat", "f_left"),
                                                            ("post_b", "b_part")}


def test_a_relationally_plausible_candidate_outranks_a_closer_look_alike():
    """The lane, in one assertion. `f_left` is a near-perfect appearance match and stands inside
    nothing; `b_part` is a poor one and sits in the same shape of nesting as the seed."""
    out = _rerank([_cand("post_flat", "f_left", 0.99), _cand("post_b", "b_part", 0.10)])
    assert out[0]["region_id"] == "b_part"
    assert out[0]["identity_rank"] == 2 and out[0]["relational_rank"] == 1


def test_every_candidate_carries_where_it_came_from():
    """The move has to be auditable, not merely different — `identity_rank` is what makes a
    re-ranking inspectable after the fact."""
    out = _rerank([_cand("post_flat", "f_left", 0.99), _cand("post_b", "b_part", 0.10)])
    assert [c["identity_rank"] for c in out] == [2, 1]
    assert all("relational" in c and "terms" in c["relational"] for c in out)


def test_ties_keep_the_order_they_arrived_in():
    """A stable, stated fallback beats whatever order the vector store happened to return."""
    out = _rerank([_cand("post_b", "b_part", 0.5), _cand("post_b", "b_sibling", 0.5)])
    scores = [c["relational"]["score"] for c in out]
    if scores[0] == scores[1]:
        assert [c["identity_rank"] for c in out] == [1, 2]


def test_reranking_with_no_geometry_at_all_is_a_no_op_not_a_reordering():
    """An empty cache must not silently produce a confident-looking new order."""
    cands = [_cand("post_b", "b_part", 0.9), _cand("post_flat", "f_left", 0.8)]
    out = rel.rerank(cands, seed_skeleton=rel.skeletons(geo.post_geometry(POST_A))["a_part"],
                     geometry={})
    assert [c["identity_rank"] for c in out] == [1, 2]


# ── 4. the proposer changed; the decider did not ─────────────────────────────────────────────

class FakeRetina:
    """A retina with only the identity route — a build that predates relational retrieval."""

    def __init__(self, candidates):
        self.candidates = list(candidates)
        self.asked = []

    def propose_candidates(self, **kwargs):
        self.asked.append(("identity", kwargs))
        return {"status": "ready", "kind": "candidates", "grounded": False, "note": "",
                "candidates": list(self.candidates), "space": "test"}


class RelationalRetina(FakeRetina):
    def propose_for_relation(self, **kwargs):
        self.asked.append(("relational", kwargs))
        return {"status": "ready", "kind": "candidates", "grounded": False, "note": "",
                "candidates": list(self.candidates), "space": "test", "ranking": "relational"}


def _seed():
    return mk.seed(POST_A, region_id="a_part")


def test_a_retina_without_relational_retrieval_is_asked_the_old_question():
    """Duck-typed on purpose. An older index — or a double standing in for one — degrades to
    identity ranking instead of erroring, because a worse proposal is still a proposal."""
    fake = FakeRetina([_cand("post_b", "b_part", 0.7)])
    mk.propose(_seed(), k=4, retina_module=fake, ranking=mk.RANKING_RELATIONAL)
    assert [kind for kind, _ in fake.asked] == ["identity"]


def test_relational_is_the_default_question_when_the_retina_can_answer_it():
    fake = RelationalRetina([_cand("post_b", "b_part", 0.7)])
    mk.propose(_seed(), k=4, retina_module=fake)
    assert [kind for kind, _ in fake.asked] == ["relational"]


def test_the_identity_ranking_stays_runnable():
    """The baseline is kept as a code path, not as a memory. A claim of improvement that cannot be
    re-measured against what it improved on is not a measurement."""
    fake = RelationalRetina([_cand("post_b", "b_part", 0.7)])
    mk.propose(_seed(), k=4, retina_module=fake, ranking=mk.RANKING_IDENTITY)
    assert [kind for kind, _ in fake.asked] == ["identity"]


def _run(ranking, candidates):
    return asyncio.run(mk.run_kernel(
        post_a=POST_A, posts=copy.deepcopy(POSTS), persist=False, region_id="a_part",
        ranking=ranking, retina_module=RelationalRetina(candidates)))


def test_the_same_candidates_get_the_same_verdicts_whichever_ranking_supplied_them():
    """THE ASSERTION THE LANE CARD ASKS FOR, as a test rather than as a diff.

    Grounding reads the candidate envelope and nothing else. Hand the two rankings an identical
    candidate list and every verdict, reason and measurement must match — the improvement has to
    come from WHICH candidates arrive, never from a candidate being treated differently once it
    has.
    """
    cands = [_cand("post_b", "b_part", 0.7), _cand("post_flat", "f_left", 0.9)]
    a, b = _run(mk.RANKING_IDENTITY, cands), _run(mk.RANKING_RELATIONAL, cands)
    key = lambda t: [(c["candidate"]["region_id"], c["status"], c.get("reason"),
                      (c.get("measurement") or {}).get("nesting_index")) for c in t["considered"]]
    assert key(a) == key(b)
    assert any(c["status"] == "grounded" for c in a["considered"])


def test_a_relational_proposal_still_grounds_only_on_masks():
    """The ruling is downstream of the ranking and stays there. A box-only candidate promoted to
    rank 1 by the prior is refused exactly as it was at rank 40."""
    boxed = _post("post_boxed", [_boxed("x_whole", (0.1, 0.1, 0.6, 0.6)),
                                 _boxed("x_part", (0.2, 0.2, 0.1, 0.1)),
                                 _boxed("x_sibling", (0.4, 0.4, 0.1, 0.1))])
    posts = {**copy.deepcopy(POSTS), "post_boxed": boxed}
    transcript = asyncio.run(mk.run_kernel(
        post_a=POST_A, posts=posts, persist=False, region_id="a_part",
        retina_module=RelationalRetina([_cand("post_boxed", "x_part", 0.99)])))
    refusal = transcript["considered"][0]
    assert refusal["status"] == "refused"
    assert refusal["reason"] == mk.REFUSED_BOX_ONLY


def test_the_prior_never_reaches_the_mark():
    """A grounded candidate's mark cites the ORGAN's measurement. Nothing box-basis may travel
    into it, or the ranking would end up inside the evidence it was only supposed to find."""
    transcript = _run(mk.RANKING_RELATIONAL, [_cand("post_b", "b_part", 0.7)])
    grounded = [c for c in transcript["considered"] if c["status"] == "grounded"]
    assert grounded, "expected the aligned shape to ground"
    mark = grounded[0]["mark"]
    assert mark[organ.STATUS_KEY] == organ.EpistemicStatus.MEASURED.value
    assert "prior" not in repr(mark) and "relational" not in repr(mark)


def test_the_edge_still_carries_no_status_and_no_provenance():
    """Lane G's rule, re-checked from this lane: the ranking changed what was proposed and must
    not have changed what an edge is."""
    transcript = _run(mk.RANKING_RELATIONAL, [_cand("post_b", "b_part", 0.7)])
    assert transcript["movements"], "expected a movement"
    edge = transcript["movements"][0]["edge"]
    assert "epistemic_status" not in edge and "provenance" not in edge


def test_posts_are_untouched_by_either_ranking():
    for ranking in (mk.RANKING_IDENTITY, mk.RANKING_RELATIONAL):
        assert _run(ranking, [_cand("post_b", "b_part", 0.7)])["posts_unchanged"] is True


# ── the retina's own vocabulary, kept honest ─────────────────────────────────────────────────

def test_the_prior_thresholds_are_the_retinas_own_and_not_imported():
    """They hold the organ's values and are declared separately on purpose: a proposer wired to
    always agree with the decider reports 100% and has stopped being evidence. If the organ
    retunes, this drifts — visibly, as a falling hit rate."""
    assert rel.MIN_CONTAINMENT == organ.MIN_CONTAINMENT
    assert rel.MAX_SCALE_RATIO == organ.MAX_SCALE_RATIO
    # Read as imports rather than as text — the module DISCUSSES both by name at length, and a
    # grep-shaped assertion would be testing the prose.
    tree = ast.parse(pathlib.Path(rel.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("nestedness_organ" in m or "structure_map" in m or "movement_kernel" in m
                   for m in imported), imported


def test_recall_is_wider_than_the_budget_by_default():
    """Re-ranking k into k can only reorder what you already had. The multiplier is what lets a
    relationally-plausible region at identity rank 30 reach an agent whose budget is 12."""
    assert rel.DEFAULT_RECALL_MULTIPLIER > 1


def test_shape_affinity_treats_two_absences_as_agreement():
    """0/0 = 1. Two parts that both bottom out DO share that shape, and scoring their agreement
    as zero would penalise the commonest real match in the corpus."""
    assert rel._alignment(0, 0) == 1.0
    assert rel._alignment(0, 4) == 0.0
    assert rel._alignment(2, 4) == 0.5


# ── 5. the geometry sidecar: derived, and honest about being absent ──────────────────────────

class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        async def gen():
            for doc in self._docs:
                yield doc
        return gen()


class _Posts:
    def __init__(self, docs):
        self.docs = list(docs)

    def find(self, query=None, projection=None):
        return _Cursor(self.docs)


@pytest.fixture
def sidecar(tmp_path, monkeypatch):
    monkeypatch.setenv("RETINA_DB_PATH", str(tmp_path / "retina"))
    geo._CACHE.update(key=None, payload=None)
    yield
    geo._CACHE.update(key=None, payload=None)


def test_the_sidecar_round_trips_every_extent(sidecar):
    out = asyncio.run(geo.geometry_rebuild(source=_Posts([POST_A, POST_FLAT])))
    assert out["totals"] == {"posts": 2, "regions": 6, "masked": 6, "unlocatable": 0}
    loaded = geo.load_geometry()
    assert set(loaded["posts"]) == {"post_a", "post_flat"}
    assert loaded["posts"]["post_a"]["a_part"]["has_mask"] is True


def test_rebuilding_the_sidecar_converges_rather_than_accumulates(sidecar):
    first = asyncio.run(geo.geometry_rebuild(source=_Posts([POST_A])))
    second = asyncio.run(geo.geometry_rebuild(source=_Posts([POST_A])))
    assert first["totals"] == second["totals"]
    assert len(geo.load_geometry(refresh=True)["posts"]) == 1


def test_a_sidecar_from_another_layout_is_ignored_whole(sidecar):
    """A stale prior is worse than none: it is silently wrong, and the ranking it produces looks
    exactly as confident as a correct one."""
    asyncio.run(geo.geometry_rebuild(source=_Posts([POST_A])))
    path = geo.geometry_path()
    path.write_text('{"geometry_version": 999, "posts": {"post_a": {"a_part": {}}}}')
    loaded = geo.load_geometry(refresh=True)
    assert loaded["stale"] is True and loaded["posts"] == {}


def test_a_missing_sidecar_is_an_absence_not_an_error(sidecar):
    status = geo.geometry_status()
    assert status["missing"] is True and status["posts"] == 0


def test_live_posts_beat_the_sidecar_because_they_cannot_be_stale(sidecar):
    asyncio.run(geo.geometry_rebuild(source=_Posts([POST_A])))
    live = geo.geometry_for({"post_b": POST_B})
    assert set(live) == {"post_b"}


def test_without_geometry_the_proposal_falls_back_to_identity_and_says_why(sidecar, monkeypatch):
    """THE CLAIM THAT KEEPS AN UNBUILT CACHE FROM LOOKING LIKE A RANKING. Returning the identity
    order under the label `relational` would be a silent lie about what the order means."""
    from backend.services.retina import service

    monkeypatch.setattr(service, "propose_candidates", lambda **kw: {
        "status": "ready", "candidates": [_cand("post_b", "b_part", 0.7)], "kind": "candidates",
        "grounded": False, "note": ""})
    envelope = service.propose_for_relation(region_id="a_part", post_id="post_a", k=1)
    assert envelope["ranking"] == "identity"
    assert "no cached geometry" in envelope["reason"]


def test_a_refusal_from_recall_is_passed_through_untouched(sidecar, monkeypatch):
    """`unknown` must not become `empty` on the way through the re-ranker — the retina's own rule
    that "I have never seen that" and "that has no neighbours" are different facts."""
    from backend.services.retina import service

    monkeypatch.setattr(service, "propose_candidates", lambda **kw: {
        "status": "unknown", "candidates": [], "reason": "never indexed", "kind": "candidates",
        "grounded": False, "note": ""})
    envelope = service.propose_for_relation(region_id="a_part", post_id="post_a", k=4)
    assert envelope["status"] == "unknown" and envelope["ranking"] == "identity"


def test_the_relational_proposal_reports_what_the_budget_cut(sidecar, monkeypatch):
    """The density lane's rule: a bounded sweep says what it dropped, or it reads as complete."""
    from backend.services.retina import service

    cands = [_cand("post_flat", "f_left", 0.99), _cand("post_b", "b_part", 0.10)]
    monkeypatch.setattr(service, "propose_candidates", lambda **kw: {
        "status": "ready", "candidates": cands, "kind": "candidates", "grounded": False,
        "note": ""})
    envelope = service.propose_for_relation(
        region_id="a_part", post_id="post_a", k=1,
        geometry=geometry_of(POST_A, POST_B, POST_FLAT))
    assert envelope["ranking"] == "relational"
    assert envelope["candidates"][0]["region_id"] == "b_part"
    assert [d["region_id"] for d in envelope["dropped"]] == ["f_left"]


# ── 6. the routes ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routers import retina as router_module

    monkeypatch.setenv("RETINA_DB_PATH", str(tmp_path / "routed"))
    geo._CACHE.update(key=None, payload=None)
    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1/retina")
    with TestClient(app) as c:
        yield c


def test_the_relational_route_refuses_a_raw_vector(client):
    """A relational prior has to know where the seed SITS. A bare embedding cannot say, and
    guessing a seed skeleton would rank confidently on the wrong shape — so the request model
    does not offer the option rather than filling it in."""
    r = client.post("/api/v1/retina/candidates/relational",
                    json={"embedding": [0.1] * 384, "k": 4})
    assert r.status_code == 422


def test_the_relational_route_keeps_the_identity_routes_status_codes(client):
    """404 for never-indexed, not an empty 200 — same rule, because the same confusion is fatal
    to a caller either way."""
    r = client.post("/api/v1/retina/candidates/relational",
                    json={"region_id": "a_part", "post_id": "post_a", "k": 4})
    assert r.status_code == 404


def test_the_geometry_rebuild_route_is_separate_from_the_index_rebuild(client, monkeypatch):
    """Two caches, two sources: the index mirrors `region_embeddings`, the sidecar mirrors
    `region_annotations`. A mask sweep moves one without moving the other, so folding them into
    one call would make it impossible to say which is stale."""
    from backend.routers import retina as router_module

    async def _rebuild():
        return {"totals": {"posts": 2, "regions": 6, "masked": 6, "unlocatable": 0}}

    monkeypatch.setattr(router_module.retina, "geometry_rebuild", _rebuild)
    r = client.post("/api/v1/retina/geometry/rebuild")
    assert r.status_code == 200 and r.json()["totals"]["regions"] == 6
