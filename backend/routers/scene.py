"""
WAVE4 — the scene routes: one picture, its regions, and the relations grounded on them.

    GET /api/v1/scene/status        what the derived cache holds, and when it was built
    GET /api/v1/scene/{post_id}     the scene: regions + makers + relations, statuses legible

READ-ONLY, and structurally so — there is no write path here to misuse. Committing a relation is
the curator surface's single write (`/api/v1/curator/queue/{id}/commit`); this router shows what
exists and changes nothing about it.

## The serializer trap, taken from the curator lane

A response model with a DEFAULTED status field is how `proposed` becomes `measured` without anybody
writing the word: FastAPI fills the field from the model's default and renders it as though it were
data. The curator router hit this and made both status fields required and un-defaulted. Same rule
here, and one more on top: `epistemic` is not merely un-defaulted, it is **re-derived from the
recorded basis on every read** (`scene_relations.hydrate`). The cache stores a basis, which is
data; the status is a conclusion, and a conclusion nobody can edit into the file.

## Absence is a value

An unbuilt cache is not an empty scene, and the two must not render alike. Every response carries
`cache` (built_at, which kinds were derived, and the caps the build applied) and `kinds_absent`, so
a picture showing no occlusions can say whether that is because there are none or because nobody
has derived them yet.

    404  no such post
    200  a scene, however thin — including one whose cache has never been built
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import scene_relations

router = APIRouter()


class Maker(BaseModel):
    """Who drew this region's geometry. `kind` is required — `unknown` is an answer, not a gap."""
    kind: str
    attributed: bool
    detail: str
    adapter: Optional[str] = None
    model: Optional[str] = None
    actor: Optional[str] = None


class RegionView(BaseModel):
    id: str
    label: str = ""
    box: Optional[Dict[str, float]] = None
    has_mask: bool
    polygons: List[List[List[float]]] = Field(default_factory=list)
    maker: Maker


class RelationView(BaseModel):
    """One relation as a reader gets it.

    `epistemic` and `ledger_status` are REQUIRED and un-defaulted. A default on either is how a
    proposal starts rendering as a finding — the failure the curator lane documented and the writer
    lane hit twice before it.
    """
    kind: str
    axis: str
    relation: str
    source: str
    target: str
    target_post_id: str = ""
    basis: str
    detail: str
    organ: str
    numbers: Dict[str, Any] = Field(default_factory=dict)
    supersedes: Optional[Dict[str, Any]] = None
    epistemic: str
    ledger_status: str
    admissible: bool
    misstated: bool
    mark_id: Optional[str] = None


class SceneView(BaseModel):
    post_id: str
    photo_url: str = ""
    regions: List[RegionView]
    relations: List[RelationView]
    tallies: Dict[str, Dict[str, int]]
    provenance_audit: Dict[str, Any]
    cache: Dict[str, Any]
    #: Kinds nobody has derived — a gap in the build.
    kinds_absent: List[str]
    #: Kinds that WERE derived and that this picture has none of — a fact about the scene. The two
    #: must not be shown alike; one is missing evidence, the other is evidence of absence.
    kinds_none_here: List[str]


async def _load_post(post_id: str) -> Optional[Dict[str, Any]]:
    from bson.errors import InvalidId
    from bson.objectid import ObjectId

    from backend.database import post_collection

    try:
        doc = await post_collection.find_one({"_id": ObjectId(post_id)})
    except (InvalidId, TypeError):
        doc = None
    if doc is None:
        doc = await post_collection.find_one({"_id": post_id})
    return doc


@router.get("/status")
def scene_status() -> Dict[str, Any]:
    """What the derived cache holds. Never 404s — this is the call you make to find out which
    state you are in, so the state belongs in the body."""
    return scene_relations.cache_status()


class SceneIndexRow(BaseModel):
    post_id: str
    photo_url: str = ""
    regions: int
    masked: int
    relations: Dict[str, int]


@router.get("/", response_model=List[SceneIndexRow])
async def list_scenes(limit: int = 60) -> List[SceneIndexRow]:
    """The pictures that have anything to show, with how much each carries.

    Declared BEFORE `/{post_id}` because FastAPI matches in order and a bare `/` would otherwise
    be read as a post id called "".
    """
    from backend.database import post_collection

    payload = scene_relations.load_cache()
    scenes = payload.get("scenes") or {}
    rows: List[SceneIndexRow] = []
    async for post in post_collection.find(
            {"region_annotations.0": {"$exists": True}},
            {"photo_url": 1, "region_annotations.id": 1, "region_annotations.mask_rle": 1}):
        post_id = str(post["_id"])
        regions = post.get("region_annotations") or []
        cached = (scenes.get(post_id) or {}).get("relations") or {}
        rows.append(SceneIndexRow(
            post_id=post_id, photo_url=str(post.get("photo_url") or ""),
            regions=len(regions),
            masked=sum(1 for r in regions if r.get("mask_rle")),
            relations={kind: len(cached.get(kind) or []) for kind in
                       ("nesting", "adjacency", "occlusion", "rhyme")}))
        if len(rows) >= max(1, int(limit)):
            break
    return rows


@router.get("/{post_id}", response_model=SceneView)
async def read_scene(post_id: str) -> SceneView:
    """One picture, everything grounded on it, every status legible.

    Relations come from two sources and stay distinguishable: the derived cache (always
    `proposed`) and the post's own ledger (`committed`). On this corpus the second is empty, and
    the view renders that emptiness rather than hiding it — the difference between a proposal and a
    finding is only visible when both can appear.
    """
    post = await _load_post(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail=f"no post {post_id!r}")
    return SceneView(**scene_relations.scene_for(post))
