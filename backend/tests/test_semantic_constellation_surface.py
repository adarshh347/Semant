"""Rehearsal host boundary: expose inquiry history and a read-only archive listing only."""
import ast
from pathlib import Path


def test_rehearsal_mounts_no_canonical_mutation_router():
    source = Path(__file__).resolve().parents[2] / "scripts/semantic_constellation_server.py"
    tree = ast.parse(source.read_text())
    mounted = [ast.unparse(n.args[0]) for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "include_router"]
    assert mounted == ["inquiries.router"]
    # The only extra routes are GET health and GET archive listing. No upload/Region/Ground/
    # Percept/Atlas route is available on the rehearsal host.
    routes = [ast.unparse(d.func) for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)
              for d in n.decorator_list if isinstance(d, ast.Call)]
    assert routes == ["app.get", "app.get"]
    writes = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr in {
                  "insert_one", "insert_many", "update_one", "update_many", "replace_one",
                  "delete_one", "delete_many", "bulk_write", "find_one_and_update"}}
    assert not writes


def test_rehearsal_seeds_do_not_replace_existing_human_history():
    source = Path(__file__).resolve().parents[2] / "scripts/semantic_constellation_server.py"
    tree = ast.parse(source.read_text())
    guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
              and "sessions.find_one" in ast.unparse(n.test)]
    assert len(guards) == 2
    assert all(isinstance(n.test, ast.UnaryOp) and isinstance(n.test.op, ast.Not) for n in guards)
    assert all("store.create(s)" in ast.unparse(n) for n in guards)
