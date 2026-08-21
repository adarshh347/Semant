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

/**
 * 16. The council's own receipts — HARNESS-003D.
 *
 * `dissolvedFixture` shows what a compilation PRODUCED. This shows what produced it: five passes,
 * their model, their calls, and — on the dissector — the two things that only exist once a real
 * account's per-minute allowance is in the loop. `transport_attempts` exceeds `call_count` because
 * the same bytes were re-sent after a refusal, and `waited_ms` is the wall-clock that bought.
 *
 * The deployment is `live` and reachable, because this fixture's job is to be the case where every
 * number is real. `pacedOutFixture` is the same run with the budget gate closing on it.
 */
export function councilFixture() {
    const s = dissolvedFixture();
    return {
        ...s,
        deployment: {
            kind: 'live',
            declared: true,
            reachable: true,
            detail: 'compiler and theorist bound to openai/gpt-oss-120b on groq',
        },
        graph: {
            ...s.graph,
            passes: [
                {
                    pass_id: 'pss_1', pass_name: 'source_ledger', outcome: 'completed',
                    model: 'openai/gpt-oss-120b', provider: 'groq',
                    call_count: 1, transport_attempts: 1, finish_reasons: ['stop'],
                    duration_ms: 4200, waited_ms: null, capacity_waits: [],
                    inputs: 7, outputs: 5, detail: '', notes: [],
                },
                {
                    pass_id: 'pss_2', pass_name: 'semantic_dissector', outcome: 'completed',
                    model: 'openai/gpt-oss-120b', provider: 'groq',
                    call_count: 2, transport_attempts: 4, finish_reasons: ['stop', 'stop'],
                    duration_ms: 31800, waited_ms: 41000,
                    capacity_waits: [
                        {
                            attempt: 1, seconds: 7.7, source: 'provider_message', taken: true,
                            detail: 'try again in 7.66s',
                        },
                        {
                            attempt: 2, seconds: 33.3, source: 'provider_retry_after', taken: true,
                            detail: 'retry-after: 33.3',
                        },
                    ],
                    inputs: 5, outputs: 3, detail: '', notes: [],
                },
                {
                    pass_id: 'pss_3', pass_name: 'targeted_repair', outcome: 'thin',
                    model: 'openai/gpt-oss-120b', provider: 'groq',
                    call_count: 1, transport_attempts: 1, finish_reasons: ['stop'],
                    duration_ms: 6100, waited_ms: null, capacity_waits: [],
                    inputs: 1, outputs: 0,
                    detail: 'su_5 came back with nothing said about it.', notes: [],
                },
                {
                    pass_id: 'pss_4', pass_name: 'relation_architect', outcome: 'completed',
                    model: 'openai/gpt-oss-120b', provider: 'groq',
                    call_count: 1, transport_attempts: 1, finish_reasons: ['stop'],
                    duration_ms: 18400, waited_ms: null, capacity_waits: [],
                    inputs: 3, outputs: 4, detail: '', notes: [],
                },
                {
                    pass_id: 'pss_5', pass_name: 'epistemic_operationalizer', outcome: 'completed',
                    model: 'openai/gpt-oss-120b', provider: 'groq',
                    call_count: 1, transport_attempts: 1, finish_reasons: ['stop'],
                    // A deterministic-looking pass that genuinely made a call and genuinely did
                    // not wait: `waited_ms` stays null rather than becoming 0.
                    duration_ms: 12900, waited_ms: null, capacity_waits: [],
                    inputs: 4, outputs: 2, detail: '', notes: [],
                },
            ],
            coverage_summary: {
                source_units: 5, disposed: 4, represented: 3,
                by_disposition: { represented_by: 3, semantic_remainder: 1 },
                lost: ['su_5'], lost_count: 1,
                user_units: 2, reading_units: 3,
                complete: false,
            },
        },
    };
}

/**
 * 17. The same council, stopped by its own declared budget.
 *
 * The last wait was NOT taken: the gate closed instead. That is the case the whole pacing design
 * exists for — a run that ends honestly short rather than one that quietly shrinks its reading to
 * fit an allowance — and it must never render as a run that was still going.
 */
