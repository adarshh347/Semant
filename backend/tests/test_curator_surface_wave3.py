"""WAVE3 — the curator surface: the five ways the door could be built wrong.

This is the seam ten lanes deferred to. Every one of them wrote "proposed until a curator commits",
and a surface that got any of the following wrong would satisfy that sentence while breaking what
it means:

  1. NOTHING AUTO-COMMITS. Filing, reading and listing must all leave the ledger untouched. A
     surface that committed on read would look identical from the outside — the item would simply
     be accepted, and nobody would know who accepted it. §1.
  2. `proposed` MUST NOT RENDER AS `measured`. The recurring serializer trap: a response model with
     a defaulted status field fills it in and FastAPI renders the default as data. Pinned in BOTH
     directions through the real route. §2.
  3. A COMMIT CHANGES EXACTLY ONE THING. One mark appended to one post, by `$push`, and every other
     field of that post byte-identical — the invariant this lane deliberately breaks, broken in
     precisely one way. §3.
  4. THE TWO STATUSES ARE DIFFERENT QUESTIONS. `epistemic` says how the producer knows;
     `ledger_status` says whether a human agreed. A measured proposal is `measured` AND `proposed`,
     and that is not a contradiction. §2.
  5. A COMMIT THAT DID NOTHING MUST SAY SO. Committing twice, or to a post that is gone, is refused
     loudly — a silent no-op would leave a curator believing they had accepted something. §4.

§5 covers the queue's own discipline: it stores no status, it does not rank, and it refuses a
proposal that carries one.
"""
from __future__ import annotations

import copy
import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import curator
from backend.services.epistemics import STATUS_KEY, EpistemicStatus

STAMP = "2026-08-07T00:00:00+00:00"


# ── fakes ───────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, _n):
        return self

    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield doc
        return _gen()


class FakeCollection:
    def __init__(self):
        self.docs = {}
        self.writes = []

    async def insert_one(self, doc):
        key = doc.get("_id") or doc.get("proposal_id") or len(self.docs)
        self.docs[key] = copy.deepcopy(doc)
        self.writes.append(("insert", key))
        return type("R", (), {"inserted_id": key})()

    async def find_one(self, query, projection=None):
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in (query or {}).items()):
                return copy.deepcopy(doc)
        return None

    def find(self, query=None, projection=None):
        out = []
        for doc in self.docs.values():
            if all(_matches(doc.get(k), v) for k, v in (query or {}).items()):
                out.append(copy.deepcopy(doc))
        return _Cursor(out)

    async def count_documents(self, query, limit=None):
        return sum(1 for doc in self.docs.values()
                   if all(_matches(doc.get(k), v) for k, v in (query or {}).items()))

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs.values():
            if all(_matches(doc.get(k), v) for k, v in (query or {}).items()):
                doc.update(update.get("$set", {}))
                for field, value in (update.get("$push") or {}).items():
                    doc.setdefault(field, []).append(copy.deepcopy(value))
                self.writes.append(("update", query, sorted(update)))
                return type("R", (), {"matched_count": 1, "modified_count": 1})()
        return type("R", (), {"matched_count": 0, "modified_count": 0})()


def _matches(value, spec):
    if isinstance(spec, dict) and "$ne" in spec:
        return value != spec["$ne"]
    return value == spec


