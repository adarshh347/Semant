"""
VISION-E · E2 — evidence embedding orchestration.

Turns a post's confirmed Regions into DINOv2 evidence vectors, obeying the model-reuse rule:
the whole image is encoded ONCE into a shared patch grid, and each Region's identity vector is
POOLED from that grid under its mask — the full image is never re-encoded per Region. A vector
is produced by one of three documented routes:

  · `whole_cls`  — the whole-image CLS token (one per post; role `whole_image`);
  · `mask_pool`  — coverage-weighted pooling of the shared patch grid under a Region's mask
                   (role `identity`, the default when the mask covers ≥ one patch cell);
  · `crop_cls`   — the CLS of a rendered crop (role `context` always; role `identity` only as a
                   fallback when the mask is sub-patch or the Region is box-only legacy).

Every vector is L2-normalized and written to the ONE sidecar (`region_embedding_service`) with
full provenance (model/checkpoint/dim/space, geometry_rev, crop+preprocessing version, source +
mask hashes, route). The DINOv2 encoder is injectable so this logic is testable without a GPU.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from backend.services import evidence_projection as ep
from backend.services import region_embedding_service as res
from backend.services import mask_geometry as mg

WHOLE_REGION_ID = "__whole__"      # the post-level whole-image vector's synthetic region id

# GPU governance: the whole-image encode goes through ModelManager, so DINOv2 evicts YOLO/SAM
# when it runs (single-GPU residency) and the shared features are content-cached (feature_key).
_registry = None
_manager = None
_adapter = None


def _ensure_manager():
    global _registry, _manager, _adapter
    if _manager is None:
        from backend.services.vision_orchestrator import AdapterRegistry, ModelManager
        from backend.services.vision_orchestrator.adapters import Dinov2FeatureAdapter
        _registry = AdapterRegistry()
        _adapter = Dinov2FeatureAdapter()
        _registry.register(_adapter)
        _manager = ModelManager(_registry)
    return _manager, _adapter


async def _features_via_manager(image, image_hash: str):
    """Acquire the GPU slot through ModelManager (evicting any other resident GPU adapter),
    load DINOv2 if needed, and return the shared whole-image patch features — content-cached by
    `feature_key`, so re-embedding the same source is a cache hit with no recompute."""
    from backend.services.vision_orchestrator import CancelToken, Priority
    from backend.services.vision_orchestrator.cache import feature_key
    from backend.services import dinov2_service
    mgr, adapter = _ensure_manager()
    ck = feature_key(image_hash, dinov2_service.MODEL_TAG, dinov2_service.CHECKPOINT,
                     dinov2_service.PREPROCESSING_VERSION, 224)
    job = await mgr.run_adapter(adapter, {"image": image}, priority=int(Priority.BACKGROUND),
                                cancel=CancelToken(), cache_key=ck, timeout_s=120.0)
    return job.artifact.data if job.artifact else None


def _pil(image_bytes: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


async def embed_post_regions(
    post: dict,
    image_bytes: bytes,
    *,
    encoder=None,
    roles=("whole_image", "identity", "context"),
    persist: bool = True,
) -> Dict[str, Any]:
    """Encode a post's evidence with DINOv2. Returns
    `{status, model, whole_image_encodes, records:[...], unavailable_reason}`.
    `whole_image_encodes` proves the shared-computation rule (it is 1 for any number of Regions).
    Each record carries `{embedding_id, region_id, role, route, dim, space, projection_hash?}`."""
    real = encoder is None
    if real:
        from backend.services import dinov2_service
        encoder = dinov2_service.get_encoder()
    if not encoder.available():
        return {"status": "unavailable", "model": getattr(encoder, "model_tag", "dinov2_vits14"),
                "whole_image_encodes": 0, "records": [], "unavailable_reason": "DINOv2 not installed"}

    post_id = str(post.get("_id") or post.get("id") or "")
    src = res.content_hash(image_bytes)
    image = _pil(image_bytes)

    model = encoder.model_tag
    ckpt = encoder.checkpoint
    prep = encoder.preprocessing_version

    # ── the ONE shared computation ──
    # real runs go through ModelManager (GPU residency + feature cache); tests use the injected
    # encoder directly. Either way the whole image is encoded exactly once for the whole post.
    if real:
        features = await _features_via_manager(image, src)
    else:
        features = encoder.encode_image(image)
    whole_image_encodes = 1
    records: List[Dict[str, Any]] = []

    async def _store(region_id, role, vector, route, *, geometry_rev=None, mask_h="",
                     projection_hash=None):
        eid = res.make_embedding_id(post_id, region_id, model=model, role=role)
        if persist:
            await res.upsert_embedding(
                eid, vector, model=model, post_id=post_id, region_id=region_id, role=role,
                geometry_rev=geometry_rev, checkpoint=ckpt, preprocessing_version=prep,
                crop_version=ep.CROP_VERSION, source_content_hash=src, mask_hash=mask_h, route=route)
        records.append({"embedding_id": eid, "region_id": region_id, "role": role, "route": route,
                        "dim": len(vector), "space": res.space_key(model, role, prep, len(vector)),
                        "projection_hash": projection_hash})

    if "whole_image" in roles:
        await _store(WHOLE_REGION_ID, "whole_image", features["cls"], "whole_cls")

    for region in post.get("region_annotations", []) or []:
        rid = str(region.get("id") or "")
        if not rid:
            continue
        proj = ep.project_region(region, image, source_content_hash=src)
        if proj is None:                            # neither mask nor box — nothing to embed
            continue
        rle = region.get("mask_rle")
        has_mask = mg.rle_is_valid(rle)
        mask_h = res.mask_hash(rle) if has_mask else ""
        grev = region.get("geometry_rev")

        if "identity" in roles:
            vec, route = None, "mask_pool"
            if has_mask:
                vec = encoder.pool_region(features, rle)    # reuse shared grid — no re-encode
            if vec is None:                                 # sub-patch mask, or box-legacy
                vec = encoder.encode_crop(proj["identity"]["image"]); route = "crop_cls"
            await _store(rid, "identity", vec, route, geometry_rev=grev, mask_h=mask_h,
                         projection_hash=proj["identity"]["projection_hash"])

        if "context" in roles:
            vec = encoder.encode_crop(proj["context"]["image"])   # context always crop-encoded
            await _store(rid, "context", vec, "crop_cls", geometry_rev=grev, mask_h=mask_h,
                         projection_hash=proj["context"]["projection_hash"])

    return {"status": "ready", "model": model, "checkpoint": ckpt,
            "whole_image_encodes": whole_image_encodes, "records": records}


# ── E3: FashionCLIP evidence vectors for fashion Regions (its OWN space) ──────
FASHION_MODEL = "fashion-clip"
FASHION_VERSION = "vitb32"


async def embed_fashion_region(post: dict, region: dict, image_bytes: bytes, *,
                               fashion=None, persist: bool = True) -> Dict[str, Any]:
    """Represent one fashion Region with the existing FashionCLIP service, stored in the
    `fashion-clip|fashion|vitb32|512` space — never mixed with the DINOv2 visual spaces.
    FashionCLIP *represents* the garment; Fashionpedia (a different model) *segments* it."""
    if fashion is None:
        from backend.services import fashion_clip_service as fashion
    if not fashion.is_available():
        return {"status": "unavailable", "reason": "FashionCLIP not installed"}
    image = _pil(image_bytes)
    src = res.content_hash(image_bytes)
    proj = ep.project_region(region, image, source_content_hash=src)
    if proj is None:
        return {"status": "skipped", "reason": "no geometry"}
    vec = fashion.embed_image(proj["identity"]["image"])   # mask-isolated garment evidence
    if not vec:
        return {"status": "error", "reason": "empty vector"}
    post_id = str(post.get("_id") or post.get("id") or "")
    rid = str(region.get("id") or "")
    rle = region.get("mask_rle")
    mask_h = res.mask_hash(rle) if mg.rle_is_valid(rle) else ""
    eid = res.make_embedding_id(post_id, rid, model=FASHION_MODEL, role="fashion")
    if persist:
        await res.upsert_embedding(eid, vec, model=FASHION_MODEL, post_id=post_id, region_id=rid,
                                   role="fashion", geometry_rev=region.get("geometry_rev"),
                                   checkpoint="patrickjohncyh/fashion-clip",
                                   preprocessing_version=FASHION_VERSION, crop_version=ep.CROP_VERSION,
                                   source_content_hash=src, mask_hash=mask_h, route="crop_cls")
    return {"status": "ready", "embedding_id": eid, "dim": len(vec),
            "space": res.space_key(FASHION_MODEL, "fashion", FASHION_VERSION, len(vec))}
