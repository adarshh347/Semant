"""
HARNESS-003B — telling a short answer from a cut-off one, and the boundaries this driver keeps.

002R's compiler parsed, produced almost nothing, and was reported as an honest empty result. Every
fact in that report was correct. It was still the wrong report, because a model that stops on
`length` and happens to close its JSON returns a graph indistinguishable from a genuinely short one
— and the two send a reader to opposite places.

The tests below are mostly about what is NOT claimed. `unknown` is the value under scrutiny
throughout: a chain that could not consult a truncation signal must say so rather than report the
stage as verified-untruncated.
"""
from __future__ import annotations

import pathlib

import pytest

from backend.schemas.inquiry_stage import (StageAttempt, StageAttemptOutcome, StageName,
                                           SubstageEvent, TruncationSource, duration_ms_between)
from backend.services.inquiry_session import outcomes


class _Receipt:
    def __init__(self, notes=(), **fields):
        self.notes = list(notes)
        for key, value in fields.items():
            setattr(self, key, value)


class _Producer:
    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)


# ── 1. which route answered, and the difference between unknown and none ─────

def test_a_typed_field_on_the_receipt_is_read_first():
    """The route that cannot be mistaken. It does not exist on `ModelReceipt` yet — see the finding
    — and is read first so the day Lane A adds one, the better source is used with no edit here."""
    hit = outcomes.detect_truncation(_Receipt(finish_reason="length"))
    assert hit.truncated is True
    assert hit.source is TruncationSource.FIELD

    miss = outcomes.detect_truncation(_Receipt(finish_reason="stop"))
    assert miss.truncated is False
    assert miss.source is TruncationSource.FIELD


def test_a_producer_that_counts_its_own_truncated_calls_is_read_directly():
    """A declared attribute, not prose. This is the route the live theorist actually offers."""
    hit = outcomes.detect_truncation(_Receipt(), producer=_Producer(truncated_calls=2,
                                                                   last_finish_reason="length"))
    assert hit.truncated is True
    assert hit.source is TruncationSource.PRODUCER_ATTRIBUTE
    assert "2 call(s)" in hit.detail


def test_a_producer_reporting_zero_truncated_calls_is_an_answer_and_not_a_silence():
    """The distinction the whole field exists for. A counter that says zero has ANSWERED."""
    clear = outcomes.detect_truncation(_Receipt(), producer=_Producer(truncated_calls=0,
                                                                     last_finish_reason=""))
    assert clear.truncated is False
    assert clear.source is TruncationSource.PRODUCER_ATTRIBUTE


def test_the_machine_written_note_is_matched_anchored_and_never_searched_for():
    """The compiler emits `finish_reason: <value>` itself. Matched at the START of a whole note —
    a substring search across the concatenated blob would hit any sentence that mentioned it."""
    hit = outcomes.detect_truncation(_Receipt(notes=["compiler: x", "finish_reason: length"]))
    assert hit.truncated is True
    assert hit.source is TruncationSource.RECEIPT_NOTE

    clear = outcomes.detect_truncation(_Receipt(notes=["finish_reason: stop"]))
    assert clear.truncated is False


def test_a_note_that_merely_mentions_the_words_is_not_a_signal():
    """The refusal that matters. A prose sentence about truncation is not a declaration of it, and
    matching one would work today and break the first time somebody improved the wording — silently,
    in the direction of reporting every truncated reading as complete."""
    prose = _Receipt(notes=[
        "3 call(s) stopped on the output budget rather than finishing. What came back is a PREFIX",
        "the model reported its finish_reason as length in an earlier round"])
    assert outcomes.detect_truncation(prose).source is TruncationSource.UNKNOWN


def test_nothing_to_consult_is_unknown_and_unknown_is_not_none():
    """`none` says a route answered and reported no truncation. `unknown` says nothing could be
    asked. A product rendering them alike would show an unchecked stage as a verified one."""
    silent = outcomes.detect_truncation(_Receipt(), producer=_Producer())
    assert silent.truncated is None
    assert silent.source is TruncationSource.UNKNOWN
    assert silent.known is False

    answered = outcomes.detect_truncation(_Receipt(finish_reason="stop"))
    assert answered.truncated is False and answered.known is True
    assert answered.source is not silent.source


