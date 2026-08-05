"""
CIRCUIT-003 M6 — epistemic status: HOW a produced item is known.

Every producer in this system already records WHAT made an item (`provenance`: model,
adapter, run). None of them records what KIND OF KNOWING it is. That distinction has been
implicit in the architecture from the beginning — `semantic_read` produces a READING and
never a MARK precisely because a sentence about the image is a different kind of claim than
an extent in it — but it lived in the actuator table, where nothing downstream could read it.

M6 makes it a FIELD, because M6 introduces the first producer whose output does not come
from the image at all. A historical claim about Schinkel's intent is not weak evidence; it is
a different species of evidence, and the only safe way to carry it is to say so on the item
itself.

THE FIVE STATUSES, and the boundary that matters:

    visible       the extent is present in the picture — you can point at it
    measured      computed from the image signal — a number, not an opinion
    interpretive  a reading ABOUT the image, resting on what was gathered
    sourced       from OUTSIDE the image, carrying a citation            ← the walled one
    uncertain     produced, but the producer will not vouch for which of the above

The first three are all IMAGE statuses: whatever their confidence, they were obtained by
looking at the picture. `sourced` was not. That is the wall.

WHY A WALL AND NOT A CONVENTION. The failure this prevents is laundering: a sourced claim
("Schinkel intended a civic temple") re-tagged as `visible` and thereby becoming citable as
something the picture shows. It would not look like a lie at any point — each step is a
plausible edit — and the resulting mark would be indistinguishable from one a segmenter
authored. So the transition is not discouraged, it is IMPOSSIBLE through the supported API
(`retag` refuses it) and DETECTED when someone bypasses the API and edits the dict directly
(`guard` refuses it). Both paths are tested.

The wall is deliberately one-directional and narrow: `sourced` may not become an image
status. Everything else may be sharpened or softened freely — `uncertain` → `measured` is a
producer becoming more confident about its own reading, which is nobody's business but its own.

SCOPE. M6 seeds the field and the wall. The epistemic LAYER — surfacing status in review, the
UI, filtering a composition by what kind of knowing it rests on — is M5, which generalizes
`guard()` from "the research actuator's output" to "everything entering the quarantine".

PURE MODULE. No database, no network, no model. It is a vocabulary and two guards.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class EpistemicStatus(str, Enum):
    """How an item is known. A `str` enum so a descriptor stays plain JSON."""
    VISIBLE = "visible"            # an extent present in the picture
    MEASURED = "measured"          # computed from the image signal
    INTERPRETIVE = "interpretive"  # a reading about the image
    SOURCED = "sourced"            # from outside the image, with a citation
    UNCERTAIN = "uncertain"        # the producer will not vouch for a kind


#: The statuses obtainable BY LOOKING AT THE IMAGE. `sourced` is the one that is not, and
#: this set is the whole definition of the wall: nothing may cross from `sourced` into here.
IMAGE_STATUSES = frozenset({
    EpistemicStatus.VISIBLE, EpistemicStatus.MEASURED,
    EpistemicStatus.INTERPRETIVE, EpistemicStatus.UNCERTAIN,
})

#: The status that may never be overwritten. A set of one, named rather than hardcoded,
#: because M5 will likely add a second (a curator's own testimony is not image-derived either).
WALLED_STATUSES = frozenset({EpistemicStatus.SOURCED})

#: The descriptor `type` a sourced statement travels as. It is NOT a mark type — the mark
#: types are region_mask / brush_field / trace_mark / relation_mark, and a sourced statement
#: is deliberately none of them so that `_quarantined_marks()` in the Director's runner cannot
#: pick one up and feed it to `connect_marks` as if it were evidence on the image.
SOURCED_STATEMENT_TYPE = "sourced_statement"

#: The descriptor key. One string, defined once, so a rename cannot half-happen.
STATUS_KEY = "epistemic_status"


class EpistemicViolation(Exception):
    """An attempt to move a claim across the wall, or to publish one that already crossed.

    An exception rather than a returned error because there is no sensible way to continue.
    A caller that gets this has a bug that would otherwise ship a laundered claim, and the
    only correct handling is to stop.
    """


# ── the wall ─────────────────────────────────────────────────────────────────

def _coerce(status: Any) -> Optional[EpistemicStatus]:
    """A status value in any accepted form → the enum member, or None if unrecognised."""
    if isinstance(status, EpistemicStatus):
        return status
    try:
        return EpistemicStatus(str(status))
    except (ValueError, TypeError):
        return None


def permitted_statuses(producer: Optional[str]) -> frozenset:
    """The statuses a given producer's output is allowed to carry.

    THE WHOLE RULE, in one place: a producer may claim what its table entry says, or it may
    claim `uncertain`. Nothing else.

    That asymmetry is the generalized wall. `uncertain` is the only move available because it
    is the only one that makes a claim WEAKER — a producer is always entitled to say it is not
    sure, and never entitled to promote its own output. Without the asymmetry the guard would
    be a spell-checker: it would catch `visble` and wave through a semantic reading arriving
    tagged `measured`, which is the crossing that actually matters.

    A WALLED default (`sourced`) admits no alternative at all, not even `uncertain`. A
    quotation whose relevance is thin is still a quotation; its weakness belongs in
    `confidence`, and moving it to `uncertain` would put it in the image-status family it can
    never belong to.
    """
    default = default_status_for(producer)
    if default in WALLED_STATUSES:
        return frozenset({default})
    return frozenset({default, EpistemicStatus.UNCERTAIN})


def declare(producer: Optional[str], status: Any) -> EpistemicStatus:
    """A producer declaring the kind of its own output. Refuses an unpermitted claim.

    This is the write-side twin of `guard`'s read-side check, and they consult the same
    `permitted_statuses` so they cannot drift into disagreeing about what is legal.
    """
    target = _coerce(status)
    if target is None:
        raise EpistemicViolation(f"'{status}' is not an epistemic status")
    allowed = permitted_statuses(producer)
    if target not in allowed:
        raise EpistemicViolation(
            f"producer '{producer}' may not claim '{target.value}' — it is classified "
            f"'{default_status_for(producer).value}' and may only weaken that to "
            f"'{EpistemicStatus.UNCERTAIN.value}'")
    return target


def retag(descriptor: Dict[str, Any], status: EpistemicStatus) -> Dict[str, Any]:
    """Change an item's epistemic status. The ONLY supported way to do so.

    Enforces the same rule `guard` reads: a claim may be weakened to `uncertain` or restated as
    its producer's classification, and a walled (`sourced`) claim may not be moved at all.
    Returns a NEW descriptor — the original is left alone, so a caller holding the pre-edit item
    still holds the truth about what the producer actually claimed.
    """
    target = _coerce(status)
    if target is None:
        raise EpistemicViolation(f"'{status}' is not an epistemic status")
    current = _coerce(descriptor.get(STATUS_KEY))
    if current in WALLED_STATUSES and target is not current:
        raise EpistemicViolation(
            f"cannot retag a '{current.value}' claim as '{target.value}': a claim from outside "
            f"the image can never become one the image shows")
    if target not in permitted_statuses(descriptor.get("producer")):
        raise EpistemicViolation(
            f"cannot retag a '{descriptor.get('producer')}' claim as '{target.value}': "
            f"a producer's output may only be weakened to "
            f"'{EpistemicStatus.UNCERTAIN.value}', never promoted")
    return {**descriptor, STATUS_KEY: target.value}


def guard(descriptors: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Verify a batch of descriptors before it enters the quarantine. Returns them unchanged.

    M5 widens this from research output to EVERYTHING. In M6 it ran on one producer's
    descriptors, where it was redundant by construction — the only thing that built them always
    wrote `sourced`. Called on every producer it stops being redundant: it becomes the single
    place where a claim's stated kind is checked against the kind its producer is classified as,
    on every path into the quarantine.

    Five ways a descriptor fails, all of them the same underlying error — a claim presenting
    itself as better-founded than it is:

      1. no status at all. An untagged descriptor reaching review is indistinguishable from a
         `visible` one to anyone reading the surface, so silence is not permitted.
      2. an unrecognised status string.
      3. a status its producer may not claim — the improper crossing (see `permitted_statuses`).
         This is the generalized wall: not just sourced→visible, but interpretive→measured,
         uncertain→visible, and every other promotion.
      4. a `sourced_statement` carrying any status other than `sourced`.
      5. a `sourced_statement` with no citation (`external_source_service`: no source, no
         claim — the research twin of "no ground → no mark").

    Raising rather than filtering is deliberate. A silently dropped laundered claim is a bug
    nobody investigates; a raised one is a bug someone fixes.
    """
    out: List[Dict[str, Any]] = []
    for d in descriptors:
        raw = d.get(STATUS_KEY)
        if raw is None:
            raise EpistemicViolation(
                f"descriptor from producer '{d.get('producer')}' carries no epistemic status — "
                f"an untagged claim reads as a confident one")
        status = _coerce(raw)
        if status is None:
            raise EpistemicViolation(f"unknown epistemic status {raw!r}")
        if status not in permitted_statuses(d.get("producer")):
            raise EpistemicViolation(
                f"producer '{d.get('producer')}' published a '{status.value}' claim — it is "
                f"classified '{default_status_for(d.get('producer')).value}' and may only "
                f"weaken that to '{EpistemicStatus.UNCERTAIN.value}'")
        if d.get("type") == SOURCED_STATEMENT_TYPE:
            if status is not EpistemicStatus.SOURCED:
                raise EpistemicViolation(
                    f"a sourced statement is tagged '{raw}' — it may only be "
                    f"'{EpistemicStatus.SOURCED.value}'")
            if not (d.get("citation") or {}).get("url"):
                raise EpistemicViolation("a sourced statement with no citation is not sourced")
        out.append(d)
    return out


