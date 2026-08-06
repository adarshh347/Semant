"""
Semant Writer W10 — depth registers: the author's own cognitive layers.

A sophisticated passage works on several layers at once. W10 makes those layers an explicit
axis of the DSL — but the axis is the AUTHOR'S, named in their words and ordered by their
judgement, and this module's entire job is to keep it that way.

THE AUTHOR'S-LADDER RULE — load-bearing, and stated here because this is where it would be
broken first:

    A register is a name the author gives a layer of their own work. Semant imposes no
    taxonomy of depth. It never renders or reads "at a depth" by consulting its own idea of
    what that depth means. Depth lives entirely in the author's declared registers and their
    register-tagged operators — realized at render through those operators, derived at read
    from provenance, invented at neither.

THE VOCABULARY STARTS EMPTY, AND THAT IS THE GUARD. There is no default ladder. A new
project has no registers, `//register` refuses until the author declares some, and no
operator can be tagged. The temptation is to seed `surface / psychological / philosophical`
because it is a reasonable ladder and an empty list looks unfinished — but a default that
arrives before the author has thought about it is not a starting point, it is the model's
taxonomy wearing the author's project. Whatever ships as the default becomes what most
authors keep, so the default IS the imposition.

THE CLASSIC LADDER IS A TEMPLATE, NOT A DEFAULT. `propose_template` exists and returns the
familiar three-rung ladder — UNSAVED, exactly as `operator_registry.propose` returns an
unsaved operator. The author edits the names, the descriptions and the order, and then
commits. That is the difference between offering a vocabulary and installing one: a
proposal the author must accept is a suggestion, and a seeded collection is a decision made
on their behalf.

ORDER IS THE AUTHOR'S AND MEANS NOTHING TO THE SYSTEM. The list is ordered because authors
think of layers as a ladder, and the depth view shows them in that order. Nothing in this
codebase treats position 3 as "deeper than" position 1, compares two registers, or scores a
passage by how far down its registers sit. A register is a NAME with a POSITION IN A LIST
the author sorted; the meaning of the ladder is theirs and is never read by anything here.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from backend.database import writer_register_collection

#: The instrumentation events. §9 — log now, analyse later.
DECLARED = "registers_declared"

_NAME_RE = re.compile(r"^[A-Za-z][\w-]*$")

#: The classic ladder, offered as an ADOPTABLE TEMPLATE and never installed.
#:
#: It is a literal here rather than a stored default precisely so that nothing reads it
#: unless the author asked for it: `propose_template()` is the only function that touches
#: it, it returns an unsaved proposal, and no other code path in the Writer imports it.
#: A test asserts a fresh project's vocabulary is empty, which is the assertion that keeps
#: this constant a suggestion.
#:
#: The descriptions are deliberately thin. A rich gloss of what "philosophical" means would
#: be this module explaining the author's layer to them, which is the imposition arriving
#: as helpfulness — the author replaces these words with their own.
CLASSIC_TEMPLATE: tuple = (
    {"name": "surface", "description": "what literally happens"},
    {"name": "psychological", "description": "what it does to the people in it"},
    {"name": "philosophical", "description": "what it is about"},
)


class RegisterError(ValueError):
    """A register declaration or reference that cannot stand, with the reason."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def propose_template() -> Dict[str, Any]:
    """The classic ladder, UNSAVED, for the author to edit and commit — or ignore.

    Mirrors `operator_registry.propose`: the system may offer, the author commits. The
    returned document is marked `committed: False` and `template: True` so no surface can
    mistake it for the project's vocabulary, and `declare` is the only thing that stores.
    """
    return {
        "committed": False,
        "template": "classic",
        "registers": [dict(r) for r in CLASSIC_TEMPLATE],
        "note": (
            "A common ladder, offered as a starting point and nothing more. Rename these, "
            "reorder them, delete the ones that are not how you think, add the layers you "
            "actually work in — this is your vocabulary and none of it is committed until "
            "you say so."
        ),
    }


