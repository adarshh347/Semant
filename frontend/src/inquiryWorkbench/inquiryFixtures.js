/**
 * INQUIRY WORKBENCH — backend-SHAPED fixtures.
 *
 * Every object here is written as the API is expected to send it: raw JSON-ish bodies, before
 * `normalizeSession` touches them. That is deliberate. A fixture written in the NORMALISED shape
 * would test the components against the contract's output while quietly skipping the contract
 * itself, and the drift `runContract.js` documents (`steps: ['rhythm']` versus the object a live
 * server sends) is exactly what that hides.
 *
 * FIXTURES ARE FOR TESTS AND DEVELOPMENT STORIES ONLY. The page never falls back to them when the
 * API is missing — it says the API is unavailable. A surface that substitutes a fixture for an
 * absent backend converts an outage into a convincing demo, which is the same lie in a different
 * layer as calling a simulated receipt evidence.
 *
 * ## Two domains, one set of types
 *
 * `consultFixture` is an architecture case and `otherDomainFixture` is a weld micrograph. They
 * traverse identical types with no branch anywhere, which is the board's generality gate asserted
 * in the only place this lane can assert it. If a topic name ever leaks into a component, the
 * micrograph fixture is what fails.
 */

const IMAGES = [
    {
        post_id: 'post_altes_front',
        title: 'Altes Museum, Lustgarten front',
        image_ref: 'imgref_altes_front',
        image_url: '/fixtures/altes-front.jpg',
    },
    {
        post_id: 'post_altes_rotunda',
        title: 'Rotunda, interior',
        image_ref: 'imgref_altes_rotunda',
        image_url: '/fixtures/altes-rotunda.jpg',
    },
];

export const FIXTURE_PROMPT =
    'How does this building turn a dispersed civic ground into a centralized interior, '
    + 'and what does the threshold between them actually do?';

export const FIXTURE_CORPUS = IMAGES;

const READING = {
    text:
        'The front reads as a single long horizontal: a screen of columns held between two solid '
        + 'ends, with no centre marked on the outside. Behind it the plan turns: the rotunda is a '
        + 'centre that the façade never announces. The stair between them is doing the work of '
        + 'converting a lateral, dispersed approach into a vertical, gathered one — you arrive '
        + 'along the building and leave the stair facing its middle. The comparison that suggests '
        + 'itself is with a temple front, but the temple front has a centre and this one refuses '
        + 'to name it.',
    status: 'interpretive',
    source: 'scene_theorist',
    model: 'vlm/scene-theorist',
    blocks: [
        {
            block_id: 'rdb_1', kind: 'observation',
            text: 'The front reads as a single long horizontal: a screen of columns held between '
                + 'two solid ends, with no centre marked on the outside.',
            image_refs: ['post_altes_front'],
        },
        {
            block_id: 'rdb_2', kind: 'observation',
            text: 'Behind it the plan turns: the rotunda is a centre that the façade never announces.',
            image_refs: ['post_altes_front', 'post_altes_rotunda'],
        },
        {
            block_id: 'rdb_3', kind: 'association',
            text: 'The comparison that suggests itself is with a temple front, but the temple '
                + 'front has a centre and this one refuses to name it.',
            image_refs: ['post_altes_front'],
        },
    ],
    provenance: { role: 'scene_theorist', called_at: '2026-08-09T09:14:02Z' },
};

const POSTS = [
    {
        post_id: 'post_altes_front', title: 'Altes Museum, Lustgarten front',
        image_ref: 'imgref_altes_front',
        fingerprint: 'a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90',
        readable: true, note: '',
    },
    {
        post_id: 'post_altes_rotunda', title: 'Rotunda, interior',
        image_ref: 'imgref_altes_rotunda',
        fingerprint: 'b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1',
        readable: true, note: '',
    },
];

const FRAME = {
    frame_id: 'frm_1',
    attentions: ['centre', 'threshold', 'approach'],
    epistemic_demands: ['a comparison across two images', 'movement, which no still image holds'],
    unresolved_terms: ['dispersed civic ground'],
    proposed_actions: [],
};

const VERDICTS = [
    {
        verdict_id: 'vd_colonnade', claim_ref: 'clm_colonnade', outcome: 'interpretive_only',
        why: 'The one request that bore on it ran against a simulation, so nothing measured '
            + 'reaches this claim.',
        evidence_refs: [], receipt_refs: ['capr_locate_1'],
    },
    {
        verdict_id: 'vd_temple', claim_ref: 'clm_temple_front', outcome: 'not_investigated',
        why: 'No observable was requested for it. Nobody asked.',
        evidence_refs: [], receipt_refs: [],
    },
];

