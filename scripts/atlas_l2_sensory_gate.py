"""
ATLAS L2 — the live sensory gate.

Every adapter the Atlas benchmark leans on, run FOR REAL against real photographs, and reported
with the four numbers that decide whether a lane can trust it:

    availability · device · latency · GPU memory (delta, peak)

...plus the two things a bare "it ran" hides:

    THE SECOND MEASURE. Every sensory producer in this codebase pairs its output with a measure
    that says whether the output means anything — `decomposition_adequate` for SAM2, coherence for
    the axis, spread for the depth and shading grids, cross-image separation for DINOv2. Synthetic
    fixtures make those measures look fine by construction (a flat grid on a flat test image is
    CORRECT), so they are only ever tested here, on photographs of real objects in real light.

    RESIDENCY. One heavy model at a time, on a 3.6 GiB card. Each probe records the card before,
    after inference, and after `model_residency.release_all()`. A probe that ends above baseline
    is a leak, and it is named as one.

Read-only: no database, no post ids, no writes. The photographs are the ones already committed at
`research/rehearsals/fixtures/` — real objects, in-repo, ours. Nothing here touches a curator post.

    PYTHONPATH=. venv/bin/python scripts/atlas_l2_sensory_gate.py
    PYTHONPATH=. venv/bin/python scripts/atlas_l2_sensory_gate.py --only depth,dinov2 --json out.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(REPO, "research", "rehearsals", "fixtures")

# The photographs. Chosen for what each one asks of a model, not for looking nice:
#   PIETA        — a carved figure in situ: parts to decompose, real depth, real modelled light
#   REVETMENT    — a tiled architectural surface: the axis case, dense real lines
#   NATARAJA     — bronze against shadow: the hard intrinsic case (dark, high contrast)
#   ROSE_WINDOW  — unrelated to all of the above: the contrastive "not this one" for DINOv2
#   LARGE        — 1366×2048, the biggest thing in the corpus: residency under a real size
PIETA = os.path.join(FIXTURES, "002F-pieta-single-object", "pieta-in-situ.jpg")
REVETMENT = os.path.join(FIXTURES, "005-surface-becoming-structure", "turquoise-tile-revetment.jpg")
NATARAJA = os.path.join(FIXTURES, "011-strained-premise-probe", "img1-nataraja-shadow.jpg")
ROSE_WINDOW = os.path.join(FIXTURES, "011-strained-premise-probe", "img2-rose-window.jpg")
LARGE = os.path.join(FIXTURES, "004-gesture-and-address", "negative-dark-structure.jpg")

# What is TRUE of each plate, written down by someone who opened it. This is the part of a sensory
# gate that cannot be derived — a depth field can only be checked against a fact about the picture,
# and the fact has to come from outside the model being checked.
#
# `centre_near` is the sign `_centre_vs_border` must return. The two entries deliberately DISAGREE;
# see that function for why that is the whole point.
PLATES: Dict[str, Dict[str, Any]] = {
    PIETA: {"centre_near": False,
            "why": "the sculpture is recessed in a niche — the chapel's near architecture, side "
                   "altars and foreground floor are all at the frame edges, so the centre is far"},
    LARGE: {"centre_near": True,
            "why": "the tower's mass fills the frame and the corners are empty night sky, so the "
                   "centre is near"},
}

MIB = 1024.0 * 1024.0


# ── the card ────────────────────────────────────────────────────────────────

def _torch():
    try:
        import torch
        return torch
    except Exception:
        return None


def gpu_mib() -> Optional[float]:
    """Allocated VRAM in MiB, or None off-CUDA. `memory_allocated`, not `nvidia-smi`: the caching
    allocator holds reserved blocks long after a model is gone, so reserved memory would report a
    leak on every clean unload. Allocated is what actually still has a tensor in it."""
    torch = _torch()
    if torch is None or not torch.cuda.is_available():
        return None
    return round(torch.cuda.memory_allocated() / MIB, 1)


def gpu_peak_mib() -> Optional[float]:
    torch = _torch()
    if torch is None or not torch.cuda.is_available():
        return None
    return round(torch.cuda.max_memory_allocated() / MIB, 1)


def reset_peak() -> None:
    torch = _torch()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def release_all() -> List[str]:
    """The real residency discipline, not a local imitation — this is what the orchestrate path
    calls between GPU steps, so a leak found here is a leak the Director would also hit.

    `release_all` is a COROUTINE, and calling it without awaiting frees nothing while raising
    nothing: python emits a RuntimeWarning to stderr and the card stays full. This gate found
    that the expensive way, reporting three fictional leaks; every real caller in the codebase
    (`real_actuators`, `routers/posts`) does await it. Hence `asyncio.run` here, and hence the
    returned list is printed — "released nothing" is the shape a silent miss takes."""
    import asyncio
    from backend.services import model_residency
    released = asyncio.run(model_residency.release_all())
    gc.collect()
    return released


# ── one probe's answer ──────────────────────────────────────────────────────

@dataclass
class Probe:
    name: str
    capability: str
    available: bool = False
    ran: bool = False
    device: str = "—"
    latency_ms: Optional[float] = None          # WARM — the second cycle, what step ten costs
    latency_cold_ms: Optional[float] = None     # first cycle, dominated by loading weights
    mem_before: Optional[float] = None
    mem_peak: Optional[float] = None
    mem_after_unload: Optional[float] = None
    mem_after_second: Optional[float] = None
    released: List[str] = field(default_factory=list)
    image: str = ""
    measure: str = ""            # what the SECOND measure said, in words
    measure_ok: Optional[bool] = None
    detail: str = ""
    error: str = ""

    @property
    def leaked(self) -> Optional[float]:
        """GROWTH across two identical load→run→unload cycles, not distance from zero.

        Distance from zero is the wrong measure and this gate reported it first, calling SAM2 an
        8.1 MiB leak. That 8.1 MiB is a one-time CUDA context/workspace floor: identical after 1,
        2, 3 and 4 loads, with no live CUDA tensor left in `gc.get_objects()`. A floor costs the
        card once; a leak costs it once PER STEP, and only the second cycle can tell them apart."""
        if self.mem_after_unload is None or self.mem_after_second is None:
            return None
        return round(self.mem_after_second - self.mem_after_unload, 1)

    @property
    def status(self) -> str:
        if self.error:
            return "ERROR"
        if not self.available:
            return "UNAVAILABLE"
        if not self.ran:
            return "REFUSED"
        if self.measure_ok is False:
            return "RAN·WEAK"
        return "OK"


def _cycle(p: Probe, body: Callable[[Probe], None]) -> Optional[float]:
    """One load → run → unload, returning the card's allocated MiB once it settles."""
    try:
        body(p)
    except Exception as e:
        p.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()
    try:
        p.released = release_all()
    except Exception as e:                                  # an unload that fails is itself news
        p.detail = (p.detail + f" | release_all raised {type(e).__name__}").strip(" |")
    return gpu_mib()


