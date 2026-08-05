"""
ATLAS C3 — the cross-image guard: a relation that spans two photographs is not a finding in either.

C3 commits a `compare_views` relation into BOTH endpoint posts' `visual_marks`, so that either
image's record can say the comparison exists. That is a deliberate choice and it carries a debt,
which this module is the payment of.

THE DEBT. M1 files cross-image relations in their own quarantine and says why: a relation joining
the façade to the rotunda "belongs to neither post, and filing it under one of them would make it
look, to every later reader, like evidence found there." Putting it in both posts makes that risk
real twice. A relation mark sitting in `post.visual_marks` is one careless `len()` away from being
counted as something the photograph shows.

THE GUARD. **No single-image surface may render or count a cross-image mark as a native percept.**
Not the Differential, not an Atlas node's caption, not a WorkingMemory's mark count, not an
article. The mark stays in the ledger — it is real, it is committed, and it is discoverable from
either end — but every surface that answers "what does THIS picture show" must leave it out, and
every surface that shows it must say what it is.

WHY A PREDICATE AND NOT A SEPARATE FIELD. The mark already carries the fact, twice over
(`geometry.cross_image` and `corpus.spans`), because `compare_views` stamps it at production. A
parallel `is_relation` flag would be a third place for the same truth to be recorded and the first
to fall out of step. Reading what the producer already wrote cannot drift from it.

THE SAFE DIRECTION. A mark is treated as cross-image if EITHER signal says so. A native mark
mistakenly withheld is a visible absence somebody notices; a cross-image relation mistakenly
counted is a photograph credited with evidence it does not hold, silently. The two errors are not
symmetric, so the check is deliberately generous.

Pure: no database, no imports from the Director. It is imported by `atlas_service`, by the corpus
hydrator and by the single-post read, none of which may depend on each other.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Sequence, Tuple

#: What `compare_views` stamps on the geometry of a relation it produced across two images.
CROSS_IMAGE_KEY = "cross_image"

#: The mark type `compare_views` mints. Kept as a hint rather than the test: a `relation_mark` can
#: also be `connect_marks`' SAME-image relation, which IS a finding about one photograph and must
#: keep counting as one.
RELATION_TYPE = "relation_mark"


def is_cross_image(mark: Any) -> bool:
    """Does this mark span more than one photograph?

    Two independent signals, either of which is enough:
      · `geometry.cross_image` — what `_run_compare_views` writes on the geometry it derives.
      · `corpus.spans` naming two or more posts — what the same producer records about scope.

    A same-image `connect_marks` relation has neither and is therefore native, which is correct:
    relating two marks inside one frame is a claim about that frame's internal structure.
    """
    if not isinstance(mark, Mapping):
        return False
    geometry = mark.get("geometry")
    if isinstance(geometry, Mapping) and bool(geometry.get(CROSS_IMAGE_KEY)):
        return True
    corpus = mark.get("corpus")
    if isinstance(corpus, Mapping):
        spans = corpus.get("spans")
        if isinstance(spans, (list, tuple)) and len({str(s) for s in spans if s}) >= 2:
            return True
    return False


def split_marks(marks: Sequence[Any]) -> Tuple[List[Any], List[Any]]:
    """`(native, cross_image)` — what this picture shows, and what merely touches it.

    Returned as a pair rather than filtered in place so a caller cannot accidentally drop the
    cross-image ones entirely. They are not noise: a writer looking at the rotunda should be able
    to learn that it has been related to the façade. They just are not findings ABOUT the rotunda.
    """
    native: List[Any] = []
    spanning: List[Any] = []
    for mark in marks or []:
        (spanning if is_cross_image(mark) else native).append(mark)
    return native, spanning


def native_marks(marks: Sequence[Any]) -> List[Any]:
    """Only what this photograph itself shows. The list every single-image count must use."""
    return split_marks(marks)[0]


def cross_image_marks(marks: Sequence[Any]) -> List[Any]:
    """Only the relations that span. Shown separately, named as relations, never added in."""
    return split_marks(marks)[1]