def _hash(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()


def _mark(mark_id="vm_occ_a1", status=EpistemicStatus.MEASURED.value):
    """An organ's mark, shaped like the ones `occlusion_organ.grounding_mark` produces."""
    return {"id": mark_id, "type": "relation_mark", "role": "in_front_of",
            "label": "r_part in front of r_whole", STATUS_KEY: status,
            "post_id": "p1", "provenance": {"producer": "occlusion_organ"},
            "created_at": STAMP}


def _proposal(mark_id="vm_occ_a1", status=EpistemicStatus.MEASURED.value, post_id="p1"):
    return curator.proposal_entry(
        mark=_mark(mark_id, status), post_id=post_id, producer="occlusion_organ",
        kind="occlusion_supersedes_containment",
        subject={"front_region_id": "r_part", "back_region_id": "r_whole"},
        evidence={"ordering_separation": 0.9822, "separation_floor": 0.95, "depth_grid": 192},
        filed_by="scripts/curator_file_occlusions.py", now=STAMP)


def _post(post_id="p1", marks=()):
    return {"_id": post_id, "photo_url": "https://example.invalid/i.jpg",
            "region_annotations": [{"id": "r_part"}, {"id": "r_whole"}],
            "percepts": [], "grounds": [], "visual_marks": list(marks)}


@pytest.fixture
def wired(monkeypatch):
    """The curator router with both collections faked, mounted without the API-key dependency —
    what is under test is the route, and the auth wrapper is `require_api_key`'s to prove."""
    import backend.routers.curator as R

    proposals, posts = FakeCollection(), FakeCollection()
    posts.docs["p1"] = _post("p1")

    monkeypatch.setattr(curator, "_collection", lambda collection=None: proposals)

    async def _posts_for(rows):
        out = {}
        for row in rows:
            doc = posts.docs.get(str(row.get("post_id") or ""))
            if doc is not None:
                out[str(row["post_id"])] = copy.deepcopy(doc)
        return out
    monkeypatch.setattr(R, "_posts_for", _posts_for)

    import backend.services.atlas_relation as AR

    async def _commit(mark, post_ids, collection=None):
        written = []
        for pid in post_ids:
            doc = posts.docs.get(str(pid))
            if doc is None:
                continue
            doc.setdefault("visual_marks", []).append(copy.deepcopy(dict(mark)))
            written.append(str(pid))
        return written
    monkeypatch.setattr(AR, "commit_relation_to_posts", _commit)

    app = FastAPI()
    app.include_router(R.router, prefix="/api/v1/curator")
    with TestClient(app) as client:
        yield client, proposals, posts


# ── 1. nothing auto-commits ────────────────────────────────────────────────

def test_filing_writes_to_the_queue_and_to_no_post(wired):
    client, proposals, posts = wired
    before = _hash(posts.docs["p1"])

    import asyncio
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        curator.file_proposal(_proposal()))
    assert len(proposals.docs) == 1
    assert _hash(posts.docs["p1"]) == before, "filing touched a post"


def test_reading_the_queue_commits_nothing(wired):
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    before = _hash(posts.docs["p1"])

    body = client.get("/api/v1/curator/queue").json()
    assert body["total"] == 1
    assert body["proposals"][0]["ledger_status"] == curator.LEDGER_PROPOSED
    assert _hash(posts.docs["p1"]) == before
    assert not any(w[0] == "update" for w in posts.writes)


def test_there_is_no_bulk_accept_and_no_threshold_anywhere():
    """A route that accepted above a score would be substituting its own judgement for the
    curator's, which is the one thing this surface exists not to do.

    Scanned over the BODY, not the prose — the module docstring names what is absent, and a scan
    that could not tell a mention from a call would force it to stop explaining itself.
    """
    import re
    from pathlib import Path

    import backend.routers.curator as R
    body = re.sub(r'"""[\s\S]*?"""', "", Path(R.__file__).read_text())
    for absent in ("accept_all", "bulk", "auto_commit", "threshold", "min_confidence"):
        assert absent not in body, absent
    routes = [(r.path, sorted(r.methods)) for r in R.router.routes]
    assert sorted(routes) == [
        ("/queue", ["GET"]),
        ("/queue/{proposal_id}", ["GET"]),
        ("/queue/{proposal_id}/commit", ["POST"]),
    ]


# ── 2. proposed must not render as measured ────────────────────────────────

def test_the_read_path_never_renders_proposed_as_measured(wired):
    """THE SERIALIZER TRAP, both directions through the real route.

    A response model with a defaulted status field renders its default as data, which is how a
    proposal starts reading as accepted without anybody writing the word. Before the commit the
    mark is `measured` and the ledger is `proposed`; after it, the mark is unchanged and the ledger
    says `committed`. The two never collapse into one another.
    """
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()

    before = client.get("/api/v1/curator/queue/{}".format(_proposal_id(proposals))).json()
    assert before["epistemic"] == EpistemicStatus.MEASURED.value
    assert before["ledger_status"] == curator.LEDGER_PROPOSED
    assert before["live"] is False
    assert before["committed_at"] is None and before["committed_by"] is None

    client.post(f"/api/v1/curator/queue/{_proposal_id(proposals)}/commit",
                json={"curator": "adarsh"})

    after = client.get("/api/v1/curator/queue/{}".format(_proposal_id(proposals))).json()
    assert after["epistemic"] == EpistemicStatus.MEASURED.value, "the KIND of knowing is unchanged"
    assert after["ledger_status"] == curator.LEDGER_COMMITTED
    assert after["live"] is True


