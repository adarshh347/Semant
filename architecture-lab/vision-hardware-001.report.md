# VISION-HARDWARE-001 — hardware/runtime confirmation

**Date:** 2026-07-19 · **Mode:** read-only probe. Gate artifact for `VISION-BUILD-001`
("do not start implementation until … VISION-HARDWARE-001 confirms actual
VRAM/driver/CUDA/PyTorch compatibility"). Probed on the current dev box.

## Confirmed facts

| Item | Value | Source |
|---|---|---|
| GPU | NVIDIA GeForce GTX 1650, **4096 MiB (4 GB)** VRAM, compute cap **7.5** (Turing) | `nvidia-smi` |
| GPU driver | **595.58.03** (current; supports CUDA 12/13 runtimes) | `nvidia-smi` |
| CUDA toolkit (nvcc) | **not installed** | `nvcc` absent |
| **PyTorch build** | **`2.13.0+cpu`** — `cuda_available = False`, `compiled_cuda = None` | `torch` |
| torchvision | `0.28.0+cpu` (CPU build) | `torchvision` |
| Python | 3.12.3 (venv) | `python -V` |
| System RAM | **7.1 GiB total, ~1.0 GiB available** (6.1 used) | `free -h` |
| Swap | 7.6 GiB total, **4.6 GiB already in use** | `free -h` |
| Disk free | 320 GB free of 468 GB (ample for checkpoints) | `df -h` |
| CPU | AMD Ryzen 5 5600H, 12 logical cores | (audit) |

## Compatibility verdict

**The GPU is present but currently UNUSABLE by the application.** PyTorch is a CPU-only
wheel — it will not touch the GTX 1650 no matter what code requests it. So today every
model (YOLO, SegFormer, FashionCLIP) runs on CPU, and any GPU-only path (SAM2 kernels)
cannot run at all.

Two hard constraints even if a CUDA build is installed:

1. **4 GB VRAM is very tight.** Per the initiative's own `infra-hardware-plan.md`: SAM2
   *tiny* is borderline (image-only), SAM2 base+/large and Fashionpedia-at-throughput
   do **not** fit. EfficientSAM-Ti / MobileSAM are the only refiners with a real chance
   locally.
2. **RAM is the tighter bottleneck than VRAM.** Only ~1 GiB is free and the box is
   **already swapping 4.6 GiB**. Loading a multi-hundred-MB model (SegFormer ~110 MB,
   CLIP ~600 MB, a SAM variant) into this headroom will swap hard or OOM. This must be
   addressed (close other load / a lazy-unload ModelManager / more RAM) before any
   local model benchmarking is meaningful.

## To make the GPU usable (not done here — decision required)

- Install a **CUDA PyTorch build** matching the driver (e.g. `cu124`) into a **pinned**
  env — the code audit flagged the env is entirely unpinned, so this must be deliberate,
  not a loose `pip install`.
- Even then, plan for **serverless GPU** for SAM2/Fashionpedia/video, exactly as
  `pre-build-decisions.md` (B1) already settled — 4 GB + 1 GB free RAM cannot serve the
  heavy roster locally.

## What this gates in VISION-BUILD-001

- **Increment A (canonical mask evidence)** — CPU-only (schema + geometry service +
  rendering + synthetic-mask tests). **Not blocked** by any of the above.
- **Increments B–F** — all require either a usable GPU (CUDA torch) or the serverless
  path, plus a defined model roster and orchestrator (see status note below). **Blocked**
  until the CUDA-vs-serverless decision and the missing prerequisite specs land.
