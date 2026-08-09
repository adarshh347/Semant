"""
HARNESS-002D — the horizontal proofs: replay, round-trip, invariance and no topic branch.

The per-stage suites prove each link. These prove the properties that only exist across the whole
chain, and the ones a reader of any single module could not check:

    a replay of a frozen session is byte-identical, and makes zero live calls
    a session survives the store and comes back the same object
    both fixtures — an art comparison and something with no shared vocabulary — run the same chain
    no production source names either fixture's subject
    nothing anywhere becomes evidence
"""
from __future__ import annotations

import ast
import copy
import json
import pathlib

import pytest

from backend.schemas.inquiry_session import (SemanticInquirySession, VOLATILE_FIELDS,
                                             SUPPORTED_VERDICTS, canonical)
from backend.services.inquiry_session import coordinator, judge as J, store, view
from backend.services.inquiry_session.capability import LockedFixtureCapability
from backend.services.inquiry_session.composer import DeterministicComposer
from backend.tests.fixtures import inquiry_session_fixtures as F

AT = "2026-08-09T00:00:00+00:00"
ROOT = pathlib.Path(__file__).resolve().parents[2]


def stages():
    return F.stages_for(F.FIXTURES[0], capability=LockedFixtureCapability(), judge=J.judge,
                        composer=DeterministicComposer(), clock=F.frozen_clock(AT))


def whole_chain(name=None, mode="consult", *, session_id="inqs_proof", answer=0, kind=None):
    """Prompt → pause → answer → receipt → verdicts → answer. The vertical, in one call."""
    name = name or F.FIXTURES[0]
    bound = F.stages_for(name, capability=LockedFixtureCapability(), judge=J.judge,
                         composer=DeterministicComposer(), clock=F.frozen_clock(AT))
    session = coordinator.new_session(prompt=F.prompt_for(name), refs=F.post_refs(name),
                                      mode=mode, session_id=session_id, now=AT)
    session = coordinator.begin(session, bound)
    if session.awaiting_user:
        request = coordinator.machine.from_dict(session.interaction).open_decision
        payload = {"response_id": "resp_proof", "session_id": session.session_id,
                   "decision_id": request.decision_id, "expected_revision": session.revision,
                   "at": AT, "kind": kind or "select_option"}
        if not kind:
            payload["option_id"] = request.options[answer].option_id
        session = coordinator.resume(session, payload, bound)
    return session, bound


# ── replay ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
@pytest.mark.parametrize("mode", ["consult", "auto"])
def test_a_replay_of_a_frozen_session_is_byte_identical(name, mode):
    """The whole reason the ids are content-derived and the clock is handed in.

    A diff between two runs should contain what actually differed. Before the coordinator passed
    the framer its clock, it contained every id in the graph instead, because `mint_inquiry_id`
    hashes the moment and every compiler id is keyed on the inquiry.
    """
    first, _ = whole_chain(name, mode)
    second, _ = whole_chain(name, mode)
    assert canonical(first) == canonical(second)


@pytest.mark.parametrize("name", F.FIXTURES)
def test_a_replay_makes_zero_live_model_calls(name):
    session, _ = whole_chain(name)
    provenance = session.graph.get("provenance") or {}
    for role in ("theorist", "compiler"):
        receipt = provenance.get(role) or {}
        assert receipt.get("call_topology") in ("replay", "unavailable", None), role
        assert int(receipt.get("call_count") or 0) == 0, role


def test_the_replay_comparison_can_actually_fail():
    """The negative control. A comparison that passes on two different sessions proves nothing."""
    a, _ = whole_chain(F.FIXTURES[0])
    b, _ = whole_chain(F.FIXTURES[1])
    assert canonical(a) != canonical(b)


def test_only_the_declared_volatile_fields_are_excluded_from_the_comparison():
    """`canonical` is allowed to drop clocks and latencies. Anything else it dropped would be a
    difference the replay proof could never see."""
    session, _ = whole_chain()
    full = json.dumps(session.model_dump(mode="json"), sort_keys=True)
    stripped = json.dumps(canonical(session), sort_keys=True)
    assert len(stripped) < len(full)
    for key in ("session_id", "prompt", "graph", "verdicts", "synthesis", "capability_receipts"):
        assert key in stripped


