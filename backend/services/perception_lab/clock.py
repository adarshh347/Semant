"""
PERCEPTUAL-ORGANS-002 Lane D — the two ambient facts the conductor refuses to reach for.

A run needs the time and it needs fresh ids, and those are the only two impurities in this whole
lane. Both are INJECTED rather than imported, for the reason Lane A gives about defaults: a module
that calls `datetime.now()` and `uuid4()` inside itself produces a different record every time it
runs, so the only assertion a test can make about its output is that it has the right shape. A
test that cannot pin a value cannot pin a law.

With both injected, an entire orchestration — plan, run, stage attempts, artifacts, response — is
byte-identical across two runs of the same input. That is what makes the mutation suite possible:
break one law, and exactly one field of one record changes.

WHY `monotonic_ms` IS SEPARATE FROM `now_iso`. A duration measured by subtracting two wall-clock
readings is a duration that an NTP correction can make negative, and `StageAttempt.duration_ms`
declares `ge=0`. They are two different questions — "what time is it" and "how long has this
taken" — and the standard library keeps them apart for the same reason.

PURE. No database, no network, no model.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """What time it is, and how long something took. Never both from one reading."""

    def now_iso(self) -> str:
        """An ISO-8601 instant WITH an offset — what every lab record's timestamp fields want."""
        ...

    def monotonic_ms(self) -> int:
        """Milliseconds from an arbitrary origin, never going backwards."""
        ...


class SystemClock:
    """The real one. The only place in this lane that reads the machine's time."""

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z")

    def monotonic_ms(self) -> int:
        import time
        return int(time.monotonic() * 1000)


@dataclass
class FrozenClock:
    """A clock that moves only when a test moves it.

    `advance()` moves both hands together, so a stage that "took" 40ms is 40ms on the wall and 40ms
    on the stopwatch. A clock whose two hands could disagree would let a test pass that a real
    clock would fail.
    """
    start: str = "2026-08-10T09:00:00Z"
    elapsed_ms: int = 0

    def __post_init__(self) -> None:
        self._base = datetime.fromisoformat(self.start.replace("Z", "+00:00"))

    def advance(self, ms: int) -> "FrozenClock":
        if ms < 0:
            raise ValueError("a monotonic clock does not go backwards")
        self.elapsed_ms += int(ms)
        return self

    def now_iso(self) -> str:
        moment = self._base + timedelta(milliseconds=self.elapsed_ms)
        return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def monotonic_ms(self) -> int:
        return self.elapsed_ms


@runtime_checkable
class IdFactory(Protocol):
    """Fresh ids, by prefix. The conductor mints every id in the lab; no adapter ever does."""

    def mint(self, prefix: str) -> str:
        ...


class UuidIds:
    """The real one. `art_3f9c…`, unique across processes and machines."""

    def mint(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class SequentialIds:
    """`art_1`, `art_2`, `run_1` — one counter per prefix, so a test can name what it expects.

    Per-prefix rather than global on purpose: a global counter makes every id in a test depend on
    how many ids of OTHER kinds were minted before it, so adding a stage attempt renumbers the
    artifacts and a diff nobody meant to make shows up in six assertions.
    """
    counters: Dict[str, int] = field(default_factory=dict)

    def mint(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}_{self.counters[prefix]}"


__all__ = ["Clock", "SystemClock", "FrozenClock", "IdFactory", "UuidIds", "SequentialIds"]
