"""Rehearsal research adapters (R1) — allowlisted, read-only, side-effect-free.

RESEARCH-ONLY. This module is imported by ``scripts/rehearsal_run.py`` and the
R1 test suite. It deliberately imports NOTHING from ``backend`` and touches no
Mongo/production code path.

R1 ADAPTER SCOPE (hard rule, still in force for R1 runs):
    The ONLY allowlisted adapter is a trivial LOCAL, PURE one —
    ``local_file_digest`` — which proves the capture path records provenance
    without invoking any sensory model. SAM / YOLO / SegFormer / DINOv2 /
    FashionCLIP / the semantic provider / any LLM are OUT OF SCOPE for R1 and
    are NOT registered here. Requesting a non-allowlisted adapter raises.

R2 EXTENSION (deliberate, bounded, per-rehearsal approval only):
    R2 breadth rehearsals may need ONE sensory reading. ``groq_vlm_probe`` is
    therefore registered as a BOUNDED vision-language adapter. It is not a
    licence to batch: one call per invocation, no retry, CAPTURE-only in
    practice (REPLAY reads frozen observations and must make zero calls).
    It still imports nothing from ``backend`` — the key comes from the
    environment — so the research substrate stays uncoupled from production.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict


class AdapterNotAllowed(Exception):
    """Raised when a non-allowlisted adapter name is requested."""


def local_file_digest(path: str) -> Dict[str, Any]:
    """Pure, local, model-free adapter: digest a file on disk.

    Returns provenance-bearing output with no network, GPU, or model call.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
        "path": os.path.abspath(path),
    }


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VLM_MODEL = "qwen/qwen3.6-27b"


def groq_vlm_probe(image_path: str = None, prompt: str = "", *,
                   image_paths: list = None,
                   model: str = GROQ_VLM_MODEL,
                   max_tokens: int = 700,
                   timeout_s: int = 90) -> Dict[str, Any]:
    """R2 BOUNDED sensory adapter — exactly ONE vision-language call.

    Reads LOCAL fixture images (never a production URL), asks one question, and
    returns the RAW answer plus full provenance. It deliberately does **not**
    parse or coerce the model's output: the rehearsal records what the model
    actually said, including malformed output, as an observation.

    Accepts either a single ``image_path`` or an ordered ``image_paths`` list for
    multi-image comparisons. The images are sent as SEPARATE content parts in the
    given order — never composited into one sheet — because compositing would
    introduce exactly the reproduction artifact that run 002 was about, and would
    make ``image_order`` a fiction. Every image's sha256 is recorded in order.

    ``reasoning_effort="none"`` is mandatory for this model — qwen3.6 is a
    reasoning model and will otherwise spend the whole ``max_tokens`` budget on
    an unclosed ``<think>`` block (``finish_reason: "length"``) and return
    nothing usable.

    No retry, no loop: the caller is responsible for throttling (Groq's
    on-demand tier caps at 8000 tokens/minute and image calls are token-heavy).
    """
    key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set in the environment")

    paths = list(image_paths) if image_paths else ([image_path] if image_path else [])
    if not paths:
        raise ValueError("groq_vlm_probe needs image_path or image_paths")

    parts = [{"type": "text", "text": prompt}]
    images = []
    for p in paths:
        with open(p, "rb") as fh:
            raw = fh.read()
        mime = mimetypes.guess_type(p)[0] or "image/jpeg"
        parts.append({"type": "image_url", "image_url": {
            "url": f"data:{mime};base64,{base64.b64encode(raw).decode()}"}})
        images.append({"path": os.path.abspath(p),
                       "sha256": hashlib.sha256(raw).hexdigest(),
                       "bytes": len(raw)})

    body = {
        "model": model,
        "reasoning_effort": "none",
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": parts}],
    }
    # The User-Agent is load-bearing, not cosmetic: Groq sits behind Cloudflare,
    # which rejects urllib's default `Python-urllib/3.x` agent with HTTP 403 and
    # body "error code: 1010" (a client-fingerprint ban) BEFORE the key is ever
    # checked — a 403 here means the agent, not a bad key or a dead model.
    req = urllib.request.Request(
        GROQ_ENDPOINT, method="POST", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": "semant-rehearsal/1.0"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # Surface the provider's own message. Groq's failures are otherwise
        # indistinguishable from each other at the status-code level:
        #   403 + "error code: 1010" -> Cloudflare agent ban (not a bad key)
        #   413                      -> the request's TOTAL token requirement
        #                               exceeds the per-minute limit outright,
        #                               so it can never be served (shrink it)
        #   429                      -> temporarily over TPM (wait and retry)
        body = ""
        try:
            body = e.read().decode()[:500]
        except Exception:
            pass
        raise RuntimeError(f"groq_vlm_probe HTTP {e.code}: {body}") from e
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    choice = (payload.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content")) or ""
    return {
        "provider": "groq",
        "model": payload.get("model") or model,
        "reasoning_effort": "none",
        "latency_ms": latency_ms,
        "finish_reason": choice.get("finish_reason"),
        "usage": payload.get("usage"),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        # Ordered — position is meaningful when a prompt says "IMAGE 1 / IMAGE 2".
        "images": images,
        "image_count": len(images),
        "image_path": images[0]["path"],
        "image_sha256": images[0]["sha256"],
        "answer_text": text,
        "answer_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "emitted_think_block": "<think>" in text,
    }


# The ALLOWLIST is the single source of truth for what CAPTURE mode may invoke.
# `local_file_digest` is the R1 pure adapter; `groq_vlm_probe` is the bounded R2
# sensory extension (see module docstring) — one call, no retry, frozen on capture.
ALLOWLIST: Dict[str, Callable[..., Any]] = {
    "local_file_digest": local_file_digest,
    "groq_vlm_probe": groq_vlm_probe,
}

# Static metadata describing each adapter's request boundary and model/device.
# R1's adapter is model-free and runs on the local CPU / filesystem; R2's sensory
# adapter crosses a remote boundary and must declare it.
ADAPTER_META: Dict[str, Dict[str, Any]] = {
    "local_file_digest": {
        "request_boundary": "local_filesystem_read",
        "model": None,
        "version": "r1.local-pure.1",
        "device": "cpu",
    },
    "groq_vlm_probe": {
        "request_boundary": "remote_http_groq_openai_v1",
        "model": GROQ_VLM_MODEL,
        "version": "r2.groq-vlm.1",
        "device": "remote",
    },
}


def get_adapter(name: str) -> Callable[..., Any]:
    """Return an allowlisted adapter callable or raise ``AdapterNotAllowed``."""
    if name not in ALLOWLIST:
        raise AdapterNotAllowed(
            f"adapter {name!r} is not allowlisted for R1; "
            f"allowed: {sorted(ALLOWLIST)}"
        )
    return ALLOWLIST[name]


def adapter_meta(name: str) -> Dict[str, Any]:
    """Return static provenance metadata for an allowlisted adapter."""
    if name not in ALLOWLIST:
        raise AdapterNotAllowed(
            f"adapter {name!r} is not allowlisted for R1; "
            f"allowed: {sorted(ALLOWLIST)}"
        )
    return dict(ADAPTER_META.get(name, {}))