# ── defaults for the producers that already exist ────────────────────────────
# Deliberately keyed on the FROZEN producer vocabulary (the `PRODUCER_*` constants in
# `suggestion_service`), not on the descriptor `type`. Two producers can share a type and
# differ in kind: `negative_space` and `material_field` are both `brush_field`, but one
# inverts a mask that already exists and the other reads a learned embedding. Both happen to
# be `measured` today; keying on the producer is what leaves room for them not to be.
#
# ROLES-001 SHRANK THIS TABLE. A producer whose claim IS its organ's or thinker's own output now
# takes its status from that role's `epistemic_ceiling` (`role_registry`). Keeping both was
# keeping two tables that had to agree with nothing making them agree — and the drift would have
# been invisible, because each side reads plausibly on its own. `sam_refine`,
# `florence_find_parts`, `grounded_sam_find_parts`, `material_field`, `rhythm`, `pressure_zone`,
# `recession`, `shading`, `fall_of_light`, `semantic_read` and `planner` moved there.
# `default_status_for` returns exactly what it returned before for every one of them, and
# `test_role_registry.py` pins the whole mapping against a verbatim copy of the pre-change table.
#
# WHAT STAYS IS THE INTERESTING HALF. Every entry below is a producer whose claim is NOT simply
# its role's output, and each is a case a derived table would have got wrong:
#
#   `find_similar`        runs on DINOv2 (ceiling `measured`) and hands back a real extent on
#                         another image — `visible`, i.e. STRONGER than its organ's ceiling,
#                         because it is not reporting a measurement at all.
#   `presence_check`,
#   `enumerate`           run on the grounding detector (ceiling `visible`) but answer a QUESTION
#                         instead of minting an extent — `interpretive`, i.e. weaker.
#   `negative_space`      is `measured` and pure-python (its actuator declares `capability=None`);
#                         no organ executes it.
#   the rest              have no single role behind them at all.