const CLAIMS = [
    {
        claim_id: 'clm_colonnade',
        text: 'A colonnade spans the full width of the front without marking a centre.',
        claim_kind: 'entity',
        status: 'proposed',
        subject: 'colonnade',
        predicate: 'spans',
        object: 'front elevation',
        source_span: { origin: 'reading', text: 'a screen of columns held between two solid ends', start: 46, end: 92 },
        image_scope: ['post_altes_front'],
        epistemic_demand: 'Someone must be able to point at the extent in the picture.',
        confidence: 0.71,
        author: 'model',
    },
    {
        claim_id: 'clm_centre_shift',
        text: 'The interior centre is not announced by the exterior.',
        claim_kind: 'spatial_relation',
        status: 'interpretive',
        subject: 'rotunda centre',
        predicate: 'is_not_announced_by',
        object: 'front elevation',
        source_span: { origin: 'reading', text: 'the rotunda is a centre that the façade never announces', start: 150, end: 204 },
        image_scope: ['post_altes_front', 'post_altes_rotunda'],
        epistemic_demand: 'Needs a comparison of two images, not one measurement.',
        confidence: 0.58,
        author: 'model',
    },
    {
        claim_id: 'clm_threshold_converts',
        text: 'The stair converts lateral approach into axial arrival.',
        claim_kind: 'causal_hypothesis',
        status: 'proposed',
        subject: 'stair',
        predicate: 'converts',
        object: 'approach direction',
        source_span: { origin: 'prompt', text: 'what does the threshold between them actually do', start: 62, end: 110 },
        image_scope: ['post_altes_front'],
        epistemic_demand: 'Movement, which no still image measures on its own.',
        confidence: null,
        author: 'model',
    },
    {
        claim_id: 'clm_temple_front',
        text: 'The front quotes a temple portico while withholding its centre.',
        claim_kind: 'historical_or_sourced',
        status: 'unresolved',
        subject: 'front elevation',
        predicate: 'quotes',
        object: 'temple portico',
        source_span: { origin: 'reading', text: 'The comparison that suggests itself is with a temple front', start: 300, end: 358 },
        image_scope: ['post_altes_front'],
        epistemic_demand: 'A source outside the image. Nothing in the pixels settles it.',
        confidence: null,
        author: 'model',
    },
];

const CLAIM_EDGES = [
    {
        edge_id: 'edg_1',
        from_claim: 'clm_colonnade',
        to_claim: 'clm_centre_shift',
        relation: 'supports',
        note: 'An unmarked centre outside is the premise of the shift.',
    },
    {
        edge_id: 'edg_2',
        from_claim: 'clm_centre_shift',
        to_claim: 'clm_threshold_converts',
        relation: 'motivates',
        note: '',
    },
    {
        edge_id: 'edg_3',
        from_claim: 'clm_temple_front',
        to_claim: 'clm_colonnade',
        relation: 'complicates',
        note: 'A portico reading would put a centre back on the front.',
    },
];

const OBSERVABLES = [
    {
        observable_id: 'obs_extent',
        claim_ref: 'clm_colonnade',
        observable_kind: 'dominant_extent',
        target: 'the run of columns across the front',
        image_scope: ['post_altes_front'],
        ground_forms: ['region', 'mask'],
        capability_classes: ['locate_phrase'],
        alternatives: [
            {
                alternative_id: 'alt_whole_colonnade',
                label: 'Locate the colonnade as one extent',
                capability_class: 'locate_phrase',
                consequence: 'One region for the whole screen. Answers "how wide", not "how many".',
                available: true,
            },
            {
                alternative_id: 'alt_per_column',
                label: 'Locate each column separately',
                capability_class: 'locate_phrase',
                consequence: 'Column-by-column extents, so rhythm and spacing become countable — '
                    + 'and a miscount becomes possible in a way the single extent avoids.',
                available: true,
            },
        ],
        success_condition: 'A region a person can look at and agree covers the columns.',
        ambiguity_condition: 'A region that also takes in the wall behind.',
        refusal_condition: 'No phrase-locating capability available.',
        residual_interpretation:
            'That the extent IS a colonnade, and that an unmarked centre means anything, stays '
            + 'interpretive however exact the region is.',
        availability: 'available',
        gap_reason: '',
    },
    {
        observable_id: 'obs_centre_compare',
        claim_ref: 'clm_centre_shift',
        observable_kind: 'cross_image_comparison',
        target: 'centre of mass of the front against centre of the rotunda',
        image_scope: ['post_altes_front', 'post_altes_rotunda'],
        ground_forms: ['point', 'region'],
        capability_classes: ['locate_phrase', 'geometry.centrality'],
        alternatives: [
            {
                alternative_id: 'alt_centrality',
                label: 'Compute centrality on both images',
                capability_class: 'geometry.centrality',
                consequence: 'Would give two comparable centres.',
                available: false,
            },
        ],
        success_condition: 'Two located centres that can be compared.',
        ambiguity_condition: '',
        refusal_condition: 'No geometry family is registered.',
        residual_interpretation: 'Whether a geometric centre is an ARCHITECTURAL centre.',
        availability: 'capability_gap',
        gap_reason:
            'No geometry capability family exists yet. Centrality is named in the plan for a '
            + 'later phase and is not implemented.',
    },
    {
        observable_id: 'obs_movement',
        claim_ref: 'clm_threshold_converts',
        observable_kind: 'movement_trace',
        target: 'the path from the colonnade to the rotunda',
        image_scope: ['post_altes_front'],
        ground_forms: ['trajectory'],
        capability_classes: ['situated.exploration'],
        alternatives: [],
        success_condition: 'A traversal that records direction changes.',
        ambiguity_condition: '',
        refusal_condition: 'Situated missions are not dispatched in this phase.',
        residual_interpretation: 'What the conversion MEANS to a person walking it.',
        availability: 'unavailable',
        gap_reason: 'Situated exploration exists but is deliberately not dispatched in Phase 1.',
    },
];

const REMAINDER = [
    {
        remainder_id: 'rem_temple',
        text: 'Whether the front quotes a temple portico.',
        why_unresolved: 'A claim about sources. No measurement of these pixels can settle it.',
        claim_refs: ['clm_temple_front'],
    },
    {
        remainder_id: 'rem_movement',
        text: 'What the stair does to a body moving through it.',
        why_unresolved: 'Needs movement. Two still images do not contain it.',
        claim_refs: ['clm_threshold_converts'],
    },
];

