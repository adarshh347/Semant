"""
Semant Writer W3 — typed relations between operators, and the one that acts.

The `relations` field has existed on the operator since W1 and stayed empty. This module
fills it, and draws the line the W3 directive is built around:

  `requires`   A needs B's meaning present to render honestly. **The only edge that feeds
               rendering.** It conditions the SAME span — it never adds one, never
               reorders, never blends.
  `precedes`   an ordering hint the author can see in the graph. Advisory only; it does
               NOT reorder directives.
  `evokes` / `amplifies` / `contrasts`
               associative structure. Rendering-INERT in v1: they describe how the
               author's operators relate, and acting on them would mean letting two
               operators condition one span as a blended field. That is Tier 3, and the
               reason it is Tier 3 is that fused provenance cannot say which operator
               produced which part of the prose — which would break the audit trail
               `GROUNDING.md` rests on.

WHY `requires` IS SAFE WHERE THE OTHERS ARE NOT. Its target is an OPERATOR REFERENCE, not
free text. You cannot write `requires "like Tolstoy"` — the edge can only point at
something already in the author's ontology, so the ontology wall (I5) holds by
construction rather than by a check at render time. Everything an edge can pull is, by
definition, something the author declared. What it still owes the author is disclosure:
every pulled operator is recorded in provenance, marked as pulled rather than typed
(`render.py`), because the author typed only `/A` and the passage must not silently claim
that is all that shaped it.

CYCLES ARE REJECTED TWICE, ON PURPOSE. At EDIT time (`validate_relation`) so the author
cannot draw one, and at RENDER time (`resolve_requires`) so a cycle that reached the data
by any other route — a direct database edit, a restored backup, a future import — cannot
hang the render loop. A guard that exists only at the write path assumes the write path is
the only way data arrives, and it never is.

This module is PURE: no database, no LLM. It takes operators as dicts and answers
questions about them.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: The edge vocabulary. Order is the order the graph legend shows them in.
RELATION_KINDS: Tuple[str, ...] = ("requires", "precedes", "evokes", "amplifies", "contrasts")

#: The ONLY edge that conditions a render. Named as a set of one so the check reads as a
#: membership test rather than a magic string comparison, and so adding a second one later
#: is a deliberate edit here rather than a scattered condition.
RENDERING_KINDS: frozenset = frozenset({"requires"})

#: How deep a `requires` chain may go. A defensive bound, not a design limit: transitive
#: resolution already terminates on cycles, and an ontology 24 operators deep in one chain
#: is a mistake worth surfacing rather than rendering.
MAX_REQUIRES_DEPTH = 24


class RelationError(ValueError):
    """A relation that must not be stored. Raised at edit time, with the reason."""


def normalise(relation: Any) -> Dict[str, str]:
    """Any accepted relation form → `{"target", "kind"}`. Raises on an unusable one."""
    if not isinstance(relation, dict):
        raise RelationError(f"a relation must be an object with a target and a kind, got {relation!r}")
    target = str(relation.get("target") or "").strip()
    kind = str(relation.get("kind") or "").strip().lower()
    if not target:
        raise RelationError("a relation needs a target operator")
    if kind not in RELATION_KINDS:
        raise RelationError(
            f"'{kind or '(none)'}' is not a relation kind — "
            f"use one of: {', '.join(RELATION_KINDS)}"
        )
    return {"target": target, "kind": kind}


def relations_of(operator: Optional[Dict[str, Any]], kind: Optional[str] = None) -> List[Dict[str, str]]:
    """An operator's relations, optionally filtered to one kind. Malformed ones are skipped."""
    out: List[Dict[str, str]] = []
    for raw in (operator or {}).get("relations", []) or []:
        try:
            rel = normalise(raw)
        except RelationError:
            continue          # a relation that cannot be read cannot act
        if kind is None or rel["kind"] == kind:
            out.append(rel)
    return out


def requires_of(operator: Optional[Dict[str, Any]]) -> List[str]:
    """The operator names this operator directly requires."""
    return [r["target"] for r in relations_of(operator, "requires")]


# ── cycle detection ──────────────────────────────────────────────────────────

def find_requires_cycle(
    start: str,
    by_name: Dict[str, Dict[str, Any]],
    *,
    extra_edge: Optional[Tuple[str, str]] = None,
) -> Optional[List[str]]:
    """The cycle through `requires` reachable from `start`, or None.

    `extra_edge` is `(source, target)` — an edge being CONSIDERED but not yet stored, which
    is what makes this usable as the edit-time guard: the author is told the edge would
    close a cycle before it exists, rather than after.

    Returns the cycle as a path (`['a', 'b', 'a']`) so the refusal can show it.
    """
    def edges(name: str) -> List[str]:
        out = list(requires_of(by_name.get(name)))
        if extra_edge and extra_edge[0] == name:
            out.append(extra_edge[1])
        return out

    # Iterative DFS carrying its own path, so a deep ontology cannot blow the stack.
    stack: List[Tuple[str, List[str]]] = [(start, [start])]
    seen_paths: set = set()
    while stack:
        name, path = stack.pop()
        for target in edges(name):
            if target in path:
                return path[path.index(target):] + [target]
            key = (target, tuple(path))
            if key in seen_paths:
                continue
            seen_paths.add(key)
            if len(path) <= MAX_REQUIRES_DEPTH:
                stack.append((target, path + [target]))
    return None


