"""
What the audit is made of: canonical hashes of every fixture document, field-level diffs between
snapshots, and the evidence record every stage appends to.

A hash here is of the CANONICAL document — `json.dumps(sort_keys=True, default=str)` over the raw
Mongo doc — so a reordered key is not a change and a changed timestamp is. The audit's rule
"fixture posts change only at explicitly accepted evidence steps" is checked by hashing every
fixture post after every stage and requiring each hash change to be claimed by a stage that
declared it would write.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def canonical(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, default=str, separators=(",", ":"))


def digest(doc: Any) -> str:
    return hashlib.sha256(canonical(doc).encode()).hexdigest()


def field_diff(before: Any, after: Any, path: str = "") -> List[Dict[str, Any]]:
    """Every leaf that differs, as `{path, before, after}`. Lists are compared by index; a length
    change shows up as added/removed entries rather than one opaque 'list changed'."""
    out: List[Dict[str, Any]] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for k in sorted(set(before) | set(after)):
            p = f"{path}.{k}" if path else str(k)
            if k not in before:
                out.append({"path": p, "before": None, "after": _short(after[k]), "kind": "added"})
            elif k not in after:
                out.append({"path": p, "before": _short(before[k]), "after": None, "kind": "removed"})
            else:
                out.extend(field_diff(before[k], after[k], p))
    elif isinstance(before, list) and isinstance(after, list):
        for i in range(max(len(before), len(after))):
            p = f"{path}[{i}]"
            if i >= len(before):
                out.append({"path": p, "before": None, "after": _short(after[i]), "kind": "added"})
            elif i >= len(after):
                out.append({"path": p, "before": _short(before[i]), "after": None, "kind": "removed"})
            else:
                out.extend(field_diff(before[i], after[i], p))
    else:
        if canonical(before) != canonical(after):
            out.append({"path": path, "before": _short(before), "after": _short(after), "kind": "changed"})
    return out


def _short(v: Any, limit: int = 160) -> Any:
    if isinstance(v, (dict, list)):
        s = canonical(v)
        return s if len(s) <= limit else s[:limit] + f"…(+{len(s) - limit})"
    return v if not isinstance(v, str) or len(v) <= limit else v[:limit] + "…"


@dataclass
class Evidence:
    """The run's evidence record. Every id, key, receipt and refusal a stage captured, keyed by the
    stage that captured it, plus the hash timeline the mutation audit reads."""
    ids: Dict[str, Dict[str, Any]] = field(default_factory=dict)         # stage → {name: id}
    receipts: List[Dict[str, Any]] = field(default_factory=list)         # model/provider receipts
    refusals: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    operations: List[Dict[str, Any]] = field(default_factory=list)       # op keys / retries
    hash_timeline: List[Dict[str, Any]] = field(default_factory=list)    # after each stage
    expected_writes: List[Dict[str, Any]] = field(default_factory=list)  # stage-claimed mutations
    unexpected: List[Dict[str, Any]] = field(default_factory=list)
    screenshots: List[Dict[str, Any]] = field(default_factory=list)
    timings: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def record_id(self, stage: str, **kv: Any) -> None:
        self.ids.setdefault(stage, {}).update({k: _jsonable(v) for k, v in kv.items()})

    def receipt(self, stage: str, **kv: Any) -> None:
        self.receipts.append({"stage": stage, **_jsonable(kv)})

    def refusal(self, stage: str, **kv: Any) -> None:
        self.refusals.append({"stage": stage, **_jsonable(kv)})

    def conflict(self, stage: str, **kv: Any) -> None:
        self.conflicts.append({"stage": stage, **_jsonable(kv)})

    def operation(self, stage: str, **kv: Any) -> None:
        self.operations.append({"stage": stage, **_jsonable(kv)})

    def expect_write(self, stage: str, post_id: str, why: str) -> None:
        self.expected_writes.append({"stage": stage, "post_id": str(post_id), "why": why})

    def timing(self, stage: str, name: str, ms: float, **kv: Any) -> None:
        self.timings.append({"stage": stage, "name": name, "ms": round(ms, 2), **_jsonable(kv)})

    def to_dict(self) -> Dict[str, Any]:
        return {k: _jsonable(v) for k, v in self.__dict__.items()}


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


class Stopwatch:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self.t0) * 1000.0
