"""
HARNESS-002D — the session lives in the runs collection without lying about what a run is.

The persistence reconciliation, tested rather than asserted in prose. Every test here is a way the
shared collection could start telling one kind of thing's story with another kind's vocabulary.
"""
from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from backend.schemas.inquiry_session import (SCHEMA_VERSION, CapabilityReceipt, ClaimVerdict,
                                             ClaimVerdictOutcome, ExecutionMode, PostRef,
                                             ReceiptStatus, SemanticInquirySession, StageEvent,
                                             StageName, StageOutcome, Synthesis, SynthesisSection,
                                             canonical)
from backend.services import run_store
from backend.services.inquiry_session import ids, store

PROMPT = "How do these two interiors organise themselves, and what could follow from both?"


# ── a fake collection that resolves dotted paths, because the real one does ──

def _dig(doc, path):
    cur = doc
    for part in str(path).split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d
        return gen()


class _Result:
    def __init__(self, matched):
        self.matched_count = matched
        self.modified_count = matched


class FakeCollection:
    """Flat AND dotted key matching. A fake that only did flat keys would pass the compare-and-set
    test by matching nothing and then matching everything, which is the opposite of the guarantee."""

    def __init__(self):
        self.docs = {}
        self.writes = 0

    def _match(self, doc, query):
        return all(_dig(doc, k) == v for k, v in (query or {}).items())

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = copy.deepcopy(doc)
        self.writes += 1
        return type("R", (), {"inserted_id": doc["_id"]})()

    async def find_one(self, query, projection=None):
        for d in self.docs.values():
            if self._match(d, query):
                return copy.deepcopy(d)
        return None

    def find(self, query=None, projection=None):
        return _Cursor([copy.deepcopy(d) for d in self.docs.values()
                        if self._match(d, query or {})])

    async def update_one(self, query, update, upsert=False):
        for d in self.docs.values():
            if self._match(d, query):
                d.update(update.get("$set", {}))
                self.writes += 1
                return _Result(1)
        return _Result(0)


def a_session(**kw) -> SemanticInquirySession:
    kw.setdefault("session_id", "inqs_000000000001")
    kw.setdefault("prompt", PROMPT)
    kw.setdefault("posts", [PostRef(post_id="p1", title="one", fingerprint="abc")])
    kw.setdefault("interaction", {"state": "framing", "revision": 0})
    return SemanticInquirySession(**kw)


def a_receipt(**kw) -> CapabilityReceipt:
    kw.setdefault("receipt_id", "capr_1")
    kw.setdefault("request_ref", "obs_1")
    kw.setdefault("capability", "locate_phrase")
    kw.setdefault("execution_mode", ExecutionMode.FIXTURE)
    kw.setdefault("status", ReceiptStatus.SIMULATED)
    kw.setdefault("attempted", True)
    return CapabilityReceipt(**kw)


# ── the discriminator ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_session_document_carries_the_discriminator_and_the_envelope():
    col = FakeCollection()
    doc = await store.create(a_session(), collection=col, now="2026-08-09T00:00:00Z")
    assert doc["kind"] == store.KIND == "semantic_inquiry"
    assert doc["contract_version"] == store.CONTRACT_VERSION
    assert doc["session"]["schema_version"] == SCHEMA_VERSION
    assert doc["session"]["prompt"] == PROMPT


@pytest.mark.asyncio
async def test_the_shared_status_field_never_leaves_the_run_vocabulary():
    """The whole reason `run_store.save_view` could not be used. `list_runs`, the runs router and
    `run_store.is_answerable` all read this field as the DIRECTOR run lifecycle."""
    col = FakeCollection()
    for state in ("framing", "reading", "compiling", "awaiting_user", "ready", "executing",
                  "judging", "composing", "complete", "exhausted", "refused", "error"):
        session = a_session(session_id=f"inqs_{state}", interaction={"state": state})
        doc = await store.create(session, collection=col)
        assert doc["status"] in run_store.STATUSES, (state, doc["status"])


