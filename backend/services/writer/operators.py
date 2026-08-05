"""
Semant Writer W1 — the operator registry: the actuator registry, authored by the writer.

`director/capabilities.py` holds a table of actuators compiled into the source: what each
NEEDS and what it LEAVES BEHIND. This module is the same table with two changes, and only
two:

  1. it is PERSISTED (Mongo, the ledger) rather than compiled in, because the author
     writes these at the keyboard and they outlive the process;
  2. its entries are AUTHORED FROM DIALOGUE (`#create`) rather than by an engineer.

Everything else is deliberately identical in shape. An operator is a first-class stored
object — `{name, definition, rendering_intent, examples, negative_examples, relations,
author, version}` — and it is the ONLY evidence base the render call is allowed to draw
on (invariant 5, the author's-ontology wall).

PROPOSE → THE AUTHOR EDITS/CONFIRMS → STORE. `propose()` drafts an operator from the
author's description and returns it UNSAVED. `create()` is the separate, explicit write.
Nothing here ever stores an operator the author has not confirmed — the same
propose-never-commit shape as every other actuator in the kernel.

VERSIONING. An update bumps `version` and appends the prior body to `history`. Provenance
records the version that rendered a passage, so a passage stays readable against the
operator as it stood when it fired, not as it stands today.

SCOPE. Operators are project-scoped for W1 (`project_id`), which for now is the
manuscript id. W3's operator graph will need this key; nothing else uses it yet.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.database import writer_operator_collection
from backend.services.writer import instrument
from backend.services.writer import library
from backend.services.writer import relations as relations_mod

#: `kind` for a composite operator distilled from a recurring cluster (W4).
ASSEMBLAGE_KIND = "assemblage"

#: An operator name is a DSL token — it has to survive `/ name(arg)` unambiguously.
NAME_RE = re.compile(r"^[A-Za-z][\w-]*$")

#: The stored shape. Named once so the router, the render prompt and the tests cannot
#: drift apart on what an operator *is*.
OPERATOR_FIELDS = (
    "name", "definition", "rendering_intent", "examples",
    "negative_examples", "relations", "author", "version",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gen() -> str:
    return f"op_{uuid4().hex[:12]}"


def _out(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


class OperatorError(ValueError):
    """A malformed operator. Raised, not returned: there is nothing to render against."""


def _validate(name: str, definition: str) -> None:
    if not name or not NAME_RE.match(name):
        raise OperatorError(
            f"'{name}' is not a usable operator name — it must start with a letter and "
            f"contain only letters, digits, '_' or '-' (it has to survive `/ {name}`)"
        )
    if not (definition or "").strip():
        raise OperatorError(
            f"operator '{name}' has no definition. An operator with no definition is a "
            f"style prior with a label on it, and the render call would have nothing of "
            f"the author's to constrain itself to"
        )


class OperatorRegistry:
    """The author's ontology. CRUD + the `#create` authoring gesture."""

    # ── reads ────────────────────────────────────────────────────────────────

    async def get(self, project_id: str, name: str) -> Optional[Dict[str, Any]]:
        return _out(await writer_operator_collection.find_one(
            {"project_id": project_id, "name": name}
        ))

    async def list(self, project_id: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        async for doc in writer_operator_collection.find({"project_id": project_id}).sort("name", 1):
            out.append(_out(doc))
        return out

    async def by_name(self, project_id: str) -> Dict[str, Dict[str, Any]]:
        """The whole project ontology keyed by name — what relation validation reads."""
        return {op["name"]: op for op in await self.list(project_id)}

    async def resolve_version(
        self, project_id: str, name: str, version: int
    ) -> Optional[Dict[str, Any]]:
        """The operator AS IT STOOD at `version`, or None if that version is unrecoverable.

        THIS IS WHAT MAKES PROVENANCE MEAN ANYTHING (I4). Every committed passage pins
        `name@version`, and until W5 nothing could turn that pin back into a body — the
        version number was recorded but not resolvable, so "what wrote this?" had an answer
        the system could not actually produce. W5 makes portability possible, and
        portability is only safe if that question keeps its answer forever, so the resolver
        is the first thing built and the first thing tested.

        Resolution is local and exact: the CURRENT doc if its version matches, otherwise the
        matching entry in `history`, which `update()` has been appending since W1. Nothing
        is reconstructed or approximated — an unresolvable version returns None rather than
        the nearest thing, because a plausible substitute is exactly the fabrication the
        audit trail exists to refuse.
        """
        doc = await writer_operator_collection.find_one(
            {"project_id": project_id, "name": name}
        )
        if not doc:
            return None

        if int(doc.get("version", 1)) == int(version):
            return _out(doc)

        for prior in doc.get("history", []) or []:
            if int(prior.get("version", -1)) == int(version):
                # A history entry holds the fields that VARY across versions; the rest
                # (id, name, project, author) are stable properties of the operator.
                restored = {k: v for k, v in doc.items() if k not in prior}
                restored.update(prior)
                restored.pop("retired_at", None)
                return _out(restored)

        return None

    async def resolve_provenance(
        self, project_id: str, provenance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Can every operator this passage names still be produced? `{resolved, missing}`.

        The audit-trail check in one call: hand it a committed passage's provenance and it
        answers whether the passage can still say what made it. `missing` being non-empty is
        a broken audit trail, which is why the W5 gate runs this over every pre-existing
        record before anything else is built on top.
        """
        resolved: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []
        for stamp in (provenance or {}).get("operators", []) or []:
            name, version = stamp.get("name"), stamp.get("version")
            body = await self.resolve_version(project_id, name, version) if version else None
            if body is None:
                missing.append({"name": name, "version": version})
            else:
                resolved.append({
                    "name": name,
                    "version": version,
                    "source": stamp.get("source"),
                    "definition": body.get("definition", ""),
                    "rendering_intent": body.get("rendering_intent", ""),
                    # W5 — where this operator came from, when it was imported.
                    "library_ref": body.get("library_ref"),
                })
        return {"resolved": resolved, "missing": missing}

    async def set_relations(
        self, project_id: str, name: str, relations: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """Replace an operator's relations. Validated, then versioned like any other edit.

        Relations are part of the operator's identity, not metadata beside it: a passage
        rendered by `interiority v2` (which requires `threshold`) rests on different
        grounding than one rendered by `interiority v1` (which required nothing). So an
        edge edit bumps the version, and provenance stays honest across the change.

        The author draws these by hand, so this commits directly — it is authoring, not a
        model proposal, and the propose-never-commit rule is about what the MODEL writes.
        """
        doc = await self.get(project_id, name)
        if not doc:
            return None
        index = await self.by_name(project_id)
        validated = relations_mod.validate_relations(name, relations, index)
        return await self.update(project_id, name, {"relations": validated})

    async def import_from_library(
        self, project_id: str, author: str, name: str
    ) -> Dict[str, Any]:
        """Import a library operator into a project as a LINKED COPY, with its closure.

        The copy is independently versioned from here on: editing it in this project touches
        neither the library nor any other project. `library_ref` records the exact version
        taken, so provenance can say where it came from without anything fetching at render.

        The whole closure comes down together, or nothing does — an operator whose `requires`
        targets or assemblage members are absent would reach at render for a referent that
        is not there.
        """
        entries = await library.by_name(author)
        if name not in entries:
            raise OperatorError(
                f"`{name}` is not in `{author}`'s library. Promote it from the project where "
                f"you defined it first."
            )

        ordered, missing = library.closure(name, entries)
        if missing:
            raise OperatorError(
                f"cannot import `{name}`: it refers to "
                f"{', '.join('`' + m + '`' for m in missing)}, which "
                f"{'is' if len(missing) == 1 else 'are'} not in your library. Promote "
                f"{'it' if len(missing) == 1 else 'them'} too — an operator without its "
                f"declared context cannot render honestly."
            )

        imported: List[Dict[str, Any]] = []
        for dep in ordered:                      # dependencies first, never a dangling ref
            if await self.get(project_id, dep):
                continue                         # already here; import does not overwrite
            entry = entries[dep]
            body = library.linked_copy(entry)
            # ONE write, so the copy lands at v1 — the author has not edited it yet. This is
            # safe to do with relations attached because the closure is walked in dependency
            # order, so every edge target already exists by the time its dependent is written.
            imported.append(await self.create(
                project_id, dep,
                definition=body.get("definition") or entry.get("rendering_intent") or dep,
                rendering_intent=body.get("rendering_intent") or "",
                examples=body.get("examples") or [],
                negative_examples=body.get("negative_examples") or [],
                relations=body.get("relations") or [],
                author=author,
                kind=body.get("kind") or "operator",
                members=body.get("members") or [],
                library_ref=body["library_ref"],
            ))
            await instrument.record(
                library.IMPORTED, project_id, operators=[dep],
                extra={"author": author, "library_version": entry.get("version"),
                       "with_closure": dep != name, "root": name},
            )

        return {"imported": imported, "root": name, "closure": ordered}

    async def pull_from_library(
        self, project_id: str, author: str, name: str
    ) -> Dict[str, Any]:
        """Bring a newer library version down into a project. Author-reviewed, never automatic.

        This is the ONLY way a library change reaches a project. Publishing from Book B makes
        a version available; Book A keeps rendering exactly as before until the author comes
        and asks for it.
        """
        entry = await library.get(author, name)
        if not entry:
            raise OperatorError(f"`{name}` is not in `{author}`'s library")
        current = await self.get(project_id, name)
        if not current:
            raise OperatorError(
                f"`{name}` is not in this project — import it rather than pulling"
            )

        ref = current.get("library_ref") or {}
        if ref.get("version") == entry.get("version"):
            return {"operator": current, "changed": False,
                    "detail": f"already at library v{entry.get('version')}"}

        body = library.linked_copy(entry)
        patch = {k: v for k, v in body.items() if k != "library_ref"}
        patch["library_ref"] = body["library_ref"]
        updated = await self.update(project_id, name, patch)

        await instrument.record(
            library.PULLED, project_id, operators=[name],
            extra={"author": author, "library_version": entry.get("version"),
                   "from_version": ref.get("version")},
        )
        return {"operator": updated, "changed": True,
                "detail": f"pulled library v{entry.get('version')}"}

    async def create_assemblage(
        self,
        project_id: str,
        name: str,
        member_names: List[str],
        rendering_intent: str,
        definition: str = "",
        author: str = "",
    ) -> Dict[str, Any]:
        """Author an assemblage — a composite operator distilled from a recurring cluster.

        AN ASSEMBLAGE IS AN OPERATOR. Same schema, same versioning, same render path; it
        carries `kind: assemblage` and a `members` list recording what it was distilled
        from, WITH VERSIONS.

        `members` IS LINEAGE, NOT A BLEND. It records ancestry so the author can ask "what
        did this come from?" — it is not a render input, and nothing downstream reads it
        into a prompt. Rendering an assemblage renders ONE span from its own authored
        intent, exactly like any other operator, which is what keeps composition sequential
        and provenance able to say which operator produced which prose. The fused-field
        version, where the members jointly condition one span, is Tier 3 precisely because
        that answer stops being available.

        If the author wants the members present at render time they add `requires` edges by
        hand (W3). This never wires them automatically: an edge the author did not draw is
        an edge they cannot be said to have declared.

        MEMBERS ARE OPERATOR REFERENCES (I5). Each is looked up in the ontology, so an
        assemblage can no more contain "like Tolstoy" than a `requires` edge could.

        `rendering_intent` is REQUIRED and is the author's. The strawman
        (`assemblages.strawman`) is only ever a starting point they edit.
        """
        # The intent check comes FIRST. `_validate` would otherwise catch a blank intent as
        # a generic "no definition", and the author would get a message about style priors
        # when what they actually need to hear is the one thing this gate is about: the
        # system can show you the recurrence, it cannot tell you what it means.
        if not (rendering_intent or "").strip():
            raise OperatorError(
                f"assemblage '{name}' needs a rendering intent in your own words. The "
                f"system can show you that these operators recur together; what their "
                f"recurrence MEANS is the one thing it must not decide for you."
            )
        if len(member_names or []) < 2:
            raise OperatorError(
                f"assemblage '{name}' needs at least two members — a cluster of one is "
                f"just the operator it already is"
            )
        _validate(name, definition or rendering_intent)

        index = await self.by_name(project_id)
        members: List[Dict[str, Any]] = []
        for raw in member_names:
            member = str(raw or "").strip()
            op = index.get(member)
            if op is None:
                raise OperatorError(
                    f"`{member}` is not an operator in this project. An assemblage is built "
                    f"from operators you have defined — that is what keeps it from naming "
                    f"something your ontology never declared. "
                    f"Define it first with `#create {member}: …`."
                )
            if member == name:
                raise OperatorError(f"assemblage '{name}' cannot contain itself")
            if any(m["name"] == member for m in members):
                continue
            # The version is part of the lineage: this assemblage was distilled from the
            # operators AS THEY STOOD, and a later edit to a member does not retroactively
            # change what it came from.
            members.append({"name": member, "version": op.get("version")})

        created = await self.create(
            project_id, name,
            definition=(definition or "").strip() or rendering_intent.strip(),
            rendering_intent=rendering_intent.strip(),
            author=author,
        )
        return await self.update(
            project_id, name, {"kind": ASSEMBLAGE_KIND, "members": members}
        )

    async def resolve(self, project_id: str, names: List[str]) -> Dict[str, Any]:
        """Names → `{"found": {name: operator}, "missing": [name, ...]}`.

        The render call's pre-flight. Missing names are RETURNED, not raised: an undefined
        operator is a refusal with a reason ("you have not defined `threshold`"), which is
        a better answer than an exception and a much better answer than rendering it
        anyway from generic priors.
        """
        found: Dict[str, Any] = {}
        missing: List[str] = []
        for name in names:
            op = await self.get(project_id, name)
            if op:
                found[name] = op
            else:
                missing.append(name)
        return {"found": found, "missing": missing}

    # ── the `#create` gesture: propose → confirm → store ─────────────────────

    def propose(self, name: str, description: str, author: str = "") -> Dict[str, Any]:
        """Draft an operator from the author's description. UNSAVED and uncommitted.

        Deliberately NOT an LLM call. The author's description IS the definition — asking
        a model to expand it would seed the ontology with priors the author never wrote,
        which is precisely what invariant 5 exists to prevent. The model's help belongs
        later (W2), on prose, not here on the ontology.
        """
        _validate(name, description)
        return {
            "name": name,
            "definition": (description or "").strip(),
            "rendering_intent": "",
            "examples": [],
            "negative_examples": [],
            "relations": [],
            "author": author or "",
            "version": 1,
            "committed": False,          # the author has not confirmed it yet
        }

    async def create(
        self,
        project_id: str,
        name: str,
        definition: str,
        rendering_intent: str = "",
        examples: Optional[List[str]] = None,
        negative_examples: Optional[List[str]] = None,
        relations: Optional[List[Dict[str, str]]] = None,
        author: str = "",
        kind: str = "operator",
        members: Optional[List[Dict[str, Any]]] = None,
        library_ref: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """The explicit author-confirmed write. Raises on a duplicate name.

        `kind`/`members`/`library_ref` exist so an assemblage or an imported operator can be
        stored in ONE write. An import that created and then patched would land the operator
        at version 2 before the author had touched it, and `version` is supposed to count
        the author's edits — a passage pinned to "v1" should mean the first thing they had.
        """
        _validate(name, definition)
        if relations:
            index = await self.by_name(project_id)
            # The operator being created is itself a valid target for its own edges to be
            # checked against (self-relation is rejected inside `validate_relations`).
            index.setdefault(name, {"name": name, "relations": []})
            relations = relations_mod.validate_relations(name, relations, index)
        if await self.get(project_id, name):
            raise OperatorError(
                f"operator '{name}' already exists in this project — update it instead of "
                f"redefining it, so passages that cite version 1 stay readable"
            )
        now = _now()
        doc = {
            "_id": _gen(),
            "project_id": project_id,
            "name": name,
            "definition": definition.strip(),
            "rendering_intent": (rendering_intent or "").strip(),
            "examples": list(examples or []),
            "negative_examples": list(negative_examples or []),
            "relations": list(relations or []),
            "author": author or "",
            # W4 — `operator` or `assemblage`. An assemblage is the same object with a
            # lineage; the kind is what lets a surface show that without guessing.
            "kind": kind or "operator",
            "members": list(members or []),
            # W5 — lineage of an imported operator: which library entry and which exact
            # version this copy was taken from. Nullable, so every pre-W5 operator is valid
            # as it stands. It is a RECORD, never a live link: nothing reads it to fetch.
            "library_ref": library_ref,
            "version": 1,
            "history": [],
            "created_at": now,
            "updated_at": now,
        }
        await writer_operator_collection.insert_one(doc)
        return _out(doc)

    async def update(self, project_id: str, name: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Edit an operator. Bumps `version`; the prior body is appended to `history`."""
        doc = await writer_operator_collection.find_one({"project_id": project_id, "name": name})
        if not doc:
            return None

        editable = ("definition", "rendering_intent", "examples", "negative_examples",
                    "relations", "author", "kind", "members", "library_ref")
        fields = {k: v for k, v in (patch or {}).items() if k in editable and v is not None}
        if not fields:
            return _out(doc)
        if "definition" in fields:
            _validate(name, fields["definition"])
        if "relations" in fields:
            index = await self.by_name(project_id)
            fields["relations"] = relations_mod.validate_relations(
                name, fields["relations"], index
            )

        prior = {k: doc.get(k) for k in ("definition", "rendering_intent", "examples",
                                         "negative_examples", "relations", "members",
                                         "library_ref", "version")}
        prior["retired_at"] = _now()
        history = list(doc.get("history", []))
        history.append(prior)

        fields["version"] = int(doc.get("version", 1)) + 1
        fields["history"] = history
        fields["updated_at"] = _now()
        await writer_operator_collection.update_one(
            {"_id": doc["_id"]}, {"$set": fields}
        )
        return await self.get(project_id, name)

    async def delete(self, project_id: str, name: str) -> bool:
        res = await writer_operator_collection.delete_one({"project_id": project_id, "name": name})
        return res.deleted_count > 0

    # ── the evidence base handed to the render call ──────────────────────────

    def as_evidence(self, operator: Dict[str, Any]) -> str:
        """One operator → the author's own words, as the render prompt will see them.

        Every line here is text the AUTHOR wrote. That is the whole contract: this
        function must never add an exemplar, a genre hint, or a style adjective of its
        own, because whatever it adds becomes indistinguishable from the author's
        ontology at the point of generation. It is a formatter, not a writer.
        """
        parts = [f"OPERATOR `{operator.get('name', '')}` (v{operator.get('version', 1)})"]
        parts.append(f"  the author defines it as: {operator.get('definition', '').strip()}")
        if operator.get("rendering_intent"):
            parts.append(f"  when it renders, the author wants: {operator['rendering_intent'].strip()}")
        for ex in operator.get("examples") or []:
            parts.append(f"  the author's example of it: {str(ex).strip()}")
        for neg in operator.get("negative_examples") or []:
            parts.append(f"  the author says this is NOT it: {str(neg).strip()}")
        for rel in operator.get("relations") or []:
            if isinstance(rel, dict) and rel.get("target"):
                parts.append(
                    f"  the author relates it to `{rel['target']}`: {rel.get('kind', 'related')}"
                )
        return "\n".join(parts)


operator_registry = OperatorRegistry()
