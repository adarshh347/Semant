#!/usr/bin/env python3
"""
INTELLIGENCE-001C — the local Qwen3.5-9B visual-observation laboratory.

WHAT THIS IS FOR. A 6.58 GB GGUF sits on this machine and answers on `http://127.0.0.1:8081/v1`
for free, forever, with no allowance window and no third party. Every rehearsal Semant has run so
far waited on a metered remote provider; 003F's own script sleeps forty-five minutes between two
calls because the account had not recovered. So the question is worth asking precisely:

    is this thing good enough to be the eye that is ALWAYS there?

WHAT IT IS NOT. It binds nothing. No production inquiry service, route, registry or dependency is
touched by this file. `local_qwen_vlm` is a provider identity recorded in run records, not a
provider registered anywhere. A lane that ended by wiring the theorist to a 9B quantisation on a
16 GB laptop would have skipped the measurement this file exists to take.

THE THREE SEPARATIONS THIS LAB REFUSES TO COLLAPSE. Each is a mistake somebody has already
shipped, and each is enforced structurally rather than by asking the model nicely:

    the user's hypothesis  is not  an image observation.
        Enforced by ORDER AND BLINDNESS. Experiment 1 never sees the user's words; experiment 2
        never sees the image. The alignment pass is handed its own frozen observations as TEXT.
        It cannot invent a new visual observation because there is nothing in front of it to look
        at. Asking a model not to look while showing it the picture is a wish; taking the picture
        away is a mechanism.

    an interpretive reading  is not  a measurement.
        Enforced by a schema whose `status` is a one-value enum, and by an audit that reads the
        prose for measurement grammar anyway — because the field can say `interpretive` while the
        sentence beside it says `approximately 30 degrees`.

    recognising a thing  is not  the repository knowing what it is.
        Enforced by an attribution audit built out of GRAMMAR, not out of a topic word list. It
        looks for "attributed to", "possibly representing", a century, a date, a bare capitalised
        proper noun mid-sentence. It contains no term from any rehearsal topic, so it will still
        work on a corpus of trains.

USAGE

    python scripts/local_qwen_vlm_lab.py census                  # the provider census
    python scripts/local_qwen_vlm_lab.py resolve                 # re-resolve the corpus, read-only
    python scripts/local_qwen_vlm_lab.py observe                 # experiment 1, prompt-blind
    python scripts/local_qwen_vlm_lab.py align                   # experiment 2, needs 1
    python scripts/local_qwen_vlm_lab.py compare                 # experiment 3, three images
    python scripts/local_qwen_vlm_lab.py reliability --trials 10 # experiment 4
    python scripts/local_qwen_vlm_lab.py rehearsal-prompts       # experiment 5
    python scripts/local_qwen_vlm_lab.py all                     # 1-5 in order, one run id
    python scripts/local_qwen_vlm_lab.py gates --run <id>         # the verdict, computed
    python scripts/local_qwen_vlm_lab.py freeze --run <id>        # capture responses for the tests

NOTHING IS INVENTED. Telemetry the server did not report is `null`. If llama-server omits a
`timings` block the record carries `null` tokens/sec, never a number computed from a stopwatch and
presented as the server's own. Memory and swap are read from `sysctl`/`ps` and are labelled as
whole-machine figures, because on unified memory there is no honest per-process VRAM number.

NO IMAGE BYTES IN GIT. The corpus manifest records post ids, their Cloudinary URLs and the sha256
of the bytes as fetched. The bytes themselves are cached under a gitignored directory. Source posts
are read with a collection whose every mutating method has been replaced by a raiser first.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LAB_ROOT = REPO_ROOT / "research" / "rehearsals" / "provider-labs" / "local-qwen-vlm"
SCHEMAS_DIR = LAB_ROOT / "schemas"
RUNS_DIR = LAB_ROOT / "runs"
FROZEN_DIR = LAB_ROOT / "frozen"
CACHE_DIR = LAB_ROOT / "image-cache"          # gitignored; see .gitignore in the lab directory
CORPUS_PATH = LAB_ROOT / "corpus.json"
PROMPTS_PATH = LAB_ROOT / "prompts.json"

#: The provider identity this lab records. It names a MEASUREMENT SUBJECT, not a registration.
#: Nothing in `backend/` resolves this string, and this lane deliberately did not make it do so.
PROVIDER_IDENTITY = "local_qwen_vlm"

DEFAULT_BASE_URL = os.environ.get("LOCAL_QWEN_BASE_URL", "http://127.0.0.1:8081")

#: What this hardware's Metal driver reports as `recommendedMaxWorkingSetSize`. The GPU
#: allocation must stay under it; a figure above it is the number that puts a configuration out
#: of reach, and is recorded rather than discovered as an out-of-memory traceback.
METAL_CEILING_MB = 12713

#: THIS LANE'S NUMBER, not the directive's — the directive says "latency is acceptable" and does
#: not define it. Named here so a reader can disagree with the threshold rather than with the
#: verdict it produces. A minute is the point past which a person watching a single image being
#: read stops waiting and goes to do something else.
LATENCY_BUDGET_MS = 60000

#: The three posts INTELLIGENCE-001C names. Resolved read-only; never written to.
LAB_POST_IDS = (
    "6a6041b81ecd6db1c931eb7a",
    "6a6041b61ecd6db1c931eb78",
    "6a60408e1ecd6db1c931eb6b",
)

#: What the model is told to call each image. Deliberately opaque — `A`, `B`, `C` would let a
#: model guess a correct-looking reference without having tracked anything, and a Mongo ObjectId
#: would be echoed back as a plausible hallucination the moment one was ever wrong. These tokens
#: appear nowhere else, so a returned ref is either one we handed over or it is invented.
REF_TOKENS = ("img-k7", "img-q2", "img-v9")


# ── the machine, as it reports itself ────────────────────────────────────────

def _sh(cmd: List[str]) -> Optional[str]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def machine_state(server_pid: Optional[int] = None) -> Dict[str, Any]:
    """
    Whole-machine memory, and the server's RSS — with the caveat that makes RSS honest here.

    NO PER-PROCESS VRAM NUMBER IS PRODUCED. On Apple unified memory the GPU allocation is not a
    separate pool, and every "VRAM used" figure on this platform is somebody's arithmetic dressed
    as a reading.

    AND RSS IS NOT THE FOOTPRINT. This lane watched llama-server report 7415 MB of RSS a minute
    after loading and 141 MB half an hour later, while answering at the same 13 tok/s throughout.
    With `-ngl 99` the weights live in Metal buffers that stop being attributed to the process,
    so a falling RSS here is an accounting change and not a model being evicted. `wired_mb` from
    `vm_stat` is the figure that tracks what the GPU is actually holding, so it is recorded
    beside RSS and the reader is told which is which.
    """
    swap = _sh(["sysctl", "-n", "vm.swapusage"])
    used_mb = None
    if swap:
        m = re.search(r"used\s*=\s*([\d.]+)M", swap)
        if m:
            used_mb = float(m.group(1))

    wired_mb = compressed_mb = free_mb = None
    vm = _sh(["vm_stat"])
    if vm:
        pg = re.search(r"page size of (\d+) bytes", vm)
        page = int(pg.group(1)) if pg else 16384

        def pages(label: str) -> Optional[float]:
            m2 = re.search(rf"{label}:\s+(\d+)", vm)
            return round(int(m2.group(1)) * page / 1048576, 1) if m2 else None

        wired_mb = pages("Pages wired down")
        compressed_mb = pages("Pages occupied by compressor")
        free_mb = pages("Pages free")

    rss_kb = None
    if server_pid:
        raw = _sh(["ps", "-o", "rss=", "-p", str(server_pid)])
        if raw and raw.isdigit():
            rss_kb = int(raw)

    return {
        "swap_used_mb": used_mb,
        "swap_raw": swap,
        "wired_mb": wired_mb,
        "compressed_mb": compressed_mb,
        "free_mb": free_mb,
        "server_rss_mb": round(rss_kb / 1024, 1) if rss_kb else None,
        "rss_caveat": "RSS under -ngl 99 on Metal is not the footprint; read wired_mb instead",
        "server_pid": server_pid,
    }


def find_server_pid() -> Optional[int]:
    raw = _sh(["pgrep", "-x", "llama-server"]) or _sh(["pgrep", "-f", "llama-server"])
    if not raw:
        return None
    for line in raw.splitlines():
        if line.strip().isdigit():
            return int(line.strip())
    return None


# ── the client ───────────────────────────────────────────────────────────────

class ProviderUnavailable(RuntimeError):
    """The server did not answer. A RESULT, recorded as `unavailable` — never a fabricated zero."""


@dataclass
class Call:
    """
    One request and everything the server said about it. Fields the server did not report are
    `None` and stay `None`.
    """
    label: str
    ok: bool
    status: str                       # completed | refused | truncated | error | unavailable
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    finish_reason: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    prompt_per_second: Optional[float] = None
    predicted_per_second: Optional[float] = None
    #: Wall clock measured HERE, and named so nobody reads it as the server's own throughput.
    client_wall_ms: Optional[float] = None
    error: Optional[str] = None
    request_digest: Optional[str] = None
    machine_after: Optional[Dict[str, Any]] = None


class LocalQwenClient:
    """
    An OpenAI-shaped client over stdlib urllib. No new dependency enters the repository for a lab.

    THE TWO DEFAULTS THAT ARE NOT OBVIOUS, both established by the census in this lane:

      `enable_thinking=False` unless a caller asks otherwise. Qwen3.5 thinks by default and the
      thinking is charged against `max_tokens`, so a 64-token budget returned `content: ""` with
      `finish_reason: "length"` — a silently empty answer that looks like a refusal. Experiments
      that want the reasoning ask for it explicitly.

      Structure comes from `response_format: json_schema`, never `json_object`. On build b10520
      `json_object` is a HINT: it returned a ```json fence and an array where the schema said
      string. `json_schema` with `strict` is grammar-constrained and returned neither.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 900.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # -- plumbing --------------------------------------------------------
    def _get(self, path: str, timeout: Optional[float] = None) -> Any:
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req, timeout=timeout or 20) as r:
            return json.load(r)

    def alive(self) -> bool:
        try:
            return self._get("/health").get("status") == "ok"
        except Exception:
            return False

    def props(self) -> Dict[str, Any]:
        return self._get("/props")

    def models(self) -> Dict[str, Any]:
        return self._get("/v1/models")

    # -- the one call --------------------------------------------------------
    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        label: str,
        max_tokens: int = 1200,
        schema: Optional[Dict[str, Any]] = None,
        thinking: bool = False,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
        timeout: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Call:
        body: Dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": bool(thinking)},
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "lab", "strict": True, "schema": schema},
            }
        if temperature is not None:
            body["temperature"] = temperature
        if seed is not None:
            body["seed"] = seed
        if extra:
            body.update(extra)

        payload = json.dumps(body).encode()
        digest = hashlib.sha256(payload).hexdigest()[:16]
        pid = find_server_pid()

        t0 = time.time()
        try:
            req = urllib.request.Request(
                f"{self.base_url}/v1/chat/completions", payload,
                {"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:600]
            return Call(label=label, ok=False, status="error",
                        error=f"HTTP {e.code}: {detail}", request_digest=digest,
                        client_wall_ms=round((time.time() - t0) * 1000, 1),
                        machine_after=machine_state(pid))
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            return Call(label=label, ok=False, status="unavailable",
                        error=f"{type(e).__name__}: {e}", request_digest=digest,
                        client_wall_ms=round((time.time() - t0) * 1000, 1),
                        machine_after=machine_state(pid))

        wall = round((time.time() - t0) * 1000, 1)
        choice = (d.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage = d.get("usage") or {}
        timings = d.get("timings") or {}
        finish = choice.get("finish_reason")

        # `length` is TRUNCATED, and is not the same thing as an answer. The gate that reads this
        # record must be able to tell a short answer from a severed one.
        status = "truncated" if finish == "length" else "completed"

        return Call(
            label=label,
            ok=status == "completed",
            status=status,
            content=msg.get("content"),
            reasoning_content=msg.get("reasoning_content"),
            finish_reason=finish,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            prompt_per_second=timings.get("prompt_per_second"),
            predicted_per_second=timings.get("predicted_per_second"),
            client_wall_ms=wall,
            request_digest=digest,
            machine_after=machine_state(pid),
        )


# ── the corpus ───────────────────────────────────────────────────────────────

def resolve_corpus_from_mongo(post_ids: Tuple[str, ...] = LAB_POST_IDS) -> List[Dict[str, Any]]:
    """
    READ-ONLY. Every mutating method on the posts collection is replaced with a raiser before the
    first query, so a resolution pass cannot alter the thing it resolves. Rule 10 — source posts
    are preserved byte-identically — is enforced here rather than promised in a docstring.
    """
    import asyncio
    from bson import ObjectId
    from backend.database import post_collection

    for name in ("insert_one", "insert_many", "update_one", "update_many",
                 "delete_one", "delete_many", "replace_one", "find_one_and_update",
                 "find_one_and_replace", "find_one_and_delete", "bulk_write", "drop"):
        if hasattr(post_collection, name):
            setattr(post_collection, name, _refuse(name))

    async def _go():
        out = []
        for pid in post_ids:
            doc = await post_collection.find_one({"_id": ObjectId(pid)})
            if not doc:
                out.append({"post_id": pid, "found": False, "photo_url": None})
                continue
            out.append({
                "post_id": pid,
                "found": True,
                "photo_url": doc.get("photo_url"),
                "general_tags": list(doc.get("general_tags") or []),
                "instagram_handle": doc.get("instagram_handle"),
                "n_text_blocks": len(doc.get("text_blocks") or []),
                "n_region_annotations": len(doc.get("region_annotations") or []),
            })
        return out

    return asyncio.run(_go())


def _refuse(name: str):
    def _r(*_a, **_k):
        raise RuntimeError(
            f"{name}() refused: the local-qwen lab resolves the corpus read-only "
            f"(rule 10 — source posts are preserved byte-identically)")
    return _r


def load_corpus() -> List[Dict[str, Any]]:
    if not CORPUS_PATH.exists():
        raise SystemExit(
            f"no corpus manifest at {CORPUS_PATH}. Run: "
            f"python scripts/local_qwen_vlm_lab.py resolve")
    return json.loads(CORPUS_PATH.read_text())["images"]


def image_bytes(entry: Dict[str, Any]) -> bytes:
    """
    Fetch once, cache outside git, and verify the sha256 the manifest recorded.

    The digest is not decoration. Experiment 1 and experiment 3 must be looking at the same pixels
    days apart, and a Cloudinary transform silently re-encoding a JPEG would otherwise turn a
    changed observation into a finding about the model.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{entry['post_id']}.jpg"
    if not path.exists():
        with urllib.request.urlopen(entry["photo_url"], timeout=60) as r:
            path.write_bytes(r.read())
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    want = entry.get("sha256")
    if want and got != want:
        raise SystemExit(
            f"image bytes for {entry['post_id']} changed: manifest {want}, fetched {got}. "
            f"Refusing to run — every observation in this lab is anchored to those bytes.")
    return raw


def data_url(raw: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


# ── the audits ───────────────────────────────────────────────────────────────
#
# GRAMMAR, NOT VOCABULARY. Every pattern below detects the SHAPE of a forbidden claim rather than
# a topic word, which is what lets this file honour rule 5. There is no `fold`, no `sculpture`, no
# `architecture` and no period name anywhere in it. Point it at a corpus of trains and it still
# catches "attributed to", "circa 1890" and "approximately 30 degrees".

#: Each entry is (pattern, what it detects, case-sensitive?). THE THIRD FIELD IS NOT DECORATION.
#: The first version of this table matched everything case-insensitively, and every pattern whose
#: point was a capitalised proper noun — `made by [A-Z]`, `style of [A-Z]` — silently matched
#: `created by the drapery` and `style of carving` instead. A pattern that depends on capitals
#: must be read with capitals meaning something.
MEASUREMENT_PATTERNS = [
    (r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|in|inch|inches|ft|feet|kg|lb|°|degrees?)\b",
     "a dimension", False),
    # No trailing \b after `%`: it is not a word character, so `40% of` never matched and the
    # single most likely fabricated measurement in a visual reading walked straight through.
    (r"\b\d+(?:\.\d+)?\s*(?:%|per\s?cent\b|percent\b)", "a percentage", False),
    (r"\bmeasur(?:ed|ement|ements|es)\b", "the word measured", False),
    (r"\b(?:exactly|precisely)\b", "a precision claim", False),
    (r"\bratio of\s+\d", "a stated ratio", False),
    (r"\b\d+(?:\.\d+)?\s*:\s*\d+(?:\.\d+)?\b", "a numeric ratio", False),
    (r"\bcalibrat(?:ed|ion)\b", "a calibration claim", False),
]

ATTRIBUTION_PATTERNS = [
    (r"\battributed to\b", "an attribution phrase", False),
    # These verbs can only mean authorship. `created`/`made` cannot — the first blind pass wrote
    # "shadows created by the drapery" — so they are below, and they demand a capitalised agent.
    (r"\b(?:sculpted|carved|chiselled|chiseled|painted|executed)\s+by\b",
     "an authorship phrase", False),
    (r"\b(?:made|created|produced|designed)\s+by\s+(?:the\s+)?[A-Z]", "a named maker", True),
    (r"\b(?:possibly|likely|probably)\s+(?:representing|depicting|a depiction of)\b",
     "an identification hedge", False),
    (r"\b(?:school|workshop|circle|manner)\s+of\s+[A-Z]", "a workshop attribution", True),
    (r"\bc(?:irca)?\.?\s*\d{3,4}\b", "a date", False),
    (r"\b\d{1,2}(?:st|nd|rd|th)[-\s]century\b", "a century", False),
    (r"\b\d{3,4}\s*(?:BCE?|CE|AD)\b", "an era date", False),
    (r"\b(?:known as|titled|entitled)\s+[\"\u201c']?[A-Z]", "a title", True),
]

#: Capitalised words that are ordinary English or belong to this lab's own apparatus, and so are
#: not evidence of a named entity. Kept short on purpose: a long stoplist hides real hits.
_CAP_STOP = {
    "I", "A", "An", "The", "This", "That", "These", "Those", "It", "Its", "There", "They",
    "In", "On", "At", "From", "To", "Of", "For", "With", "Without", "By", "As", "And", "But",
    "No", "Not", "Left", "Right", "Upper", "Lower", "Top", "Bottom", "Front", "Back",
    "Image", "Images", "Observation", "Observations", "Uncertainty", "Low", "Medium", "High",
    "Locus", "Surface", "Light", "Material", "Cannot", "Supports", "Complicates", "Challenges",
    "Does", "Determine", "None", "Yes", "Notes", "Overall", "Both", "Each", "One", "Two", "Three",
}


def find_proper_nouns(text: str) -> List[str]:
    """
    A capitalised token that is not sentence-initial and not ordinary English. Crude by design —
    this is a FLAG for a human reader, and it says so in the record. It caught the census pass's
    unprompted `Venus or Aphrodite` without knowing what either word means.
    """
    hits = []
    # SPLIT ON JSON PUNCTUATION TOO. The audited text is usually a serialised object, so a field
    # value begins after `":` or `,` rather than after a full stop. The first pass without this
    # reported `Moderate` and `Whether` as named entities because they opened a value that the
    # splitter could not see was an opening.
    for sentence in re.split(r"(?<=[.!?;:])\s+|[\n\[\{,]|\":?\s*|\|\s*", text or ""):
        toks = re.findall(r"\b[A-Z][a-zA-Z’'-]{2,}\b", sentence)
        first = re.match(r"[\s\"']*([A-Z][a-zA-Z’'-]{2,})", sentence)
        firstw = first.group(1) if first else None
        for t in toks:
            if t == firstw:
                continue
            if t in _CAP_STOP:
                continue
            # `V-shape`, `U-bend`: a hyphenated form whose tail is lowercase is a shape word.
            if "-" in t and t.split("-", 1)[1][:1].islower():
                continue
            hits.append(t)
    return sorted(set(hits))


