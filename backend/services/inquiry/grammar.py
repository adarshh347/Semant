"""
HARNESS-001A — the Perceptual Action Grammar, enforced in Python.

The twin of `frontend/src/differential/perceptualActions.js`, reading the same JSON contract and
applying the same laws by the same names. It is a SECOND ENFORCEMENT of one grammar, not a second
grammar: every closed set, every per-action declaration and every law comes from
`contracts/perceptual-action-grammar.v1.json`, and the parity tests fail the moment the two
runtimes disagree about what an action is.

WHY THE BACKEND NEEDS THIS AT ALL. The `/agent` Director path asks a model to choose backend
ACTUATORS directly, which is a different vocabulary answering a different question ("what globally
scoped operation has an executor"). The prompt-facing mind proposes PERCEPTUAL ACTS — what a
curator might do next — and those must be judged by the curator's grammar, not the machine's. Lane
A's whole job is to make the public action law shared rather than frontend-local.

THE RULES CARRIED OVER VERBATIM, because they are why the seam holds:

  1. FAIL CLOSED. `normalize_action` returns None, never a partial object. A caller that gets an
     object back may render it or hand it to Lane B, and a half-valid action treated as real is
     precisely the failure the grammar exists to prevent.

  2. PAYLOAD KEYS ARE CLAMPED TO THE DECLARED VOCABULARY. Every key not in the action's
     `required` + `optional` is dropped and RECORDED. This is the guard that stops a model from
     smuggling in geometry, a mask, a region id or a confidence — evidence it has no way to
     possess and no right to assert. `groq_planner._clamp_params` does the same thing one layer
     down for actuators; this is that discipline applied to acts.

  3. THE LAWS ARE DATA. A model may never author `challenge_percept`; nothing may claim a
     dispatch was sent. Both are `when` clauses in the contract, interpreted by the same tiny
     predicate reader in both languages, so neither can be softened in one runtime alone.

PURE MODULE. No database, no network, no model, no clock it does not accept.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import grammar_contract

_G = grammar_contract()

SCHEMA_VERSION: str = _G["schema_version"]

ACTION_TYPES: Tuple[str, ...] = tuple(_G["closed_sets"]["action_types"])
TARGETS: Tuple[str, ...] = tuple(_G["closed_sets"]["targets"])
SOURCES: Tuple[str, ...] = tuple(_G["closed_sets"]["sources"])
STATUSES: Tuple[str, ...] = tuple(_G["closed_sets"]["statuses"])
GEOMETRY_MODES: Tuple[str, ...] = tuple(_G["closed_sets"]["geometry_modes"])

TARGET_LABELS: Dict[str, str] = dict(_G["target_labels"])
NEVER_APPLIES: Tuple[str, ...] = tuple(_G["never_applies"])
MODEL_FORBIDDEN_ACTIONS: Tuple[str, ...] = tuple(_G["model_forbidden_actions"])

_MSG: Dict[str, str] = dict(_G["messages"])
_LAWS: List[Dict[str, Any]] = list(_G["laws"])


def _keys(vocabulary: Sequence[Mapping[str, Any]]) -> Tuple[str, ...]:
    return tuple(str(row["key"]) for row in vocabulary)


VOCABULARIES: Dict[str, Tuple[Mapping[str, Any], ...]] = {
    name: tuple(rows) for name, rows in _G["vocabularies"].items()
}

FIELD_ROLE_KEYS = _keys(VOCABULARIES["field_roles"])
TRACE_ROLE_KEYS = _keys(VOCABULARIES["trace_roles"])
RELATION_ROLE_KEYS = _keys(VOCABULARIES["relation_roles"])
MANUSCRIPT_MODE_KEYS = _keys(VOCABULARIES["manuscript_modes"])
CHALLENGE_TYPE_KEYS = _keys(VOCABULARIES["challenge_types"])


def closed_set(name: str) -> Tuple[str, ...]:
    """A named closed set as plain keys. A vocabulary resolves to its keys; a bare set to itself.

    The one indirection the contract introduces: an action's `enums` NAME a set rather than
    repeating its members, so the members cannot drift from the vocabulary they came from.
    """
    vocab = VOCABULARIES.get(name)
    if vocab is not None:
        return _keys(vocab)
    return tuple(_G["closed_sets"].get(name, ()))


class ActionSpec:
    """One family's declaration, read from the contract."""

    __slots__ = ("type", "target", "required", "optional", "enums",
                 "needs_geometry", "requires_confirmation")

    def __init__(self, type_: str, row: Mapping[str, Any]):
        self.type = type_
        self.target: str = row["target"]
        self.required: Tuple[str, ...] = tuple(row.get("required", ()))
        self.optional: Tuple[str, ...] = tuple(row.get("optional", ()))
        self.enums: Dict[str, Tuple[str, ...]] = {
            key: closed_set(set_name) for key, set_name in (row.get("enums") or {}).items()
        }
        self.needs_geometry: bool = bool(row.get("needs_geometry"))
        self.requires_confirmation: bool = bool(row.get("requires_confirmation"))

    @property
    def payload_keys(self) -> Tuple[str, ...]:
        """Every key this action may carry. Guard 2 clamps to exactly this."""
        return self.required + self.optional


