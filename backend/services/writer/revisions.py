"""
Semant Writer W8 — revision and passage genealogy.

W1 gave the manuscript a first draft: render, quarantine, Accept. W7 made it visible when a
committed passage diverges from what the author declared. This is the act that closes the
loop — changing the declarations and rendering the passage again — and the whole of its
design is about making that act unable to become the thing every writing tool turns it into.

THE CANON RULE: VERSIONS ARE IMMUTABLE, THE POINTER MOVES.

A committed version is written once into `writer_passage_versions` and never touched again.
There is no update path and no delete path in this module — not for tidiness, but because a
version is what a committed passage's provenance POINTS AT, and an audit trail whose targets
can be edited is not an audit trail. Revising appends a new version and moves the scene
block's pointer to it. The prose the author committed last month is still there, still says
what made it, and still reads exactly as they accepted it.

THE POINTER IS THE SCENE BLOCK, and that placement is load-bearing. `export_manuscript`
walks scene blocks; a block holds exactly one version; therefore a historical version has NO
ROUTE into exported prose. "Export is current versions only" is true by construction rather
than by a filter someone has to remember to apply — the same shape as W2 putting the export
rules in the ProseMirror schema instead of in CSS.

NO SILENT IMPROVEMENT — and the strong form of it.

The failure mode to forbid is the model polishing beyond what the author changed. The weak
guard is to instruct it not to; this project has already measured what a prompt-only wall is
worth (`GROUNDING.md`). So the guard here is structural and it is this:

    A REVISION IS A FRESH RENDER UNDER THE DECLARED SET. THE PRIOR VERSION'S TEXT IS NEVER
    IN THE PROMPT.

`revision_prompt` calls the same `build_render_prompt` a first render calls, with the same
arguments, and adds NOTHING — no "here is the current version", no "improve on this", no
mention that a revision is happening at all. The consequence is exactly what §3 asks for and
can be asserted byte-for-byte: revising under an unchanged declaration set produces a prompt
IDENTICAL to the first render's, so no new intent can have entered.

Handing the model the old text would make it an editor of prose rather than a renderer of
declarations, and "here is what you wrote, here are the new instructions" is precisely the
sentence that invites a tightened verb the author never asked for. The author still sees the
diff — on the surface, where a person can judge it. The model does not, because the model is
the party that must not be improving anything.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from backend.database import writer_passage_version_collection
from backend.services.manuscript_service import manuscript_service
from backend.services.writer import instrument

#: The instrumentation events. §8 says log the genealogy and build no analysis on it yet.
REVISED = "passage_revised"
LOOP_CLOSED = "revision_loop_closed"

#: The outcome of re-reading a revision that answered a W7 flag.
CLEARED = "cleared"
STILL_PRESENT = "still_present"


class RevisionError(ValueError):
    """A revision that must not happen, with the reason."""


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


# ── the declared set, as a comparable thing ──────────────────────────────────

def declared_set(provenance: Dict[str, Any]) -> Dict[str, Any]:
    """A passage's declarations, normalised so two of them can be compared.

    Only what the author DECLARED: the operators (by name and version) and the `//` intents.
    Deliberately not the rendered text, the model, the timestamps or the run id — those are
    facts about one firing of the loop, and a diff over them would report noise as intent.
    """
    operators: Dict[str, Any] = {}
    for stamp in (provenance or {}).get("operators", []) or []:
        if isinstance(stamp, dict) and stamp.get("name"):
            operators[str(stamp["name"])] = stamp.get("version")

    intents: Dict[str, str] = {}
    for intent in (provenance or {}).get("intents", []) or []:
        if isinstance(intent, dict) and intent.get("key"):
            intents[str(intent["key"])] = str(intent.get("value") or "")

    return {"operators": operators, "intents": intents}


def declaration_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """What the author changed between two versions — the WHY of the genealogy.

    §2 is explicit that recording *that* the text changed is not enough: a history of
    successive paragraphs with no account of what the author was doing is a diff viewer, not
    provenance. This is the account. It answers "what did I change to cause this?" and it is
    the thing the revise card shows and the genealogy keeps.

    `reversioned` deserves its own bucket rather than living in added+removed. An operator
    that went from v1 to v2 is the SAME declaration whose meaning the author edited, and
    flattening it into "removed `restraint`, added `restraint`" would lose exactly the fact
    that makes the passage read differently.
    """
    ops_before, ops_after = before.get("operators", {}), after.get("operators", {})
    int_before, int_after = before.get("intents", {}), after.get("intents", {})

    return {
        "operators_added": sorted(set(ops_after) - set(ops_before)),
        "operators_removed": sorted(set(ops_before) - set(ops_after)),
        "operators_reversioned": sorted(
            [{"name": n, "from": ops_before[n], "to": ops_after[n]}
             for n in set(ops_before) & set(ops_after) if ops_before[n] != ops_after[n]],
            key=lambda d: d["name"],
        ),
        "intents_added": sorted(set(int_after) - set(int_before)),
        "intents_removed": sorted(set(int_before) - set(int_after)),
        "intents_changed": sorted(
            [{"key": k, "from": int_before[k], "to": int_after[k]}
             for k in set(int_before) & set(int_after) if int_before[k] != int_after[k]],
            key=lambda d: d["key"],
        ),
    }


def diff_is_empty(diff: Dict[str, Any]) -> bool:
    """Nothing declared changed. NOT an error — see `revise` on why it is allowed."""
    return not any(diff.get(k) for k in (
        "operators_added", "operators_removed", "operators_reversioned",
        "intents_added", "intents_removed", "intents_changed",
    ))


# ── the immutable version store ──────────────────────────────────────────────

class VersionStore:
    """Append-only. There is no update and no delete here, and there must never be one."""

    async def record(
        self,
        project_id: str,
        *,
        lineage_id: str,
        version: int,
        text: str,
        provenance: Dict[str, Any],
        passage_id: str = "",
        block_id: str = "",
        scene_id: str = "",
        manuscript_id: str = "",
        revised_from: str = "",
        diff: Optional[Dict[str, Any]] = None,
        in_response_to: Optional[Dict[str, Any]] = None,
        model: str = "",
    ) -> Dict[str, Any]:
        """Write one immutable version. Called by Accept and by nothing else."""
        doc = {
            "_id": _gen("ver"),
            "project_id": project_id,
            "lineage_id": lineage_id,
            "version": version,
            "text": text,
            # Frozen at the moment of commit. A later edit to an operator bumps ITS version
            # and leaves this stamp naming the one that actually fired (I4, W5's resolver).
            "provenance": dict(provenance or {}),
            "passage_id": passage_id,
            "block_id": block_id,
            "scene_id": scene_id,
            "manuscript_id": manuscript_id,
            # The temporal axis (§2).
            "revised_from": revised_from,
            "declaration_diff": dict(diff or {}),
            # `{flag_id, element, reading_id}` — the element is what survives the revision
            # and can therefore be looked for again. See `close_loop`.
            "in_response_to": dict(in_response_to or {}),
            # Filled in later by `close_loop` — the only field on a version that is ever
            # written after insert, and it is an OBSERVATION ABOUT the version rather than
            # part of it: whether re-reading found the divergence still there. The prose,
            # the provenance and the diff stay untouched forever.
            "loop_outcome": None,
            "model": model,
            "committed_at": _now(),
        }
        await writer_passage_version_collection.insert_one(doc)
        return _out(doc)

    async def get(self, version_id: str) -> Optional[Dict[str, Any]]:
        return _out(await writer_passage_version_collection.find_one({"_id": version_id}))

    async def resolve(self, lineage_id: str, version: int) -> Optional[Dict[str, Any]]:
        """A HISTORICAL version, exactly as it was committed (§5, gate step 7).

        W5's resolver answered "what did this operator say when it fired?". This answers the
        other half — "what did this passage say before I revised it?" — and the two together
        are what let a superseded version still account for itself completely.
        """
        return _out(await writer_passage_version_collection.find_one(
            {"lineage_id": lineage_id, "version": int(version)}
        ))

    async def history(self, lineage_id: str) -> List[Dict[str, Any]]:
        """Every version of one passage, oldest first. Read-only — this is the genealogy."""
        out: List[Dict[str, Any]] = []
        async for doc in writer_passage_version_collection.find({"lineage_id": lineage_id}):
            out.append(_out(doc))
        return sorted(out, key=lambda d: d["version"])

    async def current(self, lineage_id: str) -> Optional[Dict[str, Any]]:
        versions = await self.history(lineage_id)
        return versions[-1] if versions else None

    async def next_version(self, lineage_id: str) -> int:
        return len(await self.history(lineage_id)) + 1


version_store = VersionStore()


# ── the current pointer: a scene block ───────────────────────────────────────

async def _scene_and_block(scene_id: str, block_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    scene = await manuscript_service.get_scene(scene_id)
    if not scene:
        raise RevisionError(f"no such scene: {scene_id}")
    block = next((b for b in scene.get("blocks", []) if b.get("id") == block_id), None)
    if block is None:
        raise RevisionError(f"no such block in scene {scene_id}: {block_id}")
    return scene, block


async def lineage_for_block(
    project_id: str, scene_id: str, block_id: str
) -> Dict[str, Any]:
    """The lineage a committed block belongs to, adopting it if it predates W8.

    ADOPTION IS NOT BACKFILL OF HISTORY. A block committed before this collection existed
    has exactly one version — the prose that is on the page — and adopting it records that
    one version from the block's OWN provenance. It invents no earlier drafts and claims no
    revisions that never happened; it simply gives the passage already in the manuscript a
    place to have a future. Fabricating a plausible history here would be the audit-trail
    equivalent of hollow filler.
    """
    scene, block = await _scene_and_block(scene_id, block_id)
    lineage_id = block.get("lineage_id")

    if lineage_id and await version_store.history(lineage_id):
        return {"lineage_id": lineage_id, "adopted": False,
                "current": await version_store.current(lineage_id)}

    lineage_id = lineage_id or _gen("lin")
    provenance = dict(block.get("provenance") or {})
    current = await version_store.record(
        project_id,
        lineage_id=lineage_id,
        version=1,
        text=block.get("content", ""),
        provenance=provenance,
        passage_id=provenance.get("passage_id", ""),
        block_id=block_id,
        scene_id=scene_id,
        manuscript_id=scene.get("manuscript_id", ""),
        model=provenance.get("model", "") or "",
    )
    await _point_block_at(scene_id, block_id, lineage_id, 1)
    return {"lineage_id": lineage_id, "adopted": True, "current": current}


async def _point_block_at(scene_id: str, block_id: str, lineage_id: str, version: int,
                          text: Optional[str] = None,
                          provenance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Move the pointer. The ONLY function that changes what a committed block shows.

    It writes through `manuscript_service`, the canon owner from WS-0A, for the same reason
    Accept does: the Writer adds no second door to the manuscript.
    """
    scene, _ = await _scene_and_block(scene_id, block_id)
    blocks = []
    for b in scene.get("blocks", []):
        if b.get("id") == block_id:
            b = dict(b)
            b["lineage_id"] = lineage_id
            b["version"] = version
            if text is not None:
                b["content"] = text
            if provenance is not None:
                b["provenance"] = dict(provenance)
        blocks.append(b)
    return await manuscript_service.update_scene(scene_id, {"blocks": blocks})