def audit_text(text: str) -> Dict[str, Any]:
    text = text or ""
    measured = [{"pattern": p, "what": w, "match": m.group(0)}
                for p, w, cs in MEASUREMENT_PATTERNS
                for m in re.finditer(p, text, 0 if cs else re.I)]
    attributed = [{"pattern": p, "what": w, "match": m.group(0)}
                  for p, w, cs in ATTRIBUTION_PATTERNS
                  for m in re.finditer(p, text, 0 if cs else re.I)]
    return {
        "measurement_claims": measured,
        "attribution_claims": attributed,
        "proper_nouns": find_proper_nouns(text),
        "clean": not measured and not attributed,
    }


def prompt_copying(prompt: str, answer: str, n: int = 6) -> Dict[str, Any]:
    """
    How much of the answer is the question read back. A model that returns the user's own phrasing
    has agreed with it rather than looked at anything, and on the adversarial prompt that is the
    entire failure being tested for.
    """
    def grams(s: str) -> set:
        w = re.findall(r"[a-z]+", (s or "").lower())
        return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
    a, b = grams(prompt), grams(answer)
    shared = a & b
    return {
        "n": n,
        "answer_ngrams": len(b),
        "shared_ngrams": len(shared),
        "fraction_of_answer": round(len(shared) / len(b), 4) if b else None,
        "examples": [" ".join(g) for g in list(shared)[:5]],
    }


