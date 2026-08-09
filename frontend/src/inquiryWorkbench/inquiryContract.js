/**
 * INQUIRY WORKBENCH — the session contract, as runnable code.
 *
 * HARNESS-002 Lane C's half of the seam pinned in the four-lane board. Lane D will generate the
 * payloads from the backend; this module is the only place that decides what an arbitrary JSON
 * body MEANS to the surface. Nothing here fetches, renders or holds React state, so the contract
 * is asserted in a unit test rather than only observed in a browser.
 *
 * ## Why normalise at all
 *
 * The same reason `agentDemo/runContract.js` gives: the promise is the thing under construction.
 * Lanes A and B are writing these objects in parallel and the first live payload will differ
 * somewhere. Reading through normalisers means that shows up as a missing row rather than a white
 * screen.
 *
 * ## Where this DELIBERATELY diverges from runContract
 *
 * `normalizeRunView` coerces an unrecognised status to `pending`. That is right for a run — an
 * older client should keep polling rather than declare a run finished. It is wrong here, and the
 * directive says so: *unknown fields and statuses are not coerced to successful defaults*. A
 * semantic inquiry carries epistemic claims, and a client that silently rewrites an unfamiliar
 * status into a familiar one is laundering a claim it did not understand.
 *
 * So every enumerated field is normalised into a PAIR: the raw value, kept verbatim, and a
 * `known` boolean saying whether this client recognises it. The UI renders unknown as unknown and
 * shows the raw string. The one thing an unknown value never does is unlock a stronger reading —
 * `SHOULD_KEEP_WATCHING` treats it as not-yet-finished, which is the conservative direction, and
 * no badge, gate or affirmative claim is keyed on a value we could not place.
 */

// ── the session lifecycle ────────────────────────────────────────────────────

export const SESSION_STATES = [
    'framing', 'reading', 'compiling', 'awaiting_user', 'ready', 'executing',
    'judging', 'composing', 'complete', 'exhausted', 'refused', 'error',
];

export const TERMINAL_STATES = ['complete', 'exhausted', 'refused', 'error'];

export const IS_TERMINAL_STATE = (state) => TERMINAL_STATES.includes(state);
export const IS_AWAITING_USER = (state) => state === 'awaiting_user';

/**
 * Keep reading the session? True for every state that is not KNOWN to be finished and not
 * blocked on a person — INCLUDING an unrecognised one. An unknown state means this client is
 * older than the server, and "not finished yet" is the only reading of it that cannot lose work.
 */
export const SHOULD_KEEP_WATCHING = (state) =>
    !IS_TERMINAL_STATE(state) && !IS_AWAITING_USER(state);

export const STATE_LABEL = {
    framing: 'Framing the question',
    reading: 'Reading the images',
    compiling: 'Compiling claims',
    awaiting_user: 'Waiting on you',
    ready: 'Ready to investigate',
    executing: 'Running a capability',
    judging: 'Judging what came back',
    composing: 'Composing the answer',
    complete: 'Complete',
    exhausted: 'Exhausted',
    refused: 'Refused',
    error: 'Error',
};

export const INTERACTION_MODES = ['auto', 'consult', 'step'];
export const DEFAULT_MODE = 'consult';

export const MODE_COPY = {
    auto: {
        title: 'Auto',
        hint: 'Semant chooses the reversible forks itself. It still records every choice, and it '
            + 'still stops before anything would be accepted into the shared record.',
    },
    consult: {
        title: 'Consult',
        hint: 'Semant pauses only where two readings would send the inquiry somewhere genuinely '
            + 'different, or where something is about to be accepted.',
    },
    step: {
        title: 'Step',
        hint: 'Pause at every major transition. Slow, and meant for watching the machinery rather '
            + 'than for getting an answer.',
    },
};

