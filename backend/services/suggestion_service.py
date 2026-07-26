"""
CIRCUIT-001 P4-A — suggestion producers.

Turns real model output into `suggestion descriptors` — the plain-JSON shape the frontend
circuit ingests as quarantined `model_suggested` marks (contract v3 §8.4). Two producers:

  - ``suggestion_from_refine_region`` — a SAM2 mask preview → a ``region_mask`` (raster_mask)
    suggestion referencing the previewed region.
  - ``suggestions_from_semantics`` — a semantic-read result → ``region_mask`` (region_ref) label
    suggestions per assertion, and ``relation_mark`` suggestions per relation.

This module is PURE and geometry-honest: it authors no pixels. A SAM suggestion references the
region SAM already produced (``mask_ref``); a semantic suggestion references an EXISTING region
by id (``region_ref``) or a derived relation — never a mask the VLM drew (the VLM's law).

Every descriptor carries its receipt in ``provenance`` — ``model``, ``adapter``, ``latency_ms``,
``run_id``, ``producer`` — so the mark that results can never claim the model without one. The
route supplies ``run_id`` from a real ``vision_run_service`` run; this module never mints runs.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.services.mask_geometry import (cosine_field_from_features, depth_band_field,
                                            region_geometry_from_grounding,
                                            field_contrast, rle_is_valid, shading_band_field,
                                            shading_gradient, soft_field_from_map,
                                            soft_field_from_mask, strokes_from_field)

PRODUCER_SAM = "sam_refine"
PRODUCER_SEMANTIC = "semantic_read"
# CIRCUIT-001 P5-A — the crossing. A find-similar neighbour lives on ANOTHER post; it enters the
# circuit as an evidence-suggestion, never an assertion (Invariant 4). Its geometry is a
# cross-post `region_ref`: a REFERENCE across the border ({post_id, region_id, geometry_rev}),
# never a copy of the neighbour's mask.
PRODUCER_FIND_SIMILAR = "find_similar"
# CIRCUIT-001 P6-A — the first brush_field producer, and the first that loads NO model. Negative
# space is the complement of a figure that already exists in the packet, so this producer consumes
# a committed region's mask and calls no segmenter: deterministic, CPU-only, ~0 VRAM, unaffected
# by the torch +cpu regression. It occupies the PERCEPTUAL capability conceptually but needs no
# adapter — there is nothing to infer, only geometry to invert.
PRODUCER_NEGATIVE_SPACE = "negative_space"
# CIRCUIT-001 P6-B — the second brush_field producer, and the FIRST on a real model. A curator taps
# one patch; DINOv2's shared patch grid (the SAME substrate find_similar/embeddings use, reached
# through ModelManager's GPU slot — never a second embedding path) yields a cosine same-material
# soft field. This one DID infer, so its receipt is full (model/adapter/checkpoint/preproc/latency),
# with one honest exception: `confidence` may never ride onto a mark (contract §6), so the field's
# contrast travels on the descriptor instead, visible to review but never laundered into evidence.
PRODUCER_MATERIAL = "material_field"
# CIRCUIT-001 P6-D — the third producer ARCHETYPE: pure signal processing. negative_space reads
# a mask that already exists; material_field reads a learned embedding; rhythm reads the image
# signal itself (Gabor energy over a region's crop). No weights, no GPU — so its receipt is
# deterministic like negative_space's (adapter + latency, but NO model/checkpoint: nothing was
# inferred, only measured).
PRODUCER_RHYTHM = "rhythm"
# CIRCUIT-001 P6-E — rhythm's sibling on the SAME cpu_perceptual reading. Where Gabor energy says
# "something repeats here", structure-tensor coherence says "the gradient here is ORGANISED along
# an axis" — drapery pulling one way, an architectural run, a directional strain. One adapter
# call already produces both maps, so this producer is a second reading of work already done.
PRODUCER_PRESSURE_ZONE = "pressure_zone"
# CIRCUIT-001 P8-A — open-vocab find_parts. Every producer above answers a question Semant chose
# in advance; this one answers the question the CURATOR asks, in words: "the folded cloth at her
# knee" → a mask. Florence-2 grounds the phrase; this producer turns that into the same
# `region_mask` suggestion the SAM refiner already mints, so a phrase-found part enters the
# circuit through the identical quarantine → review path as every other proposed region.
PRODUCER_FLORENCE_FIND = "florence_find_parts"
# CIRCUIT-001 P8-B — the open-vocab find_parts that actually runs. Two models, sequenced:
# GroundingDINO grounds the phrase to a BOX, then the already-live SAM2 refines that box into a
# real mask. Each answers what it is good at — roughly where, then exactly what extent — and the
# receipt names BOTH, because a mark produced by two models that credits one is a false receipt.
PRODUCER_GROUNDED_SAM = "grounded_sam_find_parts"
# CIRCUIT-001 P6-F — the second REAL-MODEL field (after material). Depth-Anything-V2-Small emits
# relative depth, which is what recession is actually about: not distance in metres but what falls
# away behind. Two roles from one reading — `background_recession` (the far band) and
# `atmosphere_field` (the near band, the condition the foreground sits in). It inferred, so the
# receipt is FULL (model/checkpoint/latency/vram), like material's and unlike the cpu ones.
PRODUCER_RECESSION = "recession"
# CIRCUIT-001 P6-G — the Monet answer. Every producer above reads WHAT is where; this one reads
# the LIGHT. Intrinsic decomposition separates albedo from shading, so `light_field` IS the
# shading map and `shadow_field` its exact complement — shadow is not a second measurement but
# the same one read as absence. A real model, so the receipt is full; DEFERRED until the
# GitHub-only package is installed (see intrinsic_service), which the producer never has to know.
PRODUCER_SHADING = "shading"

# The VLM emits a free-text relation ("beside", "echoes", "same-material-as"); the mark contract
# freezes relation_role to a fixed vocabulary. Map by keyword, default to the generic spatial
# address — a valid role so a relation is never silently dropped by the frontend validator.
_RELATION_ROLE_BY_KEYWORD = [
    (("echo", "motif", "repeat", "rhyme"), "motif_echo"),
    (("same-material", "same material", "material", "similar", "same"), "similarity"),
    (("contrast", "oppose", "differ", "unlike"), "contrast"),
    (("tension", "pull", "strain"), "tension"),
    (("contradict",), "contradiction"),
    (("kin", "family", "sibling", "pair"), "kinship"),
    (("support", "hold", "carry", "rest"), "support"),
    (("before", "after", "then", "sequence", "temporal"), "temporal_suggestion"),
    (("address", "face", "look", "gaze", "toward", "beside", "next", "near", "adjacent"), "address_relation"),
]
_RELATION_ROLE_DEFAULT = "address_relation"


def relation_role_for(relation: Optional[str]) -> str:
    """Map a free-text VLM relation to a frozen relation_role key (never None)."""
    text = (relation or "").strip().lower()
    for keywords, role in _RELATION_ROLE_BY_KEYWORD:
        if any(k in text for k in keywords):
            return role
    return _RELATION_ROLE_DEFAULT


def _provenance(*, model: Optional[str], adapter: Optional[str], latency_ms: Optional[float],
                run_id: Optional[str], producer: str) -> Dict[str, Any]:
    return {"model": model, "adapter": adapter, "latency_ms": latency_ms,
            "run_id": run_id, "producer": producer}


def suggestion_from_refine_region(
    region: Dict[str, Any], *, run_id: Optional[str], latency_ms: Optional[float] = None,
    model: str = "sam2.1", adapter: str = "sam2", base_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """A SAM2 preview region → a quarantined ``region_mask`` suggestion descriptor.

    The suggestion references the region SAM produced (``mask_ref`` — the mask lives on the
    region, never inline). Returns None if the region has no id (nothing to reference)."""
    region_id = region.get("id") if isinstance(region, dict) else None
    if not region_id:
        return None
    return {
        "producer": PRODUCER_SAM,
        "type": "region_mask",
        "role": None,                                   # a segmented extent has no reading yet
        "label": region.get("label") or "",
        "source_ref": str(region_id),                   # idempotency key part
        "geometry": {"kind": "raster_mask",
                     "mask_ref": {"region_id": region_id,
                                  "geometry_rev": region.get("geometry_rev", 0)}},
        "linked_ground_ids": [],
        "provenance": _provenance(model=model, adapter=adapter, latency_ms=latency_ms,
                                  run_id=run_id, producer=PRODUCER_SAM),
        # extra context (ignored by the frontend mapper, useful to the review UX / tests)
        "base_id": base_id,
    }


def suggestions_from_semantics(
    semantics: Optional[Dict[str, Any]], *, run_id: Optional[str],
    adapter: str = "semantic_pass", latency_ms: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """A semantic-read result → suggestion descriptors.

    Label proposals (assertions) → ``region_mask`` marks in ``region_ref`` mode: a NAMING
    reference to an existing region, no geometry authored (the VLM's law). Relation proposals →
    ``relation_mark`` marks with ``derived`` geometry, linked to their endpoint region ids.

    A curator-REJECTED assertion is not re-suggested; an OVERRIDDEN/edited label rides through as
    the curator's text. Ids are echoed straight from the semantics — the frontend keys idempotency
    on them, so a semantic rerun updates rather than duplicates."""
    sem = semantics or {}
    meta = sem.get("meta") or {}
    default_model = meta.get("model")
    out: List[Dict[str, Any]] = []

    for a in sem.get("assertions") or []:
        cid = a.get("candidate_id")
        if not cid or a.get("status") == "rejected":
            continue
        label = a.get("curator_label") or a.get("label") or ""
        out.append({
            "producer": PRODUCER_SEMANTIC,
            "type": "region_mask",
            "role": None,
            "label": label,
            "source_ref": str(cid),
            "geometry": {"kind": "region_ref", "region_ref": {"region_id": cid}},
            "linked_ground_ids": [],
            "provenance": _provenance(model=a.get("model") or default_model, adapter=adapter,
                                      latency_ms=latency_ms, run_id=run_id,
                                      producer=PRODUCER_SEMANTIC),
        })

    for r in sem.get("relations") or []:
        frm, to = r.get("from_id"), r.get("to_id")
        if not (frm and to):
            continue
        rel = r.get("relation") or ""
        out.append({
            "producer": PRODUCER_SEMANTIC,
            "type": "relation_mark",
            "role": relation_role_for(rel),
            "label": rel or "relation",
            "source_ref": f"{frm}|{to}|{rel}",
            "geometry": {"kind": "derived"},
            "linked_ground_ids": [frm, to],
            "provenance": _provenance(model=default_model, adapter=adapter, latency_ms=latency_ms,
                                      run_id=run_id, producer=PRODUCER_SEMANTIC),
        })

    return out


# ── producer 3: find-similar as producer (CIRCUIT-001 P5-A, the crossing) ─────────────────────

def suggestions_from_similar(
    result: Optional[Dict[str, Any]], *, run_id: Optional[str], adapter: str = "find_similar",
) -> List[Dict[str, Any]]:
    """A find-similar research packet → cross-post ``region_ref`` suggestion descriptors.

    Each neighbour is a Region on ANOTHER post. It becomes a ``model_suggested`` ``region_mask`` in
    ``region_ref`` mode ON THE CURRENT post, whose geometry is a REFERENCE across the border —
    ``{region_id, post_id, geometry_rev}`` — never a copy of the neighbour's pixels (the border
    rule: a crossing is a reference with receipts, never a copy). ``geometry_rev`` is captured at
    citation so staleness (the source changed since cited) stays detectable downstream.

    A degraded research packet (``status`` error/unavailable) carries no evidence to suggest → []."""
    res = result or {}
    if not isinstance(res, dict):
        return []
    if res.get("status") in ("error", "unavailable"):
        return []
    out: List[Dict[str, Any]] = []
    for h in res.get("results") or []:
        npost = h.get("post_id")
        nregion = h.get("region_id")
        if not npost or nregion is None:
            continue                                    # a neighbour with no source is not citable
        prov = h.get("provenance") or {}
        grev = prov.get("geometry_rev")
        region_ref: Dict[str, Any] = {"region_id": str(nregion), "post_id": str(npost)}
        if grev is not None:
            region_ref["geometry_rev"] = grev           # rev-at-citation → staleness detectable
        out.append({
            "producer": PRODUCER_FIND_SIMILAR,
            "type": "region_mask",
            "role": None,                               # a neighbour is evidence, not a reading
            "label": h.get("label") or "",
            # idempotency key: the border target, so re-searching the same neighbour replaces.
            "source_ref": f"{npost}:{nregion}",
            "geometry": {"kind": "region_ref", "region_ref": region_ref},
            "linked_ground_ids": [],
            "provenance": _provenance(model=prov.get("model"), adapter=adapter, latency_ms=None,
                                      run_id=run_id, producer=PRODUCER_FIND_SIMILAR),
        })
    return out


# ── producer 4: negative_space — the first brush_field producer (CIRCUIT-001 P6-A) ────────────

def suggestion_from_negative_space(
    region: Dict[str, Any], *, run_id: Optional[str], label: Optional[str] = None,
    base_id: Optional[str] = None, grid: int = 8, threshold: float = 0.12, radius: float = 0.05,
) -> Optional[Dict[str, Any]]:
    """A committed region's figure mask → a quarantined ``brush_field`` / ``negative_space``
    soft-field suggestion, carrying editable ``strokes[]``.

    CONSUMES the mask the region ALREADY carries (``mask_rle``). It calls no segmenter and loads no
    model — the negative space is the complement of a figure that is already there — so the receipt
    names a ``run_id`` and a ``producer`` but NO model/adapter/checkpoint: nothing was inferred, only
    geometry inverted. The mark's ``geometry.kind`` is ``soft_mask`` (the mark-layer name for a soft
    field; the action-layer ``geometry_mode`` for the same thing is ``soft_field``).

    Refusal (fail-closed): a region with no id or no valid ``mask_rle`` → None; a mask whose
    complement has nothing to draw (no figure, or all figure → an all-zero field → no strokes) →
    None. A field is NEVER fabricated from absence."""
    if not isinstance(region, dict):
        return None
    region_id = region.get("id")
    rle = region.get("mask_rle")
    if not region_id or not rle_is_valid(rle):
        return None
    field, h, w = soft_field_from_mask(rle)
    strokes = strokes_from_field(field, h, w, grid=grid, threshold=threshold, radius=radius)
    if not strokes:
        return None                                     # no negative space to speak of — refuse
    if label:
        text = label
    elif region.get("label"):
        text = f"negative space around {region['label']}"
    else:
        text = "negative space"
    return {
        "producer": PRODUCER_NEGATIVE_SPACE,
        "type": "brush_field",
        "role": "negative_space",
        "label": text,
        "source_ref": str(region_id),                   # idempotency key part
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        # A deterministic producer carries a run receipt but names no model — there was none.
        "provenance": {"run_id": run_id, "producer": PRODUCER_NEGATIVE_SPACE},
        "base_id": base_id,
    }


def suggestions_from_negative_space(
    regions: Optional[List[Dict[str, Any]]], *, run_id: Optional[str],
    grid: int = 8, threshold: float = 0.12, radius: float = 0.05,
) -> List[Dict[str, Any]]:
    """Every mask-bearing region in the packet → its negative-space suggestion. Regions without a
    usable mask are silently skipped (fail-closed); an empty or maskless input yields [] — never a
    fabricated field. Mirrors the crossing producer's degraded-input discipline."""
    out: List[Dict[str, Any]] = []
    for region in (regions or []):
        d = suggestion_from_negative_space(region, run_id=run_id, grid=grid,
                                           threshold=threshold, radius=radius)
        if d:
            out.append(d)
    return out


