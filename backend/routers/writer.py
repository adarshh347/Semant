"""
Semant Writer API (W1 · the executable document).

Mounted under /api/v1/writer. This router SERIALISES; it does not decide. Every judgement
— what an operator is, whether a directive can render, whether a passage may be committed
— lives in `services/writer/`, so the HTTP surface and the live proof script exercise the
same code path.

  Operators (the author's ontology · the ledger)
    POST   /{project_id}/operators/propose      draft from a description — UNSAVED
    POST   /{project_id}/operators              the author-confirmed write
    GET    /{project_id}/operators              list
    GET    /{project_id}/operators/{name}       read
    PATCH  /{project_id}/operators/{name}       edit (bumps version, keeps history)
    DELETE /{project_id}/operators/{name}       delete

  The loop
    POST   /{project_id}/parse                  the `/` ÷ `//` split — no model, no writes
    POST   /{project_id}/run                    execute a block → QUARANTINED passages

  Quarantine → canon (the author's gate)
    GET    /{project_id}/passages               list (quarantined by default)
    GET    /passages/{passage_id}               read one
    POST   /passages/{passage_id}/accept        commit into the manuscript
    POST   /passages/{passage_id}/dismiss       drop it

  Instrumentation (record-only; nothing reasons on it in W1)
    GET    /{project_id}/usage                  raw usage events, newest first

A REFUSAL IS NOT AN HTTP ERROR. `/run` returns 200 with `status: "refused"` and a reason
on the entry that refused. Mapping refusals onto 4xx would make "I cannot write this
honestly" indistinguishable from "your request was malformed", and the author needs to
read the reason — it is the most useful thing the system produces when the ontology is
thin. Only genuine client errors (an unknown passage, an invalid operator, a commit that
would leak orchestration) raise.
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.writer import (
    BlockParse,
    BlockRun,
    OperatorCreate,
    OperatorPropose,
    OperatorUpdate,
    AssemblageCreate,
    AssemblageDismiss,
    PassageAccept,
    PassageDismiss,
    LibraryOp,
    RelationsUpdate,
)
from backend.services.writer import dsl, instrument
from backend.services.writer import assemblages as assemblages_mod
from backend.services.writer import library as library_mod
from backend.services.writer import relations as relations_mod
from backend.services.writer.operators import OperatorError, operator_registry
from backend.services.writer.passages import PassageError, passage_store
from backend.services.writer.studio import run_block

router = APIRouter()


# --- Operators ---

@router.post("/{project_id}/operators/propose")
async def propose_operator(project_id: str, request: OperatorPropose):
    """Draft an operator from the author's description. Returns it UNSAVED (`committed: false`)."""
    try:
        return operator_registry.propose(request.name, request.description, request.author or "")
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{project_id}/operators")
async def create_operator(project_id: str, request: OperatorCreate):
    try:
        return await operator_registry.create(
            project_id,
            request.name,
            request.definition,
            rendering_intent=request.rendering_intent or "",
            examples=request.examples,
            negative_examples=request.negative_examples,
            relations=[r.model_dump() for r in request.relations],
            author=request.author or "",
        )
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{project_id}/operators")
async def list_operators(project_id: str):
    return await operator_registry.list(project_id)


@router.get("/{project_id}/operators/{name}")
async def get_operator(project_id: str, name: str):
    op = await operator_registry.get(project_id, name)
    if not op:
        raise HTTPException(status_code=404, detail=f"operator '{name}' is not defined in this project")
    return op


@router.patch("/{project_id}/operators/{name}")
async def update_operator(project_id: str, name: str, request: OperatorUpdate):
    patch = request.model_dump(exclude_none=True)
    if "relations" in patch:
        patch["relations"] = [r if isinstance(r, dict) else r.model_dump() for r in patch["relations"]]
    try:
        op = await operator_registry.update(project_id, name, patch)
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not op:
        raise HTTPException(status_code=404, detail=f"operator '{name}' is not defined in this project")
    return op