// ── the claim grammar (plan §3) ──────────────────────────────────────────────
//
// Stable FORMS, open vocabulary. The subjects and predicates stay open strings — there is no
// topic branch here and there must never be one.
export const CLAIM_KINDS = [
    'entity', 'attribute', 'spatial_relation', 'topology', 'pattern_or_sequence', 'field',
    'hierarchy', 'comparison', 'historical_or_sourced', 'causal_hypothesis', 'interpretation',
    'generative_rule', 'unknown',
];

/**
 * How a claim is held, strongest first. `measured` and `visible` are the two the surface may
 * never mint: they arrive attached to a backend evidence object or they do not appear.
 */
export const CLAIM_STATUSES = [
    'measured', 'visible', 'sourced', 'interpretive', 'imagined', 'proposed', 'unresolved',
];

/** The statuses that assert something was actually found in the pixels or the record. */
export const FINDING_STATUSES = ['measured', 'visible'];

export const STATUS_COPY = {
    measured: 'computed from the image signal',
    visible: 'present in the image and pointed at',
    sourced: 'attributed to a source outside the image',
    interpretive: 'a reading about the images, not a measurement of them',
    imagined: 'proposed rather than found',
    proposed: 'put forward by the compiler; nothing has tested it',
    unresolved: 'nothing settled this either way',
};

// ── capability outcomes ──────────────────────────────────────────────────────
//
// Six things that all look like "no result" on a careless surface and mean six different things.
// Keeping them apart is most of this lane's job.
export const CAPABILITY_OUTCOMES = [
    'live', 'simulated', 'empty', 'unavailable', 'refused', 'capability_gap',
];

export const OUTCOME_COPY = {
    live: 'The instrument ran and returned something.',
    simulated: 'A stand-in produced this shape so the flow could be checked. Nothing was measured.',
    empty: 'The instrument ran and returned nothing.',
    unavailable: 'The capability was not available, so nothing was attempted.',
    refused: 'The request was refused, and the reason is recorded.',
    capability_gap: 'Nothing in Semant can currently make this observable.',
};

export const EXECUTION_MODES = ['fixture', 'live'];

// ── decisions ────────────────────────────────────────────────────────────────

export const DECISION_KINDS = [
    'choose_operationalization', 'choose_scope', 'resolve_ambiguity', 'authorial_action',
    'review_evidence', 'choose_direction',
];

export const DECISION_ACTIONS = ['select', 'reject', 'skip', 'redirect', 'amend'];

/** Who made a recorded choice. `system` covers auto mode: no interruption is not no agency. */
export const DECIDER_KINDS = ['user', 'system', 'model'];

// ── small helpers ────────────────────────────────────────────────────────────

const arr = (v) => (Array.isArray(v) ? v : []);
const str = (v) => (typeof v === 'string' ? v : '');
const bool = (v) => v === true;

/** A number, or null. Never 0-as-a-default — a missing revision is not revision zero. */
export function numOrNull(v) {
    if (typeof v === 'number' && Number.isFinite(v)) return v;
    return null;
}

/**
 * A tri-state boolean. `true`, `false`, and null for "the backend did not say".
 *
 * Used for `usable_as_evidence`, where the difference matters: a missing field is not a promise
 * that the payload is usable, and it is not a claim that it is not. Every gate in this surface
 * tests `=== true`, so null and false both fail closed while still rendering differently.
 */
export function boolOrNull(v) {
    if (v === true || v === false) return v;
    return null;
}

/**
 * `{value, known}` for an enumerated field: the raw string kept verbatim, plus whether this
 * client recognises it. Nothing is rewritten and nothing is dropped.
 */
export function enumField(v, allowed) {
    const value = str(v);
    return { value, known: allowed.includes(value) };
}

const ISO = (v) => (typeof v === 'string' && v ? v : null);

// ── the semantic inquiry graph ───────────────────────────────────────────────

export function normalizeImageRef(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        post_id: str(v.post_id),
        title: str(v.title),
        image_ref: str(v.image_ref),
        image_url: str(v.image_url),
    };
}

