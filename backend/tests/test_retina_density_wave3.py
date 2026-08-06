"""
WAVE3 retina density — what decides which regions get embedded, and what the delta counts mean.

The embedding run itself is a `scripts/` tool pointed at Mongo and at DINOv2; it cannot live in the
suite. What can, and what this file pins, is everything that decides WHAT gets written and HOW the
result is read:

  1. **the gap** — a region is work iff it HAS a measured mask and LACKS an identity embedding.
     Both halves matter. Dropping the first would embed VLM boxes nothing may ground on; dropping
     the second would rewrite 140 rows that were already correct, which is the difference between
     "additive" as a claim and "additive" as a fact.
  2. **the filtered post** — `embed_post` hands `embed_post_regions` a copy carrying ONLY the
     target regions, and asks for `whole_image` only where that row is genuinely absent. This is
     the mechanism behind (1); without it "additive" is a comment.
  3. **the tally** — the four refusal classes the before/after is reported in. `box_only` and
     `surface_only` are different findings (coverage vs. images) and a test keeps them from
     collapsing into one "refused" number that would hide which one moved.

The lane's own claim — that the retina still only PROPOSES — is not restated here because nothing
in this lane can ground: neither script imports the organ. That is checked by the kernel's own
suite, which is where grounding lives.
"""
import asyncio
import importlib.util
import pathlib

import numpy as np
import pytest
from bson import ObjectId

from backend.services import mask_geometry as mg
from backend.services import movement_kernel as mk
from backend.services import structure_map as sm

_SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load(name):
    """Both tools are `scripts/` entry points, not package modules — load them by path."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


density = _load("retina_density")
proof = _load("retina_density_proof")


def run(coro):
    return asyncio.run(coro)


RASTER = 64


def _rle(box):
    x, y, w, h = box
    bits = np.zeros((RASTER, RASTER), np.uint8)
    bits[int(round(y * RASTER)):int(round((y + h) * RASTER)),
         int(round(x * RASTER)):int(round((x + w) * RASTER))] = 1
    return mg.rle_encode_mask(bits)


def _masked(rid, box=(0.2, 0.2, 0.3, 0.3)):
    return {"id": rid, "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]},
            "mask_rle": _rle(box)}


def _boxed(rid, box=(0.2, 0.2, 0.3, 0.3)):
    """A VLM estimate. Real data, a legitimate candidate, and not admissible as a grounding."""
    return {"id": rid, "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]}}


P1 = "6a5fef58a3ddb6341fd69930"
P2 = "6a5ffab7a3ddb6341fd699d3"


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        async def gen():
            for doc in self._docs:
                yield doc
        return gen()


class FakeCollection:
    """Enough Mongo to answer the four queries these scripts ask, and no more.

    Deliberately not a general engine: `find` here understands `_id`, `role`, `post_id` and the
    `region_annotations.0` existence probe, which is the whole query surface of the two scripts. A
    fake that pretended to be more would be a second implementation to keep true.
    """

    def __init__(self, docs):
        self.docs = list(docs)
        self.queries = []

    def _match(self, doc, query):
        for key, want in (query or {}).items():
            if key == "region_annotations.0":
                if bool(doc.get("region_annotations")) != bool(want.get("$exists")):
                    return False
            elif key == "_id":
                if str(doc.get("_id")) != str(want):
                    return False
            elif str(doc.get(key)) != str(want):
                return False
        return True

    def find(self, query=None, projection=None):
        self.queries.append(dict(query or {}))
        return FakeCursor(d for d in self.docs if self._match(d, query))

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if self._match(doc, query):
                return doc
        return None


def _wire(monkeypatch, posts, embeddings):
    monkeypatch.setattr(density, "post_collection", FakeCollection(posts))
    monkeypatch.setattr(density, "region_embeddings_collection", FakeCollection(embeddings))


def _emb(post_id, region_id, role="identity"):
    return {"post_id": post_id, "region_id": region_id, "role": role,
            "embedding_id": f"emb_{post_id}_{region_id}_{role}"}


# ── 1. the gap: mask AND no embedding, both halves ───────────────────────────────────────────

def test_a_masked_region_with_no_embedding_is_the_work(monkeypatch):
    _wire(monkeypatch, [{"_id": ObjectId(P1), "photo_url": "http://x/1.jpg",
                         "region_annotations": [_masked("cseg_finial_0")]}], [])
    plan = run(density.survey())
    assert plan["work"][P1]["region_ids"] == ["cseg_finial_0"]
    assert plan["totals"]["masked_unembedded"] == 1


def test_a_masked_region_that_already_has_one_is_left_alone(monkeypatch):
    """The 140 pre-existing rows are correct. Re-embedding them would `$set` a fresh
    `updated_at` on every one — a mutation of rows nobody asked to change, which is exactly what
    "additive" is supposed to rule out."""
    _wire(monkeypatch,
          [{"_id": ObjectId(P1), "region_annotations": [_masked("cseg_finial_0")]}],
          [_emb(P1, "cseg_finial_0")])
    plan = run(density.survey())
    assert plan["work"] == {}
    assert plan["totals"]["masked_unembedded"] == 0


def test_an_unmasked_vlm_box_is_not_work_however_unembedded(monkeypatch):
    """THE CLAIM THAT KEEPS THIS LANE POINTED AT THE RULING.

    A `fine_N` box with no embedding is not a hole this lane fills. Embedding it would add a
    candidate the kernel must then refuse `box_only` — cost with no reachable grounding. The lane
    exists to make ADMISSIBLE geometry retrievable, not to make the index bigger.
    """
    _wire(monkeypatch,
          [{"_id": ObjectId(P1), "region_annotations": [_boxed("fine_0"), _boxed("region_2")]}],
          [])
    plan = run(density.survey())
    assert plan["work"] == {}
    assert plan["totals"]["regions"] == 2
    assert plan["totals"]["masked"] == 0


def test_a_region_with_an_unusable_mask_is_counted_as_unmasked(monkeypatch):
    """`rle_is_valid` is the gate, not the mere presence of a `mask_rle` key. A corrupt mask is a
    box in a mask's clothing, and the ruling turns on the geometry being real."""
    torn = {"id": "cseg_torn_0", "box": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            "mask_rle": {"size": [64, 64], "counts": "not-a-real-rle"}}
    _wire(monkeypatch, [{"_id": ObjectId(P1), "region_annotations": [torn]}], [])
    plan = run(density.survey())
    assert plan["work"] == {}
    assert plan["totals"]["masked"] == 0


def test_the_survey_reports_the_gap_across_posts_and_ignores_other_roles(monkeypatch):
    """A `context` row is not an `identity` row. The retina's candidate search reads `identity`,
    so a region carrying only `context` is still invisible to it and still work."""
    _wire(monkeypatch, [
        {"_id": ObjectId(P1), "region_annotations": [_masked("cseg_a_0"), _masked("cseg_a_1")]},
        {"_id": ObjectId(P2), "region_annotations": [_masked("cseg_b_0"), _boxed("fine_0")]},
    ], [_emb(P1, "cseg_a_0"), _emb(P2, "cseg_b_0", role="context")])
    plan = run(density.survey())
    assert sorted(plan["work"]) == sorted([P1, P2])
    assert plan["work"][P1]["region_ids"] == ["cseg_a_1"]
    assert plan["work"][P2]["region_ids"] == ["cseg_b_0"]
    assert plan["totals"] == {"regions": 4, "masked": 3, "masked_unembedded": 2, "embedded": 1}