export function pacedOutFixture() {
    const s = councilFixture();
    const notReached = (p) => ({
        ...p,
        outcome: 'unavailable', call_count: 0, transport_attempts: 0,
        duration_ms: null, waited_ms: null, capacity_waits: [], finish_reasons: [],
        inputs: null, outputs: null,
        detail: 'The run had stopped before this pass was entered.',
    });
    const passes = s.graph.passes.map((p) => (p.pass_name === 'epistemic_operationalizer'
        ? notReached(p) : p)).map((p) => (p.pass_name === 'relation_architect'
        ? {
            ...p,
            outcome: 'unavailable',
            call_count: 0, transport_attempts: 6, duration_ms: null,
            waited_ms: 1_684_000, finish_reasons: [],
            capacity_waits: [
                { attempt: 1, seconds: 20, source: 'declared_interval', taken: true, detail: '' },
                {
                    attempt: 6, seconds: null, source: 'budget_exhausted', taken: false,
                    detail: 'the 30 minute gate budget was spent',
                },
            ],
            detail: 'The provider had no allowance left inside this run\'s budget.',
        }
        : p));
    return {
        ...s,
        state: 'exhausted',
        stop_reason: 'The run stopped waiting for provider capacity after 28m of its 30m budget.',
        graph: { ...s.graph, passes },
    };
}

/**
 * 18. The council with its passes BATCHED, and the coverage matrix that makes the batching honest.
 *
 * HARNESS-003E. One request over every atom could not be sent — 9,827 tokens against an 8,000
 * allowance — so the architect works in batches. Batching alone would make every relation crossing
 * a boundary structurally invisible, so the pass also compares every PAIR of batches, and the
 * matrix is what says whether it did.
 *
 * The architect here is whole: four batches, all six pairs compared. The operationalizer is the
 * case that matters — two of its three pairs were never put in front of the model, so it is `thin`
 * and it names them. A surface that rendered `4 of 6` and `1 of 3` alike would turn a reported
 * limit back into the silence this whole lane exists to remove.
 */
export function batchedCouncilFixture() {
    const s = councilFixture();
    const passes = s.graph.passes.map((p) => {
        if (p.pass_name === 'relation_architect') {
            return {
                ...p,
                call_count: 8, transport_attempts: 9,
                finish_reasons: ['stop', 'stop', 'stop', 'stop', 'stop', 'stop', 'stop', 'stop'],
                detail: '19 claim(s) and 11 relation(s) over 74 atoms in 4 batch(es), with 6 of 6 '
                    + 'batch pair(s) compared across 4 reconciliation round(s)',
                batch_plan: {
                    plan_id: 'plan_arch01', plan_version: 'semantic-batch-plan.v1',
                    unit: 'semantic_atom', total_items: 74,
                    batches: 4, unsendable_batches: 0,
                    allowance_tokens: 8000, largest_request_tokens: 7104,
                    pairs_total: 6, pairs_examined: 6, unexamined_pairs: [],
                    rounds: [
                        {
                            round_id: 'rnd_a1', index: 1, total: 4, groups: 2, outcome: 'completed',
                            added_edges: 3, added_claims: 1, duplicate_claims: 1, detail: '',
                        },
                        {
                            round_id: 'rnd_a2', index: 2, total: 4, groups: 2, outcome: 'completed',
                            added_edges: 2, added_claims: 0, duplicate_claims: 0, detail: '',
                        },
                        {
                            round_id: 'rnd_a3', index: 3, total: 4, groups: 2, outcome: 'completed',
                            added_edges: 1, added_claims: 1, duplicate_claims: 0, detail: '',
                        },
                        {
                            round_id: 'rnd_a4', index: 4, total: 4, groups: 2, outcome: 'completed',
                            added_edges: 0, added_claims: 0, duplicate_claims: 0, detail: '',
                        },
                    ],
                    dispositions: { used: 61, orphan: 13 },
                    duplicates_merged: 1,
                    notes: ['sized against a 8000-token allowance, holding back 800 as margin'],
                },
            };
        }
        if (p.pass_name === 'epistemic_operationalizer') {
            return {
                ...p,
                outcome: 'thin', call_count: 4, transport_attempts: 4,
                detail: '2 of 3 claim-group pair(s) were never compared, so any fork between them '
                    + 'was invisible to this pass',
                batch_plan: {
                    plan_id: 'plan_ops01', plan_version: 'semantic-batch-plan.v1',
                    unit: 'claim', total_items: 19,
                    batches: 3, unsendable_batches: 0,
                    allowance_tokens: 8000, largest_request_tokens: 6820,
                    pairs_total: 3, pairs_examined: 1,
                    unexamined_pairs: [
                        {
                            left: 'bat_o1', right: 'bat_o3',
                            reason: 'the run stopped before this pair\'s round: the declared '
                                + 'wall-clock budget or the transport attempt bound ended the pass',
                        },
                        {
                            left: 'bat_o2', right: 'bat_o3',
                            reason: 'the run stopped before this pair\'s round: the declared '
                                + 'wall-clock budget or the transport attempt bound ended the pass',
                        },
                    ],
                    rounds: [
                        {
                            round_id: 'rnd_o1', index: 1, total: 3, groups: 2, outcome: 'completed',
                            added_edges: 0, added_claims: 0, duplicate_claims: 0, detail: '',
                        },
                    ],
                    dispositions: { operationalized: 11, semantic_remainder: 5,
                        not_investigated: 3 },
                    duplicates_merged: 0,
                    notes: [],
                },
            };
        }
        return p;
    });
    return { ...s, graph: { ...s.graph, passes } };
}