/**
 * The ceiling on a scene reading's status (plan §2: *interpretive at strongest*).
 *
 * A reading arriving with `measured` on it is not a stronger reading; it is a bug upstream, and
 * rendering it faithfully would put the surface's most persuasive paragraph under the surface's
 * strongest badge. It is capped — and the cap is SHOWN, because silently downgrading would hide
 * the upstream defect just as effectively as silently promoting would hide the epistemic one.
 */
const READING_CEILING = ['interpretive', 'imagined', 'uncertain', 'unresolved'];

export function normalizeReading(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    const declared = str(v.status);
    const overreach = Boolean(declared) && !READING_CEILING.includes(declared);
    return {
        text: str(v.text),
        status: overreach ? 'interpretive' : (declared || 'interpretive'),
        capped_from: overreach ? declared : null,
        source: str(v.source),
        model: str(v.model),
        provenance: v.provenance && typeof v.provenance === 'object' ? v.provenance : {},
    };
}

export function normalizeClaim(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        claim_id: str(v.claim_id || v.id),
        text: str(v.text),
        kind: enumField(v.claim_kind ?? v.kind, CLAIM_KINDS),
        status: enumField(v.status, CLAIM_STATUSES),
        subject: str(v.subject),
        predicate: str(v.predicate),
        object: str(v.object),
        // "exact source pointers" — the span of the prompt or the reading this came from.
        source_span: v.source_span && typeof v.source_span === 'object'
            ? {
                origin: str(v.source_span.origin),
                text: str(v.source_span.text),
                start: numOrNull(v.source_span.start),
                end: numOrNull(v.source_span.end),
            }
            : null,
        image_scope: arr(v.image_scope).map(String),
        epistemic_demand: str(v.epistemic_demand),
        confidence: numOrNull(v.confidence),
        author: enumField(v.author, DECIDER_KINDS),
    };
}

export function normalizeClaimEdge(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        edge_id: str(v.edge_id || v.id),
        from_claim: str(v.from_claim || v.from),
        to_claim: str(v.to_claim || v.to),
        relation: str(v.relation),
        note: str(v.note),
    };
}

/**
 * An observable REQUEST. It asks for a capability class and a ground form; it never carries a
 * result. That separation is the operationalizer's whole discipline (plan §4), and this
 * normaliser enforces it by having nowhere to put one.
 */
export function normalizeObservable(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        observable_id: str(v.observable_id || v.id),
        claim_ref: str(v.claim_ref || v.claim_id),
        observable_kind: str(v.observable_kind || v.kind),
        target: str(v.target),
        image_scope: arr(v.image_scope).map(String),
        ground_forms: arr(v.ground_forms).map(String),
        capability_classes: arr(v.capability_classes).map(String),
        alternatives: arr(v.alternatives).map(normalizeAlternative),
        success_condition: str(v.success_condition),
        ambiguity_condition: str(v.ambiguity_condition),
        refusal_condition: str(v.refusal_condition),
        // "what would remain interpretive even if every requested measurement succeeded"
        residual_interpretation: str(v.residual_interpretation),
        availability: enumField(v.availability, ['available', 'unavailable', 'capability_gap']),
        gap_reason: str(v.gap_reason),
    };
}

export function normalizeAlternative(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        alternative_id: str(v.alternative_id || v.id),
        label: str(v.label),
        capability_class: str(v.capability_class),
        consequence: str(v.consequence),
        available: boolOrNull(v.available),
    };
}

export function normalizeRemainder(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        remainder_id: str(v.remainder_id || v.id),
        text: str(v.text),
        why_unresolved: str(v.why_unresolved),
        claim_refs: arr(v.claim_refs).map(String),
    };
}

export function normalizeRefusal(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        refusal_id: str(v.refusal_id || v.id),
        reason: str(v.reason),
        detail: str(v.detail),
        refs: arr(v.refs).map(String),
    };
}