SPEC: Dict[str, ActionSpec] = {t: ActionSpec(t, row) for t, row in _G["actions"].items()}


def spec_for(type_: Any) -> Optional[ActionSpec]:
    return SPEC.get(str(type_)) if isinstance(type_, str) else None


# ── labels ───────────────────────────────────────────────────────────────────

_LABEL_RULES: Dict[str, Dict[str, Any]] = dict(_G["default_labels"])


def _vocabulary_label(vocabulary: str, key: Any) -> str:
    """The label for a key, or the raw key when unknown, or '' when absent.

    Never raises. A payload with no role reaches `validate_action` and is REFUSED there; a crash
    during label derivation is not failing closed, it is failing open with a traceback.
    """
    if key is None:
        return ""
    for row in VOCABULARIES.get(vocabulary, ()):
        if row.get("key") == key:
            return str(row.get("label") or key)
    return str(key)


def default_label(type_: str, payload: Optional[Mapping[str, Any]] = None) -> str:
    rule = _LABEL_RULES.get(type_)
    if rule is None:
        return str(type_)
    literal = rule.get("literal")
    if literal:
        return str(literal)
    role = _vocabulary_label(rule.get("vocabulary", ""),
                            (payload or {}).get(rule.get("role_key", ""))).lower()
    return f"{rule.get('prefix', '')}{role or rule.get('fallback', '')}{rule.get('suffix', '')}"


# ── the law reader ───────────────────────────────────────────────────────────

def _at_path(obj: Any, path: str) -> Any:
    cur = obj
    for key in str(path).split("."):
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _law_applies(law: Mapping[str, Any], action: Mapping[str, Any], spec: ActionSpec) -> bool:
    """The whole predicate interpreter, mirroring `lawApplies` in the JS validator."""
    when = law.get("when") or {}
    payload = action.get("payload") or {}
    if "action" in when and action.get("type") != when["action"]:
        return False
    if "needs_geometry" in when and bool(spec.needs_geometry) != bool(when["needs_geometry"]):
        return False
    if "source_in" in when and action.get("source") not in when["source_in"]:
        return False
    if "payload_path_is_true" in when and _at_path(payload, when["payload_path_is_true"]) is not True:
        return False
    if "payload_key_truthy" in when and not payload.get(when["payload_key_truthy"]):
        return False
    if "payload_key_outside_set" in when:
        rule = when["payload_key_outside_set"]
        value = payload.get(rule["key"])
        if value is None or value in closed_set(rule["set"]):
            return False
    return True


# ── validation ───────────────────────────────────────────────────────────────

def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _fill(template: str, **vars_: Any) -> str:
    out = str(template)
    for key, value in vars_.items():
        out = out.replace("{" + key + "}", str(value))
    return out


class Verdict:
    """`valid` plus the reasons. Warnings TRAVEL WITH the action rather than being logged: a
    proposal admitting its own weakness on the card is the point, and a warning nobody sees is a
    warning that was not made."""

    __slots__ = ("valid", "errors", "warnings")

    def __init__(self, valid: bool, errors: Sequence[str], warnings: Sequence[str]):
        self.valid = valid
        self.errors = list(errors)
        self.warnings = list(warnings)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Verdict(valid={self.valid}, errors={self.errors}, warnings={self.warnings})"