def run_probe(p: Probe, body: Callable[[Probe], None]) -> Probe:
    """Run one adapter end to end, TWICE: measure the card, run it, unload, measure — then do the
    whole thing again on a warm process. The second cycle is what makes the residency claim mean
    anything (see `Probe.leaked`), and it is also the only place the WARM latency shows up; the
    first is dominated by weight loading and says nothing about what a plan's tenth step costs.

    A probe that throws is recorded as an ERROR row and the sweep continues — the point of a gate
    is the whole table, and one broken adapter should not cost the report on the other five."""
    reset_peak()
    p.mem_before = gpu_mib()
    t0 = time.perf_counter()
    p.mem_after_unload = _cycle(p, body)
    if p.latency_ms is None and p.ran:                      # a body that did not time itself
        p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    p.latency_cold_ms = p.latency_ms
    p.mem_peak = gpu_peak_mib()

    if p.error or not p.ran:                                # nothing to repeat
        return p

    p.latency_ms = None                                     # the body refills it, warm this time
    p.mem_after_second = _cycle(p, body)
    if p.latency_ms is None:
        p.latency_ms = p.latency_cold_ms                    # cold == warm is honest for the
    return p                                                # remote probe, which loads nothing


def _pil(path: str):
    from PIL import Image
    return Image.open(path).convert("RGB")


