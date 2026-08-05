"""
Simulation Engine · Lane 3 · R1 — the Retina.

Proves the candidate generator movement will stand on: an index derived from `region_embeddings`
whose rebuild is idempotent, whose neighbours are visibly related, whose refusals are
distinguishable from its empty results, and which cannot compare two vector spaces.

Everything runs against a real LanceDB index built from a checked-in fixture — no Mongo, no
network, no GPU, no model. The fixture is three well-separated clusters of 16-d vectors plus a
second (incomparable) space, a legacy unspaced row, and one row per skip reason, so "the nearest
neighbours are the related ones" and "the coverage claim is honest" are both assertions about a
real index rather than about a mock.
"""
import asyncio
import json
import pathlib

import pytest

from backend.services import retina
from backend.services.retina import store as st
from backend.services.retina.store import RetinaStore

pytestmark = pytest.mark.skipif(not st.is_available(),
                                reason=f"retina backing store unavailable: {st.unavailable_reason()}")

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "retina_embeddings.json"

DINO_SPACE = "dinov2_vits14|identity|dino-v1|16"
FASHION_SPACE = "fashion-clip|fashion|vitb32|8"
LEGACY_SPACE = "legacy|fashion-clip|8"


def _docs():
    return json.loads(FIXTURE.read_text())


