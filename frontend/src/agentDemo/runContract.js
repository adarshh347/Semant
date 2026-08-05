/**
 * AGENT-DEMO — the Run Contract, as runnable code.
 *
 * `run-contract.md` is the interface between Lane A (backend run surface) and Lane B (this
 * demo). This module is Lane B's half of it: the vocabulary, and the normalisers every component
 * reads through. Nothing here fetches, renders, or holds React state — so the contract can be
 * asserted in a unit test rather than only observed in a browser.
 *
 * WHY NORMALISE AT ALL, when the backend promises the shape? Because the promise is the thing
 * under construction. Lane A is building these routes in parallel, and for the whole of that
 * window this surface renders a fixture written from the spec rather than from a live response.
 * The first real payload WILL differ somewhere — a null where a list was assumed, a field not
 * filled yet. Reading through normalisers means that difference shows up as a missing row, not
 * as a white screen, and the demo survives the meeting of the two lanes.
 *
 * The governing principle it enforces: a run needs only IMAGES + A PROMPT. Nothing here requires
 * a region, a ground, a mark or a text block, and `canStartRun` is the executable form of that —
 * it asks for a corpus selection and an intention, and asks for nothing else.
 */

// ── the lifecycle ────────────────────────────────────────────────────────────
// pending → running → (awaiting_answer ⇄ running) → complete | stopped
export const RUN_STATUSES = ['pending', 'running', 'awaiting_answer', 'complete', 'stopped'];

export const IS_TERMINAL = (status) => status === 'complete' || status === 'stopped';
/** A run that is still going, in the sense that matters to the UI: keep listening. */
export const IS_LIVE = (status) => status === 'pending' || status === 'running';
/** The one state that needs a human before anything else can happen (A2/A3). */
export const IS_BLOCKED_ON_HUMAN = (status) => status === 'awaiting_answer';

export const RUN_MODES = ['explore', 'argue'];
export const DEFAULT_MODE = 'explore';

/**
 * M5's five ways of knowing, carried on every produced descriptor. Ordered strongest-claim
 * first, which is the order the transparency panel groups them in — a reader scanning what a run
 * produced should meet `measured` before `uncertain`, not alphabetically.
 */
export const EPISTEMIC_ORDER = ['measured', 'visible', 'sourced', 'interpretive', 'uncertain'];

export const EPISTEMIC_LABEL = {
    measured: 'Measured',
    visible: 'Visible',
    sourced: 'Sourced',
    interpretive: 'Interpretive',
    uncertain: 'Uncertain',
};

// ── small helpers ────────────────────────────────────────────────────────────

const arr = (v) => (Array.isArray(v) ? v : []);
const str = (v) => (typeof v === 'string' ? v : '');
/** null and undefined both mean "not known"; 0 and '' are real values and survive. */
const orNull = (v) => (v === undefined ? null : v);

/**
 * A number, or null. NEVER 0-as-a-default.
 *
 * This is the contract's "where a value is genuinely unknown, write null — never fabricate"
 * rule, at the one place it is easiest to break. A missing latency rendered as `0 ms` is a
 * measurement that was never taken, presented as an instant one; a missing confidence rendered
 * as `0` reads as "the model was certain it was wrong". Both are worse than an em dash.
 */
export function numOrNull(v) {
    if (typeof v === 'number' && Number.isFinite(v)) return v;
    return null;
}

// ── RunView ──────────────────────────────────────────────────────────────────

/**
 * Any payload → a RunView this surface can render without further guarding.
 *
 * Unknown `status` is coerced to `pending` rather than dropped: an unrecognised state means this
 * client is older than the server, and treating that as "not finished yet" keeps the poll alive
 * instead of declaring a run complete that is not.
 */
export function normalizeRunView(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    const status = RUN_STATUSES.includes(v.status) ? v.status : 'pending';
    return {
        run_id: str(v.run_id),
        status,
        intention: str(v.intention),
        mode: RUN_MODES.includes(v.mode) ? v.mode : DEFAULT_MODE,
        corpus: arr(v.corpus).map(normalizeCorpusImage),
        rounds: arr(v.rounds),
        question: v.question && typeof v.question === 'object' ? normalizeQuestion(v.question) : null,
        stop_reason: orNull(v.stop_reason) === undefined ? null : (v.stop_reason ?? null),
        weakest_link: numOrNull(v.weakest_link),
        suggestions: arr(v.suggestions),
        production_records: arr(v.production_records).map(normalizeProductionRecord),
        article: v.article && typeof v.article === 'object' ? v.article : null,
    };
}

export function normalizeCorpusImage(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return { post_id: str(v.post_id), image_url: str(v.image_url), title: str(v.title) };
}

