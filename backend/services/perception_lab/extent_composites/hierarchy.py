"""
PERCEPTUAL-FORMS-001G — `extent.hierarchy`: palace, courtyard, garden, fountain — and the fractions.

TWO KINDS OF LINK, AND THE FORM EXISTS BECAUSE THEY ARE NOT THE SAME LINK.

    GEOMETRIC CONTAINMENT   the child's pixels are inside the parent's. Measured per pixel on a
                            shared raster, `basis: mask`, and it says nothing about belonging: a
                            pigeon standing in a courtyard is contained by it and is not part of it
    SEMANTIC PART / WHOLE   somebody says the child belongs to the parent. `basis: manual`, and it
                            says nothing about geometry: a cathedral's west front is part of the
                            cathedral whether or not one mask sits inside the other

Collapsing them is the failure this producer is arranged against, and `HierarchyNode.basis` is
where the distinction lives — there is no third field to put it in, so the two kinds are two
values of the substrate the parentage was established from, which is exactly what they are.

`occupancy_of_parent` IS RECORDED ONLY ON A GEOMETRIC NODE. A fraction beside an asserted
parentage would make the assertion look measured, and `HierarchyNode` carries no field saying
which of the two the number belongs to. So a manual link's occupancy is left null even when the
masks would have supported one — the number is available to anyone who wants it from the extents,
and putting it here would be putting it somewhere it reads as evidence for the link.

A PROPOSED GEOMETRIC PARENT THAT DOES NOT CONTAIN THE CHILD IS REFUSED, per pixel, with no
tolerance. `extent_metrics` already rules that two masks may only be compared on a shared raster
and returns None rather than resampling; a containment claim over two rasters is a claim about
neither, and it is left out and named.

A CYCLE IS REPORTED, NEVER BROKEN. Two links that disagree in a loop mean the inputs disagree, and
dropping an edge to make a tree would hide the disagreement behind a clean picture. Lane D's
containment producer rules the same way for the same reason, and the omission reason is theirs.

EVERY NODE CITES A REVISION. `RevisionRef` requires one, and an instance carrying none is left out
rather than pinned at a revision nobody recorded — a tree that cannot be told it has gone stale is
worse than no tree.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.schemas.perception_lab import (EpistemicBasis, ExtentHierarchyPayload, GroundKind,
                                            HierarchyNode, RevisionRef)
from backend.services.mask_geometry import rle_area
from backend.services.perception_lab import extent_metrics as M
from backend.services.perception_lab.extent_composites import grounds as G
from backend.services.perception_lab.extent_composites import sources as SRC
from backend.services.perception_lab.extent_composites.compose import minted, produce
from backend.services.perception_lab.topology_forms.production import FormProduction, Omission

FORM = "extent.hierarchy"

#: The two partitions this form admits, one per kind of link. A tree holding one asserted link is
#: an interpretive tree, and reporting it under `exact_derivation` would let the measured half
#: speak for the whole record.
DERIVATION = "exact_derivation"
GROUPING = "interpretive_grouping"


class LinkKind(str, Enum):
    GEOMETRIC = "geometric"     # measured: the child's pixels are inside the parent's
    SEMANTIC = "semantic"       # asserted: the child belongs to the parent


@dataclass(frozen=True)
class ProposedLink:
    """One parentage somebody wants in the tree, and which kind of claim it is."""
    child_key: str
    parent_key: Optional[str] = None
    kind: LinkKind = LinkKind.GEOMETRIC
    asserted_by: Optional[G.GroundEvidence] = None


def _ref(source: SRC.ExtentSource, member: Any) -> Optional[RevisionRef]:
    rev = getattr(member, "geometry_rev", None)
    if rev is None:
        return None
    return RevisionRef(artifact_id=source.artifact_id,
                       instance_id=str(getattr(member, "instance_id", "")), geometry_rev=int(rev))


def _contains(parent: Any, child: Any) -> Optional[float]:
    """The fraction of the parent the child occupies, or None when it is not inside it.

    PER PIXEL AND WITH NO TOLERANCE. `intersection_area` returns None on a raster mismatch rather
    than resampling — the rule `extent_metrics` holds every comparison to — and a child is inside
    a parent only when every one of its pixels is.
    """
    child_mask, _ = SRC.geometry_of(child)
    parent_mask, _ = SRC.geometry_of(parent)
    if child_mask is None or parent_mask is None:
        return None
    shared = M.intersection_area(parent_mask, child_mask)
    if shared is None:
        return None
    child_area = rle_area(dict(child_mask))
    parent_area = rle_area(dict(parent_mask))
    if not child_area or not parent_area or shared != child_area:
        return None
    return round(shared / parent_area, 6)


def produce_extent_hierarchy(links: Sequence[ProposedLink], *,
                             sources: Sequence[SRC.ExtentSource]) -> FormProduction:
    """Build the tree the links describe, and name every link that did not earn its place.

    `pairs_examined` COUNTS THE PARENTAGES PUT FORWARD, including the ones that failed. It is the
    field that separates "the extents were compared for nesting and none contained another" from
    "nobody compared them", and those are opposite findings about the same empty tree.
    """
    from backend.services.perception_lab.extent_composites.compose import admissible_basis
    basis, kept, omitted = admissible_basis(FORM, sources)
    omissions: List[Omission] = list(omitted)
    held = SRC.index(kept) if kept else {}
    accepted: Dict[str, Tuple[Optional[str], LinkKind, Optional[float]]] = {}

    for link in links:
        if link.child_key not in held:
            omissions.append(Omission(
                what=link.child_key, reason="endpoint_dangling",
                detail="no supplied source holds this child"))
            continue
        if link.child_key in accepted:
            omissions.append(Omission(
                what=link.child_key, reason="duplicate",
                detail="a node has one parent; a second link for it would be a second tree"))
            continue
        if link.parent_key is None:
            accepted[link.child_key] = (None, link.kind, None)
            continue
        if link.parent_key not in held:
            omissions.append(Omission(
                what=f"{link.child_key}<-{link.parent_key}", reason="endpoint_dangling",
                detail="no supplied source holds this parent"))
            continue
        if link.parent_key == link.child_key:
            omissions.append(Omission(
                what=link.child_key, reason="self_pair",
                detail="a node is not inside itself, and is not part of itself either"))
            continue
        occupancy = _contains(held[link.parent_key][1], held[link.child_key][1])
        if link.kind is LinkKind.GEOMETRIC:
            if occupancy is None:
                omissions.append(Omission(
                    what=f"{link.child_key}<-{link.parent_key}",
                    reason="not_geometrically_contained",
                    detail=("every pixel of the child is not inside the parent, or the two are "
                            "not on one raster. A containment claim over two rasters is a claim "
                            "about neither.")))
                continue
            accepted[link.child_key] = (link.parent_key, link.kind, occupancy)
            continue
        assertion = link.asserted_by
        if assertion is None or assertion.attributed_to != G.HUMAN \
                or assertion.kind is not GroundKind.HUMAN_ASSERTION:
            omissions.append(Omission(
                what=f"{link.child_key}<-{link.parent_key}", reason="semantic_link_undeclared",
                detail=("a part/whole link is somebody's assertion and has to name them. Without "
                        "one it is a containment claim with the measurement removed.")))
            continue
        # THE OCCUPANCY IS DELIBERATELY DROPPED HERE even where it exists. See the module
        # docstring: a fraction beside an asserted parentage reads as evidence for the assertion.
        accepted[link.child_key] = (link.parent_key, link.kind, None)

    accepted = _without_cycles(accepted, omissions)
    nodes: List[HierarchyNode] = []
    for child_key, (parent_key, kind, occupancy) in accepted.items():
        source, member = held[child_key]
        ref = _ref(source, member)
        if ref is None:
            omissions.append(Omission(
                what=child_key, reason="revision_missing",
                detail=("this instance carries no geometry_rev, so it cannot be a level of a "
                        "hierarchy. A tree that cannot be told it has gone stale is worse than "
                        "none.")))
            continue
        nodes.append(HierarchyNode(
            node_id=minted("node", FORM, child_key, ref.geometry_rev),
            instance=ref,
            parent_node_id=(None if parent_key is None
                            else minted("node", FORM, parent_key,
                                        _ref(*held[parent_key]).geometry_rev)),
            occupancy_of_parent=occupancy,
            basis=EpistemicBasis.MASK if kind is LinkKind.GEOMETRIC else EpistemicBasis.MANUAL))

    # A NODE WHOSE PARENT WAS EXCLUDED IS EXCLUDED AND SAYS SO. `_acyclic` refuses a parent this
    # record does not hold, so it has to go — and re-rooting it would invent a parentage nobody
    # proposed, while dropping it quietly would make a partial tree read as a complete one.
    held_ids = {n.node_id for n in nodes}
    orphans = [n for n in nodes if n.parent_node_id is not None and n.parent_node_id not in held_ids]
    for orphan in orphans:
        omissions.append(Omission(
            what=orphan.node_id, reason="orphaned_by_exclusion",
            detail=(f"its parent {orphan.parent_node_id} was left out, so its parentage is no "
                    f"longer holdable. Re-rooting it here would invent a level nobody proposed.")))
    nodes = [n for n in nodes if n not in orphans]
    payload = ExtentHierarchyPayload(
        variant="extent_hierarchy", pairs_examined=len(links), nodes=nodes,
        root_node_ids=[n.node_id for n in nodes if n.parent_node_id is None])
    partition = GROUPING if any(n.basis is EpistemicBasis.MANUAL for n in nodes) else DERIVATION
    return produce(FORM, payload, basis=basis or EpistemicBasis.MASK, partition=partition,
                   sources=kept, omitted=tuple(omissions))


def _without_cycles(accepted: Dict[str, Tuple[Optional[str], LinkKind, Optional[float]]],
                    omissions: List[Omission]
                    ) -> Dict[str, Tuple[Optional[str], LinkKind, Optional[float]]]:
    """Drop every node whose parent chain reaches itself, and say which.

    THE WHOLE CYCLE GOES, NOT ONE EDGE OF IT. Breaking a loop by deleting the link that happened
    to be walked last would produce a tree that validates and that nobody chose, and the reader
    would have no way to know a disagreement had been resolved on their behalf.
    """
    out = dict(accepted)
    cycled: List[str] = []
    for start in list(out):
        seen = {start}
        walk = out[start][0]
        while walk is not None and walk in out:
            if walk in seen:
                cycled.append(start)
                break
            seen.add(walk)
            walk = out[walk][0]
    for node in cycled:
        omissions.append(Omission(
            what=node, reason="containment_cycle",
            detail=("this node's parent chain reaches itself. The links disagree, and dropping "
                    "one of them to make a tree would hide the disagreement rather than report "
                    "it.")))
        out.pop(node, None)
    return out


__all__ = ["DERIVATION", "FORM", "GROUPING", "LinkKind", "ProposedLink",
           "produce_extent_hierarchy"]
