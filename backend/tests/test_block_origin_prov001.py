"""
CIRCUIT-002 PROV-001 Seam 5 — a block says who wrote it.

`TextBlock.origin` defaults to "human". That default is correct for the editor, where a person is
typing, and it is a FALSEHOOD everywhere a model's prose is persisted without setting it — the
block is not stored with authorship unknown, it is stored with the wrong author, and it reads back
in the manuscript indistinguishable from something the curator wrote.

Three backend paths construct a TextBlock. None set `origin` before this change:

    epics.add_vision_text_to_post      vision-generated  → sutradhar
    epic_service._sync_block_to_post   epic agent prose  → sutradhar
    posts.add_tag_and_story_to_post    caller-supplied   → declared by the caller, default human

The third is deliberately not stamped `sutradhar`. Its payload is a bare string a person
assembled and submitted, which may be their own paragraph or a generated one; the server cannot
tell them apart. Asserting "sutradhar" there would be the same fabrication as the silent "human"
it replaces, only inverted — so the caller declares it, and the conservative default stands.

  1. each write path records the authorship it actually knows   → TestWritePaths
  2. no NEW path can quietly omit it                            → TestNoSilentOmission
"""
from __future__ import annotations

import inspect
import re

from backend.schemas.post import AddTagAndStoryRequest, TextBlock


# ── 1. the write paths ───────────────────────────────────────────────────────

class TestWritePaths:

    def test_the_schema_default_is_still_human(self):
        """Unchanged on purpose — the editor's typing path relies on it, and Seam 5 is about the
        paths that must SPEAK rather than about moving the default."""
        assert TextBlock(type="paragraph", content="x").origin == "human"

    def test_vision_generated_text_is_marked_sutradhar(self):
        from backend.routers import epics
        src = inspect.getsource(epics.add_vision_text_to_post)
        assert '"origin": "sutradhar"' in src

    def test_a_synced_epic_block_is_marked_sutradhar(self):
        from backend.services.epic_service import EpicService
        src = inspect.getsource(EpicService._sync_block_to_post)
        assert '"origin": "sutradhar"' in src

    def test_the_caller_supplied_story_route_records_what_it_was_told(self):
        from backend.routers import posts
        src = inspect.getsource(posts.add_tag_and_story_to_post)
        assert '"origin": request.origin' in src

    def test_that_route_defaults_to_human_and_accepts_sutradhar(self):
        """No fabrication in either direction: the default is the conservative reading, and a
        client that DOES know the text was generated can say so."""
        assert AddTagAndStoryRequest(tag="t", story="s").origin == "human"
        assert AddTagAndStoryRequest(tag="t", story="s", origin="sutradhar").origin == "sutradhar"

    def test_a_declared_origin_survives_onto_the_block(self):
        """The field would be useless if TextBlock dropped it — which is exactly what happened
        to `origin` before it was declared on the schema at all."""
        block = TextBlock(type="paragraph", content="generated",
                          origin=AddTagAndStoryRequest(tag="t", story="s",
                                                       origin="sutradhar").origin)
        assert block.origin == "sutradhar"
        assert block.model_dump()["origin"] == "sutradhar"


# ── 2. the structural guard ──────────────────────────────────────────────────

class TestNoSilentOmission:

    def test_every_backend_TextBlock_construction_sets_origin(self):
        """THE CLAIM that keeps this fixed. The defect was never one bad value — it was that
        omitting a key silently produced a wrong one, so each new write path could reintroduce
        it without anything failing.

        A TextBlock literal is recognised by the four keys it always carries together
        (id/type/content/color). Any such literal that does not also carry `origin` is the bug
        coming back, and this test is where it stops. Epic `story_blocks` are a different shape
        (block_id/sequence_order/coherence_score) and are correctly not matched.
        """
        import backend.routers.posts as posts_mod
        import backend.routers.epics as epics_mod
        import backend.services.epic_service as epic_mod

        offenders = []
        for mod in (posts_mod, epics_mod, epic_mod):
            lines = inspect.getsource(mod).splitlines()
            for i, line in enumerate(lines):
                if not re.search(r"\"color\"\s*:\s*None", line):
                    continue
                # The literal's own lines, walked outward to the enclosing braces. Deliberately
                # NOT a {...} regex: these literals contain f"block_{uuid.uuid4()}", whose braces
                # defeat any [^{}] class — the first version of this test did exactly that and
                # silently matched nothing, which is why it is written by line window now.
                start = next((j for j in range(i, max(i - 10, -1), -1)
                              if lines[j].rstrip().endswith("{")), i)
                end = next((j for j in range(i, min(i + 10, len(lines)))
                            if lines[j].strip().startswith("}")), i)
                literal = "\n".join(lines[start:end + 1])
                if '"content"' not in literal or '"type"' not in literal:
                    continue
                if '"origin"' not in literal:
                    offenders.append((mod.__name__, f"line {start + 1}"))

        assert not offenders, (
            "TextBlock constructed without an explicit origin — it will read back as human:\n"
            + "\n".join(f"  {m}: {lit}" for m, lit in offenders))
