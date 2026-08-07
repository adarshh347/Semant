/**
 * SOCIETY — a MeetingView fixture, so the surface's honesty rules are testable with no backend.
 *
 * Contains one of each outcome on purpose: a COMPOSED pair with a proposed joint hypothesis, a
 * COEXISTENT pair, an INCOMMENSURABLE pair, and a wholly-received REFUSAL. A fixture missing any
 * of them would let the surface pass while unable to render the case it exists for.
 */
export const meetingFixture = {
    node_id: 'vm_pMeet:rim',
    convened: true,
    detail: '3 agents at vm_pMeet:rim: 1 composed, 1 coexistent, 1 incommensurable',
    members: [
        { id: 'agent_nestedness', organ_set: ['nestedness_organ'], measured: 2, arities: [2] },
        { id: 'agent_adjacency', organ_set: ['adjacency_organ'], measured: 3, arities: [2] },
        { id: 'agent_chroma', organ_set: ['chroma_organ'], measured: 1, arities: [1] },
    ],
    classes: [['agent_adjacency', 'agent_nestedness'], ['agent_chroma']],
    silent: [],
    outcomes: { composed: 1, coexistent: 1, incommensurable: 1 },
    verdicts: [
        { left: 'agent_nestedness', right: 'agent_adjacency', outcome: 'composed',
          detail: '1 claim(s) neither made alone, over 1 shared subject(s)',
          shared_subjects: ['whole'], hypotheses: ['ahyp_1'] },
        { left: 'agent_nestedness', right: 'agent_chroma', outcome: 'incommensurable',
          detail: 'a warmth mean and a nesting index are both small floats, and that is a fact about floating point rather than about the picture. There is no common scale.',
          shared_subjects: [], hypotheses: [] },
        { left: 'agent_adjacency', right: 'agent_chroma', outcome: 'coexistent',
          detail: 'can be about the same things and are not: 0 shared subject(s)',
          shared_subjects: [], hypotheses: [] },
    ],
    hypotheses: [{
        hypothesis_id: 'ahyp_1',
        claim: 'nested_at_boundary',
        agent_ids: ['agent_nestedness', 'agent_adjacency'],
        about_region_id: 'whole',
        ledger_status: 'proposed',
        marks_live: '0/2',
        detail_ledger: 'a joint hypothesis is a composition over two measurements, not a measurement.',
        rests_on: [
            { agent_id: 'agent_nestedness', organ: 'nestedness_organ', mark_id: 'vm_nest_1',
              relation: 'nested_within', basis: 'mask', detail: 'containment 0.99',
              live: false, epistemic: null },
            { agent_id: 'agent_adjacency', organ: 'adjacency_organ', mark_id: 'vm_adj_1',
              relation: 'meets', basis: 'mask', detail: 'contact 0.60',
              live: false, epistemic: null },
        ],
    }],
    held: {
        agent_nestedness: [{ agent_id: 'agent_nestedness', hypothesis_id: 'ahyp_1',
                             claim: 'nested_at_boundary', epistemic_status: 'interpretive',
                             contributed: 1, received: 1 }],
        agent_adjacency: [{ agent_id: 'agent_adjacency', hypothesis_id: 'ahyp_1',
                            claim: 'nested_at_boundary', epistemic_status: 'interpretive',
                            contributed: 1, received: 1 }],
        agent_chroma: [],
    },
    refusals_to_hold: [{
        agent_id: 'agent_chroma', hypothesis_id: 'ahyp_1', claim: 'nested_at_boundary',
        reason: 'wholly_received',
        detail: 'agent_chroma contributed no mark to this claim — it was in the room when it was made.',
    }],
    journeys: {},
};

export default meetingFixture;
