"""One explicit source-to-working image boundary for the six field families.

The original encoded bytes and their existing LabSource digest remain authoritative.
The returned sRGB raster is a derivative with its own digest and a recorded transform.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps

from backend.services.perception_lab.source import image_digest

MAX_PIXELS = 16_777_216


@dataclass(frozen=True)
class PreparedImage:
    source_bytes: bytes
    source_digest: str
    source_size: tuple[int, int]
    working_size: tuple[int, int]
    rgb_bytes: bytes
    alpha_bytes: bytes
    working_rgb_digest: str
    orientation: int
    profile: str
    source_to_working: tuple[int, ...]


def _orientation_matrix(code: int, width: int, height: int) -> tuple[int, ...]:
    # Pixel coordinates have their origin at top left. The bounds use pixel centres.
    return {
        1: (1, 0, 0, 0, 1, 0, 0, 0, 1),
        2: (-1, 0, width - 1, 0, 1, 0, 0, 0, 1),
        3: (-1, 0, width - 1, 0, -1, height - 1, 0, 0, 1),
        4: (1, 0, 0, 0, -1, height - 1, 0, 0, 1),
        5: (0, 1, 0, 1, 0, 0, 0, 0, 1),
        6: (0, -1, height - 1, 1, 0, 0, 0, 0, 1),
        7: (0, -1, height - 1, -1, 0, width - 1, 0, 0, 1),
        8: (0, 1, 0, -1, 0, width - 1, 0, 0, 1),
    }[code]


def prepare_image(source_bytes: bytes) -> PreparedImage:
    if not source_bytes or len(source_bytes) > 64 * 1024 * 1024:
        raise ValueError("source image is empty or exceeds the preparation limit")
    with Image.open(io.BytesIO(source_bytes)) as opened:
        width, height = opened.size
        if not width or not height or width * height > MAX_PIXELS:
            raise ValueError("source image dimensions exceed the preparation limit")
        orientation = int(opened.getexif().get(274, 1))
        if orientation not in range(1, 9):
            raise ValueError("unsupported EXIF orientation")
        image = ImageOps.exif_transpose(opened)
        alpha = image.getchannel("A") if "A" in image.getbands() else Image.new("L", image.size, 255)
        icc = opened.info.get("icc_profile")
        if icc:
            try:
                profile = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                rgb = ImageCms.profileToProfile(image.convert("RGB"), profile,
                                                ImageCms.createProfile("sRGB"), outputMode="RGB")
            except Exception as exc:
                raise ValueError("embedded ICC profile could not be converted to sRGB") from exc
            profile_label = "embedded ICC converted to sRGB"
        else:
            rgb = image.convert("RGB")
            profile_label = "sRGB assumed; no embedded ICC profile"
        rgb_bytes = rgb.tobytes()
        return PreparedImage(
            source_bytes=source_bytes, source_digest=image_digest(source_bytes),
            source_size=(width, height), working_size=image.size,
            rgb_bytes=rgb_bytes, alpha_bytes=alpha.tobytes(),
            working_rgb_digest="sha256:" + hashlib.sha256(rgb_bytes).hexdigest(),
            orientation=orientation, profile=profile_label,
            source_to_working=_orientation_matrix(orientation, width, height))