def test_the_two_runs_that_differ_only_in_a_clock_still_compare_equal():
    a, _ = whole_chain()
    b_stages = F.stages_for(F.FIXTURES[0], capability=LockedFixtureCapability(), judge=J.judge,
                            composer=DeterministicComposer(),
                            clock=F.frozen_clock("2027-01-01T00:00:00+00:00"))
    b = coordinator.new_session(prompt=F.prompt_for(F.FIXTURES[0]), refs=F.post_refs(F.FIXTURES[0]),
                                mode="consult", session_id="inqs_proof", now=AT)
    b = coordinator.begin(b, b_stages)
    request = coordinator.machine.from_dict(b.interaction).open_decision
    b = coordinator.resume(b, {"response_id": "resp_proof", "session_id": b.session_id,
                               "decision_id": request.decision_id, "expected_revision": b.revision,
                               "kind": "select_option", "option_id": request.options[0].option_id,
                               "at": "2027-01-01T00:00:00+00:00"}, b_stages)
    # NOT equal, and that is correct: the inquiry id is minted from the moment, so a session run at
    # a different time is a different session with different ids. What `canonical` excludes is the
    # timestamps themselves, never the identity they produced — and pretending otherwise would let
    # a genuinely different graph pass a replay check.
    assert canonical(a) != canonical(b)
    assert set(VOLATILE_FIELDS) >= {"at", "created_at", "updated_at", "latency_ms"}


# ── the round trip ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_store_round_trip_loses_nothing_and_invents_nothing(name):
    session, _ = whole_chain(name)
    doc = store.new_session_doc(session, now=AT)
    restored = SemanticInquirySession.model_validate(copy.deepcopy(doc["session"]))
    assert restored.model_dump(mode="json") == session.model_dump(mode="json")
    assert doc["encoding_repairs"] == [], "a healthy session needed its payload repaired"


@pytest.mark.parametrize("name", F.FIXTURES)
def test_the_wire_projection_loses_no_claim_observable_or_section(name):
    session, bound = whole_chain(name)
    body = view.session_view(session, servable_classes=coordinator.servable_classes(bound))
    assert len(body["graph"]["claims"]) == len(session.graph["claims"])
    assert len(body["graph"]["observables"]) == len(session.graph["observables"])
    assert len(body["verdicts"]) == len(session.verdicts)
    assert len(body["synthesis"]["sections"]) == len(session.synthesis.sections)
    assert body["prompt"] == session.prompt


def test_the_projection_invents_no_reference_the_session_does_not_carry():
    session, bound = whole_chain()
    body = view.session_view(session, servable_classes=coordinator.servable_classes(bound))
    claims = {c["claim_id"] for c in body["graph"]["claims"]}
    for observable in body["graph"]["observables"]:
        assert observable["claim_ref"] in claims
    for edge in body["graph"]["claim_edges"]:
        assert edge["from_claim"] in claims and edge["to_claim"] in claims
    for verdict in body["verdicts"]:
        assert verdict["claim_ref"] in claims


# ── nothing becomes evidence ─────────────────────────────────────────────────

@pytest.mark.parametrize("name", F.FIXTURES)
@pytest.mark.parametrize("mode", ["consult", "auto"])
def test_nothing_anywhere_in_a_finished_session_is_evidence(name, mode):
    session, bound = whole_chain(name, mode)
    body = view.session_view(session, servable_classes=coordinator.servable_classes(bound))

    assert body["evidence"] == []
    assert all(r["usable_as_evidence"] is False for r in body["capability_receipts"])
    assert all(r["execution_mode"] == "fixture" for r in body["capability_receipts"])
    assert not [v for v in session.verdicts if v.outcome in SUPPORTED_VERDICTS]
    assert all(s["evidence_refs"] == [] for s in body["synthesis"]["sections"])
    assert all(s["status"] not in ("measured", "visible") for s in body["synthesis"]["sections"])


@pytest.mark.parametrize("name", F.FIXTURES)
def test_no_claim_status_was_promoted_anywhere_along_the_chain(name):
    """The compiler's ceiling is `interpretive | sourced | uncertain`, and nothing downstream —
    not the judge, not the composer, not the projection — may raise one."""
    session, bound = whole_chain(name)
    body = view.session_view(session, servable_classes=coordinator.servable_classes(bound))
    for claim in body["graph"]["claims"]:
        assert claim["status"] in ("interpretive", "sourced", "uncertain"), claim


# ── the two domains run the same chain ───────────────────────────────────────

def test_both_fixtures_take_the_same_stages_in_the_same_order():
    a, _ = whole_chain(F.FIXTURES[0])
    b, _ = whole_chain(F.FIXTURES[1])
    assert [(e.stage.value, e.outcome.value) for e in a.stages] == \
           [(e.stage.value, e.outcome.value) for e in b.stages]


def test_the_two_fixtures_really_are_different_inquiries():
    """The negative control for the test above: identical stage traces would also be what you got
    from a chain that ignored its input."""
    a, _ = whole_chain(F.FIXTURES[0])
    b, _ = whole_chain(F.FIXTURES[1])
    assert not {c["claim_id"] for c in a.graph["claims"]} & {c["claim_id"] for c in b.graph["claims"]}
    assert a.prompt != b.prompt
    assert {s.heading for s in a.synthesis.sections} == {s.heading for s in b.synthesis.sections}