def _build(path, **kwargs):
    """A real index at `path`, built from the fixture. Returns (store, report)."""
    store = RetinaStore(path)
    report = asyncio.run(retina.index_rebuild(store=store, source=_docs(), **kwargs))
    return store, report


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One index, built once, shared by the read-path tests — none of which mutate it."""
    return _build(tmp_path_factory.mktemp("retina_shared"))


# ── the build ────────────────────────────────────────────────────────────────

def test_rebuild_buckets_the_fixture_into_its_three_spaces(built):
    _, report = built
    assert report["status"] == "ready"
    assert set(report["spaces"]) == {DINO_SPACE, FASHION_SPACE, LEGACY_SPACE}
    assert report["spaces"][DINO_SPACE]["rows"] == 24        # 3 clusters x 4 posts x 2 regions
    assert report["spaces"][DINO_SPACE]["dim"] == 16
    assert report["spaces"][FASHION_SPACE]["rows"] == 2
    assert report["totals"]["indexed"] == 27
    assert not report["partial"] and not report["truncated"]


def test_every_space_gets_its_own_table(built):
    """A space is a table. Two spaces sharing one would be the whole failure mode."""
    store, report = built
    tables = {e["table"] for e in report["spaces"].values()}
    assert len(tables) == len(report["spaces"])
    assert tables <= set(store.tables_on_disk())


def test_a_legacy_unspaced_row_is_not_folded_into_a_spaced_table(built):
    """FashionCLIP rows predating VISION-E carry no `space`. They are 8-d, exactly like the
    spaced FashionCLIP vectors — and still must not share a table with them, because nobody
    measured that those two projections are comparable."""
    _, report = built
    assert report["spaces"][LEGACY_SPACE]["dim"] == report["spaces"][FASHION_SPACE]["dim"] == 8
    assert report["spaces"][LEGACY_SPACE]["legacy"] is True
    assert report["spaces"][FASHION_SPACE]["legacy"] is False
    assert report["spaces"][LEGACY_SPACE]["table"] != report["spaces"][FASHION_SPACE]["table"]


def test_the_skip_ledger_names_every_row_it_could_not_index(built):
    """Coverage is a claim, and this is where it is made. Each fixture row that declares a
    `_skip` reason must be refused for exactly that reason, and nothing else may be refused."""
    _, report = built
    expected = {}
    for doc in _docs():
        if doc.get("_skip"):
            expected[doc["_skip"]] = expected.get(doc["_skip"], 0) + 1
    assert {r: n for r, n in report["skipped"].items() if n} == expected
    assert report["totals"]["skipped"] == sum(expected.values())
    assert report["totals"]["scanned"] == report["totals"]["indexed"] + report["totals"]["skipped"]
    reasons_named = {ex["reason"] for ex in report["skipped_examples"]}
    assert reasons_named == set(expected)          # an example for each, not just a count


def test_skip_reasons_are_a_closed_enumeration(built):
    """The report always carries every reason, so 'zero skipped for this' is visibly different
    from 'this was never checked'."""
    _, report = built
    assert set(report["skipped"]) == set(retina.SKIP_REASONS)


# ── idempotence ──────────────────────────────────────────────────────────────

def test_rebuild_is_idempotent(tmp_path):
    """Same source, same index — proven by content fingerprint, not by row count alone."""
    store, first = _build(tmp_path)
    _, second = _build(tmp_path)
    assert {s: e["fingerprint"] for s, e in first["spaces"].items()} == \
           {s: e["fingerprint"] for s, e in second["spaces"].items()}
    assert {s: e["rows"] for s, e in first["spaces"].items()} == \
           {s: e["rows"] for s, e in second["spaces"].items()}
    assert second["dropped_tables"] == []
    assert sorted(store.tables_on_disk()) == sorted(e["table"] for e in second["spaces"].values())


def test_rebuilding_does_not_grow_the_index_on_disk(tmp_path):
    """Lance is a versioned format: an overwrite writes a new version and keeps the old one.
    Without compaction a logically identical rebuild still doubles the directory — idempotent
    in the ledger, leaking in the filesystem."""
    _build(tmp_path)
    after_first = RetinaStore(tmp_path).size_bytes()
    _build(tmp_path)
    _build(tmp_path)
    after_third = RetinaStore(tmp_path).size_bytes()
    assert after_third < after_first * 1.5


def test_a_changed_vector_moves_the_fingerprint(tmp_path):
    """The fingerprint must be sensitive to content, not just to shape — otherwise 'idempotent'
    would be satisfied by any two builds with the same number of rows."""
    _, first = _build(tmp_path)
    docs = _docs()
    for doc in docs:
        if doc.get("embedding_id", "").endswith("post_arch_0_seg_0"):
            doc["vector"] = [v + 0.5 for v in doc["vector"]]
    store = RetinaStore(tmp_path)
    second = asyncio.run(retina.index_rebuild(store=store, source=docs))
    assert second["spaces"][DINO_SPACE]["rows"] == first["spaces"][DINO_SPACE]["rows"]
    assert second["spaces"][DINO_SPACE]["fingerprint"] != first["spaces"][DINO_SPACE]["fingerprint"]


def test_a_rebuild_drops_tables_whose_source_is_gone(tmp_path):
    """A rebuild makes the index EQUAL the source. A space that no longer has rows must not
    survive as a stale table quietly answering queries."""
    _build(tmp_path)
    store = RetinaStore(tmp_path)
    only_dino = [d for d in _docs() if d.get("space") == DINO_SPACE]
    report = asyncio.run(retina.index_rebuild(store=store, source=only_dino))
    assert set(report["spaces"]) == {DINO_SPACE}
    assert len(report["dropped_tables"]) == 2
    assert store.spaces().keys() == {DINO_SPACE}


def test_a_narrowed_rebuild_keeps_the_spaces_it_did_not_visit(tmp_path):
    """Reindexing one space after a backfill must not un-index the others."""
    _build(tmp_path)
    store = RetinaStore(tmp_path)
    report = asyncio.run(retina.index_rebuild(store=store, source=_docs(), spaces=[DINO_SPACE]))
    assert set(report["spaces"]) == {DINO_SPACE, FASHION_SPACE, LEGACY_SPACE}
    assert report["partial"] is True
    assert report["dropped_tables"] == []


def test_a_truncated_build_says_so(tmp_path):
    """A query answered from a fraction of the corpus is a different answer, and the caller has
    to be able to find that out."""
    store = RetinaStore(tmp_path)
    report = asyncio.run(retina.index_rebuild(store=store, source=_docs()[:6], limit=6))
    assert report["truncated"] is True and report["partial"] is True
    assert retina.index_status(store)["truncated"] is True


def test_streaming_in_batches_gives_the_same_index(tmp_path):
    """Memory is bounded by (spaces x batch), so a large rebuild flushes repeatedly. The
    fingerprint is order- and batch-independent by construction; this pins that."""
    _, whole = _build(tmp_path / "whole")
    _, batched = _build(tmp_path / "batched", batch_rows=3)
    assert {s: e["fingerprint"] for s, e in whole["spaces"].items()} == \
           {s: e["fingerprint"] for s, e in batched["spaces"].items()}


# ── candidate quality ────────────────────────────────────────────────────────

def _cluster_of(post_id):
    return post_id.split("_")[1]


def test_nearest_neighbours_are_the_related_ones(built):
    """The spot check the whole lane exists to pass: a region's nearest neighbours belong to
    its own cluster, and every other cluster is further away than every member of its own."""
    store, _ = built
    for cluster in ("arch", "textile", "face"):
        eid = f"emb_dinov2_vits14_identity_post_{cluster}_0_seg_0"
        got = retina.retrieve_candidates(embedding_id=eid, k=5, store=store)
        assert len(got) == 5
        assert {_cluster_of(c["post_id"]) for c in got} == {cluster}, \
            f"{cluster} query pulled in {[c['post_id'] for c in got]}"
        far = retina.retrieve_candidates(embedding_id=eid, k=24, store=store)
        same = [c["score"] for c in far if _cluster_of(c["post_id"]) == cluster]
        other = [c["score"] for c in far if _cluster_of(c["post_id"]) != cluster]
        assert min(same) > max(other)


def test_scores_are_similarities_best_first(built):
    store, _ = built
    got = retina.retrieve_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=10, store=store)
    scores = [c["score"] for c in got]
    assert scores == sorted(scores, reverse=True)
    assert all(-1.0 <= s <= 1.0 for s in scores)
    assert scores[0] > 0.9                      # same cluster, near-identical direction


def test_a_region_is_never_its_own_neighbour(built):
    store, _ = built
    eid = "emb_dinov2_vits14_identity_post_arch_0_seg_0"
    got = retina.retrieve_candidates(embedding_id=eid, k=24, store=store)
    assert eid not in {c["embedding_id"] for c in got}
    assert len(got) == 23                       # the other 23 rows of that space, all of them


def test_exclude_post_id_drops_a_whole_post(built):
    """'Find this elsewhere' — and the exclusion is a PRE-filter, so it returns k results, not
    k-minus-however-many-got-trimmed."""
    store, _ = built
    got = retina.retrieve_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=5,
        exclude_post_id="post_arch_1", store=store)
    assert len(got) == 5
    assert "post_arch_1" not in {c["post_id"] for c in got}


def test_k_and_min_score_are_respected(built):
    store, _ = built
    eid = "emb_dinov2_vits14_identity_post_arch_0_seg_0"
    assert len(retina.retrieve_candidates(embedding_id=eid, k=3, store=store)) == 3
    strict = retina.retrieve_candidates(embedding_id=eid, k=24, min_score=0.9, store=store)
    assert strict and all(c["score"] >= 0.9 for c in strict)
    assert len(strict) < 23                     # the other clusters are genuinely excluded


def test_a_raw_embedding_can_be_queried_when_its_space_is_named(built):
    store, _ = built
    query = [1.0] * 5 + [0.0] * 11              # the arch centroid
    got = retina.retrieve_candidates(embedding=query, space=DINO_SPACE, k=4, store=store)
    assert {_cluster_of(c["post_id"]) for c in got} == {"arch"}


# ── space discipline ─────────────────────────────────────────────────────────

def test_a_search_never_leaves_the_space_it_resolved(built):
    """Every candidate comes from the query's own space — the guarantee `cosine_same_space`
    makes in the sidecar, re-made here as 'a space is a table'."""
    store, _ = built
    for eid, space in (("emb_dinov2_vits14_identity_post_arch_0_seg_0", DINO_SPACE),
                       ("emb_fashion-clip_fashion_post_textile_0_seg_0", FASHION_SPACE)):
        got = retina.retrieve_candidates(embedding_id=eid, k=50, store=store)
        assert {c["space"] for c in got} == {space}


def test_a_vector_cannot_be_searched_against_a_space_of_another_width(built):
    store, _ = built
    with pytest.raises(ValueError, match="16-d"):
        retina.retrieve_candidates(embedding=[1.0] * 16, space=FASHION_SPACE, store=store)


def test_a_raw_embedding_matching_two_spaces_refuses_to_guess(built):
    """The legacy and spaced FashionCLIP tables are both 8-d. An 8-d vector with no `space=`
    is not a query with a sensible default; it is a query missing an argument."""
    store, _ = built
    with pytest.raises(retina.AmbiguousQuery) as e:
        retina.retrieve_candidates(embedding=[0.3] * 8, k=2, store=store)
    assert set(e.value.alternatives) == {FASHION_SPACE, LEGACY_SPACE}


def test_a_16d_vector_resolves_without_a_space_because_only_one_holds_it(built):
    """Where there is nothing to guess, don't make the caller say it."""
    store, _ = built
    got = retina.retrieve_candidates(embedding=[1.0] * 5 + [0.0] * 11, k=2, store=store)
    assert {c["space"] for c in got} == {DINO_SPACE}