# ── producer 5: material_field — DINOv2 same-material field (CIRCUIT-001 P6-B) ─────────────────

def suggestion_from_material(
    features: Optional[Dict[str, Any]], seed_point: Any, *, run_id: Optional[str],
    region_id: Optional[str] = None, label: Optional[str] = None,
    model: Optional[str] = None, adapter: str = "dinov2_vits14", checkpoint: Optional[str] = None,
    preprocessing_version: Optional[str] = None, latency_ms: Optional[float] = None,
    peak_vram_mib: Optional[float] = None, min_contrast: float = 0.08,
    material_threshold: float = 0.5, radius: float = 0.05, grid_sample: int = 12,
) -> Optional[Dict[str, Any]]:
    """A tapped patch → DINOv2 cosine same-material soft field → a ``brush_field`` /
    ``material_field`` suggestion carrying editable ``strokes[]``.

    `features` is the SHARED DINOv2 patch grid — ``{"patches": <flat row-major list of grid*grid
    feature vectors>, "grid": int}`` — obtained through the ModelManager GPU path (the same
    substrate ``find_similar``/embeddings use; this producer re-encodes nothing). `seed_point` is a
    normalized ``(x, y)`` in [0, 1]: the patch the curator tapped.

    This DID infer, so ``provenance`` is a FULL receipt (model / adapter / checkpoint /
    preprocessing_version / latency_ms / peak_vram_mib) — every field the caller measured. The one
    receipt field withheld is ``confidence``: a mark may never carry a confidence score (contract
    §6), so the field's contrast rides the descriptor as ``confidence`` (visible to the review UX)
    but never reaches ``provenance`` and so never lands on the minted mark.

    Refusal (fail-closed): no seed / seed outside the frame → None; empty or malformed features →
    None; a near-uniform field (contrast below ``min_contrast`` — nothing distinguishes the seed's
    material) → None; nothing clearing the same-material threshold → None. A field is never
    fabricated from a flat one."""
    if not isinstance(features, dict):
        return None
    grid = int(features.get("grid") or 0)
    patches = features.get("patches")
    if grid <= 0 or not patches:
        return None
    if not (isinstance(seed_point, (list, tuple)) and len(seed_point) == 2):
        return None
    try:
        sx, sy = float(seed_point[0]), float(seed_point[1])
    except (TypeError, ValueError):
        return None
    if not (0.0 <= sx <= 1.0 and 0.0 <= sy <= 1.0):
        return None

    gx = min(grid - 1, max(0, int(sx * grid)))
    gy = min(grid - 1, max(0, int(sy * grid)))
    field, gh, gw = cosine_field_from_features(patches, grid, gy * grid + gx)
    if not field:
        return None
    contrast = round(field_contrast(field), 4)
    if contrast < min_contrast:
        return None                                     # near-uniform — nothing to distinguish
    strokes = strokes_from_field(field, gh, gw, grid=min(grid_sample, grid),
                                 threshold=material_threshold, radius=radius)
    if not strokes:
        return None                                     # nothing clears the same-material threshold

    # The full inference receipt — every field the caller actually measured, `confidence` excepted.
    receipt: Dict[str, Any] = {"run_id": run_id, "producer": PRODUCER_MATERIAL, "adapter": adapter}
    for key, val in (("model", model), ("checkpoint", checkpoint),
                     ("preprocessing_version", preprocessing_version),
                     ("latency_ms", latency_ms), ("peak_vram_mib", peak_vram_mib)):
        if val is not None:
            receipt[key] = val
    return {
        "producer": PRODUCER_MATERIAL,
        "type": "brush_field",
        "role": "material_field",
        "label": label or "same material",
        # idempotency: a re-tap on the SAME region + SAME patch cell replaces, never duplicates.
        "source_ref": f"{region_id or 'img'}@{gy}:{gx}",
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        "provenance": receipt,                          # FULL receipt — but never `confidence` (§6)
        "confidence": contrast,                         # rides the descriptor, never the mark
    }


