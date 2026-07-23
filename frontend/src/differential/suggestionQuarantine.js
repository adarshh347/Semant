// CIRCUIT-001 P2D-A — suggestion quarantine + provenance lineage.
//
// Implements `CIRCUIT-001-P2D-interface-contract.md` §4. This is the load-bearing module of
// the gate: it is where "the model may suggest; the human decides" stops being a slogan and
// becomes an invariant the code enforces.
//
// The two ideas, harvested in P2C:
//
//  1. Label Studio's `parent_prediction` — acceptance MINTS A NEW MARK pointing back at the
//     suggestion; the suggestion is preserved untouched. `user_confirmed` becomes a DERIVED
//     fact (a mark whose derived_from resolves to a suggestion), not a flag someone had to
//     remember to set.
//
//  2. CVAT's negative lesson — a provenance field nobody can see is no provenance at all.
//     `summarizeProvenance` exists so every mark can SAY what it is, in the UI, out loud.
//
// Pure; no renderer, no store, no clock it does not accept.

import { makeVisualMark, normalizeMark, validateMark } from './visualMarks';

// ── reading provenance ───────────────────────────────────────────────────────

/** A quarantined mark: a model proposed it and no human has accepted it yet. */
export function isSuggestion(mark) {
    if (!mark) return false;
    return mark.source === 'model_suggested'
        || mark.status === 'suggested'
        || mark.status === 'previewed';
}

/**
 * THE citability rule, and the only place it lives (contract §1). Derived, never stored.
 *
 * A mark may be cited by a percept iff it is committed, its source is the curator's own or
 * confirmed by them, and it actually has geometry. Every clause is a real gate:
 *   - not committed        → still in flight; citing it cites a draft
 *   - model_suggested/etc. → the quarantine; citing it launders a suggestion into evidence
 *   - unresolved geometry  → a role with no shape; citing it cites nothing
 *
 * `model_refined` is deliberately NOT citable on its own: the human drew it and a model
 * tightened it, but "tightened" is not "confirmed". It becomes citable only once its status
 * is committed by a curator action AND its source has been carried to user_confirmed. Until
 * then it is honest about being half the model's.
 */
export function canCiteMark(mark) {
    if (!mark) return false;
    if (mark.status !== 'committed') return false;
    if (!(mark.source === 'user' || mark.source === 'user_confirmed')) return false;
    if (mark.geometry?.kind === 'unresolved') return false;
    return true;
}

/**
 * Put a mark into quarantine. Idempotent. Forces `source: model_suggested`, `status:
 * suggested`, and strips any citability the caller might have set — a suggestion arrives
 * with no way to be mistaken for evidence, regardless of how it was constructed.
 */
export function quarantineSuggestion(mark, { now = null } = {}) {
    if (!mark) return null;
    const ts = now ?? new Date().toISOString();
    return {
        ...mark,
        source: 'model_suggested',
        status: 'suggested',
        updated_at: ts,
        warnings: [...new Set([...(mark.warnings || []), 'Suggested by a model — not evidence until you accept it.'])],
    };
}

// ── the transitions — each MINTS, none overwrites ────────────────────────────

/**
 * Accept a suggestion. Mints a NEW mark, `source: user_confirmed`, `derived_from` the
 * suggestion's id, `status: committed`. The suggestion is returned UNCHANGED — its
 * provenance is preserved so the lineage stays legible (contract §4.2).
 *
 * `edits` may carry curator corrections (label, geometry, style). A geometry edit at
 * acceptance means the human did not merely accept but reshaped — that is `model_refined`,
 * and the source reflects it.
 *
 * @returns {{ accepted: mark, suggestion: mark } | null}
 */
export function acceptSuggestion(suggestion, edits = {}, { now = null, idFn } = {}) {
    if (!isSuggestion(suggestion)) return null;
    const ts = now ?? new Date().toISOString();
    const reshaped = edits.geometry && edits.geometry.kind
        && edits.geometry.kind !== suggestion.geometry?.kind;
    const accepted = normalizeMark({
        type: suggestion.type,
        role: edits.role ?? suggestion.role,
        label: edits.label ?? suggestion.label,
        source: reshaped ? 'model_refined' : 'user_confirmed',
        status: 'committed',
        geometry: edits.geometry ?? suggestion.geometry,
        style: { ...(suggestion.style || {}), ...(edits.style || {}) },
        linked_ground_ids: edits.linked_ground_ids ?? suggestion.linked_ground_ids,
        linked_percept_ids: edits.linked_percept_ids ?? suggestion.linked_percept_ids,
        linked_action_ids: suggestion.linked_action_ids,
        derived_from: suggestion.id,
        // The model's authorship travels forward in provenance even though the source is now
        // the human's — so "who first proposed this" survives acceptance.
        provenance: { ...(suggestion.provenance || {}), model: suggestion.provenance?.model ?? null },
        created_at: ts,
        updated_at: ts,
    }, { now: ts, idFn });
    if (!accepted) return null;
    return { accepted, suggestion };   // suggestion returned as-is, untouched
}

