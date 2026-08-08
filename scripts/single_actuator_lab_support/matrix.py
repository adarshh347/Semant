"""HARNESS-001C2 — the pre-registered phrase-robustness matrix.

WHAT PRE-REGISTRATION IS FOR, precisely. An open-vocabulary organ can be made to look capable by
trying phrases until one lands and reporting the survivor. The resulting number reads as a
hit-rate and is the outcome of a search. Nothing in a trace distinguishes the two after the
fact — a phrase that was tried third and a phrase that was tried thirtieth leave identical
records — so the only place the distinction can live is BEFORE collection, in a list that is
written down and then hashed.

`lock.phrases_sha256` is that hash. The suite declares it, the first live capture freezes it into
a collection marker, and every later `--live` and `--report` recomputes it. A phrase edited
mid-collection changes the digest and the run refuses to continue. That is a fact about the run
rather than a promise about my conduct, which is the only kind of guarantee worth having here.

The same applies to fixtures: swapping an image under a stable id would silently change what
every phrase was tested against, so the fixture ids and their content hashes are locked too.

This module holds the pre-registration half — loading, digesting, and refusing. The runner that
executes the matrix lives beside it and goes through the same firewall every other arm uses.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from . import contract

SUITE_VERSION = "phrase-matrix-suite.v1"
SUITE_SCHEMA = "phrase-matrix-suite.schema.json"

SUITES_DIR = os.path.join(contract.LABS_ROOT, "suites")

#: The gate role. If this family returns nothing on a fixture, no phrase failure on that fixture
#: may be attributed to the phrase.
AVAILABILITY = "availability_control"


class SuiteError(Exception):
    """A suite that cannot be trusted to bound a matrix. Always fatal."""


class LockViolation(SuiteError):
    """The frozen phrase list or fixture set moved after collection began.

    Its own exception type because it is not one more validation failure: every other error here
    says the suite is malformed, and this one says the EXPERIMENT was altered while it ran. A
    reader skimming for what went wrong should not have to distinguish those from the message.
    """


# ── loading and validation ────────────────────────────────────────────────────────────────────

def suite_path(suite_id: str, suites_dir: Optional[str] = None) -> str:
    suites_dir = suites_dir or SUITES_DIR
    for ext in (".yaml", ".yml", ".json"):
        candidate = os.path.join(suites_dir, suite_id + ext)
        if os.path.exists(candidate):
            return candidate
    raise SuiteError(f"no suite named {suite_id!r} in {suites_dir}")


def load_suite(path_or_id: str, *, suites_dir: Optional[str] = None) -> Dict[str, Any]:
    path = path_or_id if os.path.exists(path_or_id) else suite_path(path_or_id, suites_dir)
    return contract.load_manifest(path)


def _schema_dir_has_suite_schema(schema_dir: str) -> bool:
    return os.path.exists(os.path.join(schema_dir, SUITE_SCHEMA))


def validate_suite(suite: Dict[str, Any], *, schema_dir: Optional[str] = None) -> List[str]:
    schema_dir = schema_dir or contract.SCHEMA_DIR
    if not _schema_dir_has_suite_schema(schema_dir):
        return [f"{SUITE_SCHEMA} not found in {schema_dir}"]
    with open(os.path.join(schema_dir, SUITE_SCHEMA), "r") as fh:
        schema = json.load(fh)
    import rehearsal_run as rr
    return rr.validate(suite, schema)


def check_suite(suite: Dict[str, Any], *, source: str = "<suite>",
                schema_dir: Optional[str] = None) -> Dict[str, Any]:
    """Schema-validate, then check what a schema cannot express.

    Each extra check corresponds to a way the matrix could produce numbers that look like a
    measurement and are not.
    """
    errors = validate_suite(suite, schema_dir=schema_dir)
    if errors:
        raise SuiteError(f"{source}: " + "; ".join(errors))

    from backend.services.director import capabilities
    lock = suite["actuator_lock"]
    if capabilities.get(lock) is None:
        raise SuiteError(f"{source}: actuator_lock {lock!r} is not in the production capability "
                         f"table")

    roles = [f["role"] for f in suite["phrase_families"]]
    if AVAILABILITY not in roles:
        # Without a gate, every empty in the matrix is uninterpretable: nothing distinguishes a
        # phrase this organ cannot bind from an organ that was never working on that fixture.
        raise SuiteError(f"{source}: the suite declares no {AVAILABILITY!r} family, so no phrase "
                         f"failure it records could be attributed to the phrase")

    seen: Dict[str, str] = {}
    for family in suite["phrase_families"]:
        for phrase in family["phrases"]:
            if phrase in seen:
                raise SuiteError(f"{source}: phrase {phrase!r} appears in both "
                                 f"{seen[phrase]!r} and {family['family']!r}; a phrase in two "
                                 f"families would be counted twice in every hit-rate")
            seen[phrase] = family["family"]
        # Anything beyond the card's own list has to say why, and may only have been added
        # before the first live call.
        if family["role"] == "replication_control" and not family.get("justification"):
            raise SuiteError(f"{source}: family {family['family']!r} was added to the frozen list "
                             f"and records no justification")

    ids = [f["fixture_id"] for f in suite["fixtures"]]
    if len(set(ids)) != len(ids):
        raise SuiteError(f"{source}: duplicate fixture_id")

    for fixture in suite["fixtures"]:
        abs_path = os.path.join(contract.REPO_ROOT, fixture["path"])
        if not os.path.exists(abs_path):
            raise SuiteError(f"{source}: fixture {fixture['fixture_id']!r} not found at "
                             f"{fixture['path']}")
        actual = contract.sha256_file(abs_path)
        if actual != fixture["sha256"]:
            raise SuiteError(f"{source}: fixture {fixture['fixture_id']!r} content hash moved — "
                             f"suite says {fixture['sha256']}, file is {actual}")

    declared = {p for f in suite["phrase_families"] for p in f["phrases"]}
    for phrase in suite["arms"]["wrapper_equivalence"]["phrases"]:
        if phrase not in declared:
            raise SuiteError(f"{source}: wrapper_equivalence names {phrase!r}, which is not in "
                             f"any frozen family — the equivalence arm cannot test a phrase the "
                             f"matrix never froze")
    return suite


# ── the locks ─────────────────────────────────────────────────────────────────────────────────

def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def phrase_digest(suite: Dict[str, Any]) -> str:
    """Digest over the frozen phrases, their roles and their families.

    Roles are included, not just the strings: moving `bicycle` from `negative_control` to
    `fold_target` would leave the phrase set identical while inverting what a hit means.
    """
    return _digest([[f["family"], f["role"], list(f["phrases"])]
                    for f in sorted(suite["phrase_families"], key=lambda f: f["family"])])


def fixture_digest(suite: Dict[str, Any]) -> str:
    """Digest over fixture ids paired with their CONTENT hashes."""
    return _digest(sorted((f["fixture_id"], f["sha256"]) for f in suite["fixtures"]))


def compute_locks(suite: Dict[str, Any]) -> Dict[str, str]:
    return {"phrases_sha256": phrase_digest(suite),
            "fixtures_sha256": fixture_digest(suite)}


def locks_match_declaration(suite: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Does the suite's own `lock` block match what its content actually digests to?

    Separate from the collection check, because they catch different mistakes. This one catches a
    suite whose declared lock was never filled in (the placeholder digest) or was edited by hand.
    """
    computed = compute_locks(suite)
    declared = suite.get("lock") or {}
    return (declared.get("phrases_sha256") == computed["phrases_sha256"]
            and declared.get("fixtures_sha256") == computed["fixtures_sha256"]), computed