def suggestions_from_material(
    features: Optional[Dict[str, Any]], seeds: Optional[List[Any]], *, run_id: Optional[str],
    region_id: Optional[str] = None, **kw,
) -> List[Dict[str, Any]]:
    """One field per seed patch. Seeds that refuse (outside the frame, or a near-uniform field) are
    skipped; empty or malformed input yields [] — never a fabricated field."""
    out: List[Dict[str, Any]] = []
    for seed in (seeds or []):
        d = suggestion_from_material(features, seed, run_id=run_id, region_id=region_id, **kw)
        if d:
            out.append(d)
    return out


# ── producer 6: rhythm — cpu_perceptual, no model at all (CIRCUIT-001 P6-D) ────────────────────

def _remap_strokes_into_box(strokes: List[Dict[str, Any]], box: Optional[Dict[str, Any]]
                            ) -> List[Dict[str, Any]]:
    """Strokes measured over a CROP are normalized to that crop; the mark lives in IMAGE space.

    Rescale each point by the crop's normalized bbox so a field read inside a region lands on
    that region rather than over the whole frame. `box` absent (or full-frame) → unchanged."""
    if not box:
        return strokes
    bx, by = float(box.get("x", 0.0)), float(box.get("y", 0.0))
    bw, bh = float(box.get("w", 1.0)), float(box.get("h", 1.0))
    if bw <= 0 or bh <= 0:
        return strokes
    out: List[Dict[str, Any]] = []
    for s in strokes:
        pts = [[round(bx + px * bw, 4), round(by + py * bh, 4)] for px, py in s.get("points", [])]
        out.append({**s, "points": pts,
                    # a stroke painted into a crop covers a proportionally smaller slice of the
                    # image, so its radius shrinks with the crop rather than staying frame-sized.
                    "radius": round(float(s.get("radius", 0.05)) * max(bw, bh), 4)})
    return out