@router.delete("/{project_id}/operators/{name}")
async def delete_operator(project_id: str, name: str):
    if not await operator_registry.delete(project_id, name):
        raise HTTPException(status_code=404, detail=f"operator '{name}' is not defined in this project")
    return {"deleted": name}


# --- The operator graph (W3) ---

@router.get("/{project_id}/graph")
async def operator_graph(project_id: str):
    """The ontology as nodes + typed edges. A READ over the ledger; touches no canon."""
    operators = await operator_registry.list(project_id)
    edges = []
    for op in operators:
        for rel in relations_mod.relations_of(op):
            edges.append({
                "source": op["name"],
                "target": rel["target"],
                "kind": rel["kind"],
                # Only `requires` conditions a render. The graph says which edges act, so
                # the author can see the difference rather than having to remember it.
                "feeds_render": rel["kind"] in relations_mod.RENDERING_KINDS,
            })
    return {
        "nodes": [
            {"id": op["name"], "name": op["name"], "version": op["version"],
             "definition": op.get("definition", ""),
             "rendering_intent": op.get("rendering_intent", ""),
             "examples": op.get("examples", []),
             "negative_examples": op.get("negative_examples", [])}
            for op in operators
        ],
        "edges": edges,
        "kinds": list(relations_mod.RELATION_KINDS),
        "rendering_kinds": sorted(relations_mod.RENDERING_KINDS),
    }


@router.put("/{project_id}/operators/{name}/relations")
async def set_relations(project_id: str, name: str, request: RelationsUpdate):
    """Replace an operator's edges. The author draws these by hand, so this commits —
    but it VALIDATES first (undefined target, unknown kind, cycle) and bumps the version,
    because relations are part of what the operator IS."""
    try:
        op = await operator_registry.set_relations(
            project_id, name, [r.model_dump() for r in request.relations]
        )
    except relations_mod.RelationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not op:
        raise HTTPException(status_code=404, detail=f"operator '{name}' is not defined in this project")
    await instrument.record(
        "relations", project_id, operators=[name],
        extra={"relations": [r.model_dump() for r in request.relations]},
    )
    return op


# --- Assemblages (W4 · the Tier-2 capstone) ---

@router.get("/{project_id}/assemblages/suggestions")
async def assemblage_suggestions(project_id: str, min_blocks: int = assemblages_mod.MIN_BLOCKS):
    """Clusters that recurred often enough to be worth naming, each CITING its evidence.

    A read over the usage log and the ontology. It proposes and changes nothing — and a
    candidate whose evidence cannot be produced is dropped rather than shown uncited.
    """
    index = await operator_registry.by_name(project_id)
    suggestions = await assemblages_mod.suggest(project_id, index, min_blocks=min_blocks)
    return {
        "suggestions": suggestions,
        "threshold": min_blocks,
        "default_threshold": assemblages_mod.MIN_BLOCKS,
    }


@router.post("/{project_id}/assemblages/dismiss")
async def dismiss_assemblage(project_id: str, request: AssemblageDismiss):
    """Record a dismissal. The ontology is untouched; the cluster stops nagging."""
    key = await assemblages_mod.dismiss(project_id, request.members, request.support)
    return {"dismissed": key, "members": request.members}


@router.post("/{project_id}/assemblages")
async def create_assemblage(project_id: str, request: AssemblageCreate):
    """The author names the cluster. THIS is the commit — nothing before it changed anything."""
    try:
        op = await operator_registry.create_assemblage(
            project_id,
            request.name,
            request.members,
            rendering_intent=request.rendering_intent,
            definition=request.definition or "",
            author=request.author or "",
        )
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await assemblages_mod.record_authored(project_id, request.name, request.members)
    return op


# --- The portable ontology (W5) ---
#
# Four operations, all explicit and author-committed. None of them is a canon write: the
# library holds the author's language, never their prose. Import is a LINKED COPY — the
# project copy versions independently, so editing it here can never redefine the language
# under another book's committed passages.

