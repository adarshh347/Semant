import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import RegisterPanel from './RegisterPanel';
import DepthView from './DepthView';

/**
 * Semant Writer · W10 — registers at the surface (gate step 8).
 *
 * Two absences carry this file, and both are places the surface would break the rule the
 * backend cannot:
 *
 *   THE EMPTY STATE PRE-FILLS NOTHING. A fresh project shows no registers. The classic
 *   ladder sits behind a button that says what it is, and adopting it loads rows into the
 *   FORM — nothing is stored until the author declares. A seeded list would be
 *   indistinguishable from a decision they made.
 *
 *   THE DEPTH VIEW NEVER READS THE BOOK. It shows which layers a span was MADE at and
 *   never what it means at them. A confident paragraph about a chapter's philosophical
 *   dimension sounds like insight rather than invention, which is why it must not exist.
 */

const LADDER = [
  { name: 'weather', description: 'what the room is doing', order: 0 },
  { name: 'interior', description: 'what she will not say', order: 1 },
];

const TEMPLATE = {
  committed: false,
  template: 'classic',
  registers: [
    { name: 'surface', description: 'what literally happens' },
    { name: 'psychological', description: 'what it does to the people in it' },
    { name: 'philosophical', description: 'what it is about' },
  ],
  note: 'A common ladder, offered as a starting point and nothing more.',
};

const VIEW = (over = {}) => ({
  vocabulary: LADDER,
  spans: [
    {
      lineage_id: 'lin_1', version: 1, block_id: 'b1', scene_id: 's1',
      registers: ['weather'], text: 'The frost held the window.',
    },
    {
      lineage_id: 'lin_2', version: 1, block_id: 'b2', scene_id: 's1',
      registers: [], text: 'She had written this sentence herself.',
    },
  ],
  by_register: { weather: ['lin_1@v1'], interior: [] },
  untagged: ['lin_2@v1'],
  ...over,
});

let container, root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(element) {
  await act(async () => { root.render(element); });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];
const setInput = async (el, value) => {
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
      .set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  });
};

// ══ NO IMPOSED TAXONOMY, at the surface ════════════════════════════════════

describe('declaring your layers', () => {
  const panel = (over = {}) => (
    <RegisterPanel
      onLoad={vi.fn().mockResolvedValue({ registers: [] })}
      onDeclare={vi.fn()}
      onLoadTemplate={vi.fn().mockResolvedValue(TEMPLATE)}
      {...over}
    />
  );

  it('a fresh project shows no registers and pre-fills nothing', async () => {
    await mount(panel());
    expect(byTestId('registers-empty')).not.toBeNull();
    expect(allByTestId('register-row')).toHaveLength(0);
    // and the classic ladder's words are nowhere on screen until asked for
    for (const word of ['surface', 'psychological', 'philosophical']) {
      expect(container.textContent.toLowerCase()).not.toContain(word);
    }
  });

  it('says plainly that nothing has been chosen for them', async () => {
    await mount(panel());
    expect(byTestId('registers-empty').textContent).toContain('nothing has been chosen');
  });

  it('adopting the template loads it into the FORM and stores nothing', async () => {
    const onDeclare = vi.fn();
    await mount(panel({ onDeclare }));
    await act(async () => { byTestId('adopt-template').click(); });

    expect(allByTestId('register-row')).toHaveLength(3);
    expect(byTestId('registers-status').textContent).toContain('Nothing is saved yet');
    expect(onDeclare).not.toHaveBeenCalled();
  });

  it('the adopted template is fully editable before declaring', async () => {
    const onDeclare = vi.fn().mockResolvedValue({ registers: [] });
    await mount(panel({ onDeclare }));
    await act(async () => { byTestId('adopt-template').click(); });

    await setInput(allByTestId('register-name')[0], 'weather');
    await act(async () => { allByTestId('register-remove')[2].click(); });
    await act(async () => { byTestId('registers-declare').click(); });

    expect(onDeclare).toHaveBeenCalledWith([
      { name: 'weather', description: 'what literally happens' },
      { name: 'psychological', description: 'what it does to the people in it' },
    ]);
  });

  it('the author sets the order, and the panel does not sort for them', async () => {
    const onDeclare = vi.fn().mockResolvedValue({ registers: [] });
    await mount(panel({
      onLoad: vi.fn().mockResolvedValue({ registers: LADDER }), onDeclare,
    }));

    await act(async () => { allByTestId('register-down')[0].click(); });
    await act(async () => { byTestId('registers-declare').click(); });

    expect(onDeclare.mock.calls[0][0].map((r) => r.name)).toEqual(['interior', 'weather']);
  });

  it('a layer can be added and named from nothing', async () => {
    const onDeclare = vi.fn().mockResolvedValue({ registers: [] });
    await mount(panel({ onDeclare }));
    await act(async () => { byTestId('register-add').click(); });
    await setInput(byTestId('register-name'), 'inheritance');
    await act(async () => { byTestId('registers-declare').click(); });

    expect(onDeclare).toHaveBeenCalledWith([{ name: 'inheritance', description: '' }]);
  });

  it('surfaces a refused declaration instead of swallowing it', async () => {
    const onDeclare = vi.fn().mockRejectedValue(
      new Error("cannot drop a register that operators still carry"));
    await mount(panel({
      onLoad: vi.fn().mockResolvedValue({ registers: LADDER }), onDeclare,
    }));
    await act(async () => { byTestId('registers-declare').click(); });

    expect(byTestId('registers-error').textContent).toContain('still carry');
  });
});