const TRACE = [
    {
        event_id: 'evt_1', at: '2026-08-09T09:14:00Z', actor: 'inquiry_framer', actor_kind: 'system',
        transition: 'framing → reading', reason: 'Prompt and corpus metadata read; no pixels seen.',
        refs: [], revision: 1,
    },
    {
        event_id: 'evt_2', at: '2026-08-09T09:14:06Z', actor: 'scene_theorist', actor_kind: 'model',
        transition: 'reading → compiling', reason: 'Provisional reading returned. Interpretive.',
        refs: [], revision: 2,
    },
    {
        event_id: 'evt_3', at: '2026-08-09T09:14:11Z', actor: 'semantic_compiler', actor_kind: 'model',
        transition: 'compiling → awaiting_user',
        reason: 'Four claims, three observables. One fork is material.',
        refs: ['clm_colonnade', 'obs_extent'], revision: 3,
    },
];

const DECISION_REQUEST = {
    decision_id: 'dec_extent_grain',
    session_id: 'inqs_fixture_1',
    kind: 'choose_operationalization',
    question: 'Locate the colonnade as one extent, or column by column?',
    why_now:
        'The two answer different questions and cost differently. One extent answers how wide the '
        + 'screen is; column-by-column makes rhythm countable and makes a miscount possible.',
    affected_refs: ['clm_colonnade', 'obs_extent'],
    options: [
        {
            option_id: 'opt_whole',
            label: 'One extent for the whole colonnade',
            consequence: 'Rhythm claims stay uninvestigated and move to the remainder.',
            recommended: true,
        },
        {
            option_id: 'opt_per_column',
            label: 'Column by column',
            consequence: 'Rhythm becomes investigable. More requests, and a miscount is possible.',
            recommended: false,
        },
    ],
    allow_free_text: true,
    blocking: true,
    answered: false,
    provenance: { steward: 'deliberation_steward', mode: 'consult' },
};

/** Deep-ish clone so a test mutating one fixture cannot reach into another. */
const clone = (v) => JSON.parse(JSON.stringify(v));

function baseSession(overrides = {}) {
    return {
        schema_version: 'inquiry-session.v1',
        session_id: 'inqs_fixture_1',
        inquiry_id: 'inq_fixture_1',
        revision: 3,
        state: 'compiling',
        mode: 'consult',
        graph: {
            schema_version: 'semantic-inquiry-graph.v1',
            graph_id: 'sig_fixture_1',
            inquiry_id: 'inq_fixture_1',
            prompt: FIXTURE_PROMPT,
            image_refs: clone(IMAGES),
            reading: clone(READING),
            claims: clone(CLAIMS),
            claim_edges: clone(CLAIM_EDGES),
            observables: clone(OBSERVABLES),
            semantic_remainder: clone(REMAINDER),
            refusals: [],
            provenance: { compiler: 'semantic_compiler' },
        },
        posts: clone(POSTS),
        frame: clone(FRAME),
        decision_requests: [],
        decision_records: [],
        capability_receipts: [],
        evidence: [],
        verdicts: [],
        synthesis: null,
        stages: [],
        trace: clone(TRACE),
        gaps: [],
        stop_reason: '',
        provenance: { producer: 'inquiry_session', schema_version: 'inquiry-session.v1' },
        error: '',
        ...overrides,
    };
}

/** Mid-flight: the compiler has run, nothing is blocked yet. */
export function compilingFixture() {
    return baseSession();
}

/** 1. A consult session paused at an operationalization fork. */
export function consultFixture() {
    return baseSession({
        state: 'awaiting_user',
        revision: 3,
        decision_requests: [clone(DECISION_REQUEST)],
    });
}

const USER_RECORD = {
    record_id: 'rec_1',
    decision_id: 'dec_extent_grain',
    decider: 'user',
    action: 'select',
    question: 'Locate the colonnade as one extent, or column by column?',
    selected_option_id: 'opt_whole',
    selected_label: 'One extent for the whole colonnade',
    free_text: '',
    rationale: 'Chosen by you.',
    affected_refs: ['clm_colonnade', 'obs_extent'],
    at: '2026-08-09T09:16:40Z',
    revision: 4,
};

const FIXTURE_RECEIPT = {
    receipt_id: 'capr_locate_1',
    request_ref: 'obs_extent',
    capability: 'locate_phrase',
    execution_mode: 'fixture',
    status: 'simulated',
    usable_as_evidence: false,
    attempted: true,
    payload: {
        regions: [{ kind: 'box', x: 0.06, y: 0.44, w: 0.88, h: 0.21 }],
        phrase: 'colonnade',
        note: 'Geometry produced by the simulation adapter. Nothing was measured from the image.',
    },
    detail: 'Simulation adapter — flow verification only.',
    latency_ms: 12,
    provenance: { adapter: 'simulation', capability_class: 'locate_phrase' },
};

