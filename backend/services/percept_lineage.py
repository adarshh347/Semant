"""SF-002 Part 0 — the two objects the word "percept" holds, named apart.

The system has two things called a percept. They share a word, they share no schema, and until
this module existed no code declared a relation between them. Confusing them is not academic: the
`SF-002` v1 schema was written against the wrong one, and applied as written it would have failed
to declare — and Pydantic would have dropped — every real key of the durable field. That is the
`TextBlock.origin` failure (`post.py`), which PROV-001 exists to prevent.

So, once, plainly:

**The percept draft** — the director's *proposal*. Built by `compose_percept` /
`compose_comparative_percept` (`backend/services/director/real_actuators.py`) as
`{producer:'planner', type:'percept_draft', draft_text, ground_refs, geometry:None, …}`. It is a
**mark-precursor**: it enters the suggestion quarantine and, if a curator accepts it, becomes a
**visual_mark**. It is never written to `post.percepts`. Its sibling in the planner is
`PerceptStep` (`director/argument.py`) — a percept *planned to exist*, not one that does.

**The expression percept** — the curator's *act of noticing*. Minted client-side by
`makeExpressionPercept` (`frontend/src/state/perceptMentions.js`) as
`{id:'pctx_…', kind:'expression', expression, ground_ids, properties, ground_roles?, actor,
created_at}` and persisted to `post.percepts`. This is the durable object, and the only one
`SF-002` types.

Adarsh locked **"always two"** (2026-08-01): a proposal and an act of noticing are different kinds
of thing and stay different kinds of thing. Two consequences this module carries:

1. **Any accept-time join is recorded ON THE MARK, never on the percept.** The mark already
   authors provenance (`MarkProvenance`, `backend/schemas/post.py`) and already carries
   `linked_percept_ids` (`frontend/src/differential/visualMarks.js`). A second authored copy on the
   percept is exactly the drift `groundProvenanceParity.test.js` exists to catch. The percept
   derives provenance through its `ground_ids`.
2. **A draft-shaped row must never reach `post.percepts`.** `classify_percept_row` below is the
   predicate that says so, and `backend/tests/test_percept_lineage_sf002.py` holds it to it.

The classifier is the one `SF-001B`'s census used to measure the live corpus (all 12 persisted
rows classified `expression`, zero `draft`), lifted here verbatim so the census, the guard test and
the `SF-002` validation replay all share one definition instead of three that can drift.
"""
from __future__ import annotations

from typing import Any

# The three lineages a row in `post.percepts` can belong to.
EXPRESSION = "expression"   # the curator's durable act of noticing — the object SF-002 types
DRAFT = "draft"             # a director proposal; belongs in the quarantine, becomes a mark
UNKNOWN = "unknown"         # neither — a finding, not a bucket to hide things in

# Keys that identify a director proposal. `type` is the discriminator `real_actuators` stamps;
# the rest are `percept_draft`/`PerceptStep` fields that an expression percept never carries.
DRAFT_SHAPE_KEYS = ("draft_text", "function", "ground_refs", "linked_ground_ids", "source_ref")


def classify_percept_row(row: Any) -> str:
    """Which of the two objects is this row? One of EXPRESSION | DRAFT | UNKNOWN.

    Deliberately positive-evidence-first: a row is an expression percept because it *says* it is
    (`kind`) or because its id carries the `pctx_` mint. Only then is draft shape considered. A row
    that is neither is `UNKNOWN` and stays visible as such — silently bucketing it would be how a
    third lineage arrives unnoticed.
    """
    if not isinstance(row, dict):
        return UNKNOWN
    row_id = str(row.get("id") or "")
    if row.get("kind") == EXPRESSION or row_id.startswith("pctx_"):
        return EXPRESSION
    if row.get("type") == "percept_draft" or any(k in row for k in DRAFT_SHAPE_KEYS):
        return DRAFT
    return UNKNOWN


def is_expression_percept(row: Any) -> bool:
    """The Python mirror of `isExpressionPercept` (`frontend/src/state/perceptMentions.js`).

    The frontend filters `post.percepts` through its copy on both hydrate and save, which is the
    reason no draft has ever reached the durable field. This exists so the backend can *assert*
    that rather than assume it.
    """
    return classify_percept_row(row) == EXPRESSION


def is_draft_shaped(row: Any) -> bool:
    """True for a director proposal — a mark-precursor that must never be persisted as a percept."""
    return classify_percept_row(row) == DRAFT
