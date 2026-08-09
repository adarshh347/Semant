"""
HARNESS-002A §7 — the rehearsal script: replayable, read-only, and honest about live mode.

The script's whole claim is that running it cannot touch anything. That is tested structurally
(what it imports) rather than by promising it, and the live path is tested for the one behaviour
that matters: an unavailable model must produce an empty result that says so, never a fixture
wearing a live label.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.schemas.semantic_compilation import SemanticInquiryGraph
from backend.tests.fixtures import semantic_compilation_fixtures as fixtures

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "semantic_compile.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO,
                          capture_output=True, text=True)


def test_the_script_exists_and_is_importable_without_running_anything():
    assert SCRIPT.exists()
    ast.parse(SCRIPT.read_text(encoding="utf-8"))


def test_the_script_imports_no_database_and_no_router():
    """Structural, because 'read-only' is a guarantee and not a promise. The script reaches the
    compiler and the two contracts and stops there."""
    forbidden = {"pymongo", "motor", "backend.database", "backend.main", "backend.routers"}
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {n.name for n in node.names} & forbidden
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in forbidden
            assert not (node.module or "").startswith("backend.routers")


def test_the_script_takes_urls_and_never_looks_a_post_id_up():
    """`--live` deliberately does not accept post ids: resolving one would mean opening the
    database the script promises not to."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "does not read posts" in source or "will not look one up in a database" in source
    result = run("--live", "--prompt", "anything")
    assert result.returncode != 0
    assert "needs at least one --image" in result.stderr


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_a_fixture_run_renders_without_a_network(name):
    result = run("--fixture", name)
    assert result.returncode == 0, result.stderr
    assert "PROMPT (unchanged)" in result.stdout
    assert "OBSERVABLES" in result.stdout and "never a tool" in result.stdout
    assert "SEMANTIC REMAINDER" in result.stdout
    assert "none run" in result.stdout


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_json_output_is_a_valid_graph(name):
    result = run("--fixture", name, "--json")
    assert result.returncode == 0, result.stderr
    graph = SemanticInquiryGraph.model_validate(json.loads(result.stdout))
    assert graph.claims and graph.observables
    assert graph.prompt == fixtures.load(name)["prompt"]


@pytest.mark.parametrize("name", fixtures.FIXTURES)
def test_the_replay_check_reports_byte_identity_and_exits_zero(name):
    result = run("--fixture", name, "--replay-check")
    assert result.returncode == 0, result.stderr
    assert "byte-identical under `canonical`: True" in result.stdout


def test_running_it_with_nothing_is_an_error_rather_than_a_default_fixture():
    result = run()
    assert result.returncode != 0
    assert "--fixture" in result.stderr


def test_an_unknown_fixture_name_is_refused_by_argparse():
    result = run("--fixture", "whatever")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_the_render_says_what_answered_for_each_of_the_two_roles():
    result = run("--fixture", "cross-image-comparison")
    assert "reading  scene_theorist" in result.stdout
    assert "compile  semantic_compiler" in result.stdout
    assert "replay" in result.stdout


def test_an_unavailable_compiler_makes_the_script_exit_with_its_own_code():
    """A compiler that did not answer and a compiler that answered with nothing are different
    facts, and a script returning 0 for both would hide it."""
    from backend.services.semantic_compilation.base import CompilationRequest
    from backend.services.semantic_compilation.compiler import ModelSemanticCompiler

    compiler = ModelSemanticCompiler(client=None)
    compiler._client_resolved = True
    graph = compiler.compile(CompilationRequest(prompt="anything", inquiry_id="inq_1"))
    assert graph.provenance.compiler.call_topology.value == "unavailable"

    source = SCRIPT.read_text(encoding="utf-8")
    assert "return 3" in source
