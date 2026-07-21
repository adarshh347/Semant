"""
CIRCULATION-SPINE-001 · P1 — production VisionRun / VisionStageEvent contract.

A fresh, execution-engine-neutral observability vocabulary for vision operations. It
records what a run *did*; it never drives control flow (write-behind) and never carries
geometry (masks/boxes are the Region's authority, never an event's).

Import-safe: like its sibling ``contracts.py``, this module imports no torch/model/Mongo
code, so a route can adopt it without pulling in the segmentation stack. Persistence
lives in ``backend/services/vision_run_service.py``.

Neutrality rules (P0.5 Contract Atlas §06 — so the same contract survives a later
migration onto ``Scheduler.run_plan`` without a schema change):

  1. **No implied linearity.** Events are an observation-ordered list; causal order is
     carried by ``dependencies``, never by array position (Invariants 14 & 15).
  2. **Free-form stage identity.** ``stage_id`` is a stable string; ``capability`` is an
     optional tag. The current inline route's stage names and a future planner's job
     kinds both fit without migration.
  3. **Status = ``JobStatus`` verbatim** — both worlds already speak it, including the
     fallback story (fallback = succeeded-with-``fallbacks[]``; skipped-dep = ``SKIPPED``).
  4. **Provenance = ``Provenance.as_dict()``** — populated opportunistically, never
     fabricated (Invariant 8: unknown telemetry is absent, not guessed).

This module does NOT import the rehearsal research schemas (Invariant 10); the contract
is authored fresh here.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.services.vision_orchestrator.contracts import JobStatus  # import-safe

# The repo's own versioning idiom (cf. BACKUP_SCHEMA = "vision-f-backup-v1").
CONTRACT_VERSION = "vision-run-v1"

# The operation this increment instruments. NB: deliberately distinct from the Groq
# fallback detector ``vision_service.detect_regions`` — that appears ONLY as the
# ``dissect.fallback.detect`` stage's adapter, never as a run operation (no conflation).
OPERATION_DISSECT = "dissect"

# Free-form, stable stage ids for the current inline Dissect route (P0 §01 call-trace).
# A future Scheduler may emit different ids for the same capabilities; that is allowed.
STAGE_RECEIVE         = "dissect.receive"
STAGE_FETCH_IMAGE     = "dissect.fetch_image"
STAGE_ROUTE_DOMAIN    = "dissect.route_domain"
STAGE_SEGMENT_FASHION = "dissect.segment.fashion"
STAGE_SEGMENT_ARCH    = "dissect.segment.architecture"
STAGE_SEGMENT_GENERAL = "dissect.segment.general"
STAGE_SEGMENT_COARSE  = "dissect.segment.coarse"      # block-level failure marker only
STAGE_MERGE_ANCHORS   = "dissect.merge_anchors"
STAGE_FALLBACK_DETECT = "dissect.fallback.detect"
STAGE_DECOMPOSE_FINE  = "dissect.decompose_fine"
STAGE_MERGE_CURATOR   = "dissect.merge_curator_state"
STAGE_CANONICALIZE    = "dissect.canonicalize_geometry"
STAGE_PERSIST         = "dissect.persist_regions"
STAGE_COMPLETE        = "dissect.complete"

# A run that reaches one of these is done; it must not transition back to active.
TERMINAL_STATUSES = frozenset({
    JobStatus.SUCCEEDED, JobStatus.PARTIAL, JobStatus.FAILED,
    JobStatus.SKIPPED, JobStatus.CANCELLED, JobStatus.TIMED_OUT, JobStatus.UNAVAILABLE,
})
# Non-terminal statuses a run may occupy while still executing.
ACTIVE_STATUSES = frozenset({JobStatus.PENDING, JobStatus.RUNNING})

# A RUNNING run whose ``updated_at`` is older than this is projected as *stale* — the
# read API must never describe a stalled record as live forever. Bounded and
# timestamp-based; deliberately NOT a background reaper process (Invariant: no new
# distributed system for P1).
STALE_AFTER_SECONDS = 120

# Geometry never enters an event. Masks/boxes/polygons are the Region's authority; an
# event carries only bounded summaries (counts, ids, source strings) — Invariant 6, and
# "do not persist masks or duplicated Region geometry inside events".
_FORBIDDEN_EVENT_KEYS = frozenset({
    "mask_rle", "mask", "rle", "polygon", "polygons", "bbox", "box",
    "region_annotations", "regions", "segmentation", "contours", "points",
})

# ── bounded-telemetry limits (P1.1) ──────────────────────────────────────────
# A Dissect run emits 8–13 events, each carrying a handful of counts/ids/short strings.
# These caps sit far above that (so every normal route value is valid) yet cap a
# pathological/adversarial payload long before it could bloat a Mongo doc or an HTTP body.
# They are NOT a serialization framework — just a recursive shape+size gate.
MAX_PAYLOAD_DEPTH = 6        # detail/provenance nest ≤2 in practice; 6 is generous headroom
MAX_PAYLOAD_ITEMS = 64      # any single dict/list; Provenance has ~13 fields, detail ≤6
MAX_STRING_LEN = 2048       # any string value inside a payload (source strings are ~40 chars)
MAX_ERROR_LEN = 1000        # stored/projected error text (provider errors get truncated, not dropped)
# Only these scalar types may appear in a telemetry payload (bool is an int subclass).
_ALLOWED_SCALARS = (bool, int, float, str)


class GeometryInEventError(ValueError):
    """Raised when a payload would smuggle geometry into a telemetry record."""


class BoundedPayloadError(ValueError):
    """Raised when a telemetry payload violates the bounded-shape contract (binary,
    unsupported type, over-nested, or over-large)."""


class EventRunMismatch(ValueError):
    """Raised when an event claims a run_id different from the run it is appended to."""


class IllegalRunTransition(ValueError):
    """Raised on an illegal run status transition (e.g. terminal → running)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def as_status(status: Any) -> JobStatus:
    """Coerce a str/JobStatus into JobStatus (raises ValueError on an unknown value)."""
    return status if isinstance(status, JobStatus) else JobStatus(status)