/**
 * Dismiss a suggestion. Marks it `dismissed`; keeps it (nothing is destroyed here). A
 * dismissed suggestion is not citable, not counted, and not offered again — but it remains
 * in the record so "the model proposed this and I said no" is answerable.
 */
export function dismissSuggestion(suggestion, { now = null } = {}) {
    if (!suggestion) return null;
    const ts = now ?? new Date().toISOString();
    return { ...suggestion, status: 'dismissed', updated_at: ts };
}

/**
 * Supersede a committed mark with a replacement. The OLD mark becomes `superseded` and is
 * KEPT; the replacement carries `derived_from` the old id. Silent replacement is precisely
 * how a citation re-points onto different geometry without anyone noticing (P1F/P1G), so the
 * superseded mark stays recoverable and the lineage is explicit.
 *
 * @returns {{ replacement: mark, superseded: mark } | null}
 */
export function supersedeSuggestion(oldMark, replacement, { now = null, idFn } = {}) {
    if (!oldMark || !replacement) return null;
    const ts = now ?? new Date().toISOString();
    const superseded = { ...oldMark, status: 'superseded', updated_at: ts };
    const next = normalizeMark({
        ...replacement,
        derived_from: replacement.derived_from ?? oldMark.id,
        created_at: replacement.created_at || ts,
        updated_at: ts,
    }, { now: ts, idFn });
    if (!next) return null;
    return { replacement: next, superseded };
}

/**
 * Convenience: given a suggestion, produce the user-confirmed mark alone (no wrapper). Used
 * where a caller wants just the new mark and will keep the suggestion itself elsewhere.
 */
export function deriveUserConfirmedMark(suggestion, edits = {}, opts = {}) {
    const out = acceptSuggestion(suggestion, edits, opts);
    return out ? out.accepted : null;
}

// ── lineage + surfacing ──────────────────────────────────────────────────────

/**
 * Walk `derived_from` back to the origin. Returns the chain oldest→newest (the given mark
 * last). Cycle-guarded. Lets a surface answer "what did the human change about this?" by
 * diffing adjacent links.
 */
export function getSuggestionLineage(mark, allMarks = []) {
    const byId = Object.fromEntries((allMarks || []).map((m) => [m.id, m]));
    const chain = [];
    const seen = new Set();
    let cur = mark;
    while (cur && !seen.has(cur.id)) {
        seen.add(cur.id);
        chain.unshift(cur);
        cur = cur.derived_from ? byId[cur.derived_from] : null;
    }
    return chain;
}

/**
 * A short, VISIBLE provenance label — the whole point of the CVAT lesson. Never technical,
 * never a confidence number, always honest about the model's part.
 */
export function summarizeProvenance(mark) {
    if (!mark) return '';
    switch (mark.source) {
        case 'model_suggested': return 'Model suggestion — not accepted';
        case 'user_confirmed': return 'Model proposed · you accepted';
        case 'model_refined': return 'You drew · model tightened';
        case 'imported': return 'Imported';
        case 'system': return 'System';
        case 'fixture': return 'Fixture';
        case 'user':
        default: return 'Yours';
    }
}

/** True when a mark carries any model involvement, however small. Drives the chip's presence. */
export const hasModelInvolvement = (mark) =>
    !!mark && ['model_suggested', 'user_confirmed', 'model_refined'].includes(mark.source);

/**
 * Count marks the way an evidence total must: suggestions and non-committed marks do NOT
 * count. Exposed so a UI cannot accidentally include a suggestion in "3 grounds".
 */
export function countEvidence(marks = []) {
    return (marks || []).filter((m) => m.status === 'committed' && !isSuggestion(m)).length;
}

// ── provenance bridge (contract v2 §7.2-E) ───────────────────────────────────
// The mark is the ONLY authored provenance. A ground or region that carries `mark_source`
// / `instrument_role` / `refined_from` holds them as DERIVED bridge fields — a convenience
// view for a surface that has the ground but not the mark. These helpers are the only
// sanctioned writers of those fields, and they read exclusively from the mark, so a bridge
// field can never say something the mark does not.