# ── the collection marker ─────────────────────────────────────────────────────────────────────

#: `runs_root` (and every other path below) resolves INSIDE the function rather than as a default
#: argument. `runs_root: str = contract.RUNS_ROOT` binds at def time, so redirecting the module —
#: a test pointing it at a tmp dir, a future `--runs-root` flag — would silently have no effect
#: and the freeze check would consult the real runs directory while claiming to consult another.
#: `GroqPlanner` carries the same note for the same reason after `= DEFAULT_MODEL` made an env
#: rebind invisible to every planner constructed after import. Found here by a test that expected
#: a refusal and got none.

def collection_marker(suite_id: str, runs_root: Optional[str] = None) -> str:
    return os.path.join(runs_root or contract.RUNS_ROOT, suite_id, "collection.json")


def collection_started(suite_id: str, runs_root: Optional[str] = None) -> bool:
    return os.path.exists(collection_marker(suite_id, runs_root))


def begin_collection(suite: Dict[str, Any], *, runs_root: Optional[str] = None,
                     captured_at: Optional[str] = None) -> Dict[str, Any]:
    """Freeze the locks at the moment the first live call is about to happen.

    Written BEFORE the first capture rather than after, so a run that dies halfway still leaves
    the evidence that collection had begun — otherwise a crashed first attempt would look, to the
    next invocation, exactly like a matrix that had never started, and the phrases would be
    editable again.
    """
    marker = collection_marker(suite["suite_id"], runs_root)
    if os.path.exists(marker):
        return contract.read_json(marker)
    payload = {
        "suite_id": suite["suite_id"],
        "locks": compute_locks(suite),
        "collection_started_at": captured_at,
        "actuator_lock": suite["actuator_lock"],
        "call_budget": suite["call_budget"],
        "fixtures": [{"fixture_id": f["fixture_id"], "sha256": f["sha256"]}
                     for f in suite["fixtures"]],
        "phrases": [{"family": f["family"], "role": f["role"], "phrases": list(f["phrases"])}
                    for f in suite["phrase_families"]],
    }
    contract.write_json(marker, payload)
    return payload


