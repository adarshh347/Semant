"""
HARNESS-001A — the shared contracts, and the parity that keeps them one thing.

The backend half of the cross-language gate. Its twin is
`frontend/src/differential/contracts.parity.test.js`, and between them they close the loop:

    JS planner  → committed fixture → validated HERE by the Python grammar
    Python framer → committed fixture → validated THERE by the JS validator

Neither direction goes through a third validator, because a third validator is the thing a
shared contract exists to prevent. Both fixtures are committed, and both regenerate visibly.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.services.inquiry import grammar, lexicon
from backend.services.inquiry.contracts import (CONTRACTS_DIR, GRAMMAR_FILE, LEXICON_FILE,
                                                ContractError, load)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIRROR_DIR = REPO_ROOT / "frontend" / "src" / "contracts"
JS_PLANNER_FIXTURE = CONTRACTS_DIR / "fixtures" / "js-planner-sculpture.actions.json"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "contracts_sync.py"


# ── the files exist and are the version this code enforces ───────────────────

def test_both_contracts_load_at_the_declared_version():
    assert grammar.SCHEMA_VERSION == "perceptual-action-grammar.v1"
    assert lexicon.SCHEMA_VERSION == "attunement-lexicon.v1"


def test_a_contract_at_the_wrong_version_is_refused_rather_than_read():
    # The version string is only worth carrying if a mismatch stops something. It does, at load,
    # rather than three layers down inside a validator that silently accepted an undeclared action.
    with pytest.raises(ContractError) as exc:
        load(GRAMMAR_FILE, "perceptual-action-grammar.v2")
    assert "v2" in str(exc.value)


def test_a_missing_contract_raises_rather_than_falling_back():
    # There is no fallback table, deliberately. One would be a third vocabulary invented at the
    # moment the first went missing, indistinguishable from the real one until it disagreed.
    with pytest.raises(ContractError):
        load("no-such-contract.v1.json", "anything")


# ── the frontend mirror ──────────────────────────────────────────────────────

def test_the_frontend_mirror_is_byte_identical_to_the_canonical_contract():
    """The mirror exists ONLY because the Vercel deploy uploads `frontend/` as its source, so the
    bundle cannot import from the repo root. A copy nothing pins is a second contract."""
    for name in (GRAMMAR_FILE, LEXICON_FILE):
        canonical = (CONTRACTS_DIR / name).read_bytes()
        mirror = (MIRROR_DIR / name).read_bytes()
        assert mirror == canonical, (f"frontend/src/contracts/{name} has drifted from "
                                     f"contracts/{name} — run python scripts/contracts_sync.py")


def test_the_sync_script_reports_the_tree_as_in_sync():
    result = subprocess.run([sys.executable, str(SYNC_SCRIPT), "--check"],
                            capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stdout + result.stderr


# ── the closed sets are the contract's, not retyped ──────────────────────────

def test_the_python_grammar_reads_every_closed_set_from_the_contract():
    raw = json.loads((CONTRACTS_DIR / GRAMMAR_FILE).read_text(encoding="utf-8"))
    assert list(grammar.ACTION_TYPES) == raw["closed_sets"]["action_types"]
    assert list(grammar.TARGETS) == raw["closed_sets"]["targets"]
    assert list(grammar.SOURCES) == raw["closed_sets"]["sources"]
    assert list(grammar.STATUSES) == raw["closed_sets"]["statuses"]
    assert list(grammar.GEOMETRY_MODES) == raw["closed_sets"]["geometry_modes"]
    assert list(grammar.FIELD_ROLE_KEYS) == [r["key"] for r in raw["vocabularies"]["field_roles"]]


def test_every_action_declares_a_target_inside_the_closed_set():
    for name, spec in grammar.SPEC.items():
        assert spec.target in grammar.TARGETS, name


def test_every_enum_names_a_set_that_actually_resolves():
    # A typo'd set name would resolve to an empty tuple and quietly accept nothing, which reads at
    # a call site as "this action's role is always wrong" rather than as a contract error.
    for name, spec in grammar.SPEC.items():
        for key, allowed in spec.enums.items():
            assert allowed, f"{name}.{key} names a closed set that resolved to nothing"


def test_the_python_lexicon_reads_the_same_cues_as_the_contract():
    raw = json.loads((CONTRACTS_DIR / LEXICON_FILE).read_text(encoding="utf-8"))
    assert [e["key"] for e in lexicon.LEXICON] == [e["key"] for e in raw["lexicon"]]
    assert lexicon.SCULPTURE_FIXTURE == raw["fixtures"]["sculpture"]


# ── the real parity check: the JS planner's acts, judged in Python ───────────

def test_every_act_the_JS_planner_emitted_validates_in_the_python_grammar():
    """The direction that has no substitute. These objects were built by
    `attunementPlanner.js` and written by its own vitest run; nothing in Python touched them."""
    fixture = json.loads(JS_PLANNER_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["grammar_version"] == grammar.SCHEMA_VERSION
    assert fixture["lexicon_version"] == lexicon.SCHEMA_VERSION
    assert fixture["actions"], "the JS planner fixture is empty"
    for action in fixture["actions"]:
        verdict = grammar.validate_action(action)
        assert verdict.valid, f"{action['type']} was refused in Python: {verdict.errors}"


def test_the_JS_fixture_is_the_sculpture_prompt_and_still_the_ten_acts():
    fixture = json.loads(JS_PLANNER_FIXTURE.read_text(encoding="utf-8"))
    assert fixture["prompt"] == lexicon.SCULPTURE_FIXTURE
    assert len(fixture["actions"]) == 10


def test_the_python_and_JS_planners_agree_on_which_cues_the_sculpture_prompt_fires():
    """Same sentence, same lexicon, same matcher. The JS side is read from what its planner
    actually emitted rather than asserted from a list somebody typed twice."""
    fixture = json.loads(JS_PLANNER_FIXTURE.read_text(encoding="utf-8"))
    js_cues = {a["provenance"]["cue"] for a in fixture["actions"]}
    py_cues = {hit["key"] for hit in lexicon.detect_cues(lexicon.SCULPTURE_FIXTURE)}
    # The JS planner adds cue keys of its own for the acts it seeds ('bootstrap', 'compose',
    # 'challenge'); every LEXICON key it reports must be one Python also found.
    assert py_cues == js_cues & {e["key"] for e in lexicon.LEXICON}


def test_the_two_matchers_agree_on_the_sculpture_prompt_word_for_word():
    fixture = json.loads(JS_PLANNER_FIXTURE.read_text(encoding="utf-8"))
    js_matched = {a["provenance"]["cue"]: tuple(a["provenance"]["matched"])
                  for a in fixture["actions"] if a["provenance"]["matched"]}
    for hit in lexicon.detect_cues(lexicon.SCULPTURE_FIXTURE):
        if hit["key"] in js_matched:
            assert tuple(hit["matched"]) == js_matched[hit["key"]], hit["key"]


# ── the word-boundary cues, which is why the matchers had to be re-checked ───

@pytest.mark.parametrize("prompt,cue_key", [
    ("their common way of unfolding sensuality", "light"),      # 'lit' inside "sensuality"
    ("a question of pure quality", "light"),                    # 'lit' inside "quality"
    ("the two figures stand together", "fold"),                 # 'gather' inside "together"
    ("a warm grey ground", "gesture"),                          # 'arm' inside "warm"
])
def test_a_word_cue_does_not_fire_from_inside_another_word(prompt, cue_key):
    """The third lexicon defect a fixture caught, after 'aesthetic' and 'against the'.

    A cue firing mid-word makes a card say *you said "lit"* to somebody who said "sensuality" —
    the one thing a planner that attributes everything to the prompt must never do.
    """
    assert cue_key not in {hit["key"] for hit in lexicon.detect_cues(prompt)}


def test_an_inquiry_word_cue_does_not_fire_from_inside_another_word():
    # 'apart' would otherwise fire on "apartment" and report a distinction nobody drew.
    assert "distinction" not in {h["key"] for h in
                                 lexicon.detect_inquiry_cues("the apartment block behind")}
    assert "distinction" in {h["key"] for h in
                             lexicon.detect_inquiry_cues("where the two drift apart")}


def test_the_word_cues_still_fire_on_the_whole_word():
    assert "light" in {h["key"] for h in lexicon.detect_cues("the figure is lit from the left")}
    assert "fold" in {h["key"] for h in lexicon.detect_cues("the cloth gathers at the waist")}
    assert "gesture" in {h["key"] for h in lexicon.detect_cues("her arm reaches out")}


def test_the_prefix_cues_the_lexicon_depends_on_still_match_inside_a_word():
    # 'illuminat' has to catch 'illuminated' and 'illumination'. The word-boundary rule is opt-in
    # per cue precisely so this keeps working.
    assert "light" in {h["key"] for h in lexicon.detect_cues("an illuminated recess")}
    assert "shadow" in {h["key"] for h in lexicon.detect_cues("an obscured corner")}