/**
 * A declared vertical slice that actually BITES. HARNESS-003F.
 *
 * Built on the batched council rather than beside it, because the fact under test is what a BOUND
 * does to a pass that would otherwise have run whole: this is the same four-batch relation
 * partition with one request permitted, so the numbers a reader compares — 4 planned, 1 sent — are
 * the same numbers in both fixtures and only the bound has moved.
 *
 * Every kind of exclusion is present at once. A fixture with only deferred source units would let a
 * surface that ignored uninvestigated atoms and claims pass, and those are the two a person is most
 * likely to mistake for a finding about the images: an atom nothing related and a claim nothing
 * proposed an observable for look, from outside, exactly like an atom nothing COULD be built from.
 */
export function scopedFixture() {
    const s = batchedCouncilFixture();
    const passes = s.graph.passes.map((p) => {
        if (p.pass_name === 'relation_architect') {
            return {
                ...p,
                outcome: 'thin',
                detail: '5 claim(s) over 74 atoms in 1 of 4 permitted batch(es)',
                batch_plan: {
                    ...p.batch_plan,
                    batches_sent: 1,
                    // THE MATRIX IS EMPTY AND THE REASON IS NOT "nothing across". One batch was
                    // sent, so there is no second group — and the three that were not sent are the
                    // reason, which the note has to say or the plan reads as contradicting itself.
                    pairs_total: 0, pairs_examined: 0, unexamined_pairs: [], rounds: [],
                    dispositions: { used: 14, orphan: 4, not_investigated: 56 },
                    notes: [
                        '1 of 4 batch(es) produced a claim; 3 was/were not sent at all under a '
                        + 'declared execution scope. There was no second group to compare '
                        + 'against.',
                    ],
                },
            };
        }
        if (p.pass_name === 'epistemic_operationalizer') {
            return {
                ...p,
                batch_plan: {
                    ...p.batch_plan,
                    batches_sent: 2,
                    dispositions: { operationalized: 2, not_investigated: 17 },
                },
            };
        }
        return p;
    });
    return {
        ...s,
        // A STAGE LEDGER, because a real session always has one and the panel reads it for the
        // longest stage. The compiler is the long one here for the reason it is long in every live
        // run of this chain: the council is inside it.
        stages: [
            { attempt_id: 'stg_framer', stage: 'framer', outcome: 'completed', sequence: 1,
              duration_ms: 70, actor: { execution_mode: 'none' } },
            { attempt_id: 'stg_theorist', stage: 'theorist', outcome: 'completed', sequence: 2,
              duration_ms: 90800, actor: { role: 'scene_theorist', model: 'openai/gpt-oss-120b',
                  provider: 'groq', execution_mode: 'live' } },
            { attempt_id: 'stg_compiler', stage: 'compiler', outcome: 'thin', sequence: 3,
              duration_ms: 114400, actor: { role: 'council', model: 'openai/gpt-oss-120b',
                  provider: 'groq', execution_mode: 'live' } },
        ],
        execution_scope: {
            mode: 'vertical_slice',
            recorded: true,
            scope_version: 'inquiry-execution-scope.v1',
            purpose: 'live_vertical_flow_rehearsal',
            selection_producer: 'semantic_compilation/scope-v1',
            allowance_tokens: 8000,
            full_coverage: false,
            selected_source_units: 9,
            deferred_source_units: 26,
            selected_atoms: 74,
            atoms_not_investigated: 56,
            selected_claims: 5,
            claims_not_investigated: 3,
            relation_batches_allowed: 1,
            relation_batches_sent: 1,
            operationalizer_batches_allowed: 2,
            operationalizer_batches_sent: 2,
            reconciliation_rounds_allowed: 0,
            reconciliation_rounds_sent: 0,
            exclusions: [
                {
                    ref: 'su_deferred_1', kind: 'source_unit',
                    reason: 'temporary vertical-slice rehearsal scope; not investigated and not '
                        + 'evidence of absence. Its atoms are projected at 148 token(s) and 12 of '
                        + 'the 4142-token relation request remained when it was reached.',
                },
                {
                    ref: 'atom_skipped_1', kind: 'semantic_atom',
                    reason: 'a declared execution scope permitted fewer relation requests than '
                        + 'this partition needed, so no architect call saw this atom. It was not '
                        + 'refused and nothing was found to be absent from it.',
                },
                {
                    ref: 'clm_skipped_1', kind: 'claim',
                    reason: 'a declared execution scope permitted fewer operationalization '
                        + 'requests than this partition needed, so nothing was asked about this '
                        + 'claim. It is not that nothing could be observed about it — nobody asked.',
                },
            ],
            notes: [
                'the vertical-slice scope selected 9 of 35 source unit(s) — 4 of 4 from the '
                + 'person — across 3 of 4 image group(s).',
                'every deferred unit is still in the ledger with its own id and is disposed '
                + '`refused` with the scope\'s reason.',
            ],
        },
        graph: { ...s.graph, passes },
    };
}