def _field_descriptor(*, producer: str, role: str, label: str, source_ref: str,
                      strokes: List[Dict[str, Any]], run_id: Optional[str], adapter: str,
                      latency_ms: Optional[float], confidence: Optional[float]) -> Dict[str, Any]:
    """The shared shape every DETERMINISTIC field producer emits (P6-A/P6-D/P6-E).

    The receipt names an adapter and a run but NO model/checkpoint — nothing was inferred, only
    measured — and `confidence` rides the descriptor, never `provenance` (a mark may not carry a
    confidence score, contract §6)."""
    receipt: Dict[str, Any] = {"run_id": run_id, "producer": producer, "adapter": adapter}
    if latency_ms is not None:
        receipt["latency_ms"] = latency_ms
    d: Dict[str, Any] = {
        "producer": producer,
        "type": "brush_field",
        "role": role,
        "label": label,
        "source_ref": source_ref,
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        "provenance": receipt,
    }
    if confidence is not None:
        d["confidence"] = confidence
    return d


def suggestion_from_rhythm(
    analysis: Optional[Dict[str, Any]], *, run_id: Optional[str],
    region_id: Optional[str] = None, box: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None, latency_ms: Optional[float] = None,
    # relative relief, not normalized contrast — see `_from_perceptual_map`. Measured against
    # real Gabor output: a hard-striped surface reads ≈0.18, a blank one 0.00, so 0.05 separates
    # "something repeats here" from "this is a flat wall" without demanding a test pattern.
    min_contrast: float = 0.05, threshold: float = 0.55, radius: float = 0.05,
    grid_sample: int = 12,
) -> Optional[Dict[str, Any]]:
    """A cpu_perceptual reading → a ``brush_field`` / ``rhythm`` soft-field suggestion.

    `analysis` is the adapter's output — ``{"energy": [...], "grid": n}`` — measured over the
    region's crop. Gabor energy is high where something REPEATS, so the normalized field marks
    where the repetition lives; `box` maps that crop-space field back onto the image.

    Refusal (fail-closed): no analysis, an empty/short map, a flat surface (contrast below
    ``min_contrast`` — nothing repeats, so there is no rhythm to claim), or nothing clearing the
    threshold → None. Rhythm is never fabricated from a flat wall."""
    return _from_perceptual_map(
        analysis, key="energy", producer=PRODUCER_RHYTHM, role="rhythm",
        default_label="rhythm — where something repeats", run_id=run_id, region_id=region_id,
        box=box, label=label, latency_ms=latency_ms, min_contrast=min_contrast,
        threshold=threshold, radius=radius, grid_sample=grid_sample)


