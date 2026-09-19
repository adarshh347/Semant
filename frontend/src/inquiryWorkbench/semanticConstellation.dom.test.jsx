import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SemanticConstellations from './SemanticConstellations';
import { normalizeSession } from './inquiryContract';
import { selectedAnchor } from './semanticConstellationContract';
import flower from '../../../contracts/samples/inquiry-session.constellation-flower.json';
import branching from '../../../contracts/samples/inquiry-session.constellation-branching.json';

let node, root;
beforeEach(() => { node = document.createElement('div'); document.body.append(node); root = createRoot(node); });
afterEach(async () => { await act(async () => root.unmount()); node.remove(); });
const click = async (el) => act(async () => el.click());
const field = (label) => node.querySelector(`[aria-label="${label}"]`);
const button = (label) => [...node.querySelectorAll('button')].find((b) => b.textContent === label);
async function change(el, value) {
    await act(async () => {
        const proto = el.tagName === 'SELECT' ? window.HTMLSelectElement.prototype
            : el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
        el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
    });
}
async function mount(raw = flower, onWrite = vi.fn()) {
    await act(async () => root.render(<SemanticConstellations session={normalizeSession(raw)}
        onWrite={onWrite} onRefresh={vi.fn()} />));
    return onWrite;
}

describe('preserved thought and structural candidates', () => {
    it.each([flower, branching])('shows intact source beside claims with honest attribution', async (raw) => {
        await mount(raw);
        const row = raw.semantic_constellations.current[0];
        expect(node.textContent).toContain(row.organising_question);
        expect(node.textContent).toContain(row.anchors[0].exact_text);
        expect(node.textContent).toContain('Shared ancestry does not demonstrate semantic coherence');
        expect(node.textContent).toContain('not assessed');
        expect(node.textContent).toContain('Captured before compilation');
        for (const claim of raw.graph.claims) expect(node.textContent).toContain(claim.text);
        expect(node.querySelectorAll('.iw-thought-ref').length).toBeGreaterThan(2);
    });
    it('records human judgment independently with a graph pin and checkpoint', async () => {
        const write = await mount();
        const row = flower.semantic_constellations.current[0];
        await change(field(`Membership ${row.inspection.candidates[0].claim_ref}`), 'confirmed');
        await change(field('Preservation judgment'), 'partly_preserved');
        await change(field('Preservation note'), 'The relation is missing.');
        await change(field('Recovered thought'), 'The intended connection');
        await change(field('Next investigation'), 'Compare separate and grouped passages');
        await change(field('Assessment author'), 'test-person');
        await click(button('Save memberships and human judgment'));
        expect(write).toHaveBeenCalledWith('review', expect.objectContaining({
            expected_checkpoint: flower.checkpoint,
            graph_hash: row.inspection.graph.graph_hash,
            confirmed_claim_refs: [row.inspection.candidates[0].claim_ref],
            judgment: expect.objectContaining({ value: 'partly_preserved', note: 'The relation is missing.' }),
        }), row.constellation_id);
    });
    it('opens an actual source reference without changing the graph', async () => {
        await mount();
        const source = flower.graph.source_units[0];
        await click([...node.querySelectorAll('.iw-thought-ref')].find((b) => b.textContent === source.source_unit_id));
        expect(field('Reference inspection').textContent).toContain(source.exact_quote);
        await click(button('Close reference'));
        expect(field('Reference inspection')).toBeNull();
    });
    it('does not claim a reading exists when its stage was skipped', async () => {
        const raw = structuredClone(flower);
        raw.semantic_constellations.paused = true;
        raw.semantic_constellations.preparation = 'compiler';
        await mount(raw);
        expect(node.textContent).toContain('settled without a reading block');
        expect(node.textContent).not.toContain('the image reading is stored');
    });
    it('keeps human input after a write conflict', async () => {
        const write = vi.fn().mockRejectedValue(new Error('session changed'));
        await mount(flower, write);
        await change(field('Preservation note'), 'Keep this note');
        await change(field('Assessment author'), 'test-person');
        await click(button('Save memberships and human judgment'));
        expect(field('Preservation note').value).toBe('Keep this note');
        expect(node.textContent).toContain('session changed');
    });
    it('disables review of stale graph references', async () => {
        const raw = structuredClone(flower);
        raw.semantic_constellations.current[0].graph_stale = true;
        await mount(raw);
        expect(node.textContent).toContain('inspection is stale');
        expect(button('Save memberships and human judgment').disabled).toBe(true);
    });
    it('preserves a selected passage before execution and sends human confirmation', async () => {
        const raw = structuredClone(flower);
        raw.semantic_constellations.current = [];
        raw.semantic_constellations.history = [];
        raw.semantic_constellations.paused = true;
        raw.semantic_constellations.preparation = 'prompt';
        const write = await mount(raw);
        expect(node.textContent).toContain('No thought recorded yet');
        await click(button('Select a passage'));
        await click(button('Use whole passage'));
        await change(field('Organising question'), 'What holds this together?');
        await change(field('Thought author'), 'test-person');
        await click(button('Save and confirm thought'));
        expect(write).toHaveBeenCalledWith('save', expect.objectContaining({
            thought: expect.objectContaining({ confirmed_by: 'test-person', anchors: [expect.objectContaining({
                exact_text: raw.prompt, origin: 'user_prompt', source_id: 'prompt',
            })] }),
        }), undefined);
    });
    it('reports the full oversized count and requests narrowing', async () => {
        const raw = structuredClone(flower);
        const row = raw.semantic_constellations.current[0];
        row.inspection.candidate_count = 12;
        row.inspection.narrowing_required = true;
        await mount(raw);
        expect(node.textContent).toContain('All 12 candidates are shown');
        expect(node.textContent).toContain('at most 8 claims');
    });
    it('converts DOM offsets to Unicode code points without changing source bytes', () => {
        expect(selectedAnchor({ origin: 'user_prompt', source_id: 'prompt', text: 'a🌺bc' }, 1, 4))
            .toEqual({ origin: 'user_prompt', source_id: 'prompt', span: [1, 3], exact_text: '🌺b' });
    });
});