def _bytes(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def _centre_vs_border(values: List[float], grid: int) -> float:
    """Mean of the middle half of the frame, minus the mean of its outer ring.

    A spatial claim, not a statistical one — the only kind that can catch a field that is lively
    but INVERTED, which a spread check is perfectly happy with. Depth-Anything emits INVERSE depth
    (larger = nearer), so a positive result means the centre is nearer.

    There is no universal law here, and the first draft of this gate asserted one: "the subject is
    in the middle, so the middle is nearer". That is FALSE of half this corpus. `pieta-in-situ` is
    a sculpture recessed in a niche with the chapel's near architecture at the frame edges — its
    centre is genuinely FARTHER, and the model was right to say -0.38 while this check called it a
    defect. So the expected direction is declared PER PHOTOGRAPH, by someone who looked at it (see
    `PLATES`), and the two plates are chosen to disagree: one centre-near, one centre-far. A model
    or convention that flipped the sign globally would have to break both, which it cannot do
    while still agreeing with either."""
    if not values or grid <= 2:
        return 0.0
    lo, hi = grid // 4, grid - grid // 4
    mid = [values[y * grid + x] for y in range(lo, hi) for x in range(lo, hi)]
    ring = [values[y * grid + x] for y in range(grid) for x in range(grid)
            if not (lo <= y < hi and lo <= x < hi)]
    if not mid or not ring:
        return 0.0
    return round(sum(mid) / len(mid) - sum(ring) / len(ring), 4)


def _spread(values: List[float]) -> float:
    """Range of a coarse field, as the fraction of its own scale that it actually uses.

    The failure this catches is a model that loads, runs, and returns a CONSTANT — which every
    downstream converter will happily band into a confident-looking flat field. On a photograph of
    a real object under real light, a near-zero spread means the reading is empty, not uniform."""
    if not values:
        return 0.0
    lo, hi = min(values), max(values)
    scale = max(abs(lo), abs(hi), 1e-9)
    return round((hi - lo) / scale, 4)


# ── the probes ──────────────────────────────────────────────────────────────

def probe_sam2(p: Probe) -> None:
    from backend.services import sam2_auto_service as svc
    p.available = svc.is_available()
    if not p.available:
        p.detail = "weights or library absent"
        return
    p.device = svc._device()
    p.image = os.path.relpath(PIETA, REPO)
    t0 = time.perf_counter()
    regions = svc.generate_masks(_bytes(PIETA))
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    if regions is None:
        p.detail = "generate_masks returned None (load failed)"
        return
    p.ran = True
    # THE SECOND MEASURE — the gate that replaced `if not anchors`. A single whole-frame blob is
    # the art failure mode, and it passes any "did it return something" check.
    p.measure_ok = svc.decomposition_adequate(regions)
    largest = max((svc._norm_area(r) for r in regions), default=0.0)
    p.measure = (f"decomposition_adequate={p.measure_ok} "
                 f"({len(regions)} parts, largest {largest:.1%} of frame)")
    p.detail = f"{len(regions)} regions"


def probe_depth(p: Probe) -> None:
    from backend.services import depth_service as svc
    p.available = svc.is_available()
    if not p.available:
        p.detail = "Depth-Anything unavailable"
        return
    p.device = svc._device()
    p.image = os.path.relpath(PIETA, REPO)
    t0 = time.perf_counter()
    out = svc.estimate(_pil(PIETA))
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    if not out:
        p.detail = "estimate returned None"
        return
    p.ran = True
    grid = out["depth"]
    spread = _spread(grid)
    relief = _centre_vs_border(grid, out["grid"])
    plate = PLATES[PIETA]
    # Two measures, and both must hold: the field has to VARY, and it has to vary the way this
    # particular photograph actually is.
    agrees = (relief > 0.0) == plate["centre_near"]
    p.measure_ok = spread > 0.05 and agrees
    p.measure = (f"spread={spread} over {out['grid']}×{out['grid']} "
                 f"(near {max(grid):.1f} / far {min(grid):.1f}) · centre−border={relief:+.4f}, "
                 f"expected centre {'near' if plate['centre_near'] else 'FAR'} — {plate['why']}")


def probe_intrinsic(p: Probe) -> None:
    from backend.services import intrinsic_service as svc
    p.available = svc.is_available()
    if not p.available:
        p.detail = "intrinsic package or checkpoints absent"
        return
    p.device = svc._device()
    # A NOTE ON THIS ONE'S LATENCY, because it will look broken and is not.
    #
    # Intrinsic is the most expensive adapter to RE-load, and residency discipline re-loads it
    # after every step: `load_models("paper_weights")` reads ~864 MiB of checkpoints back and
    # goes through `torch.hub` to do it. Warm cycles measured 4.2s / 7.7s / 12.2s here — an order
    # of magnitude worse than any other adapter's reload — and one run of this gate recorded a
    # SEVENTEEN MINUTE warm cycle at 0% CPU and 0% GPU, which is torch.hub blocking on the
    # network. Both checkpoints were already cached on disk; the hub loader validates anyway.
    #
    # So: intrinsic's reload cost is real, is paid per step, and has an unbounded network tail.
    # That is a property of running one model at a time on a 3.6 GiB card, not a defect — but a
    # plan that interleaves intrinsic with other GPU steps pays it every time, and anyone reading
    # a slow orchestrate run should suspect this before suspecting inference.
    #
    # The HARD case on purpose: bronze in shadow. A shading model that only works on evenly lit
    # subjects would pass on the pietà and be useless for the light readings the Atlas wants.
    p.image = os.path.relpath(NATARAJA, REPO)
    t0 = time.perf_counter()
    out = svc.estimate(_pil(NATARAJA))
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    if not out:
        p.detail = "estimate returned None (no gry_shd — an honest refusal)"
        return
    p.ran = True
    grid = out["shading"]
    spread = _spread(grid)
    p.measure_ok = spread > 0.05
    p.measure = f"shading spread={spread} over {out['grid']}×{out['grid']} (lit {max(grid):.3f} / dark {min(grid):.3f})"


def probe_dinov2(p: Probe) -> None:
    from backend.services import dinov2_service as svc
    p.available = svc.is_available()
    if not p.available:
        p.detail = "DINOv2 unavailable"
        return
    p.device = svc._device()
    p.image = f"{os.path.relpath(NATARAJA, REPO)} vs {os.path.relpath(ROSE_WINDOW, REPO)}"
    enc = svc.get_encoder()
    t0 = time.perf_counter()
    a = enc.encode_image(_pil(NATARAJA))["cls"]
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    b = enc.encode_image(_pil(ROSE_WINDOW))["cls"]
    a2 = enc.encode_image(_pil(NATARAJA))["cls"]
    p.ran = True

    def cos(u, v):
        return round(sum(x * y for x, y in zip(u, v)), 4)

    self_sim, cross_sim = cos(a, a2), cos(a, b)
    # THE SECOND MEASURE, contrastive. An encoder that has silently collapsed returns vectors that
    # are all ~1.0 apart from each other; "it returned 384 floats" cannot tell you that happened.
    p.measure_ok = self_sim > 0.99 and cross_sim < self_sim - 0.05
    p.measure = f"self={self_sim} cross={cross_sim} (separation {round(self_sim - cross_sim, 4)})"


def probe_architectural_axis(p: Probe) -> None:
    """LSD line segments → the `architectural_axis` trace mark. CPU, cv2, no weights."""
    from backend.services import line_structure_service as lines
    from backend.services import suggestion_service as ss
    p.available = lines.is_available()
    if not p.available:
        p.detail = "cv2 LSD factory absent (the 4.1–4.7 patent gap)"
        return
    p.device = "cpu"
    p.image = os.path.relpath(REVETMENT, REPO)
    t0 = time.perf_counter()
    reading = lines.detect_segments(_pil(REVETMENT))
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    if reading is None:
        p.detail = "detect_segments returned None — could not look"
        return
    # "looked, found none" is a fact about the picture; the producer must see the difference.
    count = int(reading.get("count") or 0)
    sug = ss.suggestion_from_architectural_axis(reading, run_id="l2_gate", region_id=None)
    if not sug:
        p.ran = True
        p.measure_ok = False
        p.measure = (f"{count} segments via {reading.get('adapter')}, "
                     f"but the producer REFUSED (lines without an axis)")
        return
    p.ran = True
    # THE SECOND MEASURE — `axial_coherence`, the confidence the mark actually carries. Note the
    # inversion documented at mask_geometry:972: for an AXIS, high coherence is the signal.
    conf = float(sug.get("confidence") or 0.0)
    p.measure_ok = conf > 0.0
    p.measure = (f"axial_coherence={conf:.4f} coverage={sug.get('coverage'):.4f} "
                 f"over {count} segments ({reading.get('adapter')})")
    p.detail = sug.get("label", "")


def probe_semantic(p: Probe) -> None:
    """`compare_views`' naming step. Not a vision model — the LLM that names a relation between
    two marks on two images. Probed here because the benchmark's comparative percept dies without
    it, and its availability is a config question (`GROQ_API_KEY`), not a weights question."""
    from backend.services.director import real_actuators as ra
    p.available = ra._semantic_available()
    p.device = "remote"
    if not p.available:
        p.detail = "no GROQ_API_KEY configured"
        return
    p.image = f"{os.path.relpath(NATARAJA, REPO)} vs {os.path.relpath(ROSE_WINDOW, REPO)}"
    p.ran = True
    p.measure_ok = None
    p.measure = "provider configured (naming is exercised through the orchestrate path, not here)"
    p.detail = "semantic_provider up"


def probe_large_image(p: Probe) -> None:
    """The same adapter against the biggest photograph in the corpus.

    The other probes read ~680px images, which is what a thumbnail costs, not what a plate costs.
    A model whose peak scales with input will show it here and nowhere else, and peak is the
    number that decides whether two steps can ever overlap on a 3.6 GiB card."""
    from backend.services import depth_service as svc
    p.available = svc.is_available()
    if not p.available:
        p.detail = "depth unavailable — nothing to size-test"
        return
    p.device = svc._device()
    im = _pil(LARGE)
    p.image = f"{os.path.relpath(LARGE, REPO)} ({im.size[0]}×{im.size[1]})"
    t0 = time.perf_counter()
    out = svc.estimate(im)
    p.latency_ms = round((time.perf_counter() - t0) * 1000.0, 1)
    if not out:
        p.detail = "estimate returned None on the large plate"
        return
    p.ran = True
    spread = _spread(out["depth"])
    relief = _centre_vs_border(out["depth"], out["grid"])
    plate = PLATES[LARGE]
    agrees = (relief > 0.0) == plate["centre_near"]
    p.measure_ok = spread > 0.05 and agrees
    p.measure = (f"{im.size[0]}×{im.size[1]} · spread={spread} · centre−border={relief:+.4f}, "
                 f"expected centre {'NEAR' if plate['centre_near'] else 'far'} — {plate['why']} "
                 f"· peak {gpu_peak_mib()} MiB in flight")


PROBES: List[Any] = [
    ("sam2_auto", "segmenter", probe_sam2),
    ("depth_anything", "depth", probe_depth),
    ("intrinsic", "intrinsic", probe_intrinsic),
    ("dinov2", "dinov2", probe_dinov2),
    ("architectural_axis", "—(cpu)", probe_architectural_axis),
    ("semantic/compare_views", "semantic_provider", probe_semantic),
    ("depth@2048px", "depth", probe_large_image),
]


# ── the report ──────────────────────────────────────────────────────────────

def table(rows: List[Probe]) -> str:
    head = (f"{'adapter':24} {'status':11} {'device':7} {'cold':>10} {'warm':>9} "
            f"{'peak MiB':>9} {'growth':>8}")
    out = [head, "─" * len(head)]
    for r in rows:
        cold = "—" if r.latency_cold_ms is None else f"{r.latency_cold_ms:,.0f}ms"
        warm = "—" if r.latency_ms is None else f"{r.latency_ms:,.0f}ms"
        peak = "—" if r.mem_peak is None else f"{r.mem_peak:,.1f}"
        grow = "—" if r.leaked is None else f"{r.leaked:+,.1f}"
        out.append(f"{r.name:24} {r.status:11} {r.device:7} {cold:>10} {warm:>9} "
                   f"{peak:>9} {grow:>8}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlas L2 — live sensory gate")
    ap.add_argument("--only", default="", help="comma-separated adapter names to run")
    ap.add_argument("--json", default="", help="write the full record here")
    ap.add_argument("--device", default="", help="force a device (cpu/cuda/mps) via "
                                                 "SEMANT_TORCH_DEVICE — proves the fallback")
    args = ap.parse_args()

    if args.device:
        # Set BEFORE any service imports torch — `torch_device.resolve` reads the env per call,
        # but a service that already loaded a model would keep the one it has.
        os.environ["SEMANT_TORCH_DEVICE"] = args.device

    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    missing = [p for p in (PIETA, REVETMENT, NATARAJA, ROSE_WINDOW, LARGE) if not os.path.exists(p)]
    if missing:
        print("✗ fixture photographs missing — this gate reads only in-repo images:")
        for m in missing:
            print(f"    {os.path.relpath(m, REPO)}")
        return 2

    torch = _torch()
    cuda = bool(torch and torch.cuda.is_available())
    print(f"torch {getattr(torch, '__version__', 'absent')} · cuda={cuda}"
          + (f" · {torch.cuda.get_device_name(0)}"
             f" · {torch.cuda.get_device_properties(0).total_memory / MIB:,.0f} MiB" if cuda else ""))
    try:
        from backend.services.torch_device import resolve as resolve_device
        print(f"shared device resolver → {resolve_device()}")
    except Exception:
        print("shared device resolver → ABSENT (each service picks its own)")
    print(f"baseline allocated: {gpu_mib()} MiB\n")

    rows: List[Probe] = []
    for name, capability, body in PROBES:
        if wanted and name not in wanted:
            continue
        print(f"→ {name} …", flush=True)
        rows.append(run_probe(Probe(name=name, capability=capability), body))

    print("\n" + table(rows))
    print("\nthe second measure, per adapter:")
    for r in rows:
        mark = {True: "✓", False: "✗", None: "·"}[r.measure_ok]
        line = r.measure or r.detail or r.error or "—"
        print(f"  {mark} {r.name:24} {line}")
        if r.released:
            print(f"      released: {', '.join(r.released)}")
        if r.error:
            print(f"      error: {r.error}")

    leaks = [r for r in rows if (r.leaked or 0) > 1.0]
    if leaks:
        print("\n✗ RESIDENCY: these GREW between two identical cycles — " + ", ".join(
            f"{r.name} +{r.leaked} MiB/cycle" for r in leaks))
    else:
        floor = max((r.mem_after_second or 0.0) for r in rows) if rows else 0.0
        print(f"\n✓ residency: no growth across two cycles of any adapter "
              f"(steady floor {floor} MiB — CUDA context, not a model)")

    if args.json:
        payload = {"cuda": cuda, "baseline_mib": gpu_mib(),
                   "probes": [{**asdict(r), "status": r.status, "leaked": r.leaked} for r in rows]}
        with open(args.json, "w") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\nwrote {args.json}")

    broken = [r for r in rows if r.status in ("ERROR",)]
    return 1 if (broken or leaks) else 0


if __name__ == "__main__":
    sys.exit(main())