def _from_perceptual_map(
    analysis: Optional[Dict[str, Any]], *, key: str, producer: str, role: str,
    default_label: str, run_id: Optional[str], region_id: Optional[str],
    box: Optional[Dict[str, Any]], label: Optional[str], latency_ms: Optional[float],
    min_contrast: float, threshold: float, radius: float, grid_sample: int,
) -> Optional[Dict[str, Any]]:
    """Shared body for the cpu_perceptual producers — one map key per perceptual role."""
    if not isinstance(analysis, dict):
        return None
    grid = int(analysis.get("grid") or 0)
    values = analysis.get(key)
    if grid <= 0 or not values or len(values) < grid * grid:
        return None

    # The degeneracy test must run on the RAW magnitudes, not the normalized field. Min-max
    # normalization rescales whatever it is given to span [0,1], so a normalized field's contrast
    # is ~1.0 for ANY input that is not exactly constant — including a blank wall with a whisper
    # of sensor noise, which would then be painted as confident rhythm. The honest measure is
    # RELATIVE RELIEF: how large the variation is against the magnitude it varies within.
    raw = [float(v) for v in list(values)[:grid * grid]]
    hi, lo = max(raw), min(raw)
    relief = (hi - lo) / (abs(hi) + 1e-9)
    if relief < min_contrast:
        return None                                  # flat / near-uniform → nothing to say

    field, gh, gw = soft_field_from_map(raw, grid)
    if not field:
        return None
    strokes = strokes_from_field(field, gh, gw, grid=min(grid_sample, grid),
                                 threshold=threshold, radius=radius)
    if not strokes:
        return None
    strokes = _remap_strokes_into_box(strokes, box)
    return _field_descriptor(
        producer=producer, role=role, label=label or default_label,
        source_ref=f"{region_id or 'img'}:{role}", strokes=strokes, run_id=run_id,
        adapter="cpu_perceptual", latency_ms=latency_ms,
        confidence=round(min(1.0, max(0.0, relief)), 4))


def suggestions_from_rhythm(
    analysis: Optional[Dict[str, Any]], *, run_id: Optional[str], **kw
) -> List[Dict[str, Any]]:
    """The list form — one rhythm field, or [] when the surface refuses to have one."""
    d = suggestion_from_rhythm(analysis, run_id=run_id, **kw)
    return [d] if d else []


# ── producer 7: pressure_zone — rhythm's sibling on the same reading (CIRCUIT-001 P6-E) ────────

def suggestion_from_pressure_zone(
    analysis: Optional[Dict[str, Any]], *, run_id: Optional[str],
    region_id: Optional[str] = None, box: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None, latency_ms: Optional[float] = None,
    min_contrast: float = 0.05, threshold: float = 0.55, radius: float = 0.05,
    grid_sample: int = 12,
) -> Optional[Dict[str, Any]]:
    """A cpu_perceptual reading → a ``brush_field`` / ``pressure_zone`` soft-field suggestion.

    Reads the ``coherence`` map from the SAME analysis rhythm reads — structure-tensor coherence
    is high where the local gradient is directional (a pull, a run, a strain) and low where it is
    isotropic. No second adapter call, no model, no GPU.

    Refusal (fail-closed): no analysis, an empty/short map, or an isotropic surface — a region
    with no directional organisation has no pressure to claim. On a truly flat surface every
    gradient is zero, so coherence is uniformly zero and the relief test refuses it."""
    return _from_perceptual_map(
        analysis, key="coherence", producer=PRODUCER_PRESSURE_ZONE, role="pressure_zone",
        default_label="pressure — where the surface pulls", run_id=run_id, region_id=region_id,
        box=box, label=label, latency_ms=latency_ms, min_contrast=min_contrast,
        threshold=threshold, radius=radius, grid_sample=grid_sample)


def suggestions_from_pressure_zone(
    analysis: Optional[Dict[str, Any]], *, run_id: Optional[str], **kw
) -> List[Dict[str, Any]]:
    """The list form — one pressure field, or [] when the surface is isotropic."""
    d = suggestion_from_pressure_zone(analysis, run_id=run_id, **kw)
    return [d] if d else []


# ── producer 8: recession — Depth-Anything relative depth (CIRCUIT-001 P6-F) ────────────────────