def test_a_producer_that_reported_no_value_does_not_become_a_clean_bill():
    assert outcomes.detect_truncation(
        _Receipt(notes=["finish_reason: not reported"])).truncated is None


# ── 2. adequacy is the producer's own verdict ────────────────────────────────

def test_no_declared_coverage_means_nothing_is_claimed():
    """`thin` is never inferred. 'Few claims for a long reading' is exactly the ambiguity 002R
    demonstrated, and a heuristic would be right often enough that nobody would check it on the run
    where it was wrong."""
    assert outcomes.declared_adequacy({"claims": [], "reading": {"blocks": [1] * 40}}).declared is False
    assert outcomes.declared_adequacy(None).complete is None


def test_a_declared_coverage_flag_is_read():
    incomplete = outcomes.declared_adequacy({"coverage": {"complete": False, "uncovered": 7}})
    assert incomplete.complete is False
    assert "7 source unit(s) uncovered" in incomplete.detail
    assert outcomes.declared_adequacy({"coverage": {"complete": True}}).complete is True


def test_a_coverage_ledger_is_read_entry_by_entry():
    """The shape Lane A's dissolution contract will produce: one disposition per source unit."""
    ledger = {"coverage": [
        {"source_unit_id": "su_1", "disposition": "represented_by"},
        {"source_unit_id": "su_2", "disposition": "duplicate_of"},
        {"source_unit_id": "su_3", "disposition": "semantic_remainder"},
    ]}
    read = outcomes.declared_adequacy(ledger)
    assert read.complete is False and read.uncovered == 1


# ── 3. the order the outcome is decided in ───────────────────────────────────

def test_truncation_outranks_emptiness():
    """A call cut off before it wrote anything is `truncated`, not `empty`. 'It found nothing' and
    'it never finished looking' send a reader to opposite places."""
    assert outcomes.outcome_for(
        produced=False, truncation=outcomes.Truncation(True, TruncationSource.FIELD),
        adequacy=outcomes.UNDECLARED) is StageAttemptOutcome.TRUNCATED


def test_an_unavailable_instrument_is_never_reported_as_truncated():
    """Availability first: something that never ran cannot have run out of budget."""
    assert outcomes.outcome_for(
        produced=False, truncation=outcomes.Truncation(True, TruncationSource.FIELD),
        adequacy=outcomes.UNDECLARED, unavailable=True) is StageAttemptOutcome.UNAVAILABLE


def test_a_parse_with_a_failed_coverage_check_is_thin_and_not_completed():
    """THE FLATTERING FAILURE. It produced claims, the JSON is valid, and its own check says it did
    not cover what it was given."""
    assert outcomes.outcome_for(
        produced=True, truncation=outcomes.UNKNOWN,
        adequacy=outcomes.Adequacy(complete=False)) is StageAttemptOutcome.THIN


def test_a_stage_that_produced_and_declared_nothing_wrong_is_completed():
    """The negative control. If `outcome_for` never returned `completed`, every test above would
    pass for the wrong reason."""
    assert outcomes.outcome_for(
        produced=True, truncation=outcomes.Truncation(False, TruncationSource.FIELD),
        adequacy=outcomes.Adequacy(complete=True)) is StageAttemptOutcome.COMPLETED


@pytest.mark.parametrize("flags,expected", [
    ({"errored": True}, StageAttemptOutcome.ERROR),
    ({"refused": True}, StageAttemptOutcome.REFUSED),
    ({"unavailable": True}, StageAttemptOutcome.UNAVAILABLE),
])
def test_the_four_ways_of_not_producing_stay_apart(flags, expected):
    assert outcomes.outcome_for(produced=False, truncation=outcomes.UNKNOWN,
                                adequacy=outcomes.UNDECLARED, **flags) is expected


# ── 4. the null-duration law ─────────────────────────────────────────────────