def assert_locks_unchanged(suite: Dict[str, Any], *,
                           runs_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Refuse to proceed if the frozen list moved after collection began.

    Returns the marker when collection has started, None when it has not. Both the suite's own
    declaration and the marker are checked, in that order: a suite whose declared lock does not
    match its content is malformed whether or not anything has run yet.
    """
    ok, computed = locks_match_declaration(suite)
    if not ok:
        raise LockViolation(
            f"suite {suite['suite_id']!r} declares locks that do not match its content. "
            f"Declared phrases={((suite.get('lock') or {}).get('phrases_sha256') or '')[:12]}… "
            f"computed={computed['phrases_sha256'][:12]}…. Run `matrix --plan` to write the "
            f"correct digests BEFORE collection begins; after it begins this is an edit to a "
            f"frozen experiment.")

    if not collection_started(suite["suite_id"], runs_root):
        return None

    marker = contract.read_json(collection_marker(suite["suite_id"], runs_root))
    frozen = marker.get("locks") or {}
    if frozen.get("phrases_sha256") != computed["phrases_sha256"]:
        raise LockViolation(
            f"the phrase matrix changed after collection began. Frozen "
            f"{frozen.get('phrases_sha256', '')[:12]}…, now {computed['phrases_sha256'][:12]}…. "
            f"Adding or editing a phrase once results are visible turns measurement into "
            f"result-searching; start a new suite id instead.")
    if frozen.get("fixtures_sha256") != computed["fixtures_sha256"]:
        raise LockViolation(
            f"the fixture set changed after collection began. Frozen "
            f"{frozen.get('fixtures_sha256', '')[:12]}…, now {computed['fixtures_sha256'][:12]}…. "
            f"Every phrase already collected was tested against the old set.")
    return marker


# ── the planned cells ─────────────────────────────────────────────────────────────────────────

def phrase_role(suite: Dict[str, Any], phrase: str) -> Optional[str]:
    for family in suite["phrase_families"]:
        if phrase in family["phrases"]:
            return family["role"]
    return None


def phrase_family(suite: Dict[str, Any], phrase: str) -> Optional[str]:
    for family in suite["phrase_families"]:
        if phrase in family["phrases"]:
            return family["family"]
    return None


def all_phrases(suite: Dict[str, Any]) -> List[str]:
    return [p for f in suite["phrase_families"] for p in f["phrases"]]


def slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text.strip().lower()).strip("-")[:40]


def cell_run_id(suite_id: str, fixture_id: str, phrase: str, mode: str) -> str:
    return f"{suite_id}/{fixture_id}/{mode}__{slug(phrase)}"


def plan_cells(suite: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every capture the suite calls for, enumerated before any of them runs.

    The plan is data and is emitted by `--plan`, so what was going to be collected is inspectable
    before it is collected — the point being that a reader can check the matrix was not shaped
    around its own results.
    """
    cells: List[Dict[str, Any]] = []
    full = suite["arms"]["full_matrix"]
    for fixture in suite["fixtures"]:
        for phrase in all_phrases(suite):
            cells.append({
                "run_id": cell_run_id(suite["suite_id"], fixture["fixture_id"], phrase,
                                      full["mode"]),
                "arm": "full_matrix",
                "mode": full["mode"],
                "fixture_id": fixture["fixture_id"],
                "phrase": phrase,
                "family": phrase_family(suite, phrase),
                "role": phrase_role(suite, phrase),
            })
    wrapper = suite["arms"]["wrapper_equivalence"]
    for fixture in suite["fixtures"]:
        for phrase in wrapper["phrases"]:
            cells.append({
                "run_id": cell_run_id(suite["suite_id"], fixture["fixture_id"], phrase,
                                      wrapper["mode"]),
                "arm": "wrapper_equivalence",
                "mode": wrapper["mode"],
                "fixture_id": fixture["fixture_id"],
                "phrase": phrase,
                "family": phrase_family(suite, phrase),
                "role": phrase_role(suite, phrase),
            })
    return cells


def plan(suite: Dict[str, Any]) -> Dict[str, Any]:
    cells = plan_cells(suite)
    ok, computed = locks_match_declaration(suite)
    return {
        "suite_id": suite["suite_id"],
        "actuator_lock": suite["actuator_lock"],
        "call_budget": suite["call_budget"],
        "fixtures": [f["fixture_id"] for f in suite["fixtures"]],
        "phrases": all_phrases(suite),
        "families": {f["family"]: f["role"] for f in suite["phrase_families"]},
        "cells": cells,
        "capture_count": len(cells),
        "sam_invocations_planned": len(cells),
        "planner_samples": suite["planner_sampling"]["samples"],
        "planner_grants_sam_attempts": not suite["planner_sampling"]["planning_only"],
        "locks_declared_match_content": ok,
        "computed_locks": computed,
        "declared_locks": suite.get("lock"),
    }


# ── running the matrix ────────────────────────────────────────────────────────────────────────

def fixture_by_id(suite: Dict[str, Any], fixture_id: str) -> Dict[str, Any]:
    for fixture in suite["fixtures"]:
        if fixture["fixture_id"] == fixture_id:
            return fixture
    raise SuiteError(f"no fixture {fixture_id!r} in suite {suite['suite_id']!r}")


def cell_manifest(suite: Dict[str, Any], cell: Dict[str, Any], *,
                  warm: bool) -> Dict[str, Any]:
    """One matrix cell → a `single-actuator-manifest.v1`.

    Synthesised rather than checked in as 56 near-identical YAML files: the SUITE is the
    pre-registered artifact, and 56 hand-written manifests would be 56 places for the frozen
    phrase to drift from it. Each still carries the full manifest contract, so every capture goes
    through exactly the same `capture()` and the same firewall as a hand-written one — a matrix
    cell is not a lighter kind of run.
    """
    fixture = fixture_by_id(suite, cell["fixture_id"])
    return {
        "schema_version": contract.MANIFEST_VERSION,
        "lab_id": suite["suite_id"],
        "run_id": cell["run_id"],
        "title": f"{cell['fixture_id']} · {cell['phrase']!r} · {cell['mode']}",
        "why": (f"Matrix cell from the pre-registered suite {suite['suite_id']!r}: family "
                f"{cell['family']!r} (role {cell['role']!r}) against fixture "
                f"{cell['fixture_id']!r}. The phrase was frozen before any live call in this "
                f"lane and may not be changed now."),
        "actuator_lock": suite["actuator_lock"],
        "mode": cell["mode"],
        "call_budget": suite["call_budget"],
        "image": {
            "source": "local_fixture",
            "path": fixture["path"],
            "sha256": fixture["sha256"],
            "note": (fixture["provenance"].get("observed") or "")[:400],
        },
        "prompt": None,
        "control_phrase": cell["phrase"],
        "allowed_params": ["phrase"],
        "model_expectation": {
            "checkpoint": "facebook/sam3",
            "preprocessing_version": "sam3-pcs-v1",
            "conf": 0.25,
            "imgsz": 1024,
            "max_instances": 16,
        },
        # The FIRST capture of a live matrix pays the cold start; the rest run against a resident
        # predictor in the same process. Recorded per capture from what was measured, never from
        # what this field asked for.
        "warm_or_cold": "warm" if warm else "cold",
        "repeat_count": 1,
        "expected_condition": _expected_condition(cell["role"]),
        "review": {
            "protocol": "human_visual",
            "gold_mask_path": None,
            "questions": list((suite.get("review") or {}).get("questions") or []),
        },
        # A matrix cell's pair is the SAME phrase on the SAME fixture through the other arm.
        # Declared here so `compare` attributes only across a stated pairing.
        "pair_with": (cell_run_id(suite["suite_id"], cell["fixture_id"], cell["phrase"],
                                  "organ_direct")
                      if cell["arm"] == "wrapper_equivalence" else None),
    }


def _expected_condition(role: Optional[str]) -> str:
    """The role's pre-registered expectation, as the manifest's own vocabulary.

    `fold_target` is `open` and not `positive`: whether local fold geometry is findable here is
    the QUESTION, and declaring it positive in advance would write the hoped-for answer into the
    record that is supposed to settle it.
    """
    return {
        "availability_control": "positive",
        "object_scope": "open",
        "fold_target": "open",
        "replication_control": "open",
        "adversarial_abstraction": "adversarial",
        "negative_control": "negative",
    }.get(role or "", "open")


def run_live(suite: Dict[str, Any], capture_fn: Any, *, runs_root: Optional[str] = None,
             now: Optional[str] = None, only: Optional[List[str]] = None,
             planner_client: Any = None) -> Dict[str, Any]:
    """Collect the matrix. One capture per cell, each with its own budget of one.

    NO RETRIES, ANYWHERE. An empty result is a result and is recorded as one. A runner that
    re-issued a call on empty would convert the matrix's most important observation — that a
    frozen phrase returns nothing — into a sampling artifact, and would do it invisibly.

    Cells already frozen are SKIPPED rather than re-run, so an interrupted collection resumes
    without spending a second attempt on anything already measured.
    """
    runs_root = runs_root or contract.RUNS_ROOT
    assert_locks_unchanged(suite, runs_root=runs_root)
    marker = begin_collection(suite, runs_root=runs_root, captured_at=now)

    cells = plan_cells(suite)
    if only:
        cells = [c for c in cells if c["fixture_id"] in only or c["run_id"] in only]

    results: List[Dict[str, Any]] = []
    warm = False
    for cell in cells:
        run_path = contract.run_dir(cell["run_id"], runs_root)
        if contract.is_frozen(run_path):
            results.append({**cell, "status": "already_frozen", "run_path": run_path})
            warm = True
            continue
        manifest = cell_manifest(suite, cell, warm=warm)
        manifest_path = os.path.join(run_path, "manifest.json")
        contract.write_json(manifest_path, manifest)
        out = capture_fn(manifest_path, runs_root=runs_root)
        warm = True                       # the predictor is resident for the rest of the process
        organ = out["trace"]["organ_observation"]
        results.append({
            **cell,
            "status": "captured",
            "run_path": out["run_path"],
            "organ_status": organ["status"],
            "instances": organ["instance_count"],
            "attribution": out["score"]["verdict"]["attribution"],
        })

    planner = sample_planner(suite, client=planner_client, runs_root=runs_root, now=now)
    return {"suite_id": suite["suite_id"], "marker": marker, "cells": results,
            "planner": planner}


# ── planner stability, which spends no SAM attempts ───────────────────────────────────────────

def sample_planner(suite: Dict[str, Any], *, client: Any = None,
                   runs_root: Optional[str] = None, now: Optional[str] = None,
                   ) -> Dict[str, Any]:
    """Independent planner receipts for the unchanged prompt. PLANNING ONLY.

    The suite declares `planning_only: true` in advance and this function honours it
    structurally: it calls `firewall.authorize`, never `firewall.invoke`. The firewall therefore
    records what the planner asked for and what was refused, and its `attempts` list stays empty
    — so a planner receipt cannot be mistaken for an organ result by anything downstream, and
    `sam_invocations: 0` is a measured property of the run rather than a claim in a docstring.

    C1 called the planner once per capture and happened to receive `folded drapery` twice. That
    is not stability, and this exists because it was reported as if it might be.
    """
    from .firewall import Firewall
    from . import planner as lab_planner

    runs_root = runs_root or contract.RUNS_ROOT
    sampling = suite["planner_sampling"]
    samples: List[Dict[str, Any]] = []

    for index in range(int(sampling["samples"])):
        fw = Firewall(suite["actuator_lock"], call_budget=suite["call_budget"])
        proposal = lab_planner.propose(sampling["prompt"], firewall=fw, client=client)
        selected: Optional[Dict[str, Any]] = None
        for step in proposal.steps:
            auth = fw.authorize(step.actuator, step.params)
            if auth.allowed and selected is None:
                selected = {"actuator": auth.actuator, "params": dict(auth.params)}
            # every remaining step is still put to the firewall, so its refusal is recorded
        fw.dropped_params.extend(proposal.dropped)
        samples.append({
            "sample": index + 1,
            "kind": "planning_only",         # never an organ observation; see the docstring
            "planner_status": proposal.status,
            "model": proposal.model,
            "role": proposal.role,
            "selected_actuator": (selected or {}).get("actuator"),
            "selected_phrase": ((selected or {}).get("params") or {}).get("phrase"),
            "declared_params": (selected or {}).get("params") or {},
            "refused_out_of_lock": fw.requested_unlocked(),
            "refusals": [r.to_dict() for r in fw.refusals],
            "dropped_params": list(fw.dropped_params),
            "raw_proposal": proposal.raw,
            "sam_invocations": len(fw.attempts),      # must be 0, and is asserted to be
            "notes": list(proposal.notes),
        })

    payload = {
        "suite_id": suite["suite_id"],
        "prompt": sampling["prompt"],
        "prompt_sha256": contract.sha256_bytes(sampling["prompt"].encode("utf-8")),
        "planning_only": True,
        "declared_model_contract": sampling.get("model_contract"),
        "sampled_at": now,
        "samples": samples,
        "total_sam_invocations": sum(s["sam_invocations"] for s in samples),
    }
    contract.write_json(os.path.join(runs_root, suite["suite_id"], "planner-samples.json"),
                        payload)
    return payload