/** 2. The same session after the person chose, with one fixture receipt. */
export function respondedFixture() {
    return baseSession({
        state: 'judging',
        revision: 5,
        decision_requests: [clone({ ...DECISION_REQUEST, answered: true })],
        decision_records: [clone(USER_RECORD)],
        capability_receipts: [clone(FIXTURE_RECEIPT)],
        trace: [
            ...clone(TRACE),
            {
                event_id: 'evt_4', at: '2026-08-09T09:16:40Z', actor: 'you', actor_kind: 'user',
                transition: 'awaiting_user → ready',
                reason: 'Chose one extent for the whole colonnade.',
                refs: ['dec_extent_grain', 'obs_extent'], revision: 4,
            },
            {
                event_id: 'evt_5', at: '2026-08-09T09:16:41Z', actor: 'capability_broker',
                actor_kind: 'system', transition: 'ready → executing',
                reason: 'One request to locate_phrase, through the simulation adapter.',
                refs: ['obs_extent', 'capr_locate_1'], revision: 5,
            },
        ],
    });
}

const SYNTHESIS = {
    synthesis_id: 'syn_1',
    note: 'Written from the claim graph, not from the reading paragraph.',
    sections: [
        {
            section_id: 'sec_front',
            heading: 'The front',
            text: 'The front is a single horizontal screen of columns with no centre marked on it. '
                + 'That is a reading of the picture, not a measurement of it: the request that '
                + 'would have located the extent ran against a simulation, so nothing here rests '
                + 'on a measured region.',
            claim_refs: ['clm_colonnade'],
            evidence_refs: [],
            refusal_refs: [],
            status: 'interpretive',
            user_authored: false,
        },
        {
            section_id: 'sec_shift',
            heading: 'The turn inward',
            text: 'The interior centre is not announced outside. Comparing the two centres would '
                + 'have needed a geometry capability that does not exist, so this stays a reading '
                + 'of two pictures placed side by side.',
            claim_refs: ['clm_centre_shift'],
            evidence_refs: [],
            refusal_refs: [],
            status: 'interpretive',
            user_authored: false,
        },
        {
            section_id: 'sec_grain',
            heading: 'On the grain you chose',
            text: 'You asked for one extent rather than column-by-column, so nothing here counts '
                + 'columns or speaks about rhythm.',
            claim_refs: ['clm_colonnade'],
            evidence_refs: [],
            refusal_refs: [],
            status: 'unresolved',
            user_authored: true,
        },
    ],
};

/** 3. Completed, with a cited answer and a semantic remainder. */
export function completedFixture() {
    const s = respondedFixture();
    return {
        ...s,
        state: 'complete',
        revision: 7,
        verdicts: clone(VERDICTS),
        synthesis: clone(SYNTHESIS),
        trace: [
            ...s.trace,
            {
                event_id: 'evt_6', at: '2026-08-09T09:16:44Z', actor: 'evidence_judge',
                actor_kind: 'system', transition: 'judging → composing',
                reason: 'The one receipt is a fixture. No evidence object was created from it.',
                refs: ['capr_locate_1'], revision: 6,
            },
            {
                event_id: 'evt_7', at: '2026-08-09T09:16:46Z', actor: 'synthesis_composer',
                actor_kind: 'model', transition: 'composing → complete',
                reason: 'Three sections, two remainder entries.',
                refs: ['syn_1'], revision: 7,
            },
        ],
    };
}

/** 4. An auto session: the system chose, and says so. */
export function autoFixture() {
    return baseSession({
        state: 'executing',
        mode: 'auto',
        revision: 5,
        decision_records: [
            {
                record_id: 'rec_auto_1',
                decision_id: 'dec_extent_grain',
                decider: 'system',
                action: 'select',
                question: 'Locate the colonnade as one extent, or column by column?',
                selected_option_id: 'opt_whole',
                selected_label: 'One extent for the whole colonnade',
                free_text: '',
                rationale: 'Reversible, non-authorial, and the recommended default. Auto mode took '
                    + 'it without asking and recorded the choice here.',
                affected_refs: ['clm_colonnade', 'obs_extent'],
                at: '2026-08-09T09:14:12Z',
                revision: 4,
            },
        ],
        capability_receipts: [clone(FIXTURE_RECEIPT)],
    });
}

/**
 * 5. The five ways a capability can come back with nothing useful, on one session.
 *
 * They are together on purpose: the guarantee is that they are DISTINCT, and a fixture that
 * showed them one at a time could not fail if two of them collapsed into the same rendering.
 */
export function outcomesFixture() {
    return baseSession({
        state: 'judging',
        revision: 6,
        capability_receipts: [
            clone(FIXTURE_RECEIPT),
            {
                receipt_id: 'capr_empty',
                request_ref: 'obs_extent',
                capability: 'locate_phrase',
                execution_mode: 'live',
                status: 'empty',
                usable_as_evidence: false,
                attempted: true,
                payload: {},
                detail: 'The instrument ran on the phrase and returned no instances.',
                latency_ms: 830,
                provenance: { adapter: 'director' },
            },
            {
                receipt_id: 'capr_unavailable',
                request_ref: 'obs_centre_compare',
                capability: 'geometry.centrality',
                execution_mode: 'live',
                status: 'unavailable',
                usable_as_evidence: false,
                attempted: false,
                payload: {},
                detail: 'No geometry family is registered, so nothing was attempted.',
                latency_ms: null,
                provenance: {},
            },
            {
                receipt_id: 'capr_refused',
                request_ref: 'obs_movement',
                capability: 'situated.exploration',
                execution_mode: 'live',
                status: 'refused',
                usable_as_evidence: false,
                attempted: false,
                payload: {},
                detail: 'Situated missions are not dispatched in this phase.',
                latency_ms: null,
                provenance: { refused_by: 'capability_broker' },
            },
            {
                receipt_id: 'capr_gap',
                request_ref: 'obs_centre_compare',
                capability: 'geometry.centrality',
                execution_mode: 'live',
                status: 'capability_gap',
                usable_as_evidence: false,
                attempted: false,
                payload: {},
                detail: 'Nothing in Semant can currently compare two centres across images.',
                latency_ms: null,
                provenance: {},
            },
        ],
        graph: {
            ...baseSession().graph,
            refusals: [
                {
                    refusal_id: 'ref_1',
                    reason: 'phase_boundary',
                    detail: 'Situated exploration is deliberately not dispatched in Phase 1.',
                    refs: ['obs_movement'],
                },
            ],
        },
    });
}