# The two readings one depth map supports. `background_recession` is the far band (what falls away);
# `atmosphere_field` is the near band (the condition the foreground sits in). Both are FIELD_ROLES.
DEPTH_ROLE_BANDS = {"background_recession": "far", "atmosphere_field": "near"}


def suggestion_from_recession(
    depth: Optional[Dict[str, Any]], *, run_id: Optional[str],
    role: str = "background_recession", region_id: Optional[str] = None,
    box: Optional[Dict[str, Any]] = None, label: Optional[str] = None,
    model: Optional[str] = None, adapter: str = "depth_anything_v2_small",
    checkpoint: Optional[str] = None, preprocessing_version: Optional[str] = None,
    latency_ms: Optional[float] = None, peak_vram_mib: Optional[float] = None,
    min_contrast: float = 0.05, threshold: float = 0.55, radius: float = 0.05,
    grid_sample: int = 12,
) -> Optional[Dict[str, Any]]:
    """A relative-depth reading → a ``brush_field`` recession/atmosphere soft field.

    `depth` is the adapter's output — ``{"depth": [...], "grid": n}``. Depth-Anything emits INVERSE
    depth (larger = nearer), so the far band is the normalized map's complement; `role` selects
    which band is painted (see ``DEPTH_ROLE_BANDS``).

    This one INFERRED, so the receipt is full — model / checkpoint / preprocessing / latency /
    peak VRAM — with the same single exception as material: ``confidence`` never enters
    ``provenance`` (contract §6) and rides the descriptor instead.

    Refusal (fail-closed): no reading, a malformed/short map, an unknown role, or a scene with no
    depth relief (a flat wall, a copy shot) → None. Distance is never invented."""
    if not isinstance(depth, dict):
        return None
    band = DEPTH_ROLE_BANDS.get(role)
    if band is None:
        return None
    grid = int(depth.get("grid") or 0)
    values = depth.get("depth")
    if grid <= 0 or not values or len(values) < grid * grid:
        return None

    raw = [float(v) for v in list(values)[:grid * grid]]
    hi, lo = max(raw), min(raw)
    relief = (hi - lo) / (abs(hi) + 1e-9)
    if relief < min_contrast:
        return None                                  # no depth relief → nothing recedes

    field, gh, gw = depth_band_field(raw, grid, band=band)
    if not field:
        return None
    strokes = strokes_from_field(field, gh, gw, grid=min(grid_sample, grid),
                                 threshold=threshold, radius=radius)
    if not strokes:
        return None
    strokes = _remap_strokes_into_box(strokes, box)

    receipt: Dict[str, Any] = {"run_id": run_id, "producer": PRODUCER_RECESSION, "adapter": adapter}
    for key, val in (("model", model), ("checkpoint", checkpoint),
                     ("preprocessing_version", preprocessing_version),
                     ("latency_ms", latency_ms), ("peak_vram_mib", peak_vram_mib)):
        if val is not None:
            receipt[key] = val
    default_label = ("recession — what falls away behind" if band == "far"
                     else "atmosphere — the condition the foreground sits in")
    return {
        "producer": PRODUCER_RECESSION,
        "type": "brush_field",
        "role": role,
        "label": label or default_label,
        "source_ref": f"{region_id or 'img'}:{role}",
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        "provenance": receipt,                        # FULL receipt — but never `confidence` (§6)
        "confidence": round(min(1.0, max(0.0, relief)), 4),
    }


def suggestions_from_recession(
    depth: Optional[Dict[str, Any]], *, run_id: Optional[str],
    roles: Optional[List[str]] = None, **kw
) -> List[Dict[str, Any]]:
    """Both bands of one depth reading, or [] when the scene has no relief to speak of."""
    out: List[Dict[str, Any]] = []
    for role in (roles or ["background_recession"]):
        d = suggestion_from_recession(depth, run_id=run_id, role=role, **kw)
        if d:
            out.append(d)
    return out


# ── producer 9: light / shadow — Intrinsic Ordinal Shading (CIRCUIT-001 P6-G) ───────────────────

# The two readings one shading map supports. `fall_of_light` is deliberately NOT here: a direction
# is a trace_mark, not a brush_field, and that family is a separate act (the converter ships).
SHADING_ROLE_BANDS = {"light_field": "light", "shadow_field": "shadow"}


