"""
Semant Writer W1 — quarantined passages, and the Accept gate.

INVARIANT 1, IN ONE SENTENCE: a rendered passage is born `committed: False` and the ONLY
thing that can change that is the author calling `accept`. There is no auto-commit path
in this module, no "high confidence" shortcut, and no code anywhere in the Writer that
writes prose into a scene except `accept` — which is why the write goes through
`manuscript_service.update_scene`, the canon owner from WS-0A, rather than touching
`scene_collection` directly. The Writer adds no second door to the manuscript.

INVARIANT 3, THE TWO MEMORIES. `writer_passages` is the session half: renders that have
not been accepted are transient by nature — they can be dismissed, and dismissing loses
nothing that was ever canon. `manuscripts`/`scenes` (WS-0A) plus `writer_operators` are
the ledger half: committed prose and the author's ontology. Accept is the one crossing
between them, and it is a deliberate author action.

INVARIANT 4, PROVENANCE. The passage carries its provenance while quarantined, AND the
committed block keeps it: `origin: "user_confirmed"` (the vocabulary `routers/posts.py`
already uses for "the model proposed, the curator accepted") plus a `provenance` field
naming the operators, their versions, and the `//` intents that produced it. A committed
passage can always answer "what wrote this?".

INVARIANT 6, RE-CHECKED AT THE DOOR. `render` already strips orchestration on the way out.
`accept` checks AGAIN and REFUSES to commit a passage that still leaks. Belt and braces
is right here: the check is cheap, and the guarantee it protects ("no `//` content is ever
in the manuscript") has to hold against a passage that arrived by a path W1 did not write.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.database import writer_passage_collection
from backend.services.manuscript_service import manuscript_service
from backend.services.writer import dsl, instrument
from backend.services.writer.dsl import OrchestrationNote
from backend.services.writer.render import RenderResult

QUARANTINED = "quarantined"
ACCEPTED = "accepted"
DISMISSED = "dismissed"


class PassageError(ValueError):
    """A commit that must not happen (a leak, a missing scene, an already-decided passage)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _out(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def _notes_from_provenance(provenance: Dict[str, Any]) -> List[OrchestrationNote]:
    """Provenance intents → notes, so the accept-time leak check sees what render saw."""
    return [
        OrchestrationNote(line=0, key=str(i.get("key", "")), value=str(i.get("value", "")))
        for i in (provenance or {}).get("intents", []) or []
    ]


class PassageStore:
    """The quarantine. Renders land here; only Accept gets them out into canon."""

    async def quarantine(
        self,
        project_id: str,
        result: RenderResult,
        *,
        manuscript_id: str = "",
        scene_id: str = "",
    ) -> Dict[str, Any]:
        """Persist a successful render as an UNCOMMITTED passage."""
        if not result.succeeded:
            raise PassageError(
                "only a successful render can be quarantined — a refusal has no prose to hold"
            )
        now = _now()
        doc = {
            "_id": _gen("psg"),
            "project_id": project_id,
            "manuscript_id": manuscript_id,
            "scene_id": scene_id,
            "text": result.text,
            "committed": False,              # invariant 1 — the whole point
            "status": QUARANTINED,
            "provenance": dict(result.provenance or {}),
            "operators": [o["name"] for o in (result.provenance or {}).get("operators", [])],
            "diagnostics": list(result.diagnostics or ()),
            "model": result.model,
            "created_at": now,
            "decided_at": None,
        }
        await writer_passage_collection.insert_one(doc)
        return _out(doc)

    async def get(self, passage_id: str) -> Optional[Dict[str, Any]]:
        return _out(await writer_passage_collection.find_one({"_id": passage_id}))

    async def list(
        self, project_id: str, *, scene_id: str = "", status: str = QUARANTINED
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"project_id": project_id}
        if scene_id:
            query["scene_id"] = scene_id
        if status:
            query["status"] = status
        out: List[Dict[str, Any]] = []
        async for doc in writer_passage_collection.find(query).sort("created_at", -1):
            out.append(_out(doc))
        return out

    # ── the gate ─────────────────────────────────────────────────────────────

    async def accept(self, passage_id: str, *, scene_id: str = "") -> Dict[str, Any]:
        """The author commits a passage into the sacred manuscript.

        The ONLY path from quarantine into canon. Appends one block to the scene through
        `manuscript_service` (canon's owner), stamped `user_confirmed` and carrying its
        provenance. Refuses on: an already-decided passage, a missing scene, or a passage
        that still contains orchestration.
        """
        doc = await writer_passage_collection.find_one({"_id": passage_id})
        if not doc:
            raise PassageError(f"no such passage: {passage_id}")
        if doc.get("status") != QUARANTINED:
            raise PassageError(
                f"passage {passage_id} is already {doc.get('status')} — a decision is made once"
            )

        target_scene = scene_id or doc.get("scene_id") or ""
        if not target_scene:
            raise PassageError("cannot accept a passage that names no scene to commit into")

        scene = await manuscript_service.get_scene(target_scene)
        if not scene:
            raise PassageError(f"no such scene: {target_scene}")

        # Invariant 6 at the door. This runs BEFORE any write, so a leaking passage
        # cannot half-commit.
        notes = _notes_from_provenance(doc.get("provenance", {}))
        leaks = dsl.find_orchestration_leak(doc.get("text", ""), notes)
        if leaks:
            raise PassageError(
                "refusing to commit: orchestration would reach the manuscript — "
                + "; ".join(leaks)
            )

        provenance = dict(doc.get("provenance", {}))
        provenance["passage_id"] = passage_id
        provenance["accepted_at"] = _now().isoformat()

        block = {
            "id": _gen("blk"),
            "type": "paragraph",
            "content": doc.get("text", ""),
            "color": None,
            # `routers/posts.py`'s vocabulary: the model proposed, the author accepted.
            # NOT `model_suggested` — that means still-quarantined, and this is canon now.
            "origin": "user_confirmed",
            "provenance": provenance,
        }
        blocks = list(scene.get("blocks", []))
        blocks.append(block)
        updated = await manuscript_service.update_scene(target_scene, {"blocks": blocks})

        await writer_passage_collection.update_one(
            {"_id": passage_id},
            {"$set": {
                "committed": True,
                "status": ACCEPTED,
                "scene_id": target_scene,
                "block_id": block["id"],
                "decided_at": _now(),
            }},
        )
        await instrument.record(
            instrument.ACCEPT, doc.get("project_id", ""),
            operators=doc.get("operators", []),
            intents={i["key"]: i["value"] for i in provenance.get("intents", []) if i.get("key")},
            passage_id=passage_id,
        )
        return {"passage": await self.get(passage_id), "scene": updated, "block_id": block["id"]}

    async def dismiss(self, passage_id: str, reason: str = "") -> Dict[str, Any]:
        """Drop a quarantined passage. Nothing is written to canon; nothing is lost from it."""
        doc = await writer_passage_collection.find_one({"_id": passage_id})
        if not doc:
            raise PassageError(f"no such passage: {passage_id}")
        if doc.get("status") != QUARANTINED:
            raise PassageError(
                f"passage {passage_id} is already {doc.get('status')} — a decision is made once"
            )
        await writer_passage_collection.update_one(
            {"_id": passage_id},
            {"$set": {"status": DISMISSED, "committed": False,
                      "dismiss_reason": reason or "", "decided_at": _now()}},
        )
        await instrument.record(
            instrument.DISMISS, doc.get("project_id", ""),
            operators=doc.get("operators", []), passage_id=passage_id, detail=reason,
        )
        return _out(await writer_passage_collection.find_one({"_id": passage_id}))


passage_store = PassageStore()
