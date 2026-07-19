"""
VISION-C · C3 — fashion profile.

Fashionpedia R50-FPN is local-unavailable on this box (detectron2 / torch 2.13-cu130 / no
nvcc); its adapter keeps the capability contract with an explicit serverless-deferred path
(never a silent substitute). The working garment masks come from the Phase-2a SegFormer-
clothes segmenter, now emitting authoritative mask_rle with parts kept separate from the
coarse category. Tested on a synthetic semantic map (no model load).
"""
import asyncio
import numpy as np

from backend.services import fashion_segmentation_service as fseg
from backend.services import mask_geometry as mg
from backend.services.vision_orchestrator.adapters import FashionpediaAdapter
from backend.services.vision_orchestrator import CancelToken
from backend.services.vision_orchestrator.contracts import Capability, ResourceKind
from backend.schemas.post import Region


def test_fashionpedia_contract_preserved_unavailable():
    a = FashionpediaAdapter()
    assert a.spec.capability is Capability.FASHION_PARSE       # exact capability kept
    assert a.spec.resource is ResourceKind.REMOTE             # serverless slot
    assert a.spec.model_id == "fashionpedia-attribute-mask-rcnn-r50-fpn"
    assert a.is_available() is False                          # local unavailable
    res = asyncio.run(a.infer({}, CancelToken()))
    assert res.status.value == "unavailable"                 # explicit, not a substitution
    assert "detectron2" in (res.provenance.error or "")


def test_fashionpedia_available_when_endpoint_set():
    a = FashionpediaAdapter(endpoint="https://serverless.example/fashionpedia")
    assert a.is_available() is True                          # serverless makes it available
    assert a.spec.resource is ResourceKind.REMOTE


def test_garment_segmenter_emits_authoritative_masks():
    # synthetic ATR map: a 'top' (class 4) over the torso, a 'skirt' (class 5) below.
    H, W = 80, 60
    pred = np.zeros((H, W), dtype=np.int64)
    pred[15:40, 15:45] = 4        # top (garment)
    pred[42:70, 18:42] = 5        # skirt (garment)
    probs = np.zeros((18, H, W), dtype=np.float32)
    probs[4][pred == 4] = 0.9
    probs[5][pred == 5] = 0.9

    regions = fseg._regions_from_mask(pred, probs, W, H)
    for r in regions:
        r.pop("area_frac", None)
    by_part = {r["part"]: r for r in regions}
    assert "top" in by_part and "skirt" in by_part           # two separate garment masks
    for part in ("top", "skirt"):
        r = by_part[part]
        assert r["detector"] == "segformer_clothes"
        assert r["category"] == "garment"                    # coarse category…
        assert r["part"] == part                             # …kept SEPARATE from part
        assert mg.rle_is_valid(r["mask_rle"]) and r["polygons"]
        assert r["box"] == mg.rle_bbox_norm(r["mask_rle"])   # derived from the mask
        assert r["geometry_provenance"]["adapter"] == "segformer_clothes"
        Region(**r)                                          # schema-valid


def test_garment_masks_are_geometry_not_label_parented():
    # the skirt mask's box is its own pixels — it is not pulled into the top by any label.
    H, W = 80, 60
    pred = np.zeros((H, W), dtype=np.int64)
    pred[10:30, 15:45] = 4        # top
    pred[45:70, 18:42] = 5        # skirt
    probs = np.zeros((18, H, W), dtype=np.float32)
    probs[4][pred == 4] = 0.9; probs[5][pred == 5] = 0.9
    regions = {r["part"]: r for r in fseg._regions_from_mask(pred, probs, W, H)}
    assert regions["skirt"]["box"]["y"] > regions["top"]["box"]["y"]   # distinct locations
    assert regions["skirt"]["mask_rle"] != regions["top"]["mask_rle"]  # distinct evidence
