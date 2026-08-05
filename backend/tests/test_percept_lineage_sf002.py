"""SF-002 Part 0 — the two "percepts" are two, and only one of them is durable.

`SF-001B`'s census asked the question that decided this lane's whole scope: *has any accept path
ever written a `percept_draft`-shaped proposal into `post.percepts`?* It measured **no** — 12 rows,
all expression percepts, zero draft-shaped. That answer is what let `SF-002` type ONE object.

A measurement is a fact about the past. These tests are the guard that keeps it true, and they
hold the claim at the three places it could break:

  1. the PRODUCER — what `compose_percept` / `compose_comparative_percept` emit is draft-shaped,
     goes to the quarantine, and is recognisably not an expression percept;
  2. the CLASSIFIER — the predicate the census used says so, and says so about the real dicts the
     actuators build rather than about a hand-written imitation of them;
  3. the WRITE PATH — no backend module writes `post.percepts` except the wholesale PATCH, so the
     only door into the durable field is the one the frontend guards with `isExpressionPercept`.

(3)'s frontend half is `frontend/src/state/perceptLineage.sf002.test.js`, which pins the filter
that actually stands between a draft and the database.
"""
import re
from pathlib import Path

import pytest

from backend.services import percept_lineage as PL
from backend.services.director import capabilities as caps
from backend.services.director import real_actuators as ra
from backend.services.director.plan import Step
from backend.services.director.real_actuators import ExecutionContext

# The four MARK types `_quarantined_marks` allows a percept to come to rest on.
_MARK = {
    "producer": "planner", "type": "brush_field", "role": "pressure_zone",
    "label": "the drape", "source_ref": "run_1:brush_field:0",
    "geometry": {"kind": "raster", "strokes": [[0.1, 0.2]]},
}


@pytest.fixture
def ctx():
    c = ExecutionContext(post_id="p1", post={"photo_url": "http://x/y.jpg"}, run_id="run_1",
                         suggestions=[dict(_MARK)])
    try:
        yield c
    finally:
        c.close()


def _compose(ctx, draft="The light gathers where the wool folds."):
    """Run the real actuator with an explicit draft, so no language model is needed."""
    return ctx.loop.run_until_complete(ra._run_compose_percept(
        Step(actuator="compose_percept", id="s1", params={"draft_text": draft}),
        None, ctx, caps.ACTUATORS["compose_percept"]))


# ── 1 + 2. what the producer emits is a DRAFT, by the census's own predicate ─────────────

def test_compose_percept_emits_a_draft_shaped_row_not_an_expression_percept(ctx):
    """THE CLAIM: the director's output is a proposal, and the classifier can tell."""
    _compose(ctx)
    produced = [s for s in ctx.suggestions if s.get("type") == "percept_draft"]
    assert len(produced) == 1

    row = produced[0]
    assert PL.classify_percept_row(row) == PL.DRAFT
    assert PL.is_draft_shaped(row) is True
    # And — the half that matters — it can never pass for the durable object.
    assert PL.is_expression_percept(row) is False


def test_the_draft_stays_in_the_quarantine(ctx):
    """A proposal is appended to `ctx.suggestions` and nowhere else. `ExecutionContext` has no
    percepts field to write to, which is the structural half of propose-never-commit: the runner
    could not persist a percept even if it wanted to."""
    before = len(ctx.suggestions)
    _compose(ctx)
    assert len(ctx.suggestions) == before + 1
    assert not hasattr(ctx, "percepts")


def test_an_expression_percept_and_a_draft_never_classify_alike():
    """The two shapes, side by side, as `makeExpressionPercept` and `real_actuators` mint them."""
    expression = {
        "id": "pctx_m1_0", "kind": "expression", "expression": "the light pools",
        "ground_ids": ["gnd_1"], "properties": ["light"], "actor": "creator",
        "created_at": "2026-08-05T10:00:00.000Z",
    }
    draft = {
        "producer": "planner", "type": "percept_draft", "role": None, "label": "the light pools",
        "draft_text": "the light pools", "source_ref": "run_1:percept:0",
        "ground_refs": ["run_1:brush_field:0"], "geometry": None, "linked_ground_ids": [],
    }
    assert PL.classify_percept_row(expression) == PL.EXPRESSION
    assert PL.classify_percept_row(draft) == PL.DRAFT
    # A row that is neither stays VISIBLE as neither — never quietly bucketed as durable.
    assert PL.classify_percept_row({"id": "x", "note": "?"}) == PL.UNKNOWN
    assert PL.classify_percept_row("not a dict") == PL.UNKNOWN
    assert PL.classify_percept_row(None) == PL.UNKNOWN


def test_the_pctx_mint_alone_is_enough_to_be_an_expression_percept():
    """Positive evidence first: an early row that predates `kind` is still the durable object."""
    assert PL.is_expression_percept({"id": "pctx_legacy", "expression": "x"}) is True


# ── 3. the write path: one door into the durable field ──────────────────────────────────

_REPO = Path(__file__).resolve().parents[2]

# The two modules allowed to name `percepts` as a write target, and why:
#   routers/posts.py     — the wholesale PATCH (`update_post`), the one legitimate door;
#   services/vision_recovery.py — the RESTORE path, which replays a curator's own bytes back.
_MAY_WRITE_PERCEPTS = {"backend/routers/posts.py", "backend/services/vision_recovery.py"}

# `post["percepts"] = …` or a `{"percepts": …}` payload (the `$set` form) — the two ways a module
# would name the field as a write target.
_WRITES_PERCEPTS = re.compile(r"""\[["']percepts["']\]\s*=[^=]|["']percepts["']\s*:""")

# …but ONLY in a module that can reach the post collection at all. `director/argument.py` has its
# own in-memory `{"percepts": [...]}` — a claim's carrying percepts, which are `PerceptStep`s and
# never leave the process — and `argument_planner.py` has the word inside a prompt string. Neither
# is a durable write, and flagging them would train the reader to ignore this test.
_TOUCHES_POSTS = re.compile(r"""post_collection|posts_collection|\bdb\.posts\b|\[["']posts["']\]""")


def test_no_backend_module_writes_post_percepts_except_the_patch_and_the_restore():
    """THE CLAIM: there is no second door. A draft cannot reach `post.percepts` by some other
    path, because no other backend module writes the field at all.

    This is a structural guard, not a behavioural one, and that is deliberate: the failure it
    catches is somebody ADDING an accept path that persists a proposal, and a behavioural test
    cannot see code that does not exist yet. If this test fails, the question to ask is not "how
    do I make it pass" but "is the new writer persisting a draft?".
    """
    offenders = []
    scanned = 0
    for path in sorted((_REPO / "backend").rglob("*.py")):
        rel = path.relative_to(_REPO).as_posix()
        if rel in _MAY_WRITE_PERCEPTS or "/tests/" in rel:
            continue
        source = path.read_text()
        if not _TOUCHES_POSTS.search(source):
            continue
        scanned += 1
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue
            if _WRITES_PERCEPTS.search(line):
                offenders.append(f"{rel}:{i}: {stripped}")

    # A scan that matched no files would pass vacuously and prove nothing.
    assert scanned > 0, "the post-collection scan found no modules to check — the guard is inert"
    assert offenders == [], (
        "a backend module outside the PATCH/restore path now writes `post.percepts`:\n  "
        + "\n  ".join(offenders))
