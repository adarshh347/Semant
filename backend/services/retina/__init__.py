"""
Simulation Engine · Lane 3 — the Retina.

Peripheral vision for movement. Given a region (or a raw evidence vector), propose where an
agent could look next: the nearest neighbours in ONE vector space, with similarity scores.

    from backend.services import retina

    await retina.index_rebuild()                       # derive the index from Mongo
    retina.retrieve_candidates(embedding_id=eid, k=8)  # → [{post_id, region_id, score, …}]
    retina.index_status()                              # what is indexed, and what was skipped

THREE THINGS TO HOLD ON TO:

  · **Candidates are not relations.** A neighbour is a proposal about where to look, not a
    claim about either image. Nothing here carries an `epistemic_status`, and grounding a real
    relation belongs to a later organ.
  · **The index is derived.** `region_embeddings` in Mongo is the source of truth; this is a
    rebuildable cache. Delete `data/retina` and you have lost a few seconds of build time.
  · **A space is a table.** Comparisons across vector spaces are impossible here by
    construction, not by convention.

The query path is synchronous (LanceDB is embedded — nothing to await) and touches no
database. Only `index_rebuild` is async, because only it reads Mongo.
"""
from backend.services.retina.index import (
    SKIP_REASONS,
    index_rebuild,
    index_status,
    is_legacy_space,
    iter_region_embeddings,
    space_of,
)
from backend.services.retina.service import (
    CANDIDATE_KIND,
    DEFAULT_K,
    DEFAULT_ROLE,
    NOT_A_RELATION,
    AmbiguousQuery,
    UnknownQuery,
    propose_candidates,
    resolve_query,
    retrieve_candidates,
)
from backend.services.retina.store import (
    RetinaError,
    RetinaStore,
    RetinaUnavailable,
    default_db_path,
    is_available,
    unavailable_reason,
)

__all__ = [
    # the two the directive names
    "retrieve_candidates", "index_rebuild",
    # envelopes + introspection
    "propose_candidates", "index_status", "resolve_query", "iter_region_embeddings",
    # store
    "RetinaStore", "default_db_path", "is_available", "unavailable_reason",
    # vocabulary
    "CANDIDATE_KIND", "NOT_A_RELATION", "DEFAULT_ROLE", "DEFAULT_K", "SKIP_REASONS",
    "space_of", "is_legacy_space",
    # refusals
    "RetinaError", "RetinaUnavailable", "UnknownQuery", "AmbiguousQuery",
]
