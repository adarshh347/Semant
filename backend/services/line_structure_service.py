"""
CIRCUIT-001 TRACE-001 — line-segment detection. CPU only, OpenCV only, no model.

The detection half of `architectural_axis`. Shaped like `cpu_perceptual_service`: lazy cv2
import, an `is_available()` that answers honestly, and no state — so it never touches the
GPU semaphore and cannot be evicted by, or evict, a model adapter. There is nothing to
unload, which is why this service is absent from `/produce-field/unload` (the list that has
leaked three times); a producer with no resident weights has nothing to leak.

WHY LSD AND NOT HOUGH. `HoughLinesP` needs a Canny threshold pair chosen per image: too tight
and an interior's soft cornice edges vanish, too loose and foliage explodes into thousands of
spurious segments — and the threshold that separates those two cases is exactly the thing the
producer is trying to measure, so choosing it up front decides the answer in advance. LSD is
parameter-free on the input side: it finds level-line regions at whatever contrast they occur
and reports each with an extent. Verified present in this environment (cv2 5.0.0); LSD was
absent from OpenCV between 4.1 and 4.7 over a patent, so `is_available()` probes the factory
rather than trusting the version string, and Hough remains as a declared fallback.

This module reports what it FOUND. It makes no claim about whether those lines constitute
architecture — that judgement needs thresholds calibrated against real pictures, and it lives
in the producer where it can be named and defended.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

ADAPTER_LSD = "opencv_lsd"
ADAPTER_HOUGH = "opencv_houghp"
PREPROCESSING_VERSION = "line-structure-v1"

# Work at a bounded resolution: LSD cost scales with pixels, and a wall edge is a wall edge at
# 900px. Segment coordinates are returned in the ANALYSED frame together with that frame's size,
# so the converter's normalisation is consistent and no caller has to rescale.
MAX_SIDE = 900

# A segment shorter than this fraction of the image diagonal is texture, not structure. Set low
# enough to keep window mullions, high enough to drop LSD's speckle on noisy surfaces.
MIN_SEGMENT_FRAC = 0.03


def is_available() -> bool:
    try:
        import cv2
        return hasattr(cv2, "createLineSegmentDetector") or hasattr(cv2, "HoughLinesP")
    except Exception:
        return False


def _gray_bounded(image) -> Tuple[Any, float, int, int]:
    """PIL image → bounded grayscale ndarray. Returns (gray, scale, width, height)."""
    import cv2
    import numpy as np
    rgb = image.convert("RGB")
    w, h = rgb.size
    scale = min(1.0, float(MAX_SIDE) / max(w, h))
    if scale < 1.0:
        rgb = rgb.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    arr = np.array(rgb)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return gray, scale, gray.shape[1], gray.shape[0]


def detect_segments(image, *, min_segment_frac: float = MIN_SEGMENT_FRAC
                    ) -> Optional[Dict[str, Any]]:
    """Detect line segments. Returns a reading, or None if detection could not run.

    ``{"segments": [(x0,y0,x1,y1), …], "width", "height", "total_length", "count",
       "diagonal", "adapter"}`` — all coordinates in the analysed frame.

    An image with genuinely no lines returns a reading with an EMPTY segment list, not None.
    None means "could not look"; empty means "looked, found none". The producer must be able
    to tell those apart, because only one of them is a fact about the picture."""
    if not is_available():
        return None
    try:
        import cv2
        import numpy as np
        gray, _scale, w, h = _gray_bounded(image)
        diagonal = math.hypot(w, h)
        min_len = max(4.0, diagonal * float(min_segment_frac))

        raw: List[Tuple[float, float, float, float]] = []
        adapter = ADAPTER_LSD
        used = None
        if hasattr(cv2, "createLineSegmentDetector"):
            try:
                lsd = cv2.createLineSegmentDetector()
                found = lsd.detect(gray)[0]
                used = found
            except Exception:
                used = None
        if used is not None:
            for row in used:
                x0, y0, x1, y1 = (float(v) for v in np.asarray(row).reshape(-1)[:4])
                raw.append((x0, y0, x1, y1))
        else:
            # Declared fallback. Canny thresholds are the compromise this module exists to
            # avoid, so they are only ever reached when LSD is unavailable.
            adapter = ADAPTER_HOUGH
            edges = cv2.Canny(gray, 60, 180)
            found = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=60,
                                    minLineLength=max(10, int(min_len)), maxLineGap=8)
            if found is not None:
                for row in found:
                    x0, y0, x1, y1 = (float(v) for v in np.asarray(row).reshape(-1)[:4])
                    raw.append((x0, y0, x1, y1))

        segments = [s for s in raw if math.hypot(s[2] - s[0], s[3] - s[1]) >= min_len]
        total = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in segments)
        return {"segments": segments, "width": w, "height": h,
                "total_length": round(total, 3), "count": len(segments),
                "diagonal": round(diagonal, 3), "adapter": adapter}
    except Exception as e:  # pragma: no cover — depends on the cv2 build
        print(f"⚠️ line-segment detection failed (non-fatal, producer reports unavailable): {e}")
        return None