def validate_relation(
    source: str,
    relation: Dict[str, str],
    by_name: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    """Check one proposed edge. Returns the normalised relation, or raises with the reason.

    Three refusals, all at edit time:
      - an unknown KIND — the vocabulary is closed;
      - an UNDEFINED target — I5: an edge may only point at an operator the author
        declared, which is what makes `requires` incapable of importing priors;
      - a CYCLE — structural, and it would make transitive resolution meaningless.
    """
    rel = normalise(relation)

    if rel["target"] == source:
        raise RelationError(f"`{source}` cannot relate to itself")

    if rel["target"] not in by_name:
        raise RelationError(
            f"`{rel['target']}` is not an operator in this project. A relation can only "
            f"point at an operator you have defined — that is what keeps an edge from "
            f"importing something your ontology never declared. "
            f"Define it first with `#create {rel['target']}: …`."
        )

    if rel["kind"] == "requires":
        cycle = find_requires_cycle(source, by_name, extra_edge=(source, rel["target"]))
        if cycle:
            raise RelationError(
                f"`{source} requires {rel['target']}` would close a cycle: "
                f"{' → '.join(cycle)}. A required operator has to be renderable without "
                f"waiting on the one requiring it."
            )

    return rel


def validate_relations(
    source: str,
    relations: Sequence[Any],
    by_name: Dict[str, Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Validate a whole replacement relation set for one operator, in order.

    Each edge is checked against the set accepted so far, so a batch cannot smuggle in a
    cycle that no single edge would have closed on its own.
    """
    accepted: List[Dict[str, str]] = []
    working = dict(by_name)
    working[source] = {**(by_name.get(source) or {}), "relations": accepted}

    for raw in relations or []:
        rel = validate_relation(source, raw, working)
        if any(a["target"] == rel["target"] and a["kind"] == rel["kind"] for a in accepted):
            continue          # the same edge twice is not an error, it is a duplicate
        accepted.append(rel)
        working[source] = {**(by_name.get(source) or {}), "relations": list(accepted)}

    return accepted


# ── transitive resolution, for the render actuator ───────────────────────────

def resolve_requires(
    names: Iterable[str],
    by_name: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """Directly-invoked operator names → `(pulled_names, diagnostics)`.

    Breadth-first from the directly-invoked operators, following `requires` only. Returns
    the operators that were PULLED — never the directly-invoked ones — in a stable order,
    so provenance can mark them apart from what the author typed.

    TERMINATION is guaranteed here and not merely assumed from the edit-time guard: a name
    already visited is never expanded again, so a cycle in the data yields a diagnostic and
    a finite result instead of hanging the render.
    """
    direct = [n for n in names if n]
    seen = set(direct)
    pulled: List[str] = []
    diagnostics: List[str] = []

    # Say so if a cycle is present, BEFORE walking. The traversal below terminates either
    # way, but it cannot tell a cycle from a diamond (`a requires b`, `a requires c`,
    # `b requires c` legitimately revisits `c`) because it does not carry paths. This does,
    # so the two are never conflated: a diamond is silent, a cycle is reported. A cycle in
    # the data means the edit-time guard was bypassed, which the author should hear about.
    reported: set = set()
    for name in direct:
        cycle = find_requires_cycle(name, by_name)
        if cycle:
            key = tuple(sorted(set(cycle)))
            if key not in reported:
                reported.add(key)
                diagnostics.append(
                    f"`requires` cycle in your ontology: {' → '.join(cycle)}. "
                    f"Resolution stopped at the repeat; fix the edge."
                )

    frontier: List[Tuple[str, int]] = [(n, 0) for n in direct]
    while frontier:
        name, depth = frontier.pop(0)
        operator = by_name.get(name)
        if operator is None:
            continue          # an undefined DIRECT operator is the preflight's refusal
        if depth >= MAX_REQUIRES_DEPTH:
            diagnostics.append(
                f"`requires` chain from `{name}` is deeper than {MAX_REQUIRES_DEPTH}; "
                f"stopped following it"
            )
            continue
        for target in requires_of(operator):
            if target in seen:
                # Either already pulled, or the cycle guard doing its job.
                if target in direct or target in pulled:
                    continue
                diagnostics.append(f"`requires` cycle reached `{target}`; stopped following it")
                continue
            missing = by_name.get(target) is None
            seen.add(target)
            if missing:
                # An edge pointing at nothing cannot ground anything. Not a hard refusal:
                # the author's DIRECT request is still renderable, and saying so beats
                # failing the whole span over a dangling edge.
                diagnostics.append(
                    f"`{name} requires {target}`, but `{target}` is not defined — "
                    f"rendering without it"
                )
                continue
            pulled.append(target)
            frontier.append((target, depth + 1))

    return pulled, diagnostics
