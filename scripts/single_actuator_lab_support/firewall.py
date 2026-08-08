"""The capability firewall. Built before the SAM adapter, and every arm goes through it.

WHAT IT GUARANTEES, and each clause is here because its absence is a way the lab could lie:

  · `allowed` contains EXACTLY the manifest's lock — a single string, not a list, because a
    list is a thing someone widens;
  · the call budget is exactly one, and it is spent by ATTEMPTING, not by succeeding;
  · a planner naming another actuator is REFUSED AND RECORDED, never filtered out of the
    proposal into apparent success — how often the mind reaches past its hands is the
    observable, and quietly dropping it destroys the measurement;
  · param keys are intersected with the PRODUCTION actuator's declaration, so a manifest
    cannot widen what the actuator accepts;
  · every attempted call is recorded, including the refused ones;
  · success requires exactly one call to the locked actuator, and `lock_held` is computed from
    what actually reached an instrument rather than from what was configured.

DATABASE WRITES ARE INSTRUMENTED, NOT BANNED BY IMPORT DISCIPLINE. Arm B runs the production
Director runner, which imports `backend.routers.posts`, which transitively imports
`backend.database` — so "the lab does not import a collection" would be a false guarantee. The
write methods on every collection are wrapped instead, and any call is recorded as a violation
and raised. An assertion about behaviour beats an assertion about imports whenever the thing
being tested is somebody else's code.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Refusal reasons. A closed set, mirrored in the trace schema, so a refusal cannot be recorded
# as free text that nothing downstream can count.
NOT_LOCKED = "not_the_locked_actuator"
UNKNOWN_ACTUATOR = "unknown_actuator"
BUDGET_EXHAUSTED = "call_budget_exhausted"
NO_PHRASE = "no_phrase"
REPLAY_FORBIDS = "replay_mode_forbids_calls"
CAPABILITY_UNAVAILABLE = "capability_unavailable"

# Outcomes, matching the Director's own vocabulary so the lab never invents a parallel one.
OK, EMPTY, UNAVAILABLE, ERROR = "ok", "empty", "unavailable", "error"

#: Mongo write methods. Read methods are deliberately absent — Arm B is allowed to LOOK at a
#: post if it must; it is never allowed to change one.
_WRITE_METHODS = (
    "insert_one", "insert_many", "update_one", "update_many", "replace_one",
    "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
    "find_one_and_delete", "bulk_write", "drop",
)


class FirewallViolation(Exception):
    """The lab did something the lock forbids. Never caught and turned into a note: a violated
    run is not a run with a caveat, it is a run whose evidence cannot be used."""


class CallRefused(Exception):
    """A call the firewall declined to let through. Refusals are ordinary and expected — an
    orchestrated run that reaches for `semantic_read` and is refused is a SUCCESSFUL
    measurement of the planner, not a failure of the lab."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass
class Attempt:
    """One call that reached an instrument."""
    call_index: int
    call_budget: int
    actuator: str
    kind: str                       # "organ" | "actuator"
    adapter: Optional[str] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    latency_ms: Optional[float] = None
    warm: Optional[bool] = None
    load_ms: Optional[float] = None
    outcome: str = OK
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_index": self.call_index, "call_budget": self.call_budget,
            "actuator": self.actuator, "adapter": self.adapter, "kind": self.kind,
            "started_at": self.started_at, "ended_at": self.ended_at,
            "latency_ms": self.latency_ms, "warm": self.warm, "load_ms": self.load_ms,
            "outcome": self.outcome, "error": self.error,
        }


@dataclass
class Refusal:
    actuator: Optional[str]
    reason: str
    detail: str = ""
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"actuator": self.actuator, "reason": self.reason,
                "detail": self.detail, "params": self.params}


@dataclass
class Authorization:
    """The firewall's answer about one proposed step, BEFORE anything runs."""
    allowed: bool
    actuator: Optional[str]
    params: Dict[str, Any] = field(default_factory=dict)
    dropped: List[str] = field(default_factory=list)
    refusal: Optional[Refusal] = None


