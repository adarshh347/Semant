"""
Semant Writer W1 — the executable-document loop, in one function.

`run_block` is the whole thesis made runnable: take a block the author scripted, walk it
IN ORDER, and for each `/` directive fire the render actuator under whatever `//`
orchestration is active at that line. Successful renders are quarantined; refusals are
returned with their reason and quarantine nothing. `#create` gestures come back as
PROPOSALS the author must confirm — running a block never authors an operator behind the
author's back, exactly as it never commits prose behind the author's back.

WHY THE LOOP LIVES HERE AND NOT IN THE ROUTER. The router should serialise, not decide.
Putting the walk in a service means the live proof script and the test suite exercise the
SAME loop the HTTP surface does, rather than a re-implementation that can drift from it.

CONTINUITY. Each directive is rendered against the prose that precedes it: the scene's
committed blocks first, then any prose lines earlier in this block. That is all the
author's own language, so it strengthens the ontology wall rather than piercing it — the
model gets more of the author to work from, never more of the world.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.manuscript_service import _strip_html  # canon's own HTML→text
from backend.services.manuscript_service import manuscript_service
from backend.services.writer import dsl
from backend.services.writer.dsl import CreateGesture, Directive, Prose
from backend.services.writer.operators import operator_registry
from backend.services.writer.passages import passage_store
from backend.services.writer.render import REFUSED, RenderResult, render_directive


async def _committed_prose(scene_id: str) -> str:
    """The scene's canon as plain text — the author's committed language, in order."""
    if not scene_id:
        return ""
    scene = await manuscript_service.get_scene(scene_id)
    if not scene:
        return ""
    lines = [_strip_html(b.get("content", "")) for b in scene.get("blocks", [])]
    return "\n\n".join(ln for ln in lines if ln)


#: A directive that was parsed but deliberately not run this pass. Not a refusal and not
#: an error — the block simply had nothing to ask of it. Named beside the kernel's
#: `SKIPPED` for the same reason it exists there: "did not run" and "ran and declined" are
#: different answers and must not share a status.
SKIPPED = "skipped"


async def run_block(
    project_id: str,
    text: str,
    *,
    manuscript_id: str = "",
    scene_id: str = "",
    quarantine: bool = True,
    only_directives: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Parse a block and execute it. Returns the ordered outcome of the whole block.

    BLOCK SCOPE (`only_directives`). A directive whose render the author already ACCEPTED
    is satisfied: re-rendering it would propose a second passage for prose that is already
    canon, and the author would have to dismiss a card for work they finished. So the
    caller passes the indices (in document order, counting every `/` directive in the
    block) of the directives that are still PENDING, and the rest come back `skipped`.

    `None` means run everything — the explicit "run the whole block" action, and the
    default for any caller that has no notion of what is already satisfied.

    Skipped directives are still WALKED, not filtered out before parsing: the `//`
    orchestration scope is positional, so removing a line would re-stage everything after
    it. They are also still counted for continuity, so a later directive renders against
    the same preceding prose it would have had.

    `quarantine=False` renders without persisting — used by the tests and by any caller
    that wants to see what a block would produce. It cannot commit either way; the only
    difference is whether the passage gets an id to accept later.
    """
    parsed = dsl.parse_block(text)
    canon = await _committed_prose(scene_id)

    results: List[Dict[str, Any]] = []
    proposals: List[Dict[str, Any]] = []
    prose_so_far: List[str] = []
    directive_index = -1
    pending = None if only_directives is None else set(only_directives)

    for element in parsed.elements:
        if isinstance(element, Prose):
            if element.text.strip():
                prose_so_far.append(element.text.strip())
            continue

        if isinstance(element, CreateGesture):
            # Propose only. The author confirms via the registry's `create`.
            try:
                proposals.append({
                    "line": element.line,
                    "proposal": operator_registry.propose(element.name, element.description),
                })
            except ValueError as exc:
                proposals.append({"line": element.line, "error": str(exc)})
            continue

        if not isinstance(element, Directive):
            continue                      # orchestration notes condition; they do not run

        directive_index += 1

        if pending is not None and directive_index not in pending:
            results.append({
                "line": element.line,
                "directive_index": directive_index,
                "directive": element.raw,
                "operators": list(element.operator_names),
                "orchestration": dsl.active_orchestration(element),
                "status": SKIPPED,
                "text": "",
                "refusal": "",
                "detail": "already satisfied — its render was accepted",
                "provenance": {},
                "diagnostics": [],
                "passage_id": None,
            })
            continue

        preceding = "\n\n".join(filter(None, [canon, "\n".join(prose_so_far)]))
        result: RenderResult = await render_directive(
            project_id, element,
            preceding_prose=preceding,
            manuscript_id=manuscript_id,
            scene_id=scene_id,
        )

        entry: Dict[str, Any] = {
            "line": element.line,
            "directive_index": directive_index,
            "directive": element.raw,
            "operators": list(element.operator_names),
            "orchestration": dsl.active_orchestration(element),
            "status": result.status,
            "text": result.text,
            "refusal": result.refusal,
            "provenance": result.provenance,
            "diagnostics": list(result.diagnostics),
            "passage_id": None,
        }

        if result.succeeded and quarantine:
            passage = await passage_store.quarantine(
                project_id, result, manuscript_id=manuscript_id, scene_id=scene_id
            )
            entry["passage_id"] = passage["id"]

        # A rendered passage feeds the next directive's continuity even while
        # quarantined — within one run the author is watching the block take shape.
        # It is still uncommitted; nothing here writes to canon.
        if result.succeeded:
            prose_so_far.append(result.text)

        results.append(entry)

    return {
        "project_id": project_id,
        "manuscript_id": manuscript_id,
        "scene_id": scene_id,
        "results": results,
        "proposals": proposals,
        "diagnostics": list(parsed.diagnostics),
        "refused": sum(1 for r in results if r["status"] == REFUSED),
        "rendered": sum(1 for r in results if r["status"] == "ok"),
        "skipped": sum(1 for r in results if r["status"] == SKIPPED),
    }
