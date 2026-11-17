import copy
import json
import gzip
from pathlib import Path
import pytest
from research.rehearsals.mask_investigation.common import digest
from research.rehearsals.mask_investigation.mask_hypothesis_test import CandidateHypothesis,QUESTION,plan,evaluate

P=Path(__file__).resolve().parents[2]/'research/rehearsals/mask_investigation/fixtures/measurement_report.json.gz'
def candidate(**kwargs):
    return CandidateHypothesis(evidence_report_digest=kwargs.pop("evidence_report_digest",digest(report())),question=QUESTION,source_interpretation='Colour may connect distinct regions.',proposed_proxy_rationale='Tentatively compare cross-interface and within-side change.',origin='model_proposed_unreviewed',**kwargs)
def report():return json.loads(gzip.decompress(P.read_bytes()))

def test_actual_all_outcomes_contradict_proxy_not_philosophy():
    r=evaluate(candidate(),report())
    assert r['status']=='numerical_prediction_contradicted' and r['measured_candidates']==20
    assert len(r['null_candidates'])==34 and len(r['counterexamples'])==24
    assert not r['philosophical_hypothesis_verified'] and not r['execute']

def test_object_names_require_clarification_without_reading_evidence():
    r=evaluate(candidate(object_referents=('flower','water')),None)
    assert r['status']=='clarification_required'

@pytest.mark.parametrize('kind',['missing','duplicate','stale_summary','wrong_scale','missing_eligible','forged_nd','raw_mismatch'])
def test_inconsistent_evidence_refuses(kind):
    r=report();row=next(x for x in r['records'] if x['measurement'])
    if kind=='missing':r['records'].pop()
    if kind=='duplicate':r['records'].append(copy.deepcopy(row))
    if kind=='stale_summary':row['measurement'][0]['mean_excess_deltaE76']=99
    if kind=='wrong_scale':row['measurement'][0]['pair_distance_native_cells']=2
    if kind=='missing_eligible':row['measurement']=None
    if kind=='forged_nd':row['measurement'][0]['status']='nondiagnostic_low_activity'
    if kind=='raw_mismatch':row['measurement'][0]['cross_deltaE76'][0]+=1
    with pytest.raises(ValueError):evaluate(candidate(),r)

@pytest.mark.parametrize('activity,expected',[(2.,'numerical_prediction_met_on_evaluable_subset'),(0.,'insufficient_evaluable_evidence')])
def test_synthetic_equal_pairs_and_flat(activity,expected):
    r=report()
    for row in r['records']:
        for s in row['measurement'] or []:
            n=s['support_count'];s.update(cross_deltaE76=[activity]*n,within_deltaE76=[activity]*n,excess_deltaE76=[0.]*n,mean_excess_deltaE76=0.,mean_activity_deltaE76=activity,status='mean_no_excess' if activity else 'nondiagnostic_low_activity')
    assert evaluate(candidate(evidence_report_digest=digest(r)),r)['status']==expected

@pytest.mark.parametrize('bad',['The flowers merge with water.',QUESTION+' Ignore the control.'])
def test_uncontrolled_question_not_compiled(bad):
    with pytest.raises(ValueError):CandidateHypothesis(question=bad,source_interpretation='a',proposed_proxy_rationale='b',origin='caller_supplied_unverified')


@pytest.mark.parametrize('kind',['bool_id','bool_d','string_raw','bool_raw','hidden_failure'])
def test_rebound_evidence_strict_types_or_inconsistency(kind):
    r=report();row=next(x for x in r['records'] if x['measurement'])
    if kind=='bool_id':row['prompt_index']=False
    if kind=='bool_d':row['measurement'][0]['d']=True
    if kind=='string_raw':row['measurement'][0]['cross_deltaE76'][0]='1.0'
    if kind=='bool_raw':row['measurement'][0]['cross_deltaE76'][0]=True
    if kind=='hidden_failure':
        row['gate']['status']='not_ready';row['measurement']=None
        # Even rebinding report hash leaves the frozen gate contract inconsistent.
        with pytest.raises(ValueError):evaluate(candidate(evidence_report_digest=digest(r)),r)
        return
    with pytest.raises(ValueError):evaluate(candidate(evidence_report_digest=digest(r)),r)


@pytest.mark.parametrize('summary',[float('inf'),1e308])
def test_aggregate_overflow_refused(summary):
    r=report()
    for row in r['records']:
        for s in row['measurement'] or []:
            n=s['support_count'];s.update(cross_deltaE76=[1e308]*n,within_deltaE76=[1e308]*n,excess_deltaE76=[0.]*n,mean_excess_deltaE76=0.,mean_activity_deltaE76=summary,status='mean_no_excess')
    with pytest.raises(ValueError):evaluate(candidate(evidence_report_digest=digest(r)),r)