def _suggestion_from_shading(
    shading: Optional[Dict[str, Any]], *, role: str, run_id: Optional[str],
    region_id: Optional[str] = None, box: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None, model: Optional[str] = None,
    adapter: str = "intrinsic_ordinal_shading", checkpoint: Optional[str] = None,
    preprocessing_version: Optional[str] = None, latency_ms: Optional[float] = None,
    peak_vram_mib: Optional[float] = None,
    # CALIBRATED against the real model (P6-I), not guessed. A neural decomposition does not
    # return a constant map for a constant image — fed a flat gray it still reports relief 0.062,
    # flat white 0.135, i.e. gentle invented structure. A real photograph reads 0.824. 0.25 sits
    # in that gap with margin on both sides, so a blank wall refuses and a lit scene does not.
    # (The 0.05 the scaffold shipped would have painted a confident light field onto blank gray.)
    min_contrast: float = 0.25,
    threshold: float = 0.55, radius: float = 0.05, grid_sample: int = 12,
) -> Optional[Dict[str, Any]]:
    """Shared body: a shading reading → a lit or withheld ``brush_field``.

    Full model receipt (it inferred), with `confidence` on the descriptor only (contract §6).
    Refuses an evenly-lit surface: a flat wash has no light field worth marking, and inventing
    one would be the same lie as painting rhythm onto a blank wall."""
    if not isinstance(shading, dict):
        return None
    band = SHADING_ROLE_BANDS.get(role)
    if band is None:
        return None
    grid = int(shading.get("grid") or 0)
    values = shading.get("shading")
    if grid <= 0 or not values or len(values) < grid * grid:
        return None

    raw = [float(v) for v in list(values)[:grid * grid]]
    hi, lo = max(raw), min(raw)
    relief = (hi - lo) / (abs(hi) + 1e-9)
    if relief < min_contrast:
        return None                                  # evenly lit → no light field to claim

    field, gh, gw = shading_band_field(raw, grid, band=band)
    if not field:
        return None
    strokes = strokes_from_field(field, gh, gw, grid=min(grid_sample, grid),
                                 threshold=threshold, radius=radius)
    if not strokes:
        return None
    strokes = _remap_strokes_into_box(strokes, box)

    receipt: Dict[str, Any] = {"run_id": run_id, "producer": PRODUCER_SHADING, "adapter": adapter}
    for key, val in (("model", model), ("checkpoint", checkpoint),
                     ("preprocessing_version", preprocessing_version),
                     ("latency_ms", latency_ms), ("peak_vram_mib", peak_vram_mib)):
        if val is not None:
            receipt[key] = val
    default_label = ("light — where the light lives" if band == "light"
                     else "shadow — where it is withheld")
    d: Dict[str, Any] = {
        "producer": PRODUCER_SHADING,
        "type": "brush_field",
        "role": role,
        "label": label or default_label,
        "source_ref": f"{region_id or 'img'}:{role}",
        "geometry": {"kind": "soft_mask", "strokes": strokes},
        "linked_ground_ids": [],
        "provenance": receipt,
        "confidence": round(min(1.0, max(0.0, relief)), 4),
    }
    # The fall of light rides along as context for the review UX (and for a future trace
    # producer). It is NOT geometry on this mark — a field does not carry a direction.
    fall = shading_gradient(raw, grid)
    if fall:
        d["fall_of_light"] = fall
    return d


def suggestion_from_light(shading, *, run_id, **kw):
    """A shading reading → a ``light_field`` soft field: where the light lives."""
    return _suggestion_from_shading(shading, role="light_field", run_id=run_id, **kw)


def suggestion_from_shadow(shading, *, run_id, **kw):
    """A shading reading → a ``shadow_field`` soft field: where the light is withheld."""
    return _suggestion_from_shading(shading, role="shadow_field", run_id=run_id, **kw)


def suggestions_from_shading(
    shading: Optional[Dict[str, Any]], *, run_id: Optional[str],
    roles: Optional[List[str]] = None, **kw
) -> List[Dict[str, Any]]:
    """Both bands of one shading reading, or [] when the surface is evenly lit."""
    out: List[Dict[str, Any]] = []
    for role in (roles or ["light_field"]):
        d = _suggestion_from_shading(shading, role=role, run_id=run_id, **kw)
        if d:
            out.append(d)
    return out


# ── producer 10: open-vocab find_parts — Florence-2 phrase → region (CIRCUIT-001 P8-A) ─────────