/**
 * 6. A session carrying real evidence — the Phase-2 shape.
 *
 * Its whole job is to be the OTHER side of the badge guard: `measured` appears here and nowhere
 * else, so a component that painted the badge from a receipt rather than from an evidence object
 * would pass the honest fixtures and fail this one.
 */
export function measuredEvidenceFixture() {
    const s = completedFixture();
    return {
        ...s,
        capability_receipts: [
            {
                receipt_id: 'capr_live_1',
                request_ref: 'obs_extent',
                capability: 'locate_phrase',
                execution_mode: 'live',
                status: 'live',
                usable_as_evidence: true,
                attempted: true,
                payload: { regions: [{ kind: 'mask', rle: '…', area: 0.19 }], phrase: 'colonnade' },
                detail: '',
                latency_ms: 1840,
                provenance: { adapter: 'director', instrument: 'concept_segment' },
            },
        ],
        evidence: [
            {
                evidence_id: 'evd_extent',
                claim_refs: ['clm_colonnade'],
                observable_ref: 'obs_extent',
                receipt_ref: 'capr_live_1',
                kind: 'region_extent',
                epistemic_status: 'measured',
                summary: 'One region covering 19% of the frame across the lower-middle band.',
                usable_as_evidence: true,
                execution_mode: 'live',
                verdict: {
                    verdict_id: 'vd_1',
                    outcome: 'supports',
                    note: 'The extent is measured. That it IS a colonnade is not.',
                },
                provenance: { instrument: 'concept_segment' },
            },
        ],
    };
}

/**
 * 6b. The dangerous shape: an EVIDENCE-shaped object minted from a fixture receipt.
 *
 * This is the one a careless backend actually produces — the simulation returned a region, the
 * judge wrapped it in the same envelope a live one would get, and it arrives carrying `measured`.
 * Every field looks right. Only `execution_mode` says otherwise.
 *
 * A mutation probe is why this fixture exists. Deleting the evidence-grade filter from
 * `supportingEvidence` left the whole suite green, because no fixture had a DISQUALIFIED evidence
 * object attached to a claim — the Phase-1 sessions have no evidence objects at all, so the
 * filter had nothing to filter and its removal changed nothing anyone could see.
 */
export function simulatedEvidenceFixture() {
    const s = completedFixture();
    return {
        ...s,
        evidence: [
            {
                evidence_id: 'evd_simulated',
                claim_refs: ['clm_colonnade'],
                observable_ref: 'obs_extent',
                receipt_ref: 'capr_locate_1',
                kind: 'region_extent',
                epistemic_status: 'measured',
                summary: 'One region covering 21% of the frame across the lower-middle band.',
                usable_as_evidence: false,
                execution_mode: 'fixture',
                verdict: {
                    verdict_id: 'vd_sim',
                    outcome: 'supports',
                    note: 'Produced by the simulation adapter.',
                },
                provenance: { adapter: 'simulation' },
            },
        ],
    };
}

/**
 * 7. A session from a future server: an unrecognised claim kind, status, session state and
 * receipt status, all at once.
 *
 * Nothing here may be coerced into a familiar neighbour. The point of the fixture is that the
 * surface can be older than the backend and still not lie about what it is looking at.
 */
export function unknownFutureFixture() {
    const s = baseSession();
    return {
        ...s,
        state: 'reconciling',
        revision: 9,
        graph: {
            ...s.graph,
            claims: [
                ...s.graph.claims,
                {
                    claim_id: 'clm_future',
                    text: 'The two fronts rhyme across a distance the corpus does not contain.',
                    claim_kind: 'affective_resonance',
                    status: 'attuned',
                    subject: '', predicate: '', object: '',
                    source_span: null,
                    image_scope: ['post_altes_front'],
                    epistemic_demand: '',
                    confidence: null,
                    author: 'oracle',
                },
            ],
        },
        capability_receipts: [
            {
                receipt_id: 'capr_future',
                request_ref: 'obs_extent',
                capability: 'resonance.rhyme',
                execution_mode: 'holographic',
                status: 'attuned',
                usable_as_evidence: true,
                attempted: true,
                payload: { note: 'a shape this client has never seen' },
                detail: '',
                latency_ms: null,
                provenance: {},
            },
        ],
    };
}

/**
 * 8a. STALE: the session moved while you were deciding, but your decision is still open.
 *
 * Revision 6 rather than 3, with an extra automatic record appended — so an `expected_revision: 3`
 * write is correctly rejected, and yet the person's choice may still apply and must not be thrown
 * away.
 */