export function normalizeGraph(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        schema_version: str(v.schema_version),
        graph_id: str(v.graph_id),
        inquiry_id: str(v.inquiry_id),
        // BYTE-IDENTICAL. Never trimmed, never re-cased: the compiler's source spans index into
        // this exact string, and a surface that tidied it would misalign every excerpt.
        prompt: str(v.prompt),
        image_refs: arr(v.image_refs).map(normalizeImageRef),
        reading: normalizeReading(v.reading),
        claims: arr(v.claims).map(normalizeClaim),
        claim_edges: arr(v.claim_edges).map(normalizeClaimEdge),
        observables: arr(v.observables).map(normalizeObservable),
        semantic_remainder: arr(v.semantic_remainder).map(normalizeRemainder),
        refusals: arr(v.refusals).map(normalizeRefusal),
        provenance: v.provenance && typeof v.provenance === 'object' ? v.provenance : {},
    };
}

// ── decisions ────────────────────────────────────────────────────────────────

export function normalizeDecisionOption(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        option_id: str(v.option_id || v.id),
        label: str(v.label),
        consequence: str(v.consequence),
        recommended: bool(v.recommended),
    };
}

export function normalizeDecisionRequest(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        decision_id: str(v.decision_id || v.id),
        session_id: str(v.session_id),
        kind: enumField(v.kind, DECISION_KINDS),
        question: str(v.question),
        why_now: str(v.why_now),
        affected_refs: arr(v.affected_refs).map(String),
        options: arr(v.options).map(normalizeDecisionOption),
        allow_free_text: bool(v.allow_free_text),
        blocking: bool(v.blocking),
        answered: bool(v.answered),
        provenance: v.provenance && typeof v.provenance === 'object' ? v.provenance : {},
    };
}

/**
 * One choice that was actually made — by a person OR by the system in auto mode.
 *
 * Both live in the same list and the same chronology, which is the board's rule made structural:
 * auto mode means no interruption, not invisible agency. A record whose decider is `system` is
 * rendered in the stream exactly as prominently as one a person made.
 */
export function normalizeDecisionRecord(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        record_id: str(v.record_id || v.id),
        decision_id: str(v.decision_id),
        decider: enumField(v.decider, DECIDER_KINDS),
        action: enumField(v.action, DECISION_ACTIONS),
        question: str(v.question),
        selected_option_id: str(v.selected_option_id),
        selected_label: str(v.selected_label),
        free_text: str(v.free_text),
        rationale: str(v.rationale),
        affected_refs: arr(v.affected_refs).map(String),
        at: ISO(v.at),
        revision: numOrNull(v.revision),
    };
}

// ── capability receipts ──────────────────────────────────────────────────────

/**
 * What a capability request came back as.
 *
 * DERIVED here rather than trusted, and derived conservatively: a fixture execution mode is
 * `simulated` whatever the backend called the status. That is the one place this module overrides
 * a supplied value, and it only ever moves in the direction of the weaker claim.
 */
export function receiptOutcome(receipt) {
    if (receipt.execution_mode.value === 'fixture') return 'simulated';
    const status = receipt.status.value;
    if (CAPABILITY_OUTCOMES.includes(status)) return status;
    return 'unknown';
}

export function normalizeReceipt(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    const receipt = {
        receipt_id: str(v.receipt_id || v.id),
        request_ref: str(v.request_ref),
        capability: str(v.capability),
        execution_mode: enumField(v.execution_mode, EXECUTION_MODES),
        status: enumField(v.status, CAPABILITY_OUTCOMES),
        // Never defaulted true. A missing field is not permission.
        usable_as_evidence: boolOrNull(v.usable_as_evidence),
        attempted: boolOrNull(v.attempted),
        payload: v.payload && typeof v.payload === 'object' ? v.payload : {},
        detail: str(v.detail),
        latency_ms: numOrNull(v.latency_ms),
        provenance: v.provenance && typeof v.provenance === 'object' ? v.provenance : {},
    };
    receipt.outcome = receiptOutcome(receipt);
    receipt.simulated = receipt.execution_mode.value === 'fixture'
        || receipt.status.value === 'simulated';
    return receipt;
}

