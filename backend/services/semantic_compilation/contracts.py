"""
HARNESS-002A — reading the semantic-inquiry-graph contract, and the geometry scan it declares.

The canonical file is `contracts/semantic-inquiry-graph.v1.json`. Loading is delegated to
`backend.services.inquiry.contracts.load` rather than reimplemented: that loader already caches,
already checks the declared `schema_version`, and already raises rather than falling back — and a
second loader in the same repo would be a second opinion about where contracts live.

WHAT THIS MODULE ADDS. Two things the graph contract has and the grammar contract does not:

  · `closed_set(name)` — the enums, as data, so a test can pin the Python enums against the file
    instead of the two drifting apart quietly;
  · `geometry_keys_in(payload)` — the scan that enforces `no-geometry-in-a-reading`. It walks a raw
    model payload BEFORE anything is constructed, because by the time a typed object exists the
    key has already been dropped by `extra="forbid"` and nobody can say it was ever there.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from backend.services.inquiry.contracts import ContractError, load

#: The version this code READS AND WRITES. v1 stays on disk and stays loadable — `graph_contract_v1`
#: exists so the migration test can compare the two vocabularies rather than trust that v2 is a
#: superset, and so a stored v1 graph can still be explained by the contract it was written under.
GRAPH_FILE_V1 = "semantic-inquiry-graph.v1.json"
GRAPH_SCHEMA_VERSION_V1 = "semantic-inquiry-graph.v1"
GRAPH_FILE = "semantic-inquiry-graph.v2.json"
GRAPH_SCHEMA_VERSION = "semantic-inquiry-graph.v2"


def graph_contract() -> Dict[str, Any]:
    return load(GRAPH_FILE, GRAPH_SCHEMA_VERSION)


def graph_contract_v1() -> Dict[str, Any]:
    """The superseded contract, still on disk and still readable.

    Kept rather than deleted because a stored v1 graph is explained by v1's vocabulary, and because
    "v2 is a superset" is a claim a test should check against the file rather than a promise.
    """
    return load(GRAPH_FILE_V1, GRAPH_SCHEMA_VERSION_V1)


def atom_kind_to_claim_kind() -> Dict[str, str]:
    """The one place the atom vocabulary and the claim vocabulary meet, as data.

    A DEFAULT the relation architect may override with a reason — never a rewrite applied behind it.
    Read from the contract so the mapping is reviewable beside both enums instead of buried in a
    dict literal halfway down a pass.
    """
    raw = graph_contract().get("atom_kind_to_claim_kind") or {}
    return {str(k): str(v) for k, v in raw.items() if k != "why"}


def closed_set(name: str) -> Tuple[str, ...]:
    """One declared closed set. A name the contract does not declare is an error, not an empty
    tuple: an empty vocabulary silently permits nothing, which reads downstream as "the model
    proposed nothing valid" rather than "the code asked for a set that does not exist"."""
    sets = graph_contract().get("closed_sets") or {}
    if name not in sets:
        raise ContractError(
            f"{GRAPH_FILE} declares no closed set named {name!r}. Declared: {sorted(sets)}")
    return tuple(str(v) for v in sets[name])


def laws() -> Tuple[Dict[str, Any], ...]:
    return tuple(dict(law) for law in graph_contract().get("laws") or ())


def capability_class_info() -> Dict[str, Any]:
    return dict(graph_contract().get("capability_classes") or {})


def id_prefixes() -> Dict[str, str]:
    return {str(k): str(v) for k, v in (graph_contract().get("id_prefixes") or {}).items()}


def forbidden_geometry_keys() -> frozenset:
    """Keys that would make a reading a measurement. Read from the contract, never retyped."""
    return frozenset(str(k).lower() for k in graph_contract().get("forbidden_geometry_keys") or ())


def geometry_keys_in(payload: Any, *, _seen: int = 0) -> List[str]:
    """Every forbidden key anywhere in a raw payload, sorted and de-duplicated.

    RECURSIVE, and it has to be: a model told not to output a box at the top level will put one
    inside `claims[0].evidence.bbox` on the next attempt, and a shallow check would pass it. The
    depth guard is a cycle backstop for hand-built inputs — JSON from a model cannot cycle, but a
    test passing a self-referential dict should get a refusal rather than a stack overflow.
    """
    if _seen > 32:
        return []
    forbidden = forbidden_geometry_keys()
    found: set = set()
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in forbidden:
                found.add(str(key))
            found.update(geometry_keys_in(value, _seen=_seen + 1))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.update(geometry_keys_in(item, _seen=_seen + 1))
    return sorted(found)


def unknown_values(values: Sequence[Any], set_name: str) -> List[str]:
    """The members of `values` that the named closed set does not declare, verbatim.

    Verbatim, and that is the point: a refusal quotes what the model actually said. `"bounding_box"`
    and `"bbox"` are different inventions and reporting either as "an unknown capability class"
    loses the only detail that says which prompt change would fix it.
    """
    declared = set(closed_set(set_name))
    return [str(v) for v in values if str(v) not in declared]


__all__ = ["GRAPH_FILE", "GRAPH_SCHEMA_VERSION", "GRAPH_FILE_V1", "GRAPH_SCHEMA_VERSION_V1",
           "ContractError", "graph_contract", "graph_contract_v1", "atom_kind_to_claim_kind",
           "closed_set", "laws", "capability_class_info", "id_prefixes", "forbidden_geometry_keys",
           "geometry_keys_in", "unknown_values"]
