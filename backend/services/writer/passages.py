"""
Semant Writer W1 — quarantined passages, and the Accept gate.

INVARIANT 1, IN ONE SENTENCE: a rendered passage is born `committed: False` and the ONLY
thing that can change that is the author calling `accept`. There is no auto-commit path
in this module, no "high confidence" shortcut, and no code anywhere in the Writer that
writes prose into a scene except `accept` — which is why the write goes through
`manuscript_service`, the canon owner from WS-0A, rather than touching `scene_collection`
directly. The Writer adds no second door to the manuscript.

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

THE TRANSITION PROTOCOL (ATLAS-WRITER-MASS-BUILD-001D). Accept is four writes across three
collections, and two Accepts of one passage arriving together used to produce two blocks
and two lineages. Now every canonical transition is:

    CLAIM    one conditional update moves the passage `quarantined → accepting` and pins
             the PLAN — block id, lineage id, version — on it. Exactly one caller wins.
             Losers wait for the winner and return the winner's result: twenty identical
             calls, one block, one v1.
    RECORD   an operation record (`ledger.begin`) under a deterministic id, carrying the
             plan and the step reached.
    WRITE    version insert → scene write → passage mark, in THAT order, each step
             idempotent against the plan: a version already recorded is reused, a block
             already present is not appended twice, a passage already marked is left.
             The pointer (the scene block) is written only after the version it names is
             durable, so no failure can leave a block pointing at a version that does not
             exist.
    RESUME   a step that dies marks the record `failed` with the step name. The next
             identical call — a retry, a concurrent loser — claims the failed record and
             runs the remaining steps FROM THE SAME PLAN. Nothing is re-planned, so a retry
             creates no second block, version or lineage.

Instrumentation is write-behind and runs after the record is `done`; it can fail without
touching any of the above. `ledger.trip(...)` marks every seam so a test can fail each one.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.database import writer_passage_collection
from backend.services.manuscript_service import manuscript_service
from backend.services.writer import dsl, instrument, ledger, revisions
from backend.services.writer.dsl import OrchestrationNote
from backend.services.writer.render import RenderResult

QUARANTINED = "quarantined"
#: In flight: claimed by an Accept (first or revision) that has not finished. Still NOT
#: canon — nothing reads an `accepting` passage as committed — but no longer open to a
#: second decision.
ACCEPTING = "accepting"
ACCEPTED = "accepted"
DISMISSED = "dismissed"

ACCEPT_KIND = "accept"
REVISION_KIND = "accept_revision"
DISMISS_KIND = "dismiss"

#: How long a loser waits for the winner of a claim before giving up. Generous for a
#: real database; the tests never approach it.
SETTLE_TIMEOUT_S = 10.0
SETTLE_INTERVAL_S = 0.01


class PassageError(ValueError):
    """A commit that must not happen (a leak, a missing scene, an already-decided passage)."""


class PassageInFlight(PassageError):
    """Another call holds this passage's claim and has not finished within the wait."""


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