def validate_action(action: Any) -> Verdict:
    """Judge one action. Errors refuse it; warnings ride along."""
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(action, Mapping):
        return Verdict(False, [_MSG["not_an_object"]], warnings)
    spec = spec_for(action.get("type"))
    if spec is None:
        return Verdict(False, [_fill(_MSG["unknown_action_type"], type=action.get("type"))], warnings)

    if not _non_empty_string(action.get("id")):
        errors.append(_MSG["missing_id"])
    if not _non_empty_string(action.get("label")):
        errors.append(_MSG["missing_label"])
    if action.get("source") not in SOURCES:
        errors.append(_fill(_MSG["unknown_source"], value=action.get("source")))
    if action.get("status") not in STATUSES:
        errors.append(_fill(_MSG["unknown_status"], value=action.get("status")))
    if action.get("target") not in TARGETS:
        errors.append(_fill(_MSG["unknown_target"], value=action.get("target")))
    if action.get("target") != spec.target:
        errors.append(_fill(_MSG["target_mismatch"], value=action.get("target"), type=spec.type))
    created_at = action.get("createdAt")
    if not isinstance(created_at, (int, float)) or isinstance(created_at, bool):
        errors.append(_MSG["created_at_not_a_number"])

    payload = action.get("payload") or {}
    for key in spec.required:
        value = payload.get(key)
        if isinstance(value, (list, tuple)):
            present = len(value) > 0
        elif isinstance(value, str):
            present = bool(value.strip())
        else:
            present = value is not None
        if not present:
            errors.append(_fill(_MSG["payload_required"], type=spec.type, key=key))
    for key, allowed in spec.enums.items():
        value = payload.get(key)
        if value is not None and value not in allowed:
            errors.append(_fill(_MSG["payload_not_in_vocabulary"],
                                type=spec.type, key=key, value=value))

    for law in _LAWS:
        if not _law_applies(law, action, spec):
            continue
        (errors if law.get("kind") == "error" else warnings).append(str(law["message"]))

    deduped: List[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    return Verdict(not errors, errors, deduped)


# ── construction ─────────────────────────────────────────────────────────────

def clamp_payload(type_: str, raw: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Keep only the keys this action declares. Returns (kept, dropped_keys).

    GUARD 2, and the reason it is a function rather than a line inside `normalize_action`: the
    model-backed framer calls it directly so the dropped keys land in refusal telemetry. A key
    silently discarded is how you fail to notice that a model is repeatedly trying to author
    geometry, which is the failure that matters most and shows up nowhere else.
    """
    if not isinstance(raw, Mapping):
        return {}, []
    spec = spec_for(type_)
    if spec is None:
        # An unknown action is about to be refused by name; carrying its invented payload forward
        # would put model-authored data into a refusal record where a reader might mistake it for
        # something the system considered real.
        return {}, sorted(str(k) for k in raw.keys())
    allowed = set(spec.payload_keys)
    kept = {k: v for k, v in raw.items() if k in allowed}
    dropped = sorted(str(k) for k in raw.keys() if k not in allowed)
    return kept, dropped


def normalize_action(raw: Any, *, now: float = 0.0, action_id: Optional[str] = None,
                     clamp: bool = True) -> Optional[Dict[str, Any]]:
    """Canonicalise a raw proposal into a full action, or return None.

    GUARD 1. Returning None rather than a partially-filled dict is deliberate: a caller that gets
    a dict back may put it in an `InquiryFrame` and hand it to Lane B, and a half-valid action
    consumed as real is exactly the failure this grammar exists to prevent.
    """
    if not isinstance(raw, Mapping):
        return None
    type_ = raw.get("type")
    spec = spec_for(type_)
    if spec is None:
        return None

    raw_payload = raw.get("payload") or {}
    payload = dict(clamp_payload(str(type_), raw_payload)[0]) if clamp else dict(raw_payload)

    label = raw.get("label")
    label = label.strip() if isinstance(label, str) and label.strip() else default_label(str(type_), payload)

    raw_prov = raw.get("provenance") or {}
    action: Dict[str, Any] = {
        "id": raw.get("id") or action_id or "",
        "type": str(type_),
        "label": label,
        "intent": raw["intent"] if isinstance(raw.get("intent"), str) else "",
        "source": raw["source"] if raw.get("source") in SOURCES else "system",
        "status": raw["status"] if raw.get("status") in STATUSES else "proposed",
        # The spec decides, not the caller: a proposal cannot declare itself confirmation-free
        # and thereby skip the user.
        "requiresConfirmation": spec.requires_confirmation,
        "target": spec.target,
        "createdAt": raw["createdAt"] if isinstance(raw.get("createdAt"), (int, float))
        and not isinstance(raw.get("createdAt"), bool) else now,
        "payload": payload,
        "warnings": list(raw["warnings"]) if isinstance(raw.get("warnings"), list) else [],
        "provenance": {"planner": None, "promptExcerpt": None, "matched": [],
                       **{k: v for k, v in raw_prov.items()}},
    }

    verdict = validate_action(action)
    if not verdict.valid:
        return None
    for warning in verdict.warnings:
        if warning not in action["warnings"]:
            action["warnings"].append(warning)
    return action


def validate_action_list(actions: Sequence[Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Keep the good, report the bad. Nothing is swallowed."""
    kept: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for index, action in enumerate(actions or ()):
        verdict = validate_action(action)
        if verdict.valid:
            kept.append(dict(action))
        else:
            rejected.append({"index": index, "errors": verdict.errors, "raw": action})
    return kept, rejected


def action_needs_geometry(action: Any) -> bool:
    spec = spec_for((action or {}).get("type") if isinstance(action, Mapping) else None)
    return bool(spec and spec.needs_geometry)


def model_may_author(type_: str) -> bool:
    """May a MODEL propose this action type at all?

    `challenge_percept` is the human's veto over the circuit (P1 addendum §3.1). The refusal is
    also expressed as a law on `source: model_suggested`, and this function is the same fact
    asked BEFORE a proposal is built, so a framer can record the request for human action rather
    than construct something that will be thrown away.
    """
    return type_ not in MODEL_FORBIDDEN_ACTIONS
