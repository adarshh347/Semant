"""Necessary sampling/signal checks, never object recognition or colour-outcome selection."""
from hashlib import sha256
import math
import numpy as np

SCALES = (1, 4)
MINIMUM_PAIRS = 16
MINIMUM_GLOBAL_RGB_RMS = 1.0


def inspect_mask(rgb, mask):
    rgb = np.asarray(rgb)
    mask = np.asarray(mask)
    if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError('uint8_working_RGB_required')
    h, w, _ = rgb.shape
    if min(h, w) < 16 or h*w > 1048576:
        raise ValueError('working_dimensions_outside_bounds')
    if mask.dtype != np.bool_ or mask.shape != (h, w):
        raise ValueError('exact_working_boolean_mask_required')
    step = math.ceil(max(h, w)/512)
    field = rgb[::step, ::step]
    native = mask[::step, ::step]
    # Global signal only, not a cross-boundary contrast filter. Translation-invariant.
    values = field.astype(np.float64)
    rms = float(np.sqrt(np.mean((values-values.mean(axis=(0, 1)))**2)))
    edges = []
    counts = {}
    for axis in (0, 1):
        a = native if axis == 1 else native.T
        ys, xs = np.where(a[:, :-1] != a[:, 1:])
        valid = []
        for y, x in zip(ys.tolist(), xs.tolist()):
            # Interface between x and x+1; fixed symmetric half-cell offsets.
            # For d, cross separation 2d-1, within separation 2d on each side.
            # This is geometry only; no claim these equal the prior straight-line metric.
            left = x - 3*max(SCALES) + 1
            right = x + 3*max(SCALES)
            if left < 0 or right >= a.shape[1]:
                continue
            # Entire support stays in its respective class, not just endpoints.
            if np.all(a[y, left:x+1] == a[y, x]) and np.all(a[y, x+1:right+1] == a[y, x+1]):
                valid.append([y, x])
        counts[str(axis)] = {'all_transitions': len(xs), 'supported_transitions': len(valid)}
        edges.extend([[axis, y, x] if axis == 1 else [axis, x, y] for y, x in valid])
    reasons = []
    if not native.any(): reasons.append('empty_native_mask')
    if native.all(): reasons.append('full_native_mask')
    if len(edges) < MINIMUM_PAIRS: reasons.append('insufficient_two_sided_geometry')
    if rms < MINIMUM_GLOBAL_RGB_RMS: reasons.append('low_global_signal_nondiagnostic')
    return {'status': 'sampling_candidate' if not reasons else 'not_ready', 'reasons': reasons,
            'working_rgb_sha256': sha256(rgb.tobytes()).hexdigest(),
            'working_mask_sha256': sha256(mask.astype(np.uint8).tobytes()).hexdigest(),
            'native_mask_sha256': sha256(native.astype(np.uint8).tobytes()).hexdigest(),
            'stride': step, 'native_shape': list(native.shape), 'sampling': '[::stride, ::stride]; no interpolation',
            'global_rgb_rms_code_values': rms, 'minimum_global_rgb_rms': MINIMUM_GLOBAL_RGB_RMS,
            'minimum_pairs': MINIMUM_PAIRS, 'scales': list(SCALES), 'counts_by_axis': counts,
            'supported_interfaces_axis_y_x': edges, 'geometry_pass': len(edges) >= MINIMUM_PAIRS,
            'boundary_meaning_verified': False, 'semantic_evidence_eligible': False,
            'colour_outcome_computed': False, 'winner_selected': False}