# ── refusals are not empty results ───────────────────────────────────────────

def test_an_unindexed_embedding_raises_rather_than_returning_nothing(built):
    """'I have never seen that region' and 'that region has no neighbours' are different facts.
    Collapsing them lets an agent conclude a region is isolated when the index is just stale."""
    store, _ = built
    with pytest.raises(retina.UnknownQuery):
        retina.retrieve_candidates(embedding_id="emb_never_indexed", store=store)


def test_a_region_id_alone_is_ambiguous_and_a_post_id_settles_it(built):
    """Region ids are 'seg_0'-shaped and unique only WITHIN a post — a fact the lane directive's
    `retrieve_candidates(region_id, k)` signature does not carry."""
    store, _ = built
    with pytest.raises(retina.AmbiguousQuery) as e:
        retina.retrieve_candidates(region_id="seg_0", store=store)
    assert len(e.value.alternatives) > 1
    got = retina.retrieve_candidates(region_id="seg_0", post_id="post_face_1", k=3, store=store)
    assert {_cluster_of(c["post_id"]) for c in got} == {"face"}


def test_a_role_with_no_indexed_space_is_a_refusal_not_a_silence(built):
    store, _ = built
    with pytest.raises(retina.UnknownQuery, match="role"):
        retina.retrieve_candidates(region_id="seg_0", post_id="post_arch_0",
                                   role="whole_image", store=store)


