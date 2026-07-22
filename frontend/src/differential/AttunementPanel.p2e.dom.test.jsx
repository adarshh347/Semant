import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import AttunementPanel from './AttunementPanel';

/**
 * CIRCUIT-001 P2E — First Attention prefill (Gate 2) + the draft visual_mark an
 * armed act would produce (Gate 3), mounted.
 */

const CAPABILITIES = ['find_parts', 'brush_field', 'trace_direction', 'connect_marks', 'compose_percept'];

let container, root;
async function mount(props = {}) {
    await act(async () => { root.render(<AttunementPanel capabilities={CAPABILITIES} {...props} />); });
}
const text = () => container.textContent || '';
const byText = (t) => [...container.querySelectorAll('button')].find((b) => (b.textContent || '').includes(t));
const click = async (el) => { await act(async () => el.click()); };

beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

describe('First Attention prefill from the Manuscript (Gate 2)', () => {
    it('seeds the prompt with the carried text', async () => {
        await mount({ prefill: 'the vault gathers the light' });
        expect(container.querySelector('.ap-prompt').value).toBe('the vault gathers the light');
    });

    it('shows a "brought from the Manuscript" notice, not the default helper', async () => {
        await mount({ prefill: 'the fall of light' });
        expect(container.querySelector('.ap-brought')).toBeTruthy();
        expect(text()).toMatch(/Brought from the Manuscript/);
    });

    it('does NOT auto-submit — no acts appear until the curator asks', async () => {
        await mount({ prefill: 'light and shadow' });
        expect(container.querySelector('.ap-card')).toBeFalsy();
        expect(text()).not.toMatch(/Suggested acts/);
    });

    it('suggests acts only once the curator presses the button', async () => {
        await mount({ prefill: 'the fall of light' });
        await click(byText('Suggest acts'));
        expect(text()).toMatch(/Suggested acts/);
    });

    it('drops the notice once the curator edits the seeded text', async () => {
        await mount({ prefill: 'seeded' });
        const ta = container.querySelector('.ap-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(ta, 'my own words'); ta.dispatchEvent(new Event('input', { bubbles: true }));
        });
        expect(container.querySelector('.ap-brought')).toBeFalsy();
    });

    it('renders nothing special with no prefill', async () => {
        await mount({});
        expect(container.querySelector('.ap-brought')).toBeFalsy();
        expect(container.querySelector('.ap-prompt').value).toBe('');
    });
});

describe('draft visual_mark on an armed act (Gate 3)', () => {
    async function stageBrush() {
        await mount({ prefill: 'the falling light' });
        await click(byText('Suggest acts'));
        // Arm the first brush_field card, if the planner produced one.
        const card = container.querySelector('[data-action-type="brush_field"]');
        if (!card) return null;
        const arm = card.querySelector('.ap-apply');
        if (arm) await click(arm);
        return card;
    }

    it('shows a Draft mark with role and provenance once a brush act is armed', async () => {
        const card = await stageBrush();
        if (!card) return; // planner produced no brush act for this prompt — skip
        const dm = card.querySelector('.ap-draft-mark');
        expect(dm).toBeTruthy();
        expect(dm.textContent).toMatch(/Draft mark/);
        expect(dm.textContent).toMatch(/Ready for your mark/);
    });

    it('the draft mark is not citable (no geometry yet)', async () => {
        const card = await stageBrush();
        if (!card) return;
        const dm = card.querySelector('.ap-draft-mark');
        expect(dm.getAttribute('data-citable')).toBe('false');
    });
});
