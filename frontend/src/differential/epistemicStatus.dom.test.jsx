/**
 * CIRCUIT-003 M5 — the epistemic tag, carried through the circuit and shown in review.
 *
 * The backend classifies; the frontend must not lose the classification on the way to the
 * reviewer, and must not quietly change it when the reviewer accepts. Both halves are tested
 * here, plus the display itself — a tag nobody can see is the CVAT lesson repeating with a
 * different field.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import SuggestionReview from './SuggestionReview';
import { markDisplay } from './markStaging';
import { suggestionFromDescriptor, acceptSuggestion } from './suggestionQuarantine';
import { normalizeMark, EPISTEMIC_STATUSES, EPISTEMIC_LABEL } from './visualMarks';

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => {
    container = document.createElement('div'); document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const descriptor = (over = {}) => ({
    producer: 'material_field',
    type: 'brush_field',
    role: 'material_field',
    label: 'same material',
    source_ref: 'r1@2:3',
    geometry: { kind: 'soft_mask', strokes: [{ points: [[0.5, 0.5]], radius: 0.05 }] },
    linked_ground_ids: [],
    provenance: { model: 'dinov2', adapter: 'dinov2_vits14', run_id: 'run1', producer: 'material_field' },
    epistemic_status: 'measured',
    ...over,
});

// ── the vocabulary matches the backend's, string for string ─────────────────

describe('the vocabulary', () => {
    it('is the same five the backend classifies with', () => {
        expect([...EPISTEMIC_STATUSES].sort()).toEqual(
            ['interpretive', 'measured', 'sourced', 'uncertain', 'visible']);
    });

    it('labels every one of them', () => {
        EPISTEMIC_STATUSES.forEach((s) => expect(EPISTEMIC_LABEL[s]).toBeTruthy());
    });
});

// ── ingest: the classification survives the trip ────────────────────────────

describe('ingest carries the producer’s classification', () => {
    it('rides through onto the quarantined mark', () => {
        const s = suggestionFromDescriptor(descriptor());
        expect(s.epistemic_status).toBe('measured');
    });

    it.each(EPISTEMIC_STATUSES)('carries %s unchanged', (status) => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: status }));
        expect(s.epistemic_status).toBe(status);
    });

    it('leaves a curator’s own mark untagged rather than guessing', () => {
        const m = normalizeMark({ type: 'brush_field', role: 'rhythm', source: 'user',
            geometry: { kind: 'soft_mask', strokes: [] } });
        expect(m.epistemic_status).toBe(null);
    });

    it('refuses a mark carrying a status outside the vocabulary', () => {
        expect(normalizeMark({ type: 'brush_field', role: 'rhythm', source: 'user',
            geometry: { kind: 'soft_mask', strokes: [] },
            epistemic_status: 'obvious' })).toBe(null);
    });
});

// ── the wall at acceptance ──────────────────────────────────────────────────

describe('accepting does not change what kind of claim it is', () => {
    it('preserves the tag when a suggestion becomes a user_confirmed mark', () => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: 'interpretive' }));
        const { accepted } = acceptSuggestion(s, {});
        expect(accepted.source).toBe('user_confirmed');
        // Accepting says "keep this". It does not turn a reading into an extent.
        expect(accepted.epistemic_status).toBe('interpretive');
    });

    it('preserves it through an edit-before-accept too', () => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: 'uncertain' }));
        const { accepted } = acceptSuggestion(s, { label: 'my words', role: 'material_field' });
        expect(accepted.label).toBe('my words');
        expect(accepted.epistemic_status).toBe('uncertain');
    });

    it('keeps a sourced claim sourced after acceptance', () => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: 'sourced' }));
        const { accepted } = acceptSuggestion(s, {});
        expect(accepted.epistemic_status).toBe('sourced');
    });
});

// ── the display descriptor both surfaces render from ────────────────────────

describe('markDisplay surfaces the tag', () => {
    it('exposes the status, a label and a one-line hint', () => {
        const d = markDisplay(suggestionFromDescriptor(descriptor()));
        expect(d.epistemic_status).toBe('measured');
        expect(d.epistemic_label).toBe('measured');
        expect(d.epistemic_hint).toMatch(/signal/i);
    });

    it('says nothing at all for an untagged mark', () => {
        const d = markDisplay(normalizeMark({ type: 'brush_field', role: 'rhythm', source: 'user',
            geometry: { kind: 'soft_mask', strokes: [] } }));
        expect(d.epistemic_status).toBe(null);
        expect(d.epistemic_label).toBe(null);
    });
});

// ── the review shows it ─────────────────────────────────────────────────────

describe('SuggestionReview shows the five-way tag', () => {
    const renderOne = async (status) => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: status }));
        await mount(<SuggestionReview suggestions={[s]} index={0} />);
    };

    it.each(EPISTEMIC_STATUSES)('renders the %s chip, legibly', async (status) => {
        await renderOne(status);
        const chip = container.querySelector(`[data-epistemic="${status}"]`);
        expect(chip).toBeTruthy();
        // The WORD carries the meaning — a reviewer must not need the colour to read it.
        expect(chip.textContent.trim()).toBe(EPISTEMIC_LABEL[status]);
        expect(chip.getAttribute('title')).toBeTruthy();       // the legend, on hover
    });

    it('shows the tag alongside provenance, not instead of it', async () => {
        await renderOne('interpretive');
        expect(container.textContent).toContain('Model suggestion');
        expect(container.querySelector('[data-epistemic="interpretive"]')).toBeTruthy();
    });

    it('offers no control to change the tag — it is the producer’s, not the reviewer’s', async () => {
        await renderOne('uncertain');
        const chip = container.querySelector('[data-epistemic="uncertain"]');
        expect(chip.tagName).toBe('SPAN');                     // not a button, not an input
        expect(container.querySelectorAll('[data-epistemic]').length).toBe(1);
    });

    it('renders nothing where a mark carries no tag', async () => {
        const s = suggestionFromDescriptor(descriptor({ epistemic_status: null }));
        await mount(<SuggestionReview suggestions={[s]} index={0} />);
        expect(container.querySelector('[data-epistemic]')).toBe(null);
    });
});
