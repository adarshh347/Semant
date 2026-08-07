/**
 * COGNITION — a WalkView fixture, so the surface's honesty rules are testable with no backend.
 *
 * Deliberately contains all three of the things a viewing surface would be tempted to drop: a
 * refused crossing about the EDGE, one about the TRAVELLER, and a station where the agent looked
 * and measured nothing.
 */
export const walkFixture = {
    agent_id: 'agent_depth_seeker',
    temperament: 'depth_seeker',
    character: {
        name: 'depth_seeker',
        prefers: ['axis_occlusion', 'axis_nestedness', 'axis_adjacency'],
        detail: 'moves through a scene before moving between pictures',
    },
    organ_set: ['nestedness_organ'],
    first_signature: [['nestedness_organ', 'nested_within', 'within', 'whole', 'mask', 'measured']],
    stations: [
        {
            index: 0,
            node_id: 'vm_pA:part',
            post_id: 'pA',
            region_id: 'part',
            perceptions: [{
                organ: 'nestedness_organ', relation: 'nested_within', direction: 'within',
                other_region_id: 'whole', basis: 'mask', admissible: true,
                epistemic: 'measured', expression: 'part nested within whole',
                detail: 'mask containment 0.99', mark_id: 'vm_nest_1',
            }],
            horizon: {
                reachable: [],
                refused: [
                    { to_node: 'vm_pB:part', reason: 'interpretive_basis', about: 'edge',
                      gloss: 'it is grounded on an estimate, not a measurement',
                      axis_ref: 'axis_nestedness', relation: 'nested_within', basis: 'box',
                      detail: 'the mark is box-basis' },
                    { to_node: 'vm_pC:part', reason: 'box_footing', about: 'traveller',
                      gloss: "the agent's own footing is a box — an estimate cannot carry a crossing",
                      axis_ref: 'axis_nestedness', relation: null, basis: null,
                      detail: 'the agent stands on an estimate' },
                ],
                tally: { reachable: 0, refused_edge: 1, refused_traveller: 1 },
            },
            signature: [['nestedness_organ', 'nested_within', 'within', 'whole', 'mask', 'measured']],
            ended: { reason: 'no reachable crossing from here', available: [] },
        },
        {
            index: 1,
            node_id: 'vm_pA:whole',
            post_id: 'pA',
            region_id: 'whole',
            perceptions: [],
            horizon: { reachable: [], refused: [], tally: { reachable: 0, refused_edge: 0, refused_traveller: 0 } },
            signature: [],
        },
    ],
    steps: [{
        from_node: 'vm_pA:part', to_node: 'vm_pA:whole',
        crossed_image: false, kind: 'within one picture',
        axis_ref: 'axis_occlusion', relation: 'in_front_of', mark_id: 'vm_occ_1',
        basis: 'mask', epistemic: 'measured', ledger_status: 'proposed',
        systematicity: 0.0, ordering: 0.99, policy: 'clearest_ordering',
        rule: 'take the reachable occlusion edge whose ordering is cleanest',
        arrived_with: 0,
        arrival_detail: 'arrived with an empty field — everything it knew was knowledge from where it stood',
        detail: 'a depth step',
    }],
    proposals: [],
    tally: { stations: 2, steps: 1, within_one_picture: 1, between_pictures: 0,
             perceived: 1, refused: 2, proposed: 0 },
};

export const compareFixture = {
    walks: [walkFixture, { ...walkFixture, agent_id: 'agent_analogy_seeker',
                           temperament: 'analogy_seeker',
                           character: { name: 'analogy_seeker',
                                        prefers: ['axis_nestedness', 'axis_adjacency', 'axis_occlusion'],
                                        detail: 'moves between pictures before moving through one' },
                           steps: [{ ...walkFixture.steps[0], to_node: 'vm_pB:part',
                                     crossed_image: true, kind: 'between pictures' }] }],
    comparison: {
        measurements_identical: true,
        readings_each: { depth_seeker: 1, analogy_seeker: 1 },
        first_destinations: { depth_seeker: 'vm_pA:whole', analogy_seeker: 'vm_pB:part' },
        diverged: true,
        detail: 'temperament biases the route and never the reading: identical signatures, different destinations',
    },
};

export const temperamentsFixture = [walkFixture.character, compareFixture.walks[1].character];

export default walkFixture;