def _attempt(**over):
    base = {"attempt_id": "stg_1", "stage": StageName.THEORIST,
            "outcome": StageAttemptOutcome.COMPLETED}
    base.update(over)
    return StageAttempt(**base)


def test_a_duration_without_both_ends_is_refused():
    """Zero is a real measurement — a controlled clock that does not advance genuinely yields 0.0 —
    which is exactly why it may not double as 'unmeasured'."""
    with pytest.raises(ValueError, match="was not measured"):
        _attempt(duration_ms=12.0)
    with pytest.raises(ValueError, match="was not measured"):
        _attempt(started_at="2026-01-01T00:00:00+00:00", duration_ms=0.0)


def test_a_genuine_zero_duration_is_allowed():
    """The negative control for the law. A stage that begins and ends within one tick really did
    take 0ms, and a rule that refused it would push callers into writing null for a measurement
    they made."""
    ok = _attempt(started_at="2026-01-01T00:00:00+00:00",
                  completed_at="2026-01-01T00:00:00+00:00", duration_ms=0.0)
    assert ok.duration_ms == 0.0


def test_duration_between_two_unreadable_stamps_is_none_rather_than_zero():
    assert duration_ms_between(None, "2026-01-01T00:00:00+00:00") is None
    assert duration_ms_between("not a time", "2026-01-01T00:00:00+00:00") is None
    assert duration_ms_between("2026-01-01T00:00:00+00:00",
                               "2026-01-01T00:00:01+00:00") == 1000.0


def test_a_started_attempt_cannot_carry_a_completion():
    with pytest.raises(ValueError, match="crash signature"):
        _attempt(outcome=StageAttemptOutcome.STARTED,
                 completed_at="2026-01-01T00:00:00+00:00")


def test_a_progress_counter_cannot_exceed_its_own_total():
    with pytest.raises(ValueError, match="counting the wrong thing"):
        SubstageEvent(label="reading image", index=5, total=4)


# ── 5. counts are carried, never inferred ────────────────────────────────────

def test_the_counts_line_reports_only_what_the_stage_declared():
    """002R's complaint was a report saying 'nothing was compiled'. Replacing it with an invented
    '0 blocks in' would be the same failure with more digits."""
    both = _attempt(input_counts={"reading blocks": 31},
                    output_counts={"claims": 4, "observables": 0})
    # Sorted by name, so the line is stable across runs rather than ordered by whichever count the
    # stage happened to record first.
    assert both.counts_line() == "31 reading blocks in → 4 claims · 0 observables out"

    assert _attempt(output_counts={"claims": 2}).counts_line() == "2 claims out"
    assert _attempt().counts_line() == "", "an attempt that declared nothing must report nothing"


def test_a_negative_count_is_refused():
    with pytest.raises(ValueError):
        _attempt(output_counts={"claims": -1})


# ── 6. the worker census, with its control ───────────────────────────────────

PACKAGE = pathlib.Path(outcomes.__file__).parent

#: Modules that legitimately read a clock, each named with its reason. An exception list is only
#: honest when it is short and argued; a scan with a silent skip is a scan that proves nothing about
#: whatever was skipped.
_CLOCK_EXCEPTIONS = {
    # The document's own created/updated stamps. Not a stage time, and already excluded from every
    # replay comparison by name in `VOLATILE_FIELDS`.
    "store.py",
    # `utc_now` is the DEFAULT clock a caller overrides via `Stages.clock`; every test hands one in.
    "coordinator.py",
    # The session id is minted from the prompt AND the moment, deliberately: two people asking the
    # same question of the same images are two sessions. It is the one clock in this lane, it is
    # documented as such, and it is the only field a replay excludes.
    "ids.py",
}