/**
 * A scope that was ASKED FOR and never recorded: the session died before the compiler ran.
 *
 * The state the badge most has to survive, and the one a projection keyed on the graph would lose.
 * `recorded: false` with `full_coverage: false` is a run nobody bounded in practice and nobody may
 * read as complete either.
 */
export function unrecordedScopeFixture() {
    const s = scopedFixture();
    return {
        ...s,
        state: 'exhausted',
        stop_reason: 'the theorist stage came back unavailable, so there was nothing to compile.',
        execution_scope: {
            mode: 'vertical_slice', recorded: false, scope_version: '', purpose: '',
            selection_producer: '', allowance_tokens: null, full_coverage: false,
            selected_source_units: 0, deferred_source_units: 0,
            selected_atoms: 0, atoms_not_investigated: 0,
            selected_claims: 0, claims_not_investigated: 0,
            relation_batches_allowed: null, relation_batches_sent: null,
            operationalizer_batches_allowed: null, operationalizer_batches_sent: null,
            reconciliation_rounds_allowed: null, reconciliation_rounds_sent: null,
            exclusions: [], notes: [],
        },
    };
}

/**
 * 27. A CITATION THAT NAMES A PICTURE THE SESSION DOES NOT CARRY — and one nobody cited.
 *
 * Both of the image panel's absences, in one session, because they arrive together in practice: a
 * chain that dropped an image from the catalogue leaves the citations to it behind, and the image
 * that WAS carried goes unmentioned. Neither is a rendering problem. `post_altes_missing` is cited
 * by a source unit and an atom and appears in no `image_refs` entry, which is an upstream defect
 * the surface has to be able to say out loud; `post_altes_rotunda` is handed to the run and cited
 * by nothing, which is the quieter of the two and the one more likely to be read as "fine".
 */
export function danglingImageFixture() {
    const s = dissolvedFixture();
    return {
        ...s,
        graph: {
            ...s.graph,
            // BOTH are carried, and that is the point of the second absence: the rotunda was
            // handed to the run and read, and every citation to it is stripped below. An image
            // missing from the catalogue would be a different bug; this one is present and idle.
            image_refs: clone(IMAGES),
            reading: { ...s.graph.reading, blocks: s.graph.reading.blocks.map(
                (b) => ({ ...b, image_refs: b.image_refs.filter((r) => r !== 'post_altes_rotunda') }),
            ) },
            source_units: [
                ...s.graph.source_units.map(
                    (u) => ({ ...u, image_refs: u.image_refs.filter((r) => r !== 'post_altes_rotunda') }),
                ),
                {
                    source_unit_id: 'su_9', source_type: 'reading_block', source_ref: 'rdb_4',
                    exact_quote: 'the stair converts a lateral approach into a vertical one',
                    image_refs: ['post_altes_missing'],
                },
            ],
            semantic_atoms: [
                ...s.graph.semantic_atoms,
                {
                    atom_id: 'atm_9', source_unit_ids: ['su_9'],
                    text: 'the stair converts the approach',
                    unit_kind: 'causal_hypothesis', subject: 'stair', predicate: 'converts',
                    object: 'approach',
                    image_scope: ['post_altes_missing'], epistemic_ceiling: 'interpretive',
                    author: 'model', provenance: { role: 'semantic_dissector' },
                },
            ],
            claims: s.graph.claims.map(
                (c) => ({ ...c, image_scope: c.image_scope.filter((r) => r !== 'post_altes_rotunda') }),
            ),
        },
    };
}

export default consultFixture;
