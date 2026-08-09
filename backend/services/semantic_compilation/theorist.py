"""
HARNESS-002A §3 — the scene theorist: the general VLM intelligence the stack did not have.

Everything else that looks at a picture in this system is an INSTRUMENT — a segmenter, a depth
model, an organ standing on a region. This role is a scout and a theorist: it reads the prompt and
the pictures together and says as much as a good contemporary VLM can say about what is going on in
them. That abundance is the point. The rest of the lane exists to make it inspectable rather than to
make it small.

WHAT IT MAY NOT DO, enforced here rather than asked for in the prompt:

  · author a mask, box, point, polygon, coordinate, region id or confidence. The parser is an
    ALLOWLIST — a key the reading schema does not declare has nowhere to go — and any forbidden key
    found anywhere in the raw payload is RECORDED as a refusal, with the block carrying it dropped
    rather than stripped. A stripped key is a model authoring geometry, silently;
  · claim any status stronger than `interpretive`. `SceneReading` freezes the field;
  · be substituted for. An unavailable model produces an empty reading and a named refusal. There
    is deliberately no canned reading anywhere in this module, because a plausible default is
    indistinguishable from a real one and would be believed.

CALL TOPOLOGY IS RECORDED, NOT ASSUMED. Every existing Groq multimodal call site in this repo
(`vision_service.analyze_image`, `editor_llm_service.chat_with_vision`, `rewrite_with_vision`)
sends exactly ONE image per request. So a joint view of several pictures is not something this lane
gets to assume: with more than one image it runs a bounded per-image reading plus one cross-image
synthesis, and the receipt says `per_image_then_synthesis` with the real call count. Three separate
looks plus a summary is not a joint view of three pictures, and a receipt that said otherwise would
be describing a comparison nobody made.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.schemas.semantic_compilation import (CallTopology, CompilerRefusal,
                                                  CompilerRefusalKind, ImageRef, ModelReceipt,
                                                  ReadingBlock, ReadingBlockKind, SceneReading)
from backend.services import role_registry

from . import contracts, ids
from .base import ReadingResult, refusal, sha256_of, unavailable_receipt

ROLE = "scene_theorist"
PRODUCER = "semantic_compilation/theorist-v1"

#: A bounded per-image reading, and the bound is stated. More images than this and the overflow is
#: NAMED in the receipt notes rather than quietly dropped — a silent cap reads downstream as "the
#: theorist looked at everything and found nothing there".
MAX_IMAGES = 6

#: More blocks than this is the model padding rather than reading. Applied after parsing; the
#: overflow is reported.
MAX_BLOCKS = 40

SYSTEM_PROMPT = (
    "You are a scene theorist inside a visual close-reading tool. You are shown one or more "
    "images and a person's question about them, and you produce an abundant PROVISIONAL READING: "
    "what parts you see, how they are organised, what compares or contrasts with what, what "
    "historical or cultural associations they suggest, what is in tension, and what generative "
    "hypotheses follow. Be generous and specific. You output JSON and nothing else.\n\n"
    "You are a THEORIST, not an instrument. Hard rules:\n"
    "- Never output a mask, bounding box, point, polygon, coordinate, pixel count, area, region "
    "id, mark id, or a confidence/score value. You are not measuring anything. Another part of "
    "this system measures, and it will refuse a reading that tries to do its job.\n"
    "- Never say that something has been measured, detected or established. Everything you say is "
    "a reading, and it is treated as one.\n"
    "- Speak about what you can see. If a claim rests on knowledge from outside the picture — a "
    "period, a school, an influence — put it in a `historical_association` block so it is not "
    "mistaken for something the image shows.\n"
    "- Do not answer the person's question. Read the pictures for whoever will answer it.\n"
    "- Say what is UNCERTAIN or in tension. A reading with no tensions in it is a reading that has "
    "stopped looking."
)

#: The shape the model must return. Sent as an example rather than described, for the reason
#: `groq_planner` gives: a closed set should be typed as one, because prose invites paraphrase.
_OUTPUT_SHAPE = (
    '{"reading": "<several paragraphs of provisional reading>", '
    '"blocks": [{"kind": "<one of the block kinds>", '
    '"text": "<one specific observation, comparison, association, tension or hypothesis>", '
    '"images": ["<post_id this block is about; omit or list several>"]}]}'
)


def build_prompt(prompt: str, images: Sequence[ImageRef],
                 corpus: Optional[Mapping[str, Any]] = None) -> str:
    """The user-side message. The person's prompt is included VERBATIM and labelled as theirs."""
    catalog = [{"post_id": i.post_id, "title": i.title, "note": i.note} for i in images]
    return (
        f"THE PERSON'S QUESTION, verbatim. Do not answer it; read the pictures for whoever will:\n"
        f"{prompt}\n\n"
        f"THE IMAGES you are being shown, in this order:\n{json.dumps(catalog, indent=2)}\n\n"
        + (f"CORPUS NOTES:\n{json.dumps(dict(corpus), indent=2)}\n\n" if corpus else "")
        + f"BLOCK KINDS — use only these:\n"
          f"{json.dumps(list(contracts.closed_set('reading_block_kinds')))}\n\n"
          f"Return JSON of exactly this shape:\n{_OUTPUT_SHAPE}\n"
          f"Return an empty `blocks` list rather than inventing content."
    )