def _code_names(path: pathlib.Path) -> set:
    """Every name, attribute and import this module actually USES.

    Parsed rather than grepped. A text scan matches the module's own docstring — this file's first
    version failed on `driver.py` for the sentence explaining why it does not use the Director's
    worker, which is the same defect it was written to catch one level up: a check whose evidence
    is the presence of a word rather than the content of the code.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
    return names


def test_no_module_in_this_package_touches_the_director_orchestration_worker():
    """THE RECONCILIATION, as a check rather than a claim.

    `runs.py` serialises the Director onto one worker because its runners nest `run_until_complete`
    and because two workers would race for one GPU. Neither reaches this chain — the theorist and
    compiler make blocking HTTPS calls, take no `loop=`, bind no semaphore and hold no device — so
    this package uses its own pool and must not reach for that one.
    """
    forbidden = {"_orchestration_pool", "_orchestration_loop", "ModelManager",
                 "backend.routers.posts", "backend.routers"}
    scanned = 0
    for path in sorted(PACKAGE.glob("*.py")):
        used = _code_names(path)
        scanned += 1
        overlap = used & forbidden
        assert not overlap, f"{path.name} reaches the Director's worker: {sorted(overlap)}"
    assert scanned >= 10, f"the scan saw only {scanned} module(s) — it is pointed somewhere wrong"


def test_that_worker_scan_can_actually_fail():
    """The negative control, run through the SAME parser. A control that used a different method
    would prove the control works rather than that the scan does."""
    runs = pathlib.Path(__file__).resolve().parents[1] / "routers" / "runs.py"
    used = _code_names(runs)
    assert "_orchestration_pool" in used and "_orchestration_loop" in used, (
        "runs.py must keep using the orchestration worker; if it stopped, the scan above would "
        "pass by testing nothing")


def test_the_inquiry_pool_is_its_own_and_is_bounded():
    from backend.services.inquiry_session import driver
    assert driver._POOL._thread_name_prefix == "inquiry-stage"
    assert driver._POOL._max_workers > 0, "an unbounded pool turns a slow provider into memory"

    from backend.routers import posts
    assert driver._POOL is not posts._orchestration_pool


#: Wall-clock reads. `time.perf_counter` is deliberately ABSENT: it is a monotonic elapsed
#: measurement, not a timestamp, and `capability.py` uses it for a receipt's `latency_ms` — which is
#: an honest measurement of how long a call took and is already excluded from replay by name. A rule
#: that banned it would be banning the measurement instead of the clock.
_WALL_CLOCK_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("time", "time"),
                     ("time", "gmtime"), ("time", "localtime")}


def _wall_clock_reads(path: pathlib.Path) -> set:
    """Calls in this module that ask the machine what time it is.

    Matched as `module.attribute` pairs through the parser rather than as text, so a docstring
    explaining that a module does not read a clock does not register as one reading a clock.
    """
    import ast

    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            pair = (node.value.id, node.attr)
            if pair in _WALL_CLOCK_CALLS:
                found.add(pair)
    return found


def test_no_module_in_this_package_reads_a_wall_clock_for_a_stage_time():
    """Every stage timestamp is handed in. One read from the wall would make a replay comparison
    exclude the field it exists to check — and would time the test machine's load instead of the
    stage."""
    scanned = 0
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name in _CLOCK_EXCEPTIONS:
            continue
        scanned += 1
        found = _wall_clock_reads(path)
        assert not found, f"{path.name} reads a wall clock: {sorted(found)}"
    assert scanned >= 7, f"the scan saw only {scanned} module(s) — it is pointed somewhere wrong"


def test_that_clock_scan_can_actually_fail():
    """The negative control, through the same parser. Each exception really does read one, which is
    why it is named with a reason rather than silently skipped."""
    for name in ("ids.py", "store.py", "coordinator.py"):
        assert _wall_clock_reads(PACKAGE / name), (
            f"{name} is listed as a clock exception and reads no clock; either the list is stale "
            f"or the scan above is passing by exempting the wrong files")


def test_an_elapsed_measurement_is_not_a_clock_read():
    """The other direction. `capability.py` times its own call with a monotonic counter, which is a
    measurement rather than a timestamp — banning it would ban the honest thing."""
    source = (PACKAGE / "capability.py").read_text(encoding="utf-8")
    assert "perf_counter" in source
    assert _wall_clock_reads(PACKAGE / "capability.py") == set()