def test_an_interpretive_proposal_stays_interpretive_after_a_commit(wired):
    """A curator's act makes a claim durable; it cannot make an estimate into a measurement. The
    WAVE2.5 ruling, applied to the human."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal(status=EpistemicStatus.INTERPRETIVE.value)
    pid = _proposal_id(proposals)

    client.post(f"/api/v1/curator/queue/{pid}/commit", json={"curator": "adarsh"})
    body = client.get(f"/api/v1/curator/queue/{pid}").json()
    assert body["epistemic"] == EpistemicStatus.INTERPRETIVE.value
    assert body["ledger_status"] == curator.LEDGER_COMMITTED
    assert posts.docs["p1"]["visual_marks"][0][STATUS_KEY] == \
        EpistemicStatus.INTERPRETIVE.value


def test_the_response_model_has_no_status_default_to_fill_in():
    """Read off the model, because a test over behaviour only covers the paths it imagined. A
    defaulted `ledger_status` would render on any handler that forgot to hydrate."""
    from backend.routers.curator import ProposalView

    for field in ("ledger_status", "epistemic", "live", "committed_at", "committed_by"):
        assert ProposalView.model_fields[field].is_required(), \
            f"{field} has a default — a handler that skipped hydration would render it"


def test_the_two_statuses_answer_different_questions(wired):
    """`measured` and `proposed` on one row is not a contradiction: the organ is sure and the world
    has not agreed. A surface that could not say both would have to lie about one."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    row = client.get("/api/v1/curator/queue").json()["proposals"][0]
    assert (row["epistemic"], row["ledger_status"]) == (
        EpistemicStatus.MEASURED.value, curator.LEDGER_PROPOSED)
    assert "nobody has accepted it" in row["detail_ledger"]


# ── 3. a commit changes exactly one thing ──────────────────────────────────

def _proposal_id(proposals):
    return next(iter(proposals.docs.values()))["proposal_id"]


def test_a_commit_appends_one_mark_and_changes_nothing_else(wired):
    """The invariant this lane deliberately breaks, broken in exactly one way. `visual_marks` grows
    by one; every other field of the post is byte-identical."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    before = {k: _hash(v) for k, v in posts.docs["p1"].items() if k != "visual_marks"}

    resp = client.post(f"/api/v1/curator/queue/{_proposal_id(proposals)}/commit",
                       json={"curator": "adarsh"})
    assert resp.status_code == 200

    post = posts.docs["p1"]
    assert [m["id"] for m in post["visual_marks"]] == ["vm_occ_a1"]
    assert {k: _hash(v) for k, v in post.items() if k != "visual_marks"} == before


def test_a_commit_moves_only_its_own_proposal(wired):
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal("vm_occ_a1")
    proposals.docs["b"] = _proposal("vm_occ_b2")
    target = proposals.docs["a"]["proposal_id"]

    client.post(f"/api/v1/curator/queue/{target}/commit", json={"curator": "adarsh"})

    rows = {r["proposal_id"]: r for r in client.get("/api/v1/curator/queue").json()["proposals"]}
    assert rows[target]["ledger_status"] == curator.LEDGER_COMMITTED
    other = proposals.docs["b"]["proposal_id"]
    assert rows[other]["ledger_status"] == curator.LEDGER_PROPOSED
    assert [m["id"] for m in posts.docs["p1"]["visual_marks"]] == ["vm_occ_a1"]


def test_the_commit_records_who_and_when_on_the_mark_itself(wired):
    """The ledger has to carry the human. A mark that says only what it measured leaves the
    acceptance unattributable once the queue row is archived."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    client.post(f"/api/v1/curator/queue/{_proposal_id(proposals)}/commit",
                json={"curator": "adarsh"})

    provenance = posts.docs["p1"]["visual_marks"][0]["provenance"]
    assert provenance["committed_by"] == "adarsh" and provenance["committed_at"]
    assert provenance["producer"] == "occlusion_organ", "the producer is not overwritten"


def test_a_commit_uses_push_and_never_replaces_the_mark_list():
    """A replace on `visual_marks` has already destroyed committed regions in this codebase.
    Asserted against the function the service actually calls."""
    from pathlib import Path

    import re

    import backend.services.atlas_relation as AR
    source = Path(AR.__file__).read_text()
    body = re.sub(r'"""[\s\S]*?"""', "", source)
    assert '{"$push": {"visual_marks": dict(mark)}}' in body
    # The `$set` form appears in the DOCSTRING, naming the thing it refuses. In the body, never.
    assert '{"$set": {"visual_marks"' not in body
    assert '{"$set": {"visual_marks"' in source, "the refusal must stay documented where it lives"

    import backend.services.curator as C
    assert "commit_relation_to_posts" in re.sub(
        r'"""[\s\S]*?"""', "", Path(C.__file__).read_text())