def test_the_session_state_vocabulary_does_not_fit_the_run_one():
    """The census claim, pinned. If these ever became the same set, the adapter is unnecessary and
    somebody should delete it rather than discover the overlap by accident."""
    session_states = {"framing", "reading", "compiling", "awaiting_user", "ready", "executing",
                      "judging", "composing", "complete", "exhausted", "refused", "error"}
    assert not session_states <= set(run_store.STATUSES)
    assert "awaiting_user" not in run_store.STATUSES
    assert "composing" not in run_store.STATUSES


def test_an_unknown_state_maps_to_running_rather_than_to_complete():
    """The only safe direction: `complete` would tell a lister the session had finished."""
    assert store.run_status_for("something_new") == "running"
    assert store.run_status_for("") == "running"
    assert store.run_status_for("awaiting_user") == "awaiting_answer"
    assert store.run_status_for("complete") == "complete"


@pytest.mark.asyncio
async def test_a_director_run_in_the_same_collection_is_not_loadable_as_a_session():
    """Without the discriminator on the READ, a run id would load a run document, find no session
    key, and produce a validation error about a missing prompt — which reads as a corrupt session
    rather than as the wrong kind of thing."""
    col = FakeCollection()
    await col.insert_one(run_store.new_run_doc(run_id="run_1", spec={"prompt": "x"}))
    await store.create(a_session(), collection=col)
    with pytest.raises(store.SessionNotFound):
        await store.load("run_1", collection=col)
    assert (await store.load("inqs_000000000001", collection=col)).prompt == PROMPT


@pytest.mark.asyncio
async def test_listing_sessions_does_not_return_director_runs():
    col = FakeCollection()
    await col.insert_one(run_store.new_run_doc(run_id="run_1", spec={"prompt": "x"}))
    await store.create(a_session(), collection=col)
    rows = await store.list_sessions(collection=col)
    assert [r["_id"] for r in rows] == ["inqs_000000000001"]


@pytest.mark.asyncio
async def test_a_missing_session_raises_rather_than_returning_none():
    with pytest.raises(store.SessionNotFound):
        await store.load("inqs_nope", collection=FakeCollection())


# ── compare-and-set ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_write_at_the_expected_revision_lands():
    col = FakeCollection()
    session = a_session(revision=0)
    await store.create(session, collection=col)
    advanced = session.model_copy(update={"revision": 1})
    await store.save(advanced, expected_revision=0, collection=col)
    assert (await store.load(session.session_id, collection=col)).revision == 1


@pytest.mark.asyncio
async def test_a_write_at_a_stale_revision_is_refused_and_writes_nothing():
    """Two clients answering one decision would otherwise both read revision 3, both append, and
    both write revision 4 — and the second would erase the first person's answer from a history
    whose whole promise is that it is append-only."""
    col = FakeCollection()
    session = a_session(revision=0)
    await store.create(session, collection=col)
    await store.save(session.model_copy(update={"revision": 1}), expected_revision=0,
                     collection=col)
    before = col.writes
    with pytest.raises(store.SessionWriteFailed):
        await store.save(session.model_copy(update={"revision": 1}), expected_revision=0,
                         collection=col)
    assert col.writes == before
    assert (await store.load(session.session_id, collection=col)).revision == 1


@pytest.mark.asyncio
async def test_a_save_without_an_expected_revision_still_requires_the_session_to_exist():
    with pytest.raises(store.SessionWriteFailed):
        await store.save(a_session(), collection=FakeCollection())


