#!/usr/bin/env python3
"""
INTELLIGENCE-001D — the Gemini free-tier laboratory.

WHAT THIS IS FOR. Semant already has two thinkers it can reach: a local Qwen VLM and the hosted
Groq theorist. This asks whether the currently available Gemini free tier is a third worth
having — what the ACCOUNT actually offers, whether the model can hold a structured-output
contract, and what it does with an image, with three images, and with a prompt that arrives
carrying the user's conclusion already inside it.

WHAT IT IS NOT. It integrates nothing. No production inquiry service imports this file, no route
calls it, no Director actuator wraps it. It writes under `research/rehearsals/provider-labs/
gemini-vlm/` and nowhere else. A green run here is a finding about a provider, and is explicitly
NOT a claim that Semant can now see anything it could not see yesterday.

THE THREE DISTINCTIONS THIS FILE WILL NOT LET YOU LOSE, because each is a mistake that would
survive review by looking like a result:

    a user hypothesis        The Rich prompt asserts that folds become veils, skin, metal. That
                             assertion arrived from a person, before any image was opened. A
                             model that echoes it has produced AGREEMENT.
    an interpretive reading  What a VLM says it sees. Useful, recordable, and not evidence. Every
                             record this file writes is stamped `interpretive`, and the schema
                             pins `measured` to the constant false — a record that wanted to
                             claim otherwise cannot be written without editing the schema, which
                             is the review that ought to happen.
    a measurement            Something an organ measured, with a method you can point at. This
                             lab produces none, and says so in every file it writes.

    Nothing here becomes measured because two models agreed. Agreement is a fact about models.

THE TOPIC IS DATA, NOT CODE. Folds, sculpture, veils and skin appear in `prompts.json` and in
nothing else. This file does not know what a fold is, and could run a lab on Ajanta halls or on
weather photographs by pointing at a different corpus and a different prompt file. An instrument
that had one rehearsal's vocabulary compiled into it could not report that the rehearsal failed.

THE KEY. `GEMINI_API_KEY`, from the environment, once, into a header. It is never written into a
URL (a URL is a thing that gets logged, copied into a report and pasted into a bug), never
printed, and scrubbed out of every error string before it reaches disk. With no key the lab is
still fully exercisable: the tooling runs, the frozen tests pass, and the live experiments record
`unavailable` — which is a result, not a crash.

IDENTITY IS NEVER INFERRED. Every record carries `mode`: `live` used the network, `replay` read a
frozen record back and made NO call, `fixture` came from a fake transport in the test suite. The
replay transport raises if anything tries to reach the network through it, so "replay" cannot
quietly become "live" the day someone adds a retry.

USAGE

    python scripts/gemini_vlm_lab.py corpus              # resolve the 3 posts, read-only
    python scripts/gemini_vlm_lab.py corpus --check      # prove they have not drifted
    python scripts/gemini_vlm_lab.py census              # what THIS account offers
    python scripts/gemini_vlm_lab.py list                # the six experiments, in order
    python scripts/gemini_vlm_lab.py run --experiment text_minimal
    python scripts/gemini_vlm_lab.py run-all             # small calls first, and it stops on 429
    python scripts/gemini_vlm_lab.py replay --run <run_id>
    python scripts/gemini_vlm_lab.py report [--run <run_id>]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# The validator is BORROWED, not vendored a second time. `single_actuator_lab_support.contract`
# borrows the same one from `rehearsal_run` for the same reason: a provider lab that validated
# more loosely than the rehearsal program would eventually accept a record the rest of the
# research memory would reject.
import rehearsal_run as _rr                                                      # noqa: E402

ValidationError = _rr.ValidationError

LAB = "gemini-vlm"
LAB_ROOT = os.path.join(REPO_ROOT, "research", "rehearsals", "provider-labs", LAB)
SCHEMA_DIR = os.path.join(LAB_ROOT, "schemas")
FIXTURE_DIR = os.path.join(LAB_ROOT, "fixtures")
RUNS_ROOT = os.path.join(LAB_ROOT, "runs")
CENSUS_DIR = os.path.join(LAB_ROOT, "census")
CORPUS_DIR = os.path.join(LAB_ROOT, "corpus")
PROMPTS_PATH = os.path.join(LAB_ROOT, "prompts.json")
CORPUS_PATH = os.path.join(LAB_ROOT, "corpus.json")
CENSUS_PATH = os.path.join(CENSUS_DIR, "census.json")

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
KEY_ENV = "GEMINI_API_KEY"

#: The three posts this lab looks at. IDs only — the URLs are resolved from the database and
#: written to `corpus.json`, so a URL that rotates is a recorded change and not a silent one.
CORPUS_POST_IDS = (
    "6a6041b81ecd6db1c931eb7a",
    "6a6041b61ecd6db1c931eb78",
    "6a60408e1ecd6db1c931eb6b",
)

#: Small calls first. `run-all` walks this order so that a quota ceiling is hit by the cheapest
#: call that could hit it, not by the four-image one after twenty seconds of upload.
EXPERIMENTS = (
    "text_minimal",
    "image_one",
    "json_strict",
    "image_three",
    "hypothesis_alignment",
    "relation_proposal",
)

#: Free tiers are metered. The lab refuses to exceed this in one invocation rather than
#: discovering the ceiling by hitting it repeatedly; `--max-calls` can lower it, never raise it.
MAX_CALLS_PER_RUN = 24


# ── the key, and never seeing it ──────────────────────────────────────────────────────────────

def api_key() -> Optional[str]:
    """The key, from the environment, or None. Never a prompt, never a file, never an argument.

    A `--api-key` flag would put it in shell history and in `ps`. There is deliberately no way
    to pass it to this program except the environment.
    """
    value = (os.environ.get(KEY_ENV) or "").strip()
    return value or None


def key_fingerprint(key: Optional[str]) -> Optional[str]:
    """Which key, without the key. Enough to tell two accounts apart in a run record."""
    if not key:
        return None
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def redact(text: Any, key: Optional[str] = None) -> str:
    """Scrub the key out of anything on its way to disk, a log or a report.

    Called on every error message and every URL. The key should never reach here in the first
    place — it lives in a header — but "should never" is not a guarantee, and a provider that
    echoes the request URL back inside a 400 would otherwise write it into the record.
    """
    out = "" if text is None else str(text)
    secret = key if key is not None else api_key()
    if secret:
        out = out.replace(secret, "***REDACTED***")
    return out


# ── schemas, hashes, disk ─────────────────────────────────────────────────────────────────────

def load_schema(name: str) -> Dict[str, Any]:
    with open(os.path.join(SCHEMA_DIR, f"{name}.schema.json"), "r") as fh:
        return json.load(fh)


def validate(instance: Any, schema_name: str, *, raise_on_error: bool = False) -> List[str]:
    return _rr.validate(instance, load_schema(schema_name), raise_on_error=raise_on_error)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(obj: Any) -> str:
    """A digest of a structure, stable across dict ordering."""
    return sha256_bytes(json.dumps(obj, sort_keys=True, default=str).encode("utf-8"))


def write_json(path: str, payload: Any) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    return path


def read_json(path: str) -> Any:
    with open(path, "r") as fh:
        return json.load(fh)


def load_prompts() -> Dict[str, Dict[str, Any]]:
    doc = read_json(PROMPTS_PATH)
    return {p["id"]: p for p in doc["prompts"]}


# ── the transport seam ────────────────────────────────────────────────────────────────────────

@dataclass
class Response:
    """What a transport returns. Deliberately dumb: status, headers, bytes. Parsing happens
    above, so a fake transport in a test is a two-line object and cannot accidentally implement
    behaviour the real one does not have."""
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except Exception:
            return None


class HttpTransport:
    """The only thing in this file that touches the network."""

    mode = "live"

    def __init__(self, timeout: float = 90.0):
        self.timeout = timeout

    def request(self, method: str, url: str, headers: Mapping[str, str],
                body: Optional[bytes]) -> Response:
        import requests
        resp = requests.request(method, url, headers=dict(headers), data=body,
                                timeout=self.timeout)
        return Response(status=resp.status_code,
                        headers={k.lower(): v for k, v in resp.headers.items()},
                        body=resp.content)


class RefusingTransport:
    """Replay's transport. Its whole job is to make the network unreachable.

    Replay means a frozen record was read back. If a code path in replay ever reaches for the
    API — a retry, a fallback, a "just re-fetch the model list" — this raises instead of quietly
    turning a replay into a live call that the record would then describe as a replay.
    """

    mode = "replay"

    def request(self, *_args: Any, **_kwargs: Any) -> Response:
        raise RuntimeError("replay mode reached for the network; refusing")


class FrozenTransport:
    """A scripted transport for the test suite and for `--fixture` runs.

    Takes an ordered list of `Response`s (or of callables). Records what it was asked for, so a
    test can assert the request boundary — the headers, the body shape, the number of calls —
    which is most of what there is to get wrong about a provider client.
    """

    mode = "fixture"

    def __init__(self, responses: Sequence[Any]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def request(self, method: str, url: str, headers: Mapping[str, str],
                body: Optional[bytes]) -> Response:
        self.calls.append({"method": method, "url": url, "headers": dict(headers),
                           "body": json.loads(body.decode("utf-8")) if body else None})
        if not self._responses:
            raise AssertionError("FrozenTransport ran out of scripted responses")
        nxt = self._responses.pop(0)
        return nxt(method, url, headers, body) if callable(nxt) else nxt


# ── the client ────────────────────────────────────────────────────────────────────────────────

class GeminiClient:
    """The Gemini REST surface, at the size this lab needs it.

    NO SDK. `google-generativeai` would be a new production dependency in requirements.txt for
    a research lab that makes two kinds of request, and it hides the two things the census is
    actually about — the raw response body and the response headers. `requests` is already a
    declared dependency; the REST shape is the observable.

    THE KEY GOES IN A HEADER. `?key=...` is the documented alternative and is what most examples
    show; it also puts the secret into every proxy log, every traceback that echoes a URL, and
    every copy-paste of a failing request. `x-goog-api-key` costs nothing and does none of that.
    """

    def __init__(self, transport: Any = None, *, key: Optional[str] = None,
                 api_root: str = API_ROOT):
        self.transport = transport if transport is not None else HttpTransport()
        self._key = key if key is not None else api_key()
        self.api_root = api_root
        self.calls = 0

    @property
    def available(self) -> bool:
        return bool(self._key)

    @property
    def mode(self) -> str:
        return getattr(self.transport, "mode", "live")

    def redact(self, text: Any) -> str:
        """Scrub THIS client's key, not whatever happens to be in the environment.

        The module-level `redact` falls back to `api_key()`, which is right for the paths that
        use the ambient key and silently wrong for a client constructed with an explicit one:
        it would find nothing to scrub and hand back the secret intact. Every record written by
        `call()` goes through here.
        """
        return redact(text, self._key)

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["x-goog-api-key"] = self._key
        return headers

    def _send(self, method: str, path: str, payload: Optional[Any]) -> Tuple[Response, float]:
        url = f"{self.api_root}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        started = time.time()
        self.calls += 1
        resp = self.transport.request(method, url, self._headers(), body)
        return resp, (time.time() - started) * 1000.0

    def list_models(self) -> Tuple[Response, float]:
        return self._send("GET", "/models", None)

    def generate_content(self, model: str, payload: Dict[str, Any]) -> Tuple[Response, float]:
        return self._send("POST", f"/models/{model}:generateContent", payload)


# ── reading a Gemini response without believing more than it said ─────────────────────────────

def _first_text(body: Any) -> Optional[str]:
    """The candidate's text, or None. Never "" — an empty string and an absent answer are
    different results and the record distinguishes them."""
    try:
        parts = body["candidates"][0]["content"]["parts"]
    except Exception:
        return None
    chunks = [p["text"] for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
    return "".join(chunks) if chunks else None


def _usage(body: Any) -> Optional[Dict[str, Optional[int]]]:
    """Usage metadata AS REPORTED. Absent means null, not zero — a zero would read as a free
    call, which is the one thing a quota census must not invent."""
    if not isinstance(body, dict):
        return None
    meta = body.get("usageMetadata")
    if not isinstance(meta, dict):
        return None
    def _int(k: str) -> Optional[int]:
        v = meta.get(k)
        return v if isinstance(v, int) else None
    return {"prompt_token_count": _int("promptTokenCount"),
            "candidates_token_count": _int("candidatesTokenCount"),
            "total_token_count": _int("totalTokenCount")}


def _retry_after_seconds(resp: Response, body: Any) -> Optional[float]:
    """Two places it can come from, both observed, neither assumed."""
    header = resp.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        for detail in body["error"]["details"]:
            delay = detail.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                return float(delay[:-1])
    except Exception:
        pass
    return None


def classify(resp: Response, body: Any) -> Tuple[str, Optional[str], Optional[bool]]:
    """(status, finish_reason, safety_blocked) — the five outcomes, kept apart.

    `empty` (answered with nothing), `refused` (safety or recitation stopped it) and `error` are
    three different findings about a provider. Collapsing them into "it didn't work" is how a
    model that refuses a third of a corpus gets reported as flaky.
    """
    if resp.status != 200:
        return "error", None, None
    if not isinstance(body, dict):
        return "error", None, None
    block = ((body.get("promptFeedback") or {}).get("blockReason"))
    if block:
        return "refused", str(block), True
    candidates = body.get("candidates") or []
    if not candidates:
        return "empty", None, False
    finish = candidates[0].get("finishReason")
    finish = str(finish) if finish is not None else None
    if finish in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"):
        return "refused", finish, True
    text = _first_text(body)
    if text is None or text.strip() == "":
        return "empty", finish, False
    return "ok", finish, False


# ── the epistemic stamp ───────────────────────────────────────────────────────────────────────

#: Fixed, and fixed on purpose. Nothing this lab produces is a measurement: a VLM naming a
#: quality has read the image, not measured it, and no amount of agreement between models
#: promotes a reading. The schema pins `measured` to the constant false, so a future call site
#: that wanted to claim otherwise has to edit a schema in a reviewed diff.
def epistemic_stamp(prompt: Optional[Mapping[str, Any]] = None,
                    note: Optional[str] = None) -> Dict[str, Any]:
    carries = None
    if prompt is not None:
        carries = bool(prompt.get("carries_claim"))
    return {
        "status": "interpretive",
        "measured": False,
        "supported_by_capability": None,
        "prompt_carries_user_claim": carries,
        "note": note,
    }


def assert_not_measured(record: Mapping[str, Any]) -> None:
    """The guard behind the guard.

    The schema already forbids it. This runs before every write anyway, because a schema is
    only consulted where someone remembered to consult it, and the cost of the second check is
    a dict lookup against the cost of one interpretive reading entering the research memory
    dressed as evidence.
    """
    ep = record.get("epistemic") or {}
    if ep.get("measured") is not False or ep.get("status") != "interpretive":
        raise ValidationError(
            "refusing to write a lab record that claims measurement; this lab measures nothing")
    if ep.get("supported_by_capability") is not None:
        raise ValidationError(
            "refusing to write a lab record that names a supporting capability; none exists")


# ── the corpus, read-only ─────────────────────────────────────────────────────────────────────

def _posts_collection() -> Any:
    """Imported lazily and locally, so every part of this file that needs no database runs
    without one — which is all of it except this function."""
    from backend.database import sync_database
    return sync_database().get_collection("posts")


def _fingerprint(doc: Mapping[str, Any]) -> str:
    """The kernel's own definition of "the document", not a second one written here."""
    from backend.services.perception_lab.source import fingerprint_of
    return fingerprint_of(doc)


