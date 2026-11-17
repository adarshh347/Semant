"""Constrained, retrospective numerical hypothesis test, not language grounding."""
from typing import Literal
from pydantic import ConfigDict, Field
from .common import Strict
from .common import digest
from .mask_interface_measurement import CONTRACT
import numpy as np

QUESTION='Do all mask proposals eligible under the geometry and global-signal gates have mean colour excess at most 1 Delta E76 at both native pair distances 1 and 7?'

class CandidateHypothesis(Strict):
    model_config=ConfigDict(strict=True,extra='forbid')
    question: Literal[QUESTION]
    source_interpretation: str=Field(min_length=1,max_length=4096)
    proposed_proxy_rationale: str=Field(min_length=1,max_length=2048)
    object_referents: tuple[str,...]=()
    evidence_report_digest: str=Field(pattern=r'^[0-9a-f]{64}$')
    origin: Literal['caller_supplied_unverified','model_proposed_unreviewed']
    human_review: Literal['not_recorded']='not_recorded'


def plan(candidate):
    c=CandidateHypothesis.model_validate(candidate.model_dump())
    if c.object_referents:
        return {'status':'clarification_required','reason':'mask_object_correspondence_unverified',
                'unresolved_referents':list(c.object_referents),'execute':False,'semantic_bridge_verified':False}
    return {'status':'offline_research_proposal','hypothesis':c.model_dump(mode='json'),
            'purpose':'Test the declared numerical correlate on every eligible candidate at both fixed scales.',
            'measurement_contract':CONTRACT,'scope':'all candidates eligible under geometry and global-signal gates, not all image contours',
            'expected_numerical_outcome':'every eligible candidate mean excess <=1 at both scales',
            'execute':False,'human_review':'not_recorded','semantic_bridge_verified':False,
            'evidence_timing':'retrospective operationalization of previously inspected experiment'}


def evaluate(candidate, report):
    proposed=plan(candidate)
    if proposed['status']!='offline_research_proposal':return proposed
    if digest(report)!=candidate.evidence_report_digest:raise ValueError('bound_report_digest_mismatch')
    if digest(report['contract'])!=report['contract_digest']:raise ValueError('contract_digest_mismatch')
    if report['contract']['metric']!=CONTRACT:raise ValueError('measurement_contract_mismatch')
    expected={(n,p,c) for n in ('monet','flat') for p in range(9) for c in range(3)}
    bindings=report['contract']['candidate_gates']
    if len(bindings)!=54:raise ValueError('gate_bindings_required')
    bound={tuple(b['identity']):b for b in bindings}
    if len(bound)!=54:raise ValueError('duplicate_gate_bindings')
    seen=set();counterexamples=[];nondiagnostic=[];nulls=[];measured=0
    for row in report['records']:
        if type(row['prompt_index']) is not int or type(row['candidate_index']) is not int:raise ValueError('strict_candidate_identity_required')
        identity=(row['source'],row['prompt_index'],row['candidate_index'])
        if identity in seen:raise ValueError('duplicate_candidate')
        if identity not in bound or digest(row['gate'])!=bound[identity]['gate_digest'] or row['gate']['status']!=bound[identity]['status']:raise ValueError('frozen_gate_mismatch')
        seen.add(identity);values=row['measurement']
        if values is None:
            if row['gate']['status']=='sampling_candidate':raise ValueError('eligible_measurement_missing')
            nulls.append(list(identity));continue
        if row['gate']['status']!='sampling_candidate' or len(values)!=2 or [s['d'] for s in values]!=[1,4]:raise ValueError('candidate_scope_mismatch')
        measured+=1
        for s in values:
            if any(type(s[k]) is not int for k in ('d','pair_distance_native_cells','support_count')):raise ValueError('strict_integer_summary_required')
            for key in ('excess_deltaE76','cross_deltaE76','within_deltaE76'):
                if type(s[key]) is not list or any(type(x) not in (int,float) for x in s[key]):raise ValueError('strict_numeric_arrays_required')
            if any(type(s[k]) not in (int,float) or not np.isfinite(s[k]) for k in ('mean_excess_deltaE76','mean_activity_deltaE76')):raise ValueError('strict_numeric_summary_required')
            ex=np.asarray(s['excess_deltaE76'],dtype=float)
            if ex.ndim!=1 or len(ex)<16 or not np.isfinite(ex).all() or s['support_count']!=len(ex):raise ValueError('invalid_measurement_support')
            cross=np.asarray(s['cross_deltaE76'],dtype=float);within=np.asarray(s['within_deltaE76'],dtype=float)
            if cross.shape!=ex.shape or within.shape!=ex.shape or not np.isfinite(cross).all() or not np.isfinite(within).all() or np.any(cross<0) or np.any(within<0) or not np.array_equal(ex,cross-within):raise ValueError('raw_measurements_inconsistent')
            if len(ex)!=len(row['gate']['supported_interfaces_axis_y_x']):raise ValueError('gate_support_mismatch')
            with np.errstate(over='ignore',invalid='ignore'):
                activity=float(np.maximum(cross,within).mean())
            if not np.isfinite(activity):raise ValueError('nonfinite_aggregate')
            if activity!=s['mean_activity_deltaE76'] or (s['status']=='nondiagnostic_low_activity')!=(activity<1):raise ValueError('activity_status_mismatch')
            with np.errstate(over='ignore',invalid='ignore'):
                mean=float(ex.mean())
            if not np.isfinite(mean):raise ValueError('nonfinite_aggregate')
            if mean!=s['mean_excess_deltaE76'] or s['pair_distance_native_cells']!=2*s['d']-1:raise ValueError('measurement_summary_mismatch')
            status=s['status']
            if status=='nondiagnostic_low_activity':nondiagnostic.append([*identity,s['d']])
            elif status not in ('mean_no_excess','mean_excess') or status!=('mean_no_excess' if mean<=1 else 'mean_excess'):raise ValueError('status_mismatch')
            elif mean>1:counterexamples.append({'candidate':list(identity),'pair_distance':2*s['d']-1,'mean_excess':mean})
    if seen!=expected:raise ValueError('complete_candidate_set_required')
    status='numerical_prediction_contradicted' if counterexamples else ('insufficient_evaluable_evidence' if not measured or nondiagnostic else 'numerical_prediction_met_on_evaluable_subset')
    result={'proposal':proposed,'status':status,'measured_candidates':measured,'null_candidates':nulls,
            'counterexamples':counterexamples,'nondiagnostic_measurements':nondiagnostic,
            'measurement_report_digest':digest(report),'semantic_bridge_verified':False,
            'philosophical_hypothesis_verified':False,'human_review':'not_recorded','execute':False,
            'limits':['Numerical proxy choice is supplied, not inferred or semantically verified.',
                      'Null candidates are not supporting evidence; conclusions concern eligible subset only.',
                      'Contradiction concerns this correlate, not the source philosophical interpretation.',
                      'Model proposal origin grants no authority; this is not authenticated human review.',
                      'Caller-bound report digest prevents stale edits, not forged/rebound evidence; authenticity is external.']}
    return {**result,'receipt_digest':digest(result)}