_DEFAULTS: Dict[str, EpistemicStatus] = {
    # -- extents: something is there and you can point at it --------------------
    "find_similar": EpistemicStatus.VISIBLE,      # a real extent, on another image
    # -- measurements: computed off the signal, no opinion in them --------------
    "negative_space": EpistemicStatus.MEASURED,
    "architectural_axis": EpistemicStatus.MEASURED,
    # M5 — NOT measured, and this is the entry that keeps `uncertain` from being decorative.
    #
    # `external_limit`'s refusal turns on `MIN_PROJECTIVE_SPREAD`, which the producer itself
    # labels UNCALIBRATED: a placeholder picked to sit between a synthetic frontal field and a
    # synthetic converging one, with none of the standing of `architectural_axis`'s 0.25 (that
    # one was measured on 18 real images). A gate whose threshold is admittedly synthetic can
    # let through a limit that is not there, so what comes out the other side is not a
    # measurement — it is a reading that has not been checked. Calling it `measured` would let
    # the calibration debt disappear behind a confident-sounding word. When activation
    # re-measures the threshold on real frontal vs receding photographs, this moves to MEASURED
    # and the change is one line.
    "external_limit": EpistemicStatus.UNCERTAIN,
    # -- readings: a claim ABOUT the picture, resting on it ---------------------
    # (`semantic_read` moved to the `semantic_annotator` role: it mints both label proposals and
    # relations, and both are the VLM's reading rather than the image's testimony — a naming is
    # an interpretation even when the extent it names is `visible`. That reasoning is now the
    # role's ceiling, which is where it belongs, since it is a fact about the thinker.)
    "presence_check": EpistemicStatus.INTERPRETIVE,
    "enumerate": EpistemicStatus.INTERPRETIVE,
    "connect_marks": EpistemicStatus.INTERPRETIVE,
    "compose_percept": EpistemicStatus.INTERPRETIVE,
    # CONCEPT-SEG-001 — the other half of a SAM 3 result, and the reason this table still exists.
    #
    # `concept_segment` (the mask) takes `measured` from the `sam3` organ role. This is the LABEL,
    # and it has no role because it has no single producer: the concept may come from the
    # `dissector` thinker, from a fixed `domain_profiles` vocabulary, or from the curator's own
    # phrase. What they have in common is that none of them is the image — nothing in the picture
    # says "this is a collar" — so the naming is `interpretive` whoever wrote it.
    #
    # Emitting it separately is what lets a wrong naming be rejected WITHOUT discarding a correct
    # measurement. SF-004-R2 §4.3 is the case: `shoulder fabric` at confidence 0.27–0.43 returned
    # a clean mask of the background. One status for both would force a choice between trusting
    # the whole thing and binning the whole thing, and it is neither.
    "concept_naming": EpistemicStatus.INTERPRETIVE,
    # -- from outside the image -------------------------------------------------
    "historical_source": EpistemicStatus.SOURCED,
}


