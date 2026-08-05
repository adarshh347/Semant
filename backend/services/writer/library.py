"""
Semant Writer W5 — the portable ontology: the author's language, carried between books.

Until now an operator lived inside one manuscript. This lifts it: promote what you defined
in Book A into a library above project scope, import it into Book B, and render with it
there — still grounded, because it is still YOUR declared language. The evidence base
widens from one project's ontology to the author's, and the honesty spine holds because of
two guardrails, which are the whole of W5:

  SINGLE AUTHOR. An operator from someone else's hand rendering your canon would be the
  priors violation with a human source — prose in a voice you never declared, and one you
  cannot check against your own book. The library is keyed by author, import refuses across
  authors, and the render actuator refuses again as a backstop (`author_guard`).

  PINNED VERSIONS, FOREVER. Every committed passage names `name@version`, and that pin must
  keep resolving through promote, import, edit, publish and pull. Library entries therefore
  keep full immutable history and nothing is ever discarded. `operator_registry.resolve_version`
  is the other half of this, and W5's gate checks it before anything here is built on.

LINKED COPY, NOT A LIVE REFERENCE — the load-bearing design decision.

An import COPIES the operator into the project, stamped with `library_ref` (the library id
and the exact version taken), and the project copy versions independently from then on.
Editing it in Book B touches neither the library nor Book A. Publishing back is an explicit
act; pulling a newer version down is another.

The alternative — a live shared reference — would mean that sharpening an operator while
writing Book B silently changes what Book A's committed prose *claims to have been made
from*. The prose itself is immutable and safe, but its declared meaning would shift under it
without the author ever revisiting that book. That is not portability; it is the language
evolving on its own across books, which is the emergent behaviour the plan defers until
there is a corpus to prove it should. Linked copies give the author the portable library
today and leave that future buildable on the same mechanism.

NOTHING HERE IS A CANON WRITE. Promote, import, publish and pull are ontology operations.
There is no scene, no passage and no block path in this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from uuid import uuid4

from backend.database import writer_library_collection
from backend.services.writer import instrument, relations as relations_mod

#: The fields that constitute an operator's BODY — what varies across versions and what a
#: promote/publish carries up. Identity (id, author, name) is not in here.
BODY_FIELDS = (
    "definition", "rendering_intent", "examples", "negative_examples",
    "relations", "members", "kind",
)

PROMOTED = "library_promoted"
IMPORTED = "library_imported"
PUBLISHED = "library_published"
PULLED = "library_pulled"


class LibraryError(ValueError):
    """A library operation that must not happen, with the reason. Raised, not returned."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen() -> str:
    return f"lib_{uuid4().hex[:12]}"