# ── the prompt (§3 — the strong form of no-silent-improvement) ───────────────

def revision_prompt(
    operators: Sequence[Dict[str, Any]],
    orchestration: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> Dict[str, str]:
    """The re-render contract — which is the RENDER contract, unchanged.

    This function deliberately does nothing but forward. It exists so the claim is legible
    at the call site and enforceable in a test: a revision's prompt is built by the same
    builder, from the declared set, with no revision-specific framing whatsoever.

    Everything a revision might want to add here is exactly what §3 forbids. "Here is the
    current version" makes the model an editor. "The author wants this improved" hands it a
    standard the author never declared. "Try a different approach" is taste with extra steps.
    The prior text goes to the AUTHOR, on the surface, where a person can judge it.
    """
    from backend.services.writer.render import build_render_prompt

    return build_render_prompt(operators, orchestration, **kwargs)


#: Vocabulary that must never reach a render or re-render prompt. The gate scans for it.
#: Not a filter — nothing strips these — but a tripwire, so a well-meaning edit that adds
#: "polish this" to a prompt fails a test instead of shipping.
POLISH_VOCABULARY = (
    "improve", "polish", "tighten", "better", "stronger", "smoother", "elevate",
    "refine", "enhance", "sharpen", "more vivid", "more evocative", "flourish",
    "rewrite it", "fix the", "clean up", "make it good",
)


def polish_leaks(prompt: Dict[str, str]) -> List[str]:
    """Any polish instruction present in a prompt. Empty is the only passing answer."""
    blob = f"{prompt.get('system', '')}\n{prompt.get('user', '')}".lower()
    return [word for word in POLISH_VOCABULARY if word in blob]


# ── the revision itself ──────────────────────────────────────────────────────

async def prepare(
    project_id: str, scene_id: str, block_id: str
) -> Dict[str, Any]:
    """What the author needs to revise a block: its lineage, and what it was declared under.

    Read-only. Rendering happens through the normal loop; this only says what the current
    declarations ARE, so the surface can show them and let the author change them.
    """
    lineage = await lineage_for_block(project_id, scene_id, block_id)
    current = lineage["current"] or {}
    return {
        "lineage_id": lineage["lineage_id"],
        "adopted": lineage["adopted"],
        "current_version": current.get("version"),
        "current_text": current.get("text", ""),
        "declared": declared_set(current.get("provenance", {})),
        "history": await version_store.history(lineage["lineage_id"]),
    }


async def accept_revision(
    project_id: str,
    *,
    lineage_id: str,
    scene_id: str,
    block_id: str,
    text: str,
    provenance: Dict[str, Any],
    passage_id: str = "",
    in_response_to: Optional[Dict[str, Any]] = None,
    model: str = "",
) -> Dict[str, Any]:
    """The author commits a re-render as the next version. The pointer moves; nothing is lost.

    Every guard the first Accept applies has already run on the quarantined passage — this is
    called BY that path (`passages.accept_revision`), not instead of it.
    """
    history = await version_store.history(lineage_id)
    if not history:
        raise RevisionError(
            f"lineage {lineage_id} has no committed version to revise — "
            "a revision needs a parent"
        )
    parent = history[-1]

    diff = declaration_diff(
        declared_set(parent.get("provenance", {})), declared_set(provenance)
    )
    version = parent["version"] + 1
    recorded = await version_store.record(
        project_id,
        lineage_id=lineage_id,
        version=version,
        text=text,
        provenance=provenance,
        passage_id=passage_id,
        block_id=block_id,
        scene_id=scene_id,
        manuscript_id=parent.get("manuscript_id", ""),
        revised_from=f"{lineage_id}@v{parent['version']}",
        diff=diff,
        in_response_to=in_response_to,
        model=model,
    )

    # The pointer moves only now, and only after the new version is durably recorded — so a
    # failure between the two leaves the author looking at prose that still has a version.
    scene = await _point_block_at(scene_id, block_id, lineage_id, version,
                                  text=text, provenance=provenance)

    await instrument.record(
        REVISED, project_id,
        operators=[o.get("name") for o in (provenance or {}).get("operators", [])
                   if isinstance(o, dict) and o.get("name")],
        passage_id=passage_id,
        extra={
            "lineage_id": lineage_id,
            "version": version,
            "revised_from": recorded["revised_from"],
            "declaration_diff": diff,
            "declarations_unchanged": diff_is_empty(diff),
            "in_response_to": (in_response_to or {}).get("flag_id", ""),
        },
    )
    return {"version": recorded, "scene": scene, "declaration_diff": diff}


# ── closing the W7 loop (§5, gate step 6) ───────────────────────────────────

async def close_loop(version_id: str, reading: Dict[str, Any]) -> Dict[str, Any]:
    """Did revising in response to a flag actually clear it?

    THE POINT IS THAT `still_present` IS A RECORDED OUTCOME, NOT A FAILURE TO RECORD. A loop
    that only logged its successes would tell the calibration signal (W7 §5) that every
    revision works, which is the most flattering possible lie about the author's tools. An
    operator whose flags keep coming back after the author has already rewritten against them
    is the clearest evidence that the OPERATOR is miscalibrated rather than the prose — and
    that evidence exists only if this writes down the disappointments too.

    Nothing is analysed here. W8 §8 says log the outcome and build no analysis on it yet.
    """
    version = await version_store.get(version_id)
    if not version:
        raise RevisionError(f"no such version: {version_id}")
    answered = version.get("in_response_to") or {}
    if not answered.get("flag_id"):
        raise RevisionError(
            f"version {version_id} was not made in response to a flag — there is no loop to close"
        )

    # THE ELEMENT, NOT THE FLAG ID, IS WHAT CAN RECUR. The new reading produces new flags
    # with new ids, so asking "is flag flg_abc still here?" would answer `cleared` every
    # time and the loop would congratulate itself unconditionally. What persists across a
    # revision is the DECLARED ELEMENT the flag rested on — `intent:avoid`,
    # `operator:restraint:intent` — so that is what is looked for again.
    flag_id = answered["flag_id"]
    element = answered.get("element") or ""
    recurred = [
        f for f in (reading or {}).get("flags", []) or []
        if isinstance(f, dict) and f.get("element") == element
    ]
    outcome = STILL_PRESENT if recurred else CLEARED

    await writer_passage_version_collection.update_one(
        {"_id": version_id},
        {"$set": {"loop_outcome": {
            "outcome": outcome,
            "flag_id": flag_id,
            "element": element,
            "reading_id": (reading or {}).get("id", ""),
            "closed_at": _now(),
        }}},
    )
    await instrument.record(
        LOOP_CLOSED, version.get("project_id", ""),
        operators=[o.get("name") for o in (version.get("provenance") or {}).get("operators", [])
                   if isinstance(o, dict) and o.get("name")],
        extra={
            "lineage_id": version.get("lineage_id"),
            "version": version.get("version"),
            "flag_id": flag_id,
            "element": element,
            "outcome": outcome,
        },
    )
    return await version_store.get(version_id)