def build_synthesis_prompt(prompt: str, per_image: Sequence[Tuple[ImageRef, str]]) -> str:
    """The cross-image call. TEXT ONLY — it is handed the readings, never the pictures again.

    This is the honest half of `per_image_then_synthesis`: the comparison is made from separate
    looks, and the object that makes it can say so because it never saw two images at once either.
    """
    sections = "\n\n".join(f"IMAGE {ref.post_id} ({ref.title or 'untitled'}):\n{text}"
                           for ref, text in per_image)
    return (
        f"THE PERSON'S QUESTION, verbatim:\n{prompt}\n\n"
        f"You have already read each image SEPARATELY. You are not being shown them again. Below "
        f"are your own readings. Produce only the CROSS-IMAGE blocks — comparisons, tensions, "
        f"shared or divergent organisation, historical associations that only appear across them, "
        f"and generative hypotheses. Do not repeat single-image observations.\n\n"
        f"{sections}\n\n"
        f"BLOCK KINDS — use only these:\n"
        f"{json.dumps(list(contracts.closed_set('reading_block_kinds')))}\n\n"
        f"Return JSON of exactly this shape:\n{_OUTPUT_SHAPE}"
    )


# ── parsing ──────────────────────────────────────────────────────────────────

def _text(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def parse_blocks(inquiry_id: str, payload: Any, images: Sequence[ImageRef],
                 *, source: str = "") -> Tuple[List[ReadingBlock], List[CompilerRefusal],
                                               List[str]]:
    """Raw model JSON → reading blocks, plus every refusal along the way.

    Tolerant of SHAPE, strict about CONTENT — the split `parse_steps` and `parse_claims` both make.
    A missing `images` list, an integer where a string belongs, a block that is not an object: all
    survivable. An invented block kind, a geometry key, an image this corpus does not hold: none is
    corrected, all are refused by name.
    """
    refusals: List[CompilerRefusal] = []
    notes: List[str] = []
    blocks: List[ReadingBlock] = []
    known_ids = {i.post_id for i in images}
    declared = set(contracts.closed_set("reading_block_kinds"))

    raw = payload.get("blocks") if isinstance(payload, Mapping) else None
    rows = [r for r in raw if isinstance(r, Mapping)] if isinstance(raw, list) else []

    for index, row in enumerate(rows):
        where = f"{source}block {index}" if source else f"block {index}"

        found = contracts.geometry_keys_in(row)
        if found:
            # DROPPED, not stripped. The block's prose might be perfectly good; keeping it would
            # mean a model that tried to author geometry got its reading published anyway, and the
            # only record of the attempt would be a line in a refusal list nobody diffs.
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(found),
                "a scene reading may not carry geometry, a region id or a confidence. The theorist "
                "is a thinker: it may say a thing is there and may not say where, in numbers. The "
                "block carrying these keys was dropped rather than stripped.",
                detail=[where, _text(row.get("text"))[:160]]))
            continue

        text = _text(row.get("text")) or _text(row.get("observation"))
        if not text:
            continue

        kind = _text(row.get("kind")).lower()
        if kind not in declared:
            refusals.append(refusal(
                inquiry_id, CompilerRefusalKind.UNKNOWN_READING_BLOCK_KIND, kind or "(empty)",
                f"not one of {sorted(declared)}. Refused by name rather than coerced to the "
                f"nearest-looking kind: a `hypothesis` filed as an `organization` reads as "
                f"something the theorist saw.",
                detail=[where, text[:160]]))
            continue

        refs: List[str] = []
        for candidate in row.get("images") or row.get("image_refs") or ():
            candidate = str(candidate).strip()
            if not candidate:
                continue
            if candidate not in known_ids:
                refusals.append(refusal(
                    inquiry_id, CompilerRefusalKind.DANGLING_REFERENCE, candidate,
                    "the reading names an image this corpus does not hold. The reference was "
                    "dropped; the block was kept, because the observation may still be about one "
                    "of the images it was shown.",
                    detail=[where]))
                continue
            if candidate not in refs:
                refs.append(candidate)

        blocks.append(ReadingBlock(block_id=ids.block_id(inquiry_id, kind, text),
                                   kind=ReadingBlockKind(kind), text=text, image_refs=refs))

    # A model repeats itself across a per-image sweep. Two identical blocks are one block, and the
    # id is content-derived so the collapse is exact rather than approximate.
    seen: Dict[str, ReadingBlock] = {}
    for block in blocks:
        if block.block_id in seen:
            merged = sorted(set(seen[block.block_id].image_refs) | set(block.image_refs))
            seen[block.block_id] = seen[block.block_id].model_copy(update={"image_refs": merged})
            continue
        seen[block.block_id] = block
    deduped = list(seen.values())
    if len(deduped) < len(blocks):
        notes.append(f"the theorist repeated {len(blocks) - len(deduped)} block(s); identical "
                     f"blocks were merged and their image references unioned")

    if len(deduped) > MAX_BLOCKS:
        notes.append(f"the theorist returned {len(deduped)} blocks; kept the first {MAX_BLOCKS}")
        deduped = deduped[:MAX_BLOCKS]
    return deduped, refusals, notes