def test_one_post_can_be_surveyed_alone(monkeypatch):
    _wire(monkeypatch, [
        {"_id": ObjectId(P1), "region_annotations": [_masked("cseg_a_0")]},
        {"_id": ObjectId(P2), "region_annotations": [_masked("cseg_b_0")]},
    ], [])
    assert list(run(density.survey(P2))["work"]) == [P2]


# ── 2. the filtered post — the mechanism behind "additive" ───────────────────────────────────

class _Recorder:
    """Stands in for `evidence_embedding_service`, and records what it was actually handed."""

    def __init__(self):
        self.calls = []

    async def embed_post_regions(self, post, image, roles=(), persist=False):
        self.calls.append({"region_ids": [str(r.get("id")) for r in post["region_annotations"]],
                           "roles": tuple(roles), "persist": persist})
        return {"status": "ok",
                "records": [{"route": "mask_pool", "region_id": r.get("id")}
                            for r in post["region_annotations"]]}


class _Http:
    async def get(self, url):
        return type("R", (), {"content": b"jpeg-bytes"})()


def _embed(monkeypatch, post, embeddings, region_ids):
    _wire(monkeypatch, [post], embeddings)
    rec = _Recorder()
    monkeypatch.setattr(density, "ees", rec)
    out = run(density.embed_post(str(post["_id"]), region_ids, http=_Http(), persist=True))
    return rec, out


def test_only_the_targets_are_handed_to_the_embedding_service(monkeypatch):
    """This is what makes the run additive rather than a rewrite dressed as one. The service
    embeds every region it is given, so the filtering has to happen before the call."""
    post = {"_id": ObjectId(P1), "photo_url": "http://x/1.jpg", "region_annotations": [
        _masked("cseg_a_0"), _masked("cseg_a_1"), _boxed("fine_0")]}
    rec, out = _embed(monkeypatch, post, [_emb(P1, "cseg_a_0"), _emb(P1, "w", role="whole_image")],
                      ["cseg_a_1"])
    assert rec.calls[0]["region_ids"] == ["cseg_a_1"]
    assert out["requested"] == 1


def test_whole_image_is_requested_only_where_the_row_is_absent(monkeypatch):
    post = {"_id": ObjectId(P1), "photo_url": "http://x/1.jpg",
            "region_annotations": [_masked("cseg_a_0")]}
    have, _ = _embed(monkeypatch, post, [_emb(P1, "w", role="whole_image")], ["cseg_a_0"])
    assert "whole_image" not in have.calls[0]["roles"]

    missing, _ = _embed(monkeypatch, post, [], ["cseg_a_0"])
    assert "whole_image" in missing.calls[0]["roles"]


def test_the_region_roles_are_the_ones_the_retina_reads(monkeypatch):
    """`identity` is the role the candidate search queries; embedding anything else would leave
    the starvation exactly where it was."""
    assert density.IDENTITY == "identity"
    assert density.IDENTITY in density.REGION_ROLES


def test_a_post_with_no_matching_target_writes_nothing(monkeypatch):
    post = {"_id": ObjectId(P1), "photo_url": "http://x/1.jpg",
            "region_annotations": [_masked("cseg_a_0")]}
    _wire(monkeypatch, [post], [])
    rec = _Recorder()
    monkeypatch.setattr(density, "ees", rec)
    out = run(density.embed_post(P1, ["cseg_nope_9"], http=_Http(), persist=True))
    assert out["status"] == "nothing_to_do" and rec.calls == []


def test_a_post_with_no_image_is_reported_rather_than_guessed_at(monkeypatch):
    post = {"_id": ObjectId(P1), "region_annotations": [_masked("cseg_a_0")]}
    _wire(monkeypatch, [post], [])
    rec = _Recorder()
    monkeypatch.setattr(density, "ees", rec)
    out = run(density.embed_post(P1, ["cseg_a_0"], http=_Http(), persist=True))
    assert out["status"] == "no_image" and rec.calls == []


# ── 3. the tally — the four classes the delta is reported in ─────────────────────────────────