def suggestion_from_phrase(
    grounding: Optional[Dict[str, Any]], *, phrase: str, run_id: Optional[str],
    model: Optional[str] = None, adapter: str = "florence2_base",
    checkpoint: Optional[str] = None, revision: Optional[str] = None,
    preprocessing_version: Optional[str] = None, latency_ms: Optional[float] = None,
    peak_vram_mib: Optional[float] = None, region_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """A grounded phrase → a quarantined ``region_mask`` suggestion carrying real geometry.

    Unlike the SAM refiner — which references a region the segmenter already persisted — a
    phrase-found part does not exist yet, so the descriptor carries the geometry inline under
    ``proposed_geometry`` (normalized polygons + box) for the acceptance path to mint a Region
    from. The mark itself still authors no pixels: ``geometry.kind`` stays ``region_ref`` once a
    Region exists. Until the curator accepts, this is a proposal about where something is.

    The receipt is FULL and names the pinned revision — "which weights said this" is part of the
    claim, not metadata about it.

    Refusal (fail-closed): the phrase grounds nothing, or everything it grounds is degenerate →
    None. A phrase that finds nothing must return nothing; a box covering the whole frame or a
    two-point 'polygon' is not a part, and inventing one would be the model agreeing with the
    curator rather than answering them."""
    text = (phrase or "").strip()
    if not text:
        return None
    geom = region_geometry_from_grounding(grounding)
    if not geom:
        return None

    receipt: Dict[str, Any] = {"run_id": run_id, "producer": PRODUCER_FLORENCE_FIND,
                               "adapter": adapter}
    for key, val in (("model", model), ("checkpoint", checkpoint), ("revision", revision),
                     ("preprocessing_version", preprocessing_version),
                     ("latency_ms", latency_ms), ("peak_vram_mib", peak_vram_mib)):
        if val is not None:
            receipt[key] = val

    return {
        "producer": PRODUCER_FLORENCE_FIND,
        "type": "region_mask",
        "role": None,                       # a found extent has no perceptual reading yet
        "label": text,                      # the curator's own words name it
        # idempotency: the same phrase on the same image replaces rather than duplicates.
        "source_ref": f"phrase:{text.lower()}",
        # No Region exists yet, so nothing can be referenced. `unresolved` is the honest kind
        # until acceptance mints one — the geometry rides alongside as a PROPOSAL.
        "geometry": {"kind": "unresolved"},
        "proposed_geometry": {"polygons": geom["polygons"], "box": geom["box"]},
        "linked_ground_ids": [],
        "provenance": receipt,
        "phrase": text,
    }


def suggestions_from_phrase(
    grounding: Optional[Dict[str, Any]], *, phrase: str, run_id: Optional[str], **kw
) -> List[Dict[str, Any]]:
    """The list form — one suggestion, or [] when the phrase grounds nothing here."""
    d = suggestion_from_phrase(grounding, phrase=phrase, run_id=run_id, **kw)
    return [d] if d else []


# ── producer 11: Grounded-SAM open-vocab find_parts (CIRCUIT-001 P8-B) ─────────────────────────

def best_grounded_box(detection: Optional[Dict[str, Any]], *, min_score: float = 0.5
                      ) -> Optional[Dict[str, Any]]:
    """The highest-scoring grounded box, normalized — or None when nothing clears `min_score`.

    Pure, so the threshold decision is testable without a GPU. The threshold is the honest
    presence-check: below it the detector is guessing, and a guessed box handed to SAM2 comes back
    as a confident-looking mask around nothing."""
    if not isinstance(detection, dict):
        return None
    boxes = detection.get("boxes") or []
    scores = detection.get("scores") or []
    size = detection.get("image_size") or [0, 0]
    w, h = int(size[0] or 0), int(size[1] or 0)
    if not boxes or w <= 0 or h <= 0:
        return None
    best_i, best_score = None, -1.0
    for i, b in enumerate(boxes):
        sc = float(scores[i]) if i < len(scores) else 0.0
        if sc >= min_score and sc > best_score:
            best_i, best_score = i, sc
    if best_i is None:
        return None
    x0, y0, x1, y1 = (float(v) for v in boxes[best_i][:4])
    nx0, ny0 = max(0.0, min(1.0, x0 / w)), max(0.0, min(1.0, y0 / h))
    nx1, ny1 = max(0.0, min(1.0, x1 / w)), max(0.0, min(1.0, y1 / h))
    if (nx1 - nx0) <= 0.005 or (ny1 - ny0) <= 0.005:
        return None                                  # a sliver is not a part
    return {"box_xyxy": [round(nx0, 5), round(ny0, 5), round(nx1, 5), round(ny1, 5)],
            "score": round(best_score, 4),
            "label": (detection.get("labels") or [""])[best_i]
                     if best_i < len(detection.get("labels") or []) else ""}


def suggestion_from_grounded_phrase(
    region: Optional[Dict[str, Any]], *, phrase: str, run_id: Optional[str],
    score: Optional[float] = None,
    detector_model: Optional[str] = None, detector_revision: Optional[str] = None,
    segmenter_model: str = "sam2.1", detector_latency_ms: Optional[float] = None,
    segmenter_latency_ms: Optional[float] = None, peak_vram_mib: Optional[float] = None,
    presence: Optional[float] = None, verifier_model: Optional[str] = None,
    verifier_revision: Optional[str] = None, verifier_latency_ms: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """A SAM2-refined region (grounded from a phrase) → a ``region_mask`` find_parts suggestion.

    `region` is what `refine_session.preview` already returns — the SAME shape the SAM refine
    producer consumes — so a phrase-found part reaches the quarantine through the identical path
    as a click-refined one. Nothing new is invented downstream.

    The receipt names BOTH models. A two-model chain that credits one is a false receipt: the
    extent came from SAM2, but *where to look* came from the detector, and a curator auditing the
    mark later needs both to reproduce it.

    Refusal: no region (the phrase grounded nothing, or SAM2 declined) → None."""
    text = (phrase or "").strip()
    if not text or not isinstance(region, dict) or not region.get("id"):
        return None

    receipt: Dict[str, Any] = {
        "run_id": run_id, "producer": PRODUCER_GROUNDED_SAM,
        # two adapters, named in the order they ran
        "adapter": "grounding_dino_tiny+sam2",
        "segmenter_model": segmenter_model,
    }
    for key, val in (("model", detector_model), ("revision", detector_revision),
                     ("detector_latency_ms", detector_latency_ms),
                     ("latency_ms", segmenter_latency_ms),
                     ("peak_vram_mib", peak_vram_mib),
                     # P8-C: the verifier is part of the claim. A mark that survived a presence
                     # gate should say which model agreed it was there, and at what pin.
                     ("verifier_model", verifier_model),
                     ("verifier_revision", verifier_revision),
                     ("verifier_latency_ms", verifier_latency_ms)):
        if val is not None:
            receipt[key] = val
    if verifier_model:
        receipt["adapter"] = "grounding_dino_tiny+clip_vit_b32+sam2"

    d: Dict[str, Any] = {
        "producer": PRODUCER_GROUNDED_SAM,
        "type": "region_mask",
        "role": None,                                # a found extent has no reading yet
        "label": text,                               # the curator's words name it
        "source_ref": f"phrase:{text.lower()}",      # same question → same suggestion
        # SAM2 produced a real mask on a real region, so this REFERENCES it — no inline pixels,
        # exactly like the click-refine producer.
        "geometry": {"kind": "raster_mask",
                     "mask_ref": {"region_id": region["id"],
                                  "geometry_rev": region.get("geometry_rev", 0)}},
        "linked_ground_ids": [],
        "provenance": receipt,
        "phrase": text,
    }
    if score is not None:
        d["confidence"] = round(float(score), 4)     # descriptor only — never on the mark (§6)
    if presence is not None:
        # The gate's verdict rides the descriptor too, for the same reason: it is a score, and a
        # mark may not carry one (contract §6). Review can show it; evidence cannot claim it.
        d["presence"] = round(float(presence), 4)
    return d


def suggestions_from_grounded_phrase(
    region: Optional[Dict[str, Any]], *, phrase: str, run_id: Optional[str], **kw
) -> List[Dict[str, Any]]:
    """The list form — one suggestion, or [] when the phrase grounds nothing here."""
    d = suggestion_from_grounded_phrase(region, phrase=phrase, run_id=run_id, **kw)
    return [d] if d else []
