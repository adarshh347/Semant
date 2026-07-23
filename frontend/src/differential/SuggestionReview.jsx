import React from 'react';
import { ChevronLeft, ChevronRight, Check, X, PenTool, Layers } from 'lucide-react';
import { markDisplay } from './markStaging';
import { roleLabel, ROLE_VOCABULARY } from './visualMarks';
import { editablePoints } from './handleEditing';

/**
 * SuggestionReview — the suggestion review surface (CIRCUIT-001 P4-B, 2a/2b/2d/2e).
 *
 * When a model proposes dozens of marks, Accept/Dismiss one-at-a-time trains blind
 * acceptance — the exact failure the quarantine exists to prevent. This surface makes
 * reviewing FAST, EDITABLE, and HONEST:
 *
 *   - one suggestion at a time, reviewed IN ORDER (n/p to cycle, a accept, d dismiss);
 *   - each row shows `markDisplay`'s honest descriptor — role, provenance label,
 *     producer, "suggested" state, citability — so a decision is never made blind (2e);
 *   - EDIT-BEFORE-ACCEPT (2b): role/label via the pickers, geometry via the handles;
 *     the accept mints a `user_confirmed` mark with the edits, `derived_from` the
 *     suggestion, which is preserved un-edited — the Label Studio pattern;
 *   - BULK HONESTY (2d): "Dismiss all" is one button (refusal needs no ceremony); there
 *     is NO accept-all button — accepting many is the a-rhythm, one glance per item,
 *     never a silent batch. A dismiss reason is one optional keystroke, skippable.
 *
 * A thin VIEW: all state (index, staged edit) and the quarantine calls live in the
 * workspace; this turns clicks/props into callbacks. Geometry editing is delegated
 * upward (the handles live on the stage).
 */

// One-keystroke, skippable dismiss reasons — recorded when given, never required.
const DISMISS_REASONS = ['wrong place', 'not real', 'duplicate', 'too coarse'];

export default function SuggestionReview({
    suggestions = [],
    index = 0,
    edit = {},                 // { role?, label?, points? } — staged, never mutates the suggestion
    dismissReason = null,
    onPrev, onNext, onAccept, onDismiss, onDismissAll,
    onSetRole, onSetLabel, onEditGeometry, onSetDismissReason,
    geometryEditing = false,   // true while the stage handles are open for this suggestion
}) {
    const total = suggestions.length;
    if (!total) return null;
    const i = Math.max(0, Math.min(index, total - 1));
    const s = suggestions[i];
    const d = markDisplay(s);
    if (!d) return null;

    const roleKeys = ROLE_VOCABULARY[s.type] || [];
    const stagedRole = edit.role ?? s.role;
    const stagedLabel = edit.label ?? s.label ?? '';
    const hasGeometryEdit = !!edit.points;
    const editable = !!editablePoints(s);
    const producer = s.provenance?.model || null;
    // Our edits keep the geometry KIND, so acceptance stays user_confirmed (citable).
    // Only a kind-change would be model_refined (uncitable) — which this UX never does.
    const edited = edit.role != null || edit.label != null || hasGeometryEdit;

    return (
        <section className="diff-insp-section diff-review" aria-label="Suggestion review">
            <div className="diff-review-head">
                <span className="diff-eyebrow">Reviewing model output</span>
                <span className="diff-review-count" aria-live="polite">{i + 1} / {total}</span>
            </div>

            {/* the honest descriptor — a decision is never made blind (2e) */}
            <div className="diff-review-card">
                <div className="diff-review-provrow">
                    <span className="diff-chip diff-mark-prov-chip is-model">{d.provenance}</span>
                    <span className="diff-review-status">{d.status_label}</span>
                </div>
                <div className="diff-review-meta">
                    <span className="diff-review-role-label">{d.role_label || 'no role'}</span>
                    {producer && <span className="diff-review-producer">· {producer}</span>}
                    {d.needs_geometry && <span className="diff-review-warn">· needs geometry</span>}
                    <span className={`diff-review-citable${d.citable ? '' : ' is-no'}`}>
                        · {d.citable ? 'citable once accepted' : 'not yet citable'}
                    </span>
                </div>

                {/* edit-before-accept (2b) — role picker */}
                {roleKeys.length > 0 && (
                    <div className="diff-review-roles" role="radiogroup" aria-label="Role">
                        {roleKeys.map((rk) => (
                            <button key={rk} type="button" role="radio" aria-checked={stagedRole === rk}
                                className={`diff-subtool diff-role-chip${stagedRole === rk ? ' on' : ''}`}
                                onClick={() => onSetRole?.(rk)}>{roleLabel(s.type, rk)}</button>
                        ))}
                    </div>
                )}

                {/* edit-before-accept (2b) — label */}
                <input className="diff-review-label" placeholder="Name it (optional)…"
                    value={stagedLabel} onChange={(e) => onSetLabel?.(e.target.value)} />

                {/* edit-before-accept (2b) — geometry, via the stage handles */}
                {editable && (
                    <button type="button"
                        className={`diff-quiet diff-review-geo${geometryEditing ? ' on' : ''}`}
                        onClick={() => onEditGeometry?.()}>
                        <PenTool size={13} /> {geometryEditing ? 'editing shape…' : hasGeometryEdit ? 'shape edited — adjust again' : 'Adjust shape'}
                    </button>
                )}

                {edited && (
                    <p className="diff-review-edited" role="status">
                        Edited — accepting mints <strong>your</strong> version, with the model’s
                        proposal preserved in lineage.
                    </p>
                )}
            </div>

            {/* review actions — a accept, d dismiss, n/p cycle */}
            <div className="diff-review-actions">
                <button type="button" className="diff-icon-btn" title="Previous (p)" onClick={onPrev} disabled={total < 2}>
                    <ChevronLeft size={15} />
                </button>
                <button type="button" className="diff-primary diff-review-accept" onClick={onAccept} title="Accept (a)">
                    <Check size={13} /> Accept
                </button>
                <button type="button" className="diff-quiet diff-review-dismiss" onClick={() => onDismiss?.()} title="Dismiss (d)">
                    <X size={13} /> Dismiss
                </button>
                <button type="button" className="diff-icon-btn" title="Next (n)" onClick={onNext} disabled={total < 2}>
                    <ChevronRight size={15} />
                </button>
            </div>

            {/* optional dismiss reason — one keystroke, skippable, recorded when given */}
            <div className="diff-review-reasons" aria-label="Dismiss reason (optional)">
                {DISMISS_REASONS.map((r) => (
                    <button key={r} type="button"
                        className={`diff-review-reason${dismissReason === r ? ' on' : ''}`}
                        onClick={() => onSetDismissReason?.(dismissReason === r ? null : r)}>{r}</button>
                ))}
            </div>

            {/* bulk (2d) — dismiss-all is one button (refusal needs no ceremony); there is
                NO accept-all button — accepting many is the a-rhythm, a glance per item. */}
            <div className="diff-review-bulk">
                <span className="diff-review-bulk-hint"><Layers size={12} /> Accept all = press <kbd>a</kbd> through each — a glance per mark.</span>
                <button type="button" className="diff-quiet diff-review-dismiss-all" onClick={onDismissAll}>
                    Dismiss all {total}
                </button>
            </div>
        </section>
    );
}
