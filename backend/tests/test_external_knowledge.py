"""
CIRCUIT-003 M6 — the external-knowledge actuator and the epistemic `sourced` wall.

No network. Every retrieval test injects a fake provider, so what is under test is the
DISCIPLINE — a claim cannot exist without a source, a quotation cannot exist that is not in
the document, and a sourced claim cannot become a visible one — rather than Wikipedia's uptime.

The four the build gate names, and where they live below:
  a research claim always carries a real source   → §2, §3
  no findable source → refusal                    → §4
  `sourced` cannot be overwritten                 → §5 (three independent routes, all blocked)
  no fabricated citations                         → §3 (the verbatim-span guard)
"""
from __future__ import annotations

import dataclasses

import pytest

from backend.services import epistemics
from backend.services import external_source_service as ess
from backend.services.epistemics import EpistemicStatus, EpistemicViolation
from backend.services.director import capabilities as caps
from backend.services.director import real_actuators as ra
from backend.services.director.capabilities import Resource
from backend.services.director.execution import EMPTY, OK, UNAVAILABLE
from backend.services.director.memory import build_memory
from backend.services.director.plan import REFUSED_MISSING_PARAM, Step, resolve


# ── fixtures: a library that is entirely under our control ───────────────────

SCHINKEL_TEXT = (
    "The Altes Museum is a museum building on Museum Island in Berlin. "
    "Karl Friedrich Schinkel conceived the building as a civic temple in which citizens "
    "of the young state would meet art on equal terms. "
    "Its rotunda quotes the Pantheon and was intended to hold the visitor still before "
    "the collection began. "
    "Unrelated sentence about the weather in a coastal town far from any museum."
)


def _doc(text=SCHINKEL_TEXT, *, title="Altes Museum", url="https://en.wikipedia.org/wiki/Altes_Museum",
         revision="12345"):
    return ess.SourceDocument(
        text=text,
        citation=ess.Citation(title=title, url=url, publisher="Wikipedia",
                              source_id="wikipedia:1", revision=revision))


class FakeProvider:
    """A library with exactly the documents a test says it has."""
    name = "fake"

    def __init__(self, docs=None, *, available=True, raises=None):
        self.docs = list(docs or [])
        self.available = available
        self.raises = raises
        self.queries = []

    def is_available(self):
        return self.available

    def search(self, topic, *, limit=3):
        self.queries.append(topic)
        if self.raises:
            raise self.raises
        return self.docs[:limit]


TOPIC = "Schinkel Altes Museum civic intent"


# ── 1. the actuator is in the catalogue, and produces the right KIND ─────────

def test_actuator_is_registered_and_needs_a_topic():
    a = caps.get("historical_source")
    assert a is not None
    assert a.capability == "external_source"
    assert a.authors_geometry is False
    # It requires a PHRASE and nothing else — in particular NOT the image. An actuator that
    # cannot see the picture cannot accidentally describe it.
    assert [r.kind for r in a.requires] == [Resource.PHRASE]


def test_actuator_produces_source_and_never_a_mark():
    """The wall, expressed in the catalogue. A citation is not evidence on the image."""
    a = caps.get("historical_source")
    assert a.produces == (Resource.SOURCE,)
    for forbidden in (Resource.MARK, Resource.REGION, Resource.GROUND, Resource.PERCEPT):
        assert forbidden not in a.produces
    # and nothing else in the catalogue can be satisfied BY a source
    assert caps.producers_of(Resource.SOURCE) == ("historical_source",)


def test_a_source_never_satisfies_a_mark_hungry_step():
    """The wall at plan time: research → relate is refused, because a quotation is not a mark.

    This is the one that would catch a future edit making `historical_source` produce MARK to
    'make chains work' — the chain would start working, and the system would start relating
    citations to masks as though they were the same kind of thing.
    """
    memory = build_memory(image_ref="img", phrase=TOPIC)
    plan = resolve([Step(actuator="historical_source", id="s1"),
                    Step(actuator="connect_marks", id="s2")],
                   memory, intention="research then relate")
    assert [s.id for s in plan.steps] == ["s1"]
    assert [r.step.id for r in plan.refused] == ["s2"]
    assert plan.refused[0].reason == "missing_input"