def _out(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


def _body(operator: Dict[str, Any]) -> Dict[str, Any]:
    return {k: operator.get(k) for k in BODY_FIELDS if operator.get(k) is not None}


# ── the single-author guard (I5, across authors) ─────────────────────────────

def author_guard(operator_author: str, manuscript_author: str) -> Optional[str]:
    """The refusal reason if this operator may not render for this author, else None.

    REFUSES ONLY ON A KNOWN MISMATCH — both sides declared, and different. That asymmetry is
    deliberate and it is a migration decision as much as an honesty one: every operator and
    manuscript written before W5 has no author recorded, and a guard that refused on absence
    would refuse every existing project's every render. Absence is not evidence of a foreign
    hand; it is evidence that nobody has said yet.

    What it DOES catch is the case the wall is actually about: prose about to be rendered
    into your manuscript by an operator another person declared. That cannot be checked
    against your book by anyone, including you.
    """
    op = (operator_author or "").strip()
    ms = (manuscript_author or "").strip()
    if not op or not ms or op == ms:
        return None
    return (
        f"`{op}` declared this operator; this manuscript is `{ms}`'s. An operator carries "
        f"its author's declared meaning, and rendering from someone else's would put prose "
        f"in your book in a voice you never declared — which is exactly what an operator "
        f"exists to prevent. Import it into your own library and make it yours first."
    )


# ── reads ────────────────────────────────────────────────────────────────────

async def get(author: str, name: str) -> Optional[Dict[str, Any]]:
    return _out(await writer_library_collection.find_one({"author": author, "name": name}))


async def list_entries(author: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async for doc in writer_library_collection.find({"author": author}).sort("name", 1):
        out.append(_out(doc))
    return out


async def by_name(author: str) -> Dict[str, Dict[str, Any]]:
    return {e["name"]: e for e in await list_entries(author)}


async def resolve_version(author: str, name: str, version: int) -> Optional[Dict[str, Any]]:
    """A library entry AS IT STOOD at `version`. Old versions are never discarded."""
    doc = await writer_library_collection.find_one({"author": author, "name": name})
    if not doc:
        return None
    if int(doc.get("version", 1)) == int(version):
        return _out(doc)
    for prior in doc.get("history", []) or []:
        if int(prior.get("version", -1)) == int(version):
            restored = {k: v for k, v in doc.items() if k not in prior}
            restored.update(prior)
            restored.pop("retired_at", None)
            return _out(restored)
    return None


# ── transitive closure ───────────────────────────────────────────────────────

def dependencies_of(operator: Dict[str, Any]) -> List[str]:
    """Every operator name this one REFERS to: `requires` targets and assemblage members.

    Both are operator references, and both must travel with it. An operator whose declared
    context is absent would reach at render time for a referent that is not there — the
    dangling reference W3 refused to allow inside a project, refused again across projects.

    Associative edges (`evokes` and friends) are NOT dependencies: they are rendering-inert,
    so an operator is perfectly renderable without them. Dragging them along would import
    half an ontology to satisfy an edge that never fires.
    """
    deps = list(relations_mod.requires_of(operator))
    for member in operator.get("members") or []:
        target = member.get("name") if isinstance(member, dict) else str(member)
        if target:
            deps.append(target)
    seen: Set[str] = set()
    return [d for d in deps if not (d in seen or seen.add(d))]


def closure(
    root: str,
    available: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], List[str]]:
    """`root` plus everything it transitively refers to → `(ordered_names, missing)`.

    Dependencies come out BEFORE their dependents, so a caller writing them in order never
    creates a moment where a stored operator points at one that does not exist yet.

    `missing` is what could not be found. A caller must refuse and name them rather than
    import a partial ontology: half a declared context is not a smaller version of the
    author's language, it is a broken one.

    Terminates on cycles by construction — a name already visited is never expanded twice.
    """
    ordered: List[str] = []
    missing: List[str] = []
    visiting: Set[str] = set()
    done: Set[str] = set()

    def walk(name: str) -> None:
        if name in done or name in visiting:
            return          # already placed, or a cycle — either way, stop
        entry = available.get(name)
        if entry is None:
            if name not in missing:
                missing.append(name)
            return
        visiting.add(name)
        for dep in dependencies_of(entry):
            walk(dep)
        visiting.discard(name)
        done.add(name)
        ordered.append(name)

    walk(root)
    return ordered, missing


# ── the four operations ──────────────────────────────────────────────────────

async def promote(
    author: str,
    project_id: str,
    name: str,
    project_ontology: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Copy a project operator UP into the library, with its closure.

    The project keeps working exactly as it did — promote reads the project and writes the
    library, never the reverse.
    """
    if not (author or "").strip():
        raise LibraryError(
            "a library is one author's language, so promoting needs an author. Set the "
            "manuscript's author first."
        )

    ordered, missing = closure(name, project_ontology)
    if missing:
        raise LibraryError(
            f"cannot promote `{name}`: it refers to "
            f"{', '.join('`' + m + '`' for m in missing)}, which "
            f"{'is' if len(missing) == 1 else 'are'} not in this project. An operator whose "
            f"declared context is missing would reach for a referent that is not there."
        )

    promoted: List[Dict[str, Any]] = []
    for dep_name in ordered:
        operator = project_ontology[dep_name]
        existing = await get(author, dep_name)
        if existing:
            # Already in the library. Promote does not overwrite — `publish` is the
            # deliberate act for that, and silently replacing the author's library entry
            # because they promoted something that depends on it would be exactly the
            # spooky action the linked-copy model exists to avoid.
            promoted.append(existing)
            continue

        now = _now()
        doc = {
            "_id": _gen(),
            "author": author,
            "name": dep_name,
            "version": 1,
            "history": [],
            "source": {
                "project_id": project_id,
                "operator_id": operator.get("id"),
                "project_version": operator.get("version"),
            },
            "created_at": now,
            "updated_at": now,
            **_body(operator),
        }
        doc.setdefault("kind", "operator")
        await writer_library_collection.insert_one(doc)
        promoted.append(_out(doc))
        await instrument.record(
            PROMOTED, project_id, operators=[dep_name],
            extra={"author": author, "library_version": 1,
                   "with_closure": dep_name != name, "root": name},
        )

    return {"promoted": promoted, "root": name, "closure": ordered}


async def publish(
    author: str,
    project_id: str,
    name: str,
    operator: Dict[str, Any],
) -> Dict[str, Any]:
    """Push a project operator's CURRENT state up as a NEW library version.

    Explicit, and it touches no other project: a library version is available to be pulled,
    never pushed. Book A does not change because Book B published.
    """
    entry = await writer_library_collection.find_one({"author": author, "name": name})
    if not entry:
        raise LibraryError(
            f"`{name}` is not in your library yet — promote it before publishing to it"
        )

    prior = {k: entry.get(k) for k in BODY_FIELDS if k in entry}
    prior["version"] = entry.get("version", 1)
    prior["retired_at"] = _now()
    history = list(entry.get("history", []))
    history.append(prior)          # immutable: old versions are never discarded

    fields = _body(operator)
    fields["version"] = int(entry.get("version", 1)) + 1
    fields["history"] = history
    fields["updated_at"] = _now()
    fields["source"] = {
        "project_id": project_id,
        "operator_id": operator.get("id"),
        "project_version": operator.get("version"),
    }
    await writer_library_collection.update_one({"_id": entry["_id"]}, {"$set": fields})

    await instrument.record(
        PUBLISHED, project_id, operators=[name],
        extra={"author": author, "library_version": fields["version"]},
    )
    return await get(author, name)


def linked_copy(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A library entry → the fields a project copy is created from, with its lineage.

    `library_ref` pins the EXACT version taken. It is lineage, not a live link: it records
    where this copy came from so provenance can say so, and nothing reads it to fetch
    anything at render time.
    """
    body = _body(entry)
    body["library_ref"] = {
        "library_id": entry.get("id"),
        "author": entry.get("author"),
        "name": entry.get("name"),
        "version": entry.get("version"),
        "imported_at": _now().isoformat(),
    }
    return body
