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


async def run_block(
    project_id: str,
    text: str,
    *,
    manuscript_id: str = "",
    scene_id: str = "",
    quarantine: bool = True,
) -> Dict[str, Any]:
    """Parse a block and execute it. Returns the ordered outcome of the whole block.

    `quarantine=False` renders without persisting — used by the tests and by any caller
    that wants to see what a block would produce. It cannot commit either way; the only
    difference is whether the passage gets an id to accept later.
    """
    parsed = dsl.parse_block(text)
    canon = await _committed_prose(scene_id)

    results: List[Dict[str, Any]] = []
    proposals: List[Dict[str, Any]] = []
    prose_so_far: List[str] = []

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

        preceding = "\n\n".join(filter(None, [canon, "\n".join(prose_so_far)]))
        result: RenderResult = await render_directive(
            project_id, element,
            preceding_prose=preceding,
            manuscript_id=manuscript_id,
            scene_id=scene_id,
        )

        entry: Dict[str, Any] = {
            "line": element.line,
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
    }