def test_no_topic_is_refused_before_anything_runs():
    """The research twin of 'no ground → no mark', enforced at plan time."""
    plan = resolve([Step(actuator="historical_source", id="s1")],
                   build_memory(image_ref="img"), intention="research nothing")
    assert plan.steps == ()
    assert plan.refused[0].reason == REFUSED_MISSING_PARAM


# ── 2. a claim always carries a real source ──────────────────────────────────

def test_citation_requires_a_followable_url():
    with pytest.raises(EpistemicViolation):
        ess.Citation(title="Altes Museum", url="", publisher="Wikipedia", source_id="x")
    with pytest.raises(EpistemicViolation):
        ess.Citation(title="  ", url="https://example.org/a", publisher="W", source_id="x")


def test_statement_cannot_exist_without_a_citation():
    with pytest.raises(EpistemicViolation):
        ess.SourcedStatement(text="Schinkel meant a civic temple.", citation=None, confidence=0.9)


def test_every_retrieved_statement_carries_a_citation():
    result = ess.retrieve(TOPIC, provider=FakeProvider([_doc()]))
    assert result.ok
    for s in result.statements:
        assert isinstance(s.citation, ess.Citation)
        assert s.citation.url.startswith("https://")
        assert s.citation.title
        assert s.citation.revision == "12345"     # the quote is pinned to a version


# ── 3. no fabricated citations: a quote must be IN the document ──────────────

def test_a_statement_not_in_the_source_is_refused():
    """The anti-fabrication guard. A plausible sentence plus a real url is the exact shape of
    a fabricated citation, and it cannot be constructed."""
    doc = _doc()
    with pytest.raises(EpistemicViolation) as exc:
        ess.SourcedStatement.from_document(
            doc, "Schinkel also designed the Eiffel Tower.", confidence=0.99)
    assert "not in the source" in str(exc.value)


def test_every_quoted_statement_is_verbatim():
    doc = _doc()
    result = ess.retrieve(TOPIC, provider=FakeProvider([doc]))
    assert result.statements
    for s in result.statements:
        assert s.text in doc.text


def test_irrelevant_sentences_are_not_quoted():
    result = ess.retrieve(TOPIC, provider=FakeProvider([_doc()]))
    assert not any("weather in a coastal town" in s.text for s in result.statements)


# ── 4. no findable source → refusal ──────────────────────────────────────────

def test_no_document_found_is_a_refusal_not_a_guess():
    result = ess.retrieve("qwertyuiop zxcvbnm asdfgh", provider=FakeProvider([]))
    assert result.status == ess.RETRIEVAL_EMPTY
    assert result.statements == ()
    assert not result.ok


def test_documents_with_nothing_relevant_refuse():
    doc = _doc(text="A coastal town has weather. The weather changes with the season. "
                    "Nothing here concerns any architect or any building at all.")
    result = ess.retrieve(TOPIC, provider=FakeProvider([doc]))
    assert result.status == ess.RETRIEVAL_EMPTY
    assert result.documents_seen == 1          # it looked, and says so


def test_provider_down_is_unavailable_not_empty():
    """'The library is unreachable' must never read as 'there is nothing on this'."""
    assert ess.retrieve(TOPIC, provider=FakeProvider(available=False)).status \
        == ess.RETRIEVAL_UNAVAILABLE
    assert ess.retrieve(TOPIC, provider=FakeProvider(raises=TimeoutError("slow"))).status \
        == ess.RETRIEVAL_UNAVAILABLE


def test_empty_topic_retrieves_nothing():
    prov = FakeProvider([_doc()])
    assert ess.retrieve("   ", provider=prov).status == ess.RETRIEVAL_EMPTY
    assert prov.queries == []                  # it did not even look


# ── 5. the wall: `sourced` cannot become `visible` or `measured` ─────────────

def test_status_is_read_only_on_the_statement_object():
    """Route 1: the object itself. Frozen dataclass + property = no assignment exists."""
    s = ess.SourcedStatement.from_document(
        _doc(), "Karl Friedrich Schinkel conceived the building as a civic temple in which "
                "citizens of the young state would meet art on equal terms.", confidence=0.8)
    assert s.epistemic_status is EpistemicStatus.SOURCED
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        s.epistemic_status = EpistemicStatus.VISIBLE
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.citation = None


@pytest.mark.parametrize("target", [EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED,
                                    EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN])