def _clean(registers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalise a proposed vocabulary. Raises rather than repairing."""
    if not isinstance(registers, (list, tuple)):
        raise RegisterError("a register vocabulary is an ordered list of registers")

    out: List[Dict[str, Any]] = []
    seen = set()
    for i, entry in enumerate(registers):
        if isinstance(entry, str):
            entry = {"name": entry}
        if not isinstance(entry, dict):
            raise RegisterError(f"register {i + 1} is not a register: {entry!r}")

        name = str(entry.get("name") or "").strip()
        if not name:
            raise RegisterError(f"register {i + 1} has no name")
        if not _NAME_RE.match(name):
            raise RegisterError(
                f"'{name}' cannot be a register name — use a word the DSL can carry in "
                f"`//register: {name}` (letters, digits, _ and -, starting with a letter)"
            )
        if name.lower() in seen:
            raise RegisterError(
                f"'{name}' is declared twice — a register is one layer, named once"
            )
        seen.add(name.lower())

        out.append({
            "name": name,
            "description": str(entry.get("description") or "").strip(),
            # Position in the author's ladder. Recorded so the depth view can show their
            # order; never compared, never scored — see the module docstring.
            "order": i,
        })
    return out


# ── the vocabulary ──────────────────────────────────────────────────────────

async def declare(project_id: str, registers: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The author-confirmed write. Replaces the vocabulary with exactly what they set.

    A REPLACE rather than an append, because the vocabulary is one ordered list and the
    author reorders it by handing over the new order. Registers already in use by an
    operator cannot be dropped this way — see the guard below, which refuses rather than
    orphaning a tag.
    """
    cleaned = _clean(registers)

    # Removing a register that operators still carry would leave those operators pointing
    # at a name that no longer means anything — a dangling reference of exactly the kind
    # `requires` edges are validated against. Refuse and name what is in the way.
    from backend.services.writer.operators import operator_registry

    in_use: Dict[str, List[str]] = {}
    for op in await operator_registry.list(project_id):
        tag = op.get("register")
        if tag:
            in_use.setdefault(tag, []).append(op["name"])

    kept = {r["name"] for r in cleaned}
    orphaned = {tag: ops for tag, ops in in_use.items() if tag not in kept}
    if orphaned:
        detail = "; ".join(
            f"'{tag}' is carried by {', '.join('/' + n for n in sorted(ops))}"
            for tag, ops in sorted(orphaned.items())
        )
        raise RegisterError(
            f"cannot drop a register that operators still carry — {detail}. "
            f"Retag those operators first, so nothing is left pointing at a layer you "
            f"no longer name."
        )

    doc = {
        "_id": project_id,
        "project_id": project_id,
        "registers": cleaned,
        "updated_at": _now(),
    }
    await writer_register_collection.update_one(
        {"_id": project_id}, {"$set": doc}, upsert=True
    )
    return {"project_id": project_id, "registers": cleaned}


async def vocabulary(project_id: str) -> List[Dict[str, Any]]:
    """The author's registers, in the author's order. EMPTY until they declare some."""
    doc = await writer_register_collection.find_one({"_id": project_id})
    return list((doc or {}).get("registers", []))


async def names(project_id: str) -> List[str]:
    return [r["name"] for r in await vocabulary(project_id)]


async def resolve(project_id: str, name: str) -> Optional[Dict[str, Any]]:
    """One declared register, or None. Case-insensitive — the author typed it twice."""
    wanted = (name or "").strip().lower()
    for register in await vocabulary(project_id):
        if register["name"].lower() == wanted:
            return register
    return None


async def require(project_id: str, name: str) -> Dict[str, Any]:
    """A declared register, or a refusal that says how to declare it.

    THE GROUNDED-REFERENCE GUARD, and the reason a register is not free text. Tagging an
    operator `philosophical` when no such register is declared would let the model's word
    into the ontology through the back door — the same failure `requires` avoids by taking
    an operator reference rather than a string.
    """
    found = await resolve(project_id, name)
    if found:
        return found

    declared = await names(project_id)
    if not declared:
        raise RegisterError(
            f"'{name}' is not one of your registers — you have not declared any yet. "
            f"Name the layers you actually work in first; there is no default ladder here "
            f"because the ladder is yours."
        )
    raise RegisterError(
        f"'{name}' is not one of your registers. You have declared: "
        f"{', '.join(declared)}. Add it to your vocabulary if it is a layer you work in — "
        f"a register has to be a name you gave, not one this system supplied."
    )


def parse_register_intent(value: str) -> List[str]:
    """`//register: interior, thematic` → `["interior", "thematic"]`.

    A set is allowed because a passage can be asked to work at more than one layer. Order
    here is the author's typing order and carries no priority — nothing downstream ranks
    them.
    """
    return [part.strip() for part in re.split(r"[,;]", value or "") if part.strip()]


# ── the depth view: derived, never interpreted ──────────────────────────────

def registers_in(provenance: Dict[str, Any]) -> List[str]:
    """The layers one committed span operates at, READ OFF ITS PROVENANCE.

    This is the whole of "read at depth", and what it is NOT is the point. It makes no
    model call, forms no opinion, and reads nothing but the register each operator carried
    when it fired. A generated "here is the philosophical reading of your chapter" would be
    the model's account of the author's book presented as the book's own depth — the same
    fabrication W9 refuses for summaries, on the axis where it would be hardest to catch.

    A SPAN THE AUTHOR TYPED HAS NO REGISTER, and does not acquire one by inference. There is
    no classifier here and no heuristic that guesses a layer from the words: prose with no
    operator behind it simply carries no depth information, and reporting that honestly is
    more useful than a confident guess about writing the model never saw declared.
    """
    out: List[str] = []
    for stamp in (provenance or {}).get("operators", []) or []:
        if not isinstance(stamp, dict):
            continue
        register = (stamp.get("register") or "").strip()
        if register and register not in out:
            out.append(register)
    return out


def order_key(vocabulary: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """Register name → the author's position for it. Their ladder, their sequence."""
    return {r["name"]: r.get("order", i) for i, r in enumerate(vocabulary)}


async def depth_view(project_id: str, spans: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Which committed spans work at which of the author's layers. Purely derived.

    `spans` are committed passage versions (W8's ledger). Returns the vocabulary in the
    author's order, each span's registers, and a per-register index — enough for a surface
    to filter by layer without anything here having formed a view about any of it.
    """
    vocabulary = await vocabulary_of(project_id)
    order = order_key(vocabulary)

    entries: List[Dict[str, Any]] = []
    by_register: Dict[str, List[str]] = {r["name"]: [] for r in vocabulary}
    untagged: List[str] = []

    for span in spans:
        found = registers_in(span.get("provenance", {}))
        # Shown in the AUTHOR'S ladder order, not the order the operators happened to fire.
        found = sorted(found, key=lambda r: order.get(r, len(order)))
        key = f"{span.get('lineage_id')}@v{span.get('version')}"
        entries.append({
            "lineage_id": span.get("lineage_id"),
            "version": span.get("version"),
            "block_id": span.get("block_id", ""),
            "scene_id": span.get("scene_id", ""),
            "registers": found,
            # The author's own words, unaltered — the same rule W9 established. This view
            # shows prose; it never describes it.
            "text": span.get("text", ""),
        })
        for register in found:
            by_register.setdefault(register, []).append(key)
        if not found:
            untagged.append(key)

    return {
        "vocabulary": vocabulary,
        "spans": entries,
        "by_register": by_register,
        # Named honestly rather than hidden: prose the author typed, or rendered before
        # they had a ladder, sits outside the depth axis and is not assigned a layer.
        "untagged": untagged,
    }


#: `vocabulary` is the public name; this alias keeps `depth_view` readable above.
vocabulary_of = vocabulary
