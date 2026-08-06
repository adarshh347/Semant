"""
Simulation Engine · Lane 3 — the Retina.

Peripheral vision for movement. Given a region (or a raw evidence vector), propose where an
agent could look next: the nearest neighbours in ONE vector space, with similarity scores.

    from backend.services import retina

    await retina.index_rebuild()                       # derive the index from Mongo
    await retina.geometry_rebuild()                    # derive the extents the prior ranks on
    retina.retrieve_candidates(embedding_id=eid, k=8)  # → [{post_id, region_id, score, …}]
    retina.propose_for_relation(region_id=r, post_id=p, k=12)   # ordered for a RELATION
    retina.index_status()                              # what is indexed, and what was skipped

TWO QUESTIONS, ONE INDEX. `retrieve_candidates` answers "what resembles this?" — the retina's
original and only question. `propose_for_relation` answers "what is likely to STAND IN a relation
with this?", by widening identity recall and re-ranking it on box-basis extents. WAVE3 measured
the first as slightly ANTI-correlated with what the movement kernel can ground: the twelve nearest
neighbours of a seed grounded nothing at all. The second is the fix, and it is still a proposal.

FOUR THINGS TO HOLD ON TO:

  · **Candidates are not relations.** A neighbour is a proposal about where to look, not a
    claim about either image. Nothing here carries an `epistemic_status`, and grounding a real
    relation belongs to a later organ.
  · **A relational prior is an estimate.** It is computed from bounding boxes, which is what the
    WAVE2.5 ruling permits a proposer: boxes propose, masks ground. The kernel re-reads every
    proposal on masks and disagrees with roughly a fifth of them — by design, not by accident.
  · **Both caches are derived.** `region_embeddings` is the source of truth for the index,
    `region_annotations` for the geometry sidecar. Delete `data/retina` and you have lost a few
    seconds of build time. They have different sources, so they go stale independently.
  · **A space is a table.** Comparisons across vector spaces are impossible here by
    construction, not by convention.

The query path is synchronous (LanceDB is embedded — nothing to await) and touches no
database. Only `index_rebuild` and `geometry_rebuild` are async, because only they read Mongo.
"""
from backend.services.retina.geometry import (
    geometry_for,
    geometry_rebuild,
    geometry_status,
    load_geometry,
    post_geometry,
)
from backend.services.retina.index import (
    SKIP_REASONS,
    index_rebuild,
    index_status,
    is_legacy_space,
    iter_region_embeddings,
    space_of,
)
from backend.services.retina.relational import (
    DEFAULT_RECALL_MULTIPLIER,
    DEFAULT_WEIGHTS,
    NOT_A_MEASUREMENT,
    PRIOR_BASIS,
    PRIOR_KIND,
    relational_prior,
    rerank,
    shape_affinity,
    skeleton_of,
    skeletons,
)
from backend.services.retina.service import (
    CANDIDATE_KIND,
    DEFAULT_K,
    DEFAULT_ROLE,
    NOT_A_RELATION,
    AmbiguousQuery,
    UnknownQuery,
    propose_candidates,
    propose_for_relation,
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
    # relational retrieval — propose for a RELATION, not by resemblance
    "propose_for_relation", "skeletons", "skeleton_of", "shape_affinity", "relational_prior",
    "rerank", "DEFAULT_WEIGHTS", "DEFAULT_RECALL_MULTIPLIER", "PRIOR_KIND", "PRIOR_BASIS",
    "NOT_A_MEASUREMENT",
    # the geometry sidecar the prior is read from
    "geometry_rebuild", "geometry_status", "geometry_for", "load_geometry", "post_geometry",
    # store
    "RetinaStore", "default_db_path", "is_available", "unavailable_reason",
    # vocabulary
    "CANDIDATE_KIND", "NOT_A_RELATION", "DEFAULT_ROLE", "DEFAULT_K", "SKIP_REASONS",
    "space_of", "is_legacy_space",
    # refusals
    "RetinaError", "RetinaUnavailable", "UnknownQuery", "AmbiguousQuery",
]
