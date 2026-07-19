"""
VISION-D · D1 — evidence packet.

The packet must map stable candidate ids to the right masks, mark curator labels
authoritative, list allowed_ids, and build a prompt that binds interpretation to those ids
with no geometry permission. Contact-sheet snapshots for the four domains are generated as
gate evidence (see D1 report); here we test structure + invariants.
"""
import base64
import io

import numpy as np
import pytest

from backend.services import evidence_packet as ep
from backend.services import mask_geometry as mg


def _img_bytes(w=80, h=60):
    from PIL import Image
    im = Image.new("RGB", (w, h), (120, 120, 120))
    buf = io.BytesIO(); im.save(buf, format="JPEG")
    return buf.getvalue()


def _region(rid, x, y, w, h, **kw):
    bits = np.zeros((60, 80), dtype=np.uint8)
    bits[int(y * 60):int((y + h) * 60), int(x * 80):int((x + w) * 80)] = 1
    r = {"id": rid, "mask_rle": mg.rle_encode_mask(bits)}
    mg.canonicalize_geometry(r, provenance={"adapter": kw.get("detector", "yolo")})
    r.update({"detector": kw.get("detector", "yolo"), "category": kw.get("category", "object"),
              "label": kw.get("label", ""), "actor": kw.get("actor", "auto"),
              "user_note": kw.get("user_note", "")})
    return r


def test_packet_structure_and_stable_numbering():
    post = {"region_annotations": [
        _region("seg_1", 0.5, 0.1, 0.3, 0.3, label="chair"),
        _region("seg_0", 0.1, 0.1, 0.3, 0.3, label="table"),   # deliberately out of order
    ], "domain_profile": {"chosen": ["general"]}}
    pk = ep.build_packet(post, _img_bytes(), intent="name")
    # numbering is deterministic: sorted by id, so seg_0 → 1, seg_1 → 2 regardless of input order
    assert pk["numbering"] == {"seg_0": 1, "seg_1": 2}
    assert pk["allowed_ids"] == ["seg_0", "seg_1"]
    assert [c["candidate_id"] for c in pk["candidates"]] == ["seg_0", "seg_1"]
    # base64 images decode
    assert base64.b64decode(pk["image_b64"]) and base64.b64decode(pk["contact_sheet_b64"])
    assert pk["image_hash"] and len(pk["image_hash"]) == 64


def test_numbering_survives_reruns():
    post = {"region_annotations": [_region("b", 0.1, 0.1, 0.2, 0.2),
                                   _region("a", 0.5, 0.5, 0.2, 0.2)]}
    n1 = ep.build_packet(post, _img_bytes())["numbering"]
    n2 = ep.build_packet(post, _img_bytes())["numbering"]
    assert n1 == n2 == {"a": 1, "b": 2}                 # stable across calls (retry/cache safe)


def test_curator_labels_marked_authoritative():
    post = {"region_annotations": [
        _region("seg_0", 0.1, 0.1, 0.3, 0.3, label="Gandhara head", actor="creator"),
        _region("seg_1", 0.5, 0.1, 0.3, 0.3, label="face", user_note="the calm one"),
    ]}
    pk = ep.build_packet(post, _img_bytes())
    by_id = {c["candidate_id"]: c for c in pk["candidates"]}
    assert by_id["seg_0"]["curator_label"] == "Gandhara head" and by_id["seg_0"]["authoritative"]
    assert by_id["seg_1"]["curator_note"] == "the calm one" and by_id["seg_1"]["authoritative"]
    # the prompt tells the model these are authoritative and must not be overwritten
    assert "AUTHORITATIVE" in pk["prompt"] and "Gandhara head" in pk["prompt"]


def test_prompt_binds_to_ids_and_forbids_geometry():
    post = {"region_annotations": [_region("seg_0", 0.1, 0.1, 0.3, 0.3, label="wall")]}
    prompt = ep.build_packet(post, _img_bytes())["prompt"]
    assert "id=seg_0" in prompt
    assert "NO geometry" in prompt and "never invent ids" in prompt
    assert "needs_better_evidence" in prompt          # the painting escape hatch


def test_empty_regions_yields_empty_candidates():
    pk = ep.build_packet({"region_annotations": []}, _img_bytes())
    assert pk["candidates"] == [] and pk["allowed_ids"] == []