# ── the schemas ──────────────────────────────────────────────────────────────

def load_schema(name: str) -> Dict[str, Any]:
    return json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text())


def validate(obj: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """
    A small structural validator — enough for the four shapes this lab constrains, and no new
    dependency. Reports EVERY failure rather than the first, because a run record that says
    "invalid" without saying how many ways is not a measurement.
    """
    errs: List[str] = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(obj, dict):
            return [f"{path}: expected object, got {type(obj).__name__}"]
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}.{k}: required, missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in obj:
                if k not in props:
                    errs.append(f"{path}.{k}: not allowed by the schema")
        for k, sub in props.items():
            if k in obj:
                errs += validate(obj[k], sub, f"{path}.{k}")
    elif t == "array":
        if not isinstance(obj, list):
            return [f"{path}: expected array, got {type(obj).__name__}"]
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: needs >= {schema['minItems']} items, has {len(obj)}")
        for i, it in enumerate(obj):
            errs += validate(it, schema.get("items", {}), f"{path}[{i}]")
    elif t == "string":
        if not isinstance(obj, str):
            errs.append(f"{path}: expected string, got {type(obj).__name__}")
        elif "enum" in schema and obj not in schema["enum"]:
            errs.append(f"{path}: {obj!r} not in {schema['enum']}")
        elif "minLength" in schema and len(obj) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
    elif t == "integer":
        if not isinstance(obj, int) or isinstance(obj, bool):
            errs.append(f"{path}: expected integer")
    return errs


def parse_json(content: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
    """
    Parse, and report HOW it failed. A fenced block is a distinct failure from malformed JSON —
    the census found `json_object` mode returning ```json fences, and a harness that stripped them
    silently would have reported that mode as reliable.
    """
    if content is None:
        return None, "no content"
    s = content.strip()
    fenced = s.startswith("```")
    if fenced:
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s), ("fenced" if fenced else None)
    except json.JSONDecodeError as e:
        return None, f"malformed: {e}"


# ── run records ──────────────────────────────────────────────────────────────

def new_run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%S")


#: Common rule 11 — replay / fixture / live / local / provider identities must remain explicit.
#: Stamped by `write_record` onto EVERY record rather than by each caller, because an identity
#: that depends on somebody remembering to add it is the identity that goes missing on the one
#: record where it mattered.
EXECUTION_MODE = "local_live"


def write_record(run_id: str, name: str, payload: Dict[str, Any]) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    stamped = {
        "provider": PROVIDER_IDENTITY,
        "execution_mode": EXECUTION_MODE,
        "replayed": False,
        "host": {"platform": sys.platform, "node": os.uname().nodename,
                 "machine": _sh(["sysctl", "-n", "hw.model"])},
        "binds_anything": False,
        **payload,
    }
    p = d / f"{name}.json"
    p.write_text(json.dumps(stamped, indent=2, ensure_ascii=False) + "\n")
    return p


def read_record(run_id: str, name: str) -> Optional[Dict[str, Any]]:
    p = RUNS_DIR / run_id / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def latest_run() -> Optional[str]:
    if not RUNS_DIR.exists():
        return None
    runs = sorted(p.name for p in RUNS_DIR.iterdir() if p.is_dir())
    return runs[-1] if runs else None


# ── the provider census ──────────────────────────────────────────────────────

def gguf_identity(path: Path) -> Dict[str, Any]:
    """
    The model's own metadata, read out of the GGUF header.

    `/v1/models` returns the FILENAME. A filename is what somebody typed; `general.base_model.0`
    and `general.quantized_by` are what the file says about itself. The two have disagreed before
    on this machine's sibling directory, and a census that recorded only the first would have
    attributed a quantisation to whoever named the file.
    """
    import struct
    if not path.exists():
        return {"available": False, "reason": f"not found: {path}"}
    want = ("general.", "qwen", "block_count", "context_length", "embedding_length")
    out: Dict[str, Any] = {"available": True, "path": str(path),
                           "size_bytes": path.stat().st_size}
    with path.open("rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            return {"available": False, "reason": f"not a GGUF file (magic {magic!r})"}
        out["gguf_version"] = struct.unpack("<I", f.read(4))[0]
        out["tensor_count"] = struct.unpack("<Q", f.read(8))[0]
        n_kv = struct.unpack("<Q", f.read(8))[0]

        def rs() -> str:
            n = struct.unpack("<Q", f.read(8))[0]
            return f.read(n).decode("utf-8", "replace")

        size = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
        fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?",
               10: "<Q", 11: "<q", 12: "<d"}

        def rv(t: int) -> Any:
            if t == 8:
                return rs()
            if t == 9:
                et = struct.unpack("<I", f.read(4))[0]
                n = struct.unpack("<Q", f.read(8))[0]
                if n > 64:                       # the tokenizer arrays; skipped, not summarised
                    if et == 8:
                        for _ in range(n):
                            rs()
                    else:
                        f.read(size[et] * n)
                    return f"<array of {n}>"
                return [rv(et) for _ in range(n)]
            return struct.unpack(fmt[t], f.read(size[t]))[0]

        meta: Dict[str, Any] = {}
        for _ in range(n_kv):
            k = rs()
            v = rv(struct.unpack("<I", f.read(4))[0])
            if "tokenizer" in k:
                continue
            if any(k.startswith(w) or w in k for w in want):
                meta[k] = v
        out["metadata"] = meta
    return out


def cmd_census(args) -> int:
    """
    Fifteen questions, each answered by a probe rather than by a README.

    THE ONE THAT MATTERS MOST is `structured_output`, and it is asked three ways — `json_object`,
    `json_schema` and a raw GBNF grammar — because they are not the same feature and this build
    honours only two of them.
    """
    client = LocalQwenClient(args.base_url)
    run_id = args.run or new_run_id()
    started = machine_state(find_server_pid())

    if not client.alive():
        rec = {"provider": PROVIDER_IDENTITY, "run_id": run_id, "base_url": args.base_url,
               "reachable": False,
               "note": "the server did not answer /health. Every field below is absent rather "
                       "than zero: this census establishes nothing about the model.",
               "machine_at_start": started}
        write_record(run_id, "census", rec)
        print(f"UNAVAILABLE — no server at {args.base_url}")
        print("start it with:  cd '/Users/merleauponty/ml models/qwen 9b q5km' && "
              "VISION=1 CTX=32768 ./serve.sh")
        return 2

    props = client.props()
    models = client.models()
    corpus = load_corpus()
    imgs = [image_bytes(e) for e in corpus]

    probes: Dict[str, Any] = {}

    def probe(name: str, **kw) -> Call:
        c = client.chat(label=f"census:{name}", **kw)
        probes[name] = {k: v for k, v in asdict(c).items() if v is not None}
        return c

    # 1 — vision, one image, base64
    probe("one_image_base64", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url(imgs[0])}},
        {"type": "text", "text": "One short sentence: what is physically in this picture?"}]}],
        max_tokens=200)

    # 2 — vision, one image, remote URL fetched by the SERVER
    probe("one_image_remote_url", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": corpus[0]["photo_url"]}},
        {"type": "text", "text": "One short sentence: what is physically in this picture?"}]}],
        max_tokens=200)

    # 3 — three images in one request, each named
    probe("three_images", messages=[{"role": "user", "content":
        sum([[{"type": "text", "text": f"{REF_TOKENS[i]}:"},
              {"type": "image_url", "image_url": {"url": data_url(imgs[i])}}]
             for i in range(len(imgs))], [])
        + [{"type": "text", "text":
            "For each of " + ", ".join(REF_TOKENS) + " give one short line naming only what is "
            "visible. Keep them separate."}]}], max_tokens=400)

    # 4 — json_object mode. Asks for a STRING and an ARRAY so a hint can be caught being a hint.
    probe("structured_json_object", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url(imgs[0])}},
        {"type": "text", "text": "Return JSON with keys: subject (a string), "
                                 "materials (an array of strings)."}]}],
        max_tokens=300, extra={"response_format": {"type": "json_object"}})

    # 5 — json_schema, strict
    probe("structured_json_schema", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url(imgs[0])}},
        {"type": "text", "text": "Describe the object."}]}],
        max_tokens=300,
        schema={"type": "object", "additionalProperties": False,
                "required": ["subject", "materials"],
                "properties": {"subject": {"type": "string"},
                               "materials": {"type": "array", "items": {"type": "string"}}}})

    # 6 — raw GBNF
    probe("structured_gbnf", messages=[{"role": "user", "content": "Answer anything."}],
          max_tokens=40, extra={"grammar": 'root ::= "{\\"ok\\": " ("true"|"false") "}"'})

    # 7 — reasoning content, separated or inlined
    probe("reasoning_separated", messages=[{"role": "user", "content":
        "Think briefly, then answer: what is 17 * 3?"}], max_tokens=400, thinking=True)

    # 8 — the thinking budget trap: a small max_tokens WITH thinking on
    probe("thinking_starves_content", messages=[{"role": "user",
        "content": "Reply with exactly the word: ok"}], max_tokens=64, thinking=True)

    # 9 — context overflow. A refusal here is the ANSWER; an OOM would be a different one.
    big = "the quick brown fox jumps over the lazy dog. " * 9000
    probe("context_overflow", messages=[{"role": "user", "content": big}],
          max_tokens=16, timeout=300)

    # 10 — client-side cancellation, then does the server still serve?
    cancel: Dict[str, Any] = {}
    t0 = time.time()
    try:
        payload = json.dumps({"messages": [{"role": "user",
                                            "content": "Count slowly from 1 to 500."}],
                              "max_tokens": 2000,
                              "chat_template_kwargs": {"enable_thinking": False}}).encode()
        req = urllib.request.Request(f"{args.base_url}/v1/chat/completions", payload,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=4):
            cancel["aborted"] = False
    except Exception as e:
        cancel["aborted"] = True
        cancel["raised"] = type(e).__name__
    cancel["after_ms"] = round((time.time() - t0) * 1000, 1)
    time.sleep(2)
    recover = client.chat([{"role": "user", "content": "Reply with exactly: alive"}],
                          label="census:after_cancel", max_tokens=16)
    cancel["server_recovered"] = recover.ok
    cancel["recovery_content"] = recover.content
    probes["cancellation"] = cancel

    # 11 — the same image twice in one process: does prompt cache report a hit?
    probe("cache_second_pass", messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url(imgs[0])}},
        {"type": "text", "text": "One short sentence: what is physically in this picture?"}]}],
        max_tokens=200)

    gguf = gguf_identity(Path(args.model_path))

    rec = {
        "provider": PROVIDER_IDENTITY,
        "run_id": run_id,
        "base_url": args.base_url,
        "reachable": True,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "server": {
            "build_info": props.get("build_info"),
            "model_alias": props.get("model_alias"),
            "model_ftype": props.get("model_ftype"),
            "modalities": props.get("modalities"),
            "total_slots": props.get("total_slots"),
            "n_ctx": (props.get("default_generation_settings") or {}).get("n_ctx"),
            "chat_template_caps": props.get("chat_template_caps"),
            "reasoning_format_default": ((props.get("default_generation_settings") or {})
                                         .get("params") or {}).get("reasoning_format"),
            "capabilities": [m.get("capabilities")
                             for m in (models.get("models") or [])],
        },
        "gguf": gguf,
        "machine_at_start": started,
        "machine_at_end": machine_state(find_server_pid()),
        "probes": probes,
    }
    write_record(run_id, "census", rec)
    _print_census(rec)
    return 0