# ── round trip and encoding ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_full_session_round_trips_through_the_store_losslessly():
    col = FakeCollection()
    session = a_session(
        inquiry_id="inq_1", revision=2,
        frame={"schema_version": "inquiry-frame.v1", "prompt": PROMPT},
        graph={"schema_version": "semantic-inquiry-graph.v1", "claims": [{"claim_id": "clm_a"}]},
        interaction={"state": "complete", "revision": 2, "events": [{"kind": "session_opened"}]},
        selected_observable_ref="obs_1",
        capability_receipts=[a_receipt()],
        verdicts=[ClaimVerdict(verdict_id="vrd_1", claim_ref="clm_a",
                               outcome=ClaimVerdictOutcome.INTERPRETIVE_ONLY,
                               why="nothing measured bears on it")],
        synthesis=Synthesis(synthesis_id="syn_1", sections=[
            SynthesisSection(section_id="sec_1", text="a provisional reading",
                             claim_refs=["clm_a"])]),
        stages=[StageEvent(event_id="stg_1", stage=StageName.THEORIST,
                           outcome=StageOutcome.COMPLETED)],
        gaps=["no instrument measures composure"], stop_reason="an answer was composed")
    await store.create(session, collection=col)
    loaded = await store.load(session.session_id, collection=col)
    assert loaded.model_dump(mode="json") == session.model_dump(mode="json")


@pytest.mark.asyncio
async def test_a_cycle_in_a_model_provenance_is_broken_and_named_rather_than_crashing_the_write():
    """Reusing `run_store.acyclic` rather than writing a second projection. A session embeds three
    lanes' snapshots and a model's free-form provenance, which is exactly the shape that acquires a
    cycle by accident — and argue mode died of one for as long as argue mode existed."""
    col = FakeCollection()
    graph = {"provenance": {}}
    graph["provenance"]["self"] = graph
    doc = await store.create(a_session(graph=graph), collection=col)
    assert doc["encoding_repairs"], "the cycle was neither broken nor reported"
    assert run_store.CYCLE_MARKER in str(doc["session"])


# ── the firewall, at envelope scale ──────────────────────────────────────────

def test_a_fixture_receipt_cannot_declare_itself_usable_as_evidence():
    with pytest.raises(ValidationError, match="unlabelled measurement"):
        a_receipt(usable_as_evidence=True)


def test_a_fixture_receipt_cannot_claim_it_ran_live():
    with pytest.raises(ValidationError, match="may not contradict"):
        a_receipt(status=ReceiptStatus.LIVE)


def test_an_unavailable_receipt_cannot_claim_it_was_attempted():
    """`attempted` is the only field separating an instrument that was not there from one that ran
    and found nothing."""
    with pytest.raises(ValidationError, match="Nothing was attempted"):
        a_receipt(status=ReceiptStatus.UNAVAILABLE, attempted=True,
                  execution_mode=ExecutionMode.LIVE)


def test_evidence_minted_from_a_fixture_receipt_is_refused_by_the_envelope():
    """The other direction. A receipt cannot see the evidence list, so the two guards are not
    redundant."""
    with pytest.raises(ValidationError, match="cannot become the thing"):
        a_session(capability_receipts=[a_receipt()],
                  evidence=[{"evidence_id": "evd_1", "receipt_ref": "capr_1"}])


def test_evidence_declaring_fixture_execution_is_refused_whatever_it_points_at():
    with pytest.raises(ValidationError, match="execution_mode `fixture`"):
        a_session(evidence=[{"evidence_id": "evd_1", "execution_mode": "fixture"}])


def test_a_verdict_claiming_support_must_cite_evidence():
    with pytest.raises(ValidationError, match="A receipt is not evidence"):
        ClaimVerdict(verdict_id="vrd_1", claim_ref="clm_a",
                     outcome=ClaimVerdictOutcome.SUPPORTED_BY_EVIDENCE, why="the receipt came back",
                     receipt_refs=["capr_1"])


def test_a_verdict_may_cite_a_receipt_without_claiming_support():
    verdict = ClaimVerdict(verdict_id="vrd_1", claim_ref="clm_a",
                           outcome=ClaimVerdictOutcome.INTERPRETIVE_ONLY,
                           why="a route was invoked and nothing was measured",
                           receipt_refs=["capr_1"])
    assert verdict.evidence_refs == []