export function conflictSessionFixture() {
    return baseSession({
        state: 'awaiting_user',
        revision: 6,
        decision_requests: [clone(DECISION_REQUEST)],
        decision_records: [
            {
                record_id: 'rec_auto_scope',
                decision_id: 'dec_auto_scope',
                decider: 'system',
                action: 'select',
                question: 'Read both images, or only the one the claim names?',
                selected_option_id: 'opt_both',
                selected_label: 'Both images',
                free_text: '',
                rationale: 'Reversible and non-authorial, so auto-taken and recorded here.',
                affected_refs: ['clm_centre_shift'],
                at: '2026-08-09T09:16:38Z',
                revision: 6,
            },
        ],
    });
}

/**
 * 8b. DUPLICATE: the decision was answered somewhere else entirely.
 *
 * A different conflict with a different right answer. Nothing should invite a resubmit here — the
 * decision is closed — so the page must be able to explain a conflict with no open card to attach
 * it to.
 */
export function duplicateSessionFixture() {
    return {
        ...respondedFixture(),
        revision: 6,
        decision_records: [
            { ...clone(USER_RECORD), record_id: 'rec_other', rationale: 'Answered in another tab.' },
        ],
    };
}

/**
 * 9. An entirely different domain, through identical types.
 *
 * If any component grows a branch on subject matter, this is the fixture that catches it.
 */
export function otherDomainFixture() {
    return {
        schema_version: 'inquiry-session.v1',
        session_id: 'inqs_fixture_weld',
        inquiry_id: 'inq_fixture_weld',
        revision: 3,
        state: 'awaiting_user',
        mode: 'consult',
        graph: {
            schema_version: 'semantic-inquiry-graph.v1',
            graph_id: 'sig_fixture_weld',
            inquiry_id: 'inq_fixture_weld',
            prompt: 'Where does the corrosion follow the grain boundaries and where does it cut across them?',
            image_refs: [
                {
                    post_id: 'post_weld_a',
                    title: 'Weld cross-section, 200×',
                    image_ref: 'imgref_weld_a',
                    image_url: '/fixtures/weld-a.jpg',
                },
            ],
            reading: {
                text: 'Dark intrusions run along most of the boundary network but at least two '
                    + 'cross a grain interior, which would not be intergranular attack.',
                status: 'interpretive',
                source: 'scene_theorist',
                model: 'vlm/scene-theorist',
                provenance: {},
            },
            claims: [
                {
                    claim_id: 'clm_boundary_follow',
                    text: 'Corrosion follows the grain boundary network.',
                    claim_kind: 'pattern_or_sequence',
                    status: 'proposed',
                    subject: 'corrosion', predicate: 'follows', object: 'grain boundaries',
                    source_span: { origin: 'reading', text: 'run along most of the boundary network', start: 22, end: 59 },
                    image_scope: ['post_weld_a'],
                    epistemic_demand: 'Needs both networks located and compared.',
                    confidence: 0.64,
                    author: 'model',
                },
            ],
            claim_edges: [],
            observables: [
                {
                    observable_id: 'obs_weld_network',
                    claim_ref: 'clm_boundary_follow',
                    observable_kind: 'network_overlap',
                    target: 'boundary network against corrosion network',
                    image_scope: ['post_weld_a'],
                    ground_forms: ['mask'],
                    capability_classes: ['locate_phrase'],
                    alternatives: [],
                    success_condition: 'Two masks that can be intersected.',
                    ambiguity_condition: 'One mask swallowing the other.',
                    refusal_condition: '',
                    residual_interpretation: 'That the overlap means intergranular attack.',
                    availability: 'available',
                    gap_reason: '',
                },
            ],
            semantic_remainder: [
                {
                    remainder_id: 'rem_weld',
                    text: 'Whether the attack is intergranular.',
                    why_unresolved: 'A metallurgical reading, not a geometric one.',
                    claim_refs: ['clm_boundary_follow'],
                },
            ],
            refusals: [],
            provenance: {},
        },
        decision_requests: [
            {
                decision_id: 'dec_weld_scope',
                session_id: 'inqs_fixture_weld',
                kind: 'choose_scope',
                question: 'Measure across the whole section, or only the heat-affected zone?',
                why_now: 'The two give different denominators and the ratio is the answer.',
                affected_refs: ['clm_boundary_follow', 'obs_weld_network'],
                options: [
                    {
                        option_id: 'opt_whole_section', label: 'Whole section',
                        consequence: 'Includes parent metal, which dilutes the ratio.',
                        recommended: false,
                    },
                    {
                        option_id: 'opt_haz', label: 'Heat-affected zone only',
                        consequence: 'Tighter, and depends on where you put the boundary.',
                        recommended: true,
                    },
                ],
                allow_free_text: true,
                blocking: true,
                answered: false,
                provenance: {},
            },
        ],
        decision_records: [],
        capability_receipts: [],
        evidence: [],
        synthesis: null,
        trace: [
            {
                event_id: 'evt_w1', at: '2026-08-09T10:02:00Z', actor: 'semantic_compiler',
                actor_kind: 'model', transition: 'compiling → awaiting_user',
                reason: 'Scope changes the denominator.', refs: ['obs_weld_network'], revision: 3,
            },
        ],
        error: '',
    };
}

/**
 * The canonical fixture for the Lane D handoff — the richest single session this surface renders,
 * exported so the backend can be diffed against something concrete rather than against prose.
 */
export function canonicalFixture() {
    return completedFixture();
}

// ── stage ledgers (HARNESS-003C) ─────────────────────────────────────────────
//
// Written in Lane B's FORWARD shape, because that is what this surface must render next and the
// only way to know it renders is to hand it one. `framerStage` below is deliberately written in
// TODAY's narrower shape — `at`, no `duration_ms`, no actor block — so both servers are covered by
// the same fixtures rather than by a promise that the old one still works.