def test_a_rejected_fork_takes_the_same_chain_to_a_different_and_honest_end():
    session, _ = whole_chain(kind="reject_all")
    assert session.capability_receipts == []
    assert session.verdicts, "the claims still deserve verdicts when nobody chose a route"
    assert not [v for v in session.verdicts if v.outcome.value == "unresolved"], \
        "nothing was invoked, so nothing is 'we asked and got nothing'"
    assert session.synthesis is not None


# ── no topic branch ──────────────────────────────────────────────────────────

def _production_sources():
    roots = [ROOT / "backend" / "services" / "inquiry_session",
             ROOT / "backend" / "schemas" / "inquiry_session.py",
             ROOT / "backend" / "routers" / "inquiries.py",
             ROOT / "scripts" / "inquiry_rehearse.py",
             ROOT / "scripts" / "inquiry_contract_sample.py",
             ROOT / "frontend" / "src" / "inquiryWorkbench"]
    out = []
    for root in roots:
        if root.is_file():
            out.append(root)
        else:
            out += [p for p in root.rglob("*")
                    if p.suffix in (".py", ".js", ".jsx", ".css") and "test" not in p.name
                    and "__pycache__" not in str(p) and "Fixtures" not in p.name]
    return out


def test_no_production_source_in_this_lane_names_either_fixtures_subject():
    nouns = F.topic_nouns()
    assert len(nouns) >= 8
    sources = _production_sources()
    assert len(sources) >= 20, "the scan is pointed at nothing"
    offences = [f"{p.relative_to(ROOT)}: {noun}"
                for p in sources for noun in nouns
                if noun.lower() in p.read_text(encoding="utf-8").lower()]
    assert offences == [], offences


def test_that_scan_can_fail(tmp_path):
    """The negative control. A scan matching nothing is indistinguishable from one pointed at the
    wrong directory — which is the exact defect the pixel-honesty harness found in itself."""
    decoy = tmp_path / "decoy.py"
    decoy.write_text(f"SPECIAL_CASE = {F.topic_nouns()[0]!r}\n", encoding="utf-8")
    text = decoy.read_text(encoding="utf-8").lower()
    assert any(noun.lower() in text for noun in F.topic_nouns())


#: What Phase 2 would reach for, and Phase 1 may not. Matched against CODE — import targets, names
#: and attributes — and never against prose: every one of these words appears in this lane's
#: docstrings, saying that the thing is not touched, and a scan that counted those would force the
#: explanations out of the files that most need them.
_PHASE_TWO_REACH = ("segmentation_service", "dinov2", "sam3", "actuators", "percept", "atlas",
                    "visual_marks", "region_annotations", "curator", "agent_memory", "organ")


def _code_names(tree):
    """Every name this module could reach something through. Strings and docstrings excluded."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def test_the_lane_reaches_no_actuator_organ_agent_or_ledger():
    """Structural. Phase 2 is not authorized here, and the way to keep it out is to have no name
    that could reach it rather than an instruction not to write one."""
    package = ROOT / "backend" / "services" / "inquiry_session"
    scanned = 0
    for path in package.glob("*.py"):
        names = _code_names(ast.parse(path.read_text(encoding="utf-8")))
        scanned += 1
        for name in names:
            for token in _PHASE_TWO_REACH:
                assert token not in name.lower(), f"{path.name} reaches {name!r}"
    assert scanned >= 8, "the scan is pointed at nothing"


def test_that_reach_scan_can_fail(tmp_path):
    """The negative control, and it matters twice over here: the scan deliberately ignores prose,
    so a bug that made it ignore everything would look exactly like a clean lane."""
    decoy = tmp_path / "decoy.py"
    decoy.write_text("from backend.services import segmentation_service\n", encoding="utf-8")
    names = _code_names(ast.parse(decoy.read_text(encoding="utf-8")))
    assert any(t in n.lower() for n in names for t in _PHASE_TWO_REACH)


def test_the_reach_scan_reads_code_and_not_comments(tmp_path):
    """The other direction: a file that only MENTIONS an actuator in prose is clean."""
    innocent = tmp_path / "innocent.py"
    innocent.write_text('"""No percept, mark or Atlas edge is written here."""\nX = 1\n',
                        encoding="utf-8")
    names = _code_names(ast.parse(innocent.read_text(encoding="utf-8")))
    assert not any(t in n.lower() for n in names for t in _PHASE_TWO_REACH)


def test_the_only_collection_this_lane_names_is_the_runs_collection():
    package = ROOT / "backend" / "services" / "inquiry_session"
    named = set()
    for path in package.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "backend.database":
                named |= {a.name for a in node.names}
    assert named <= {"run_collection", "post_collection"}, named
    assert "inquiry_runs" not in " ".join(p.read_text(encoding="utf-8")
                                          for p in package.glob("*.py"))


# ── the rehearsal script ─────────────────────────────────────────────────────

def test_the_rehearsal_script_is_offline_and_opens_no_database():
    source = (ROOT / "scripts" / "inquiry_rehearse.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in imported if m.startswith("backend.database")]
    assert "post_collection" not in source