def test_retag_refuses_to_launder_a_sourced_claim(target):
    """Route 2: the supported mutation API refuses every crossing."""
    d = ess.SourcedStatement.from_document(
        _doc(), "The Altes Museum is a museum building on Museum Island in Berlin.",
        confidence=0.6).to_descriptor(run_id="run1", provider="fake")
    with pytest.raises(EpistemicViolation):
        epistemics.retag(d, target)
    assert d[epistemics.STATUS_KEY] == "sourced"       # and the original is untouched


def test_guard_catches_a_hand_edited_descriptor():
    """Route 3: someone bypasses `retag` and edits the dict. Caught before it is published."""
    d = ess.SourcedStatement.from_document(
        _doc(), "The Altes Museum is a museum building on Museum Island in Berlin.",
        confidence=0.6).to_descriptor(run_id="run1", provider="fake")
    d[epistemics.STATUS_KEY] = "visible"
    with pytest.raises(EpistemicViolation):
        epistemics.guard([d])


def test_source_ref_is_stable_across_processes():
    """The circuit keys idempotency on `source_ref`, so the same quotation from the same source
    must produce the same ref every time — including in a fresh interpreter, which rules out
    Python's salted `hash()`."""
    import subprocess
    import sys

    quote = "The Altes Museum is a museum building on Museum Island in Berlin."
    mine = ess.SourcedStatement.from_document(_doc(), quote, confidence=0.5) \
        .to_descriptor(run_id="r", provider="fake")["source_ref"]
    script = (
        "from backend.services import external_source_service as e;"
        "c=e.Citation(title='Altes Museum',url='https://en.wikipedia.org/wiki/Altes_Museum',"
        "publisher='Wikipedia',source_id='wikipedia:1',revision='12345');"
        f"d=e.SourceDocument(text={SCHINKEL_TEXT!r},citation=c);"
        f"print(e.SourcedStatement.from_document(d,{quote!r},confidence=0.5)"
        ".to_descriptor(run_id='r',provider='fake')['source_ref'])")
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         env={"PYTHONHASHSEED": "1", "PATH": "/usr/bin:/bin",
                              "PYTHONPATH": __import__("os").getcwd()})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == mine


def test_guard_rejects_a_sourced_statement_with_no_citation():
    d = {"type": epistemics.SOURCED_STATEMENT_TYPE, epistemics.STATUS_KEY: "sourced",
         "citation": {}}
    with pytest.raises(EpistemicViolation):
        epistemics.guard([d])


def test_guard_rejects_an_unknown_status():
    with pytest.raises(EpistemicViolation):
        epistemics.guard([{"type": "brush_field", epistemics.STATUS_KEY: "obvious"}])


def test_retag_within_the_image_statuses_is_allowed():
    """The wall is one-directional and narrow. A producer sharpening its own reading is
    nobody's business but its own — over-blocking would make the guard something people
    route around rather than use."""
    d = {"producer": "rhythm", "type": "brush_field", epistemics.STATUS_KEY: "uncertain"}
    assert epistemics.retag(d, EpistemicStatus.MEASURED)[epistemics.STATUS_KEY] == "measured"


# ── 6. the runner: quarantined, tagged, and invisible to the mark path ───────

@pytest.fixture
def sourced_ctx(monkeypatch):
    """Run `historical_source` against a fake library, in-process."""
    prov = FakeProvider([_doc()])
    monkeypatch.setattr(ess, "default_provider", lambda: prov)
    ctx = ra.ExecutionContext(post_id="p1", post={"photo_url": "x"})
    yield ctx, prov
    ctx.close()


def test_runner_produces_quarantined_sourced_statements(sourced_ctx):
    ctx, prov = sourced_ctx
    runner = ra.RealActuatorRunner("historical_source", ctx)
    result = runner(Step(actuator="historical_source", id="s1", params={"phrase": TOPIC}),
                    build_memory(image_ref="img", phrase=TOPIC))

    assert result.status == OK
    assert prov.queries[0] == TOPIC            # the curator's words are asked first
    assert ctx.suggestions
    for s in ctx.suggestions:
        assert s["type"] == epistemics.SOURCED_STATEMENT_TYPE
        assert s[epistemics.STATUS_KEY] == "sourced"
        assert s["citation"]["url"]
        assert s["geometry"] is None            # no extent — it is not on the image
        assert s["provenance"]["producer"] == "historical_source"
    # It produced SOURCE, and only SOURCE.
    assert set(result.produced) == {Resource.SOURCE}


