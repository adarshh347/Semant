"""
The backend the harness serves: the REAL `backend.main:app`, with three additions that live here
and nowhere in `backend/`.

1. FAKES AT THE SEAMS. The circuit has no env switch for deterministic providers (every test
   binds fakes by injection), so this entry binds them the same way, in-process, before serving.
   `SEMANT_VERTICAL_FAKES` chooses the set:
     all      every model and every GPU producer is a deterministic fake  (offline / core CI)
     ml_only  GPU producers are faked; model providers run LIVE on whatever keys are present
     none     nothing is faked (only meaningful on a machine with the ML stack)
   Each binding is a receipt the harness can read back (`GET /__rehearsal/receipts`), so the run
   record names what was fake and what was live rather than inferring it from an env var.

2. FAULT INJECTION. A wrapper over the motor collection write methods, armed through
   `POST /__rehearsal/fault`, that can raise or kill the process on the Nth write to a named
   collection. This is how "one injected write failure at each multi-document transition" and
   "backend restart before finalization" are produced without touching a route.

3. WRITE LOG. Every collection write is appended to an in-memory log (`GET /__rehearsal/writes`)
   so a stage can prove "every refusal writes nothing" against what actually reached Mongo.

The control routes are loopback-only and refuse to mount unless `SEMANT_VERTICAL_HARNESS=1`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from typing import Any, Dict, List, Optional

if os.environ.get("SEMANT_VERTICAL_HARNESS") != "1":
    raise SystemExit("app_entry is the vertical rehearsal's entry; set SEMANT_VERTICAL_HARNESS=1")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FAKES = os.environ.get("SEMANT_VERTICAL_FAKES", "all")
RECEIPTS: List[Dict[str, Any]] = []
WRITES: List[Dict[str, Any]] = []
FAULTS: List[Dict[str, Any]] = []
_LOCK = threading.Lock()


def _receipt(seam: str, mode: str, **kv: Any) -> None:
    RECEIPTS.append({"seam": seam, "mode": mode, **kv})


# ── 1. fakes ──────────────────────────────────────────────────────────────────────────────────

def _bind_ml_fakes() -> None:
    """GPU producers: the segmenter, DINOv2 and the field producers. Same fakes the route tests
    bind (`backend/tests/test_run_routes.py`), so the HTTP path is the real one."""
    import backend.routers.posts as P
    import backend.services.segmentation_service as seg
    import backend.services.dinov2_service as dsvc
    from backend.services import epistemics

    seg.is_available = lambda: True
    seg.segment_image_bytes = lambda data, **k: [
        {"id": f"seg_{i}", "geometry_rev": 0,
         "box": {"x": 0.1 + 0.2 * i, "y": 0.1, "w": 0.3, "h": 0.3}, "mask_rle": None}
        for i in range(2)]
    dsvc.is_available = lambda: True

    def _mk(role: str):
        async def _handler(post_id, post, region, req, run_id):
            # A producer reads the image. The fake reads it too — through the route's own
            # fetch — so an image that cannot be fetched is `unavailable` here exactly as it
            # would be for a real producer, rather than a fake inventing a field over nothing.
            try:
                await P._fetch_post_image_cached(post_id, post)
            except Exception as e:  # noqa: BLE001
                return [], "unavailable", False
            return [epistemics.stamp({
                "producer": role, "type": "brush_field", "role": role,
                "geometry": {"kind": "soft_mask",
                             "strokes": [{"points": [[0.5, 0.5]], "radius": 0.05}]},
                "provenance": {"model": f"fake::{role}", "adapter": role, "run_id": run_id},
                "confidence": 0.6})], "ready", True
        return _handler

    for name in ("material_field", "rhythm", "pressure_zone", "negative_space",
                 "presence_check", "light_field", "shadow_field", "fall_of_light",
                 "architectural_axis"):
        P._FIELD_PRODUCERS[name] = _mk(name)
    _receipt("gpu_producers", "fake", producers=sorted(P._FIELD_PRODUCERS))

    # The runner probes each actuator's capability (segmenter, dinov2, intrinsic, depth …) before
    # calling its producer; with the producers faked, every probe answers "up" — and says so.
    import backend.services.director.real_actuators as ra
    ra._capability_available = lambda capability: True
    _receipt("capability_probes", "fake", detail="every capability reports available")

    # The corpus path (`POST /atlas/{id}/draft`) routes to `real_registry`; give it stubs that
    # run, produce, and say they are stubs — `StubActuator` is the gate's own unattended runner.
    import backend.services.director.corpus_execution as ce
    from backend.services.director.execution import StubActuator
    from backend.services.director.capabilities import known

    def _stub_registry(ctx):
        return {n: StubActuator(n, model=f"fake::{n}") for n in known()}
    # Corpus path only. The single-image path (`/orchestrate`, the Light Table's machine read)
    # keeps the REAL runner over the fake producers above, so its suggestions reach the
    # Differential's quarantine exactly as a live run's would.
    ce.real_registry = _stub_registry
    _receipt("corpus_actuators", "fake", model="fake::<actuator>")


def _bind_model_fakes() -> None:
    """Model providers: the Groq planners, the composer, the Writer's renderer and alignment
    reader, and the Scout. Deterministic replies shaped exactly as the parsers expect."""
    import backend.services.director.groq_planner as gp
    import backend.services.director.argument_planner as ap
    import backend.services.director.composition as comp
    import backend.services.writer.render as render_svc
    import backend.services.writer.alignment as align
    from backend.services.director import argument as A
    from backend.services.director.plan import Step

    # Planner: no client → the rule-based table, which the Director reports as such.
    gp.GroqPlanner._get_client = lambda self: None
    _receipt("groq_planner", "fake", model="rule_based")

    # Argument planner has NO fallback by design, so the fake proposes one fixed decomposition
    # over the corpus it is handed: one supporting percept on the first image, one challenge on
    # the second — enough to bind, enough to be refused if the corpus cannot carry it.
    def _propose(self, thesis, memory):
        images = [getattr(i, "post_id", None) or (i.get("post_id") if isinstance(i, dict) else None)
                  for i in getattr(getattr(memory, "corpus", None), "images", ())]
        images = [i for i in images if i]
        first = images[0] if images else None
        second = images[1] if len(images) > 1 else first
        self.last_notes = ("planner: vertical-rehearsal-fake",)
        return [
            A.SubClaim(claim_id="c0", text="the sequence gathers toward the darker block",
                       target_status=A.INTERPRETIVE, percepts=(
                           A.PerceptStep(step=Step(actuator="negative_space", params={},
                                                   id="fake:c0:0:negative_space"),
                                         function=A.SUPPORT, image=first),
                           A.PerceptStep(step=Step(actuator="presence_check",
                                                   params={"phrase": "a darker block"},
                                                   id="fake:c0:1:presence_check"),
                                         function=A.CHALLENGE, image=second))),
            A.SubClaim(claim_id="c1", text="the light edge repeats across the walk",
                       target_status=A.INTERPRETIVE, percepts=(
                           A.PerceptStep(step=Step(actuator="light_field", params={},
                                                   id="fake:c1:0:light_field"),
                                         function=A.SUPPORT, image=second),)),
        ]
    ap.GroqArgumentPlanner.propose = _propose
    ap.GroqArgumentPlanner._get_client = lambda self: object()   # "available", so the view says so
    _receipt("argument_planner", "fake", model="vertical-rehearsal-fake")

    class FakeLLM(comp.LLM):
        def __init__(self):
            super().__init__(client=None, model="fake/composer")

        def complete(self, system, user):
            ids = [i for i in re.findall(r'"id":\s*"([^"]+)"', user) if not i.startswith("<")]
            return json.dumps({"prose": "The field concentrates toward one side of the frame.",
                               "grounded_in": ids, "relevance": [], "qualified": False,
                               "thesis": "The field concentrates toward one side of the frame."})
    comp.LLM.from_service = classmethod(lambda cls: FakeLLM())
    _receipt("composer", "fake", model="fake/composer")

    _renders = {"n": 0}

    async def _render(system, user):
        # Distinct prose per render, so two passages can never be told apart only by id: the
        # audit's "no quarantined prose in the export" check must see the text itself differ.
        _renders["n"] += 1
        n = _renders["n"]
        return json.dumps({"passage": f"The latch gave before she decided to push (render {n}).",
                           "refusal": ""}), "fake/manuscript_renderer"
    render_svc._call_model = _render
    _receipt("manuscript_renderer", "fake", model="fake/manuscript_renderer")

    async def _align(system, user):
        return json.dumps({"flags": [{"element": "restraint", "kind": "diverges",
                                      "evidence": "decided to push",
                                      "note": "names the decision the operator withholds"}]}), \
            "fake/alignment_reader"
    align._call_model = _align
    _receipt("alignment_reader", "fake", model="fake/alignment_reader")


def _live_model_receipts() -> None:
    from backend.config import settings
    groq = bool(getattr(settings, "GROQ_API_KEY", None))
    openrouter = bool(getattr(settings, "OPENROUTER_API_KEY", None)) and \
        settings.OPENROUTER_API_KEY not in ("", "ci", "unset")
    for seam in ("groq_planner", "argument_planner", "composer", "manuscript_renderer",
                 "alignment_reader"):
        _receipt(seam, "live" if groq else "unavailable", provider="groq",
                 credential="GROQ_API_KEY", present=groq)
    _receipt("semantic_annotator", "live" if openrouter else "unavailable", provider="openrouter",
             credential="OPENROUTER_API_KEY", present=openrouter)


if FAKES in ("all", "ml_only"):
    _bind_ml_fakes()
if FAKES == "all":
    _bind_model_fakes()
else:
    _live_model_receipts()
    if FAKES == "none":
        _receipt("gpu_producers", "live")


# ── 2. fault injection + 3. write log ─────────────────────────────────────────────────────────

_WRITE_OPS = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
              "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
              "find_one_and_delete", "bulk_write")


def _install_collection_wrapper() -> None:
    from motor.motor_asyncio import AsyncIOMotorCollection

    for op in _WRITE_OPS:
        original = getattr(AsyncIOMotorCollection, op, None)
        if original is None:
            continue

        def make(op_name, orig):
            async def wrapped(self, *args, **kwargs):
                name = self.name
                with _LOCK:
                    WRITES.append({"collection": name, "op": op_name})
                    armed = [f for f in FAULTS if f["collection"] == name and not f.get("fired")
                             and (f.get("op") in (None, "", op_name))]
                    fault = None
                    for f in armed:
                        f["seen"] = f.get("seen", 0) + 1
                        if f["seen"] >= f.get("after", 1):
                            fault = f
                            break
                if fault is not None:
                    mode = fault.get("mode", "raise")
                    if mode == "raise":
                        fault["fired"] = True
                        raise RuntimeError(f"injected write failure: {name}.{op_name}")
                    if mode == "raise_after":
                        # The write HAPPENS, then the response is lost: the client sees a 500.
                        out = await orig(self, *args, **kwargs)
                        fault["fired"] = True
                        raise RuntimeError(f"injected response loss after {name}.{op_name}")
                    if mode == "exit_after":
                        await orig(self, *args, **kwargs)
                        fault["fired"] = True
                        os._exit(86)
                return await orig(self, *args, **kwargs)
            return wrapped

        setattr(AsyncIOMotorCollection, op, make(op, original))


_install_collection_wrapper()

# ── the app ───────────────────────────────────────────────────────────────────────────────────

from backend.main import app  # noqa: E402  (after the fakes, deliberately)
from fastapi import APIRouter, Request  # noqa: E402

control = APIRouter()


def _loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="rehearsal control is loopback-only")


@control.get("/__rehearsal/receipts")
async def receipts(request: Request):
    _loopback(request)
    return {"fakes": FAKES, "receipts": RECEIPTS, "pid": os.getpid()}


@control.get("/__rehearsal/writes")
async def writes(request: Request, since: int = 0):
    _loopback(request)
    with _LOCK:
        return {"count": len(WRITES), "writes": WRITES[since:]}


@control.post("/__rehearsal/fault")
async def arm_fault(request: Request):
    """`{collection, op?, mode: raise|raise_after|exit_after, after?: N}` → armed fault id."""
    _loopback(request)
    body = await request.json()
    fault = {"id": len(FAULTS), "collection": body["collection"], "op": body.get("op"),
             "mode": body.get("mode", "raise"), "after": int(body.get("after", 1)),
             "seen": 0, "fired": False}
    with _LOCK:
        FAULTS.append(fault)
    return fault


@control.delete("/__rehearsal/fault")
async def clear_faults(request: Request):
    _loopback(request)
    with _LOCK:
        fired = [f for f in FAULTS if f.get("fired")]
        FAULTS.clear()
    return {"cleared": True, "fired": fired}


@control.get("/__rehearsal/faults")
async def list_faults(request: Request):
    _loopback(request)
    return {"faults": FAULTS}


app.include_router(control)
