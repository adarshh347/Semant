import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import SuggestionReview from './SuggestionReview';
import { RefineProposalGhost } from './DifferentialWorkspace';
import { quarantineSuggestion } from './suggestionQuarantine';
import { makeVisualMark } from './visualMarks';

/**
 * CIRCUIT-001 P4-B — the suggestion review surface, and the SAM-preview ghost.
 *
 * The surface is a thin VIEW (state lives in the workspace); here we prove the DOM
 * wiring: every row shows the honest descriptor (2e), the pickers/handles stage edits
 * (2b), the actions fire the right callbacks, and — the load-bearing honesty check (2d)
 * — there is NO accept-all control, only a dismiss-all button and the a-rhythm hint.
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const traceSugg = (id, role = 'gaze_address', label = 'a line the model proposes') =>
    quarantineSuggestion(makeVisualMark('trace_mark', {
        id, role, label, source: 'model_suggested',
        geometry: { kind: 'polyline', points: [[0.2, 0.2], [0.8, 0.8]] },
        provenance: { model: 'planner-x' },
    }));
const fieldSugg = (id) =>
    quarantineSuggestion(makeVisualMark('brush_field', {
        id, role: 'light_field', source: 'model_suggested',
        geometry: { kind: 'freehand_path', strokes: [{ points: [[0.3, 0.3]], radius: 0.05, op: 'add' }] },
        provenance: { model: 'planner-x' },
    }));

const text = () => container.textContent;
const btn = (re) => [...container.querySelectorAll('button')].find((b) => re.test(b.textContent));

describe('SuggestionReview — the review surface', () => {
    const three = [traceSugg('vm_1'), traceSugg('vm_2', 'gesture'), traceSugg('vm_3')];

    it('(2e) every row shows the honest descriptor — provenance, role, producer, status', async () => {
        await mount(<SuggestionReview suggestions={three} index={0} edit={{}} />);
        expect(container.querySelector('.diff-mark-prov-chip').textContent).toBe('Model suggestion — not accepted');
        expect(text()).toContain('Gaze / address');   // role_label (CSS capitalizes on screen)
        expect(text()).toContain('planner-x');          // producer (provenance.model)
        expect(text()).toContain('1 / 3');              // review position
        expect(text().toLowerCase()).toContain('suggested mark');   // status_label
        expect(text().toLowerCase()).toContain('not yet citable');
    });

    it('(2b) role chip and label input stage edits via callbacks', async () => {
        const onSetRole = vi.fn(); const onSetLabel = vi.fn();
        await mount(<SuggestionReview suggestions={three} index={0} edit={{}} onSetRole={onSetRole} onSetLabel={onSetLabel} />);
        const gestureChip = [...container.querySelectorAll('.diff-role-chip')].find((b) => /gesture/i.test(b.textContent));
        await act(async () => { gestureChip.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onSetRole).toHaveBeenCalledWith('gesture');
        const input = container.querySelector('.diff-review-label');
        // React tracks controlled-input value via a descriptor — set through the native
        // setter so the synthetic onChange fires (the standard jsdom workaround).
        const nativeSet = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        await act(async () => {
            nativeSet.call(input, 'my name');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        expect(onSetLabel).toHaveBeenCalledWith('my name');
    });

    it('(2b) "Adjust shape" shows for editable geometry, hidden for a field of strokes', async () => {
        const onEditGeometry = vi.fn();
        await mount(<SuggestionReview suggestions={three} index={0} edit={{}} onEditGeometry={onEditGeometry} />);
        const geo = btn(/adjust shape/i);
        expect(geo).toBeTruthy();
        await act(async () => { geo.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onEditGeometry).toHaveBeenCalled();

        await mount(<SuggestionReview suggestions={[fieldSugg('vm_f')]} index={0} edit={{}} onEditGeometry={onEditGeometry} />);
        expect(btn(/adjust shape/i)).toBeFalsy();   // strokes are not point-editable
    });

    it('an edited suggestion shows the "mints your version" honesty note', async () => {
        await mount(<SuggestionReview suggestions={three} index={0} edit={{ role: 'gesture' }} />);
        expect(text().toLowerCase()).toContain('preserved in lineage');
    });

    it('accept / dismiss / next / prev fire their callbacks', async () => {
        const onAccept = vi.fn(); const onDismiss = vi.fn(); const onNext = vi.fn(); const onPrev = vi.fn();
        await mount(<SuggestionReview suggestions={three} index={1} edit={{}}
            onAccept={onAccept} onDismiss={onDismiss} onNext={onNext} onPrev={onPrev} />);
        btn(/accept/i).dispatchEvent(new MouseEvent('click', { bubbles: true }));
        btn(/^.*dismiss$/i) && btn(/dismiss/i).dispatchEvent(new MouseEvent('click', { bubbles: true }));
        expect(onAccept).toHaveBeenCalledTimes(1);
        expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it('(2d) there is a Dismiss-all button but NO accept-all control', async () => {
        const onDismissAll = vi.fn();
        await mount(<SuggestionReview suggestions={three} index={0} edit={{}} onDismissAll={onDismissAll} />);
        const dismissAll = btn(/dismiss all/i);
        expect(dismissAll).toBeTruthy();
        await act(async () => { dismissAll.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onDismissAll).toHaveBeenCalledTimes(1);
        // the honesty rule: no single control accepts the batch — only the a-rhythm hint
        const acceptAllButton = [...container.querySelectorAll('button')].find((b) => /accept all/i.test(b.textContent));
        expect(acceptAllButton).toBeUndefined();
        expect(text().toLowerCase()).toContain('a glance per mark');
    });

    it('(2d) optional dismiss reasons are one skippable keystroke', async () => {
        const onSetDismissReason = vi.fn();
        await mount(<SuggestionReview suggestions={three} index={0} edit={{}} onSetDismissReason={onSetDismissReason} />);
        const reason = [...container.querySelectorAll('.diff-review-reason')].find((b) => /not real/i.test(b.textContent));
        expect(reason).toBeTruthy();
        await act(async () => { reason.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
        expect(onSetDismissReason).toHaveBeenCalledWith('not real');
    });
});

describe('RefineProposalGhost — the SAM preview on the suggestion layer (2c)', () => {
    const NAT = { w: 1000, h: 1000 };
    const proposal = { polygons: [[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]], confidence: 0.9 };

    it('renders a distinct dashed teal mask when a proposal has polygons', async () => {
        await mount(<RefineProposalGhost proposal={proposal} natural={NAT} />);
        const path = container.querySelector('.diff-refine-ghost path');
        expect(path).not.toBeNull();
        expect(path.getAttribute('stroke-dasharray')).toBeTruthy();   // dashed = a preview, not committed
        expect(path.getAttribute('d')).toContain('M');
    });

    it('renders nothing without a proposal (no ad-hoc overlay)', async () => {
        await mount(<RefineProposalGhost proposal={null} natural={NAT} />);
        expect(container.querySelector('.diff-refine-ghost')).toBeNull();
    });
});