def default_status_for(producer: Optional[str]) -> EpistemicStatus:
    """The status a producer's output carries unless it says otherwise.

    ROLES-001: the ROLE behind the producer is asked first. That ordering is the point — a
    producer wired to a new organ or thinker inherits its ceiling with no edit here, which is
    the failure mode `model_residency` already documents at length (a thing wired in one place
    and registered in another, with nothing connecting the two).

    `_DEFAULTS` then covers the producers no single role executes, and only those.

    An UNKNOWN producer gets `uncertain`, never a flattering guess. A producer wired after both
    tables were written is exactly the case where a confident default would be wrong, and
    `uncertain` is both honest and loud enough to get one of them updated.
    """
    # Imported lazily: `role_registry` imports THIS module for the status vocabulary, so a
    # module-level import here would be a cycle. It also keeps `epistemics` importable on its
    # own, which is what lets the pure guards be unit-tested with no registry in the picture.
    from backend.services.role_registry import ceiling_for_producer
    from_role = ceiling_for_producer(producer)
    if from_role is not None:
        return from_role
    return _DEFAULTS.get(str(producer or ""), EpistemicStatus.UNCERTAIN)


def classified_producers() -> frozenset:
    """Every producer that has an EXPLICIT classification, from either table.

    ROLES-001 split the classification across two surfaces — the role's `epistemic_ceiling` and
    `_DEFAULTS` — so "is this producer classified?" needs one place to be asked. Without it the
    M5 no-drift guard would have to know about both, and would go stale the moment a third
    surface appeared.

    The distinction this preserves is the one that matters: an unclassified producer FALLS to
    `uncertain`, which is safe, and a producer classified AS `uncertain` (`external_limit`) is a
    deliberate statement. `default_status_for` cannot tell them apart; this can.
    """
    from backend.services.role_registry import ROLES
    from_roles = {p for role in ROLES.values() for p in role.producers}
    return frozenset(from_roles | set(_DEFAULTS))