def build_reading(inquiry_id: str, payload: Any, images: Sequence[ImageRef],
                  receipt: ModelReceipt, *, extra_text: str = "",
                  source: str = "") -> ReadingResult:
    """One raw payload → a `ReadingResult`. The single parse path, shared by replay and live."""
    refusals: List[CompilerRefusal] = []
    notes: List[str] = []

    if not isinstance(payload, Mapping):
        refusals.append(refusal(
            inquiry_id, CompilerRefusalKind.UNPARSEABLE_MODEL_OUTPUT, type(payload).__name__,
            "the theorist returned something that is not a JSON object. Nothing in it was used and "
            "nothing was invented in its place."))
        return ReadingResult(
            reading=SceneReading(text="", image_refs=list(images),
                                 provenance=receipt.model_copy(update={"parsed": False})),
            refusals=tuple(refusals),
            notes=("the reading is empty because the model output could not be read",))

    top_level = contracts.geometry_keys_in(
        {k: v for k, v in payload.items() if k not in {"blocks"}})
    if top_level:
        refusals.append(refusal(
            inquiry_id, CompilerRefusalKind.GEOMETRY_IN_A_READING, ", ".join(top_level),
            "the theorist put geometry at the top level of its reading. The keys were refused; the "
            "reading's prose was kept because it is not where the geometry was.",
            detail=[source or "payload"]))

    blocks, block_refusals, block_notes = parse_blocks(inquiry_id, payload, images, source=source)
    refusals.extend(block_refusals)
    notes.extend(block_notes)

    text = _text(payload.get("reading")) or _text(payload.get("text"))
    if extra_text:
        text = f"{extra_text}\n\n{text}".strip() if text else extra_text

    if not text and not blocks:
        notes.append("the theorist returned an empty reading. That is a valid answer and it was "
                     "NOT replaced by a default.")

    return ReadingResult(
        reading=SceneReading(text=text, blocks=blocks, image_refs=list(images),
                             provenance=receipt.model_copy(update={"parsed": True})),
        refusals=tuple(refusals), notes=tuple(notes))


# ── the replay implementation ────────────────────────────────────────────────

