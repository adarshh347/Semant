// CIRCUIT-001 P2E — the action ↔ visual_mark ↔ manuscript bridge.
//
// Synthesis, not new truth. Lane A (P2D-A) built the visual_mark model and the
// quarantine; Lane B (P2C-MS2) built the Manuscript circulation actions. This
// module is the thin, PURE seam where an armed action becomes a draft mark, and
// where a mark becomes something the Manuscript can show honestly.
//
// It invents no vocabulary and stores nothing. Every rule it needs already lives
// in visualMarks.js / suggestionQuarantine.js; this module only composes them so
// a caller never has to remember the order (quarantine a suggestion, derive
// citability, surface provenance) — getting that order wrong is exactly how a
// suggestion launders itself into evidence.

import { actionToDraftMark, markSummary, roleLabel } from './visualMarks';
import {
    quarantineSuggestion, summarizeProvenance, canCiteMark, isSuggestion,
} from './suggestionQuarantine';

const STATUS_LABEL = {
    draft: 'Draft mark',
    staged: 'Staged mark',
    suggested: 'Suggested mark',
    previewed: 'Previewed',
    committed: 'Committed',
    dismissed: 'Dismissed',
    superseded: 'Superseded',
    blocked: 'Blocked',
};

/**
 * An armed/staged P2B action → a DRAFT visual_mark, or null.
 *
 * The geometry is `unresolved`: the planner never touches the image, so the mark
 * arrives with a role and no shape — the curator's hand supplies the geometry
 * (P2B "arming is not drawing"). A model-authored action is put through the
 * quarantine here, at the bridge, so a suggested mark can never be constructed
 * outside it. Fails closed: an action whose family makes no mark returns null,
 * never a partial (same discipline as `normalizeMark`).
 */
export function draftMarkFromAction(action, { now = null, idFn } = {}) {
    const mark = actionToDraftMark(action, { now, idFn });
    if (!mark) return null;
    return mark.source === 'model_suggested' ? quarantineSuggestion(mark, { now }) : mark;
}

/**
 * A display descriptor for a mark — the single shape both Differential (armed
 * strip, ground chip) and the Manuscript (PassageInspector) render from, so the
 * two surfaces cannot describe the same mark differently.
 *
 * `citable` is DERIVED via `canCiteMark`, never read off a stored flag: a
 * suggestion, a draft, or a mark with no geometry is not citable, and the
 * descriptor says so out loud rather than leaving a surface to guess.
 */
export function markDisplay(mark) {
    if (!mark) return null;
    return {
        id: mark.id,
        type: mark.type,
        role: mark.role,
        role_label: roleLabel(mark.type, mark.role),
        summary: markSummary(mark),
        status: mark.status,
        status_label: STATUS_LABEL[mark.status] || mark.status,
        // The CVAT lesson: a provenance nobody can see is no provenance. Always a
        // short, visible, number-free label.
        provenance: summarizeProvenance(mark),
        citable: canCiteMark(mark),
        is_suggestion: isSuggestion(mark),
        derived_from: mark.derived_from || null,
        // 'unresolved' → the role exists, the shape does not yet. "Ready for your mark."
        needs_geometry: mark.geometry?.kind === 'unresolved',
        linked_action_ids: [...(mark.linked_action_ids || [])],
        // Session-only in this gate: there is no marks backend (P2D-A §7.3). A
        // surface must say "not saved" and must not pretend it survives reload.
        session: true,
    };
}

/**
 * The marks that stand behind a percept: those linked directly to it, or to any
 * ground it cites. A committed field/trace mark rides on a ground; the percept
 * cites the ground; so this is how the Manuscript reaches the instrument that
 * produced the evidence it is writing about — without inventing a new link.
 */
export function marksForPercept(percept, marks = []) {
    if (!percept?.id) return [];
    const gids = new Set(percept.ground_ids || []);
    return (marks || []).filter((m) => (
        (m.linked_percept_ids || []).includes(percept.id)
        || (m.linked_ground_ids || []).some((g) => gids.has(g))
    ));
}

/** One quiet line summarising a percept's marks for a collapsed view. */
export function marksSummary(marks = []) {
    if (!marks.length) return '';
    const citable = marks.filter(canCiteMark).length;
    const n = marks.length;
    const head = `${n} session mark${n === 1 ? '' : 's'}`;
    return citable === n ? head : `${head} · ${n - citable} not citable`;
}