def test_sourced_statements_are_invisible_to_the_mark_path(sourced_ctx):
    """The wall inside the runner. `connect_marks` and `compose_percept` read
    `_quarantined_marks()`; a citation must not appear there, or a plan could relate a
    quotation to a mask as though both were evidence on the image."""
    ctx, _ = sourced_ctx
    ra.RealActuatorRunner("historical_source", ctx)(
        Step(actuator="historical_source", id="s1", params={"phrase": TOPIC}),
        build_memory(image_ref="img", phrase=TOPIC))
    assert ctx.suggestions                      # they are in the quarantine …
    assert ra._quarantined_marks(ctx) == []     # … and none of them is a mark


def test_a_source_step_never_advances_the_evidence_layer(sourced_ctx):
    """Producing SOURCE leaves working memory's evidence counts exactly where they were."""
    ctx, _ = sourced_ctx
    memory = build_memory(image_ref="img", phrase=TOPIC)
    before = memory.available()
    after = memory.evolve((Resource.SOURCE,) * 3, step_id="s1")
    assert after.available() == before
    assert after.mark_ids == () and after.region_ids == ()


def test_runner_refuses_when_the_library_is_down(monkeypatch):
    monkeypatch.setattr(ess, "default_provider", lambda: FakeProvider(available=False))
    ctx = ra.ExecutionContext(post_id="p1", post={"photo_url": "x"})
    try:
        result = ra.RealActuatorRunner("historical_source", ctx)(
            Step(actuator="historical_source", id="s1", params={"phrase": TOPIC}),
            build_memory(image_ref="img", phrase=TOPIC))
        # The capability probe fails first — either way the answer is UNAVAILABLE and the
        # quarantine stays empty. What must never happen is a claim with no source behind it.
        assert result.status == UNAVAILABLE
        assert ctx.suggestions == []
    finally:
        ctx.close()


def test_runner_reports_empty_when_nothing_is_findable(monkeypatch):
    monkeypatch.setattr(ess, "default_provider", lambda: FakeProvider([]))
    ctx = ra.ExecutionContext(post_id="p1", post={"photo_url": "x"})
    try:
        result = ra.RealActuatorRunner("historical_source", ctx)(
            Step(actuator="historical_source", id="s1", params={"phrase": "asdfgh qwertyu"}),
            build_memory(image_ref="img", phrase="asdfgh qwertyu"))
        assert result.status == EMPTY
        assert ctx.suggestions == []            # no source → no claim
    finally:
        ctx.close()


def test_runner_never_reads_the_image(sourced_ctx, monkeypatch):
    """It has no business fetching pixels, and this pins that it does not: the image fetch is
    replaced with one that fails the test if it is ever called."""
    ctx, _ = sourced_ctx
    import backend.routers.posts as posts

    async def _forbidden(post_id, post):
        raise AssertionError("historical_source must never read the image")
    monkeypatch.setattr(posts, "_fetch_post_image_cached", _forbidden)

    result = ra.RealActuatorRunner("historical_source", ctx)(
        Step(actuator="historical_source", id="s1", params={"phrase": TOPIC}),
        build_memory(image_ref="img", phrase=TOPIC))
    assert result.status == OK


# ── 7. the field is seeded on the producers that already existed ─────────────

def test_image_producers_carry_a_sensible_default():
    from backend.services import suggestion_service as ss

    seg = ss.suggestion_from_refine_region({"id": "r1", "label": "arch"}, run_id="run1")
    assert seg[epistemics.STATUS_KEY] == "visible"          # an extent you can point at

    field = ss._field_descriptor(
        producer=ss.PRODUCER_RHYTHM, role="rhythm", label="rhythm", source_ref="r1",
        strokes=[{"points": [[0.5, 0.5]], "radius": 0.05}], run_id="run1",
        adapter="cpu_perceptual", latency_ms=1.0, confidence=0.4)
    assert field[epistemics.STATUS_KEY] == "measured"        # computed off the signal

    readings = ss.suggestions_from_semantics(
        {"assertions": [{"candidate_id": "r1", "label": "a cornice"}]}, run_id="run1")
    assert readings and readings[0][epistemics.STATUS_KEY] == "interpretive"


def test_an_unregistered_producer_defaults_to_uncertain():
    """A producer wired after the table was written is exactly where a flattering default
    would be wrong."""
    assert epistemics.default_status_for("some_new_producer") is EpistemicStatus.UNCERTAIN
    assert epistemics.default_status_for(None) is EpistemicStatus.UNCERTAIN