class FrozenSceneTheorist:
    """Replays a frozen model payload through the production parser.

    NOT a fake reading — a real one, produced once by a model and kept. The distinction matters:
    this class contains no prose of its own, so a fixture that stopped resembling what the model
    actually returns is a visible edit to a JSON file rather than a drift inside a stub.
    """

    name = "replay"

    def __init__(self, payload: Any, *, model: Optional[str] = None,
                 topology: CallTopology = CallTopology.REPLAY, call_count: int = 0):
        self._payload = payload
        self._model = model
        self._topology = topology
        self._call_count = call_count

    def read(self, prompt: str, images: Sequence[ImageRef], *, inquiry_id: str,
             corpus: Optional[Mapping[str, Any]] = None,
             now: Optional[str] = None) -> ReadingResult:
        receipt = ModelReceipt(
            role=ROLE, model=self._model, provider=None,
            prompt_sha256=sha256_of(build_prompt(prompt, images, corpus)),
            image_refs=[i.post_id for i in images], requested_at=now,
            raw_response_sha256=[sha256_of(json.dumps(self._payload, sort_keys=True,
                                                      ensure_ascii=False))],
            call_count=self._call_count, call_topology=self._topology,
            notes=["replayed from a frozen model output; no network call was made"])
        return build_reading(inquiry_id, self._payload, images, receipt)


# ── the live implementation ──────────────────────────────────────────────────