def stamp(descriptor: Dict[str, Any], *,
          status: Optional[EpistemicStatus] = None) -> Dict[str, Any]:
    """Set a descriptor's status in place and return it — for producers building a new item.

    Unlike `retag` this is a first write, so there is nothing to launder: it refuses to
    overwrite an existing status at all, walled or not. A producer that has already declared
    its epistemic kind is not second-guessed by the plumbing.

    An EXPLICIT status still goes through `declare`, so "the producer said so" is not a way
    around the classification — a producer may weaken its own claim, never promote it.
    """
    if descriptor.get(STATUS_KEY) is not None:
        return descriptor
    producer = descriptor.get("producer")
    chosen = declare(producer, status) if status is not None else default_status_for(producer)
    descriptor[STATUS_KEY] = EpistemicStatus(chosen).value
    return descriptor


# ── degradation: when a producer's own numbers say "only just" ────────────────

#: How far above its refusal threshold a reading must sit before it counts as measured rather
#: than marginal.
#:
#: UNCALIBRATED — say so, in the voice the producers themselves use for such numbers. Two is a
#: conservative round choice, not a measured one: it says "clear the bar by the height of the
#: bar again". It is deliberately on the cautious side, because the failure it prevents (a
#: barely-there field presented as a measurement) is worse than the one it causes (a real field
#: labelled uncertain, which a reviewer can still accept). Re-measuring the producers' own
#: thresholds is what would let this be set rather than picked.
MARGINAL_FACTOR = 2.0


def is_marginal(value: Optional[float], threshold: Optional[float], *,
                factor: float = MARGINAL_FACTOR) -> bool:
    """Did this reading only just clear its own refusal gate?

    The producers already refuse below `threshold` — that half is settled, and this does not
    touch it. This is about the band just ABOVE the line, where a producer currently returns a
    field with the same confident shape as one from an unmistakable surface. A rhythm at relief
    0.051 against a 0.05 gate and a rhythm at 0.4 are not the same kind of claim, and until now
    nothing downstream could tell them apart.

    Returns False when either number is missing: an unknown confidence is not evidence of
    marginality, and inventing one to be safe would put `uncertain` on producers that never
    reported a number at all (the deterministic geometry operators), which is the decorative
    use of the word this whole entry exists to avoid.
    """
    if value is None or threshold is None:
        return False
    try:
        return float(value) < float(threshold) * float(factor)
    except (TypeError, ValueError):
        return False


def status_for(producer: Optional[str], *, confidence: Optional[float] = None,
               threshold: Optional[float] = None, degraded: bool = False) -> EpistemicStatus:
    """The rigorous classification for one produced item: the table, weakened by the run.

    Two ways a producer lands on `uncertain`:
      STRUCTURAL — its table entry says so, because something about the producer is unresolved
                   for every run it will ever do (`external_limit`'s uncalibrated gate).
      PER-RUN    — this particular reading only just cleared its own threshold, or the caller
                   knows the run took a degraded path (a fallback, a partial input).

    A walled (`sourced`) producer is unaffected by either: see `permitted_statuses`.
    """
    default = default_status_for(producer)
    if default in WALLED_STATUSES:
        return default
    if degraded or is_marginal(confidence, threshold):
        return EpistemicStatus.UNCERTAIN
    return default