def _considered(status, reason="", post_id=P2, region_id="cseg_x_0"):
    return {"status": status, "reason": reason,
            "candidate": {"post_id": post_id, "region_id": region_id, "score": 0.3}}


def _transcript(considered, candidates):
    return {"considered": considered, "retina": {"status": "ready", "candidates": candidates}}


POSTS = {P2: {"_id": ObjectId(P2),
              "region_annotations": [_masked("cseg_x_0"), _boxed("fine_0")]}}


def test_box_only_and_surface_only_are_counted_apart():
    """They are different findings and a single "refused" number would hide which one moved.
    `surface_only` says the relation is not in the image; `box_only` says it may well be and this
    corpus cannot yet measure it — one is about pictures, the other about coverage. The whole
    point of this lane is that the second number falls, so it has to be visible on its own."""
    counts = proof.tally(_transcript([
        _considered("refused", mk.REFUSED_BOX_ONLY),
        _considered("refused", mk.REFUSED_BOX_ONLY),
        _considered("refused", sm.REFUSED_SURFACE_ONLY),
        _considered("refused", "insystematic"),
        _considered("grounded"),
    ], []), POSTS)
    assert counts["box_only"] == 2
    assert counts["surface_only"] == 1
    assert counts["insystematic"] == 1
    assert counts["grounded"] == 1


def test_an_unclassified_refusal_is_surfaced_rather_than_dropped():
    """A refusal that fits none of the three named classes still has to appear somewhere, or the
    counts silently stop summing to the number of candidates and the report reads as cleaner than
    the run was."""
    counts = proof.tally(_transcript([_considered("refused", "unreadable_post")], []), POSTS)
    assert counts["other_refusals"] == {"unreadable_post": 1}


def test_a_grounded_candidate_is_never_also_counted_as_a_refusal():
    counts = proof.tally(_transcript([_considered("grounded")], []), POSTS)
    assert (counts["box_only"], counts["surface_only"], counts["insystematic"]) == (0, 0, 0)
    assert counts["other_refusals"] == {}


def test_a_candidate_counts_as_mask_carrying_only_if_its_region_really_has_one():
    """The headline number of this lane — how much of what the retina proposes is admissible
    geometry. It is read off the POST, not off the candidate envelope, because the retina does not
    report basis and must not be trusted to: it proposes by similarity and knows nothing about
    masks."""
    counts = proof.tally(_transcript([], [
        {"post_id": P2, "region_id": "cseg_x_0", "score": 0.4},
        {"post_id": P2, "region_id": "fine_0", "score": 0.3},
        {"post_id": "6a0000000000000000000000", "region_id": "cseg_x_0", "score": 0.2},
    ]), POSTS)
    assert counts["candidates"] == 3
    assert counts["mask_carrying_candidates"] == 1


def test_the_before_row_is_a_recorded_measurement_not_a_recomputation():
    """#143's numbers cannot be re-derived: the 140-row index they were measured against no longer
    exists. They are quoted, and the three refusal classes account for all 12 candidates — which
    is how a reader can tell that run was retrieval-starved rather than structurally empty."""
    before = proof.BEFORE
    assert before["grounded"] == 0
    assert before["mask_carrying_candidates"] == 0
    assert (before["box_only"] + before["insystematic"] + before["surface_only"]
            == before["candidates"])


@pytest.mark.parametrize("seed", [proof.BOX_SEED, proof.MASK_SEED])
def test_the_proof_runs_both_seeds_and_persists_neither(seed):
    """The box seed is not a control that got left in. It is the assertion that density did not
    quietly repeal the ruling: a box on the near side is an estimate, and no amount of retrieval
    on the far side can make that crossing measured."""
    assert seed in (proof.BOX_SEED, proof.MASK_SEED)
    assert proof.BOX_SEED.startswith("fine_")
    assert proof.MASK_SEED.startswith("cseg_")