def test_an_unbuilt_index_refuses_rather_than_reporting_no_neighbours(tmp_path):
    store = RetinaStore(tmp_path / "never_built")
    with pytest.raises(retina.UnknownQuery, match="not built"):
        retina.retrieve_candidates(embedding=[1.0] * 16, store=store)
    assert retina.index_status(store)["status"] == "not_built"


def test_exactly_one_query_form_is_required(built):
    store, _ = built
    with pytest.raises(ValueError, match="exactly one"):
        retina.retrieve_candidates(store=store)
    with pytest.raises(ValueError, match="exactly one"):
        retina.retrieve_candidates(region_id="seg_0", embedding_id="emb_x", store=store)


def test_a_manifest_from_another_schema_version_is_treated_as_absent(tmp_path):
    """A mapping we cannot vouch for is worse than no mapping: better to report 'not built' and
    rebuild than to answer queries against table names that may mean something else now."""
    store, _ = _build(tmp_path)
    manifest = json.loads(store.manifest_path.read_text())
    manifest["manifest_version"] = st.MANIFEST_VERSION + 99
    store.manifest_path.write_text(json.dumps(manifest))
    assert RetinaStore(tmp_path).spaces() == {}
    assert retina.index_status(RetinaStore(tmp_path))["status"] == "not_built"


# ── honesty ──────────────────────────────────────────────────────────────────

def test_a_candidate_carries_the_contract_and_its_provenance(built):
    store, _ = built
    got = retina.retrieve_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=1, store=store)
    c = got[0]
    assert {"post_id", "region_id", "score"} <= set(c)         # the directive's contract
    assert c["model"] == "dinov2_vits14" and c["dim"] == 16
    assert c["checkpoint"] == "dinov2_vits14_pretrain"
    assert c["geometry_rev"] == 3 and c["route"] == "mask_pool"
    assert c["space"] == DINO_SPACE


def test_a_candidate_is_never_dressed_as_a_claim(built):
    """The retina proposes where to look. It does not know anything about either image, so a
    candidate carries no epistemic status, no relation and no label — and the day someone
    starts persisting these as edges, this is the test that should object."""
    store, _ = built
    got = retina.retrieve_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=8, store=store)
    assert got
    for c in got:
        assert c["kind"] == retina.CANDIDATE_KIND == "candidate"
        assert not ({"epistemic_status", "relation", "relation_type", "label", "measured",
                     "grounded", "verdict"} & set(c))


def test_the_envelope_carries_the_caveat_and_the_state_of_the_index(built):
    store, _ = built
    env = retina.propose_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=3, store=store)
    assert env["status"] == "ready" and len(env["candidates"]) == 3
    assert env["grounded"] is False and "not relations" in env["note"]
    assert env["space"] == DINO_SPACE
    assert env["index"]["rows"] == 27 and env["index"]["truncated"] is False


def test_the_envelope_keeps_every_refusal_distinct(built):
    """`unavailable` / `unknown` / `ambiguous` / `error` / `empty` all mean different things to
    a caller deciding where an agent may move."""
    store, _ = built
    cases = {
        "unknown": dict(embedding_id="emb_never_indexed"),
        "ambiguous": dict(region_id="seg_0"),
        "error": dict(embedding=[1.0] * 16, space=FASHION_SPACE),
    }
    for expected, kwargs in cases.items():
        env = retina.propose_candidates(store=store, **kwargs)
        assert env["status"] == expected, (expected, env["reason"])
        assert env["candidates"] == [] and env["reason"]
        assert env["grounded"] is False


