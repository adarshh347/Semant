"""Pure, bounded readers of saved coherence-weighted axial tangent fields."""
from __future__ import annotations

import json
import math

from backend.services.perception_lab.field_data import FieldError

REVISION = "orientation-consumers-v2"


def _check(grid):
    meta = grid.metadata
    try:
        convention = json.loads(meta["value_convention"])
    except (ValueError, TypeError, KeyError) as exc:
        raise FieldError("saved field has no orientation convention") from exc
    if (meta.get("kind") != "axial_orientation_2d" or grid.shape[2] != 2
            or meta.get("frame") != "image_pixel_xy_topleft"
            or meta.get("units") != "dimensionless_coherence_weighted_double_angle"
            or convention.get("algorithm") != "structure-tensor-tangent-v1"
            or convention.get("form") != "tangent"
            or meta.get("channels") != [
                {"name": name, "quantity": "coherence_weighted_axial_tangent", "unit": "1"}
                for name in ("coherence_cos_2theta", "coherence_sin_2theta")]):
        raise FieldError("expected a compatible saved coherence-weighted axial tangent field")
    return grid.shape[:2]


def _points(grid, points, maximum):
    h, w = _check(grid)
    if not isinstance(points, (list, tuple)) or not 1 <= len(points) <= maximum:
        raise FieldError(f"supply 1–{maximum} explicit field-pixel points")
    output = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or any(type(v) is not int for v in point)
                or not 0 <= point[0] < w or not 0 <= point[1] < h):
            raise FieldError("point must be an integer x,y inside the saved field")
        output.append(list(point))
    return output