class Firewall:
    """One lock, one budget, one record of everything attempted.

    `replay=True` makes every invocation raise. That is what makes "replay performs zero live
    calls" a property of the harness rather than a promise in a docstring — the replay arm could
    not call the organ if its author wanted it to.
    """

    def __init__(self, actuator_lock: str, *, call_budget: int = 1, replay: bool = False,
                 allowed_params: Optional[List[str]] = None):
        if not isinstance(actuator_lock, str) or not actuator_lock.strip():
            raise FirewallViolation("the firewall needs exactly one actuator name")
        self.lock = actuator_lock.strip()
        self.budget = int(call_budget)
        if self.budget < 1:
            raise FirewallViolation("call budget must be at least 1")
        self.replay = bool(replay)
        self._manifest_params = list(allowed_params) if allowed_params else None

        self.attempts: List[Attempt] = []
        # Authorizations GRANTED, which is not the same number as calls made. A granted
        # authorization reserves a call: without this the budget could only be spent by
        # invoking, so a planner proposing three steps would have all three authorized (nothing
        # had run yet) and the surplus would vanish from the record instead of being refused.
        self.granted: int = 0
        self.refusals: List[Refusal] = []
        self.dropped_params: List[Dict[str, Any]] = []
        self.db_writes: List[Dict[str, Any]] = []
        self._db_restore: List[Tuple[Any, str, Any]] = []

    # ── the vocabulary the planner is allowed to see ────────────────────────────────────────

    def catalogue(self) -> List[Dict[str, Any]]:
        """The actuator catalogue, containing ONLY the lock.

        Built from the production capability table rather than hand-written, so the lab shows
        the planner the real `requires`/`produces`/`param_keys` for the one tool it has. An
        orchestration framework never broadens the lock: this is the method that would have to
        be edited to do so, and it returns a one-element list by construction.
        """
        from backend.services.director.capabilities import ACTUATORS
        a = ACTUATORS[self.lock]
        return [{
            "actuator": a.name,
            "does": a.summary,
            "requires": [r.describe() for r in a.requires],
            "produces": [p.value for p in a.produces],
            "params_you_may_set": list(self.allowed_param_keys()),
        }]

    def allowed_param_keys(self) -> Tuple[str, ...]:
        """The intersection of the manifest's `allowed_params` and the actuator's declared
        `param_keys`. The intersection, so neither side can widen the other: a manifest asking
        for `region_ids` gets nothing, and an actuator that grows a param tomorrow does not
        become reachable from an old manifest."""
        from backend.services.director.capabilities import get as get_actuator
        actuator = get_actuator(self.lock)
        declared = set(actuator.param_keys) if actuator else set()
        if self._manifest_params is None:
            return tuple(sorted(declared))
        return tuple(sorted(declared & set(self._manifest_params)))

    # ── authorization ───────────────────────────────────────────────────────────────────────

    def authorize(self, actuator: Optional[str], params: Optional[Dict[str, Any]] = None,
                  ) -> Authorization:
        """May this step run? Records the refusal if not.

        Order matters and is deliberate: the NAME is checked before the budget, so a planner
        that asked for `semantic_read` is recorded as having reached for an unlocked actuator
        rather than as having merely run out of calls. The two say different things about the
        planner and only one of them is about the planner at all.
        """
        from backend.services.director.capabilities import get as get_actuator
        raw = dict(params or {})
        name = (actuator or "").strip()

        if not name:
            refusal = Refusal(None, UNKNOWN_ACTUATOR, "the step named no actuator", raw)
            self.refusals.append(refusal)
            return Authorization(False, None, refusal=refusal)

        if name != self.lock:
            known = get_actuator(name) is not None
            reason = NOT_LOCKED if known else UNKNOWN_ACTUATOR
            detail = (f"{name!r} is a real actuator but this lab is locked to {self.lock!r}"
                      if known else
                      f"{name!r} is not in the production capability table")
            refusal = Refusal(name, reason, detail, raw)
            self.refusals.append(refusal)
            return Authorization(False, name, refusal=refusal)

        allowed_keys = set(self.allowed_param_keys())
        kept = {k: v for k, v in raw.items() if k in allowed_keys}
        dropped = sorted(str(k) for k in raw if k not in allowed_keys)
        if dropped:
            # Recorded, never silent. This is where a planner trying to author geometry, a
            # region id, or a confidence would show up, and it shows up nowhere else.
            self.dropped_params.append(
                {"actuator": name, "keys": dropped,
                 "reason": f"not in the intersection of the manifest's allowed_params and "
                           f"{name}.param_keys"})

        spent = max(self.granted, len(self.attempts))
        if spent >= self.budget:
            refusal = Refusal(name, BUDGET_EXHAUSTED,
                              f"budget of {self.budget} call(s) already spent or reserved", kept)
            self.refusals.append(refusal)
            return Authorization(False, name, params=kept, dropped=dropped, refusal=refusal)

        self.granted += 1
        return Authorization(True, name, params=kept, dropped=dropped)

    def refuse(self, actuator: Optional[str], reason: str, detail: str = "",
               params: Optional[Dict[str, Any]] = None) -> Refusal:
        """Record a refusal the firewall did not itself decide — a missing phrase, an
        unavailable capability. Kept here so the trace has ONE list of refusals rather than one
        per arm."""
        refusal = Refusal(actuator, reason, detail, dict(params or {}))
        self.refusals.append(refusal)
        return refusal

    # ── invocation ──────────────────────────────────────────────────────────────────────────

    def invoke(self, actuator: str, kind: str, fn: Callable[[], Any], *,
               adapter: Optional[str] = None, warm: Optional[bool] = None,
               load_ms: Optional[float] = None) -> Tuple[Any, Attempt]:
        """Run one budgeted call through the lock. The ONLY way anything in this lab reaches an
        instrument.

        The budget is spent by attempting rather than by succeeding. An actuator that raises has
        still been called — the model was loaded, the image was read, the wall clock moved — and
        a budget that refunded failures would let a lab retry until something came back, which
        is the shape of searching for a result rather than measuring for one.
        """
        if self.replay:
            self.refuse(actuator, REPLAY_FORBIDS,
                        "replay rebuilds from frozen observations and calls nothing")
            raise FirewallViolation(
                f"replay mode attempted to invoke {actuator!r} — replay must make no live call")
        if actuator != self.lock:
            self.refuse(actuator, NOT_LOCKED, f"locked to {self.lock!r}")
            raise FirewallViolation(
                f"attempted to invoke {actuator!r} while locked to {self.lock!r}")
        if len(self.attempts) >= self.budget:
            self.refuse(actuator, BUDGET_EXHAUSTED, f"budget of {self.budget} already spent")
            raise FirewallViolation(
                f"call budget of {self.budget} exhausted; {actuator!r} refused")

        attempt = Attempt(call_index=len(self.attempts) + 1, call_budget=self.budget,
                          actuator=actuator, kind=kind, adapter=adapter, warm=warm,
                          load_ms=load_ms, started_at=time.time())
        # Appended BEFORE the call, so a call that never returns still shows in the record.
        self.attempts.append(attempt)
        t0 = time.perf_counter()
        try:
            result = fn()
        except Exception as e:
            attempt.ended_at = time.time()
            attempt.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            attempt.outcome = ERROR
            attempt.error = f"{type(e).__name__}: {e}"
            return None, attempt
        attempt.ended_at = time.time()
        attempt.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        return result, attempt

    # ── database instrumentation ────────────────────────────────────────────────────────────

    def guard_database(self) -> int:
        """Wrap every write method on every Mongo collection `backend.database` exposes.

        Returns the number of methods instrumented, so a test can assert the guard actually
        found something — a guard that silently instrumented nothing would pass every invariance
        check it was supposed to enforce.
        """
        import backend.database as db

        count = 0
        for attr in dir(db):
            if not attr.endswith("_collection"):
                continue
            collection = getattr(db, attr, None)
            if collection is None:
                continue
            for method in _WRITE_METHODS:
                original = getattr(collection, method, None)
                if original is None:
                    continue
                setattr(collection, method, self._trap(attr, method))
                self._db_restore.append((collection, method, original))
                count += 1
        return count

    def _trap(self, collection_name: str, method: str) -> Callable[..., Any]:
        def _refuse(*args: Any, **kwargs: Any) -> Any:
            record = {"collection": collection_name, "method": method}
            self.db_writes.append(record)
            raise FirewallViolation(
                f"the lab attempted a database write: {collection_name}.{method}(). "
                f"This lab proposes and never commits.")
        return _refuse

    def release_database(self) -> None:
        for collection, method, original in reversed(self._db_restore):
            try:
                setattr(collection, method, original)
            except Exception:
                pass
        self._db_restore = []

    def __enter__(self) -> "Firewall":
        self.guard_database()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release_database()

    # ── what the trace reads ────────────────────────────────────────────────────────────────

    @property
    def actuators_called(self) -> List[str]:
        return [a.actuator for a in self.attempts]

    @property
    def lock_held(self) -> bool:
        """Computed from what REACHED an instrument, never from what was configured. A lock
        that reported itself held would be reporting its own intentions."""
        return all(a.actuator == self.lock for a in self.attempts)

    @property
    def leaked(self) -> bool:
        return not self.lock_held

    @property
    def budget_respected(self) -> bool:
        return len(self.attempts) <= self.budget

    def requested_unlocked(self) -> List[str]:
        """Actuator names something asked for and was refused for not being the lock."""
        return sorted({r.actuator for r in self.refusals
                       if r.reason in (NOT_LOCKED, UNKNOWN_ACTUATOR) and r.actuator})

    def receipts(self) -> Dict[str, Any]:
        return {
            "invocations": [a.to_dict() for a in self.attempts],
            "refused_actions": [r.to_dict() for r in self.refusals],
            "dropped_params": list(self.dropped_params),
            "database_writes_attempted": list(self.db_writes),
        }
