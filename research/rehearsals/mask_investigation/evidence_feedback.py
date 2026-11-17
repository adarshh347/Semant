"""Bounded review purposes from stored numerical evidence, not semantic inference.

This pure step reuses the fixed hypothesis validator. It recomputes local
diagnostics from validated raw arrays, not unvalidated display summaries.
It does not choose new coordinates, tune thresholds, run tools or approve work.
"""
from copy import deepcopy

import numpy as np

from .common import digest
from .mask_hypothesis_test import evaluate


def propose_feedback(candidate, report):
    """Preserve the original test and suggest inspectable, non-executing review.

    All numerical statements concern the selected, gate-eligible subset. The
    priority order is a fixed engineering convention, not a learned decision.
    """
    outcome = evaluate(candidate, report)
    if outcome['status'] == 'clarification_required':
        return deepcopy(outcome)  # No evidence access for unresolved referents.

    diagnostics = []
    discordant = []
    nondiagnostic = []
    for row in report['records']:
        if row['measurement'] is None:
            continue
        identity = [row['source'], row['prompt_index'], row['candidate_index']]
        scales = []
        for measurement in row['measurement']:
            excess = np.asarray(measurement['excess_deltaE76'], dtype=float)
            cross = np.asarray(measurement['cross_deltaE76'], dtype=float)
            within = np.asarray(measurement['within_deltaE76'], dtype=float)
            above = np.flatnonzero(excess > 1).tolist()
            low = np.flatnonzero(np.maximum(cross, within) < 1).tolist()
            scales.append({
                'pair_distance_native_cells': measurement['pair_distance_native_cells'],
                'status': measurement['status'],
                'mean_excess_deltaE76': float(excess.mean()),
                'support_count': len(excess),
                'local_excess_above_one_count': len(above),
                'local_excess_above_one_support_indices': above,
                'local_low_activity_count': len(low),
                'mean_pass_hides_local_excess': (
                    measurement['status'] == 'mean_no_excess' and bool(above)
                ),
            })
        statuses = [s['status'] for s in scales]
        if 'nondiagnostic_low_activity' in statuses:
            nondiagnostic.append(identity.copy())
        elif statuses[0] != statuses[1]:
            discordant.append(identity.copy())
        diagnostics.append({'candidate': identity, 'scales': scales})

    hidden = [
        [*item['candidate'], scale['pair_distance_native_cells']]
        for item in diagnostics for scale in item['scales']
        if scale['mean_pass_hides_local_excess']
    ]
    reasons = []
    if discordant:
        reasons.append('inspect_scale_dependence_without_selecting_a_winning_scale')
    if hidden:
        reasons.append('inspect_local_exceptions_before_any_whole_interface_claim')
    if nondiagnostic or not diagnostics:
        reasons.append('stop_or_review_insufficient_signal_not_support')
    if outcome['null_candidates']:
        reasons.append('retain_unmeasured_candidates_and_conditional_scope')
    if not reasons:
        reasons.append('review_proxy_relevance_before_interpretive_use')

    result = {
        'version': 'mask-evidence-feedback.v1',
        'status': 'review_proposal_only',
        'original_test': deepcopy(outcome),
        'measurement_report_digest': digest(report),
        'diagnostics': diagnostics,
        'scale_discordant_candidates': discordant,
        'mean_pass_with_local_excess_candidate_scales': hidden,
        'nondiagnostic_candidates': nondiagnostic,
        'proposed_review_purposes': reasons,
        'planned_actions': [],
        'execute': False,
        'human_review': 'not_recorded',
        'semantic_bridge_verified': False,
        'limits': [
            'This is retrospective numerical feedback, not hypothesis formation from prose.',
            'The original mean-based test is unchanged; local excess does not falsify a mean claim.',
            'Support indices index the bound gate interfaces, not recognized objects.',
            'No new scale, selection, measurement, model inference or parameter search is proposed.',
            'A review purpose is not human approval or permission to execute.',
            'Digests detect stale edits, not fabricated and rebound evidence or provenance.',
            'Returned data is mutable; editing it invalidates its checksum, not an authenticated signature.',
        ],
    }
    return {**result, 'feedback_digest': digest(result)}


if __name__ == '__main__':
    import gzip
    import json
    from pathlib import Path
    from .mask_hypothesis_test import CandidateHypothesis, QUESTION

    fixture = Path(__file__).with_name('fixtures') / 'measurement_report.json.gz'
    stored_report = json.loads(gzip.decompress(fixture.read_bytes()))
    supplied_candidate = CandidateHypothesis(
        question=QUESTION,
        source_interpretation='Colour may connect distinct regions.',
        proposed_proxy_rationale='Tentatively compare cross-interface and within-side change.',
        origin='caller_supplied_unverified',
        evidence_report_digest=digest(stored_report),
    )
    print(json.dumps(propose_feedback(supplied_candidate, stored_report), indent=2))