// ══ NO INTERPRETATION, at the surface ══════════════════════════════════════

describe('the depth view', () => {
  const view = (over = {}) => (
    <DepthView onLoad={vi.fn().mockResolvedValue(VIEW())} {...over} />
  );

  it('shows which layers a span was made at', async () => {
    await mount(view());
    expect(allByTestId('depth-span')).toHaveLength(2);
    expect(byTestId('depth-tag').textContent).toBe('weather');
  });

  it('offers the author’s layers as filters, in their order', async () => {
    await mount(view());
    const labels = allByTestId('depth-filter').map((b) => b.textContent);
    expect(labels[0]).toContain('weather');
    expect(labels[1]).toContain('interior');
  });

  it('filtering shows the author their own paragraphs and nothing about them', async () => {
    await mount(view());
    await act(async () => { allByTestId('depth-filter')[0].click(); });

    expect(allByTestId('depth-span')).toHaveLength(1);
    expect(byTestId('depth-span-text').textContent).toBe('The frost held the window.');
  });

  it('an empty layer says so rather than guessing at one', async () => {
    await mount(view());
    await act(async () => { allByTestId('depth-filter')[1].click(); });
    expect(byTestId('depth-empty').textContent).toContain('Nothing you have committed');
  });

  it('a hand-typed span is named as carrying no layer, not assigned one', async () => {
    await mount(view());
    expect(byTestId('depth-untagged').textContent).toContain('no layer recorded');
    expect(allByTestId('depth-tag')).toHaveLength(1);
  });

  it('renders the author’s prose unaltered', async () => {
    const cadenced = 'The frost held.\nShe did not say it.';
    await mount(view({
      onLoad: vi.fn().mockResolvedValue(VIEW({
        spans: [{ lineage_id: 'l', version: 1, registers: ['weather'], text: cadenced }],
        by_register: { weather: ['l@v1'], interior: [] },
      })),
    }));
    expect(byTestId('depth-span-text').textContent).toBe(cadenced);
  });

  it('offers NO reading, analysis or score of any layer', async () => {
    // A confident paragraph about a chapter's philosophical dimension sounds like
    // insight rather than invention, which is exactly why it must not exist.
    await mount(view());
    const labels = [...container.querySelectorAll('button')]
      .map((b) => b.textContent.trim().toLowerCase());
    for (const forbidden of ['interpret', 'read at', 'analyse', 'analyze', 'explain',
      'what this means', 'score', 'rate', 'summar']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
    expect(container.querySelector('.writer-depth').textContent.toLowerCase())
      .not.toContain('interpretation');
  });

  it('says so when there is no ladder to read along', async () => {
    await mount(view({
      onLoad: vi.fn().mockResolvedValue(VIEW({ vocabulary: [], by_register: {} })),
    }));
    expect(byTestId('depth-no-ladder').textContent).toContain('the ladder is yours');
    expect(byTestId('depth-span')).toBeNull();
  });

  it('surfaces a failed load instead of rendering an empty book', async () => {
    await mount(view({ onLoad: vi.fn().mockRejectedValue(new Error('depth unavailable')) }));
    expect(container.textContent).toContain('depth unavailable');
    expect(byTestId('depth-span')).toBeNull();
  });
});
