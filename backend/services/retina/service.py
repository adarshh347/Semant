"""
Simulation Engine · Lane 3 — the Retina: peripheral vision.

Before an agent can *move* from one image to another, something cheap and broad has to propose
where it could go. That is this: ask "what is roughly near this?" and get back a short list.

WHAT A CANDIDATE IS NOT. It is not a relation, not a motif, not a measurement, and not a claim
about either image. Two regions being close in DINOv2 space means a model's projection put
them close, and that is the entire content of the assertion. Grounding a real relation is a
later organ's job. So nothing this module emits carries an `epistemic_status` — it is not a
weak claim to be sharpened later, it is not a claim — and every result is stamped
`kind: "candidate"`, with the envelope carrying `grounded: False`. A test pins both, because
the day someone starts persisting these as edges, the schema should be the thing that objects.

The retina NARROWS THE SEARCH. It does not decide.

SPACE DISCIPLINE. A query resolves to exactly ONE space and searches exactly that table (see
`store.py`). Where a space cannot be resolved unambiguously this module RAISES rather than
pick one: `retrieve_candidates(embedding=v, k=5)` against an index holding three different
384-d spaces is not a query with a sensible default, it is a query missing an argument.

SYNCHRONOUS, on purpose. LanceDB is embedded and memory-mapped: a lookup is a page fault, not
a round trip, and there is nothing to await. Only `index_rebuild` — which reads Mongo — is
async. FastAPI runs a plain `def` handler in a threadpool, so the read path never blocks the
event loop despite being sync.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from backend.services.retina import geometry as geo_sidecar
from backend.services.retina import relational as rel
from backend.services.retina import store as st
from backend.services.retina.index import index_status
from backend.services.retina.store import RetinaError, RetinaStore, RetinaUnavailable

#: Stamped on every result. The one word that says a downstream consumer must ground this
#: before treating it as anything.
CANDIDATE_KIND = "candidate"

#: Said out loud in every envelope, so the caveat travels with the data rather than living in
#: a docstring the caller never reads.
NOT_A_RELATION = (
    "Candidates are vector-space neighbours with similarity scores. They are proposals for "
    "where to look next — not relations, not measurements, and not claims about either image. "
    "Grounding decides truth; the retina only narrows the search."
)

DEFAULT_ROLE = "identity"
DEFAULT_K = 8


class UnknownQuery(RetinaError):
    """The thing being asked about is not in the index.

    Distinct from an empty result, and raised rather than returned as `[]`, because "I have
    never seen that region" and "that region has no neighbours" are different facts. Collapsing
    them would let an agent conclude a region is isolated when the truth is that the index is
    stale or the rebuild skipped it.
    """


class AmbiguousQuery(RetinaError):
    """The query matches more than one space or more than one region, and picking would be a
    guess. Carries the alternatives so the caller can say which one it meant."""

    def __init__(self, message: str, alternatives: Sequence[Any] = ()):
        super().__init__(message)
        self.alternatives = list(alternatives)


def _similarity(distance: float) -> float:
    """LanceDB cosine distance → cosine similarity. `distance = 1 - cos`, so this inverts it;
    clamped because floating point occasionally hands back 1.0000000004."""
    return round(max(-1.0, min(1.0, 1.0 - float(distance))), 4)


def _candidate(row: Dict[str, Any], space: str) -> Dict[str, Any]:
    """One index row → one candidate. The contract's three keys (`post_id`, `region_id`,
    `score`) plus the provenance that lets a caller judge the proposal without a second
    round-trip: which model in which space at which geometry revision proposed it.

    Note what is absent and must stay absent: no `epistemic_status`, no relation, no label.
    """
    return {
        "post_id": row.get("post_id") or "",
        "region_id": row.get("region_id") or "",
        "score": _similarity(row.get("_distance", 1.0)),
        "embedding_id": row.get("embedding_id") or "",
        "role": row.get("role") or "",
        "space": space,
        "model": row.get("model") or "",
        "checkpoint": row.get("checkpoint") or "",
        "route": row.get("route") or "",
        "dim": int(row.get("dim") or 0),
        "geometry_rev": row.get("geometry_rev"),
        "kind": CANDIDATE_KIND,
    }


def _indexed_spaces(store: RetinaStore) -> Dict[str, Dict[str, Any]]:
    spaces = store.spaces()
    if not spaces:
        raise UnknownQuery(f"retina index is empty or not built at {store.path} — "
                           f"run index_rebuild()")
    return spaces


# ── resolving a query to (space, vector) ─────────────────────────────────────

def _resolve_by_embedding(store: RetinaStore, embedding: Sequence[float],
                          space: Optional[str]) -> Dict[str, Any]:
    """A raw vector. Its space is not knowable from its contents, so it must be given — unless
    exactly one indexed space has its width, in which case there is nothing to guess."""
    vector = [float(x) for x in embedding]
    if not vector:
        raise ValueError("empty embedding")
    if space:
        entry = store.space_entry(space)
        if entry is None:
            raise UnknownQuery(f"space {space!r} is not in the index")
        if int(entry["dim"]) != len(vector):
            raise ValueError(f"space {space!r} is {entry['dim']}-d but the query vector is "
                             f"{len(vector)}-d")
        return {"space": space, "vector": vector, "self_embedding_id": None}

    matches = [s for s, e in _indexed_spaces(store).items() if int(e["dim"]) == len(vector)]
    if not matches:
        raise UnknownQuery(f"no indexed space holds {len(vector)}-d vectors")
    if len(matches) > 1:
        raise AmbiguousQuery(
            f"{len(vector)}-d matches {len(matches)} indexed spaces — pass space= to say which "
            f"one this vector lives in", sorted(matches))
    return {"space": matches[0], "vector": vector, "self_embedding_id": None}


def _resolve_by_embedding_id(store: RetinaStore, embedding_id: str,
                             space: Optional[str]) -> Dict[str, Any]:
    """An embedding id is globally unique (it encodes model, role, post and region), so this is
    the precise form of the query — no disambiguation needed."""
    search_spaces = [space] if space else sorted(_indexed_spaces(store))
    hits = []
    for s in search_spaces:
        row = store.lookup_embedding_id(s, embedding_id)
        if row is not None:
            hits.append((s, row))
    if not hits:
        raise UnknownQuery(f"embedding {embedding_id!r} is not in the index"
                           + (f" for space {space!r}" if space else ""))
    if len(hits) > 1:                                  # ids are unique; this means a bad build
        raise AmbiguousQuery(f"embedding {embedding_id!r} is indexed in several spaces",
                             sorted(s for s, _ in hits))
    s, row = hits[0]
    return {"space": s, "vector": list(row["vector"]), "self_embedding_id": embedding_id,
            "row": row}


def _resolve_by_region(store: RetinaStore, region_id: str, post_id: Optional[str],
                       space: Optional[str], role: Optional[str]) -> Dict[str, Any]:
    """A region id, optionally narrowed by post, space and role.

    `region_id` is 'seg_0'-shaped and unique only WITHIN a post, so on any real corpus it
    matches many regions. `post_id` is what makes it a question with one answer; `role` picks
    which projection of that region (identity / context / whole_image) to move from.
    """
    spaces = _indexed_spaces(store)
    if space:
        if space not in spaces:
            raise UnknownQuery(f"space {space!r} is not in the index")
        search_spaces = [space]
    elif role:
        search_spaces = sorted(s for s, e in spaces.items() if (e.get("role") or "") == role)
        if not search_spaces:
            raise UnknownQuery(f"no indexed space carries role {role!r} — indexed roles: "
                               + str(sorted({e.get('role') or '' for e in spaces.values()})))
    else:
        search_spaces = sorted(spaces)

    hits = []
    for s in search_spaces:
        for row in store.lookup_region(s, region_id, post_id=post_id):
            hits.append((s, row))
    if not hits:
        where = f" in post {post_id!r}" if post_id else ""
        raise UnknownQuery(f"region {region_id!r}{where} is not in the index"
                           f" (searched {search_spaces})")
    if len(hits) > 1:
        raise AmbiguousQuery(
            f"region {region_id!r} matches {len(hits)} indexed rows — region ids are unique "
            f"only within a post; pass post_id= (and space=/role= if needed)",
            [{"space": s, "post_id": r.get("post_id"), "embedding_id": r.get("embedding_id"),
              "role": r.get("role")} for s, r in hits[:20]])
    s, row = hits[0]
    return {"space": s, "vector": list(row["vector"]),
            "self_embedding_id": row.get("embedding_id"), "row": row}


def _present(value: Any) -> bool:
    """Was this query argument actually supplied? Length-checked rather than truth-tested so a
    numpy array (whose truthiness raises) can be handed in as an embedding."""
    if value is None:
        return False
    if hasattr(value, "__len__"):
        return len(value) > 0
    return True


def resolve_query(store: RetinaStore, *, embedding: Optional[Sequence[float]] = None,
                  embedding_id: Optional[str] = None, region_id: Optional[str] = None,
                  post_id: Optional[str] = None, space: Optional[str] = None,
                  role: Optional[str] = DEFAULT_ROLE) -> Dict[str, Any]:
    """Turn any of the three query forms into `{space, vector, self_embedding_id}`."""
    given = [k for k, v in (("embedding", embedding), ("embedding_id", embedding_id),
                            ("region_id", region_id)) if _present(v)]
    if len(given) != 1:
        raise ValueError("pass exactly one of embedding=, embedding_id= or region_id= "
                         f"(got {given or 'none'})")
    if given[0] == "embedding":
        return _resolve_by_embedding(store, embedding, space)
    if given[0] == "embedding_id":
        return _resolve_by_embedding_id(store, str(embedding_id), space)
    return _resolve_by_region(store, str(region_id), post_id, space, role)


# ── the query ────────────────────────────────────────────────────────────────

def retrieve_candidates(
    *,
    embedding: Optional[Sequence[float]] = None,
    embedding_id: Optional[str] = None,
    region_id: Optional[str] = None,
    post_id: Optional[str] = None,
    space: Optional[str] = None,
    role: Optional[str] = DEFAULT_ROLE,
    k: int = DEFAULT_K,
    exclude_post_id: Optional[str] = None,
    exclude_self: bool = True,
    min_score: Optional[float] = None,
    store: Optional[RetinaStore] = None,
) -> List[Dict[str, Any]]:
    """Nearest neighbours in ONE vector space — the candidate generator movement stands on.

    Returns `[{post_id, region_id, score, …provenance}]`, best first — the k nearest rows in
    the resolved space, with no floor unless you ask for one. `score` is cosine similarity;
    `min_score` (default: none) drops anything below it.

    The default is deliberately no floor, not `0.0`. A floor of zero looks harmless and quietly
    discards every neighbour pointing the other way, so `k=24` comes back with 14 and the
    caller has no way to tell a thin corpus from a hidden filter. Narrowing is the caller's
    decision to make out loud.

    Query by a raw `embedding` (pass `space=` unless exactly one indexed space has its width),
    by `embedding_id` (the precise form), or by `region_id` (+ `post_id`, since region ids
    repeat across posts).

    `exclude_self` drops the query's own row — a region is never its own neighbour.
    `exclude_post_id` drops everything from one post, for "find this elsewhere".

    RAISES rather than returning `[]` when it could not look: `RetinaUnavailable` if LanceDB is
    missing, `UnknownQuery` if the index has never seen the thing asked about, `AmbiguousQuery`
    if the query names more than one space or region. An empty list means one thing only —
    it looked, and nothing cleared the bar.
    """
    resolved, candidates = _search(
        store or RetinaStore(), embedding=embedding, embedding_id=embedding_id,
        region_id=region_id, post_id=post_id, space=space, role=role, k=k,
        exclude_post_id=exclude_post_id, exclude_self=exclude_self, min_score=min_score)
    return candidates


def _search(store: RetinaStore, *, embedding, embedding_id, region_id, post_id, space, role,
            k: int, exclude_post_id, exclude_self: bool, min_score: Optional[float]):
    """Resolve, then search. Shared by both entry points so the envelope can report the space
    that was actually searched even when the result is empty."""
    st.require_available()
    resolved = resolve_query(store, embedding=embedding, embedding_id=embedding_id,
                             region_id=region_id, post_id=post_id, space=space, role=role)

    clauses = []
    if exclude_self and resolved.get("self_embedding_id"):
        clauses.append(f"embedding_id != {st.sql_literal(resolved['self_embedding_id'])}")
    if exclude_post_id:
        clauses.append(f"post_id != {st.sql_literal(exclude_post_id)}")
    where = " AND ".join(clauses) if clauses else None

    limit = max(1, int(k))
    rows = store.search(resolved["space"], resolved["vector"], k=limit, where=where)
    out = [_candidate(r, resolved["space"]) for r in rows]
    if min_score is not None:
        out = [c for c in out if c["score"] >= min_score]
    return resolved, out[:limit]


def propose_candidates(**kwargs) -> Dict[str, Any]:
    """`retrieve_candidates` wrapped in a status envelope, for the route and any caller that
    would rather branch on a string than catch.

    Every refusal keeps its own status — `unavailable` (could not look), `unknown` (never
    indexed), `ambiguous` (query underspecified), `empty` (looked, found nothing) — because
    collapsing them into one empty list is how a stale index starts looking like an isolated
    region. The envelope also reports the index's own state (built_at, partial, truncated), so
    a thin result can be read against how much corpus was actually searched.
    """
    store = kwargs.pop("store", None) or RetinaStore()
    query = {"embedding": None, "embedding_id": None, "region_id": None, "post_id": None,
             "space": None, "role": DEFAULT_ROLE, "k": DEFAULT_K, "exclude_post_id": None,
             "exclude_self": True, "min_score": None}
    unknown = set(kwargs) - set(query)
    query.update(kwargs)
    base = {"kind": "candidates", "grounded": False, "note": NOT_A_RELATION,
            "space": query["space"], "candidates": [], "reason": ""}
    if unknown:
        return {**base, "status": "error", "reason": f"unknown arguments {sorted(unknown)}"}
    try:
        resolved, candidates = _search(store, **query)
    except RetinaUnavailable as e:
        return {**base, "status": "unavailable", "reason": str(e)}
    except AmbiguousQuery as e:
        return {**base, "status": "ambiguous", "reason": str(e), "alternatives": e.alternatives}
    except UnknownQuery as e:
        return {**base, "status": "unknown", "reason": str(e)}
    except (ValueError, RetinaError) as e:
        return {**base, "status": "error", "reason": str(e)}

    status = index_status(store)
    return {
        **base,
        "status": "ready" if candidates else "empty",
        "space": resolved["space"],          # the space actually searched, empty result or not
        "candidates": candidates,
        "index": {"built_at": status.get("built_at"), "partial": status.get("partial"),
                  "truncated": status.get("truncated"),
                  "rows": (status.get("totals") or {}).get("rows")},
    }


def propose_for_relation(*, posts: Optional[Mapping[str, Any]] = None,
                         geometry: Optional[Mapping[str, Any]] = None,
                         recall_multiplier: int = rel.DEFAULT_RECALL_MULTIPLIER,
                         weights: Optional[Mapping[str, float]] = None,
                         **kwargs) -> Dict[str, Any]:
    """Candidates ordered by how likely they are to STAND IN a relation, not by resemblance.

    Two stages, and the split is the point:

      · **recall** — identity kNN at `k × recall_multiplier`. Cheap, broad, and exactly what the
        retina has always been: peripheral vision, deliberately over-inclusive.
      · **re-rank** — order that shortlist by a box-basis relational prior (`relational.py`), then
        hand back the top `k`.

    The multiplier is what makes this more than a permutation. Re-ranking k into k can only move
    good candidates up from within the k you already had; widening recall first is what lets a
    relationally-plausible region at identity rank 30 reach an agent whose budget is 12.

    Falls back to identity order — `ranking: "identity"`, with a `reason` — when there is no
    geometry to rank on, rather than pretending the order means something it does not. Everything
    `propose_candidates` guarantees still holds: candidates are not relations, nothing carries an
    `epistemic_status`, and the kernel grounds on masks and may reject every one of these.
    """
    k = int(kwargs.get("k", DEFAULT_K) or DEFAULT_K)
    multiplier = max(1, int(recall_multiplier or 1))
    seed_post_id = str(kwargs.get("post_id") or "")
    seed_region_id = str(kwargs.get("region_id") or "")
    # The sidecar lives beside the index, so a caller pointing at a different index must be
    # ranked from THAT index's geometry — not from whatever sits at the default path.
    store = kwargs.get("store")

    envelope = propose_candidates(**{**kwargs, "k": k * multiplier})
    recall = {"k": k, "recall_k": k * multiplier, "multiplier": multiplier,
              "returned": len(envelope.get("candidates") or [])}
    base = {**envelope, "ranking": "identity", "recall": recall,
            "prior_note": rel.NOT_A_MEASUREMENT}
    if envelope.get("status") != "ready":
        return {**base, "candidates": (envelope.get("candidates") or [])[:k]}

    geo = dict(geometry or {}) or geo_sidecar.geometry_for(posts, store)
    seed_geometry = geo.get(seed_post_id) or {}
    seed_skeleton = rel.skeleton_of(seed_geometry, seed_region_id) if seed_geometry else None
    if seed_skeleton is None:
        return {**base, "candidates": envelope["candidates"][:k],
                "reason": (f"no cached geometry for seed {seed_post_id}/{seed_region_id} — "
                           f"ranked by identity. Run geometry_rebuild(), or pass posts=."),
                "geometry": geo_sidecar.geometry_status(store)}

    ranked = rel.rerank(envelope["candidates"], seed_skeleton=seed_skeleton, geometry=geo,
                        weights=weights)
    kept = ranked[:k]
    return {
        **base,
        "ranking": "relational",
        "candidates": kept,
        "seed_skeleton": seed_skeleton,
        "weights": dict(kept[0]["relational"]["weights"]) if kept else dict(rel.DEFAULT_WEIGHTS),
        # What the k budget cut, named rather than silently absent — the density lane's rule that a
        # bounded sweep says what it dropped.
        "dropped": [{"post_id": c["post_id"], "region_id": c["region_id"],
                     "identity_rank": c["identity_rank"],
                     "relational_score": c["relational"]["score"]} for c in ranked[k:]],
        "geometry": ({"source": "live"} if (geometry or posts)
                     else geo_sidecar.geometry_status(store)),
    }


__all__ = ["retrieve_candidates", "propose_candidates", "propose_for_relation", "resolve_query",
           "index_status", "CANDIDATE_KIND", "NOT_A_RELATION", "DEFAULT_ROLE", "DEFAULT_K",
           "RetinaError", "RetinaUnavailable", "UnknownQuery", "AmbiguousQuery"]
