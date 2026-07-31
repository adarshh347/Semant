import { readFileSync } from 'node:fs';
import { describe, it, expect } from 'vitest';
import {
    acceptSuggestion, dismissSuggestion, quarantineSuggestion, canCiteMark, isSuggestion,
} from './suggestionQuarantine';
import * as Quarantine from './suggestionQuarantine';
import { makeVisualMark, isPersistableMark } from './visualMarks';
import { markDisplay } from './markStaging';
import { withEditedPoints } from './handleEditing';

/**
 * CIRCUIT-001 P4-B — suggestion review, contract conformance. These exercise the REAL
 * Lane A4 quarantine along the exact paths the workspace's review handlers use, so they
 * prove the honest-review guarantees without mounting the full workspace (jsdom has no
 * layout — the review UI wiring is covered by suggestionReview.dom).
 *
 * The rule this gate serves: acceptance must stay a decision — fast, never automatic.
 */

const WS = readFileSync(new URL('./DifferentialWorkspace.jsx', import.meta.url), 'utf8');

const traceSugg = (id = 'vm_x') => quarantineSuggestion(makeVisualMark('trace_mark', {
    id, role: 'gaze_address', label: 'a line the model proposes', source: 'model_suggested',
    geometry: { kind: 'polyline', points: [[0.2, 0.2], [0.8, 0.8]] },
    provenance: { model: 'planner-x' },
}));

// ── 2b — edit-before-accept: the Label Studio pattern ─────────────────────────
describe('2b — edit-before-accept mints the curator’s version, preserves the proposal', () => {
    it('staged role/label/geometry ride into a user_confirmed derived mark; suggestion untouched', () => {
        const sugg = traceSugg();
        const before = structuredClone(sugg);
        // exactly the edits object the workspace's acceptCurrentSuggestion builds:
        const points = [[0.25, 0.25], [0.85, 0.85]];
        const edits = { role: 'gesture', label: 'my line', geometry: withEditedPoints(sugg, points).geometry };
        const out = acceptSuggestion(sugg, edits);
        expect(out).not.toBeNull();
        expect(out.accepted.derived_from).toBe(sugg.id);   // lineage points back
        expect(out.accepted.role).toBe('gesture');
        expect(out.accepted.label).toBe('my line');
        expect(out.accepted.geometry.points).toEqual(points);
        expect(out.accepted.status).toBe('committed');
        // same geometry KIND → user_confirmed → CITABLE (the UX keeps the kind on purpose)
        expect(out.accepted.source).toBe('user_confirmed');
        expect(canCiteMark(out.accepted)).toBe(true);
        // the suggestion is returned byte-identical, and the input object is not mutated
        expect(out.suggestion).toEqual(before);
        expect(sugg).toEqual(before);
    });

    it('a geometry KIND change accepts as model_refined (not citable) — why the UX keeps the kind', () => {
        const sugg = traceSugg();
        const out = acceptSuggestion(sugg, { geometry: { kind: 'freehand_path', strokes: [{ points: [[0.3, 0.3]], radius: 0.05, op: 'add' }] } });
        expect(out.accepted.source).toBe('model_refined');
        expect(canCiteMark(out.accepted)).toBe(false);
    });

    it('accepting with NO edits still mints user_confirmed from the suggestion', () => {
        const sugg = traceSugg();
        const out = acceptSuggestion(sugg);
        expect(out.accepted.role).toBe('gaze_address');
        expect(out.accepted.source).toBe('user_confirmed');
        expect(canCiteMark(out.accepted)).toBe(true);
    });
});

// ── 2d — bulk honesty: accepting many is a rhythm, never a silent batch ────────
describe('2d — acceptance stays one-at-a-time; only dismissal may be bulk', () => {
    it('the quarantine exposes no batch-accept — one accept commits exactly one mark', () => {
        expect(Quarantine.acceptAll).toBeUndefined();
        expect(Quarantine.acceptSuggestions).toBeUndefined();
        const a = acceptSuggestion(traceSugg('vm_a'));
        const b = acceptSuggestion(traceSugg('vm_b'));
        expect(a.accepted.id).not.toBe(b.accepted.id);   // two calls → two distinct marks
    });

    it('the workspace has no accept-all function — only a per-item accept and a bulk dismiss', () => {
        expect(WS).not.toMatch(/acceptAll|acceptAllSuggestions|accept_all/);
        expect(WS).toMatch(/const acceptCurrentSuggestion = useCallback/);   // one at a time
        expect(WS).toMatch(/const dismissAllSuggestions = useCallback/);     // refusal may be bulk
        // and the surface advertises the a-rhythm, not a batch button
        const REVIEW = readFileSync(new URL('./SuggestionReview.jsx', import.meta.url), 'utf8');
        expect(REVIEW).not.toMatch(/onAcceptAll/);
        expect(REVIEW).toMatch(/a glance per mark/);
    });
});

// ── dismissed suggestions never persist, never cite ───────────────────────────
describe('dismissed suggestions are kept but never citable or persisted', () => {
    it('dismiss → status dismissed, not citable, not persistable, dropped from pending', () => {
        const d = dismissSuggestion(traceSugg());
        expect(d.status).toBe('dismissed');
        expect(canCiteMark(d)).toBe(false);
        expect(isPersistableMark(d)).toBe(false);
        // isSuggestion stays true (source is still model_suggested) — the pending filter
        // excludes it by status, exactly as the workspace's pendingSuggestions does.
        expect(isSuggestion(d)).toBe(true);
        const pending = [d].filter((m) => isSuggestion(m) && m.status !== 'dismissed');
        expect(pending).toHaveLength(0);
    });
});

// ── 2e — provenance visible in every review row ───────────────────────────────
describe('2e — every row carries an honest provenance descriptor', () => {
    it('markDisplay gives provenance, status label, citability and suggestion flag', () => {
        const d = markDisplay(traceSugg());
        expect(d.provenance).toBe('Model suggestion — not accepted');
        expect(d.is_suggestion).toBe(true);
        expect(d.citable).toBe(false);
        expect(d.status_label.toLowerCase()).toContain('suggested');
        expect(d.role_label).toBe('Gaze / address');
    });
});

// ── 2a / 2c — the review surface + SAM preview are wired the honest way ────────
describe('2a/2c — wiring guards', () => {
    it('review keyboard (n/p/a/d) is wired and precedes tool shortcuts', () => {
        expect(WS).toMatch(/if \(review && !editing\)/);
        expect(WS).toMatch(/reviewNext\(\); return;/);
        expect(WS).toMatch(/acceptCurrentSuggestion\(\); return;/);
        expect(WS).toMatch(/dismissCurrentSuggestion\(\); return;/);
    });

    it('editing a suggestion stages into review.edit — never mutates the suggestion', () => {
        expect(WS).toMatch(/editing\.target === '__suggestion__'/);
        expect(WS).toMatch(/edit: \{ \.\.\.rv\.edit, points: editing\.points \}/);
    });

    it('(2c) the SAM preview is routed off RegionOverlay onto the suggestion-layer ghost', () => {
        expect(WS).toMatch(/proposal=\{null\}/);                       // RegionOverlay no longer draws the mask
        expect(WS).toMatch(/<RefineProposalGhost proposal=\{refine\.proposal\}/);
        expect(WS).toMatch(/tool === 'refine' && suggestionLayer\?\.visibility !== false/);
    });

    it('the dismiss-reason P4F gap is marked and worked around additively', () => {
        expect(WS).toMatch(/P4F:/);
        expect(WS).toMatch(/dismiss_reason/);
    });
});