@router.get("/library/{author}")
async def list_library(author: str):
    """The author's cross-manuscript library. A read; touches nothing."""
    return {"author": author, "entries": await library_mod.list_entries(author)}


@router.post("/{project_id}/library/promote")
async def promote_to_library(project_id: str, request: LibraryOp):
    """Lift a project operator UP into the library, with its `requires`/members closure."""
    try:
        return await library_mod.promote(
            request.author, project_id, request.name,
            await operator_registry.by_name(project_id),
        )
    except library_mod.LibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{project_id}/library/import")
async def import_from_library(project_id: str, request: LibraryOp):
    """Bring a library operator DOWN as a linked copy, with its closure."""
    try:
        return await operator_registry.import_from_library(
            project_id, request.author, request.name)
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{project_id}/library/publish")
async def publish_to_library(project_id: str, request: LibraryOp):
    """Push this project's current version UP as a new library version."""
    operator = await operator_registry.get(project_id, request.name)
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"operator '{request.name}' is not defined in this project")
    try:
        return await library_mod.publish(request.author, project_id, request.name, operator)
    except library_mod.LibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{project_id}/library/pull")
async def pull_from_library(project_id: str, request: LibraryOp):
    """Bring a newer library version down. Author-reviewed; never automatic."""
    try:
        return await operator_registry.pull_from_library(
            project_id, request.author, request.name)
    except OperatorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- The loop ---

@router.post("/{project_id}/parse")
async def parse_block(project_id: str, request: BlockParse):
    """The `/` ÷ `//` split, with no model called and nothing stored."""
    parsed = dsl.parse_block(request.text)
    return {
        "directives": [
            {
                "line": d.line,
                "raw": d.raw,
                "operators": [{"name": o.name, "argument": o.argument} for o in d.operators],
                "orchestration": dsl.active_orchestration(d),
            }
            for d in parsed.directives
        ],
        "orchestration_notes": [
            {"line": n.line, "key": n.key, "value": n.value, "known": n.known}
            for n in parsed.notes
        ],
        "creates": [
            {"line": c.line, "name": c.name, "description": c.description} for c in parsed.creates
        ],
        "prose_lines": [{"line": p.line, "text": p.text} for p in parsed.prose if p.text.strip()],
        "diagnostics": list(parsed.diagnostics),
    }


@router.post("/{project_id}/run")
async def run(project_id: str, request: BlockRun):
    """Execute a scripted block. Every render is QUARANTINED — nothing reaches canon here."""
    return await run_block(
        project_id,
        request.text,
        manuscript_id=request.manuscript_id or "",
        scene_id=request.scene_id or "",
        quarantine=request.quarantine,
        only_directives=request.only_directives,
    )


# --- Quarantine → canon ---

@router.get("/{project_id}/passages")
async def list_passages(project_id: str, scene_id: str = "", status: str = "quarantined"):
    return await passage_store.list(project_id, scene_id=scene_id, status=status)


@router.get("/passages/{passage_id}")
async def get_passage(passage_id: str):
    passage = await passage_store.get(passage_id)
    if not passage:
        raise HTTPException(status_code=404, detail=f"no such passage: {passage_id}")
    return passage


@router.post("/passages/{passage_id}/accept")
async def accept_passage(passage_id: str, request: PassageAccept):
    """The author's commit — the ONLY path from quarantine into the sacred manuscript."""
    try:
        return await passage_store.accept(passage_id, scene_id=request.scene_id or "")
    except PassageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/passages/{passage_id}/dismiss")
async def dismiss_passage(passage_id: str, request: PassageDismiss):
    try:
        return await passage_store.dismiss(passage_id, request.reason or "")
    except PassageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- Instrumentation ---

@router.get("/{project_id}/usage")
async def usage(project_id: str, limit: int = 200):
    """Raw usage events. Recorded from day one; nothing in W1 reasons on them."""
    return await instrument.usage_for_project(project_id, limit=limit)