const FRAMER_STAGE_V1 = {
    event_id: 'stg_framer',
    stage: 'framer',
    outcome: 'completed',
    at: '2026-08-09T09:14:00Z',
    revision: 1,
    detail: 'Prompt and corpus metadata read; no pixels seen.',
    input_refs: [],
    output_refs: ['frm_1'],
};

const THEORIST_RUNNING = {
    attempt_id: 'stg_theorist',
    stage: 'theorist',
    outcome: 'started',
    sequence: 2,
    revision: 2,
    queued_at: '2026-08-09T09:14:01Z',
    started_at: '2026-08-09T09:14:02Z',
    completed_at: null,
    duration_ms: null,
    actor: {
        role: 'scene_theorist',
        model: 'qwen/qwen3.6-27b',
        provider: 'groq',
        execution_mode: 'live',
    },
    call_topology: 'per_image_then_synthesis',
    planned_calls: 5,
    actual_calls: 2,
    image_index: 1,
    image_total: 4,
    substage: 'reading image 2',
    input_refs: ['post_altes_front', 'post_altes_rotunda'],
    input_count: 4,
    output_refs: [],
    output_count: 0,
    calls: [
        { call_id: 'call_1', label: 'image 1', duration_ms: 8400, finish_reason: 'stop' },
        { call_id: 'call_2', label: 'image 2', duration_ms: null, finish_reason: '' },
    ],
};

const THEORIST_COMPLETED = {
    ...THEORIST_RUNNING,
    outcome: 'completed',
    completed_at: '2026-08-09T09:14:41Z',
    duration_ms: 39200,
    actual_calls: 5,
    image_index: 3,
    substage: 'cross-image synthesis',
    output_refs: ['rdb_1', 'rdb_2', 'rdb_3'],
    output_count: 31,
    calls: [
        { call_id: 'call_1', label: 'image 1', duration_ms: 8400, finish_reason: 'stop' },
        { call_id: 'call_2', label: 'image 2', duration_ms: 7900, finish_reason: 'stop' },
        { call_id: 'call_3', label: 'image 3', duration_ms: 8100, finish_reason: 'stop' },
        { call_id: 'call_4', label: 'image 4', duration_ms: 7600, finish_reason: 'stop' },
        { call_id: 'call_5', label: 'cross-image synthesis', duration_ms: 7200, finish_reason: 'stop' },
    ],
};

const COMPILER_TRUNCATED = {
    attempt_id: 'stg_compiler',
    stage: 'compiler',
    outcome: 'truncated',
    sequence: 3,
    revision: 3,
    started_at: '2026-08-09T09:14:41Z',
    completed_at: '2026-08-09T09:15:02Z',
    duration_ms: 21400,
    actor: {
        role: 'semantic_compiler',
        model: 'openai/gpt-oss-120b',
        provider: 'groq',
        execution_mode: 'live',
    },
    call_topology: 'text_only',
    planned_calls: 1,
    actual_calls: 1,
    // The live measurement from the 002D finding: every run hit the output budget.
    finish_reason: 'length',
    input_refs: ['rdb_1', 'rdb_2', 'rdb_3'],
    input_count: 31,
    output_refs: ['clm_colonnade', 'clm_centre_shift'],
    output_count: 2,
    detail: 'The response stopped at the output limit. The parsed prefix is what is below.',
    error_summary: '31 reading blocks entered; 2 claims and 0 observables emerged.',
};

const STEWARD_SKIPPED = {
    attempt_id: 'stg_steward',
    stage: 'steward',
    outcome: 'skipped',
    sequence: 4,
    revision: 4,
    duration_ms: null,
    detail: 'No observable reached the steward, so there was no fork to offer.',
    input_refs: [],
    output_refs: [],
};

/**
 * 10. Actively running: the theorist mid-way through four images.
 *
 * The state the 002R rehearsal spent most of its time in and could not see.
 */
export function runningStagesFixture() {
    return baseSession({
        state: 'reading',
        revision: 2,
        graph: { ...baseSession().graph, claims: [], claim_edges: [], observables: [],
                 semantic_remainder: [], reading: { text: '', status: '', source: '', provenance: {} } },
        stages: [FRAMER_STAGE_V1, THEORIST_RUNNING],
    });
}

/** 11. A rich reading, then a compiler that stopped mid-sentence. */
export function truncatedCompilerFixture() {
    return baseSession({
        state: 'exhausted',
        revision: 5,
        stop_reason: 'The compiler was truncated, so no observable was produced to investigate.',
        stages: [FRAMER_STAGE_V1, THEORIST_COMPLETED, COMPILER_TRUNCATED, STEWARD_SKIPPED],
        graph: {
            ...baseSession().graph,
            claims: clone(CLAIMS).slice(0, 2),
            claim_edges: [],
            observables: [],
            semantic_remainder: [],
        },
    });
}

/** 12. Nothing compiled at all — the barren graph, with the ledger that explains it. */
export function barrenFixture() {
    return baseSession({
        state: 'exhausted',
        revision: 4,
        stop_reason: 'Nothing was compiled from the reading.',
        stages: [
            FRAMER_STAGE_V1,
            THEORIST_COMPLETED,
            {
                ...COMPILER_TRUNCATED,
                outcome: 'empty',
                finish_reason: 'stop',
                output_refs: [],
                output_count: 0,
                detail: 'The compiler returned a well-formed response containing no claims.',
                error_summary: '31 reading blocks entered; 0 claims and 0 observables emerged.',
            },
            STEWARD_SKIPPED,
        ],
        graph: {
            ...baseSession().graph,
            claims: [],
            claim_edges: [],
            observables: [],
            semantic_remainder: [],
        },
    });
}