/**
 * May this object's payload be shown as EVIDENCE?
 *
 * `simulated` disqualifies regardless of what the flag says: a fixture receipt that arrived with
 * `usable_as_evidence: true` is an upstream defect, and the defect must not be honoured by the
 * surface that exists to catch it.
 *
 * An execution mode this client cannot PLACE also disqualifies, and the distinction matters —
 * absent is not the same as unrecognised. An absent mode leaves the question to
 * `usable_as_evidence`; a mode we have never seen answers it no, because vouching for a mode we
 * do not understand is exactly the coercion-to-a-successful-default the contract forbids.
 */
export function isEvidenceGrade(obj) {
    if (!obj) return false;
    if (obj.simulated) return false;
    const mode = obj.execution_mode;
    if (mode && mode.value && !mode.known) return false;
    if (mode && mode.value === 'fixture') return false;
    return obj.usable_as_evidence === true;
}

// ── evidence and verdicts ────────────────────────────────────────────────────

export const VERDICT_OUTCOMES = ['supports', 'complicates', 'refutes', 'inconclusive'];

export function normalizeEvidence(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    const ev = {
        evidence_id: str(v.evidence_id || v.id),
        claim_refs: arr(v.claim_refs).map(String),
        observable_ref: str(v.observable_ref),
        receipt_ref: str(v.receipt_ref),
        kind: str(v.kind),
        epistemic_status: enumField(v.epistemic_status, CLAIM_STATUSES),
        summary: str(v.summary),
        usable_as_evidence: boolOrNull(v.usable_as_evidence),
        execution_mode: enumField(v.execution_mode, EXECUTION_MODES),
        verdict: v.verdict && typeof v.verdict === 'object'
            ? {
                verdict_id: str(v.verdict.verdict_id || v.verdict.id),
                outcome: enumField(v.verdict.outcome, VERDICT_OUTCOMES),
                note: str(v.verdict.note),
            }
            : null,
        provenance: v.provenance && typeof v.provenance === 'object' ? v.provenance : {},
    };
    ev.simulated = ev.execution_mode.value === 'fixture';
    return ev;
}

// ── synthesis ────────────────────────────────────────────────────────────────

export function normalizeSynthesisSection(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        section_id: str(v.section_id || v.id),
        heading: str(v.heading),
        text: str(v.text),
        claim_refs: arr(v.claim_refs).map(String),
        evidence_refs: arr(v.evidence_refs).map(String),
        refusal_refs: arr(v.refusal_refs).map(String),
        status: enumField(v.status, CLAIM_STATUSES),
        user_authored: bool(v.user_authored),
    };
}

export function normalizeSynthesis(raw) {
    if (!raw || typeof raw !== 'object') return null;
    return {
        synthesis_id: str(raw.synthesis_id || raw.id),
        sections: arr(raw.sections).map(normalizeSynthesisSection),
        note: str(raw.note),
    };
}

// ── trace ────────────────────────────────────────────────────────────────────

export function normalizeTraceEvent(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        event_id: str(v.event_id || v.id),
        at: ISO(v.at),
        actor: str(v.actor),
        actor_kind: enumField(v.actor_kind, DECIDER_KINDS),
        transition: str(v.transition),
        reason: str(v.reason),
        refs: arr(v.refs).map(String),
        revision: numOrNull(v.revision),
    };
}

// ── the session ──────────────────────────────────────────────────────────────