def _ext_for(mime: str) -> str:
    return {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(mime, "bin")


def fetch_image(url: str) -> Tuple[bytes, str]:
    """Bytes and mime type, from the CDN. Read-only, and outside the API key's blast radius."""
    import requests
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    mime = (resp.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
    return resp.content, mime


def resolve_corpus(post_ids: Sequence[str] = CORPUS_POST_IDS, *,
                   fetch: bool = True) -> Dict[str, Any]:
    """The three posts → a manifest of URLs and digests. READS. NEVER WRITES.

    Rule 10 in the spine is "preserve source posts byte-identically", and the way this file
    honours it is by having no write path at all — not a guarded one, none — and the test suite
    checks that structurally, by name, so no later edit can quietly acquire one. The
    fingerprint recorded here is what a later `--check` compares against.

    Image BYTES are cached to `corpus/` and gitignored. What gets committed is the digest —
    enough to prove the same picture was sent, small enough that the research memory stays
    readable, and the CDN stays the one copy of the image.
    """
    from bson import ObjectId
    posts = _posts_collection()
    rows: List[Dict[str, Any]] = []
    for pid in post_ids:
        doc = posts.find_one({"_id": ObjectId(pid)})
        if doc is None:
            rows.append({"post_id": pid, "resolved": False,
                         "why": "no such post", "photo_url": None,
                         "sha256": None, "bytes": None, "mime_type": None,
                         "post_fingerprint": None})
            continue
        url = doc.get("photo_url")
        row: Dict[str, Any] = {
            "post_id": pid,
            "resolved": bool(url),
            "why": None if url else "post has no photo_url",
            "photo_url": url,
            "post_fingerprint": _fingerprint(doc),
            "sha256": None, "bytes": None, "mime_type": None, "cached_at": None,
        }
        if url and fetch:
            try:
                data, mime = fetch_image(url)
                row.update(sha256=sha256_bytes(data), bytes=len(data), mime_type=mime)
                cached = os.path.join(CORPUS_DIR, f"{pid}.{_ext_for(mime)}")
                os.makedirs(CORPUS_DIR, exist_ok=True)
                with open(cached, "wb") as fh:
                    fh.write(data)
                row["cached_at"] = os.path.relpath(cached, REPO_ROOT)
            except Exception as e:
                row["resolved"] = False
                row["why"] = f"fetch failed: {type(e).__name__}: {redact(e)}"
        rows.append(row)
    return {"version": "gemini-vlm-corpus.v1",
            "note": ("Resolved read-only from the posts collection. No field of any post was "
                     "written. `post_fingerprint` is the invariant a run re-checks."),
            "images": rows}


def load_corpus() -> List[Dict[str, Any]]:
    if not os.path.exists(CORPUS_PATH):
        raise SystemExit("no corpus.json — run: python scripts/gemini_vlm_lab.py corpus")
    return [r for r in read_json(CORPUS_PATH)["images"] if r.get("resolved")]


def corpus_bytes(row: Mapping[str, Any]) -> bytes:
    """The cached image, verified against the digest in the manifest before it is sent.

    A cache that had drifted would send a different picture under a recorded hash, and every
    observation in the run would be about an image nobody could identify afterwards.
    """
    path = os.path.join(REPO_ROOT, row["cached_at"]) if row.get("cached_at") else None
    if not path or not os.path.exists(path):
        data, _mime = fetch_image(row["photo_url"])
    else:
        with open(path, "rb") as fh:
            data = fh.read()
    got = sha256_bytes(data)
    if row.get("sha256") and got != row["sha256"]:
        raise ValidationError(
            f"image for {row['post_id']} does not match the manifest digest "
            f"({got[:12]} != {row['sha256'][:12]}); refusing to send it")
    return data


def corpus_fingerprints(post_ids: Sequence[str]) -> Dict[str, Optional[str]]:
    """Fingerprints now, for the before/after invariant. Best-effort: with no database this
    returns nulls, and a null is recorded as "not checked" rather than as "unchanged"."""
    try:
        from bson import ObjectId
        posts = _posts_collection()
    except Exception:
        return {pid: None for pid in post_ids}
    out: Dict[str, Optional[str]] = {}
    for pid in post_ids:
        try:
            doc = posts.find_one({"_id": ObjectId(pid)})
            out[pid] = _fingerprint(doc) if doc else None
        except Exception:
            out[pid] = None
    return out


# ── the instructions that are topic-free, and therefore live in code ──────────────────────────
#
# The four canonical prompts are DATA (prompts.json) because they carry a rehearsal's subject.
# These three carry none: they would read identically over weather photographs. Keeping them
# here and the topic there is the line rule 5 draws.

PROBE_TEXT = "Reply with exactly one word: ready"

OBSERVATION_INSTRUCTION = (
    "Describe only what is visible in the image or images provided. For each image, name a "
    "quality you can see and state the visible evidence for it. Do not explain what the work "
    "means, do not name the artist, period or material unless it is legible in the image, and "
    "do not carry a claim over from one image to another. If something cannot be settled from "
    "what is shown, put it in the refusals rather than answering it."
)

ALIGNMENT_INSTRUCTION = (
    "A person wrote the text below before these images were examined. It may assert a "
    "conclusion, or it may only ask a question.\n\n"
    "First restate what, if anything, the text ASSUMED. Then examine the images and report "
    "what is visible that bears on it, image by image. You are not being asked whether you "
    "agree with the person. 'refused' and 'not_answerable_from_images' are correct answers "
    "when the images cannot settle the claim, and are preferred to a supported verdict you "
    "cannot show evidence for.\n\nTHE PERSON WROTE:\n"
)

RELATION_INSTRUCTION = (
    "Below are observations a system recorded earlier from a set of images. The images "
    "themselves are NOT provided and you must not imagine them. Propose relations that hold "
    "BETWEEN these observations, and for each one name the observation indices it rests on. "
    "If a relation you can think of is not supported by the observations as written, put it in "
    "'declined' instead of proposing it."
)


# ── one call, recorded ────────────────────────────────────────────────────────────────────────

def _image_part(row: Mapping[str, Any], data: bytes) -> Dict[str, Any]:
    return {"inline_data": {"mime_type": row.get("mime_type") or "image/jpeg",
                            "data": base64.b64encode(data).decode("ascii")}}


def _request_summary(text_parts: Sequence[str], image_rows: Sequence[Mapping[str, Any]],
                     sizes: Mapping[str, int], gen_config: Optional[Dict[str, Any]],
                     response_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """What was sent, small enough to read. Image bytes never enter a record — the digest is
    the identity, and a base64 blob in a JSON file makes the run unreadable to a human, which
    is the only reader these files have."""
    return {
        "boundary_hash": stable_hash({"text": list(text_parts),
                                      "images": [r.get("sha256") for r in image_rows],
                                      "gen": gen_config, "schema": response_schema}),
        "text_parts": list(text_parts),
        "image_parts": [{"post_id": r["post_id"], "sha256": r["sha256"],
                         "mime_type": r.get("mime_type") or "image/jpeg",
                         "bytes": sizes.get(r["post_id"], r.get("bytes") or 0)}
                        for r in image_rows],
        "response_schema_sent": response_schema,
        "generation_config": gen_config,
    }


def unavailable_record(call_id: str, experiment: str, *, model: Optional[str],
                       prompt: Optional[Mapping[str, Any]] = None,
                       why: str = f"{KEY_ENV} is not set") -> Dict[str, Any]:
    """The record written when there is no key.

    Not a crash and not a skip: a file, in the run, saying which experiment did not happen and
    why. A run directory that simply lacked four of its six experiments would be indistinguishable
    from one where four calls were quietly dropped.
    """
    record = {
        "call_id": call_id, "lab": LAB, "experiment": experiment, "mode": "live",
        "provider": "gemini", "endpoint": "(not called)", "model": model,
        "prompt_id": (prompt or {}).get("id"),
        "request": {"boundary_hash": stable_hash({"unavailable": why}),
                    "text_parts": [], "image_parts": [],
                    "response_schema_sent": None, "generation_config": None},
        "outcome": {"status": "unavailable", "http_status": None, "finish_reason": None,
                    "safety_blocked": None, "text": None, "json": None,
                    "json_valid_against_schema": None, "schema_errors": [],
                    "error_type": None, "error_message": redact(why)},
        "telemetry": {"latency_ms": None, "usage": None, "model_version_reported": None,
                      "retry_after_s": None, "rate_limited": None},
        "epistemic": epistemic_stamp(prompt, "no call was made; nothing was observed"),
        "corpus_invariant": None,
        "captured_at": None,
        "content_hash": "",
    }
    record["content_hash"] = stable_hash({k: v for k, v in record.items()
                                          if k != "content_hash"})
    return record


def call(client: GeminiClient, *, call_id: str, experiment: str, model: str,
         text_parts: Sequence[str], image_rows: Sequence[Mapping[str, Any]] = (),
         response_schema: Optional[Dict[str, Any]] = None,
         validate_with: Optional[str] = None,
         prompt: Optional[Mapping[str, Any]] = None,
         max_output_tokens: int = 1024,
         check_corpus: bool = True) -> Dict[str, Any]:
    """Make exactly one call and return its record. Never raises for a provider failure.

    ONE CALL. No retry loop, no "try the next model", no reformat-and-ask-again. A lab that
    retried until it got parseable JSON would measure how long it takes to get lucky, and would
    report a model's schema compliance as perfect while the retry counter climbed out of sight.
    A 429 is a finding about the free tier, which is a thing this lab exists to find.
    """
    parts: List[Dict[str, Any]] = [{"text": t} for t in text_parts]
    sizes: Dict[str, int] = {}
    for row in image_rows:
        data = corpus_bytes(row)
        sizes[row["post_id"]] = len(data)
        parts.append(_image_part(row, data))

    gen_config: Dict[str, Any] = {"temperature": 0, "maxOutputTokens": max_output_tokens}
    if response_schema is not None:
        gen_config["responseMimeType"] = "application/json"
        gen_config["responseSchema"] = response_schema

    ids = [r["post_id"] for r in image_rows]
    before = corpus_fingerprints(ids) if (check_corpus and ids) else {}

    payload = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_config}

    status, finish, blocked = "error", None, None
    http_status: Optional[int] = None
    body: Any = None
    latency: Optional[float] = None
    err_type: Optional[str] = None
    err_msg: Optional[str] = None
    try:
        resp, latency = client.generate_content(model, payload)
        http_status = resp.status
        body = resp.json()
        status, finish, blocked = classify(resp, body)
        if status == "error":
            err = (body or {}).get("error") if isinstance(body, dict) else None
            err_type = str((err or {}).get("status") or f"HTTP {resp.status}")
            err_msg = client.redact((err or {}).get("message") or resp.body[:400])
    except Exception as e:                       # transport-level: DNS, TLS, timeout, refusal
        status, err_type, err_msg = "error", type(e).__name__, client.redact(e)
        resp = Response(status=0)

    text = _first_text(body) if isinstance(body, dict) else None
    parsed: Any = None
    schema_ok: Optional[bool] = None
    schema_errors: List[str] = []
    if status == "ok" and response_schema is not None:
        # Asking a provider to honour a schema and CHECKING that it did are two acts. Doing only
        # the first is how "JSON mode" gets reported as working on the strength of the request.
        try:
            parsed = json.loads(text or "")
        except Exception as e:
            schema_ok = False
            schema_errors = [f"response was not JSON: {type(e).__name__}"]
        else:
            errs = _rr.validate(parsed, load_schema(validate_with) if validate_with
                                else response_schema)
            schema_ok = not errs
            schema_errors = errs

    after = corpus_fingerprints(ids) if (check_corpus and ids) else {}
    invariant = None
    if before:
        invariant = {"before": stable_hash(before), "after": stable_hash(after),
                     "unchanged": (before == after and all(v is not None
                                                           for v in before.values()))}

    record: Dict[str, Any] = {
        "call_id": call_id, "lab": LAB, "experiment": experiment,
        "mode": client.mode, "provider": "gemini",
        "endpoint": f"/models/{model}:generateContent", "model": model,
        "prompt_id": (prompt or {}).get("id"),
        "request": _request_summary(text_parts, image_rows, sizes, gen_config, response_schema),
        "outcome": {
            "status": status, "http_status": http_status, "finish_reason": finish,
            "safety_blocked": blocked, "text": text, "json": parsed,
            "json_valid_against_schema": schema_ok, "schema_errors": schema_errors,
            "error_type": err_type, "error_message": err_msg,
        },
        "telemetry": {
            "latency_ms": round(latency, 1) if latency is not None else None,
            "usage": _usage(body),
            "model_version_reported": (body or {}).get("modelVersion")
            if isinstance(body, dict) else None,
            "retry_after_s": _retry_after_seconds(resp, body),
            "rate_limited": (http_status == 429) if http_status is not None else None,
        },
        "epistemic": epistemic_stamp(prompt),
        "corpus_invariant": invariant,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "content_hash": "",
    }
    record["content_hash"] = stable_hash({k: v for k, v in record.items()
                                          if k != "content_hash"})
    return record


def write_call(run_dir: str, record: Mapping[str, Any]) -> str:
    """Validate, then write. In that order, always."""
    assert_not_measured(record)
    errs = validate(record, "gemini-call")
    if errs:
        raise ValidationError(f"refusing to write an invalid call record: {'; '.join(errs)}")
    return write_json(os.path.join(run_dir, "calls", f"{record['call_id']}.json"), record)


# ── the census ────────────────────────────────────────────────────────────────────────────────

def _blank_quota(note: Optional[str] = None) -> Dict[str, Any]:
    """The honest default for every rate limit: no value, and `not_observed` as the source.

    The models endpoint does not report RPM, TPM or daily caps. They are on the account
    dashboard, which is authoritative and which this program cannot read. Filling them in from
    documentation would produce a census file that looks exactly like one taken from the console
    — same shape, same numbers, no way to tell — and the first time the free tier changed, the
    lab would keep reporting last year's ceiling with total confidence.
    """
    return {"value": None, "unit": None, "source": "not_observed", "note": note}


def take_census(client: Optional[GeminiClient] = None) -> Dict[str, Any]:
    """What THIS account offers, from the account. Never from an article.

    Two kinds of fact come back. The models endpoint reports the model list, context limit and
    output limit — those get `models_endpoint`. Everything else it does not report stays null
    with `not_observed`, including image support and JSON mode: the endpoint's
    `supportedGenerationMethods` says `generateContent`, which is not the same claim. Those two
    are promoted to true by `census --from-run`, and only on the evidence of a call that
    actually sent an image or actually held a schema.
    """
    key = api_key()
    census: Dict[str, Any] = {
        "version": "gemini-census.v1",
        "taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "skipped",
        "skipped_reason": None,
        "project": {"key_present": bool(key), "key_fingerprint": key_fingerprint(key)},
        "models": [],
        "quotas": {
            "rpm": _blank_quota("requests per minute — account dashboard only"),
            "tpm": _blank_quota("tokens per minute — account dashboard only"),
            "rpd": _blank_quota("requests per day — account dashboard only"),
            "tpd": _blank_quota("tokens per day — account dashboard only"),
        },
        "retry_after": {"observed": None, "header": None, "body_retry_delay": None,
                        "note": "populated only by an actual 429 recorded in a run"},
        "usage_metadata": {"reported": None, "fields": []},
        "data_use": _blank_quota("whether free-tier prompts train the product — a policy fact "
                                 "about this account, read off the account or not at all"),
    }
    if client is None:
        client = GeminiClient()
    if not client.available:
        census["skipped_reason"] = f"{KEY_ENV} is not set; the account was never contacted"
        return census

    try:
        resp, _latency = client.list_models()
    except Exception as e:
        census["mode"] = "skipped"
        census["skipped_reason"] = f"models endpoint unreachable: {type(e).__name__}: {redact(e)}"
        return census

    if resp.status != 200:
        census["mode"] = "skipped"
        body = resp.json()
        msg = ((body or {}).get("error") or {}).get("message") if isinstance(body, dict) else None
        census["skipped_reason"] = (f"models endpoint returned HTTP {resp.status}: "
                                    f"{redact(msg or resp.body[:200])}")
        return census

    census["mode"] = client.mode
    body = resp.json() or {}
    for m in body.get("models") or []:
        census["models"].append({
            "name": m.get("name"),
            "display_name": m.get("displayName"),
            "version": m.get("version"),
            "input_token_limit": m.get("inputTokenLimit"),
            "output_token_limit": m.get("outputTokenLimit"),
            "supported_generation_methods": list(m.get("supportedGenerationMethods") or []),
            "image_input": None,
            "image_input_evidence": None,
            "json_mode": None,
            "json_mode_evidence": None,
            "observed_from": "models_endpoint",
        })
    return census


def census_from_run(census: Dict[str, Any], run_dir: str) -> Dict[str, Any]:
    """Promote `image_input` and `json_mode` on the evidence of calls that happened.

    This is the only path by which either becomes true, and it names the call_id that did it.
    A capability asserted because the documentation lists it is a capability nobody has seen.
    """
    records = load_run(run_dir)
    for rec in records:
        if rec["outcome"]["status"] != "ok":
            continue
        model = rec.get("model")
        row = next((m for m in census["models"]
                    if m["name"] in (model, f"models/{model}")), None)
        if row is None:
            continue
        if rec["request"]["image_parts"] and row["image_input"] is not True:
            row["image_input"] = True
            row["image_input_evidence"] = rec["call_id"]
            row["observed_from"] = "live_call"
        if rec["outcome"]["json_valid_against_schema"] is True and row["json_mode"] is not True:
            row["json_mode"] = True
            row["json_mode_evidence"] = rec["call_id"]
            row["observed_from"] = "live_call"

    usage_fields = sorted({k for rec in records
                           for k, v in (rec["telemetry"].get("usage") or {}).items()
                           if v is not None})
    if usage_fields:
        census["usage_metadata"] = {"reported": True, "fields": usage_fields}
    limited = [r for r in records if r["telemetry"].get("rate_limited")]
    if limited:
        first = limited[0]
        census["retry_after"] = {
            "observed": first["telemetry"].get("retry_after_s") is not None,
            "header": None,
            "body_retry_delay": (f"{first['telemetry']['retry_after_s']}s"
                                 if first["telemetry"].get("retry_after_s") is not None else None),
            "note": f"from {first['call_id']}, HTTP 429",
        }
    return census


def choose_model(explicit: Optional[str] = None) -> str:
    """The model to call, from the census, or an explicit one.

    Deliberately NO default model name in this file, and the suite checks that none crept in. A
    model name written here is a guess about someone else's product line: it goes stale in
    silence, answers 404, and gets reported as "the free tier is broken". The census is the
    account speaking; if it has not been taken, that is what this says.
    """
    if explicit:
        return explicit.split("/")[-1]
    if not os.path.exists(CENSUS_PATH):
        raise SystemExit("no census — run: python scripts/gemini_vlm_lab.py census\n"
                         "(or pass --model; this lab does not guess a model name)")
    census = read_json(CENSUS_PATH)
    for m in census.get("models") or []:
        if "generateContent" in (m.get("supported_generation_methods") or []):
            return str(m["name"]).split("/")[-1]
    raise SystemExit("the census records no model supporting generateContent")


# ── the six experiments ───────────────────────────────────────────────────────────────────────
#
# Ordered smallest first. Each returns a list of records; each records `unavailable` rather than
# raising when there is no key, so the shape of a keyless run is the shape of a real one with the
# outcomes replaced.

def _observations_for_relations(records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """The observations this run actually produced, flattened for experiment 6.

    Reads THIS RUN's records, not a curated list. Experiment 6 is supposed to operate on what
    the earlier calls really returned, including a thin or a strange one — handing it a tidied
    set would test a pipeline that does not exist.
    """
    out: List[Dict[str, Any]] = []
    for rec in records:
        payload = rec["outcome"].get("json")
        if not isinstance(payload, dict):
            continue
        for obs in payload.get("observations") or []:
            if isinstance(obs, dict):
                out.append({"from_call": rec["call_id"],
                            "image_index": obs.get("image_index"),
                            "quality": obs.get("quality"),
                            "visible_evidence": obs.get("visible_evidence")})
    return out


def experiment(name: str, client: GeminiClient, model: str, corpus: Sequence[Mapping[str, Any]],
               prompts: Mapping[str, Mapping[str, Any]],
               earlier: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    obs_schema = load_schema("visual-observation")
    align_schema = load_schema("hypothesis-alignment")
    rel_schema = load_schema("relation-proposal")
    one = list(corpus[:1])
    three = list(corpus[:3])

    if name == "text_minimal":
        if not client.available:
            return [unavailable_record("01-text_minimal", name, model=model)]
        return [call(client, call_id="01-text_minimal", experiment=name, model=model,
                     text_parts=[PROBE_TEXT], max_output_tokens=32, check_corpus=False)]

    if name == "image_one":
        if not client.available:
            return [unavailable_record("02-image_one", name, model=model)]
        return [call(client, call_id="02-image_one", experiment=name, model=model,
                     text_parts=[OBSERVATION_INSTRUCTION], image_rows=one)]

    if name == "json_strict":
        if not client.available:
            return [unavailable_record("03-json_strict", name, model=model)]
        return [call(client, call_id="03-json_strict", experiment=name, model=model,
                     text_parts=[OBSERVATION_INSTRUCTION], image_rows=one,
                     response_schema=obs_schema, validate_with="visual-observation")]

    if name == "image_three":
        if not client.available:
            return [unavailable_record("04-image_three", name, model=model)]
        return [call(client, call_id="04-image_three", experiment=name, model=model,
                     text_parts=[OBSERVATION_INSTRUCTION], image_rows=three,
                     response_schema=obs_schema, validate_with="visual-observation",
                     max_output_tokens=2048)]

    if name == "hypothesis_alignment":
        # One call per canonical prompt, all four against the same three images, so the only
        # thing that varies between them is the prompt. That is the comparison: what a rich
        # hypothesis, a sparse question, an adversarial claim and a generative ask each do to
        # the same evidence.
        records: List[Dict[str, Any]] = []
        for i, pid in enumerate(("rich", "sparse", "adversarial", "generative"), start=1):
            prompt = prompts[pid]
            cid = f"05-{i}-{pid}"
            if not client.available:
                records.append(unavailable_record(cid, name, model=model, prompt=prompt))
                continue
            records.append(call(
                client, call_id=cid, experiment=name, model=model,
                text_parts=[ALIGNMENT_INSTRUCTION + prompt["text"]],
                image_rows=three, response_schema=align_schema,
                validate_with="hypothesis-alignment", prompt=prompt,
                max_output_tokens=2048))
        return records

    if name == "relation_proposal":
        observations = _observations_for_relations(earlier)
        if not client.available:
            return [unavailable_record("06-relation_proposal", name, model=model)]
        if not observations:
            # An honest empty: there was nothing to relate. Recorded as `empty`, with no call
            # made, rather than sending an empty list and reporting whatever came back.
            rec = unavailable_record("06-relation_proposal", name, model=model,
                                     why="no earlier observations in this run to relate")
            rec["outcome"]["status"] = "empty"
            rec["content_hash"] = stable_hash({k: v for k, v in rec.items()
                                               if k != "content_hash"})
            return [rec]
        listing = "\n".join(f"[{i}] image {o['image_index']}: {o['quality']} — "
                            f"{o['visible_evidence']}" for i, o in enumerate(observations))
        return [call(client, call_id="06-relation_proposal", experiment=name, model=model,
                     text_parts=[RELATION_INSTRUCTION, listing],
                     response_schema=rel_schema, validate_with="relation-proposal",
                     max_output_tokens=2048, check_corpus=False)]

    raise SystemExit(f"unknown experiment {name!r}; known: {', '.join(EXPERIMENTS)}")


# ── runs ──────────────────────────────────────────────────────────────────────────────────────

def new_run_dir(runs_root: str = RUNS_ROOT) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = os.path.join(runs_root, stamp)
    suffix = 1
    while os.path.exists(path):
        suffix += 1
        path = os.path.join(runs_root, f"{stamp}-{suffix}")
    os.makedirs(os.path.join(path, "calls"), exist_ok=True)
    return path


def load_run(run_dir: str) -> List[Dict[str, Any]]:
    calls_dir = os.path.join(run_dir, "calls")
    if not os.path.isdir(calls_dir):
        return []
    return [read_json(os.path.join(calls_dir, fn))
            for fn in sorted(os.listdir(calls_dir)) if fn.endswith(".json")]


def run_experiments(names: Sequence[str], *, client: Optional[GeminiClient] = None,
                    model: Optional[str] = None, runs_root: str = RUNS_ROOT,
                    max_calls: int = MAX_CALLS_PER_RUN,
                    stop_on_rate_limit: bool = True) -> Tuple[str, List[Dict[str, Any]]]:
    """Run the named experiments, write every call, and stop when the tier says stop.

    STOPS ON 429 by default. Continuing past a rate limit would turn one finding — "the free
    tier ran out here, after N calls, and asked for M seconds" — into a run of identical errors
    that buries it.
    """
    client = client if client is not None else GeminiClient()
    resolved_model = model or (choose_model(model) if client.available else "(no model)")
    prompts = load_prompts()
    corpus = load_corpus() if os.path.exists(CORPUS_PATH) else []
    run_dir = new_run_dir(runs_root)
    records: List[Dict[str, Any]] = []

    manifest = {
        "run_id": os.path.basename(run_dir),
        "lab": LAB,
        "mode": client.mode,
        "key_present": client.available,
        "key_fingerprint": key_fingerprint(api_key()),
        "model": resolved_model,
        "experiments_requested": list(names),
        "corpus": [{"post_id": r["post_id"], "sha256": r.get("sha256")} for r in corpus],
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "produces": "interpretive readings only; this lab measures nothing",
    }
    write_json(os.path.join(run_dir, "manifest.json"), manifest)

    for name in names:
        if client.calls >= max_calls:
            print(f"  · stopping before {name}: call budget {max_calls} reached")
            break
        for rec in experiment(name, client, resolved_model, corpus, prompts, records):
            write_call(run_dir, rec)
            records.append(rec)
            print(f"  · {rec['call_id']:<24} {rec['outcome']['status']:<12}"
                  f" http={rec['outcome']['http_status']}"
                  f" schema={rec['outcome']['json_valid_against_schema']}"
                  f" {rec['telemetry']['latency_ms']}ms")
            if stop_on_rate_limit and rec["telemetry"].get("rate_limited"):
                delay = rec["telemetry"].get("retry_after_s")
                print(f"  · rate limited; the tier asked for {delay}s. Stopping — that is the "
                      f"finding.")
                manifest["stopped_at"] = rec["call_id"]
                manifest["stopped_because"] = "rate_limited"
                write_json(os.path.join(run_dir, "manifest.json"), manifest)
                return run_dir, records

    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["calls_made"] = client.calls
    write_json(os.path.join(run_dir, "manifest.json"), manifest)
    return run_dir, records


def replay(run_dir: str) -> List[Dict[str, Any]]:
    """Read a run back and re-validate every record. Makes NO call, and cannot.

    The client is built on `RefusingTransport`, so this is not a promise in a docstring: any
    code path that reached for the network here would raise.
    """
    client = GeminiClient(transport=RefusingTransport(), key=None)
    assert client.mode == "replay"
    records = load_run(run_dir)
    if not records:
        raise SystemExit(f"no calls under {run_dir}")
    for rec in records:
        assert_not_measured(rec)
        errs = validate(rec, "gemini-call")
        if errs:
            raise ValidationError(f"{rec.get('call_id')}: frozen record invalid; "
                                  f"refusing to replay it: {'; '.join(errs)}")
        got = stable_hash({k: v for k, v in rec.items() if k != "content_hash"})
        if got != rec["content_hash"]:
            raise ValidationError(f"{rec['call_id']}: content hash does not match the record "
                                  f"({got[:12]} != {rec['content_hash'][:12]})")
    return records


# ── the report ────────────────────────────────────────────────────────────────────────────────

def latest_run(runs_root: str = RUNS_ROOT) -> Optional[str]:
    if not os.path.isdir(runs_root):
        return None
    dirs = sorted(d for d in os.listdir(runs_root)
                  if os.path.isdir(os.path.join(runs_root, d)))
    return os.path.join(runs_root, dirs[-1]) if dirs else None


def report(run_dir: str) -> str:
    """The matrix. Every column is something observed; there is no score.

    A verdict column would invite a number, and the only honest verdict this lab can reach is
    whether the provider held the contract it was given — which is the `schema` column.
    """
    records = load_run(run_dir)
    manifest = (read_json(os.path.join(run_dir, "manifest.json"))
                if os.path.exists(os.path.join(run_dir, "manifest.json")) else {})
    lines = [
        f"run       {os.path.basename(run_dir)}",
        f"mode      {manifest.get('mode')}"
        + ("" if manifest.get("key_present") else " (key ABSENT — no call was made)")
        + f"   model {manifest.get('model')}",
        "",
        f"{'call':<24} {'outcome':<12} {'http':>5} {'schema':<8} {'finish':<12} "
        f"{'ms':>8} {'tokens':>8}",
        "-" * 84,
    ]
    for rec in records:
        usage = rec["telemetry"].get("usage") or {}
        total = usage.get("total_token_count")
        schema_ok = rec["outcome"]["json_valid_against_schema"]
        lines.append(
            f"{rec['call_id']:<24} {rec['outcome']['status']:<12} "
            f"{str(rec['outcome']['http_status'] or '-'):>5} "
            f"{('-' if schema_ok is None else ('valid' if schema_ok else 'INVALID')):<8} "
            f"{str(rec['outcome']['finish_reason'] or '-'):<12} "
            f"{str(rec['telemetry']['latency_ms'] or '-'):>8} "
            f"{str(total if total is not None else '-'):>8}")
    invalid = [r for r in records if r["outcome"]["json_valid_against_schema"] is False]
    unchanged = [r for r in records if (r.get("corpus_invariant") or {}).get("unchanged") is False]
    lines += [
        "",
        f"calls {len(records)}   ok {sum(1 for r in records if r['outcome']['status'] == 'ok')}"
        f"   unavailable "
        f"{sum(1 for r in records if r['outcome']['status'] == 'unavailable')}"
        f"   schema failures {len(invalid)}",
        f"source posts altered: {'YES — INVESTIGATE' if unchanged else 'no'}",
        "",
        "Every row above is an INTERPRETIVE reading. None of it is a measurement, and none of",
        "it becomes one by agreeing with Qwen, with Groq, or with the person who wrote the",
        "prompt.",
    ]
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────

def _cmd_corpus(args: argparse.Namespace) -> int:
    resolved = resolve_corpus(fetch=not args.no_fetch)
    if args.check:
        if not os.path.exists(CORPUS_PATH):
            print("no corpus.json to check against")
            return 1
        stored = read_json(CORPUS_PATH)
        drift = []
        for old, new in zip(stored["images"], resolved["images"]):
            for field_name in ("photo_url", "sha256", "post_fingerprint"):
                if old.get(field_name) != new.get(field_name):
                    drift.append(f"{old['post_id']}.{field_name}: "
                                 f"{str(old.get(field_name))[:16]} -> "
                                 f"{str(new.get(field_name))[:16]}")
        if drift:
            print("CORPUS DRIFT:")
            for d in drift:
                print("  ", d)
            return 1
        print(f"corpus unchanged — {len(stored['images'])} posts, same URLs, same bytes, "
              f"same documents")
        return 0
    write_json(CORPUS_PATH, resolved)
    for row in resolved["images"]:
        print(f"  {row['post_id']}  {'ok' if row['resolved'] else 'UNRESOLVED'}  "
              f"{(row.get('sha256') or '-')[:12]}  {row.get('bytes') or '-'} bytes"
              f"{'' if row['resolved'] else '  ' + str(row.get('why'))}")
    print(f"wrote {os.path.relpath(CORPUS_PATH, REPO_ROOT)}")
    return 0


def _cmd_census(args: argparse.Namespace) -> int:
    census = take_census()
    if args.from_run:
        run_dir = (args.from_run if os.path.isdir(args.from_run)
                   else os.path.join(RUNS_ROOT, args.from_run))
        census = census_from_run(census, run_dir)
    errs = validate(census, "gemini-census")
    if errs:
        raise ValidationError(f"refusing to write an invalid census: {'; '.join(errs)}")
    write_json(CENSUS_PATH, census)
    print(f"mode: {census['mode']}")
    if census.get("skipped_reason"):
        print(f"skipped: {census['skipped_reason']}")
    for m in census["models"]:
        print(f"  {m['name']:<44} in={m['input_token_limit']} out={m['output_token_limit']} "
              f"img={m['image_input']} json={m['json_mode']}")
    print("  quotas (rpm/tpm/rpd/tpd): "
          + ", ".join(f"{k}={census['quotas'][k]['value']}({census['quotas'][k]['source']})"
                      for k in ("rpm", "tpm", "rpd", "tpd")))
    print(f"wrote {os.path.relpath(CENSUS_PATH, REPO_ROOT)}")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    for i, name in enumerate(EXPERIMENTS, start=1):
        print(f"  {i}. {name}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    names = list(EXPERIMENTS) if args.all else [args.experiment]
    if not api_key():
        print(f"{KEY_ENV} is not set — recording every experiment as `unavailable`.")
    run_dir, _records = run_experiments(names, model=args.model, max_calls=args.max_calls)
    print(f"\nrun {os.path.relpath(run_dir, REPO_ROOT)}")
    print(report(run_dir))
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    run_dir = (args.run if os.path.isdir(args.run) else os.path.join(RUNS_ROOT, args.run))
    records = replay(run_dir)
    print(f"replayed {len(records)} calls from {os.path.basename(run_dir)}; "
          f"no network was reached")
    print(report(run_dir))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    run_dir = ((args.run if os.path.isdir(args.run) else os.path.join(RUNS_ROOT, args.run))
               if args.run else latest_run())
    if not run_dir:
        print("no runs yet")
        return 1
    print(report(run_dir))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("corpus", help="resolve the three posts, read-only")
    c.add_argument("--check", action="store_true",
                   help="re-resolve and fail on any drift instead of writing")
    c.add_argument("--no-fetch", action="store_true", help="URLs only; do not download bytes")
    c.set_defaults(fn=_cmd_corpus)

    c = sub.add_parser("census", help="what this account actually offers")
    c.add_argument("--from-run", default=None,
                   help="promote image/JSON support from a run's evidence")
    c.set_defaults(fn=_cmd_census)

    sub.add_parser("list", help="the six experiments").set_defaults(fn=_cmd_list)

    c = sub.add_parser("run", help="run one experiment")
    c.add_argument("--experiment", choices=EXPERIMENTS, required=True)
    c.add_argument("--model", default=None, help="override the census's model choice")
    c.add_argument("--max-calls", type=int, default=MAX_CALLS_PER_RUN)
    c.set_defaults(fn=_cmd_run, all=False)

    c = sub.add_parser("run-all", help="all six, smallest first, stopping on a 429")
    c.add_argument("--model", default=None)
    c.add_argument("--max-calls", type=int, default=MAX_CALLS_PER_RUN)
    c.set_defaults(fn=_cmd_run, all=True, experiment=None)

    c = sub.add_parser("replay", help="re-read a run; makes no call")
    c.add_argument("--run", required=True)
    c.set_defaults(fn=_cmd_replay)

    c = sub.add_parser("report", help="the matrix for a run")
    c.add_argument("--run", default=None)
    c.set_defaults(fn=_cmd_report)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args))
    except ValidationError as e:
        print(f"refused: {redact(e)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