def _intents(provenance: Dict[str, Any]) -> Dict[str, str]:
    return {i["key"]: i["value"] for i in (provenance or {}).get("intents", []) if i.get("key")}


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

    # ── the guards every commit applies, before any write ────────────────────

    async def _gate(self, doc: Dict[str, Any], scene_id: str) -> Dict[str, Any]:
        """The checks that need no write: the scene exists, and nothing leaks. Returns the scene."""
        if not scene_id:
            raise PassageError("cannot accept a passage that names no scene to commit into")
        scene = await manuscript_service.get_scene(scene_id)
        if not scene:
            raise PassageError(f"no such scene: {scene_id}")
        # Invariant 6 at the door. This runs BEFORE any write, so a leaking passage
        # cannot half-commit.
        notes = _notes_from_provenance(doc.get("provenance", {}))
        leaks = dsl.find_orchestration_leak(doc.get("text", ""), notes)
        if leaks:
            raise PassageError(
                "refusing to commit: orchestration would reach the manuscript — "
                + "; ".join(leaks)
            )
        return scene

    # ── the claim ────────────────────────────────────────────────────────────

    async def _claim(self, passage_id: str, kind: str, plan: Dict[str, Any]) -> bool:
        """`quarantined → accepting`, with the plan pinned. One atomic write; one winner."""
        ledger.trip(f"{kind}.claim")
        res = await writer_passage_collection.update_one(
            {"_id": passage_id, "status": QUARANTINED},
            {"$set": {"status": ACCEPTING, "op_kind": kind, "plan": dict(plan),
                      "claimed_at": _now()}},
        )
        return res.matched_count > 0

    async def _settle(self, passage_id: str, kind: str, runner) -> Dict[str, Any]:
        """Wait for the claim-holder; resume it if it died. Returns the ONE result."""
        op_id = ledger.operation_id(kind, passage_id)
        deadline = asyncio.get_event_loop().time() + SETTLE_TIMEOUT_S
        while True:
            doc = await writer_passage_collection.find_one({"_id": passage_id})
            if not doc:
                raise PassageError(f"no such passage: {passage_id}")
            if doc.get("status") == ACCEPTED:
                return await self._result_for(doc)
            if doc.get("status") == DISMISSED:
                raise PassageError(
                    f"passage {passage_id} is already dismissed — a decision is made once")
            if doc.get("status") == ACCEPTING:
                if doc.get("op_kind") != kind:
                    raise PassageError(
                        f"passage {passage_id} is being committed as `{doc.get('op_kind')}`, "
                        f"not `{kind}` — a decision is made once")
                op = await ledger.get(op_id)
                if op is None:
                    # Claimed, but the record was never written — the claimant died between
                    # the two. Writing it is the resume; whoever inserts it runs.
                    op = await ledger.begin(kind, passage_id, plan=doc.get("plan") or {})
                    if op is not None:
                        return await runner(doc, doc.get("plan") or {}, op_id)
                elif op.get("state") == ledger.FAILED and await ledger.claim_resume(op_id):
                    return await runner(doc, doc.get("plan") or {}, op_id)
            if asyncio.get_event_loop().time() > deadline:
                raise PassageInFlight(
                    f"passage {passage_id} is still being committed by another call; "
                    f"retry — the same call will return the same result once it lands")
            await asyncio.sleep(SETTLE_INTERVAL_S)

    async def _result_for(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """The result an accepted passage's commit produced, rebuilt from what it recorded.

        The same answer for the caller that did the work and for the nineteen that waited —
        and for a retry an hour later. Nothing here is recomputed from prose; it is read
        off the passage, the version and the scene.
        """
        scene = await manuscript_service.get_scene(doc.get("scene_id", ""))
        result: Dict[str, Any] = {
            "passage": _out(doc),
            "scene": scene,
            "block_id": doc.get("block_id"),
            "lineage_id": doc.get("lineage_id"),
            "version": doc.get("version"),
        }
        if doc.get("op_kind") == REVISION_KIND:
            version = await revisions.version_store.resolve(
                doc.get("lineage_id", ""), int(doc.get("version") or 0))
            result["version"] = version
            result["declaration_diff"] = dict((version or {}).get("declaration_diff") or {})
        return result

    # ── the gate ─────────────────────────────────────────────────────────────

    async def accept(
        self, passage_id: str, *, scene_id: str = "", idempotency_key: str = "",
    ) -> Dict[str, Any]:
        """The author commits a passage into the sacred manuscript.

        The ONLY path from quarantine into canon. Appends one block to the scene through
        `manuscript_service` (canon's owner), stamped `user_confirmed` and carrying its
        provenance. Refuses on: a dismissed passage, a missing scene, or a passage that
        still contains orchestration. A passage already accepted — or being accepted by
        another call — returns THAT commit's result rather than making a second one.
        """
        doc = await writer_passage_collection.find_one({"_id": passage_id})
        if not doc:
            raise PassageError(f"no such passage: {passage_id}")
        await ledger.assert_key_free(idempotency_key, ACCEPT_KIND, passage_id)
        if doc.get("status") != QUARANTINED:
            return await self._settle(passage_id, ACCEPT_KIND, self._run_accept)

        target_scene = scene_id or doc.get("scene_id") or ""
        scene = await self._gate(doc, target_scene)

        # W8 — a committed passage is version 1 of a LINEAGE from the moment it lands, so
        # the first thing the author revises already has a history to append to rather than
        # a special case to adopt. The ids are planned ONCE, here, and pinned by the claim.
        plan = {
            "scene_id": target_scene,
            "manuscript_id": scene.get("manuscript_id", ""),
            "block_id": _gen("blk"),
            "lineage_id": _gen("lin"),
            "version": 1,
        }
        if not await self._claim(passage_id, ACCEPT_KIND, plan):
            return await self._settle(passage_id, ACCEPT_KIND, self._run_accept)
        op = await ledger.begin(ACCEPT_KIND, passage_id, plan=plan,
                                idempotency_key=idempotency_key)
        if op is None:
            return await self._settle(passage_id, ACCEPT_KIND, self._run_accept)
        return await self._run_accept(doc, plan, op["id"])

    async def _run_accept(
        self, doc: Dict[str, Any], plan: Dict[str, Any], op_id: str
    ) -> Dict[str, Any]:
        """The writes, in order, each idempotent against the plan. Resumable from any step."""
        passage_id = doc["_id"]
        provenance = dict(doc.get("provenance", {}))
        provenance["passage_id"] = passage_id
        provenance.setdefault("accepted_at", _now().isoformat())
        text = doc.get("text", "")
        block = {
            "id": plan["block_id"],
            "type": "paragraph",
            # ONE block. A multi-paragraph render keeps its paragraphs INSIDE this content
            # (blank-line separated) under one identity; `manuscript_service.block_paragraphs`
            # reads the structure back. It is never several blocks sharing an id.
            "content": text,
            "color": None,
            # `routers/posts.py`'s vocabulary: the model proposed, the author accepted.
            # NOT `model_suggested` — that means still-quarantined, and this is canon now.
            "origin": "user_confirmed",
            "provenance": provenance,
            "lineage_id": plan["lineage_id"],
            "version": 1,
        }
        step = "version_insert"
        try:
            await ledger.step(op_id, step)
            ledger.trip("accept.version_insert")
            try:
                await revisions.version_store.record(
                    doc.get("project_id", ""),
                    lineage_id=plan["lineage_id"],
                    version=1,
                    text=text,
                    provenance=provenance,
                    passage_id=passage_id,
                    block_id=plan["block_id"],
                    scene_id=plan["scene_id"],
                    manuscript_id=plan.get("manuscript_id", ""),
                    model=doc.get("model", "") or "",
                )
            except revisions.VersionExists:
                pass                              # a prior attempt got this far

            step = "scene_write"
            await ledger.step(op_id, step)
            ledger.trip("accept.scene_write")
            appended = await manuscript_service.append_block(plan["scene_id"], block)

            step = "passage_mark"
            await ledger.step(op_id, step)
            ledger.trip("accept.passage_mark")
            await writer_passage_collection.update_one(
                {"_id": passage_id, "status": ACCEPTING},
                {"$set": {
                    "committed": True,
                    "status": ACCEPTED,
                    "scene_id": plan["scene_id"],
                    "block_id": plan["block_id"],
                    "lineage_id": plan["lineage_id"],
                    "version": 1,
                    "decided_at": _now(),
                }},
            )
            await ledger.finish(op_id, {"block_id": plan["block_id"],
                                        "lineage_id": plan["lineage_id"], "version": 1})
        except Exception as exc:
            await ledger.fail(op_id, step, exc)
            raise

        await instrument.record(
            instrument.ACCEPT, doc.get("project_id", ""),
            operators=doc.get("operators", []),
            intents=_intents(provenance),
            passage_id=passage_id,
        )
        result = await self._result_for(
            await writer_passage_collection.find_one({"_id": passage_id}))
        result["scene"] = appended["scene"]
        return result

    async def accept_revision(
        self,
        passage_id: str,
        *,
        lineage_id: str,
        scene_id: str,
        block_id: str,
        in_response_to: Optional[Dict[str, Any]] = None,
        idempotency_key: str = "",
    ) -> Dict[str, Any]:
        """Commit a quarantined re-render as the NEXT VERSION of an existing passage.

        WHY THIS LIVES BESIDE `accept` RATHER THAN INSIDE `revisions`. Every guard the first
        commit applies has to apply here identically — the decided-once check, the missing
        scene, and above all the invariant-6 leak re-check at the door. A revision arriving
        by a different route with a lighter set of checks would be exactly the second door
        into canon this module exists to refuse. So the door is the same door; what differs
        is only that this one moves a pointer instead of appending a block.
        """
        doc = await writer_passage_collection.find_one({"_id": passage_id})
        if not doc:
            raise PassageError(f"no such passage: {passage_id}")
        await ledger.assert_key_free(idempotency_key, REVISION_KIND, passage_id)
        if doc.get("status") != QUARANTINED:
            return await self._settle(passage_id, REVISION_KIND, self._run_revision)

        await self._gate(doc, scene_id)
        plan = {
            "scene_id": scene_id,
            "block_id": block_id,
            "lineage_id": lineage_id,
            "in_response_to": dict(in_response_to or {}),
        }
        if not await self._claim(passage_id, REVISION_KIND, plan):
            return await self._settle(passage_id, REVISION_KIND, self._run_revision)
        op = await ledger.begin(REVISION_KIND, passage_id, plan=plan,
                                idempotency_key=idempotency_key)
        if op is None:
            return await self._settle(passage_id, REVISION_KIND, self._run_revision)
        return await self._run_revision(doc, plan, op["id"])

    async def _run_revision(
        self, doc: Dict[str, Any], plan: Dict[str, Any], op_id: str
    ) -> Dict[str, Any]:
        passage_id = doc["_id"]
        provenance = dict(doc.get("provenance", {}))
        provenance["passage_id"] = passage_id
        provenance.setdefault("accepted_at", _now().isoformat())

        step = "version_and_pointer"
        try:
            await ledger.step(op_id, step)
            try:
                committed = await revisions.accept_revision(
                    doc.get("project_id", ""),
                    lineage_id=plan["lineage_id"],
                    scene_id=plan["scene_id"],
                    block_id=plan["block_id"],
                    text=doc.get("text", ""),
                    provenance=provenance,
                    passage_id=passage_id,
                    in_response_to=plan.get("in_response_to") or None,
                    model=doc.get("model", "") or "",
                )
            except revisions.RevisionError as exc:
                # A REFUSAL, not a crash: the lineage moved on, or the block is not where
                # the plan expected. Nothing was written for this passage, so the claim is
                # RELEASED — the passage goes back to quarantine for the author to re-open
                # the revision against what is current. This is the one compensating
                # step in the protocol, and it compensates for a write that did not happen.
                await writer_passage_collection.update_one(
                    {"_id": passage_id, "status": ACCEPTING},
                    {"$set": {"status": QUARANTINED, "op_kind": None, "plan": None,
                              "refused": str(exc)}})
                await ledger.fail(op_id, "refused", exc)
                raise

            step = "passage_mark"
            await ledger.step(op_id, step)
            ledger.trip("accept_revision.passage_mark")
            await writer_passage_collection.update_one(
                {"_id": passage_id, "status": ACCEPTING},
                {"$set": {
                    "committed": True,
                    "status": ACCEPTED,
                    "scene_id": plan["scene_id"],
                    "block_id": plan["block_id"],
                    "lineage_id": plan["lineage_id"],
                    "version": committed["version"]["version"],
                    "decided_at": _now(),
                }},
            )
            await ledger.finish(op_id, {"block_id": plan["block_id"],
                                        "lineage_id": plan["lineage_id"],
                                        "version": committed["version"]["version"]})
        except Exception as exc:
            if not isinstance(exc, revisions.RevisionError):     # a refusal was recorded above
                await ledger.fail(op_id, step, exc)
            raise

        await instrument.record(
            instrument.ACCEPT, doc.get("project_id", ""),
            operators=doc.get("operators", []),
            intents=_intents(provenance),
            passage_id=passage_id,
        )
        return {
            "passage": await self.get(passage_id),
            "version": committed["version"],
            "scene": committed["scene"],
            "declaration_diff": committed["declaration_diff"],
        }

    async def dismiss(
        self, passage_id: str, reason: str = "", *, idempotency_key: str = ""
    ) -> Dict[str, Any]:
        """Drop a quarantined passage. Nothing is written to canon; nothing is lost from it.

        One conditional write. A second Dismiss finds it dismissed and returns it as it
        stands; a Dismiss of an accepted passage is refused — a decision is made once.
        """
        doc = await writer_passage_collection.find_one({"_id": passage_id})
        if not doc:
            raise PassageError(f"no such passage: {passage_id}")
        await ledger.assert_key_free(idempotency_key, DISMISS_KIND, passage_id)
        ledger.trip("dismiss.passage_mark")
        res = await writer_passage_collection.update_one(
            {"_id": passage_id, "status": QUARANTINED},
            {"$set": {"status": DISMISSED, "committed": False,
                      "dismiss_reason": reason or "", "decided_at": _now()}},
        )
        if res.matched_count == 0:
            current = await writer_passage_collection.find_one({"_id": passage_id})
            if current.get("status") == DISMISSED:
                return _out(current)                 # converged; nothing to redo
            raise PassageError(
                f"passage {passage_id} is already {current.get('status')} — a decision is made once"
            )
        op = await ledger.begin(DISMISS_KIND, passage_id, plan={"reason": reason or ""},
                                idempotency_key=idempotency_key)
        if op is not None:
            await ledger.finish(op["id"])
        await instrument.record(
            instrument.DISMISS, doc.get("project_id", ""),
            operators=doc.get("operators", []), passage_id=passage_id, detail=reason,
        )
        return _out(await writer_passage_collection.find_one({"_id": passage_id}))


passage_store = PassageStore()
