"""Typed form controls from the canonical contract. Invalid values refuse, never coerce."""
import math
from backend.services.perception_lab.contracts import lab_contract

def declarations(form):
    return lab_contract().get("form_parameters", {}).get(form, [])

def resolve(form, supplied):
    effective = dict(supplied)
    ignored = []
    for d in declarations(form):
        name = d["name"]
        if name not in effective and "initial" in d:
            effective[name] = d["initial"]
        if name not in effective:
            if d.get("required_when") and all(effective.get(k) == v for k, v in d["required_when"].items()):
                raise ValueError(f"{name} is required when {d['required_when']}")
            continue
        value = effective[name]
        kind = d["type"]
        valid = True
        if kind == "boolean": valid = type(value) is bool
        elif kind == "enum": valid = value in d["enum"]
        elif kind == "integer_pair":
            valid = isinstance(value, (list, tuple)) and len(value) == 2 and all(
                type(v) is int and d["minimum"] <= v <= d["maximum"] for v in value)
        elif kind == "number":
            valid = type(value) in (int, float) and math.isfinite(value) and d["exclusive_minimum"] < value <= d["maximum"]
        if not valid: raise ValueError(f"invalid {name}: {value!r}; {d['description']}")
    if form == "extent.density_field" and effective["kernel"] == "none" and "bandwidth" in effective:
        ignored.append(("bandwidth", "kernel=none; bandwidth was not applied"))
        del effective["bandwidth"]
    return effective, ignored
