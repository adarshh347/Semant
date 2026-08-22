"""
INTELLIGENCE-002C §generality — two subjects with nothing in common, one composer.

The lane's other claim, beside the honesty rules, is that none of it knows what the inquiry is
about. The proof is two frozen input sets — two moorings compared for how they are held, and two
cut loaves compared for how they were raised — run through the identical composer, plus scans
(each with its own negative control) proving that neither subject's vocabulary, neither subject's
ids and none of the machinery that would make a composition unreproducible appears in the
production source.

It also pins the vocabulary reuse. `EpistemicStatus` is not this lane's enum; it is
`backend/services/epistemics.py`'s, and a test says so, because a second status vocabulary that
looked like the first until it disagreed is the failure that module was written to prevent.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from backend.services import epistemics
from backend.services.inquiry_intelligence import composer
from backend.services.inquiry_intelligence.composer import (SECTION_ORDER, LineKind, RefusalKind,
                                                            SectionId)
from backend.tests.fixtures import intelligence_composer_fixtures as fixtures

#: Everything this directive is allowed to have written on the production side, which is one file.
#: Derived from the module rather than typed out, so moving it cannot quietly point the scan at
#: nothing.
#:
#: NOT the whole package. `backend/services/inquiry_intelligence/` is shared: 001A landed `intent`,
#: 001B `observer` and `observation_audit`, and more lanes are due. Scanning siblings would mean
#: this suite policing files it did not write — failing on their perfectly legitimate imports, and
#: going red when a lane that has nothing to do with the composer lands. Each lane scans its own.
PRODUCTION_SOURCES = [Path(composer.__file__).resolve()]

BOTH = pytest.mark.parametrize("name", fixtures.FIXTURES)


# ── both samples traverse the same path ──────────────────────────────────────

@BOTH
def test_a_sample_composes_into_the_same_typed_shape_whatever_its_subject(name):
    composition = fixtures.compose_fixture(name)
    assert tuple(s.section for s in composition.sections) == SECTION_ORDER
    kinds = {l.kind for l in composition.lines()}
    for required in (LineKind.PROPOSAL, LineKind.OBSERVATION, LineKind.ALIGNMENT, LineKind.CHOICE,
                     LineKind.RELATION, LineKind.RESIDUE, LineKind.GAP):
        assert required in kinds, "{} lost {}".format(name, required.value)
    assert composition.provenance.producer == composer.COMPOSER_PRODUCER
    assert composition.provenance.schema_version == composer.SCHEMA_VERSION


@BOTH
def test_a_sample_keeps_all_six_distinctions_apart(name):
    """The six the directive names, each demonstrated by at least one line."""
    composition = fixtures.compose_fixture(name)
    for section in SECTION_ORDER:
        assert composition.section(section).lines, \
            "{} demonstrates nothing under {}".format(name, section.value)


def test_the_two_samples_ask_for_different_capabilities():
    """If the same capabilities came back for both, the composer would be keying on something
    other than what it was handed — which is what a topic branch looks like from the outside."""
    wanted = []
    for name in fixtures.FIXTURES:
        wanted.append({c for l in fixtures.compose_fixture(name).section(SectionId.MEASURABLE).lines
                       for c in l.subjects})
    assert wanted[0] and wanted[1]
    assert not wanted[0] & wanted[1]


def test_the_two_samples_produce_different_refusals_from_one_set_of_rules():
    a = {r.kind for r in fixtures.compose_fixture("moorings").refusals}
    b = {r.kind for r in fixtures.compose_fixture("proofs").refusals}
    assert a != b
    assert (a | b) <= set(RefusalKind)


def test_the_two_samples_reach_different_strengths():
    """`moorings` has an `extent` behind one reading and reaches `visible`; `proofs` has none and
    tops out at `measured`. Same code, different ceiling, on the evidence and nothing else."""
    strengths = [{l.status for l in fixtures.compose_fixture(n).backed()}
                 for n in fixtures.FIXTURES]
    assert strengths[0] != strengths[1]
    assert epistemics.EpistemicStatus.VISIBLE in strengths[0]
    assert epistemics.EpistemicStatus.VISIBLE not in strengths[1]


# ── no topic branch ──────────────────────────────────────────────────────────

def test_no_production_source_names_either_sample_s_subject():
    nouns = fixtures.topic_nouns()
    assert len(nouns) >= 8
    offences = []
    for path in PRODUCTION_SOURCES:
        text = path.read_text(encoding="utf-8").lower()
        for noun in nouns:
            if noun.lower() in text:
                offences.append("{}: {}".format(path, noun))
    assert offences == [], offences


def test_that_scan_can_fail():
    """The negative control. A scan that matches nothing is indistinguishable from a scan pointed
    at the wrong directory."""
    decoy = "SPECIAL_CASE = '{}'\n".format(fixtures.topic_nouns()[0])
    assert any(noun.lower() in decoy.lower() for noun in fixtures.topic_nouns())


def test_the_scan_is_pointed_at_something():
    """And the control for the control. `PRODUCTION_SOURCES` is now one entry rather than a glob,
    so an empty list would silently satisfy every scan above."""
    assert PRODUCTION_SOURCES and all(p.exists() for p in PRODUCTION_SOURCES)
    assert all(p.read_text(encoding="utf-8") for p in PRODUCTION_SOURCES)


def _words(text: str) -> set:
    """A source split into whole words, underscores counting as separators.

    WHY THE SCAN ABOVE MATCHES SUBSTRINGS AND THIS ONE DOES NOT. This lane's own topic nouns were
    chosen so that a substring hit is a real hit, and the stricter test is worth keeping for them.
    The nouns borrowed from 001A were chosen by another lane for its own samples, and two of them
    are inside ordinary English: `rose` is in "prose" and `rim` is in "trimmed". A substring scan
    over a borrowed vocabulary reports the language rather than the code, and the only way to
    satisfy it is to write worse prose. Splitting on non-letters keeps what actually matters — an
    identifier like `rose_window_case` is still two words, and is still caught.
    """
    return set(re.split(r"[^a-z]+", text.lower()))


def test_the_composer_does_not_name_the_subjects_of_the_lane_it_consumes_either():
    """A guarantee only the merged tree can check. INTELLIGENCE-001A's four fixtures are about
    sculpture, a cathedral window, two plants and a contradicted reading of a vessel; the composer
    is downstream of all four and must know none of them. Their scan covers their schema; this
    covers the module that reads its output."""
    from backend.tests.fixtures.inquiry_intelligence_fixtures import TOPIC_NOUNS
    nouns = sorted({n.lower() for group in TOPIC_NOUNS.values() for n in group})
    assert len(nouns) >= 15
    offences = []
    for path in PRODUCTION_SOURCES:
        words = _words(path.read_text(encoding="utf-8"))
        offences.extend("{}: {}".format(path, n) for n in nouns if n in words)
    assert offences == [], offences


def test_that_scan_can_fail_on_an_identifier_and_not_only_on_prose():
    """The negative control, and the one that matters for a word-boundary scan: a topic noun
    buried in a symbol name must still be caught."""
    from backend.tests.fixtures.inquiry_intelligence_fixtures import TOPIC_NOUNS
    nouns = {n.lower() for group in TOPIC_NOUNS.values() for n in group}
    assert _words("SPECIAL_CASE_rose_window = 1\n") & nouns
    assert _words("prose = 'trimmed'\n") & nouns == set()


def test_no_production_source_names_any_id_or_capability_from_either_sample():
    """A stricter version of the same rule. Topic nouns catch a branch on the subject; ids and
    capability names catch a branch on the rehearsal — the composer recognising `moorings`'
    particular observation and treating it specially."""
    tokens = set()
    for name in fixtures.FIXTURES:
        raw = fixtures.load(name)
        tokens |= {k for k in raw.get("capabilities", {})}
        tokens |= {str(g.get("capability", "")) for g in raw.get("capability_gaps", [])}
        for group in ("observations", "alignments", "contrast_plans", "accepted_relations",
                      "rejected_relations", "critiques", "observables", "capability_gaps",
                      "evidence"):
            for item in raw.get(group, []):
                tokens |= {str(v) for k, v in item.items() if k.endswith("_id")}
        for h in raw["inquiry_map"]["hypotheses"]:
            tokens.add(str(h["hypothesis_id"]))
        for i in raw["inquiry_map"]["images"]:
            tokens.add(str(i["image_id"]))
    tokens = {t for t in tokens if len(t) > 3}
    assert len(tokens) > 40
    offences = []
    for path in PRODUCTION_SOURCES:
        text = path.read_text(encoding="utf-8")
        offences.extend("{}: {}".format(path, t) for t in sorted(tokens) if t in text)
    assert offences == [], offences


# ── structural: nothing that would make a composition unreproducible ─────────

def _top_level_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0:
            if isinstance(node, ast.Import):
                names |= {n.name for n in node.names}
            else:
                names.add(node.module or "")
    return names


FORBIDDEN_IMPORTS = {"pymongo", "motor", "backend.database", "groq", "torch", "requests", "httpx",
                     "openai", "datetime", "time", "random", "uuid", "os"}


def test_the_production_package_imports_nothing_that_composes_a_write_or_a_clock():
    """Structural, because the guarantee is 'plain data in, plain data out'. The clock and the
    random source are in the list for a second reason: `now` is injected and every id is a hash of
    content, so a composition replays exactly, and either import would be the way that stops
    being true."""
    for path in PRODUCTION_SOURCES:
        found = _top_level_imports(path) & FORBIDDEN_IMPORTS
        assert not found, "{} imports {} at module level".format(path, found)


def test_that_scan_can_fail_too(tmp_path):
    decoy = tmp_path / "decoy.py"
    decoy.write_text("import datetime\n", encoding="utf-8")
    assert _top_level_imports(decoy) & FORBIDDEN_IMPORTS


def test_the_package_reaches_no_further_into_the_system_than_the_status_vocabulary():
    """One import from the rest of the backend, and it is the shared epistemic vocabulary. A
    composer that reached into a service registry or a store would be a composer that behaves
    differently depending on what else is running."""
    reached = set()
    for path in PRODUCTION_SOURCES:
        reached |= {n for n in _top_level_imports(path) if n.startswith("backend.")}
    assert reached == {"backend.services.epistemics"}


# ── the vocabulary is not this lane's ────────────────────────────────────────

def test_the_status_enum_is_the_one_the_rest_of_the_system_already_uses():
    """Not a copy of it. A second status vocabulary would look like the first until it disagreed,
    which is the whole reason `epistemics` exists."""
    assert composer.EpistemicStatus is epistemics.EpistemicStatus


def test_the_strength_ordering_is_imported_rather_than_restated():
    assert tuple(composer._STRENGTH) == tuple(epistemics.IMAGE_STRENGTH)
    assert epistemics.EpistemicStatus.SOURCED not in composer._STRENGTH   # the wall


def test_every_ceiling_is_a_real_status_and_only_proposals_are_walled():
    walled = {k for k, v in composer.CEILING_BY_KIND.items() if v in epistemics.WALLED_STATUSES}
    assert walled == {LineKind.PROPOSAL}
    for kind, ceiling in composer.CEILING_BY_KIND.items():
        assert isinstance(ceiling, epistemics.EpistemicStatus)
        if kind is not LineKind.PROPOSAL:
            assert ceiling in epistemics.IMAGE_STATUSES


def test_every_line_kind_has_a_ceiling_and_an_origin():
    """A kind added to one table and forgotten in the other would fall through to a KeyError at
    compose time, which is the wrong place to find out."""
    assert set(composer.CEILING_BY_KIND) == set(LineKind)
    assert set(composer.ORIGIN_BY_KIND) == set(LineKind)


def test_the_two_evidence_tables_do_not_overlap():
    """A kind that both promotes and is named as non-promoting would resolve by whichever check
    ran first — which is a rule nobody wrote down."""
    assert not set(composer.MEASURING_EVIDENCE_KINDS) & set(composer.NON_PROMOTING_EVIDENCE_KINDS)
    assert set(composer.AGREEMENT_EVIDENCE_KINDS) <= set(composer.NON_PROMOTING_EVIDENCE_KINDS)


def test_every_section_has_a_title_and_a_sentence_for_being_empty():
    assert set(composer.SECTION_TITLES) == set(SectionId)
    assert set(composer.SECTION_EMPTINESS) == set(SectionId)
    assert len(set(SECTION_ORDER)) == len(SectionId)


def test_no_verdict_word_both_sustains_and_refutes():
    assert not set(composer.SUSTAINING_VERDICTS) & set(composer.REFUTING_VERDICTS)


# ── the samples themselves ───────────────────────────────────────────────────

@BOTH
def test_a_sample_declares_why_it_exists(name):
    """The samples carry their own argument. One that stopped exercising what it says it does
    would still pass every assertion above, and a reader would have no way to notice."""
    sample = fixtures.load(name)
    assert sample["name"] == name
    assert len(sample["why_this_fixture"]) >= 5
    assert len(sample["topic_nouns"]) >= 8


@BOTH
def test_every_key_of_a_sample_is_either_commentary_or_an_input(name):
    """A key added to a sample and forgotten in the loader would be silently ignored at exactly
    the seam under test."""
    accepted = set(fixtures.CompositionRequest.__dataclass_fields__) | set(fixtures.COMMENTARY_KEYS)
    assert set(fixtures.load(name)) <= accepted


def test_the_samples_share_no_identifier_at_all():
    raw = [json.dumps(fixtures.load(n)) for n in fixtures.FIXTURES]
    for name in fixtures.FIXTURES:
        for other, text in zip(fixtures.FIXTURES, raw):
            if other == name:
                continue
            for noun in fixtures.load(name)["topic_nouns"]:
                assert noun not in text