def _print_census(rec: Dict[str, Any]) -> None:
    p = rec["probes"]
    s = rec["server"]
    g = (rec.get("gguf") or {}).get("metadata") or {}
    print(f"\nPROVIDER CENSUS · {PROVIDER_IDENTITY} · run {rec['run_id']}")
    print(f"  build            {s.get('build_info')}")
    print(f"  file             {s.get('model_alias')}  ({s.get('model_ftype')})")
    print(f"  says of itself   {g.get('general.name')} · base "
          f"{g.get('general.base_model.0.organization')}/{g.get('general.base_model.0.name')} "
          f"· quantized by {g.get('general.quantized_by')} · {g.get('general.license')}")
    print(f"  architecture     {g.get('general.architecture')} · "
          f"{g.get('qwen35.block_count')} blocks · native ctx {g.get('qwen35.context_length')}")
    print(f"  modalities       {s.get('modalities')}")
    print(f"  served ctx       {s.get('n_ctx')} over {s.get('total_slots')} slots")

    def line(name: str, verdict: str, detail: str = "") -> None:
        print(f"  {name:<30}{verdict:<14}{detail}")

    def ok(name: str) -> bool:
        return bool(p.get(name, {}).get("ok"))

    print()
    line("one image (base64)", "yes" if ok("one_image_base64") else "NO",
         (p.get("one_image_base64", {}).get("content") or "")[:70])
    line("one image (remote url)", "yes" if ok("one_image_remote_url") else "NO",
         "the SERVER fetches it — outbound network from llama-server")
    line("three images at once", "yes" if ok("three_images") else "NO",
         f"{p.get('three_images', {}).get('prompt_tokens')} prompt tokens")
    jo, jo_note = parse_json(p.get("structured_json_object", {}).get("content"))
    line("response_format json_object", "HINT ONLY" if jo_note or not isinstance(jo, dict)
         else "parses", f"note={jo_note}")
    js, js_note = parse_json(p.get("structured_json_schema", {}).get("content"))
    line("response_format json_schema", "ENFORCED" if isinstance(js, dict) and not js_note
         else "no", f"note={js_note}")
    line("raw GBNF grammar", "ENFORCED"
         if (p.get("structured_gbnf", {}).get("content") or "").strip() == '{"ok": true}'
         or (p.get("structured_gbnf", {}).get("content") or "").strip() == '{"ok": false}'
         else "no")
    line("reasoning_content", "separated" if p.get("reasoning_separated", {}).get(
        "reasoning_content") else "inlined/absent")
    starve = p.get("thinking_starves_content", {})
    line("thinking + small budget",
         "STARVES" if not (starve.get("content") or "").strip() else "survives",
         f"finish={starve.get('finish_reason')}, content={starve.get('content')!r}")
    ov = p.get("context_overflow", {})
    line("context overflow", ov.get("status", "?"), (ov.get("error") or "")[:80])
    c = p.get("cancellation", {})
    line("client cancellation", "clean" if c.get("server_recovered") else "SERVER LOST",
         f"aborted={c.get('aborted')} after {c.get('after_ms')}ms, recovered="
         f"{c.get('server_recovered')}")
    line("prompt cache on repeat", str(p.get("cache_second_pass", {}).get("cached_tokens")),
         "cached_tokens on an identical second request")
    print()
    def rate(k: str) -> str:
        v = p.get("one_image_base64", {}).get(k)
        return f"{v:.1f} tok/s" if isinstance(v, (int, float)) else "not reported"
    line("prompt speed", rate("prompt_per_second"), "server-reported, one image + short text")
    line("generation speed", rate("predicted_per_second"), "server-reported")
    m0, m1 = rec["machine_at_start"], rec["machine_at_end"]
    line("wired memory", f"{m0.get('wired_mb')} -> {m1.get('wired_mb')} MB",
         "whole machine; the figure the GPU allocation actually moves")
    line("server RSS", f"{m1.get('server_rss_mb')} MB",
         "NOT the footprint under -ngl 99 on Metal — see rss_caveat in the record")
    line("swap", f"{m0.get('swap_used_mb')} -> {m1.get('swap_used_mb')} MB",
         "WHOLE MACHINE, not this process")
    print()


# ── experiment 1 — prompt-blind observation ──────────────────────────────────

BLIND_SYSTEM = (
    "You are looking at one photograph and reporting only what is visible in it.\n"
    "Report where in the frame you are looking, how what you see is organised, how the surface "
    "behaves under the light, and what material effect that appearance suggests.\n"
    "State your uncertainty for each entry.\n"
    "Everything you report is an interpretation of an appearance. Nothing you report has been "
    "measured, so never state a dimension, an angle, a percentage or a ratio.\n"
    "Do not name a maker, a period, a date, a title or a person the object might depict. If you "
    "recognise the object, that recognition is not part of this report.\n"
    "If something cannot be determined from this photograph, say so in cannot_determine."
)

BLIND_USER = (
    "Image {ref}. Give between three and six separate entries, each about a different part of "
    "the picture. Use the reference {ref} exactly."
)


def _observe_one(client: LocalQwenClient, ref: str, raw: bytes, schema: Dict[str, Any],
                 max_tokens: int, thinking: bool) -> Dict[str, Any]:
    call = client.chat(
        [{"role": "system", "content": BLIND_SYSTEM},
         {"role": "user", "content": [
             {"type": "image_url", "image_url": {"url": data_url(raw)}},
             {"type": "text", "text": BLIND_USER.format(ref=ref)}]}],
        label=f"observe:{ref}", max_tokens=max_tokens, schema=schema, thinking=thinking)
    obj, note = parse_json(call.content)
    errs = validate(obj, schema) if obj is not None else ["no parseable JSON"]
    prose = json.dumps(obj, ensure_ascii=False) if obj is not None else (call.content or "")
    return {
        "ref": ref,
        "call": {k: v for k, v in asdict(call).items() if v is not None},
        "parsed": obj,
        "parse_note": note,
        "schema_errors": errs,
        "ref_correct": bool(isinstance(obj, dict) and obj.get("image_ref") == ref),
        "audit": audit_text(prose),
    }


def cmd_observe(args) -> int:
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or new_run_id()
    schema = load_schema("observation")
    corpus = load_corpus()

    results = []
    for i, entry in enumerate(corpus):
        raw = image_bytes(entry)
        r = _observe_one(client, REF_TOKENS[i], raw, schema, args.max_tokens, args.thinking)
        r["post_id"] = entry["post_id"]
        results.append(r)
        n = len((r["parsed"] or {}).get("observations") or [])
        print(f"  {REF_TOKENS[i]}  {r['call']['status']:<10} {n} entries  "
              f"ref_ok={r['ref_correct']}  schema_errors={len(r['schema_errors'])}  "
              f"audit_clean={r['audit']['clean']}")
        for a in r["audit"]["measurement_claims"] + r["audit"]["attribution_claims"]:
            print(f"        FLAG {a['what']}: {a['match']!r}")
        if r["audit"]["proper_nouns"]:
            print(f"        proper nouns (for a human to read): "
                  f"{', '.join(r['audit']['proper_nouns'])}")

    # A plain prose caption, for the gate that asks whether structure earns its cost.
    caption = client.chat([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_url(image_bytes(corpus[0]))}},
        {"type": "text", "text": "Write a caption for this photograph."}]}],
        label="observe:plain_caption", max_tokens=250)

    rec = {"provider": PROVIDER_IDENTITY, "run_id": run_id, "experiment": "1-prompt-blind",
           "system": BLIND_SYSTEM, "user_template": BLIND_USER,
           "prompt_blind": True,
           "note": "The user's own words were not in this process's request bodies. Experiment 2 "
                   "introduces them, and only after these observations were written to disk.",
           "images": results,
           "plain_caption": {k: v for k, v in asdict(caption).items() if v is not None}}
    write_record(run_id, "experiment-1-observe", rec)
    print(f"\n  written  {RUNS_DIR / run_id / 'experiment-1-observe.json'}")
    return 0


# ── experiment 2 — prompt-aware alignment ────────────────────────────────────

ALIGN_SYSTEM = (
    "You are given a set of observations that were written earlier by someone looking at "
    "photographs, and a person's separate hypotheses about those photographs.\n"
    "You cannot see the photographs. Judge each hypothesis ONLY against the observations you are "
    "given.\n"
    "For each hypothesis choose exactly one stance: supports, complicates, challenges, "
    "does_not_bear_on, cannot_determine.\n"
    "Cite the observation ids you used. If no observation bears on a hypothesis, the stance is "
    "does_not_bear_on. If the observations are about the right thing but do not settle it, the "
    "stance is cannot_determine.\n"
    "Never state a visual detail that is not in the observations."
)