/** The bridge fields a mark projects onto the ground/region it is linked to. */
export function bridgeFieldsFromMark(mark) {
    if (!mark) return { mark_id: null, mark_source: null, instrument_role: null, refined_from: null };
    return {
        mark_id: mark.id,
        mark_source: mark.source,
        instrument_role: mark.role ?? null,
        refined_from: mark.derived_from ?? null,
    };
}

/**
 * Given a ground/region and the marks that reference it, return the object with its bridge
 * fields rewritten FROM the mark. The most recently updated linked mark wins (a supersession
 * makes the newer mark the truth). Returns the input unchanged when no mark links to it — a
 * ground with no mark has no derived provenance to assert.
 */
export function reconcileBridgeFields(target, marks = []) {
    if (!target) return target;
    const linked = (marks || [])
        .filter((m) => (m.linked_ground_ids || []).includes(target.id))
        .sort((a, b) => String(a.updated_at || '').localeCompare(String(b.updated_at || '')));
    const mark = linked[linked.length - 1];
    if (!mark) return target;
    return { ...target, ...bridgeFieldsFromMark(mark) };
}

/**
 * Does a target's stored bridge fields agree with its linked mark? The drift check made
 * runnable — a surface (or a test) can assert this and know a bridge field never lies.
 * Returns true when there is no linked mark (nothing to disagree with).
 */
export function bridgeFieldsAgree(target, marks = []) {
    if (!target) return true;
    const reconciled = reconcileBridgeFields(target, marks);
    if (reconciled === target) return true;
    for (const k of ['mark_id', 'mark_source', 'instrument_role', 'refined_from']) {
        const want = reconciled[k] ?? null;
        const have = target[k] ?? null;
        if (want !== have) return false;
    }
    return true;
}

// ── producer intake (CIRCUIT-001 P4-A) ───────────────────────────────────────
// Real model output enters the circuit HERE, and only as a quarantined suggestion. A backend
// producer (SAM refine / semantic read) emits a `suggestion descriptor` — a plain JSON shape,
// contract v3 §8.4 — and these helpers turn it into a `model_suggested` mark, fail-closed. A
// descriptor that does not validate is dropped, never rendered as a partial (the same discipline
// as normalizeMark). Nothing here persists: a suggestion's status keeps it out of the database.

/**
 * A STABLE identity for a suggestion: `producer:type:source_ref`. Re-running a producer over the
 * same source (same region / same candidate) yields the same key — the basis of idempotent
 * intake (a re-run replaces, never duplicates).
 */
export function suggestionKey(descriptor) {
    const d = descriptor || {};
    return `${d.producer || '?'}:${d.type || '?'}:${d.source_ref ?? '?'}`;
}

/** The deterministic mark id for a descriptor — so re-ingest lands on the SAME mark id. */
export function suggestionId(descriptor) {
    return `vm_sug_${suggestionKey(descriptor).replace(/[^a-zA-Z0-9]+/g, '_')}`;
}

/**
 * One descriptor → one quarantined `model_suggested` mark, or **null** (fail-closed). The id is
 * deterministic (`suggestionId`) so a second ingest of the same descriptor replaces rather than
 * duplicates. The producer's provenance rides through unchanged — its receipt (model + run_id +
 * producer) is exactly what makes the suggestion honest.
 */
export function suggestionFromDescriptor(descriptor, { now = null } = {}) {
    if (!descriptor || typeof descriptor !== 'object') return null;
    const id = suggestionId(descriptor);
    const mark = normalizeMark({
        id,
        type: descriptor.type,
        role: descriptor.role ?? null,
        label: typeof descriptor.label === 'string' ? descriptor.label : '',
        source: 'model_suggested',
        status: 'suggested',
        geometry: descriptor.geometry,
        linked_ground_ids: Array.isArray(descriptor.linked_ground_ids) ? descriptor.linked_ground_ids : [],
        provenance: descriptor.provenance || {},
    }, { now, idFn: () => id });
    if (!mark) return null;
    // Belt and braces: force the quarantine flags even if a descriptor arrived mislabelled.
    return quarantineSuggestion(mark, { now });
}

/** A list of descriptors → the valid suggestion marks (invalid dropped). Order preserved. */
export function suggestionsFromDescriptors(descriptors = [], opts = {}) {
    return (Array.isArray(descriptors) ? descriptors : [])
        .map((d) => suggestionFromDescriptor(d, opts))
        .filter(Boolean);
}

// Re-exported so a quarantine consumer has the constructors without a second import.
export { makeVisualMark, normalizeMark, validateMark };
