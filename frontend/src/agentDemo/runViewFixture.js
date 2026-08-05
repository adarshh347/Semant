/**
 * AGENT-DEMO — `runViewFixture`, Lane B's copy.
 *
 * OWNERSHIP NOTE, and it matters: `run-contract.md` assigns this fixture to Lane A, which also
 * owns the routes that will produce it. This file is written from the spec so Lane B can build
 * and be tested before those routes exist. When Lane A's fixture lands, THIS ONE SHOULD BE
 * DELETED and its import swapped — not merged with, not kept alongside. Two fixtures claiming to
 * be the same contract is the drift the shared-fixture rule exists to prevent.
 *
 * Until then it is the honest thing available: a payload written to the contract, which the
 * component tests render, so the surface is exercised against a shape rather than against
 * nothing.
 *
 * IT DELIBERATELY INCLUDES THE FAILURES. A fixture that only renders the happy path would tell
 * you nothing about this surface's actual job, which is transparency — so it carries a refused
 * step, a step that produced nothing, an unknown latency, an unknown model, a percept with no
 * confidence, and (in its awaiting-answer variant) a real blocking question. Those are the rows
 * whose rendering is worth checking.
 */
import articleFixture from '../article/articleFixture.js';

const GROUND = 'post_lustgarten';
const FACADE = 'post_facade';
const ROTUNDA = 'post_rotunda';

/** A 1×1 data-URI so the fixture fetches nothing, matching ArticleLab's offline discipline. */
const BLANK = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';

export const FIXTURE_CORPUS = [
    { post_id: GROUND, image_url: BLANK, title: 'Lustgarten' },
    { post_id: FACADE, image_url: BLANK, title: 'Colonnade' },
    { post_id: ROTUNDA, image_url: BLANK, title: 'Rotunda' },
];

const PROMPT =
    'How does the Altes Museum turn a dispersed civic ground into a centralized interior?';

function record(over = {}) {
    return {
        step_id: 's0',
        actuator: 'pressure_zone',
        params: { image: GROUND },
        model: 'dinov2_vits14',
        adapter: 'pressure_zone',
        consumed: [`${GROUND}:image`],
        produced: [
            { id: null, ref: 'run_demo_1:s0#0', kind: 'brush_field',
              epistemic_status: 'measured', confidence: 0.82 },
        ],
        refusal: null,
        latency_ms: 412,
        ...over,
    };
}

export const FIXTURE_PRODUCTION_RECORDS = [
    record({ step_id: 's1', params: { image: GROUND } }),
    record({
        step_id: 's2',
        actuator: 'rhythm',
        params: { image: FACADE },
        model: null,                       // a producer that names no model — receipt is run_id only
        adapter: 'rhythm',
        consumed: [`${FACADE}:image`],
        produced: [
            { id: null, ref: 'run_demo_1:s2#0', kind: 'trace_mark',
              epistemic_status: 'visible', confidence: null },
        ],
        latency_ms: 96,
    }),
    record({
        step_id: 's3',
        actuator: 'pressure_zone',
        params: { image: ROTUNDA },
        consumed: [`${ROTUNDA}:image`],
        produced: [
            { id: null, ref: 'run_demo_1:s3#0', kind: 'brush_field',
              epistemic_status: 'measured', confidence: 0.77 },
        ],
        latency_ms: 388,
    }),
    // A REFUSAL. Not an error and not an absence — a result, with a reason.
    record({
        step_id: 's4',
        actuator: 'external_limit',
        params: { image: FACADE },
        model: 'geocalib',
        adapter: 'geocalib',
        consumed: [`${FACADE}:image`],
        produced: [],
        refusal: {
            reason: 'up_vector_spread',
            detail: 'Frontal image — no projective frame to trace. A lattice of horizon strokes '
                + 'across a flat wall would assert a recession the picture does not have.',
        },
        latency_ms: 121,
    }),
    // A step that RAN and produced nothing, with no latency recorded. Both unknowns stay null.
    record({
        step_id: 's5',
        actuator: 'historical_source',
        params: { query: 'Altes Museum Schinkel rotunda' },
        model: null,
        adapter: 'external_source',
        consumed: [],
        produced: [],
        refusal: null,
        latency_ms: null,
    }),
    record({
        step_id: 's6',
        actuator: 'compose_percept',
        params: {},
        model: 'gpt-oss-120b',
        adapter: 'semantic_pass',
        consumed: ['sug_1', 'sug_3'],
        produced: [
            { id: null, ref: 'run_demo_1:s6#0', kind: 'percept',
              epistemic_status: 'interpretive', confidence: 0.4 },
        ],
        latency_ms: 1840,
    }),
];