# ── 4. a commit that did nothing says so ───────────────────────────────────

def test_committing_twice_is_refused_rather_than_repeated(wired):
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    pid = _proposal_id(proposals)

    assert client.post(f"/api/v1/curator/queue/{pid}/commit",
                       json={"curator": "adarsh"}).status_code == 200
    again = client.post(f"/api/v1/curator/queue/{pid}/commit", json={"curator": "adarsh"})
    assert again.status_code == 409
    assert "would put the same mark in the ledger twice" in again.json()["detail"]
    assert len(posts.docs["p1"]["visual_marks"]) == 1


def test_a_commit_with_no_curator_is_refused(wired):
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    resp = client.post(f"/api/v1/curator/queue/{_proposal_id(proposals)}/commit",
                       json={"curator": "   "})
    assert resp.status_code == 400
    assert "needs a curator" in resp.json()["detail"]
    assert posts.docs["p1"]["visual_marks"] == []


def test_a_commit_to_a_post_that_is_gone_refuses_and_leaves_the_proposal_open(wired):
    """The worst available outcome is a commit that wrote nothing and said nothing — the curator
    would believe they had accepted something."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal(post_id="p_missing")
    pid = _proposal_id(proposals)

    resp = client.post(f"/api/v1/curator/queue/{pid}/commit", json={"curator": "adarsh"})
    assert resp.status_code == 409
    assert "went nowhere" in resp.json()["detail"]
    assert proposals.docs["a"]["committed_at"] is None, "the proposal is still open"


def test_an_unknown_proposal_is_a_404(wired):
    client, _, _ = wired
    assert client.get("/api/v1/curator/queue/prop_nope").status_code == 404
    assert client.post("/api/v1/curator/queue/prop_nope/commit",
                       json={"curator": "adarsh"}).status_code == 404


# ── 5. the queue's own discipline ──────────────────────────────────────────

def test_a_proposal_may_not_carry_a_status_of_its_own():
    """Lane G refuses one on an edge, WAVE3 refuses one on an observation, and the reason is the
    same: a stored status is a second copy that can disagree with the ledger, and the one that
    disagrees quietly is the one deciding whether something has been accepted."""
    row = _proposal()
    for forbidden in (STATUS_KEY, "committed", "status", "ledger_status"):
        with pytest.raises(curator.ProposalRefused, match="may not carry"):
            curator.assert_valid_proposal({**row, forbidden: "measured"})


def test_a_proposal_with_no_mark_cites_no_measurement():
    with pytest.raises(curator.ProposalRefused, match="cites no measurement"):
        curator.proposal_entry(mark={}, post_id="p1", producer="x", kind="y",
                               subject={}, evidence={})


def test_the_queue_is_in_filed_order_and_not_ranked_by_the_evidence(wired):
    """A queue sorted by the producer's own confidence is the surface telling the curator what to
    look at first. The evidence is on every row; the ordering is the order things arrived."""
    client, proposals, posts = wired
    weak = _proposal("vm_occ_weak")
    weak["evidence"]["ordering_separation"] = 0.9501
    strong = _proposal("vm_occ_strong")
    strong["evidence"]["ordering_separation"] = 0.9999
    proposals.docs["a"], proposals.docs["b"] = weak, strong

    rows = client.get("/api/v1/curator/queue").json()["proposals"]
    assert [r["mark_id"] for r in rows] == ["vm_occ_weak", "vm_occ_strong"]


def test_the_evidence_is_the_producers_own_numbers_passed_through(wired):
    """A curator judging an occlusion needs the ordering statistic and the grid it was read at. A
    surface that summarised them into a score would be making the judgement it presents."""
    client, proposals, posts = wired
    proposals.docs["a"] = _proposal()
    row = client.get("/api/v1/curator/queue").json()["proposals"][0]
    assert row["evidence"] == {"ordering_separation": 0.9822, "separation_floor": 0.95,
                               "depth_grid": 192}
    assert "score" not in row and "confidence" not in row


def test_filing_cannot_reach_a_post_collection():
    """Structural, not promised: `file_proposal` takes no post collection and has no way to get
    one, so filing cannot become committing by accident."""
    import inspect

    assert "posts" not in inspect.signature(curator.file_proposal).parameters
    body = inspect.getsource(curator.file_proposal)
    assert "post_collection" not in body and "commit_relation_to_posts" not in body