def _number(value, name, low, high, integer=False):
    if (type(value) not in ((int,) if integer else (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise FieldError(f"{name} must be {'an integer' if integer else 'finite'} in {low}–{high}")
    return value


def axial_summary(grid, points, parameters):
    cells = _points(grid, points, 4096)
    if set(parameters) - {"bins", "weighting"}:
        raise FieldError("unsupported axial summary parameter")
    bins = _number(parameters.get("bins", 12), "bins", 6, 36, integer=True)
    weighting = parameters.get("weighting", "coherence")
    if weighting not in ("coherence", "uniform"):
        raise FieldError("weighting must be coherence or uniform")
    width = grid.shape[1]
    cells = [list(cell) for cell in sorted({tuple(cell) for cell in cells}, key=lambda p: (p[1], p[0]))]
    total = sc = ss = coherence_total = 0.
    count, histogram = 0, [0.] * bins
    for x, y in cells:
        i = y*width+x
        if not grid.valid[i]:
            continue
        c, s = grid.values[2*i:2*i+2]
        coherence = math.hypot(c, s)
        if not 0 < coherence <= 1.00001:
            raise FieldError("saved axial magnitude is not valid coherence")
        angle = (math.atan2(s, c)/2) % math.pi
        weight = coherence if weighting == "coherence" else 1.
        histogram[min(bins-1, int(angle/math.pi*bins))] += weight
        sc += c/coherence*weight; ss += s/coherence*weight; total += weight
        coherence_total += coherence; count += 1
    resultant = min(1., math.hypot(sc, ss)/total) if total else None
    return {"schema": REVISION, "field_hash": grid.measurement_hash, "support": cells,
            "sample_count": len(cells), "valid_count": count, "invalid_count": len(cells)-count,
            "weighting": weighting, "bins": bins, "histogram_weights": histogram,
            "bin_edges_degrees": [180*i/bins for i in range(bins+1)],
            "mean_axis_degrees": (math.degrees(math.atan2(ss, sc)/2) % 180)
                if resultant is not None and resultant > 1e-8 else None,
            "axial_resultant_length": resultant,
            "mean_local_coherence": coherence_total/count if count else None,
            "meaning": "doubled-angle distribution over unique valid cells; not semantic confidence"}


def _axis_at(grid, position, minimum):
    x, y = position
    h, w, _ = grid.shape
    if x < 0 or y < 0 or x > w-1 or y > h-1:
        return None, "field_boundary"
    x0, y0 = math.floor(x), math.floor(y)
    x1, y1 = min(w-1, x0+1), min(h-1, y0+1)
    c = s = 0.
    for xx, yy, weight in ((x0, y0, (1-(x-x0))*(1-(y-y0))),
                            (x1, y0, (x-x0)*(1-(y-y0))),
                            (x0, y1, (1-(x-x0))*(y-y0)),
                            (x1, y1, (x-x0)*(y-y0))):
        if weight <= 0:
            continue
        index = yy*w+xx
        if not grid.valid[index]:
            return None, "invalid_support"
        a, b = grid.values[2*index:2*index+2]
        magnitude = math.hypot(a, b)
        if not 0 < magnitude <= 1.00001:
            raise FieldError("saved axial magnitude is not valid coherence")
        c += weight*a; s += weight*b
    if math.hypot(c, s) < minimum:
        return None, "low_coherence"
    angle = .5*math.atan2(s, c)
    return (math.cos(angle), math.sin(angle)), None


def _crosses_invalid_support(grid, start, end):
    """Exact segment/open-bilinear-support intersection, including grazing paths.

    A sample (i,j) contributes iff |x-i| < 1 and |y-j| < 1.
    Its zero-weight rectangle boundary does not contribute. With <=1px steps,
    at most nine sample rectangles need checking; no substep sampling bound
    can guarantee finding a short corner crossing.
    """
    height, width, _ = grid.shape
    columns = range(max(0, math.floor(min(start[0], end[0]))),
                    min(width-1, math.ceil(max(start[0], end[0])))+1)
    rows = range(max(0, math.floor(min(start[1], end[1]))),
                 min(height-1, math.ceil(max(start[1], end[1])))+1)
    for y in rows:
        for x in columns:
            if grid.valid[y*width+x]:
                continue
            enter, leave = 0., 1.
            for coordinate, a, b in zip((x, y), start, end):
                if a == b:
                    if not coordinate-1 < a < coordinate+1:
                        enter, leave = 1., 0.
                        break
                else:
                    first = (coordinate-1-a)/(b-a)
                    last = (coordinate+1-a)/(b-a)
                    enter = max(enter, min(first, last))
                    leave = min(leave, max(first, last))
            if enter < leave:
                return True
    return False


def trace(grid, points, parameters):
    seeds = _points(grid, points, 16)
    allowed = {"step_size", "max_steps", "max_length", "min_coherence", "max_turn_degrees", "directions"}
    if set(parameters) - allowed:
        raise FieldError("unsupported trace parameter")
    settings = dict(step_size=.5, max_steps=512, max_length=128., min_coherence=.15,
                    max_turn_degrees=60., directions="both")
    settings.update(parameters)
    for name, low, high in (("step_size", .1, 1), ("max_length", .1, 1024),
                            ("min_coherence", .01, 1), ("max_turn_degrees", 1, 90)):
        _number(settings[name], name, low, high)
    _number(settings["max_steps"], "max_steps", 1, 2048, integer=True)
    if settings["directions"] not in ("both", "positive", "negative"):
        raise FieldError("directions must be both, positive or negative")
    signs = (1, -1) if settings["directions"] == "both" else (
        1 if settings["directions"] == "positive" else -1,)
    paths = []
    minimum, step = settings["min_coherence"], settings["step_size"]
    turn_limit = math.cos(math.radians(settings["max_turn_degrees"]))
    for seed in seeds:
        for sign in signs:
            path, length, previous = [seed[:]], 0., None
            stop = "max_steps"
            for _ in range(settings["max_steps"]):
                axis, failure = _axis_at(grid, path[-1], minimum)
                if failure:
                    stop = failure; break
                if previous is None:
                    axis = tuple(sign*v for v in axis)
                else:
                    dot = sum(a*b for a, b in zip(axis, previous))
                    if dot < 0:
                        axis = tuple(-v for v in axis); dot = -dot
                    if dot < turn_limit:
                        stop = "max_turn"; break
                remaining = settings["max_length"]-length
                if remaining <= 1e-9:
                    stop = "max_length"; break
                distance = min(step, remaining)
                candidate = [path[-1][i]+distance*axis[i] for i in (0, 1)]
                if _crosses_invalid_support(grid, path[-1], candidate):
                    stop = "invalid_support"; break
                # Coherence is checked at bounded substeps. Invalid support is
                # checked analytically above, including arbitrarily short grazes.
                for fraction in (.25, .5, .75, 1):
                    position = [path[-1][i]+fraction*distance*axis[i] for i in (0, 1)]
                    _, failure = _axis_at(grid, position, minimum)
                    if failure:
                        break
                if failure:
                    stop = failure; break
                path.append(candidate); length += distance; previous = axis
                if length >= settings["max_length"]-1e-9:
                    stop = "max_length"; break
            paths.append({"seed": seed, "direction_sign": sign, "points": path,
                          "steps": len(path)-1, "length_field_pixels": length,
                          "stop_reason": stop, "stop_point": path[-1]})
    return {"schema": REVISION, "field_hash": grid.measurement_hash, "seeds": seeds,
            "parameters": settings, "paths": paths, "coordinate_frame": "field_pixel_xy_topleft",
            "source_to_field": grid.metadata["source_to_field"],
            "integration": "Euler; bilinear coherence-weighted doubled-angle interpolation; sign continuity",
            "support_check": "exact segment intersection with open bilinear support of invalid samples",
            "coherence_check": "at current point and quarter-step checkpoints; not a continuous minimum guarantee",
            "direction_convention": "initial positive uses theta=atan2(sin2,cos2)/2; sign has no observed meaning",
            "meaning": "constructed route through the saved axial estimate, not observed geometry or motion"}


CONSUMERS = {"orientation_flow.trace": trace, "orientation_flow.axial_summary": axial_summary}