const ROUNDS = [
    {
        round: 1,
        intention: PROMPT,
        plan: { steps: ['pressure_zone', 'rhythm', 'pressure_zone'] },
        step_ids: ['s1', 's2', 's3'],
        weakest_link: 0.77,
        note: 'Opened on the three images; measured pressure on the ground and the rotunda.',
    },
    {
        round: 2,
        intention: PROMPT,
        plan: { steps: ['external_limit', 'historical_source', 'compose_percept'] },
        step_ids: ['s4', 's5', 's6'],
        weakest_link: 0.4,
        note: 'Tried the projective frame (refused), then composed across the two measurements.',
    },
];

/**
 * The default fixture: a finished `argue` run carrying a real M4 article.
 *
 * The article is `articleFixture()` verbatim — the same payload `/lab/article` renders. Reused
 * rather than re-invented so this surface and the article harness cannot disagree about what an
 * ArticleDraft looks like, and so the article's own deliberate defects (a relevance flag, an
 * AMBIGUOUS citation that refuses to draw, a refused claim) arrive here too.
 */
export default function runViewFixture(over = {}) {
    return {
        run_id: 'run_demo_1',
        status: 'complete',
        intention: PROMPT,
        mode: 'argue',
        corpus: FIXTURE_CORPUS,
        rounds: ROUNDS,
        question: null,
        stop_reason: null,
        weakest_link: 0.4,
        suggestions: [],
        production_records: FIXTURE_PRODUCTION_RECORDS,
        article: articleFixture(),
        ...over,
    };
}

/** Mid-flight: one round done, nothing terminal. Drives the live-progress rendering. */
export function runningFixture() {
    return runViewFixture({
        status: 'running',
        rounds: ROUNDS.slice(0, 1),
        production_records: FIXTURE_PRODUCTION_RECORDS.slice(0, 3),
        weakest_link: 0.77,
        article: null,
    });
}

/**
 * Blocked on a human (A2/A3). The question is grounded — it names the step it blocks and the
 * param it needs, which is what makes it answerable rather than a chat prompt.
 */
export function awaitingAnswerFixture() {
    return runViewFixture({
        status: 'awaiting_answer',
        rounds: ROUNDS.slice(0, 1),
        production_records: FIXTURE_PRODUCTION_RECORDS.slice(0, 3),
        article: null,
        weakest_link: 0.77,
        question: {
            question_id: 'q1',
            text: 'Which reading of the colonnade should I test?',
            why: 'The plan needs a `lens` for the next step, and the corpus supports two readings '
                + 'that would produce different evidence.',
            options: [
                { value: 'threshold', label: 'As a threshold between ground and interior' },
                { value: 'screen', label: 'As a screen that withholds the interior' },
            ],
            blocked_step_id: 's7',
            param: 'lens',
        },
    });
}

/** `explore` mode: produced percepts, no article. The surface must render evidence directly. */
export function exploreFixture() {
    return runViewFixture({
        run_id: 'run_demo_explore',
        mode: 'explore',
        article: null,
    });
}

/**
 * HONEST EMPTINESS: a finished run that produced nothing, and says why. The surface must show
 * the reason rather than an empty success.
 */
export function emptyRunFixture() {
    return runViewFixture({
        run_id: 'run_demo_empty',
        status: 'stopped',
        mode: 'explore',
        rounds: [],
        production_records: [],
        article: null,
        weakest_link: null,
        stop_reason: 'Every planned step refused: the corpus carries no measurable pressure and '
            + 'no projective frame. Nothing was produced, and nothing was guessed.',
    });
}