class ModelSceneTheorist:
    """One VLM, bounded calls, receipts kept, and no fallback anywhere.

    `client` is injectable so the class is testable with no network. Shaped like `GroqPlanner` and
    `ModelInquiryFramer` on purpose: `calls` is observable so the topology can be asserted rather
    than trusted.
    """

    name = "model"

    def __init__(self, client: Any = None, *, model: Optional[str] = None,
                 max_images: int = MAX_IMAGES, reasoning_effort: Optional[str] = "none"):
        self._client = client
        self._client_resolved = client is not None
        self._model = model
        self.max_images = max_images
        # `vision_service` documents why: qwen3.6-27b is a reasoning model and, left alone, emits an
        # unclosed <think> block that eats the whole token budget before any JSON appears.
        self._reasoning_effort = reasoning_effort
        self.calls: int = 0
        self.truncated_calls: int = 0
        self.last_finish_reason: str = ""
        self.last_notes: Tuple[str, ...] = ()

    @property
    def model(self) -> Optional[str]:
        return self._model if self._model is not None else role_registry.model_for(ROLE)

    def _get_client(self) -> Any:
        if self._client_resolved:
            return self._client
        self._client_resolved = True
        try:
            from groq import Groq

            from backend.config import settings
            self._client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
        except Exception:
            self._client = None
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    # ── one call ──
    def _call(self, content: Any) -> str:
        self.calls += 1
        kwargs: Dict[str, Any] = {
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": content}],
            "model": self.model,
            "response_format": {"type": "json_object"},
        }
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        completion = self._get_client().chat.completions.create(**kwargs)
        choice = completion.choices[0]
        self.last_finish_reason = str(getattr(choice, "finish_reason", "") or "")
        if self.last_finish_reason == "length":
            # Recorded, never silently accepted. A reading cut off mid-sentence that still parses
            # is a SHORT reading, and a short reading is indistinguishable from a picture with
            # little in it unless something says which happened.
            self.truncated_calls += 1
        return choice.message.content or ""

    def read(self, prompt: str, images: Sequence[ImageRef], *, inquiry_id: str,
             corpus: Optional[Mapping[str, Any]] = None,
             now: Optional[str] = None) -> ReadingResult:
        images = list(images)
        prompt_hash = sha256_of(build_prompt(prompt, images, corpus))

        if not images:
            # A scene reading with no scene is not a reading. No call is made, and the state is
            # named `text_only` so it stays distinguishable from a model that was down.
            receipt = unavailable_receipt(
                ROLE, "no images were selected, so nothing was read and no call was made",
                model=self.model, provider="groq", prompt_sha256=prompt_hash, now=now)
            return ReadingResult(
                reading=SceneReading(provenance=receipt.model_copy(
                    update={"call_topology": CallTopology.TEXT_ONLY})),
                refusals=(refusal(
                    inquiry_id, CompilerRefusalKind.READING_UNAVAILABLE, "no images",
                    "a scene reading needs a scene. Nothing was read and nothing was invented in "
                    "its place; the compilation continues from the prompt and the frame alone."),),
                notes=("no images were selected",))

        if not self.is_available():
            receipt = unavailable_receipt(
                ROLE, "the scene theorist is unavailable (no client or API key)",
                model=self.model, provider="groq", prompt_sha256=prompt_hash, images=images,
                now=now)
            return ReadingResult(
                reading=SceneReading(image_refs=images, provenance=receipt),
                refusals=(refusal(
                    inquiry_id, CompilerRefusalKind.READING_UNAVAILABLE, ROLE,
                    "no client or API key. The reading is empty and says so. There is no canned "
                    "reading in this module: a plausible default is indistinguishable from a real "
                    "one and would be believed."),),
                notes=("the scene theorist was unavailable",))

        kept, dropped = images[:self.max_images], images[self.max_images:]
        notes: List[str] = []
        if dropped:
            notes.append(f"the reading is bounded at {self.max_images} images; not read: "
                         + ", ".join(i.post_id for i in dropped))

        if len(kept) == 1:
            return self._single(prompt, kept, corpus, inquiry_id, now, prompt_hash, notes)
        return self._per_image(prompt, kept, corpus, inquiry_id, now, prompt_hash, notes)

    # ── one image: a genuine single joint view ──
    def _single(self, prompt: str, images: List[ImageRef], corpus: Optional[Mapping[str, Any]],
                inquiry_id: str, now: Optional[str], prompt_hash: str,
                notes: List[str]) -> ReadingResult:
        content = [{"type": "text", "text": build_prompt(prompt, images, corpus)},
                   {"type": "image_url", "image_url": {"url": images[0].image_ref}}]
        try:
            raw = self._call(content)
            payload = json.loads(raw)
        except Exception as exc:
            return self._failed(inquiry_id, images, prompt_hash, now, exc,
                                CallTopology.SINGLE_JOINT_CALL, notes)
        receipt = ModelReceipt(
            role=ROLE, model=self.model, provider="groq", prompt_sha256=prompt_hash,
            image_refs=[i.post_id for i in images], requested_at=now,
            raw_response_sha256=[sha256_of(raw)], call_count=self.calls,
            call_topology=CallTopology.SINGLE_JOINT_CALL,
            # TYPED, for 003B's field route. The note stays too: removing it would break the
            # fallback for anything still reading notes, and a field plus a note cannot disagree
            # because both are written from the same variable.
            finish_reason=self.last_finish_reason or None,
            notes=list(notes) + self._truncation_notes() + [_NO_BYTES_NOTE])
        result = build_reading(inquiry_id, payload, images, receipt)
        return ReadingResult(result.reading, result.refusals, tuple(notes) + result.notes)

    # ── several images: separate looks, then a synthesis that says so ──
    def _per_image(self, prompt: str, images: List[ImageRef],
                   corpus: Optional[Mapping[str, Any]], inquiry_id: str, now: Optional[str],
                   prompt_hash: str, notes: List[str]) -> ReadingResult:
        hashes: List[str] = []
        refusals: List[CompilerRefusal] = []
        per_image: List[Tuple[ImageRef, str]] = []
        payloads: List[Tuple[str, Any]] = []

        for image in images:
            content = [{"type": "text", "text": build_prompt(prompt, [image], corpus)},
                       {"type": "image_url", "image_url": {"url": image.image_ref}}]
            try:
                raw = self._call(content)
                payload = json.loads(raw)
            except Exception as exc:
                refusals.append(refusal(
                    inquiry_id, CompilerRefusalKind.READING_UNAVAILABLE, image.post_id,
                    f"the theorist failed on this image: {type(exc).__name__}. The other images "
                    f"were still read, and this one is absent rather than guessed."))
                continue
            hashes.append(sha256_of(raw))
            payloads.append((image.post_id, payload))
            if isinstance(payload, Mapping):
                per_image.append((image, _text(payload.get("reading"))
                                  or _text(payload.get("text"))))

        if not payloads:
            receipt = unavailable_receipt(
                ROLE, "every per-image reading failed", model=self.model, provider="groq",
                prompt_sha256=prompt_hash, images=images, now=now)
            return ReadingResult(
                reading=SceneReading(image_refs=images, provenance=receipt.model_copy(
                    update={"call_count": self.calls,
                            "call_topology": CallTopology.PER_IMAGE_THEN_SYNTHESIS})),
                refusals=tuple(refusals), notes=tuple(notes))

        synthesis: Any = {}
        if per_image:
            try:
                raw = self._call(build_synthesis_prompt(prompt, per_image))
                synthesis = json.loads(raw)
                hashes.append(sha256_of(raw))
            except Exception as exc:
                refusals.append(refusal(
                    inquiry_id, CompilerRefusalKind.READING_UNAVAILABLE, "cross-image synthesis",
                    f"the cross-image synthesis failed: {type(exc).__name__}. The per-image "
                    f"readings stand; nothing across them was written."))

        # The merged payload runs through the SAME parser as everything else. Per-image blocks are
        # stamped with the image they came from, because a block parsed out of a single-image call
        # is about that image whether or not the model bothered to say so.
        merged_blocks: List[Dict[str, Any]] = []
        sections: List[str] = []
        by_id = {i.post_id: i for i in images}
        for post_id, payload in payloads:
            for row in (payload.get("blocks") or ()) if isinstance(payload, Mapping) else ():
                if isinstance(row, Mapping):
                    merged_blocks.append({**row, "images": [post_id]})
            text = _text(payload.get("reading")) if isinstance(payload, Mapping) else ""
            text = text or (_text(payload.get("text")) if isinstance(payload, Mapping) else "")
            if text:
                title = by_id[post_id].title or "untitled"
                sections.append(f"[{post_id} — {title}]\n{text}")
        if isinstance(synthesis, Mapping):
            for row in synthesis.get("blocks") or ():
                if isinstance(row, Mapping):
                    merged_blocks.append(row)
            across = _text(synthesis.get("reading")) or _text(synthesis.get("text"))
            if across:
                sections.append(f"[across the images — written from the readings above, not from a "
                                f"second look]\n{across}")

        receipt = ModelReceipt(
            role=ROLE, model=self.model, provider="groq", prompt_sha256=prompt_hash,
            image_refs=[i.post_id for i in images], requested_at=now,
            raw_response_sha256=hashes, call_count=self.calls,
            call_topology=CallTopology.PER_IMAGE_THEN_SYNTHESIS,
            # The sweep's LAST reason. `truncated_calls` is the honest count across the sweep and
            # is what 003B's producer-attribute route reads; a single field over many calls would
            # report the last one as if it spoke for all of them, so both travel.
            finish_reason=self.last_finish_reason or None,
            notes=list(notes) + [
                f"{len(payloads)} per-image reading(s) plus "
                f"{'one' if isinstance(synthesis, Mapping) and synthesis else 'no'} cross-image "
                f"synthesis. The images were never in one request together, and the comparison was "
                f"made from the readings rather than from a second look.",
                *self._truncation_notes(), _NO_BYTES_NOTE])
        result = build_reading(inquiry_id, {"reading": "\n\n".join(sections),
                                            "blocks": merged_blocks}, images, receipt)
        return ReadingResult(result.reading, tuple(refusals) + result.refusals,
                             tuple(notes) + result.notes)

    def _truncation_notes(self) -> List[str]:
        """A reading cut off by the token budget is a SHORT reading, and a short reading is
        indistinguishable from a picture with little in it unless the receipt says which."""
        if not self.truncated_calls:
            return []
        return [f"{self.truncated_calls} call(s) stopped on the output budget rather than "
                f"finishing. What came back is a PREFIX; a thin reading here is not evidence that "
                f"there was little to see."]

    def _failed(self, inquiry_id: str, images: List[ImageRef], prompt_hash: str,
                now: Optional[str], exc: BaseException, topology: CallTopology,
                notes: List[str]) -> ReadingResult:
        receipt = unavailable_receipt(
            ROLE, f"the scene theorist failed: {type(exc).__name__}", model=self.model,
            provider="groq", prompt_sha256=prompt_hash, images=images, now=now)
        return ReadingResult(
            reading=SceneReading(image_refs=images, provenance=receipt.model_copy(
                update={"call_count": self.calls, "call_topology": topology})),
            refusals=(refusal(
                inquiry_id, CompilerRefusalKind.READING_UNAVAILABLE, type(exc).__name__,
                "the reading failed and was not replaced. The compilation continues from the "
                "prompt and the frame alone, and the graph says the reading is missing."),),
            notes=tuple(notes))


#: Stated on every live receipt. `image_sha256` stays EMPTY rather than being filled with a hash of
#: the URL string: a field called `image_sha256` holding the digest of a URL is worse than an empty
#: one, because it looks like the picture was fingerprinted and it was not.
_NO_BYTES_NOTE = ("no image bytes passed through this process — the transport was handed URLs, so "
                  "`image_sha256` is empty rather than holding a hash of the reference string")


__all__ = ["ROLE", "PRODUCER", "MAX_IMAGES", "MAX_BLOCKS", "SYSTEM_PROMPT", "build_prompt",
           "build_synthesis_prompt", "parse_blocks", "build_reading", "FrozenSceneTheorist",
           "ModelSceneTheorist"]