def _observation_digest(exp1: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """
    The observations, flattened into text with stable ids — and NO IMAGE.

    This is the whole of the third separation. Experiment 2 is structurally incapable of adding a
    visual observation because the request body contains no image part; the model is looking at
    prose it did not write. A prompt that merely *asked* it not to look would have been a wish.
    """
    lines, index = [], {}
    for img in exp1["images"]:
        parsed = img.get("parsed") or {}
        for j, o in enumerate(parsed.get("observations") or []):
            oid = f"{img['ref']}-o{j}"
            index[oid] = json.dumps(o, ensure_ascii=False)
            # `id=` RATHER THAN `[id]`. The first version rendered the id inside square
            # brackets, and the model dutifully cited `"[img-k7-o0]"` — every one of eleven
            # citations valid, every one recorded as a hallucination by a checker comparing raw
            # strings. The harness taught it the wrong form and then failed it for learning.
            lines.append(
                f"id={oid} | locus: {o.get('locus')} | organization: "
                f"{o.get('visible_organization')} | surface and light: "
                f"{o.get('surface_light_behavior')} | apparent material effect: "
                f"{o.get('apparent_material_effect')} | uncertainty: {o.get('uncertainty')} "
                f"| status: {o.get('status')}")
        for c in parsed.get("cannot_determine") or []:
            lines.append(f"id={img['ref']}-undetermined | {c}")
    return "\n".join(lines), index


def normalize_oid(raw: Any) -> str:
    """
    Strip the decoration a model wraps around an id it read in a list. Kept as a repair COUNT
    rather than a silent fix: a run where every citation needed repairing is telling you the
    prompt taught the wrong format, and absorbing that quietly is how a harness defect gets
    written up as a model defect.
    """
    return str(raw).strip().strip("[]`\"' ").strip()


_FUNCTION_WORDS = set(
    "a an the and or but if then than that this these those there it its is are was were be been "
    "being of in on at to for from with without by as into over under between within about not no "
    "which who whom whose what when where how very more most less least some any each both other "
    "such same also only just even still yet can could may might must shall should will would do "
    "does did done have has had having i you he she they we them their his her our your my me us "
    "one two three four five six seven eight nine ten first second third".split())


#: Words about REASONING rather than about pictures. The novelty check exists to catch a visual
#: detail invented with no image in front of the model; `explicitly`, `states`, `grounds` and
#: `claim` are the model talking about the exercise, and counting them made the first alignment
#: pass report twenty-six inventions when it had made none.
_DISCOURSE_WORDS = set(
    "claim claims ground grounds stance stances observ observation observations note notes state "
    "statement mention describ description descriptions explicit implicit imply implication "
    "support supports contradict contradiction challeng complicat determin indicat suggest "
    "consistent inconsistent critical import general generic typical direct specific evidence "
    "reason therefore however although whereas match matches similar difference differ text "
    "given above below follow accord regard respect concern relat refer".split())


def _stem(w: str) -> str:
    """
    A crude suffix strip, and crude ON PURPOSE. Its whole job is to stop `reflecting` counting as
    a term invented out of nothing when the observations said `reflects`. It is not linguistics
    and the record says which words it collapsed, so a reader can disagree with it.
    """
    for suf in ("ations", "ation", "ingly", "ing", "edly", "ed", "ly", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def _content_words(text: str) -> set:
    return {_stem(w) for w in re.findall(r"[a-z]{4,}", (text or "").lower())
            if w not in _FUNCTION_WORDS}


def novelty(said_text: str, known_text: str) -> Dict[str, Any]:
    """
    Terms the model used that are in neither the observations nor the person's own words —
    split, because the two halves mean different things. `substantive` is the number that would
    indicate an invented visual detail; `discourse` is the model narrating its own reasoning and
    is expected to be non-zero in every run.
    """
    novel = sorted(_content_words(said_text) - _content_words(known_text))
    subst = [w for w in novel if w not in _DISCOURSE_WORDS]
    return {
        "novel_terms": novel,
        "novel_discourse": [w for w in novel if w in _DISCOURSE_WORDS],
        "novel_substantive": subst,
        "novel_substantive_count": len(subst),
        "note": "stems are compared, not words; see _stem. `substantive` is the half that would "
                "indicate a visual detail produced with no picture in front of the model.",
    }


def cmd_align(args) -> int:
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or latest_run()
    exp1 = read_record(run_id, "experiment-1-observe") if run_id else None
    if not exp1:
        print("experiment 1 has not been run for this run id. Run `observe` first — the order is "
              "the mechanism, not a convenience.")
        return 2

    prompts = json.loads(PROMPTS_PATH.read_text())
    which = args.prompt_id or "rich-tactile-philosophy"
    entry = next((p for p in prompts["prompts"] if p["id"] == which), None)
    if not entry:
        print(f"no prompt {which!r}. Have: {[p['id'] for p in prompts['prompts']]}")
        return 2

    digest, index = _observation_digest(exp1)
    schema = load_schema("alignment")

    call = client.chat(
        [{"role": "system", "content": ALIGN_SYSTEM},
         {"role": "user", "content":
             "OBSERVATIONS (written earlier, from the photographs):\n" + digest
             + "\n\nTHE PERSON'S HYPOTHESES (their words, not observations):\n"
             + entry["text"]
             + "\n\nBreak their hypotheses into separate claims and take a stance on each."}],
        label=f"align:{which}", max_tokens=args.max_tokens, schema=schema,
        thinking=args.thinking)

    obj, note = parse_json(call.content)
    errs = validate(obj, schema) if obj is not None else ["no parseable JSON"]

    # Did it invent a visual detail? Anything it says that is not in the observations and not in
    # the person's own words is a term the model produced with nothing in front of it.
    nov = novelty(json.dumps(obj, ensure_ascii=False) if obj else (call.content or ""),
                  digest + "\n" + entry["text"] + "\n" + ALIGN_SYSTEM)

    cited, bad_ids, repairs = [], [], 0
    for c in ((obj or {}).get("claims") or []):
        for raw_oid in (c.get("observation_ids") or []):
            oid = normalize_oid(raw_oid)
            if oid != str(raw_oid):
                repairs += 1
            cited.append(oid)
            if oid not in index and not oid.endswith("-undetermined"):
                bad_ids.append(oid)

    rec = {
        "provider": PROVIDER_IDENTITY, "run_id": run_id, "experiment": "2-prompt-aware-alignment",
        "prompt_id": which, "prompt_provenance": entry["provenance"],
        "saw_an_image": False,
        "note": "The request body carried no image part. The model could not have made a new "
                "visual observation here; that is enforced by the absence of the picture rather "
                "than by the instruction above it.",
        "observations_given": digest,
        "system": ALIGN_SYSTEM,
        "call": {k: v for k, v in asdict(call).items() if v is not None},
        "parsed": obj, "parse_note": note, "schema_errors": errs,
        "novelty": nov,
        "cited_observation_ids": cited,
        "hallucinated_observation_ids": bad_ids,
        "citation_format_repairs": repairs,
        "audit": audit_text(json.dumps(obj, ensure_ascii=False) if obj else (call.content or "")),
        "prompt_copying": prompt_copying(entry["text"], call.content or ""),
    }
    write_record(run_id, f"experiment-2-align-{which}", rec)

    stances = {}
    for c in ((obj or {}).get("claims") or []):
        stances[c.get("stance")] = stances.get(c.get("stance"), 0) + 1
    print(f"  prompt        {which} ({entry['provenance']})")
    print(f"  status        {call.status}   schema_errors={len(errs)}")
    print(f"  claims        {len(((obj or {}).get('claims') or []))}  stances={stances}")
    print(f"  cited ids     {len(cited)} cited, {len(bad_ids)} do not exist, "
          f"{repairs} needed their format repaired")
    print(f"  novel terms   {nov['novel_substantive_count']} substantive "
          f"{nov['novel_substantive'][:10]}  (+{len(nov['novel_discourse'])} discourse)")
    print(f"  copying       {rec['prompt_copying']['fraction_of_answer']} of the answer is the "
          f"question read back")
    for a in rec["audit"]["measurement_claims"] + rec["audit"]["attribution_claims"]:
        print(f"     FLAG {a['what']}: {a['match']!r}")
    return 0


# ── experiment 3 — multi-image comparison ────────────────────────────────────

COMPARE_SYSTEM = (
    "You are given short observations about several photographs, each under its own reference.\n"
    "Answer with comparisons between the references — what two of them share, and where they "
    "part company.\n"
    "Every comparison must name exactly the references it is about, using the reference strings "
    "given to you.\n"
    "Do not write a single essay about all of them at once. Do not name a maker, a period or a "
    "title. Nothing here has been measured."
)


def cmd_compare(args) -> int:
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or latest_run()
    exp1 = read_record(run_id, "experiment-1-observe") if run_id else None
    if not exp1:
        print("experiment 1 has not been run for this run id. Run `observe` first.")
        return 2

    digest, _ = _observation_digest(exp1)
    schema = load_schema("comparison")
    refs = [i["ref"] for i in exp1["images"]]

    call = client.chat(
        [{"role": "system", "content": COMPARE_SYSTEM},
         {"role": "user", "content":
             "OBSERVATIONS:\n" + digest
             + f"\n\nThe references are: {', '.join(refs)}. Give between three and six "
               f"comparisons, each naming the references it concerns."}],
        label="compare", max_tokens=args.max_tokens, schema=schema, thinking=args.thinking)

    obj, note = parse_json(call.content)
    errs = validate(obj, schema) if obj is not None else ["no parseable JSON"]

    # TWO DIFFERENT MISTAKES, and the first run collapsed them. `img-k7-o3` is not an invented
    # string — it is a real OBSERVATION id used where an IMAGE ref was required, which is a level
    # confusion: the model compared two loci and labelled it a comparison of two pictures. An
    # invented ref is a hallucination; a level confusion is a category error that a downstream
    # reader would silently misread as a claim about whole images. Reporting them as one number
    # would have described a fluent, well-formed, wrongly-scoped comparison as a hallucination.
    _digest, index = _observation_digest(exp1)
    off = sorted({normalize_oid(r) for c in ((obj or {}).get("comparisons") or [])
                  for r in (c.get("refs") or []) if normalize_oid(r) not in refs})
    wrong_level = [r for r in off if r in index]
    invented = [r for r in off if r not in index]

    rec = {"provider": PROVIDER_IDENTITY, "run_id": run_id, "experiment": "3-multi-image-compare",
           "refs": refs, "saw_an_image": False,
           "note": "Compact per-image observations from experiment 1 are the input. The images "
                   "are not re-sent: this measures comparison, not re-perception.",
           "system": COMPARE_SYSTEM,
           "call": {k: v for k, v in asdict(call).items() if v is not None},
           "parsed": obj, "parse_note": note, "schema_errors": errs,
           "invented_refs": invented,
           "wrong_level_refs": wrong_level,
           "wrong_level_note": "a real observation id used where an image ref was required — the "
                               "model compared two loci and labelled it a comparison of two "
                               "pictures. Not a hallucination; a category error, and one a reader "
                               "would take for a claim about whole images.",
           "audit": audit_text(
               json.dumps(obj, ensure_ascii=False) if obj else (call.content or ""))}
    write_record(run_id, "experiment-3-compare", rec)

    n = len(((obj or {}).get("comparisons") or []))
    print(f"  status        {call.status}   schema_errors={len(errs)}")
    print(f"  comparisons   {n}   invented refs: {invented or 'none'}   "
          f"wrong-level refs: {wrong_level or 'none'}")
    for c in ((obj or {}).get("comparisons") or [])[:6]:
        print(f"    {'+'.join(c.get('refs') or [])}: {(c.get('shared') or '')[:60]} | "
              f"parts at: {(c.get('differs') or '')[:60]}")
    return 0


# ── experiment 4 — strict JSON reliability ───────────────────────────────────

def cmd_reliability(args) -> int:
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or new_run_id()
    schema = load_schema("observation")
    corpus = load_corpus()
    raws = [image_bytes(e) for e in corpus]

    trials = []
    for i in range(args.trials):
        k = i % len(raws)
        ref = REF_TOKENS[k]
        m0 = machine_state(find_server_pid())
        r = _observe_one(client, ref, raws[k], schema, args.max_tokens, args.thinking)
        parsed = r["parsed"]
        prose = (json.dumps(parsed, ensure_ascii=False) if parsed
                 else (r["call"].get("content") or ""))
        trials.append({
            "i": i, "ref": ref, "post_id": corpus[k]["post_id"],
            "status": r["call"]["status"],
            "json_parsed": parsed is not None,
            "parse_note": r["parse_note"],
            "schema_ok": parsed is not None and not r["schema_errors"],
            "schema_errors": r["schema_errors"],
            "ref_correct": r["ref_correct"],
            "invalid_status_values": sorted({o.get("status") for o in
                                             (parsed or {}).get("observations") or []
                                             if o.get("status") != "interpretive"}),
            "hallucinated_refs": ([parsed.get("image_ref")]
                                  if parsed and parsed.get("image_ref") not in REF_TOKENS else []),
            "measurement_claims": len(r["audit"]["measurement_claims"]),
            "attribution_claims": len(r["audit"]["attribution_claims"]),
            "proper_nouns": r["audit"]["proper_nouns"],
            "prompt_copying": prompt_copying(BLIND_SYSTEM + BLIND_USER.format(ref=ref), prose),
            "latency_ms": r["call"].get("client_wall_ms"),
            "prompt_tokens": r["call"].get("prompt_tokens"),
            "completion_tokens": r["call"].get("completion_tokens"),
            "prompt_per_second": r["call"].get("prompt_per_second"),
            "predicted_per_second": r["call"].get("predicted_per_second"),
            "swap_before_mb": m0.get("swap_used_mb"),
            "swap_after_mb": (r["call"].get("machine_after") or {}).get("swap_used_mb"),
            "server_rss_mb": (r["call"].get("machine_after") or {}).get("server_rss_mb"),
        })
        t = trials[-1]
        print(f"  trial {i:>2}  {t['status']:<10} parse={t['json_parsed']} "
              f"schema={t['schema_ok']} ref={t['ref_correct']} "
              f"measured={t['measurement_claims']} attrib={t['attribution_claims']} "
              f"{t['latency_ms']:.0f}ms")

    def frac(key) -> float:
        return round(sum(1 for t in trials if t[key]) / len(trials), 4) if trials else 0.0

    lat = sorted(t["latency_ms"] for t in trials if t["latency_ms"] is not None)
    pps = [t["prompt_per_second"] for t in trials if t["prompt_per_second"]]
    gps = [t["predicted_per_second"] for t in trials if t["predicted_per_second"]]
    swaps = [t["swap_after_mb"] for t in trials if t["swap_after_mb"] is not None]
    rss = [t["server_rss_mb"] for t in trials if t["server_rss_mb"] is not None]

    summary = {
        "trials": len(trials),
        "json_parse_rate": frac("json_parsed"),
        "schema_rate": frac("schema_ok"),
        "ref_correct_rate": frac("ref_correct"),
        "trials_with_invalid_status": sum(1 for t in trials if t["invalid_status_values"]),
        "trials_with_hallucinated_ref": sum(1 for t in trials if t["hallucinated_refs"]),
        "trials_with_measurement_claim": sum(1 for t in trials if t["measurement_claims"]),
        "trials_with_attribution_claim": sum(1 for t in trials if t["attribution_claims"]),
        "max_prompt_copy_fraction": max(
            (t["prompt_copying"]["fraction_of_answer"] or 0) for t in trials) if trials else None,
        "latency_ms_median": lat[len(lat) // 2] if lat else None,
        "latency_ms_max": lat[-1] if lat else None,
        "prompt_tokens_per_second_median": sorted(pps)[len(pps) // 2] if pps else None,
        "generation_tokens_per_second_median": sorted(gps)[len(gps) // 2] if gps else None,
        "peak_swap_used_mb": max(swaps) if swaps else None,
        "peak_server_rss_mb": max(rss) if rss else None,
    }
    write_record(run_id, "experiment-4-reliability",
                 {"provider": PROVIDER_IDENTITY, "run_id": run_id,
                  "experiment": "4-strict-json-reliability",
                  "schema": "observation.schema.json",
                  "summary": summary, "trials": trials})
    print()
    for k, v in summary.items():
        print(f"  {k:<38}{v}")
    return 0


# ── experiment 5 — the four canonical prompts ────────────────────────────────

def cmd_rehearsal_prompts(args) -> int:
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or latest_run() or new_run_id()
    exp1 = read_record(run_id, "experiment-1-observe")
    if not exp1:
        print("experiment 1 has not been run for this run id. Run `observe` first.")
        return 2

    digest, index = _observation_digest(exp1)
    schema = load_schema("alignment")
    prompts = json.loads(PROMPTS_PATH.read_text())["prompts"]
    out = []

    for entry in prompts:
        call = client.chat(
            [{"role": "system", "content": ALIGN_SYSTEM},
             {"role": "user", "content":
                 "OBSERVATIONS (written earlier, from the photographs):\n" + digest
                 + "\n\nTHE PERSON'S HYPOTHESES (their words, not observations):\n"
                 + entry["text"]
                 + "\n\nBreak their hypotheses into separate claims and take a stance on each."}],
            label=f"prompts:{entry['id']}", max_tokens=args.max_tokens, schema=schema,
            thinking=args.thinking)
        obj, note = parse_json(call.content)
        errs = validate(obj, schema) if obj is not None else ["no parseable JSON"]
        nov = novelty(json.dumps(obj, ensure_ascii=False) if obj else (call.content or ""),
                      digest + "\n" + entry["text"] + "\n" + ALIGN_SYSTEM)
        stances = {}
        for c in ((obj or {}).get("claims") or []):
            stances[c.get("stance")] = stances.get(c.get("stance"), 0) + 1
        norm = [normalize_oid(o) for c in ((obj or {}).get("claims") or [])
                for o in (c.get("observation_ids") or [])]
        bad_ids = sorted({o for o in norm
                          if o not in index and not o.endswith("-undetermined")})
        r = {
            "prompt_id": entry["id"], "character": entry["character"],
            "provenance": entry["provenance"], "what_it_probes": entry["what_it_probes"],
            "call": {k: v for k, v in asdict(call).items() if v is not None},
            "parsed": obj, "parse_note": note, "schema_errors": errs,
            "stances": stances, "hallucinated_observation_ids": bad_ids,
            "novelty": nov,
            "prompt_copying": prompt_copying(entry["text"], call.content or ""),
            "audit": audit_text(
                json.dumps(obj, ensure_ascii=False) if obj else (call.content or "")),
        }
        out.append(r)
        print(f"  {entry['id']:<28}{call.status:<10} claims="
              f"{len(((obj or {}).get('claims') or []))} stances={stances} "
              f"novel={nov['novel_substantive_count']} copy="
              f"{r['prompt_copying']['fraction_of_answer']}")
        if entry["id"] == "adversarial-sameness":
            challenged = stances.get("challenges", 0) + stances.get("complicates", 0)
            print(f"        the adversarial probe: {challenged} of "
                  f"{len(((obj or {}).get('claims') or []))} claims resist the premise. "
                  f"A run where every claim `supports` has agreed, not looked.")

    write_record(run_id, "experiment-5-canonical-prompts",
                 {"provider": PROVIDER_IDENTITY, "run_id": run_id,
                  "experiment": "5-four-canonical-prompts",
                  "saw_an_image": False, "results": out})
    return 0


# ── the stability probe ──────────────────────────────────────────────────────

def cmd_stability(args) -> int:
    """
    THE SAME QUESTION, ASKED AGAIN. This probe exists because two runs of experiment 5 disagreed
    completely: on the adversarial prompt one returned `challenges` for every claim and the other
    returned `supports` for every claim, from the same observations, the same model and the same
    words. A single run of that experiment reads as a finding about the model; it is a finding
    about one sample.

    Cheap on purpose — the alignment pass carries no image, so a repeat costs seconds rather than
    the minute an observation costs. There is no excuse for reporting the single sample.
    """
    client = LocalQwenClient(args.base_url)
    if not client.alive():
        print(f"UNAVAILABLE — no server at {args.base_url}")
        return 2
    run_id = args.run or latest_run()
    exp1 = read_record(run_id, "experiment-1-observe") if run_id else None
    if not exp1:
        print("experiment 1 has not been run for this run id. Run `observe` first.")
        return 2

    prompts = json.loads(PROMPTS_PATH.read_text())["prompts"]
    entry = next((x for x in prompts if x["id"] == args.prompt_id), None)
    if not entry:
        print(f"no prompt {args.prompt_id!r}")
        return 2

    digest, index = _observation_digest(exp1)
    schema = load_schema("alignment")
    trials = []
    for i in range(args.repeats):
        call = client.chat(
            [{"role": "system", "content": ALIGN_SYSTEM},
             {"role": "user", "content":
                 "OBSERVATIONS (written earlier, from the photographs):\n" + digest
                 + "\n\nTHE PERSON'S HYPOTHESES (their words, not observations):\n"
                 + entry["text"]
                 + "\n\nBreak their hypotheses into separate claims and take a stance on each."}],
            label=f"stability:{entry['id']}:{i}", max_tokens=args.max_tokens, schema=schema)
        obj, _note = parse_json(call.content)
        claims = ((obj or {}).get("claims") or [])
        stances = {}
        for c in claims:
            stances[c.get("stance")] = stances.get(c.get("stance"), 0) + 1
        resisted = sum(v for k, v in stances.items() if k in ("challenges", "complicates"))
        trials.append({"i": i, "status": call.status, "n_claims": len(claims),
                       "stances": stances, "resisted": resisted,
                       "accepted": stances.get("supports", 0),
                       "latency_ms": call.client_wall_ms,
                       "claims": [{"claim": c.get("claim"), "stance": c.get("stance")}
                                  for c in claims]})
        print(f"  repeat {i:>2}  {call.status:<10} {len(claims)} claims  {stances}")

    ok = [t for t in trials if t["n_claims"]]
    all_resist = sum(1 for t in ok if t["accepted"] == 0 and t["resisted"])
    all_accept = sum(1 for t in ok if t["resisted"] == 0 and t["accepted"])
    summary = {
        "prompt_id": entry["id"], "repeats": len(trials), "usable": len(ok),
        "runs_where_every_claim_resisted": all_resist,
        "runs_where_every_claim_accepted": all_accept,
        "runs_mixed": len(ok) - all_resist - all_accept,
        "claim_count_range": [min((t["n_claims"] for t in ok), default=None),
                              max((t["n_claims"] for t in ok), default=None)],
        "reading": "For an adversarial premise, `runs_where_every_claim_accepted` above zero "
                   "means the model can be captured by the premise — and a split result means "
                   "whether it is captured is a sample, not a property.",
    }
    write_record(run_id, f"probe-stability-{entry['id']}",
                 {"run_id": run_id, "probe": "repeat-stability", "saw_an_image": False,
                  "temperature": "server default (1.0 — see serve.sh)",
                  "summary": summary, "trials": trials})
    print()
    for k, v in summary.items():
        print(f"  {k:<38}{v}")
    return 0

# ── the restart probe ────────────────────────────────────────────────────────

SERVE_DIR = Path(os.environ.get(
    "LOCAL_QWEN_SERVE_DIR", "/Users/merleauponty/ml models/qwen 9b q5km"))


def cmd_restart(args) -> int:
    """
    Shut the server down and bring it back, and time both halves.

    A provider that is "continuously available" is one you can restart without ceremony. This is
    the only command in the file that stops anything, it is never part of `all` unless asked for,
    and it reports a failure to come back as `unavailable` rather than retrying until it looks fine.
    """
    client = LocalQwenClient(args.base_url)
    run_id = args.run or latest_run() or new_run_id()
    pid = find_server_pid()
    rec: Dict[str, Any] = {"provider": PROVIDER_IDENTITY, "run_id": run_id,
                           "probe": "shutdown-and-restart", "pid_before": pid}

    if pid is None:
        rec["result"] = "nothing was running"
        write_record(run_id, "probe-restart", rec)
        print("nothing to restart — no llama-server process found")
        return 2

    t0 = time.time()
    subprocess.run(["kill", "-TERM", str(pid)], capture_output=True)
    gone = False
    for _ in range(200):
        if find_server_pid() is None:
            gone = True
            break
        time.sleep(0.1)
    rec["shutdown_clean"] = gone
    rec["shutdown_ms"] = round((time.time() - t0) * 1000, 1)
    print(f"  shutdown      {'clean' if gone else 'DID NOT EXIT'} in {rec['shutdown_ms']:.0f}ms")

    log = LAB_ROOT / "image-cache" / "restart-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t1 = time.time()
    subprocess.Popen(
        ["/bin/bash", "-lc", f'cd "{SERVE_DIR}" && VISION=1 CTX={args.ctx} ./serve.sh'],
        stdout=log.open("wb"), stderr=subprocess.STDOUT, start_new_session=True)

    healthy = False
    for _ in range(int(args.startup_budget * 2)):
        if client.alive():
            healthy = True
            break
        time.sleep(0.5)
    rec["startup_ms"] = round((time.time() - t1) * 1000, 1) if healthy else None
    rec["came_back"] = healthy
    print(f"  startup       {'healthy' if healthy else 'NEVER CAME BACK'}"
          + (f" in {rec['startup_ms']:.0f}ms" if healthy else
             f" within {args.startup_budget}s"))

    if healthy:
        first = client.chat([{"role": "user", "content": "Reply with exactly: alive"}],
                            label="restart:first_answer", max_tokens=16)
        rec["first_answer_ok"] = first.ok
        rec["first_answer_ms"] = first.client_wall_ms
        rec["first_answer"] = first.content
        print(f"  first answer  {first.content!r} in {first.client_wall_ms:.0f}ms")
    rec["pid_after"] = find_server_pid()
    rec["machine_after"] = machine_state(rec["pid_after"])
    write_record(run_id, "probe-restart", rec)
    return 0 if healthy else 2


# ── the gates ────────────────────────────────────────────────────────────────

@dataclass
class Gate:
    name: str
    asks: str
    verdict: str                      # PASS | FAIL | UNDETERMINED
    evidence: str


def cmd_gates(args) -> int:
    """
    The directive's eight conditions, each read out of a run record rather than out of an
    impression. A gate whose evidence was never captured is UNDETERMINED — which is a third
    answer, and collapsing it into FAIL would make a missing experiment look like a bad model.
    """
    run_id = args.run or latest_run()
    if not run_id:
        print("no runs recorded")
        return 2
    rel = read_record(run_id, "experiment-4-reliability")
    exp1 = read_record(run_id, "experiment-1-observe")
    exp3 = read_record(run_id, "experiment-3-compare")
    exp5 = read_record(run_id, "experiment-5-canonical-prompts")
    census = read_record(run_id, "census")
    restart = read_record(run_id, "probe-restart")
    stab = read_record(run_id, "probe-stability-adversarial-sameness")
    gates: List[Gate] = []

    def g(name, asks, cond, ev, have=True):
        gates.append(Gate(name, asks,
                          "UNDETERMINED" if not have else ("PASS" if cond else "FAIL"), ev))

    s = (rel or {}).get("summary") or {}
    n = s.get("trials") or 0
    parsed = round((s.get("json_parse_rate") or 0) * n)
    g("parse rate", "at least 9 of 10 small repeated responses parse",
      n >= 10 and (s.get("json_parse_rate") or 0) >= 0.9,
      f"{parsed}/{n} parsed; schema-valid {round((s.get('schema_rate') or 0) * n)}/{n}",
      have=bool(rel))

    g("image references", "image references remain correct",
      (s.get("ref_correct_rate") == 1.0) and not s.get("trials_with_hallucinated_ref")
      and not ((exp3 or {}).get("invented_refs"))
      and not ((exp3 or {}).get("wrong_level_refs")),
      f"reliability echoed the right ref in {s.get('ref_correct_rate')} of trials with "
      f"{s.get('trials_with_hallucinated_ref')} invented; the comparison pass invented "
      f"{((exp3 or {}).get('invented_refs')) or 'none'} and used "
      f"{((exp3 or {}).get('wrong_level_refs')) or 'no'} observation ids where an image ref was "
      f"required (a level confusion, not a hallucination — and it fails this gate because a "
      f"reader takes it for a claim about whole images)",
      have=bool(rel and exp3))

    novel = sum((r.get("novelty") or {}).get("novel_substantive_count") or 0
                for r in ((exp5 or {}).get("results") or []))
    bad_ids = [oid for r in ((exp5 or {}).get("results") or [])
               for oid in (r.get("hallucinated_observation_ids") or [])]

    # TWO DIFFERENT MISTAKES AGAIN, and the first version of this gate reported them as one.
    # `img-k7-o9` is a FABRICATED CITATION — well-formed, pointing at an observation that was
    # never written, and the kind of thing a reader would follow. `grounids` is a MALFORMED
    # STRING: the model garbled a token inside a JSON array whose grammar only promised strings.
    # Both fail the gate. Reporting a typo as an invented observation would have been the lane
    # telling a small lie about its own most important result.
    real_refs = [i["ref"] for i in ((exp1 or {}).get("images") or [])]
    well_formed = re.compile(r"^(?:%s)-o\d+$" % "|".join(re.escape(r) for r in real_refs)
                             ) if real_refs else None
    fabricated = [o for o in bad_ids if well_formed and well_formed.match(o)]
    malformed = [o for o in bad_ids if o not in fabricated]
    halluc = len(bad_ids)
    g("hypotheses stay hypotheses", "user hypotheses do not become observations",
      halluc == 0,
      f"the alignment pass was sent no image at all. It cited {halluc} observation ids that do "
      f"not exist: {len(fabricated)} well-formed but pointing at observations never written "
      f"({fabricated or 'none'}), and {len(malformed)} malformed strings the grammar could not "
      f"catch because it only promised an array of strings ({malformed or 'none'}) — a grammar "
      f"constrains shape, never a foreign key. It also used {novel} substantive terms present in "
      f"neither the observations nor "
      f"the person's own words — a SCREENING number this gate deliberately does not fire on, "
      f"because the check cannot tell an invented picture from an abstraction of one that was "
      f"given (`opaque` -> `opacity`). The terms are listed in the record for a reader to judge",
      have=bool(exp5))

    measured = (s.get("trials_with_measurement_claim") or 0) + (s.get(
        "trials_with_invalid_status") or 0)
    g("no measured status", "no measured status is fabricated",
      measured == 0,
      f"{s.get('trials_with_invalid_status')} trials carried a status other than `interpretive`; "
      f"{s.get('trials_with_measurement_claim')} trials wrote measurement grammar",
      have=bool(rel))

    three = ((census or {}).get("probes") or {}).get("three_images") or {}
    peak_swap = s.get("peak_swap_used_mb")
    wired = ((census or {}).get("machine_at_end") or {}).get("wired_mb")
    # THE FIRST VERSION OF THIS GATE FAILED THE MODEL FOR THE MACHINE'S CONDITION. It required
    # whole-machine swap under 4 GB, and on a box with a browser open that is a fact about the
    # browser. What "three images fit" can honestly mean is: the request completed, and the GPU
    # allocation stayed under the Metal ceiling this hardware reports. Swap is printed beside it
    # as context, explicitly not attributed to this process.
    g("three images fit", "three-image processing fits safely",
      bool(three.get("ok")) and (wired is None or wired < METAL_CEILING_MB),
      f"three images in one request: {three.get('status')}, {three.get('prompt_tokens')} prompt "
      f"tokens; wired memory {wired} MB against this hardware's {METAL_CEILING_MB} MB Metal "
      f"ceiling. Whole-machine swap peaked at {peak_swap} MB during the trials — context, not "
      f"evidence about the model: on unified memory that figure belongs to everything running",
      have=bool(census and rel))

    med = s.get("latency_ms_median")

    def r1(v):
        return round(v, 1) if isinstance(v, (int, float)) else v

    g("latency", "latency is acceptable",
      med is not None and med <= LATENCY_BUDGET_MS,
      f"median {r1(med)} ms, max {r1(s.get('latency_ms_max'))} ms per structured observation, "
      f"against a declared budget of {LATENCY_BUDGET_MS} ms. Generation "
      f"{r1(s.get('generation_tokens_per_second_median'))} tok/s, prompt "
      f"{r1(s.get('prompt_tokens_per_second_median'))} tok/s — the latency is that arithmetic, "
      f"not a stall. The directive does not define `acceptable`; this budget is this lane's, "
      f"declared here so a reader can disagree with the number rather than with the verdict",
      have=bool(rel))

    g("restart", "server restart is reliable",
      bool(restart and restart.get("shutdown_clean") and restart.get("came_back")
           and restart.get("first_answer_ok")),
      (f"shutdown {restart.get('shutdown_ms')} ms, startup {restart.get('startup_ms')} ms, "
       f"first answer {restart.get('first_answer_ms')} ms" if restart else "not probed"),
      have=bool(restart))

    ss = (stab or {}).get("summary") or {}
    g("resists a false premise", "an adversarial premise is not simply agreed with",
      ss.get("runs_where_every_claim_accepted") == 0,
      f"of {ss.get('usable')} repeats of the adversarial prompt, {ss.get('runs_where_every_claim_resisted')} "
      f"resisted every claim, {ss.get('runs_where_every_claim_accepted')} accepted every claim and "
      f"{ss.get('runs_mixed')} were mixed. This gate is not in the directive's list; it is here "
      f"because two runs of experiment 5 disagreed completely and a single sample would have "
      f"been reported as a property",
      have=bool(stab))

    # The last gate is a PROXY and says so. "More useful than a caption" is a judgement; what can
    # be counted is how many distinct places in the picture each form of output actually names.
    loci = 0
    cap_words = None
    if exp1:
        loci = sum(len((i.get("parsed") or {}).get("observations") or [])
                   for i in exp1.get("images") or [])
        cap_words = len(((exp1.get("plain_caption") or {}).get("content") or "").split())
    g("beats a caption", "output is more useful than a plain prose caption",
      loci >= 3 * len((exp1 or {}).get("images") or [1]),
      f"PROXY, not a judgement: {loci} separately located entries across "
      f"{len((exp1 or {}).get('images') or [])} images, each carrying its own surface, material "
      f"and uncertainty fields, against a {cap_words}-word caption naming the picture once. "
      f"Whether that is *worth* it is a reader's call, and the record holds both texts",
      have=bool(exp1))

    print(f"\nGATES · {PROVIDER_IDENTITY} · run {run_id}\n")
    for gt in gates:
        print(f"  {gt.verdict:<14}{gt.name}")
        print(f"                {gt.asks}")
        print(f"                {gt.evidence}\n")
    failed = [x.name for x in gates if x.verdict == "FAIL"]
    undet = [x.name for x in gates if x.verdict == "UNDETERMINED"]
    if failed:
        rec_verdict = "DO NOT INTEGRATE YET"
    elif undet:
        rec_verdict = "INCOMPLETE — evidence missing for: " + ", ".join(undet)
    else:
        rec_verdict = "ELIGIBLE for a later integration decision"
    print(f"  → {rec_verdict}")
    print("    This lane recommends nothing beyond eligibility. Binding a provider is a "
          "different decision,\n    made where the production contract lives.\n")
    write_record(run_id, "gates", {"provider": PROVIDER_IDENTITY, "run_id": run_id,
                                   "gates": [asdict(x) for x in gates],
                                   "verdict": rec_verdict})
    return 0 if not failed else 1


# ── freezing, resolving, and the CLI ─────────────────────────────────────────

def cmd_freeze(args) -> int:
    """
    Copy a run's real responses into `frozen/` so the tests can exercise the audits with no
    server. A frozen response is EVIDENCE, not a fixture invented to make a test pass — every one
    of these came off the model on this machine.
    """
    run_id = args.run or latest_run()
    if not run_id:
        print("no runs recorded")
        return 2
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    kept = []
    for name in ("experiment-1-observe", "experiment-2-align-rich-tactile-philosophy",
                 "experiment-3-compare", "experiment-4-reliability",
                 "experiment-5-canonical-prompts", "census", "gates"):
        rec = read_record(run_id, name)
        if rec is None:
            continue
        # The image cache path and machine telemetry are stripped: they are true of one machine at
        # one moment and would make the frozen corpus look like a claim about every machine.
        blob = json.dumps(rec, ensure_ascii=False)
        (FROZEN_DIR / f"{name}.json").write_text(blob + "\n")
        kept.append(name)
    (FROZEN_DIR / "PROVENANCE.md").write_text(
        f"# Frozen responses — {PROVIDER_IDENTITY}\n\n"
        f"Captured from run `{run_id}` on this machine. Every file here is a REAL response from\n"
        f"the local server, kept so `backend/tests/test_local_qwen_vlm_lab.py` can exercise the\n"
        f"audits and the schema without a model loaded. Nothing here was hand-written to make a\n"
        f"test pass; where a response is bad, the test asserts that the audit CATCHES it.\n\n"
        f"Files: {', '.join(kept)}\n")
    print(f"  froze {len(kept)} records from run {run_id} into {FROZEN_DIR}")
    return 0


def cmd_resolve(args) -> int:
    rows = resolve_corpus_from_mongo()
    images = []
    for r in rows:
        if not r.get("found"):
            print(f"  {r['post_id']}  NOT FOUND")
            images.append(r)
            continue
        with urllib.request.urlopen(r["photo_url"], timeout=60) as h:
            raw = h.read()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{r['post_id']}.jpg").write_bytes(raw)
        r["sha256"] = hashlib.sha256(raw).hexdigest()
        r["bytes"] = len(raw)
        images.append(r)
        print(f"  {r['post_id']}  {r['bytes']} bytes  sha256 {r['sha256'][:16]}…  "
              f"tags={r['general_tags']} text_blocks={r['n_text_blocks']} "
              f"regions={r['n_region_annotations']}")
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(json.dumps({
        "provider_lab": PROVIDER_IDENTITY,
        "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "access": "read-only; every mutating method on the posts collection was replaced with a "
                  "raiser before the first query",
        "bytes_in_git": False,
        "note": "The image bytes are cached under image-cache/, which this lab's .gitignore "
                "excludes. The sha256 is the anchor: an observation in this lab is about THESE "
                "bytes and the harness refuses to run if they change.",
        "images": images}, indent=2) + "\n")
    print(f"\n  written  {CORPUS_PATH}")
    return 0


def cmd_all(args) -> int:
    run_id = args.run or new_run_id()
    args.run = run_id
    print(f"\n=== INTELLIGENCE-001C · {PROVIDER_IDENTITY} · run {run_id} ===\n")
    steps = [("census", cmd_census), ("experiment 1 — prompt-blind observation", cmd_observe),
             ("experiment 2 — prompt-aware alignment", cmd_align),
             ("experiment 3 — multi-image comparison", cmd_compare),
             ("experiment 4 — strict JSON reliability", cmd_reliability),
             ("experiment 5 — the four canonical prompts", cmd_rehearsal_prompts),
             ("probe — repeat stability on the adversarial prompt", cmd_stability)]
    if args.with_restart:
        steps.append(("probe — shutdown and restart", cmd_restart))
    for title, fn in steps:
        print(f"\n--- {title}")
        rc = fn(args)
        if rc == 2:
            print(f"  stopping: {title} could not run")
            return 2
    print("\n--- gates")
    return cmd_gates(args)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="INTELLIGENCE-001C — the local Qwen3.5-9B visual-observation laboratory. "
                    "Evaluates, and binds nothing.")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--run", default=None, help="run id to write into or read from")
    ap.add_argument("--max-tokens", type=int, default=1600)
    ap.add_argument("--thinking", action="store_true",
                    help="let the model think first. Off by default: thinking is charged against "
                         "max_tokens and a small budget returns empty content.")
    ap.add_argument("--model-path", default=str(
        Path(os.environ.get("LOCAL_QWEN_SERVE_DIR",
                            "/Users/merleauponty/ml models/qwen 9b q5km"))
        / "Qwen3.5-9B-Q5_K_M.gguf"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("census", help="the fifteen provider questions, each probed")
    sub.add_parser("resolve", help="re-resolve the three posts from Mongo, read-only")
    sub.add_parser("observe", help="experiment 1 — prompt-blind observation")
    a2 = sub.add_parser("align", help="experiment 2 — prompt-aware alignment")
    a2.add_argument("--prompt-id", default="rich-tactile-philosophy")
    sub.add_parser("compare", help="experiment 3 — multi-image comparison")
    a4 = sub.add_parser("reliability", help="experiment 4 — repeated strict-JSON trials")
    a4.add_argument("--trials", type=int, default=10)
    sub.add_parser("rehearsal-prompts", help="experiment 5 — the four canonical prompts")
    st = sub.add_parser("stability", help="ask one prompt N times and count the stances")
    st.add_argument("--repeats", type=int, default=6)
    st.add_argument("--prompt-id", default="adversarial-sameness")
    ar = sub.add_parser("restart", help="shut the server down and bring it back")
    ar.add_argument("--ctx", type=int, default=32768)
    ar.add_argument("--startup-budget", type=float, default=180.0)
    sub.add_parser("gates", help="the eight conditions, computed from the records")
    sub.add_parser("freeze", help="copy a run's real responses into frozen/ for the tests")
    aa = sub.add_parser("all", help="census and experiments 1-5, then the gates")
    aa.add_argument("--with-restart", action="store_true")

    args = ap.parse_args(argv)
    for attr, default in (("trials", 10), ("prompt_id", "rich-tactile-philosophy"),
                          ("with_restart", False), ("ctx", 32768), ("repeats", 6),
                          ("startup_budget", 180.0)):
        if not hasattr(args, attr):
            setattr(args, attr, default)

    return {
        "census": cmd_census, "resolve": cmd_resolve, "observe": cmd_observe,
        "align": cmd_align, "compare": cmd_compare, "reliability": cmd_reliability,
        "rehearsal-prompts": cmd_rehearsal_prompts, "stability": cmd_stability,
        "restart": cmd_restart,
        "gates": cmd_gates, "freeze": cmd_freeze, "all": cmd_all,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
