"""
PERCEPTUAL-FORMS-001G — the composite Extent forms: five claims about measured extents.

FIVE FORMS THAT ARE CLAIMS RATHER THAN MEASUREMENTS:

    extent.fused_hypothesis            are these pieces one thing, and on what evidence
    extent.visible_inferred_partition  which of this we saw, which we inferred, which we do not know
    extent.hierarchy                   palace -> courtyard -> garden, with the fractions
    extent.density_field               where the collection is, when there is no single object
    extent.hypothesis_set              the competing readings, held open

NONE OF THEM LOOKS AT A PIXEL IT WAS NOT HANDED. Every one is assembled from extents that were
measured already — Lane B's exact substrates, the Extent facade's masks, Lane D's containment
readings — and what they add is a claim ABOUT those measurements. That is the whole reason the
partitions here are `interpretive_grouping`, `inferred_completion` and `unresolved_alternative`
rather than `visible_measured`: the members being measured does not make the grouping measured.

FOUR OF THE FIVE ARE DEFERRED IN THE MERGED CONTRACT and the fifth is experimental. This lane does
not soften that. Every producer runs Lane A's `check_form_producible`, and a deferred form comes
back with `producible: False` and a typed refusal attached — carrying its payload, because
settling the shape a phase before anything writes it is the stated reason those forms were
registered at all.

A MODEL REACHES NONE OF THIS UNLESS LANE C ADMITTED IT. `admission.py` holds the seven verdicts as
data and refuses everything else with a reason that says which kind of no it is. Two of the seven
are admitted as ONE GROUND AMONG SEVERAL and may never stand alone; three candidates are refused
outright; and no form quietly gets a different producer when its own is unavailable.

PURE. No database, no network, no model, no clock, no image, no route.
"""
from __future__ import annotations

from backend.services.perception_lab.extent_composites.alternatives import (Reading,
                                                                            produce_hypothesis_set)
from backend.services.perception_lab.extent_composites.compose import PRODUCER, produce
from backend.services.perception_lab.extent_composites.density import (GAUSSIAN, Kernel,
                                                                      NO_SMOOTHING,
                                                                      produce_density_field)
from backend.services.perception_lab.extent_composites.fusion import (ProposedFusion,
                                                                      produce_fused_hypothesis)
from backend.services.perception_lab.extent_composites.grounds import GroundEvidence, Vetting, vet
from backend.services.perception_lab.extent_composites.hierarchy import (LinkKind, ProposedLink,
                                                                        produce_extent_hierarchy)
from backend.services.perception_lab.extent_composites.partition import (
    SuppliedPart, produce_visible_inferred_partition)
from backend.services.perception_lab.extent_composites.admission import (ADMISSIONS, Admission,
                                                                         EVIDENCE_ROOT,
                                                                         ModelNotAdmitted, Role,
                                                                         Verdict, admissions_for,
                                                                         admitted,
                                                                         ground_admission,
                                                                         producer_for)
from backend.services.perception_lab.extent_composites.sources import (ExtentSource,
                                                                       NotAnExtentSet, extent_set,
                                                                       fragment_set, index)

__all__ = [
    "ADMISSIONS", "Admission", "EVIDENCE_ROOT", "ExtentSource", "GAUSSIAN", "GroundEvidence",
    "Kernel", "LinkKind", "ModelNotAdmitted", "NO_SMOOTHING", "NotAnExtentSet", "PRODUCER",
    "ProposedFusion", "ProposedLink", "Reading", "Role", "SuppliedPart", "Verdict", "Vetting",
    "admissions_for", "admitted", "extent_set", "fragment_set", "ground_admission", "index",
    "produce", "produce_density_field", "produce_extent_hierarchy", "produce_fused_hypothesis",
    "produce_hypothesis_set", "produce_visible_inferred_partition", "producer_for", "vet",
]