export function normalizeSession(raw) {
    const v = raw && typeof raw === 'object' ? raw : {};
    return {
        schema_version: str(v.schema_version),
        session_id: str(v.session_id),
        inquiry_id: str(v.inquiry_id),
        // The optimistic-concurrency token. Null rather than 0 when absent: sending 0 as an
        // expected revision would be asserting a version the server never issued.
        revision: numOrNull(v.revision),
        state: enumField(v.state, SESSION_STATES),
        mode: enumField(v.mode, INTERACTION_MODES),
        graph: normalizeGraph(v.graph),
        decision_requests: arr(v.decision_requests).map(normalizeDecisionRequest),
        decision_records: arr(v.decision_records).map(normalizeDecisionRecord),
        capability_receipts: arr(v.capability_receipts).map(normalizeReceipt),
        evidence: arr(v.evidence).map(normalizeEvidence),
        synthesis: normalizeSynthesis(v.synthesis),
        trace: arr(v.trace).map(normalizeTraceEvent),
        error: str(v.error),
    };
}

// ── reading a session ────────────────────────────────────────────────────────

/** The first open decision — or null. */
export function openDecision(session) {
    if (!session) return null;
    return session.decision_requests.find((d) => !d.answered) || null;
}

export function claimById(session, claimId) {
    if (!session) return null;
    return session.graph.claims.find((c) => c.claim_id === claimId) || null;
}

export function observablesForClaim(session, claimId) {
    if (!session) return [];
    return session.graph.observables.filter((o) => o.claim_ref === claimId);
}

export function evidenceForClaim(session, claimId) {
    if (!session) return [];
    return session.evidence.filter((e) => e.claim_refs.includes(claimId));
}

/**
 * Evidence a claim may be presented as SUPPORTED by. Simulated and non-usable objects are
 * excluded here rather than at each render site, so no component has to remember the rule.
 */
export function supportingEvidence(session, claimId) {
    return evidenceForClaim(session, claimId).filter(isEvidenceGrade);
}

/** `{simulated: 1, empty: 2, …}` — only the outcomes actually present. */
export function outcomeCounts(session) {
    const counts = {};
    for (const r of (session?.capability_receipts || [])) {
        counts[r.outcome] = (counts[r.outcome] || 0) + 1;
    }
    return counts;
}

/**
 * Has anything on this session been measured?
 *
 * Asked of the EVIDENCE objects only. A receipt cannot answer it however confident its payload
 * looks, which is the executable form of "do not count fixture payload as evidence".
 */
export function hasMeasuredEvidence(session) {
    return (session?.evidence || []).some(
        (e) => isEvidenceGrade(e) && FINDING_STATUSES.includes(e.epistemic_status.value));
}

// ── what the surface asks of the user ────────────────────────────────────────

/**
 * The whole precondition for an inquiry: images, and a question. Deliberately the only gate the
 * entry form consults, for the same reason `canStartRun` is — so no future field can quietly
 * become mandatory without this function being the place it happens.
 */
export function canStartInquiry({ imageIds = [], prompt = '' } = {}) {
    return arr(imageIds).length > 0 && str(prompt).trim().length > 0;
}

export function startInquiryBody({ imageIds = [], prompt = '', mode = DEFAULT_MODE } = {}) {
    return {
        prompt: str(prompt).trim(),
        image_ids: arr(imageIds).map(String),
        mode: INTERACTION_MODES.includes(mode) ? mode : DEFAULT_MODE,
    };
}

/**
 * The POST body for a decision response.
 *
 * `expected_revision` is always sent when known: the server rejects a response written against a
 * session that has since moved, and a 409 is a far better outcome than a decision silently
 * applied to a graph the person never saw.
 */
export function decisionResponseBody({
    decisionId = '', responseId = '', optionId = '', freeText = '',
    action = 'select', expectedRevision = null,
} = {}) {
    const body = {
        decision_id: str(decisionId),
        response_id: str(responseId),
        action: DECISION_ACTIONS.includes(action) ? action : 'select',
    };
    if (str(optionId)) body.selected_option_id = str(optionId);
    if (str(freeText).trim()) body.free_text = str(freeText).trim();
    if (numOrNull(expectedRevision) !== null) body.expected_revision = expectedRevision;
    return body;
}