def test_two_verdicts_for_one_claim_are_refused():
    with pytest.raises(ValidationError, match="one verdict or none"):
        a_session(verdicts=[
            ClaimVerdict(verdict_id="vrd_1", claim_ref="clm_a",
                         outcome=ClaimVerdictOutcome.UNRESOLVED, why="a"),
            ClaimVerdict(verdict_id="vrd_2", claim_ref="clm_a",
                         outcome=ClaimVerdictOutcome.NOT_INVESTIGATED, why="b")])


def test_a_section_rendering_as_measured_must_cite_evidence():
    with pytest.raises(ValidationError, match="exists to make impossible"):
        SynthesisSection(section_id="sec_1", text="the ceiling is one surface", status="measured")


def test_a_session_with_no_prompt_is_refused():
    with pytest.raises(ValidationError, match="inquiry into nothing"):
        a_session(prompt="   ")


# ── replay ───────────────────────────────────────────────────────────────────

def test_canonical_strips_every_timestamp_wherever_it_is_nested():
    """Lane A shipped a `canonical()` that missed a second `requested_at` one level down and the
    fixtures caught it. This one walks."""
    session = a_session(
        frame={"provenance": {"framed_at": "2026-01-01T00:00:00Z", "producer": "x"}},
        graph={"provenance": {"compiled_at": "2026-01-01T00:00:00Z",
                              "theorist": {"requested_at": "2026-01-01T00:00:00Z"}}},
        interaction={"state": "framing", "events": [{"at": "2026-01-01T00:00:00Z"}]},
        capability_receipts=[a_receipt(latency_ms=12.5)],
        stages=[StageEvent(event_id="stg_1", stage=StageName.FRAMER,
                           outcome=StageOutcome.COMPLETED, at="2026-01-01T00:00:00Z")])
    data = canonical(session)
    assert "2026-01-01T00:00:00Z" not in str(data)
    assert "latency_ms" not in str(data)
    # And nothing else went with them.
    assert data["frame"]["provenance"]["producer"] == "x"
    assert data["stages"][0]["stage"] == "framer"


def test_two_sessions_of_identical_content_are_canonically_identical():
    a = a_session(provenance={"created_at": "2026-01-01T00:00:00Z"})
    b = a_session(provenance={"created_at": "2099-12-31T23:59:59Z"})
    assert canonical(a) == canonical(b)


def test_the_session_id_is_the_one_id_derived_from_a_clock():
    from datetime import datetime, timezone
    early = datetime(2026, 1, 1, tzinfo=timezone.utc)
    late = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert ids.session_id(PROMPT, ["p1"], now=early) != ids.session_id(PROMPT, ["p1"], now=late)
    # Everything else is content-derived and stable.
    assert ids.verdict_id("inqs_1", "clm_a") == ids.verdict_id("inqs_1", "clm_a")
    assert ids.receipt_id("inqs_1", "obs_1", "locate_phrase") == \
        ids.receipt_id("inqs_1", "obs_1", "locate_phrase")
    assert ids.section_id("inqs_1", "h", "t") != ids.section_id("inqs_1", "h", "different")


def test_the_order_the_posts_were_listed_in_is_not_part_of_the_session_s_identity():
    """Two people who picked the same images picked the same corpus. What separates their sessions
    is the clock, tested above — not the order a form serialised a multi-select in."""
    from datetime import datetime, timezone
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert ids.session_id(PROMPT, ["p1", "p2"], now=at) == \
        ids.session_id(PROMPT, ["p2", "p1"], now=at)
    assert ids.session_id(PROMPT, ["p1", "p2"], now=at) != \
        ids.session_id(PROMPT, ["p1", "p3"], now=at)
    assert ids.session_id(PROMPT, ["p1"], now=at).startswith("inqs_")


def test_a_synthesis_composed_after_a_further_decision_is_a_different_answer():
    assert ids.synthesis_id("inqs_1", 2) != ids.synthesis_id("inqs_1", 3)