/**
 * One executed step's manifest — "the actuator tells, in full detail, what it produced".
 *
 * `refusal` stays null unless it is a real object. A refused step is not an error and not an
 * absence: it is a result, with a reason, and the panel renders it as such.
 */
export function normalizeProductionRecord(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        step_id: str(v.step_id),
        actuator: str(v.actuator),
        params: v.params && typeof v.params === 'object' ? v.params : {},
        model: v.model ?? null,
        adapter: v.adapter ?? null,
        consumed: arr(v.consumed).map(String),
        produced: arr(v.produced).map(normalizeProduced),
        refusal: v.refusal && typeof v.refusal === 'object'
            ? { reason: str(v.refusal.reason), detail: str(v.refusal.detail) }
            : null,
        latency_ms: numOrNull(v.latency_ms),
    };
}

export function normalizeProduced(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        id: str(v.id),
        // `ref` IS NOT DECORATION, and dropping it here was a real defect. The server's own rule
        // (`run_surface._suggestion_ref`): `id` is the descriptor's id where it HAS one and null
        // where it does not, because "a quarantined suggestion is not a stored record and has no
        // id until it is accepted, and minting one here would dress a proposal as a thing." `ref`
        // — `run:step#n` — exists precisely so a reader can point at the item without that
        // becoming a claim about persistence. In a live run nearly every produced item is
        // quarantined, so nearly every `id` normalizes to '' and a UI keyed on it keys every row
        // in a step identically, which React cannot reconcile while the panel is streaming.
        ref: str(v.ref),
        kind: str(v.kind),
        epistemic_status: str(v.epistemic_status),
        confidence: numOrNull(v.confidence),
    };
}

export function normalizeQuestion(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        question_id: str(v.question_id || v.id),
        text: str(v.text || v.question),
        why: str(v.why),
        options: arr(v.options).map((o) =>
            (o && typeof o === 'object')
                ? { value: str(o.value), label: str(o.label || o.value) }
                : { value: String(o), label: String(o) }),
        blocked_step_id: str(v.blocked_step_id),
        param: str(v.param),
    };
}

// ── what the surface asks of the user ────────────────────────────────────────

/**
 * ANNOTATION-INDEPENDENCE, executable.
 *
 * The entire precondition for a run is: something to look at, and something to ask. This
 * function is deliberately the ONLY gate the entry form consults, so no future field can quietly
 * become mandatory — if a check for regions or grounds ever appears in the UI, it will not be
 * here, and the test that pins this will still pass while the form silently disagrees. Hence the
 * companion test asserting a zero-annotation corpus is startable.
 */
export function canStartRun({ imageIds = [], tags = [], prompt = '' } = {}) {
    const hasCorpus = arr(imageIds).length > 0 || arr(tags).length > 0;
    return hasCorpus && str(prompt).trim().length > 0;
}

/** The POST /api/v1/runs body. Omits empty selectors rather than sending `[]`. */
export function startRunBody({ imageIds = [], tags = [], prompt = '', mode = DEFAULT_MODE } = {}) {
    const body = { prompt: str(prompt).trim() };
    if (arr(imageIds).length) body.image_ids = arr(imageIds).map(String);
    if (arr(tags).length) body.tags = arr(tags).map(String);
    body.mode = RUN_MODES.includes(mode) ? mode : DEFAULT_MODE;
    return body;
}

// ── reading a run ────────────────────────────────────────────────────────────

/** Every produced descriptor across every step, flattened, for counting and grouping. */
export function allProduced(view) {
    return arr(view?.production_records).flatMap((r) => arr(r.produced));
}

/** `{ measured: 4, interpretive: 1, … }` — only the statuses actually present. */
export function epistemicCounts(view) {
    const counts = {};
    for (const p of allProduced(view)) {
        const k = p.epistemic_status || 'uncertain';
        counts[k] = (counts[k] || 0) + 1;
    }
    return counts;
}

export function refusedRecords(view) {
    return arr(view?.production_records).filter((r) => r.refusal);
}

/**
 * HONEST EMPTINESS. A run that produced nothing is not a success with an empty list, and this is
 * what the surface asks in order to say so. It returns true only for a FINISHED run — a running
 * one has produced nothing yet, which is not the same claim at all.
 */
export function isHonestlyEmpty(view) {
    if (!view || !IS_TERMINAL(view.status)) return false;
    return allProduced(view).length === 0 && !view.article;
}

/**
 * What a terminal run should say about why it ended. A `stopped` run without a reason is itself
 * a defect worth showing rather than hiding behind a generic label.
 */
export function stopSummary(view) {
    if (!view || !IS_TERMINAL(view.status)) return null;
    if (view.status === 'complete') return { tone: 'complete', text: 'Run complete.' };
    return {
        tone: 'stopped',
        text: view.stop_reason || 'Stopped, and the loop did not say why.',
    };
}
