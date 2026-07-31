"""
Manuscript-Oriented Writing Studio API (WS-0A · the sacred manuscript).

Mounted under /api/v1/manuscript. This gate is pure canon — no AI, no orchestration.
It exposes the manuscript, its chapter/scene hierarchy, immutable version snapshots,
and export. The propose→quarantine→accept machinery arrives in WS-0B; here every
write is an explicit author commit.

  Manuscripts
    POST   /                                 create
    GET    /                                 list (shelf summaries)
    GET    /{ms_id}                           full manuscript + hierarchy + scene stubs
    PATCH  /{ms_id}                           update title/synopsis
    DELETE /{ms_id}                           delete (cascades scenes + versions)
    POST   /{ms_id}/reorder                   atomically replace the outline
    GET    /{ms_id}/export                    assemble the whole work as text

  Chapters
    POST   /{ms_id}/chapters                  add
    PATCH  /{ms_id}/chapters/{ch_id}          rename
    DELETE /{ms_id}/chapters/{ch_id}          delete (cascades its scenes)

  Scenes
    POST   /{ms_id}/scenes                    add (in a chapter)
    GET    /scenes/{sc_id}                    read body
    PATCH  /scenes/{sc_id}                    save body/title (the canonical write)
    DELETE /scenes/{sc_id}                    delete

  Versions
    POST   /scenes/{sc_id}/versions          snapshot the current body
    GET    /scenes/{sc_id}/versions          list snapshots (metadata)
    GET    /versions/{ver_id}                read a snapshot body
    POST   /scenes/{sc_id}/versions/{ver_id}/restore   non-destructive restore
"""

from fastapi import APIRouter, HTTPException

from backend.schemas.manuscript import (
    ManuscriptCreate,
    ManuscriptUpdate,
    ChapterCreate,
    ChapterUpdate,
    SceneCreate,
    SceneUpdate,
    ReorderRequest,
    SnapshotRequest,
)
from backend.services.manuscript_service import manuscript_service

router = APIRouter()


# --- Manuscripts ---

@router.post("/")
async def create_manuscript(request: ManuscriptCreate):
    return await manuscript_service.create_manuscript(request.title, request.synopsis)


@router.get("/")
async def list_manuscripts():
    return {"manuscripts": await manuscript_service.list_manuscripts()}


@router.get("/{manuscript_id}")
async def get_manuscript(manuscript_id: str):
    ms = await manuscript_service.get_manuscript(manuscript_id)
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return ms


@router.patch("/{manuscript_id}")
async def update_manuscript(manuscript_id: str, request: ManuscriptUpdate):
    ms = await manuscript_service.update_manuscript(manuscript_id, request.model_dump(exclude_unset=True))
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return ms


@router.delete("/{manuscript_id}")
async def delete_manuscript(manuscript_id: str):
    ok = await manuscript_service.delete_manuscript(manuscript_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return {"ok": True}


@router.post("/{manuscript_id}/reorder")
async def reorder(manuscript_id: str, request: ReorderRequest):
    try:
        ms = await manuscript_service.reorder(
            manuscript_id, [c.model_dump() for c in request.chapters]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return ms


@router.get("/{manuscript_id}/export")
async def export_manuscript(manuscript_id: str, format: str = "markdown"):
    result = await manuscript_service.export_manuscript(manuscript_id, format)
    if not result:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return result


# --- Chapters ---

@router.post("/{manuscript_id}/chapters")
async def add_chapter(manuscript_id: str, request: ChapterCreate):
    ms = await manuscript_service.add_chapter(manuscript_id, request.title)
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript not found")
    return ms


@router.patch("/{manuscript_id}/chapters/{chapter_id}")
async def update_chapter(manuscript_id: str, chapter_id: str, request: ChapterUpdate):
    ms = await manuscript_service.update_chapter(
        manuscript_id, chapter_id, request.model_dump(exclude_unset=True)
    )
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript or chapter not found")
    return ms


@router.delete("/{manuscript_id}/chapters/{chapter_id}")
async def delete_chapter(manuscript_id: str, chapter_id: str):
    ms = await manuscript_service.delete_chapter(manuscript_id, chapter_id)
    if not ms:
        raise HTTPException(status_code=404, detail="Manuscript or chapter not found")
    return ms


# --- Scenes ---

@router.post("/{manuscript_id}/scenes")
async def add_scene(manuscript_id: str, request: SceneCreate):
    blocks = [b.model_dump() for b in request.blocks] if request.blocks is not None else None
    scene = await manuscript_service.add_scene(
        manuscript_id, request.chapter_id, request.title, blocks
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Manuscript or chapter not found")
    return scene


@router.get("/scenes/{scene_id}")
async def get_scene(scene_id: str):
    scene = await manuscript_service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.patch("/scenes/{scene_id}")
async def update_scene(scene_id: str, request: SceneUpdate):
    patch = request.model_dump(exclude_unset=True)
    if "blocks" in patch and patch["blocks"] is not None:
        patch["blocks"] = [b if isinstance(b, dict) else b.model_dump() for b in patch["blocks"]]
    scene = await manuscript_service.update_scene(scene_id, patch)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str):
    ms = await manuscript_service.delete_scene(scene_id)
    if not ms:
        raise HTTPException(status_code=404, detail="Scene not found")
    return ms


# --- Version snapshots ---

@router.post("/scenes/{scene_id}/versions")
async def snapshot_scene(scene_id: str, request: SnapshotRequest):
    version = await manuscript_service.snapshot_scene(scene_id, request.label)
    if not version:
        raise HTTPException(status_code=404, detail="Scene not found")
    return version


@router.get("/scenes/{scene_id}/versions")
async def list_versions(scene_id: str):
    return {"versions": await manuscript_service.list_scene_versions(scene_id)}


@router.get("/versions/{version_id}")
async def get_version(version_id: str):
    version = await manuscript_service.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/scenes/{scene_id}/versions/{version_id}/restore")
async def restore_version(scene_id: str, version_id: str):
    scene = await manuscript_service.restore_version(scene_id, version_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene or version not found")
    return scene