def assert_bounded_payload(payload: Any, where: str, _depth: int = 0) -> None:
    """Recursively enforce the bounded-telemetry contract on a free-form payload.

    Rejects, in one pass: geometry keys (``GeometryInEventError``); and — as
    ``BoundedPayloadError`` — binary/bytes, unsupported non-serializable types (custom
    objects, sets, datetimes, ndarrays, whole Region dicts-as-objects), over-nesting, and
    over-large collections/strings. This is the single gate every telemetry payload passes
    through, so masks, boxes, image bytes and complete Region objects can never enter Mongo
    or an HTTP response. Import-safe: pure Python, no I/O.
    """
    if _depth > MAX_PAYLOAD_DEPTH:
        raise BoundedPayloadError(
            f"telemetry payload {where!r} exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
    if payload is None or isinstance(payload, _ALLOWED_SCALARS):
        if isinstance(payload, str) and len(payload) > MAX_STRING_LEN:
            raise BoundedPayloadError(
                f"telemetry string in {where!r} exceeds {MAX_STRING_LEN} chars")
        return
    if isinstance(payload, (bytes, bytearray, memoryview)):
        raise BoundedPayloadError(f"binary payload forbidden in telemetry field {where!r}")
    if isinstance(payload, dict):
        if len(payload) > MAX_PAYLOAD_ITEMS:
            raise BoundedPayloadError(
                f"telemetry dict {where!r} exceeds {MAX_PAYLOAD_ITEMS} keys")
        for k, v in payload.items():
            if str(k).lower() in _FORBIDDEN_EVENT_KEYS:
                raise GeometryInEventError(
                    f"geometry key {k!r} is forbidden inside telemetry field {where!r}")
            assert_bounded_payload(v, where, _depth + 1)
        return
    if isinstance(payload, (list, tuple)):
        if len(payload) > MAX_PAYLOAD_ITEMS:
            raise BoundedPayloadError(
                f"telemetry list {where!r} exceeds {MAX_PAYLOAD_ITEMS} items")
        for v in payload:
            assert_bounded_payload(v, where, _depth + 1)
        return
    raise BoundedPayloadError(
        f"unsupported telemetry type {type(payload).__name__!r} in field {where!r}")


def bound_error(msg: Optional[Any]) -> Optional[str]:
    """Bound stored/projected error text: keep the leading technical detail, truncate the
    tail so unbounded provider output can never reach Mongo or HTTP. Never dropped — a
    truncated error is more useful than a lost one. (P1.1 correction 6.)"""
    if msg is None:
        return None
    msg = str(msg)
    if len(msg) > MAX_ERROR_LEN:
        return msg[:MAX_ERROR_LEN] + "…[truncated]"
    return msg


def make_event(
    *,
    stage_id: str,
    status: Any,
    run_id: Optional[str] = None,
    capability: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    latency_ms: Optional[float] = None,
    dependencies: Optional[List[str]] = None,
    adapter: Optional[str] = None,
    provenance: Optional[Dict[str, Any]] = None,
    fallbacks: Optional[List[str]] = None,
    input_refs: Optional[List[Any]] = None,
    output_refs: Optional[List[Any]] = None,
    error: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    observed_at: Optional[datetime] = None,
    event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one immutable VisionStageEvent as a Mongo-ready dict.

    ``latency_ms`` is present only when actually measured; device/dtype/vram live inside
    ``provenance`` and appear only when a path really knows them — never fabricated
    (Invariant 8). Every free-form payload passes the bounded+geometry gate
    (``assert_bounded_payload``); ``error`` is truncated, not rejected. ``dependencies``
    are **stage_id strings** (causal prerequisites), represented independently of array
    position (Invariant 15).
    """
    status = as_status(status)
    for name, payload in (("detail", detail), ("input_refs", input_refs),
                          ("output_refs", output_refs), ("provenance", provenance),
                          ("fallbacks", fallbacks), ("dependencies", dependencies)):
        if payload is not None:
            assert_bounded_payload(payload, name)
    return {
        "event_id": event_id or uuid.uuid4().hex,
        "run_id": run_id,
        "contract_version": CONTRACT_VERSION,
        "stage_id": stage_id,
        "capability": capability,
        "status": status.value,
        "observed_at": observed_at or _now(),
        "started_at": started_at,
        "completed_at": completed_at,
        "latency_ms": latency_ms,
        # dependencies are stage_id strings, NOT event_ids (see module + schema docs).
        "dependencies": list(dependencies) if dependencies else [],
        "adapter": adapter,
        "provenance": provenance,                       # Provenance.as_dict() or None
        "fallbacks": list(fallbacks) if fallbacks else [],
        "input_refs": list(input_refs) if input_refs else [],
        "output_refs": list(output_refs) if output_refs else [],
        "error": bound_error(error),
        "detail": detail,
    }


def new_run_doc(
    *,
    post_id: str,
    operation: str = OPERATION_DISSECT,
    initiator: Optional[str] = None,
    requested_profile: Optional[Dict[str, Any]] = None,
    status: Any = JobStatus.RUNNING,
) -> Dict[str, Any]:
    """Build a fresh VisionRun document (mirrors the proven ``agent_runs`` shape).

    ``_id`` is minted by the service (ObjectId); ``run_id`` == ``str(_id)`` in the
    projection, matching the ``agent_runs`` / ``run_helper`` idiom.
    """
    if requested_profile is not None:
        assert_bounded_payload(requested_profile, "requested_profile")
    now = _now()
    return {
        "contract_version": CONTRACT_VERSION,
        "post_id": post_id,
        "operation": operation,
        "status": as_status(status).value,
        "initiator": initiator,
        "requested_profile": requested_profile,
        "actual_source": None,
        "created_at": now,
        "started_at": now,
        "updated_at": now,
        "completed_at": None,
        "terminal_reason": None,
        "error": None,
        "telemetry_degraded": False,
        "events": [],
        "result_summary": None,
    }


class VisionStageEventOut(BaseModel):
    event_id: str
    run_id: Optional[str] = None            # P1.1: was stripped by the response model
    contract_version: Optional[str] = None  # P1.1: one event contract across store/HTTP/examples
    stage_id: str
    capability: Optional[str] = None
    status: str
    observed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    dependencies: List[str] = Field(default_factory=list)   # stage_id strings, not event_ids
    adapter: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    fallbacks: List[str] = Field(default_factory=list)
    input_refs: List[Any] = Field(default_factory=list)
    output_refs: List[Any] = Field(default_factory=list)
    error: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


class VisionRunOut(BaseModel):
    """Transport-safe projection of a VisionRun (bounded; no geometry)."""
    run_id: str
    contract_version: Optional[str] = None
    post_id: Optional[str] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    stale: bool = False
    staleness_seconds: Optional[int] = None
    initiator: Optional[str] = None
    requested_profile: Optional[Dict[str, Any]] = None
    actual_source: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    terminal_reason: Optional[str] = None
    error: Optional[str] = None
    telemetry_degraded: bool = False
    result_summary: Optional[Dict[str, Any]] = None
    events: List[VisionStageEventOut] = Field(default_factory=list)


def project_run(doc: Dict[str, Any], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Transport-safe projection with honest staleness.

    A run that is still ``running``/``pending`` but whose ``updated_at`` is older than
    ``STALE_AFTER_SECONDS`` is flagged ``stale`` with a real age (in seconds) computed
    from actual timestamps — never silently 'completed', never claimed live forever.
    ``events`` keep their stored (observation) order; that order is not a causal claim.
    """
    now = now or _now()
    status = doc.get("status")
    updated_at = doc.get("updated_at")
    stale = False
    staleness_seconds: Optional[int] = None
    active = status in (JobStatus.RUNNING.value, JobStatus.PENDING.value)
    if active and isinstance(updated_at, datetime):
        u = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
        age = (now - u).total_seconds()
        if age > STALE_AFTER_SECONDS:
            stale = True
            staleness_seconds = int(age)
    return {
        "run_id": str(doc.get("_id")),
        "contract_version": doc.get("contract_version"),
        "post_id": doc.get("post_id"),
        "operation": doc.get("operation"),
        "status": status,
        "stale": stale,
        "staleness_seconds": staleness_seconds,
        "initiator": doc.get("initiator"),
        "requested_profile": doc.get("requested_profile"),
        "actual_source": doc.get("actual_source"),
        "created_at": doc.get("created_at"),
        "started_at": doc.get("started_at"),
        "updated_at": updated_at,
        "completed_at": doc.get("completed_at"),
        "terminal_reason": doc.get("terminal_reason"),
        "error": doc.get("error"),
        "telemetry_degraded": bool(doc.get("telemetry_degraded", False)),
        "result_summary": doc.get("result_summary"),
        "events": doc.get("events", []),
    }