def test_only_the_research_producer_is_sourced():
    """No image producer may claim `sourced` — it is the one status that requires a citation,
    and none of them has one."""
    sourced = [p for p, s in epistemics._DEFAULTS.items() if s is EpistemicStatus.SOURCED]
    assert sourced == ["historical_source"]


def test_stamp_does_not_overwrite_a_declared_status():
    d = {"producer": "rhythm", epistemics.STATUS_KEY: "uncertain"}
    assert epistemics.stamp(d)[epistemics.STATUS_KEY] == "uncertain"


# ── 8. finding the shelf: query relaxation, and what it may not relax ────────

class ConjunctiveProvider(FakeProvider):
    """A library whose search demands EVERY term, as MediaWiki's actually does. Without the
    ladder, a five-word research topic finds nothing here — which is the real-world failure
    the ladder exists for."""

    def search(self, topic, *, limit=3):
        self.queries.append(topic)
        terms = [t for t in topic.lower().split() if len(t) > 2]
        return [d for d in self.docs
                if all(t in f"{d.title} {d.text}".lower() for t in terms)][:limit]


def test_ladder_starts_with_the_curators_exact_words():
    ladder = ess._query_ladder(TOPIC)
    assert ladder[0] == TOPIC


def test_ladder_ranks_proper_nouns_first_and_stops_above_one_term():
    ladder = ess._query_ladder(TOPIC)
    # proper nouns name the subject, so they are the last thing dropped
    assert "schinkel altes museum" in ladder
    assert all(len(rung.split()) >= 2 for rung in ladder)


def test_relaxation_finds_what_a_strict_query_misses():
    prov = ConjunctiveProvider([_doc()])
    assert prov.search(TOPIC) == []              # the strict query finds nothing …
    result = ess.retrieve(TOPIC, provider=ConjunctiveProvider([_doc()]))
    assert result.ok                             # … and the ladder finds the article
    assert len(result.queries_used) > 1


def test_relaxation_never_loosens_the_claim():
    """A looser QUERY may not produce a looser statement: relevance is still scored against
    the full topic, and the quote is still verbatim."""
    doc = _doc()
    result = ess.retrieve(TOPIC, provider=ConjunctiveProvider([doc]))
    for s in result.statements:
        assert s.text in doc.text
        assert s.citation.url == doc.citation.url
    assert not any("weather in a coastal town" in s.text for s in result.statements)


def test_nonsense_stays_unanswerable_after_relaxation():
    """The two-term floor is what keeps 'found a document' meaningful."""
    result = ess.retrieve("qwertyuiop zxcvbnm plorktar", provider=ConjunctiveProvider([_doc()]))
    assert result.status == ess.RETRIEVAL_EMPTY
    assert result.statements == ()


def test_queries_actually_issued_are_reported():
    result = ess.retrieve(TOPIC, provider=ConjunctiveProvider([_doc()]))
    assert result.queries_used
    assert result.queries_used[0] == TOPIC
    # the detail names the relaxed queries, so a reader can see the gap between what was asked
    # and what was searched
    assert "searched" in result.detail


def test_bibliography_lines_are_never_quoted():
    """Apparatus is not testimony. A 'Further reading' entry is short and dense with the
    topic's terms, so it outranks real prose on overlap alone while asserting nothing."""
    doc = _doc(text=(
        "Karl Friedrich Schinkel conceived the Altes Museum as a civic temple for citizens.\n"
        "== Further reading ==\n"
        "Jörg Trempler: Das Wandbildprogramm von Karl Friedrich Schinkel, Altes Museum Berlin.\n"
        "== External links ==\n"
        "Official site of the Altes Museum with Schinkel's civic drawings and intent.\n"))
    result = ess.retrieve(TOPIC, provider=FakeProvider([doc]))
    assert result.ok
    assert all("Trempler" not in s.text and "Official site" not in s.text
               for s in result.statements)


def test_ordinary_sections_are_still_quoted():
    """The skip is a named list, not a blanket distrust of headings."""
    doc = _doc(text=("== History ==\n"
                     "Karl Friedrich Schinkel conceived the Altes Museum as a civic temple "
                     "in which citizens would meet art on equal terms.\n"))
    result = ess.retrieve(TOPIC, provider=FakeProvider([doc]))
    assert result.ok and "civic temple" in result.statements[0].text
