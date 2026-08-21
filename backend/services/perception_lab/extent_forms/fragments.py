"""
PERCEPTUAL-FORMS-001B — `extent.fragment_set`: the pieces, and nothing about whether they are one.

WHAT IT SAYS. These pixels are connected to each other and not to those. Under the pairing
declared in `raster.py` that means sharing an EDGE, so two patches meeting at a single corner come
back as two pieces — which is the whole reason the pairing is declared rather than defaulted.

WHAT IT CANNOT SAY, AND THE THREE PLACES THAT IS ENFORCED RATHER THAN INTENDED:

  · `unity_asserted` is the literal `False` in the schema, so no producer can flip it.
  · `ExtentFragmentSetPayload` is `extra="forbid"`, so there is nowhere else to put the claim.
  · THIS FILE DOES NOT CARRY THE INSTANCE'S NAME ONTO ITS PIECES. `ExtentFragment.naming` exists,
    and copying "the tree" from an extent onto each of its three separated patches would assert
    exactly the unity the form refuses — three things each called the tree. A producer that
    believes those patches are one tree says so in `extent.fused_hypothesis`, where the grounds
    are enumerated and the status is capped below `measured`. So `naming` is left None, always,
    and a test holds it there.

That is what makes a fragment set SAFE TO COMPUTE EAGERLY: nothing downstream can read unity out
of it, so producing one commits to nothing at all.

ONE RASTER PER SET, REFUSED OTHERWISE. `fragments` is a flat list and the payload has no field in
which a second raster could be named, so a set assembled from an 800x600 mask and a 200x150 one
would report two `area` fractions of two different frames under one `regions_examined`. Boundary
records carry their own `raster_shape` and holes carry their own masks; this form is the one that
cannot, so this form is the one that refuses. See `inputs.one_raster`.

SEPARATION IS QUADRATIC AND SAYS SO. The exact gap between two pieces is a minimum over their
surface pixels, so measuring every pair costs pairs-times-surface. It is on by default because
"how far apart are they" is half the question a fragment set is asked, and
`measure_separation=False` is how a caller with four hundred pieces declines it — a decision
made out loud rather than a size threshold nobody can see.

PURE. No database, no network, no model, no clock, no image.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from backend.schemas.perception_lab import (Box, ExtentFragment, ExtentFragmentSetPayload,
                                            PerceptualForm)
from backend.services.perception_lab.extent_forms import measure as M
from backend.services.perception_lab.extent_forms.inputs import (Derived, SourceExtent, one_raster,
                                                                 provenance_for)
from backend.services.perception_lab.extent_forms.raster import PixelSet, foreground_components

#: A gap of one step means the two pieces touch at an edge or a corner. Named so a reader of
#: `separations` does not have to rediscover what `1` means.
TOUCHING = 1


def fragment_id(piece: PixelSet) -> str:
    """`frag_` and the piece's content digest.

    STABLE ACROSS EDITS ELSEWHERE, which is what "stable identity" has to mean to be worth
    anything. A positional id — first piece, second piece — renumbers every fragment in the image
    the moment a new one appears in the top-left corner, so a reviewer's note about `frag_3` would
    silently come to be about a different shape. This id changes only when the piece does.
    """
    return "frag_" + piece.digest


def fragment_model(piece: PixelSet) -> ExtentFragment:
    """One piece as the contract's record. `naming` is None — see the module docstring."""
    box = M.bbox(piece)
    return ExtentFragment(fragment_id=fragment_id(piece), mask_rle=piece.rle,
                          box=Box(**box) if box else None, area=M.normalized_area(piece),
                          naming=None)


def separations(pieces: Sequence[PixelSet]) -> List[Dict[str, Any]]:
    """The exact gap between every pair of pieces, in integer steps, closest pairs first.

    `touching` IS `gap == 1` AND NOT A SEPARATE MEASUREMENT. Two pieces one step apart share an
    edge or a corner; under the declared pairing a shared edge would have made them one piece, so
    a gap of one between two fragments is always a corner touch. That is a fact worth surfacing
    and it is derived from the number rather than measured beside it, so the two cannot disagree.

    ORDERED BY GAP, THEN BY ID, so the list is a fact about the mask rather than about iteration.
    """
    out: List[Dict[str, Any]] = []
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            gap = M.gap_px(pieces[i], pieces[j])
            if gap is None:
                continue
            ids = sorted((fragment_id(pieces[i]), fragment_id(pieces[j])))
            out.append({"fragment_ids": ids, "gap_px": gap, "touching": gap <= TOUCHING})
    out.sort(key=lambda row: (row["gap_px"], row["fragment_ids"]))
    return out


def fragment_set(extents: Sequence[SourceExtent], *, source_image_digest: str,
                 measure_separation: bool = True) -> Derived:
    """`extent.fragment_set` for a set of masked extents, with its receipt.

    `regions_examined` COUNTS EVERY PIECE THAT WAS LOOKED AT, before anything was collapsed. Two
    overlapping instances that both contain the same island produce one fragment — the island is
    one island, and it has one content-addressed id — but two examinations, and the difference
    between the count and the list is where that shows. `measurements["found_in"]` names which
    instances each piece came out of, because the payload has no field for it and losing it would
    make the collapse invisible.
    """
    one_raster(extents, what="extent.fragment_set")
    pieces: List[PixelSet] = []
    seen: Dict[str, str] = {}
    found_in: Dict[str, List[str]] = {}
    examined = 0
    per_instance: Dict[str, int] = {}
    for source in extents:
        components = foreground_components(source.raster)
        examined += len(components)
        per_instance[source.key] = len(components)
        for piece in components:
            key = fragment_id(piece)
            found_in.setdefault(key, []).append(source.key)
            if key in seen:
                continue
            seen[key] = source.key
            pieces.append(piece)
    payload = ExtentFragmentSetPayload(variant="extent_fragment_set", unity_asserted=False,
                                       regions_examined=examined,
                                       fragments=[fragment_model(p) for p in pieces])
    measurements: Dict[str, Any] = {
        "area_px": {fragment_id(p): p.area_px for p in pieces},
        "centroid": {fragment_id(p): M.centroid(p) for p in pieces},
        "perimeter_px": {fragment_id(p): M.perimeter_px(p) for p in pieces},
        "pieces_examined": per_instance,
        "found_in": {k: sorted(set(v)) for k, v in sorted(found_in.items())},
    }
    measurements["separations"] = separations(pieces) if measure_separation else None
    return Derived(
        form=PerceptualForm.EXTENT_FRAGMENT_SET, payload=payload,
        provenance=provenance_for(extents, source_image_digest=source_image_digest),
        measurements=measurements)


__all__ = ["TOUCHING", "fragment_id", "fragment_model", "fragment_set", "separations"]
