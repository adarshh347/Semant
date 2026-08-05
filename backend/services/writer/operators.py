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
from backend.services.writer import relations as relations_mod

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
    ) -> Dict[str, Any]:
        """The explicit author-confirmed write. Raises on a duplicate name."""
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

        editable = ("definition", "rendering_intent", "examples", "negative_examples", "relations", "author")
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
                                         "negative_examples", "relations", "version")}
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
