"""
PERCEPTUAL-FORMS-001D — the structural Topology forms.

Four higher-order records, assembled from relations that were measured already:

    topology.containment_tree        what is nested inside what, all the way down
    topology.adjacency_graph         what touches what, across the whole scene
    topology.transition              what changed between two revisions of one pair
    topology.uncertain_relation_set  what would be true, if that reading of the extents were right

NOT A NEW MODEL AND NOT A SEMANTIC GRAPH. Every edge in every one of these is a relation the
Topology façade already measured; these producers add ordering, assembly and comparison, and no
evidence whatever. That is why all four are `exact_derivation`, why none may claim more than the
weakest artifact under it, and why nothing in this package looks at a pixel.

WHAT IS NOT HERE, and the absences are the design:

    no Extent call             Topology consumes SUPPLIED extents. Lane C's rule, inherited
    no Depth call              likewise, and the occlusion seam stays where it is
    no façade edit             `topology.py` measures; this composes. Two acts, two modules
    no route, no store         nothing here writes anything anywhere
    no label                   an identity is `artifact_id#instance_id`, never a name

TWO OF THE FOUR ARE DEFERRED IN THE MERGED CONTRACT. `topology.transition` and
`topology.uncertain_relation_set` are registered, designed and unwritable, and this lane does not
soften that: every producer runs Lane A's `check_form_producible`, and the two deferred forms come
back with `producible: False` and a typed refusal attached. What they DO come back with is the
assembled payload, because settling the shape a phase before anything writes it is the stated
reason those forms were registered at all. See `production.FormProduction`.
"""
from __future__ import annotations

from backend.services.perception_lab.topology_forms.production import (OMISSION_REASONS, ORGAN,
                                                                       PARTITION, PRODUCER,
                                                                       FormProduction, Omission,
                                                                       ceiling_for,
                                                                       check_inputs_are_read,
                                                                       check_producible, dangling,
                                                                       minted, not_a_revision,
                                                                       weaker_basis, weakest)
from backend.services.perception_lab.topology_forms.sources import (HypothesisSet, NotARelationSet,
                                                                    Reading, RelationSet, Supplied,
                                                                    as_artifact, endpoint_key,
                                                                    revision_key)

__all__ = [
    "ORGAN", "PRODUCER", "PARTITION", "OMISSION_REASONS", "Omission", "FormProduction",
    "check_producible", "check_inputs_are_read", "ceiling_for", "weakest", "weaker_basis",
    "dangling", "not_a_revision", "minted",
    "Supplied", "NotARelationSet", "as_artifact", "endpoint_key", "revision_key",
    "RelationSet", "HypothesisSet", "Reading",
]
