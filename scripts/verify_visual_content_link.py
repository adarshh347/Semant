"""
Verification — Visual↔Content integration, backend half.

Two claims the frontend integration rests on, neither of which held before this pass:

  1. A block's `origin` survives a save. The editor has stamped `origin: 'sutradhar'`
     on generated blocks since the slash lane, but `TextBlock` had no such field, so
     Pydantic dropped it and every AI block came back from the server looking human.

  2. The writer the editor calls is grounded. Track C wired the Anuraṇana context pack
     into `/chat/vision`, `/rewrite/vision` and `/flow/expand-node` — but `/draft`,
     `/write` and "write about this part" all go through the *epics* vision endpoints,
     which never received a pack. "Write about this part with the region's reading and
     note as context" was simply false.

Both are proved against the real code paths (the routers, not a re-implementation) on a
throwaway fixture post, which is deleted again even when an assertion fails.

    python scripts/verify_visual_content_link.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import post_collection                      # noqa: E402
from backend.schemas.post import TextBlock, PostUpdate            # noqa: E402
from backend.schemas.epic import VisionSuggestionRequest          # noqa: E402
from backend.services import vision_service as vision_mod         # noqa: E402
from backend.services.editor_llm_service import GROUNDING_PREAMBLE  # noqa: E402
from backend.routers import epics                                 # noqa: E402

MARKER = "verify-visual-content-link"
FIXTURE_URL = f"https://example.invalid/{MARKER}.jpg"
NOTE = "the hem hangs like a held breath"
LENS_READING = "the garment withholds more than it shows"

ok = 0
fail = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  PASS  {label}")
    else:
        fail += 1
        print(f"  FAIL  {label}" + (f"\n          {detail}" if detail else ""))


# --- 1. block provenance survives the save path -------------------------------------
def verify_origin_roundtrip() -> None:
    print("\n[1] `origin` survives TextBlock / PostUpdate")

    raw = {"id": "block_1", "type": "paragraph", "content": "x", "origin": "sutradhar"}

    block = TextBlock(**raw)
    check("TextBlock keeps origin", block.origin == "sutradhar", f"got {block.origin!r}")

    dumped = block.model_dump()
    check("model_dump emits origin", dumped.get("origin") == "sutradhar", f"got {dumped}")

    # This is the exact path PATCH /posts/{id} takes.
    update = PostUpdate(text_blocks=[raw])
    persisted = update.model_dump(exclude_unset=True)["text_blocks"][0]
    check("PostUpdate round-trip keeps origin",
          persisted.get("origin") == "sutradhar", f"got {persisted}")

    default = TextBlock(id="b", type="paragraph", content="x")
    check("a block with no origin defaults to human", default.origin == "human")


# --- 2. the editor's writer is grounded ---------------------------------------------
async def make_fixture() -> str:
    doc = {
        "photo_url": FIXTURE_URL,
        "photo_public_id": MARKER,
        "text_blocks": [],
        "region_annotations": [{
            "id": "reg_fixture_hem", "actor": "creator", "detector": None,
            "box": {"x": 0.1, "y": 0.6, "w": 0.3, "h": 0.2},
            "label": "hem", "category": "garment", "material": "linen",
            "description": "", "attributes": [], "depth": 0,
            "prioritised": True, "weight": 80, "user_note": NOTE,
        }],
        "local_context": {"aletheia": {
            "lenses": [{"name": "Concealment", "intensity": 70,
                        "reading": LENS_READING, "region_ids": ["reg_fixture_hem"]}],
            "tension": "", "concealed": "",
        }},
    }
    res = await post_collection.insert_one(doc)
    return str(res.inserted_id)


async def cleanup() -> None:
    await post_collection.delete_many({"photo_public_id": MARKER})


class PromptSpy:
    """Stands in for the Groq call and records the prompt the router built."""

    def __init__(self):
        self.prompt = None

    async def analyze_image(self, image_url, prompt, **_):
        self.prompt = prompt
        return "generated text"


async def call_endpoint(kind: str, image_url: str, spy: PromptSpy) -> None:
    svc = vision_mod.vision_service
    orig_analyze, orig_avail = svc.analyze_image, svc._is_available
    svc.analyze_image = spy.analyze_image
    svc._is_available = lambda: True
    try:
        if kind == "prompt_enhance":
            req = VisionSuggestionRequest(image_url=image_url, suggestion_type="prompt_enhance",
                                          user_prompt="Write about the hem.")
            await epics.vision_prompt_enhance(req)
        else:
            req = VisionSuggestionRequest(image_url=image_url, suggestion_type="auto_recommend",
                                          existing_text="")
            await epics.vision_auto_recommend(req)
    finally:
        svc.analyze_image, svc._is_available = orig_analyze, orig_avail


async def verify_grounding() -> None:
    print("\n[2] the editor's writer receives the Anuraṇana pack")

    for kind in ("prompt_enhance", "auto_recommend"):
        spy = PromptSpy()
        await call_endpoint(kind, FIXTURE_URL, spy)
        p = spy.prompt or ""
        check(f"/{kind}: pack is prepended", GROUNDING_PREAMBLE in p)
        check(f"/{kind}: the curator's note reaches the writer", NOTE in p,
              "the region's user_note is absent from the prompt")
        check(f"/{kind}: the reading reaches the writer", LENS_READING in p,
              "the Aletheia lens reading is absent from the prompt")
        check(f"/{kind}: the caller's ask survives at the tail",
              p.rstrip().endswith("Generate the text:"))

    print("\n[3] an image we don't own degrades to the pre-Track-C writer")
    spy = PromptSpy()
    await call_endpoint("prompt_enhance", "https://example.invalid/not-ours.jpg", spy)
    p = spy.prompt or ""
    check("unknown image: no pack, no preamble", GROUNDING_PREAMBLE not in p)
    check("unknown image: prompt still built", "Write about the hem." in p)


async def main() -> int:
    verify_origin_roundtrip()
    try:
        await make_fixture()
        await verify_grounding()
    finally:
        await cleanup()
        left = await post_collection.count_documents({"photo_public_id": MARKER})
        check("fixture removed", left == 0, f"{left} fixture doc(s) still in the DB")

    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
