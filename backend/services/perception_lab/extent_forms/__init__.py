"""
PERCEPTUAL-FORMS-001B — exact, model-independent Extent forms, beneath the mask.

WHAT THIS PACKAGE IS. Three of the nineteen perceptual forms — `extent.boundary_rings`,
`extent.hole_set`, `extent.fragment_set` — computed from a mask that already exists, per pixel,
with nothing left to a model and nothing left to a threshold. Given the same RLE it returns the
same bytes on any machine, with or without cv2, with or without numpy.

WHAT THIS PACKAGE IS NOT, and each of these is a boundary rather than a gap:

  · IT DOES NOT MAKE MASKS. Segmentation is `extent.py`'s façade over adapters. This reads what
    that produced and derives what follows from it. No model is loaded here, ever.
  · IT DOES NOT MAKE ARTIFACTS. All three forms declare `produced_by_operations: []`, and an
    artifact names the operation that produced it. There is no such operation yet, so building an
    artifact here would mean naming one that never ran. It returns PAYLOADS and the provenance a
    later lane needs to wrap them, and that lane registers the operation.
  · IT DOES NOT ORCHESTRATE. No step, no run, no session, no route, no store.
  · IT DOES NOT TOUCH THE LIVE FAÇADE. `extent.py` is unchanged; nothing it returns changes shape.

THE THREE FORMS, AND THE ONE THING EACH REFUSES TO SAY.

    boundary_rings   the edge as closed curves, each DECLARING its winding rather than leaving a
                     reader to infer inside from point order
    hole_set         the voids, each naming the extent it is a void OF — a hole is not a shape
    fragment_set     the pieces, with `unity_asserted` fixed at False and nowhere else to put a
                     claim that three patches are one tree

A HOLE IS NOT A FRAGMENT and the package keeps them apart structurally, not by naming: fragments
come from the components of the mask, holes come from the bounded components of a PIECE's
complement, and the two are computed by different functions over different pixel sets. Outer
boundaries and hole boundaries stay distinct for the same reason — the tracer classifies a ring
by the sign of its lattice area, which is an integer, so the class is decided exactly.

PURE. No database, no network, no model, no clock, no image. See `raster.py` for the one
convention that is chosen rather than forced: foreground 4-connected, background 8-connected.
"""
from __future__ import annotations

from backend.services.perception_lab.extent_forms.boundary import (TracedRing, boundary_rings,
                                                                    instance_boundary, trace)
from backend.services.perception_lab.extent_forms.fragments import (fragment_id,
                                                                     fragment_model, fragment_set,
                                                                     separations)
from backend.services.perception_lab.extent_forms.holes import Void, hole_set, voids_of
from backend.services.perception_lab.extent_forms.inputs import (DERIVATION_REVISION, Derived,
                                                                 DerivationProvenance, PRODUCER,
                                                                 SourceExtent, source_extent,
                                                                 source_extents)
from backend.services.perception_lab.extent_forms.raster import (
    BACKGROUND_CONNECTIVITY, ExtentFormRefusal, FOREGROUND_CONNECTIVITY, PixelSet, Raster,
    canonical_rle, complement_components, complement_of, digest_of, foreground_components,
    raster_of)

__all__ = [
    "BACKGROUND_CONNECTIVITY", "DERIVATION_REVISION", "DerivationProvenance", "Derived",
    "ExtentFormRefusal", "FOREGROUND_CONNECTIVITY", "PRODUCER", "PixelSet", "Raster",
    "SourceExtent", "TracedRing", "Void", "boundary_rings", "canonical_rle",
    "complement_components", "complement_of", "digest_of", "foreground_components",
    "fragment_id", "fragment_model", "fragment_set", "hole_set", "instance_boundary", "raster_of",
    "separations", "source_extent", "source_extents", "trace", "voids_of",
]