/** 13. A complete session with its whole ledger, for the ordinary case. */
export function stagedCompleteFixture() {
    const s = completedFixture();
    return {
        ...s,
        stages: [
            FRAMER_STAGE_V1,
            THEORIST_COMPLETED,
            {
                ...COMPILER_TRUNCATED,
                outcome: 'completed',
                finish_reason: 'stop',
                output_count: 4,
                output_refs: ['clm_colonnade', 'clm_centre_shift', 'clm_threshold_converts',
                              'clm_temple_front'],
                detail: '',
                error_summary: '',
            },
            {
                attempt_id: 'stg_capability',
                stage: 'capability',
                outcome: 'completed',
                sequence: 5,
                duration_ms: 12,
                actor: { role: 'capability_broker', execution_mode: 'fixture' },
                input_refs: ['obs_extent'],
                output_refs: ['capr_locate_1'],
            },
            {
                attempt_id: 'stg_composer',
                stage: 'composer',
                outcome: 'completed',
                sequence: 7,
                duration_ms: 4300,
                actor: { role: 'synthesis_composer', model: 'openai/gpt-oss-120b', provider: 'groq',
                         execution_mode: 'live' },
                finish_reason: 'stop',
                input_refs: ['clm_colonnade'],
                output_refs: ['syn_1'],
                output_count: 3,
            },
        ],
    };
}

/** 14. A stage vocabulary from a future server. */
export function unknownStageFixture() {
    return baseSession({
        state: 'reconciling',
        stages: [
            FRAMER_STAGE_V1,
            {
                attempt_id: 'stg_future',
                stage: 'resonator',
                outcome: 'attuning',
                duration_ms: null,
                actor: { execution_mode: 'holographic' },
            },
        ],
    });
}

/**
 * 15. The whole chain, dissolved — the shape HARNESS-003A is building toward.
 *
 * Every source unit has exactly one disposition except `su_5`, which deliberately has none: a unit
 * the compiler LOST is not a remainder, and the ledger has to be able to tell those apart.
 */
export function dissolvedFixture() {
    const s = completedFixture();
    return {
        ...s,
        graph: {
            ...s.graph,
            source_units: [
                {
                    source_unit_id: 'su_1', source_type: 'prompt_clause',
                    source_ref: 'prompt#0:62',
                    exact_quote: 'How does this building turn a dispersed civic ground into a centralized interior',
                    image_refs: [],
                },
                {
                    source_unit_id: 'su_2', source_type: 'prompt_clause',
                    source_ref: 'prompt#62:110',
                    exact_quote: 'what does the threshold between them actually do',
                    image_refs: [],
                },
                {
                    source_unit_id: 'su_3', source_type: 'reading_block', source_ref: 'rdb_1',
                    exact_quote: 'a screen of columns held between two solid ends',
                    image_refs: ['post_altes_front'],
                },
                {
                    source_unit_id: 'su_4', source_type: 'reading_block', source_ref: 'rdb_3',
                    exact_quote: 'The comparison that suggests itself is with a temple front',
                    image_refs: ['post_altes_front'],
                },
                {
                    source_unit_id: 'su_5', source_type: 'reading_block', source_ref: 'rdb_2',
                    exact_quote: 'the rotunda is a centre that the façade never announces',
                    image_refs: ['post_altes_front', 'post_altes_rotunda'],
                },
            ],
            semantic_atoms: [
                {
                    atom_id: 'atm_1', source_unit_ids: ['su_3'],
                    text: 'a colonnade spans the front',
                    unit_kind: 'entity', subject: 'colonnade', predicate: 'spans',
                    object: 'front elevation',
                    image_scope: ['post_altes_front'], epistemic_ceiling: 'interpretive',
                    author: 'model',
                    provenance: { role: 'semantic_dissector', model: 'openai/gpt-oss-120b' },
                },
                {
                    atom_id: 'atm_2', source_unit_ids: ['su_1', 'su_2'],
                    text: 'the threshold converts the approach',
                    unit_kind: 'causal_hypothesis', subject: 'threshold', predicate: 'converts',
                    object: 'approach',
                    image_scope: ['post_altes_front'], epistemic_ceiling: 'interpretive',
                    author: 'user',
                    provenance: { role: 'semantic_dissector' },
                },
                {
                    atom_id: 'atm_3', source_unit_ids: ['su_4'],
                    text: 'the front quotes a temple portico',
                    unit_kind: 'historical_or_sourced', subject: '', predicate: '', object: '',
                    image_scope: ['post_altes_front'], epistemic_ceiling: 'sourced',
                    author: 'model', provenance: { role: 'semantic_dissector' },
                },
            ],
            coverage: [
                { source_unit_id: 'su_1', disposition: 'represented_by', refs: ['atm_2'], reason: '' },
                { source_unit_id: 'su_2', disposition: 'represented_by', refs: ['atm_2'], reason: '' },
                { source_unit_id: 'su_3', disposition: 'represented_by', refs: ['atm_1'], reason: '' },
                {
                    source_unit_id: 'su_4', disposition: 'semantic_remainder', refs: [],
                    reason: 'A claim about sources. No measurement of these pixels can settle it.',
                },
            ],
        },
    };
}

export default consultFixture;
