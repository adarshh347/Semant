import copy
import gzip
import json
from pathlib import Path

import pytest

from research.rehearsals.mask_investigation.common import digest
from research.rehearsals.mask_investigation.evidence_feedback import propose_feedback
from research.rehearsals.mask_investigation.mask_hypothesis_test import CandidateHypothesis, QUESTION


FIXTURE = Path(__file__).resolve().parents[2] / 'research/rehearsals/mask_investigation/fixtures/measurement_report.json.gz'


def report():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))


def candidate(r, **kwargs):
    return CandidateHypothesis(
        question=QUESTION, source_interpretation='Colour may connect distinct regions.',
        proposed_proxy_rationale='Compare cross-interface and within-side change.',
        origin='caller_supplied_unverified', evidence_report_digest=digest(r), **kwargs,
    )


def uniform(r, excess, activity):
    for row in r['records']:
        for s in row['measurement'] or []:
            n = s['support_count']
            s.update(cross_deltaE76=[activity]*n,
                     within_deltaE76=[activity-excess]*n, excess_deltaE76=[excess]*n,
                     mean_excess_deltaE76=excess, mean_activity_deltaE76=activity,
                     status='nondiagnostic_low_activity' if activity < 1 else
                     ('mean_no_excess' if excess <= 1 else 'mean_excess'))
    return r


def test_saved_evidence_preserves_original_and_local_exceptions():
    r = report()
    before = copy.deepcopy(r)
    result = propose_feedback(candidate(r), r)
    assert r == before
    assert result['original_test']['status'] == 'numerical_prediction_contradicted'
    assert len(result['original_test']['counterexamples']) == 24
    assert len(result['original_test']['null_candidates']) == 34
    assert len(result['diagnostics']) == 20
    assert len(result['mean_pass_with_local_excess_candidate_scales']) == 16
    assert all(s['local_excess_above_one_count'] > 0
               for d in result['diagnostics'] for s in d['scales'])
    assert len(result['scale_discordant_candidates']) == 16
    assert result['planned_actions'] == [] and result['execute'] is False
    assert result['semantic_bridge_verified'] is False
    assert result['human_review'] == 'not_recorded'
    assert result['feedback_digest'] == digest({k:v for k,v in result.items() if k != 'feedback_digest'})


def test_clarification_precedes_evidence_access():
    r = report()
    class Unreadable:
        def __getitem__(self, key):
            raise AssertionError('must not access evidence')
    result = propose_feedback(candidate(r, object_referents=('flower',)), Unreadable())
    assert result['status'] == 'clarification_required'


def test_untrusted_display_summaries_cannot_hide_raw_exceptions():
    r = report()
    expected = propose_feedback(candidate(r), r)
    for row in r['records']:
        for s in row['measurement'] or []:
            s.update(max_excess_deltaE76=-100, p95_excess_deltaE76=-100,
                     fraction_excess_above_one=0, low_activity_fraction=0)
    result = propose_feedback(candidate(r), r)
    assert result['diagnostics'] == expected['diagnostics']


@pytest.mark.parametrize('activity', [0., .5])
def test_flat_abstains_not_scale_disagreement(activity):
    r = uniform(report(), 0., activity)
    result = propose_feedback(candidate(r), r)
    assert result['original_test']['status'] == 'insufficient_evaluable_evidence'
    assert len(result['nondiagnostic_candidates']) == 20
    assert not result['scale_discordant_candidates']
    assert not result['mean_pass_with_local_excess_candidate_scales']
    assert 'stop_or_review_insufficient_signal_not_support' in result['proposed_review_purposes']


def test_equal_pairs_do_not_invent_exceptions_or_semantics():
    r = uniform(report(), 0., 2.)
    result = propose_feedback(candidate(r), r)
    assert result['original_test']['status'] == 'numerical_prediction_met_on_evaluable_subset'
    assert not result['scale_discordant_candidates']
    assert not result['mean_pass_with_local_excess_candidate_scales']
    assert result['proposed_review_purposes'] == ['retain_unmeasured_candidates_and_conditional_scope']


def test_mixed_nondiagnostic_and_diagnostic_pair_is_not_discordance():
    r = uniform(report(), 0., 2.)
    s = next(row for row in r['records'] if row['measurement'])['measurement'][0]
    n = s['support_count']
    s.update(cross_deltaE76=[0.]*n, within_deltaE76=[0.]*n,
             mean_activity_deltaE76=0., status='nondiagnostic_low_activity')
    result = propose_feedback(candidate(r), r)
    assert len(result['nondiagnostic_candidates']) == 1
    assert not result['scale_discordant_candidates']
    assert result['original_test']['status'] == 'insufficient_evaluable_evidence'


def test_cli_replays_the_exact_fixture(tmp_path):
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTHONPATH': str(root) + os.pathsep + os.environ.get('PYTHONPATH', '')}
    run = subprocess.run([sys.executable, '-m',
                          'research.rehearsals.mask_investigation.evidence_feedback'],
                         cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    result = json.loads(run.stdout)
    r = report()
    c = candidate(r)
    c.proposed_proxy_rationale = 'Tentatively compare cross-interface and within-side change.'
    assert result == propose_feedback(c, r)


def test_local_exception_is_not_a_mean_claim_counterexample():
    r = uniform(report(), 0., 2.)
    s = next(row for row in r['records'] if row['measurement'])['measurement'][0]
    n = s['support_count']
    s['cross_deltaE76'][0] = 4.
    s['excess_deltaE76'][0] = 2.
    s['mean_excess_deltaE76'] = 2./n
    s['mean_activity_deltaE76'] = (2.*n+2.)/n
    result = propose_feedback(candidate(r), r)
    assert result['original_test']['status'] == 'numerical_prediction_met_on_evaluable_subset'
    assert not result['original_test']['counterexamples']
    assert len(result['mean_pass_with_local_excess_candidate_scales']) == 1
    assert result['diagnostics'][0]['scales'][0]['local_excess_above_one_support_indices'] == [0]


def test_input_and_output_are_detached():
    r = report()
    c = candidate(r)
    result = propose_feedback(c, r)
    r['records'][0]['source'] = 'changed'
    c.source_interpretation = 'changed'
    assert result['original_test']['proposal']['hypothesis']['source_interpretation'] != 'changed'
    assert all(d['candidate'][0] != 'changed' for d in result['diagnostics'])


@pytest.mark.parametrize('kind', ['stale', 'missing', 'duplicate', 'raw_inconsistent'])
def test_feedback_cannot_bypass_existing_validation(kind):
    r = report()
    c = candidate(r)
    if kind == 'stale':
        r['counts'] = {}
    if kind == 'missing':
        r['records'].pop()
    if kind == 'duplicate':
        r['records'].append(copy.deepcopy(r['records'][0]))
    if kind == 'raw_inconsistent':
        next(row for row in r['records'] if row['measurement'])['measurement'][0]['excess_deltaE76'][0] += 1
    if kind != 'stale':
        c = candidate(r)
    with pytest.raises(ValueError):
        propose_feedback(c, r)
