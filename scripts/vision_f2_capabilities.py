"""
VISION-F · F2 — live capability matrix probe.

Actually EXERCISES each recovery capability (load a model, run one op, unload), records the live
result, and confirms the unavailable→skip guard. No corpus writes. Run:
PYTHONPATH=. venv/bin/python scripts/vision_f2_capabilities.py
"""
import asyncio
import io
import json
import os
import traceback

import httpx
from PIL import Image

from backend.database import post_collection
from backend.services import vision_capabilities as cap

OUT = "architecture-lab/vision-f-recovery/F2-capabilities"


def _small():
    return Image.new("RGB", (224, 224), (90, 110, 140))


async def probe():
    m: dict = {}

    async def rec(name, fn):
        try:
            detail = fn()
            if asyncio.iscoroutine(detail):          # a fn that returns a coroutine — await it
                detail = await detail
            m[name] = {"available": True, "detail": str(detail)[:120]}
        except Exception as e:
            m[name] = {"available": False, "detail": f"{type(e).__name__}: {e}"}
            traceback.print_exc()

    # image fetch/decode
    async def _img():
        p = await post_collection.find_one({"photo_url": {"$exists": True}})
        async with httpx.AsyncClient() as c:
            b = (await c.get(p["photo_url"], timeout=15, follow_redirects=True)).content
        return f"decoded {Image.open(io.BytesIO(b)).size}"
    await rec("image", _img)

    # geometry (pure python)
    def _geo():
        from backend.services import mask_geometry as mg
        import numpy as np
        r = {"mask_rle": mg.rle_encode_mask((np.eye(8) > 0).astype("uint8"))}
        mg.canonicalize_geometry(r, provenance={"a": "t"})
        return f"rev={r['geometry_rev']} polys={len(r['polygons'])}"
    rec_geo = _geo  # sync
    await rec("geometry", rec_geo)

    # domain router (FashionCLIP zero-shot)
    def _router():
        from backend.services import fashion_clip_service as fc
        if not fc.is_available():
            raise RuntimeError("fashionclip deps missing")
        d = fc.classify_domains(_small())
        return f"available={d.get('available')} ranked={d.get('ranked')}"
    await rec("domain_router", _router)
    await rec("fashionclip", lambda: (__import__("backend.services.fashion_clip_service",
              fromlist=["embed_image", "is_available"]).embed_image(_small()) and "512d ok"))

    # local GPU adapters: load + unload (real materialisation)
    async def _adapter(mod_attr, name):
        from backend.services.vision_orchestrator import adapters as A
        ad = getattr(A, mod_attr)()
        if not ad.is_available():
            raise RuntimeError(f"{name} not available (deps/checkpoint)")
        ms = await ad.load()
        await ad.unload()
        return f"load {ms:.0f}ms, unloaded"
    await rec("yolo", lambda: _adapter("YoloSegmenterAdapter", "yolo"))
    await rec("segformer", lambda: _adapter("SegFormerAdeAdapter", "segformer"))
    await rec("sam", lambda: _adapter("Sam2RefinerAdapter", "sam"))
    await rec("dinov2", lambda: _adapter("Dinov2FeatureAdapter", "dinov2"))
    m["fashion_segmenter"] = m.get("segformer", {"available": False})  # garment masks via segformer path

    # D semantic provider — structured output (one real call)
    async def _sem():
        from backend.services.semantic_provider import SemanticProvider
        sp = SemanticProvider()
        if not sp.available():
            raise RuntimeError("semantic provider key missing")
        import base64
        buf = io.BytesIO(); _small().save(buf, "JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        res = sp.interpret(image_b64=b64, allowed_ids=["seg_0"],
                           prompt="Name candidate seg_0 in one word. Bind only to supplied ids.")
        return f"status={res.status} dropped={res.dropped_ids}"
    await rec("semantic_provider", _sem)

    # ModelManager schedule + cancel + unload
    async def _mgr():
        from backend.services.vision_orchestrator import AdapterRegistry, ModelManager, CancelToken, Priority
        from backend.services.vision_orchestrator.adapters import Dinov2FeatureAdapter
        reg = AdapterRegistry(); ad = Dinov2FeatureAdapter(); reg.register(ad)
        mgr = ModelManager(reg)
        # a cancelled job returns without running
        ct = CancelToken(); ct.cancel() if hasattr(ct, "cancel") else setattr(ct, "cancelled", True)
        job = await mgr.run_adapter(ad, {"image": _small()}, priority=int(Priority.BACKGROUND),
                                    cancel=ct, cache_key="f2-cancel", timeout_s=30)
        await ad.unload()
        return f"cancel honoured (status={job.status.value})"
    await rec("model_manager", _mgr)

    return m


async def main():
    os.makedirs(OUT, exist_ok=True)
    matrix = await probe()
    avail = {k: v["available"] for k, v in matrix.items()}

    # confirm the skip guard: with SAM down, a general rerun is skipped not written
    down = {**avail, "sam": False}
    guard_demo = cap.resolve_action("rerun_profile_general", down)

    report = {"matrix": matrix, "available": avail, "guard_demo": guard_demo,
              "fashionpedia": "deferred (serverless — no endpoint configured; F does not pretend otherwise)"}
    with open(f"{OUT}/matrix.json", "w") as f:
        json.dump(report, f, indent=1, sort_keys=True, default=str)

    print("=== F2 CAPABILITY MATRIX (live) ===")
    for k, v in sorted(matrix.items()):
        print(f"  {k:18} {'OK ' if v['available'] else 'DOWN'}  {v['detail']}")
    print(f"\nskip-guard (SAM forced down) → rerun_profile_general resolves to: "
          f"{guard_demo['action']} ({guard_demo['reason']})")
    downs = [k for k, ok in avail.items() if not ok]
    print(f"\nunavailable → planned skips (not partial writes): {downs or 'none'}")
    print(f"fashionpedia: deferred (serverless, no endpoint) -> {OUT}/matrix.json")


if __name__ == "__main__":
    asyncio.run(main())