def test_the_envelope_reports_an_empty_search_as_empty_not_as_a_failure(built):
    """It looked, and nothing cleared the bar. That is a result, not a refusal."""
    store, _ = built
    env = retina.propose_candidates(
        embedding_id="emb_dinov2_vits14_identity_post_arch_0_seg_0", k=8,
        min_score=0.999999, store=store)
    assert env["status"] == "empty" and env["candidates"] == []
    assert env["space"] == DINO_SPACE           # the space it searched, even with no results


def test_index_status_reports_coverage_not_just_success(built):
    store, _ = built
    status = retina.index_status(store)
    assert status["status"] == "ready"
    assert status["totals"]["rows"] == 27
    assert status["totals"]["skipped"] == 6
    assert status["spaces"][DINO_SPACE]["rows_on_disk"] == 24
    assert status["totals"]["index_bytes"] > 0


# ── the routes ───────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """The retina router over a throwaway index, seeded through the real rebuild path.

    `RETINA_DB_PATH` is redirected first: the handlers construct their own `RetinaStore()`, and
    a test that read the developer's actual index would be neither hermetic nor repeatable.
    Mongo is replaced at `iter_region_embeddings`, so the route drives the real build.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.routers import retina as router_module
    from backend.services.retina import index as index_module

    monkeypatch.setenv("RETINA_DB_PATH", str(tmp_path / "routed"))

    async def _fake_source(*, limit=None, spaces=None):
        for doc in _docs():
            yield doc

    monkeypatch.setattr(index_module, "iter_region_embeddings", _fake_source)

    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/v1/retina")
    with TestClient(app) as c:
        yield c


def test_status_reports_an_unbuilt_index_as_200_not_as_an_error(client):
    """This is the call you make to find out which state you are in, so the state belongs in
    the body — a 503 here would make 'not built yet' indistinguishable from 'broken'."""
    r = client.get("/api/v1/retina/status")
    assert r.status_code == 200 and r.json()["status"] == "not_built"


def test_rebuild_then_candidates_over_http(client):
    built = client.post("/api/v1/retina/rebuild", json={})
    assert built.status_code == 200
    assert built.json()["totals"]["rows"] == 27

    assert client.get("/api/v1/retina/status").json()["status"] == "ready"

    r = client.post("/api/v1/retina/candidates", json={
        "embedding_id": "emb_dinov2_vits14_identity_post_arch_0_seg_0", "k": 4})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready" and len(body["candidates"]) == 4
    assert {_cluster_of(c["post_id"]) for c in body["candidates"]} == {"arch"}
    assert body["grounded"] is False and "not relations" in body["note"]
    assert all(c["kind"] == "candidate" for c in body["candidates"])


def test_each_refusal_gets_its_own_status_code(client):
    """A caller that cannot tell 'the index is stale' from 'this region has no neighbours' will
    draw the wrong conclusion from an empty list."""
    client.post("/api/v1/retina/rebuild", json={})
    for code, payload in (
        (404, {"embedding_id": "emb_never_indexed"}),                       # never indexed
        (409, {"region_id": "seg_0"}),                                      # names many regions
        (400, {"embedding": [1.0] * 16, "space": FASHION_SPACE}),           # width disagrees
        (422, {"embedding_id": "x", "k": 0}),                               # k out of range
    ):
        r = client.post("/api/v1/retina/candidates", json=payload)
        assert r.status_code == code, (code, payload, r.text[:200])


def test_an_empty_search_is_a_200_because_it_looked(client):
    client.post("/api/v1/retina/rebuild", json={})
    r = client.post("/api/v1/retina/candidates", json={
        "embedding_id": "emb_dinov2_vits14_identity_post_arch_0_seg_0",
        "k": 8, "min_score": 1.0})
    assert r.status_code == 200
    assert r.json()["status"] == "empty" and r.json()["candidates"] == []


def test_a_partial_rebuild_over_http_declares_itself_partial(client):
    r = client.post("/api/v1/retina/rebuild", json={"limit": 6})
    assert r.status_code == 200
    assert r.json()["partial"] is True
    assert client.get("/api/v1/retina/status").json()["partial"] is True
